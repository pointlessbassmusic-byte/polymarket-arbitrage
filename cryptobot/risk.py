"""Position sizing and account-level risk limits.

Sizing is capped fractional-Kelly: stake proportional to edge/odds, scaled
down hard (memecoin "probabilities" are guesses), then clipped by per-trade,
per-token and liquidity caps. Liquidity cap matters most: in a thin pool
your own exit is the slippage, so never hold more than a sliver of the pool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .models import Position, Signal, now

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    bankroll_usd: float = 1_000.0
    kelly_fraction: float = 0.25          # quarter-Kelly
    max_position_usd: float = 100.0
    max_position_pct_of_liquidity: float = 0.005   # 0.5% of pool
    max_open_positions: int = 8
    max_total_exposure_usd: float = 500.0
    max_daily_loss_usd: float = 100.0
    max_positions_per_token: int = 1
    min_confidence: float = 0.35
    # Volatility targeting: scale stakes down when a token's realized 30m
    # vol exceeds this reference level. Academic result: volatility-managed
    # momentum keeps the premium while avoiding the crash tail.
    vol_target_30m: float = 0.04


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    day_start: float = field(default_factory=now)
    halted: bool = False


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.state = RiskState()

    def record_pnl(self, pnl: float) -> None:
        self._roll_day()
        self.state.daily_pnl += pnl
        if self.state.daily_pnl <= -self.cfg.max_daily_loss_usd:
            if not self.state.halted:
                logger.warning(
                    "daily loss limit hit (%.2f) — halting new entries",
                    self.state.daily_pnl,
                )
            self.state.halted = True

    def _roll_day(self) -> None:
        if now() - self.state.day_start >= 86400:
            self.state = RiskState()

    def size_position(self, sig: Signal, open_positions: list[Position]) -> float:
        """Return notional USD to deploy, 0 if the trade is rejected."""
        self._roll_day()
        if self.state.halted:
            return 0.0
        if sig.confidence < self.cfg.min_confidence:
            return 0.0
        if len(open_positions) >= self.cfg.max_open_positions:
            return 0.0
        if sum(1 for p in open_positions if p.key == sig.key) >= self.cfg.max_positions_per_token:
            return 0.0
        exposure = sum(p.size_usd for p in open_positions)
        room = self.cfg.max_total_exposure_usd - exposure
        if room <= 0:
            return 0.0

        # Kelly: f = p - q/b, with b = win/loss ratio, p = confidence.
        b = sig.risk_reward
        p = sig.confidence
        kelly = p - (1.0 - p) / b if b > 0 else 0.0
        if kelly <= 0:
            return 0.0
        stake = kelly * self.cfg.kelly_fraction * self.cfg.bankroll_usd
        # Vol targeting: a token running 2x the reference vol gets half the
        # stake, keeping each position's expected dollar-vol roughly equal.
        if sig.vol_30m > self.cfg.vol_target_30m > 0:
            stake *= self.cfg.vol_target_30m / sig.vol_30m
        stake = min(
            stake,
            self.cfg.max_position_usd,
            self.cfg.max_position_pct_of_liquidity * sig.liquidity_usd,
            room,
        )
        return stake if stake >= 1.0 else 0.0
