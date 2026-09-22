"""Main scan-and-trade loop.

Each cycle:
  1. Build the candidate universe: configured watchlist queries + DexScreener
     boosted tokens + CoinGecko trending (attention flows precede volatility).
  2. Snapshot every tracked pair, feed the volatility engine.
  3. Rank by multi-window "wildness", run the signal detectors.
  4. Periodically pull all pools for the wildest tokens and check cross-DEX
     price gaps.
  5. Manage open positions: trailing stops, targets, time stops. When a
     live executor is armed, entries buy and exits sell on-chain via the
     MetaMask-key + 0x path; otherwise everything is paper.
  6. Feed every closed trade to the EdgeTracker, which learns per-pattern
     expectancy and scales future signal confidence accordingly.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .analytics import EdgeTracker
from .costs import CostConfig, CostModel
from .data.coingecko import CoinGeckoClient
from .data.dexscreener import DexScreenerClient
from .data.goplus import ScreenConfig, TokenScreen
from .execution.wallet import NATIVE_GECKO_IDS
from .models import Signal, SignalType, TokenSnapshot, now
from .protections import ProtectionConfig, ProtectionManager
from .portfolio import Portfolio
from .risk import RiskConfig, RiskManager
from .signals import SignalConfig, detect_all, detect_cross_dex_arb
from .volatility import VolatilityEngine

logger = logging.getLogger(__name__)


@dataclass
class ScannerConfig:
    scan_interval_s: float = 60.0
    watchlist_queries: list[str] = field(default_factory=lambda: [
        "PEPE", "WIF", "BONK", "SHIB", "DOGE", "FLOKI", "BRETT", "POPCAT",
    ])
    chains: list[str] = field(default_factory=lambda: [
        "ethereum", "base", "solana", "bsc", "arbitrum",
    ])
    max_tracked_pairs: int = 150
    arb_check_top_n: int = 10           # deep-scan pools of the N wildest tokens
    arb_check_every_cycles: int = 5
    max_position_age_s: float = 6 * 3600  # time stop
    edge_report_every_cycles: int = 30


class Scanner:
    def __init__(self, scan_cfg: ScannerConfig, sig_cfg: SignalConfig,
                 risk_cfg: RiskConfig, state_dir: Optional[Path] = None,
                 executor=None, screen_cfg: Optional[ScreenConfig] = None,
                 protection_cfg: Optional[ProtectionConfig] = None,
                 cost_cfg: Optional[CostConfig] = None):
        self.cfg = scan_cfg
        self.sig_cfg = sig_cfg
        self.dex = DexScreenerClient()
        self.gecko = CoinGeckoClient()
        self.costs = CostModel(cost_cfg)
        self.screen = TokenScreen(screen_cfg)
        self.protections = ProtectionManager(
            protection_cfg or ProtectionConfig(),
            starting_equity=risk_cfg.bankroll_usd,
        )
        self.vol = VolatilityEngine()
        self.risk = RiskManager(risk_cfg)
        self.portfolio = Portfolio(
            state_file=(state_dir / "cryptobot_portfolio.json") if state_dir else None,
            cost_model=self.costs,
        )
        self.edges = EdgeTracker(
            state_file=(state_dir / "cryptobot_edges.json") if state_dir else None
        )
        self.executor = executor
        self._native_prices: dict[str, float] = {}   # gecko id -> usd
        self._native_prices_ts: float = 0.0
        # Dashboard state (read-only from the outside)
        self.recent_signals: deque[dict] = deque(maxlen=100)
        self.movers: list[dict] = []
        self.equity_curve: deque[tuple[float, float]] = deque(maxlen=1440)
        self.started_at: float = now()
        # key -> (chain, base_address) so we can deep-scan pools later
        self.tracked: dict[str, tuple[str, str]] = {}
        self._cycle = 0
        self._latest_prices: dict[str, float] = {}

    async def close(self) -> None:
        await self.dex.close()
        await self.gecko.close()
        await self.screen.close()

    # -- universe ----------------------------------------------------------

    async def discover(self) -> list[TokenSnapshot]:
        snaps: dict[str, TokenSnapshot] = {}

        async def add_query(q: str) -> None:
            try:
                for s in await self.dex.search(q):
                    if s.chain in self.cfg.chains:
                        snaps[s.key] = s
            except Exception as exc:
                logger.warning("search %r failed: %s", q, exc)

        await asyncio.gather(*(add_query(q) for q in self.cfg.watchlist_queries))

        # Attention feeds: boosted tokens and CoinGecko trending symbols.
        try:
            boosts = await self.dex.boosted_tokens()
            boost_addrs = [
                (b.get("chainId"), b.get("tokenAddress"))
                for b in boosts[:15]
                if b.get("chainId") in self.cfg.chains and b.get("tokenAddress")
            ]
            for chain, addr in boost_addrs[:8]:
                try:
                    for s in await self.dex.token_pairs(chain, addr):
                        snaps.setdefault(s.key, s)
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("boost discovery failed: %s", exc)

        if self._cycle % 10 == 0:
            try:
                trending = await self.gecko.trending()
                await asyncio.gather(*(
                    add_query(t.get("symbol", ""))
                    for t in trending[:5] if t.get("symbol")
                ))
            except Exception as exc:
                logger.warning("coingecko trending failed: %s", exc)

        # Refresh pairs we already track but didn't see this cycle.
        missing_by_chain: dict[str, list[str]] = {}
        for key, (chain, _) in self.tracked.items():
            if key not in snaps:
                missing_by_chain.setdefault(chain, []).append(key.split(":", 1)[1])
        for chain, addrs in missing_by_chain.items():
            try:
                for s in await self.dex.get_pairs(chain, addrs):
                    snaps[s.key] = s
            except Exception as exc:
                logger.warning("refresh %s failed: %s", chain, exc)

        return list(snaps.values())

    # -- one cycle ---------------------------------------------------------

    async def run_cycle(self) -> list[Signal]:
        self._cycle += 1
        snaps = await self.discover()

        profiles = []
        for s in snaps:
            self._latest_prices[s.key] = s.price_usd
            profiles.append((s, self.vol.observe(s)))

        # Track the wildest pairs for continuity across cycles.
        profiles.sort(key=lambda sv: sv[1].wildness, reverse=True)
        for s, _ in profiles[: self.cfg.max_tracked_pairs]:
            self.tracked[s.key] = (s.chain, s.base_address)
        while len(self.tracked) > self.cfg.max_tracked_pairs:
            self.tracked.pop(next(iter(self.tracked)))

        signals: list[Signal] = []
        for s, v in profiles:
            signals.extend(detect_all(s, v, self.sig_cfg))

        if self._cycle % self.cfg.arb_check_every_cycles == 0:
            signals.extend(await self._arb_pass(profiles[: self.cfg.arb_check_top_n]))

        await self._manage_positions()
        await self._act_on_signals(signals)

        if self._cycle % self.cfg.edge_report_every_cycles == 0 and self.edges.by_type:
            logger.info("edge report: %s", self.edges.report())

        # Dashboard state
        for sig in signals:
            self.recent_signals.appendleft(sig.as_dict() | {"symbol": sig.symbol})
        self.movers = [
            {
                "symbol": v.symbol, "key": v.key,
                "price_usd": self._latest_prices.get(v.key, 0.0),
                "move_5m": v.move_5m, "move_30m": v.move_30m,
                "move_1h": v.move_1h, "move_24h": v.move_24h,
                "zscore_5m": v.zscore_5m, "wildness": v.wildness,
            }
            for _, v in profiles[:15]
        ]
        summary = self.portfolio.summary(self._latest_prices)
        self.equity_curve.append(
            (now(), self.risk.cfg.bankroll_usd
             + summary["realized_pnl"] + summary["unrealized_pnl"])
        )

        top = profiles[0][1] if profiles else None
        logger.info(
            "cycle %d: %d pairs, %d signals, wildest=%s (%.1f%% 5m) | %s",
            self._cycle, len(snaps), len(signals),
            top.symbol if top else "-", 100 * top.move_5m if top else 0.0,
            self.portfolio.summary(self._latest_prices),
        )
        return signals

    async def _arb_pass(self, top_profiles) -> list[Signal]:
        out: list[Signal] = []
        seen_tokens: set[tuple[str, str]] = set()
        for s, _ in top_profiles:
            tok = (s.chain, s.base_address)
            if not s.base_address or tok in seen_tokens:
                continue
            seen_tokens.add(tok)
            try:
                pools = await self.dex.token_pairs(s.chain, s.base_address)
            except Exception as exc:
                logger.warning("token_pairs %s failed: %s", s.base_symbol, exc)
                continue
            if sig := detect_cross_dex_arb(pools, self.sig_cfg):
                out.append(sig)
        return out

    # -- positions ---------------------------------------------------------

    async def _manage_positions(self) -> None:
        for key in list(self.portfolio.positions.keys()):
            pos = self.portfolio.positions[key]
            price = self._latest_prices.get(key)
            if price is None:
                # Pair fell out of every feed — refetch it directly.
                try:
                    fresh = await self.dex.get_pairs(pos.chain, [key.split(":", 1)[1]])
                    if fresh:
                        price = fresh[0].price_usd
                        self._latest_prices[key] = price
                except Exception:
                    pass
            if price is None:
                continue
            reason = self.portfolio.check_exit(key, price)
            if reason is None and now() - pos.opened_at > self.cfg.max_position_age_s:
                reason = "time_stop"
            if reason:
                trade = self.portfolio.close(key, price, reason)
                if trade:
                    self.risk.record_pnl(trade.pnl_usd)
                    self.edges.record(trade)
                    self.protections.on_trade_closed(trade)
                    if self.executor is not None and pos.token_address:
                        asyncio.create_task(
                            self.executor.sell(pos.chain, pos.token_address, pos.qty)
                        )

    async def _act_on_signals(self, signals: list[Signal]) -> None:
        # Best asymmetry first; one entry per token per cycle.
        for sig in sorted(signals, key=lambda s: s.risk_reward * s.confidence,
                          reverse=True):
            if sig.type == SignalType.CROSS_DEX_ARB:
                # Arb is reported, and (only if a live executor is armed)
                # would be handed to it. Paper mode just logs the edge.
                logger.info("ARB   %s", sig.reason)
                continue
            if sig.key in self.portfolio.positions:
                continue
            allowed, why = self.protections.entry_allowed(sig.key)
            if not allowed:
                logger.debug("skip %s: %s", sig.symbol, why)
                continue
            # Learned edge: scale confidence by the pattern's realized
            # expectancy once enough trades exist to judge it.
            sig.confidence = min(
                1.0, sig.confidence * self.edges.confidence_multiplier(sig.type.value)
            )
            size = self.risk.size_position(sig, list(self.portfolio.positions.values()))
            if size <= 0:
                continue
            # Profitability gate: the edge must survive its own round-trip
            # costs (fees + price impact + gas) with margin at this size.
            ok, why = self.costs.entry_allowed(
                sig.expected_move, size, sig.liquidity_usd, sig.chain)
            if not ok:
                logger.info("skip %s: %s", sig.symbol, why)
                continue
            # Last gate before money: contract-level rug/honeypot screen.
            verdict = await self.screen.check(sig.chain, sig.token_address)
            if not verdict.ok:
                logger.info("skip %s: %s", sig.symbol, verdict)
                continue
            self.portfolio.open_from_signal(sig, size)
            if self.executor is not None:
                asyncio.create_task(self._execute_live(sig, size))

    async def _native_price(self, chain: str) -> float:
        """USD price of the chain's gas token, cached for 5 minutes."""
        gecko_id = NATIVE_GECKO_IDS.get(chain)
        if gecko_id is None:
            return 0.0
        if now() - self._native_prices_ts > 300:
            try:
                ids = sorted(set(NATIVE_GECKO_IDS.values()))
                self._native_prices = await self.gecko.simple_price(ids)
                self._native_prices_ts = now()
            except Exception as exc:
                logger.warning("native price refresh failed: %s", exc)
        return self._native_prices.get(gecko_id, 0.0)

    async def _execute_live(self, sig: Signal, size_usd: float) -> None:
        if not sig.token_address:
            return
        try:
            native_price = await self._native_price(sig.chain)
            await self.executor.buy(
                sig.chain,
                token_address=sig.token_address,
                notional_usd=size_usd,
                native_price_usd=native_price,
            )
        except Exception:
            logger.exception("live execution failed for %s", sig.symbol)

    # -- dashboard ---------------------------------------------------------

    def state(self) -> dict:
        """Full JSON-serializable snapshot for the dashboard."""
        summary = self.portfolio.summary(self._latest_prices)
        positions = []
        for p in self.portfolio.positions.values():
            price = self._latest_prices.get(p.key, p.entry_price)
            positions.append({
                "symbol": p.symbol, "chain": p.chain, "key": p.key,
                "entry_price": p.entry_price, "price": price,
                "size_usd": p.size_usd, "pnl_usd": round(p.unrealized_pnl(price), 2),
                "stop_loss": p.stop_loss, "take_profit": p.take_profit,
                "opened_at": p.opened_at,
                "signal_type": p.signal_type.value if p.signal_type else None,
            })
        closed = [
            {
                "symbol": t.symbol, "pnl_usd": round(t.pnl_usd, 2),
                "size_usd": t.size_usd, "exit_reason": t.exit_reason,
                "closed_at": t.closed_at,
                "signal_type": t.signal_type.value if t.signal_type else None,
            }
            for t in self.portfolio.closed[-50:]
        ][::-1]
        return {
            "ts": now(),
            "started_at": self.started_at,
            "cycle": self._cycle,
            "tracked_pairs": len(self.tracked),
            "bankroll_usd": self.risk.cfg.bankroll_usd,
            "live_armed": bool(self.executor and getattr(self.executor, "armed", False)),
            "halted": self.risk.state.halted,
            "drawdown": round(self.protections.drawdown, 4),
            "summary": summary,
            "positions": positions,
            "closed_trades": closed,
            "signals": list(self.recent_signals)[:50],
            "movers": self.movers,
            "edges": self.edges.report(),
            "equity_curve": [(round(t), round(v, 2)) for t, v in self.equity_curve],
        }

    # -- loop --------------------------------------------------------------

    async def run_forever(self) -> None:
        logger.info(
            "scanner started: %d watchlist queries, chains=%s, live=%s",
            len(self.cfg.watchlist_queries), self.cfg.chains,
            bool(self.executor and getattr(self.executor, "armed", False)),
        )
        while True:
            started = now()
            try:
                await self.run_cycle()
            except Exception:
                logger.exception("cycle failed")
            elapsed = now() - started
            await asyncio.sleep(max(5.0, self.cfg.scan_interval_s - elapsed))
