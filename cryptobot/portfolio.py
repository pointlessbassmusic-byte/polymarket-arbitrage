"""Paper-trading portfolio: positions, trailing stops, PnL ledger."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .models import ClosedTrade, Position, Side, Signal, SignalType, now

logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(self, trail_pct: float = 0.05, state_file: Optional[Path] = None):
        self.positions: dict[str, Position] = {}
        self.closed: list[ClosedTrade] = []
        self.realized_pnl: float = 0.0
        self.default_trail = trail_pct
        self.state_file = state_file

    # -- entries -----------------------------------------------------------

    def open_from_signal(self, sig: Signal, size_usd: float) -> Position:
        pos = Position(
            key=sig.key,
            chain=sig.chain,
            symbol=sig.symbol,
            side=sig.side,
            entry_price=sig.price_usd,
            size_usd=size_usd,
            qty=size_usd / sig.price_usd,
            opened_at=sig.ts,
            stop_loss=sig.price_usd * (1.0 - sig.stop_loss_pct),
            take_profit=sig.price_usd * (1.0 + sig.take_profit_pct),
            trail_pct=self.default_trail if sig.type == SignalType.VOL_BREAKOUT else None,
            high_water=sig.price_usd,
            signal_type=sig.type,
            token_address=sig.token_address,
        )
        self.positions[pos.key] = pos
        logger.info(
            "OPEN  %-12s $%.2f @ %.6g  stop %.6g  target %.6g  (%s)",
            pos.symbol, size_usd, pos.entry_price, pos.stop_loss,
            pos.take_profit, sig.type.value,
        )
        self.save()
        return pos

    # -- exits -------------------------------------------------------------

    def check_exit(self, key: str, price: float) -> Optional[str]:
        """Update trailing state; return an exit reason if the position
        should close at `price`, else None."""
        pos = self.positions.get(key)
        if pos is None:
            return None
        if price > pos.high_water:
            pos.high_water = price
            # Ratchet the stop up under a trailing position once in profit.
            if pos.trail_pct is not None and price > pos.entry_price:
                trailed = price * (1.0 - pos.trail_pct)
                if trailed > pos.stop_loss:
                    pos.stop_loss = trailed
        if price <= pos.stop_loss:
            return "stop_loss" if price <= pos.entry_price else "trailing_stop"
        if price >= pos.take_profit:
            # Breakouts trail instead of taking profit at the first target —
            # that's where the fat right tail lives.
            if pos.trail_pct is not None:
                pos.take_profit = price * 2.0  # effectively disabled
                return None
            return "take_profit"
        return None

    def close(self, key: str, price: float, reason: str) -> Optional[ClosedTrade]:
        pos = self.positions.pop(key, None)
        if pos is None:
            return None
        pnl = pos.unrealized_pnl(price)
        trade = ClosedTrade(
            key=pos.key, symbol=pos.symbol, side=pos.side,
            entry_price=pos.entry_price, exit_price=price,
            size_usd=pos.size_usd, pnl_usd=pnl,
            opened_at=pos.opened_at, closed_at=now(),
            exit_reason=reason, signal_type=pos.signal_type,
        )
        self.closed.append(trade)
        self.realized_pnl += pnl
        logger.info(
            "CLOSE %-12s %+.2f USD (%.1f%%) @ %.6g  [%s]",
            pos.symbol, pnl, 100.0 * pnl / pos.size_usd if pos.size_usd else 0.0,
            price, reason,
        )
        self.save()
        return trade

    # -- reporting ---------------------------------------------------------

    def summary(self, prices: Optional[dict[str, float]] = None) -> dict:
        prices = prices or {}
        unrealized = sum(
            p.unrealized_pnl(prices.get(k, p.entry_price))
            for k, p in self.positions.items()
        )
        wins = sum(1 for t in self.closed if t.pnl_usd > 0)
        return {
            "open_positions": len(self.positions),
            "exposure_usd": round(sum(p.size_usd for p in self.positions.values()), 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized, 2),
            "trades": len(self.closed),
            "win_rate": round(wins / len(self.closed), 3) if self.closed else None,
        }

    def save(self) -> None:
        if not self.state_file:
            return
        try:
            data = {
                "realized_pnl": self.realized_pnl,
                "positions": [vars(p) | {"side": p.side.value,
                                          "signal_type": p.signal_type.value if p.signal_type else None}
                              for p in self.positions.values()],
                "closed": [vars(t) | {"side": t.side.value,
                                       "signal_type": t.signal_type.value if t.signal_type else None}
                           for t in self.closed[-200:]],
            }
            self.state_file.write_text(json.dumps(data, indent=2))
        except OSError:
            logger.exception("failed to persist portfolio state")
