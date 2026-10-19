# Mandel cycle 4 report, 2026-10-19: the audit, five batches, and the data that cannot be redistributed

*DRAFT at the cycle's working close. Five sections, each drafted by a reader agent from the ledger, experiment log,
registry, archive INDEX and commit log and then checked number by number by an independent agent; every figure carries
its source in an HTML comment that renders invisibly, so the file is auditable in the raw. Sections were read at
slightly different minutes on 2026-10-19 (21:00 to 21:24 UTC) while the Kraken and StockTwits fetches were still
appending to the archive, which is why a few totals differ by a few bundles between sections; each states its own read
time. Lines marked [[PENDING]] wait on the six claims still running (T-331, T-425, T-459, T-465 on Kraken 1-minute
trades; T-414, T-415 on StockTwits) and on the T-337 re-run and refutation; they are filled when those land and the
totals are re-read once, together.*

*Section 01, summary. Written at the close of cycle 4 (2026-10-15 to 2026-10-19), branch `claude/mandel-genesis`.
Every count below is taken at a cut-off of 2026-10-19 21:00 UTC: INDEX entries and ledger events stamped before 21:00,
commits before 21:00, and the experiments and registry files as they stood then (last written 20:06 and 20:20 UTC)
<!-- stat mtimes: INDEX.json and ledger.jsonl 20:54 UTC, experiments.jsonl 20:06, registry.json 20:20 -->. The Kraken
1-minute and StockTwits fetch chains were still writing at that moment, so the archive, ledger, commit and Kraken figures
must be refreshed together at the final cut-off; the lines marked [[PENDING]] are for the lead to fill. Nothing was
deleted; every verdict, park and block is in the ledger with its reason.*

## The one-paragraph version

Cycle 4 was the cycle in which Mandel stopped writing claims and started grinding them. In five days and
101 commits <!-- git log --since='2026-10-15 00:00:00' --until='2026-10-19 21:00:00' count --> it recorded 575 experiment
results <!-- experiments.jsonl count, created_at 2026-10-15..19 --> against 342 theories through 342 harnesses
<!-- experiments.jsonl distinct theory_ids / distinct harness --> and stored 3,444 data bundles holding 51,092,137 rows
and 1.87 GB <!-- INDEX count/rows/bytes, created_at 2026-10-15..19 before 21:00 UTC -->, 3,303 of them on local disk
only under the rule that data whose terms forbid redistribution is stored local-only
<!-- INDEX in_git=false count; MANDEL.md §7 2026-10-15 entry -->. It began with an adversarial audit of the first 125
harnesses that confirmed 81 defects and fixed them in three independently checked rounds
<!-- MANDEL.md §2 Harness rules preamble -->, wrote the twelve harness rules down <!-- MANDEL.md §2 rules 1-12 -->,
and re-ran all 262 harnesses on the corrected code, which moved 95 statuses <!-- commit 5a1a5c8 -->. Then came the
batches: 4 and 5 (45 harnesses), 6a (43 options claims), 6b (49 harnesses on Cboe strategy indices, DoltHub chains,
box rates, OPEC dates and Deribit trades) <!-- MANDEL.md §7 2026-10-15 --> and 6c (80 underlying-library claims, 18 on
data already archived and 62 on freshly fetched Yahoo, FRED, ALFRED, CFTC, SEC, FINRA, Coinbase, Kalshi and Polymarket
histories) <!-- experiments.jsonl b6c_* distinct theory_ids and created_at by day; commit 6e09d78 -->. The registry went
from 250 untested theories to 6; supported rose from 24 to 51, not supported from 53 to 239, inconclusive from 8 to 45,
parked from 8 to 15 <!-- git show 188a9c7:mandel/theories/registry.json vs registry.json -->. The supported column is
mostly variance premia (14) and model-priced option structures (16), with six calendar or seasonal effects (T-59, T-345,
T-349, T-357, T-436, T-515), five Polymarket market-structure claims (T-06, T-07, T-10, T-11, T-36), three VIX
term-structure claims (T-53, T-534, T-535), two Cboe index comparisons (T-168, T-170) and five others (T-228, T-320,
T-332, T-366, T-514) <!-- registry.json status=supported, grouped by claim text -->; several are descriptive (a premium
exists, a drift exists) and none is a demonstrated after-cost trading edge. The one prediction-market result with an
apparent after-fee edge, T-337's fade of Polymarket "Bitcoin above" prices against the Deribit digital (+4.7 cents per
contract after fees over 4,987 trades <!-- registry T-337 notes -->), is held at inconclusive until its Binance
resolution control runs [[PENDING]].

## Theories by status

Cycle start is the first registry commit of 2026-10-15 (`188a9c7`, 07:16 UTC <!-- git log registry.json, oldest since 2026-10-15 00:00 -->);
it differs from the cycle-3 addendum only by T-542, pre-registered that morning <!-- ledger theory.preregistered T-542 seq 1785 -->.

| Status | Cycle-3 report close <!-- REPORT-cycle3 addendum --> | Cycle start `188a9c7` <!-- git show 188a9c7:registry --> | Cycle end <!-- registry.json status count --> | Change over the cycle |
|---|---|---|---|---|
| supported | 24 | 24 | 51 | +27 |
| not supported | 53 | 53 | 239 | +186 |
| inconclusive | 8 | 8 | 45 | +37 |
| untested | 250 | 250 | 6 | -244 |
| blocked | 132 | 133 | 121 | -12 |
| parked | 8 | 8 | 15 | +7 |
| total | 475 | 476 | 477 | +1 (T-543, pre-registered forward test <!-- ledger theory.preregistered T-543 seq 2132 -->) |

268 of the 476 theories present at cycle start changed status, and T-543 was added
<!-- git show 188a9c7:registry vs registry.json, per-id diff -->. The large moves: 173 untested to not supported,
31 untested to supported, 30 untested to inconclusive, 11 blocked to not supported, 5 blocked to inconclusive,
1 blocked to supported (T-224) <!-- same diff -->. Five theories lost support on
the audited re-run: T-01, because the calibration harness now scores only horizons with n >= 300 and the 90-day
horizon has 260 <!-- X-cf9d5ba7 -->; T-13, because on those horizons the strict ordering fails, skill 0.780 at 1 day
against 0.795 at 3 days <!-- X-29198603 -->; T-241, whose sentence says the curve already prices the post-spike VIX
decline when VIX lands below the forward in 19 of 23 spikes, so the curve under-prices it <!-- X-ba679106 -->; T-350,
whose SPY Santa excess is +0.49 pp against the claim's 1 pp bar <!-- X-83672e35 -->; and T-530, where only 30 of 63
grid phases pass under rule 10 <!-- registry T-530 notes -->.
Seventeen theories were unblocked by a free fetch <!-- ledger theory.unblocked count -->, four were newly blocked because
they need survivorship-free single-stock data (T-391, T-392, T-395, T-452 <!-- ledger theory.blocked seq 2510-2513 -->),
and seven were parked, each under its own trial's park rule (T-324, T-389, T-445, T-469 on 10-15; T-405, T-404 on 10-16;
T-328 on 10-19 <!-- ledger theory.parked count and payloads -->). Six remain untested because their data is still
arriving: T-331, T-425, T-459 and T-465 wait on Kraken 1-minute trades, T-414 and T-415 on the StockTwits chain
<!-- registry status=untested ids --> [[PENDING]].

## Experiments recorded this cycle

| Verdict | Records <!-- experiments.jsonl verdict count --> | Theories whose last cycle-4 record carries it <!-- experiments.jsonl last record per theory_id --> |
|---|---|---|
| not supported | 402 | 247 |
| supported | 103 | 50 |
| inconclusive | 69 | 45 |
| error | 1 | 0 (T-266, `eth_btc_dvol_ratio` raised ValueError; the re-run is inconclusive at 21 of 25 signals <!-- X-7cf64c6f, X-808aaa9a -->) |
| total | 575 | 342 |

By day: 513 on 10-15, 29 on 10-16, 33 on 10-19 <!-- experiments.jsonl created_at by day -->. 174 theories have more
than one record this cycle because the official re-runs recorded again on the corrected code
<!-- experiments.jsonl theory_ids with >1 cycle-4 record -->. 162 of the 575 records are labelled MODEL-PRICED in their
reason, including 37 of the 103 supported ones <!-- experiments.jsonl reason contains 'MODEL-PRICED' -->. Most of them
are Black-Scholes legs at a VIX-, GVZ- or DVOL-based IV (VIX is named in 65 of the 162 reasons, DVOL in 25, GVZ in 12
<!-- experiments.jsonl keyword counts over the MODEL-PRICED reasons -->); two Deribit records fit their IVs from trade
prints instead, T-262's calendar inversion under Black-76 and T-257's risk-reversal harvest under Black-Scholes
<!-- X-550ca26f, X-f3e5922c -->, and one, T-275's SLV call backspread, prices at SLV's trailing 60-day realised vol
<!-- X-9856d560 -->; none is a traded quote. The smile held fixed from two captured SPY quote days belongs to the SPY
structure records <!-- registry T-114 notes; 'quote day' appears in 69 of the 162 MODEL-PRICED reasons, 63 of them structure_t_* -->.
Batch 6c recorded 80 claims once each: 18 on data already archived on 10-15 (recorded 20:26-20:28 UTC under commit
6e09d78, before the batch's Yahoo/FRED fetch was stored at 23:04 <!-- commits 6e09d78, 933c7de; experiments.jsonl b6c_* created_at -->)
and 62 on 10-16 and 10-19 on data fetched later in the cycle; the verdicts are 4 supported, 65 not supported,
11 inconclusive <!-- experiments.jsonl b6c_* verdicts and created_at by day -->. One supported theory, T-148, has no
cycle-4 record and keeps its earlier verdict <!-- registry status=supported minus experiments.jsonl cycle-4 theory_ids -->.

## Data fetched this cycle

All archive figures are read at the 21:00 UTC cut-off (INDEX `created_at` and ledger `ts` before 21:00) and must be
refreshed together at the final one.

| | Bundles | Rows | MB |
|---|---|---|---|
| Stored with a cycle-4 `created_at` <!-- INDEX count/rows/bytes, created_at 2026-10-15..19 before 21:00 UTC --> | 3,444 | 51,092,137 | 1,872.1 |
| of which local-only (`in_git: false`) <!-- INDEX in_git filter --> | 3,303 | 49,863,331 | 1,831.0 |
| of which committed to git <!-- INDEX in_git filter --> | 141 | 1,228,806 | 41.1 |
| Whole archive at the 21:00 UTC cut-off <!-- INDEX count, all entries --> | 3,474 | 51,265,846 | 1,881.4 |
| Archive at the cycle-3 close <!-- REPORT-cycle3 'Registry' paragraph --> | 66 | 395,688 | |

3,389 of the 3,444 names are new; 55 are earlier bundles re-stored, which is why only 30 entries still carry a
pre-cycle stamp <!-- ledger archive.stored names before/after 2026-10-15; INDEX created_at < 2026-10-15 count -->. The
ledger holds 3,860 `archive.stored` events for the cycle <!-- ledger kind count, ts before 21:00 UTC -->. Every one of
the 3,303 local-only bundles carries its rebuild recipe <!-- INDEX recipe non-empty count -->, so what is not in git can
be re-fetched rather than re-found. The rule behind local-only is MANDEL.md's: data whose terms forbid redistribution is
stored local-only <!-- MANDEL.md §7 2026-10-15 entry -->, and the commits apply it source by source: 313 of the 327
batch-6c Yahoo/FRED bundles are git-ignored while the federal public-domain FRED and ALFRED series go in and the
copyrighted FRED series (Moody's, Michigan, OECD, NBER) stay local <!-- commit 933c7de -->, and 47 daily-history bundles
stored this cycle, 29 of them re-stores of pre-cycle names such as SPY, QQQ, GLD and BTC-USD, remain in git
<!-- INDEX daily-history-* in_git=true with cycle-4 created_at; ledger archive.stored names before 2026-10-15 -->; CFTC COT,
Treasury auctions, SEC tickers and the Wikipedia S&P 500 tables are in git while Coinbase, Cleveland Fed and the other
restricted sources are not <!-- commit bb793fd -->; the DoltHub chains are CC BY-SA 4.0 and are committed with attribution
<!-- data/dolt_options.py docstring -->; the Deribit trade history, the SEC EDGAR bulk files and the Coinbase,
CoinMarketCap, CoinMetrics, DefiLlama and iShares crypto history are all local-only <!-- commits 92e7fa5, a10fa1c, 5a438d3 -->.
The largest local-only families by size: Deribit 38 bundles, 9,827,400 rows, 313.2 MB; Kalshi 140, 8,253,929, 281.0 MB;
Yahoo daily bars and events 1,709, 6,462,799, 239.9 MB; Coinbase 662, 7,096,665, 207.7 MB; CoinMarketCap 11, 2,102,479,
204.0 MB; Polymarket 169, 4,273,925, 176.6 MB; FINRA 310, 3,433,827, 134.1 MB; SEC 73, 5,676,554, 127.4 MB
<!-- INDEX local-only bundles grouped by name prefix -->. One repair was needed: 25 INDEX entries that a stale concurrent
writer had reverted before the archive's reload fix were restored from their `archive.stored` events, and `verify` now
checks every bundle's size against the INDEX <!-- commit a166657; ledger archive.index.repaired count 25 -->.

Still writing at the cut-off: Kraken XBTUSD 1-minute trades, 25 monthly bundles covering 2022-01 to 2024-01 so far,
1,087,487 rows, 101.4 MB, latest stored 20:54 UTC <!-- INDEX kraken-trades-1m-XBTUSD-* bundles, created_at before 21:00 UTC -->
(the separate `kraken-trades-stablecoin-episodes` bundle, 705,691 rows and 18.0 MB of USDT/USDC peg-episode trades for
T-330 stored on 10-16, is not part of that chain <!-- INDEX kraken-trades-stablecoin-episodes rows/bytes/tags/recipe -->)
[[PENDING]]; the StockTwits chain for T-414 and T-415, of which only the two daily `social-stocktwits` captures of 10-14
and 10-15 exist in the INDEX <!-- INDEX name match stocktwits --> [[PENDING]]; and the Binance BTCUSDT resolution klines
for T-337, whose bundle `binance-1m-BTCUSDT-btc-above` landed at 20:13 UTC with 83,692 rows but has not yet been run
<!-- INDEX binance-* bundle; registry T-337 status inconclusive --> [[PENDING]].

## Headline findings, in five sentences

First, the variance risk premia are real and survive rule 10's pooling over every grid phase: BTC's DVOL-squared exceeds
realised 30-day variance by +0.0940 (95% CI +0.0493 to +0.1436, 30 of 30 phases) <!-- X-a25e88fc -->, gold's GVZ premium
is +0.0062 (21 of 21 phases) <!-- X-b8cf2713 -->, oil's OVX premium +0.0398 (18 of 21) <!-- X-3313ccaf -->, and short
variance struck at VIX-squared and settled on SPY close-to-close realised variance earns +8.12 %^2 a month (CI +1.43 to
+11.22) over 403 cycles, with the tail reported rather than hidden: skew -7.60, kurtosis 93.0, a worst cycle of -630.8
entered 2020-02-26, and +9.44 with the 41 entries overlapping it removed <!-- X-a7f44bf6; registry T-540 notes -->;
these are descriptive premia, measured without fees or margin, and not a strategy. Second, 37 supported records are
MODEL-PRICED and say so <!-- experiments.jsonl reason contains 'MODEL-PRICED', verdict supported -->: the delta-hedged
short 30-day BTC straddle makes +9.5% of premium with an after-fee Sharpe of 0.71 at the measured 0.945 ATM/DVOL scale
<!-- registry T-255 notes -->, the 25-delta GLD put-write +0.35% of strike per monthly cycle <!-- X-8846da32 -->, the
SPY jade lizard's edge shrinks to +0.71% at an IV scale of 0.81 <!-- registry T-113 notes -->, and every one of them
still awaits its traded test on chain mids. Third, three calendar effects on the underlying passed as worded, all from
batch 6c's archived-data group: T-345, SPY's last two sessions of the month lose a net -45.6 bps (CI -77.4 to -13.1)
after SPY has beaten TLT by more than 2 pp month-to-date, under both rule-12 readings <!-- X-a500a4a7; registry T-345 notes -->;
T-357, the pre-election-year excess of +7.76 pp, rests on 24 observations since 1928 <!-- X-71e7a233 -->; and T-349,
IWM's pre-holiday session, passed at p 0.0476 and flips to undecided under a non-circular bootstrap
<!-- X-f37df8d5; registry T-349 notes -->. Separately, one batch-4 technical rule passed: T-332's IBS < 0.2 next-day
reversal is +12.03 bps over the unconditional mean with a DSR of 0.976, but the pass statistic trades at the close that
defines the signal, so the +7.54 bps open-to-close execution reading is the honest one
<!-- X-660e7d9f; batch4_ohlc.py ohlc_ibs_reversal; registry T-332 notes -->. Fourth, the only supported result from the
new fetches, T-366, is a drift and not an edge: the Coinbase cbETH/ETH ratio rose +2.79% a year (HAC CI +2.70 to
+2.88) over 1,261 days and the refuter could not move it, which says the market discount did not eat the staking yield,
and capturing it means holding cbETH, which is the staking yield itself <!-- registry T-366 notes; X-adc486b0 -->. Fifth,
the rules did more work than the data: the audit's 81 confirmed defects <!-- MANDEL.md §2 preamble --> and the 95 status
changes on re-run <!-- commit 5a1a5c8 --> include T-530 losing support because only 30 of 63 grid phases pass
<!-- registry T-530 notes -->, T-162 falling to undecided because the Ledoit-Wolf test the trial names gives p 0.078
where the bootstrap passes <!-- registry T-162 notes -->, and T-220 failing under rule 12 because the gate and strike
read at one information set give +0.87% and +0.59% of max loss with intervals through zero <!-- registry T-220 notes -->.

## What the cycle did not find

It did not find a new tradable edge after costs. Of the 80 batch-6c claims, 65 are not supported, 11 are inconclusive
and the 4 supported are the three calendar effects (T-345, T-349, T-357) and the cbETH drift (T-366) above
<!-- experiments.jsonl b6c_* verdicts -->; all 25 claims on the Yahoo, FRED and ALFRED fetch came back not supported
<!-- commit 9399224 -->, all 24 factor-group records did too <!-- experiments.jsonl harness prefix fact -->, 16 of 17
FOMC records <!-- experiments.jsonl harness prefix fomc -->, and 12 of the 14 prediction-market claims <!-- commit 3cd7b4f -->,
where following Kalshi taker-flow imbalance nets -4.52 cents a contract out of sample on 5,529 trades because the mid
does not move against the taken side and the spread is crossed twice <!-- X-f2e6f009 -->. Two effects are real but
under cost and were parked for exactly that reason: the SPY/IVV twin reverts with an 11.3-day half-life but nets
-7.83 bp against +0.17 bp gross <!-- ledger theory.parked T-324 seq 2473 -->, and the IBIT premium fade makes +0.185%
gross against a 0.85% round trip <!-- ledger theory.parked T-328 seq 6209 -->. BTC's daily reversal was parked under the
same kind of rule but is a different case: its +11.3 bp against the 60 bp bar carries a CI of -23.6 to +47.2, so it is
indistinguishable from zero rather than real-but-small <!-- ledger theory.parked T-469 seq 2476 -->.
The single-stock claims could only be tested on a survivor subset: the index-addition reversal priced 266 of 322
additions and the short-volume ratio 93.4% of its events, both inconclusive for it <!-- X-b49ccc70, X-0bc4c55f -->, and
the three stock cross-section claims report survivor-only diagnostics, not their claimed universe
<!-- X-371fc97a, X-a4df2c9f, X-0040d3a6 -->. SKEW still predicts nothing about realised tails: its implied 2-sigma
probability averages 8.54% against a realised 1.05% <!-- X-1c42240d -->, which is why T-228 is supported as worded and
useless as a signal <!-- registry T-228 notes -->. And the Deribit history, fetched for four claims, supported none:
the FOMC straddle's implied-minus-realised move is +0.13% with a CI from -0.35% to +0.59% over 38 decisions
<!-- X-08824f68 -->, and the calendar inversion is not supported when its legs are MODEL-PRICED (Black-76) at
trade-fitted IVs <!-- X-550ca26f -->.

## 2. Method: how verdicts were produced this cycle

Cycle 3 closed with harnesses that had been written once and run once. Cycle 4 spent its first day finding out how
many of them were wrong, writing down the rules they had broken, and re-running everything on the corrected code
before any new claim was recorded. The rest of the cycle built new harnesses only through a workflow in which a
second agent tries to break each one before it is wired in, and a third tries to refute any 'supported' preview
before it is recorded. The ledger holds 575 experiment records since 2026-10-15 across 342 distinct harnesses
(402 not supported, 103 supported, 69 inconclusive, 1 error) <!-- experiments.jsonl, created_at >= 2026-10-15 -->;
this section is about how those verdicts were reached, not what they say. Where a 'supported' claim is named below,
read it as "the harness could not refute the claim as worded"; several are descriptive (a premium or a drift) or
model-priced, and none is a tradable edge after costs unless its own line says so.

### 2.1 The harness audit

An adversarial audit of the first 125 harnesses confirmed 81 defects, fixed in three rounds with each fix
independently checked <!-- MANDEL.md §2 Harness rules preamble -->.

| Round | What was done | Check | Source |
|---|---|---|---|
| 1 | 81 skeptic-confirmed findings applied across 9 experiment modules, one fixer per file, with regression tests (`tests/test_mandel_audit_*.py`); run.py carried 18 findings and underlying2.py 25 | independent checker: 68 fixes confirmed, 13 flagged for a second round; full suite 517 passed | <!-- commit bb34b14 --> <!-- commit 1bd890b --> |
| 2 | the 13 checker-flagged follow-ups and the parts the fixers had skipped: below min_n a failure counts only when decisive (market calibration, horizon order, longshot, bundle arb, Hurst, multifractal, holdout Sharpe); T-13 tests every named horizon including 3d; T-bills passed to low_vol_tilt and metals_tsmom; paired-timeline bootstrap for conditional_straddle | checkers: 20 of 23 checks pass; the 3 latent flags (T-435 window and min_n basis, T-231's reverse-calendar clause marked not implemented) handled in the next commit with no archived verdict change | <!-- commit dbd4451 --> <!-- commit 6f74735 --> |
| 3 | rule 5 applied before the verdict in all 9 cross_asset.py functions; batch-4 CPI-calendar controls implemented as each trial classes them (T-221, T-273, T-341, T-216) | checker: no real-archive verdict changes | <!-- commit 53c54e0 --> |

The audit changed verdicts only through an official re-run on the fixed code, never by hand. The re-run of the 106
audit-affected harnesses moved six theory statuses <!-- commit 089cebb -->: T-350 santa_rally supported to
not_supported (the claim's SPY >= 1 pp gate: +0.49 pp over 33 years), T-241 vix_spike_forward supported to
not_supported (the old harness had called a refuting result supported), T-13 horizon_monotone supported to
not_supported (skill 1d 0.780 <= 3d 0.795, n 389/382), T-01 market_calibration supported to inconclusive (90-day
horizon n 260 < min_n 300), T-231 term_vs_spot_premium not_supported to inconclusive (68 < 70 cycles, failure not
decisive), T-102 structure_t_102 inconclusive to not_supported (studentized CI -64% to +19% on 403 cycles)
<!-- commit 089cebb -->. The 106 records sit in the experiment log in the 11:00 UTC hour of 2026-10-15
<!-- experiments.jsonl, 106 records created 2026-10-15T11 -->. After round 3, the 19 cross-asset and 4 CPI-control
harnesses were re-run (23 records in the 12:00 hour <!-- experiments.jsonl, 23 records created 2026-10-15T12 -->)
and two more moved: T-266 supported to inconclusive (21 < min_n 25 signals) and T-256 not_supported to inconclusive
(18 < 25 entries, CI -13.0 to +43.3, not decisive); T-216 stayed supported with the FOMC/CPI exclusion (+8.01 bps, CI
+0.61 to +15.26) <!-- commit 53c54e0 -->. That is the "eight verdicts moved on re-run" in the changelog
<!-- MANDEL.md §7, 2026-10-15 entry -->. Every earlier verdict record stays in the log; the registry keeps the
superseded result ids next to the new one (T-350 carries four result ids <!-- registry T-350 results -->).

Three rule-5 rounds and a rule-10 audit followed the audit on the batch-4/5 modules before the official re-run
<!-- commits e5a6e8f, 0a6611c, 790dc0f -->. The first sweep (13:12 UTC) applied rule 5 to the batch-4/5 modules, so
that below min_n a decisive failure counts as not_supported instead of everything being capped at inconclusive
<!-- commit e5a6e8f --> <!-- MANDEL.md §2 rule 5 -->; it is what moved T-361 and T-324 off their recorded inconclusive
verdicts, since round 2 already reports T-361 as staying not_supported and rounds 2 and 3 report no changes relative
to their pinned bases, and both moves were recorded in the official re-run (X-a809c4fb, X-49cd0e78)
<!-- commit 0a6611c --> <!-- commit 790dc0f --> <!-- X-a809c4fb --> <!-- X-49cd0e78 -->. Round 2 (14:21 UTC) made
decisive tests at the pass's own one-sided confidence (T-341/T-342/T-361 mirror p, T-242 one-sided lower bound, the
carry claims' one-sided mirrors, T-427 PSR); on the real archive every harness at or above min_n was byte-identical
and T-361 stayed not_supported below min_n <!-- commit 0a6611c -->. Round 3 (15:58 UTC) plus the rule-10 audit of the
same modules produced no verdict changes on the real archive relative to their pinned base <!-- commit 790dc0f -->.

### 2.2 The twelve harness rules

The rules were written into MANDEL.md section 2 in two steps: ten on 2026-10-15 at 13:34 UTC <!-- commit 9811f8a -->
and rules 11 and 12 at 16:32 UTC after the batch-6b refutations <!-- commit 99278be -->. A harness that breaks one
is a defect, whatever its verdict <!-- MANDEL.md §2 -->. In brief:

| Rule | What it says | Where it came from |
|---|---|---|
| 1 | Test the claim exactly as worded: every horizon, asset, threshold and sub-period named in the claim or its trial's `pass` is a criterion; restating a claim is a new, superseding theory and the old verdict stands | audit |
| 2 | Unimplemented means not supported: any failing implemented criterion gives not_supported, any criterion that cannot be implemented caps the verdict at inconclusive, and supported needs every criterion implemented and passing | audit |
| 3 | min_n in the claim's own units (cycles, trades, events, months), never in whatever the code happens to count | audit |
| 4 | Point in time: a signal uses only data available at the decision; `available_at` is the earliest time a participant could know the value; forward windows start after the decision | audit |
| 5 | Below min_n only decisive failures count: never supported; a failing criterion counts only when its bound at the pass's own confidence lies wholly on the wrong side (or would persist at min_n); any other failure is inconclusive | audit |
| 6 | Intervals for the statistic actually claimed: studentized or percentile block bootstrap; differences bootstrapped paired on a shared timeline; blocks at least as long as any overlap; one- or two-sided as the pass states | audit |
| 7 | Rates and Sharpe: DTB3 is a discount yield (continuous rate -ln(1 - d·91/360)/(91/365)); funded strategies compare Sharpe ratios on excess returns; 252 trading days a year, 365 for crypto | audit |
| 8 | Options: settle on raw closes; price on the dividend forward when an ex-date falls inside the life; model-priced results are labelled MODEL-PRICED and report their sensitivity to the IV scale | audit |
| 9 | Costs as the claim states; data limits are inconclusive, never errors, and name exactly what is missing | audit |
| 10 | No arbitrary grid phase: a named entry or expiry calendar is used as named; otherwise the pooled all-start estimate (overlapping entries, blocks at least twice the hold) is the primary statistic and the per-start range is reported | two 'supported' previews, T-540 and T-154, failed this when checked |
| 11 | Alternatives must agree: when a trial names alternative procedures, a criterion passes only if every named construction passes; a borderline pass that flips under a permitted alternative is not evidence | the refutation of T-162 |
| 12 | One information set per decision: a gate, a strike choice and a price used at the same decision must all be known at the same time; when the archive stamps a value after the fill, read all of them at the previous close or all at the entry-day close as the live proxy, and if the two readings disagree the result is undecided | the refutation of T-220 |

<!-- rule texts and attributions: MANDEL.md §2 Harness rules 1-12 -->

What each of the three refutation-born rules did to the theory that produced it:

- **Rule 10.** The rule-10 audit of the earlier modules (structure claims on the standard monthly expiry calendar,
  overlays, cross-asset structures, options_market lockouts pooled over all starts; in underlying2 only
  crypto_weekly_v2 was grid-dependent) found no defect in the rule-10 logic under independent checkers; the
  commit's own expected changes on re-run were T-530 supported to not_supported and T-102 not_supported to
  inconclusive <!-- commit 1eaae35 -->. Both happened in the official re-run (below). Applied to the 43 batch-6a harnesses with
  checkers 52 of 53 ok, it moved the T-154 ZEBRA preview from supported to not_supported on the monthly expiry
  calendar (mean difference +0.076% of S, 95% CI -0.095% to +0.280%, 403 cycles, MODEL-PRICED with no costs
  <!-- X-54e06747 -->) while T-540 stayed supported on the pooled estimate: +8.12 %^2 per month, CI +1.43 to +11.22,
  17 of 21 single grids pass, worst cycle -630.8 entered 2020-02-26 with skew -7.6 and kurtosis 93
  <!-- commit 6ee1b48 --> <!-- registry T-540 notes -->. T-540 is a variance-unit restatement of the SPX variance
  premium, a descriptive premium with a tail the trial itself says is the point, not a strategy after costs.
  T-530's own note records why it lost support: pooled over all 2,693 contango days the forward-minus-realised
  variance is +0.0143 with both halves positive, but one-sided p 0.0465 and only 30 of the 63 single grid phases
  pass, so the earlier 'supported' had come from one grid phase <!-- registry T-530 notes --> <!-- X-e049bc5e -->.
- **Rule 11.** T-162 (BXMD vs BXM) passed the studentized HAC block bootstrap (Sharpe gap +0.113 annualised, CI
  +0.007 to +0.221) but failed the Ledoit-Wolf 2008 test the trial names as the alternative (two-sided p 0.078), so it
  is inconclusive; 161 of 294 BXMD months are Cboe back-test values from before its 2015-08-03 launch
  <!-- registry T-162 notes --> <!-- X-173afa14 -->. T-170 (PUT vs BXM) passed under both constructions and stayed
  supported <!-- commit 3ae4cd8 -->.
- **Rule 12.** T-220 (VIX settlement credit spread) had its VIX3M/VIX gate and strike choice read at one information
  set, at the previous close and at the entry close as the live proxy; both readings fail (mean return on max loss
  +0.87%, 95% CI -1.11% to +2.45%, and +0.59%, CI -2.15% to +2.04%; 110 gated trades at the previous close and 111 at
  the entry close, 2013-01-16 to 2026-09-16, MODEL-PRICED Black-76 at VVIX), and chain-calibrated pricing is negative
  in both, so it is not_supported
  <!-- registry T-220 notes --> <!-- X-1c908327 --> <!-- commit 3ae4cd8 -->.

### 2.3 The write / review / fix / refute workflow

Every batch this cycle went through the same shape. A writer agent produces a harness module and its tests in an
isolated new file that nothing imports, so no verdict depends on it while a skeptic reviews it
<!-- commit 3784c24 -->. A reviewer's finding counts when it is reproduced (the commits record "reviewer-reproduced
defects", never assertions); a fixer applies the reproduced findings; an independent checker diffs the fix against a
pinned base commit, which is what let several fix rounds run concurrently without reviewing each other's edits
<!-- commit c237062 --> <!-- commit dc496ff --> <!-- commit 0eca4be -->. The module then
produces preview verdicts, and every 'supported' preview goes to a separate refutation agent before anything is
recorded <!-- commit e1456e8 --> <!-- MANDEL.md §7, 2026-10-15 entry -->. Only after that is the module wired into
the runner, with `BATCH_BUNDLES` rebuilt from a fresh trace of every bundle each harness loads (137 batch harnesses
at the batch-6b wiring); a bundle a harness only probes is declared only when it is archived, so an absent optional
bundle never makes `run_all` skip a harness <!-- commit 20696ec -->. The official run then records the verdict.

What the reviewers and refuters caught, per batch, as the commit messages and registry notes record it:

| Batch | Harnesses | Reviewer-reproduced defects | Supported previews and what refutation did to them | Source |
|---|---|---|---|---|
| 4 and 5 (FOMC, factors, Deribit carry, OHLC, VX futures, macro days, FX, hourly) | 45 | reviewer fixes recorded, count not stated in the commit messages | 3 recorded supported at wiring (T-216 and T-224 MODEL-PRICED on the dividend forward, T-332); 3 inconclusive below min_n (T-361, T-329, T-324), 39 not_supported; the rule-5 round 2 and round 3 and the rule-10 audit changed nothing relative to their pinned bases (commits 0a6611c, 790dc0f), but the rule-5 sweep as a whole moved two of the three below-min_n inconclusives, T-361 and T-324, to not_supported as decisive failures, recorded in the official re-run (X-a809c4fb, X-49cd0e78) | <!-- commit 9381274 --> <!-- commit 0a6611c --> <!-- commit 790dc0f --> <!-- X-a809c4fb --> <!-- X-49cd0e78 --> |
| 6a (options library on archived data: var, dir, term, surf, xc) | 43 | 12, of which 3 verdict-changing | previews 10 supported, 4 inconclusive, 29 not_supported; after rule 10 and every refuter finding, 9 supported previews remained (T-154 fell); all 9 recorded supported in the official re-run | <!-- commit c237062 --> <!-- commit 6ee1b48 --> <!-- commit 5a1a5c8 --> |
| 6b first four groups (bw, hedge, chain, misc) | 33 | 11, of which 3 verdict-changing | previews 4 supported (T-162, T-170, T-168, T-220), 8 inconclusive, 21 not_supported; refutation moved T-162 to inconclusive (rule 11) and T-220 to not_supported (rule 12); T-170 and T-168 stayed | <!-- commit a0e8160 --> <!-- commit 3ae4cd8 --> |
| 6b vol-history (T-250) and DoltHub chains | 1 and 4 | not stated | preview not_supported for T-250 (pooled premium +0.011 to +0.014 against the claimed 0.05) | <!-- commit 669af52 --> <!-- experiments.jsonl b6b_dolt_* records --> |
| 6b Deribit group | 11 | 4, of which 1 verdict-changing | after the Deribit histories were fetched, two independent refuters reproduced two defects in T-262 (legs priced on spot instead of each expiry's forward; an equal-weight mean over 110 overlapping signal days instead of the trial's non-overlapping walks): fixed, 0 of 16 start offsets pass, not_supported. T-268's 'supported' preview was refuted to inconclusive (the pass's 'target > 2 vol points' splits 3/3 across trade-time tolerances) | <!-- commit 177a434 --> <!-- commit a1bb713 --> <!-- commit e406249 --> |
| 6c on archived data (calendar, momentum/trend, misc) | 18 | 9 | no supported preview refuted; T-345, T-349, T-357 recorded supported (T-349 noted fragile at p 0.0476) | <!-- commit 6e09d78 --> |
| 6c on fetched Yahoo/FRED/ALFRED data (xs, pairs, rates, macro) | 25 | 10, of which 1 verdict-at-risk | no supported preview, so no refutation round; all 25 not_supported | <!-- commit 9399224 --> |
| 6c public sources | 4 | not stated | none supported; T-405 and T-404 parked under their own rules | <!-- commit 51920df --> |
| 6c stock events | 3 | not stated | none supported; T-334 and T-394 inconclusive for survivorship | <!-- commit 953d219 --> |
| 6c stocks and crypto | 16 | 3 verdict-at-risk and 1 verdict-changing (T-367) reported; the full count is not stated | T-366 survived refutation under every lag, price field, sampling day and estimator, and is recorded as a descriptive drift, not a trading edge | <!-- commit 55ad6df --> <!-- registry T-366 notes --> |
| 6c prediction markets | 14 | 2 verdict-changing (T-12 population, T-336 pair audit) and 1 verdict-at-risk reported | none supported; T-337 passes every implemented criterion and is capped by a missing control (below) | <!-- commit 3cd7b4f --> |

Where a count is stated, reviewers reproduced 46 defects across the 6a, 6b and 6c-archived and 6c-fetched batches
(12 + 11 + 4 + 9 + 10) <!-- sum of the stated rows above -->; the batches that report only verdict-relevant counts
add 7 more (4 + 3) <!-- commit 55ad6df --> <!-- commit 3cd7b4f -->. Four 'supported' previews did not survive
checking: T-154 (rule 10), T-162 (rule 11), T-220 (rule 12), T-268 (refuter on the fetched Deribit history); T-262's
first preview was refuted before recording for two reproduced defects, and no source states what its preview verdict
had been <!-- commits 6ee1b48, 3ae4cd8, e406249, a1bb713 --> <!-- registry T-262 notes -->; the rule-10 audit of the
older code separately moved
two recorded verdicts, T-530 out of support and T-102 to inconclusive <!-- commit 1eaae35 -->. By the close, 217
batch harnesses are wired <!-- commit 3cd7b4f -->, of which 80 are batch-6c records in the log
<!-- experiments.jsonl, harness prefix b6c_ -->.

### 2.4 Pre-registered park rules, pre-registrations, blocks and unblocks

A theory is parked only under a rule its own trial wrote before the data was seen. Seven were parked this cycle
<!-- ledger, 7 theory.parked events since 2026-10-15 -->, each with its reason in the ledger and its pre-park status
kept in the registry:

| Theory | Park rule (the trial's own) | The numbers that triggered it | Status before park | Ledger |
|---|---|---|---|---|
| T-324 SPY/IVV twin reversion | reversion real but below retail cost | AR(1) half-life 11.3 days; mean gross +0.17 bp per trade against 8 bp round trip; net -7.83 bp (CI -9.14 to -6.58), 175 trades 2010-2026 | not_supported | <!-- ledger seq 2473 --> <!-- registry T-324 status_before_park --> |
| T-389 contrarian factor timing | adds nothing beyond static exposure | 60-month z tilt minus static Sharpe -0.03 (CI -0.11 to +0.04) pooled over the 3 quarterly phases, 704 months 1968-2026 | not_supported | <!-- ledger seq 2474 --> <!-- registry T-389 status_before_park --> |
| T-445 accruals anomaly | arbitraged away | post-publication Lo20-Hi20 +0.17%/month (CI -0.10 to +0.42), FF5 alpha t 1.21, 362 months 1996-07 to 2026-08, against +0.38%/month before 1996-07 | not_supported | <!-- ledger seq 2475 --> <!-- registry T-445 status_before_park --> |
| T-469 BTC short-term reversal | no tradable daily reversal | conditional minus unconditional next-day excess +11.3 bp (CI -23.6 to +47.2) against the 60 bp bar, 422 signals | not_supported | <!-- ledger seq 2476 --> <!-- registry T-469 status_before_park --> |
| T-405 gold COT extremes | insufficient extremes | 872 point-in-time COT weeks 2009-10 to 2026-09 give 20 weeks with z > 2 against 50 needed, at most 16 more fit in the window; difference +0.04% (CI -2.90 to +2.70) | not_supported | <!-- ledger seq 5905 --> <!-- registry T-405 status_before_park --> |
| T-404 GLD flows vs price | flows follow price | next-week GLD return on the 52-week z of the 4-week tonnes change NW t -0.10 over 1,087 weeks; contemporaneous slope t +5.07; Granger returns to flows p < 0.0001, flows to returns p 0.99 | not_supported | <!-- ledger seq 5906 --> <!-- registry T-404 status_before_park --> |
| T-328 IBIT premium fade | premium within AP cost band | 25 fades at abs(z) > 2, 2024-04 to 2026-09, gross +0.185% per trade against the 0.85% round trip, net -0.665% (one-sided lower bound -0.69%) | not_supported | <!-- ledger seq 6209 --> <!-- registry T-328 status_before_park --> |

The first four were parked at 18:47 UTC on 2026-10-15, after the last re-run record (18:43:28) and inside the re-run
commit 5a1a5c8 (18:49 UTC) <!-- ledger seq 2473-2476 ts --> <!-- experiments.jsonl window end --> <!-- commit 5a1a5c8 -->;
T-405 and T-404 on 2026-10-16 <!-- ledger seq 5905-5906 ts --> and T-328 on 2026-10-19 <!-- ledger seq 6209 ts -->.
Parking does not touch the verdict: each keeps its not_supported result and its experiment ids.

Two forward tests were pre-registered through `theory.preregistered` events rather than recorded as results
<!-- ledger, 2 theory.preregistered events since 2026-10-15 -->. T-542 restates T-505 (SPX put-call parity) without
the day-one gate that had let one noisy day decide the claim, with 2 of the 20 SPX capture days it needs known at
registration <!-- ledger seq 1785 --> <!-- registry T-542 notes and blocked_on -->. T-543 is the forward-only test
of T-221's in-sample pooled FOMC+CPI result (-51.7 bps, 95% CI -95.8 to -9.9 over 109 event days), counting only
event days after 2026-10-15 with 0 of 30 known; the in-sample number is evidence for registering it, not for
supporting it <!-- ledger seq 2132 --> <!-- commit 53c54e0 --> <!-- registry T-221 notes --> <!-- registry T-543 notes and blocked_on -->.

Four underlying claims were moved from untested to blocked with ledgered reasons after the batch-6c triage and its
adversarial recheck found no free source with delisted names and a point-in-time universe (T-391, T-392, T-395,
T-452) <!-- ledger seq 2510-2513 --> <!-- commit 8244604 -->. Seventeen theories moved the other way, each
`theory.unblocked` event naming the bundles that unblocked it <!-- ledger, 17 theory.unblocked events since 2026-10-15 -->:
4 at the batch-4/5 wiring (T-160, T-242, T-343, T-224) <!-- ledger seq 1946-1949 -->, 2 at batch 6a (T-538, T-137)
<!-- ledger seq 2133-2134 --> and 11 at batch 6b (T-202, T-220, T-188, T-518, T-119, T-121, T-173, T-539, T-250,
T-222, T-260) <!-- ledger seq 2199-2209 -->.

### 2.5 The official re-run of all harnesses

After batch 6b was wired, every harness then in the runner was re-run on the current code under rules 1 to 12: 262
harnesses, 180 not_supported, 46 supported, 36 inconclusive, 0 errors <!-- commit 5a1a5c8 -->. The 262 records sit
in the log between 18:23:59 and 18:43:28 UTC on 2026-10-15, one per harness
<!-- experiments.jsonl, 262 records with distinct harness names in that window -->, and the verdict counts in the
log match the commit <!-- experiments.jsonl window counts: 180 / 46 / 36 -->. The commit records 95 status changes
<!-- commit 5a1a5c8 -->. Reconstructed from the log, 96 of the 262 records differ from the previous record of the
same harness: 92 are first verdicts for the newly wired batch-6a (43) and batch-6b (49) harnesses and 4 are changed
verdicts on harnesses recorded before <!-- experiments.jsonl, prior-record comparison per harness -->; the
one-record gap between 95 and 96 is not resolvable from these files and is left as stated in the commit.

The four changed verdicts:

| Record | Harness | Theory | Change | Why |
|---|---|---|---|---|
| X-e049bc5e | conditional_forward_v2 | T-530 | supported to not_supported | rule 10: pooled p 0.0465 one-sided, 30 of 63 grid phases pass <!-- X-e049bc5e --> |
| X-0c1fb82f | structure_t_102 | T-102 | not_supported to inconclusive | pooled smile-scaled mean -45.7% (CI -59.8 to -13.9) passes, but the trial's SKEW-scaled sensitivity is not implemented (rule 2) <!-- X-0c1fb82f --> |
| X-a809c4fb | fomc_monetary_momentum | T-361 | inconclusive to not_supported | 85 expansionary-plus-contractionary meetings of 261 classified, below min_n 120; one criterion fails decisively (long-only arm Sharpe 0.05 vs buy-and-hold 0.52), so rule 5 gives not_supported; the net gap +0.64 pp (CI -1.34 to +2.74) fails but not decisively <!-- X-a809c4fb --> |
| X-49cd0e78 | ohlc_spy_ivv_twin | T-324 | inconclusive to not_supported (then parked) | 175 trades, net -7.83 bps after 8 bps round trip (CI -9.14 to -6.58) <!-- X-49cd0e78 --> |

The eleven newly supported claims, each of which had survived an independent refutation first
<!-- commit 5a1a5c8 -->, with what each is and is not:

| Record | Theory | What is supported | What it is not |
|---|---|---|---|
| X-78f814bf | T-123 gamma-scalped long straddle | MODEL-PRICED at 0.90 x VIX (the claim's scale), delta-hedged daily, 1 bp per share, 403 cycles pooled over 21 offsets; mean -1.98 vol pts per vega, CI -2.46 to -1.37; at 0.81 x VIX the CI includes zero (mean -0.20, CI -0.70 to +0.52, 0 of 21 offsets pass) and the sign flips at 0.80 x VIX <!-- X-78f814bf --> <!-- registry T-123 claim and trial pass --> | a market-priced result; the supported sign depends on the IV scale, which is a model input |
| X-a774b108 | T-234 variance strip win rate | model-free: VIX^2 exceeded next-month realised variance in 370 of 441 months, 0.839 (Clopper-Pearson 0.801 to 0.872) <!-- X-a774b108 --> | a P&L; a frequency of the premium being positive |
| X-a7f44bf6 | T-540 variance swap in variance units | pooled mean +8.12 %^2/month, CI +1.43 to +11.22; worst cycle -630.8 <!-- X-a7f44bf6 --> | a strategy after costs; the premium's tail is the point |
| X-f5e50a1d | T-113 jade lizard | MODEL-PRICED at flat VIX, no transaction costs (none stated), 313 cycles <!-- X-f5e50a1d --> | priced on a chain or net of costs |
| X-5cce8455 | T-135 1-3-2 call tree | MODEL-PRICED at flat VIX, no transaction costs, 403 cycles <!-- X-5cce8455 --> | priced on a chain or net of costs |
| X-b2c26a56 | T-516 digital put | MODEL-PRICED N(-d2) at flat VIX, no transaction costs, 403 cycles <!-- X-b2c26a56 --> | priced on a chain or net of costs |
| X-8c2b7bf1 | T-152 calendarised butterfly | MODEL-PRICED, half-spreads from 11,885 SPY quotes on two capture days, n 23 <!-- X-8c2b7bf1 --> | a long sample: 23 cycles |
| X-1c42240d | T-228 SKEW-implied tail gap | SKEW-implied P(21-day < -2 VIX-sigma) averages 8.54% vs realised 1.05%, 441 holds pooled over 21 offsets <!-- X-1c42240d --> | a trade or a tail predictor: SKEW carries no information about realised tails (frequency 0.79% with SKEW > 135 vs 1.10% otherwise, placebo p 0.61) <!-- registry T-228 notes --> |
| X-b56d12eb | T-255 BTC delta-hedged short straddle | MODEL-PRICED at DVOL, 66 cycles; mean +9.5% of premium (CI +5.2 to +13.5), after-fee Sharpe 0.71 at the measured ATM/DVOL scale 0.945 from 2 book captures; the refuter's trade-IV haircut gave +8.1%, Sharpe 0.97 <!-- registry T-255 notes --> | a traded-price result; the trial's own per-cycle haircut still runs |
| X-66d68491 | T-170 PUT vs BXM | a comparison of published Cboe index histories, 236 months, 5 of which are back-tested values before PUT's 2007-06-20 launch <!-- X-66d68491 --> | a live strategy, and it does not generalise to the other put-write arms (PUTY-BXM +0.005, CI -0.117 to +0.138; WPUT-BXM -0.121) <!-- registry T-170 notes --> |
| X-47e71844 | T-168 CLLZ vs SPY | the claim as worded is that CLLZ has *no higher* Sharpe than SPY <!-- registry T-168 claim -->: monthly Sharpe 0.1389 vs 0.1748 over 405 months 1993-02 to 2026-10, difference -0.0359 (CI -0.0639 to -0.0128), meeting the pass's upper bound of 0.05 <!-- X-47e71844 --> <!-- registry T-168 trial pass --> | evidence for the collar; it is a negative result recorded as supported, and 67% of the window is Cboe's back-test before CLLZ's 2015-08-03 launch <!-- registry T-168 notes --> |

The 92 first verdicts, by module, so that each X id is on the record:

| Group | Records (theory, verdict, X id) |
|---|---|
| 6a var | T-101 inconclusive X-5be89eeb; T-123 supported X-78f814bf; T-156 not_supported X-daad6f05; T-157 not_supported X-dad7f2ce; T-233 not_supported X-b734534f; T-234 supported X-a774b108; T-235 not_supported X-a54d5155; T-540 supported X-a7f44bf6; T-529 not_supported X-f1fa28ba |
| 6a dir | T-113 supported X-f5e50a1d; T-133 not_supported X-78d24028; T-135 supported X-5cce8455; T-136 inconclusive X-d77c443f; T-138 not_supported X-93c696cc; T-139 not_supported X-57623c6d; T-140 not_supported X-cbfc46bf; T-154 not_supported X-54e06747; T-516 supported X-b2c26a56 |
| 6a term | T-143 X-10a49f0d, T-144 X-87edcdcc, T-145 X-58e4c1d3, T-146 X-3c150160, T-147 X-63ef8ec5, T-149 X-396ecf5b, T-150 X-0716df12, T-151 X-24b761f5, T-155 X-3e10c60c all not_supported; T-152 supported X-8c2b7bf1 |
| 6a surf | T-159 X-bd91ae4f, T-227 X-e2bef5fd, T-229 X-445e5d1a, T-237 X-f61b21fd, T-239 X-f49a2a7a, T-240 X-7f1908d5, T-249 X-6ae5939f, T-511 X-f680a617 all not_supported; T-228 supported X-1c42240d; T-538 inconclusive X-66a6cce7 |
| 6a xc | T-255 supported X-b56d12eb; T-261 not_supported X-51c9d9c3; T-194 inconclusive X-471ee9f1; T-199 not_supported X-6f856e67; T-137 not_supported X-16ddfa68 |
| 6b bw | T-128 X-3d662f03, T-161 X-f5ad4c58, T-163 X-1f452751, T-171 X-9c038379, T-172 X-b1cbc563, T-174 X-3e616bfc, T-202 X-b6a74212, T-527 X-2e704524 all not_supported; T-162 inconclusive X-173afa14; T-164 inconclusive X-df13fe5c; T-170 supported X-66d68491 |
| 6b hedge | T-166 X-7d7b4e5d, T-169 X-80fa69b3, T-179 X-30b8aabf, T-180 X-63ffe887, T-528 X-c362849a, T-220 X-1c908327 all not_supported; T-168 supported X-47e71844; T-178 inconclusive X-7459c2a7 |
| 6b chain | T-153 X-fc398775, T-184 X-0cbfdd19, T-185 X-e4010567, T-507 X-7d886959, T-103 X-e3bda8ef all not_supported; T-182 X-ac71dd4f, T-191 X-f64267bb, T-500 X-6568b066, T-501 X-a6b081cf, T-508 X-133cc150 all inconclusive |
| 6b misc | T-188 not_supported X-221aebb6; T-518 inconclusive X-da58485b; T-522 not_supported X-e726de11; T-275 not_supported X-9856d560 |
| 6b dolt and volh | T-119 not_supported X-0b00e203; T-121 not_supported X-cd21ab67; T-173 inconclusive X-70e4d9b6; T-539 not_supported X-e6e164dc; T-250 not_supported X-931dd4dd |
| 6b drb | T-222 inconclusive X-2e4eac10; T-197 not_supported X-047acafb; T-223 not_supported X-3c1a0a3e; T-263 inconclusive X-dbb078ec; T-268 inconclusive X-4dad8586; T-269 not_supported X-c595e83c; T-195 X-7163e0a9, T-196 X-1830d794, T-260 X-f43acb93, T-257 X-8587bd48, T-262 X-ce9af676 all inconclusive |

<!-- all rows: experiments.jsonl, records created 2026-10-15T18:23:59 to 18:43:28 with no earlier record for the harness -->

Four of the Deribit-group records above were placeholders: the harnesses existed but their history bundles did not,
so they reported inconclusive under rule 9 until the fetch landed the same evening, when T-263 and T-262 were
recorded not_supported and T-268 and T-257 inconclusive <!-- commit e406249 -->. Batch 6c was never part of this
re-run; its 80 records were produced group by group from 2026-10-15 20:00 UTC onward as the data landed
<!-- experiments.jsonl, b6c_ records on 2026-10-15T20, 2026-10-16 and 2026-10-19 -->.

### 2.6 Archive hardening

Three things changed in how bundles are written and checked, two of them because the cycle's concurrent fetch chains
found the holes.

**Atomic bundle writes.** `Archive.store` now writes each bundle whole to a `.partial` file and renames it into place
under the index lock, so a kill mid-write leaves the stored bundle intact and a reader may stream from it meanwhile
<!-- mandel/archive.py store(), .partial then os.replace under file_lock -->; the INDEX itself is rewritten through a
temp file, fsync and rename <!-- mandel/_io.py atomic_write_text --> <!-- mandel/archive.py docstring: "the index, which is rewritten atomically" -->.
This came out of the independent check of the Deribit history fetchers, which also made SIGTERM store complete
windows the way Ctrl-C already did and had the T-257/T-262 harness stream the roughly 3M-row daily trade bundle
instead of materialising it <!-- commit 5a1a5c8 -->.

**The stale-INDEX bug.** Fetcher checkers reproduced that `Archive._reload_index` used `setdefault`, so a process
holding a stale in-memory entry wrote it back over another process's newer entry, leaving INDEX.json pointing at the
wrong sha256 and row count. The disk copy now wins for every name it holds, with a regression test that runs two
`Archive` objects on one root <!-- commit 1892f6c --> <!-- mandel/archive.py _reload_index docstring -->. The
cross-module run lock that `public_history` had used as a workaround was then narrowed to its own module's runs
<!-- commit a1325f7 -->.

**The repair.** The bug had already done damage before the fix. After a container restart, a full size check found 25
bundles (the Cboe VIX family, FRED DTB3/DGS2/DGS10/DFF, the Deribit DVOL histories) whose files were the 2026-10-15
07:17 refresh while their INDEX entries were the 2026-10-14 versions <!-- commit a166657 -->. Each file's sha256
matched its latest `archive.stored` event, so the entries were restored from those events, and each restoration is an
`archive.index.repaired` ledger event recording old and new <!-- commit a166657 --> <!-- ledger, 25 archive.index.repaired events, seq 6136-6160, 2026-10-19T16:10:44 -->.
For cboe-VIX-history, for instance, the entry went from 9,293 rows, 189,499 bytes, created 2026-10-14T11:10 to 9,294
rows, 189,517 bytes, created 2026-10-15T07:18 <!-- ledger seq 6136 payload -->. No recorded verdict changed:
harnesses read the files, not the INDEX, and the stale `created_at` only hid one extra day behind the point-in-time
capture filter <!-- commit a166657 -->.

**Verify now checks sizes.** `Archive.index_mismatches()` lists every bundle on this machine whose file size differs
from its INDEX entry (bundles not on this machine are skipped), and `mandel verify` prints each mismatch as
"INDEX says N bytes, file has M" and returns non-zero if any exist, alongside the ledger hash-chain check and the
proposal, insight and forecast reconciliation <!-- mandel/archive.py index_mismatches --> <!-- mandel/cli.py cmd_verify -->.
A full content check (`Archive.verify`) remains the sha256 recomputation per bundle. The post-restart checkpoint on
2026-10-16 had already used the size check by hand: ledger verifies, the 400 most recent bundles exist with their
INDEX sizes <!-- commit b932407 -->.

**What the archive holds at the close.** Read at 2026-10-19 20:15 UTC, with the Kraken 1-minute fetch still adding
monthly bundles (its latest, kraken-trades-1m-XBTUSD-2023-10, was stored at 20:08 <!-- ledger seq 6235 -->): 3,471
bundles, 51,134,655 rows, 1,869,193,456 bytes; 155 in git and 3,316 local-only <!-- INDEX count, rows, bytes, in_git at 2026-10-19T20:15Z -->.
The ledger holds 3,857 `archive.stored` events since 2026-10-15 at that same 20:15 UTC read (the count keeps rising
with the Kraken fetch, so the lead re-reads it once at the final close) <!-- ledger kinds since 2026-10-15, read 2026-10-19T20:15Z -->. The in-git
rule is set per source in the fetcher docstrings: in git for FRED/ALFRED series that are public domain from a US
federal agency (the decision is read from the series page at fetch time; Michigan's UMCSENT, Moody's BAA10Y via the
St. Louis Fed, the OECD rates and USREC are local-only), the DoltHub chains and vol history (CC BY-SA 4.0, attribution
in the recipe), the CFTC COT reports, Treasury auctions and the SEC ticker map (public domain), the Wikipedia S&P 500
tables (CC BY-SA 4.0, attribution and revision in the recipe) and the OPEC announcement dates (Känzig, CC BY 4.0);
local disk only for Cboe strategy indices (Cboe's website terms), Coinbase, Kraken, CoinMarketCap, blockchain.com,
DefiLlama, BlackRock's iShares and Coin Metrics community data (CC BY-NC 4.0), Deribit (no stated data licence),
Binance (terms grant no redistribution right), Polymarket and Kalshi, box rates (CC BY-NC-ND 4.0), the Cleveland Fed
nowcasts (a Reserve Bank, not a federal agency), the fja05680 membership list, and the StockTwits, FINRA and Sprott
sources
<!-- mandel/data/market_history.py, dolt_options.py, public_history.py items 1, 2, 3, 7, 8, 11, options_misc.py items 1 and 2, cboe_strategy.py, crypto_history.py, deribit_history.py, binance_klines.py, pm_history.py docstrings --> <!-- commits 0e4bd29, bb793fd -->.
A test asserts that every `in_git=False` bundle is git-ignored <!-- commit 0e4bd29 -->.

### 2.7 Still running at the close

Seven claims have harnesses written but no verdict yet, because their data is still being fetched or one control
is missing. Their lines will be filled by the lead:

- T-331 cross-exchange crypto gap reversion, T-425 cross-exchange BTC price discovery, T-465 VPIN and crypto
  volatility, T-459 crypto trade-flow imbalance: untested, awaiting the Kraken 1-minute trades
  <!-- registry T-331, T-425, T-465, T-459 status --> [[PENDING]]
- T-414 StockTwits bullish ratio, T-415 social message volume and next-day realised volatility: untested, awaiting
  the StockTwits capture <!-- registry T-414, T-415 status --> [[PENDING]]
- T-337 Polymarket vs Deribit digital: inconclusive with every implemented criterion passing (+4.7 cents per contract
  after the 0.07 p(1-p) fee each way, 4,987 trades, one-sided lower +4.2, DSR 1.0 at 7 variants), capped by the
  resolution-source basis control, which needed Binance BTCUSDT klines not archived at the time (rule 9)
  <!-- X-6aab305c --> <!-- registry T-337 notes -->; the klines are now stored (686 resolution windows, 83,692 rows,
  local only <!-- commit ebfea1c --> <!-- ledger seq 6242 --> <!-- INDEX binance-1m-BTCUSDT-btc-above -->), the
  control reads them and T-337's bundle declaration was re-traced <!-- commit 053fb3c -->, and the re-run and its
  refutation were running at the close <!-- commit 2defba3 -->, with X-6aab305c still the only T-337 record
  <!-- experiments.jsonl, T-337 records --> [[PENDING]]

## Options claims: batches 6a and 6b

Two batches took the options library from "written" to "tested" this cycle. Batch 6a is 43 harnesses on data the
archive held before any batch-6b fetch: the VIX family, SPY and ^GSPC closes, DVOL, and the two captured chain
days. <!-- git c237062, e1456e8; experiments.jsonl b6_* harness count --> Batch 6b is 49 harnesses on data fetched for
the purpose on 2026-10-15: 59 Cboe strategy benchmark indices (344,475 daily rows, every bundle local-only under Cboe's
website terms, 55 of them carrying back-tested history before launch), <!-- INDEX count of bundles tagged strategy-index;
git 0e4bd29; data/cboe_strategy.py docstring --> the DoltHub end-of-day SPY option chain (184,226 quotes, 2019-02-09 to
2026-10-14, in git under CC BY-SA 4.0) and its volatility history for SPY and the nine sector SPDRs (12,884 rows),
<!-- INDEX dolt-chain-SPY, dolt-volhistory; git 4bea20a, 9a2f7c0 --> the van Binsbergen-Diamond-Grotteria SPX box rates
(3,548 trading days, 2004-01-02 to 2018-03-19, a research series deposited 2021-11-23, local-only under CC BY-NC-ND),
<!-- INDEX box-rates-bdg; data/options_misc.py docstring --> Kanzig's OPEC announcement dates (338 rows, 169 dates
1983-07-19 to 2025-12-01, in git under CC BY 4.0), <!-- INDEX opec-announcements; data/options_misc.py docstring --> and
four Deribit trade tapes from history.deribit.com, all local-only because Deribit states no data licence: 488,998 rows
of BTC and ETH option trades around 21 catalyst windows (488,977 trades plus the 21 window rows), 82,473 rows from the
24 hours before 38 FOMC decisions, 3,716 rows of BTCDVOL futures trades and settlements for 42 expired futures, and
2,465,638 rows of BTC option trades from the 07:00-09:00 UTC window of 1,779 days (2021-12 to 2026-10). <!-- INDEX deribit-option-trades-catalysts, deribit-option-trades-fomc,
deribit-dvol-futures-trades, deribit-option-trades-daily-BTC; git df7e586, 92e7fa5; data/deribit_history.py docstring -->
One declared source did not arrive: the Tardis first-of-month Deribit book feed for T-260 answered HTTP 429 (a shared
per-IP transfer budget) from this host, so the keyless fetcher stops and must be run from a host with its own IP.
<!-- data/options_misc.py docstring section 4 -->

The 92 theories the two batches touch are all options-strategy entries. Before the cycle 79 were untested and 13 were
blocked; after it 11 are supported, 61 not supported and 20 inconclusive. <!-- registry.json status diff against
f889527, the last cycle-3 commit; 92 = 43 + 49 unique theory_ids in experiments.jsonl --> The 13 that were blocked
(T-119, T-121, T-137, T-173, T-188, T-202, T-220, T-222, T-250, T-260, T-518, T-538, T-539) were unblocked by ledgered
`theory.unblocked` events when their harness was wired, two at 13:12 UTC with batch 6a and eleven at 18:13 UTC with
batch 6b. <!-- ledger.jsonl seq 2133-2134, 2199-2209 --> Across the whole options library (228 theories) the cycle moved
147 statuses: 92 through these two batches and 55 through other harnesses (the structure claims, the DVOL/GVZ/OVX/VXTLT
claims, the VX-futures claims, the audit re-run), which belong to their own sections; two pre-registered entries (T-542,
T-543) were added as blocked, with no harness and no experiment; the library now has 32 supported, 108 not supported,
30 inconclusive and 58 blocked, and no untested entry. <!-- registry.json kind=options-strategy, status diff against
f889527: 147 changed + 2 new = 149 entries differ -->

Three caveats apply to the whole table and are repeated per row only where they decide the verdict.

- **MODEL-PRICED.** 45 of the 92 records price their legs by Black-Scholes or Black-76 at the IV proxy the claim names
  (VIX/100, VIX3M, DVOL, OVX, VVIX for the Black-76 VIX structures, a trailing realised vol, IVs fitted to Deribit trade
  prints, or a smile scaled from the captured SPY chain), never on a traded option quote history, and say so in the
  reason as harness rule 8 requires. <!-- experiments.jsonl, count of latest b6_/b6b_ records whose reason carries
  MODEL-PRICED; X-1c908327, X-f49a2a7a (Black-76 at VVIX); X-f3e5922c, X-550ca26f (trade-fitted IVs); X-e3bda8ef (captured
  smile); MANDEL.md section 2 rule 8 --> The archive holds two captured chain days (quote days 2026-10-13 and 2026-10-14), enough to calibrate
  costs and one-day sensitivities, not a traded test. <!-- batch6b_chain.py docstring --> The level matters: the captured
  SPY ATM IV / VIX ratio was about 0.81 on 2026-10-14, the SPX ratio about 0.79 (0.785 on the 30-DTE SPXW), and the
  measured 30-day ATM IV / DVOL ratio 0.945 on two Deribit book captures. <!-- batch6_dir.py and batch6b_bw.py
  docstrings; X-445e5d1a; X-b56d12eb --> Most model-priced reasons report an IV-scale sensitivity (29 of the 45 at both
  0.81 and 0.90, batch 6a's SPY structures among them; others at x0.9/x1.1 or x0.8/x1.2; T-255 at 0.85 to 1.00); a scale
  is a criterion only where the trial names it (T-128 at 0.90, T-233 at 0.81), otherwise the verdict is for the claim's
  own proxy. <!-- experiments.jsonl b6_/b6b_ reasons, scale survey of the 45 MODEL-PRICED records; X-3d662f03;
  X-b734534f; X-b56d12eb; batch6_dir.py and batch6b_bw.py docstrings -->
- **Back-tested index values.** 14 records compare published Cboe index histories, and every index launched after
  the start of its claim's window: BXM (2002-04-30) by one month, PUT (2007-06-20) by five, CLL (2008-09-30) by about
  one (0.1 of an 18.1-year window), the rest by years (BXY 2006-03-20, VXTH 2011-07-29, CLLZ, PPUT, BFLY, CNDR, BXMD,
  BXMW and CMBO on 2015-08-03, BXMH 2020-09-08, PPUT3M 2021-08-02). <!-- experiments.jsonl count of b6b records mentioning
  back-tested values; batch6b_hedge.py docstring; X-f5ad4c58; X-66d68491; X-7d7b4e5d; X-df13fe5c; X-1f452751; X-b1cbc563 -->
  Rows before launch are Cboe's back-test, published at launch after the design was chosen. The claims describe the
  published histories, so the harnesses use those rows: the five bw Sharpe comparisons (T-162, T-163, T-164, T-170,
  T-172) label the verdict BACK-TESTED INDEX VALUES with the count, the other nine state the back-tested count or share of
  the window, and twelve of the fourteen report the post-launch months beside it (T-161 and T-180, whose back-tested rows
  are one BXM month and 2% of the PUT window, do not). <!-- batch6b_bw.py and batch6b_hedge.py docstrings; experiments.jsonl,
  the 14 latest b6b records mentioning back-tested values; X-f5ad4c58; X-63ffe887 -->
- **Grid phase, alternatives, information sets.** Rules 10, 11 and 12 were applied or written during these batches
  (rule 10 after batch 6a was wired at 13:12 UTC and before the official run, applied to all 43 harnesses at 15:42 UTC;
  rules 11 and 12 at 16:32 UTC after the refutations of T-162 and T-220, before batch 6b was wired at 18:14 UTC), so every
  verdict below is on the pooled all-start estimate or the claim's own calendar, passes only when every named construction
  passes, and reads a gate, a strike and a price from one information set. <!-- MANDEL.md section 2 rules 10-12; git
  e1456e8 (13:12:47), 1eaae35 (15:39:46), 6ee1b48 (15:42:58), 99278be (16:32:43), 20696ec (18:14:25) -->

Every "supported" preview went through an independent refutation attempt before it was recorded; the official re-run
of all 262 harnesses on 2026-10-15 (records 18:23-18:43 UTC, committed as 5a1a5c8 at 18:49 UTC) recorded the verdicts,
the 92 batch-6 records among them being written 18:30-18:35 UTC, and the four Deribit-history claims were re-run at
20:21-20:22 UTC after their tapes landed. <!-- git c237062, a0e8160, 5a1a5c8, d7cf03c (123/262 at 18:28);
experiments.jsonl created_at -->
Eleven of the 92 are supported: T-113, T-123, T-135, T-152, T-228, T-234, T-255, T-516 and T-540 from batch 6a, T-168
and T-170 from batch 6b. <!-- git 5a1a5c8; experiments.jsonl --> None of the eleven is a profitability claim after costs
on traded prices; what each one does and does not say follows the table.

### Every options-strategy theory batches 6a and 6b moved

Status before and after is the registry diff against the last cycle-3 commit; the deciding number and the caveat are
from the recorded experiment named in each row. <!-- registry.json status diff against f889527; experiments.jsonl -->

**Batch 6a, variance and short premium (`batch6_var`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-101 short straddle, VIX−RV21 tercile | untested → inconclusive | top-minus-bottom tercile +10.8 pts of premium at s = 0.90 (CI +2.6 to +20.7) over 342 out-of-sample cycles against min_n 390 | MODEL-PRICED; 8 of 21 grid offsets pass alone; the 48 missing cycles need SPY history before 1993-01-29 <!-- X-5be89eeb --> |
| T-123 gamma-scalped long straddle | untested → supported | hedged P&L −1.98 vol pts per unit vega at s = 0.90 (CI −2.46 to −1.37), 21 of 21 offsets | MODEL-PRICED; at s = 0.81 the mean is −0.20 (CI −0.70 to +0.52) and the sign flips at s = 0.800 <!-- X-78f814bf --> |
| T-156 45-DTE strangle, exit at 21 DTE | untested → not_supported | 21-DTE exit minus hold +0.094 bp of spot per day (CI −0.216 to +0.566); both halves fail | MODEL-PRICED; 403 monthly entries <!-- X-daad6f05 --> |
| T-157 weekly theta ladder | untested → not_supported | drawdown ratio ladder / single 1.245 (CI 0.51 to 2.14) against < 0.85 | MODEL-PRICED; 1,753 weekly rungs vs 403 monthly entries <!-- X-dad7f2ce --> |
| T-233 hedged short straddle at 0.81 × VIX | untested → not_supported | −3.60% of premium (CI −7.17 to −0.31) at s = 0.81; −5.12% at the measured 0.799; +16.6% at s = 1.00 | MODEL-PRICED; the sign is the IV scale <!-- X-b734534f --> |
| T-234 VIX² above realised variance | untested → supported | 370 of 441 months = 0.839 (Clopper-Pearson 0.801 to 0.872); thirds 0.878 / 0.823 / 0.816 | model-free; reading applied is the point win rate per third, the stricter every-third-lower-bound reading does not hold (0.744 in the last third) <!-- X-a774b108 --> |
| T-235 z-scaled short variance | untested → not_supported | Sharpe scaled 0.78 vs constant 0.64, difference +0.041, one-sided p 0.292, PBO 0.343 | model-free; 429 months <!-- X-a54d5155 --> |
| T-540 short variance in variance units | untested → supported | +8.12 %²/month (CI +1.43 to +11.22), 17 of 21 offsets; worst cycle −630.8 entered 2020-02-26, skew −7.60, kurtosis 93.0 | model-free; the preview failed rule 10 and the pooled estimate survived <!-- X-a7f44bf6; MANDEL.md rule 10 --> |
| T-529 VIX1D next-day premium | untested → not_supported | (VIX1D/100)²/365 minus next-day r² = −0.2241 %² per day (CI −0.4693 to −0.1012) over 1,107 days | model-free; the /252 convention gives +0.1557 <!-- X-f1fa28ba --> |

**Batch 6a, directional and ratio structures on SPY (`batch6_dir`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-113 jade lizard | untested → supported | mean P&L / (0.2 S) +2.740% (CI +1.753 to +3.615) over 313 entered months, 21 of 21 offsets | MODEL-PRICED at VIX, no costs; +0.707% at s = 0.81; 1,891 of 8,463 entries skipped for credit < 1% of S <!-- X-f5e50a1d --> |
| T-133 zero-cost 1×2 call ratio | untested → not_supported | mean +0.786% of S (CI +0.693 to +0.876) passes, but losses > 3× the median gain in 0.89% of entries (CI +0.47 to +1.48) against the claimed > 3% | MODEL-PRICED <!-- X-78d24028 --> |
| T-135 1-3-2 call Christmas tree | untested → supported | zone hit rate 48.8% vs risk-neutral 31.5%: +17.32 pp (CI +13.90 to +20.93), 21 of 21 offsets | MODEL-PRICED; +15.35 pp at s = 0.81 <!-- X-5cce8455 --> |
| T-136 stock repair after a 10% drawdown | untested → inconclusive | +1.00% of S (CI −1.53 to +2.69) over 25 episodes against min_n 30 | MODEL-PRICED; event study, not decisive <!-- X-d77c443f --> |
| T-138 SKEW-timed risk reversal | untested → not_supported | top minus bottom SKEW quintile −0.04% of S (CI −0.61 to +0.74); 0 of 21 offsets | MODEL-PRICED at flat IV, so the entry premium does not vary with SKEW <!-- X-93c696cc --> |
| T-139 LEAPS as stock replacement | untested → not_supported | return difference −0.77%/yr (CI −1.60 to +0.37) not below 0; drawdown ratio 0.82 passes | MODEL-PRICED; 33 annual holds <!-- X-57623c6d --> |
| T-140 deep-ITM call as stock substitute | untested → not_supported | daily correlation 0.9424 (CI 0.8987 to 0.9830) against > 0.98 | MODEL-PRICED; shortfall −0.58 pp (CI −2.61 to +1.10) <!-- X-cbfc46bf --> |
| T-154 ZEBRA | untested → not_supported | (ZEBRA − delta-matched SPY) / S +0.076% (CI −0.095 to +0.280) on the monthly calendar; pooled 21-session grid −0.025% (CI −0.118 to +0.080), 2 of 21 offsets | MODEL-PRICED; the preview was supported on one grid phase <!-- X-54e06747; git 6ee1b48 --> |
| T-516 3%-OTM digital put | untested → supported | realised frequency 16.3% vs N(−d2) 28.0%: −11.72 pp (CI −14.35 to −9.03), 21 of 21 offsets | MODEL-PRICED at flat VIX; −7.19 pp at s = 0.81; the upper CI reaches 0 at about 0.66 × VIX <!-- X-b2c26a56 --> |

**Batch 6a, time and term structure on SPY (`batch6_term`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-143 long calendar by VIX/VIX3M regime | untested → not_supported | regime difference in P&L/debit +1.37%, block-shift p 0.4098 (×3 thresholds 1.0000); 325 high-regime days | MODEL-PRICED; the archive's VIX3M starts 2009-09-18, not the claim's 2007-12 <!-- X-10a49f0d --> |
| T-144 short calendar in steep contango | untested → not_supported | 1,753 conditional entries, mean +1.99%; first half +3.08% (98.33% CI −2.99 to +9.99) | MODEL-PRICED; all four deflated CIs include 0 <!-- X-87edcdcc --> |
| T-145 long diagonal vs vertical | untested → not_supported | Sharpe 1.49 vs 1.49, difference −0.00 (CI −0.11 to +0.12), PBO 0.9143 | MODEL-PRICED; 204 months <!-- X-58e4c1d3 --> |
| T-146 double calendar vs single | untested → not_supported | std ratio 0.796 (CI 0.665 to 0.949); first half CI 0.598 to 1.032 crosses 1 | MODEL-PRICED <!-- X-3c150160 --> |
| T-147 double diagonal vs iron condor | untested → not_supported | P&L / max loss difference −6.75% (CI −8.19 to −4.97) on low-VIX entries | MODEL-PRICED; 114 months; SKEW tilt −7.66% <!-- X-63ef8ec5 --> |
| T-149 vega-neutral ratio calendar | untested → not_supported | Spearman(P&L, ΔVIX) +0.638 (CI +0.601 to +0.672) against |ρ| < 0.3 | MODEL-PRICED; 858 weeks <!-- X-396ecf5b --> |
| T-150 PMCC does not beat the covered call | untested → not_supported | Sharpe PMCC 1.42 vs CC 1.19: +0.23 (CI −0.15 to +0.57), first half +0.38 (CI +0.09 to +0.61) lies above 0 | MODEL-PRICED; return on capital 77.9% vs 19.0%/yr, max drawdown −75.2% vs −30.4% <!-- X-0716df12 --> |
| T-151 LEAPS collar vs standard collar | untested → not_supported | Sharpe 1.50 vs 1.53, difference −0.04 (CI −0.40 to +0.38) | MODEL-PRICED <!-- X-24b761f5 --> |
| T-152 calendarised butterfly in VIX spikes | untested → supported | spike-decile P&L/debit time fly −2.62% vs plain −61.84%: +59.22 pp (CI +39.72 to +77.58), 18 of 21 offsets, 23 spike months against min_n 15 | MODEL-PRICED; VIX stands in for VIX3M before 2009-09-18 on 66 of 473 spike entries; walk-forward halves each below min_n; +44.71 pp at s = 0.81 <!-- X-8c2b7bf1 --> |
| T-155 rolling a tested short put | untested → not_supported | roll minus reset +3.196 bp of spot per day (CI +2.003 to +4.323): rolling is better, so the "does not" claim fails | MODEL-PRICED; variance ratio roll / reset 6.068 <!-- X-3e10c60c --> |

**Batch 6a, surface and index relative value (`batch6_surf`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-159 VIX/VIX3M regime filter on the VRP | untested → not_supported | high-VIX tercile contango-minus-backwardation +499.5 %² (CI −525.7 to +7238.3), deflated p 0.628 | model-free; low and mid terciles hold 0 and 1 backwardation days, untestable <!-- X-bd91ae4f --> |
| T-227 high SKEW, more realised tails | untested → not_supported | high-SKEW 1.46% vs low-SKEW 1.16% of windows: +0.30 pp, upper bound +2.52 pp against the 1 pp margin; 2009-2026 realised-skewness difference −0.286 (p 0.000) | model-free; 1,990 low-SKEW windows <!-- X-e2bef5fd --> |
| T-228 SKEW-implied tail gap | untested → supported | SKEW-implied 8.54% vs realised 1.05%: +7.49 pp (lower bound +6.52) against 2 pp; 21 of 21 offsets | model-free; a constant-normal benchmark gives +1.23 pp, below the margin <!-- X-1c42240d --> |
| T-229 put spread when SKEW is cheap | untested → not_supported | low-SKEW payoff/debit 0.658 vs all months 0.725: −0.067 (CI −0.405 to +0.335) | MODEL-PRICED; smile slope κ calibrated on one SPX capture <!-- X-445e5d1a --> |
| T-237 VXN−VIX z-score extremes | untested → not_supported | pooled +0.77 vol pts (CI +0.28 to +1.25) but the wide side −0.35 (CI −1.14 to +0.43) over 41 events | model-free; the narrow side alone is +1.75 <!-- X-f61b21fd --> |
| T-239 VIX call overlay on a 1% budget | untested → not_supported | drawdown reduction 21.5% (lower bound −2.4%) against > 25%; 203 cycles | MODEL-PRICED Black-76 at VVIX <!-- X-f49a2a7a --> |
| T-240 VVIX above realised vol-of-VIX | untested → not_supported | 90 of 247 months = 0.364 against > 0.70; mean premium −21.9 vol pts | model-free <!-- X-7f1908d5 --> |
| T-249 forward variance premium fraction | untested → not_supported | forward minus spot premium fraction +0.043 (CI −0.407 to +0.178), 68 holds | model-free; the level version +0.0098 (CI +0.0029 to +0.0143) is positive <!-- X-6ae5939f --> |
| T-511 weekend variance below 1.5× | untested → not_supported | Fri→Mon / weekday-night variance 1.272 (CI 1.010 to 1.532) against < 1.5; 1,535 weekends | model-free <!-- X-f680a617 --> |
| T-538 dispersion, COR1M vs realised | blocked → inconclusive | COR1M 37.1 vs sector-proxy realised 55.7: −18.6 pts | the nine sector SPDRs are not the claim's constituents; constituent closes and weights not archived <!-- X-66a6cce7 --> |

**Batch 6a, crypto hedging and captured-chain parity (`batch6_xc`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-255 BTC delta-hedged short straddle | untested → supported | +14.3% of premium (CI +10.2 to +18.1), after fees +11.2%, Sharpe 1.34; 30 of 30 offsets; at the measured 0.945 scale +9.5% (CI +5.2 to +13.5), Sharpe 0.71 | MODEL-PRICED at DVOL; 66 cycles 2021-04 to 2026-08 <!-- X-b56d12eb --> |
| T-261 coin-corrected delta on an inverse strangle | untested → not_supported | variance ratio corrected / naive 0.873 (CI 0.793 to 0.979) against < 0.8 | MODEL-PRICED at DVOL <!-- X-51c9d9c3 --> |
| T-194 SPY vs SPX financing rate | untested → inconclusive | 4 of 4 expiries within 25 bp on 2026-10-13, 0 of 4 on 2026-10-14 (gaps −80 to −92 bp); 4 of min_n 10 | two capture days; a 15-minute spot mismatch moves the rate about 10 bp/yr per 1 bp of spot <!-- X-471ee9f1; the 25 bp band is registry T-194 claim --> |
| T-199 GLD option-implied carry | untested → not_supported | day one 50 of 56 pairs = 89.3% within 50 bp against ≥ 90%; day two 92.9% | capture-day statistic; the nearest failing pair misses by 2.3 bp <!-- X-6f856e67 --> |
| T-137 near-ATM parity deviations | blocked → not_supported | 142 of 888 pairs = 15.99% outside the band against < 1%; SPX 37.7%, SPY 0.0%, GLD 0.0%, IBIT 7.1% | two capture days; SPX fails on a bill-financed forward and passes at its own box rate (0.0%); with that reading the pooled share is 1.35% at the close and 0.23% at the synchronous spot <!-- X-16ddfa68 --> |

**Batch 6b, buy-write and put-write (`batch6b_bw`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-128 put-write beats SPY | untested → not_supported | Sharpe 0.861 vs 0.547: +0.315 (CI +0.012 to +0.554) at IV ×1.00, +0.075 (p 0.284) at ×0.90; second half p 0.322 | MODEL-PRICED; VIX overstates SPY's ATM IV <!-- X-3d662f03 --> |
| T-161 BXM Jensen alpha | untested → not_supported | alpha −0.78%/yr (CI −2.86 to +1.16), beta 0.629, 294 months | published index; 1 back-tested month <!-- X-f5ad4c58 --> |
| T-162 BXMD vs BXM Sharpe | untested → inconclusive | +0.113: studentized CBB CI +0.007 to +0.221 passes, Ledoit-Wolf CI −0.015 to +0.241 (p 0.078) fails; rule 11 | 161 of 294 months back-tested <!-- X-173afa14 --> |
| T-163 BXMW vs BXM | untested → not_supported | +0.071 (CI −0.092 to +0.249), 171 months | 38 months back-tested; with 0.05% roll costs −0.153 <!-- X-1f452751 --> |
| T-164 BXMH vs BXM | untested → inconclusive | +0.111 (CI +0.000 to +0.242); the lower end is within 2 Monte Carlo s.e. of 0 | 222 of 294 months back-tested <!-- X-df13fe5c --> |
| T-170 PUT vs BXM Sharpe | untested → supported | 0.554 vs 0.442: +0.112 (CI +0.030 to +0.188), 236 months; post-launch +0.113 (CI +0.028 to +0.188) | 5 back-tested months; PUTY−BXM +0.005, WPUT−BXM −0.121 <!-- X-66d68491 --> |
| T-171 wheel with a basis floor | untested → not_supported | calibration gate fails: BXM tracking error 2.35%/yr, PUT 2.53% against < 2%; difference +0.023 (CI −0.067 to +0.108) | MODEL-PRICED <!-- X-9c038379 --> |
| T-172 CMBO vs BXY | untested → not_supported | −0.011 (CI −0.068 to +0.049), 459 months; second half −0.060 | 326 of 459 months back-tested <!-- X-b1cbc563 --> |
| T-174 covered put | untested → not_supported | 107 of 321 rolling 120-month windows negative = 0.333 against ≥ 0.90; gate fails | MODEL-PRICED <!-- X-3e616bfc --> |
| T-202 PUT−BXM return gap in (0, 1.5) pp | blocked → not_supported | CAGR +7.16% vs +5.97%: +1.19 pp/yr, CI +0.14 to +2.27 pp, upper end outside the band | 5 back-tested months <!-- X-b6a74212 --> |
| T-527 call-spread overwrite | untested → not_supported | Sharpe 0.449 vs 0.903: −0.454 (CI −0.594 to −0.253); gate fails | MODEL-PRICED flat IV, which overprices the 5%-OTM wing <!-- X-2e704524 --> |

**Batch 6b, hedged overlays and the VIX settlement (`batch6b_hedge`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-166 CLL below a beta-matched blend | untested → not_supported | CAGR CLL +8.28% vs blend +7.37%: +0.91% (CI −3.49 to +4.03), beta 0.51; 219 months | 1% of the window back-tested; one flagged CLL level step excluded <!-- X-7d7b4e5d --> |
| T-168 CLLZ no higher Sharpe than SPY | untested → supported | monthly Sharpe 0.1389 vs 0.1748: −0.0359 (CI −0.0639 to −0.0128), 405 months; post-launch −0.0272 (CI −0.0888 to +0.0235) | 67% of the window back-tested <!-- X-47e71844 --> |
| T-169 PPUT more than 1%/yr below a blend | untested → not_supported | CAGR +7.85% vs +8.82%: −0.96% (CI −3.32 to +1.35) against < −1% | 67% back-tested <!-- X-80fa69b3 --> |
| T-178 BFLY below CNDR | untested → inconclusive | monthly Sharpe 0.0291 vs 0.0982: −0.0691 (CI −0.1361 to −0.0001); 5 of 6 bootstrap variants pass, marginal | 72% back-tested; 485 months <!-- X-7459c2a7 --> |
| T-179 CNDR return on the VIX−RV gap | untested → not_supported | slope +0.00018 per vol pt (CI −0.00015 to +0.00054), 438 rolls | 70% back-tested <!-- X-30b8aabf --> |
| T-180 Black-Scholes replicates BXM and PUT | untested → not_supported | BXM R² 0.964, TE 2.35%/yr; PUT R² 0.960, TE 2.53% against TE < 2% | MODEL-PRICED; the simulation sits 5.05%/yr above BXM, 3.60% above PUT <!-- X-63ffe887 --> |
| T-528 VXTH drawdown 10 pts shallower | untested → not_supported | maxDD SPY TR 55.2% vs VXTH 43.3%: +11.9 pts, 90% CI −6.5 to +23.8; PPUT3M 39.9% is shallower still | 26% (VXTH) and 75% (PPUT3M) back-tested; 5,161 days <!-- X-c362849a --> |
| T-220 VIX call credit spread into the SOQ | blocked → not_supported | one information set: +0.87% of max loss (CI −1.11 to +2.45) at the previous close, +0.59% (CI −2.15 to +2.04) at the entry close; chain-calibrated −0.41% / −0.53% | MODEL-PRICED Black-76 at VVIX; 110 trades from 2013; today's half-spreads applied to history; rule 12 <!-- X-1c908327 --> |

**Batch 6b, captured-chain arbitrage and financing (`batch6b_chain`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-153 jelly roll at bill carry | untested → not_supported | 4 of 38 strikes (10.5%) and 1 of 57 (1.8%) within tolerance against ≥ 95% on every capture; the dividend-free pair 83.7% / 92.1% | two captures; the SPX control is 100% <!-- X-fc398775 --> |
| T-182 conversion lends below the bill | untested → inconclusive | day one 73.0% of 293 pairs at the close spot vs 96.9% at the parity-implied spot: the spot variants disagree; day two 100% | the underlying's ask is assumed (+$0.005) <!-- X-ac71dd4f --> |
| T-184 synthetic long financing < bill + 50 bp | untested → not_supported | 1 of 4 expiries on day one (gaps +48.9 to +97.6 bp) against ≥ 80% | 8 of min_n 20 expiry observations; decisive on day one <!-- X-0cbfdd19 --> |
| T-185 synthetic short borrow < 50 bp | untested → not_supported | 79.8% / 76.6% of 124 pairs on day one against ≥ 80%; day two 0.0% at the close spot | two captures <!-- X-e4010567 --> |
| T-191 deep-ITM puts at intrinsic | untested → inconclusive | at-intrinsic share +99.1 pp higher where the exercise criterion holds (CI +98.6 to +99.6), 1,232 puts | passes on both days; needs 20 captured days <!-- X-f64267bb --> |
| T-500 credit butterflies | untested → inconclusive | 0 of 19,276 SPX and 0 of 7,404 SPY executable credit butterflies (95% upper 0.016% / 0.040%) | 2 of the 5 capture days the pass needs <!-- X-6568b066 --> |
| T-501 credit calendars | untested → inconclusive | 0.0% of 7,856 SPY calendars at a credit; mid-price inversions 5.41% | 2 of 5 days <!-- X-a6b081cf --> |
| T-507 protective put cheaper than call + bills | untested → not_supported | 57.0% / 52.0% of 293 strikes on day one against ≥ 60%; 0.3% on day two | the underlying's ask is assumed <!-- X-7d886959 --> |
| T-508 vertical bound violations | untested → inconclusive | 0 of 60,335 executable violations on day one across SPY, SPX, QQQ, GLD and IBIT | 2 of 5 days <!-- X-133cc150 --> |
| T-103 short strangle beats short straddle | untested → not_supported | smile-scaled Sharpe difference +0.1240 (CI +0.0275 to +0.2091) but flat-VIX −0.0172: the same-sign criterion fails | MODEL-PRICED on a smile from two capture days <!-- X-e3bda8ef --> |

**Batch 6b, box rates, OPEC, elections, silver (`batch6b_misc`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-188 box−bill spread moves with VIX | blocked → not_supported | correlation of Δ(box6m − bill) with ΔVIX 0.033 (CI −0.017 to +0.101) over 3,547 days against > 0.2 | research series 2004-2018 at 6/12/18-month maturities, not the claim's 60-120 DTE <!-- X-221aebb6 --> |
| T-518 USO straddle on OPEC+ days | blocked → inconclusive | 0 of 67 event sessions knowable at the T−1 close (min_n 40); the ex-post difference +0.611% (CI +0.129 to +1.152) is look-ahead | MODEL-PRICED at OVX; Kanzig's list is announcements, not the meeting calendar <!-- X-da58485b --> |
| T-522 election-day SPY move | untested → not_supported | 9 of 16 elections positive (two-sided p 0.8036) against ≥ 13; mean ratio difference +0.046 (CI −0.222 to +0.336) | underpowered by design <!-- X-e726de11 --> |
| T-275 SLV 1×2 call backspread | untested → not_supported | +0.808% of S (CI −0.484 to +2.430) at realised vol; +0.247% at RV + 5 pts | MODEL-PRICED at trailing realised vol, no VRP, no skew <!-- X-9856d560 --> |

**Batch 6b, DoltHub traded quotes (`batch6b_dolt`, `batch6b_volh`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-119 1:2 call backspread loses | blocked → not_supported | mean P&L / max loss −0.078 (CI −0.202 to +0.051) against upper < 0; 707 entry days | traded mids 2019-2026; 11.9% of trades settle above the upper breakeven <!-- X-0b00e203 --> |
| T-121 put front-ratio | blocked → not_supported | bid/ask mean +0.008 of naked-leg margin (CI −0.013 to +0.028); 565 entry days; stress months present | 46 trades open across a stress session average −0.093 <!-- X-cd21ab67 --> |
| T-173 1×2 overlay by call-skew slope | blocked → inconclusive | top minus bottom slope quartile +0.54 to +0.63% of S across four readings: one passes, two marginal, one fails (CI −0.02 to +2.34) | 78-85 cohorts; without the most favourable cohort +0.35% (CI −0.13 to +1.43) <!-- X-70e4d9b6 --> |
| T-539 long put ladder | blocked → not_supported | bid/ask mean +0.011 (CI −0.012 to +0.029) | traded quotes <!-- X-e6e164dc --> |
| T-250 sector implied-minus-realised correlation | blocked → not_supported | implied 0.463 vs realised 0.440: +0.011 (CI −0.026 to +0.050) against > 0.05; 87 cycles | vendor IV; no point-in-time sector weights archived <!-- X-931dd4dd --> |

**Batch 6b, Deribit (`batch6b_drb`)**

| Theory | Status | Deciding number | Caveat |
|---|---|---|---|
| T-222 catalyst strangle | blocked → inconclusive | 4 catalysts knowable at entry against min_n 20; mean return on debit +16.3% (CI −47.5 to +120.7), 1 of 4 positive | trade prints; 21 windows stored, 9 verifiably known at entry <!-- X-2e4eac10 --> |
| T-197 quarterly basis > bill + 100 bp | untested → not_supported | median excess +331 bp, but on 189-day blocks (rule 6) the CI is +74 to +680 bp and includes 100 bp; 2022 −34 bp, 2023 −82 bp | the trial's 20-day blocks (+254 to +415 bp) would have passed <!-- X-047acafb --> |
| T-223 monthly-expiry Friday straddle | untested → not_supported | monthly minus other Fridays +15.74 bp of spot (CI −15 to +45); 67 vs 223 Fridays | MODEL-PRICED at DVOL, settled at the actual delivery price <!-- X-3c1a0a3e --> |
| T-263 BTC FOMC straddle premium | untested → not_supported | implied minus realised move +0.13% (CI −0.35 to +0.59), hit rate 0.53, 38 decisions | trade prints in the 24 h before each decision <!-- X-08824f68 --> |
| T-268 DVOL futures term premium | untested → inconclusive | +2.14 vol pts (CI +0.77 to +3.48) at a 24 h tolerance; the > 2 target fails at 36/48 h and no cutoff (+1.91 to +1.93) | basis +0.26 vs DVOL drift +1.87; 16 of 38 marks are the index itself <!-- X-574db0ce --> |
| T-269 CME 1256 vs IBIT covered call after tax | untested → not_supported | after-tax difference −9.04%/yr (CI −18.62 to +0.39) over 5 years | MODEL-PRICED at DVOL; statutory rates <!-- X-c595e83c --> |
| T-195 Deribit put-call parity | untested → inconclusive | 0 of 88 observations exceed fees (95% upper 4.11%); 88 of min_n 500 | 2 book captures <!-- X-7163e0a9 --> |
| T-196 inverse box lends above bill + 100 bp | untested → inconclusive | median executable box minus bill −1,233 bp (mid +499 / +538 bp against a 417 bp bill) | 2 snapshots of 200 <!-- X-1830d794 --> |
| T-260 box rate > bill + 200 bp on 70% of days | blocked → inconclusive | 0 of 2 days (mid 180 / 485 bp against 417 bp) | 2 of 60 days; Tardis blocked from this host <!-- X-f43acb93 --> |
| T-257 risk-reversal skew harvest | untested → inconclusive | pooled +0.04% of S (CI −0.52 to +0.62), hit rate 0.50; 24 of 40 entries | MODEL-PRICED at trade-fitted IVs; 257 of 262 signals sell the put wing <!-- X-f3e5922c --> |
| T-262 calendar on an inverted BTC term structure | untested → not_supported | all-start non-overlapping mean +0.93% of S (CI −0.48 to +2.34), 0 of 16 starts; 31 holds | MODEL-PRICED at trade-fitted IVs, Black-76 on each expiry's own forward <!-- X-550ca26f --> |

### What the eleven supported claims show, and do not

**T-540, T-234 and T-123 are the variance risk premium in three sets of clothes.** All three run on VIX and SPY or
^GSPC closes with no option price in them. T-540 is the premium in the units a variance swap pays: short 30-day variance
struck at VIX² and settled on the next 21 close-to-close returns earns +8.12 %² per month (CI +1.43 to +11.22) pooled over
all 21 start offsets, with 17 of 21 single grids passing on their own; the distribution has skew −7.60 and kurtosis 93.0,
and the worst cycle, entered 2020-02-26, loses 630.8. <!-- X-a7f44bf6 --> Those tail figures are the content of the claim,
not a flaw in it: the trial says the tail is the point. <!-- registry T-540 trial.pass --> T-234 is the same premium as a
win rate: VIX² exceeds the next 21-day realised variance in 370 of 441 calendar months (0.839, Clopper-Pearson 0.801 to
0.872), and in each third of the sample the point rate clears 0.75 although the last third's lower bound (0.744) does not;
the reason states that the stricter reading does not hold. <!-- X-a774b108 --> T-123 is the buyer's side: a 30-DTE ATM
straddle bought at 0.90 × VIX and delta-hedged daily loses 1.98 vol points per unit vega (CI −2.46 to −1.37) on every one
of the 21 grids. <!-- X-78f814bf --> None of this is a tradable edge. The premium is measured at the variance-swap level,
and VIX sits above the ATM IV an option seller actually receives: SPY's vendor 30-day ATM IV runs 3.2 points below VIX/100
on average, <!-- X-931dd4dd --> the captured SPY ATM IV / VIX ratio was 0.799 on the two quote days, <!-- X-b734534f --> and
at that level the premium disappears from the model. T-123's loss shrinks to −0.20 (CI −0.70 to +0.52) at s = 0.81 and
changes sign at s = 0.800; <!-- X-78f814bf --> T-233, the seller's version of the same straddle at 0.81 × VIX with a
0.5-vol-point round trip, is not supported at −3.60% of premium (CI −7.17 to −0.31), −5.12% at the measured 0.799;
<!-- X-b734534f --> and T-234's own ATM-straddle control at s = 0.81 has a win rate of 0.658 and a mean premium of −3.16
%² per month against the VIX strip's 0.839 and +9.33. <!-- X-a774b108 --> What stands is a description: the index
variance strip has been rich relative to realised variance since 1993. Whether an account can collect it depends on
the price of the ATM straddle it must sell, which the archive has for two days.

**T-170 and T-168 are comparisons of published Cboe index histories.** T-170 says the PUT index (ATM put-write on
bills) has a higher monthly Sharpe than BXM (ATM buy-write): 0.554 against 0.442, a difference of +0.112 (CI +0.030 to
+0.188) over 236 months from 2007-02 to 2026-09, and it passes under both the studentized block bootstrap the trial names
and the Ledoit-Wolf test it does not (two-sided p 0.019); only 5 of its months are pre-launch back-test, and the
post-launch months alone give +0.113 (CI +0.028 to +0.188). <!-- X-66d68491 --> It does not generalise to the other
put-write arms: PUTY − BXM is +0.005 (CI −0.117 to +0.138), WPUT − BXM −0.121 (CI −0.359 to +0.126), and the 2%-OTM
parity control PUTY − BXY is −0.086 (CI −0.256 to +0.073); only the dynamic PUTD arm shows a gap (+0.222, CI +0.076 to
+0.392). <!-- X-66d68491 --> It is a fact about two index constructions at index fills, not about an account: the index
claims take no decision and carry no account-level costs, and T-163 shows what a 0.05%-of-notional roll charge does to
a gap of this size (+0.071 to −0.153). <!-- batch6b_bw.py docstring; X-1f452751 --> T-168 is a supported negative: the
CLLZ zero-cost put-spread collar has no higher monthly Sharpe than SPY total return, −0.0359 (CI −0.0639 to −0.0128) over
405 months, the pass being an upper bound at or below 0.05 with a point estimate at or below 0. <!-- X-47e71844 --> 67% of
that window is Cboe's back-test before the 2015-08-03 launch; the 134 live months alone give −0.0272 (CI −0.0888 to
+0.0235), which still meets the pass. <!-- X-47e71844; registry T-168 notes --> In the 40 months with SPX down more than
5% CLLZ lost 5.89% against SPY's 7.57%, so the collar did what collars do; what it did not do is improve risk-adjusted
return. <!-- X-47e71844 -->

**T-228 is a mapping artefact, and worth keeping for that reason.** The claim says the SKEW-implied risk-neutral
probability of a 2-sigma monthly drop (Cboe's white-paper mapping, 2.3% at SKEW 100 and 14.45% at 145 <!-- registry T-228
claim -->) exceeds the realised frequency by more than 2 points. It does: 8.54% implied against 1.05% realised over 441 holds, a gap of +7.49 pp
with a lower bound of +6.52 pp, on 21 of 21 grids. <!-- X-1c42240d --> But a constant normal benchmark (P = 2.28%) leaves
a gap of only +1.23 pp, below the margin, so the excess comes from the SKEW-to-probability mapping, not from realised
tails being rarer than normal. <!-- X-1c42240d --> On whether SKEW predicts anything, the two batch-6a tests disagree in
an instructive way: T-228's own control finds realised tail frequency 0.79% when SKEW is above 135 against 1.10%
otherwise (placebo p 0.608), <!-- X-1c42240d --> and T-227 cannot show high-SKEW windows carry 1 pp more tail events
(+0.30 pp, upper bound +2.52 pp), yet its second criterion fails because high-SKEW windows in 2009-2026 do have more
negative realised 21-day skewness (−0.286, one-sided p 0.000). <!-- X-e2bef5fd --> SKEW's implied tail probability
overstates realised tails; the SKEW-timed structures built on it (T-138, T-229) are not supported. <!-- X-93c696cc;
X-445e5d1a --> It is not a tail predictor to trade; it is a reason not to read Cboe's table literally.

**T-255 is the BTC variance premium, model-priced at DVOL.** A 30-day ATM BTC straddle sold at Black-Scholes with
sigma = DVOL and delta-hedged on daily closes earns +14.3% of premium per cycle (CI +10.2 to +18.1) pooled over all 30
start offsets of 66 cycles from 2021-04 to 2026-08, +11.2% after Deribit fees and a 1 bp/day funding charge, annualised
Sharpe 1.34; all 30 offsets pass all three criteria. <!-- X-b56d12eb --> The level is the IV scale again: DVOL is a
variance-swap level that sits above the ATM IV, the measured 30-day ATM mark / DVOL ratio is 0.945 on two book captures
in October 2026, and at that scale the mean is +9.5% (CI +5.2 to +13.5) with an after-fee Sharpe of 0.71; at 0.90 it is
+5.1% and at 0.85 −0.3%. <!-- X-b56d12eb --> The refuter's per-cycle haircut from history.deribit.com trade IVs (ratios
0.814 to 0.98 over 2021-2026) left net +8.1%, Sharpe 0.97, still passing; the trial's own per-cycle haircut waits on the
daily trade tape, which was archived at 19:18 UTC after this record was written. <!-- registry T-255 notes; INDEX
deribit-option-trades-daily-BTC created_at --> A shuffled-DVOL placebo keeps the level premium (median +6.9%) and the
actual +14.3% beats all 100 permutations, so the timing part is real in the model. <!-- X-b56d12eb --> It is a cousin of
cycle 3's T-49 (DVOL 62.9 against realised 54.9) <!-- REPORT-2026-10-14-cycle3.md --> and, like it, not a venue result:
Deribit does not onboard US persons, and the archive treats it as data, not a venue. <!-- data/options.py docstring -->

**T-152, T-113, T-135 and T-516 are model-priced structure statements.** Each prices SPY legs by Black-Scholes at
VIX (or VIX3M) on the dividend forward, settles on raw closes and, except T-152 (half-spreads per fill from 11,885 OTM SPY
quotes captured on 2026-10-13 and 2026-10-14, on 6 vs 4 contracts), charges no transaction cost, so each says what a
flat-IV model implies about a shape, not what a traded book earned. <!-- batch6_dir.py and batch6_term.py docstrings;
X-8c2b7bf1 (costs); X-f5e50a1d, X-5cce8455, X-b2c26a56 ("no transaction costs") --> T-152:
in the top decile of VIX-increase months since 2007-12, a calendarised butterfly loses 2.62% of its debit by the front
expiry where the plain butterfly on the same strikes loses 61.84%, a paired difference of +59.22 pp (CI +39.72 to
+77.58) on 18 of 21 grids; outside the spike decile the ordering reverses (time fly −2.39%, plain +11.28%), so it is a
statement about a hedge in a spike, not an edge, and 66 of its 473 spike entries price the back leg at VIX because the
archive's VIX3M begins 2009-09-18 (real-VIX3M-only: +54.21 pp). <!-- X-8c2b7bf1 --> T-113: a one-month jade lizard earns
+2.740% of naked-put margin per month (CI +1.753 to +3.615) over 313 entered months, 21 of 21 grids, having skipped 1,891
of 8,463 entries whose credit was under 1% of spot; the edge is the short-premium VRP and shrinks to +0.707% at s = 0.81.
<!-- X-f5e50a1d; registry T-113 notes --> T-135: a 1-3-2 call tree finishes in its profit zone 48.8% of the time against
a risk-neutral 31.5%, +17.32 pp (CI +13.90 to +20.93), and the reason gives the mechanism the claim itself names: the
realised standard deviation of log(S_T/F) is 15.9% against a mean VIX IV of 19.5%, with a mean log return of +0.71% per
cycle, i.e. the VRP plus drift; the test is a probability comparison, not a P&L. <!-- X-5cce8455 --> T-516: 30-day
digital puts at 0.97 × spot finish in the money 16.3% of the time against a flat-VIX N(−d2) of 28.0%, −11.72 pp (CI
−14.35 to −9.03), and N(−d2) scores a Brier of 0.1513 against 0.1413 for point-in-time climatology; the gap narrows to
−7.19 pp at s = 0.81 and the upper bound reaches zero at about 0.66 × VIX, and a flat IV ignores the put skew a traded
digital is priced on. <!-- X-b2c26a56 --> All four keep their sign at s = 0.81 (T-516 with its interval still below
zero, −9.85 to −4.52 pp; T-113, T-135 and T-152 as point sensitivities the reasons mark "not in the pass rule" or "report
only", so a pass at that scale is not established for them), and T-113's trial names a chain-mid recheck at 60 days that
two archived chain days cannot run; the other three trials name no such control. <!-- X-8c2b7bf1; X-f5e50a1d;
X-5cce8455; X-b2c26a56; registry T-113, T-135, T-516, T-152 trial.controls -->

### Refuted before recording

Five options claims passed as previews and did not survive refutation or the rule-10 audit, and one recorded cycle-3
verdict (T-530, supported on 2026-10-14 and again at 11:39 UTC on 2026-10-15) was overturned by the audit at 18:26 UTC.
<!-- X-eb6f8b95; X-d4ada054; X-e049bc5e --> In every case the refuter's finding is written into the registry note or the
commit, and the rule it exposed is now in MANDEL.md; where a bullet below says a preview was supported or that two
refuters worked independently, the source is a commit body, not a commit subject or an experiment record. <!-- git
e406249, 92e7fa5, a1bb713 (bodies) -->

- **T-162, BXMD vs BXM (rule 11).** The preview was supported on a studentized block-bootstrap interval of +0.007 to
  +0.221 for a Sharpe gap of +0.113. The trial names the Ledoit-Wolf (2008) test as an alternative construction, and
  under it the symmetric interval is −0.015 to +0.241 (two-sided p 0.078). <!-- X-173afa14 --> The refuter also found the
  lower end fragile: removing any one of five years (2008, 2020, 2003, 2012, 2019) puts it at or below zero, and 161 of
  the 294 months are BXMD values Cboe back-tested before the 2015-08-03 launch. <!-- X-173afa14; registry T-162 notes -->
  Rule 11 was written from it: when a trial names alternatives, a criterion passes only if every named construction
  passes, and a borderline pass that flips under a permitted alternative is not evidence. <!-- MANDEL.md rule 11; git
  99278be --> Recorded inconclusive. <!-- git 3ae4cd8 -->
- **T-220, VIX call credit spread into the SOQ (rule 12).** The preview read the VIX3M/VIX gate at the previous close
  but chose its strikes from the sale-day VX settlement, two information sets in one decision; that mixed specification
  gives +1.28% of max loss (CI +0.19 to +2.67), which only 3 of 6 bootstrap variants pass. <!-- X-1c908327 --> Read from one
  information set, both admissible readings fail: +0.87% (CI −1.11 to +2.45) from the previous close and +0.59% (CI −2.15
  to +2.04) from the entry close, and the chain-calibrated Black-76 pricing the trial also names is negative under both
  (−0.41%, −0.53%). <!-- X-1c908327 --> Two further findings sit in the reason: the flat-VVIX model prices the spread 38%
  above the market mid on the one day both exist (0.193 against 0.140), and after today's half-spreads 55 of the 110
  trades have no net credit at all. <!-- X-1c908327 --> Rule 12 was written from it. <!-- MANDEL.md rule 12; git
  99278be --> Recorded not supported. <!-- git 3ae4cd8 -->
- **T-262, BTC calendar on an inverted term structure.** Two independent refuters reproduced the same two defects: the
  legs were priced on the median spot index although the fitted Deribit IVs are Black-76 on each expiry's own forward,
  and the primary statistic was an equal-weight mean over 110 overlapping signal days instead of the trial's
  non-overlapping entries. <!-- git a1bb713 body --> After the fix the all-start mean of the 16 non-overlapping walks is
  +0.93% of spot (CI −0.48 to +2.34), 0 of 16 starts pass alone, and one episode, the 2024 US election, had carried 48%
  of the earlier P&L. <!-- X-550ca26f; registry T-262 notes --> The reason also shows how much the open "7-30 DTE" front
  rule matters: the rule that keeps a front alive through the hold passes (+0.88%, CI +0.13 to +1.54) on 71 entries
  that make 18 non-overlapping holds, below the min_n of 30. <!-- X-550ca26f --> Recorded not supported on 31 holds.
  <!-- git e406249 -->
- **T-268, DVOL futures term premium.** The preview was supported on a mean of +2.14 vol points (CI +0.77 to +3.48)
  across 38 expiries. The refuter read the pass as worded: its "target > 2 vol points" is a criterion (rule 1), and the
  trial leaves the trade-time tolerance open, so both criteria are judged at 6, 12, 24, 36 and 48 hours and with no
  cutoff; the CI clears zero under all six, the target passes at three and fails at three (+1.91 to +1.93), so the
  result is undecided. <!-- X-574db0ce; git e406249 and 92e7fa5 bodies for the supported preview --> The decomposition is the finding: the futures basis at T−7d is
  +0.26 (CI −0.11 to +0.64) and the fall of spot DVOL into expiry +1.87 (CI +0.57 to +3.12), and in 16 of the 38 points
  Deribit's published futures mark is the DVOL index itself. <!-- X-574db0ce --> A DVOL drift into expiry, not a futures
  term premium. <!-- registry T-268 notes --> Recorded inconclusive.
- **T-154, ZEBRA (rule 10).** The preview was supported on one phase of a 21-session grid. The claim names monthly
  30-DTE options, so under rule 10 it runs on SPY's standard monthly expiry calendar: the difference against a
  delta-matched SPY position is +0.076% of spot (CI −0.095 to +0.280), the wrong side of the "ZEBRA earns less" claim,
  and the pooled all-start grid reported as robustness is −0.025% (CI −0.118 to +0.080) with 2 of 21 offsets passing.
  <!-- X-54e06747; git 6ee1b48 --> MANDEL.md names it, with T-540, as the preview that failed rule 10 when checked; the
  difference is that T-540's pooled estimate held and T-154's did not. <!-- MANDEL.md rule 10; X-a7f44bf6 --> Recorded
  not supported.
- **T-530, forward variance in contango (rule 10).** This one was recorded supported at the close of cycle 3, on 63
  contango entries of a single 63-day grid: forward minus realised variance +0.0220, p 0.0005, halves +0.0185 / +0.0254.
  <!-- X-eb6f8b95 --> The rule-10 audit pooled every start of the grid, 2,693 contango days: +0.0143, one-sided p 0.0465
  against the 0.025 the two-sided 95% interval needs, halves +0.0189 / +0.0098, and 30 of the 63 single phases pass.
  <!-- X-e049bc5e; git 1eaae35 --> The level is still positive in both halves; what it lost is significance once the
  phase stopped being chosen. Recorded not supported in the official re-run; the cycle-3 record stays in
  experiments.jsonl, as every record does. <!-- git 5a1a5c8; registry T-530 notes -->

### Still open on the options side

The six claims still running (T-331, T-425, T-465, T-459 on Kraken 1-minute trades; T-414, T-415 on StockTwits) are
not options claims and are covered in their own sections: [[PENDING]] One cross-reference carries the marker: T-337, the
Polymarket-vs-Deribit digital, reads the same Deribit tape through 32 monthly near-expiry bundles archived on 2026-10-16
(6,784,877 rows, 2024-03 to 2026-10, the last month partial) and awaits the Binance BTCUSDT 1-minute resolution windows
stored on 2026-10-19 (83,692 rows, local only): [[PENDING]] <!-- INDEX deribit-option-trades-near-BTC-* (32 bundles,
rows summed, 2026-10 tagged partial); ledger seq 6242 archive.stored binance-1m-BTCUSDT-btc-above; git ebfea1c -->

What the options claims themselves wait on is data, not analysis. The captured-chain claims (T-182, T-191, T-500,
T-501, T-508, T-194) need 5 or 20 capture days where the archive has 2 (5 for the "on >= 80% of captured days" criteria
of T-182, T-500, T-501 and T-508; 20 for T-191's stability and T-194's pass; 60 is T-153's confirmation and T-260's
days, not theirs); <!-- batch6b_chain.py docstring; registry T-191 and T-194 trial.pass --> the model-priced structures
(T-113, T-154, T-135, T-516, T-152) and the IV-scale questions behind T-123 and T-233 need chain history to replace the
flat-VIX proxy, while T-255, priced at DVOL, needs no chain: its trial's per-cycle DVOL-to-ATM haircut from
history.deribit.com trade IVs can now run on the daily trade tape archived at 19:18 UTC on 2026-10-15 and awaits a
re-run; <!-- X-f5e50a1d; X-54e06747; X-b56d12eb; registry T-255 notes; INDEX deribit-option-trades-daily-BTC created_at -->
T-195 and T-196 need
hourly Deribit book polls that history.deribit.com cannot serve, and T-260 needs the Tardis first-of-month feed run from
a host with its own IP. <!-- X-7163e0a9; X-1830d794; data/options_misc.py docstring --> On 2026-10-19 the archive repair
restored 25 INDEX entries a stale concurrent writer had reverted before the 2026-10-15 fix, among them the VIX-family
indices, four FRED series and the two DVOL histories these harnesses read; each was restored from its latest
`archive.stored` event, whose sha256 the file on disk matches on 2026-10-19. Nothing in the ledger records which INDEX
entry the 2026-10-15 run read, but the files themselves are the ones the INDEX now describes. <!-- ledger.jsonl
archive.index.repaired (25 events, seq 6136-6160, 2026-10-19T16:10 UTC, one reason text for all 25: "restored from the
latest archive.stored event, whose sha256 the file on disk matches"); git a166657 -->

## 4. Underlying claims, batch 6c

*The underlying strategy library entered the registry in cycle 3 as theories with exact rules and trial math: 130
strategies at the main report, 171 after the verifier pass of the addendum, with 211 verifier corrections.* <!--
REPORT-2026-10-14-cycle3.md, "Options strategies ... then the underlying" and the addendum table --> *Batch 6c is the first
pass at testing them. Nothing in this section is a tradable edge until it says so; most of it is a map of what the free
data can and cannot decide.*

### Triage: 17 now, 65 after a fetch, 4 blocked

The batch-6c triage sorted the untested underlying-library claims into three bins: 17 testable now on archived data, 65
testable after a free fetch, 4 blocked on survivorship-free single-stock data. <!-- MANDEL.md section 7 changelog, 2026-10-15
entry --> That is 86 claims. <!-- sum of the three triage counts --> By the close of 2026-10-19 the harnesses had recorded
80 verdicts under batch-6c harness names. <!-- experiments.jsonl: 80 records whose harness starts b6c_ --> Of those, 77 are
underlying-library claims; the other three (T-12, T-31, T-32) are older prediction-market theories registered in cycle 2
(origins src:11/adj:A5, src:05/src:07 and src:08/src:10/src:11), which the cycle-2 report listed as 'untested, cheap
harness pending' and the same prediction-market fetch unlocked. <!-- registry T-12, T-31, T-32 origin;
REPORT-2026-10-14-cycle2.md, "Untested, cheap harness pending"; registry notes of the 80 b6c theory ids: 77 carry the
underlying-library note --> Six underlying-library claims are still running: T-331, T-425, T-465 and T-459 on Kraken
1-minute trades and T-414 and T-415 on StockTwits. They are the registry's only `untested` theories. <!-- registry: status
untested = exactly T-331, T-414, T-415, T-425, T-459, T-465 --> 77 recorded plus 6 running is 83, one more than the
triage's 82 testable; the same one-claim gap shows between the changelog's 17 testable now and the 18 harnesses that ran
on archived data on 2026-10-15. <!-- git 6e09d78: "18 harnesses written, reviewed, fixed, refuted, wired and recorded" -->
I have not reconciled that one claim; the per-group table below counts what was recorded.

The four blocked claims are T-391 (insider purchase clusters), T-392 (13F cloning of concentrated managers), T-395
(repurchase announcements at 5% or more of market cap) and T-452 (post-earnings drift from SEC XBRL). <!-- ledger
theory.blocked x4, 2026-10-15T20:29, source "batch-6c triage with adversarial recheck" --> All four need the returns of
names that later delisted, merged or went bankrupt: Yahoo answers 404 'No data found, symbol may be delisted' (the CELG
probe) and reuses tickers for other instruments, and no free source reached from this host provides CRSP-style delisted
prices or delisting returns. <!-- registry T-391, T-392, T-395, T-452 blocked_on; git 8244604 --> T-391 also needs
historical shares outstanding for names that no longer file; T-395 needs pre-2009 share counts that are not in XBRL
companyfacts; T-452 needs XBRL acceptance datetimes and a point-in-time top-3,000 cap universe. <!-- registry T-391, T-395,
T-452 blocked_on --> The triage note is kept on each theory and each change is a `theory.blocked` ledger event. <!-- git
8244604 -->

### The fetchers, and what each could and could not reach

Five fetcher modules were written for the batch: `market_history`, `crypto_history`, `pm_history`, `public_history` and
`binance_klines`; the cycle-2 `social` module is in the table for comparison, because its daily captures are the only
StockTwits bundles in the INDEX. <!-- module docstrings; git 1892f6c, ebfea1c; INDEX count --> Every source was probed
from this host on 2026-10-15 (Binance on 2026-10-19) and each module's docstring records the endpoint, the point-in-time
rule and the licence decision. <!-- public_history.py, crypto_history.py, pm_history.py, market_history.py,
binance_klines.py docstrings --> The archive INDEX, read for this report at 2026-10-19 21:20 UTC, listed 3,475 bundles,
51,307,171 rows, 155 of them in git <!-- INDEX count, snapshot 2026-10-19T21:20Z; the latest bundle then was
kraken-trades-1m-XBTUSD-2024-02, created 21:09:33Z -->, against 66 bundles and 395,688 rows at the close of cycle 3.
<!-- REPORT-2026-10-14-cycle3.md, "Registry ... Archive" --> The ledger held 3,861 `archive.stored` events with
timestamps from 2026-10-15 at the same snapshot. <!-- ledger kinds, ts >= 2026-10-15, read 2026-10-19T21:20Z; last at
21:09:33Z --> The Kraken and StockTwits fetches were still writing, so both counts move until the lead re-reads them at
close.

| Module | Sources | In the INDEX today | Reached | Not reached, or capped | Licence decision |
|---|---|---|---|---|---|
| `market_history` | Yahoo chart API (daily OHLC with dividends and splits, hourly), FRED graph CSV, ALFRED vintages | first store 327 bundles, 1.08M rows, 313 local-only <!-- git 933c7de -->; now daily-history 901 (47 in git), daily-events 855, hourly 48 (8 in git), fred 27 (14 in git), alfred 16 (4 in git) <!-- INDEX count --> | whole daily history in one call; ALFRED every real-time vintage (UNRATE: 800 vintages 1960-03-15..2026-10-02) <!-- market_history.py docstring --> | delisted tickers 404; reused tickers resolve to other instruments (FB is now a Cboe ETF); hourly bars reach back about 730 sessions, 1-minute about 30 days; `query1` answered 429 to browser user agents, `query2` worked <!-- market_history.py docstring --> | FRED in git only when the series page says public domain and the source is a US federal agency; Yahoo, Michigan, Moody's, OECD and NBER series local-only <!-- market_history.py docstring --> |
| `crypto_history` | Coinbase Exchange candles and products, Kraken public trades, CoinMarketCap historical listings, Coin Metrics community API, blockchain.info hash rate, DefiLlama yields, iShares IBIT page | coinbase-* 662 bundles, 7,096,665 rows; cmc 11; coinmetrics 7; defillama 2; ishares 2; btc-hashrate 1; kraken-trades-1m 26 monthly bundles (2022-01..2024-02), 1,128,812 rows at the 21:20 UTC snapshot; kraken stablecoin episodes 705,691 rows; none in git <!-- INDEX count --> | Coinbase `/products` lists 842 products, 515 online and 327 delisted, and delisted products keep their candles <!-- crypto_history.py docstring -->; CMC's keyless data-api answers the point-in-time ranking with dead coins included (BitConnect on 2018-01-07) <!-- crypto_history.py docstring --> | Kraken `/OHLC` returns only the latest 720 bars, so every Kraken bundle is rebuilt from `/Trades` at about 1 request/s (about 67k pages since 2022, about 18.6 hours; 58 monthly bundles expected) <!-- crypto_history.py docstring -->; CMC's per-coin history returns at most the latest 400 days; a forbidden Coin Metrics metric fails the whole request with 403; DefiLlama's `/pools` (16,790 pools) omits dead pools; the iShares NAV xls and holdings CSV both answer the HTML product page, so there is no NAV history download, only a 447-day premium/discount chart <!-- crypto_history.py docstring --> | none of these sources is public domain or openly licensed (Coin Metrics is CC BY-NC 4.0): every bundle local disk only <!-- crypto_history.py docstring --> |
| `pm_history` | Polymarket Gamma, CLOB and data-api; Kalshi trade-api v2 | kalshi-* 142 bundles, 8,256,999 rows (2 legacy in git); polymarket-* 173 bundles, 4,338,987 rows (4 legacy in git); pm-kalshi-pairs 1,025 rows <!-- INDEX count --> | Gamma keyset paging (the only complete route); CLOB hourly prices in 14-day windows; data-api taker trades, whose sizes sum exactly to Gamma's volumeNum; Kalshi historical and live stores either side of the 2026-08-16 cutoff <!-- pm_history.py docstring --> | Gamma pages hold at most 100 rows and plain offset paging is refused beyond about 2,000 rows; public search refuses pages above 100, so at most 5,000 of the 5,525 'bitcoin above' results are reachable that way (the keyset route replaced it); markets ending before 2023 are AMM-era with no CLOB history; data-api has no trades for 2023 markets and its offset is capped at 10,000; Kalshi answers at most 5,000 candles a request and met 429 from this shared host, so it is paced at 1 s; trade paging is capped at 15 pages a route <!-- pm_history.py docstring --> | Polymarket and Kalshi publish no open data licence: every batch-6c bundle, the pairs table and both fetch logs local only <!-- pm_history.py docstring --> |
| `public_history` | CFTC COT (Socrata), Treasury auctions, Cleveland Fed nowcasts, SPDR GLD archive, Sprott trust pages, SSGA SPY holdings, Wikipedia S&P 500 tables, fja05680 membership, FINRA short interest and Reg SHO daily files, SEC EDGAR submissions and companyfacts, StockTwits symbol streams, Deribit near-expiry option trades | cftc-cot 10 (in git); treasury-auctions 1 (in git); wikipedia-sp500 2 (in git); fja-sp500 2; finra-short-interest 211; finra-regsho 99; sec-* 74 (the ticker map in git); sprott 4; spdr 2; clevelandfed 3; ssga 1; deribit near-expiry trades 32 monthly bundles, 6,784,877 rows; no batch-6c StockTwits bundle yet <!-- INDEX count --> | COT release times verified against Socrata `:created_at` for every report since 2022-07; SEC acceptance times bounded two ways; the SPDR archive since 2004-11-18 <!-- public_history.py docstring --> | the MediaWiki API answered 429 to this shared host, and on 2026-10-15 Wikimedia answered 403 'Please respect our robot policy' to httpx for every User-Agent tried while urllib with the same User-Agent got 200, so the tables are read from page HTML through urllib <!-- public_history.py module docstring item 7; public_history.py `_wiki_get` docstring -->; the old SPDR CSV now serves a PDF; FINRA does not publish its dissemination date, so availability is set at the 8th NYSE business day after settlement; StockTwits retention is a rolling year (the oldest days are lost daily until fetched) and the run takes about 38 hours under its own archive root <!-- public_history.py docstring --> | CFTC, Treasury and SEC public domain (SEC bulk kept local for repository size); Wikipedia CC BY-SA 4.0 with attribution and revision in the recipe, in git; Cleveland Fed (a Reserve Bank), SPDR (disclaimer forbids redistribution), Sprott, SSGA, fja05680 (MIT, but its 1996-2019 base list is a book download), FINRA, StockTwits and Deribit local only <!-- public_history.py docstring --> |
| `binance_klines` | Binance BTCUSDT 1-minute klines around every Polymarket 'Bitcoin above' resolution time | 1 bundle, 83,692 rows, local only, stored 2026-10-19 20:13 UTC <!-- INDEX binance-1m-BTCUSDT-btc-above --> | `data-api.binance.vision`, Binance's public market-data mirror, answered 200 with weight headers; 686 resolution times 2024-03-15..2026-10-15 (490 noon, 196 at 17:00 ET), 121 bars each <!-- binance_klines.py docstring; git ebfea1c --> | `api.binance.com` answers 451 from this host; Binance.US answers 200 but is a different order book and is not mixed into the bundle <!-- binance_klines.py docstring --> | Binance's terms grant no redistribution right: local only, INDEX entry and recipe committed <!-- binance_klines.py docstring --> |
| `social` (cycle 2) | Reddit RSS, StockTwits trending, alternative.me Fear & Greed, House PTR index | daily captures; social-stocktwits-2026-10-14 and -15 are the only StockTwits bundles in the INDEX <!-- INDEX count --> | works without credentials <!-- social.py docstring --> | SEC EDGAR refused this host at the time (now reached by `public_history` with a declared User-Agent) <!-- social.py docstring; public_history.py docstring --> | in git <!-- INDEX in_git --> |

Two budget facts shape everything below. The prediction-market universe uncapped would be about 157k resolved Polymarket
markets and about 150k Kalshi markets, with daily history about 22 hours, Polymarket trade paging about 80 hours and
about 500 GB of downloads, Kalshi hourly candles about 56 hours plus trades about 220 hours; the default pull is a cap
(about 53.5k requests, about 510 MB on disk, about 7.8 hours of wall time) and the docstring names which claims each cap
trims. <!-- pm_history.py docstring, "Budget" --> The crypto default is about 99k calls, about 11.3M rows and about
22 hours, 18.6 of them Kraken, in one process. <!-- crypto_history.py docstring, "Estimates" --> Kraken is the reason four
claims are still running: at the 21:20 UTC snapshot the 1-minute bundles covered 2022-01 through 2024-02, 26 of the 58
months expected, the latest landed at 21:09 UTC. <!-- INDEX count, snapshot 2026-10-19T21:20Z; crypto_history.py
docstring -->

### Results by group

Every claim was tested on its own wording, pass criteria and `min_n` under the twelve harness rules. <!-- MANDEL.md section
2, "Harness rules" --> Verdicts: 4 supported, 65 not supported, 11 inconclusive. <!-- experiments.jsonl, 80 b6c records -->
Three of the 65 then parked under their trials' own park rules (T-405, T-404, T-328), so the registry reads 4 supported,
62 not supported, 11 inconclusive, 3 parked for the same 80 theories. <!-- registry status of the 80 b6c theory ids;
ledger theory.parked 2026-10-16T02:48 x2 and 2026-10-19T17:03 --> Each group had a write, review and fix pass, and every
supported preview (T-345, T-349 and T-357 in the first three groups, T-366 in the stock and crypto groups) had an
independent refutation pass before recording, as the changelog rule requires; the Yahoo/FRED groups had no supported
preview and so no refutation round, and the prediction-market commit records none. <!-- git 6e09d78, 55ad6df, 9399224,
3cd7b4f; MANDEL.md section 7, 2026-10-15 entry --> The commits count 9 reviewer-reproduced defects fixed in the first three groups, 10 in the Yahoo/FRED
groups, 2 verdict-changing and 1 verdict-at-risk in the prediction-market groups, and 3 verdict-at-risk plus 1
verdict-changing (T-367) in the stock and crypto groups. <!-- git 6e09d78, 9399224, 3cd7b4f, 55ad6df -->

| Group (module) | Claims | Supported | Not supported | Inconclusive | Reading |
|---|---|---|---|---|---|
| calendar (`b6c_cal`) | 5 | 3 | 2 | 0 | T-345, T-349, T-357 supported (below); T-347 Friday-minus-Monday speculative spread -3.6 bps against a 10 bps bar, p 0.70 <!-- X-f408bf40 -->; T-450 pension rebalancing slope HAC t -1.29 against -2 <!-- X-d5506b2c --> |
| momentum and trend (`b6c_mom`) | 7 | 0 | 6 | 1 | T-300 TSMOM minus historical-mean -25.8 bps a month after 2012 <!-- X-b6f22a08 -->; T-301 SMA-10 drawdown 24.3% vs 52.9% buy-and-hold but a Holm-adjusted p of at least 0.065 over the 96 declared variants (settled by bounds: at most 88 variants can rank before the primary, 8 x 0.0081) <!-- X-e5086ee8 -->; T-308, T-310, T-317, T-481 fail their Sharpe or Holm criteria <!-- X-0b696555, X-1b19b4a3, X-7d956b2f, X-21d2486b -->; T-311 crash filter inconclusive: 3 activation episodes against the 5-episode gate <!-- X-d2b172be --> |
| misc (`b6c_misc`) | 6 | 0 | 5 | 1 | T-318 88 technical rules vs buy-and-hold, PBO 0.39 against a 0.5 bar fails <!-- X-33edd767 -->; T-326 gold/silver ratio lower bound -0.83 bp a day <!-- X-159692aa -->; T-372 ES implied financing -7.1 bp against DTB3, lower bound -15.7 bp against a +20 bp threshold <!-- X-6453466b -->; T-370 gold implied financing -159.3 bp against DTB3, outside its +-50 bp band <!-- X-295e4045 -->; T-484 bond TSMOM +13.5 bp a month, lower -6.1 <!-- X-80f8ff58 -->; T-416 Fear & Greed extremes inconclusive, underpowered at 31 events <!-- X-be21458b --> |
| cross-sectional ETF (`b6c_xs`) | 7 | 0 | 7 | 0 | all seven long-short ETF ranks fail, five with negative net means and two with positive point estimates whose intervals include zero: 52-week high -0.147%/month <!-- X-2e07740e -->, return seasonality -0.391% <!-- X-ea341756 -->, weekly reversal -0.304%/week with gross -0.000% and costs 0.295% <!-- X-f552ce8e -->, VIX-conditioned reversal -0.35%/week out of sample <!-- X-25c17354 -->, country long reversal -0.089%/month <!-- X-ba0aaeda -->; commodity momentum +0.470%/month (CI -0.444 to +1.422), permutation p 0.067, DSR 0.23 <!-- X-1fe91bd6 -->, frog-in-the-pan +0.106%/month (CI -0.579 to +0.726), DSR 0.28 <!-- X-f2054bba --> |
| pairs (`b6c_pairs`) | 5 | 0 | 5 | 0 | distance pairs -8.1 bp a month, below the random-pair control <!-- X-b1d9defb -->; cointegration persists in 13.2% of windows against a 50% bar <!-- X-4761369a -->; Kalman hedge worse than static (paired net-Sharpe difference -0.58 over all pair-windows, -0.53 in 2008-2016 and -0.62 in 2017-2026) <!-- X-fb57378c -->; Brent/WTI 21 trades, -24.3 bp each <!-- X-1021d8c2 -->; dual-class 3 of 9 pairs positive against 6 of 10 <!-- X-45f5e60a --> |
| rates (`b6c_rates`) | 7 | 0 | 7 | 0 | Treasury carry/roll-down timing Sharpe gain +0.08 against +0.15 <!-- X-99dd2004 -->; SGOV tracks bills at -13.1 bp a year against a 10 bp band <!-- X-0b61007d -->; cross-asset carry composite Sharpe -0.20 <!-- X-f35fc78f -->; credit timing, global bond carry, equity country carry all under their 0.3 Sharpe bars <!-- X-3e56d2d8, X-5aa4029e, X-6a6e92e3 -->; Treasury butterfly -0.19% a trade <!-- X-cbd10dc5 --> |
| macro (`b6c_macro`) | 6 | 0 | 6 | 0 | fund-flow 'dumb money' slope has the wrong sign (t +1.0) <!-- X-7eefd024 -->; sentiment-size premium OOS R^2 negative <!-- X-af59b520 -->; DAA canary +0.154 excess Sharpe over the plain rotation (+0.712 against +0.558), CI -0.187 to +0.700, fails the interval and the DSR (0.038 on the difference series) <!-- X-13bf7026 -->; 2x-leverage-above-SMA200 lower bound -1.29 bp a day <!-- X-d8b319d5 -->; LETF pair decay and interlisted parity fail their DSR <!-- X-5aa9cbcc, X-826972ac --> |
| public sources (`b6c_pub`) | 4 | 0 | 4 (2 parked) | 0 | T-405 gold COT extremes: only 20 weeks with z > 2 against 50 needed and the window cannot supply them, parked 'insufficient extremes' <!-- X-d5f4ff4a; ledger theory.parked T-405 -->; T-442 auction weeks +7.9 bps against 10, p 0.18 <!-- X-ef7cb82d -->; T-472 PHYS discount reversion 27 closed trades against 30 and the window has closed <!-- X-7c8bbcdc -->; T-404 GLD flows: returns lead flows (Granger p < 0.0001 one way, 0.99 the other), parked 'flows follow price' <!-- X-abb887f5; ledger theory.parked T-404 --> |
| stock events (`b6c_events`) | 3 | 0 | 1 | 2 | T-374 dividend-month run-up +5.6 bp net, p 0.10 to 0.16 under firm, month and two-way clustering; the 5 unpriced current members cannot flip it <!-- X-3ac4830c -->; T-334 and T-394 inconclusive on survivorship (below) <!-- X-b49ccc70, X-0bc4c55f --> |
| stock cross-section (`b6c_stockxs`) | 4 | 0 | 1 | 3 | T-375, T-393, T-451 not judged: 83-91% of their point-in-time universes have no free price (below) <!-- X-371fc97a, X-a4df2c9f, X-0040d3a6 -->; T-473 Avellaneda-Lee fails on its own survivor universe: gross excess Sharpe +0.42, costs 8.2% a year, net Sharpe -0.62 <!-- X-216a585e --> |
| crypto cross-section (`b6c_cryptoxs`) | 6 | 0 | 5 | 1 | T-314 weekly momentum on a point-in-time top-30 -0.48%/week net of 50 bps a side <!-- X-814a53e0 -->; T-420 volume-conditioned momentum -0.62%/quarter out of sample <!-- X-ac8a9fbf -->; T-400 MVRV regimes the wrong way round (-0.21) <!-- X-c450403e -->; T-402 stablecoin supply t +0.33 <!-- X-7733f62f -->; T-403 hash ribbons +0.03 over the unconditional 90-day return <!-- X-e0672102 -->; T-367 DeFi USDC carry inconclusive: the Spark and Maple charts are cut off before the window start <!-- X-bc267bb3 --> |
| crypto venues (`b6c_cryptovenue`) | 6 | 1 | 4 (1 parked) | 1 | T-366 supported as a descriptive drift (below); T-328 IBIT premium fade gross +0.18% against a 0.85% round trip, parked 'premium within AP cost band' <!-- X-220f99d4; ledger theory.parked T-328 -->; T-330 stablecoin peg fades -0.21% an episode <!-- X-541a468d -->; T-419 high-volume premium +21.1 bp against +50 <!-- X-b4c92cb5 -->; T-424 BTC-leads-alts coefficient negative, net Sharpe -6.1 <!-- X-9563b748 -->; T-365 stETH discount: 0 post-Shapella episodes above 1.5% <!-- X-62d64270 --> |
| prediction-market calibration (`b6c_pmcal`) | 6 | 0 | 6 | 0 | T-12 and T-378 below; T-31 MLP vs logit log loss 0.3727 vs 0.3713, both behind the market price 0.3669 <!-- X-85b63f4b -->; T-32 effective rank 0.73 n against 0.1 n <!-- X-9f1b8578 -->; T-359 late favourite -0.0013 per dollar <!-- X-a5f1fba5 -->; T-316 shock continuation -0.034 net <!-- X-dbdf48e1 --> |
| prediction-market cross-venue (`b6c_pmxv`) | 5 | 0 | 3 | 2 | T-409 lead-lag -3.11 cents a follow trade out of sample <!-- X-dcbbf3fe -->; T-358 event-uncertainty premium slope p 0.55 <!-- X-62ab0104 -->; T-360 Kalshi CPI nowcast -3.71 cents a contract <!-- X-57e63c0f -->; T-336 and T-337 inconclusive (below) <!-- X-00316661, X-6aab305c --> |
| prediction-market microstructure (`b6c_pmmicro`) | 3 | 0 | 3 | 0 | spreads and fees eat every edge on Kalshi: hourly reversal -2.80 cents a contract <!-- X-26fb4505 -->, market-making replay -$0.0755 a market-day <!-- X-7de80894 -->, taker-flow imbalance -4.52 cents, where the mid does not move against the taken side and the loss is two half-spreads plus two fees <!-- X-f2e6f009 --> |
| Kraken 1-minute (T-331, T-425, T-465, T-459) | 4 | [[PENDING]] | [[PENDING]] | [[PENDING]] | [[PENDING]] fetch at 26 of 58 monthly bundles at the 21:20 UTC snapshot <!-- INDEX count, 2026-10-19T21:20Z; crypto_history.py docstring --> |
| StockTwits (T-414, T-415) | 2 | [[PENDING]] | [[PENDING]] | [[PENDING]] | [[PENDING]] no batch-6c StockTwits bundle in the INDEX yet; the run is about 38 hours under its own root <!-- INDEX count; public_history.py docstring --> |
| **Recorded** | **80** | **4** | **65** | **11** | <!-- experiments.jsonl --> |

### What the four supported claims are, and are not

- **T-345, month-end rebalancing flow (supported).** In the 128 of 290 months since 2002-08 where SPY had beaten TLT by
  more than 2 pp at the third-to-last close, SPY's last-two-day return was -20.3 bps against +29.3 bps in other months:
  net of 2 bps a leg a gap of -45.6 bps (95% CI -77.4 to -13.1), permutation p 0.0022, block-bootstrap p 0.0030, both
  halves about -45 bps, and the same under the previous-close reading rule 12 requires. <!-- X-a500a4a7 --> The Holm
  p over the declared 10-trial grid is 0.0154, reported because the pass names the unadjusted p. <!-- X-a500a4a7;
  registry T-345 notes --> What it is: a conditional two-day return difference, about five signals a year. What it is
  not: a funded strategy with a Sharpe or DSR gate; none was in the pass, so none was tested.
- **T-349, IWM pre-holiday (supported, fragile).** 238 pre-holiday sessions since 2000-05-30 returned +16.2 bps against
  +3.9 bps on 6,395 other sessions, +12.3 bps, p 0.0476 against the 0.05 bar; the two-sided 95% CI is -2.7 to +27.3
  and the first half is only +2.6 bps. <!-- X-f37df8d5 --> Choices the trial does not name move it over the line: a
  non-circular moving-block bootstrap gives 0.0495 (undecided), price-only returns 0.062, an asymptotic HAC t of 1.61
  (p 0.054), and counting Friday Dec-31 sessions before a Saturday New Year 0.056. <!-- registry T-349 notes --> The
  secondary ^RUT reading from 1987 is stronger (+19.1 bps, Holm p 0.0030) and SPY's is not (+7.4 bps, Holm p 0.41).
  <!-- X-f37df8d5 --> It passes as worded and should be read as borderline.
- **T-357, presidential year 3 (supported).** On ^GSPC price returns 1928-2025, 98 complete years, year 3 of the term
  returned +13.96% against +6.20% in other years, +7.76 pp (term-bootstrap CI +0.78 to +14.22), permutation p 0.023 on
  term blocks and 0.043 anchored at 1928, 24 year-3 observations against a min_n of 20, both halves about +7.5 to +8 pp.
  <!-- X-71e7a233; registry T-357 notes --> Price only, and pre-1957 the index is the S&P 90. <!-- X-71e7a233 --> A
  descriptive cycle-year difference, not a strategy with costs.
- **T-366, cbETH staking drift (supported, descriptive).** The Coinbase CBETH-ETH ratio rose at +2.79% a year over
  1,261 days from 2023-04-12 (HAC CI +2.70 to +2.88), inside the claimed 1.5-3.5% net-staking band, positive in 100% of
  1,010 rolling 252-day windows; the refuter could not move it under any lag, price field, sampling day or estimator.
  <!-- X-adc486b0; registry T-366 notes --> It says the market discount did not eat the staking yield. Capturing it means
  holding cbETH, which is the staking yield itself, so it is a drift, not an edge. <!-- registry T-366 notes -->

### Notable results that are not supported

- **T-12, volume and calibration (not supported, but the gap is real).** On the fetcher's unbiased hash sample of 655
  resolved markets with point-in-time taker volume, Brier skill against a coin rises from 0.23 in the lowest volume
  quartile to 0.69 in the highest (Q4-Q1 0.45, CI 0.30 to 0.59), but not monotonically: Q4 0.69 sits below Q3 0.72, so the
  claim as worded fails. <!-- X-d6b6a6f4 --> Two confounds are named: 70% of Q1 markets had no trade before the decision
  (resting-book quotes), and log volume correlates 0.44 with market age. <!-- X-d6b6a6f4 --> The leaky end-of-life Gamma
  volume field shows no gap (0.11, CI -0.06 to +0.28), which retires the earlier T-01 and T-12 readings taken on it. <!--
  X-d6b6a6f4; registry T-12 notes --> This is a calibration fact about markets, not a trade.
- **T-378, near-certain carry (not supported).** Across 14,812 observations on 8,535 markets (7,783 Polymarket, 752
  Kalshi), buying the favourite at 0.95-0.99 earns an annualised net excess of +0.19 a year over the box-rate-plus-2%
  hurdle with clustered CIs above zero, yet fails the DSR (0.81 at 12 trials). <!-- X-d8389daa --> The excess is carried
  by 3.0% of observations: holds of two days or less (439 of them, mean excess 5.0 a year annualised) contribute 0.15 of
  the 0.19; longer holds earn 0.04, the dollar-weighted excess is -0.007, and Kalshi alone is -0.17. <!-- X-d8389daa -->
  An annualised number on a two-day hold is not a return anyone can compound.
- **T-337, Polymarket 'Bitcoin above' vs the Deribit digital [[PENDING]].** Every implemented criterion passes: fading
  gaps above 5 points between the Polymarket price and the Deribit-implied digital nets +4.74 cents a contract after the
  0.07 p(1-p) taker fee each way and a 1-point haircut (4,987 trades, one-sided lower bound +4.18; the cubic smile gives
  +5.11 over 4,874), gap half-life 1.4 hours, DSR 1.000 at the trial's 7 variants. <!-- X-6aab305c --> The Deribit side
  is a model-implied probability, an SVI smile fitted to near-expiry trades and cross-checked with a cubic fit under rule
  11, not a quoted contract; the strike sensitivity is +0.2% to +5.74 cents and -0.2% to +3.82. <!-- X-6aab305c --> The
  verdict was capped at inconclusive because the resolution-source basis control (Binance BTCUSDT against the Deribit
  index) had no Binance price to read. <!-- X-6aab305c --> The Binance windows were stored at 20:13:02 UTC on 2026-10-19,
  nineteen minutes after that record (19:53:59 UTC) <!-- INDEX binance-1m-BTCUSDT-btc-above created_at
  2026-10-19T20:13:02Z; X-6aab305c created_at 2026-10-19T19:53:59Z -->, and the
  harness now re-prices the digital at the Binance/Deribit basis known at each decision hour. <!-- git ebfea1c --> Re-run
  and, if supported, refutation: [[PENDING]]. One of 7,782 parsed markets resolves on Coinbase and is noted. <!-- git
  ebfea1c -->
- **T-336, Polymarket-Kalshi convergence (inconclusive).** The automated pair table (1,025 templated pairs, 991 passing
  rule checks) is not the hand-audited table the trial requires (every pair carries audited=False), and the BTC family's
  5 pm legs live 1-3 hourly points, so no 24-hour BTC window exists. <!-- X-00316661 --> On the CPI and FOMC families the
  measured halving rate is 0.766 over 1,772 episodes against a random-walk null of 0.557, but the two named trade
  constructions disagree (exit at |d| < 1 nets -3.98 cents an episode, the pure-arb hold to settlement +1.05), so under
  rule 11 that leg is undecided. <!-- X-00316661 -->

### Survivorship: what the free sources cannot price

Yahoo answers 404 for delisted and acquired names and reuses tickers, so only names still quoted have prices: about 640
single stocks, all drawn from the fja05680 S&P 500 ticker list. <!-- batch6c_stockxs.py docstring, "SURVIVORSHIP" -->
Every single-stock harness measures the share of its point-in-time universe without a usable price and, when that share
is above zero, returns None for every criterion whose answer depends on the missing names; the priced subset is computed
and reported as a survivor-only diagnostic, never as the claim's statistic. <!-- batch6c_stockxs.py docstring;
batch6c_events.py docstring, "Survivorship (rule 9)" --> That is rule 9 (a data limit is inconclusive, never an error) and
rule 2 (an unimplemented criterion caps the verdict). <!-- MANDEL.md section 2, harness rules 2 and 9 -->

Five claims are inconclusive for this reason alone, with the unpriced share measured:

| Claim | Universe | Priced | Unpriced | Survivor-subset reading (not judged) |
|---|---|---|---|---|
| T-334 S&P 500 addition reversal | 322 measurable additions 2010-2026 | 266 (82.6%), 7 of them through a rename or successor | 56: 47 with no Yahoo history under any ticker (delisted or acquired; 47 no longer in the index), 3 whose ticker Yahoo now gives to another company, 6 with no traded bar on the entry or exit date <!-- X-b49ccc70 --> | mean 20-day excess net -0.605% at 20 bps, one-sided upper bound +0.368%; the absent names would need a mean of -2.72% for the bound to clear zero <!-- X-b49ccc70 --> |
| T-394 FINRA short-volume ratio | 23,052 z > 2 events, point-in-time members 2019-2026 | 21,529 (93.4%) | 1,523: 1,435 on 67 symbols with no Yahoo history even through renames, 88 on symbols whose history misses those dates; 1,512 on names no longer in the index <!-- X-0bc4c55f --> | net +10.7 bp at 10 bps, upper bound +17.7 bp; the absent events would need -257.2 bp; the park condition 'daily SVR not informative' is undecided <!-- X-0bc4c55f --> |
| T-375 lending days-to-cover deciles | point-in-time FINRA stock universe, 152 formations 2020-2026 | 668 of 7,414 FINRA stocks per date have Yahoo prices | 90.9% of the universe (range 89.9-92.3% over 154 dates; 71.2% of names trading 1m shares a day or more) <!-- X-371fc97a --> | EW (bottom minus top) gross +0.758%, net +0.358% a month, 0.472 pp short of the 0.83% bar; VW gross +1.156%, 0.074 pp short; decile breakpoints and both legs depend on the missing names <!-- X-371fc97a --> |
| T-393 short-interest DTC | largest 1,000 stocks by point-in-time cap, 209 release periods 2018-2026 | at most 620 stocks a date have a price and a cap | 90.8% of the FINRA universe unpriced, so at least 38.0% of every date's top 1,000 is unknown <!-- X-a4df2c9f --> | net -0.048% a period (CI -0.371 to +0.290), FF5 alpha t -1.02 <!-- X-a4df2c9f --> |
| T-451 Piotroski within value | 10-K filer-years 2011-2026 in the archived SEC XBRL facts | 9,418 of 56,656 filer-years with a Yahoo price | 83.4%; the bias has no known sign, since distressed delistings fall mainly in the F 0-2 short leg <!-- X-0040d3a6 --> | L/S -2.71% a month on 71 months (56 long, 8 short positions); below min_n 150 in any case <!-- X-0040d3a6 --> |

Three more results carry survivorship in a stated way without being blocked by it. T-473 is defined on 'members with
Yahoo prices', so its survivorship is the claim's own: 622 of 903 tickers usable, 18.5% of member-days from 2010 without
a usable price, and the verdict (not supported, an upper bound) is judged. <!-- X-216a585e --> T-374's universe is current
members, as the claim states; 5 of 503 constituents (BE, P, SKYD, TWLO, VYLR) have no archived history, and the harness
shows the failure stands under every reading they could take over the whole span, while the second-half criterion alone
is undecided by them. <!-- X-3ac4830c --> T-314 is the one cross-section built on a universe with the dead included
(CoinMarketCap point-in-time rankings): it measures the survivorship inflation directly, +1.140% a week between today's
top-30 universe and the point-in-time one, and still fails. <!-- X-814a53e0 --> The ETF cross-sections (T-313, T-319,
T-420, T-462, T-471) run on declared survivor lists and say so; T-419 notes 'dead ETFs: none (Yahoo drops delisted
tickers)'. <!-- X-1fe91bd6, X-f552ce8e, X-ac8a9fbf, X-25c17354, X-ba0aaeda, X-b4c92cb5 --> T-367's DefiLlama pools are a
snapshot with dead pools absent, stated in the recipe. <!-- X-bc267bb3; crypto_history.py docstring -->

The four blocked claims (T-391, T-392, T-395, T-452) are the same limit seen before any harness ran: each needs returns for
names that no longer trade, and the triage's adversarial recheck found no free source with delisted names and a
point-in-time universe. <!-- git 8244604; registry blocked_on --> Until one exists, every single-stock cross-section on
this substrate is a survivor-only diagnostic.

### Honest summary of the batch

Of 80 claims recorded, 4 are supported and none of the 4 is a tradable edge after costs: two calendar conditional means
(one of them one bootstrap choice from undecided), one cycle-year difference on price returns, one staking drift. <!--
experiments.jsonl; X-a500a4a7, X-f37df8d5, X-71e7a233, X-adc486b0 --> The 65 not-supported verdicts fail in more
than one way, and the sign of the effect is often one of them: the Friday-minus-Monday contrast is -3.6 bps <!--
X-f408bf40 -->, TSMOM minus the historical mean -7.6 bps a month <!-- X-b6f22a08 -->, distance pairs -8.1 bp a month and
below the random-pair control <!-- X-b1d9defb -->, the fund-flow slope has the wrong sign (t +1.0 where -2 or less was
needed) <!-- X-7eefd024 -->, the MVRV regime difference is -0.206 <!-- X-c450403e --> and the BTC-leads-alts
coefficient -0.0352 <!-- X-9563b748 -->. Others carry a positive point estimate that the interval, the p-value or the
deflated Sharpe will not support: commodity momentum +0.470% a month <!-- X-1fe91bd6 -->, frog-in-the-pan +0.106% <!--
X-f2054bba -->, bond TSMOM +13.5 bp <!-- X-80f8ff58 -->, the DAA canary +0.154 Sharpe <!-- X-13bf7026 -->, auction weeks
+7.9 bps <!-- X-ef7cb82d -->, the dividend-month run-up +5.6 bp net <!-- X-3ac4830c -->. Three fail on the deflated
Sharpe and on nothing else that was judged: T-325, T-467 and T-378. <!-- X-5aa9cbcc, X-826972ac, X-d8389daa: each
'failed:' clause names only the DSR criterion --> Costs decide where the gross effect is small or zero: the weekly ETF
reversal (gross -0.000%, costs 0.295% a week) <!-- X-f552ce8e -->, Avellaneda-Lee (gross excess Sharpe +0.423, costs
8.20% a year, net Sharpe -0.615) <!-- X-216a585e --> and the Kalshi taker-flow replay (mid-to-mid gross +0.17 cents,
half-spreads 0.70 and 0.69, fees 1.43 and 1.35) <!-- X-f2e6f009 -->. Of the 11
inconclusive, five are survivorship, two want episodes that have not happened (T-365, T-311), one wants more events
(T-416), one wants chart history a source cut off (T-367), one wants a hand audit (T-336) and one, T-337, has the data it
was missing as of 20:13 UTC today and is the one prediction-market claim with an apparent edge. <!-- X-62d64270,
X-d2b172be, X-be21458b, X-bc267bb3, X-00316661, X-6aab305c; registry T-337 notes --> Six claims and the T-337 re-run are
[[PENDING]].

## 5. Next: what is parked, what is blocked, what is queued, and what it cost

*Registry at the close: 477 theories, of which 51 supported, 239 not supported, 45 inconclusive, 6 untested, 121 blocked
and 15 parked <!-- registry status counts -->. Nothing was deleted; every status below moved through a ledgered event,
and every blocked or parked line names what would move it again.*

### Parked, and why

Fifteen theories are parked <!-- registry status counts -->. Eight came out of cycle 2 and stand as they were; seven were
parked this cycle, each under the park rule its own trial wrote down before the result was seen <!-- ledger theory.parked:
15 events in all, 7 with ts >= 2026-10-15 -->. A park is not a rejection. It says the effect, where there is one, is not
worth a harness slot at this cost or this sample, and it says what would unpark it.

| Theory | Parked | Reason, as ledgered |
|---|---|---|
| T-324 SPY/IVV twin reversion | 2026-10-15 | reversion real but below retail cost: ratio AR(1) half-life 11.3 days, mean gross +0.17 bp per trade against an 8 bp round trip, net -7.83 bp (CI -9.14..-6.58), 175 trades 2010-2026 <!-- ledger seq 2473; registry T-324 parked_reason --> |
| T-389 contrarian factor timing | 2026-10-15 | adds nothing beyond static exposure (the expected outcome): 60-month z tilt minus static Sharpe -0.03 (CI -0.11..+0.04), pooled over the 3 quarterly phases, 704 months 1968-2026 <!-- ledger seq 2474; registry T-389 parked_reason --> |
| T-445 accruals after Sloan | 2026-10-15 | arbitraged away: post-publication Lo20-Hi20 +0.17%/month (CI -0.10..+0.42), FF5 alpha t 1.21, 362 months 1996-07..2026-08, against +0.38%/month before 1996-07 <!-- ledger seq 2475; registry T-445 parked_reason --> |
| T-469 BTC daily reversal | 2026-10-15 | no tradable daily reversal: conditional minus unconditional next-day excess +11.3 bp (CI -23.6..+47.2) against the 60 bp bar, 422 signals <!-- ledger seq 2476; registry T-469 parked_reason --> |
| T-405 gold COT extremes | 2026-10-16 | insufficient extremes: 872 point-in-time COT weeks 2009-10..2026-09 hold 20 weeks with z > 2 against the 50 needed, and at most 16 more reports fit the window; difference +0.04% (CI -2.90..+2.70), slope NW t +0.55 <!-- ledger seq 5905; registry T-405 parked_reason --> |
| T-404 GLD flows | 2026-10-16 | flows follow price: next-week GLD return on the 52-week z of the 4-week tonnes change, NW t -0.10 over 1,087 weeks; contemporaneous slope t +5.07; Granger returns to flows p < 0.0001, flows to returns p 0.99 <!-- ledger seq 5906; registry T-404 parked_reason --> |
| T-328 IBIT premium fade | 2026-10-19 | premium within AP cost band: 25 \|z\| > 2 fades 2024-04..2026-09, gross +0.185% per trade against the 0.85% round trip, net -0.665% (one-sided lower bound -0.69%), decisive below min_n 30; premium AR(1) 0.36, half-life 0.7 sessions <!-- ledger seq 6209; registry T-328 notes -->. The recorded result behind the park, X-220f99d4 (the registry's only T-328 result, 2026-10-19T17:02:48, verdict not_supported), counts 26 live trades at gross +0.184%, net -0.666%, one-sided lower bound -0.690% <!-- X-220f99d4 statistic.per_timing.live, tests.live.ci90; registry T-328 results -->; the park reason and the record disagree on the trade count and on the third decimal, and the lead should say which is authoritative and why they differ. |

Three of the seven found something real that cost ate (T-324, T-328, and T-445's pre-publication half); the other four
found nothing to eat. The eight from cycle 2 <!-- registry parked_reason of T-03, T-08, T-09, T-26, T-29, T-34, T-35, T-41 -->:
T-03 (no horizon shows a mean error whose interval excludes zero, so there is no structural bias to test sign-consistency
on), T-08 (a first-order Markov model on price buckets loses 0.04 bits per step to the base rate over 60 series), T-09
(MSM with k = 3 scores 1.18 nats per observation worse than 20-day rolling variance on 12 Polymarket series; unpark on the
4,411-day BTC and 8,484-day SPY histories), T-26 (a knowledge-retrieval claim with no trading value), T-29 (no claimant
source for pre-information forecasts; the standard control design already covers any that appears), T-34 (the
box-counting dimension duplicates the DFA Hurst estimate), T-35 (the Mandelbrot escape-time metaphor proposes no
falsifiable statistic; kept as a record that it was considered), T-41 (no contrarian effect of extreme crypto fear or
greed on 7-day BTC returns over 3,166 days, block-shift p 0.52 and 0.96, halves of opposite sign).

### Blocked, grouped by what would unblock them

121 theories are blocked <!-- registry status counts -->, against 132 at the close of cycle 3 <!-- REPORT-2026-10-14-cycle3.md
addendum -->. This cycle unblocked 17 by fetching what they named <!-- ledger theory.unblocked count, ts >= 2026-10-15 -->,
blocked 4 after the batch-6c triage and its adversarial recheck found no free survivorship-clean stock source
<!-- ledger theory.blocked seq 2510-2513 -->, and added 2 pre-registered forward tests that are blocked on their own clocks
<!-- ledger theory.preregistered seq 1785 (T-542), 2132 (T-543) -->; 132 - 17 + 4 + 2 = 121 (computed). The 121 blockers
are 107 distinct strings <!-- registry blocked_on distinct count -->. Grouped by the kind of thing that is missing:

| What is missing | Theories | Examples, with the smallest unit of progress each names <!-- registry blocked_on --> |
|---|---|---|
| Daily option-chain capture, which began 2026-10-14 | 50 | T-112, T-117 (30 capture days); T-118, T-120, T-122, T-537 (250 entry days including a stress episode); T-206, T-207, T-209, T-210, T-226, T-519, T-520 (two earnings seasons plus an earnings-date history); T-141, T-142 (intraday 0DTE snapshots, 120 sessions); T-165 (four quarterly SPY/QQQ ex-dates, about 340 days); T-158 (40 qualifying earnings events, 18-24 months at 10 names) <!-- registry blocked_on --> |
| Mandel's own loop has not matured | 14 | T-16, T-18, T-20 (50 decided proposals; 0 now); T-14, T-15, T-25, T-37 (registered children); T-17, T-30 (cycles with decided proposals); T-27, T-28 (scored sources beyond the three controls); T-21, T-22, T-23 <!-- registry blocked_on --> |
| Forward captures of things nobody archives | 16 | Polymarket and Kalshi books (T-335: 30 days of 60-second capture; T-407: hourly on both venues for 30 days; T-429); Deribit books with open interest (T-259: 60 days; T-513: about 26 weekly expiries); trending lists and mention counts (T-39, T-40, T-43, T-44, T-46, T-399); the House PTR index (T-457); listed futures contracts (T-371); markets resolving after 2026-10-14 (T-47: 300 sub-0.10 observations at 7 days; T-05: a question-matching table); T-542 (20 SPX capture days, 2 of 20) <!-- registry blocked_on --> |
| A survivorship-free universe | 11 | nine single-stock claims (T-307, T-338, T-339, T-340, T-391, T-392, T-395, T-452, T-455), one fund list (T-380), one coin universe (T-477) <!-- registry blocked_on --> |
| A free source that is reachable but not wired | 14 | arctic_shift Reddit history (T-412, T-413); GDELT (T-418); Wikimedia pageviews at about one call per article-year (T-466); PTR PDF parsing and the Senate eFD scrape (T-42, T-390); a single-name ex-dividend calendar (T-183); S&P DJI announcement dates (T-453, whose press-release scrape the registry marks "not verified"); wallet-level Polymarket trades (T-406); a poll archive (T-410); T-327, T-456, T-464; and T-369, which does not fit the label: IBKR publishes no downloadable history of the retail JPY rate it needs, and the institutional proxy that is computable answers a different question <!-- registry blocked_on -->. Two of the 14 therefore have no verified free source. |
| Paid, keyed or vendor-only data | 8 | CME GC/OG and ES/MES option quotes (T-200, T-201, T-276, T-277); an X API token (T-45); Glassnode SOPR (T-401); estimate history (T-396); TAQ (T-461) <!-- registry blocked_on --> |
| Limits of this host | 5 | Google Trends 429 (T-417); EDGAR 403 for shares outstanding (T-454); the data-api 10,000-row offset cap (T-460); Yahoo's 30-day minute and 60-day 5-minute depth (T-422, T-426) <!-- registry blocked_on --> |
| Other | 3 | T-355 (six halvings across BTC and LTC against min_n 8: untestable at power, with a monitoring hook per halving); T-434 (individual Treasury futures histories, and not retail-implementable); T-543 (forward event days, below) <!-- registry blocked_on --> |

Two blockers are stale in their wording, and only one of them in substance. T-456 names the CFTC files as "not in
Mandel's data list" <!-- registry T-456 blocked_on -->, and the archive now holds 10 cftc-cot-* bundles, among them the
disaggregated gold report (088691) that T-405 ran on <!-- INDEX count; X-d5f4ff4a -->; it needs a re-triage, not a fetch.
T-464 says the same of DefiLlama <!-- registry T-464 blocked_on -->, and a DefiLlama fetcher now exists
(crypto_history.fetch_defillama_yields) <!-- crypto_history.py docstring -->, but the two defillama-* bundles are the
yields pools fetched for T-367 (recipe yields.llama.fi) <!-- INDEX recipe -->, which 55ad6df records as inconclusive for
want of DefiLlama history <!-- git log 55ad6df -->; the stablecoin-supply series T-464 needs (stablecoincharts/all) is
still unfetched <!-- registry T-464 trial data; INDEX holds no such bundle -->. The
chain-capture group is the largest and the slowest: nothing in it can move faster than one capture a day, and the archive
here holds two capture days (last subsection).

### Follow-ups queued

1. **Deribit hourly book capture for T-195, T-196 and T-260.** All three ran on the two daily book snapshots and are
   inconclusive by min_n <!-- X-7163e0a9, X-1830d794, X-f43acb93 -->. T-195 parity has 88 of the 500 hourly (K, T)
   observations it needs; 0 of 88 exceed the fee threshold, but the exact-binomial upper bound is 4.11% against the 1%
   bar <!-- X-7163e0a9 -->. T-196 has 2 of 200 hourly snapshots; at mid the quarterly box lends at 499 and 538 bp
   against a 417 bp bill, at executable prices the median is -789 and -843 bp, a median excess of -1,233 bp against the
   +100 bp bar <!-- X-1830d794 -->. T-260 has 2 of 60 capture days and 0 of 2 above 200 bp at mid <!-- X-f43acb93 -->.
   history.deribit.com serves trades, not books, so no history request can fill the declared `deribit-book-hourly-BTC`
   bundle; the request is an hourly poll of `get_book_summary_by_currency` for options and futures, 168 snapshots for
   T-195 and 336 for T-196 <!-- X-7163e0a9 reason; batch6b_drb.py REQUESTS -->.
2. **Tardis from a host with its own IP.** T-260's own data bundle, `deribit-box-monthly`, is the keyless Tardis
   first-of-month ticker feed, minute 00:00-00:01 UTC, from 2019-04, about 91 capture days <!-- options_misc.py
   docstring, section 4 -->. From this shared egress host Tardis answered HTTP 429 code 277 "data transfer limit" with
   retryAfterSeconds 45,818 at about 12:03Z on 2026-10-15; one small call got through at about 12:30Z and the shared
   budget was gone again minutes later (retryAfterSeconds 51,829); the fetcher stops at the first such answer and is
   meant to run from the Linode <!-- options_misc.py TARDIS_ACCESS -->. Its licence (internal research only, no
   redistribution of raw data, no use to train or evaluate general-purpose AI models) keeps the bundle out of git and
   the raw quotes out of any LLM context <!-- options_misc.py docstring, section 4 -->. The control T-260 could run says
   the futures-basis implied rate sat above 200 bp on 0.57 of 60 first-of-month days 2019-05..2026-10 (median +276 bp),
   which is a different instrument from the claim's option box <!-- X-f43acb93 -->. The same feed would also give
   T-195 and T-196 24 hourly book snapshots per capture day <!-- X-7163e0a9 reason -->.
3. **A survivorship-free stock panel.** The free price source has no delisted names, so 83-91% of the point-in-time
   FINRA and SEC universes are unpriced and T-375, T-393 and T-451 cannot be judged; their survivor-only diagnostics are
   reported, never judged <!-- git log 55ad6df -->. T-334 priced 266 of 322 index additions (56 delisted or re-issued
   tickers have no free history) and T-394 93.4% of 23,052 z > 2 events; T-334's one-sided bound test and T-394's park
   condition ("daily SVR not informative") both turn on the missing names <!-- git log 953d219 -->; on the coin side T-314 measured +1.14% per week of survivorship inflation <!-- git log 55ad6df -->.
   What is needed is a point-in-time security master with delisted names and delisting returns. The registry's own
   candidate is EDGAR 8-K item 2.02 dates run from the user's server plus a delisted-price source <!-- registry T-338
   blocked_on -->; the SEC bulk already sits in 74 sec-* bundles, 73 of them local-only (sec-company-tickers is in git)
   <!-- INDEX count and in_git; git log a10fa1c, bb793fd -->, the prices do not.
4. **A hand-audited Polymarket-Kalshi pair table.** T-336 is inconclusive because its trial requires hand-audited pairs
   and the frozen table carries `audited: False` on every one of its 1,025 templated pairs (FOMC 110, CPI MoM 126, CPI
   YoY 156, core YoY 46, core MoM 27, BTC 555, election 5; 15 flagged timing_suspect); the automated rule checks pass
   991 <!-- X-00316661; pm_history.py docstring -->. The measured, unjudged reading is worth the audit: 1,772 episodes,
   halving rate 0.766 (Wilson lower 0.746, event-clustered lower 0.734) against a 0.557 random-walk null <!-- X-00316661 -->.
   The convergence trade is the cautionary part: exiting at |d| < 1 point loses 3.98 cents per episode (CI -4.60..-3.41)
   because the exit pays both venues' spreads and fees again on a position that converges with certainty at settlement,
   while holding to settlement nets +1.05 cents (CI +0.43..+1.77) after T-bill carry; the two constructions the trial
   names disagree, so rule 11 leaves the secondary undecided <!-- X-00316661 -->. The BTC family has no 24-hour windows
   at all (legs live 1-3 hourly points), and its two venues resolve on different sources, a Binance candle close against
   the CF Benchmarks BRTI 60-second average <!-- X-00316661; pm_history.py docstring -->. The audit fields (pm_rules,
   kalshi_rules, timing_gap_hours, basis_note) are carried on every pair for whoever does it <!-- pm_history.py docstring -->.
5. **Binance resolution klines for T-337.** [[PENDING]] The recorded verdict is inconclusive with every implemented
   criterion passing: fading |gap| > 5 points between Polymarket 'Bitcoin above' prices and the Deribit risk-neutral
   digital nets +4.74 cents per contract after the 0.07 p(1-p) fee each way and a 1-point haircut over 4,987 trades
   (one-sided lower +4.18; cubic smile +5.11, lower +4.60), gap half-life 1.4 h, DSR 1.000 at the trial's 7 variants;
   the cap was the missing resolution-source basis control <!-- X-6aab305c -->. That bundle has since been stored: 686
   resolution times 2024-03-15..2026-10-15 (490 at noon ET, 196 at 17:00 ET), a 121-bar one-minute window each plus the
   hourly candle whose close the 17:00 ET variant resolves on, 83,692 rows in all, local only <!-- git log ebfea1c; INDEX
   binance-1m-BTCUSDT-btc-above rows and in_git -->; the harness re-prices the digital at the Binance/Deribit basis known
   at each decision hour and judges the fades under both smile fits <!-- git log ebfea1c -->; the refutation was running
   at the last checkpoint <!-- git log 2defba3 -->, and no commit records the re-run itself (053fb3c re-traces the bundle
   declaration; 3cd7b4f says the klines were being fetched) <!-- git log 053fb3c, 3cd7b4f -->. The strike sensitivity
   already on record brackets the answer: +0.2% on strikes gives +5.74 cents over 5,225 trades, -0.2% gives +3.82 over
   5,557 <!-- X-6aab305c -->. This is the one prediction-market claim with an apparent edge <!-- registry T-337 notes -->;
   it is not supported until the re-run says so and a refuter fails to move it, and even then it is a per-contract
   number on a fee-only cost model, with no book depth behind it.
6. **Forward tests.** T-543 is the pre-registered forward-only version of the FOMC/CPI BTC short-straddle finding,
   MODEL-PRICED at DVOL; it counts only event days after 2026-10-15 and needs 30 of them (0 of 30 on 2026-10-15; about
   20 a year), so its first verdict is more than a year out <!-- registry T-543 -->. It was registered after the
   in-sample pooled variant showed -51.7 bps (CI -95.8..-9.9) over 109 event days 2021-04..2026-10 (FOMC 44, CPI 66);
   those days are excluded from the test, and the in-sample result is evidence for registering it, not for supporting it
   <!-- registry T-543 controls and notes -->. T-542 restates the SPX parity claim without its day-one gate and needs 20
   SPX capture days (2 of 20) <!-- registry T-542 -->. T-357, the presidential year-3 effect, is supported as worded on
   24 year-3 observations: +7.76 pp over the other cycle years (CI +0.78..+14.22), permutation p 0.0227 on term-aligned
   blocks and 0.0430 anchored at 1928, halves +7.50 and +8.02 pp <!-- X-71e7a233 -->. It is a description of 98 past
   years of price-only returns with the pre-1957 S&P 90 flagged, one decision every four years and no cost or execution
   term in its pass <!-- X-71e7a233; registry T-357 trial -->; the 25th observation arrives with the next pre-election
   year, and nothing moves it before then.
7. **Six claims still running.** Four wait on Kraken 1-minute trades: T-331 (Coinbase-vs-Kraken last-trade gap above
   0.70% in at least 0.5% of hourly marks, 2022-01..2026-09, min_n 2,000 hours) [[PENDING]]; T-425 (the
   inventory-neutral 1-minute arbitrage rule at the user's fee tier, min_n 100,000 aligned minutes) [[PENDING]];
   T-459 (5-minute signed-volume imbalance above 2 sigma, thresholds fit on 2023-24 and tested on 2025-26, min_n
   20,000 out-of-sample trades) [[PENDING]]; T-465 (VPIN's incremental R-squared for next-hour realised volatility,
   min_n 20,000 hours) [[PENDING]] <!-- registry T-331, T-425, T-459, T-465 -->. Kraken's /OHLC serves only the latest
   720 bars, so every bar is rebuilt from /Trades at about one call a second, 58 monthly bundles in about 18.6 hours
   <!-- crypto_history.py docstring -->; 26 of the 58 monthly bundles (2022-01..2024-02) were in the INDEX at the 21:24 UTC read on 2026-10-19 that
   the cost table below also uses, the latest created at 21:09:33 UTC, and the count rises while the fetch runs
   <!-- INDEX kraken-trades-1m-XBTUSD-* count and created_at, read 2026-10-19T21:24Z -->, while the Coinbase side is complete at 58 monthly 1-minute
   bundles <!-- INDEX count coinbase-1m-BTC-USD-* -->. Two wait on the StockTwits backfill: T-414 (the pre-open bullish
   ratio against the open-to-next-open sign, 14 symbols, min_n 1,200 symbol-days, accuracy at least 52% with
   permutation p < 0.01 after deflation over 16 cells) [[PENDING]] and T-415 (message intensity in a HAR-RV regression
   beside implied vol, 21 symbols, min_n 1,500 symbol-days, incremental R-squared at least 2% with t > 3 and an
   out-of-sample QLIKE gain) [[PENDING]] <!-- registry T-414, T-415 trial min_n and pass; the 14 and 21 symbols from
   public_history.py docstring, section 12 (the registry states 14 for T-414 and no symbol count for T-415) -->. StockTwits keeps a rolling year
   (max=632,500,000 returned 2025-10-15 on 2026-10-15), so the oldest day is lost every day until fetched; the bundles
   are weekly and local-only <!-- public_history.py docstring, section 12 -->, none was in the INDEX at its last write
   <!-- INDEX -->, and the last checkpoint says the fetch is in progress <!-- git log 2defba3 -->.

### What the cycle cost

The ledger is the only cost record, and for this cycle it is incomplete: there is no `cycle.started` or
`cycle.finished` row for cycle 4 (the ledger holds three of each, all for cycles 1-3) <!-- ledger kind counts -->, so the
agent and token figures the cycle-3 close recorded (40 agents, 9,000 wall-seconds, 4.15M tokens) <!-- ledger seq 1640 -->
have no counterpart yet. What the files do say, from one read of the ledger and the INDEX together at 21:24 UTC on
2026-10-19, while the Kraken fetch was still appending to both (the lead should re-derive the ledger, archive and
elapsed rows at the close from one such read):

| Measure | Cycle 4 (2026-10-15..19) | Source |
|---|---|---|
| Ledger rows | 4,499: 3,861 archive.stored, 575 experiment.recorded, 25 archive.index.repaired, 17 theory.unblocked, 7 theory.parked, 4 theory.blocked, 2 theory.preregistered, 6 forecast.recorded, 2 forecast.resolved | <!-- ledger count by kind, ts >= 2026-10-15, read 2026-10-19T21:24Z --> |
| Activity by day | 10-15: 2,183 rows; 10-16: 2,205; 10-17 and 10-18: none; 10-19: 111 (2,183 + 2,205 + 111 = 4,499, computed) | <!-- ledger count by day, same read --> |
| Experiment records | 575 across 342 harnesses: 402 not_supported, 103 supported, 69 inconclusive, 1 error (records count re-runs and previews, not theories) | <!-- experiments.jsonl, created_at >= 2026-10-15 --> |
| Harness wall time | 3,810.7 s summed over the 574 records that carry a wall_seconds value; all 575 carry a cost field, and one of them, X-4dad8586 (b6b_drb_dvol_futures_basis), has an empty one | <!-- experiments.jsonl cost.wall_seconds; X-4dad8586 cost --> |
| Archive | 3,445 bundles created this cycle, 51,133,462 rows, 1,875,866,722 bytes gzip, 3,304 of them local-only; the whole archive is 3,475 bundles and 51,307,171 rows, against 66 bundles and 395,688 rows at the cycle-3 close | <!-- INDEX created_at >= 2026-10-15; INDEX totals, same read as the ledger rows and the Kraken count above; REPORT-2026-10-14-cycle3.md --> |
| Commits | 101 since 2026-10-15 00:00 UTC, 43 of them checkpoint or WIP; first 07:16:23 on 10-15, last 20:34:19 on 10-19 | <!-- git log --since=2026-10-15T00:00:00Z --> |
| Elapsed | ledger 2026-10-15T07:09:30 to 2026-10-19T21:09:33 (seq 6246, the kraken-trades-1m-XBTUSD-2024-02 store; the last timestamp moves while that fetch runs), 4 days 14 h (computed), with two container restarts | <!-- ledger first and last ts, same read; git log b932407, 1badf89 --> |

The commit log names the roles rather than counting agents: one fixer per file and an independent checker for the
harness audit (81 confirmed findings across 9 modules; 68 confirmed on check, 13 sent to a second round; 517 tests
passing) <!-- git log bb34b14 -->, a write/review/fix/refute workflow per batch group, two independent refuters on T-262
<!-- git log a1bb713 -->, and reviewer-reproduced defects per group: 12 in batch 6a (3 verdict-changing) <!-- git log
c237062 -->, 11 in the first four 6b groups (3 verdict-changing) <!-- git log a0e8160 -->, 4 in the Deribit group
(1 verdict-changing) <!-- git log 177a434 -->, 9 and 10 in the first two 6c groups <!-- git log 6e09d78, 9399224 -->. The stocks/crypto and prediction-market 6c
groups report only their verdict-relevant defects, 4 (3 verdict-at-risk, 1 verdict-changing) <!-- git log 55ad6df --> and
3 (2 verdict-changing, 1 verdict-at-risk) <!-- git log 3cd7b4f -->, which are not comparable with those totals, and the
stock-events group states no count <!-- git log 953d219 -->. A size check after the second restart found 25 INDEX
entries that a stale concurrent writer had reverted, before the archive fix of 1892f6c, to the 2026-10-14 versions of
the 2026-10-15 07:17 refresh of the Cboe, FRED and DVOL histories; each file matched the sha256 of its latest
archive.stored event and was restored from it, with no recorded verdict change <!-- git log a166657, 1892f6c, 1badf89;
ledger seq 6136-6160 -->. The ratio MANDEL.md
asks for, validated improvements per unit of cost, is still zero over one: no proposal has been decided in any cycle
<!-- registry T-16 blocked_on: 50 decided proposals (0 now) -->.

### The standing risk

The repository is public, and 155 archive bundles are tracked in it (1,299,657 rows, 45,260,375 bytes) <!-- INDEX in_git
count and sums; git ls-files -->. The fetchers class the FRED/ALFRED, CFTC, Treasury and SEC bundles as federal public
domain <!-- git log 933c7de, bb793fd -->, DoltHub as CC BY-SA 4.0 and the OPEC dates as CC BY 4.0 <!-- git log 0e4bd29;
dolt_options.py docstring -->; fomc-meetings has been in git since 52fcde0 with no licence note in unlocks.py, like the
AQR workbook below <!-- git log 52fcde0; unlocks.py docstring has no licence note -->. Three groups were committed before any fetcher wrote the local-only rule down: 20 Cboe
bundles (the 19 volatility-index histories, first committed 2026-10-14, and the VX futures settlements, 2026-10-15;
120,078 rows, 2,316,637 bytes) <!-- INDEX; git log --diff-filter=A on cboe-VIX-history, cboe-vx-futures -->, 57
Yahoo-recipe bundles (47 daily histories, 8 hourly, 2 social-prices; 357,148 rows, 13,172,747 bytes; the first on
2026-10-14) <!-- INDEX; git log --diff-filter=A on daily-history-SPY -->, and the AQR BAB daily factor (25,369 rows,
471,265 bytes, 2026-10-15) <!-- INDEX; git log 52fcde0 -->. The fetchers written since read the same sources as not
redistributable: Cboe's website terms allow one personal non-commercial copy and nothing further <!-- cboe_strategy.py
docstring -->, and Yahoo's data carries no redistribution licence and is "local disk only, never in git"
<!-- market_history.py YAHOO_LICENCE -->; AQR's workbook terms are not recorded in any docstring <!-- unlocks.py docstring
has no licence note -->. The same reading covers the Polymarket and Kalshi bundles in git (6: five from cycle 2 and the 2026-10-15 dated
book snapshot), the Deribit bundles (9: five histories and four dated surface summaries) and the dated social captures
(10: Reddit, StockTwits, derived, crypto and House PTR, two days each); pm_history records keeping the legacy bundles as
the lead's call <!-- INDEX in_git names and created_at; pm_history.py, options_misc.py, public_history.py licence notes -->. Since 14:28 UTC on 2026-10-15
every new restricted bundle is stored with in_git=False and a test asserts it is git-ignored <!-- git log 0e4bd29 -->;
.gitignore now carries 1,950 bundle lines <!-- .gitignore count -->. What has not happened is a decision about the
bundles already in history: no ledger event, commit or docstring records one <!-- ledger kinds; git log
--since=2026-10-15; mandel/data/*.py docstrings -->, and the only written position is pm_history's note that keeping the
legacy Polymarket and Kalshi bundles in git is the lead's call <!-- pm_history.py docstring -->. Until one is made, every
push republishes them.

### The daily captures that keep running

The daily job in OPERATIONS.md runs `verify`, `social-fetch`, `options-fetch`, `options-fetch --smile`,
`book-snapshot` and `experiment-run all`, re-renders the theories and the map, and commits, at 06:40 on the Linode
(host time: OPERATIONS.md gives OnCalendar=*-*-* 06:40:00 with no timezone);
a Sunday timer runs `unlock-fetch all` for the slower histories <!-- OPERATIONS.md daily and weekly services -->. Each
pass stores 14 raw Cboe chains (AAPL, ETHA, GLD, IBIT, IWM, NVDA, QQQ, SLV, SPX, SPY, TLT, TSLA, USO, VIX) and the BTC
and ETH Deribit books local-only, with a committed surface summary per source, six social bundles and one dated
Polymarket book snapshot <!-- INDEX bundle names; options.py docstring -->. The archive in this container holds exactly
two capture days, 2026-10-14 and 2026-10-15 <!-- INDEX dated bundle names -->; whether the Linode timer has run on
10-16 to 10-19 is not visible from this clone, and the only dated bundles after 10-15 here are three batch-6c
snapshots from 10-16 <!-- INDEX -->. That capture is the clock behind the 50 chain-blocked theories, T-542 (2 of 20
days), T-66's market-priced implied move (inconclusive; first verdict about mid-December by the cycle-3 estimate)
<!-- registry T-66; REPORT-2026-10-14-cycle3.md --> and T-195, T-196 and T-260 above. Two days already decided one
thing: SPX parity failed by its day-one gate at 2.2% and passed at 0.5% on day two, which is why T-542 exists without
the gate <!-- git log 188a9c7 -->. If the timer is not running, every one of those clocks is stopped.
