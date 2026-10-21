# Currency option-implied signals: the FX variance risk premium, implied-vol level and term slope, skew and positioning for currency selection and dollar timing (literature survey, 1998-2026)

- **Authors / kind:** Literature survey of 15 sweep candidates.
  - Peer-reviewed: Della Corte-Ramadorai-Sarno (DRS; JFE 2016), Londono-Zhou (JFE 2017), Della Corte-Kozhan-Neuberger (DKN; JFE 2021), Fullwood-James-Marsh (FJM; JFE 2021), Ornelas-Mauad (IJF 2019), Li-Sarno-Zinna (LSZ; JFQA 2025), Qiao-Wang (J. Empirical Finance 2026), Low-Zhang, MSSS (JF 2012), Bakshi-Panayotov, Brunnermeier-Nagel-Pedersen (BNP), Fan-Londono-Xiao.
  - Working papers: Ornelas (BCB 454), Torok, Babiak-Barunik (decay benchmark).
  - Exchange and data: a Kalshi CFTC filing, Cboe's EVZ notice, CFTC Socrata.
- **Links:** https://openaccess.city.ac.uk/id/eprint/13156/ · https://www.repository.cam.ac.uk/bitstreams/70b926af-1044-455e-abf9-be49a31c323b/download · https://openaccess.city.ac.uk/id/eprint/24959/ · https://openaccess.city.ac.uk/id/eprint/24178/ · https://fred.stlouisfed.org/series/EVZCLS
- **Coverage confidence:** 0.55 (22 of 38 distinct sources opened and checked, eight in full text; rounded down because many reads were abstract-only).
- **Date researched:** 2026-10-21. **How much was read:**
  - Full text: DRS, LSZ, Ornelas, Londono-Zhou, DKN, FJM, Torok and the Kalshi filing.
  - Abstracts only for the rest. Ornelas-Mauad's digits are garbled, so its numbers are unverified.
  - Not opened: Quantpedia, Hutchinson et al., Jurek, Farhi et al., Macrosynergy (403).
  - FRED EVZCLS and the CFTC TFF series were checked live.
- **Selected because:** implied volatility, skew, term structure and the variance risk premium are program inputs, but Mandel has tested them only on equity, commodity and BTC underlyings. T-580's FX "own_iv" is just the VIX level. The G10 carry and currency momentum books T-368, T-431 and T-478 all failed over 2013-2026.

## What it says

- **Cross-sectional currency VRP (DRS).** Hedgers overpay to insure feared currencies and sell them spot, and speculators with limited funding liquidity absorb the flow (CFTC commercials sell expensive-to-insure currencies).
  - Long cheap insurance (high RV minus 1-year IV), short expensive: 4.95% p.a., Sharpe 0.61, developed currencies 1998-2013, net of bid-ask. Carry correlation -0.08.
  - **Decayed.** LSZ (including a DRS co-author) find it "much weaker" through 2021. Babiak-Barunik measure -0.29% p.a. over 2005-2021.
- **Per-currency VRP gap (Ornelas).** IV minus intraday RV predicts appreciation.
  - The headline 0.28%/month uses the global average VRP. EUR alone is insignificant (t 0.71-1.42); JPY is significantly negative.
  - Out-of-sample gains are significant only for EM.
  - The sign flips with the RV window: the 1-month VRP correlates -8% and -3% with the 6- and 12-month VRPs.
- **World currency VRP and global FX vol (Londono-Zhou; Qiao-Wang).** A rising world VRP predicts foreign-currency depreciation at 4-6 months (2000-2011, 18 of 22 currencies). Global implied and realised vol positively predict currency returns beyond 3 months (in-sample R² 2.5-7.1%); Qiao-Wang's return definition and sample end are unverified.
- **US equity VRP (Londono-Zhou).** VIX² minus trailing realised variance predicts dollar depreciation: 2.10% annualised per 100 units at 1 month, 2000-2011. It is not significant for EUR alone, and there is no replication after 2011.
- **Volatility carry (DKN).** Long forward vol on currencies with a downward-sloping term structure, short on upward-sloping ones: 5.15%/month (t 5.91) on 1/3-month FVAs, falling to 2.50% at 12/24 months, Sharpe 1.46-1.25, 1996-2015. It is a payoff on volatility, not spot, and has no replication after 2015.
- **Term slope and spot (Ornelas-Mauad).** In G10 a steep slope predicts weak spot returns, and in EM strong ones (2002-2016). The ATM-slope book beats carry, risk reversal and VRP on currency-only Sharpe. **Contested** by DKN's pooled sign.
- **Low-IV minus high-IV straddles (FJM).** 34%/month of premium after costs, Sharpe 1.03, about 40 bp/month of notional (9 G10, weekly, 1999-2016). Payoffs are flat while premiums rise with IV, so in six pairs it may be a static ranking.
- **EUR VRP existence (Low-Zhang; Ammann-Buesser).** The premium is negative in GBP, EUR, JPY and CHF and shrinks with maturity; significance depends on the RV sampling. EVZ ran from 2007-11 until it ceased on 2025-01-27.
- **Skew filters on carry (BNP; CME 2023).** Carry losses lower future crash risk but raise its price. The CME study was readable only on an unattributed mirror. **Dropped.**
- **Skew-neutral carry (Torok).** Sharpe 0.54 over 2006-2022, gross, EM-dominated, with no G10 result. **Dropped.**
- **Skewness risk premium (LSZ).** 5.47% p.a. (t 3.31) on 28 currencies, carried by interest differentials. G10-only it is 2.31% and insignificant. **Dropped.**
- **Global FX vol innovations (MSSS; Bakshi-Panayotov).** Carry is short global FX vol (a contemporaneous result). Changes in currency vol and commodity prices forecast carry payoffs out of sample.
- **Kalshi EUR/USD ladders.** FXEURUSD (2026-07) settles on Pyth and includes touch contracts. The hourly KXEURUSDH settles on ICE. There is no evidence either way.
- **CFTC positioning (BNP; DRS).** Speculator crowding comes before carry crashes. Eight TFF FX series run from 2006-06. No published trading rule exists.
- **Equity tail-beta sort (Fan-Londono-Xiao).** Currencies that hedge S&P tail risk earn less. The figures are unverified.

## Evidence quality

**Rating: rigorous.** Twelve of the fifteen claims are peer-reviewed, and five of those journal papers were read in full. Survival is weak:
- The one effect with independent post-publication tests (DRS) has decayed.
- Nothing else has evidence after 2016.
- Results lean on EM currencies.
- The OTC 1-year vols and FVAs the papers trade are not retail instruments.

## What Mandel adopts

- **Testable now:**
  - `us-equity-vrp-predicts-dol-1m`, out of sample after the paper (2012-2026), sharing VP code with T-649 and T-685.
  - `global-fx-rv-level-predicts-dol-3m`, with the positive level sign pre-registered.
  - `fx-vol-innovation-carry-timing`: T-368 rebuilt on ALFRED vintages, judged against its VIX > 30 filter.
  - `vix-beta-currency-sort-flx-proxy`.
- **After the free EVZCLS fetch:**
  - `eur-vrp-evz-vs-realised` is the strongest prior, a twin of the supported T-48, T-50, T-244 and T-246. It carries a 0.5-vol-point cost bar, because EVZ sits above ATM IV (the T-57/T-233 lesson).
  - `eur-evz-gap-predicts-eurusd-week` is registered with an expected null, since EUR is insignificant in its source. FOMC, ECB and CPI weeks are reported separately.
- **After free fetches:**
  - `fx-tff-leveraged-crowding-4w`, Commitments of Traders data under T-405's park rule, counted with T-606.
  - `kalshi-eurusd-hourly-vs-spot-digital`, a reference-price test (net of the taker fee, with Brier reported) expected to be the eighth non-member. Kalshi's index ladders (Result 22), BTC/ETH ladders (21d) and T-544 (-5.21 cents) all lost to the book.
- **Blocked on CME option settlements:**
  - `fx-vrp-xs-sort-drs-1y-cme` (12-month IV only).
  - `fx-fva-term-slope-sort-cme`.
  - `fx-atm-iv-term-slope-spot-sort`.
  - `fx-low-minus-high-iv-straddles-cme`, whose demeaned variant must also pass.

## What Mandel holds loosely or rejects

- **Decayed:** the DRS sort (LSZ footnote 22, Babiak-Barunik, Bartram et al.). The whole CVOL window falls inside the decay.
- **Contested sign:**
  - Short-window against 1-year VRP.
  - Term slope (Ornelas-Mauad against DKN).
  - JPY and CHF as safe havens.
- **Contradicted by Mandel:**
  - Anything that rides carry. T-368 (gross Sharpe 0.01, DSR 0.008), T-431, T-478, T-381 and T-433 failed, so the skew filters, Torok and LSZ are dropped.
  - SKEW as a tail proxy: T-52 and T-227 refuted it.
  - VRP existence is not automatic: T-51 and T-65 missed at p 0.095.
- **Not US-executable as published:** OTC variance swaps and FVAs. Mandel uses CME options on 6E, 6J, 6B, 6A, 6C and 6S (none exist on DKK, NOK or SEK), CME futures and OANDA.

## Design implications for the RSI predictive substrate

- **Leak to fix first:**
  - `fx-spot-g10` stamps noon fixes as available on the same day, but H.10 publishes them only weekly (Mondays 16:15 ET). Re-stamp every fix to its release date.
  - OECD rates need ALFRED vintages (T-433 measured a mean lag of 3.8 months).
- **F3 features for FX, quoted as USD per foreign unit:**
  - Per-currency IV, realised vol and VRP at matched tenors.
  - Demeaned IV and the IV term slope.
  - Global FX vol and its AR(1) innovation.
  - US equity VRP and a VIX-change beta.
  - The TFF net position over open interest, as a z-score.
  - These replace the VIX-level "own_iv" (IC +0.054, pooled over mixed quote conventions).
- **Data:**
  - fred-EVZCLS, minus stale and post-2025-01-24 prints.
  - TFF futures for the eight FX codes, joined on contract code.
  - Kalshi KXEURUSDH via `/historical`.
  - Forward capture of CME FX option and futures settlements.
  - CME DataMine history is a paid decision for the user.
- **Pipeline rules:**
  - Black-76 inversion against the matching futures settlement.
  - Total-variance interpolation.
  - Yahoo bars re-keyed from bar start to bar close; Kalshi candles read by period end.
- **Tests:**
  - Separate DSR families for DOL timing (T-605, T-575 and the new trials), the FX cross-section (T-368, T-431, T-478) and FX options.
  - Stationary-bootstrap intervals; static-rank and circular-shift placebos act as gates.
  - Six currencies over about 100 months need a true Sharpe near 0.7 to reach t = 2.

## Cross-links

- A11: BTZ's VRP timing is the equity twin of this cluster (T-649, T-685).
- A15: T-605 dollar carry and T-606 COT pressure share its DSR families.
- A9: vol-managed carry and T-682.
- A14: month-end dollar flows (T-575).
- A6: open interest.
- A4: the Calvet-Fisher MSM can supply the realised leg of a currency VRP.
- A5: the Kalshi ladder is scored against the price paid.
- 12, 13, 14: regime features.
- Theories: T-48, T-50, T-51, T-52, T-57, T-65, T-227, T-228, T-233, T-244, T-246, T-337, T-368, T-381, T-405, T-431, T-433, T-478, T-544, T-575, T-580, T-605, T-606, T-649, T-682, T-685.
- Children: EDGE_VERDICT 21d, Result 22, MASTER_PLAN 2026-10-15.

## Sources used

- DRS: https://openaccess.city.ac.uk/id/eprint/13156/
- LSZ: https://www.repository.cam.ac.uk/bitstreams/70b926af-1044-455e-abf9-be49a31c323b/download
- Babiak-Barunik: https://arxiv.org/html/2101.09738
- Ornelas: https://www.bcb.gov.br/pec/wps/ingl/wps454.pdf
- Londono-Zhou: https://www.federalreserve.gov/econres/ifdp/variance-risk-premiums-and-the-forward-premium-puzzle.htm · https://www.ckgsb.edu.cn/uploads/201410/27/XVP_July_2014_LondonoZhou.pdf
- Qiao-Wang (abstract): https://www.sciencedirect.com/science/article/abs/pii/S0927539826000551
- DKN: https://openaccess.city.ac.uk/id/eprint/24178/
- Ornelas-Mauad: https://www.sciencedirect.com/science/article/abs/pii/S0169207019301086
- FJM: https://openaccess.city.ac.uk/id/eprint/24959/
- Low-Zhang: https://ideas.repec.org/a/cup/jfinqa/v40y2005i04p803-832_00.html
- Ammann-Buesser: https://ideas.repec.org/p/usg/sfwpfi/201304.html
- EVZ: https://fred.stlouisfed.org/series/EVZCLS · https://cdn.cboe.com/resources/release_notes/2025/20250113_Consultation-Results-Regarding-the-Cessation-of-the-RVOL-and-EVZ-Indices.pdf
- BNP: https://www.nber.org/papers/w14473
- Torok: https://ssrn.com/abstract=4040261
- MSSS: https://openaccess.city.ac.uk/id/eprint/3391/
- Bakshi-Panayotov: https://ideas.repec.org/a/eee/jfinec/v110y2013i1p139-163.html
- Kalshi: https://www.cftc.gov/filings/ptc/ptc07162610487.pdf
- CFTC TFF: https://publicreporting.cftc.gov/resource/gpe5-46if.json
- Fan-Londono-Xiao: https://openaccess.city.ac.uk/id/eprint/29716/
- Not opened: https://vvv.quantpedia.com/?p=15356 · https://macrosynergy.com/academy/notebooks/fx-volatility-risk-premia/ · https://cattlemensharrison.com/is-cvol-skew-a-leading-indicator-of-price-trends-in-commodities-bonds-and-currency-markets/
