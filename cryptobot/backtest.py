"""Backtest harness: replay historical DEX candles through the live
detectors, risk sizing, and exit logic, and report per-pattern edge.

Usage:
    python -m cryptobot.backtest PEPE WIF BRETT --days 3
    python -m cryptobot.backtest --chain base BRETT --days 7 --json

Candles come from GeckoTerminal (5-minute buckets per pool). The replay
uses the SAME VolatilityEngine, detectors, RiskManager, Portfolio, and
ProtectionManager the live scanner uses — the only differences are
documented honestly rather than papered over:

  * candles carry no buy/sell transaction split, so the breakout
    detector's buy-ratio gate is neutralized (ratio fixed at its
    threshold) — backtest breakout results are therefore slightly
    OPTIMISTIC and live results should be expected to be tighter;
  * liquidity/FDV are today's values held constant through the replay;
  * intra-candle sequence is unknown, so exits are CONSERVATIVE: when a
    candle spans both the stop and the target, the stop is assumed to
    have hit first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass

from .analytics import EdgeTracker
from .costs import CostConfig, CostModel
from .data.dexscreener import DexScreenerClient
from .data.geckoterminal import Candle, GeckoTerminalClient
from .models import TokenSnapshot
from .portfolio import Portfolio
from .protections import ProtectionConfig, ProtectionManager
from .risk import RiskConfig, RiskManager
from .signals import SignalConfig, detect_all
from .volatility import VolatilityEngine

logger = logging.getLogger(__name__)

CANDLES_PER_HOUR = 12      # 5-minute buckets
CANDLES_PER_DAY = 288


@dataclass
class PoolMeta:
    chain: str
    pair_address: str
    symbol: str
    token_address: str
    liquidity_usd: float
    fdv_usd: float | None


def snapshot_from_candles(candles: list[Candle], i: int, meta: PoolMeta,
                          neutral_buy_ratio: float) -> TokenSnapshot:
    """Build the TokenSnapshot the scanner would have seen at candle i."""
    c = candles[i]

    def change(back: int) -> float | None:
        j = i - back
        if j < 0 or candles[j].close <= 0:
            return None
        return c.close / candles[j].close - 1.0

    vol_1h = sum(x.volume_usd for x in candles[max(0, i - CANDLES_PER_HOUR + 1): i + 1])
    vol_24h = sum(x.volume_usd for x in candles[max(0, i - CANDLES_PER_DAY + 1): i + 1])
    # Fabricate a neutral txn split that exactly meets the configured
    # gate — see module docstring for why.
    buys = int(1000 * neutral_buy_ratio)
    return TokenSnapshot(
        ts=c.ts, chain=meta.chain, pair_address=meta.pair_address,
        base_symbol=meta.symbol, base_address=meta.token_address,
        quote_symbol="?", price_usd=c.close,
        change_5m=change(1), change_1h=change(CANDLES_PER_HOUR),
        change_6h=change(6 * CANDLES_PER_HOUR), change_24h=change(CANDLES_PER_DAY),
        volume_24h_usd=vol_24h, volume_1h_usd=vol_1h,
        liquidity_usd=meta.liquidity_usd, fdv_usd=meta.fdv_usd,
        txns_24h_buys=buys, txns_24h_sells=1000 - buys,
        pair_created_at=None,
    )


class Backtester:
    def __init__(self, sig_cfg: SignalConfig, risk_cfg: RiskConfig,
                 prot_cfg: ProtectionConfig | None = None,
                 cost_cfg: CostConfig | None = None):
        self.sig_cfg = sig_cfg
        self.risk = RiskManager(risk_cfg)
        self.costs = CostModel(cost_cfg)
        self.portfolio = Portfolio(cost_model=self.costs)
        self.edges = EdgeTracker()
        self.protections = ProtectionManager(
            prot_cfg or ProtectionConfig(), risk_cfg.bankroll_usd)
        # Protections/risk measure wall-clock; the replay drives a virtual
        # clock instead, so patch their notion of now.
        self._vclock = 0.0
        import cryptobot.portfolio as pf_mod
        import cryptobot.protections as prot_mod
        import cryptobot.risk as risk_mod
        prot_mod.now = lambda: self._vclock          # type: ignore[assignment]
        risk_mod.now = lambda: self._vclock          # type: ignore[assignment]
        pf_mod.now = lambda: self._vclock            # type: ignore[assignment]

    def run(self, pools: dict[str, tuple[PoolMeta, list[Candle]]],
            max_position_age_s: float = 6 * 3600) -> dict:
        """Replay all pools in parallel on a shared 5-minute clock."""
        engine = VolatilityEngine()
        # Merge all candle timestamps into one ordered clock.
        clock = sorted({c.ts for _, cs in pools.values() for c in cs})
        index: dict[str, dict[float, int]] = {
            key: {c.ts: i for i, c in enumerate(cs)}
            for key, (_, cs) in pools.items()
        }
        signals_seen = 0

        for ts in clock:
            self._vclock = ts
            for key, (meta, candles) in pools.items():
                i = index[key].get(ts)
                if i is None or i < CANDLES_PER_DAY:   # need a 24h baseline
                    continue
                c = candles[i]

                # 1. exits first, on this candle's range (stop-first when
                #    both stop and target are inside the candle).
                pos = self.portfolio.positions.get(key)
                if pos is not None:
                    exit_price, reason = None, None
                    if c.low <= pos.stop_loss:
                        exit_price, reason = pos.stop_loss, (
                            "stop_loss" if pos.stop_loss <= pos.entry_price
                            else "trailing_stop")
                    elif pos.trail_pct is None and c.high >= pos.take_profit:
                        exit_price, reason = pos.take_profit, "take_profit"
                    elif ts - pos.opened_at > max_position_age_s:
                        exit_price, reason = c.close, "time_stop"
                    if exit_price is None:
                        # No exit: let the trailing logic ratchet on the high.
                        self.portfolio.check_exit(key, c.high)
                        p2 = self.portfolio.positions.get(key)
                        if p2 is not None and c.low <= p2.stop_loss < c.high:
                            exit_price, reason = p2.stop_loss, "trailing_stop"
                    if exit_price is not None:
                        trade = self.portfolio.close(key, exit_price, reason)
                        if trade:
                            self.risk.record_pnl(trade.pnl_usd)
                            self.edges.record(trade)
                            self.protections.on_trade_closed(trade)
                        continue

                # 2. entries on the candle close.
                snap = snapshot_from_candles(
                    candles, i, meta, self.sig_cfg.breakout_min_buy_ratio)
                vol = engine.observe(snap)
                sigs = detect_all(snap, vol, self.sig_cfg)
                signals_seen += len(sigs)
                for sig in sigs:
                    if sig.key in self.portfolio.positions:
                        continue
                    if not self.protections.entry_allowed(sig.key)[0]:
                        continue
                    sig.confidence = min(1.0, sig.confidence
                                         * self.edges.confidence_multiplier(sig.type.value))
                    size = self.risk.size_position(
                        sig, list(self.portfolio.positions.values()))
                    if size <= 0:
                        continue
                    if not self.costs.entry_allowed(
                            sig.expected_move, size, sig.liquidity_usd,
                            sig.chain)[0]:
                        continue
                    self.portfolio.open_from_signal(sig, size)
                    break

        # Force-close whatever is still open at the end.
        for key in list(self.portfolio.positions.keys()):
            _, candles = pools[key]
            trade = self.portfolio.close(key, candles[-1].close, "backtest_end")
            if trade:
                self.edges.record(trade)

        return {
            "candles": sum(len(cs) for _, cs in pools.values()),
            "pools": len(pools),
            "signals": signals_seen,
            "trades": len(self.portfolio.closed),
            "realized_pnl": round(self.portfolio.realized_pnl, 2),
            "summary": self.portfolio.summary(),
            "edges": self.edges.report(),
        }


async def resolve_pools(symbols: list[str], chain: str | None,
                        days: float) -> dict[str, tuple[PoolMeta, list[Candle]]]:
    """Symbol -> most liquid pool (optionally on one chain) -> candles."""
    from .data.geckoterminal import GT_NETWORKS
    dex = DexScreenerClient()
    gt = GeckoTerminalClient()
    pools: dict[str, tuple[PoolMeta, list[Candle]]] = {}
    try:
        def norm(s: str) -> str:
            return s.upper().lstrip("$")

        for sym in symbols:
            snaps = await dex.search(sym)
            snaps = [s for s in snaps
                     if norm(s.base_symbol) == norm(sym)
                     and s.chain in GT_NETWORKS
                     and (chain is None or s.chain == chain)]
            # Fresh pools fake liquidity to rank in search; demand a pool
            # old enough to cover the window and rank by real 24h volume.
            aged = [s for s in snaps
                    if s.age_hours is None or s.age_hours >= days * 24]
            if not aged:
                logger.warning("no pool with %.0f days of history for %s",
                               days, sym)
                continue
            best = max(aged, key=lambda s: s.volume_24h_usd)
            meta = PoolMeta(
                chain=best.chain, pair_address=best.pair_address,
                symbol=best.base_symbol, token_address=best.base_address,
                liquidity_usd=best.liquidity_usd, fdv_usd=best.fdv_usd,
            )
            logger.info("%s -> %s:%s ($%.0fk liquidity), fetching %.1f days…",
                        sym, best.chain, best.pair_address[:10],
                        best.liquidity_usd / 1000, days)
            candles = await gt.ohlcv_history(
                best.chain, best.pair_address, days=days)
            if len(candles) > CANDLES_PER_DAY:
                pools[best.key] = (meta, candles)
            else:
                logger.warning("%s: only %d candles, need >%d — skipped",
                               sym, len(candles), CANDLES_PER_DAY)
    finally:
        await dex.close()
        await gt.close()
    return pools


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay historical candles through the bot's detectors")
    parser.add_argument("symbols", nargs="+", help="token symbols, e.g. PEPE WIF")
    parser.add_argument("--chain", default=None,
                        help="restrict to one chain (default: most liquid pool anywhere)")
    parser.add_argument("--days", type=float, default=3.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    pools = await resolve_pools(args.symbols, args.chain, args.days + 1.0)
    if not pools:
        print("no pools with enough history")
        return 1

    bt = Backtester(SignalConfig(), RiskConfig())
    report = bt.run(pools)

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n=== Backtest: {report['pools']} pools, "
              f"{report['candles']} candles, {report['signals']} signals ===")
        print(f"trades: {report['trades']}   "
              f"realized PnL: ${report['realized_pnl']}   "
              f"win rate: {report['summary']['win_rate']}")
        for pattern, stats in report["edges"]["by_signal_type"].items():
            print(f"  {pattern:18s} {stats['trades']:3d} trades  "
                  f"win {stats['win_rate']:.0%}  "
                  f"expectancy {stats['expectancy_per_dollar']:+.3f}/$  "
                  f"pnl ${stats['total_pnl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
