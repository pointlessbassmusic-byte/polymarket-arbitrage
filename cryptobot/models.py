"""Shared dataclasses for the crypto volatility bot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Side(str, Enum):
    LONG = "long"
    # Shorting memecoins on-chain is rarely practical; kept for completeness
    # (used by the NFT module to flag "avoid/exit" rather than actual shorts).
    SHORT = "short"


class SignalType(str, Enum):
    VOL_BREAKOUT = "vol_breakout"          # price + volume expansion, ride momentum
    MEAN_REVERT = "mean_revert"            # overextended spike, fade / buy the dip
    CROSS_DEX_ARB = "cross_dex_arb"        # same token priced differently across pools
    VOL_REGIME_SHIFT = "vol_regime_shift"  # quiet coin waking up (5m vol >> 24h vol)
    NFT_FLOOR_SWING = "nft_floor_swing"    # OpenSea collection floor volatility


@dataclass
class TokenSnapshot:
    """One observation of a DEX pair, normalized from any data source."""

    ts: float
    chain: str
    pair_address: str
    base_symbol: str
    base_address: str
    quote_symbol: str
    price_usd: float
    # Native percent changes reported by the source, as fractions (0.05 = 5%).
    change_5m: Optional[float] = None
    change_1h: Optional[float] = None
    change_6h: Optional[float] = None
    change_24h: Optional[float] = None
    volume_24h_usd: float = 0.0
    volume_1h_usd: float = 0.0
    liquidity_usd: float = 0.0
    fdv_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    txns_24h_buys: int = 0
    txns_24h_sells: int = 0
    pair_created_at: Optional[float] = None  # unix seconds

    @property
    def key(self) -> str:
        return f"{self.chain}:{self.pair_address}"

    @property
    def age_hours(self) -> Optional[float]:
        if self.pair_created_at is None:
            return None
        return max(0.0, (self.ts - self.pair_created_at) / 3600.0)

    @property
    def buy_sell_ratio(self) -> float:
        total = self.txns_24h_buys + self.txns_24h_sells
        if total == 0:
            return 0.5
        return self.txns_24h_buys / total


@dataclass
class VolatilityProfile:
    """Multi-window volatility view of a token."""

    key: str
    symbol: str
    # Absolute return magnitude per window, as fractions.
    move_5m: float = 0.0
    move_30m: float = 0.0
    move_1h: float = 0.0
    move_24h: float = 0.0
    # Annualization-free realized vol: stdev of sampled log returns per window.
    realized_vol_30m: float = 0.0
    # How unusual the current 5m move is vs this token's own recent history.
    zscore_5m: float = 0.0
    samples: int = 0

    @property
    def wildness(self) -> float:
        """Composite volatility score used for ranking. Short windows weigh more."""
        return (
            4.0 * abs(self.move_5m)
            + 2.0 * abs(self.move_30m)
            + 1.5 * abs(self.move_1h)
            + 0.5 * abs(self.move_24h)
        )


@dataclass
class Signal:
    ts: float
    type: SignalType
    key: str
    chain: str
    symbol: str
    side: Side
    price_usd: float
    confidence: float          # 0..1
    expected_move: float       # fraction, expected favorable move
    stop_loss_pct: float       # fraction below entry (for longs)
    take_profit_pct: float     # fraction above entry
    reason: str
    # Asymmetry: expected upside / expected downside. > 2 is what we hunt for.
    risk_reward: float = 1.0
    liquidity_usd: float = 0.0

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "type": self.type.value,
            "key": self.key,
            "chain": self.chain,
            "symbol": self.symbol,
            "side": self.side.value,
            "price_usd": self.price_usd,
            "confidence": round(self.confidence, 3),
            "expected_move": round(self.expected_move, 4),
            "stop_loss_pct": round(self.stop_loss_pct, 4),
            "take_profit_pct": round(self.take_profit_pct, 4),
            "risk_reward": round(self.risk_reward, 2),
            "liquidity_usd": self.liquidity_usd,
            "reason": self.reason,
        }


@dataclass
class Position:
    key: str
    chain: str
    symbol: str
    side: Side
    entry_price: float
    size_usd: float            # notional at entry
    qty: float                 # token amount
    opened_at: float
    stop_loss: float           # absolute price
    take_profit: float         # absolute price
    trail_pct: Optional[float] = None
    high_water: float = 0.0    # best price seen since entry (for trailing)
    signal_type: Optional[SignalType] = None

    def unrealized_pnl(self, price: float) -> float:
        if self.side == Side.LONG:
            return (price - self.entry_price) * self.qty
        return (self.entry_price - price) * self.qty


@dataclass
class ClosedTrade:
    key: str
    symbol: str
    side: Side
    entry_price: float
    exit_price: float
    size_usd: float
    pnl_usd: float
    opened_at: float
    closed_at: float
    exit_reason: str
    signal_type: Optional[SignalType] = None


@dataclass
class NftCollectionSnapshot:
    """One observation of an OpenSea collection."""

    ts: float
    slug: str
    floor_price_eth: float
    one_day_volume_eth: float = 0.0
    one_day_change: float = 0.0     # fraction
    seven_day_change: float = 0.0
    num_owners: int = 0
    total_supply: int = 0


def now() -> float:
    return time.time()
