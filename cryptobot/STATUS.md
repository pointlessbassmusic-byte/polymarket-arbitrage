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
| Kalshi hourly BTC above/below markets, settled, minute quotes (one-off pull, `python -m cryptobot.kalshi_binaries`) | are far strikes overpriced: buy the favourite at 85–97¢ half an hour before the print (`kalshi-btc-hourly-tails`, pre-registered) | 30 days, about 17,000 markets; the study runs when the pull ends |

`python -m cryptobot.vrp_collect --state state --report` and the
dashboard's research card show the counts.

## What a key unlocks

| key | unlocks |
|---|---|
| Kalshi (needed) | the live venue |
| Alpaca paper (free) | the opening-range pilot on ten years of 5-minute QQQ bars (`python -m cryptobot.orb_study --fetch`) and daily bars for any stock test |
| tastytrade | options and CME micro Bitcoin; the volatility-premium ladder needs about $25,000 of options margin ($6,000 for a weekly version), so not at the desk's size |
| Kraken | the carry spot leg (shelved) and spot-margin shorts, which replay negative at retail fees |

Fidelity has no API; it stays a human account.

## Decided this month

Killed: Kraken margin as a venue, DOGE/SHIB/PEPE spread reversion,
stop-and-reverse, vol-targeted index trend, follow-the-S&P in BTC, and
the price-scaled small-cap earnings drift (its placebo, entering a
month after the report, beat the real entry: the names win whenever
you buy them, which is survivorship, not drift).
Inconclusive, recorded: overnight-only index exposure (real premium, eaten
by fees), post-earnings drift (the registered sort loses), the Bitcoin
volatility premium (real, +5 vol points a month at the gate, 2021–2026 on
Deribit's index; the one-straddle version a small account can run had an
−88% month on a weekend gap into expiry, the 21-rung ladder that fixes it
needs about $25,000 of options margin and is judged out of sample from
the IBIT rows), Fed-liquidity timing, cross-asset lead-lag, stop width,
BTC beta hedge, near-resolution capture on Polymarket. Nothing new is
alive.
