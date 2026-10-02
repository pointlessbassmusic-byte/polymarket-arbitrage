"""Position sizing and account-level risk limits.

Sizing is RISK-BASED, not notional-based: what a stop-protected trade can
actually lose is (position x stop distance), not the position. So we fix
the dollar risk per trade and solve for the position:

    risk_$   = bankroll x risk_per_trade_pct x (edge quality scalar)
    position = risk_$ / stop_loss_pct

A $25 position with a 5% stop risks $1.25, the same as a $12.50 position
with a 10% stop — and sizing on notional (plain Kelly) misses that, which
is why it produced ~$3 positions on a $100 book. Positions that small
cannot clear DEX gas economics on any chain, so the account simply never
traded. Tight stops now earn proportionally larger positions, which is
what makes a small account viable at all.

Kelly still sets the *edge quality scalar* (a trade with better odds gets
more of the risk budget), but it no longer sets the notional directly.

Everything is then clipped by per-trade, per-token, exposure and liquidity
caps. The liquidity cap matters most: in a thin pool your own exit is the
slippage, so never hold more than a sliver of the pool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .models import Position, Signal, now

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    bankroll_usd: float = 1_000.0
    # Fraction of the bankroll risked if a trade hits its stop. This, not
    # position size, is the real risk dial.
    risk_per_trade_pct: float = 0.015     # 1.5% of bankroll per stop-out
    kelly_fraction: float = 0.25          # quarter-Kelly, as a scalar on risk
    max_position_usd: float = 100.0
    # Floor: below this a position cannot outrun gas on most chains. A
    # trade whose risk-based size lands under it is sized UP to the floor
    # when affordable, else skipped entirely (never silently undersized).
    min_position_usd: float = 0.0
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

        # Kelly as an edge-quality scalar in [0, 1]: f = p - q/b.
        b = sig.risk_reward
        p = sig.confidence
        kelly = p - (1.0 - p) / b if b > 0 else 0.0
        if kelly <= 0:
            return 0.0
        quality = min(1.0, kelly / self.cfg.kelly_fraction) \
            if self.cfg.kelly_fraction > 0 else 1.0

        # Risk budget -> position, via the stop distance.
        risk_usd = self.cfg.bankroll_usd * self.cfg.risk_per_trade_pct * quality
        stop = max(sig.stop_loss_pct, 0.005)      # guard against /0
        stake = risk_usd / stop

        # Vol targeting: a token running 2x the reference vol gets half the
        # stake, keeping each position's expected dollar-vol roughly equal.
        if sig.vol_30m > self.cfg.vol_target_30m > 0:
            stake *= self.cfg.vol_target_30m / sig.vol_30m

        ceiling = min(
            self.cfg.max_position_usd,
            self.cfg.max_position_pct_of_liquidity * sig.liquidity_usd,
            room,
        )
        stake = min(stake, ceiling)

        # Economic floor: an undersized position is dominated by gas, so
        # size up to the floor when the caps allow, otherwise stand aside.
        if self.cfg.min_position_usd > 0 and stake < self.cfg.min_position_usd:
            if ceiling >= self.cfg.min_position_usd:
                stake = self.cfg.min_position_usd
            else:
                return 0.0
        return stake if stake >= 1.0 else 0.0
