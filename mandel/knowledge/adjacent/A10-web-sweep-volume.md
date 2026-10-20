# Trading volume, turnover and liquidity as return signals: the academic record, its decay, and Mandel's tests

- **Authors / kind:** Literature survey (web sweep and verification pass) of 16 strategies and patterns built on volume, dollar volume, share turnover, liquidity and one-step-adjacent flows (option volume, open interest, ETF flows). Mostly peer-reviewed (JF, RFS, JFE, QJE and others, 1993-2022), plus replication and decay studies and two practitioner backtests.
- **Links:** https://openaccess.city.ac.uk/id/eprint/31278/ · https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html · https://ideas.repec.org/a/eee/finmar/v5y2002i1p31-56.html · https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html
- **Coverage confidence:** 0.45 (about 20 of the 44 cited sources opened and checked against the claims, mostly at abstract level).
- **Date researched:** 2026-10-20. **How much was read:** two papers in full text (the Medhat-Schmeling manuscript, every number checked; Gao et al.); RePEc/NBER abstracts for most others; OSAP SignalDoc for std_turn, VolSD, Illiquidity and OptionVolume1. Unreachable (403 or quota): Harris-Amato, Drienko et al., Heitz et al., Zarattini et al., OSAP long-short returns. Figures marked "from memory" are unverified.
- **Selected because:** volume, dollar volume and turnover are the F0 inputs of the learning program (T-577, T-578), where relative volume alone has a mean IC near +0.01. The literature puts volume's information in its interaction with returns and in volatility, not in its level, so this cluster decides how F0 is redesigned and which classic claims archived data can settle.

## What it says

- **Short-term momentum in high-turnover stocks (Medhat-Schmeling, RFS 2022).** Sort on last month's return and turnover (volume / shares outstanding). High-turnover winners beat losers: +1.37%/month (t 4.74), 1.00% net of half-spreads, largest-500 2x2 +0.42% (t 4.91), US 1963-2018; 22 markets agree. The low-turnover reversal leg has not worked since the mid-2000s (CXO). No independent US test after 2018.
- **High-volume return premium (Gervais-Kaniel-Mingelgrin, JF 2001).** A high-volume week without a large price move precedes higher returns over the next month (visibility); found in 41 countries. Contested in Korea; no recent US single-stock replication.
- **Aggregate illiquidity (Amihud 2002).** Expected market illiquidity (mean |return| / dollar volume) predicts higher excess returns. The time-series abstract was unreachable; OSAP confirms the cross-sectional predictor (t 6.6, equal-weighted, 1964-1997). Replications (not opened) report decay after decimalisation.
- **Aggregate turnover as sentiment (Baker-Stein 2004).** High turnover predicts lower equal-weighted market returns. No post-2004 replication; turnover trends up, so it must be detrended.
- **Volatility of liquidity (Chordia-Subrahmanyam-Anshuman 2001).** Stocks whose turnover or share volume varies more earn less (std_turn t 3.74, VolSD t 3.56, equal-weighted, 1966-1995); no settled mechanism.
- **Option-to-stock volume ratio (Johnson-So 2012).** Low-minus-high O/S decile +0.34%/week, 1996-2010, stronger when short-sale costs (borrow fee, short interest) are high; Ge-Lin-Pearson trace it to opening call buys. No US test after 2010, before the 0DTE boom.
- **Earnings-announcement premium (Frazzini-Lamont).** Largest where past announcement volume surged (attention buying); reported gone in the US after 2004 (Heitz et al., unverified).
- **Volume at 52-week highs (Huddart-Lang-Yetman 2009).** Volume jumps when price crosses its 52-week range, and returns afterwards are positive. "Confirmed beats unconfirmed" is a trader's extension, not the paper's claim.
- **Dynamic volume-return relation (Campbell-Grossman-Wang 1993; Llorente et al. 2002).** Return autocorrelation falls with volume for indexes and large stocks (hedging volume reverts); informed volume continues. The size pattern is from memory and Medhat-Schmeling's megacap result contradicts it monthly.
- **Market intraday momentum (Gao et al. 2018; Baltussen et al. 2021).** The first half-hour predicts the last half-hour (SPY 1993-2013, R² 1.6%), more on high-volume and macro-news days; across 60+ futures (1974-2020) the rest-of-day return predicts the last 30 minutes, reverts over the next days, and is tied to short-gamma dealer and leveraged-ETF rebalancing. Gao's year-by-year volume terciles are look-ahead.
- **Intraday periodicity (Heston-Korajczyk-Sadka 2010).** A half-hour slot's return recurs at the same slot for 40+ days (VWAP schedules); timing trades saves about the effective spread.
- **ETF flows (Brown-Davies-Ringgenberg 2021).** Short high-flow, long low-flow ETFs: 1.1-2.0%/month; no post-publication test. **Premium/discount (Petajisto 2017):** abnormal returns reported before costs only.
- **Crypto liquidity provision (Bianchi-Babiak-Dickerson 2022).** Reversal pay concentrates in low-activity, small, volatile pairs; Liu-Tsyvinski-Wu find volume characteristics spanned by size and momentum.
- **Commodity open interest (Hong-Yogo 2012).** Open-interest growth predicts commodity and bond returns (hedging pressure); sign not in the abstract, post-financialisation untested.

## Evidence quality

**Rating: rigorous.** Peer-reviewed, with cross-country replications for STMOM, the volume premium and intraday momentum, and OSAP reproductions on CRSP. Rigorous method is not a current edge: samples end 1995-2018, effects are strongest equal-weighted in small names, liquidity premia are documented as decayed (Ben-Rephael-Kadan-Wohl; Hou-Xue-Zhang: 96% of trading-friction anomalies fail value-weighted; McLean-Pontiff: 58% post-publication fall), and the practitioner items are unreplicated.

## What Mandel adopts

- **STMOM post-sample** (`stmom-high-turnover-2x2-sp500`, with STREV and 12-1 baselines). Expect a low-power fail: the MDE (~0.39%/month) about equals the paper's largest-500 effect and UMD is ~0 since 2009 (T-446). T-420/T-462 failed on ETFs only.
- **Single-stock visibility premium** (`hvrp-visibility-weeks-sp500`), deflated with T-419's 36 cells (ETF events +6.9 bp, DSR 0.033).
- **Return x volume interaction as a measurement** (`return-volume-interaction-daily-by-size`, |NW t| > 2.8); trading translations only after.
- **Market liquidity as one family:** `aggregate-amihud-expected-illiq-iwm` and `aggregate-turnover-sentiment-ew-12m` are mirror images, Holm-corrected with T-421 and the failed sentiment predictors T-398, T-449, T-458.
- **Volume variability** (`volume-variability-cv-sp500-vw`) on share volume, value-weighted; dollar volume would encode the price path.
- **Volume-confirmed 52-week highs** (`volume-confirmed-52w-high-sp500`), counting T-309 and T-304.
- **Intraday momentum on high opening relative volume** (`intraday-momentum-rvol-tercile-spy`), trailing terciles, deflated with T-427's 60 cells (T-427: -2.09 bp/day net); the unseen 2016-2023 replication is a precondition.
- **Same-slot continuation** (`intraday-same-slot-continuation-hourly`), expected to fail net (T-577: 0 of 276 non-crypto cells), useful for execution timing (T-559, T-576).
- **Crypto low-activity loser reversal** (`crypto-low-activity-loser-reversal-weekly`), long-only on Coinbase, one-day skip; T-320 sets the cost bar.
- **Registered blocked:** `option-stock-volume-ratio-weekly-occ`, `etf-flow-reversal-xs-forward`, `commodity-oi-growth-dbc-timing`. The Frazzini-Lamont volume cell joins T-339 before it is measured.

## What Mandel holds loosely or rejects

- **Volume predicts the size of the next move, not its sign.** Hurst: volume ratio predicts next-bar range (t +4 to +43), not return; T-415: StockTwits intensity fails to add to HAR volatility forecasts; T-12 (higher-volume markets better calibrated) not_supported; the children's settle rates sit within ~1c of mid in every volume bucket.
- **Final volume is look-ahead:** the children's Result 9 "+6% favourite" cell was a final-volume artefact. Only volume published by decision time enters.
- **Stocks-in-Play opening-range breakout** (Zarattini et al.): source unreachable, Sharpe 2.81 implausible, stop entries adversely selected (Shannon/Kelly maker-fill learnings). At most a frozen T-426 cell.
- **Trust/ETF premium reversion:** duplicates T-472 (27 trades, net +0.059%, lower bound -0.198%), T-328 and T-324. Dropped.
- **Attention-buying short:** no point-in-time retail-attention data, and its price proxy contradicts the STMOM leg. Dropped.
- **Altcoin volume-shock short:** T-546's -1.80% sits over a placebo null of -1.32%, on seen data; left to Hurst's H-hype-fade (read 2027-01-12). Shorts only via Coinbase Derivatives or Kalshi perps, never offshore venues.
- **Decayed or contested:** time-series Amihud; low-turnover reversal; the earnings premium after 2004; ETF flow momentum (T-404: flows follow price). OBV and volume-breakout rules are presumed overfit (T-318's 88-rule SPA failed). Hong-Yogo's sign is unverified.

## Design implications for the RSI predictive substrate

- **Features (T-578):** r(1m) x TO(1m), r1 x lv_rel20 and abnormal volume x 52-week-high distance as declared F0xF2 interaction cells; route volume features to the realised volatility (HAR-RV) target too.
- **Construction traps:** shares outstanding from sec-companyfacts at acceptance time, split-adjusted to Yahoo's fetch-date basis (else NVDA's 2015 turnover is off 40x); dollar volume = split-adjusted close x volume, never adjclose; 52-week highs on the split-adjusted close; relative volume within one feed; drop the zero-volume 16:00 bar.
- **Data to add:** SEC submissions with 8-K items (unblocks T-339, T-338, T-452); OCC per-symbol volume (each trade listed once per side: halve it); CFTC COT for ~18 contracts (=F settles as weights only); daily ETF shares outstanding; Alpaca SIP minute bars 2016-2023; OSAP long-short returns.
- **Gate:** MDE with every verdict; prior trials counted; survivorship (~18.5% of member-days since 2010 unpriced) stated as an upper bound.

## Cross-links

- A4 (multifractal model): volume is the observable of trading time; subordination predicts Hurst's finding that volume forecasts volatility, not direction.
- 12, 13, 14 (Claude trading videos): their relative-volume and VWAP filters are F0 features to test as interactions.
- A5 (Halawi): turnover-conditioned drift is a claim about how fast information enters price.
- UNDERLYING-STRATEGIES.md, OPTIONS-STRATEGIES.md (O/S, dealer gamma), VENUES.md.
- Theories: T-12, T-304, T-307, T-309, T-318, T-320, T-328, T-339, T-393 and T-394 (days to cover, short volume), T-398, T-404, T-415, T-419, T-420, T-421, T-426, T-427, T-446, T-449, T-455, T-458, T-462, T-472, T-546, T-577, T-578.

## Sources used

- Medhat & Schmeling 2022, RFS: https://doi.org/10.1093/rfs/hhab055 (manuscript https://openaccess.city.ac.uk/id/eprint/31278/)
- CXO review of STMOM: https://www.cxoadvisory.com/momentum-investing/interaction-of-short-term-stock-momentumreversal-and-turnover/
- Gervais, Kaniel & Mingelgrin 2001, JF: https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html
- Kaniel, Ozoguz & Starks 2012, JFE: https://ideas.repec.org/a/eee/jfinec/v103y2012i2p255-279.html
- Amihud 2002, JFM: https://ideas.repec.org/a/eee/finmar/v5y2002i1p31-56.html
- Baker & Stein 2004, JFM: https://ideas.repec.org/a/eee/finmar/v7y2004i3p271-299.html
- Chordia, Subrahmanyam & Anshuman 2001, JFE: https://ideas.repec.org/a/eee/jfinec/v59y2001i1p3-32.html
- Open Source Asset Pricing: https://www.openassetpricing.com/data/
- Johnson & So 2012, JFE: https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html
- Ge, Lin & Pearson 2016, JFE: https://ideas.repec.org/a/eee/jfinec/v120y2016i3p601-622.html
- Frazzini & Lamont, NBER w13090: https://www.nber.org/papers/w13090
- Huddart, Lang & Yetman 2009: https://doi.org/10.1287/mnsc.1080.0920
- Campbell, Grossman & Wang 1993, QJE: https://doi.org/10.2307/2118454
- Llorente, Michaely, Saar & Wang 2002, RFS: https://ideas.repec.org/a/oup/rfinst/v15y2002i4p1005-1047.html
- Gao, Han, Li & Zhou 2018: https://doi.org/10.2139/ssrn.2440866
- Baltussen, Da, Lammers & Martens 2021: https://doi.org/10.2139/ssrn.3760365
- Heston, Korajczyk & Sadka 2010, JF: https://doi.org/10.1111/j.1540-6261.2010.01573.x
- Brown, Davies & Ringgenberg 2021, RoF: https://ideas.repec.org/a/oup/revfin/v25y2021i4p937-972..html
- Petajisto 2017, FAJ: https://ideas.repec.org/a/taf/ufajxx/v73y2017i1p24-54.html
- Bianchi, Babiak & Dickerson 2022, JBF: https://ideas.repec.org/a/eee/jbfina/v142y2022ics0378426622001418.html
- Hong & Yogo 2012, JFE: https://ideas.repec.org/a/eee/jfinec/v105y2012i3p473-490.html
- Not opened (403/unread, cited for decay): Harris & Amato 2019 https://nowpublishers.com/article/Details/CFR-0058; Heitz et al. https://www.ssrn.com/abstract=3296537; Hou, Xue & Zhang 2020 https://doi.org/10.1093/rfs/hhy131; McLean & Pontiff 2016 https://doi.org/10.1111/jofi.12365; Ben-Rephael, Kadan & Wohl 2015 https://ideas.repec.org/a/cup/jfinqa/v50y2015i1-2p197-229_00.html; Zarattini et al. https://doi.org/10.2139/ssrn.4729284
