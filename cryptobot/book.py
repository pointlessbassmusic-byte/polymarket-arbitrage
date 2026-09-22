"""Trading books and the decision journal.

A *book* is one self-contained account: its own cash, positions, risk
limits and protections. The bot runs two of them side by side:

  * **sim**  — always trading, on live market data, with simulated money.
    It is the benchmark and the learning engine: it keeps producing
    outcomes whether or not real money is switched on.
  * **real** — identical logic, but its entries also execute on-chain.
    Dormant until real mode is armed.

Running both at once is deliberate. Once real trading starts, the sim
book keeps a parallel record of what the strategy *should* have made,
so the gap between the two is a direct measurement of real execution
quality (slippage, latency, failed swaps) rather than a guess.

The `EdgeTracker` is deliberately shared, not per-book: what the sim
book learns about which patterns pay should inform real sizing from the
first real trade, rather than starting that learning over from zero.

The **decision journal** records every signal the bot evaluated and what
it did about it — including, especially, the ones it declined and why.
A bot that only shows its trades hides most of its reasoning; the skips
are where the risk controls actually earn their keep.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .analytics import EdgeTracker
from .costs import CostModel
from .portfolio import Portfolio
from .protections import ProtectionConfig, ProtectionManager
from .risk import RiskConfig, RiskManager


@dataclass
class Decision:
    """One evaluated signal: what it was, and what happened to it."""
    ts: float
    book: str                 # "sim" | "real"
    symbol: str
    chain: str
    signal_type: str
    action: str               # "opened" | "skipped" | "closed"
    reason: str               # human-readable: the gate that decided it
    stage: str = ""           # which gate: protections/sizing/costs/security
    size_usd: float = 0.0
    price_usd: float = 0.0
    confidence: float = 0.0
    risk_reward: float = 0.0
    pnl_usd: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "ts": self.ts, "book": self.book, "symbol": self.symbol,
            "chain": self.chain, "signal_type": self.signal_type,
            "action": self.action, "reason": self.reason, "stage": self.stage,
            "size_usd": round(self.size_usd, 2),
            "price_usd": self.price_usd,
            "confidence": round(self.confidence, 2),
            "risk_reward": round(self.risk_reward, 2),
            "pnl_usd": None if self.pnl_usd is None else round(self.pnl_usd, 2),
        }


class DecisionJournal:
    """Bounded, newest-first record of what the bot decided and why."""

    def __init__(self, maxlen: int = 400):
        self._entries: deque[Decision] = deque(maxlen=maxlen)

    def record(self, decision: Decision) -> None:
        self._entries.appendleft(decision)

    def recent(self, limit: int = 60, book: Optional[str] = None) -> list[dict]:
        out = []
        for d in self._entries:
            if book and d.book != book:
                continue
            out.append(d.as_dict())
            if len(out) >= limit:
                break
        return out

    def counts(self, book: Optional[str] = None) -> dict[str, int]:
        """How many signals died at each gate — where the edge is filtered."""
        tally: dict[str, int] = {}
        for d in self._entries:
            if book and d.book != book:
                continue
            key = d.stage or d.action
            tally[key] = tally.get(key, 0) + 1
        return tally


@dataclass
class TradingBook:
    """One account: cash, positions, risk limits, protections."""

    name: str
    starting_equity: float
    portfolio: Portfolio
    risk: RiskManager
    protections: ProtectionManager
    executes_onchain: bool = False

    @classmethod
    def create(cls, name: str, risk_cfg: RiskConfig, costs: CostModel,
               prot_cfg: Optional[ProtectionConfig] = None,
               state_dir: Optional[Path] = None,
               executes_onchain: bool = False) -> "TradingBook":
        return cls(
            name=name,
            starting_equity=risk_cfg.bankroll_usd,
            portfolio=Portfolio(
                state_file=(state_dir / f"cryptobot_{name}_portfolio.json")
                if state_dir else None,
                cost_model=costs,
            ),
            risk=RiskManager(risk_cfg),
            protections=ProtectionManager(prot_cfg or ProtectionConfig(),
                                          starting_equity=risk_cfg.bankroll_usd),
            executes_onchain=executes_onchain,
        )

    def equity(self, prices: dict[str, float]) -> float:
        s = self.portfolio.summary(prices)
        return self.starting_equity + s["realized_pnl"] + s["unrealized_pnl"]

    def state(self, prices: dict[str, float], edges: EdgeTracker) -> dict:
        summary = self.portfolio.summary(prices)
        equity = self.starting_equity + summary["realized_pnl"] + summary["unrealized_pnl"]
        positions = []
        for p in self.portfolio.positions.values():
            price = prices.get(p.key, p.entry_price)
            positions.append({
                "symbol": p.symbol, "chain": p.chain, "key": p.key,
                "entry_price": p.entry_price, "price": price,
                "size_usd": round(p.size_usd, 2),
                "pnl_usd": round(p.unrealized_pnl(price), 2),
                "pnl_pct": (price / p.entry_price - 1.0) if p.entry_price else 0.0,
                "stop_loss": p.stop_loss, "take_profit": p.take_profit,
                "opened_at": p.opened_at,
                "signal_type": p.signal_type.value if p.signal_type else None,
            })
        closed = [{
            "symbol": t.symbol, "chain": t.key.split(":")[0],
            "pnl_usd": round(t.pnl_usd, 2), "size_usd": round(t.size_usd, 2),
            "costs_usd": round(t.costs_usd, 2), "exit_reason": t.exit_reason,
            "closed_at": t.closed_at, "held_s": t.closed_at - t.opened_at,
            "signal_type": t.signal_type.value if t.signal_type else None,
        } for t in self.portfolio.closed[-60:]][::-1]
        return {
            "name": self.name,
            "starting_equity": self.starting_equity,
            "equity": round(equity, 2),
            "return_pct": (equity / self.starting_equity - 1.0)
                          if self.starting_equity else 0.0,
            "executes_onchain": self.executes_onchain,
            "halted": self.risk.state.halted,
            "drawdown": round(self.protections.drawdown, 4),
            "summary": summary,
            "positions": positions,
            "closed_trades": closed,
        }


def now() -> float:
    return time.time()
