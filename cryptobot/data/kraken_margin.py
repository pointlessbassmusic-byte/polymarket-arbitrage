"""Market data for the Kraken spot-margin venue (no key needed).

Daily candles from Kraken's public OHLC (up to 720 days), seeded with the
cached Hyperliquid history for the tercile fit; mids from the ticker.
Prices are converted to the bot's units (kPEPE / kSHIB per 1,000 coins).

`funding_rates` returns the margin borrow as a NEGATIVE hourly rate:
positive funding credits a short in the bot's accounting, and a margin
short pays the rollover fee every 4 hours whichever way the price goes.
That way the paper book charges the borrow the real one will pay.
"""
from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import httpx

from ..execution.kraken_margin import US_COINS, units
from .geckoterminal import Candle
from .kraken import KrakenClient, margin_fee_4h

logger = logging.getLogger(__name__)
DAY = 86400


class KrakenMarginData:
    def __init__(self, history_seed: Optional[Path] = None, client: Optional[httpx.AsyncClient] = None,
                 coins: tuple = US_COINS, borrow_per_4h: Optional[dict] = None):
        self.kraken = KrakenClient(client=client)
        self.coins = tuple(coins)
        self.borrow_per_4h = {c: margin_fee_4h(c) for c in self.coins}
        self.borrow_per_4h.update(borrow_per_4h or {})
        self._seed: dict[str, list[Candle]] = {}
        self.seed_loaded = False
        if history_seed:
            if Path(history_seed).exists():
                pools = pickle.loads(Path(history_seed).read_bytes())
                for _, (meta, cs) in pools.items():
                    if meta.symbol in self.coins:
                        self._seed[meta.symbol] = list(cs)
                self.seed_loaded = bool(self._seed)
            if not self.seed_loaded:
                logger.warning("history seed %s missing or empty: terciles would be fit on Kraken's "
                               "720 days of candles only", history_seed)

    async def close(self) -> None:
        await self.kraken.close()

    async def universe(self) -> list[str]:
        out = []
        for c in self.coins:
            if await self.kraken.pair_for(c):
                out.append(c)
        return out

    async def candles(self, coin: str, interval: str = "1d", **_) -> list[Candle]:
        pair = await self.kraken.pair_for(coin)
        if pair is None:
            raise ValueError(f"no Kraken USD pair for {coin}")
        r = await self.kraken._client.get("/OHLC", params={"pair": pair, "interval": 1440,
                                                            "since": int(time.time()) - 720 * DAY})
        r.raise_for_status()
        result = (r.json() or {}).get("result") or {}
        rows = next((v for k, v in result.items() if k != "last"), [])
        k = units(coin)
        out = []
        for row in rows:
            try:
                ts, o, h, lo, c, vwap, vol = (float(x) for x in row[:7])
            except (TypeError, ValueError):
                continue
            if c <= 0:
                continue
            out.append(Candle(ts=ts, open=o * k, high=h * k, low=lo * k, close=c * k, volume_usd=vol * vwap))
        out.sort(key=lambda x: x.ts)
        first = out[0].ts if out else float("inf")
        return [x for x in self._seed.get(coin, []) if x.ts < first] + out

    async def all_mids(self) -> dict[str, float]:
        pairs = {c: await self.kraken.pair_for(c) for c in self.coins}
        names = [p for p in pairs.values() if p]
        quotes = await self.kraken.tickers(names)
        out = {}
        for coin, p in pairs.items():
            q = quotes.get(p) if p else None
            if q and q[0] > 0 and q[1] > 0:
                out[coin] = (q[0] + q[1]) / 2 * units(coin)
        return out

    async def funding_rates(self) -> dict[str, float]:
        """Borrow cost as a negative hourly rate (the short pays)."""
        return {c: -self.borrow_per_4h[c] / 4.0 for c in self.coins}

    async def margin_rates(self) -> dict[str, float]:
        """Collateral per $ of short at the configured leverage is under
        1, so nothing caps the slot the way Coinbase's overnight rate does."""
        return {}
