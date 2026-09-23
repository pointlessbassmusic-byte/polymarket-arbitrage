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

### Is there an edge in the data at all?

The study above says the detectors as built do not clear friction. The
prior question — does *any* signal in this data — is answered by
`python -m cryptobot.research`, which skips strategies entirely and
measures the one outcome a stop-and-target trader cares about: for every
candle, does price reach +T before −S?

A bucket is only interesting if it beats the break-even hit rate
`p = (S + cost) / (T + S)`.

**1. No barrier geometry is net positive on its own.** Sweeping nine
target/stop pairs × four horizons over the same 21 days, every one of the
36 cells loses roughly the cost:

| barrier | 24h hit | break-even | gross | net |
|---|---|---|---|---|
| +4%/−2% | 36.8% | 53.3% | +0.21% | **−0.99%** |
| +6%/−2% | 26.6% | 40.0% | +0.13% | −1.07% |
| +8%/−3% (48h) | 30.0% | 38.2% | +0.30% | −0.90% |

Gross is within noise of zero — the price process is close to driftless,
which is what it should be. The whole loss is friction.

**2. No feature bucket closes the gap.** At +4%/−2% over 24h the gap any
signal must close is 16.5pp. Across seven features × ten deciles the
largest lift is **+6.4pp** (`move_24h` d7), and the best two-feature cell
out of several hundred reaches 46.0% against a 53.3% break-even — gross
+0.76% per trade against 1.2% costs. Best case, still short.

That +0.76% independently reproduces the +0.82% break-even friction the
walk-forward study measured from actual trades. Two different methods,
same number.

**3. The selection does not survive out of sample.** This is the one that
settles it. Ranking 183 two-feature rules on the first half of the data
and scoring them on the second — measured as **lift over each half's own
baseline**, because a market that rallies in the second half lifts every
rule at once:

```
in-sample  2026-09-03..2026-09-12  base hit 26.4%
out-sample 2026-09-12..2026-09-22  base hit 47.2%
regime swing between halves: +20.8pp

correlation of in-sample lift vs out-of-sample lift:
    pearson -0.272   spearman -0.185

top-10 by in-sample lift: +6.2pp in sample -> -2.0pp out of sample
```

The correlation is **negative**. Picking the best-looking rule on past
data makes you slightly *worse* than picking at random. Any strategy
assembled by searching these features is fitting noise.

```bash
python -m cryptobot.research sweep    --cache pools.pkl
python -m cryptobot.research buckets  --cache pools.pkl --target 0.04 --stop 0.02
python -m cryptobot.research validate --cache pools.pkl   # run this before trusting anything
```

### The regime question, on a year of data

The 21-day regime swing had the magnitude to matter, so it was tested
properly: `python -m cryptobot.regime` on **six months of hourly** and
**one year of daily** candles across the same 17 tokens (the free
GeckoTerminal tier's limits). Market state is measured cross-sectionally
(breadth = fraction of tokens up over the lookback), the unit of
observation is the timestamp rather than the token, windows do not
overlap, and bucket cuts are fitted on the first half and scored on the
second.

**The state does not persist.** Autocorrelation at the first
non-overlapping lag — the number that says whether a regime lasts longer
than a trade:

| lookback | step | data | clean autocorr |
|---|---|---|---|
| 24h | 24h | 6mo hourly | −0.084 |
| 72h | 24h | 6mo hourly | −0.045 |
| 168h | 24h | 6mo hourly | −0.144 |
| 168h | 24h | 1y daily | −0.128 |
| 336h | 24h | 1y daily | −0.127 |
| 168h | 168h | 1y daily | +0.161 (n=51, within noise) |

The raw lag-1 figures (+0.74, +0.83) look like strong persistence until
set against their mechanical floor: a 7-day window sampled daily shares
6 days with its neighbour, so pure noise autocorrelates at ~0.86. The
module reports that floor alongside. Every observed value sits at or
below it.

**The state does not predict.** On one year of daily data every breadth
and median-return bucket's forward lift is within one standard error of
zero, net returns at DEX friction run −1.6% to −2.0% per trade in every
cell, and the bucket ordering flips sign between lookbacks (+0.73 at 7d,
−0.66 at 14d). The one cell that looked live on hourly data — top
7-day-breadth quartile, +14.7pp hit-rate lift on 21 observations — is
−0.1pp on the year of daily data at the same lookback.

**What the year actually was.** Equal-weight, the basket returned
**−69.6%** (median −71.4%, 0 of 16 tokens positive):

```
HIGHER -91%  BRETT -86%  TOSHI -83%  Bonk -82%  Mog -81%  MEW -81%
KEYCAT -77%  POPCAT -73%  PONKE -70%  TURBO -69%  FLOKI -66%  DEGEN -61%
DOGE -59%    SPX -54%    PEPE -52%    AERO -31%
```

That is a drift of roughly −0.3% per day. Every long-only signal in this
project — breakout, mean reversion, regime, breadth — was measured
against that current, and none of them found anything strong enough to
swim in it.

```bash
python -m cryptobot.regime --cache hourly.pkl --lookback 168 --horizon 24
python -m cryptobot.regime --cache daily.pkl --candle-hours 24 --lookback 168 --horizon 24
```

### Where this leaves the strategy

Four independent measurements — walk-forward on the detectors, barrier
sweep, feature-selection validation, regime persistence — agree. In
order of confidence:

- **Do not fund the DEX version.** Holds across every geometry, every
  feature bucket, every regime state and both halves of every dataset.
- **Entry timing from price features is a dead end.** 183 rules,
  negative selection correlation.
- **Market regime is not a usable signal at any scale from 1 to 14
  days.** No persistence beyond the mechanical overlap, no out-of-sample
  prediction, on a year of data.
- **The asset class was a −70% long over the test year.** Long-only
  memecoin strategies of any kind start from a −0.3%/day handicap. A
  fee-cheaper venue lowers the cost side of the arithmetic but does not
  touch that.

What would change the picture is a different *edge source*, not a
different parameter: short exposure (which needs a venue with perps or
borrow), cross-venue price discrepancies measured against real order
books, or an information source that is not the price series itself.
None of those are testable from candles, and none of them is what this
project currently trades.

## The first thing that survived: shorting bounces on perps

Everything above was long-only, on DEX candles, at ~1.2% friction, over
at most a year. Hyperliquid's public API (no key) serves daily perp
candles back to 2023 for 18 of the same memecoins, plus funding history,
at 0.035% taker with a short side. `python -m cryptobot.perp_study` runs
the whole apparatus on that: both sides, by calendar year, fees +
slippage + funding in the cost, timeouts scored at the realized move
rather than as a stop.

**Unconditional, nothing works.** Long loses in 6 of 7 years at every
geometry. Short wins the bear years and loses the manias — a regime bet.

**Conditional, the selection test finally passes.** In-sample lift
predicts out-of-sample lift: pearson **+0.34 long, +0.59 short** (it was
−0.27 on 21 days of DEX data). Two short rules and one long rule came
out on top; the honest test is a yearly **walk-forward** — tercile cuts
refitted each year on prior years only, benchmark = the unconditional
side over the same year:

`short: move_1d[2] & move_3d[0]` — a top-tercile up-day after a
bottom-tercile 3-day move, i.e. **short the one-day bounce in a
decline** — at ±20%/10%, 14-day horizon:

| year | coins | trades | rule net | uncond. short | lift |
|---|---|---|---|---|---|
| 2022 | 3 | 49 | +2.06% ±2.3 | +0.70% | +1.36% |
| 2023 | 6 | 55 | +2.87% ±2.0 | +0.71% | +2.16% |
| 2024 (mania) | 14 | 243 | +0.30% ±1.4 | −0.05% | +0.35% |
| 2025 | 18 | 462 | +1.38% ±1.4 | +1.25% | +0.13% |
| 2026 | 18 | 129 | +3.15% ±2.2 | +0.69% | +2.47% |

**5 of 5 years positive, beats the benchmark 5 of 5, +1.47% per trade
over 938 trades.** At the tighter ±15/5 over 7 days it is 4 of 5 (2025
flat at −0.01%), +0.60% per trade.

`short: move_7d[2] & rvol_7d[1]` — short a top-tercile 7-day rally in
mid-range volatility — is +2.07% per trade over 1,646 trades at ±20/10
but **loses the 2024 mania** (−2.27%). It reads as 6-of-6 when the
tercile cuts are fitted on the first half of the data, because that half
includes 2024; refit honestly it is 4 of 5. That is exactly the kind of
leak the walk-forward exists to catch.

`long: rvol_7d[0] & drawdown_30d[0]` — quiet and deep below the 30-day
high — beats buy-and-hold every year but nets ≈ 0 (−0.03%). Long is
still dead.

### What to be careful about

- **Survivorship in 2021–23.** Those years have 3–6 coins: the ones that
  survived to be listed. The strong years for the rule are also the
  thin ones.
- **The barrier is doing less than the drift.** At ±20/10 over 14 days
  most trades reach neither barrier, so the P&L is mostly "short for 14
  days after the pattern". The rule's job is to pick *when*, and its
  lift over the unconditional short is what shows it does.
- **Funding was a tailwind that has gone.** Mean daily funding was
  +0.104% in 2024 (shorts were paid ~0.4% per hold), +0.01% in 2025,
  −0.004% in 2026. The 2024 result would be negative without it.
- **Selection.** Chosen as the top rules of 176 per side, then swept
  across 12 geometries. Year-by-year consistency across two manias and
  two bears is the defence; it is not the same as a fresh sample.
- **Execution is assumed, not measured.** Daily-close entries, 0.05%
  slippage per side, average funding across coins. The coins the rule
  selects (just rallied) tend to carry *higher* positive funding, which
  helps a short, but their books are thinner.

```bash
python -m cryptobot.perp_study --cache hl_daily.pkl --funding hl_funding.pkl \
    --target 0.20 --stop 0.10 --days 14 --walk-forward "short:move_1d[2]&move_3d[0]"
python -m cryptobot.perp_study --cache hl_daily.pkl --funding hl_funding.pkl --validate
```

### What this means for the bot

The engine as built — long-only, DEX, five-minute volatility — trades a
strategy the data says does not exist. The one thing that has survived
every test so far is a **daily, short-side, exchange-executed** rule.
Getting from here to a fundable bot is: a Hyperliquid execution adapter
(the venue is a perps DEX, so it is still a wallet signature, no KYC), a
daily scheduler in place of the minute loop, and the same two books —
sim first — running the rule live so the paper trades accumulate against
real fills, real funding and real slippage. Roughly 100–460 trades a
year across 18 coins at +1.5% each is the ceiling the history suggests;
a $200 book risking 10% per trade would have made on the order of
$50–$150 a year, before compounding and before anything goes wrong.

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
