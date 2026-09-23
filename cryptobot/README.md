# 🌊 Crypto Volatility / Memecoin Swing Bot

A second engine in this repo: instead of prediction-market arbitrage, this
module hunts **wild volatility in DEX-traded tokens** (memecoins and majors),
detects swing patterns across **5 min / 30 min / 1 h / 24 h** windows, and
rides them — paper trading by default, MetaMask-compatible on-chain execution
behind a double safety switch.

## How the pieces map to the idea

| Idea | Implementation |
|---|---|
| Price/volatility backbone | **DexScreener API** (free, covers every token a MetaMask wallet can trade, native 5m/1h/6h/24h windows) + **CoinGecko** trending for attention flow |
| 30-minute window | Built in-house: the scanner samples every tracked pair each minute and `VolatilityEngine` computes 30m moves, realized vol, and per-token z-scores |
| MetaMask as trading backbone | `execution/wallet.py` signs swaps with the same private key your MetaMask wallet uses, routed through the **0x Swap API** (the aggregator behind MetaMask Swaps). Entries buy the token with the chain's native coin; exits sell it back, with exact-amount allowances (never infinite approvals) |
| Patterns | Four detectors: volatility **breakout** (ride with trailing stop), **mean reversion** (fade a local flush), **regime shift** (quiet coin waking up, z-score based), **cross-DEX arbitrage** (same token, different pool prices, net of fees) |
| Asymmetric risk | Structural, not predictive: stops sit where the setup is invalidated (near), targets at the prior extension (far); anything under **2:1 reward/risk is refused**. Sizing is capped quarter-Kelly, additionally clipped to 0.5% of pool liquidity so your own exit doesn't become the slippage |
| Learning the edge | `analytics.py` buckets every closed trade by pattern and chain, tracking win rate, profit factor and **expectancy per dollar**. Once a pattern has ≥10 trades, its realized expectancy scales the confidence (and therefore sizing) of future signals of that type — detectors must keep paying to keep full size |
| Rug/honeypot screen | `data/goplus.py` queries the free [GoPlus Labs security database](https://docs.gopluslabs.io/reference/token-security-api) before **any** entry: honeypot flags, sell/buy taxes, unsellable positions, owner powers (pause, blacklist, balance edits). Renounced ownership neutralizes owner-power flags (so PEPE-style blue chips pass), unless a hidden owner is detected |
| Regime protections | `protections.py` ports [Freqtrade's protections framework](https://www.freqtrade.io/en/stable/plugins/): per-token **cooldown** after every close, **StoplossGuard** (4 stop-outs in 2h → global entry halt), **LowProfitPairs** (a token that keeps losing gets locked), **MaxDrawdown** (15% off equity peak → pause). Entries only — exits always run |
| Volatility management | Research on crypto momentum shows the premium survives but crashes hard unless volatility-managed. Stops widen with the token's own realized vol (ATR-style, so normal noise doesn't shake you out), and stakes scale down as realized vol rises above target, equalizing dollar-vol per position |

## Crypto vs prediction-market arbitrage — why this engine is different

The Polymarket bot in this repo captures **structural** edges: YES+NO
bundles priced below $1, or the same event priced differently on two
venues. Those edges are near-riskless once filled — the risk is execution.
DEX swing edges are **statistical**: they only exist on average, decay as
regimes change, and carry real adverse-move risk while you're in the
position. That difference drives the design here:

* stops/targets and a hard reward:risk gate replace "hold to resolution";
* the edge tracker exists because a crypto pattern that worked last month
  can stop working — realized expectancy, not backtests, sets sizing;
* liquidity hygiene matters more than price: in prediction markets the
  book is the book, on DEXes *your own exit* is the slippage;
* the only truly structural edge kept here is cross-DEX price gaps, and
  even those are gated by a fee buffer since the two legs aren't atomic
  from a wallet.

## Quick start

```bash
pip install -r requirements.txt

# one scan cycle, print signals as JSON
python run_cryptobot.py --once

# continuous paper-trading loop (1 scan/minute)
python run_cryptobot.py

# loop + live web dashboard at http://localhost:8081
python run_cryptobot.py --dashboard

# replay real history through the same detectors (GeckoTerminal candles)
python -m cryptobot.backtest PEPE BRETT --days 3
python -m cryptobot.backtest BRETT --chain base --days 7 --json
```

### The dashboard

Two books run side by side on the same live market data:

* **Simulated** — always trading, simulated money, starts at
  `sim.bankroll_usd` (default $200). This is the benchmark and the
  learning engine.
* **Real** — identical logic, but its entries also execute on-chain.
  The toggle is **locked** until `execution.live`, `CRYPTOBOT_ARM_LIVE`
  and a valid key are all in place; the UI switch is a third safety
  layer, never a way to arm anything.

Running both at once is deliberate: once real money starts, the sim book
keeps a parallel record of what the strategy *should* have made, so the
gap between the two lines is a direct measurement of real execution
quality rather than a guess.

The centrepiece is the **live decision feed**: every signal the bot
evaluated and what it did about it — including each one it declined and
which gate stopped it (cooldown, sizing, cost, rug scan). A bot that
shows only its trades hides most of its reasoning, and the skips are
where the risk controls earn their keep. A funnel beside it counts where
signals die, so you can see at a glance whether the edge is being
filtered by costs, by protections, or by the security screen.

Also shown: equity for both books, open positions with live P&L, closed
trades with the costs each one paid, the wildest multi-window movers, and
the learned edge per pattern. Light and dark follow your system theme.

Tune everything in [`cryptobot_config.yaml`](../cryptobot_config.yaml):
watchlist queries, chains, liquidity/volume hygiene floors, detector
thresholds, the asymmetry gate, and risk caps.

## Safety rails (read before going live)

Paper trading is the default and the recommended mode. Live execution
requires **all** of:

1. `execution.live: true` in the config,
2. `CRYPTOBOT_ARM_LIVE=yes` in the environment,
3. a private key in `$CRYPTOBOT_PRIVATE_KEY` — use a **dedicated hot wallet**
   with only what you can lose, never your main MetaMask key,
4. RPC URLs per chain in the config,
5. a passing `--preflight`.

A [free 0x API key](https://0x.org) in `$CRYPTOBOT_0X_API_KEY` is strongly
recommended — without it the quote endpoint is heavily rate-limited.

Even armed, every trade re-checks a hard per-trade USD cap and max slippage,
allowances are approved per-amount (never infinite), and a daily-loss
circuit breaker halts new entries.

Universe hygiene guards against the memecoin failure modes: minimum pool
liquidity and 24h volume, minimum pair age (skips the rug window), and an
FDV-to-liquidity ceiling.

**This is research/educational software. Memecoins can and do go to zero;
nothing here is financial advice.**

## Layout

```
cryptobot/
├── models.py            # snapshots, signals, positions
├── volatility.py        # multi-window engine (5m/30m/1h/24h, z-scores)
├── signals.py           # 4 detectors + asymmetry gate
├── risk.py              # capped Kelly sizing, exposure & loss limits
├── portfolio.py         # positions, trailing stops, PnL ledger
├── analytics.py         # per-pattern edge tracker → confidence feedback
├── costs.py             # round-trip cost model + net-RR entry gate
├── preflight.py         # go-live checklist (--preflight)
├── study.py             # walk-forward edge study (-m cryptobot.study)
├── protections.py       # Freqtrade-style cooldown / guards / drawdown halt
├── dashboard.py         # FastAPI live dashboard (--dashboard)
├── backtest.py          # candle replay through the live detectors
├── scanner.py           # discover → observe → detect → manage loop
├── data/
│   ├── dexscreener.py   # main price/volume/liquidity feed
│   ├── coingecko.py     # trending, majors, native-token prices
│   ├── geckoterminal.py # historical per-pool OHLCV for backtests
│   └── goplus.py        # GoPlus security DB: rug/honeypot screen
└── execution/
    └── wallet.py        # 0x buy/sell, MetaMask-key signing, private relays
```

## Backtesting honestly

`python -m cryptobot.backtest` replays 5-minute GeckoTerminal candles for
each token's canonical pool (aged pools ranked by real 24h volume — fresh
copycat pools faking liquidity are excluded) through the **same**
volatility engine, detectors, Kelly sizing, protections, and exit logic
the live scanner runs, on a virtual clock. Three limitations are stated
rather than hidden: candles carry no buy/sell split (the breakout buy-ratio
gate is neutralized, so breakout results skew slightly optimistic);
liquidity/FDV are today's values held constant; and intra-candle order is
unknown, so when a candle spans both stop and target the **stop is assumed
to hit first** (conservative). Use it to compare threshold settings, not
to project returns.

The shipped defaults were checked against an 8-token × 8-day sweep
(PEPE, BRETT, MOG, TURBO, FLOKI, POPCAT, SPX, TOSHI; ~18k candles):
the regime-shift z-score gate was raised 3→4 (win rate 46%→55%, losing
tokens 3→2, gain spread across tokens; z=5 cut winners), while the
breakout thresholds validated as-is — loosening them turned the sweep
negative, tightening lost the biggest winner. One sweep window is weak
evidence on its own; the live EdgeTracker remains the ongoing check.

## What $100–$200 can actually do

Sizing was originally fractional-Kelly on notional, which quietly broke
small accounts: on a $100 book it produced ~$3 positions, and a $3
position cannot clear gas on any chain, so **the account never traded at
all**. The fix was to size on *risk* rather than notional — a $25
position with a 5% stop risks $1.25, so position size and risk are not
the same thing:

    position = (bankroll x risk_per_trade_pct) / stop_distance

Tight stops now earn proportionally larger positions, which is exactly
what makes a small account viable. Measured over the same 8-day window:

| Bankroll | Return | Costs as % of gross |
|---|---|---|
| $100 | +0.25% | 87% |
| **$200** | **+0.45%** | **77%** |
| $500 (all chains) | −0.24% | 111% |
| $500 (base+solana) | +0.55% | 91% |

Two things follow, and both are now defaults. **$200 roughly doubles
$100's return** — not because the strategy changes, but because larger
positions amortize fixed gas better. And the chain list is restricted to
**base + solana**: BSC lost money in every configuration tested, and
Ethereum needs $200+ *per position* just to clear its own gas, which
prices out a small account entirely.

## What 21 days of real data say (read this first)

A walk-forward study over **21 days × 18 tokens** (`python -m
cryptobot.study`), with each detector run in isolation across six
consecutive non-overlapping windows:

| detector | trades | gross | costs | net | windows +/- |
|---|---|---|---|---|---|
| breakout | 2 | −$3.04 | $1.02 | −$4.05 | 0 / 2 |
| mean reversion | 0 | — | — | — | never fired in 21 days |
| regime shift | 18 | **+$2.06** | **$10.56** | **−$8.49** | 2 / 2 |

**The strategy loses money on a DEX, and the reason is not the signal.**
The regime detector's gross edge is positive (+$2.06); its costs are
$10.56 — five times larger. Half its exits were time stops: trades that
went nowhere and paid a full round trip to learn nothing.

Three things follow, none of which are fixed by tuning:

1. **Holding longer helps, but not enough.** Raising the time stop from
   6h to 48h eliminates the timeouts and more than triples gross
   (+$2.06 → +$7.09), because targets finally get a chance to be
   reached. Costs are unchanged, so net is still −$2.86.
2. **Being more selective makes it worse.** Raising the cost gate to 6×
   or 8× cuts the sample to 7 and 2 trades, both negative. There is no
   selectivity setting that rescues it.
3. **Bigger positions do not help.** At $50 on Base, gas is only ~0.2 of
   the 1.18% round trip; the rest is the DEX fee and slippage, which are
   *proportional*. Scale changes nothing.

### The edge is not established

Per-trade gross return over the best configuration: **+0.82%, standard
error 0.82%, t = 1.00, 95% CI −0.78% … +2.42%.** It is not
distinguishable from zero. Roughly 68 trades would settle it; there are
17. The single favourable 8-day window that an earlier commit reported as
"+0.45%" does not survive out of sample — which is what a walk-forward is
for.

### Where the arithmetic could work

The break-even friction for the measured gross edge is ~0.82% round trip.
Holding the same trades fixed and varying only the fee:

| venue | round trip | net on $200 / 21d |
|---|---|---|
| DEX as configured | 1.00% | −$1.35 |
| DEX 0.05% fee tier | 0.50% | +$2.87 |
| CEX taker (0.10%) | 0.30% | +$4.56 |
| CEX maker (0.02%) | 0.14% | +$5.91 |

This is **conditional on the edge being real**, which 17 trades cannot
show. It is a reason to keep measuring, not a reason to fund anything.

Re-run the study as paper data accumulates:

```bash
python -m cryptobot.study PEPE BRETT MOG SPX --days 21 --windows 6
python -m cryptobot.study --cache pools.pkl --windows 6 --hold-hours 48
```

## The cost reality

Charging realistic round-trip costs (swap fees + price impact vs pool
depth + per-chain gas) against the same 8-token window turned the gross
+$3.30 into **−$0.66 net** — the frictionless model would have lost money
live. Three mechanisms restored net profitability and are now defaults:

1. **Cost-aware entry gate** — a signal's expected move must clear 4× its
   own round-trip cost at the proposed size, and gas may eat at most 1%
   of the position per side. Consequence: Ethereum mainnet needs ≥$200
   positions to qualify; small accounts automatically concentrate on
   Base/Arbitrum/BSC/Solana where gas is cents.
2. **Breakeven ratchet** — once a trade is 2× its round-trip cost above
   entry, the stop moves to entry+costs. This alone flipped the sweep:
   the best configuration went from −$4.19 to **+$2.94 net** (62% win
   rate, positive on every traded token) because cost-bleeding time-stops
   and round-trippers became scratches instead of losses.
3. **Costs charged on every paper/backtest fill**, so the EdgeTracker
   learns net expectancy and the dashboard shows PnL net of a visible
   cost line — no fantasy numbers anywhere.

4. **Net reward:risk gate** — the asymmetry test now runs *after* costs.
   This was found by tracing a real backtest loss: two SPX trades lost
   $30.81 on price moves of only −2.6% and −2.3%, because each $333
   Ethereum position paid $7.35 round-trip. Their setup read 2.5:1
   gross — and (6.6% − 2.2%) / (2.6% + 2.2%) = **0.92:1 net**. A losing
   bet wearing a winning gate, because costs are charged on the winner
   and the loser alike and hit tight stops hardest. Gating on net
   reward:risk ≥ 1.25 fixed it, and made results *insensitive* to the
   edge-multiple setting (2×, 3× and 4× now converge on the same
   trades) — the sign of a structural fix rather than a tuned one.
5. **MEV protection** — swaps on public-mempool chains are broadcast
   through a private relay ([Flashbots Protect](https://docs.flashbots.net/flashbots-protect/quick-start)
   on Ethereum, 48 Club on BSC; both free, no key), so sandwich bots
   never see them pending. A volatile memecoin swap is precisely what
   they hunt. Trading an exposed chain without a relay is refused by
   default. Base/Arbitrum/Optimism have no public pending pool, so they
   need none — that is a real property of sequencer L2s, not an omission.
6. **Fast exit loop** — open positions are re-priced every 15s on their
   own loop, independent of the 60s discovery cycle. A memecoin can gap
   through a stop in well under a minute, and the gap between the stop
   level and the actual fill is pure avoidable cost.

Run `python run_cryptobot.py --preflight` before arming live: it checks
keys, RPCs, wallet balances, MEV relay coverage, every data feed, and
per-chain economic viability against your position caps.

## Security posture

A bot that holds a hot-wallet key and serves a web UI is worth treating
as an attack surface, so a dedicated security review was run over the
whole module. What it changed:

* **The dashboard is loopback-only and token-guarded.** It has no login,
  `/api/state` exposes the entire position book, and `/api/mode` can
  switch the bot to real money — so it binds `127.0.0.1` by default
  (`--host` to widen, with a warning) and every `/api/*` route needs a
  token generated at startup and printed in the URL.
* **Host headers are pinned.** Binding to loopback does *not* stop DNS
  rebinding: an attacker page whose hostname re-resolves to 127.0.0.1
  becomes same-origin with the dashboard. Requests carrying any other
  Host are refused with 421.
* **The rug screen requires positive evidence.** GoPlus returns thin
  records for contracts it has not analysed, and "no flags set" used to
  read as "clear" — and got cached for an hour. An unanalysed record is
  now `known=False`, is never cached, and **real money will not buy a
  contract nobody has screened** (paper still will, so the benchmark
  stays complete).
* **Swap quotes are validated before they are signed.** The signed
  transaction's `to`, `data` and `value` all come off the wire from the
  aggregator. Each quote is now checked against the request — native
  value never exceeds what was offered, the sell/buy tokens and chain
  must match, the sell amount cannot grow, `minBuyAmount` must respect
  the configured slippage, and an allowance is only ever granted to the
  same contract the transaction calls.
* Token symbols are escaped everywhere (they come from whoever deployed
  the token), and runtime state files are gitignored by glob.

## Tests

```bash
python -m pytest tests/ -v
```

`tests/test_cryptobot.py` is unit-level. `tests/test_integration.py` is
the one that earns its keep: it fakes **only** the network boundary
(DexScreener, CoinGecko, GoPlus) and drives a scripted market through the
real scanner — discovery, volatility engine, detectors, cost gating, risk
sizing, protections, portfolio, persistence and the decision journal — on
a virtual clock, asserting that a signal in at one end produces an
accounted, journalled, persisted trade at the other.

That split is deliberate. Two review passes over this module found
thirteen bugs, and nearly every one lived in the *seams* between
components rather than inside them — the fast-exit loop reading the wrong
book, a portfolio that saved but never loaded, the edge tracker fed twice
per outcome, a security screen that read silence as safety. Each unit was
individually correct; 120-odd unit tests caught none of them.

The integration tests were validated the only way that means anything:
every one of those bugs was reintroduced one at a time and the suite had
to fail. One test did *not* fail on the first attempt — it exercised two
helpers instead of the loop whose guard actually held the bug — and was
rewritten to drive the real loop until it did.
