# Where things stand (2026-10-13)

One page for the operator. Everything here is in the registry
(`cryptobot/hypotheses.yaml`) and the research doc
(`cryptobot/RESEARCH-2026-10.md`); this is the map.

## What trades

| strategy | venue | status | evidence |
|---|---|---|---|
| bounce-short on DOGE / SHIB (PEPE when Kalshi activates it) | Kalshi perps | paper until funded and armed | inconclusive: backtest +9–15%/yr on capital, deflated Sharpe 0.13–0.35, so run small and let live fills decide |
| funding carry | shelved in the US | allocation 0 | funding on US venues averages about zero |

The allocator sizes the bounce-short from its evidence and the live
record, halves it on bad slippage, and kills it at a 25% drawdown.
Manual override is on the dashboard.

## To go live with $100–250

1. On the server: `./deploy.sh` (Docker, `.env` with a dashboard token, the
   history seed, paper trading up).
2. Kalshi: enable perpetuals on the account, create an API key, fund the
   perps balance with the amount, then `./desk.sh keys` and paste the key
   id and PEM when prompted.
3. `./desk.sh status` until every preflight line is `[ok]`.
4. `./desk.sh arm` (sets `perp.live: true` and `CRYPTOBOT_ARM_LIVE=yes`,
   restarts). The dashboard's real toggle unlocks. `./desk.sh disarm`
   goes back to paper.

All of it works from a phone's SSH app; `cryptobot/PHONE.md` is the
step-by-step, including the tunnel to the dashboard.

Never a key with withdrawal permission. Never the Hyperliquid wallet
from the US.

## What is being collected (no keys, runs inside the desk)

| series | for | state |
|---|---|---|
| IBIT option surface, daily | the volatility-premium ladder, out of sample (`btc-vrp-ladder-oos`) | since 2026-10-12; 12 months decide; the backtest itself is done (below) |
| Deribit DVOL and BTC closes, daily | the volatility-premium backtest's history and the IBIT basis | 2021-03 to date, refreshed daily |
| Kalshi BTC / ETH / US500 hourly candles | does BTC lead the index perp off-session | 100 of 500 shared hours on 2026-10-13; Kalshi serves the whole history, so `python -m cryptobot.intraday_leadlag --state state --fetch` runs it any day, desk or no desk; about 2026-10-30 |
| S&P-vs-BTC divergence days | the one cross-asset pattern, out of sample | 60 qualifying days needed, years |
| Kalshi perp order books, eight tickers every 15 s (inside the desk) | does book imbalance predict the next minutes (`kalshi-book-imbalance`, pre-registered) | 30 days decide; `python -m cryptobot.book_recorder --report` |
| Hype scanner, hourly (inside the desk): CoinGecko trending and top-100 meme volumes, StockTwits message rate for 14 coins, Fear & Greed | a mention-rate test on the Kalshi meme perps once 90 days are on file | `python -m cryptobot.hype_scanner --status` |
| 2s10s-slope-into-XLF paper pilot (Alpaca paper, inside the desk) | the one macro lead that cleared its bar, best of 48 trials | 20 trades of 20 sessions decide; `python -m cryptobot.macro_bot --report` |
| QQQ opening-range paper pilot (Alpaca paper, inside the desk) | the alive backtest against live quotes | 60 traded sessions decide (about three months); `python -m cryptobot.orb_bot --report` |

`python -m cryptobot.vrp_collect --state state --report` and the
dashboard's research card show the counts.

## What a key unlocks

| key | unlocks |
|---|---|
| Kalshi (needed) | the live venue |
| Alpaca paper (in) | the opening-range pilot ran on six years of 5-minute QQQ bars: alive in backtest (+33%/yr at 1 c/share, Sharpe 1.05); next a 60-session paper pilot; live needs a $25,000 margin account (pattern-day-trader rule) |
| tastytrade | options and CME micro Bitcoin; the volatility-premium ladder needs about $25,000 of options margin ($6,000 for a weekly version), so not at the desk's size |
| Kraken | the carry spot leg (shelved) and spot-margin shorts, which replay negative at retail fees |

Fidelity has no API; it stays a human account.

## Decided this month

Killed: Kraken margin as a venue, DOGE/SHIB/PEPE spread reversion,
stop-and-reverse, vol-targeted index trend, follow-the-S&P in BTC, and
the price-scaled small-cap earnings drift (its placebo, entering a
month after the report, beat the real entry: the names win whenever
you buy them, which is survivorship, not drift).
Inconclusive, recorded: BTC against its listed proxies (MSTR, COIN, MARA,
RIOT, CLSK: the overnight BTC move is the open gap, a 50 bp intraday
drift follows it on every name but cannot be separated from the gap's
last half hour with hourly data, COIN's residual reverts under the bar;
meme-squeeze reversal killed, squeezes continued +9% on average; short
interest nothing on a year of prints), a monthly IBIT iron condor (the one options
structure that fits $1,000: credit collected 71% of the time, one wipe
in five, Sharpe 0.37) and eight macro-to-asset leads from FRED and ETF
data (one candidate, the 2s10s slope into XLF over 20 days, best of 48
trials, sent to paper; gold vs real yields and gas momentum killed as
leads).
Profiled, 5 minutes to 37 days, every coin (addendum 25): the median
hourly move is 20–31 bp against the 18 bp round trip, a day's is
117–307 bp, a month's 1,241–1,746 bp; ranges peak 13:00–16:00 UTC and
weekends run 25–35% quieter; no hour, weekday, volume or prior-day
macro signal gives direction (the null's hit rate on 549 trials);
volume and the VIX level predict the next bar's range, which is a
sizing input, not a trade. Same-day comovement with the Nasdaq is about
110 bp per sd.
Killed (addendum 26): pricing Kalshi's hourly BTC ladder and 15-minute
up/down market from the profile's conditional dispersion; the mid's
Brier beats the model's at every decision time, vol-scaled or not, and
the model's trades lose 1–24% per dollar. Direction is unpredictable
and dispersion is already in the price. Also closed: the post-gap drift
in BTC proxies (the exact 09:30 predictor leaves t ≤ 1.2) and the
397-name universe screen (no sort clears the bar; standouts are a watch
list).
Inconclusive (addendum 27): shorting meme and small-alt froth (volume
shock plus 7-day run-up) earned +244 bp a week on Hyperliquid, mostly
listing decay, and loses on the 19 coins Kalshi lists; not tradeable
from a US account. One-minute bars: no minute-of-hour, autocorrelation
or within-hour return signal; only range persists. A forward hype
scanner (CoinGecko trending, meme volumes, StockTwits rate, Fear &
Greed) now runs hourly in the desk as a data build.
Searched and empty: 6,096 one- and two-feature barrier rules over Kalshi's
hourly perps (closed: the in-sample winners lose every month), eleven
years of hourly BTC and ten years of nine macro ETFs (inconclusive: the
walk-forward earns the market's own drift, the best in-sample Sharpe is
what the best of N null trials gives).
Inconclusive, recorded: monthly trend-following on Kalshi's index, metal
and oil perps (ten years of ETF proxies: +3%/yr after a 5%/yr carry
assumption, +8%/yr without it, long-only +6–7%/yr but every instrument
beat by buy-and-hold over a bull decade; Kalshi's real funding on those
perps is the open number), Kalshi's hourly BTC binaries (17,614 markets, 30
days: longshots overpriced and lose 35–40% per dollar, favourites
underpriced by 1.5 points, +0.4–0.6% per dollar after fees at t ≤ 1.0;
not traded), hourly rules on Kalshi's perps (26 reversal,
momentum and hour-of-day rules across 20 coins: 0–6 bp of gross edge per
hour against a 16–18 bp round trip, walk-forward −45 bp a trade; many
small trades a day lose the fee on this venue), overnight-only index
exposure (real premium, eaten by fees), post-earnings drift (the
registered sort loses), the Bitcoin
volatility premium (real, +5 vol points a month at the gate, 2021–2026 on
Deribit's index; the one-straddle version a small account can run had an
−88% month on a weekend gap into expiry, the 21-rung ladder that fixes it
needs about $25,000 of options margin and is judged out of sample from
the IBIT rows), Fed-liquidity timing, cross-asset lead-lag, stop width,
BTC beta hedge, near-resolution capture on Polymarket.
Alive: the QQQ opening-range breakout (pre-registered, one rule, 2020–2026
on Alpaca's IEX bars: +33%/yr of capital at 1 c/share, Sharpe 1.05, PSR
1.00, 2023 the one losing year). It is a leveraged day-trading rule, so
it needs a $25,000 margin account to run live; it goes to a paper pilot
on the Alpaca paper account first.
