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
