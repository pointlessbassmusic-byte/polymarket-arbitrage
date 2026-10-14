"""Trade protections, modeled on Freqtrade's protections framework
(https://www.freqtrade.io/en/stable/plugins/) — the most battle-tested
open-source crypto bot's answer to "the strategy is fine, the regime isn't":

  * CooldownPeriod   — no immediate re-entry on a token just closed;
  * StoplossGuard    — several stop-losses in a short window means the
                       whole market regime is hostile: halt all entries;
  * LowProfitPairs   — a token that keeps losing gets locked individually;
  * MaxDrawdown      — equity drawdown from peak beyond a limit pauses
                       trading to break loss spirals.

All four gate new ENTRIES only — exits always run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .models import ClosedTrade, now

logger = logging.getLogger(__name__)


@dataclass
class ProtectionConfig:
    # CooldownPeriod
    cooldown_s: float = 1800.0             # 30 min per-token cooldown after close

    # StoplossGuard
    stoploss_guard_window_s: float = 7200.0    # look back 2h
    stoploss_guard_limit: int = 4              # 4 stops in window -> halt
    stoploss_guard_halt_s: float = 3600.0      # halt entries for 1h

    # LowProfitPairs
    low_profit_window_s: float = 21600.0       # look back 6h
    low_profit_min_trades: int = 2
    low_profit_lock_s: float = 7200.0          # lock losing token 2h

    # MaxDrawdown
    max_drawdown_pct: float = 0.15             # 15% off equity peak
    drawdown_halt_s: float = 7200.0


@dataclass
class _TokenState:
    last_close: float = 0.0
    locked_until: float = 0.0
    recent: list[ClosedTrade] = field(default_factory=list)


class ProtectionManager:
    def __init__(self, cfg: ProtectionConfig, starting_equity: float):
        self.cfg = cfg
        self._tokens: dict[str, _TokenState] = {}
        self._stop_times: list[float] = []
        self._halted_until: float = 0.0
        self._equity = starting_equity
        self._equity_peak = starting_equity

    # -- feed --------------------------------------------------------------

    def on_trade_closed(self, trade: ClosedTrade) -> None:
        ts = now()
        st = self._tokens.setdefault(trade.key, _TokenState())
        st.last_close = ts
        st.recent.append(trade)
        st.recent = [t for t in st.recent
                     if ts - t.closed_at <= self.cfg.low_profit_window_s]

        # StoplossGuard: count stop-outs across ALL tokens.
        if trade.exit_reason == "stop_loss":
            self._stop_times.append(ts)
            self._stop_times = [t for t in self._stop_times
                                if ts - t <= self.cfg.stoploss_guard_window_s]
            if len(self._stop_times) >= self.cfg.stoploss_guard_limit:
                self._halted_until = ts + self.cfg.stoploss_guard_halt_s
                logger.warning(
                    "StoplossGuard: %d stops in %.0f min — halting entries %.0f min",
                    len(self._stop_times), self.cfg.stoploss_guard_window_s / 60,
                    self.cfg.stoploss_guard_halt_s / 60,
                )
                self._stop_times.clear()

        # LowProfitPairs: lock a token whose recent trades sum negative.
        if (len(st.recent) >= self.cfg.low_profit_min_trades
                and sum(t.pnl_usd for t in st.recent) < 0):
            st.locked_until = ts + self.cfg.low_profit_lock_s
            logger.info("LowProfitPairs: locking %s for %.0f min",
                        trade.symbol, self.cfg.low_profit_lock_s / 60)

        # MaxDrawdown on realized equity.
        self._equity += trade.pnl_usd
        self._equity_peak = max(self._equity_peak, self._equity)
        if self._equity_peak > 0:
            dd = 1.0 - self._equity / self._equity_peak
            # Evaluate regardless of an existing halt: a StoplossGuard halt
            # (and the closes during it) could otherwise consume the whole
            # drawdown budget, after which this would never engage.
            if dd >= self.cfg.max_drawdown_pct:
                self._halted_until = max(self._halted_until,
                                         ts + self.cfg.drawdown_halt_s)
                logger.warning(
                    "MaxDrawdown: %.1f%% off peak — halting entries %.0f min",
                    100 * dd, self.cfg.drawdown_halt_s / 60,
                )

    # -- gate --------------------------------------------------------------

    def entry_allowed(self, key: str) -> tuple[bool, str]:
        ts = now()
        if ts < self._halted_until:
            return False, "global halt (stoploss guard / drawdown)"
        st = self._tokens.get(key)
        if st:
            if ts < st.locked_until:
                return False, "token locked (low profit)"
            if ts - st.last_close < self.cfg.cooldown_s:
                return False, "cooldown after recent close"
        return True, ""

    @property
    def drawdown(self) -> float:
        if self._equity_peak <= 0:
            return 0.0
        return 1.0 - self._equity / self._equity_peak
