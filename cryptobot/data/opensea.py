"""OpenSea API v2 client — NFT collection floor/volume volatility.

Note on scope: OpenSea is an NFT marketplace. It has no fungible-token
(memecoin) trading API, so it cannot be a price backbone for coins — that
side comes from DEX data. What OpenSea *is* good for is a second volatility
universe: collection floor prices swing violently, and the same
swing/asymmetry logic applies. Signals here are informational (flagged in
the dashboard/log); the bot does not auto-trade NFTs.

Requires an API key (free at https://docs.opensea.io/reference/api-keys).
If no key is configured the module is skipped silently.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from ..models import NftCollectionSnapshot, now

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opensea.io/api/v2"


class OpenSeaClient:
    def __init__(self, api_key: str, timeout: float = 15.0,
                 client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"X-API-KEY": api_key, "User-Agent": "crypto-vol-bot/0.1"},
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
                    await asyncio.sleep(3.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                logger.warning("opensea %s failed (%s), retrying", path, exc)
                await asyncio.sleep(2.0 * (attempt + 1))
        return None

    async def collection_stats(self, slug: str) -> Optional[NftCollectionSnapshot]:
        data = await self._get(f"/collections/{slug}/stats")
        if not data:
            return None
        total = data.get("total") or {}
        intervals = {i.get("interval"): i for i in data.get("intervals") or []}
        one_day = intervals.get("one_day") or {}
        seven_day = intervals.get("seven_day") or {}

        def frac(x: Any) -> float:
            try:
                return float(x) / 100.0
            except (TypeError, ValueError):
                return 0.0

        try:
            floor = float(total.get("floor_price") or 0.0)
        except (TypeError, ValueError):
            floor = 0.0
        return NftCollectionSnapshot(
            ts=now(),
            slug=slug,
            floor_price_eth=floor,
            one_day_volume_eth=float(one_day.get("volume") or 0.0),
            one_day_change=frac(one_day.get("price_change")),
            seven_day_change=frac(seven_day.get("price_change")),
            num_owners=int(total.get("num_owners") or 0),
            total_supply=0,
        )
