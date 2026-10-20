"""Memecoin / crypto volatility swing bot.

Scans DEX-traded tokens (the universe tradeable from a MetaMask wallet) for
wild multi-window volatility, detects swing patterns and asymmetric
risk/reward setups, and rides them with paper trading by default. Live
execution signs swaps with a MetaMask-compatible private key through a DEX
aggregator, and is disabled unless explicitly armed in config.
"""

__version__ = "0.1.0"
