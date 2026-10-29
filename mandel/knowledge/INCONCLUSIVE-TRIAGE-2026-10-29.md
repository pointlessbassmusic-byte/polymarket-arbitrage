# Why 60 theories are inconclusive, and what would decide them (2026-10-29)

An independent pass over every theory with status `inconclusive`, reading each one's last verdict text and trial against
the archive. Buckets:

| bucket | n | what it means |
|---|---|---|
| a registered criterion could not be decided (rule 9 / rule 11) | 40 | see the table below |
| model-priced option structure, needs real chains | 10 | T-54, T-55, T-56, T-57, T-101, T-102, T-136, T-256, T-257, T-518: decided only by the capture box's chains, months to years of them |
| capture days or expiry cycles (time) | 8 | T-38, T-66, T-173, T-194, T-195, T-196, T-260, T-503 |
| one horizon short of n | 1 | T-01 (90-day horizon at n 260 of 300) |
| data coverage | 1 | T-603 (survivorship-free panel) |

## The 40 by class

- **A, decidable now by a reading the trial text already fixes (acted on 2026-10-29, ledgered as `reading.ruling`):**
  T-633 (the permutation is the test, the bootstrap its check), T-268 ('target > 2 vol points' is a reporting target
  inside the pass's parenthesis), T-336 (the controls call (b) the pure-arb variant, so (a) is the convergence trade).
- **A, knife-edge Monte-Carlo bands left undecided on purpose:** T-741 (42-day block p 0.0494 +- 0.0013 at the declared
  100,000-draw cap), T-178 (one of six block x seed variants' upper bound +0.0018), T-164 (lower bound +0.0001). More
  draws would only pick a side of a p that sits on 0.05; undecided is the honest reading. T-238 and T-231 are superseded
  (T-534 supported, T-530 not supported) and their missing simulations are not built.
- **B, waits on time:** T-191, T-500, T-501, T-508 (3-18 more chain-capture days once the box runs), T-162 (~2032),
  T-222 (~2032), T-266 (~2027-08), T-311 (two more bear episodes), T-329 (~2029), T-414 (a StockTwits backfill of ~78
  trading days: fetch budget, not calendar), T-416 (~2039 by its own power clause), T-551 (2032-01), T-554 (months),
  T-592 (~2030-04), T-615 (~2030), T-659 (~2027-09, or the Dukascopy extension), T-690 (~2027-12 plus a CNMS re-fetch).
- **C, needs a user input or data the repo declared out of reach:** T-334, T-375, T-393, T-394, T-451, T-691, T-538
  (survivorship-free single-stock panel / constituent weights), T-367 (DeFi pool history before DefiLlama's cutoff),
  T-425 (the user's Coinbase/Kraken fee tier), T-550, T-654 (a daily full-chain SPY history the capture box could only
  build forward over years).
- **D, capped by the claim's own wording:** T-182 (its 'day one' had no archived underlying ask), T-459 (20,000 trades at
  2 sigma: centuries; parked), T-558 (rule 12's two information sets can never agree on a close-traded signal; the parent
  T-332 stands).

## Flags the reviewer raised

- Verdict possibly too generous (an at-min_n failure sits behind the undecided criterion): T-633, T-690, T-459, T-425,
  T-336 (if (a)), T-615 (under the plain 2-sd reading), T-394 (borderline, survivor universe). T-633 and T-336 are
  resolved by the rulings above; T-459 is parked; T-425 and T-690 keep rule 9's cap and their notes say why.
- Verdict possibly too harsh (every implemented criterion passes at large n; only a mechanical criterion is undecided):
  T-500, T-501, T-508, T-191 (3-18 capture days away), T-268 (resolved by the ruling, subject to the index-mark refutation
  check), T-558 (by design; see D).

Parked this pass: T-459, T-365 (its trigger has not occurred in 3.5 years).

## Addendum, the same day: what the weighting review found in the ranking itself

- `next_tests` weighted blocked theories at 0.5 and so buried T-552, whose blocking data (Kraken 1-minute through
  2026-09) had arrived on 2026-10-26. Re-run with a BRR-replication exit it passed and survived refutation. A blocked
  theory whose data has arrived should rank with the inconclusive ones.
- `data_readiness` reads 1.0 for T-376 (needs 60 SPX chain captures, 1 exists) and T-717 (paid CME FX settlements):
  it counts bundle names, not coverage. Both are false "unblocked" flags; coverage counts in `blocked_on` ("60 daily
  captures") should feed the score.
- The runner moves no theory out of `blocked` by itself (UPDATABLE excludes it) and attaches results only through the
  registry's `experiments` field: a newly built harness must be written there, or its first run records an orphan row
  (X-ffe459bb, X-09f0f769 are such rows; their re-runs X-0061ea37 and X-87957809 carry the ids).
