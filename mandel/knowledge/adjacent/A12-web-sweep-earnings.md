# Earnings, size and corporate events: what still pays around announcements, share counts, index changes and insider filings

- **Authors / kind:** A literature sweep of 16 strategy claims, mostly peer-reviewed: Martineau (CFR 2022), Garfinkel-Sokobin (JAR 2006), Savor-Wilson (JF 2016), Gao-Xing-Zhang (JFQA 2018), Dubinsky-Johannes-Kaeck-Seeger (RFS 2019), Chang-Hartzmark-Solomon-Soltes (RFS 2017), Johnson-So (JFE 2012, JFQA 2018), DellaVigna-Pollet (JF 2009), Wang-Yan-Zheng (JFE 2020), Asness et al. (JFE 2018), Greenwood-Sammon (HBS WP 2023) and Cohen-Malloy-Pomorski (JF 2012). The replication databases are OSAP and Hou-Xue-Zhang. Practitioner sources: Equibles, Quantpedia, CXO and Wall Street Horizon.
- **Links:** https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf · https://www.biz.uiowa.edu/faculty/jgarfinkel/pubs/drift_JAR.pdf · https://www.lehigh.edu/~xuy219/research/Short_Final_Version.pdf · https://www.hbs.edu/ris/Publication%20Files/23-025_563e45c6-df92-4d9c-ae05-608d4d0acab1.pdf · https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- **Coverage confidence:** 0.65 (24 of 35 sources opened: 7 in full text, 17 at abstract or summary level).
- **Date researched:** 2026-10-20. **How much was read:** Seven texts were read in full via pdftotext: Martineau, Garfinkel-Sokobin, the Savor-Wilson draft, the Dubinsky et al. slides, Wang-Yan-Zheng, Asness et al. and Greenwood-Sammon. Frazzini-Lamont, PBFJ 2023, Ge-Lin-Pearson, Michaely-Rubin-Vedrashko and the vendor beat-rate pages were not opened. The search budget ran out before most post-2015 replications could be looked for. Vendor figures are unverified.
- **Selected because:** This cluster is where the program's inputs meet scheduled corporate events: days until earnings, volume and turnover, shares outstanding, market cap, short interest and implied volatility. Most of its anomalies also have a measured post-publication decay to test against.

## What it says

- **PEAD** (sort on earnings surprise, hold about 60 days; underreaction). Martineau finds no large-cap drift since about 2006. Subrahmanyam (2001-2024) gets t 2.18 for all stocks and t 1.43 excluding microcaps. **Decayed** in investable names.
- **Earnings-day abnormal turnover.** Garfinkel-Sokobin (45,187 NYSE/AMEX announcements, 1985-1998): the top turnover-change group earns +1.386% over 60 days against -0.070% for the bottom group (t 9.49), controlling for the surprise. The mechanism is opinion divergence under short-sale constraints. No post-2000 replication was found.
- **Earnings announcement premium.** Savor-Wilson (1974-2009): announcers beat non-announcers by +0.39%/week equal-weighted (t 14.3). Heitz et al. (summary only) find it gone in the US since the 2004 Form 8-K rule. **Decayed.**
- **Pre-release implied volatility.** Gao-Hu-Zhang (working paper): 71% of the premium arrives in the 10 sessions before the release, because uncertainty resolves early. High implied-volatility names at T-11 gain +1.52% market-adjusted; low ones show nothing. Not replicated.
- **Pre-earnings straddle.** Gao-Xing-Zhang: an ATM straddle held from T-3 through the announcement earns +3.34%, but quoted spreads of 1-3% per side can absorb that.
- **Earnings IV crush.** Dubinsky et al.: implied earnings-day jump volatility "uniformly" exceeds realised, and straddles held over the release lose 8% per event gross. The short side is short gamma, with fat right tails that cluster by name.
- **Earnings seasonality.** Chang et al. (recency bias: forecasters anchor on the recent weak quarters): firms announcing their seasonally strong quarter earn 65 bp/month alpha against 31 bp for the weak-quarter group. Not replicated.
- **Late and Friday announcers.** Johnson-So: managers delay bad news, so late schedulers report worse news, and equity prices ignore the schedule. DellaVigna-Pollet: Friday releases are 45% more likely to be negative surprises, with 60% of the response delayed.
- **Option-to-stock volume.** Johnson-So (1996-2010): when shorting is costly, informed traders with bad news use options, so low-O/S stocks beat high-O/S stocks by 0.34%/week. No evidence after 2010.
- **Short volume.** Wang-Yan-Zheng (FINRA, 2010-2015): heavily shorted stocks underperform by 12.6%/yr equal-weighted (t 6.0). Abnormal short-term shorting does not anticipate bad news; only 20-60-day flows persist.
- **Analyst revisions.** Investors underreact to consensus EPS changes. OSAP AnalystRevision earns 0.46%/month (t 3.17, 1975-1980). McLean-Pontiff: returns fall 58% after publication.
- **Size premium given quality.** Asness et al. (1957-2012): SMB alpha rises from 14 bp (t 1.23) to 49 bp (t 4.89) with QMJ as a control. The raw small-cap premium has decayed.
- **Share issuance and buybacks.** Managers time the market. Fu-Huang: about +10% over three years after buybacks and -12% after equity offerings before 2003, about 0 for 2003-2008. **Decayed.**
- **Index inclusion.** Greenwood-Sammon: the addition return fell from 7.4% in the 1990s to 0.3% in the past decade. Index-fund rebalancing offsets the effect for migrations. In the 2010s direct additions earned +5.4% and migrations +1.8% (not -1.8%), on a window that includes the announcement-night jump, which cannot be traded. **Decayed.**
- **Insider buying.** Cohen-Malloy-Pomorski (1986-2007): opportunistic purchases earn 82 bp/month. Equibles (2020-2025, 47,458 purchases): buyers trail the S&P 500, with no timing premium. arXiv 2602.06198: what is left sits in a day-1 overnight gap. **Decayed.**
- **Dividend initiations.** Michaely-Thaler-Womack (1964-1988, mostly small firms): a dividend change signals persistent earnings and investors underreact; initiation drift t 3.37. No post-1995 replication was found.

## Evidence quality

**Rating: rigorous.** The sources are peer-reviewed, use large samples and are catalogued in OSAP and Hou-Xue-Zhang. That rigour belongs to measurements that are in-sample, gross of transaction costs and mostly from before 2010. The decay evidence is thinner and partly working-paper or practitioner work.

## What Mandel adopts

- **Earnings event variance ratio** (`earnings-event-variance-ratio-vx3`), the strongest claim. It compares implied event variance from VXAPL, VXGOG and VXAZN (2011-2026, about 185 events) with realised variance, after four free SEC calls. It belongs to the variance risk premium class that Mandel supports in T-244, T-246 and T-148. T-224 found the reverse on macro days, where a flat 30-day GVZ under-prices event-day variance, but single-stock implied volatility is event-aware. A pass does not fund anything: the deciding arm uses quoted prices in T-207's defined-risk form, because Hurst's IBIT condor had a worst month of -168%.
- **FINRA short-volume level** (`finra-svr-quarterly-level-sp500`), testable now. It is the persistent-flow sibling of T-394, whose spike version was null (+0.7 bp gross), and it is deflated together with T-394.
- **SMB alpha after junk controls, out-of-sample from 2013**, testable now. It asks whether T-385 failed through junk exposure (RMW loading t 4.68).
- **Dividend-initiation drift**, testable now. It is long-only, with a minimum detectable effect of about 7.4 pp at n of about 90.
- **Price-free event variables.** These are the turnover change dTO (with a non-event baseline, because T-419, T-546 and T-578's relative-volume IC of about +0.01 were weak), the expected-announcer premium (T-339 on 8-K dates, with a null expected), the late-announcer short, the seasonality score and a pre-release implied-volatility test with a difference-in-differences placebo.
- **O/S as a forward test only:** 100 or more names, read at 104 weeks.

## What Mandel holds loosely or rejects

- **Large-cap PEAD** runs only as T-338's control. Hurst's own small-cap PEAD was killed by its placebo: an entry 25 sessions late earned +1.77%/month against +1.32% for the real entry.
- **Insider buying** duplicates T-391. The child's 28,706-event study (EDGE_VERDICT 21e) earned +0.00% against SPY.
- **Buybacks and share issuance** stay under T-449, which is not_supported (+0.30%/month, CI -0.18 to +0.86).
- **Index inclusion** stays under T-453 (T-334 is inconclusive). The migration split is post-hoc.
- **The pre-earnings straddle** stays under T-204. Pricing it on constant-maturity VX is circular, as T-57 showed.
- **Revisions** stay under T-396. **The dividend-month premium** stays rejected (T-374), and so does Friday attention (T-347).
- **Venue limits.** Alpaca small accounts probably cannot sell naked straddles, so only defined-risk structures are allowed. Short legs need borrow.

## Design implications for the RSI predictive substrate

- **Data unlock:** re-fetch data.sec.gov submissions keeping `items` and non-XBRL forms for about 1,100 historical S&P 500 CIKs. That gives 8-K Item 2.02 acceptance times, with D defined as the first session whose open follows acceptance. Seven rows depend on it. A companyfacts re-fetch would add 10-Q NetIncomeLoss as filed.
- **Point-in-time ML features,** with price isolated as the target: days to the expected earnings date, a late flag, the turnover change, the 60-day short-volume level, the 12-month change in shares outstanding, an initiation flag, the implied event variance and a seasonality score. CAR is excluded because it is price-derived.
- **Look-ahead tests:** 8-K acceptance against wire time; 16:00 releases against the VX close; split-adjusted volume against as-filed shares; the FINRA backfill vintage.
- **Statistics:** a survivorship flip test (rule 9) and a block bootstrap on every panel.
- **Option data:** verify DoltHub single-stock implied volatility coverage, and extend the capture box's CHAIN_SYMBOLS to the S&P 100.

## Cross-links

- A4: earnings-day variance is a scheduled fat-tail jump. A5: the decay of PEAD and the day-1 insider reaction both measure how fast information reaches the price.
- 12, 13, 14: earnings features belong there with D+2 entry and placebo dates.
- Theories: T-338, T-452, T-339, T-204-T-207, T-248, T-394, T-396, T-385, T-449, T-453, T-334, T-391, T-374, T-347, T-419, T-546, T-224, T-244, T-521, T-538, T-578.

## Sources used

- Martineau (2022) https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf
- UCLA Anderson Review https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- Garfinkel-Sokobin https://www.biz.uiowa.edu/faculty/jgarfinkel/pubs/drift_JAR.pdf
- Savor-Wilson https://faculty.wharton.upenn.edu/wp-content/uploads/2012/04/Draft20111215p_edited.pdf
- Heitz et al. https://paperswithbacktest.com/strategies/the-disappearing-earnings-announcement-premium
- Gao-Hu-Zhang https://quantpedia.com/pre-announcement-returns/
- Gao-Xing-Zhang https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/anticipating-uncertainty-straddles-around-earnings-announcements/7B34877AD5E06304BA3C55FBA3219FDD
- Dubinsky et al. https://www.stern.nyu.edu/sites/default/files/assets/documents/NYU%20conference%20Johannes%20final.pdf
- Chang et al. https://ideas.repec.org/a/oup/rfinst/v30y2017i1p281-323..html
- Johnson-So https://ideas.repec.org/a/cup/jfinqa/v53y2018i06p2431-2464_00.html · https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html
- DellaVigna-Pollet https://www.nber.org/papers/w11683
- Wang-Yan-Zheng https://www.lehigh.edu/~xuy219/research/Short_Final_Version.pdf
- OSAP https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- Asness et al. https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2015/05/Size-Matters-if-You-Control-Your-Junk.pdf
- Hou-Xue-Zhang https://www.nber.org/papers/w23394
- Fu-Huang (CXO) https://www.cxoadvisory.com/buybacks-secondaries/extinction-of-the-buybacksecondary-offering-effect
- Greenwood-Sammon https://www.hbs.edu/ris/Publication%20Files/23-025_563e45c6-df92-4d9c-ae05-608d4d0acab1.pdf
- Cohen-Malloy-Pomorski https://www.nber.org/papers/w16454.pdf
- Equibles https://equibles.com/research/what-happens-after-an-insider-buys-evidence-from-47-458-open-market-purchases
- arXiv 2602.06198 https://arxiv.org/html/2602.06198v2
