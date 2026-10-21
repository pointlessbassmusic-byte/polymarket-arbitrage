# Mechanical ETP and index flows in futures: VIX-ETP leverage and roll rebalancing, commodity index and ETF rolls, and how much survived decay (literature survey)

- **Authors / kind:** Literature survey of 15 candidate strategies, each source-checked and re-registered by a verifier (13 fixed, 2 dropped). Core papers: Brogger (JBF 2021); O'Neill & Whaley (JFM 2023); Todorov (RoF 2024, BIS WP 952); Bangsgaard & Kokholm (JBF 2025); Nielsen & Posselt (IRFA 2024); Augustin, Cheng & Van den Bergen (FAJ 2021); Mou (2011); Irwin, Sanders & Yan (AEPP 2023, "ISY"); Bessembinder et al. (JFE 2016); Henderson, Pearson & Wang (RFS 2015). Practitioner: CXO, BIS, K33, NYDIG, Kitco.
- **Links:** https://research-api.cbs.dk/ws/portalfiles/portal/64811551/s_ren_bundgaard_br_gger_03_2021.pdf · https://www.bis.org/publ/work952.pdf · https://scotthirwin.com/wp-content/uploads/2022/02/Irwin_Sanders_Yan_AEPP_All.pdf · https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_predatorysunshine0314.pdf
- **Coverage confidence:** 0.60 (fraction of the sources actually read and verified: 20 of 32 opened, about 12 in full text or the relevant sections, the rest as abstracts, listings or summaries).
- **Date researched:** 2026-10-21. **How much was read:** extracted text of Brogger, Todorov (SUERF, BIS), Nielsen-Posselt, Mou, ISY Tables 2-3, the Bessembinder CFTC draft and the practitioner pages; abstracts for the rest. Not opened: Barbon et al., Cheng, Sanders-Irwin 2016, Dubois-Marechal, Saverys 2024. Archive: VX futures (2013-01..2026-10, settle, volume, open interest) and daily VXX/UVXY/SVXY exist; issuer shares outstanding do not; EIA curves end 2024-04-05.
- **Selected because:** shares outstanding, open interest, derivative volume, the VIX term structure and calendars are program inputs, and these flows are uninformed and forecastable before the trade.

## What it says

- **VIX-ETP leverage rebalancing into the close.** A daily-reset fund with leverage L and AUM A must add A·L(L−1)·r of exposure after an index return r; L(L−1) > 0 outside [0, 1], so long and inverse funds both trade with the move at the settlement. Brogger (2010-11..2017-12): mean flow 6.7% of VX M1+M2 volume; a one-sd flow moves VX +0.046 vol points over 15:30-16:15 against a ~0.05 spread; front-running made 402%/yr gross (Sharpe 5.14), negative at 0.04 points of cost. O'Neill-Whaley: the predictability diminished over time. On 2018-02-27 UVXY (2x→1.5x) and SVXY (−1x→−0.5x) cut L(L−1) from 2 to 0.75; UVIX/SVIX (2022) raised it again. No post-2018 holdout exists.
- **Next-day reversal.** Brogger's 24-hour coefficient is insignificant, read as full reversal (absence of evidence, not a measured fade); investors lose 2.4%/yr. Todorov: fading leverage rebalancing has Sharpe above two, gross.
- **Spillover to S&P futures.** Bangsgaard-Kokholm: VIX-ETP demand predicts the end-of-day SPX futures return in and out of sample, through dealers' ES hedges, with a later reversal. Unreplicated.
- **Calendar-roll pressure.** Constant-maturity ETPs sell M1 and buy M2 daily. Todorov: ETF inception raised the M1 basis 82.5% and the M2−M1 spread 59.1%; a 0.61-point non-fundamental component traded at Sharpe 1.78. Single source.
- **Short both legs of an opposite-leverage pair, open to close.** Todorov via CXO (to 2018, gross): VIX ±1 21%/yr (Sharpe 0.89), natural gas ±3 43% (2.59), silver ±2 18% (1.86), gold ±3 8% (0.81). Corrected sign: P&L ≈ gap × intraday × Σw·L(L−1), a bet on the intraday move continuing the overnight gap.
- **ETP flows and the VIX futures premium.** Nielsen-Posselt (2012-10..2019-02): flows bet on mean reversion (a 1-point return rise cuts next-day flow 0.72 points) and move the premium, which predicts VX returns (Cheng, RFS 2019).
- **Convexity crowding.** In February 2018 potential rebalancing impact was 60% of the first two contracts' size; the FAJ case study ties the 2018-02-05 spiral to it (short-vol ETPs lost over 90% in a day). One event.
- **Commodity-index roll front-run.** GSCI rolls on business days 5-9, BCOM 6-10. Mou (1980-2010): opening the spread 10 days early had Sharpe 1.09-2.75 in 2000-2010. ISY: the pre-roll move fell from −32.1 bp (t −6.72, 2004-2011) to −3.1 bp (t −0.90, 2012-2019), roll cost from 4.36% to 0.64%/yr. Decayed.
- **Post-roll rebound.** ISY: +36.6 bp (2004-2011), still +15.9 bp (t 4.11) in 2012-2019, absent outside the index; the authors cannot explain it.
- **USO's own roll.** Bessembinder et al. (2008-2013): ~25 bp per roll in adverse settlements, over 95% of temporary impact reversed within 15 minutes, narrower spreads on roll days: liquidity provision, not predation.
- **Commodity LETFs into settlement.** No direct evidence; the VIX formula applied to BOIL/KOLD, UCO/SCO, AGQ/ZSL, UGL/GLL before NYMEX/COMEX settlement windows.
- **Commodity-linked note hedging.** Henderson-Pearson-Wang: futures rose 37-51 bp on pricing dates, permanently (press summary, pre-2012).
- **January index reweighting.** BCOM 2026 bank estimates: ~$5bn of selling each in silver and gold, ~13% of COMEX silver open interest. No measured impact.
- **Spot BTC ETF flows and CME basis shorts.** NYDIG: ~$0.30 of leveraged-fund basis shorts per $1 of weekly inflow (t 6.4), contemporaneous.

## Evidence quality

**Rating: mainstream-educational.** Rigorous for the existence and decay of the price impact (three peer-reviewed VIX-ETP papers; Mou, ISY and Bessembinder on rolls). But every positive profit figure is gross and pre-2018 (VIX) or pre-2012 (commodities), and the reweighting, BTC-ETF and commodity-LETF claims are practitioner estimates or extrapolation.

## What Mandel adopts

- **The VIX-ETP flow family, pre-registered and deflated jointly** (four rows plus T-658's cells), with issuer shares point-in-time at 09:30 the next session. `vix-etp-leverage-rebal-vxx-last-half-hour` must beat its price-only momentum twin, since T-427 lost 2.09 bps/day (HAC t −2.58) and T-428's reversal slope was −0.084; it is inconclusive if K varies less than 1.5x. `vix-etp-rebal-vx-settle-reversal-post-tvix` is best-powered (about 1,570 sessions from 2020-07-13) but a mechanism test only: TAS closes at 15:58 ET and VIX at 16:15, so VIX controls are lagged.
- **The convexity overlay** (`vix-etp-rebal-convexity-downday-vx-beta`): cut short-vol exposure when convexity crowds open interest, judged on maximum drawdown and CVaR. It only reduces risk; always-long SVXY drew down 95% (T-379), T-435's contango filter failed, and the VIX/VIX3M term structure (T-53, supported) enters as a control.
- **ETF flows into T-652**, leverage-weighted (Σ L·NAV·dShares), with a reverse-causality control because T-404 parked GLD flows as following price. Blocked until VXX's ETN outstanding exists and T-652 has a verdict.
- **The opposite-pair short as a gap-continuation bet**, at fixed costs (5 bp per VIX leg per side, 3 bp metals and gas), no borrow fee (nothing held overnight); an upper bound, as historical locates are unknown. T-333 (SPY gap-intraday corr +0.018) and T-325 (DSR 0.000) set a low prior.
- **The energy-curve family on one EIA fetch** with T-687/T-688: the GSCI front-run as a 2020-01..2024-03 holdout, the post-roll rebound (its 2012-2019 +15.9 bp still exceeds the ~5.6 bp round-trip cost), and USO's disclosed roll days.
- **Spot BTC ETF flow to the CME basis**, sharing T-611's Farside fetch, with T-612 as a competing regressor.
- **Agreement with the children:** Bessembinder's liquidity providers earn within 15 minutes, as Brier and Shannon find that takers lose to makers and the touch-maker edge (+0.80 to +0.93c) depends on queue position, zero on strict through-fills (Results 15, 24). And T-345 (month-end rebalancing, −45.6 bps net, supported) shows a calendar-known flow can survive.

## What Mandel holds loosely or rejects

- **Front-running VIX-ETP flows: decayed.** Brogger's JBF abstract finds no excess profits from trading ahead of the flow.
- **Calendar-roll pressure: dropped** to a diagnostic. VX trades on Cboe CFE, not on Mandel's venue list; no ETP isolates M1 against M2; ETN outstanding is unobtainable; T-160 failed (halves −$7.6 and +$15.3 a day).
- **The BITO roll: dropped.** Paid per-contract data, roll days not published in advance, a K33 claim missing from its source, and decay after the 2024 spot ETFs (T-329, inconclusive: +0.229% pre-2024, +0.039% after).
- **The GSCI front-run as an edge** (−3.1 bp is below cost) and **the post-roll rise** (one source, unexplained: a forking paths risk until the holdout speaks).
- **USO after 2020** (discretionary holdings, $890m), **note hedging** (37-51 bp is implausible for $2-20m notes), **January reweights** (forecasts, eight holdout years).
- **Todorov's gross Sharpes**, including a VIX pair return that needs an implausible gap-intraday correlation. The SPX channel faces T-427/T-428's nulls; NYDIG's sign is ambiguous and T-362 failed.
- **Venues:** VX futures are data only; trading uses VIX ETPs on Alpaca and CME futures. Nothing needs an offshore venue.

## Design implications for the RSI predictive substrate

- **F4 flow features** for T-577/T-578: K = Σ A·L(L−1)/VX dollar volume, Rebal = K × r, leverage-weighted VIX-ETP flow, commodity-LETF demand, and roll calendar flags (GSCI, BCOM, post-roll, USO, January reweights). They must add over vx_basis (20-day IC −0.13 on equity ETFs, t −7.3 in T-580's F3 scan, where 0 of 132 swing cells pass).
- **Data to add, first-seen, backfill flagged:** ProShares and Volatility Shares daily shares outstanding and NAV; leverage histories; Yahoo 60-minute VXX (from 2024-10-22); forward 5-minute VXX and NG/CL/GC/SI captures; EIA contracts 1-4 plus forward CME settlements; GSCI roll schedule and target weights; USCF filings; Farside flows.
- **Point-in-time rules:** Yahoo bars are stamped by open and the zero-length 16:00 bar is the closing print; VIX closes after the 16:00 VX settle; Farside counts from 13:30 UTC t+1; drop Settle = 0 rows; mask front-roll jumps; flag FOMC and CPI days.
- **Tests:** a price-only twin; AUM-path shuffles and block bootstrap; L instead of L(L−1) as a reported placebo; block-shifted roll calendars at fixed distance to expiry; inconclusive rules (VIF > 10, little K variation, under 20 disclosed rolls).

## Cross-links

- A6 (LETF rebalancing as a covariate), A13 (closing-auction pressure), A9 (futures curves, commodity carry), A11 (variance risk premium), A8 (crypto basis, funding rates), A14 (month-end flows), A15 (COT hedging pressure).
- A4 (MMAR): Volmageddon as a fat-tail event. A5: how fast information reaches price. 12, 13, 14: pipelines these features feed.
- Theories T-53, T-160, T-325, T-329, T-333, T-345, T-362, T-379, T-404, T-427, T-428, T-435, T-611, T-612, T-651, T-652, T-658, T-687, T-688.

## Sources used

- Brogger (2021): https://research-api.cbs.dk/ws/portalfiles/portal/64811551/s_ren_bundgaard_br_gger_03_2021.pdf
- O'Neill & Whaley (2023): https://research.bond.edu.au/en/publications/effects-of-nondiscretionary-trading-on-futures-prices/
- Todorov: https://www.suerf.org/wp-content/uploads/2023/12/f_aaa5ebec57257fa776a1990c2bd025c1_11687_suerf.pdf · https://www.bis.org/publ/work952.pdf · CXO summary https://www.cxoadvisory.com/volatility-effects/exploiting-liquidity-needs-of-futures-based-etfs
- Bangsgaard & Kokholm (2025): https://ideas.repec.org/a/eee/jbfina/v180y2025ics0378426625001761.html
- Nielsen & Posselt (2024): https://repec.econ.au.dk/repec/creates/rp/22/rp22_06.pdf
- Augustin, Cheng & Van den Bergen (2021): https://rpc.cfainstitute.org/research/financial-analysts-journal/2021/volmageddon-failure-short-volatility-products
- Mou (2011): https://www.cftc.gov/sites/default/files/idc/groups/public/@swaps/documents/file/plstudy_33_yu.pdf
- Irwin, Sanders & Yan (2023): https://scotthirwin.com/wp-content/uploads/2022/02/Irwin_Sanders_Yan_AEPP_All.pdf
- Bessembinder et al. (2016): https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_predatorysunshine0314.pdf
- Henderson, Pearson & Wang (2015): https://experts.illinois.edu/en/publications/new-evidence-on-the-financialization-of-commodity-markets-2/
- Practitioner: Kitco https://www.kitco.com/news/article/2026-01-07/silver-struggles-above-80-index-rebalancing-sparks-near-term-volatility · BIS https://www.bis.org/publ/qtrpdf/r_qt2112t.htm · K33 https://k33.com/research/archive/articles/happy-birthday-bito · NYDIG https://viewemail.nydig.com/notes-on-a-rally
