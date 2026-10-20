# Crypto derivatives, flows and on-chain-adjacent variables: what the 2020-2026 literature claims and what survives

- **Authors / kind:** Survey of 14 strategies or patterns from about 31 sources: peer-reviewed papers (Liu-Tsyvinski-Wu, J. Finance 2022; Griffin-Shams, J. Finance 2020; Baur-Smales, JFM 2022; Shen-Urquhart-Wang, Financial Review 2022; Fieberg-Liedtke-Zaremba, IRFA 2024; Mourey-Shahrour-Şoiman, FRL 2025; Weiss et al., FRL 2026), working papers (He-Manela-Ross-von Wachter; Borri-Liu-Tsyvinski-Wu 2025; Fabus et al. 2026; Almeida et al. 2024), a thesis, a GitHub replication and practitioner pages.
- **Links:** https://arxiv.org/html/2212.06888v7 · https://arxiv.org/pdf/2510.14435 · https://www.nber.org/papers/w25882 · https://doi.org/10.1016/j.irfa.2024.103218 · https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22332 · https://ideas.repec.org/a/eee/finlet/v86y2025ipes1544612325019154.html
- **Coverage confidence:** 0.35 (7 of about 31 sources read in full, including the two that carry most of the effect sizes; 8 checked at abstract or metadata level only; the rest unopened or 403).
- **Date researched:** 2026-10-20. **How much was read:** text was extracted from He et al. (v7) and Borri et al. (Table 2) and their numbers checked. Almeida et al., the deribit-rr backtest, the ML-Quant summary of Fabus et al., and the bgeometrics and TradingView pages were opened. Seven peer-reviewed papers were confirmed from the abstract only, and Weiss et al. from the title only. Every data claim was checked against Mandel's bundles.
- **Selected because:** the learning program's inputs include funding rate, basis, open interest, implied volatility, skew, the variance risk premium, ETF flows, COT positioning and market cap, and Mandel's crypto record (T-363, T-314, T-402, T-546) has tested only price and funding versions of them. This cluster covers the variables one step away.

## What it says

- **Perp premium convergence (He et al.).** Short the perp and hold spot when the perp trades rich. The premium exists because leveraged retail longs pay for exposure and margin-constrained arbitrage capital is scarce. On Binance hourly BTC, 2020-01..2024-03: Sharpe 11.65 at zero cost and 3.35 at high retail fees; 37.6% of the return comes from convergence and 14.9% from funding. The effect has decayed: the mean premium was 0.69 before 2022 and 0.17 after, and Borri puts the carry Sharpe at 4.06 from 2024 and negative in 2025. Only the positive leg can be executed from the US. The negative leg needs short spot, which means paying an IBIT borrow cost in US hours.
- **Size (CSIZE).** Coins with small market caps earn more. Borri Table 2, weekly value-weighted: 5-1 is -2.3%/week (t -2.66), and -0.9% (t -1.69) post-2020; smallest minus largest is about +0.9%/week post-2020. Fieberg et al.: the premium sits in micro-caps too small to trade economically, appears mainly in bull markets, and decays.
- **Two-week momentum, loser leg.** 5-1 is +2.6%/week (t 3.89), and +2.1% (t 3.70) post-2020. Fieberg et al.: most of the alpha comes from the short leg, and trading costs are heavy.
- **Network value (CVALUE).** Market cap relative to new addresses: 5-1 is -3.5%/week (t -3.50), and -2.3% post-2020. Only the same author group has replicated it, and the free data carry active addresses, not new ones.
- **Intraday half-hour momentum (Shen et al.).** In a session defined by volume, the first half-hour return predicts the last half-hour, most strongly in high-volume sessions. The authors attribute it to liquidity provision. Coefficients unseen; no replication.
- **Spot BTC ETF flows (Fabus et al., via a secondary summary).** After timestamp alignment, each $1bn of net inflow is followed by +1.67 pp of next-day BTC return, and returns also predict flows. Unreplicated, and other papers disagree.
- **CME Commitments of Traders (Baur-Smales).** Leveraged funds time the market by adjusting their net shorts, and following their changes is profitable. Magnitudes unseen. Since 2024 those shorts are largely basis hedges.
- **Weekend crypto predicts Monday equities (Mourey et al.).** Negative weekend crypto returns predict Monday declines in the Nasdaq and Russell 2000, more strongly after May 2022; positive weekends predict nothing. It is a day-of-week effect, and most of it probably sits in the opening gap, which ES futures already price on Sunday.
- **Deribit expiry reversal with dealer gamma (Weiss et al.).** Returns reverse around the Friday 08:00 UTC expiry, most when dealer gamma exposure is negative. Confirmed from the title only.
- **25-delta risk reversal (skew).** The thesis claim (controlled t 3.73, weaker after 2024) could not be opened. The one replication that could be opened gets 58.9% sign accuracy (p about 0.18) and calls the signal noise.
- **Variance risk premium as a predictor.** The vol-of-vol forecasting paper returned 403. Almeida et al. show only that the BTC VRP (implied variance minus trailing realised volatility squared) is high in low-volatility regimes. That is a same-period relationship, not a forecast.
- **Stablecoin issuance after drawdowns (Griffin-Shams).** In 2017-2018, Tether purchases followed downturns and came before price rises. The sample is from the manipulation era.
- **Coinbase premium.** An index with a definition but no predictive claim anywhere.
- **CME weekend gap fill.** The claim of "±90% fill" comes with no method, and most small gaps fill under any random walk.
- **Open-interest flush and liquidations.** Only case studies exist ($19bn of open interest gone in 36 hours, Oct 2025), and none makes a return claim.

## Evidence quality

**Rating: practitioner.** The rigorous core (Liu-Tsyvinski-Wu, Fieberg et al., and the checked numbers in He et al. and Borri et al.) documents effects that have decayed, sit in micro-caps Coinbase does not list, or were earned on Binance, which US persons cannot use. The claims Mandel could trade rest on short papers read only at abstract level, an unreplicated working paper, a thesis that could not be opened, and anecdote. A Sharpe of 11.65 against a liquid market should be treated as a cost or leak artefact until shown otherwise.

## What Mandel adopts

- Testable now on archived bundles, each pre-registered with a DSR that counts prior trials:
  - `cme-btc-leveraged-funds-change`: COT positioning stamped by release time, judged on post-publication data only (from 2022-05), with the CME basis as the decisive control.
  - `btc-weekend-drop-monday-equity-session`: BTC as a cross-asset leader for SPY/QQQ/IWM open-to-close, with the target's own price kept out of the inputs. It has the reference-price shape the children require (a market that trades while the book is closed), but it must beat ES futures. T-549 (overnight drift, supported) is context.
  - `crypto-two-week-losers-exclusion`: the loser leg, long-only on Coinbase, consistent with T-556 (DOGE/SHIB bounce-short, supported). T-314's failed winner leg enters the DSR.
  - `crypto-small-cap-quintile-vs-btc`, traded a day after the CMC snapshot. T-546 predicts a negative result.
  - `deribit-monthly-expiry-reversal-unconditional` (stage 1). T-216 (SPY OPEX gamma pin, supported) shows that gamma effects exist; T-223 found no larger BTC move into the fixing.
  - `btc-rr25-z-predicts-weekly-return` on T-257's smiles; `stablecoin-mint-after-btc-drawdown`, which must add 50 bp over the T-320 base rate; and `btc-us-session-first-half-hour-momentum` at lowest priority. Each reports FOMC and CPI days separately.
- Blocked, with first-seen capture starting now: `spot-btc-etf-flow-next-session` (the $500m threshold is fixed, not fitted), `perp-oi-flush-reversal-btc` (coin-denominated open interest), `coinbase-binance-premium-next-day` (with a Coinbase-Kraken placebo), `crypto-active-address-value-quintile`, and `btc-vrp-predicts-returns-holdout`. For the last one, T-580's F3 scan has already seen own_iv_rv with positive IC over the whole DVOL history, so only a 2019-2021 holdout plus a forward window counts as out-of-sample.
- Perp premium carry survives only as Hurst's H-ibit-carry forward test, read on 2027-02-12.

## What Mandel holds loosely or rejects

- Funding-rate carry: the effect has decayed, and T-363 (Sharpe -0.64), T-198, T-258 and T-423 are not supported. Funding is a censored signal: a practitioner count (not opened) puts BitMEX BTC funding at its 0.01%/8h baseline for 78% of Q3-2025, and Deribit's ±5 bp dampener hides small premiums. So funding data cannot show the post-2022 premium. Hurst measures US-venue funding near zero. P&L earned on Binance or Deribit is not US-legal, so their data are used as signals only.
- CME weekend gaps: dropped, because CME BTC futures have traded through weekends since 2026-05-29.
- ETF flow magnitude: too large relative to daily volatility, which suggests look-ahead. T-328 and T-404 are parked.
- Skew and the VRP as predictors: T-52, T-138, T-227 and T-235 failed on SPX, and the child crypto study found Deribit's implied distribution already priced into Polymarket BTC/ETH contracts. T-49 and T-246 show that the VRP exists, not that it forecasts.
- Intraday momentum: T-427 failed, T-577 has 0 of 50 crypto 5-minute cells net positive, and Hurst's hourly rules show under 6 bp of follow-through against 16-18 bp of fees.
- Cross-venue premiums: Brier and Kelly find that gaps close fast and that large gaps are mismatched questions, and Kalshi's hourly BTC/ETH ladders do not lag Coinbase spot.
- On-chain value: the replication is not independent, the data are current-vintage, and T-400 (MVRV) is not supported.
- Smart-money COT: Result 18 (informed traders are a pointer, not a signal) and T-405 (parked) are hostile.

## Design implications for the RSI predictive substrate

- New bundles, with offshore venues used as signals only: binance-1h-BTCUSDT, binance-um-metrics, farside-btc-etf-flows, ishares-ibit-history, coinbase-hourly-USDT-USD, coinmetrics-adractcnt, deribit-option-trades-BTC-2019-2021, and a Thursday Deribit book capture for sign(GEX).
- First-seen capture for every series that gets revised; backfills are labelled as revised data.
- Point-in-time rules: Coinbase bars are stamped at the start, Binance and Deribit candles at the open. CMC snapshots become tradable a day later. COT uses available_at. Day-t ETF flows enter at 13:30 UTC on t+1. On-chain data lag 2 days. Delisted coins get a survivorship haircut.
- Candidate features: dLF/OI, the percentile of the change in coin open interest, stablecoin-mint z, Coinbase premium z, RR25 z, the weekend BTC return, CMC market cap rank, and ETF flow. Funding is used only as a control.
- Never condition on USD-denominated open interest during a price drop, because it falls mechanically with price.
- Default placebos: Wednesday pseudo-weekends, random-tercile labels and first-passage nulls.

## Cross-links

- A4: liquidation cascades and vol-of-vol are bursts of trading time. A5: its retrieval-date leakage control is the same idea as the t+1 flow rule.
- 12, 13, 14: their indicator and HMM-regime pipelines should be scored on these features under the same gate.
- venues/US-LEVERAGE-VENUES-2026-10-20.md (Kalshi perps, CDE nano futures, IBIT).
- T-363, T-553, T-198, T-258, T-423, T-314, T-546, T-556, T-402, T-464, T-320, T-223, T-216, T-257, T-49, T-246, T-580, T-405, T-404, T-328, T-427, T-549, T-400; H-ibit-carry, H-btc-us500-lead.

## Sources used

- He et al., Fundamentals of Perpetual Futures: https://arxiv.org/html/2212.06888v7
- Borri et al. (2025): https://arxiv.org/pdf/2510.14435
- Liu-Tsyvinski-Wu: https://www.nber.org/papers/w25882
- Fieberg-Liedtke-Zaremba: https://doi.org/10.1016/j.irfa.2024.103218
- Shen-Urquhart-Wang: https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/
- Fabus et al. summary: https://www.ml-quant.com/papers/ssrn/7545019/
- Baur-Smales: https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22332
- Mourey et al.: https://ideas.repec.org/a/eee/finlet/v86y2025ipes1544612325019154.html
- Weiss et al. (title only): https://doi.org/10.1016/j.frl.2026.110340
- deribit-rr: https://github.com/JERONIMODIFRANCO/deribit-rr/tree/main
- Almeida et al.: https://arxiv.org/abs/2410.15195
- Griffin-Shams: https://papers.ssrn.com/abstract=3195066
- Coinbase Premium Index: https://charts.bgeometrics.com/coinbase_premium.html
- TradingView CME gaps: https://www.tradingview.com/ideas/cmegaps/
