# Options flow and dealer Greeks as market signals: dealer gamma, vanna/charm, put/call volume, open interest, OPEX and 0DTE (literature survey)

- **Authors / kind:** Literature survey of 13 candidate strategies, each source-checked and re-registered by a verifier. Core papers: Baltussen, Da, Lammers & Martens (JFE 2021, "BDLM"); Ni, Pearson, Poteshman & White (RFS 2021, "NPPW"); Amaya et al. (2025 WP); Adams et al. (2026 draft); Ni, Pearson & Poteshman (JFE 2005, "NPP"); Golez & Jackwerth (JFE 2012); Johnson & So (JFE 2012); Pan & Poteshman (RFS 2006); Muravyev, Pearson & Pollet (JFE 2025, "MPP"). Practitioner: SqueezeMetrics (GEX, DIX), CXO Advisory, Quantpedia, Cboe.
- **Links:** https://www3.nd.edu/~zda/intramom.pdf · https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf · https://www.jean-sebastienfontaine.com/papers/0dte-options-volatility.pdf · https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html · https://www.nber.org/papers/w10925 · https://squeezemetrics.com/monitor/static/DIX.csv
- **Coverage confidence:** 0.55 (fraction of the sources actually read and verified: about 22 of 33 opened, most as abstracts or listings).
- **Date researched:** 2026-10-20. **How much was read:** full text of BDLM, Amaya et al., Adams et al., SqueezeMetrics "Short Is Long" and Avellaneda's slides reproducing the NPP preprint; abstracts or listings of the other papers; the CXO put/call page and the OSAP SignalDoc. Data probed live: DIX.csv (3,891 rows, 2011-05-02..2026-10-20), Cboe put/call files, the OCC volume query. Not opened: Gao-Han-Li-Zhou, Barbon-Buraschi "Gamma Fragility", the SqueezeMetrics GEX white paper, Maurer, Cboe's 2023 0DTE note, Hull Tactical. Vilkov's 0DTE results are paywalled.
- **Selected because:** dealer gamma, put/call volume and open interest are inputs in the user's trading-bot program, and Mandel's unconditional tests (T-427, T-216, T-192/T-502, T-438) gave mixed verdicts. This literature supplies the mechanisms and conditioners those tests lacked.

## What it says

- **Gamma-conditioned intraday momentum (BDLM).** Short-gamma dealers and leveraged-ETF rebalancing trade with the day's move near the close. On S&P 500 futures 1996-2020 the slope of the last half-hour return on the rest-of-day return is 6.63 (x100, NW t 4.78, R² 3.58%) after negative-gamma days and 0.82 (t 1.03) otherwise; the timing rule on the index-futures basket has Sharpe 1.73 before costs (verified). Decay: negative-GEX days are now rare (162 sessions 2021-01..2026-10, 104 in 2022, 19 inside Mandel's intraday window). Barbon et al.: the LETF channel decayed, the gamma channel persists.
- **Gamma dampens volatility.** NPPW (single stocks) find hedgers' net purchased option positions lower volatility. Amaya et al. (Cboe trade data, 2020-2023) confirm the sign at a small size: median -0.08 pp of daily vol, maximum +3.3 pp against a 4.5 pp SD of daily changes. Only 68.7% of SPX volume is customer-vs-market-maker, so open-interest GEX misclassifies about a third. SqueezeMetrics' next-day SD contrast is vendor in-sample.
- **Expiry-day dampening (Adams et al.).** Exception Tuesdays and Thursdays before May 2022 show 61 bps (about 7%) lower 10-minute realised volatility on days with an expiring 0DTE, driven by older positions that become 0DTE; the effect vanished once every weekday became an expiry. No trading P&L; Cboe 2023 found no impact.
- **Strike pinning.** NPP (1996-2002, 4,395 stocks): closes cluster at strikes on expiration Fridays, mostly when market makers are net long. Golez-Jackwerth: S&P futures pin to the ATM strike on serial expiries. Both predate $1 strikes, weeklies and daily expiries; NPP's 16.5 bps is unconfirmed.
- **OPEX week and vanna/charm.** Stivers-Sun (JBF 2013): higher S&P 100 returns in OPEX weeks, partly attributed to delta-hedge rebalancing and falling implied volatility, the academic form of the vanna/charm story. Quantpedia's Sharpe 0.61 is its own construction.
- **Put/call volume.** CXO (2003-2013): correlations tiny, best R² 0.006 at 21 days, and a rule's gross edge vanished above 0.25% round-trip costs. Pan-Poteshman (proprietary open-buy volume, 1990-2001): low-P/C stocks beat high by over 40 bps next day. Blau-Nguyen-Whitby: unsigned public P/C predicts only fleetingly.
- **Open interest growth.** Fodor-Krieger-Doran: call-OI increases precede higher single-stock returns. Seo-Byun-Kim: OTM call-OI growth predicts market returns (market unconfirmed, possibly KOSPI 200).
- **Option-to-stock volume (Johnson-So).** Lowest O/S decile beats highest by 0.34%/week (1996-2010; OSAP "clear", t 3.45); Ge-Lin-Pearson attribute it to embedded leverage. MPP: excluding high borrow-fee stocks removes at least two-thirds of option signals' predictability.
- **Signed option flow.** Michael-Cucuringu-Howison: option volume imbalance predicts overnight equity returns; no crypto estimate exists.
- **DIX.** SqueezeMetrics: DIX >= 45% precedes a 5.3% vs 2.8% mean 60-day return, in sample. The level broke in 2022 (annual mean 0.395-0.440 before, 0.454-0.486 after), so the fixed threshold is a regime artefact.
- **0DTE premium.** Vilkov: a variance premium exists, but most static held-to-expiry rules have insignificant means and P&L follows realised skewness (setup verified, results not).

## Evidence quality

**Rating: mainstream-educational.** The academic core is rigorous (JFE/RFS, Newey-West inference, a natural experiment) but rests on proprietary signed positions. Mandel can test only public proxies (vendor OI-based GEX, unsigned OCC volume), practitioner claims are in-sample, and nearly every effect is small or decayed.

## What Mandel adopts

- **Sign-based gamma-conditioned momentum** as a post-publication successor to T-427, whose unconditional rule lost 2.09 bps/day (HAC t -2.58). A percentile conditioner was rejected: it ranks long-gamma days and tests a different mechanism. Blocked on a hashed GEX vintage and 2021-2023 1-minute S&P data; the deflation counts T-427's 60 cells (66 trials).
- **GEX tercile within variance risk premium terciles** for 1-day short straddles (2012-2026), using GEX row t-2 because row t posts after the t close. VRP stratification is required because GEX is low when T-101's VRP effect operates, and GEX must add out-of-sample R² beyond VIX and HAR, where T-415 and T-235 added nothing. This unblocks T-217/T-218 in model-priced form.
- **The SPXW weekday-expiry switch** (testable now, 2014-2026, Parkinson range over VIX-implied sigma, weekday and year-month fixed effects). It generalises T-216 (supported: opex Fridays +9.14 bps for model-priced 1-day short straddles) and agrees with T-219's lower |r|/sigma on witching Fridays.
- **Single-stock strike-band clustering** (testable now, 2005-2026, NPP's band-hit statistic); T-192/T-502 tested only SPY.
- **DIX rebuilt from FINRA Reg SHO short volume** (testable now, 2019-08..2026-10), with a drawdown placebo in the pass, because short volume share rises into dips; T-394 is inconclusive.
- **Deribit signed delta flow on BTC** (testable now), executed on Coinbase Derivatives nano futures; flow must predict beyond the day's own return. Low prior.
- **Equity put/call z-score contrarian**, which must beat a VIX top-tercile rule.
- **OCC captures start now** for O/S, customer put/call and OI tests (a strict rolling 2-year window).

## What Mandel holds loosely or rejects

- **OPEX-week drift with an implied-volatility conditioner: dropped.** A forking-paths rescue of T-438/T-353 (not_supported, halves +19.8/-22.1 bps); at about 50 conditional weeks the minimum detectable effect is about 90 bps against a claimed 20. Vanna/charm stays unproven.
- **Leveraged-ETF rebalancing as its own test: dropped.** Decayed per Barbon et al.; T-427 and T-428 found nothing in the last half-hour; kept only as a covariate.
- **0DTE short premium:** a duplicate of T-217. T-529 shows the 1-day premium flips sign between /365 and /252; T-109 model-priced condors fail; Hurst's real BTC VRP still produced a -88% month. Only traded prices settle it.
- **Flow-following.** T-463 (Kalshi taker flow), T-423 (Deribit funding, DSR 0.000) and Hurst's Kalshi perps taker flow (|t| <= 2.5) all failed, and copying informed wallets loses the fee at any delay (EDGE_VERDICT Result 18). "Unusual options activity" is this family; a reference must lead the book, and end-of-day OI and put/call are public.
- **Put/call and OI growth as index timers** (contested or null), and **vendor GEX/DIX as point-in-time data** (a backfilled single vintage).
- **Borrow-fee confound:** O/S and P/C spreads may be MPP's borrow premium, which Mandel cannot measure (T-193 blocked; days to cover is a proxy).
- Deribit is read as public data only, never traded.

## Design implications for the RSI predictive substrate

- **F4 flow feature family** for T-578: GEX percentile (row t-2 at a close entry), sign(GEX), rebuilt DIX percentile, equity put/call z, SPX call-minus-put OI growth, and expiry flags (monthly OPEX, SPXW weekday expiry, quarter-end). Report ablation IC beside F3 (T-580; F0F1F3 mean IC +0.028, 0 cells pass).
- **Data to add:** a hashed DIX/GEX vintage, diffed per download; the daily OCC volume query by account type from 2024-10-21; Cboe put/call CSVs and daily JSON from 2019-10-07; Dukascopy US500/USATECH 1-minute 2021-2023; capture-box chain OI for Mandel's own GEX and max pain (T-513).
- **Point-in-time rules:** GEX row t posts the evening of t; FINRA short volume about 17:20 ET; the OCC posting time is unverified (use the t+1 close); Cboe same-day volume is preliminary.
- **Tests:** block-shuffled GEX placebo; VRP, VIX and drawdown comparators; both halves positive; deflate over predecessors' cells too.

## Cross-links

- 12, 13, 14 (Claude trading videos): their regime and flow features should face these comparators.
- A4 (MMAR): gamma dampening is one mechanism for volatility clustering; HAR and MSM are the baselines GEX must beat.
- A5 (Halawi): how fast information reaches price, the question behind the fleeting put/call signal.
- OPTIONS-STRATEGIES.md, UNDERLYING-STRATEGIES.md, SOCIAL-SOURCES.md; theories T-216, T-217, T-218, T-427, T-438, T-502, T-529, T-578, T-580.

## Sources used

- BDLM (2021), full text: https://www3.nd.edu/~zda/intramom.pdf
- Barbon et al., SFI WP 22-40 (abstract): https://www.sfi.ch/en/publications/n-22-40-liquidity-provision-to-leveraged-etfs-and-equity-options-rebalancing-flows-evidence-from-end-of-day-stock-prices
- NPPW (2021): https://ideas.repec.org/a/oup/rfinst/v34y2021i4p1952-1986..html
- Amaya et al. (2025), full text: https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf
- Adams et al. (2026), full text: https://www.jean-sebastienfontaine.com/papers/0dte-options-volatility.pdf
- NPP (2005) via Avellaneda's slides: https://math.nyu.edu/inmemoriam/avellaneda/PinningSlides.pdf
- Golez & Jackwerth (2012): https://ideas.repec.org/a/eee/jfinec/v106y2012i3p566-585.html
- Stivers & Sun via Quantpedia: https://quantpedia.com/screener/details/102
- CXO put/call ratios: https://www.cxoadvisory.com/sentiment-indicators/predictive-power-of-put-call-ratios
- Blau, Nguyen & Whitby (2014): https://ideas.repec.org/a/eee/jbfina/v43y2014icp179-187.html
- Pan & Poteshman: https://www.nber.org/papers/w10925
- Fodor, Krieger & Doran (2011): https://ircommons.uwf.edu/esploro/outputs/journalArticle/Do-option-open-interest-changes-foreshadow-future/99380090633606600
- Seo, Byun & Kim (2020): https://ideas.repec.org/a/wly/jfutmk/v40y2020i6p989-1010.html
- Johnson & So (2012): https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html
- Ge, Lin & Pearson (2016): https://ideas.repec.org/a/eee/jfinec/v120y2016i3p601-622.html
- MPP (2025): https://ideas.repec.org/a/eee/jfinec/v172y2025ics0304405x25001618.html
- OSAP SignalDoc: https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- Michael, Cucuringu & Howison (2022): https://arxiv.org/abs/2201.09319
- SqueezeMetrics: https://squeezemetrics.com/monitor/download/pdf/short_is_long.pdf · https://squeezemetrics.com/monitor/static/DIX.csv
- CXO on Vilkov's 0DTE rules: https://cxoadvisory.com/equity-options/0dte-strategy-outcomes
- Cboe data: https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv · https://cdn.cboe.com/data/us/options/market_statistics/daily/2025-03-03_daily_options
- OCC volume query: https://marketdata.theocc.com/volume-query
