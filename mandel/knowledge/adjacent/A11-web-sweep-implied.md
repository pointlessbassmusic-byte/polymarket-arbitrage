# Options-implied information as a return predictor: implied volatility level, skew, term structure and the variance risk premium (literature survey, 1996-2026)

- **Authors / kind:** 15 published strategies. Peer-reviewed: Bali-Hovakimian (Management Science 2009), Goyal-Saretto (JFE 2009), Cremers-Weinbaum and Xing-Zhang-Zhao (JFQA 2010), An-Ang-Bali-Cakici (JF 2014), Vasquez and Johnson (JFQA 2017), Cheng (RFS 2019) and Bollerslev-Tauchen-Zhou (BTZ; RFS 2009). Working papers: Buss-Schönleber-Vilkov, Simon-Campasano, Park (FEDS 2013-54), Almeida et al., and Li-Wang (arXiv 2608.26115), the only 2015-2026 re-estimation. Replications and summaries: Open Source Asset Pricing (OSAP), theses, GitHub backtests, CXO, Quantpedia.
- **Links:** https://arxiv.org/abs/2608.26115 · https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv · https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf · https://www.federalreserve.gov/pubs/feds/2013/201354/201354pap.pdf
- **Coverage confidence:** 0.55 (25 of 39 cited sources opened, six of them in full text).
- **Date researched:** 2026-10-20. **How much was read:** full text for Li-Wang, Almeida et al., BTZ Table 2, Park, a CBS thesis and the OSAP rows. Abstracts only for the other journal papers; practitioner summaries otherwise. Unreadable: CEPR DP12760, Simon-Campasano, Neuhierl et al., Neo's dissertation. The search budget ran out before targeted decay searches.
- **Selected because:** implied volatility, skew, term structure and the VRP are inputs in the user's training program. T-580's market-level options-implied ML family is not supported (best DSR 0.368), and no cross-sectional single-stock options signal has been tested: T-531 and T-193 are blocked.

## What it says

- **RV-minus-IV spread (Bali-Hovakimian).** Stocks whose implied vol is rich relative to 30-day realised vol earn more. The value-weighted quintile spread is 0.732%/month (t 2.9) over 1996-2004, the original figures that OSAP's replication matched. There is no evidence after 2004.
- **HV-minus-IV straddles (Goyal-Saretto).** Long straddles where options are cheap relative to historical vol and short where they are rich earn a significant return over 1996-2005. The widely quoted 15%/month belongs to a different working-paper strategy, so this sort's effect size is unverified.
- **Call-minus-put IV spread (Cremers-Weinbaum).** Informed demand pushes the favoured side's IV off put-call parity. Expensive-call stocks beat expensive-put stocks by about 50 bp/week over 1996-2005, with decay inside that sample. A CBS thesis finds 19 bp/week (t 2.45) for 2011-2015. Li-Wang's 21-day slope has t 7.0 over 2015-2026 and t 4.2 in 2023-26. This is the cluster's best survival record, but every figure is gross.
- **Volatility smirk (Xing-Zhang-Zhao).** The steepest OTM-put-minus-ATM-call smirks underperformed by 10.9%/year over 1996-2005. OSAP rates it only 'likely' (0.64%/month, t 2.19). The effect has **decayed**: t -5.5 (2015-19), t -4.2 (2020-22), t -1.5 (2023-26), and the sign flips at 63 days.
- **OTM-IV skewness proxy (Li-Wang).** The cross-strike skewness of OTM IVs predicts lower returns (21-day t -11.7 in 2023-26). It measures the dispersion of IV values, not risk-neutral skewness, and its t-statistics grow with horizon, as overlapping returns would make them.
- **IV changes (An-Ang-Bali-Cakici).** A rising call IV predicts higher returns and a rising put IV lower ones, about 1%/month, persisting up to six months (1996-2011). Equal-weighted, small-cap heavy, with no evidence after 2011.
- **Single-stock term structure (Li-Wang).** An upward 60-minus-30-day IV slope predicts higher returns (t 3.7 in 2023-26). The earnings confound is uncontrolled.
- **Term-slope straddles (Vasquez).** High-slope straddles beat low-slope ones by 27.1%/month gross and 12.3% net over 1996-2007, per unit of premium.
- **S&P VRP timing (BTZ).** VIX² minus the past month's realised variance predicts 3-month returns (t 2.86, adj R² 6.82%) over 1990-2007. A 2026 replication finds an out-of-sample R² of -0.074 at 63 days.
- **Implied correlation (Buss-Schönleber-Vilkov, via CXO).** COR-type measures predict market returns up to a year ahead, beyond the VRP (1996-2015). The out-of-sample claim is unverified.
- **VX daily roll (Simon-Campasano).** Short front VIX futures in steep contango and buy them in backwardation, holding 5 days with a hedge. Half the profit came from 2008, with "little or no profit since mid-2010". **Decayed.**
- **VIX futures premium (Cheng).** The ex ante premium predicts VX returns with a coefficient near one, and it falls when risk rises, as hedging pressure drops.
- **VIX curve PC2 (Johnson).** The slope component predicts returns on variance swaps, VX futures and straddles over 1996-2013, gross.
- **VVIX and tail hedges (Park).** A one-SD rise in VVIX lowers next-day SPX put returns by 1.32-2.19% (t -4.5 to -5.5) over 2006-2012. These are delta-hedged returns residualised on same-day moves, so they are untradable as measured.
- **BTC VRP by regime (Almeida et al.).** The BVIX-based VRP is 0.17 in low-DVOL regimes against 0.12 in high-DVOL regimes (2017-2022). The regimes are full-sample clusters and the realised leg is backward-looking, so the gap is partly mechanical.

## Evidence quality

**Rating: rigorous.** The primary literature is peer-reviewed, and OSAP replicates the cross-sectional signals on the original samples. The case for survival into the 2020s is **speculative**. It rests on one unrefereed preprint with firm fixed effects (look-ahead), overlapping returns, no size or momentum controls and no transaction costs. Most magnitudes are gross and in-sample.

## What Mandel adopts

- **Testable now (archived data), pre-registered:** `spx-vrp-predicts-equity-premium-oos` (expanding out-of-sample 2008-2026, one primary RV definition); `cor1m-predicts-equity-premium-oos` (126-session horizon, sign-restricted, must encompass the VRP); `vx-daily-roll-hedged-carry-2013` (a decay test); `vix-futures-premium-falls-with-risk` (one observation per settlement cycle, final settlement values); `vix-curve-pc2-vx-returns` (must beat T-435's VIX3M/VIX gate); `vvix-spy-put-hedged-returns` (a delta-hedged target, plus a conditional defined-risk short put spread on Alpaca); `btc-vrp-ratio-by-dvol-tercile` (point-in-time terciles).
- **The premium itself is taken as given**, in agreement with T-48, T-540, T-148, T-49, T-246, T-255, T-228 and T-534/T-535/T-53. The open question is whether its size times anything.
- **Cross-sectional family, blocked on the DoltHub fetch:** `rv-minus-iv-spread-sp500-xs`, `t531-call-put-iv-spread-dolthub` (with the verdict recorded on T-531), `call-put-iv-change-xs`, `single-stock-iv-term-slope-xs` (excluding earnings names), `otm-iv-skewness-proxy-xs`, and `single-stock-smirk-xzz-replication` (as a control and decay record). The option-return straddle rows (`hv-iv-straddle-xs-sp500`, `iv-term-slope-straddle-xs-sp500`) are low priority.
- **Lessons from the children:** a reference-price source must lead the market; option-to-stock lead-lag exists only where informed flow trades options first. Deribit DVOL is a measured non-member for Polymarket BTC digitals. The child's Deribit open-time-stamp leakage fixes DVOL timing. Hurst's IBIT ladder forward test (H-ibit-ladder) is the executable home for any BTC regime gate, against Hurst's IV minus RV >= 5 point gate.

## What Mandel holds loosely or rejects

- **Decayed:** the smirk, whose index analogues also failed in Mandel (T-52, T-138, T-227, T-229). The VX roll, decayed by the source's own account, is consistent with T-160, T-379, T-435 and T-242 (not supported). Mandel's own post-publication anomaly tests decayed too (T-445, T-446, T-382).
- **Contested by Mandel verdicts:**
  - VRP timing: the out-of-sample R² is negative; T-580 F3, T-235 and T-318 are not supported.
  - Implied correlation: T-538 inconclusive, T-236 blocked, T-250 not supported.
  - VVIX: T-243, T-536, T-240 and T-239 not supported.
  - HV-IV straddles: T-232/T-533, T-123 and T-550.
  - Term-slope straddles: T-262, T-143 and T-144.
  - RVIV: it carries a low-vol tilt (T-384, T-448 failed).
- **Rejected:** the claim that the BTC 25-delta risk reversal predicts spot. The source was unreadable and the sign is unknown. An independent backtest finds noise (correlation 0.076), and T-423, T-364 and T-257 argue against it.
- **Mechanism dropped:** the skewness "lottery" story, and the calm-regime BTC VRP. T-246's halves (+0.1535 against +0.0344) and T-256 lean the other way, and T-67 (ETH) is not supported.
- **Not US-executable as published:** Deribit (signal only; trade via IBIT or Coinbase), Cboe CFE VX futures (only the SVXY/VXX proxies) and naked short straddles (Alpaca iron-fly form instead).

## Design implications for the RSI predictive substrate

- **Features:** RVIV, call-put IV spread, smirk, OTM-IV skewness, dCP, single-stock term slope, VRP, COR1M/DSPX, VX roll per day, Cheng's P_t, VIX-curve PC2, z(VVIX), DVOL tercile. The single-stock features were absent from T-580's F3 family. They enter ML only after passing one at a time.
- **Data to add:** DoltHub single-name volatility_history and option_chain; DoltHub stocks ohlcv/split/dividend (delisted names included, so no survivorship bias); SEC 8-K item numbers for an earnings flag; FINRA days-to-cover as a short-interest borrow-cost proxy; VIXY/SVIX.
- **Pipeline rules:**
  - Use raw closes, never split-adjusted ones (AAPL 43.74 adjusted against 174.97 raw).
  - Use a dividend-projected forward: a parity-implied forward erases the call-put signal.
  - Restrict moneyness for American puts.
  - Interpolate in total variance, and use no tenor beyond about 55 DTE.
  - VIX-family indices close at 16:15 ET, so enter at the next session.
- **Tests:**
  - Separate DSR families for single-stock options, option returns, VX (counting T-53, T-159, T-160, T-379, T-435, T-530, T-242) and market timing.
  - Fama-MacBeth regressions with the signals as each other's controls.
  - Both halves must be positive over the full post-publication window, because about 91 month-ends give only t ≈ 1.1-1.5 at half the published effect.
  - A forward test on DoltHub snapshots after 2026-10-20 before any capital.

## Cross-links

- 12, 13, 14 (Claude trading videos): DVOL terciles and the VIX-curve contango/backwardation regimes are the regime features 13's HMM approximates.
- A4 (MSM): a HAR or MSM variance forecast supplies BTZ's RV leg and Cheng's E_t[VIX].
- A5 (Halawi): option prices as an aggregated forecast, scored against the price paid.
- OPTIONS-STRATEGIES.md, UNDERLYING-STRATEGIES.md, venues/US-LEVERAGE-VENUES-2026-10-20.md; T-48, T-53, T-246, T-531, T-534, T-580.

## Sources used

- Li & Wang, arXiv 2608.26115 (full text) https://arxiv.org/abs/2608.26115
- OSAP SignalDoc.csv (RIVolSpread, CPVolSpread, SmileSlope, skew1, dVol rows) https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv
- Bollerslev, Tauchen & Zhou (2009) https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf
- Park (2013), FEDS 2013-54 https://www.federalreserve.gov/pubs/feds/2013/201354/201354pap.pdf
- Almeida et al., arXiv 2410.15195 https://arxiv.org/html/2410.15195v2
- Cremers & Weinbaum https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p335-367_00.html; CBS thesis https://research-api.cbs.dk/ws/portalfiles/portal/60755923/306868_Trading_on_deviations_from_put_call_parity_and_mean_reversion.pdf
- Xing, Zhang & Zhao https://ideas.repec.org/a/cup/jfinqa/v45y2010i03p641-662_00.html
- An, Ang, Bali & Cakici https://www.nber.org/papers/w19590.pdf
- Vasquez https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/equity-volatility-term-structures-and-the-cross-section-of-option-returns/F0A40E99FD2458367DD9A56A89783D38
- Johnson https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-premia-and-the-vix-term-structure/56572D1F060448571BD8F597C732D9C3
- Cheng https://ideas.repec.org/a/oup/rfinst/v32y2019i1p180-227..html; Pyun https://ideas.repec.org/a/eee/jfinec/v132y2019i1p150-174.html
- Goyal & Saretto record https://academicnewsletter.sufe.edu.cn/info/357238
- kahtongtan replication https://github.com/kahtongtan/variance-risk-premium; deribit-rr https://github.com/JERONIMODIFRANCO/deribit-rr/tree/main
- CXO Advisory volatility-effects summaries (Goyal-Saretto WP, IV changes, term structure, implied correlation, VIX roll, VIX slope, VVIX) https://www.cxoadvisory.com/volatility-effects/
- Quantpedia https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures; Deribit Insights https://insights.deribit.com/industry/bitcoin-options-finding-edge-in-four-years-of-volatility-regimes/
- Cited, not readable: https://cepr.org/publications/dp12760 · https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2024.04720 · https://ink.library.smu.edu.sg/etd_coll/887/
