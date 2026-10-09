"""Funding-carry bot: short the perp on Hyperliquid, long the spot on
Kraken, collect funding. Market-neutral; the return is the funding rate.

Rule (from `cryptobot.carry_study`, 4 of 4 years positive, worst year
still positive): rank coins by trailing 14-day funding, hold the top 3
that pay more than 0.06%/day, exit when the trailing 3-day rate turns
negative or the coin drops out of the top 6.

Two books as everywhere else: `sim` always runs and is the benchmark;
`real` mirrors it and also sends orders once armed. A carry position is
two legs of equal notional; the sim book tracks

    funding received (hourly, from the live rate)
  - fees on entry and exit (perp taker + spot taker, both ways)
  + basis P&L: (spot - spot_entry) - (perp - perp_entry), per unit

The basis term is what the study could not see. On liquid coins it is
small and mean-reverting, and it is exactly what the sim book exists to
measure before any real money goes in.

Evaluation is daily; funding accrues on every hourly tick.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .book import Decision, DecisionJournal
from .data.hyperliquid import TAKER_FEE, HyperliquidClient
from .data.kraken import KrakenClient, TAKER_FEE as KRAKEN_TAKER
from .execution.kraken_spot import KrakenSpotExecutor, SpotExecConfig
from .execution.perp_exchange import PerpExecConfig, PerpExecutor
from .models import now

logger = logging.getLogger(__name__)

SLIPPAGE = 0.0005


@dataclass
class CarryConfig:
    # Empty = discover at runtime: every Hyperliquid perp with a Kraken USD
    # spot pair (~150). Breadth is what carry runs on — on 150 coins the
    # worst year was +8.1% against +2.9% on the 18 memecoins alone.
    coins: tuple = ()
    top_n: int = 3
    lookback_days: int = 14
    enter_min_daily: float = 0.0006
    exit_lookback_days: int = 3
    exit_min_daily: float = 0.0
    # Share of CAPITAL committed per slot, both legs included. A $1 carry
    # position needs $1 of spot plus 1/perp_leverage of perp margin, so the
    # notional is capital * slot_fraction / (1 + 1/perp_leverage). Sizing
    # notional off equity directly (as before) quietly assumed half the
    # capital a position really ties up.
    slot_fraction: float = 0.30
    perp_leverage: float = 1.0
    # Close both legs when the coin trades this far above the perp entry.
    # High-funding coins are the ones that pump: over 187 historical carry
    # trades one in ten rose 80%+ during the hold, and at 1x 16 would have
    # been liquidated with no guard. A +50% guard had zero liquidations and
    # gave up little funding; leverage above 1x never paid once liquidations
    # are counted. The hedge makes the move itself P&L-neutral.
    margin_guard: Optional[float] = 0.50
    # Spot and perp must price the same asset. Pairs are matched by ticker,
    # and tickers collide: Kraken's LIT is Litentry (~$0.12), Hyperliquid's
    # LIT is a different token (~$4). A "hedge" across two assets is two
    # naked positions. Normal spot/perp gaps are a few tenths of a percent.
    max_price_gap: float = 0.03
    # Spot leg as a post-only maker order (Kraken 0.16%, no spread) rather
    # than a taker (0.26% + spread). On the 70 trades priced on both
    # venues this takes the round trip from 0.79% to 0.49% and the
    # median trade from -0.07% to +0.23%. The sim book assumes maker
    # fills; the real book records what actually filled as maker.
    maker_spot: bool = True
    daily_at_utc_hour: int = 0
    daily_at_utc_minute: int = 20
    monitor_interval_s: int = 3600
    state_dir: Optional[Path] = None


KRAKEN_MAKER = 0.0016


def round_trip_fraction(maker_spot: bool = False) -> float:
    perp = 2 * (TAKER_FEE + SLIPPAGE)
    spot = 2 * KRAKEN_MAKER if maker_spot else 2 * (KRAKEN_TAKER + SLIPPAGE)
    return perp + spot


@dataclass
class CarryPosition:
    coin: str
    notional_usd: float
    perp_entry: float
    spot_entry: float
    opened_at: float
    funding_usd: float = 0.0
    funding_accrued_at: float = 0.0
    fees_usd: float = 0.0
    perp_qty: float = 0.0        # real book: contracts to buy back
    spot_volume: float = 0.0     # real book: base units to sell

    def accrue(self, hourly_rate: float, at: float) -> float:
        since = self.funding_accrued_at or self.opened_at
        hours = max(0.0, (at - since) / 3600.0)
        amt = self.notional_usd * hourly_rate * hours      # short receives +rate
        self.funding_usd += amt
        self.funding_accrued_at = at
        return amt

    def basis_pnl(self, perp: float, spot: float) -> float:
        """Long spot, short perp, equal notional at entry."""
        qty = self.notional_usd / self.spot_entry
        spot_leg = (spot - self.spot_entry) * qty
        perp_leg = (self.perp_entry - perp) * (self.notional_usd / self.perp_entry)
        return spot_leg + perp_leg

    def pnl(self, perp: float, spot: float) -> float:
        return self.funding_usd + self.basis_pnl(perp, spot) - self.fees_usd


@dataclass
class CarryClosed:
    coin: str
    notional_usd: float
    opened_at: float
    closed_at: float
    funding_usd: float
    basis_usd: float
    fees_usd: float
    pnl_usd: float
    reason: str


@dataclass
class CarryBook:
    name: str
    starting_equity: float
    executes: bool = False
    positions: dict = field(default_factory=dict)
    closed: list = field(default_factory=list)
    realized: float = 0.0
    state_file: Optional[Path] = None
    # Spot legs whose perp was already closed but whose sell failed:
    # {coin: volume}. Retried every tick; a stranded spot long is bounded,
    # which is why exits close the perp first.
    pending_spot_sells: dict = field(default_factory=dict)

    def equity(self, perps: dict, spots: dict) -> float:
        unreal = sum(p.pnl(perps.get(p.coin, p.perp_entry), spots.get(p.coin, p.spot_entry))
                     for p in self.positions.values())
        return self.starting_equity + self.realized + unreal

    def open(self, coin, notional, perp, spot, at, fee_frac,
             perp_qty: float = 0.0, spot_volume: float = 0.0) -> CarryPosition:
        pos = CarryPosition(coin, notional, perp, spot, at, fees_usd=notional * fee_frac / 2,
                            perp_qty=perp_qty, spot_volume=spot_volume)
        self.positions[coin] = pos
        self.save()
        return pos

    def close(self, coin, perp, spot, at, fee_frac, reason) -> Optional[CarryClosed]:
        pos = self.positions.pop(coin, None)
        if pos is None:
            return None
        pos.fees_usd += pos.notional_usd * fee_frac / 2
        basis = pos.basis_pnl(perp, spot)
        pnl = pos.funding_usd + basis - pos.fees_usd
        t = CarryClosed(coin, pos.notional_usd, pos.opened_at, at, pos.funding_usd, basis,
                        pos.fees_usd, pnl, reason)
        self.closed.append(t)
        self.realized += pnl
        self.save()
        return t

    def state(self, perps: dict, spots: dict) -> dict:
        eq = self.equity(perps, spots)
        return {
            "name": self.name, "starting_equity": self.starting_equity,
            "equity": round(eq, 2),
            "return_pct": (eq / self.starting_equity - 1.0) if self.starting_equity else 0.0,
            "executes_onchain": self.executes, "halted": False, "drawdown": 0.0,
            "summary": {"realized_pnl": round(self.realized, 2),
                        "unrealized_pnl": round(eq - self.starting_equity - self.realized, 2),
                        "open_positions": len(self.positions),
                        "exposure_usd": round(sum(p.notional_usd for p in self.positions.values()), 2),
                        "trades": len(self.closed),
                        "total_costs": round(sum(t.fees_usd for t in self.closed), 2),
                        "win_rate": (sum(t.pnl_usd > 0 for t in self.closed) / len(self.closed))
                        if self.closed else None},
            "positions": [{
                "symbol": p.coin, "chain": "carry", "key": f"carry:{p.coin}",
                "entry_price": p.perp_entry, "price": perps.get(p.coin, p.perp_entry),
                "size_usd": round(p.notional_usd, 2),
                "pnl_usd": round(p.pnl(perps.get(p.coin, p.perp_entry), spots.get(p.coin, p.spot_entry)), 2),
                "pnl_pct": p.pnl(perps.get(p.coin, p.perp_entry), spots.get(p.coin, p.spot_entry)) / p.notional_usd,
                "funding_usd": round(p.funding_usd, 2),
                "stop_loss": None, "take_profit": None, "opened_at": p.opened_at,
                "signal_type": "carry"} for p in self.positions.values()],
            "closed_trades": [{
                "symbol": t.coin, "chain": "carry", "pnl_usd": round(t.pnl_usd, 2),
                "size_usd": round(t.notional_usd, 2), "costs_usd": round(t.fees_usd, 2),
                "funding_usd": round(t.funding_usd, 2), "basis_usd": round(t.basis_usd, 2),
                "exit_reason": t.reason, "closed_at": t.closed_at,
                "held_s": t.closed_at - t.opened_at, "signal_type": "carry"}
                for t in self.closed[-60:]][::-1],
        }

    def save(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.write_text(json.dumps({
                "realized": self.realized,
                "pending_spot_sells": self.pending_spot_sells,
                "positions": [asdict(p) for p in self.positions.values()],
                "closed": [asdict(t) for t in self.closed[-200:]]}, indent=2))
        except OSError:
            logger.exception("carry state save failed")

    def load(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        try:
            d = json.loads(self.state_file.read_text())
            self.realized = float(d.get("realized", 0.0))
            self.pending_spot_sells = {k: float(v) for k, v in
                                       (d.get("pending_spot_sells") or {}).items()}
            self.positions = {p["coin"]: CarryPosition(**p) for p in d.get("positions", [])}
            self.closed = [CarryClosed(**t) for t in d.get("closed", [])]
        except (OSError, ValueError, TypeError, KeyError):
            logger.exception("carry state unreadable — starting flat")
            self.positions, self.closed, self.realized = {}, [], 0.0


class CarryBot:
    def __init__(self, cfg: CarryConfig, sim_equity: float, real_equity: float,
                 exec_cfg: PerpExecConfig, hl: Optional[HyperliquidClient] = None,
                 kraken: Optional[KrakenClient] = None,
                 executor: Optional[PerpExecutor] = None,
                 spot_executor: Optional[KrakenSpotExecutor] = None,
                 spot_cfg: Optional[SpotExecConfig] = None):
        self.cfg = cfg
        self.hl = hl or HyperliquidClient()
        self.kraken = kraken or KrakenClient()
        self.executor = executor or PerpExecutor(exec_cfg)
        self.spot = spot_executor or KrakenSpotExecutor(spot_cfg or SpotExecConfig())
        self.books = {}
        for name, eq, ex in (("sim", sim_equity, False), ("real", real_equity, True)):
            b = CarryBook(name, eq, ex,
                          state_file=(cfg.state_dir / f"cryptobot_carry_{name}.json")
                          if cfg.state_dir else None)
            b.load()
            self.books[name] = b
        self.mode = "sim"
        self.journal = DecisionJournal()
        self.started_at = now()
        self.last_daily_run = 0.0
        self.perps: dict[str, float] = {}
        self.spots: dict[str, float] = {}
        self.rates: dict[str, float] = {}
        self.ranking: list[dict] = []
        self.equity_curve: deque = deque(maxlen=2000)
        self._pairs: dict[str, str] = {}
        self._coins: list[str] = []
        self.real_capital: Optional[float] = None    # allocator override; None = book equity

    # -- mode ----------------------------------------------------------------
    @property
    def real_armed(self) -> bool:
        # Both legs or neither: one leg alone is a naked position.
        return bool(self.executor.armed and self.spot.armed)

    def set_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in ("sim", "real"):
            return False, "mode must be sim or real"
        if mode == "real" and not self.real_armed:
            return False, ("real mode needs BOTH legs armed: perp.live and carry.live true, "
                           "CRYPTOBOT_ARM_LIVE=yes, a wallet key, and "
                           "CRYPTOBOT_KRAKEN_KEY / CRYPTOBOT_KRAKEN_SECRET")
        self.mode = mode
        return True, ""

    def active_books(self):
        return [self.books["sim"]] + ([self.books["real"]] if self.mode == "real" else [])

    async def close(self):
        await self.hl.close()
        await self.kraken.close()
        await self.spot.close()

    # -- data ----------------------------------------------------------------
    async def refresh_prices(self) -> None:
        if not self._coins:
            self._coins = await self.universe()
        try:
            mids = await self.hl.all_mids()
            self.perps = {c: mids[c] for c in self._coins if c in mids}
            self.rates = await self.hl.funding_rates()
        except Exception as exc:
            logger.warning("hyperliquid refresh failed: %s", exc)
        try:
            if not self._pairs:
                for c in self._coins:
                    p = await self.kraken.pair_for(c)
                    if p:
                        self._pairs[c] = p
            ticks = await self.kraken.tickers(list(self._pairs.values()))
            for c, p in self._pairs.items():
                if p in ticks:
                    bid, ask = ticks[p]
                    mult = 1000.0 if c.startswith("k") and c[1:].isupper() else 1.0
                    self.spots[c] = (bid + ask) / 2 * mult
        except Exception as exc:
            logger.warning("kraken refresh failed: %s", exc)

    async def trailing_rates(self, coin: str) -> tuple[Optional[float], Optional[float]]:
        """(long-window, short-window) mean daily funding from ONE fetch."""
        long_d, short_d = self.cfg.lookback_days, self.cfg.exit_lookback_days
        t = now()
        try:
            rows = await self.hl.funding_history(
                coin, start_ms=int((t - long_d * 86400) * 1000), max_calls=3)
        except Exception as exc:
            logger.warning("funding history %s failed: %s", coin, exc)
            return None, None
        if len(rows) < long_d * 12:
            return None, None
        recent = [r.rate for r in rows if r.ts >= t - short_d * 86400]
        return (statistics.mean(r.rate for r in rows) * 24,
                statistics.mean(recent) * 24 if recent else None)

    async def universe(self) -> list[str]:
        if self.cfg.coins:
            return list(self.cfg.coins)
        try:
            return await self.hl.universe()
        except Exception as exc:
            logger.warning("universe fetch failed: %s", exc)
            return list(self._pairs)

    # -- daily ---------------------------------------------------------------
    async def run_daily(self) -> None:
        await self.refresh_prices()
        ranking = []
        for coin in self._coins:
            if coin not in self._pairs:
                continue                        # no spot leg on Kraken
            long_r, short_r = await self.trailing_rates(coin)
            if long_r is None:
                continue
            ranking.append({"coin": coin, "rate_long": long_r, "rate_short": short_r})
            await asyncio.sleep(0.2)
        ranking.sort(key=lambda r: -r["rate_long"])
        self.ranking = ranking
        rank_of = {r["coin"]: i for i, r in enumerate(ranking)}
        by_coin = {r["coin"]: r for r in ranking}
        top = [r["coin"] for r in ranking if r["rate_long"] > self.cfg.enter_min_daily][:self.cfg.top_n]
        fee = round_trip_fraction(self.cfg.maker_spot)
        t = now()
        for book in self.active_books():
            # exits
            for coin in list(book.positions):
                r = by_coin.get(coin)
                short_r = r["rate_short"] if r else None
                why = None
                if short_r is not None and short_r < self.cfg.exit_min_daily:
                    why = f"trailing {self.cfg.exit_lookback_days}d funding {100 * short_r:+.3f}%/d"
                elif rank_of.get(coin, 999) >= 2 * self.cfg.top_n:
                    why = "dropped out of the top ranks"
                if why:
                    await self._close(book, coin, why, fee, t)
            # entries
            for coin in top:
                if len(book.positions) >= self.cfg.top_n or coin in book.positions:
                    continue
                if coin not in self.perps or coin not in self.spots:
                    continue
                gap = self.price_gap(coin)
                if gap is None or gap > self.cfg.max_price_gap:
                    self._note(book, coin, "skipped", "identity",
                               f"spot and perp prices differ by {100 * (gap or 0):.1f}% — "
                               f"not the same asset, or a broken market")
                    continue
                capital = book.equity(self.perps, self.spots)
                if book.name == "real" and self.real_capital is not None:
                    capital = min(capital, self.real_capital)
                notional = self.slot_notional(capital)
                if notional < 10:
                    continue
                perp_qty = spot_vol = 0.0
                if book.executes:
                    legs = await self._open_legs(book, coin, notional)
                    if legs is None:
                        continue
                    perp_px, spot_px, perp_qty, spot_vol, notional = legs
                else:
                    perp_px, spot_px = self.perps[coin], self.spots[coin]
                book.open(coin, notional, perp_px, spot_px, t, fee,
                          perp_qty=perp_qty, spot_volume=spot_vol)
                naked = "NAKED SHORT (no spot leg) — " if book.executes and not spot_vol else ""
                self._note(book, coin, "opened", "entry",
                           f"{naked}trailing {self.cfg.lookback_days}d funding "
                           f"{100 * by_coin[coin]['rate_long']:+.3f}%/d, rank {rank_of[coin] + 1}",
                           notional)
        self.last_daily_run = t

    def slot_notional(self, equity: float) -> float:
        """Notional per slot, so that spot + perp margin = slot_fraction of capital."""
        return equity * self.cfg.slot_fraction / (1.0 + 1.0 / self.cfg.perp_leverage)

    def set_real_capital(self, usd: float) -> None:
        """The allocator's deployable capital for the real book; zero stops
        new entries. Open positions are left to their own exits."""
        self.real_capital = max(0.0, float(usd))

    def guard_tripped(self, pos) -> bool:
        if self.cfg.margin_guard is None:
            return False
        perp = self.perps.get(pos.coin)
        return perp is not None and perp >= pos.perp_entry * (1 + self.cfg.margin_guard)

    def price_gap(self, coin: str) -> Optional[float]:
        """|spot / perp - 1|, both in the perp's units, from live mids."""
        perp, spot = self.perps.get(coin), self.spots.get(coin)
        if not perp or not spot:
            return None
        return abs(spot / perp - 1.0)

    async def _open_legs(self, book, coin, notional):
        if self.cfg.maker_spot:
            return await self._open_legs_maker(book, coin, notional)
        return await self._open_legs_taker(book, coin, notional)

    async def _open_legs_maker(self, book, coin, notional):
        """Buy spot as maker FIRST, then short the perp for what filled.

        A maker order can rest for minutes. Waiting with an unhedged spot
        long risks at most what the spot cost; waiting with an unhedged
        short does not have a ceiling. So the leg that waits goes first.
        """
        try:
            sf = await self.spot.buy_maker(coin, notional)
        except Exception as exc:
            self._note(book, coin, "skipped", "execution", f"spot maker buy failed: {exc}")
            return None
        mult = 1000.0 if coin.startswith("k") and coin[1:].isupper() else 1.0
        spot_px = sf.price * mult
        filled_usd = sf.volume * sf.price
        try:
            pf = await self.executor.open_short(coin, filled_usd, self.perps[coin])
        except Exception as exc:
            logger.error("perp short failed for %s after spot filled — selling spot", coin)
            try:
                await self.spot.sell(coin, sf.volume)
                self._note(book, coin, "skipped", "execution",
                           f"perp short failed ({exc}); spot sold back")
            except Exception:
                book.pending_spot_sells[coin] = book.pending_spot_sells.get(coin, 0.0) + sf.volume
                book.save()
                self._note(book, coin, "skipped", "execution",
                           f"perp short failed ({exc}); spot sell queued for retry")
            return None
        if sf.volume and sf.maker_volume < sf.volume:
            logger.info("%s spot: %.0f%% filled as maker", coin, 100 * sf.maker_volume / sf.volume)
        return pf.price, spot_px, pf.qty, sf.volume, filled_usd

    async def _open_legs_taker(self, book, coin, notional):
        """Short perp, then buy spot of the SAME filled notional. If the
        spot leg fails, buy the perp back: never hold a naked short."""
        try:
            pf = await self.executor.open_short(coin, notional, self.perps[coin])
        except Exception as exc:
            self._note(book, coin, "skipped", "execution", f"perp short failed: {exc}")
            return None
        filled_usd = pf.qty * pf.price
        try:
            sf = await self.spot.buy(coin, filled_usd)
        except Exception as exc:
            logger.error("spot buy failed for %s after perp filled — unwinding perp", coin)
            try:
                await self.executor.close(coin, pf.qty, self.perps[coin])
                self._note(book, coin, "skipped", "execution",
                           f"spot buy failed ({exc}); perp short unwound")
            except Exception as exc2:
                # Worst case: a naked short we could not flatten. Record it as
                # a position with no spot leg so monitoring keeps trying to exit.
                logger.critical("NAKED SHORT %s: spot failed and perp unwind failed: %s",
                                coin, exc2)
                self._note(book, coin, "opened", "execution",
                           f"NAKED SHORT — spot buy failed and perp unwind failed: {exc2}",
                           filled_usd)
                return pf.price, self.spots.get(coin, pf.price), pf.qty, 0.0, filled_usd
            return None
        # spot price normalised to the perp's units (k-coins are per 1000)
        mult = 1000.0 if coin.startswith("k") and coin[1:].isupper() else 1.0
        return pf.price, sf.price * mult, pf.qty, sf.volume, filled_usd

    async def _close(self, book, coin, why, fee, t):
        perp = self.perps.get(coin)
        spot = self.spots.get(coin)
        if perp is None or spot is None:
            return
        if book.executes:
            pos = book.positions[coin]
            try:
                await self.executor.close(coin, pos.perp_qty or pos.notional_usd / pos.perp_entry,
                                          perp)
            except Exception:
                logger.exception("real perp close failed for %s — keeping both legs", coin)
                return
            if pos.spot_volume > 0:
                try:
                    if self.cfg.maker_spot:
                        await self.spot.sell_maker(coin, pos.spot_volume)
                    else:
                        await self.spot.sell(coin, pos.spot_volume)
                except Exception:
                    logger.exception("spot sell failed for %s — queued for retry", coin)
                    book.pending_spot_sells[coin] = pos.spot_volume
        trade = book.close(coin, perp, spot, t, fee, why)
        if trade:
            self._note(book, coin, "closed", "exit",
                       f"{why} (funding {trade.funding_usd:+.2f}, basis {trade.basis_usd:+.2f})",
                       trade.notional_usd, trade.pnl_usd)

    def _note(self, book, coin, action, stage, reason, size=0.0, pnl=None):
        self.journal.record(Decision(ts=now(), book=book.name, symbol=coin, chain="carry",
                                     signal_type="carry", action=action, stage=stage,
                                     reason=reason, size_usd=size, pnl_usd=pnl))

    # -- hourly --------------------------------------------------------------
    async def _retry_spot_sells(self, book) -> None:
        for coin, vol in list(book.pending_spot_sells.items()):
            try:
                await self.spot.sell(coin, vol)
            except Exception as exc:
                logger.warning("spot sell retry for %s failed: %s", coin, exc)
                continue
            del book.pending_spot_sells[coin]
            self._note(book, coin, "closed", "exit", "queued spot sell completed")
            book.save()

    async def monitor(self) -> None:
        await self.refresh_prices()
        if self.books["real"].pending_spot_sells:
            await self._retry_spot_sells(self.books["real"])
        t = now()
        fee = round_trip_fraction(self.cfg.maker_spot)
        for book in self.books.values():
            dirty = False
            for pos in list(book.positions.values()):
                if pos.coin in self.rates:
                    pos.accrue(self.rates[pos.coin], t)
                    dirty = True
                if self.guard_tripped(pos):
                    rise = self.perps[pos.coin] / pos.perp_entry - 1
                    await self._close(book, pos.coin,
                                      f"margin guard: perp up {100 * rise:.0f}% from entry", fee, t)
            if dirty:
                book.save()
        self.equity_curve.append((t, self.books["sim"].equity(self.perps, self.spots),
                                  self.books["real"].equity(self.perps, self.spots)))

    def _daily_due(self, at: Optional[float] = None) -> bool:
        t = now() if at is None else at
        day = int(t // 86400)
        last = int(self.last_daily_run // 86400) if self.last_daily_run else -1
        sched = self.cfg.daily_at_utc_hour * 3600 + self.cfg.daily_at_utc_minute * 60
        return day > last and (t % 86400) >= sched

    async def run_forever(self) -> None:
        logger.info("carry bot up: %s, top %d, mode %s",
                    f"{len(self.cfg.coins)} coins" if self.cfg.coins else "full universe",
                    self.cfg.top_n, self.mode)
        await self.run_daily()
        while True:
            await self.monitor()
            if self._daily_due():
                await self.run_daily()
            await asyncio.sleep(self.cfg.monitor_interval_s)

    # -- dashboard -----------------------------------------------------------
    def state(self) -> dict:
        return {
            "ts": now(), "started_at": self.started_at, "cycle": int(self.last_daily_run),
            "tracked_pairs": len(self._pairs), "mode": self.mode,
            "real_unlocked": self.real_armed,
            "real_locked_reason": "" if self.real_armed else
                "needs BOTH legs armed: perp.live + carry.live, CRYPTOBOT_ARM_LIVE=yes, "
                "a wallet key and CRYPTOBOT_KRAKEN_KEY/SECRET",
            "chains": ["hyperliquid", "kraken"],
            "strategy": {"rule": f"top{self.cfg.top_n} by {self.cfg.lookback_days}d funding, "
                                 f"enter > {100 * self.cfg.enter_min_daily:.3f}%/d, "
                                 f"exit < {100 * self.cfg.exit_min_daily:.3f}%/d "
                                 f"({self.cfg.exit_lookback_days}d)",
                         "ranking": self.ranking[:10],
                         "universe": len(self._pairs),
                         "last_daily_run": self.last_daily_run},
            "books": {n: b.state(self.perps, self.spots) for n, b in self.books.items()},
            "decisions": self.journal.recent(60), "gate_counts": self.journal.counts(),
            "signals": [], "movers": [], "edges": {},
            "equity_curve": [(round(t), round(a, 2), round(r, 2)) for t, a, r in self.equity_curve],
        }


def allocation(cfg: dict, strategy: str) -> float:
    """Share of the bankroll given to `strategy` (config `allocation:`).
    Carry and the bounce-short are complementary: carry earned most in the
    2024 mania, the bounce-short in the 2025 collapse. 50/50 by default."""
    shares = cfg.get("allocation") or {"carry": 0.5, "bounce_short": 0.5}
    total = sum(float(v) for v in shares.values()) or 1.0
    return float(shares.get(strategy, 0.0)) / total


def build(cfg: dict, state_dir: Optional[Path]) -> CarryBot:
    carry = cfg.get("carry", {})
    perp = cfg.get("perp", {})
    ccfg = CarryConfig(
        top_n=int(carry.get("top_n", 3)), lookback_days=int(carry.get("lookback_days", 14)),
        enter_min_daily=float(carry.get("enter_min_daily", 0.0006)),
        exit_min_daily=float(carry.get("exit_min_daily", 0.0)),
        slot_fraction=float(carry.get("slot_fraction", 0.30)),
        perp_leverage=float(carry.get("perp_leverage", 1.0)),
        margin_guard=(None if carry.get("margin_guard", 0.50) is None
                      else float(carry.get("margin_guard", 0.50))),
        maker_spot=bool(carry.get("maker_spot", True)),
        coins=tuple(carry.get("coins") or ()), state_dir=state_dir)
    exec_cfg = PerpExecConfig(live=bool(perp.get("live", False)),
                              private_key_env=perp.get("private_key_env", "CRYPTOBOT_PRIVATE_KEY"),
                              max_trade_usd=float(perp.get("max_trade_usd", 50)))
    spot_cfg = SpotExecConfig(live=bool(carry.get("live", False)),
                              max_trade_usd=float(perp.get("max_trade_usd", 50)),
                              max_slippage=float(carry.get("max_slippage", 0.01)))
    share = allocation(cfg, "carry")
    return CarryBot(ccfg, float(cfg.get("sim", {}).get("bankroll_usd", 200)),    # paper: full sim bankroll
                    share * float(cfg.get("risk", {}).get("bankroll_usd", 1000)), exec_cfg,
                    spot_cfg=spot_cfg)


async def _main(args) -> int:
    import yaml
    cfg = yaml.safe_load(args.config.read_text()) or {}
    bot = build(cfg, args.state_dir)
    if args.once:
        await bot.run_daily()
        for r in bot.ranking:
            print(f"{r['coin']:9s} {100 * r['rate_long']:+.3f}%/d  "
                  f"3d {100 * (r['rate_short'] or 0):+.3f}%/d")
        print("sim positions:", list(bot.books["sim"].positions))
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
    ap = argparse.ArgumentParser(description="funding-carry bot (short perp, long spot)")
    ap.add_argument("--config", type=Path, default=Path("cryptobot_config.yaml"))
    ap.add_argument("--state-dir", type=Path, default=Path("."))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dashboard", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8083)
    ap.add_argument("--token", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
