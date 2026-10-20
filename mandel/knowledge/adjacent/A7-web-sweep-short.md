# Short interest, short volume, securities lending and squeezes: what the positioning literature predicts, and what survives borrow fees

- **Authors / kind:** literature survey. Journal papers: Rapach-Ringgenberg-Zhou (RRZ, JFE 2016), Boehmer-Jones-Zhang (BJZ, JF 2008), Boehmer-Huszar-Jordan (BHJ, JFE 2010), Lynch-Nikolic-Yan-Yu (LNYY, JFM 2014), Wang-Yan-Zheng (WYZ, JFE 2020), Engelberg et al. (Mgmt Sci 2025), Muravyev-Pearson-Pollet (MPP, JF 2025), Asquith-Pathak-Ritter (APR, JFE 2005). Working papers: Hong et al., Drechsler-Drechsler, Evans et al., Hanauer et al. Practitioner sources (SqueezeMetrics, CXO, Quantpedia), the SEC staff report on early 2021, and Chen-Zimmermann's replication.
- **Links:** https://www.lehigh.edu/~xuy219/research/Short_Final_Version.pdf · https://conference.nber.org/conf_papers/f184100/f184100.pdf · https://squeezemetrics.com/monitor/download/pdf/short_is_long.pdf · https://www.sec.gov/files/staff-report-equity-options-market-struction-conditions-early-2021.pdf
- **Coverage confidence:** 0.58 (about 24 of 41 cited sources opened and checked, 8 of them read in full or to table level; for 3 of the 15 candidates no source could be read).
- **Date researched:** 2026-10-20. **How much was read:** SqueezeMetrics, WYZ (Tables 2, 5, 7), MPP's Appendix Table 1, Evans et al., the SEC report, Dwars and the Chen-Zimmermann rows were read in full or to table level. The others were read only as abstracts or CXO summaries. SSRN returned 403 and four other sources would not open. Several cited works were not reopened (MPP 2022, Christophe-Ferri-Angel, Diether-Lee-Werner, Kelley-Tetlock). Every data claim was checked against Mandel's finra-short-interest (211 releases) and finra-regsho-cnms (2,063 file days) bundles.
- **Selected because:** short interest, days to cover and short volume are inputs to the learning program, and Mandel holds the free FINRA files for 2017-2026. Three registered theories (T-454, T-393, T-375) stalled on data that is now partly in hand.

## What it says

- **Aggregate short interest (SII).** The detrended equal-weighted SI ratio is claimed as a leading indicator of lower S&P 500 excess returns at 1-12 months, through cash flows. RRZ (1973-2014): annual R² of 12.89% in sample and 13.24% out of sample. **Decayed in the US:** excluding crises leaves R² at 0.13% (Dwars, 1973-2021), so the result rests on 2008. Internationally the sign holds in 29 of 32 countries (Gorbenko, 2006-2016).
- **Aggregate daily shorting flow.** A 1-SD rise goes with market returns up to 36 bp lower over 10 days (LNYY). No replication was found.
- **DIX ("short is long").** SqueezeMetrics read off-exchange short volume as market makers filling buyers. They report a 60-day S&P 500 return of 5.3% after DIX ≥ 45% vs 2.8% unconditional (2011-2018, in sample, no costs). Their own text says DIX "tends to rise into corrections". Their stock-level chart is a same-day relation, so using it as a predictor would be look-ahead.
- **Persistent shorting flow.** BJZ (2000-2004): heavily shorted stocks underperform by a risk-adjusted 1.16% over 20 days. WYZ (FINRA daily files 2010-2015, the CNMS source) find an FF3 alpha of −12.6%/yr EW (t 6.0). Their long window (−65..−6) gives a spread of 6.2 bp/day EW. Abnormal short-term flows do not predict, and there is no reversal.
- **Good news in low short interest.** Heavily traded low-SI stocks earn positive abnormal returns (BHJ). In WYZ the spread comes from the low-shorting quintile (5.2 bp/day EW, t 6.38; weaker in large caps). This half needs no borrow.
- **Days to cover.** Hong et al. (1988-2012): EW L/S 1.19%/month gross. **Contested:** Quantpedia's out-of-sample backtest is slightly negative, and Chen-Zimmermann's short-interest row has t ≈ 1.0.
- **SI surprise (SUSI).** SI against its own 12-month mean and sd: EW decile L/S 0.43%/month gross (Hanauer et al., 1980-2013). Stronger around earnings and unrelated to shorting costs. No replication was found.
- **Borrow fees.** The loan-fee L/S earns 4.01%/month gross (Engelberg et al.), and anomalies vanish in the 80% of low-fee stocks (Drechsler-Drechsler, about 2004-2012). **MPP's replication (2006-2020) is decisive:** 162 anomalies go from 0.15%/month gross to −0.02% after the borrow fee. The short-interest row goes from −0.41% to −0.06% without high-fee names. The short leg is a fee transfer to lenders.
- **SI over institutional ownership.** High-SI EW portfolios underperform; VW ones do not, and the result is fragile across sub-periods (APR). The published signal lives in the top 1% of SI.
- **FTDs and operational shorting.** ETFs accounted for 78% of FTDs in 2016, and operational shorting "is not a significant predictor of future ETF returns" (Evans et al.).
- **Shorting before earnings.** None was found before negative news in 2010-2015 (WYZ).
- **Short squeezes.** GME short interest peaked at 109.26% of shares. Covering was a small share of buying, and the SEC found no gamma squeeze. This is a tail-risk pattern with no out-of-sample prediction record.

## Evidence quality

**Rating: rigorous.** The core is peer-reviewed, risk-adjusted and independently replicated (WYZ of BJZ, MPP, Chen-Zimmermann), but what that work mostly establishes is decay: short legs are fee transfers, the US SII rests on 2008, and modern public data show no shorting before news. DIX and the squeeze material are practitioner tier. The ETF-hedging, ETF-synthetic and INFO-composite claims could not be verified.

## What Mandel adopts

- **`aggregate-short-interest-finra-rawdtc`**, a re-scope of T-454. The signal is log(1 + SI/ADV) from raw fields, recursively detrended. It must beat a volume-only placebo, because FINRA floors `daysToCoverQuantity` at 1.00 on 13-34% of common-stock rows. Expected result: an underpowered null (about 139 OOS releases, no GFC), matching T-398 and T-458, two aggregate timing predictors that failed out of sample.
- **Rival CNMS signs, deflated jointly (4-cell Bonferroni):** `aggregate-offexchange-svr-spy-10d` (pre-registered negative) and `dix-dollar-weighted-svr-spy-60d` (pre-registered positive). The ratio drifted from 0.42 to 0.52, so only trailing windows are used (a 60-day z, and a 252-day rank for DIX); an expanding history would act as a 2022-26 dummy. Both tests include a price-only dip control, because short volume rises into dips. T-394's spike null (+0.7 bp gross) fits the market-maker reading.
- **`low-short-interest-long-sp500`.** This is the executable, borrow-free half, and MPP's fee critique does not touch it. Controls: FF5+UMD+BAB, since low-SI large caps load on quality and low volatility, both dead in T-383 and T-384. Shares outstanding are split-adjusted, and survivorship is handled with a tipping-point bound.
- **`persistent-offexchange-svr-xs-monthly`** (WYZ's window, formed at month-end, residualised on dollar volume) and **`short-interest-surprise-susi-sp500-monthly`** (monthly, split-restated). Both are distinct from T-394.
- **`crowded-short-funding-oi-filter-t556-forward`** journals Kalshi perp funding rate and open interest at each T-556 short. It is a risk filter, and per T-564 a filter that lowers the mean is rejected.
- **By-products with no verdict:** the DTC L/S attached to T-393, an ETF short-interest diagnostic, and IBKR fee capture as an amendment to T-375 and T-193.

## What Mandel holds loosely or rejects

- **SI/DTC long-short and loan fees as alpha.** Both are fee transfers, and Mandel's survivor-only runs are null (T-393 net −0.05% per release; T-375 +0.36%/month against a 0.83% bar). Borrow consumed the short edges in T-185 and T-325.
- **SII's headline R²:** crisis-dependent and decayed.
- **ETF short interest as bullish hedging (or a lagged ETF flows proxy), and ETF-implied constituent shorting (94 bp/month).** The sources are unverified, and the verified ones (Evans; Hughen-Ma) show no relation.
- **Parked:** FTD signals (Evans's null), pre-earnings shorting (needs 8-K Item 2.02 dates), INFO (paywalled; a two-component version would be a forking path; needs T-391's Form 4 insider filings) and SI/IO (about 5 S&P names; needs 13F, as T-392 does).
- **Squeeze-chasing.** There is no out-of-sample evidence, and no GME/AMC StockTwits history. Crypto crowding is traded only on US-legal venues (Kalshi perps, Coinbase Derivatives), and offshore funding feeds are never routed around geoblocks.
- **Children (EDGE_VERDICT Result 18, reference-price learnings).** Informed footprints point to a source; they are not signals to copy. Positioning every desk reads is a consensus, not a leading reference, so the prior is low.

## Design implications for the RSI predictive substrate

- **Fix `mandel/ml/features.py`.** `si_dtc` reads the floored `daysToCoverQuantity`, and only from 2025-26. Use raw log1p(SI/ADV) from 2017-12 instead. Add `si_susi`, short-volume-ratio features (the 60-day z, its 5-day change, the residualised −65..−6 mean), and market-level SII and DIX percentile features, run as an ablation family in T-578 (306 cells, 0 pass so far).
- **Two shared harnesses.**
  - FINRA-release harness: available_at = end of the 8th NYSE business day after settlement; revisionFlag rerun; split adjustment.
  - CNMS harness: membership by effective date, a 450-member floor, a backfill flag before mid-2021-05, and trailing z-scores only.
- **Data to add:** prices for about 108 former members, Goyal's SII, the DIX CSV (as a cross-check only), a daily IBKR shortable-stock capture, and 8-K Item 2.02 dates (also for T-339 and T-452). Later: N-PORT, 13F and the Kalshi open-interest journal.
- **Metrics:** Clark-West OOS R² with block-bootstrap CIs, net returns per release, FF5+UMD(+BAB) alpha, DSR at declared trials, and the tipping-point bound.

## Cross-links

- A4: squeezes are fat-tail jumps; size stops by the jump tail. A5: slow incorporation of public SI is an information-decay question.
- 12, 13, 14: positioning features belong in those pipelines only with point-in-time stamps and a placebo.
- UNDERLYING-STRATEGIES.md; OPTIONS-STRATEGIES.md (implied borrow via put-call parity); SOCIAL-SOURCES.md; venues/US-LEVERAGE-VENUES-2026-10-20.md.
- T-454, T-393, T-375, T-394, T-193, T-183, T-185, T-325, T-556, T-564, T-303, T-423, T-398, T-458, T-391, T-392, T-399, T-339, T-452, T-383, T-384, T-578.

## Sources used

- RRZ (abstract read on IDEAS): https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2474930 · Gorbenko: https://academic.oup.com/raps/article/13/4/691/7127046 · Dwars: https://thesis.eur.nl/pub/73709/Thesis_Final_Draft.pdf
- LNYY: https://ideas.repec.org/a/eee/finmar/v17y2014icp199-229.html · WYZ: https://www.lehigh.edu/~xuy219/research/Short_Final_Version.pdf
- SqueezeMetrics: https://squeezemetrics.com/monitor/download/pdf/short_is_long.pdf
- BJZ: https://ideas.repec.org/a/bla/jfinan/v63y2008i2p491-527.html · BHJ: https://ideas.repec.org/a/eee/jfinec/v96y2010i1p80-97.html
- Hong et al.: https://nber.org/papers/w21166 · Quantpedia: https://quantpedia.com/strategies/short-interest-effect-long-short-version/
- SUSI (CXO): https://www.cxoadvisory.com/short-selling/surprise-in-short-interest-as-stock-return-predictor/
- Engelberg et al.: https://ideas.repec.org/a/inm/ormnsc/v71y2025i7p5529-5551.html · Drechsler-Drechsler: https://www.nber.org/papers/w20282 · MPP: https://conference.nber.org/conf_papers/f184100/f184100.pdf
- APR: https://www.nber.org/papers/w10434 · Chen-Zimmermann: https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- Evans et al.: https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2018/08/ETF-Short-Interest-and-Failures-to-Deliver.pdf · SEC: https://www.sec.gov/files/staff-report-equity-options-market-struction-conditions-early-2021.pdf
- Hughen-Ma (CXO): https://www.cxoadvisory.com/short-selling/etf-short-interest-and-future-returns/ · INFO (CXO): https://www.cxoadvisory.com/investing-expertise/signals-from-trading-volumes-of-informed-traders/
- Unreadable, unverified: https://scholars.utoledo.edu/display/pub-001694186100001 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4527115
