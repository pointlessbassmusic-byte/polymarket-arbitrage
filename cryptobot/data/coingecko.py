"""CoinGecko free API client — majors and established memecoins.

Used to complement DexScreener: CoinGecko has clean 24h/7d stats and a
trending endpoint that reflects retail attention. Free tier, no key needed
(a demo key can be set to raise rate limits).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"


class CoinGeckoClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0,
                 client: Optional[httpx.AsyncClient] = None):
        headers = {"User-Agent": "crypto-vol-bot/0.1"}
        if api_key:
            headers["x-cg-demo-api-key"] = api_key
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=timeout, headers=headers)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        for attempt in range(3):
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(10.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                logger.warning("coingecko %s failed (%s), retrying", path, exc)
                await asyncio.sleep(2.0 * (attempt + 1))
        return None

    async def trending(self) -> list[dict]:
        """Top trending searches — pure attention signal."""
        data = await self._get("/search/trending")
        return [c.get("item", {}) for c in (data or {}).get("coins", [])]

    async def top_movers(self, vs_currency: str = "usd", per_page: int = 100) -> list[dict]:
        """Market snapshot ordered by 24h volume, with 1h/24h/7d change."""
        data = await self._get(
            "/coins/markets",
            params={
                "vs_currency": vs_currency,
                "order": "volume_desc",
                "per_page": per_page,
                "page": 1,
                "price_change_percentage": "1h,24h,7d",
            },
        )
        return data or []
