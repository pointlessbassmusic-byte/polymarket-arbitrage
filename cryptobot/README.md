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
| MetaMask as trading backbone | `execution/wallet.py` signs swaps with the same private key your MetaMask wallet uses, routed through the **0x Swap API** (the aggregator behind MetaMask Swaps) |
| OpenSea | OpenSea has **no token-trading API** (it's NFTs only), so it can't price memecoins. It's used for what it *can* do: `data/opensea.py` tracks collection **floor-price volatility** as a second swing universe (log-only, needs a free API key) |
| Patterns | Four detectors: volatility **breakout** (ride with trailing stop), **mean reversion** (fade a local flush), **regime shift** (quiet coin waking up, z-score based), **cross-DEX arbitrage** (same token, different pool prices, net of fees) |
| Asymmetric risk | Structural, not predictive: stops sit where the setup is invalidated (near), targets at the prior extension (far); anything under **2:1 reward/risk is refused**. Sizing is capped quarter-Kelly, additionally clipped to 0.5% of pool liquidity so your own exit doesn't become the slippage |

## Quick start

```bash
pip install -r requirements.txt

# one scan cycle, print signals as JSON
python run_cryptobot.py --once

# continuous paper-trading loop (1 scan/minute)
python run_cryptobot.py
```

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
├── portfolio.py         # paper positions, trailing stops, PnL ledger
├── scanner.py           # discover → observe → detect → manage loop
├── data/
│   ├── dexscreener.py   # main price/volume/liquidity feed
│   ├── coingecko.py     # trending + majors
│   └── opensea.py       # NFT floor volatility (log-only)
└── execution/
    └── wallet.py        # 0x quotes + MetaMask-key signing (opt-in)
```

Tests: `python -m pytest tests/test_cryptobot.py -v`
