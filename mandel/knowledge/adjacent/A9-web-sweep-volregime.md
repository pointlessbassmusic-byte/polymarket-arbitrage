# Volatility management, variance risk, futures curves and positioning: which published predictors survive costs and publication (literature survey)

- **Authors / kind:** survey of 15 strategy claims, mostly from peer-reviewed journals, plus two working papers, practitioner research and EIA data. Lead papers: Moreira-Muir with its critics Cederburg et al. and Barroso-Detzel; Harvey et al.; Shu-Yu-Mulvey; Bollerslev-Tauchen-Zhou; Boons-Porras Prado; Kang-Rouwenhorst-Tang.
- **Links:** https://www.nber.org/papers/w22208 · https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf · https://arxiv.org/html/2402.05272v3 · https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf · https://www.chicagofed.org/-/media/publications/working-papers/2025/wp2025-17.pdf
- **Coverage confidence:** 0.40 (fraction of the sources actually read and verified: 14 opened in full, 8 at abstract level, about 25 cited replications not opened).
- **Date researched:** 2026-10-20. **How much was read:** full text of the 14 unmarked entries under Sources used (Shu-Yu-Mulvey's Table 4 checked exactly), abstracts of the 8 marked ones. The search allowance ran out before replication searches on tail risk, vol-of-vol and hedging pressure.
- **Selected because:** they use the learning program's non-price inputs (realised and implied volatility, variance risk premium, futures term structure, COT positioning, short interest, shares outstanding, dollar volume) and bear on why T-577/T-578/T-580 found nothing in 764 cells.

## What it says

- **Volatility-managed market (Moreira-Muir).** Scale equity exposure by inverse realised variance: volatility persists but expected returns do not rise with it. In-sample alphas replicate; real-time gains fail for most factors (Cederburg et al.); after transaction costs only the managed market keeps its alpha, in high-sentiment periods (Barroso-Detzel). Harvey et al.: US equities 1927-2017 Sharpe 0.40 unscaled vs 0.48-0.51 scaled, robust to costs. No 2015-2026 decay study found.
- **Downside semivariance scaling (Wang-Yan, to 2018).** Scaling by bad volatility beats total-variance scaling because high downside volatility also predicts lower returns. Shares authors with Cederburg et al.; no post-2018 check.
- **Volatility-scaled momentum (Barroso-Santa-Clara, 1927-2011).** Scaling UMD by its 6-month realised volatility "nearly eliminates crashes and nearly doubles the Sharpe ratio". The premium underneath has decayed: +11.3%/yr 1993-2008, +0.1%/yr 2009-2026 (T-446).
- **Conditional multifactor timing (DeMiguel et al., 1967-2020).** Factor weights linear in market volatility, optimised net of stock-level costs with trades netted across factors: out-of-sample net Sharpe 13% above the unconditional portfolio. The gain rests on the netting.
- **Where volatility targeting pays (Harvey et al., 60 assets).** Sharpe rises only in equities and credit, where the leverage effect lives; bonds, FX and commodities gain nothing, though left tails thin everywhere. Not replicated after 2017.
- **Better volatility forecasts (HAR-RV with semivariances or implied volatility).** Bollerslev et al. 2018: realised-volatility models track a risk target better, worth 8-19 bp/yr over simple models after costs; Sharpe is insensitive to the estimator (Harvey et al.). Risk control, not alpha.
- **Jump-model regime switching (Shu-Yu-Mulvey).** Two states on EWM downside deviation and Sortino ratios, a penalty per switch, applied from day t+2 at 10 bp a trade: S&P 500 1990-2023 Sharpe 0.68 vs a hidden Markov model 0.54 vs buy-and-hold 0.48, maximum drawdown -26.6% vs -55.2% for buy-and-hold. One research group; only 2024 onward is post-publication.
- **Skewness dispersion (Babiak et al., 2000-2022).** The cross-sectional spread of daily realised skewness from 5-minute returns predicts the S&P 500 (out-of-sample R^2 2.9% at 1 month), concentrated in FOMC months. Unreplicated; two-thirds of months contain a meeting.
- **Tail risk (Kelly-Jiang).** A monthly Hill exponent from pooled extreme stock returns: +1 SD forecasts +4.5% market excess return over a year. Replication unchecked.
- **Variance risk premium as a predictor (Bollerslev-Tauchen-Zhou, 1990-2007).** VIX^2 minus realised variance predicts quarterly returns (t 2.86); with daily-return RV their own check gives t 2.34. Dew-Becker-Giglio: index-option alphas indistinguishable from zero for 15 years (a break near 2010): probably decayed.
- **Realised skewness in the cross-section (Amaya et al., 1993-2008).** Lowest-minus-highest weekly decile: 19-24 bp/week gross (t 3.65-3.70). Daily-return versions fail Hou-Xue-Zhang's replication (unopened).
- **Vol-of-vol (Baltussen et al., 1996-2014).** Stocks whose implied volatility is itself volatile underperform by 0.69%/month value-weighted, for up to 24 months and in Europe. No post-2014 US replication found.
- **Commodity carry (Szymanowska et al.).** Basis (roll yield) sorts earn spot premia of 5-14%/yr: backwardation pays longs through storage and hedging pressure. Practitioners report post-2015 decay (snippets). EIA's free contract 1-4 curves (WTI, heating oil, RBOB, Henry Hub) end 2024-04-05.
- **Basis-momentum (Boons-Prado, 21 commodities 1959-2014).** Nearby minus second-nearby 12-month return: 18.38%/yr (t 6.73), nearly all roll return, beating basis and momentum.
- **COT hedging pressure and flow (Basu-Miffre; Kang-Rouwenhorst-Tang, 1994-2012).** Hedger net short earns a premium; hedger buying predicts +43 bp over 20 days. KRT sort on the Tuesday as-of date, and about half the return accrues before the Friday release.
- **Machine learning after costs (Robeco; Azevedo et al.).** 1-month ML strategies paid mainly before 2004; 3-12 month horizons net better over 2004-2021 through lower turnover. Azevedo et al. report a net LSTM alpha of 1.20%/month (t 3.46) but find cost-mitigation does not raise net anomaly returns. Avramov et al. (unverified) put the profits in microcaps.

## Evidence quality

**Rating: rigorous.** Most claims come from top journals with out-of-sample tests and costs; several were checked to the table. But method is not implementability: real-time, after-cost and post-publication evidence is contested (Cederburg, Barroso-Detzel, Dew-Becker-Giglio), two sources are unreplicated working papers, and Man AHL and Robeco are practitioners.

## What Mandel adopts

- **vol-target-spy-monthly-realtime:** the volatility-managed market, the one case Barroso-Detzel find survives costs. Target fixed ex ante, 40 trials in the DSR (with T-310's and T-562's), paired block bootstrap, power reported first: the Sharpe-difference SE (~0.10) is as large as the expected gain. T-310's pooled buy-and-hold gain (0.81 vs 0.63) was never judged alone.
- **vol-target-gain-by-leverage-effect:** Harvey's cross-asset prediction as a difference-in-differences, with own-volatility targets (a common 10% target pins bond ETFs at the cap and fakes a pass).
- **jump-model-derisk-spy:** the regime-switching successor to T-561/T-562, matching Mandel's guidance to the Kelly child that state models help where the state is measured directly (T-561 cut drawdown). 1994-2023 is labelled replication.
- **har-forecaster-risk-targeting-value:** HAR-RV forecasters judged on tracking error, not Sharpe, building on the QLIKE wins T-569 and T-572.
- **vrp-predicts-spy-3m-post-2010:** Mandel's first VRP timing test for SPY, with the decay prediction recorded before reading.
- **downside-semivariance-vs-total-scaling-factors** (2019-2026, weight cap 3) and **vol-scaled-umd-post-bsc** (from 2012, so the in-sample 2009 crash cannot carry it).
- **eia-energy-backwardation-timing** and **energy-basis-momentum-ts:** a time-series route around blocked T-371, momentum as competitor, one shared DSR.
- **cot-hedger-flow-post-release-etf:** the post-release half only, with point-in-time release stamps as in T-405.
- **vol-of-vol-stock-dolthub** (after a DoltHub fetch, rule-9 coverage gate) and **ml-price-free-etf-quarterly-v1:** 63-session horizon, publication-stamped short interest, days to cover, RegSHO short volume, dollar volume, realised and implied volatility and days to FOMC/CPI; DSR over every ML cell; T-578's 2026 window excluded.

## What Mandel holds loosely or rejects

- Factor timing beyond the market: post-publication premia are near zero (T-382, T-386, T-447, T-446) and timing lost to static (T-388; T-389 -0.03). DeMiguel et al. is dropped: its netting needs stock-level holdings.
- Volatility targeting as alpha: in T-310 scaling helped trend no more than buy-and-hold (DiD -0.082); above 1x, Mandel's leverage review for the small-account desk child found financing exceeds the edges.
- Skewness dispersion, Kelly-Jiang tail risk, weekly realised skewness: dropped. The archive has survivorship bias, the 5-minute cross-section has no free source, and a weekly decile book costs 40-80 bp/week against 19-24 bp gross. Option tail measures already failed (T-52, T-227).
- VRP timing: the gap exists (T-48, T-540) but VRP-conditioned rules failed (T-159, T-235, T-179).
- Carry and curves: every recent carry sleeve failed (T-381, T-368, T-431, T-433), as did commodity momentum (T-313) and VX curve rules (T-160, T-379, T-435); EIA curves stop in 2024, so a pass is historical. Offshore funding carry (Hyperliquid) is not US-legal, and on US venues the desk child killed it.
- COT: half of KRT's effect is unusable; gold COT showed nothing (T-405).
- Vol-of-vol: the VVIX premium (T-243, T-536) and low-volatility tilts (T-384, T-448), related claims, failed. FOMC concentration: Mandel's FOMC drift faded after 2016 (T-341).

## Design implications for the RSI predictive substrate

- Features, each point-in-time at its available_at: EWMA, HAR-RV and SHAR forecasts; downside semivariance; VRP = (VIX/100)^2/12 - RV21; vol-of-vol of Cboe implied-volatility indices; VIX/VIX3M term structure; online jump-model state (never smoothed); basis and basis-momentum; weekly COT change at release; short interest at FINRA publication; net share issuance from shares outstanding.
- Data to add: EIA contracts 1-4 (CL, HO, RB, NG); CFTC Socrata reports for eight more contracts; DoltHub volatility_history for all symbols plus delisted-name prices; French NYSE breakpoints; CANE, MTUM, VLUE.
- A shared volatility-targeting sizing layer in the ML harness, so prediction and sizing are judged apart; drawdown-only results count as risk overlays (T-561); survivors go to a forward paper record, never live.

## Cross-links

- A4 (MSM, T-569): MSM is a reported forecaster in the HAR test.
- 13 (HMM regime model): the jump model is its successor (T-561, T-562).
- 12, 14 (Claude trading workflows): add volatility sizing and cost-aware ML.
- Theories: T-310, T-311, T-371, T-405, T-446, T-561, T-562, T-569, T-572, T-577, T-578, T-580.

## Sources used

- Moreira & Muir (abstract): https://www.nber.org/papers/w22208
- Cederburg et al. (abstract): https://www.lehigh.edu/~xuy219/research/COWY.pdf
- Barroso & Detzel (abstract): https://ciencia.ucp.pt/en/publications/do-limits-to-arbitrage-explain-the-benefits-of-volatility-managed/
- Wang & Yan (abstract): https://ideas.repec.org/a/eee/jbfina/v131y2021ics0378426621001576.html
- Barroso & Santa-Clara (abstract): https://run.unl.pt/bitstream/10362/11836/1/Barroso_2012.pdf
- DeMiguel et al.: https://lbsresearch.london.edu/id/eprint/3716/1/The%20Journal%20of%20Finance%20-%202024%20-%20DeMIGUEL%20-%20A%20Multifactor%20Perspective%20on%20Volatility%E2%80%90Managed%20Portfolios.pdf
- Harvey et al.: https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf
- Bollerslev et al. (2018): https://pure.au.dk/ws/files/154593513/Bollerslev_2018_Risk_everywhere_VOR.pdf
- Shu et al.: https://arxiv.org/html/2402.05272v3
- Babiak et al.: https://arxiv.org/html/2604.07870
- Kelly & Jiang (abstract): https://www.nber.org/papers/w19375
- Bollerslev, Tauchen & Zhou: https://public.econ.duke.edu/~boller/Published_Papers/rfs_09.pdf
- Dew-Becker & Giglio: https://www.chicagofed.org/-/media/publications/working-papers/2025/wp2025-17.pdf
- Amaya et al.: https://repec.econ.au.dk/repec/creates/rp/13/rp13_41.pdf
- Baltussen et al.: https://personal.eur.nl/vanbekkum/2018JFQA_unknown_unknowns.pdf
- Szymanowska et al. (abstract): https://ideas.repec.org/a/bla/jfinan/v69y2014i1p453-482.html
- EIA NYMEX futures: https://www.eia.gov/dnav/pet/pet_pri_fut_s1_d.htm
- Boons & Porras Prado: https://4nations.albertjmenkveld.com/papers/boonsprado17.pdf
- Basu & Miffre (abstract): https://ideas.repec.org:443/a/eee/jbfina/v37y2013i7p2652-2664.html
- Kang et al.: https://conference.nber.org/conf_papers/f69870/f69870.pdf
- Robeco: https://www.robeco.com/en-us/insights/2023/07/the-term-structure-of-machine-learning-alpha
- Azevedo et al.: https://afajof.org/management/viewp.php?n=75544
