# Mandel cycle 3 report, 2026-10-14: venues, options strategies, then the underlying

*Written at the close of cycle 3 (C-e15f625e). Branch `claude/mandel-genesis`. Nothing deleted; everything that
could not be verified today is labelled and queued, not dropped.*

## The one-paragraph version

Three libraries now sit in the substrate and every entry in them is also a falsifiable theory with trial
math. `VENUES.md` maps 123 venues where a US person can trade or source data through an API, 110 of them
checked against their own documentation by a sweep agent and again by a skeptic agent. `OPTIONS-STRATEGIES.md`
holds 180 options strategies in eight families as legs the payoff engine can price and draw, each with
payoff, max profit and loss, breakevens, Greeks, crypto and metals notes and one claim. `UNDERLYING-STRATEGIES.md`
holds 130 strategies on stocks, funds, crypto, metals and event contracts with exact rules and what the
literature found after publication. Underneath them is the new options layer: free CBOE chains with implied
vol and Greeks captured daily, nineteen volatility and dispersion index histories back to 1990, Deribit
books and DVOL, a Black-Scholes and multi-leg payoff engine, and twenty new harnesses. Twenty-five of
those ran on real data today. The clean findings: a positive variance risk premium in SPX, BTC, gold, oil
and bonds; VIX backwardation precedes a 6.5-point larger VIX fall; SKEW does not predict crashes;
turn-of-month on SPY holds; six trend rules beat buy-and-hold on none of eight assets after deflation.
The honest finding: pricing options at a flat VIX overstates today's actual 30-delta SPY call by 79%, so
the four model-priced overlay backtests report inconclusive with a sensitivity reading instead of a verdict,
and a market-priced replacement harness is already accumulating the chain history that will decide them.

## Venues (task: every venue where API trading in the US can occur)

| US retail API access | Count | Examples |
|---|---|---|
| yes | 42 | Alpaca, Interactive Brokers (TWS, Web API, FIX, forecast contracts, IDEALPRO forex), Tradier, tastytrade (equities, options, futures), Public.com, Webull OpenAPI, moomoo OpenD, Robinhood Crypto API, Coinbase Advanced Trade, Kraken Pro, Gemini ActiveTrader, Bitstamp USA, Kalshi, Polymarket US, OANDA v20, Ironbeam, plus 15 data providers (Databento, Massive/Polygon, ThetaData, ORATS, Finnhub, Tiingo, FRED, CBOE delayed CDN ...) |
| yes with conditions | 34 | Schwab Trader API, E*TRADE, TradeStation, Lime, Lightspeed, Tradovate/NinjaTrader, AMP via CQG/Rithmic, Coinbase Derivatives, Bitnomial, Crypto.com US, OKX US, Alpaca Crypto, Webull event contracts, CME via brokers |
| institutional-only | 10 | CME Group, ICE Futures U.S., Cboe Futures Exchange direct, exchange-direct connectivity |
| unclear | 12 | mostly status changes in 2026 the pages do not settle |
| no | 25 | Firstrade, Ally, Fidelity, Vanguard (no public API), Deribit (no US onboarding; data only), CFDs (illegal for US retail) |

Options through an API, by route: equity and ETF options via Alpaca (up to four-leg orders, levels 1 to 3),
IBKR, Tradier, tastytrade, Schwab, E*TRADE, TradeStation, Public, Webull; index options (SPX, XSP, Section
1256) via IBKR, Tradier, tastytrade, Schwab (Alpaca's index options are Broker-API-only on the fetched
pages); futures options on gold, silver, oil, equity indices and CME crypto via IBKR, tastytrade,
Ironbeam, Tradovate and the CQG/Rithmic brokers; crypto options for US persons only through CME products
and Bitnomial, not Deribit; metals exposure for an API trader is GLD, SLV, IAU, PPLT options or COMEX
futures options, not spot bullion. Each row in `VENUES.md` carries auth, paper trading, rate limits,
market-data terms, fees, Python SDK, account rules (PDT and the intraday-margin regimes replacing it,
options approval levels, 1256) and the URLs fetched.

## Options strategies (focus first), then the underlying

| Family | Strategies | Examples |
|---|---|---|
| directional and verticals | 18 | long/short calls and puts, debit and credit spreads, ratio verticals, ladders, synthetics, LEAPS replacement, 0DTE spreads |
| volatility | 25 | straddles, strangles, butterflies, iron condors, jade and big lizards, backspreads, gamma scalping |
| time and term structure | 18 | calendars, diagonals, double calendars, PMCC, ZEBRA, rolling mechanics, VIX3M/VIX regime filter |
| income overlay | 20 | covered calls, collars, cash-secured puts, the wheel, covered strangles, buy-write and put-write index benchmarks, IBIT and GLD overwriting |
| arbitrage and synthetics | 23 | parity, conversion, reversal, box financing, jelly roll, dividend arbitrage, GC/GLD basis, Deribit parity with funding |
| event-driven | 23 | earnings straddles and IV crush, FOMC and CPI vol, opex and 0DTE gamma pinning, VIX settlement, crypto and metals event vol |
| surface and relative value | 26 | skew and term-structure trades, VRP harvesting, variance replication, dispersion, VIX call hedges, VXX/SVXY options, GVZ/OVX/DVOL cross-asset vol |
| crypto and metals specific | 27 | Deribit inverse options, DVOL and the BTC VRP, funding-hedged options, IBIT/ETHA options, COMEX futures options, GVZ, gold/silver ratio, 1256 and delivery mechanics |

The engine ran every template: 150 of 180 parsed cleanly; 30 fell back to default strikes; 29 entries state a
max loss the legs contradict (usually "limited" for a naked leg) and 16 state a max profit the legs contradict.
Those flags are written into the library next to each entry for the verifier. Only the volatility family
received its adversarial verifier pass today; the other seven hit the session usage limit (resets 15:20 UTC)
and the run is resumable from cache. The 130 underlying strategies (trend and momentum 19, mean reversion and
stat arb 19, carry and basis 20, event and calendar 24, factor and flow 25, microstructure and sentiment 23)
are in the same state: extracted with exact rules, claims, trial math and literature notes, verifier pending.

## Verdicts today (new harnesses only)

| Harness | Theory | Verdict | Reading |
|---|---|---|---|
| vrp_spx | T-48 | supported | implied 21.0 vs realised 18.6 vol pts over 8,459 days, p 0.014, halves agree |
| vrp_btc | T-49 | supported | DVOL 62.9 vs realised 54.9, p 0.001 |
| vrp_gold | T-50 | supported | GVZ 18.7 vs realised 16.9, p 0.004 |
| vrp_oil | T-63 | supported | OVX 41.8 vs 36.7, p 0.0015 |
| vrp_bonds | T-64 | supported | VXTLT 15.5 vs 14.4, p 0.022 |
| vrp_nasdaq, vrp_russell | T-51, T-65 | not supported | positive on 80% of days but p 0.095 |
| vrp_eth | T-67 | not supported | p 0.20; second half negative |
| skew_tail | T-52 | not supported | top SKEW quintile crashes less often (0.068 vs 0.123) |
| term_structure_reversion | T-53 | supported | VIX falls 6.09 pts after backwardation vs +0.45 in contango, p 0.0005 |
| covered call, put write, collar, short straddle (model-priced) | T-54 to T-57 | inconclusive by design | flat VIX overstates the 30-delta call by 79%; at IV x0.81 the straddle's +1.10%/month becomes +0.24% (p 0.07) |
| implied_move (market-priced) | T-66 | inconclusive | 0 of 30 resolved captures; first verdict about mid-December |
| trend_rules | T-58 | not supported | 0 of 8 assets after deflation; raw Sharpe higher on SPY, QQQ, BTC, ETH but not significant |
| turn_of_month | T-59 | supported | +9.0 vs +1.6 bps/day, p 0.002, halves +8.8/+5.9 |
| weekday_effect | T-60 | not supported | Friday -5.1 bps, Bonferroni p 0.43 |
| gold_silver_ratio | T-61 | not supported | 716 signals, no reversion (p 0.74) |
| crypto_weekend | T-62 | not supported | p 0.40; weekend vol 0.72x weekday |

Registry: 375 theories (14 supported, 11 not supported, 6 inconclusive, 227 untested with a harness
suggestion, 109 blocked with a named blocker, 8 parked). Archive: 66 bundles, 395,688 rows, 16 raw daily
captures kept on local disk only.

## What is honest about this and what is not yet

The model-free results stand on their own data and nulls. The strategy libraries are large and useful as
maps, but 310 of their 375 theories are unverified claims written by one agent each; the engine check
caught 45 payoff statements that disagree with their own legs, which is the measure of how much the
verifier pass matters. "Testable now" in those entries is the agent's judgement, not Mandel's; a harness
still has to be written for each before a status can move.

## Next, in order

1. Resume the two verifier passes from cache after 15:20 UTC and re-render (one command each).
2. Keep the daily capture running: `options-fetch` makes T-66 and the surface-calibrated overlays real.
3. Write harnesses for the ten most-cited options claims (earnings IV crush, calendar vs term structure,
   box financing rate vs bills, dispersion vs COR1M, 0DTE pinning) from the chains as they accumulate.
4. Pick execution venues from `VENUES.md` when a theory passes the gate: Alpaca paper for equities and
   options, Kalshi and Polymarket US for event contracts, tastytrade or IBKR for index and futures options.

## Addendum, 17:45 UTC: verifier passes complete

Both strategy libraries now have their adversarial verifier pass for every family.

| Library | Strategies | Verifier corrections | Strategies the verifier added |
|---|---|---|---|
| Options | 211 | 277 | 35 |
| Underlying | 171 | 211 | 52 |

Every claim was reworded to some degree. Untested theories were updated in place. The 27 claims that already
had a verdict keep it, because each verdict tested the old wording; the corrected wording became a new theory
with a `supersedes` link, and all 27 restatements were harnessed the same day. Where the rewording mattered:

- **Santa window** restricted to after publication (1973 on): +0.86 points, significant but under the 1-point
  bar, so not supported. The 1928-based pass stands only for the original wording.
- **BTC Mondays** pass as restated (p 0.012), but the restatement dropped a correction for testing seven
  weekdays; corrected it would be about 0.08, and the effect does not survive retail fees.
- **VIX forwards** now use the convexity-adjusted forward the verifier specified; VIX still lands below it in
  80% of contango months and 19 of 23 spikes.
- **SPX parity**, split by root as specified: 2.2% of strike pairs outside the band against a 2% bar.

The payoff engine re-checked all 211 options templates. 67 are beyond a one-expiry engine (calendars, strips,
dynamic hedges, futures legs) and 7 describe both the long and short versions in one sentence. 19 remain
flagged; on inspection they are variant mentions or two-underlying pairs, with no confirmed payoff error.

Registry after the addendum: 475 theories, 24 supported, 53 not supported, 8 inconclusive, 250 untested,
132 blocked, 8 parked. 168 tests pass.
