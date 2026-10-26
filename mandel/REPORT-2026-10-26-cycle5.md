# Mandel cycle 5 report, 2026-10-20 to 2026-10-26: the learning program, the web sweep, the first paper week

## The one-paragraph version

Cycle 5 was the week Mandel put a rule on a venue and found out what a forward test measures. In seven days and
76 commits it pre-registered 198 theories (the day-to-month learning program T-577..T-580, 161 web-sweep candidates,
salvage successors and the children's forward tests), ran 116 harnesses on 116 theories (91 not supported, 16
inconclusive, 9 supported, every supported one through an independent refutation pass) and stored 45 data bundles
(1.6 M rows, 136 MB, Kraken 1-minute tape among them). The registry stands at 675 theories: 330 not supported, 210
blocked on data, 60 inconclusive, 60 supported, 15 parked, 0 untested. The learning program found no price-prediction
model that clears a taker fee across 901 symbols at any horizon from 5 minutes to 20 days (T-577, T-578, T-580), and one
robust structure: short-horizon cross-asset reversal (T-579, 225 of 604 confirmed on unseen periods, joint sign-flip p
0.0005) at 1-3 bp, below any fee. The web sweep's 82 testable strategies produced 0 supported. The four crypto
microstructure claims on the Coinbase-Kraken tape produced 0 supported: the venues sit 1.8 bp apart at the median and
nothing beyond print staleness. Meanwhile the paper runner (T-559, T-560) went live on Alpaca paper on Oct 20, hit two
execution defects in its first three sessions (a renamed ticker and a venue with no auctions; phantom spreads whose
opening orders never filled), booked its first round trips on Oct 22-23, and exposed a measurement gap: the paper venue
fills 16 minutes before the close and 3 minutes after the open, while the rules are defined on the official prints.
The first overnight trip made +0.83 on paper and would have lost 4.12 at the prints. The tracker now reports both.

## By the numbers

| | cycle 5 | cumulative |
|---|---|---|
| theories pre-registered | 198 | 675 |
| experiments recorded | 116 (91 / 16 / 9) | 1,218 |
| supported after refutation | 9 (T-548, T-549, T-555, T-556, T-569, T-570, T-572, T-574, T-579) | 60 |
| harnesses built and reviewed before first run | 82 (batch 13) + 21 modules; 4 (Kraken) re-reviewed, 6 defects fixed pre-run | |
| data bundles stored | 45, 1.6 M rows, 136 MB | 3,563 |
| child reports / guidance | 8 / 7 (first contact Oct 20, intake Oct 26) | |
| commits | 76 | |

## Headline findings

1. **No day-to-month price-prediction edge on US equities, ETFs or crypto at retail cost** (T-577, T-578, T-580;
   `mandel/ml/PROGRAM.md`). 632 walk-forward cells, target isolated, inputs at 5/15/30/45/60-minute and 1/5/20-day bars
   across price, volume, cross-asset, calendar and options-implied families. The always-long control matches or beats
   the models; implied-volatility inputs add nothing. Hurst's independent stock day-trading bot (16 trials, Oct 26)
   reached the same answer.
2. **Reversal is the only robust short-horizon structure** (T-579): 142 of 225 confirmed pairs survive a one-bar gap,
   so it is not bid-ask bounce alone - but at 1-3 bp it pays only a maker, and a maker's fill is adverse selection that
   only live orders measure.
3. **The web is not a source of untested edges.** 200 candidate strategies, 161 registered, 82 testable: 73 not
   supported, 9 inconclusive, 0 supported. 46 contradicted Mandel's or the children's settled results before testing.
4. **Coinbase and Kraken are one market at 1-minute resolution** (T-331, T-425, T-459, T-465): excursions beyond
   0.70% once in 41,545 hours; the inventory arb pays only at a $400M/month maker tier and only as the venue's own print
   reversal; flow imbalance and VPIN carry nothing. Eighth measured non-member of the reference-price class; the Fed
   decision remains the only member.
5. **A paper forward test measures the venue first and the rule second.** Alpaca paper runs no auctions, so the
   runner's fills are 15:44 ET and ~09:33 ET prints; the official-print shadow (Yahoo, keyless) now sits beside every
   round trip. Over a year the slippage column, not the P&L column, is the number that decides whether the live version
   is worth running. Expected return of the three calendar rules at $1,000: about 8% a year, index-fund-like, Sharpe
   0.6-0.8 - the forward test cannot confirm the sign in a year; it can confirm execution.
6. **Children.** Brier: weather market beats NWS on 25 of 25 dates; two-book lead-lag Polymarket->Kalshi +0.051 (t 5.3),
   not a taker trade. Shannon: NBA in-play latency closes in-play taker code for all three leagues; the G10 recorder fired
   RBNZ and ECB in October (records only). Hurst: bounce-short 2 closed at +7.7% / +8.8%, too few to judge. Kelly:
   cross-venue matching is date-ruled.

## What did not pan out, and why that is recorded

- T-425's one positive cell (+153% at the $400M+ tier) is a fill-at-next-close artefact on Kraken's own 1-minute
  reversal: 5-minute bars lose 16%, 2026 loses 5.9%, DSR 0. Written into the theory's notes so it is never read as an edge.
- T-459 could not reach a tenth of its own min_n at a 2-sigma threshold (50 trades on 8 days) and the relaxed reading
  loses; parked in effect, not to be rebuilt at a lower threshold.
- The weekly check-in's "FINRA stalled" alert was a false alarm: FINRA publishes 8 business days after settlement.

## Engineering

- Signal map build 35 s -> 4.5 s; test suite 14 min -> 4.8 min on 4 workers (`REPORT-2026-10-26-efficiency.md`).
- Paper runner: SPYM for SPLG, day orders on paper, phantom-spread discard, official-print shadow, reconcile dedupe;
  each ledgered as a `forward.amendment` before any affected fill.
- Kraken harness module: six pre-run fixes from an independent review, all in the direction of making the trading claims
  fail less easily (`harness.amended`).

## Next

- Time-gated evidence: capture-box chains for the options overlays (T-54..T-57, T-66, T-38), the paper runner's
  shadow column, the children's locked read dates (Hurst Nov 5 / Nov 12 / Dec 13; Kelly 150 tennis longshots).
- Russell preliminary lists 2026-11-13 (T-583 family).
- Evidence graph: teach `data_readiness` the publication calendars (FINRA +8 business days) to stop false stall alerts.
- Operator: re-pin the Linode to 52a1c77 (official-print shadow); add polymarket-arbitrage to Hurst's weekly routine's
  sources so its WEEKLY.md entries can push.
- Not planned: another broad discovery sweep. The registry's 210 blocked theories are blocked on data that arrives with
  time, not on ideas.
