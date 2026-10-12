# Where things stand (2026-10-12)

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
| IBIT option surface, daily | Bitcoin volatility-premium test | since 2026-10-12; a year of rows before the test |
| Kalshi BTC / ETH / US500 hourly candles | does BTC lead the index perp off-session | 500 shared hours needed, about three weeks |
| S&P-vs-BTC divergence days | the one cross-asset pattern, out of sample | 60 qualifying days needed, years |
| earnings calendar and prices, monthly | post-earnings drift, price-scaled, sub-$2B, out of sample | from 2026-11; 24 months decide |

`python -m cryptobot.vrp_collect --state state --report` and the
dashboard's research card show the counts.

## What a key unlocks

| key | unlocks |
|---|---|
| Kalshi (needed) | the live venue |
| Alpaca paper (free) | the opening-range pilot on ten years of 5-minute QQQ bars (`python -m cryptobot.orb_study --fetch`) and daily bars for any stock test |
| tastytrade | options and CME micro Bitcoin, only if the volatility test ever passes |
| Kraken | the carry spot leg (shelved) and spot-margin shorts, which replay negative at retail fees |

Fidelity has no API; it stays a human account.

## Decided this month

Killed: Kraken margin as a venue, DOGE/SHIB/PEPE spread reversion,
stop-and-reverse, vol-targeted index trend, follow-the-S&P in BTC.
Inconclusive, recorded: overnight-only index exposure (real premium, eaten
by fees), post-earnings drift (the registered sort loses; a price-scaled
small-cap variant looks good in a biased panel and is judged out of
sample), Fed-liquidity timing, cross-asset lead-lag, stop width, BTC
beta hedge, near-resolution capture on Polymarket. Nothing new is alive.
