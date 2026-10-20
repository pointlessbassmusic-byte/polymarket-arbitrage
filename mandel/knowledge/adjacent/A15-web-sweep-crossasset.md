# Cross-asset lead-lag, momentum and carry: economic links, commodity and credit leaders, turnover momentum, VIX-conditioned reversal, dollar carry and COT pressure

- **Authors / kind:** Literature survey of 15 sweep candidates: 13 peer-reviewed papers (JF, RFS, JFE, JFQA, Management Science; 2000-2022), two working papers (Li-Yuan-Zhou; Fan et al. 2018), replications (OSAP, Pinchuk 2023, Tse 2015, Xu-Li-Singh 2023) and practitioner summaries (CXO, Quantpedia).
- **Links:** https://openaccess.city.ac.uk/id/eprint/31278/ · https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv · https://www.nber.org/papers/w17653 · https://www.nber.org/papers/w16427
- **Coverage confidence:** 0.56 (23 of 41 distinct sources opened and checked against the claim; four returned 403, several were read as abstracts or summaries only).
- **Date researched:** 2026-10-20. **How much was read:** full text for Medhat-Schmeling, the Huang 2015 draft, Pinchuk and Casassus-Higuera, plus the downloaded OSAP SignalDoc. The rest were abstracts, with CXO/Quantpedia summaries standing in for Jacobsen et al., Fan et al. and LRV's tables. No search for decay after 2010 was possible.
- **Selected because:** it covers the program's cross-asset leaders (SPY, dollar, 10-year yield, gold, oil, BTC, credit) and their neighbours (economic links, turnover, COT positioning, rate differentials), and every claim is old enough for 2006-2026 to be out-of-sample.

## What it says

- **Industry economic links (Menzly-Ozbas).** Segmented investors miss news that first moves an industry's suppliers and customers, so the input-output-weighted return of linked industries predicts next month's industry return. It is weaker where analyst coverage is high. OSAP: customer t 4.11, supplier t 5.03 (1986-2005), graded "likely". No magnitude or post-2005 figure was found.
- **Customer momentum (Cohen-Frazzini).** Suppliers follow their major customers' past-month return (investor inattention). 1978-2004: 1.30%/month value-weighted (t 3.03). 2005-2018: 0.62% (t 1.54, not significant). It has roughly halved, and is partly Hou's big-leads-small effect (Pinchuk).
- **Big, high-volume firms lead within an industry (Hou; Chordia-Swaminathan).** High-dollar-volume leaders' weekly returns predict low-volume followers', mostly on bad news, and nonsynchronous trading does not explain it. IndRetBig t 11.0 (1972-2001). The follower leg is neglected small caps, which the archive mostly lacks.
- **Industries lead the market (HTV).** Financial, retail, print and real-estate returns forecast the market by up to two months (1946-2002); gross Sharpe barely beats buy-and-hold. Tse: 1 to 7 of 48 industries significant to 2013. Contested.
- **Oil leads equities negatively (DJM).** Oil rises predict lower stock returns in 12 of 18 markets. Out-of-sample R2 is about 1.2% at one quarter through 2009 (Casassus-Higuera). Untested after 2010, and the sign may have flipped.
- **Copper, sign set by the business cycle (JMV).** Metal rises predict lower returns in expansions and higher in contractions (CFNAI state). Verified only from the 2010 draft: gross, five out-of-sample years of the authors' own. 2010-2026 has almost no contraction months.
- **Gold/platinum ratio (Huang-Kilic).** A tail-risk proxy predicting the equity premium: 1-month R2 just above 1% (t 2.82), 1-year 16.6% (1975-2013). Xu-Li-Singh: the level fails internationally to 2019; only the change predicts. 87.7% of post-2014 levels exceed the 2000-2013 maximum.
- **Equities lead corporate bonds (DUX).** Hourly stock returns lead junk and BBB bond prices; HYG, an ETF, is tied to equities within the hour, and net-of-cost profit is disputed.
- **Bond-return moments predict the equity premium (Li-Yuan-Zhou).** Mean and skewness of corporate bond returns predict the market; abstract only, no numbers.
- **Short-term momentum in high-turnover stocks (Medhat-Schmeling).** Turnover is monthly volume over shares outstanding. High-turnover winners minus losers earn +1.37%/month (t 4.74) and low-turnover stocks reverse (-1.41%, t -7.13), 1963-2018. The largest-500 2x2 earns 0.42% (t 4.91). It survives half-spreads and grew rather than decayed through 2018; 2019-2026 is unmeasured.
- **VIX-conditioned reversal (Nagel).** Reversal returns are the price of liquidity provision and rise with VIX; they are gross, on transaction prices that include bid-ask bounce. Medhat-Schmeling find the VIX link only in small caps.
- **Dollar carry (LRV).** Long developed currencies against USD when the average forward discount is positive, short otherwise: Sharpe 0.66 net of bid-ask, drawdown -31.7% (1983-2010), uncorrelated with cross-sectional carry. Few sign switches, and no figure after 2010.
- **COT speculative pressure (Fan et al.).** Net non-commercial positions relative to their one-year mean capture the hedging-pressure (backwardation) premium. Gross Sharpe: commodities 0.61, currencies 0.47, equity indices 0.50; rates negative (1992-2018). The evidence comes from one research group.
- **Factor momentum (Ehsani-Linnainmaa).** 53 bps/month after a positive year against 1 bp after a losing one. Contested (Fan et al.).

## Evidence quality

**Rating: rigorous.** Thirteen of fifteen claims are in JF, RFS, JFE, JFQA or Management Science, and OSAP replicates four in sample. That is not a tradable edge today: nearly every figure is gross, samples end 2004-2013, and the only post-publication numbers found (Cohen-Frazzini, HTV, the gold/platinum level) show decay or failure.

## What Mandel adopts

- **Short-term momentum in high-turnover stocks is the best-evidenced test now.** `short-term-momentum-high-turnover` runs on point-in-time S&P 500 members over 93 post-sample months. Low power is declared in advance: a positive mean with p >= 0.05 is inconclusive and goes to a forward record. It differs from T-420 and T-319, both on ETFs.
- **Three more tests are runnable now, registered as successors rather than discoveries.** `industry-leader-lead-lag-weekly` and `vix-conditioned-daily-reversal-stocks` (T-462 counted in its deflation) need no new data. So does `dollar-carry-afd-timing`, a time-series bet distinct from T-368's cross-section.
- **`spy-leads-hyg-60m` is the one intraday test, a successor to the T-577/T-578 bond_etf cells.** Those cells had IC +0.10, net -0.05 bp and DSR 0.014. The new test asks whether a thresholded 60-minute rule turns that IC into net return.
- **One shared monthly harness tests five SPY-timing predictors:** oil, gold/platinum change, HTV industries, credit change and, after the ALFRED fetch, copper-by-state. It uses expanding OLS, R2_OS against the historical mean, Clark-West with Holm for multiple comparisons, a 2 bps switching rule, and one joint DSR family that also counts T-458 and T-481.
- **Three tests are kept, blocked on free fetches.** `io-linked-industry-momentum` must beat a permuted-link placebo, so generic co-movement (which sank T-306, T-475, T-308) cannot pass. `cot-speculative-pressure-futures` faces both TSMOM and the historical mean. `customer-momentum-edgar-links` is low priority.
- **The children's reference-price rule sets the expectation.** An edge exists where a source leads the market (fed-funds futures), not where the crowd already reads it; oil, copper, credit and gold are watched, so equities probably absorb them.

## What Mandel holds loosely or rejects

- **Decayed:** customer momentum (value-weighted insignificant after 2005) and the Hou follower leg (small caps). Expect nulls; record them.
- **Contested:** HTV gets a cheap refutation run, expected to be not_supported. The gold/platinum level is pre-declared inconclusive by a range rule that reads no outcomes. Tail-risk proxies have failed before: SKEW in T-52 and T-227.
- **Lead-lag has failed every time costs were charged.** T-424 (BTC into alts) had the wrong sign, t -2.76, and T-467 failed. In VENUE_LEAD_LAG, Polymarket follows Kalshi but a taker loses about 2 points. LAG_2026-10-05's 3-second lead was not tradable. The desk child's 48 macro relations gave one candidate (2s10s -> XLF, t +2.6).
- **A positive IC is not a net return.** T-577 (276 cells) and T-578 (306 cells) passed none. T-579's strongest cross-asset rows are inverse: SPY's 20-day return has IC -0.11 to -0.20 against stocks and ETFs over the next 1-20 days. That is market-level reversal, not a lead.
- **Carry on US venues has failed:** T-368, T-431, T-381 and T-430, and the desk child finds funding rate carry dead on US venues (Hyperliquid's is closed to US persons; not pursued). Dollar carry needs a regime-preserving placebo, since one sign bet can ride a dollar trend.
- **Dropped:** factor momentum duplicates T-388 (Sharpe difference -0.04, DSR 0.08). BTC's overnight move into COIN, MSTR and IBIT has no source, and the desk child's crypto-proxy-crossref (43 trials) calls it beta, not a lead; it defers to H-btc-us500-lead (read 2026-11-05).
- **Not directly tradable:** FF49 legs, paper factors and TRACE moments are proxies; stocks, ETFs, CME futures and OANDA FX execute.

## Design implications for the RSI predictive substrate

- **New F1 leader features for T-579:** roll-masked CL_F and HG_F r1/r5/r20, the change in log gold/platinum, the change in BAA10Y, and duration-hedged HYG and LQD excess returns.
- **New F0 features:** turnover × month-t return, the within-industry high-dollar-volume leader return, and reversal × VIX(t-1). T-580's VIX-level IC is positive, which agrees with Nagel in direction but has not been tested as an interaction.
- **Data to fetch:** BEA Use tables with release dates (concordance hashed before any return is read), ALFRED CFNAI-MA3 vintages, fred-DCOILWTICO, COT for ~22 more contracts with continuous futures, EDGAR major-customer text, OSAP.
- **Shared utilities:** a futures roll-mask (T-468 windows), point-in-time S&P membership with T-473's filters (survivorship reported), and placebos as gates.
- **Monthly signals fill at the next session after month-end.** A fill at the signal's own close is a look-ahead.

## Cross-links

- A4: structure, where it exists, shows at coarser horizons. The claims that survive here are monthly.
- A5: skill is measured against a benchmark, here the historical-mean forecast.
- 12, 13, 14: they propose cross-asset features; this file records which the literature supports and how far each has decayed.
- Theories: T-300, T-306, T-308, T-319, T-368, T-381, T-388, T-405, T-420, T-424, T-430, T-431, T-458, T-462, T-467, T-475, T-481, T-577 to T-580. Children: VENUE_LEAD_LAG_2026-09-23, LAG_2026-10-05, H-btc-us500-lead, H-ibit-carry.

## Sources used

- Medhat-Schmeling: https://openaccess.city.ac.uk/id/eprint/31278/
- OSAP SignalDoc: https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- Menzly-Ozbas: https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1555-1580.html
- Cohen-Frazzini: https://www.aqr.com/Insights/Research/Journal-Article/Economic-Links-and-Predictable-Returns
- Pinchuk: https://ar5iv.labs.arxiv.org/html/2301.11394
- Hou: https://ideas.repec.org/a/oup/rfinst/v20y2007i4p1113-1138.html
- HTV (CXO): https://www.cxoadvisory.com/economic-indicators/market-leading-industries
- Tse: https://works.bepress.com/yiuman-tse/15
- DJM: https://repub.eur.nl/pub/1017
- Casassus-Higuera: https://www.economia.uc.cl/docs/doctra/dt-406.pdf
- JMV (CXO): https://cxoadvisory.com/economic-indicators/industrial-metals-as-asymmetric-equity-return-predictors
- Huang: https://conference.nber.org/conf_papers/f80928.pdf
- Xu-Li-Singh: https://www.emerald.com/insight/content/doi/10.1108/IJMF-06-2020-0328/full/html
- DUX: https://ideas.repec.org/a/cup/jfinqa/v44y2009i05p1081-1102_99.html
- Li-Yuan-Zhou: https://en.rmbs.ruc.edu.cn/Media/Seminars/91a4745e5eb3445ca81e324dc1a8c923.htm
- Nagel: https://www.nber.org/papers/w17653
- LRV: https://www.nber.org/papers/w16427 · https://quantpedia.com/strategies/dollar-carry-trade
- Fan et al. (CXO): https://cxoadvisory.com/equity-premium/net-speculators-position-as-futures-return-predictor
- Ehsani-Linnainmaa: https://www.nber.org/papers/w25551
- IMF: https://www.imf.org/en/Blogs/Articles/2022/01/11/crypto-prices-move-more-in-sync-with-stocks-posing-new-risks
- Not opened (403): SSRN 4938752, 4374753; Management Science 10.1287/mnsc.2017.2933; Alpha Architect.
