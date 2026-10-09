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

## Running the strategy that survived: `cryptobot.perp_bot`

The bounce-short rule now runs as its own daily bot, built to match how
it was validated rather than how the 5-minute scanner works:

```bash
python -m cryptobot.perp_bot --once                 # evaluate today, print signals
python -m cryptobot.perp_bot --dashboard --port 8082  # sim book live, hourly monitor
```

- **Daily cadence.** Once a day after 00:10 UTC it pulls closed daily
  candles for 18 Hyperliquid memecoins, refits the tercile cuts on every
  candle before today (the expanding window from the walk-forward), and
  shorts any coin whose last day is a top-tercile up-move inside a
  bottom-tercile 3-day move. Target −20%, stop +10%, 14-day time exit.
- **Two books, same as the scanner.** `sim` always trades on live data
  and is the benchmark; `real` is dormant until armed
  (`perp.live: true`, `CRYPTOBOT_ARM_LIVE=yes`, and a wallet key in
  `CRYPTOBOT_PRIVATE_KEY`). The real book records actual fills, so the
  gap between the two is measured execution cost.
- **Exchange costs on paper fills.** Taker fee + slippage each side, no
  gas. Shorts use a side-aware portfolio: stop above entry, target
  below, breakeven ratchet moving the stop *down*, and no trailing — a
  trailing short in a squeeze is how a bounded loss stops being one.
- **Execution is a wallet signature.** Hyperliquid is a perps DEX, so
  going live needs no exchange account. Orders are IOC limits at mid ±
  1% (a market order with a worst-price cap) via the official SDK,
  reduce-only on closes so a stale state file can never flip a position.
  The SDK is imported lazily; paper trading never needs it installed.
- **Restarts are safe.** Both books persist to `cryptobot_<book>_portfolio.json`
  and restore on start; a real position is never forgotten.

The dashboard is the same one, pointed at the perp bot (port 8082). It
shows the fitted cuts, the last evaluation, both books, every decision
and why.

Treat the sim book as the experiment it is. The history says roughly
100–460 trades a year at +1.5% each; a couple of hundred live paper
trades against real mids and real funding is what will say whether the
walk-forward was telling the truth.

### Does the bot trade what was validated? (`--replay`)

`python -m cryptobot.perp_bot --replay hl_daily.pkl --replay-from 2025-05-20`
drives the bot's own evaluate/consider/monitor through the cached daily
history, checking stops on each day's high and targets on its low, and
compares with the study over the same window. It is the check that the
code trades the rule, not a cousin of it. It caught three things:

1. **The breakeven ratchet.** Sized for 5-minute DEX swings, it fired
   on the first ordinary daily dip and dragged the stop to just under
   entry; 83% of trades were then scratched on the next day's high and
   one in fifty reached the target. The rule was validated with a fixed
   stop and target, so the perp books run without the ratchet.
2. **Re-entry timing decides a full percent.** After a stop-out (a +10%
   squeeze) the bounce pattern fires again almost immediately, and those
   re-entries are the losers. Making a coin eligible again 14 days after
   its last *exit* gave +0.3% per trade; 14 days after its last *entry*
   — the nearest one-position reading of the walk-forward — gave +1.2%.
   The bot uses entry-based eligibility, and that sensitivity is the
   honest width of the estimate.
3. **Time exits at the day's high.** A replay artefact — the first
   monitor tick after 14 days landed on the high phase — that cost ~5%
   on every time exit. Fixed to fill at the open, as an hourly monitor
   would.

With those settled, the bot's replay and the study agree trade for trade
(245 vs 247 trades; 77/134/34 vs 77/137/33 target/stop/timeout):

| | trades | net per trade |
|---|---|---|
| replay 2025-05 → 2025-12 | 140 | +1.00% |
| replay 2026 | 105 | +1.57% |
| **replay, whole window** | **245** | **+1.24%** |
| study, same semantics | 247 | +1.16% |

**What to expect.** The out-of-sample, one-position-per-coin figure for
this rule is roughly +1.2% net per trade with a standard error near
0.8%, on a window that was a bear market for the asset class. Small
changes in re-entry timing move it between +0.3% and +1.2%. That is a
strategy worth paper-trading, not one worth leveraging. At ~180 trades a
year it is on the order of +$2 per $10 of position per year — a $200 sim
book risking 10% per trade would have made about $40 over this window
before compounding.

### More volume, more venues? Measured

Three obvious ways to scale were checked before building any of them.

**Cross-venue arbitrage (Kraken / Coinbase / OKX / Hyperliquid).** A
two-minute live sample of eight memecoins, taking the best executable
pair each tick (buy at the lowest ask, sell at the highest bid):

| coin | gross spread, median | best net after taker fees |
|---|---|---|
| PEPE | 0.018% | −0.067% |
| WIF | 0.075% | +0.085% |
| BONK | 0.087% | +0.060% |
| DOGE | 0.036% | −0.036% |

Net of both venues' taker fees the spread is negative **91%** of the
time; the best moments are +0.06–0.09% and last seconds. Spot–spot arb
between major venues is a market-maker's business with co-location and
fee tiers this book will never have. Kraken as a *venue* is useful for
one thing here: the spot leg of a carry trade (below).

**Same rule, whole Hyperliquid universe (176 perps, 158 non-memes).**
The bounce-short walked forward on everything: 3 of 5 years positive,
beats the unconditional short in 2 of 5, −0.9% in 2023 and −0.35% in
2024, +0.88% trade-weighted only because 2025–26 was a bear. On
non-memes alone it is the same shape. Adding 158 coins multiplies trade
count by nine and turns a 5-of-5 rule into a coin-flip: the edge is a
memecoin phenomenon. More coins is more volume, not more profit.

**Funding carry (short perp, long spot).** From the funding history:

| year | mean funding/day | annualised | hours negative |
|---|---|---|---|
| 2023 | +0.056% | 20% | 38% |
| 2024 | +0.104% | 38% | 8% |
| 2025 | +0.010% | 4% | 22% |
| 2026 | −0.004% | −2% | 27% |

Holding the top-3 funding coins, rebalanced monthly, would have paid
13–22%/yr gross in the flat years and 65% in 2024, before ~7%/yr of
rebalancing cost. It is market-neutral and high-capacity, and it is
the one thing a second venue (Kraken spot) actually enables. It is also
entirely regime-dependent: the yield is whatever the crowd's leverage
appetite is, and this year it is roughly zero.

## The second strategy: funding carry (`cryptobot.carry_bot`)

Short the perp on Hyperliquid, hold the same notional of spot on Kraken,
collect funding. Market-neutral: the return is the funding rate, not
the price. It is the one thing a second venue actually enables, and it
is complementary to the bounce-short across regimes — funding pays most
in the manias where the short rule struggles.

`python -m cryptobot.carry_study --funding hl_funding.pkl --sweep` scores
the rule family (rank by trailing funding, hold the top N above a bar,
exit when recent funding turns negative) per calendar year, charging a
full round trip (perp taker + spot taker, both ways: 0.79%) on every
entry. It is far less parameter-sensitive than the bounce-short: a dozen
combinations are positive in every year with the worst year still
positive. The one chosen has the fewest entries and the lowest fee drag:

**top 3 by 14-day trailing funding · enter above 0.06%/day · exit when
the 3-day rate is negative or the coin leaves the top 6**

| year | gross funding | fees | net | annualised | entries | slots used |
|---|---|---|---|---|---|---|
| 2023 (7 mo) | 12.4% | 3.7% | +8.7% | +14.6% | 14 | 32% |
| 2024 | 49.3% | 5.5% | **+43.8%** | +43.7% | 21 | 93% |
| 2025 | 13.2% | 3.2% | +10.1% | +10.1% | 12 | 55% |
| 2026 (9 mo) | 3.4% | 1.3% | +2.1% | +2.9% | 5 | 28% |

**What the study cannot see: basis.** A carry position's P&L is funding
minus fees *plus* whatever the perp–spot spread does over the hold. On
liquid coins it is small and mean-reverting; on a memecoin during a
squeeze it can move a few percent in a day. The sim book tracks it per
position (`basis_usd`) so that, after a few months, the funding the
study promised can be compared with what the book actually kept.

```bash
python -m cryptobot.carry_bot --once                      # ranking + what sim would hold
python -m cryptobot.carry_bot --dashboard --port 8083     # sim book live
```

**On the full universe it is better, not worse.** Unlike the
bounce-short, carry is not a memecoin phenomenon: there is nearly always
*someone* paying funding. Rerun on the 150 Hyperliquid perps that have a
Kraken USD spot pair, the same rule — chosen on 18 memecoins — is again
the top-ranked set of parameters, which is an out-of-sample confirmation
of the choice:

| year | memes only (18) | Kraken-tradeable (150) |
|---|---|---|
| 2023 | +14.6% | +13.2% |
| 2024 | +43.7% | +37.7% |
| 2025 | +10.1% | +8.1% |
| 2026 | +2.9% | **+17.0%** |
| worst year | +2.9% | **+8.1%** |

68 coins were held at some point, none for more than 9% of slot-days.
The price of breadth is turnover: fees run 7–18% a year against 1–6% on
the memes-only version, so a maker spot leg (Kraken 0.16% vs 0.26%) is
worth having.

The bot defaults to that universe, discovered live (Hyperliquid perps ∩
Kraken USD pairs), re-ranks daily after 00:20 UTC, accrues funding
hourly from the live rate, and marks basis from live Hyperliquid mids and
Kraken mid-quotes. **Basis, measured.** Kraken publishes two years of daily spot candles,
so every carry trade since October 2024 can be priced on both legs
(`python -m cryptobot.basis_study`). That surfaced a live bug before it
cost anything: Kraken's **LIT** is Litentry (~$0.12), Hyperliquid's
**LIT** is a different token (~$4), and ticker matching would have
"hedged" a short in one by buying the other. One such trade showed
−63% basis on the study's history. The bot now refuses any coin whose
spot and perp prices differ by more than 3% at entry (journaled as an
`identity` skip). On today's universe LIT is the only coin it catches;
the median gap of the other 151 coins is 0.08%.

With the collision removed, 70 trades priced on both venues:

| per trade | mean | median |
|---|---|---|
| funding collected | +1.57% | +0.52% |
| basis | +0.02% (sd 0.72%, worst −3.28%) | +0.04% |
| **net after 0.79% fees** | **+0.80%** | **−0.07%** |

Basis is noise, and it does not blow out when the coin moves 30%+
(mean +0.24% on those trades). The real shape of the strategy shows in
the last row: only 34 of 70 trades beat the round trip. The money is in
the long holds; short holds mostly pay fees, so fees are the lever.

**Maker spot leg (default).** Posting the Kraken leg as a post-only
order at the touch costs 0.16% with no spread, instead of 0.26% plus
slippage. On the same 70 trades:

| spot leg | round trip | median trade | trades beating fees | annualised 2023 / 24 / 25 / 26 |
|---|---|---|---|---|
| taker | 0.79% | −0.07% | 34 / 70 | +13.2% / +37.7% / +8.1% / +17.5% |
| **maker** | **0.49%** | **+0.23%** | **46 / 70** | **+20.7% / +44.6% / +12.7% / +21.1%** |

That assumes the maker orders fill. The executor rests a post-only
order at the bid (buys) or ask (sells), re-posts at the new touch up to
three times if it does not fill within two minutes, and sends whatever
is left as a capped taker order, so a trade always completes. Every
fill records how much went through as maker, which is how the real book
will show the true fee.

A maker order can wait, so the order of operations flips on entry:
**spot first, then the perp short for exactly what filled.** A spot long
left waiting can lose at most what it cost; a short left waiting has no
ceiling. If the perp then fails, the spot is sold straight back (or
queued for retry). Exits still close the perp first.

**Real mode, both legs.** The spot leg is `execution/kraken_spot.py`:
Kraken's signed private API (HMAC-SHA512, verified against Kraken's
published test vector), IOC limit orders at mid ± 1%, volumes floored to
the pair's lot size and refused under its minimum. Real mode needs
*both* legs armed — `perp.live` and `carry.live` true,
`CRYPTOBOT_ARM_LIVE=yes`, the Hyperliquid wallet key, and
`CRYPTOBOT_KRAKEN_KEY` / `CRYPTOBOT_KRAKEN_SECRET`. Create the Kraken key
with trade and query permissions only, **never withdrawal**.

Two venues means two places to fail, and the order of operations is
chosen so the bad case is always the bounded one:

| situation | what the bot does |
|---|---|
| perp short fails | buys no spot; nothing opened |
| perp fills, spot buy fails | buys the perp back immediately |
| ...and that unwind also fails | records the position as **NAKED SHORT** in the journal and keeps managing it, rather than hiding it |
| exit: perp close fails | keeps both legs, retries next day |
| exit: perp closed, spot sell fails | queues the sell, retries every hour, persists across restarts |

Exits close the perp first because a stranded spot long can lose at most
what it cost; a stranded short cannot be bounded.

## Published strategies, tested as published (`cryptobot.factor_study`)

Four ideas from papers and open-source trading tools, each with a
concrete claim and parameters fixed *before* seeing this data. None is
tuned here, so every year is out of sample for every one of them.
Hyperliquid perps, 176 coins, mid-2023 to now, perp fees + slippage +
realised funding on every leg.

| idea | source | result |
|---|---|---|
| weekly cross-sectional momentum (long top quintile, short bottom) | Liu & Tsyvinski, NBER w25882: ~3%/week | **−0.26%/wk**, t = −0.45; 2 of 4 years positive. Liquid-only momentum and illiquid-only reversal also fail |
| crowded funding reverses (short high funding, long low) | widely repeated trading claim | **−0.38%/wk**; even gross is negative: high-funding coins kept outperforming |
| FOMO volume-spike breakout (vol > 2× 10d mean, SMA5 > SMA20, BTC > SMA20) | open-source meme-coin buy signal | apparent lift vs all days, but **against the average coin on the same day it is +0.14–0.33%, t ≤ 1.1**, 2023 negative; hedged ≈ 0. The signal times the market, it does not pick coins |
| short new listings | common claim that listings bleed | **−14% to −21% mean** (median short wins at 7d, but rare 5× listing pumps dominate). Going long is lottery-shaped and decaying |

What the FOMO signal was really carrying is its BTC-trend condition.
Isolated as "hold only while BTC > SMA50", it cuts drawdowns sharply
(2025: −17% vs −33% buy-and-hold; 2026: −18% vs −40%) and beats
buy-and-hold in 4 of 6 years, but it is a long-only market bet that
still lost 51% in 2022. It does not belong in a book built on
market-neutral carry and a short-side rule.

Used as a regime filter on the bounce-short (short only when BTC <
SMA50) it **does not help**: the rule did better in uptrends in 2024
and 2025 and worse in 2023 and 2026, every split within about one
standard error. The rule does not depend on regime, so the filter stays
out.

```bash
python -m cryptobot.factor_study --perps hl_all_daily.pkl --funding hl_funding_all.pkl
```

Sources: [Liu, Tsyvinski & Wu, Common Risk Factors in Cryptocurrency](https://www.nber.org/papers/w25882.pdf);
[weekly reversal only in small/illiquid coins](https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php);
[funding extremes as crowding](https://www.luxalgo.com/library/concept/funding-rate/);
[meme-coin volume-spike buy signal](https://www.tradingview.com/script/VGtCLwDu-Meme-Coin-Buy-Signal-Indicator-by-ashar).

## The "FOMO desk" post, in shadow (`cryptobot.launch_shadow`)

An X article (@savipww, 2026-09-23) describes a desk that scans fresh
memecoin launches every 15 minutes, kills most with hard thresholds,
asks an LLM (TypeSafe's "Jev") typed questions about the survivors, and
buys one, holding one position at a time.

What it claims cannot be checked: $89 → $7,769 in seven days with no
trade log, the best day of which came from its prediction-market side,
not memecoins; thresholds "tuned over one week"; an exit rule described
as the thing that makes it work but never given; and referral links to
the trading venue in every section. What it gets right is its own
instruction: run it in shadow for a week before trusting it.

`launch_shadow` does that for the part public data can test. It never
trades. Every 15 minutes it pulls trending pools on Solana, BSC and Base
from GeckoTerminal, keeps launches aged 15 minutes to 72 hours, and
records the first sighting of each pool in three groups:

- **fresh**: every launch in the window (the baseline);
- **hard**: passes the article's thresholds verbatim: liquidity ≥ $12k,
  24h volume ≥ $40k, market cap $60k–$8M, ≥ 150 trades, not the
  buys-without-sells trap;
- **crowd**: also passes a stated stand-in for the LLM's "crowd"
  judgement: buys > sells over 30m and 1h, and the last hour no more
  than half of the last six hours' volume.

It then prices each recorded pool at +1h, +4h and +24h. A pool that has
vanished counts as −100%. The filter only earns its place if its group
beats the baseline observed over the same hours. The holder checks (top
wallet, top-10 share, holder count) and the LLM itself are not tested;
they need the article's logged-in FOMO session.

```bash
python -m cryptobot.launch_shadow --state launches.jsonl            # leave running
python -m cryptobot.launch_shadow --state launches.jsonl --report   # results so far
```

### What the shadow run showed (two evenings, Oct 2–3 2026)

Holding filtered launches for 24 hours lost money: median −21% for the
post's filters, −42% for every fresh launch. The post's missing exit
rule is where any edge would have to be, so `--exits` replays every
recorded launch through its 5-minute candles under 36 rules (take
profit +20/+50/+100%/none × stop −15/−30%/none × sell after 1/4/24h).
A candle that opens through the stop fills at its open, because
memecoins gap. The rule is chosen on the first evening and scored on the
second; choosing on all the data would find a lucky rule.

| | picked on Oct 2 (mean) | tested on Oct 3 (mean) | every fresh launch, same rule, Oct 3 |
|---|---|---|---|
| post's filters: tp +100%, no stop, 4h | +11.7% (n=47) | **+13.8%** (n=47) | **+18.1%** (n=70) |
| my "many buyers" stand-in: no tp, stop −30%, 4h | +16.2% (n=19) | +12.5% (median −30.6%) | +213.5% (one launch) |

Two findings, both from far too little data to trade on:

- **The exit matters, not the filter.** Selling within four hours turned
  the 24-hour losses into gains on both evenings, out of sample. But
  buying every trending launch with the same exit did as well or better.
  Across all 36 rules the post's filter beats the unfiltered baseline in
  20, a coin flip; the "many buyers" stand-in in 4.
- **The returns are carried by a few launches.** Means are positive while
  medians hover near zero or below, and single launches move the
  averages by hundreds of percent. That is lottery-shaped, the same shape
  that made shorting new perp listings fail.

Two evenings of one market mood cannot separate an edge from a good
week for launches. Venue fees (FOMO's own) are not included, and entry
assumes the scan's snapshot price, which a real order would not get.

```bash
python -m cryptobot.launch_shadow --state launches.jsonl --exits candles.pkl
```

## Polymarket "Bitcoin Up or Down": two X posts, tested (`cryptobot.updown_study`)

Two posts (@RetroValix, @Dan1ro0, Oct 2026) describe bots on Polymarket's
15-minute "Bitcoin Up or Down" markets, which pay $1 a share to Up if
Chainlink's BTC/USD price ends at or above where it started:

1. **Fair value + hedge-to-lock** (account "mo-money", "+$470,883"):
   price each side with a model (BTC vs its open, time left,
   volatility), buy the cheap side, then buy the other side when the
   pair can be completed for under $1.
2. **DMI/ADX** ("+$809,704"): buy the side whose directional index
   (+DI or −DI) dominates when ADX > 25.

Both posts carry referral or product links and neither shows how its
account's results arose. The test is against what Polymarket actually
quoted: 2,100 resolved BTC 15-minute markets (Sep 13 – Oct 5 2026), each
with its ~1-minute price history, plus 1-minute Coinbase BTC candles
(`cryptobot.updown_data`). Costs are Polymarket's taker fee,
**0.07 × p × (1 − p) per share** (3.5% of the stake at 50¢; makers pay
none), plus half a cent of spread. Settings are chosen on the first 11
days and scored on the last 11.

**A trap worth knowing.** The first run showed taker profits of +12% to
+39% per dollar out of sample. That was an artefact: quotes print about
once a minute, and comparing a model fed BTC's price *now* against a
quote up to a minute old makes the market look slow. Fixed so the
information test only gives the model BTC data from before the quote's
timestamp, and trades fill at the first quote printed after the
decision:

| at 5 min before close (10 and 2 min are similar) | test half (Sep 24 – Oct 5) |
|---|---|
| market price is calibrated? | yes: priced 0.6 → won ~0.59 |
| fair-value model adds information? | no: log loss 0.4294 → 0.4338 (worse) |
| taker on model edge | **−7.2% per $**, 1 of 12 days up |
| + hedge-to-lock | **−9.4% per $**, win rate 56%, 1 of 12 days up |
| maker bid at fair value − margin | **−31% per $** (filled when price falls through it) |
| DMI/ADX > 25, as posted | **−2.9% per $** despite a 74% hit rate |

What this means:

- **The market already prices the public information.** The fair-value
  model and DMI only restate what the current price says. DMI's high hit
  rate is the trend the price has already absorbed, and the fee takes
  the rest.
- **Hedge-to-lock buys consistency, not profit.** It turns fewer large
  losses into many small wins and occasional large losses: the win
  rate rises, the return does not.
- **The only edge visible is speed.** The stale-quote artefact shows
  the printed prices *did* lag BTC. Capturing that needs a live order
  book and a BTC feed measured in seconds or less, competing with
  professional market makers. That is plausibly what an "HFT" account
  like mo-money does; it cannot be tested on minute data and is not a
  realistic edge for this bot.

```bash
python -m cryptobot.updown_data --out updown_15m.pkl --days 30
python -m cryptobot.updown_study --data updown_15m.pkl
```

### Moonbags: "sell 60% at 2×, let the rest ride" (@0xNevsky)

The post's rule, "$100 → $4,216 overnight": sell 60% at 2× (which
returns 1.2× the entry, so the rest is "free"), keep 40% running. Tested
on the same 139 recorded launches, with 5-minute candles, as a
scale-out exit (`exit_scaled`, 40 variants: sell 50/60/100% at 2× or 3×,
optional −30% stop before the take, the bag held or trailed 50% from its
peak, 4h or 24h):

| every fresh launch | mean/trade | without top 3 trades | top 3 share of profit | typical median |
|---|---|---|---|---|
| post's rule: 60% at 2×, −30% stop, bag held 24h | +53.5% | **−4.9%** | **109%** | −30.7% |
| 50% at 3×, bag trails 50%, 4h (best moonbag) | +88.4% | +15.1% | 83% | −5% to +16% |
| all out at 3×, 24h | +13.2% | +9.1% | 33% | −27% to −58% |

Moonbags raise the average by keeping the rare 25–55× runner, and that
is all they do: the post's own rule loses money without its three best
trades. They make returns **less** consistent, not more. Selling
everything at the target has the smallest mean and the least
dependence on any single trade. 139 launches over two evenings; entry
at the scan's snapshot price and no venue fee, both optimistic.

## Negative results, kept (`cryptobot.hypotheses`)

Every idea tested here, the dead ones included, is in
`cryptobot/hypotheses.yaml` with its source, claim, test, data, result,
verdict and the command that reproduces it: 23 so far, 2 alive (the
bounce-short and funding carry), 1 adopted, 17 killed, 3 inconclusive.
Check a new idea against it before testing:

```bash
python -m cryptobot.hypotheses --similar "sell 60% at 2x and hold a moonbag"
python -m cryptobot.hypotheses --verdict alive
```

## Running it: the trading desk (`cryptobot.desk`)

Both surviving strategies run in one process, each on its share of the
bankroll (`allocation:` in the config, 50/50 by default), behind one
dashboard:

| path | what |
|---|---|
| `/` | both strategies' sim and real equity, and the total |
| `/bounce/` | bounce-short dashboard |
| `/carry/` | carry dashboard |

One token guards every API route, mounted ones included. The books
persist in the state directory and are restored on start.

**Locally:**

```bash
python -m cryptobot.desk                        # paper trade both; prints the dashboard URL
python -m cryptobot.desk --preflight            # what real money needs, and what is missing
```

**On an always-on machine** (the sims need weeks of uninterrupted
uptime to say anything; a laptop that sleeps will not do). One command
does all of the below on a fresh Ubuntu/Debian server such as a Linode:

```bash
git clone https://github.com/pointlessbassmusic-byte/polymarket-arbitrage && cd polymarket-arbitrage
git checkout claude/crypto-arbitrage-volatility-bot-qic8gv
./deploy.sh          # installs Docker, writes .env with a random token, builds the seed, starts paper trading
```

Or by hand:

```bash
cp .env.example .env                            # set CRYPTOBOT_DASH_TOKEN at least
docker compose up -d                            # restarts on crash and reboot; state in ./state
docker compose logs -f                          # dashboard URL
docker compose run --rm desk python -m cryptobot.desk --preflight
```

The port is published on 127.0.0.1 only. From elsewhere, use an SSH
tunnel (`ssh -L 8080:localhost:8080 your-server`) rather than opening it.

**Going live** is a checklist, and `--preflight` checks every line:

1. `perp.live: true` (and `carry.live: true` when carry has capital);
2. `CRYPTOBOT_ARM_LIVE=yes`;
3. the venue key: a Coinbase CDP trade-only key
   (`CRYPTOBOT_COINBASE_KEY_NAME` / `_SECRET`) on `perp.venue: coinbase`,
   or a **dedicated** Hyperliquid wallet key (`CRYPTOBOT_PRIVATE_KEY`);
4. with carry on, a Kraken key with trade and query permissions only,
   **never withdrawal** (`CRYPTOBOT_KRAKEN_KEY` / `_SECRET`);
5. `perp.max_trade_usd` at least the largest planned order (otherwise
   orders are capped and positions undersized);
6. each venue funded: carry's spot leg on Kraken, carry's perp margin
   plus the bounce-short's capital on Hyperliquid. For a $1,000 real
   bankroll split 50/50 that is $225 on Kraken and $725 on Hyperliquid.

On Coinbase, once the key is in `.env`, `--preflight` also asks the venue
to price one contract of each coin (a preview, nothing is placed) and
reports the real fee and margin, or the rejection reason. That is the
whole order path exercised against the live account before any money
moves.

Once armed, the real book **reconciles** against the venue on start and
every hour: the positions Coinbase (or Hyperliquid) reports are compared
with the book, and any difference (a position the venue has that the
book does not, or the reverse, or a size that disagrees) is logged,
journaled and shown on the dashboard's mode line. Nothing is fixed
automatically: a mismatch means an order went through that the bot did
not record, or a trade was made by hand, and which side is right is
your call.

**Alerts.** Set `CRYPTOBOT_ALERT_WEBHOOK` in `.env` to a Discord or
Slack incoming-webhook URL and the desk pushes what a human must hear
about: every real fill and exit with its P&L, order failures,
reconciliation mismatches, daily-loss halts, and startup. Paper-book
decisions stay in the journal. A failing webhook is counted and logged,
never allowed to interrupt trading.

Once a day (`desk.digest_utc`, default 00:30 UTC, after the daily run)
the same webhook gets a digest: equity and return per book, what closed
with its P&L, what is open, halts and drawdown, the sim-vs-real gap in
percentage points, and any venue mismatch. `python -m cryptobot.desk
--digest` prints the same thing from the saved books.

**Execution log.** Coinbase keeps no fill history beyond single orders
and no funding history, so the real book writes its own:
`state/execution.jsonl` gets every real fill (signal price vs fill
price as adverse basis points, modelled fee vs the fee the venue
charged), every funding accrual on a real position, an hourly margin
snapshot (every tick within half an hour of the 16:00 ET
intraday-to-overnight switch, flagged), and every real-book skip.
`python -m cryptobot.execlog --state-dir state [--days 30]` summarises
it; the daily digest carries a one-line version. That report is what
the small-real-money gates in `RESEARCH-2026-10.md` ask for.

Then switch each dashboard's toggle to real. The sim books keep running
alongside, so the gap between sim and real is measured execution cost.

## Research sweep, October 2026

`cryptobot/RESEARCH-2026-10.md` records a sweep of public repositories,
papers, practitioner write-ups, free data and the US venue landscape:
41 candidates, 14 shortlisted, each verified through three lenses. The
short version: nothing public offers a credible, costed, out-of-sample
edge a US retail account can trade that this project has not tested;
the two items that mattered were the selection-bias diagnostics below
and the Coinbase cost/margin corrections above. The file also holds the
small-real-money protocol and the no-constraints design.

The first rule tested under the new pre-registration protocol
(`cryptobot/PREREGISTER.md`) was the sweep's one untested alpha
candidate, BTC's outside-US-hours seasonality: criterion written first,
one trial, result inconclusive (PSR 0.84, post-publication window flat).
The registry now refuses an `alive` verdict that does not record the
size of the search behind it.

## How credible is the bounce-short? Correcting for the search

Every walk-forward year was positive, and that was presented as strong
evidence. It is weaker than it looks, for a reason that has nothing to
do with the data: the rule was the best of a search. Across this
project 4,512 (feature-pair × tercile band × barrier geometry × side)
trials were scored on the same 18 coins, and the best of thousands of
noise trials also has positive years. `cryptobot/stats.py` measures how
much of the result that explains, using the standard tools (Bailey &
López de Prado's Probabilistic and Deflated Sharpe ratios, CSCV
probability of backtest overfitting, combinatorial purged
cross-validation, minimum track record length):

| | 18 coins (fees + funding) | DOGE/PEPE/SHIB (flat 0.40%) |
|---|---|---|
| trials searched / effective independent | 4,512 / 28.7 (short-only 10.5) | 4,512 / 59 (short-only 26) |
| CSCV probability of overfitting (PBO) | 0.22 (short-only 0.12) | 0.09 (short-only 0.21) |
| rule's out-of-sample rank in the family | 0.74; never in-sample best; **0.57 within shorts** | 0.90; never in-sample best |
| rule's own PSR (P(Sharpe > 0)) | 0.91 | 0.99 |
| Deflated Sharpe at nominal N / at N_eff | 0.00 / 0.18–0.35 | 0.00 / 0.13–0.34 |
| cross-sectional lift over same-day basket | +0.002%/trade (zero) | −0.001%/trade (zero) |
| CPCV (6×2, purged, embargoed) | 5/5 paths, 15/15 splits positive | 5/5 paths, 14/15 splits positive |
| MinTRL to show SR > 0 at 95% | ~104 months | ~32 months |

Reading it plainly:

- **The family is not a CSCV overfit** (PBO well under 0.5) and the
  rule's performance **is stable under refitting and purging** (every
  CPCV path positive). Shorting memecoin perps at wide barriers paid in
  most cells during 2022–23 and 2025–26.
- **The specific rule's selection is not statistically credible.** It
  was never the in-sample best in any of 252 splits; within the
  short-only family on 18 coins it is a median column; its own Sharpe is
  not significant at 5% on 18 coins; and after deflating for even the
  most generous count of independent trials (~10–26) the probability
  that its Sharpe beats what the best null trial would show is 0.18–0.35.
  A t-stat of 1.3–2.3 is exactly what the best of a few dozen
  independent noise trials produces.
- **The edge, where it exists, is timing, not coin selection.** On the
  days the rule fires, the coins it picks net +0.95% per trade and the
  coins it does not pick, shorted the same day, net +0.89%. "Beats the
  unconditional short" is a statement about *which days* to be short
  the memecoin basket. The one-slot-per-coin logic is not picking coins.
- **The live record cannot settle it for years.** With ~2 months of
  paper trades, the sim P&L is noise either way; the desk digest now
  reports trades logged against the minimum track record needed.

One more caveat the diagnostics do not cover: **the universe is chosen
with hindsight.** The 18 memecoins are the ones listed on Hyperliquid
in 2026. Coins that were delisted after collapsing are missing, which
for a short strategy hides its best trades and biases the backtest
against the rule; coins that survived because they rallied (PEPE in
2023) are over-represented, which biases it the other way. The nearest
test is the registry's `bounce-short-all-perps` run on all 176 current
perps: 3 of 5 years positive and the benchmark beaten in 2, weaker than
the memecoin subset. Until a point-in-time listing history exists, the
18-coin numbers should be read as the optimistic end of the range.

Both bounce-short entries in the registry are therefore
**inconclusive**, not alive. That is not a kill: the mechanism is
plausible, costs are realistic, and CPCV is clean. It means expected
live returns should be shrunk hard toward zero relative to the backtest
tables above, real capital should stay at a size whose loss is
tolerable while the record accumulates, and the verdict rule for every
future idea is written into the registry: *alive* needs DSR ≥ 0.95 at
N_eff, PBO ≤ 0.5 and ≥ 80% of CPCV paths positive.

## Running the desk with real money: allocation, learning, loss limits

You load money; the desk decides how much of it each strategy may use,
trades, and reports. The design follows what the diagnostics showed:

**What live trading teaches fast** (weeks): execution cost, fill
quality, venue reliability, reconciliation, drawdown. The desk measures
all of it (`state/execution.jsonl`, the digest, the dashboard) and acts
on it: slippage worse than modelled halves a strategy's weight; a venue
mismatch is flagged; a drawdown past the limit stops new entries.

**What live trading cannot teach fast** (years): whether the edge is
real. The bounce-short needs 32–104 months of track record to show its
Sharpe is above zero. So the allocator never chases a good month.

**The allocator** (`cryptobot/allocator.py`, hourly, and on every change
you make) sets each strategy's weight from

    prior      = backtest mean per trade × confidence
                 (confidence is the registry's Deflated Sharpe or PSR: 0.34
                 for the bounce-short, so the backtest is believed a third)
    posterior  = (50 × prior + n_live × live mean) / (50 + n_live)
    f*         = posterior / sd²                 (Kelly fraction)
    weight     = clamp(f* × ½, learning floor 50%, 100%)

and then applies hard gates: registry verdict `killed` → 0; no armed
executor → 0 (paper only); real equity 25% below its peak → 0 and a
**KILL** that only you can clear (the dashboard's *resume* button);
mean adverse slippage above 50 bp over 10+ fills → halved. Every weight
comes with its reason on the dashboard. Five live trades move the
posterior by 5/55; a strategy earns more capital by accumulating
evidence, not by a streak. With one strategy and $200 that means: half
deployed while learning, all of it only once live evidence has raised
the posterior, nothing after a 25% drawdown until you look at it.

**Execution is tuned from live fills** (`cryptobot/exec_tuner.py`,
hourly): the executors send immediate-or-cancel limits at mid ± a
distance; unfilled orders above 20% of attempts widen it by a quarter,
fills sitting well inside the limit with almost no misses tighten it,
one change a day, floor 0.1%, cap 2%, persisted across restarts and
explained on the dashboard's execution card. This is the one parameter
live data can settle in days rather than years. A watchdog raises an
alert when a bot's daily run is more than 26 hours overdue, and
`GET /health` (no token; no balances or secrets) lets an uptime monitor
notice a dead desk.

**Taxes.** `python -m cryptobot.taxlots --state-dir state --year 2026
--out lots.csv` writes one row per closed real trade (quantity, open and
close times, proceeds, cost basis, modelled and venue-reported fees,
funding, net P&L). These contracts are not Section 1256 instruments and
1099-DA reports proceeds without basis, so this file is the basis
record.

**Manual mode**: set weights on the dashboard (they must add up to 100%
or less; the rest is cash). The gates still apply. *Back to auto*
returns control to the allocator.

**Compounding** comes from reading capital from the venue every hour:
weights apply to what the account actually holds.

**Changing strategies**: the lab on the dashboard shows every idea in
the registry with its verdict and evidence. A new strategy gets capital
when it is pre-registered (`PREREGISTER.md`), tested, given a bot with
an executor, and listed under `strategies:` in the config with its
backtest numbers and confidence; the allocator then sizes it against
the others. Nothing is funded on a backtest alone: the confidence term
is what the diagnostics say the backtest is worth.

**For $100–250** the venue is Kalshi (`perp.venue: kalshi`): DOGE and
SHIB contracts of ~$5–8, so every slot fits whole. Coinbase needs
~$6,000 to hold all three of its contracts; below that it is a SHIB-only
book. If your Kalshi account does not yet have perps access
(`--preflight` checks `/margin/enabled`), run Coinbase with SHIB until it
does.

**The dashboard** (`python -m cryptobot.desk`, or `./deploy.sh` on the
server): capital and allocation with reasons and controls, real and
paper equity curves, each strategy's books, evidence and track record,
venue reconciliation, execution quality from real fills, the registry
lab, and desk events. One token guards every API route.

## Running from the US: Coinbase Derivatives instead of Hyperliquid

Hyperliquid blocks US residents. The bot does not route around that: a
VPN or a non-US server reaching Hyperliquid from a US account breaks its
terms and is the kind of thing that ends with frozen funds. Hyperliquid's
public market data (no account, no key) is still used for research.

A Linode is the right server either way. It only needs to be always on;
a US region is fine for Coinbase and Kraken US, and must not be used to
reach Hyperliquid's trading API from the US.

**The bounce-short moves to Coinbase Derivatives**, Coinbase's
CFTC-regulated futures venue (`perp.venue: coinbase`). It lists
perpetual-style futures (hourly funding, 24/7) on three of the eighteen
memecoins: DOGE, 1000PEPE, 1000SHIB, in whole contracts of about $480,
$440 and $60. The rule itself does not change. Re-tested on just those
three coins, walk-forward with cuts refit on prior years, one slot per
coin at 1x, a third of the capital each:

| year | HL-like fees | 0.40% round trip | 0.60% round trip |
|---|---|---|---|
| 2022 | +11.8% | +9.6% | +7.8% |
| 2023 | +8.8% | +6.9% | +5.2% |
| 2024 | +23.5% | +20.1% | +17.1% |
| 2025 | +53.2% | +50.1% | +47.4% |
| 2026 YTD | +9.3% | +7.0% | +5.1% |

5/5 years positive, beats the unconditional short 5/5, +2.76% per trade
over 230 trades, max drawdown about −20%. Coinbase's taker fee is 0.10%
per side plus slippage, so the middle column is the realistic one.

What changes in practice:

- **Whole contracts.** The sim book keeps fractional sizes, so the sim
  is the strategy's return. The real book sends `floor(slot /
  contract)` contracts and journals a `sizing` skip when a slot is
  smaller than one contract; `--preflight` reports the live contract
  sizes and the minimum bankroll (about $1,500 for all three coins at
  100% bounce-short). Below that, the real book trades only the coins it
  can afford whole.
- **History.** Coinbase's candles start in December 2025 (PEP in
  February 2026), so the tercile cuts are fitted on seeded Hyperliquid
  public history (`perp.history_seed`) until Coinbase has enough of its
  own. Build it once with
  `python -m cryptobot.data.coinbase_futures --seed state/hl_daily_us3.pkl`
  (public endpoint, no account).
- **Keys.** A CDP API key with *trade* permission only, ECDSA type,
  futures enabled on the account (`CRYPTOBOT_COINBASE_KEY_NAME` /
  `_SECRET`). Same arming rule: `perp.live: true` and
  `CRYPTOBOT_ARM_LIVE=yes` and both env vars.

**What a small account actually gets.** The table above is the
strategy with fractional sizing. The paper book on Coinbase charges
Coinbase's actual fee (0.05% per side with a **$0.20 per-contract
floor**, which makes the $53 1000SHIB contract cost 0.38% per side),
sizes each slot against the **overnight short margin rate** the venue
publishes (92% DOGE, 114% 1000PEPE, 95% 1000SHIB on 2026-10-08: a $1
memecoin short needs about $1 of margin, there is no leverage), and
rounds every slot down to whole contracts, exactly as the real book
does. Replayed 2022-01 to 2026-10 with the deployed sizing (one slot per
coin, 10% daily-loss halt):

| bankroll | 2022 | 2023 | 2024 | 2025 | 2026 YTD | signals too small |
|---|---|---|---|---|---|---|
| $1,500 | +8.9% | +9.0% | +11.0% | +3.4% | −2.6% | 98 of 189 |
| $3,000 | +4.5% | +9.1% | +17.2% | −7.8% | −2.8% | 40 of 167 |
| $6,000 | +9.8% | +8.9% | +14.6% | +36.6% | −0.4% | 3 of 148 |
| $10,000 (fractional) | +12.2% | +11.3% | +34.9% | +50.8% | +4.8% | — |

Contracts are 5,000 DOGE (~$420), 100,000 × 1000PEPE (~$380) and
10,000 × 1000SHIB (~$53); when DOGE or PEPE trade higher, as in 2024-25,
a $500 or $1,000 slot cannot hold one and the signal is skipped. The
2025 year was mostly those trades. Under about $6,000 the account is
effectively a SHIB-plus-whatever-fits bot and the year-to-year numbers
are lumpier than the fractional table; at $6,000 it tracks the
strategy. Reproduce with
`python -m cryptobot.perp_bot --replay state/hl_daily_us3.pkl --replay-from 2022-01-01 --bankroll 1500 --on-capital --whole-contracts`.

A note on how this table was found: an earlier version of the contract
table had the 1000PEPE and 1000SHIB units 1,000× too small (Coinbase's
`contract_size` is already in 1000-coin units because the product is
priced per 1,000 coins). The fee floor exposed it in replay; in a live
account it would have sized a $1,000 slot as ~2,600 PEPE contracts. The
units are now asserted against the recorded `contract_size` values in
the tests, and `--preflight` prints the live dollar size, fee and
overnight margin per contract.

**Kalshi as the small-account venue (`perp.venue: kalshi`).** Kalshi,
a CFTC-regulated exchange, has listed perpetual futures since June 2026:
DOGE at 100 coins a contract (~$8) and SHIB at one million coins (~$5),
with PEPE listed but inactive on 2026-10-08. Fees are 4 bp taker / 2 bp
maker with no per-contract floor, shorts get ~2-3x margin (the bot stays
at 1x) and there is no intraday/overnight margin switch. Contracts fifty
times smaller than Coinbase's mean a $200 account holds every slot
whole, so the whole-contract table above does not apply there. Liquidity
on 2026-10-08: DOGE ~$2.4M a day with a 0.08% spread, SHIB ~$0.5M. The
executor (`execution/kalshi_perps.py`) sends immediate-or-cancel limits at
mid ± 0.5%, so an unfilled order is a definite non-fill; market data
(`data/kalshi_perps.py`) needs no key and is seeded with the same
Hyperliquid history. Perps API access is enabled per member
("rolling out"), which `--preflight` checks via `/margin/enabled`; the demo
environment is one config line (`perp.kalshi_base_url`). Funding on
Kalshi's DOGE and SHIB perps averaged about zero over their first 364
eight-hour periods, so carry stays shelved there as well.

**Carry is shelved in the US.** Carry's edge needed breadth (the
150-coin universe); US venues list three memecoin perps, and over the
past year their funding on Kraken Futures averaged DOGE +0.005, PEPE
−0.006, SHIB −0.015 %/day (Hyperliquid about +0.01%/day): there is
nobody to collect from. `allocation.carry: 0` turns it off and the desk
runs the bounce-short alone; set it back to 0.5 with `perp.venue:
hyperliquid` where Hyperliquid is available.

## Carry on capital, and the 50/50 split

**A correction.** Carry yields quoted above (+13% to +45% a year) are per
dollar of *position*. A carry position needs money on both venues, the
spot on Kraken and the perp margin on Hyperliquid, so at 1x a $100
position ties up $200 and the return on capital is about half. The bot
now sizes that way (`slot_fraction` is capital per slot, both legs).

**Liquidation risk, measured.** High-funding coins are the ones that
pump. Over 187 historical carry trades (median hold 8 days) one in ten
rose 80%+ during the hold and the largest single day was +67%. At 1x
with no guard, 16 would have liquidated the short, leaving the spot leg
unhedged right after a pump. Replaying those trades on daily perp
candles (a day that reaches the liquidation level counts as a
liquidation, the conservative reading):

| perp leverage, guard | liquidations | worst year on capital |
|---|---|---|
| 1x, none | 16 | (liquidations not charged) |
| **1x, close both legs at +50%** | **0** | **+3.8%** |
| 1.5x, +50% | 12 | |
| 2x, +35% | 14 | |
| 3x, +25% | 36 | |

Leverage never pays once liquidations are counted. The bot now runs the
perp leg at 1x with a **+50% margin guard** (`margin_guard`): when the
coin trades 50% above entry, both legs close. The hedge makes the rally
itself cost nothing; the guard gives up only the funding not yet
collected.

**The two survivors, on the same footing** (return on capital):

| | 2023 | 2024 | 2025 | 2026 | |
|---|---|---|---|---|---|
| carry, 1x, +50% guard | +6.9% | **+12.2%** | +3.8% | +5.8% | hedged |
| bounce-short, 1/18 of capital per coin | +5.2% | **+1.4%** | **+35.8%** | +11.2% | max drawdown −15.5% |
| **50 / 50** | **+6.1%** | **+6.8%** | **+19.8%** | **+8.5%** | |

The bounce-short earns more on average and much less evenly; carry is
steadier and earns most in manias, exactly when the bounce-short
struggles. The default `allocation:` splits capital 50/50, and each bot
sizes from its share. The bounce-short now uses one equal slot per coin
at 1x (its 2022-23 figures understate it: only 3-7 coins existed while
capital is split 18 ways).

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
