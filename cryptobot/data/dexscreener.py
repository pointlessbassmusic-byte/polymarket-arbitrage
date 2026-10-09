"""DexScreener API client (free, no key required).

DexScreener covers essentially every DEX-listed token — i.e. the universe you
can actually trade from a MetaMask wallet — and natively reports price change
over 5m / 1h / 6h / 24h windows, which maps directly onto the volatility
windows this bot hunts.

Endpoints used (https://docs.dexscreener.com/api/reference):
  GET /latest/dex/search?q=<query>
  GET /latest/dex/pairs/<chain>/<pairAddresses>   (comma separated, max 30)
  GET /token-profiles/latest/v1                    (freshly listed / promoted)
  GET /token-boosts/top/v1                         (heavily promoted = attention)
Rate limit: ~300 req/min for pair endpoints, 60 req/min for profiles/boosts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable, Optional

import httpx

from ..models import TokenSnapshot, now

logger = logging.getLogger(__name__)

BASE_URL = "https://api.dexscreener.com"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_pair(raw: dict, ts: Optional[float] = None) -> Optional[TokenSnapshot]:
    """Normalize one DexScreener pair object into a TokenSnapshot."""
    try:
        price = _f(raw.get("priceUsd"))
        if price <= 0:
            return None
        change = raw.get("priceChange") or {}
        volume = raw.get("volume") or {}
        txns = (raw.get("txns") or {}).get("h24") or {}
        liquidity = (raw.get("liquidity") or {}).get("usd")
        created_ms = raw.get("pairCreatedAt")

        def pct(window: str) -> Optional[float]:
            v = change.get(window)
            return None if v is None else _f(v) / 100.0

        return TokenSnapshot(
            ts=ts if ts is not None else now(),
            chain=raw.get("chainId", ""),
            pair_address=raw.get("pairAddress", ""),
            base_symbol=(raw.get("baseToken") or {}).get("symbol", "?"),
            base_address=(raw.get("baseToken") or {}).get("address", ""),
            quote_symbol=(raw.get("quoteToken") or {}).get("symbol", "?"),
            price_usd=price,
            change_5m=pct("m5"),
            change_1h=pct("h1"),
            change_6h=pct("h6"),
            change_24h=pct("h24"),
            volume_24h_usd=_f(volume.get("h24")),
            volume_1h_usd=_f(volume.get("h1")),
            liquidity_usd=_f(liquidity),
            fdv_usd=_f(raw.get("fdv")) or None,
            market_cap_usd=_f(raw.get("marketCap")) or None,
            txns_24h_buys=int(_f(txns.get("buys"))),
            txns_24h_sells=int(_f(txns.get("sells"))),
            pair_created_at=_f(created_ms) / 1000.0 if created_ms else None,
        )
    except Exception:  # defensive: one malformed pair must not kill a scan
        logger.exception("failed to parse pair: %r", raw.get("pairAddress"))
        return None


class DexScreenerClient:
    def __init__(self, timeout: float = 15.0, client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "crypto-vol-bot/0.1"},
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        for attempt in range(3):
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                logger.warning("dexscreener %s failed (%s), retrying", path, exc)
                await asyncio.sleep(1.5 * (attempt + 1))
        return None

    async def search(self, query: str) -> list[TokenSnapshot]:
        data = await self._get("/latest/dex/search", params={"q": query})
        pairs = (data or {}).get("pairs") or []
        ts = now()
        return [s for p in pairs if (s := parse_pair(p, ts))]

    async def get_pairs(self, chain: str, pair_addresses: Iterable[str]) -> list[TokenSnapshot]:
        """Fetch up to 30 pairs on one chain in a single call."""
        addrs = list(pair_addresses)
        out: list[TokenSnapshot] = []
        ts = now()
        for i in range(0, len(addrs), 30):
            chunk = ",".join(addrs[i : i + 30])
            data = await self._get(f"/latest/dex/pairs/{chain}/{chunk}")
            for p in (data or {}).get("pairs") or []:
                if s := parse_pair(p, ts):
                    out.append(s)
        return out

    async def token_pairs(self, chain: str, token_address: str) -> list[TokenSnapshot]:
        """All pools for one token on a chain — the input for cross-DEX arb."""
        data = await self._get(f"/token-pairs/v1/{chain}/{token_address}")
        ts = now()
        pairs = data if isinstance(data, list) else (data or {}).get("pairs") or []
        return [s for p in pairs if (s := parse_pair(p, ts))]

    async def boosted_tokens(self) -> list[dict]:
        """Tokens paying for promotion right now — a raw attention signal."""
        data = await self._get("/token-boosts/top/v1")
        return data if isinstance(data, list) else []

    async def latest_profiles(self) -> list[dict]:
        """Recently updated token profiles — skews toward fresh launches."""
        data = await self._get("/token-profiles/latest/v1")
        return data if isinstance(data, list) else []
