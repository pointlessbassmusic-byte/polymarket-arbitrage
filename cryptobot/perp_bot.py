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
    # Walk-forward hit rate (~35%) at 2:1 is the confidence the sizer sees.
    confidence: float = 0.35
    liquidity_usd: float = 5_000_000   # perp book depth proxy for the cost model
    fetch_pause_s: float = 0.2         # between per-coin candle requests
    state_dir: Optional[Path] = None


def perp_cost_model() -> CostModel:
    """Exchange friction: taker fee + slippage per side, no gas."""
    return CostModel(CostConfig(
        dex_fee=TAKER_FEE, extra_slippage=SLIPPAGE,
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
        self.costs = perp_cost_model()
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

    async def _consider(self, book: TradingBook, sig: Signal) -> None:
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
        ok, why = self.costs.entry_allowed(
            sig.expected_move, size, sig.liquidity_usd, sig.chain,
            take_profit_pct=sig.take_profit_pct, stop_loss_pct=sig.stop_loss_pct)
        if not ok:
            note("skipped", "costs", why, size)
            return
        if book.executes_onchain:
            try:
                fill = await self.executor.open_short(sig.symbol, size, sig.price_usd)
            except Exception as exc:
                logger.exception("real short failed for %s", sig.symbol)
                note("skipped", "execution", f"order failed: {exc}", size)
                return
            # The real book records the REAL fill, not the signal price.
            sig = Signal(**{**vars(sig), "price_usd": fill.price})
            size = fill.qty * fill.price
        book.portfolio.open_from_signal(sig, size)
        self.eligible_at[f"{book.name}:{sig.key}"] = sig.ts + self.cfg.hold_days * 86400
        note("opened", "entry", sig.reason, size)

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
        t = now()
        for book in self.books.values():
            dirty = False
            for key, pos in list(book.portfolio.positions.items()):
                if pos.symbol in rates:
                    pos.accrue_funding(rates[pos.symbol], t)
                    dirty = True
                mid = self._mids.get(pos.symbol)
                if mid is None:
                    continue
                reason = book.portfolio.check_exit(key, mid)
                if reason is None and now() - pos.opened_at >= self.cfg.hold_days * 86400:
                    reason = "time_exit"
                if reason is None:
                    continue
                price = mid
                if book.executes_onchain:
                    try:
                        fill = await self.executor.close(pos.symbol, pos.qty, mid)
                        price = fill.price
                    except Exception:
                        logger.exception("real close failed for %s — keeping position",
                                         pos.symbol)
                        continue
                trade = book.portfolio.close(key, price, reason)
                if trade is None:
                    continue
                book.risk.record_pnl(trade.pnl_usd)
                book.protections.on_trade_closed(trade)
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
        prices = {k: self._mids.get(k.split(":")[1], 0.0) for b in self.books.values()
                  for k in b.portfolio.positions}
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
            },
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
        await self.run_daily()          # evaluate on startup so the book is current
        while True:
            await self.monitor()
            if self._daily_due():
                await self.run_daily()
            await asyncio.sleep(self.cfg.monitor_interval_s)


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
                 bankroll: float = 10_000.0, daily_funding: float = 0.0) -> dict:
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
    for t in closed:
        y = dt.datetime.utcfromtimestamp(t.opened_at).year
        by_year.setdefault(y, []).append(t.pnl_usd / t.size_usd)
    return {
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


def build(cfg: dict, state_dir: Optional[Path]) -> PerpBot:
    from .carry_bot import allocation
    perp = cfg.get("perp", {})
    share = allocation(cfg, "bounce_short")
    sim_bank = share * float(cfg.get("sim", {}).get("bankroll_usd", 200))
    risk_kw = {k: v for k, v in cfg.get("risk", {}).items()
               if k in RiskConfig.__dataclass_fields__}
    coins = tuple(perp.get("coins", MEMECOINS))
    real_bank = share * float(risk_kw.get("bankroll_usd", 1000))
    real_risk = slot_risk(risk_kw, real_bank, len(coins))
    sim_risk = slot_risk(risk_kw, sim_bank, len(coins))
    prot_kw = {k: v for k, v in cfg.get("protections", {}).items()
               if k in ProtectionConfig.__dataclass_fields__}
    bot_cfg = PerpBotConfig(
        target_pct=float(perp.get("target_pct", 0.20)),
        stop_pct=float(perp.get("stop_pct", 0.10)),
        hold_days=int(perp.get("hold_days", 14)),
        coins=coins,
        state_dir=state_dir,
    )
    exec_cfg = PerpExecConfig(
        live=bool(perp.get("live", False)),
        private_key_env=perp.get("private_key_env", "CRYPTOBOT_PRIVATE_KEY"),
        max_trade_usd=float(perp.get("max_trade_usd", 50)),
        max_slippage=float(perp.get("max_slippage", 0.01)),
    )
    return PerpBot(bot_cfg, sim_risk, real_risk, ProtectionConfig(**prot_kw), exec_cfg)


async def _main(args) -> int:
    cfg = load_config(args.config)
    if args.replay:
        import datetime as dt
        import pickle
        pools = pickle.loads(args.replay.read_bytes())
        start = dt.datetime.fromisoformat(args.replay_from).replace(
            tzinfo=dt.timezone.utc).timestamp()
        perp = cfg.get("perp", {})
        rcfg = PerpBotConfig(target_pct=float(perp.get("target_pct", 0.20)),
                             stop_pct=float(perp.get("stop_pct", 0.10)),
                             hold_days=int(perp.get("hold_days", 14)))
        rep = await replay(pools, start, rcfg)
        print(f"replay from {args.replay_from}: {rep['trades']} closed trades, "
              f"{rep['open']} still open, mean net {100 * rep['mean_net']:+.2f}%/trade")
        for y, (n, m) in rep["by_year"].items():
            print(f"  {y}: n={n:4d}  mean net {100 * m:+.2f}%")
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
