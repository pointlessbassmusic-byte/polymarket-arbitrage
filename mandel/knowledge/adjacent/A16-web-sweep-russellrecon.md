# Russell 1000/2000 reconstitution and other rule-based index migrations: migrant flows, cutoff effects, post-recon reversal and how far they have decayed (literature survey)

- **Authors / kind:** Literature survey of 16 candidate strategies on index-membership flows beyond S&P 500 additions, each source-checked and re-registered by a verifier (13 fixed, 3 dropped). Core papers: Chang, Hong & Liskovich (RFS 2015, "CHL"); Madhavan (FAJ 2003); Pavlova & Sikorskaya (RFS 2023, "P-S"); Chinco & Sammon (JFE 2024); Greenwood & Sammon (JF 2025); Ben-David, Franzoni & Moussawi (JF 2018, "BFM"); Cai & Houge (FAJ 2008); Shankar & Miller (2006); critiques by Wei & Young (CFR 2024) and Appel, Gormley & Keim. Practitioner: Dimensional, FTSE Russell/LSEG, Cboe, S&P DJI, QuanterLab.
- **Links:** https://www.nber.org/papers/w19290 · https://www.dimensional.com/us-en/insights/even-migrating-stocks-face-index-reconstitution-costs · https://conference.nber.org/conf_papers/f147357/f147357.pdf · https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/ftse-russell-announces-december-2026-russell-us-indexes-reconstitution-schedule
- **Coverage confidence:** 0.55 (fraction of the sources actually read and verified: 18 of 33, six only as abstracts or digests).
- **Date researched:** 2026-10-21. **How much was read:** full text of CHL, Madhavan, the P-S 2021 draft, Chinco-Sammon, Greenwood-Sammon and Wei-Young; the Dimensional, LSEG, Cboe and QuanterLab articles; FTSE Russell's June 2026 summary and December 2026 schedule; abstracts of Shankar-Miller, Cai-Houge, Akhigbe et al., Biktimirov-Xu, Micheli-Neuman and the BFM digest. Not opened: S&P DJI's Indexology posts (403; figures from search summaries), Nasdaq's 2026 FAQ (404), Petajisto, Appel-Gormley-Keim.
- **Selected because:** market cap, shares outstanding, volume, dollar volume, short interest and calendars are inputs of the user's program, and index membership (index addition and deletion) is the adjacent variable that turns them into a scheduled, inelastic demand shock. Mandel's S&P 500 versions are inconclusive or blocked (T-334, T-340, T-453), and the first December Russell reconstitution in over 30 years is a clean forward event if registered before Rank Day (2026-10-30).

## What it says

- **Downward migrants (R1000 to R2000).** Both indices are value-weighted, so a migrant's weight jumps about 10-15x and R2000-benchmarked money must buy (P-S: passive funds buy an extra 112 bp of shares). CHL (1996-2012, regression discontinuity): +5.6% in June against just-missed stocks (t 2.65), nothing in July or August. Dimensional (2014-2023): +1.2% vs the R2000 over the 20 days before recon, -0.95% over the 20 after. Decayed: Chinco-Sammon find recon-day returns converged to nearly zero over 2000-2021, and FTSE Russell (2026) says short-term effects have not reliably followed the pattern.
- **Upward migrants (R2000 to R1000).** The mirror: R2000 trackers sell and active R2000 funds cut ownership by 46 bp. CHL: -5.4% in June (t 3.0); Dimensional: -1.1% before recon, about +2% after. June 2026 had 42 upward and 39 downward migrants: small cross-sections.
- **Post-recon reversal.** Madhavan (1996-2002): the R2000 additions-minus-deletions spread was negative in July in 6 of 7 years. CHL find no significant reversal at the 1000 cutoff. Contested; migrants' pre-recon moves oppose the trade, so generic short-term reversal can mimic it.
- **Benchmarking intensity and passive demand in days of volume.** P-S (1998-2018, 34 indices): the top quartile of benchmarking-intensity change earns +80 bp in June relative to the average stock, the bottom quartile -110 bp; demand elasticity -3.03. Chinco-Sammon: changed names trade 9.5x normal volume on recon day. No post-2018 replication.
- **Long-run benchmarking discount.** P-S: R2000 addition lowers returns about 60 bp a month for five years (1998-2006) and deletion raises them 48 bp; after 2007 about -26/+28 bp, the addition effect sometimes insignificant. Wei-Young find weight-based ranks at the cutoff introduce selection bias.
- **Lower cutoff (rank about 3000).** No band at the bottom of the R2000. Madhavan: additions minus deletions +10.78% in June, all 7 Junes positive, but his March-May figures are inflated by forming portfolios on actual membership. CHL (2005-2012): t 1.25-1.45, not significant.
- **Deletions beat additions over 12 months.** Cai-Houge (1979-2004): buy-and-hold beat the rebalanced R2000 by 2.22% at one year. Unreplicated since 2004; the deletion leg lives in delisted microcaps.
- **IJR minus IWM after recon.** S&P DJI, seen only through search summaries: a seasonal July spread, the S&P 600 beating the R2000 by +0.68% in July 1994-2014 (t 2.54).
- **Nasdaq-100 December.** Biktimirov-Xu: first-time additions keep their gains, repeat additions and deletions revert (no magnitudes). QuanterLab (one-year holds): deletions beat QQQ by 18.7 points per window before 2016 and trailed by 16.3 after.
- **S&P 400/600.** Shankar-Miller: direct entrants react more than inter-index migrations, fully reversed within 60 days. Greenwood-Sammon (S&P 500, NBER 2022 version): index effect 7.6% to 0.8%; late-2010s direct additions +2.2%, migrations -2.3%.
- **Volatility, turnover and beta.** BFM (2000-2012, Russell switchers): one SD more ETF ownership raises daily volatility and turnover about 16%. CHL: co-movement with the new index rises.
- **Closing auction.** LSEG: $102.5bn on Nasdaq and $114.7bn on NYSE traded at the 27 June 2025 close. Chinco-Sammon: recon-day price pressure is near zero.
- **RVX in recon windows.** Cboe (2022): RVX mostly sat below its annual average in May-June since 2015. No statistics.

## Evidence quality

**Rating: mainstream-educational.** The academic core is rigorous (discontinuity and IV designs at the Russell cutoff, RFS/JFE/JF), but its identification is contested, most samples end by 2012-2018, and the out-of-sample evidence is practitioner work, gross of costs, showing effects decayed about fivefold, or to zero. The IJR and RVX claims are commercial and untested.

## What Mandel adopts

- **Two testable-now trials, pre-registered before measurement.** `ijr-minus-iwm-post-russell-recon` (recon close to +20 sessions; within-year permutation null avoiding recon and S&P rebalance weeks; post-2015 half positive) joins T-385's family, whose unconditional spread failed (+0.22%/yr, DSR 0.001). `rvx-vrp-russell-recon-window` is a one-sided conditional successor to T-65 (RVX variance risk premium, not_supported, p 0.0945) with a required opex-matched contrast, because June recon windows also hold quad witching and the FOMC, and T-216 (supported) shows expiries move the variance gap.
- **A 6-trial migrant family under Holm:** downward run-up, upward short (each with a Rank-Day variant) and the 20-session reversal at the close and next open, with a short-term-reversal control. Out-of-sample 2013-2026, entered only after the preliminary list is published, keeping names later removed.
- **Lower-cutoff Microcap movers** with spread-based costs, excluding newly eligible names, IPOs and spin-offs.
- **Gated or long-horizon arms:** passive demand in days of volume only if a migrant test passes; the 12-month benchmarking spread and deletions-minus-additions in one DSR family.
- **Nasdaq-100 December arms** (predictions frozen at the ranking date) and **S&P 400/600 direct additions**, whose timestamped change list also unblocks T-340 and T-453.
- **Migrants' volatility and turnover shift** against total-cap-matched stayers; the implied volatility leg is forward-only on chain captures.
- **A December 2026 forward record**, frozen before Rank Day, never pooled with June.
- The children agree: their `closedTime` landmine (an anchor that conditions on the outcome) is the trap of signalling on ex-post membership; Hurst killed small-cap post-earnings drift when a placebo entry beat the real one, so every trial has a placebo; T-334 priced only 82.6% of its additions, so survivorship is reported per event.

## What Mandel holds loosely or rejects

- **Effect size.** CHL's 5.6% has decayed to Dimensional's 1.2% gross and Chinco-Sammon's near zero; at 30 bp round trip and 14 out-of-sample Junes the migrant trade sits at the detection limit. A discontinuity against just-missed stocks is not a tradable return against IWM, and migrants are momentum-sorted against the trade.
- **Closing-auction overnight reversal: dropped.** Chinco-Sammon measure no pressure, T-428 is not_supported, and the generic claim is T-664.
- **Short interest conditioning: dropped.** Akhigbe et al. report contemporaneous co-movement, not a pre-entry days-to-cover predictor, with the opposite sign to the candidate; RegSHO short volume covers about 600 symbols; T-393 and T-375 are inconclusive.
- **Quarterly IPO additions: dropped.** Micheli-Neuman imply less crowding; data blocked as for T-523.
- **December tax-loss stacking** is anecdotal: T-351, T-444 and T-440 are not_supported. Madhavan's March-May returns are look-ahead. Weight-based matching and practitioner screens (passive buying over 5x ADV, float under 40%) are rejected. Pre-2026 Nasdaq-100 history may not represent the new rules.
- Every trade uses Alpaca stocks, ETFs and options or CME RTY futures; nothing needs an offshore venue.

## Design implications for the RSI predictive substrate

- **Data to add:** FTSE Russell preliminary and final lists with publication timestamps and source/destination index; iShares IWB/IWM/IWC holdings history; delisting-aware prices; a sourced Rank Day/list/recon calendar (31 May until 2015, early or mid May 2016-2022, 30 April 2024-2026); a full-universe SEC shares outstanding fetch (36 of 44 CIK buckets archived); N-PORT tracker AUM; S&P 400/600 and Nasdaq-100 change lists; the French short-term-reversal factor.
- **Harness:** extend T-334's event study with `russell_membership(rank_day, caps, prior_members, band=0.025)` with list-accuracy, FINRA publication-lag and survivorship reports.
- **Features for T-577/T-578:** sessions to Rank Day and recon, a recon-window flag for IWM/IJR, predicted migrant flag, distance from the band edge, predicted passive demand over 20-day median dollar volume, days to cover at publication.
- **Forward:** freeze December predictions before 2026-11-13 and capture chains for predicted migrants.

## Cross-links

- A6 (opex: the 2026-12-11 recon falls a week before quad witching), A7 (short interest, borrow fees), A10 (volume, ETF flows), A11 (implied volatility, VRP), A12 (S&P 500 index inclusion), A13 (closing auction, overnight), A14 (turn of year). 12, 13, 14: recon-window features belong there.
- Theories: T-334, T-340, T-453, T-385, T-65, T-216, T-57, T-351, T-444, T-440, T-428, T-664, T-549, T-393, T-375, T-523, T-577, T-578.

## Sources used

- CHL https://www.nber.org/papers/w19290
- Dimensional https://www.dimensional.com/us-en/insights/even-migrating-stocks-face-index-reconstitution-costs
- Chinco-Sammon https://www.hbs.edu/ris/Publication%20Files/double-what-you-think-it-is%20may%2023_3c1ae213-5aec-407d-b656-13e3822f0b8b.pdf
- P-S https://conference.nber.org/conf_papers/f147357/f147357.pdf
- Madhavan https://www.hillsdaleinv.com/uploads/The_Russell_Reconstitution_Effect,_Ananth_Madhaven,_Financial_Analysts_Journal,_JulyAugust_2003,_Pages_51-64.pdf
- Greenwood-Sammon https://www.nber.org/system/files/working_papers/w30748/w30748.pdf
- Wei-Young https://cfr.ivo-welch.info/published/papers/wei2020selection.pdf
- Appel-Gormley-Keim (not opened) https://cfr.ivo-welch.info/published/papers/appel2020identification.pdf
- BFM https://www.nber.org/digest/sep14/do-etfs-increase-stock-volatility
- Shankar-Miller https://ideas.repec.org/a/bla/finrev/v41y2006i3p339-360.html
- Cai-Houge https://ideas.repec.org/a/taf/ufajxx/v64y2008i4p76-91.html
- Akhigbe et al. https://ideas.repec.org/a/eee/quaeco/v84y2022icp577-588.html
- Micheli-Neuman https://arxiv.org/abs/2006.07456
- Biktimirov-Xu https://ideas.repec.org/a/pal/assmgt/v20y2019i2d10.1057_s41260-019-00108-6.html
- QuanterLab https://quanterlab.com/research/nasdaq-100-additions-versus-deletions-eighteen-decembers-an-effect-that-died-aro
- S&P DJI (403) https://www.indexologyblog.com/2015/03/25/a-tale-of-two-benchmarks-reconstitution-effect/
- LSEG https://www.lseg.com/en/insights/ftse-russell/more-key-facts-ahead-of-the-2026-russell-us-indexes-reconstitution
- FTSE Russell June 2026 summary https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/2026-russell-us-indexes-reconstitution-summary.pdf
- FTSE Russell December 2026 schedule https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/ftse-russell-announces-december-2026-russell-us-indexes-reconstitution-schedule
- Cboe https://www.cboe.com/insights/posts/russell-reconstitution-opportunities-to-harvest-volatility
