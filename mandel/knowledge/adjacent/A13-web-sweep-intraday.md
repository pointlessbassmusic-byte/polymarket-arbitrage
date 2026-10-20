# Intraday and time-of-day return patterns: a survey of intraday momentum, overnight drift, closing-auction pressure, fix flows and clock seasonality

- **Authors / kind:** cluster survey of 15 claims from the 2026-10-20 web sweep. Peer-reviewed core: Gao et al. (JFE 2018), Baltussen et al. (JFE 2021), Boyarchenko-Larsen-Whelan (RFS 2023), Lou-Polk-Skouras (JFE 2019), Akbas et al. (JFE 2022), Bogousslavsky (JFE 2021), Krohn-Mueller-Whelan (JF 2024), Heston-Korajczyk-Sadka (JF 2010), Berkman et al. (JFQA 2012). Working papers: Bogousslavsky-Muravyev, Baltussen-Da-Soebhag, Da et al., Zarattini et al.
- **Links:** https://academicweb.nd.edu/~zda/intramom.pdf · https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf · https://personal.lse.ac.uk/polk/research/TugOfWar.pdf · https://academicweb.nd.edu/~zda/EOD.pdf · https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf · https://academicweb.nd.edu/~zda/IntraOption.pdf
- **Coverage confidence:** 0.45 (8 of 27 cited sources read in full; 9 checked at abstract, review or replication level, counted at half weight; 10 cited but not opened).
- **Date researched:** 2026-10-20. **How much was read:** full texts of the six linked papers, Gao et al. and Bogousslavsky-Muravyev; abstracts or reviews for the rest. The stocks-in-play ORB returns are paywalled and unverified, and the web-search budget ran out, so most post-2020 decay searches were impossible.
- **Selected because:** time of day is an input on every bar of the learning program (T-577), Mandel's best-known intraday tests failed (T-427, T-428), and every auction-timed rule it runs (T-549, T-559) pays the costs this literature measures.

## What it says

- **Gamma-conditioned intraday momentum.** Short-gamma hedgers (dealers at negative gamma exposure, built from open interest; leveraged ETFs) trade with the move into the close. The prior-close-to-15:30 return predicts the last half-hour: equity futures t 7.29, out-of-sample R² 2.88% (60+ futures, 1974-2020); slope 6.63 (t 4.78) after negative-NGE days, 0.82 (t 1.03) otherwise. Gao et al. (SPY 1993-2013): out-of-sample R² 1.4%. No post-2020 independent replication.
- **Volume/news conditioning.** Stronger on high first-half-hour volume, volatile and macro-news days, but Gao's terciles are formed within each year (a look-ahead). The noise-area breakout (Sharpe 1.33 net) is unreplicated.
- **Leveraged-ETF rebalancing.** Demand = AUM × (x²−x) × the day's return, executed near the closing auction (16.8% of MOC volume on a 1% day in 2009); interaction t 2.2-3.1 (2006-2020). Contested: ETF flows into and out of LETFs may offset it.
- **Overnight drift at the European open.** Dealers unload US-close inventory when European liquidity arrives: ES 02:00-03:00 ET earns 1.48 bp/day (1998-2020), positive in 20 of 23 years, the only hour surviving Bonferroni. Sharpe 1.1 before costs, −0.5 after the spread; after negative closing signed volume, 1.1 net.
- **Tug of war.** Past-month overnight return predicts overnight returns (+3.47%/month, t 16.6) and intraday reversal (−3.24%), 1993-2013.
- **Daytime-reversal intensity.** More overnight-up/intraday-down days than a stock's norm predicts +0.92%/month EW (1993-2017, gross), 0.43% in the top market cap group; non-US replications reportedly fail.
- **End-of-day reversal.** Intraday losers bounce in the last half-hour, 3.78-6.86 bp/day gross (t > 10, 1993-2019), via retail dip-buying and short sellers avoiding new overnight positions. Unreplicated; the authors doubt it survives costs.
- **Anomalies de-risked at the close.** Overnight margin and securities lending fees make arbitrageurs cut mispriced positions before the close (abstract only).
- **Closing auction pressure.** The auction reached 7.48% of dollar volume (2018); the official close sits 8.1 bp from the last midquote (2.7 bp for large caps) and reverts half within 20 minutes, fully overnight. Only the change in intraday-to-auction volume predicts returns (4.2%/yr).
- **FX fixing W.** The dollar rises into the Tokyo and London fixes and falls after (a long-foreign basket −5.0%/yr before Tokyo, +5.3% after; G9 1999-2019). Decayed to −1.6/+2.1 in 2014-2019; full spreads erase it.
- **Same-half-hour continuation** for up to 40 days (JF 2010). Decaying: the first lag reportedly fell ~75%; an FX/S&P/BTC replication breaks even at 0.05 bp against 0.6 bp of cost.
- **Straddle same-interval momentum.** Prior-day 09:35-10:00 straddle winners repeat (73 bp/day, t 22, 2010-2024). Mid-quote only; single-name spreads of several percent swamp it.
- **BTC 22:00-00:00 UTC.** Two hours a day earned most of BTC's 2015-2021 return (Sharpe 1.58, no costs, weak in bear markets); a US-close spillover is the guess. Practitioner, no post-publication replication.
- **Intraday volatility U-shape.** Realised volatility peaks at the open and close and spikes at 08:30 releases and the 14:00 FOMC (10.9× on payroll Fridays); year-to-year profile correlation 0.91. Whether 0DTE implied volatility prices it is untested.
- **Opening range breakout.** The plain 5-minute ORB replicates gross (NQ +0.131 R) but nets +0.002 R on NQ and −0.04 to −0.08 R on four other indices (2015-2026).
- **Attention buying at the open.** High-attention stocks gain overnight and reverse intraday; buying them at the open costs more than the half-spread (JFQA 2012).

## Evidence quality

**Rating: rigorous.** The core is peer-reviewed, with long samples, out-of-sample R² and multiple-testing corrections. The rating is for the sources, not tradability: nearly every figure is gross, samples end 2013-2020, and three claims (noise-area, stocks-in-play, BTC block) are practitioner grade.

## What Mandel adopts

- **Costs first.** `closing-auction-deviation-overnight-reversal-60m` is testable now on 718 sessions (the 60m 15:30 bar's close is the last regular trade, checked against 5m bars). It prices the auction for T-559's sleeve, T-549's overnight hold and the cross-sections below, and reframes T-428 (slope −0.084), whose regressor partly measured auction deviation. `attention-open-pressure-intraday-shortfall-sp500` is its opening-auction twin.
- **Flow-conditioned T-427 successors.** T-427's null (gross −0.09 bp, slope −0.004, t −0.22, 2023-2026) is what hedging-demand theory predicts: only 19 of 734 sessions had negative free GEX. `gex-conditioned-rod-last-half-hour-momentum` (volatility control, T-427's 60 cells deflated in) and `letf-rebalancing-demand-last-half-hour-panel` are pre-registered as blocked; `intraday-momentum-high-opening-volume` is testable now, with trailing cut-offs. A reconciliation, not a confirmation.
- **Overnight cross-section.** T-549 (QQQ/IWM overnight +3.4 to +3.6 bp/night net, supported) agrees with Lou-Polk-Skouras at index level. `overnight-return-persistence-sp500-top-decile`, `negative-daytime-reversal-intensity-sp500` and `dtc-decile-overnight-minus-intraday-sp500` (FINRA short interest days to cover) share T-348's decomposition, point-in-time membership and a 90% survivorship coverage gate (coverage left T-375/T-393 inconclusive).
- **`es-0200-et-drift-after-closing-hour-selling`** on ES/MES, verdict to Hurst's proposed H-us500-overnight (drift against the perp funding rate). An ES tick has shrunk from ~1.25 bp to ~0.32 bp since the paper's era.
- **Timing and features, not trades:** `usd-fix-pre-post-reversal-7ccy` (FX conversions on OANDA), `same-hour-return-continuation-60m-xs` (into T-577's F2 only if it passes), `vix1d-open-fomc-session-variance-ratio` (an event-hour variance risk premium; informs T-217/T-218 after T-529 found VIX1D cheap), `end-of-day-reversal-28-megacaps` as a pilot, and `btc-2200-0000-utc-block-seasonality`, reusing Hurst's coin-hour cells first.

## What Mandel holds loosely or rejects

- **Unconditional intraday momentum.** Absent in Mandel's window (T-427: SPY −2.09, QQQ −2.42, IWM −1.04 bp/day net). The T-579 scan points the other way: return since the open and VWAP distance predict the next bar inversely for equity ETFs from 5m to 60m (60m confirmed IC −0.108, t −3.7) and for crypto; tod_sin/cos and lv_rel_tod never confirmed, and T-577 passed 0 of 276 intraday cells. The measured regime is reversal, too small to trade.
- **Free GEX is not the paper's NGE** (~6% negative days against 48%, backfilled, clustered in 2022): its sign is a regime dummy unless volatility is controlled.
- **Decayed:** same-half-hour periodicity, the Tokyo fix, the 02:00 drift after spread. **Unreplicated:** noise-area, stocks-in-play, BTC block, end-of-day reversal. Hurst's H-orb-qqq has 0 trades in 5 paper sessions.
- **Hour-scale crypto rules** fail on US venues: Hurst's best hourly rule on 20 Kalshi perps made +26 bp gross, −45 bp walk-forward, against a 16-18 bp round trip; 6,096 rules deflate to nothing. The BTC day-of-week effect passed (T-436) but not under Bonferroni (T-354, p 0.077).
- **Return-state conditioning of overnight holds** added nothing (T-563) and T-333's gap fade lost 6.25 bp/trade, so the ES test uses a signed-volume proxy, not a return tercile.
- **LETF flow** is contested and T-325 failed; USD month-end flows failed (T-575); straddle momentum is a market maker's edge. Nothing here needs an offshore venue.

## Design implications for the RSI predictive substrate

- **Archive, first-seen stamped:** SqueezeMetrics DIX/GEX; Alpaca IEX 1-minute SPY/QQQ from 2020-08; Dukascopy USA500 and FX minutes from 2012; LETF shares outstanding × NAV; capture-box chains at 09:35/10:00/15:30/16:00; 15:59:50 NBBO mids.
- **Features (T-577/T-578):** same-time-of-day lagged returns; overnight/intraday components; auction deviation; r_ROD × GEX_{t-1}; LETF demand; ET clock with DST asynchrony; FOMC/CPI/payrolls/OPEX/month-end/earnings flags; Reg SHO off-exchange share; realised volatility over its time-of-day profile.
- **Harness rules:** exit at the official close, never a 16:00 stub; dividend-adjust returns spanning the prior close; drop early closes; verify bar stamps (Yahoo stamps by open); trailing cut-offs only; a maker entry fills only on a print through it (the children's adverse-selection learning); deflate for T-427's 60 cells and Hurst's 478 coin-hours.

## Cross-links

- A4: the volatility U-shape is "trading time"; time-of-day normalisation deforms the clock. A5: how fast information enters price (the children's in-play results are the extreme case).
- 13 (HMM regimes) → T-562/T-563; 14 (look-ahead) → bar-stamp rules; 12 → backtest-to-live attrition on ES bars.
- UNDERLYING-STRATEGIES.md (`intraday-half-hour-momentum`, `opening-range-breakout`, `overnight-vs-intraday`, `closing-auction-reversal`), OPTIONS-STRATEGIES.md (0DTE), VENUES.md.
- T-427, T-428, T-426, T-348, T-549, T-563, T-333, T-559, T-529, T-216, T-217, T-218, T-375, T-393, T-414, T-419, T-436, T-354, T-325, T-575, T-577, T-579.

## Sources used

- Baltussen et al., JFE 2021 (full text): https://academicweb.nd.edu/~zda/intramom.pdf
- Gao et al., JFE 2018 (full text): https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf
- Zarattini, Aziz & Barbon, SFI RP 24-97 (abstract): https://ideas.repec.org/p/chf/rpseri/rp2497.html
- Boyarchenko, Larsen & Whelan, NY Fed SR 917 (full text): https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf
- Lou, Polk & Skouras, JFE 2019 (full text): https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Akbas et al. (CXO review): https://cxoadvisory.com/?p=32204
- Baltussen, Da & Soebhag, 2025 (full text): https://academicweb.nd.edu/~zda/EOD.pdf
- Bogousslavsky, JFE 2021 (abstract): https://ideas.repec.org/a/eee/jfinec/v141y2021i1p172-194.html
- Bogousslavsky & Muravyev, 2020 (full text): http://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7
- Krohn, Mueller & Whelan, BoC SWP 2021-48 (full text): https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf
- Heston, Korajczyk & Sadka (abstract): https://arxiv.org/abs/1005.3535
- Andersen-Bollerslev replication: https://github.com/sakshamg251206/intraday-seasonality-andersen-bollerslev
- Da et al., 2026 (full text): https://academicweb.nd.edu/~zda/IntraOption.pdf
- Quantpedia, BTC overnight seasonality: https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin
- ORB replication (MQL5): https://www.mql5.com/en/blogs/post/776235 · CXO on Zarattini, Barbon & Aziz: https://www.cxoadvisory.com/?p=45379
- Berkman et al., JFQA 2012 (abstract): https://www.cambridge.org/core/product/identifier/S0022109012000270/type/journal_article
- SqueezeMetrics DIX/GEX: https://squeezemetrics.com/monitor/static/DIX.csv
- Cited, not opened: Li-Sakkas-Urquhart, Ivanov-Lenkey, Cheng-Madhavan, Bondarenko-Muravyev, EFMA 2024 (503), Dim-Eraker-Vilkov (403), four others.
