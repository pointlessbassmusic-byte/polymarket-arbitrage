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

The dashboard shows equity, open positions with live PnL, recent signals,
the wildest multi-window movers, closed trades, and the learned edge report
per pattern (win rate, profit factor, expectancy, current sizing multiplier).
Light and dark mode follow your system theme.

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
4. RPC URLs per chain in the config.

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
    └── wallet.py        # 0x buy/sell + MetaMask-key signing (opt-in)
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

Tests: `python -m pytest tests/test_cryptobot.py -v`
