# Mandel cycle 2 report, 2026-10-14: theories made executable, data brought in, triage

*Written at the close of cycle 2 (C-d5278133), before Mandel meets the children.
Everything is on branch `claude/mandel-genesis`. Nothing from cycle 1 was deleted;
what is not useful now is parked with a reason and a recipe to bring it back.*

## The one-paragraph version

Forty-four theories drawn from the 21 sources, Mandel's own ideas, the repo's arbitrage
premise and the new social layer are written down as single falsifiable statements with
their trial math (statistic, null, procedure, data, minimum sample, pass criterion,
controls) in `theories/registry.json`. Eleven executable harnesses ran on real data pulled
into the archive (2,100 resolved Polymarket markets, 62,362 daily prices, 300 order books,
Kalshi settled markets and candles, one day of Reddit / StockTwits / crypto sentiment /
House disclosures, and full daily histories for BTC, ETH, SPY, QQQ and the crypto Fear &
Greed index). Six theories are supported, one is not supported but needs more snapshots,
one is inconclusive until thirty capture days exist, six are untested because their harness
is not written yet, twenty-two are blocked on a named missing input (mostly: children), and
eight are parked. The headline finding is negative in the useful way: Polymarket prices are
well calibrated at every horizon, no structural bias exists to exploit, YES+NO bundles show
no after-fee mispricing in the one snapshot, and a declared search of 21 simple momentum
rules overfits exactly as the deflated Sharpe and PBO machinery predicts. Prices do carry
structure (anti-persistence, multifractal scaling), which is a property to model, not an
edge to trade.

## Verdicts, with the numbers that matter

| Harness | Theories | Verdict | What was measured |
|---|---|---|---|
| market_calibration | T-01 | supported | Brier skill vs coin 0.86 (1d), 0.86 (3d), 0.78 (7d), 0.72 (30d), 0.70 (90d); n 393 to 265 |
| multiscale_edge | T-03 | not supported, parked | no horizon's mean error interval excludes zero: there is no bias to be consistent about |
| bundle_arb_scan | T-04 | not supported (kept) | 0 after-fee YES+NO mispricings in 268 markets; median round-trip spread 0.02; one snapshot only |
| multifractal_scaling | T-06 | supported | 30% of 40 longest series show tau(q) concavity beyond the shuffled null (chance 5%) |
| hurst_ci | T-07 | supported | median DFA H 0.35; 30% of series outside their shuffle null; bounded prices mean-revert mechanically near 0 and 1 |
| markov_baseline | T-08 | not supported, parked | first-order bucket Markov loses 0.04 bits/step to the base rate out of sample (60 series) |
| msm_volatility | T-09 | not supported, parked | MSM(k=3) scores 1.18 nats/obs worse than 20-day rolling variance (12 series); series too short |
| dsr_pbo_harness | T-10, T-36 | supported | best of 21 rules: Sharpe -0.03, deflated Sharpe 0.00, PBO 0.90 over 11,687 periods |
| controls | T-11 | supported | coin 0.25, oracle 0, market 0.024 on the same 200 questions |
| social_attention | T-38 | inconclusive | 1 of 30 capture days; runs daily and will turn into a verdict on its own |
| fear_greed_contrarian | T-41 | not supported, parked | 3,166 aligned days; fear<=25 adds +0.0001 to 7d BTC log return (p 0.52, halves disagree); greed>=75 adds +0.023 (p 0.96) |

Two readings taken from the calibration table but not yet automated as verdicts:

- **T-02 longshot bias.** The under-0.10 bucket holds three quarters of all observations
  (mean price 0.008 to 0.014). It resolves YES at 0.010 (1d), 0.007 (3d), 0.028 (7d),
  0.020 (30d), 0.019 (90d). At 7 days and beyond, cheap YES resolves slightly *more* often
  than priced, the opposite of the classic longshot bias, but that is 5 to 8 YES events per
  horizon. It is a lead, not a finding.
- **T-13 skill rises toward resolution.** Skill is monotone in horizon (0.70 at 90d to 0.86
  at 1d), as expected; the market learns as time passes.

## Triage

**Useful now (supported, feed the next cycle).** T-01 market calibration is the benchmark
every child and every strategy must beat. T-10 and T-36 justify the gate's deflation
machinery with real numbers. T-06 and T-07 describe the structure of the price process and
are inputs to any model of it. T-11 keeps the scoring path honest.

**Not useful this iteration, parked with reasons (unpark conditions in `THEORIES.md`).**
T-03 (no bias to test), T-08 (Markov), T-09 (MSM on short series; unpark to retest on the
4,411-day BTC and 8,484-day SPY histories now in the archive), T-41 (Fear & Greed), T-29
(presentiment: no mechanism, covered by the control design), T-35 (Mandelbrot-set
metaphor: no statistic proposed), T-26 (retrieval quality), T-34 (box-count duplicate of H).

**Not supported but kept active.** T-04 bundle arbitrage needs repeated book snapshots to
measure frequency and half-life; one snapshot cannot park it.

**Untested, cheap harness pending.** T-02 (longshot bucket as a verdict), T-12 (calibration
by volume quartile; fix the end-of-life volume leak first), T-13 (horizon monotonicity),
T-19 (naive vs point-in-time run), T-31 (small MLP vs logistic regression, walk-forward),
T-32 (low-rank structure across concurrent markets).

**Blocked, with the blocker named.** 22 theories, in three families: those that need
registered children recording forecasts (T-14, T-15, T-25, T-37), those that need decided
proposals (T-16, T-17, T-18, T-20, T-21, T-22, T-23, T-30), and those that need thirty days
of social capture, a key, or an entity-matching table (T-05, T-27, T-28, T-39, T-40, T-42
to T-46).

## Data inventory (all in the archive, all in git, 4.6 MB)

| Bundle | Rows | Recipe |
|---|---|---|
| polymarket-closed-markets | 2,100 | Gamma /markets closed=true, 100 per page |
| polymarket-price-history-daily | 62,362 | CLOB /prices-history fidelity=1440 per token |
| polymarket-books-snapshot | 300 | CLOB /book for YES and NO tokens |
| kalshi-settled-markets, kalshi-candles | see INDEX | Kalshi trade API, throttled 1.1 s |
| social-reddit / stocktwits / crypto / prices / house-ptr / derived (dated) | 100 / 411 / 439 / 1,022 / 421 / 210 | `python -m mandel social-fetch`, one day |
| crypto-fear-greed-history | 3,174 | alternative.me, full series since 2018-02 |
| daily-history-{BTC-USD, ETH-USD, SPY, QQQ} | 4,411 / 3,262 / 8,484 / 6,942 | Yahoo period form (range=max silently returns monthly bars) |

Every bundle carries a recipe, a sha256 and tags in `archive/INDEX.json`; point-in-time
rows carry `observed_at` and `available_at`. A parked theory or a stale bundle is dug up by
name, never re-derived.

## The social / flow layer

Collected without credentials: Reddit RSS for r/wallstreetbets, r/options, r/pennystocks,
r/stocks, r/CryptoCurrency, r/SatoshiStreetBets, r/thetagang, r/Superstonk, r/Bitcoin,
r/ethtrader (new and hot, 100 each); StockTwits trending plus ten equity and four crypto
symbol streams, with the platform's own bullish/bearish tags; alternative.me Fear & Greed;
CoinGecko trending and 90-day daily prices; Yahoo daily closes for a 14-symbol watchlist;
the House clerk's yearly disclosure index filtered to periodic transaction reports (421 this
year, each with its PDF link). X/Twitter is collected only through the official API when
`X_BEARER_TOKEN` is set; the bundle is skipped and the recipe recorded otherwise. SEC EDGAR
refuses this host (403) and Binance is geo-blocked (451); both recipes are kept.

A derived bundle aggregates cashtag mentions, unique authors and a small lexicon sentiment
score per (source, ticker, day). The first day's top attention: BTC 96, SPY 50, QQQ 41,
ETH 40, DOGE 38, SOL 38, GME 37 mentions on StockTwits. None of this is a signal yet.
Theories T-38 to T-46 state what would make it one, and the first harness
(`social_attention`) already runs and reports its own shortfall.

## Costs of this cycle

Agents: two workflows (theory extraction, stopped after I wrote the registry directly
because its merge step would have overwritten the ledgered one; social-source sweep,
running at the time of writing) plus direct work. Wall time about 2.5 hours. The data pull
was the slow part (rate limits), the experiments run in 12 seconds end to end.

## What the next cycle should do, in order

1. Run `social-fetch` and `experiment-run all` daily (the OPERATIONS.md timer now does)
   so T-38 and the other social theories turn into verdicts by mid-November.
2. Write the six cheap pending harnesses (T-02, T-12, T-13, T-19, T-31, T-32); each is an
   afternoon of numpy against bundles that already exist.
3. Take a second and third book snapshot a few days apart to settle T-04.
4. Meet the children (MANDEL.md §5); that unblocks eleven theories at once.
