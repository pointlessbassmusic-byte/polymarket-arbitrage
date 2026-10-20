"""Edge attribution: learn which patterns actually pay, and feed it back.

Crypto swings and prediction-market arbitrage have very different profit
mechanics — prediction-market arb is a near-riskless spread you capture,
while DEX swing edges are statistical and decay as conditions change. So
instead of hardcoding faith in any detector, every closed trade is bucketed
by signal type (and chain), and once a bucket has enough samples its
realized expectancy scales the confidence of future signals of that type:
patterns that keep paying size up toward a capped bonus, patterns that keep
losing size down toward zero.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import ClosedTrade

logger = logging.getLogger(__name__)

MIN_SAMPLES = 10        # below this, no adjustment — not enough evidence
MULT_FLOOR = 0.3        # never fully mute a detector (edges come back)
MULT_CAP = 1.3          # never let a hot streak run sizing away


@dataclass
class EdgeStats:
    trades: int = 0
    wins: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_pnl: float = 0.0
    total_staked: float = 0.0

    def record(self, trade: ClosedTrade) -> None:
        self.trades += 1
        self.total_pnl += trade.pnl_usd
        self.total_staked += trade.size_usd
        if trade.pnl_usd > 0:
            self.wins += 1
            self.gross_profit += trade.pnl_usd
        else:
            self.gross_loss += -trade.pnl_usd

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def profit_factor(self) -> Optional[float]:
        if self.gross_loss <= 0:
            return None if self.gross_profit <= 0 else float("inf")
        return self.gross_profit / self.gross_loss

    @property
    def expectancy(self) -> float:
        """Average return per dollar staked — the number that matters."""
        return self.total_pnl / self.total_staked if self.total_staked else 0.0

    def as_dict(self) -> dict:
        pf = self.profit_factor
        return {
            "trades": self.trades,
            "win_rate": round(self.win_rate, 3),
            "profit_factor": round(pf, 2) if pf not in (None, float("inf")) else pf,
            "expectancy_per_dollar": round(self.expectancy, 4),
            "total_pnl": round(self.total_pnl, 2),
        }


class EdgeTracker:
    def __init__(self, state_file: Optional[Path] = None):
        self.by_type: dict[str, EdgeStats] = {}
        self.by_chain: dict[str, EdgeStats] = {}
        self.state_file = state_file
        self._load()

    def record(self, trade: ClosedTrade) -> None:
        st = trade.signal_type.value if trade.signal_type else "unknown"
        self.by_type.setdefault(st, EdgeStats()).record(trade)
        chain = trade.key.split(":", 1)[0]
        self.by_chain.setdefault(chain, EdgeStats()).record(trade)
        self._save()

    def confidence_multiplier(self, signal_type: str) -> float:
        """Scale a signal's confidence by that pattern's realized edge.

        Neutral (1.0) until MIN_SAMPLES trades exist. Then a linear map of
        expectancy: -10%/trade -> floor, 0 -> ~0.8, +10%/trade -> cap. A
        detector must actually pay to keep full sizing.
        """
        stats = self.by_type.get(signal_type)
        if stats is None or stats.trades < MIN_SAMPLES:
            return 1.0
        mult = 0.8 + 5.0 * stats.expectancy
        return max(MULT_FLOOR, min(MULT_CAP, mult))

    def report(self) -> dict:
        return {
            "by_signal_type": {k: v.as_dict() for k, v in self.by_type.items()},
            "by_chain": {k: v.as_dict() for k, v in self.by_chain.items()},
            "multipliers": {
                k: round(self.confidence_multiplier(k), 2) for k in self.by_type
            },
        }

    # -- persistence -------------------------------------------------------

    def _save(self) -> None:
        if not self.state_file:
            return
        try:
            payload = {
                "by_type": {k: vars(v) for k, v in self.by_type.items()},
                "by_chain": {k: vars(v) for k, v in self.by_chain.items()},
            }
            self.state_file.write_text(json.dumps(payload, indent=2))
        except OSError:
            logger.exception("failed to persist edge stats")

    def _load(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        try:
            payload = json.loads(self.state_file.read_text())
            self.by_type = {k: EdgeStats(**v) for k, v in payload.get("by_type", {}).items()}
            self.by_chain = {k: EdgeStats(**v) for k, v in payload.get("by_chain", {}).items()}
            logger.info("loaded edge stats: %d signal types", len(self.by_type))
        except (OSError, ValueError, TypeError):
            logger.exception("failed to load edge stats — starting fresh")
