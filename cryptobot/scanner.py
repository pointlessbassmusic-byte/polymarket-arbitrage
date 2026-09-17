"""Main scan-and-trade loop.

Each cycle:
  1. Build the candidate universe: configured watchlist queries + DexScreener
     boosted tokens + CoinGecko trending (attention flows precede volatility).
  2. Snapshot every tracked pair, feed the volatility engine.
  3. Rank by multi-window "wildness", run the signal detectors.
  4. Periodically pull all pools for the wildest tokens and check cross-DEX
     price gaps.
  5. Manage open (paper) positions: trailing stops, targets, time stops.
  6. Optionally snapshot OpenSea collections for NFT floor swings (log-only).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .data.coingecko import CoinGeckoClient
from .data.dexscreener import DexScreenerClient
from .data.opensea import OpenSeaClient
from .models import Signal, SignalType, TokenSnapshot, now
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
    opensea_collections: list[str] = field(default_factory=list)
    opensea_api_key: str = ""
    nft_floor_move_threshold: float = 0.10


class Scanner:
    def __init__(self, scan_cfg: ScannerConfig, sig_cfg: SignalConfig,
                 risk_cfg: RiskConfig, state_dir: Optional[Path] = None,
                 executor=None):
        self.cfg = scan_cfg
        self.sig_cfg = sig_cfg
        self.dex = DexScreenerClient()
        self.gecko = CoinGeckoClient()
        self.opensea = (
            OpenSeaClient(scan_cfg.opensea_api_key)
            if scan_cfg.opensea_api_key and scan_cfg.opensea_collections else None
        )
        self.vol = VolatilityEngine()
        self.risk = RiskManager(risk_cfg)
        self.portfolio = Portfolio(
            state_file=(state_dir / "cryptobot_portfolio.json") if state_dir else None
        )
        self.executor = executor
        # key -> (chain, base_address) so we can deep-scan pools later
        self.tracked: dict[str, tuple[str, str]] = {}
        self._cycle = 0
        self._latest_prices: dict[str, float] = {}

    async def close(self) -> None:
        await self.dex.close()
        await self.gecko.close()
        if self.opensea:
            await self.opensea.close()

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
        self._act_on_signals(signals)

        if self.opensea and self._cycle % 5 == 1:
            await self._nft_pass()

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

    async def _nft_pass(self) -> None:
        assert self.opensea is not None
        for slug in self.cfg.opensea_collections:
            try:
                snap = await self.opensea.collection_stats(slug)
            except Exception as exc:
                logger.warning("opensea %s failed: %s", slug, exc)
                continue
            if snap and abs(snap.one_day_change) >= self.cfg.nft_floor_move_threshold:
                logger.info(
                    "NFT floor swing: %s floor %.4f ETH, 24h %+.1f%%, 7d %+.1f%%",
                    slug, snap.floor_price_eth,
                    100 * snap.one_day_change, 100 * snap.seven_day_change,
                )

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

    def _act_on_signals(self, signals: list[Signal]) -> None:
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
            size = self.risk.size_position(sig, list(self.portfolio.positions.values()))
            if size <= 0:
                continue
            self.portfolio.open_from_signal(sig, size)
            if self.executor is not None:
                asyncio.create_task(self._execute_live(sig, size))

    async def _execute_live(self, sig: Signal, size_usd: float) -> None:
        try:
            # Buying <token> with the chain's native gas token.
            quote = await self.executor.quote(
                sig.chain,
                sell_token="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # native
                buy_token=sig.key.split(":", 1)[1],
                sell_amount_usd=size_usd,
                sell_token_price_usd=1.0,  # placeholder: executor re-prices
            )
            if quote:
                await self.executor.execute_swap(sig.chain, quote, size_usd)
        except Exception:
            logger.exception("live execution failed for %s", sig.symbol)

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
