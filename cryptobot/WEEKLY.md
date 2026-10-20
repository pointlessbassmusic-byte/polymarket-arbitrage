# Weekly check log

Written by a scheduled cloud session every Monday (and on forward-test read
dates). Each entry: the shadow replay of the live bounce-short on public
prices against its backtest, and any forward test whose read date has
passed and whose data is public. The desk's own books are reviewed on
the server (`./desk.sh review`, sent through the webhook every Monday).

## 2026-10-20 (first entry, written by hand)

    shadow replay of the live bounce-short 2026-10-20 (public Hyperliquid daily candles; what the desk should have done)
      DOGE  short from 2026-10-09 at 0.085345: OPEN, +7.3% so far, time exit due 2026-10-23
      kSHIB short from 2026-10-09 at 0.005465: OPEN, +8.8% so far, time exit due 2026-10-23
      closed: none yet (backtest: +3.36% a trade, 57% winners)

Forward reads due: none (next: btc-leads-us500-intraday about 2026-11-05).

