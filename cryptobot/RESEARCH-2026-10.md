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

## Addendum, 2026-10-09: two operator proposals and one article, tested

| test | result | verdict |
|---|---|---|
| `btc-beta-hedge-bounce-short`: long BTC sized to the walk-forward beta | hedged Sharpe higher in 2 of 5 years on both universes; the strategy carries about −0.5 BTC beta, the hedge swaps BTC's drift for lower variance | inconclusive |
| `stop-and-reverse`: flip to a long when the short is stopped at +10% (and at +5%) | reversal leg −1.3%/trade on 18 coins (1 of 5 years positive), −4.7% on US-3 (0 of 5, t = −3.9); after a stop the bounce fades and both sides lose | **killed** |
| `near-resolution-capture` (Dan1ro0 article): buy the favourite in the last minutes of a 15-min BTC Up/Down market | 2 min: −0.77% per $ (t −0.21); 1 min: +0.41% per $ (t +0.22); implied and realised probabilities match to within noise | inconclusive |

The article's other structures map to registry entries: fair-value taker
(`polymarket-updown-fair-value`, killed), hedged/temporal pairs
(`polymarket-hedge-to-lock`, killed), maker side
(`polymarket-maker-fair-value`, killed on adverse selection), and
latency (`polymarket-latency`, untested: it is a race against market
makers). The wallets it screenshots are not reproducible from the
public quote; their edge, if real, is queue position and speed.

## Addendum, 2026-10-09 (2): stocks in the same bot, and Fed liquidity

**Instrument.** Kalshi lists a CFTC-regulated S&P 500 perpetual,
`KXUS500PERP` (about $13.7 a contract, ~$6.7M a day on 2026-10-08), plus
gold, silver, copper, platinum, palladium and aluminium perps; a Nasdaq
100 perp is listed but inactive. So an index sleeve fits the existing
executor and desk with no new venue. What it does not have is a rule
with evidence: the bounce-short is a memecoin mechanism and does not
transfer, and the sweep's only A-grade index candidate was vol-targeted
trend, a drawdown cutter rather than alpha.

**Fed money injection as a signal** (`fed-liquidity-equities`,
pre-registered, data from FRED H.4.1 series and the FRED S&P / Nasdaq
series): weekly changes in net liquidity (Fed assets − TGA − reverse
repo) do not predict next-week index returns (correlation 0.02–0.17,
t ≤ 0.7 in every era since 2015). The 4-week change has a modest
relation to the next 4 weeks (t 2.5 in 2022–26 on the S&P, 1–2
elsewhere). A long-only "hold after a rise" rule never beats
buy-and-hold on Sharpe by more than 0.01 and gives up about half of
every up year to avoid 2018 and 2022. Inconclusive: a slow regime
variable, not a trading signal. The week of the question illustrates
why: the same week reads as +$82B on the weekly-average TGA series and
−$48B on a daily-TGA measure, and the S&P rose about 1% regardless.

## Addendum, 2026-10-09 (3): the IOC limit, the stop width, and a stock sleeve

**IOC limit, measured instead of guessed.** Walking Kalshi's live books
with the bot's order sizes: $50–$2,000 orders fill 4.3–4.6 bp from mid
on DOGE and SHIB (half the 8–9 bp spread; books of ~$700k a side) and
0.3–1.3 bp on the US500 perp. The shipped config had a 1% limit, twenty
times what the book needs; it is now 0.5%, and the tuner will tighten
it further from real fills. Widening cannot help: the only effect of a
looser limit is to accept a bad print in a fast market.

**Stop width (risk tolerance).** Recorded as `stop-width-risk-tolerance`.
A 20% stop raises the mean and the Sharpe per trade on both universes
(US-3 0.173 → 0.202; 18 coins 0.090 → 0.119) but doubles the size of
every loser and makes the worst year on 18 coins three times deeper
(−15% vs −5.7%); 15% is worse than 10% on both. The deployed 10% stays:
the gain is inside the rule family's noise, and the bot's own Kelly gate
rejects the wider geometries at the registered 35% confidence.

**Stocks.** Two pre-registered candidates, neither earns capital:
Fed net liquidity (`fed-liquidity-equities`, inconclusive: no weekly
signal, a modest monthly one) and vol-targeted trend
(`index-trend-voltarget`, killed as a return source: Sharpe below
buy-and-hold in 3 of 4 Nasdaq eras; it halves drawdowns by halving
returns). The plumbing is in place for when something passes: the
Kalshi executor and data client know the US500 and gold perps (0.001
of the index level a contract, ~$13.7 and ~$4.1; US500 book ~$1.5M a
side, 0.6 bp spread, ~$6.7M a day), and `index_trend_study.py` /
`fedliq_study.py` are the harness for index rules. They are not in any
bot's universe.

## Addendum, 2026-10-09 (4): investigation queue from automated-trading evidence, crypto and stocks

Every candidate below passed, or is listed as failing, the same four
tests: (1) a costed out-of-sample result in a paper or an independent
replication, not a 2020–21 backtest; (2) executable by a US resident on a
venue this desk can reach (Kalshi perps, Coinbase Derivatives, Kraken or
Coinbase spot, listed US options or futures through a US broker);
(3) testable with free data; (4) not already in the registry. Each
queued item has a pre-registered stub in `hypotheses.yaml` with its
success criterion written before the run, per `PREREGISTER.md`.

### Queued, in order

| # | id | asset | rule | evidence | cost on our venue |
|---|---|---|---|---|---|
| 1 | `overnight-index-perp` | stocks | hold the Kalshi US500 perp 16:00→09:30 ET, flat intraday; weekday subsets as named variants | Lou, Polk & Skouras (JFE 2019): strategy returns accrue overnight; 2025 ETF seasonality (Mon→Tue positive, Fri→Mon negative); no post-2019 replication of the full design | 4 bp taker / 2 bp maker a side, 0.6 bp spread, 8-hour funding |
| 2 | `pairs-doge-shib-us` | crypto | daily log-price spread between DOGE and SHIB (PEPE on Coinbase), rolling hedge ratio, enter at z ≥ 2, exit at 0, stop at 4 or 20 days | mixed: one peer-reviewed test lost out of sample at every threshold; a 2026 paper reports BTC-ETH Sharpe 2.4 out of sample without verifiable costs; practitioner repos mostly flat | about 34 bp per pair round trip at Kalshi taker plus half-spread, both legs |
| 3 | `orb-qqq-pilot` | stocks | 5-minute opening-range breakout on QQQ, ATR stop, 1-R target, flat at close; gate for the "stocks in play" version | Zarattini & Aziz (2023) gross reproduced by two replications, net about zero at 2.2 ¢/share; the 2024 stocks-in-play variant's edge comes from relative-volume selection; no 2023–25 out-of-sample record | needs an equity broker API; not executable on the desk's venues |
| 4 | `btc-vrp-listed-options` | crypto | sell 30-day ~25-delta IBIT or CME micro BTC strangles when implied exceeds realised by a margin set in advance | Bitcoin variance risk premium documented on Deribit 2017–22 and found to shrink in high-vol regimes; no evidence on any US-listed instrument; 2025 vendor months show IBIT implied below realised in 3 of 4 months sampled | collect data first: no free history of IBIT option prices; needs an options-approved broker |
| 5 | `pead-revisit` | stocks | buy top-decile earnings surprises at the next open, hold 20 days, short bottom decile | contested: gone in large caps by 2022 per one study, revived in 2025 papers; cost-sensitive in small caps | commission-free single-stock broker plus a free earnings-surprise feed |

Why this order: item 1 needs only daily open/close history and the
executor that is already running, and its criterion is the cost
question (an overnight premium of a few basis points a day survives
only as a maker order or on a weekday subset). Item 2 is the one
crypto structure whose two legs both exist on a US venue, and where
funding on the short leg partly cancels funding on the long leg. Items
3 and 5 need an equity broker and intraday or earnings data the desk
does not have, so a pilot on free QQQ bars decides whether the broker
is worth adding. Item 4 cannot be tested until a year of option prices
has been collected; the collector is cheap, the test is not.

### Found and not queued

- **Short volatility (VIX roll-down, 0DTE, covered calls).** XIV lost
  96% in one session in February 2018; a 2024 working paper finds
  0DTE put ratio spreads with a net Sharpe of 0.93 and baskets near
  0.82 out of sample, but retail 0DTE traders lose 4.7% relative to
  the market (t −10), and Dim, Eraker & Vilkov find the premium high
  and the average gain small. A margin-intensive options book with
  tail risk is not a $250 strategy. Revisit only after item 4's data
  exists, since the infrastructure is the same.
- **Index inclusion.** Greenwood & Sammon (JoF 2025): the inclusion
  return fell from 7.4% in the 1990s to under 1%; a 2025 retail-driven
  rebound has no post-inclusion continuation to trade.
- **Turn of the month.** Maberly & Waggoner (Atlanta Fed, 2000): gone
  from S&P futures after 1990; Liu (2011): concentrated on the first
  trading day, and the switching strategy underperforms buy-and-hold;
  CXO: one of 188 calendar effects persisted across subperiods. Our
  own calendar test on BTC (`btc-offhours-seasonality`) is already
  inconclusive.
- **Crypto cash-and-carry basis, Binance cross-sectional factors,
  Deribit volatility selling, trend as a drawdown cutter:** covered in
  §2 and §6; nothing new since.
- **Overnight-vs-intraday in crypto:** `btc-offhours-seasonality` is
  the crypto analogue and is inconclusive; item 1 is the index version
  on an instrument that trades through the night.

Sources: [Lou, Polk & Skouras, "A tug of war: overnight versus intraday expected returns" (JFE 2019)](https://www.sciencedirect.com/science/article/pii/S0304405X18303008);
[Zarattini & Aziz, "Can Day Trading Really Be Profitable?" (SSRN 4416622)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622);
[Zarattini, Aziz & Barbon, "A Profitable Day Trading Strategy for the U.S. Equity Market" (SSRN 4729284)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284);
[ORB replication on QQQ (giovannibrusco)](https://github.com/giovannibrusco/zarattini-2023-orb-qqq);
[Springer, "On cointegration and cryptocurrency dynamics"](https://link.springer.com/article/10.1007/s42521-021-00027-5);
[IJSRA 2026, cointegration stat-arb BTC-ETH](https://ijsra.net/sites/default/files/fulltext_pdf/IJSRA-2026-0283.pdf);
[crypto-stat-arb (aman3599)](https://github.com/aman3599/crypto-stat-arb);
[pairs-trading-backtester (al7arbi-111)](https://github.com/al7arbi-111/pairs-trading-backtester);
[Survey of statistical arbitrage pairs (WNE UW 2025)](https://www.wne.uw.edu.pl/download_file/6095/0);
[Alexander & Imeraj, "The Bitcoin VIX and Its Variance Risk Premium" (SSRN 3383734)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3383734);
[Almeida, Grith & Miftachov, "Risk Premia in the Bitcoin Market" (arXiv 2410.15195)](https://arxiv.org/pdf/2410.15195);
[IBIT IV/HV history (OptionsAnalysisSuite)](https://www.optionsanalysissuite.com/etf/ibit/iv-hv-history);
[IVolatility on IBIT options](https://www.ivolatility.com/news/3056);
[Maberly & Waggoner, turn-of-the-month in S&P futures (Atlanta Fed WP 2000-11)](https://www.atlantafed.org/research/publications/wp/2000/11.aspx);
[Liu, "The Turn-of-the-Month Anomaly in the Age of ETFs" (JFP 2011)](https://www.financialplanningassociation.org/article/journal/APR11-turn-month-anomaly-age-etfs-reexamination-return-enhancement-strategies);
[CXO Advisory, calendar effects in S&P futures](https://www.cxoadvisory.com/?p=17701);
[Quantpedia, turn of the month in equity indexes](https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes);
[Quantpedia, volatility risk premium effect](https://quantpedia.com/strategies/volatility-risk-premium-effect);
[Dew-Becker, "The decline of the variance risk premium"](https://www.dew-becker.org/documents/synth_opt.pdf).

## Addendum, 2026-10-09 (5): Fidelity, and which broker APIs the equity items need

**Fidelity has no retail API.** Fidelity offers FIX connectivity to
institutions and advisor/workplace integrations, nothing for an
individual account ([TradersPost, Sept 2025](https://blog.traderspost.io/article/does-fidelity-have-an-api);
[FintegrationFS](https://www.fintegrationfs.com/fintechapisusa/fidelity-investments)).
The aggregator [SnapTrade](https://snaptrade.com/brokerage-integrations/fidelity-api)
reads Fidelity positions and balances but states it cannot place
trades. The community libraries
([fidelity-api](https://github.com/kennyboy106/fidelity-api),
[fidelipy](https://github.com/KuphJr/fidelipy)) drive the website with a
Playwright browser, hold the login and 2FA in a script, and are
unsupported; secondary sources say browser scripting breaks Fidelity's
account terms ([TradersPost](https://blog.traderspost.io/article/does-fidelity-allow-trading-bots),
[InvestorTrip](https://www.investortrip.com/reviews/robinhood/automated-trading-systems)).
Fidelity's own agreement text was not retrievable here. Decision: the
executor never drives a Fidelity account. Fidelity stays the human
account; read-only aggregation is worth wiring only if strategy capital
is held there.

**Brokers with an official API, mapped to the queue.**

| broker | API covers | cost (per sources, verify) | fits |
|---|---|---|---|
| Alpaca | US stocks, ETFs, options, crypto; paper trading; free IEX bars | $0 commission ([Alpaca](https://thewearify.com/alpaca-vs-interactive-brokers/)) | `orb-qqq-pilot`, `pead-revisit`; the free bars are the pilot's data source |
| Schwab Trader API (Individual) | stocks, ETFs, options, streaming quotes; no futures listed | free; refresh token expires every 7 days ([TradersPost](https://blog.traderspost.io/article/thinkorswim-api); [schwabr](https://r-packages.io/packages/schwabr)) | same two, plus the options leg of `btc-vrp-listed-options` |
| tastytrade Open API | equities, options, futures and futures options, spot crypto; futures product list queryable ([docs](https://developer.tastytrade.com/api-overview), [orders](https://developer.tastytrade.com/open-api-spec/orders/)) | options $1/contract to open, $0 to close, $10/leg cap ([stockbrokers.com](https://www.stockbrokers.com/compare/interactivebrokers-vs-tastytrade)) | `btc-vrp-listed-options` via IBIT or CME micro BTC options; /MBT presence to be confirmed through the product-list endpoint |
| Interactive Brokers | stocks, options, futures incl. CME micros, 11 crypto coins; TWS/Gateway, Web API, FIX | $0 stocks (US), ~$0.65/option, ~$0.85/futures contract ([stockbrokers.com](https://www.stockbrokers.com/compare/interactivebrokers-vs-tastytrade); [curvedtrading](https://curvedtrading.com/articles/en/reviews/tastytrade-vs-interactive-brokers-options/)) | everything above; the most setup |

Nothing is added now: queue item 1 runs on Kalshi, which is wired. An
Alpaca paper account is the zero-cost step when item 3 or 5 starts.

## Addendum, 2026-10-09 (6): cross-asset regressions (stocks, foreign stocks, rates, dollar, VIX, oil vs crypto)

Pre-registered as `cross-asset-crypto-leadlag`; module
`cryptobot/crossasset_study.py`; 2,818 US business days from 2015-07 to
2026-10. BTC is sampled at 16:00 and 09:00 New York time from Coinbase
hourly bars; stocks and macro series are FRED daily closes; the
memecoin and all-perp baskets are equal-weight Hyperliquid daily closes.
Every regression looked at was counted: 69 trials.

**Same-day comovement is strong and recent.** Correlation of BTC's
16:00-to-16:00 return with each series, by era:

| series | 2015-19 | 2020-21 | 2022-23 | 2024-26 |
|---|---|---|---|---|
| S&P 500 | +0.02 | +0.36 | +0.49 | +0.42 |
| Nasdaq | +0.02 | +0.39 | +0.52 | +0.43 |
| VIX change | −0.04 | −0.37 | −0.42 | −0.38 |
| broad dollar | −0.00 | −0.23 | −0.21 | −0.15 |
| 10y yield change | −0.02 | +0.09 | −0.10 | +0.03 |
| 10y real yield change | −0.04 | +0.02 | −0.14 | −0.02 |
| Nikkei 225 | −0.06 | +0.16 | +0.06 | +0.06 |

By half-year the S&P correlation jumped from about zero to 0.48 in
2020H1, peaked at 0.60–0.64 in 2022H1, dipped to 0.16 in 2023H2 and has
been 0.31–0.57 since. Crypto trades as a high-beta risk asset; rates and
the dollar matter only through that channel; foreign stocks barely
register once the US session is accounted for.

**Nothing leads at the daily horizon.** Newey-West t of the next
period's target on today's predictor, full sample then the last two eras:

| predictor → target | full | 2022-23 | 2024-26 |
|---|---|---|---|
| S&P → BTC next 24h | −1.10 | −1.42 | −1.75 |
| Nasdaq → BTC next 24h | −0.90 | −1.24 | −1.62 |
| 10y real yield → BTC next 5d | −2.57 | −2.02 | −0.60 |
| 10y yield → BTC next 5d | −1.77 | −2.07 | +0.13 |
| breakeven → BTC next 24h | +1.83 | +0.90 | +0.68 |
| anything → memecoin basket | ≤ 1.8 in magnitude | | |
| anything → all-perp basket | ≤ 1.7 (one 2.06 in 2020-21) | | |

The bar was |t| ≥ 2.5 full sample and the same sign at |t| ≥ 1.5 in both
latest eras; nothing clears it. The real-yield relation (BTC falls in
the week after real yields rise) was real in 2020–23 and has faded; the
"BTC follows stocks next day" idea is, if anything, slightly reversed.
Multivariate R² is 0.003–0.03.

**The operator's divergence case.** After a US session with stocks up
more than 0.5% and BTC down more than 0.5% (194 days), BTC's next 24
hours averaged +0.41% (t 1.5): +0.62% in 2015–19, +0.43% in 2020–21,
−0.57% in 2022–23, +0.82% (t 2.3, n 47) in 2024–26. The mirror case
(stocks down, BTC up) averaged +0.52% (t 1.5). Convergence exists on
average, with a sign flip in 2022–23 and a t that does not meet the
bar. It is the one pattern with an economic story, so it is
pre-registered as `divergence-catchup-btc` on out-of-sample days only
(after 2026-10-09; about 15–20 qualifying days a year, so years to
decide). Not traded.

**The reverse direction is comovement, not a lead.** BTC's move from the
US close to 09:00 ET "predicts" that day's S&P close-to-close with t 3.9
(7.9 in 2024–26, correlation 0.21). The S&P close-to-close contains the
overnight futures gap, which BTC moved with; without a free S&P open
series the two cannot be separated, and the Kalshi US500 perp has 76
hours of hourly history, so the intraday test (does the BTC perp lead
the US500 perp hour to hour while the cash market is closed?) waits for
data; `xasset/kalshi_hourly.pkl` is the start of that cache.

**Rules, walk-forward on BTC next-24h at 8 bp (Kalshi BTC perp, 0.0001
BTC a contract, ~$56M a day):** follow-the-S&P sign rule Sharpe −0.42
(net negative in 2024–26, killed as a sub-rule); OLS on stocks only
+0.25 (PSR 0.77); rates and VIX only +0.06; all same-day-known
predictors +0.03 (−0.31 at 20 bp). Best rule's deflated Sharpe at 69
trials: 0.14. Verdict: inconclusive. The desk's baskets do not respond
to any of it with a lag, so no cross-asset filter goes on the
bounce-short either (a filter is one more selected rule).

**Plumbing added:** the Kalshi executor's contract table now knows the
BTC (0.0001) and ETH (0.001) perps for the follow-ups; neither is in
any universe.

## Addendum, 2026-10-09 (7): Kraken Pro as a venue, broker plumbing, and promotion stacking

**Kraken Pro: the API exists, the costs rule it out.** Kraken opened spot
margin to US retail on 2026-05-06 through Kraken Derivatives US, long or
short, with DOGE up to 10x and PEPE and SHIB up to 5x
([launch](https://blog.kraken.com/product/margin/cftc-regulated-spot);
[US margin page](https://support.kraken.com/articles/getting-started-us-margin)).
The global margin list also covers BONK, FLOKI, WIF and others, but the
US retail list does not. The order endpoint takes `leverage`,
`reduce_only` and `validate`
([AddOrder](https://docs.kraken.com/api/docs/rest-api/add-order)), so
the venue is wired (`perp.venue: kraken`). Costs since 2026-07-09: tier 1
pays 0.40% maker and 0.80% taker
([fee schedule](https://www.kraken.com/features/fee-schedule);
[tier change](https://support.kraken.com/in/articles/cross-platform-fee-tier-changes)).
A margin position adds an opening fee and a rollover every 4 hours, each
0.02-0.04% on these coins
([US margin fees](https://support.kraken.com/articles/us-margin-fees)).
That is about 0.18% a day, or 66% a year, which a week-long short cannot
carry. Replay, registry `kraken-margin-venue` (killed):

| venue | mean net per trade | on $250, 2022 / 23 / 24 / 25 / 26 |
|---|---|---|
| Kalshi perps | +1.92% | +8.5 / +9.4 / +27.5 / +49.4 / −0.9% |
| Kraken tier 1, 0.12%/day borrow | −0.56% | −9.5 / −11.1 / −5.5 / +17.5 / −19.1% |
| Kraken tier 1, 0.18%/day (CLI default) | −1.03% | |
| Kraken tier 6 | +0.07% | −4.8 / −6.4 / +4.9 / +25.4 / −15.8% |
| Kraken tier 12, 0.12%/day | +0.85% | +0.8 / +0.1 / +14.7 / +35.4 / −9.7% |

Kraken's US perpetuals are a different product
([launch](https://www.businesswire.com/news/home/20260615010932/en/Kraken-Launches-Perpetual-Futures-for-US-Clients);
[contracts](https://support.kraken.com/articles/us-perpetual-futures)).
They are listed on Bitnomial, include DOGE (PDOGUK) and SHIB (PSHBUN),
cost $0.15 a contract a side
([US futures fees](https://support.kraken.com/articles/us-futures-fees)),
and settle funding daily. If the DOGE contract is the 1,000-coin "Kilo"
size in [Bitnomial's rulebook](https://bitnomial.com/exchange/rulebook/chapter/5/),
about $85, the fee is about 18 bp a side and the replay gives +1.64% per
trade. Two facts are unconfirmed: the contract size, and whether a retail
API key can trade these perpetuals. Neither is documented
([contract specifications](https://support.kraken.com/articles/contract-specifications)),
so no executor is written (`kraken-us-perps-venue`, inconclusive).

One general conclusion: **borrow through a perp, not through spot
margin.** Kraken's rollover costs about 66% a year on memecoins and 33%
on BTC. Kalshi perps cost 4 bp a side plus funding, which has averaged
near zero on these coins.

**Brokers added as plumbing**, none trading on its own:

- **Alpaca:** stocks, ETFs and options, with paper and live endpoints,
  IOC whole-share orders, flattening through the positions endpoint, and
  free IEX bars for the ORB pilot.
- **tastytrade:** OAuth2 token refresh, balances, positions, CME micro
  Bitcoin lookup, and dry-run orders for the options item.
- **`python -m cryptobot.brokers --probe`** reads every account that has
  keys and never places an order.

**Promotions: what "bounce around until maxed" can and cannot do.**
`promo-capture-hedged` in the registry, `python -m cryptobot.promos` for
the arithmetic. No "$250 on a $1,000 buy" offer was live on Kraken on
2026-10-09. The current Kraken referral pays a fixed $20
([support](https://support.kraken.com/articles/kraken-app-referral-program)).
Kraken's deposit matches ran in October 2025 and February 2026 and
carried clawbacks ([Oct terms](https://www.kraken.com/legal/october-deposit-match-terms),
[Feb terms](https://www.kraken.com/legal/february-deposit-match-terms)).
Other live or recent offers:

- **Gemini:** $50 after a $100 trade.
- **Coinbase:** a randomized BTC reward after a first purchase
  ([Finder](https://www.finder.com/cryptocurrency/crypto-bonuses);
  [College Investor](https://thecollegeinvestor.com/37016/best-crypto-bonus-offers/)).
- **Cash-back portals:** a Kraken sign-up through
  [Rakuten](https://www.rakuten.com/shop/kraken) pays on top of the
  referral.
- **Brokerage transfer matches:** 1-4%, with 1-5 year clawbacks and
  "no outflows" terms ([Robinhood](https://robinhood.com/us/en/support/articles/account-transfer-bonus-faq-jax),
  [Public](https://help.public.com/en/articles/6499808-cash-bonus-to-transfer-account),
  [NerdWallet](https://www.nerdwallet.com/best/investing/brokerage-account-promotions-and-bonuses)).
- **Kalshi:** 3.50% variable APY on balances of $250 or more, accrued
  daily on net value ([help](https://help.kalshi.com/en/articles/13823847-apy-on-kalshi)).
  Its page does not say whether perps collateral counts, so the first
  monthly statement will show it.

| offer (hedged where it needs a coin held) | net after costs and 24% tax |
|---|---|
| hypothetical $250 for a $1,000 buy, held 30 days | ~$170 |
| Gemini $50 on a $100 trade | ~$36 |
| Kraken referral $20 | ~$13 |
| 1% transfer match on $10,000, 2-year clawback | ~$76 (0.4% a year) |
| Kalshi APY on the $250 desk balance | ~$7 a year |

The hedge is a same-size perp short. On a 30-day hold it costs about
$11 per $1,000, while an unhedged coin's 30-day standard deviation is
around $140 per $1,000 for BTC and two to three times that for
memecoins. The binding limit is the number of distinct
one-per-person offers, not capital. The total is a one-off few hundred
dollars of ordinary income. What turns it into a terms or legal
problem:

- multiple accounts per person, or someone else's identity
- self-referral
- wash trades to meet a volume requirement (prohibited on CFTC venues,
  Kalshi and Coinbase Derivatives included)
- moving money out during a clawback window, which forfeits the bonus

## Addendum, 2026-10-12 (8): queue item 1 run, the overnight-only index rule

Pre-registered as `overnight-index-perp`, run on 2026-10-12 with
`cryptobot/overnight_study.py`. Data: VTI daily open, close and adjusted
close since 2001 (the free EODHD demo token; dividends recovered from the
adjustment factor and credited to the overnight holder), SPY for the ten
years the Nasdaq data API serves, the Nasdaq-100 index since 1996, and
the Kalshi US500 perp's funding since its listing on 2026-10-06. Stooq
and Yahoo, the sources named in the pre-registration, were unreachable
from the server.

**The premium is real.** Gross, almost all of the index's return accrues
between the close and the next open:

| VTI, annualised log return (Sharpe) | overnight | intraday |
|---|---|---|
| 2001–2007 | +21.6% (2.47) | −16.4% (−1.15) |
| 2008–2014 | −0.6% (−0.02) | −1.8% (−0.10) |
| 2015–2019 | +12.6% (1.53) | −2.0% (−0.18) |
| 2020–2026 | +13.5% (0.99) | +0.5% (0.03) |

SPY and the Nasdaq-100 have the same shape. The literature result
(Lou, Polk & Skouras) replicates through 2026.

**It does not survive the round trip.** The premium is 4–5 basis points
a night; the Kalshi perp costs 8.6 bp a night as a taker (two 4 bp fees
and two 0.3 bp half-spreads) or 4.6 bp as a maker.

| VTI, net per night | 4 bp taker | 2 bp maker |
|---|---|---|
| all nights | −4.0 bp, Sharpe −0.56, beats buy-and-hold 0/4 eras | −0.0 bp, Sharpe −0.00, 1/4 |
| skip Fri→Mon | −4.0 bp, 0/4 | +0.0 bp, 1/4 |
| Mon→Tue only | +1.1 bp, 1/4 | +5.1 bp, Sharpe 0.53, PSR 0.98, 3/4 |

The Mon→Tue maker variant is the only run that clears the pre-registered
bar, and only on VTI: on SPY it beats buy-and-hold in 0 of 2 eras, on the
Nasdaq-100 in 1 of 4, and its deflated Sharpe is 0.54 at the 24 runs
looked at per instrument. That is the selected-variant pattern the
registry's rule exists to catch. The all-nights rule at 2 bp is net
negative on SPY in 2020–2026 and is killed as a trade.

**Funding makes it worse.** The US500 perp's first six daily funding
prints averaged 0.030% a day (median 0.019%), two to four times the
fair basis of about 0.008% (short rates less dividends). A long held
overnight pays it. At the observed median, even the Mon→Tue maker
variant falls to a PSR of 0.92 on VTI and 0.89 on SPY.

**Verdict: inconclusive**, with 72 trials recorded. The rule reopens if
the perp's maker fee drops below about 1 bp or funding settles at or
below the fair basis for a few months. Nothing to build on the
executor: a maker path (resting orders at the close) is only worth
writing for a rule that is alive. The study refetches its own inputs:

```bash
python -m cryptobot.overnight_study --fetch --dir overnight
```

Queue items 2 (DOGE/SHIB pairs) and 3 (ORB pilot on QQQ) are next.
Item 2 needs nothing new. Item 3 needs Alpaca keys for the 5-minute
bars.

## Addendum, 2026-10-12 (9): queue item 2 run, DOGE/SHIB/PEPE spread mean reversion

Pre-registered as `pairs-doge-shib-us`; `cryptobot/pairs_study.py`;
Hyperliquid daily closes 2022–2026 with realised hourly funding from
2023-05. The rule as registered: 90-day rolling hedge ratio, an
Engle–Granger residual test, enter at a 60-day z-score of 2, exit at
zero, stop at 4 or after 20 days, $1 long and $1 short, 8.5 bp per
execution.

| registered rule | trades | mean net / trade | Sharpe | PSR | 2025–26 |
|---|---|---|---|---|---|
| DOGE / SHIB | 13 | +0.06% | +0.04 | 0.51 | −5.3% |
| DOGE / PEPE | 7 | +3.78% | +1.74 | 0.80 | +4.2% |
| SHIB / PEPE | 14 | −5.52% | −1.99 | 0.08 | −20.7% |
| combined | 34 | −1.47% | −0.68 | 0.26 | −21.8% |

By year, combined: +10.9 / −46.0 / +7.0 / −7.3 / −14.5% of one leg's
notional. Sixteen of the 34 trades ended at the stop, usually within
days: when one memecoin runs, the "spread" is a trend, and the
cointegration test that should screen those windows out passes them a
week before they break. The sensitivity grid (entry z of 1.5, 2 or 2.5,
with or without the Engle–Granger filter, 18 trials) has no positive
cell; dropping the filter multiplies the trades by six and keeps the
sign. Funding moved single trades by a percent at most.

**Verdict: killed** (net negative in 2025–2026, the pre-registered kill
condition). The seven DOGE/PEPE trades at +3.8% are the kind of
sub-sample the registry's rule exists to ignore. This agrees with the
peer-reviewed out-of-sample result the sweep found and not with the
2026 paper's BTC-ETH Sharpe of 2.4, which is not reproduced on coins a
US account can trade.

What remains in the queue: the ORB pilot (needs Alpaca keys for 5-minute
bars), the IBIT options collector, and PEAD.

## Addendum, 2026-10-12 (10): the collectors are running

Two of the queue's items are blocked on data nobody sells for free, so
the desk now collects it (`cryptobot/vrp_collect.py`, run daily by the
desk when `collectors.enabled` is true, or by hand):

- **IBIT option surface** for `btc-vrp-listed-options`. Cboe publishes a
  delayed quote for every IBIT option with its implied volatility and
  delta, free. One row a day: 30-day at-the-money IV interpolated between
  the bracketing expiries, 25-delta put and call IV, spreads at the ATM
  strike, and 20- and 30-day realised volatility from IBIT closes. First
  row, 2026-10-12: spot 46.64, IV 36.6% (Cboe's own 30-day figure 36.4%),
  realised 37.5%, so implied sits 0.9 points *below* realised and the
  rule's entry gate (implied at least 5 points over realised) is shut.
  Skew is 2.0 points, puts over calls. The backtest needs about a year
  of these rows.
- **Kalshi hourly candles** for the BTC, ETH and US500 perps, for the
  `cross-asset-crypto-leadlag` follow-up (does the BTC perp lead the
  US500 perp hour to hour while the cash market is closed?). The public
  endpoint keeps a few days of hourly history, so the last 48 hours are
  appended daily and deduplicated.

Both write under the desk's state directory, which the Docker volume
keeps across restarts. `python -m cryptobot.vrp_collect --state state
--report` prints the series so far.

Queue status after this session: item 1 (overnight index) inconclusive,
item 2 (memecoin pairs) killed, item 4 (IBIT volatility) collecting,
item 3 (ORB pilot) waiting on Alpaca keys for 5-minute bars, item 5
(PEAD) queued behind it.

## Addendum, 2026-10-12 (11): harnesses waiting on their data

Three pre-registered tests now have their code written and tested on
synthetic data, so each runs the day its inputs exist, with no further
design decisions to make in sight of the result:

| registry id | harness | runs when |
|---|---|---|
| `orb-qqq-pilot` | `cryptobot/orb_study.py` | Alpaca keys are in `.env` (`--fetch` pulls ten years of 5-minute bars) |
| `btc-leads-us500-intraday` | `cryptobot/intraday_leadlag.py` | the hourly cache holds 500 shared hours, about three weeks |
| `divergence-catchup-btc` | `cryptobot/oos_track.py` | 60 qualifying days, which is years |

The dashboard's research card and the daily digest show where each
stands.

## Addendum, 2026-10-12 (12): queue item 5 run, post-earnings-announcement drift

Pre-registered as `pead-revisit`; `cryptobot/pead_collect.py` and
`cryptobot/pead_study.py`. The panel came from Nasdaq's free data API:
the earnings calendar for every trading day 2015–2026 (167,004 rows;
the source has gaps, 18 days in June 2016 among them) and ten years of
daily prices for the 1,977 announcers under $5B with at least three
estimates. Prices are split-adjusted. Two biases are built into the
source and are stated with every result: histories exist for current
listings only, so names delisted since are missing (worst for the
bottom decile), and the market cap is today's, so "small" means small
now. Usable windows cover 85% of qualifying announcements, 2017–2026 in
practice.

**The pre-registered sort loses.** Ranking by Nasdaq's percentage
surprise, the top decile bought at the next open for 20 sessions
*underperforms* the equal-weight basket of all announcers:

| ranked by % surprise | spread per month | Sharpe | PSR | 2022–26 |
|---|---|---|---|---|
| cap ≤ $5B | −0.65% | −0.53 | 0.06 | −37% |
| cap ≤ $2B | −0.82% | −0.59 | 0.06 | −41% |

Percentage surprises are dominated by tiny-denominator names (a cent
against a consensus of zero), so the decile is noise.

**The academic scaling looks different, and that is the problem.**
Ranking by (EPS − consensus) / price, the standard surprise measure and
a variant chosen after seeing the first result:

| ranked by surprise / price | spread per month | Sharpe | PSR | years positive | 2022–26 |
|---|---|---|---|---|---|
| cap ≤ $5B | +0.65% | +0.42 | 0.89 | 5 of 11 | +58% |
| cap ≤ $2B | +1.32% | +0.83 | 0.99 | 10 of 11 | +76% |

The long-short Sharpe is negative in both (−0.56, −0.43): shorting the
bottom decile loses, which is what survivorship does to a panel of
survivors. Across the five full-panel runs looked at, the best
variant's deflated Sharpe is 0.68 and its minimum track record 45
months. The written bar is cleared only by the sort that was not
registered, on a panel whose two biases both push the same way.

**Verdict: inconclusive.** The variant is pre-registered as
`pead-per-price-smallcap` and judged out of sample from November 2026,
collected month by month so the cap and the listing are point-in-time;
24 months decide. Nothing trades on it before then.

What it took: three parallel calendar streams and two price streams
over about three hours, with the throttle-versus-holiday answer,
delisted symbols and a window-alignment bug found and fixed on the way.

## Addendum, 2026-10-13 (13): the earnings-drift variant fails its placebo

The one result in addendum 12 that cleared a bar was the sort that was
not registered: surprise divided by price, cap at or under $2B, +1.32%
a month over the other announcers. Two biases were known (survivors
only; today's cap as the size filter). Before waiting two years for
the out-of-sample months, the same panel can say whether those biases
made the result, with three cheap checks (`pead_study` flags
`--max-dollar-volume`, `--entry-offset`, `--price-lag`).

**Point-in-time size does not remove it.** Filtering on the median
daily dollar volume over the 60 sessions before each report, which is
known at the time, instead of today's market cap:

| size filter, surprise / price | spread per month | Sharpe | PSR | 2022–26 |
|---|---|---|---|---|
| cap ≤ $2B (today's) | +1.32% | +0.83 | 0.99 | +76% |
| trailing $ volume ≤ $10M a day | +1.57% | +0.84 | 0.99 | +109% |
| trailing $ volume ≤ $3M a day | +2.34% | +0.75 | 0.99 | +146% |

**The placebo wins by more than the real entry.** Drift after an
announcement should be concentrated after the announcement. Entering
the same names 25 sessions later (sessions 25–45, before the next
quarterly report) or 60 sessions later, and, as the mirror, 25
sessions *before* the report:

| entry, cap ≤ $2B | spread per month | Sharpe | years positive |
|---|---|---|---|
| next open after the report (the claim) | +1.32% | +0.83 | 10 of 11 |
| 25 sessions late (no announcement in the window) | +1.77% | +1.13 | 10 of 11 |
| 60 sessions late | +1.38% | +1.10 | 8 of 11 |
| 25 sessions early (before the report) | −1.10% | −0.83 | 2 of 11 |

With the dollar-volume filter the same three read +1.57%, +1.68% and
−0.87%. The top decile outperforms the rest in any window after the
report and underperforms before it.

**The pre-report sign is the denominator's doing.** Dividing the
surprise by the last close before the report ranks a name higher the
further its price fell into the report. Dividing instead by the close
25 sessions earlier, which cannot see that fall, the early placebo
flips from −1.10% to +1.86% a month (Sharpe 1.41) while the real entry
(+1.26%) and the late placebo (+1.62%) barely move. So the names in the
top decile are not those with news; they are cheap small names on a
particular price path, and they beat the other announcers before, at
and a month after the report alike. In a panel of current listings
only, a set of cheap small names that outperforms whenever you look is
what survivorship looks like: the ones that went to zero are not in it.

**Decision.** `pead-per-price-smallcap` is killed before its first
out-of-sample month; the test it registered would have measured this
characteristic and called it drift. `pead-revisit` stays inconclusive
under its own written rule (the registered sort lost, at 17 trials
now), with the mechanism recorded. The monthly earnings collection is
out of the daily collector; `pead_collect monthly` remains callable
for a future earnings test that needs a survivorship-free panel. No
reversal or low-price strategy is registered out of this: the
characteristic is indistinguishable from survivorship in this data,
and a clean panel would be the first step, not a rule.

Trials this addendum: ten (three size runs, four placebos, three
denominator runs).

## Addendum, 2026-10-13 (14): Kalshi serves the whole hourly history

Addendum 10 said the Kalshi candlestick endpoint keeps a few days of
hourly history, so the collector appended 48 hours a day and a missed
day was lost. Checked again with longer windows: one request returns
the BTC perp's hourly candles back to its June listing (2,852 bars)
and the US500 perp's since it listed on 2026-10-06 (106 bars; an hour
with no trade prints no candle). The collector now appends from the
last stored bar (a 120-day backfill on an empty cache, a 6-hour
overlap otherwise), and `intraday_leadlag --fetch` fills the cache
itself, so the lead-lag test runs on any machine with no desk and no
key. 100 shared hours on file today; 500 around 2026-10-30. The IBIT
option surface is the one series that still has to be caught on the
day: Cboe's delayed quotes have no history, so that one needs the desk
(or any daily runner) up at 21:15 UTC.

## Addendum, 2026-10-13 (15): the Bitcoin volatility premium, backtested now

`btc-vrp-listed-options` was waiting a year for IBIT surface rows. Its
pre-registration allowed an earlier run "with purchased history"; a free
one exists. Deribit's 30-day BTC implied-volatility index (DVOL) is
public, daily since 2021-03-24, and on the one shared day IBIT's own
30-day ATM implied vol sat 1.2 points under it. `cryptobot/vrp_study.py`
runs the registered rule on DVOL and Coinbase BTC closes; the deviation
is in the registry, and the collector now stores DVOL daily next to the
IBIT rows so the basis is measured as they accrue.

**The premium is real.** Short 30-day variance at DVOL, settled on the
next 30 days' realised vol, one position at a time, after 1.5 vol
points of friction:

| entry gate (IV − 20-day realised) | trades | per trade, vol points | t | years positive |
|---|---|---|---|---|
| none | 64 | +4.8 | 2.3 | 5 of 6 |
| ≥ 5 points (registered) | 56 | +5.3 | 2.8 | 6 of 6 |
| ≥ 10 points | 48 | +4.2 | 1.9 | 6 of 6 |

**The registered trade fails its own risk bar.** One short ATM straddle
at a time at the 5-point gate, Black-Scholes marked at DVOL, delta-
hedged at weekday closes (IBIT cannot be hedged at the weekend), held
to expiry, charged $0.65 a contract, 2.5% half-spread and 1 bp per
hedge, on margin of 25% of notional:

| execution, gate 5 | per month | Sharpe | PSR | worst month | max drawdown |
|---|---|---|---|---|---|
| one straddle at a time, to expiry (registered) | +5.8% | 1.02 | 0.97 | −88% | −105% |
| same, bought back 7 days before expiry | +3.4% | 0.70 | 0.94 | −48% | −50% |
| same, with 10-delta wings bought | +4.5% | 0.91 | 0.95 | −85% | −98% |
| ladder: one rung a weekday at 1/21 size | +3.25% | 1.21 | 1.00 | −14.7% | −23.6% |
| ladder with wings | +2.45% | 1.28 | 1.00 | −13.3% | −21.2% |

The −88% month is 2023-02-10 to 03-13: BTC fell under the strike into
the last week, the hedge went to a full short, and the 20% weekend gap
into expiry (the banking-crisis rally) was paid twice, on the straddle
and on the hedge. That is pin gamma on a 24-hour underlying hedged in
US hours, and neither the early buy-back nor the wings remove it; only
diluting each expiry to 1/21 of the book does. The 2025 months the
vendor showed as implied-below-realised: April skipped by the gate,
March −6%, December +10%.

**Verdict: inconclusive.** The registered rule clears Sharpe and PSR
and fails the worst-month bar; its deflated Sharpe is 0.42 at 15
trials. The ladder clears every written number but is post-hoc (DSR
0.59), and it needs one IBIT contract per rung: about $1,165 of margin
each at a $46 share, $25,000 for 21 rungs, $6,000 for a weekly five.
The desk's $250–1,000 can only run the one-at-a-time version. The
ladder is pre-registered as `btc-vrp-ladder-oos`, judged on the IBIT
rows the collector stores (`vrp_study --source ibit --overlap`) after
twelve months, not traded before then and not below that capital.

Trials this addendum: fifteen, all counted in the registered rule's
deflated Sharpe.

## Addendum, 2026-10-13 (16): the premium's small-money form, pre-registered

The volatility premium in addendum 15 needs $25,000 of options margin
to harvest the way the backtest did. Kalshi sells the same risk in $1
pieces: its hourly "BTC above/below" series (KXBTCD) lists about 190
strikes an hour, 30–35 of them trade, and the top-of-hour print settles
them all. A far strike quoted at 5¢ is a one-hour digital option; if
tails are overpriced the way 30-day volatility is, the favourite side
(85–97¢) resolves more often than its price says, and buying it half an
hour before the print earns the gap after Kalshi's fee of
0.07 × p × (1 − p) a contract.

The public API serves every settled market and its minute quotes with
no key. The pull (`cryptobot/kalshi_binaries.py`, paced at one request
a second) covers 30 days, about 17,000 traded markets. The rule, the
two decision times (30 and 15 minutes out), the price band, the spread
cap, the clustering by hour and the bar were written into the registry
(`kalshi-btc-hourly-tails`) before any quote was read: net per dollar
positive with cluster t ≥ 2 at both decision times and in both halves
of the sample, or inconclusive; negative at both, killed. The mirror
(buy the longshot), a resting-bid maker fill and the 0.97–0.99 bucket
are counted as trials. The Polymarket 15-minute markets tested earlier
were calibrated in their last two minutes; this is a longer horizon, a
different venue and the one the desk already has a key for.

## Addendum, 2026-10-13 (17): many small trades a day, measured on the desk's own venue

The operator's direction: trade many times a day for small profits
that add up, rather than once a day. The arithmetic first. On Kalshi's
perps a round trip costs 16–18 basis points (4 bp taker a side plus
the 4–5 bp from mid the desk measured on $50–500 orders). A rule that
trades every hour needs more than that per trade, on average, after
the hours it is wrong. Daily candles were chosen in the first place
because the daily bounce-short earns about +190 bp a trade gross; a
trade that size pays the fee ten times over.

Kalshi serves hourly candles for every one of its 28 perps back to
June 2026, so the question could be measured tonight rather than
argued. Pre-registered as `kalshi-perps-hourly-rules`: 24 grid rules
(fade or follow a 1-hour or 24-hour move beyond 1.5, 2 or 3 sigma,
hold 1 or 4 hours) and the best long and short hour of the day, pooled
across the 20 coins with at least two weeks of history, 45,419 hours,
t-statistics clustered by hour.

| rule family | trades a day | gross per trade | net at 18 bp |
|---|---|---|---|
| fade a 1-hour move (best of six) | 5–29 | +0.7 to +5.7 bp | −12 to −17 bp |
| follow a 1-hour move (best of six) | 5–29 | −0.7 to −5.7 bp | −19 to −24 bp |
| fade a 24-hour move | 2–32 | −2 to −26 bp | −20 to −44 bp |
| follow a 24-hour move, hold 4 h, 2 sigma | 8 | +26 bp | +8 bp (t 0.9) |
| best hour of the day, long (11 UTC) | 15 | +9 bp | −9 bp |

Walk-forward, each month trading whichever rule had been best on all
the months before it: 364 trades, −45 bp a trade, every one of the
four months negative, with the pick flipping between 24-hour reversal
and 24-hour momentum from month to month. One-hour moves on this venue
carry under 6 bp of predictable follow-through or reversal in either
direction; the fee is three times that. The one gross edge above the
cost (24-hour momentum) is the best of 26 and does not survive being
chosen in advance.

**Verdict: inconclusive** by the written rule (one rule is net
positive in sample), and nothing here trades. The honest version of
"many small trades" on Kalshi is the hourly binaries test in addendum
16, where each hour's trade is a few cents on a dollar with no
slippage model to argue about; its 30-day sample is still being
pulled, and the first 120 hours read +1.0% per dollar at 30 minutes
out with a t of 0.7, which is noise until the rest arrives.

## Addendum, 2026-10-13 (18): the opening-range pilot ran, and it is alive

The Alpaca paper key arrived tonight and `orb_study --fetch` pulled
137,377 five-minute QQQ bars from the free IEX feed: 1,543 regular
sessions from August 2020 to October 2026. The rule was registered on
2026-10-09, before any bar was seen: first 5-minute bar up, buy at the
second bar's open (down, sell short); stop 0.1 × 14-day ATR; target
10 R; flat at the close; 1% of capital at risk a day, at most 4×
leverage.

| cost per share, each side | net per year of capital | Sharpe | PSR | years positive |
|---|---|---|---|---|
| 1.0 c (registered) | +32.6% | 1.05 | 1.00 | 6 of 7 |
| 2.2 c (replications' break-even) | +26.8% | 0.86 | 0.99 | 6 of 7 |
| none | +37.5% | 1.21 | 1.00 | 6 of 7 |

Mean +0.26 R a session with a 20% hit rate: 1,239 stops, 65 targets,
239 flat at the close. By year at 1 c: 2020 (Aug on) +10%, 2021 +60%,
2022 +60%, 2023 −8%, 2024 +44%, 2025 +27%, 2026 +8%.

**Verdict: alive**, by the bar written in advance (Sharpe above 0.5
with PSR at least 0.95, and 2023–2026 net positive). One rule, so the
deflated Sharpe is the PSR. The caveats, stated before anyone trades
it:

- The window is six years, not ten: the free feed starts in 2020 and
  misses 2016–2019, where the replication found QQQ thin. The strong
  2021–2022 carry the average; 2023 lost.
- IEX bars are a fraction of consolidated volume. The opening range
  and the fills are a thin-tape view; a paper pilot against live
  quotes is the check.
- It is leveraged day trading. The pattern-day-trader rule needs a
  margin account above $25,000, so the desk's $250 cannot run it live.
  The next step is a 60-session paper pilot on the Alpaca paper
  account, an `orb_bot` inside the desk, scored against this backtest.

## Addendum, 2026-10-13 (19): the hourly binaries, judged on 30 days

The pull finished: 17,614 traded hourly BTC above/below markets in 706
hours, minute quotes for each. The rule registered in addendum 16
(favourite at 85–97¢ at the ask, fee paid, 30 and 15 minutes before
the print, t clustered by hour):

| decision time | trades | net per $ | cluster t | hit vs implied | halves |
|---|---|---|---|---|---|
| 30 min before | 2,692 | +0.63% | 1.0 | 94.2% vs 92.6% | −0.10% / +1.26% |
| 15 min before | 1,797 | +0.35% | 0.5 | 94.0% vs 92.7% | +0.74% / +0.01% |

The mirror is the clear result: buying the 3–15¢ side loses 34% and
41% per dollar (t −3.8, −5.0), resolving 4.9% of the time against 6.0%
implied. So the longshot bias is there, and the favourite is
underpriced by about 1.5 points of probability. What is left after the
fee (about half a cent) and the ask side of a 1–2¢ spread is a few
tenths of a percent per dollar, with a t-statistic at or below one.
Resting a bid instead of paying the ask loses 1.7% and 3.4%: the fills
arrive when the hour is turning against the favourite. The 90–95¢
bucket is the one positive at both times (+1.5%, +0.5%); 85–90¢ flips
sign between the two.

**Verdict: inconclusive** by the bar written before the pull (t ≥ 2 at
both decision times and both halves positive; net negative at both
would have killed it). Not traded. This was the small-money form of
"many trades a day": four favourites an hour, 1 to 5 contracts each,
and the arithmetic comes to pennies with wide error bars. The structure
is the right shape for a small account; the edge at this venue is
simply thin. A 60-day pull is one command if a longer look is ever
wanted.

## Addendum, 2026-10-13 (20): monthly trend-following on the macro perps

Kalshi's new perps on the S&P 500, Nasdaq 100, gold, silver, copper,
platinum, palladium and WTI make the most replicated factor in the
literature, time-series momentum, tradable in $4–14 pieces at 4 bp a
side. Pre-registered as `tsmom-kalshi-macro-perps` and run on ten years
of the ETFs that track the same prices (GLD, SLV, CPER, PPLT, PALL,
USO, SPY, QQQ from the Nasdaq data API, 2016–2026):

| variant | per year | Sharpe | PSR | max drawdown | full years positive |
|---|---|---|---|---|---|
| 12-month, long-short, 5%/yr carry (registered) | +3.2% | 0.28 | 0.79 | −31% | 4 of 8 |
| the same, no carry drag | +8.2% | 0.70 | 0.98 | −22% | 5 of 8 |
| 12-month, long-only | +7.4% | 0.67 | 0.98 | −19% | 5 of 8 |
| 1 / 3 / 6-month, long-short | −0.7 / −1.0 / +1.0% | about 0 | | | |

The rule is positive on seven of the eight instruments and beats
buying and holding on none of them: this was a decade in which nearly
everything went up, so the long side carries the result and shorting
the losers (2021–2023) cost 29 points. **Verdict: inconclusive.** The
number that decides it is the one assumed, not measured: the carry on
Kalshi's index and metal perps. The 5%/yr drag turns a 0.70 Sharpe
into 0.28. Measuring that funding is the next step and takes one pull
from the public API; at near-zero funding the family is worth a second
look with longer histories, and at 5% it is not.

## Addendum, 2026-10-13 (21): what Kalshi's perps actually pay in funding

Pulled from the public funding history, daily prints, annualised
(positive means longs pay):

| perp | days of history | funding a year | share of prints positive |
|---|---|---|---|
| gold | 32 | +3.7% | 47% |
| silver | 32 | +3.2% | 41% |
| palladium | 20 | +4.8% | 55% |
| platinum | 20 | +17.6% | 80% |
| US500 | 7 | +10.1% | 71% |
| copper | 6 | −17.9% | 17% |
| BTC | 395 | +8.2% | 48% (median zero) |
| ETH, DOGE, SHIB, SOL, XRP, LINK, ADA, LTC, BCH, HYPE, SUI, NEAR, ZEC | 128–395 | −3.5% to +6% | mostly zero prints |

Two things follow. The 5%/yr carry drag assumed in addendum 20 is
about what a long metals book pays, so that verdict stands. And a
funding-capture carry (short the perp, hold the ETF at Alpaca) has one
candidate above the noise, platinum at 17.6%, on twenty days of
history; at $250 of capital that is $40 a year before the hedge's
costs, which is not a strategy, it is a rounding error. Re-read when
the metal and index perps have months of prints, not weeks.
