"""End-to-end tests: a scripted market driven through the REAL scanner.

Every bug the two review passes found lived in the seams between
components — the fast-exit loop reading the wrong book, the portfolio
that saved but never loaded, the edge tracker fed twice, the security
screen that graded silence as safety. Each unit was individually fine,
and 120-odd unit tests caught none of them.

So these tests fake only the network boundary (DexScreener, CoinGecko,
GoPlus) and run everything else for real: discovery, the volatility
engine, the detectors, cost gating, risk sizing, protections, the
portfolio, persistence and the decision journal. A signal goes in at one
end and an accounted, journalled, persisted trade comes out the other.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager

import pytest

from cryptobot.costs import CostConfig
from cryptobot.data.goplus import SecurityVerdict
from cryptobot.models import TokenSnapshot
from cryptobot.risk import RiskConfig
from cryptobot.scanner import Scanner, ScannerConfig
from cryptobot.signals import SignalConfig


class FakeToken:
    """One token with a scripted price path, reported the way DexScreener
    reports: a current price plus percent changes over each window."""

    def __init__(self, symbol, chain="base", pair="0xPAIR", token="0xTOKEN",
                 start=1.0, liquidity=400_000.0, volume_24h=2_000_000.0,
                 buys=700, sells=300):
        self.symbol, self.chain = symbol, chain
        self.pair, self.token = pair, token
        self.liquidity, self.volume_24h = liquidity, volume_24h
        self.buys, self.sells = buys, sells
        self.prices = [start]
        self.volume_1h = volume_24h / 24.0

    def tick(self, price: float, *, volume_1h: float | None = None):
        self.prices.append(price)
        if volume_1h is not None:
            self.volume_1h = volume_1h

    def _back(self, n: int) -> float:
        i = max(0, len(self.prices) - 1 - n)
        prev = self.prices[i]
        return (self.prices[-1] / prev - 1.0) if prev > 0 else 0.0

    def snapshot(self, ts: float) -> TokenSnapshot:
        # One tick == one 5-minute bucket, as the live scanner samples.
        return TokenSnapshot(
            ts=ts, chain=self.chain, pair_address=self.pair,
            base_symbol=self.symbol, base_address=self.token,
            quote_symbol="WETH", price_usd=self.prices[-1],
            change_5m=self._back(1), change_1h=self._back(12),
            change_6h=self._back(72), change_24h=self._back(288),
            volume_24h_usd=self.volume_24h, volume_1h_usd=self.volume_1h,
            liquidity_usd=self.liquidity, fdv_usd=self.liquidity * 20,
            txns_24h_buys=self.buys, txns_24h_sells=self.sells,
            pair_created_at=ts - 90 * 86400,
        )

    @property
    def key(self) -> str:
        return f"{self.chain}:{self.pair}"


class FakeMarket:
    """Stands in for the three network clients the scanner talks to."""

    def __init__(self, tokens, verdict=None):
        self.tokens = {t.key: t for t in tokens}
        self.ts = 1_700_000_000.0
        self.verdict = verdict or SecurityVerdict(ok=True, known=True,
                                                  checked_at=time.time())
        self.screen_calls = []

    def advance(self, seconds=300.0):
        self.ts += seconds

    def _snaps(self):
        return [t.snapshot(self.ts) for t in self.tokens.values()]

    # -- DexScreener surface ------------------------------------------
    async def search(self, q):            return self._snaps()
    async def get_pairs(self, chain, addrs):
        want = set(addrs)
        return [s for s in self._snaps()
                if s.chain == chain and s.pair_address in want]
    async def token_pairs(self, chain, addr):  return []
    async def boosted_tokens(self):            return []
    # -- CoinGecko surface --------------------------------------------
    async def trending(self):                  return []
    async def simple_price(self, ids, vs_currency="usd"):
        return {i: 2000.0 for i in ids}
    # -- GoPlus surface ------------------------------------------------
    async def check(self, chain, token_address):
        self.screen_calls.append((chain, token_address))
        return self.verdict
    async def close(self):                     return None


@contextmanager
def virtual_clock(market):
    """Run the time-dependent modules on the market's clock.

    The portfolio, protections and risk layers all read wall-clock time.
    Left alone, a scripted market that advances in 5-minute steps would
    age a position by hours per millisecond of test — every trade would
    hit its time stop instantly and every cooldown would swallow the
    next entry. Patch for the duration, restore afterwards (the same
    contract the backtester uses).
    """
    import cryptobot.portfolio as pf_mod
    import cryptobot.protections as prot_mod
    import cryptobot.risk as risk_mod
    mods = (pf_mod, prot_mod, risk_mod)
    saved = [m.now for m in mods]
    for m in mods:
        m.now = lambda: market.ts
    try:
        yield
    finally:
        for m, original in zip(mods, saved):
            m.now = original


def build(market, *, sim_bankroll=200.0, state_dir=None, executor=None,
          risk=None, cost=None):
    """A real Scanner with only its network clients replaced."""
    sc = Scanner(
        ScannerConfig(chains=["base", "solana"], watchlist_queries=["X"],
                      max_position_age_s=10 * 3600),
        SignalConfig(),
        risk or RiskConfig(),
        state_dir=state_dir, executor=executor,
        cost_cfg=cost or CostConfig(),
        sim_bankroll_usd=sim_bankroll,
    )
    sc.dex = market
    sc.gecko = market
    sc.screen = market
    return sc


def run_cycles(sc, market, n, driver=None):
    """Advance the market n 5-minute buckets through real scan cycles."""
    async def go():
        for i in range(n):
            if driver:
                driver(i)
            await sc.run_cycle()
            market.advance()
    with virtual_clock(market):
        asyncio.run(go())


def warm_up(market, token, n=30, drift=0.0005):
    """Quiet history so the volatility engine has a baseline."""
    for i in range(n):
        token.tick(token.prices[-1] * (1 + drift * (1 if i % 2 else -1)))


# -- the full path ---------------------------------------------------------

class TestFullLifecycle:
    def test_breakout_entry_through_to_stop_out_is_fully_accounted(self):
        tok = FakeToken("WILD")
        market = FakeMarket([tok])
        sc = build(market)

        # 25 quiet buckets, then a pump big enough to trip the breakout
        # detector, then a collapse through the stop.
        def driver(i):
            if i < 25:
                tok.tick(tok.prices[-1] * (1.0005 if i % 2 else 0.9995))
            elif i < 33:
                tok.tick(tok.prices[-1] * 1.05, volume_1h=600_000.0)
            else:
                tok.tick(tok.prices[-1] * 0.90)

        run_cycles(sc, market, 45, driver)

        book = sc.books["sim"]
        assert book.portfolio.closed, "no trade completed end to end"
        trade = book.portfolio.closed[0]

        # Accounted: costs charged, PnL net, edge tracker fed, journal written.
        assert trade.costs_usd > 0
        gross = ((trade.exit_price - trade.entry_price)
                 * (trade.size_usd / trade.entry_price))
        # costs_usd is stored rounded to 4dp while the deduction uses full
        # precision, so compare at that granularity.
        assert trade.pnl_usd == pytest.approx(gross - trade.costs_usd, abs=1e-3)
        assert trade.pnl_usd < gross, "costs were not actually deducted"
        assert sc.edges.by_type, "closed trade never reached the EdgeTracker"
        actions = {d["action"] for d in sc.journal.recent(200)}
        assert {"opened", "closed"} <= actions
        # And the sizing respected the book's own caps.
        assert trade.size_usd <= book.risk.cfg.max_position_usd

    def test_position_survives_a_restart(self, tmp_path):
        tok = FakeToken("HODL")
        market = FakeMarket([tok])
        sc = build(market, state_dir=tmp_path)

        def pump(i):
            if i < 25:
                tok.tick(tok.prices[-1] * (1.0005 if i % 2 else 0.9995))
            else:
                tok.tick(tok.prices[-1] * 1.05, volume_1h=600_000.0)

        run_cycles(sc, market, 33, pump)
        opened = dict(sc.books["sim"].portfolio.positions)
        assert opened, "test needs an open position to be meaningful"

        # A fresh process pointed at the same state directory.
        again = build(FakeMarket([tok]), state_dir=tmp_path)
        restored = again.books["sim"].portfolio.positions
        assert set(restored) == set(opened)
        for key, pos in opened.items():
            assert restored[key].size_usd == pytest.approx(pos.size_usd)
            assert restored[key].stop_loss == pytest.approx(pos.stop_loss)
            assert restored[key].symbol == pos.symbol


# -- the seams the reviews found -------------------------------------------

class TestRealBookSeams:
    class ArmedExecutor:
        """An executor that reports armed but performs no I/O."""
        armed = True
        def __init__(self): self.buys, self.sells = [], []
        def supports(self, chain): return chain == "base"
        async def buy(self, chain, token_address, notional_usd, native_price_usd):
            self.buys.append((chain, token_address, notional_usd)); return "0xbuy"
        async def sell(self, chain, token_address, qty_tokens):
            self.sells.append((chain, token_address, qty_tokens)); return "0xsell"

    def _armed_scanner(self, market):
        ex = self.ArmedExecutor()
        sc = build(market, executor=ex)
        assert sc.set_mode("real")[0]
        return sc, ex

    def test_fast_exit_loop_manages_real_positions_when_sim_is_flat(self):
        # The regression: the 15s loop used to read only the sim book, so
        # a real position waited a full discovery cycle for its stop.
        tok = FakeToken("ONLYREAL")
        market = FakeMarket([tok])
        sc, _ = self._armed_scanner(market)

        from cryptobot.models import Side, Signal, SignalType
        sig = Signal(ts=market.ts, type=SignalType.MEAN_REVERT,
                     key=tok.key, chain=tok.chain, symbol=tok.symbol,
                     side=Side.LONG, price_usd=1.0, confidence=0.6,
                     expected_move=0.10, stop_loss_pct=0.05,
                     take_profit_pct=0.10, reason="seeded", risk_reward=2.0,
                     liquidity_usd=tok.liquidity, token_address=tok.token)
        with virtual_clock(market):
            sc.books["real"].portfolio.open_from_signal(sig, 50.0)
        assert not sc.books["sim"].portfolio.positions   # sim deliberately flat

        tok.tick(0.80)                                    # straight through the stop

        # Drive the ACTUAL monitor loop, not its helpers: the regression
        # lived in that loop's own "anything open?" guard, which read the
        # sim book and so skipped entirely while real money was exposed.
        sc.cfg.position_check_interval_s = 0.01

        async def go():
            task = asyncio.create_task(sc.monitor_positions_forever())
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        with virtual_clock(market):
            asyncio.run(go())

        assert not sc.books["real"].portfolio.positions, \
            "real position was not exited by the fast monitor loop"
        assert sc.books["real"].portfolio.closed[0].exit_reason == "stop_loss"

    def test_one_outcome_is_learned_once_even_with_both_books_trading(self):
        tok = FakeToken("DOUBLE")
        market = FakeMarket([tok])
        sc, ex = self._armed_scanner(market)

        def pump(i):
            if i < 25:
                tok.tick(tok.prices[-1] * (1.0005 if i % 2 else 0.9995))
            elif i < 33:
                tok.tick(tok.prices[-1] * 1.05, volume_1h=600_000.0)
            else:
                tok.tick(tok.prices[-1] * 0.90)

        run_cycles(sc, market, 45, pump)
        sim = sc.books["sim"].portfolio.closed
        real = sc.books["real"].portfolio.closed
        assert sim and real, "both books should have traded the same signal"
        # Both books traded; the shared tracker must count the outcome once.
        learned = sum(v["trades"] for v in
                      sc.edges.report()["by_signal_type"].values())
        assert learned == len(sim)
        assert ex.buys and ex.sells, "real book did not reach the executor"


class TestScreenSeam:
    def _run(self, verdict):
        tok = FakeToken("UNKNOWN")
        market = FakeMarket([tok], verdict=verdict)
        ex = TestRealBookSeams.ArmedExecutor()
        sc = build(market, executor=ex)
        assert sc.set_mode("real")[0]

        def pump(i):
            if i < 25:
                tok.tick(tok.prices[-1] * (1.0005 if i % 2 else 0.9995))
            else:
                tok.tick(tok.prices[-1] * 1.05, volume_1h=600_000.0)

        run_cycles(sc, market, 33, pump)
        return sc

    def test_unscreened_token_is_paper_only(self):
        # GoPlus has no analysis for this contract. Paper may trade it so
        # the benchmark stays whole; real money must not touch it.
        sc = self._run(SecurityVerdict(ok=True, known=False,
                                       checked_at=time.time()))
        assert sc.books["sim"].portfolio.positions, \
            "sim should still trade an unscreened token"
        assert not sc.books["real"].portfolio.positions, \
            "real money bought a contract nobody screened"
        reasons = [d["reason"] for d in sc.journal.recent(200)
                   if d["book"] == "real" and d["action"] == "skipped"]
        assert any("unscreened" in r for r in reasons)

    def test_rejected_token_is_traded_by_neither_book(self):
        sc = self._run(SecurityVerdict(ok=False, known=True,
                                       reasons=["honeypot"],
                                       checked_at=time.time()))
        assert not sc.books["sim"].portfolio.positions
        assert not sc.books["real"].portfolio.positions


class TestCostSeam:
    def test_expensive_chain_is_skipped_end_to_end_with_a_reason(self):
        # $50 positions cannot carry Ethereum gas; the whole pipeline must
        # decline rather than quietly trade at a loss.
        tok = FakeToken("PRICEY", chain="ethereum", pair="0xETHPAIR")
        market = FakeMarket([tok])
        sc = build(market)
        sc.cfg.chains = ["ethereum"]

        def pump(i):
            if i < 25:
                tok.tick(tok.prices[-1] * (1.0005 if i % 2 else 0.9995))
            else:
                tok.tick(tok.prices[-1] * 1.05, volume_1h=600_000.0)

        run_cycles(sc, market, 33, pump)
        assert not sc.books["sim"].portfolio.positions
        skips = [d for d in sc.journal.recent(200) if d["action"] == "skipped"]
        assert any(d["stage"] in ("costs", "sizing") for d in skips), \
            "expected an explicit cost/sizing refusal in the journal"
