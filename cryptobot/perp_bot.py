"""Daily perp bot: the one strategy that survived the data.

`cryptobot.perp_study` walked this rule forward year by year on
Hyperliquid daily candles and it was net positive in 5 of 5 years,
beating the unconditional short in each:

    short when yesterday's move is in the top tercile of history
    AND the 3-day move is in the bottom tercile
    -- a one-day bounce inside a decline --
    target -20%, stop +10%, 14-day time exit.

Everything about how it runs follows from how it was validated:

  * DAILY cadence. Features come from closed daily candles, once a day
    after 00:00 UTC. There is no intraday signal to chase.
  * EXPANDING-WINDOW terciles. The cuts are refitted every day on every
    candle before today, exactly as in the walk-forward. Nothing in
    today's candle touches its own cut.
  * TWO BOOKS. `sim` always trades on live data as the benchmark; `real`
    trades identically and also sends orders once armed. The gap between
    them is the execution cost the backtest could only assume.
  * EXCHANGE COSTS. Fees + slippage on every paper fill, funding accrued
    hourly against open positions, so the sim book is honest about carry.

Position monitoring runs hourly against live mids: stop, target, and the
time exit. The bot persists both books and restores them on restart.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .analytics import EdgeTracker
from .book import Decision, DecisionJournal, TradingBook
from .costs import CostConfig, CostModel
from .data.hyperliquid import MEMECOINS, TAKER_FEE, HyperliquidClient
from .execlog import FILE as EXECLOG_FILE, ExecutionLog
from .execution.coinbase_futures import SizeTooSmall
from .execution.perp_exchange import PerpExecConfig, PerpExecutor
from .models import Side, Signal, SignalType, now
from .perp_study import WARMUP_DAYS, daily_features
from .protections import ProtectionConfig
from .research import bucket_of, quantiles
from .risk import RiskConfig

logger = logging.getLogger(__name__)

CHAIN = "hyperliquid"
SLIPPAGE = 0.0005


@dataclass
class PerpBotConfig:
    coins: tuple = MEMECOINS
    rule: tuple = (("move_1d", 2), ("move_3d", 0))
    target_pct: float = 0.20
    stop_pct: float = 0.10
    hold_days: int = 14
    min_history_days: int = 120        # do not fit terciles on less
    daily_at_utc_hour: int = 0
    daily_at_utc_minute: int = 10      # candle closes at 00:00; give it time
    monitor_interval_s: int = 3600
    retry_interval_s: int = 60         # after a real close fails: do not wait a whole monitor cycle
    # Walk-forward hit rate (~35%) at 2:1 is the confidence the sizer sees.
    confidence: float = 0.35
    liquidity_usd: float = 5_000_000   # perp book depth proxy for the cost model
    fetch_pause_s: float = 0.2         # between per-coin candle requests
    state_dir: Optional[Path] = None
    taker_fee: float = TAKER_FEE       # per side; the venue's, so paper fills cost what real ones do
    min_fee_per_lot: float = 0.0       # exchange minimum per contract per side
    # Basket timing: the diagnostics (cryptobot.stats) found zero cross-
    # sectional lift, i.e. on a signal day the OTHER coins earn the same
    # when shorted. "substitute" shorts another unheld coin when the
    # signalled coin's contract does not fit the slot; "all" shorts every
    # unheld coin on any signal day (research only).
    basket_mode: str = "off"           # off | substitute | all
    # coin -> units per contract. Non-empty means the venue trades whole
    # contracts: the paper book then rounds every slot down to whole
    # contracts too, so sim and real can only differ by execution.
    contract_units: dict = field(default_factory=dict)


def perp_cost_model(taker_fee: float = TAKER_FEE, min_fee_per_lot: float = 0.0) -> CostModel:
    """Exchange friction: taker fee + slippage per side, no gas."""
    return CostModel(CostConfig(
        dex_fee=taker_fee, extra_slippage=SLIPPAGE, min_fee_per_lot_usd=min_fee_per_lot,
        gas_usd={CHAIN: 0.0}, default_gas_usd=0.0,
        min_edge_multiple=4.0, min_net_risk_reward=1.25, max_gas_fraction=1.0,
    ))


def fit_cuts(history: list[dict], rule: tuple) -> dict[str, list[float]]:
    return {f: quantiles(history, f, 3) for f, _ in rule}


def rule_fires(feats: dict, cuts: dict, rule: tuple) -> bool:
    return all(bucket_of(feats[f], cuts[f]) == b for f, b in rule)


class PerpBot:
    def __init__(self, cfg: PerpBotConfig, sim_risk: RiskConfig,
                 real_risk: RiskConfig, prot_cfg: ProtectionConfig,
                 exec_cfg: PerpExecConfig,
                 client: Optional[HyperliquidClient] = None,
                 executor: Optional[PerpExecutor] = None):
        self.cfg = cfg
        self.client = client or HyperliquidClient()
        self.executor = executor or PerpExecutor(exec_cfg)
        self.costs = perp_cost_model(cfg.taker_fee, cfg.min_fee_per_lot)
        self._margin: dict[str, float] = {}   # overnight SHORT margin rate per coin, when the venue publishes it
        self.execlog = ExecutionLog(Path(cfg.state_dir) / EXECLOG_FILE if cfg.state_dir else None)
        # The allocator re-sizes the real book's slots from live capital;
        # these let it rebuild the risk config the way build() did.
        self.risk_base: dict = {}
        self.real_capital: float = real_risk.bankroll_usd
        self._last_margin_snapshot: float = 0.0
        self.sub_contract_skips = 0
        self.reconcile_report: Optional[dict] = None
        self.pending_closes: set[str] = set()   # real positions whose exit order failed
        self._last_curve_ts: float = 0.0
        # One trade per coin per hold period, measured from ENTRY: a coin
        # becomes eligible again hold_days after it was last entered,
        # whether or not that trade is still open. That is the nearest
        # one-position-at-a-time reading of the walk-forward, which scored
        # every signal day. A stop-out is a +10% squeeze, which is exactly
        # when the pattern fires again, and those immediate re-entries are
        # the losers; measuring the wait from exit instead of entry
        # dropped the replay from +1.2% to +0.3% per trade. The per-token
        # cooldown protection is therefore off here (see `_eligible`).
        import dataclasses
        prot_cfg = dataclasses.replace(prot_cfg, cooldown_s=0)
        self.eligible_at: dict[str, float] = {}
        self.books = {
            # No breakeven ratchet: the rule was validated with a fixed
            # stop and target, and on daily candles the ratchet scratches
            # every trade on its first dip (replay: 83% "stops" at entry).
            "sim": TradingBook.create("sim", sim_risk, self.costs, prot_cfg,
                                      cfg.state_dir, executes_onchain=False,
                                      breakeven_ratchet=False),
            "real": TradingBook.create("real", real_risk, self.costs, prot_cfg,
                                       cfg.state_dir, executes_onchain=True,
                                       breakeven_ratchet=False),
        }
        # Real positions the executor opened, keyed like the portfolio, so a
        # close knows the quantity to flatten.
        self.mode = "sim"
        self.journal = DecisionJournal()
        self.edges = EdgeTracker()
        self.started_at = now()
        self.last_daily_run: float = 0.0
        self._mids: dict[str, float] = {}
        self._funding: dict[str, float] = {}
        self._features: dict[str, dict[float, dict]] = {}
        self.recent_signals: deque = deque(maxlen=40)
        self.equity_curve: deque = deque(maxlen=2000)
        self.cuts: dict[str, list[float]] = {}
        self.history_days: int = 0

    # -- mode --------------------------------------------------------------

    @property
    def real_armed(self) -> bool:
        return self.executor.armed

    def set_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in ("sim", "real"):
            return False, "mode must be sim or real"
        if mode == "real" and not self.real_armed:
            return False, ("real mode needs perp.live=true, CRYPTOBOT_ARM_LIVE=yes "
                           "and a funded wallet key")
        self.mode = mode
        return True, ""

    def active_books(self) -> list[TradingBook]:
        return [self.books["sim"]] + ([self.books["real"]] if self.mode == "real" else [])

    async def close(self) -> None:
        await self.client.close()

    # -- daily signal ------------------------------------------------------

    async def evaluate(self) -> list[Signal]:
        """Fetch daily candles, refit terciles on history, apply the rule."""
        rows_hist: list[dict] = []
        today: dict[str, tuple[dict, float]] = {}
        for coin in self.cfg.coins:
            try:
                candles = await self.client.candles(coin, "1d")
            except Exception as exc:
                logger.warning("candles for %s failed: %s", coin, exc)
                continue
            # The last candle is today's, still forming. Features are
            # computed on the last CLOSED candle, and history stops before it.
            closed = candles[:-1] if candles and candles[-1].ts > now() - 86400 else candles
            if len(closed) < WARMUP_DAYS + 2:
                continue
            closes = [c.close for c in closed]
            vols = [c.volume_usd for c in closed]
            # Features of a closed candle never change, so they are cached
            # per (coin, candle ts) and only new candles are computed.
            cache = self._features.setdefault(coin, {})
            feats = []
            for i in range(WARMUP_DAYS, len(closed)):
                ts = closed[i].ts
                f = cache.get(ts)
                if f is None:
                    f = cache[ts] = daily_features(closes, vols, i)
                feats.append(f)
            rows_hist.extend(feats[:-1])
            today[coin] = (feats[-1], closes[-1])
            if self.cfg.fetch_pause_s:
                await asyncio.sleep(self.cfg.fetch_pause_s)
        self.history_days = len(rows_hist) // max(len(today), 1)
        if len(rows_hist) < self.cfg.min_history_days:
            logger.warning("only %d history rows — not fitting", len(rows_hist))
            return []
        self.cuts = fit_cuts(rows_hist, self.cfg.rule)
        signals = []
        for coin, (feats, close) in today.items():
            if not rule_fires(feats, self.cuts, self.cfg.rule):
                continue
            sig = Signal(
                ts=now(), type=SignalType.BOUNCE_SHORT, key=f"{CHAIN}:{coin}",
                chain=CHAIN, symbol=coin, side=Side.SHORT, price_usd=close,
                confidence=self.cfg.confidence, expected_move=self.cfg.target_pct,
                stop_loss_pct=self.cfg.stop_pct, take_profit_pct=self.cfg.target_pct,
                risk_reward=self.cfg.target_pct / self.cfg.stop_pct,
                liquidity_usd=self.cfg.liquidity_usd,
                reason=(f"1d move {feats['move_1d']:+.1%} (top tercile) inside a "
                        f"3d move {feats['move_3d']:+.1%} (bottom tercile)"),
            )
            signals.append(sig)
            self.recent_signals.appendleft(sig.as_dict())
        logger.info("daily evaluation: %d coins, %d signals", len(today), len(signals))
        return signals

    async def run_daily(self) -> None:
        signals = await self.evaluate()
        for sig in signals:
            for book in self.active_books():
                await self._consider(book, sig)
        self.last_daily_run = now()

    def _substitute(self, sig: Signal, coin: str, why: str) -> Optional[Signal]:
        """The same signal re-pointed at another coin at its current mid."""
        px = self._mids.get(coin)
        if not px or px <= 0:
            return None
        return Signal(**{**vars(sig), "symbol": coin, "key": f"{CHAIN}:{coin}", "price_usd": px,
                         "reason": f"{why}: {sig.symbol} signal, basket short of {coin}"})

    async def _consider(self, book: TradingBook, sig: Signal, *, substitute: bool = True) -> None:
        if self.cfg.basket_mode == "all" and substitute:
            for coin in self.cfg.coins:
                if coin == sig.symbol or f"{CHAIN}:{coin}" in book.portfolio.positions:
                    continue
                alt = self._substitute(sig, coin, "basket")
                if alt is not None:
                    await self._consider(book, alt, substitute=False)
        await self._consider_one(book, sig, substitute=substitute)

    async def _consider_one(self, book: TradingBook, sig: Signal, *, substitute: bool) -> None:
        def note(action, stage, reason, size=0.0):
            self.journal.record(Decision(
                ts=now(), book=book.name, symbol=sig.symbol, chain=sig.chain,
                signal_type=sig.type.value, action=action, stage=stage,
                reason=reason, size_usd=size, price_usd=sig.price_usd,
                confidence=sig.confidence, risk_reward=sig.risk_reward))

        if sig.key in book.portfolio.positions:
            return
        until = self.eligible_at.get(f"{book.name}:{sig.key}", 0.0)
        if now() < until:
            note("skipped", "cooldown",
                 f"entered within the last {self.cfg.hold_days}d")
            return
        allowed, why = book.protections.entry_allowed(sig.key)
        if not allowed:
            note("skipped", "protections", why)
            return
        size = book.risk.size_position(sig, list(book.portfolio.positions.values()))
        if size <= 0:
            note("skipped", "sizing", "no size: risk caps or exposure limit")
            return
        # Overnight short margin above 100% (Coinbase memecoin perps: 92-114%)
        # means a $1 short needs more than $1 of margin. The slot is the
        # margin we have, so notional = slot / rate; never above 1x either way.
        rate = self._margin.get(sig.symbol, 0.0)
        if rate > 1.0:
            size = size / rate
        lots = 0.0
        units = self.cfg.contract_units.get(sig.symbol)
        if units:
            contract_usd = units * sig.price_usd
            n = int(size // contract_usd + 1e-9)
            if n < 1:
                self.sub_contract_skips += 1
                note("skipped", "sizing",
                     f"slot ${size:.0f} is smaller than one contract (${contract_usd:.0f})", size)
                if book.executes_onchain:
                    self.execlog.skip(book=book.name, coin=sig.symbol, stage="sizing",
                                      reason=f"slot ${size:.0f} < one contract ${contract_usd:.0f}", size=size)
                if self.cfg.basket_mode == "substitute" and substitute:
                    for coin in self.cfg.coins:
                        if coin == sig.symbol or f"{CHAIN}:{coin}" in book.portfolio.positions:
                            continue
                        alt = self._substitute(sig, coin, "substitute")
                        if alt is None:
                            continue
                        alt_units = self.cfg.contract_units.get(coin)
                        if alt_units and size < alt_units * alt.price_usd:
                            continue
                        await self._consider_one(book, alt, substitute=False)
                        break
                return
            size = n * contract_usd
            lots = float(n)
        ok, why = self.costs.entry_allowed(
            sig.expected_move, size, sig.liquidity_usd, sig.chain,
            take_profit_pct=sig.take_profit_pct, stop_loss_pct=sig.stop_loss_pct)
        if not ok:
            note("skipped", "costs", why, size)
            return
        if book.executes_onchain:
            try:
                fill = await self.executor.open_short(sig.symbol, size, sig.price_usd)
            except SizeTooSmall as exc:          # whole contracts: slot too small
                note("skipped", "sizing", str(exc), size)
                return
            except Exception as exc:
                logger.exception("real short failed for %s", sig.symbol)
                note("skipped", "execution", f"order failed: {exc}", size)
                return
            # The real book records the REAL fill, not the signal price.
            intended = sig.price_usd
            sig = Signal(**{**vars(sig), "price_usd": fill.price})
            size = fill.qty * fill.price
            if units:
                lots = fill.qty / units
            if not fill.dry_run:
                self.execlog.fill(book=book.name, coin=sig.symbol, side="short", contracts=lots,
                                  qty=fill.qty, intended=intended, filled=fill.price, notional=size,
                                  fee_modelled=self._fee_side(size, lots), fee_actual=fill.fee_usd,
                                  order_id=fill.order_id, reason=sig.reason)
        pos = book.portfolio.open_from_signal(sig, size)
        pos.lots = lots
        self.eligible_at[f"{book.name}:{sig.key}"] = sig.ts + self.cfg.hold_days * 86400
        note("opened", "entry", sig.reason, size)

    def set_real_capital(self, usd: float) -> None:
        """Deployable real capital: one equal slot per coin at 1x, exposure
        never above it. Zero stops new real entries (open positions keep
        their stops and targets). Accounting (starting_equity) is untouched."""
        usd = max(0.0, float(usd))
        book = self.books["real"]
        halted = book.risk.state
        book.risk.cfg = slot_risk(self.risk_base, usd, len(self.cfg.coins))
        book.risk.state = halted
        self.real_capital = usd

    def _fee_side(self, notional: float, lots: float) -> float:
        """The fee the cost model expects for one side of this trade."""
        c = self.costs.cfg
        return max(notional * c.dex_fee, lots * c.min_fee_per_lot_usd)

    async def _margin_snapshot(self) -> None:
        """Hourly margin snapshot of the real account (every tick near the
        16:00 ET switch), so the execution log shows how close the
        overnight rate change came to a liquidation."""
        if not (self.real_armed and self.execlog.enabled and hasattr(self.executor, "balance")):
            return
        from .execlog import near_margin_switch
        t = now()
        if t - self._last_margin_snapshot < 3600 and not near_margin_switch(t):
            return
        try:
            bal = await self.executor.balance()
        except Exception as exc:
            logger.warning("margin snapshot failed: %s", exc)
            return
        self._last_margin_snapshot = t
        self.execlog.margin(balance=bal)

    # -- reconciliation ----------------------------------------------------

    async def reconcile(self) -> Optional[dict]:
        """Compare the real book with what the venue says is open. Only
        meaningful when armed (the dry-run book has no venue positions).
        Nothing is changed automatically: a mismatch is a human decision,
        so it is logged, journaled and shown on the dashboard."""
        if not self.real_armed or not hasattr(self.executor, "positions"):
            return None
        try:
            venue = await self.executor.positions()
        except Exception as exc:
            logger.warning("reconcile: venue positions unavailable: %s", exc)
            return None
        book = {p.symbol: -p.qty for p in self.books["real"].portfolio.positions.values()}
        tol = 1e-6
        report = {
            "ts": now(),
            "venue_only": sorted(c for c in venue if c not in book),
            "book_only": sorted(c for c in book if c not in venue),
            "qty_mismatch": sorted(c for c in venue if c in book
                                   and abs(venue[c] - book[c]) > tol * max(1.0, abs(book[c]))),
        }
        report["ok"] = not (report["venue_only"] or report["book_only"] or report["qty_mismatch"])
        if not report["ok"] and (self.reconcile_report is None or self.reconcile_report.get("ok")):
            logger.warning("reconcile MISMATCH: venue-only %s, book-only %s, qty %s",
                           report["venue_only"], report["book_only"], report["qty_mismatch"])
            self.journal.record(Decision(
                ts=now(), book="real", symbol=",".join(
                    report["venue_only"] + report["book_only"] + report["qty_mismatch"]),
                chain=CHAIN, signal_type=SignalType.BOUNCE_SHORT.value, action="mismatch",
                stage="reconcile",
                reason=f"venue-only {report['venue_only']}, book-only {report['book_only']}, "
                       f"size differs {report['qty_mismatch']}"))
        self.reconcile_report = report
        return report

    # -- monitoring --------------------------------------------------------

    async def monitor(self) -> None:
        try:
            self._mids = await self.client.all_mids()
        except Exception as exc:
            logger.warning("mids refresh failed: %s", exc)
            return
        try:
            rates = await self.client.funding_rates()
        except Exception as exc:
            logger.warning("funding refresh failed: %s", exc)
            rates = {}
        self._funding = rates
        if hasattr(self.client, "margin_rates"):
            try:
                self._margin = await self.client.margin_rates()
            except Exception as exc:
                logger.warning("margin rates refresh failed: %s", exc)
        t = now()
        for book in self.books.values():
            dirty = False
            for key, pos in list(book.portfolio.positions.items()):
                if pos.symbol in rates:
                    before = pos.funding_usd
                    hours = max(0.0, (t - (pos.funding_accrued_at or pos.opened_at)) / 3600.0)
                    pos.accrue_funding(rates[pos.symbol], t)
                    dirty = True
                    if book.executes_onchain and self.real_armed and hours > 0:
                        self.execlog.funding(book=book.name, coin=pos.symbol, rate_hourly=rates[pos.symbol],
                                             hours=hours, notional=pos.size_usd, usd=pos.funding_usd - before)
                mid = self._mids.get(pos.symbol)
                if mid is None:
                    continue
                reason = book.portfolio.check_exit(key, mid)
                if reason is None and now() - pos.opened_at >= self.cfg.hold_days * 86400:
                    reason = "time_exit"
                if reason is None:
                    self.pending_closes.discard(key)        # exit no longer due: stop fast-polling
                    continue
                price = mid
                if book.executes_onchain:
                    try:
                        fill = await self.executor.close(pos.symbol, pos.qty, mid)
                        price = fill.price
                        self.pending_closes.discard(key)
                        if not fill.dry_run:
                            self.execlog.fill(book=book.name, coin=pos.symbol, side="close", contracts=pos.lots,
                                              qty=fill.qty, intended=mid, filled=fill.price,
                                              notional=fill.qty * fill.price,
                                              fee_modelled=self._fee_side(fill.qty * fill.price, pos.lots),
                                              fee_actual=fill.fee_usd, order_id=fill.order_id, reason=reason)
                    except Exception as exc:
                        logger.exception("real close failed for %s — keeping position",
                                         pos.symbol)
                        if key not in self.pending_closes:
                            self.journal.record(Decision(
                                ts=now(), book=book.name, symbol=pos.symbol, chain=CHAIN,
                                signal_type=SignalType.BOUNCE_SHORT.value, action="failed",
                                stage="execution", size_usd=pos.size_usd, price_usd=mid,
                                reason=f"{reason} close failed: {exc}; retrying every "
                                       f"{self.cfg.retry_interval_s}s"))
                        self.pending_closes.add(key)
                        continue
                trade = book.portfolio.close(key, price, reason)
                if trade is None:
                    continue
                was_halted = book.risk.state.halted
                book.risk.record_pnl(trade.pnl_usd)
                book.protections.on_trade_closed(trade)
                if book.risk.state.halted and not was_halted:
                    self.journal.record(Decision(
                        ts=now(), book=book.name, symbol="*", chain=CHAIN,
                        signal_type=SignalType.BOUNCE_SHORT.value, action="halted",
                        stage="execution",
                        reason=f"daily loss {book.risk.state.daily_pnl:+.2f} hit the limit; "
                               f"no new entries until the day rolls"))
                if book.name == "sim":
                    self.edges.record(trade)
                self.journal.record(Decision(
                    ts=now(), book=book.name, symbol=pos.symbol, chain=CHAIN,
                    signal_type=SignalType.BOUNCE_SHORT.value, action="closed",
                    stage="exit", reason=f"{reason} (funding {trade.funding_usd:+.2f})",
                    size_usd=pos.size_usd, price_usd=price, pnl_usd=trade.pnl_usd))
                dirty = False
            if dirty:
                book.portfolio.save()
        self.pending_closes &= {k for b in self.books.values() for k in b.portfolio.positions}
        await self._margin_snapshot()
        prices = {k: self._mids.get(k.split(":")[1], 0.0) for b in self.books.values()
                  for k in b.portfolio.positions}
        if now() - self._last_curve_ts >= 3600:          # hourly points whatever the monitor cadence
            self._last_curve_ts = now()
            self.equity_curve.append((now(), self.books["sim"].equity(prices),
                                      self.books["real"].equity(prices)))

    # -- dashboard ---------------------------------------------------------

    def state(self) -> dict:
        prices = {}
        for b in self.books.values():
            for k, p in b.portfolio.positions.items():
                prices[k] = self._mids.get(p.symbol, p.entry_price)
        return {
            "ts": now(), "started_at": self.started_at,
            "cycle": int(self.last_daily_run),
            "tracked_pairs": len(self.cfg.coins),
            "mode": self.mode,
            "real_unlocked": self.real_armed,
            "real_locked_reason": "" if self.real_armed else
                "needs perp.live=true, CRYPTOBOT_ARM_LIVE=yes and a wallet key",
            "chains": [CHAIN],
            "strategy": {
                "rule": " & ".join(f"{f}[{b}]" for f, b in self.cfg.rule),
                "target_pct": self.cfg.target_pct, "stop_pct": self.cfg.stop_pct,
                "hold_days": self.cfg.hold_days, "cuts": self.cuts,
                "history_days": self.history_days,
                "last_daily_run": self.last_daily_run,
                "funding_hourly": {c: self._funding.get(c, 0.0) for c in self.cfg.coins},
                "short_margin": {c: self._margin.get(c, 0.0) for c in self.cfg.coins},
            },
            "reconcile": self.reconcile_report,
            "books": {n: b.state(prices, self.edges) for n, b in self.books.items()},
            "decisions": self.journal.recent(60),
            "gate_counts": self.journal.counts(),
            "signals": list(self.recent_signals),
            "movers": [],
            "edges": self.edges.report(),
            "equity_curve": [(round(t), round(a, 2), round(r, 2))
                             for t, a, r in self.equity_curve],
        }

    # -- loop --------------------------------------------------------------

    def _daily_due(self, at: Optional[float] = None) -> bool:
        """True once per UTC day, once the scheduled minute has passed."""
        t = now() if at is None else at
        day = int(t // 86400)
        last_day = int(self.last_daily_run // 86400) if self.last_daily_run else -1
        scheduled = (self.cfg.daily_at_utc_hour * 3600
                     + self.cfg.daily_at_utc_minute * 60)
        return day > last_day and (t % 86400) >= scheduled

    async def run_forever(self) -> None:
        logger.info("perp bot up: %d coins, rule %s, mode %s", len(self.cfg.coins),
                    self.cfg.rule, self.mode)
        await self.reconcile()          # before trading: does the venue agree with the book?
        await self.run_daily()          # evaluate on startup so the book is current
        while True:
            await self.monitor()
            await self.reconcile()
            if self._daily_due():
                await self.run_daily()
            await asyncio.sleep(self.cfg.retry_interval_s if self.pending_closes
                                else self.cfg.monitor_interval_s)


class ReplayClient:
    """Reveals cached daily candles up to a moving 'today' so the live bot
    can be driven through history one day at a time."""

    def __init__(self, pools: dict):
        self.series = {meta.symbol: candles for _, (meta, candles) in pools.items()}
        self.today: float = 0.0
        self.mids: dict[str, float] = {}
        self.funding: dict[str, float] = {}

    async def candles(self, coin, interval="1d", **kw):
        return [c for c in self.series.get(coin, []) if c.ts < self.today]

    async def all_mids(self):
        return dict(self.mids)

    async def funding_rates(self):
        return dict(self.funding)

    async def close(self):
        pass


async def replay(pools: dict, start_ts: float, cfg: PerpBotConfig, *,
                 bankroll: float = 10_000.0, daily_funding: float = 0.0,
                 on_capital: bool = False) -> dict:
    """Run the bot's own evaluate/consider/monitor through history.

    Exits are checked against each day's high (stop side) and then low
    (target side), the study's conservative convention. Sizing caps are
    lifted so every signal trades, which is what the study measured; the
    number that matters is the mean net return per trade, compared with
    `perp_study --walk-forward` over the same window.
    """
    import dataclasses
    import datetime as dt
    client = ReplayClient(pools)
    cfg = dataclasses.replace(cfg, fetch_pause_s=0.0, coins=tuple(client.series))
    if on_capital:
        # The deployed sizing: one equal slot per coin, bank never exceeded,
        # whole contracts if the venue has them. Result is return on the bank.
        risk = slot_risk({}, bankroll, len(cfg.coins))
    else:
        risk = RiskConfig(bankroll_usd=bankroll, risk_per_trade_pct=0.001,
                          max_position_usd=10.0, max_total_exposure_usd=1e9,
                          max_daily_loss_usd=1e9, max_open_positions=10_000,
                          min_position_usd=10.0, min_confidence=0.0)
    prot = ProtectionConfig(cooldown_s=0, stoploss_guard_limit=10_000,
                            low_profit_min_trades=10_000, max_drawdown_pct=1.0)
    bot = PerpBot(cfg, risk, risk, prot, PerpExecConfig(), client=client,
                  executor=PerpExecutor(PerpExecConfig()))
    days = sorted({int(c.ts // 86400) * 86400 for cs in client.series.values()
                   for c in cs if c.ts >= start_ts})
    # One virtual clock for every module that reads the time: this one
    # (under whichever name it was imported — `python -m` runs it as
    # __main__), and the portfolio / protections / risk layers, whose
    # cooldowns and daily limits would otherwise run on wall-clock time.
    import cryptobot.portfolio as pf_mod
    import cryptobot.protections as prot_mod
    import cryptobot.risk as risk_mod
    g = globals()
    clocks = [g, vars(pf_mod), vars(prot_mod), vars(risk_mod)]
    saved = [c["now"] for c in clocks]
    vclock = [0.0]

    def set_clock(t: float) -> None:
        vclock[0] = t

    for c in clocks:
        c["now"] = lambda: vclock[0]
    sim = bot.books["sim"].portfolio

    def barrier_price(sym: str, c, phase: str, at: float) -> float:
        """Fill at the barrier, not the day's extreme: an hourly monitor
        exits near the level, and the study assumed exactly that. A time
        exit fires on the first tick after the hold elapses, which is the
        open of that day, not its high."""
        extreme = getattr(c, phase)
        pos = sim.positions.get(f"{CHAIN}:{sym}")
        if pos is None:
            return extreme
        if at - pos.opened_at >= cfg.hold_days * 86400:
            return c.open
        if phase == "high" and extreme >= pos.stop_loss:
            return pos.stop_loss
        if phase == "low" and extreme <= pos.take_profit:
            return pos.take_profit
        return extreme

    try:
        for day in days:
            # 00:10 UTC: yesterday's candle has closed; evaluate and enter at
            # its close (the study's entry price).
            client.today = day
            set_clock(day + 600)
            await bot.run_daily()
            # During the day: stop on the high, then target on the low.
            todays = {sym: next((c for c in cs if int(c.ts // 86400) * 86400 == day), None)
                      for sym, cs in client.series.items()}
            for phase in ("high", "low", "close"):
                at = day + {"high": 3600 * 8, "low": 3600 * 16, "close": 86400 - 60}[phase]
                client.mids = {sym: barrier_price(sym, c, phase, at)
                               for sym, c in todays.items() if c}
                set_clock(at)
                client.funding = {sym: daily_funding / 24.0 for sym in client.mids} \
                    if phase == "close" else {}
                await bot.monitor()
    finally:
        for c, original in zip(clocks, saved):
            c["now"] = original
    book = bot.books["sim"]
    closed = book.portfolio.closed
    by_year: dict[int, list[float]] = {}
    pnl_year: dict[int, float] = {}
    for t in closed:
        y = dt.datetime.utcfromtimestamp(t.opened_at).year
        by_year.setdefault(y, []).append(t.pnl_usd / t.size_usd)
        pnl_year[y] = pnl_year.get(y, 0.0) + t.pnl_usd
    return {
        "bankroll": bankroll,
        "on_capital_by_year": {y: pnl_year[y] / bankroll for y in sorted(pnl_year)},
        "skipped_sub_contract": bot.sub_contract_skips,
        "trades": len(closed),
        "open": len(book.portfolio.positions),
        "mean_net": (sum(t.pnl_usd / t.size_usd for t in closed) / len(closed)) if closed else 0.0,
        "by_year": {y: (len(v), sum(v) / len(v)) for y, v in sorted(by_year.items())},
        "exits": {r: sum(1 for t in closed if t.exit_reason == r)
                  for r in {t.exit_reason for t in closed}},
    }


def load_config(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text()) or {}


def slot_risk(base: dict, bank: float, n_coins: int) -> RiskConfig:
    """One equal slot per coin at 1x: every signal gets bank / n_coins of
    notional and total exposure never exceeds the bank. That is how the
    rule was measured on capital (+1.4% to +35.8% a year, max drawdown
    -15.5%, all 18 slots in use at the worst moment); sizing by stop
    distance would put ~15% of the bank in each short and lever up when
    signals cluster, which they do."""
    slot = bank / max(1, n_coins)
    return RiskConfig(**{**base, "bankroll_usd": bank, "max_position_usd": slot,
                         "min_position_usd": slot,
                         "risk_per_trade_pct": slot * 0.10 / bank if bank else 0.0,
                         "max_total_exposure_usd": bank, "max_open_positions": n_coins,
                         "max_daily_loss_usd": bank * 0.10, "min_confidence": 0.0})


VENUES = ("hyperliquid", "coinbase", "kalshi")


def build(cfg: dict, state_dir: Optional[Path]) -> PerpBot:
    """Venue comes from `perp.venue`. On `coinbase` (Coinbase Derivatives,
    the CFTC-regulated venue US clients can use) the universe is the three
    memecoins it lists, orders are whole contracts through the Coinbase
    SDK, and market data can come from Coinbase too (`perp.data`), seeded
    with cached history for the tercile fit."""
    from .carry_bot import allocation
    perp = cfg.get("perp", {})
    venue = perp.get("venue", "hyperliquid")
    if venue not in VENUES:
        raise ValueError(f"perp.venue must be one of {VENUES}")
    share = allocation(cfg, "bounce_short")
    sim_bank = share * float(cfg.get("sim", {}).get("bankroll_usd", 200))
    risk_kw = {k: v for k, v in cfg.get("risk", {}).items()
               if k in RiskConfig.__dataclass_fields__}
    venue_kw: dict = {}
    if venue == "coinbase":
        from .execution.coinbase_futures import CONTRACTS, US_COINS
        from .execution.coinbase_futures import TAKER_FEE as CB_FEE
        coins = tuple(perp.get("coins") or US_COINS)
        from .execution.coinbase_futures import MIN_FEE_PER_CONTRACT
        venue_kw = {"taker_fee": CB_FEE, "min_fee_per_lot": MIN_FEE_PER_CONTRACT,
                    "contract_units": {c: CONTRACTS[c].units_per_contract for c in coins if c in CONTRACTS}}
    elif venue == "kalshi":
        from .execution.kalshi_perps import CONTRACTS as K_CONTRACTS
        from .execution.kalshi_perps import TAKER_FEE as K_FEE
        from .execution.kalshi_perps import US_COINS as K_COINS
        coins = tuple(perp.get("coins") or K_COINS)
        venue_kw = {"taker_fee": K_FEE,
                    "contract_units": {c: K_CONTRACTS[c].units_per_contract for c in coins if c in K_CONTRACTS}}
    else:
        coins = tuple(perp.get("coins") or MEMECOINS)
    real_bank = share * float(risk_kw.get("bankroll_usd", 1000))
    real_risk = slot_risk(risk_kw, real_bank, len(coins))
    sim_risk = slot_risk(risk_kw, sim_bank, len(coins))
    prot_kw = {k: v for k, v in cfg.get("protections", {}).items()
               if k in ProtectionConfig.__dataclass_fields__}
    bot_cfg = PerpBotConfig(
        target_pct=float(perp.get("target_pct", 0.20)),
        stop_pct=float(perp.get("stop_pct", 0.10)),
        hold_days=int(perp.get("hold_days", 14)),
        monitor_interval_s=int(perp.get("monitor_interval_s", 3600)),
        basket_mode=str(perp.get("basket_mode", "off")),
        coins=coins,
        state_dir=state_dir,
        **venue_kw,
    )
    exec_cfg = PerpExecConfig(
        live=bool(perp.get("live", False)),
        private_key_env=perp.get("private_key_env", "CRYPTOBOT_PRIVATE_KEY"),
        max_trade_usd=float(perp.get("max_trade_usd", 50)),
        max_slippage=float(perp.get("max_slippage", 0.01)),
    )
    executor = client = None
    if venue == "coinbase":
        from .execution.coinbase_futures import CoinbaseExecConfig, CoinbaseFuturesExecutor
        executor = CoinbaseFuturesExecutor(CoinbaseExecConfig(
            live=bool(perp.get("live", False)),
            max_trade_usd=float(perp.get("max_trade_usd", 500)),
            max_slippage=float(perp.get("max_slippage", 0.01))))
        if perp.get("data", "coinbase") == "coinbase":
            from .data.coinbase_futures import CoinbaseMarketData
            seed = perp.get("history_seed")
            seed_path = Path(seed) if seed else None
            if seed_path and not seed_path.exists() and state_dir:
                seed_path = Path(state_dir) / seed_path.name     # inside Docker, state is /data
            client = CoinbaseMarketData(history_seed=seed_path)
    elif venue == "kalshi":
        from .execution.kalshi_perps import KalshiExecConfig, KalshiPerpsExecutor
        executor = KalshiPerpsExecutor(KalshiExecConfig(
            live=bool(perp.get("live", False)),
            base_url=str(perp.get("kalshi_base_url", KalshiExecConfig.base_url)),
            max_trade_usd=float(perp.get("max_trade_usd", 500)),
            max_slippage=float(perp.get("max_slippage", 0.005))))
        if perp.get("data", "kalshi") == "kalshi":
            from .data.kalshi_perps import KalshiMarketData
            seed = perp.get("history_seed")
            seed_path = Path(seed) if seed else None
            if seed_path and not seed_path.exists() and state_dir:
                seed_path = Path(state_dir) / seed_path.name
            client = KalshiMarketData(history_seed=seed_path, base_url=executor.cfg.base_url)
    bot = PerpBot(bot_cfg, sim_risk, real_risk, ProtectionConfig(**prot_kw), exec_cfg,
                  client=client, executor=executor)
    bot.risk_base = dict(risk_kw)
    return bot


async def _main(args) -> int:
    cfg = load_config(args.config)
    if args.replay:
        import datetime as dt
        import pickle
        pools = pickle.loads(args.replay.read_bytes())
        start = dt.datetime.fromisoformat(args.replay_from).replace(
            tzinfo=dt.timezone.utc).timestamp()
        perp = cfg.get("perp", {})
        venue_kw = {}
        if perp.get("venue") == "coinbase":
            from .execution.coinbase_futures import CONTRACTS
            from .execution.coinbase_futures import TAKER_FEE as CB_FEE
            from .execution.coinbase_futures import MIN_FEE_PER_CONTRACT
            venue_kw = {"taker_fee": CB_FEE}
            if args.whole_contracts:
                venue_kw["contract_units"] = {c: k.units_per_contract for c, k in CONTRACTS.items()}
                venue_kw["min_fee_per_lot"] = MIN_FEE_PER_CONTRACT
        rcfg = PerpBotConfig(target_pct=float(perp.get("target_pct", 0.20)),
                             stop_pct=float(perp.get("stop_pct", 0.10)),
                             hold_days=int(perp.get("hold_days", 14)), basket_mode=args.basket, **venue_kw)
        rep = await replay(pools, start, rcfg, bankroll=args.bankroll,
                           on_capital=args.on_capital)
        print(f"replay from {args.replay_from}: {rep['trades']} closed trades, "
              f"{rep['open']} still open, mean net {100 * rep['mean_net']:+.2f}%/trade"
              f"; fee {100 * rcfg.taker_fee:.2f}%/side"
              + (f" (min ${rcfg.min_fee_per_lot:.2f}/contract)" if rcfg.min_fee_per_lot else "")
              + (f"; whole contracts, {rep['skipped_sub_contract']} signals too small"
                 if rcfg.contract_units else ""))
        for y, (n, m) in rep["by_year"].items():
            cap = rep["on_capital_by_year"].get(y, 0.0)
            print(f"  {y}: n={n:4d}  mean net {100 * m:+.2f}%"
                  + (f"   on ${args.bankroll:,.0f}: {100 * cap:+.1f}%" if args.on_capital else ""))
        print(f"  exits: {rep['exits']}")
        return 0
    bot = build(cfg, args.state_dir)
    if args.once:
        signals = await bot.evaluate()
        for s in signals:
            print(s.as_dict())
        print(f"{len(signals)} signal(s); terciles {bot.cuts}")
        await bot.close()
        return 0
    if args.dashboard:
        import uvicorn
        from .dashboard import create_app
        app = create_app(bot, token=args.token)
        server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port,
                                               log_level="warning"))
        await asyncio.gather(bot.run_forever(), server.serve())
    else:
        await bot.run_forever()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="daily bounce-short perp bot")
    ap.add_argument("--config", type=Path, default=Path("cryptobot_config.yaml"))
    ap.add_argument("--state-dir", type=Path, default=Path("."))
    ap.add_argument("--once", action="store_true", help="evaluate today and exit")
    ap.add_argument("--replay", type=Path, metavar="CACHE",
                    help="drive the bot through cached daily history (pickle)")
    ap.add_argument("--replay-from", default="2025-05-20")
    ap.add_argument("--bankroll", type=float, default=10_000.0)
    ap.add_argument("--on-capital", action="store_true",
                    help="replay with the deployed sizing (one slot per coin) and report return on the bankroll")
    ap.add_argument("--whole-contracts", action="store_true",
                    help="coinbase venue: round slots down to whole contracts, as the real book does")
    ap.add_argument("--basket", default="off", choices=("off", "substitute", "all"),
                    help="basket timing: substitute another coin when the contract does not fit, or short all unheld coins on a signal day")
    ap.add_argument("--dashboard", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8082)
    ap.add_argument("--token", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
