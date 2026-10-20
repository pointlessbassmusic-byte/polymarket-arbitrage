# Calendar and macro-event patterns: uncertainty premia, FOMC-window carry and bond drift, month-end flows, auction concessions and weekend option decay

- **Authors / kind:** Literature survey of 15 sweep candidates: ten peer-reviewed papers (JF, JFE, RFS, FRL), six working papers and two Quantpedia practitioner summaries.
- **Links:** https://www.nber.org/system/files/working_papers/w25817/revisions/w25817.rev2.pdf · https://acris.aalto.fi/ws/portalfiles/portal/40965155/hhz054.pdf · https://www.fmg.ac.uk/sites/default/files/publications/dp-54.pdf
- **Coverage confidence:** 0.65 (26 works and data documents, weighted full text 1, abstract 0.5, summary 0.25: 13 full, 7 abstracts, 2 summaries, 4 not opened).
- **Date researched:** 2026-10-20. **How much was read:** full text for nine papers and Cboe's PutWrite methodology, every data claim checked against the archive; abstracts only for Kurov-Wolfe-Gilbert, Savor-Wilson, Wachter-Zhu, Lou-Yan-Zhang, Jones-Shemesh, Muravyev-Ni and Ben-David et al.; SSRN returned 403 for Stivers-Sun and Ma-Pratt. No post-2018 replication of a conditional version was searched (the web-search budget ran out).
- **Selected because:** calendar inputs (FOMC, CPI, payrolls, month-end, OPEX, holidays, time of day) are the registry's most-tested, most-decayed family; the question is whether an effect survives conditioning on a non-price input (implied volatility, dealer gamma, auction size, settlement regime, rate differentials) and whether its mechanism predicts where it moves.

## What it says

- **Uncertainty build-up before releases (Hu-Pan-Wang-Zhu).** Holders of known event risk are paid as it resolves; VIX builds beforehand. 1994-2018, close t-1 to just before: FOMC +27.1 bps (t 5.95, 190 statements), payrolls +10.1, ISM +9.1, GDP +7.5. The FOMC slope on the 3-day VIX change has t 2.20; the non-event placebo is flat. For pooled macro releases the 3-day change fails (t 0.32) and only a 6-day window works. Kurov-Wolfe-Gilbert: the unconditional drift "essentially disappeared after 2015".
- **VIX-spike next-day premium (same paper).** 1994-2018: after VIX closes 3 points above its EWMA, the S&P earns +57.2 bps the next day (t 3.24, about 8 events a year; +46.9 with the 3:45 pm VIX). The authors concede large price drops carry the same information.
- **Announcement-day beta (Savor-Wilson; Wachter-Zhu).** Macro risk resolves on release days, so beta is priced on CPI, jobs and FOMC days and much less otherwise. No post-2016 test.
- **FOMC-day short-dollar carry (Mueller-Tahbaz-Salehi-Vedolin).** 1994-2010: the three highest-rate currencies against USD earn 16.83 bps on FOMC days vs 1.67 otherwise (t 2.43); Sharpe up to 0.5 after bid-ask. About 75% arrives before the statement, more when policy uncertainty is high.
- **Post-FOMC Treasury drift (Brooks-Katz-Lustig).** 157 meetings 1989-2008: a 10 bp fed funds surprise moves the 10-year yield 1.7 bps on the day and 14 bps after 50 days, mostly after positive surprises; slow bond fund flows.
- **Dash for cash (Etula et al.).** Month-end payments force selling that settles by T, so returns are low on T-8..T-4 and high on T-3..T+3 in the T+3 era (2003-2013 reversal windows +103% cumulative against -31%). Europe's 2014 move to T+2 cut the autocorrelation at T-2 by 0.777 (t -3.20).
- **Threshold rebalancing (Harvey-Mazzoleni-Melone).** A simulated 60/40 drift signal over bands of 0-2.5% predicts lower next-day equity returns (1997-2023, |t| > 4, front-running Sharpe > 1).
- **Dividend payment-day pressure (Hartzmark-Solomon).** 1926-2018: +3.2 bps market return per sd of payout on t and t-1; multipliers 1.5-2.3; nothing in Q4.
- **Gamma-conditioned intraday momentum (Baltussen et al.).** The rest-of-day return predicts the last half hour (futures 1974-2020); on the S&P only when dealer gamma is negative (48% of days). Free SqueezeMetrics GEX is negative on only 19 of 734 sessions since 2023-11: not the paper's condition.
- **Treasury pre-auction concession (Lou-Yan-Zhang).** Prices fall before auctions and recover after; hidden cost 9-18 bps of size.
- **Payday (Ma-Pratt).** Paycheck flows: the 16th earns +0.214% per event (t 3.07), decayed in the 2010s.
- **Informative pre-FOMC pressure (Arif-Da-Lin).** Informed hedging the session before meetings: a one-sd lower trailing-24-month mean predicts +11.78% over two years; out-of-sample R2 7-30% (origins 2005-2013), about 15 independent windows.
- **Weekend option decay (Jones-Shemesh; Muravyev-Ni).** Option prices mis-handle variance while markets are closed, so returns are lower over weekends; delta-hedged index options lose 1% overnight and gain 0.3% intraday.
- **Quarter-end mark-up (Ben-David et al.).** Marking up for reporting, hedge-fund-held stocks rise on the last quarter day, mostly in the final minutes, then partly reverse.
- **Same-weekday momentum (Da-Zhang).** Fixed-weekday fund flows: 2.05% a month (t 10.94, 1963-2021), but its share of momentum fell to 18% after 1993.

## Evidence quality

**Rating: rigorous.** Nine of fifteen claims rest on JF, JFE, RFS or FRL papers; Hu et al. and Etula et al. test mechanisms with a placebo or natural experiment. Not a tradable edge: samples end 2008-2018, transaction costs are absent or bid-ask only, several windows were chosen after looking (Hu's 6-day window, the 0-2.5% bands, Arif-Da-Lin's 24 months), and the only post-publication evidence (Kurov-Wolfe-Gilbert; T-341, T-343) shows decay.

## What Mandel adopts

- **Nine conditional successors are testable now, pre-registered as successors, not discoveries.** `vix-buildup-pre-fomc-drift` (T-341/T-215/T-343) ends the VIX change at t-2 so it is point-in-time, and tests an event-versus-non-event interaction controlling for T-332's reversal; power is about 1 SE. `hvix-next-session-premium` enters at the t+1 open and must beat decile-matched price drops; T-535 and T-580's VIX-level IC (+0.11 at 1 day on equity ETFs) agree in sign, while T-421 found a spread shock added nothing beyond the VIX change.
- **`treasury-pre-auction-concession` has the strongest prior.** T-442's secondary already saw -27.6 bps over t-5..t-1 in 10/30-year weeks (p 0.0022), so the primary evidence is the unseen 2-, 5-, 7- and 20-year weeks of 2014-2026, deduplicated, FRNs and TIPS removed.
- **Mechanism tests.** `dash-for-cash-settlement-shift` uses the paper's T-2 autocorrelation on the US 2017 T+2 switch, IEF as the no-shift control, agreeing with T-59, T-345 and T-574. `fomc-window-short-dollar-carry` (OANDA) uses a two-day noon window containing the pre-announcement leg, with a T-575 month-end control. `post-fomc-treasury-yield-drift` holds out 2008-11 on and needs 60 non-ZLB meetings.
- **`threshold-rebalancing-signal` must add to T-345 and turn-of-month dummies; `payday-16th-anomaly` is one pre-specified day.**
- **`putwrite-weekend-decay-excess` unblocks T-526 on archived PUT marks** with a 1.5x variance-ratio null from T-511 (weekend variance 1.27 weeknights), net of the variance risk premium PUT always carries. It agrees with T-216 and T-170; any trade starts as a defined-risk shadow (T-561: drawdown -70%).
- **Forward or blocked:** `pre-fomc-day-minus-1-predictor` counts only origins after 2021-12; dealer-gamma `gex-conditioned-intraday-momentum` (after T-427) needs DIX.csv archived; dividend payday needs pay dates; quarter-end mark-up needs 13F data and a frozen classification rule.
- **The children set the expectation.** The event-contract children's learnings class these as risk or flow premia, not reference-price leads, judged as cost-charged return tilts; their Fed bucket rule shows a telegraphed regime (2024-25) shrinks event premia.

## What Mandel holds loosely or rejects

- **Decayed:** the unconditional pre-FOMC drift (T-341 -5.3 bps over 2016-2026; T-215 +4.4, CI -15 to +23), the announcement-day premium (T-343: +12.7 bps 1993-2009, fails over the full span), FOMC-cycle weeks (T-342 -5.2 over 2017-2026), payday seasonality.
- **Contradicted by Mandel:** Savor-Wilson is dropped as T-343 in substance; T-384 found high beta beating low beta on ordinary days and T-387 failed. Quarter-end mark-up starts from T-346/T-439, wrong sign, same sign at placebo month-ends. T-358: event-contract uncertainty did not scale pre-event SPY returns (p 0.553).
- **Dead after costs:** same-weekday momentum (replacing the book daily costs about 15 bps against 10 gross); T-60, T-347 and T-476 agree.
- **No data path:** the Stivers-Sun OPEX-week cross-section (paper unopened; the capture box covers 14 underlyings; T-353/T-438 failed and T-192/T-502 found no pinning).
- **Not registered:** crypto hour-of-day seasonality, which the desk child's 549-trial null rejects. Everything here trades on US-legal venues (Alpaca, CME, OANDA).

## Design implications for the RSI predictive substrate

- **Features:** event dummies (FOMC, CPI, payrolls, auction week by tenor, OPEX, pre-holiday, month position T-k by settlement regime); VIX build-up z ending t-2; VIX-minus-EWMA spike; auction-size z; the rebalancing deviation (flow family, leakage review); same-weekday mean return as one deflated F0 feature in T-578. No T-578 cell with calendar features passed (0 of 306), so they enter as interactions with implied volatility, gamma or flows.
- **Data to add:** DIX.csv with fetch hash, dividend pay dates, per-stock option volume history, SEC 13F data sets, FRED SOFR and target series, an ISM calendar, intraday VIX history.
- **A shared calendar utility against the look-ahead traps found here:** the realised NYSE calendar with unscheduled closures dated at announcement, SEC-verified settlement dates, and release timestamps (VIX 16:15 ET, H.10 noon FX, H.15 yields next day, split-adjusted dividends, DIX.csv without vintages).
- **Gate:** matched non-event placebos, joint deflation with each predecessor family, declared power. Nothing joins T-559's calendar sleeve or T-567 before a pass and an independent refutation.

## Cross-links

- A4: structure shows at coarser horizons; the bond drift and Day -1 predictor are monthly.
- A5: skill is measured against a benchmark.
- 12, 13, 14: those workflows add calendar features first; this file records which survive.
- Theories: T-59, T-170, T-215, T-216, T-332, T-341 to T-347, T-349, T-353, T-358, T-384, T-387, T-421, T-427, T-439, T-442, T-511, T-526, T-535, T-559, T-561, T-567, T-574, T-575, T-577 to T-580. Children: fed_watch, H-btc-tom, desk-child addendum 25.

## Sources used

- Hu et al., NBER w25817: https://www.nber.org/system/files/working_papers/w25817/revisions/w25817.rev2.pdf
- Kurov et al., FRL 40: https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html
- Savor-Wilson, JFE 113: https://ideas.repec.org/a/eee/jfinec/v113y2014i2p171-201.html
- Wachter-Zhu, NBER w24432: https://www.nber.org/papers/w24432.pdf
- Mueller et al., FMG DP 54: https://www.fmg.ac.uk/sites/default/files/publications/dp-54.pdf
- Brooks et al., NBER w25127: https://www.nber.org/papers/w25127
- Etula et al., RFS 33: https://acris.aalto.fi/ws/portalfiles/portal/40965155/hhz054.pdf
- Harvey et al., NBER w33554: https://www.nber.org/papers/w33554
- Hartzmark-Solomon, NBER w30688: https://www.nber.org/papers/w30688
- Baltussen et al., JFE 142: https://academicweb.nd.edu/~zda/intramom.pdf
- SqueezeMetrics DIX/GEX: https://squeezemetrics.com/monitor/static/DIX.csv
- Lou-Yan-Zhang, RFS 26: https://ideas.repec.org/a/oup/rfinst/v26y2013i8p1891-1912.html
- Quantpedia (Ma-Pratt): https://quantpedia.com/strategies/payday-anomaly
- Quantpedia (Stivers-Sun): https://quantpedia.com/strategies/option-expiration-week-effect
- Arif-Da-Lin: https://academicweb.nd.edu/~zda/FOMC.pdf
- Jones-Shemesh, JF 73: https://ideas.repec.org/a/bla/jfinan/v73y2018i2p861-900.html
- Muravyev-Ni, JFE 136: https://ideas.repec.org/a/eee/jfinec/v136y2020i1p219-238.html
- Ben-David et al., JF 68: https://ideas.repec.org/a/bla/jfinan/v68y2013i6p2383-2434.html
- SEC 13F data sets: https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
- Da-Zhang: https://academicweb.nd.edu/~zda/Same_Weekday_Momentum.pdf
