"""Market data for the bounce-short from Coinbase's public API.

Hyperliquid's public market data has no account behind it, but a US
desk that must not touch Hyperliquid may prefer not to depend on it at
all. This serves the same `candles` / `all_mids` / `funding_rates`
interface the bot uses, from Coinbase's unauthenticated endpoints, in the
bot's units (kPEPE = 1000 PEPE, which is also how Coinbase quotes it).

Coinbase's perpetual-style futures only have history since December
2025. The rule fits its tercile cuts on all prior history, so a cached
Hyperliquid daily history (`history_seed`) is prepended for dates before
Coinbase's first candle. Same asset, same daily closes within a fraction
of a percent; the seed is data, not a venue.
"""

from __future__ import annotations

import asyncio
import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import httpx

from .geckoterminal import Candle
from ..execution.coinbase_futures import CONTRACTS

logger = logging.getLogger(__name__)

API = "https://api.coinbase.com/api/v3/brokerage/market"
DAY = 86400


class CoinbaseMarketData:
    def __init__(self, history_seed: Optional[Path] = None,
                 client: Optional[httpx.AsyncClient] = None):
        self._c = client or httpx.AsyncClient(timeout=25)
        self._owns = client is None
        self._seed: dict[str, list[Candle]] = {}
        self.seed_loaded = False
        if history_seed:
            if Path(history_seed).exists():
                pools = pickle.loads(Path(history_seed).read_bytes())
                for _, (meta, cs) in pools.items():
                    if meta.symbol in CONTRACTS:
                        self._seed[meta.symbol] = list(cs)
                self.seed_loaded = bool(self._seed)
            if not self.seed_loaded:
                logger.warning("history seed %s missing or empty: terciles would be fit on "
                               "Coinbase's own candles only (since Dec 2025), not the history "
                               "the rule was validated on. Build it: python -m "
                               "cryptobot.data.coinbase_futures --seed %s", history_seed, history_seed)
        self._products: tuple[float, dict] = (0.0, {})

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    async def universe(self) -> list[str]:
        return list(CONTRACTS)

    async def candles(self, coin: str, interval: str = "1d", **_) -> list[Candle]:
        pid = CONTRACTS[coin].product_id
        end = int(time.time())
        out: list[Candle] = []
        start = end - 349 * DAY                       # Coinbase caps at 350 per call
        r = await self._c.get(f"{API}/products/{pid}/candles",
                              params={"start": str(start), "end": str(end), "granularity": "ONE_DAY"})
        r.raise_for_status()
        for row in r.json().get("candles", []):
            px = float(row["close"])
            if px <= 0:
                continue
            out.append(Candle(ts=float(row["start"]), open=float(row["open"]), high=float(row["high"]),
                              low=float(row["low"]), close=px,
                              volume_usd=float(row["volume"]) * CONTRACTS[coin].units_per_contract * px))
        out.sort(key=lambda c: c.ts)
        first = out[0].ts if out else float("inf")
        seed = [c for c in self._seed.get(coin, []) if c.ts < first]
        return seed + out

    async def products(self, max_age_s: float = 10.0) -> dict:
        """The FUTURE product list keyed by product_id, shared by all_mids
        and funding_rates so one monitor tick is one request."""
        ts, cached = self._products
        if cached and time.time() - ts < max_age_s:
            return cached
        r = await self._c.get(f"{API}/products", params={"product_type": "FUTURE", "limit": 500})
        r.raise_for_status()
        by_id = {p["product_id"]: p for p in r.json().get("products", [])}
        self._products = (time.time(), by_id)
        return by_id

    async def all_mids(self) -> dict[str, float]:
        by_id = await self.products()
        out = {}
        for coin, c in CONTRACTS.items():
            p = by_id.get(c.product_id)
            if p and p.get("price"):
                out[coin] = float(p["price"])
        return out

    async def margin_rates(self) -> dict[str, float]:
        """Overnight SHORT margin rate per coin (fraction of notional). The
        switch from intraday to overnight shortly after 16:00 ET is where
        Coinbase says most surprise liquidations happen."""
        by_id = await self.products()
        out = {}
        for coin, c in CONTRACTS.items():
            d = ((by_id.get(c.product_id) or {}).get("future_product_details") or {})
            r = (d.get("overnight_margin_rate") or {}).get("short_margin_rate")
            try:
                if r is not None:
                    out[coin] = float(r)
            except (TypeError, ValueError):
                continue
        return out

    async def funding_rates(self) -> dict[str, float]:
        """Current hourly funding per coin (positive = longs pay shorts)."""
        by_id = await self.products()
        out = {}
        for coin, c in CONTRACTS.items():
            d = (by_id.get(c.product_id) or {}).get("future_product_details") or {}
            try:
                out[coin] = float(d.get("funding_rate") or 0.0)
            except (TypeError, ValueError):
                continue
        return out

async def build_seed(path: Path, days: int = 365 * 5) -> int:
    """Write the history seed: Hyperliquid PUBLIC daily candles (no account,
    no key) for the three US coins, in the backtester's pickle layout."""
    from ..backtest import PoolMeta
    from .hyperliquid import HyperliquidClient
    hl = HyperliquidClient()
    out = {}
    try:
        start_ms = int((time.time() - days * DAY) * 1000)
        for coin in CONTRACTS:
            cs = await hl.candles(coin, "1d", start_ms=start_ms)
            meta = PoolMeta(chain="hyperliquid", pair_address=coin, symbol=coin,
                            token_address=coin, liquidity_usd=0.0, fdv_usd=None)
            out[coin] = (meta, cs)
            logger.info("%s: %d daily candles", coin, len(cs))
    finally:
        await hl.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(out))
    return sum(len(cs) for _, cs in out.values())


if __name__ == "__main__":
    import argparse
    import asyncio
    ap = argparse.ArgumentParser(description="Build perp.history_seed for the Coinbase venue.")
    ap.add_argument("--seed", type=Path, default=Path("state/hl_daily_us3.pkl"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = asyncio.run(build_seed(args.seed))
    print(f"wrote {n} candles to {args.seed}")
