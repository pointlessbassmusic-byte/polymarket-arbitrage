"""Kraken spot execution — the long leg of the carry trade.

Kraken's private REST API authenticates each POST with two headers:

    API-Key:  the public key
    API-Sign: base64( HMAC-SHA512( base64decode(secret),
                                   uri_path + SHA256(nonce + postdata) ) )

where `nonce` is a strictly increasing integer also sent in the body.
Use a key with ONLY "Query Funds", "Create & Modify Orders" and "Query
Open/Closed Orders" permissions — never withdrawal.

Orders are IOC limit orders at mid x (1 ± max_slippage), the same
capped-market shape as the perp leg. Volume is rounded DOWN to the
pair's lot decimals and refused under the pair's minimum, so the bot
can never send an order Kraken would reject for size.

Arming matches every other executor: config live AND
CRYPTOBOT_ARM_LIVE=yes AND both key env vars present.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import math
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import httpx

from cryptobot.data.kraken import hl_to_base

logger = logging.getLogger(__name__)

API_URL = "https://api.kraken.com"


@dataclass
class SpotExecConfig:
    live: bool = False
    key_env: str = "CRYPTOBOT_KRAKEN_KEY"
    secret_env: str = "CRYPTOBOT_KRAKEN_SECRET"
    max_trade_usd: float = 50.0
    max_slippage: float = 0.01


@dataclass
class SpotFill:
    pair: str
    side: str           # "buy" | "sell"
    volume: float       # base units
    price: float        # USD per base unit
    txid: Optional[str] = None
    dry_run: bool = False

    @property
    def notional(self) -> float:
        return self.volume * self.price


def sign(path: str, data: dict, secret_b64: str) -> str:
    postdata = urllib.parse.urlencode(data)
    sha = hashlib.sha256((str(data["nonce"]) + postdata).encode()).digest()
    mac = hmac.new(base64.b64decode(secret_b64), path.encode() + sha, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()


def floor_to(x: float, decimals: int) -> float:
    """Round DOWN to `decimals`, tolerating float noise: 29 / 0.00001 is
    2899999.9999... in binary floating point, and a bare floor would drop
    a whole lot."""
    q = 10 ** decimals
    return math.floor(x * q + 1e-9) / q


class KrakenSpotExecutor:
    def __init__(self, cfg: SpotExecConfig, client: Optional[httpx.AsyncClient] = None):
        self.cfg = cfg
        self._key = os.environ.get(cfg.key_env, "")
        self._secret = os.environ.get(cfg.secret_env, "")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self._key and self._secret)
        if cfg.live and env_armed and not (self._key and self._secret):
            logger.warning("kraken spot armed but %s/%s missing — dry-run",
                           cfg.key_env, cfg.secret_env)
        self._client = client or httpx.AsyncClient(base_url=API_URL, timeout=20.0)
        self._owns = client is None
        self._pairs: dict[str, dict] = {}      # base -> {name, lot_decimals, ordermin, pair_decimals}
        self._last_nonce = 0

    @property
    def armed(self) -> bool:
        return self._armed

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    # -- public ----------------------------------------------------------------
    async def _pair_info(self, hl_coin: str) -> dict:
        if not self._pairs:
            r = await self._client.get("/0/public/AssetPairs")
            r.raise_for_status()
            for name, info in ((r.json() or {}).get("result") or {}).items():
                ws = info.get("wsname") or ""
                if not ws.endswith("/USD"):
                    continue
                self._pairs[ws.split("/")[0]] = {
                    "name": name,
                    "lot_decimals": int(info.get("lot_decimals", 8)),
                    "pair_decimals": int(info.get("pair_decimals", 8)),
                    "ordermin": float(info.get("ordermin") or 0.0),
                }
        base = hl_to_base(hl_coin)
        info = self._pairs.get(base) or self._pairs.get({"DOGE": "XDG", "BTC": "XBT"}.get(base, ""))
        if info is None:
            raise ValueError(f"no Kraken USD pair for {hl_coin}")
        return info

    async def _mid(self, pair: str) -> float:
        r = await self._client.get("/0/public/Ticker", params={"pair": pair})
        r.raise_for_status()
        t = next(iter(((r.json() or {}).get("result") or {}).values()))
        return (float(t["b"][0]) + float(t["a"][0])) / 2

    # -- private ---------------------------------------------------------------
    def _nonce(self) -> int:
        n = max(int(time.time() * 1000), self._last_nonce + 1)
        self._last_nonce = n
        return n

    async def _private(self, method: str, data: dict) -> dict:
        path = f"/0/private/{method}"
        data = {"nonce": self._nonce(), **data}
        headers = {"API-Key": self._key, "API-Sign": sign(path, data, self._secret)}
        r = await self._client.post(path, data=data, headers=headers)
        r.raise_for_status()
        body = r.json() or {}
        if body.get("error"):
            raise RuntimeError(f"kraken {method}: {body['error']}")
        return body.get("result") or {}

    async def _order(self, info: dict, side: str, volume: float, limit: float) -> SpotFill:
        volume = floor_to(volume, info["lot_decimals"])
        if volume <= 0 or volume < info["ordermin"]:
            raise ValueError(f"{info['name']}: volume {volume} under minimum {info['ordermin']}")
        res = await self._private("AddOrder", {
            "pair": info["name"], "type": side, "ordertype": "limit",
            "price": f"{limit:.{info['pair_decimals']}f}", "volume": f"{volume:.{info['lot_decimals']}f}",
            "timeinforce": "IOC",
        })
        txid = (res.get("txid") or [None])[0]
        if not txid:
            raise RuntimeError(f"kraken AddOrder returned no txid: {res}")
        # IOC settles immediately; read back what actually filled.
        for _ in range(5):
            q = await self._private("QueryOrders", {"txid": txid})
            o = q.get(txid) or {}
            if o.get("status") in ("closed", "canceled", "expired"):
                filled = float(o.get("vol_exec") or 0.0)
                if filled <= 0:
                    raise RuntimeError(f"{info['name']} IOC {side} did not fill")
                return SpotFill(info["name"], side, filled, float(o.get("price") or limit), txid)
            await asyncio.sleep(0.5)
        raise RuntimeError(f"{info['name']} order {txid} state unknown after polling")

    async def buy(self, hl_coin: str, notional_usd: float) -> SpotFill:
        info = await self._pair_info(hl_coin)
        notional_usd = min(notional_usd, self.cfg.max_trade_usd)
        mid = await self._mid(info["name"])
        limit = mid * (1 + self.cfg.max_slippage)
        vol = notional_usd / mid
        if not self._armed:
            logger.info("DRY-RUN kraken buy %s %.8g @ <= %.8g", info["name"], vol, limit)
            return SpotFill(info["name"], "buy", vol, mid, dry_run=True)
        return await self._order(info, "buy", vol, limit)

    async def sell(self, hl_coin: str, volume: float) -> SpotFill:
        info = await self._pair_info(hl_coin)
        mid = await self._mid(info["name"])
        limit = mid * (1 - self.cfg.max_slippage)
        if not self._armed:
            logger.info("DRY-RUN kraken sell %s %.8g @ >= %.8g", info["name"], volume, limit)
            return SpotFill(info["name"], "sell", volume, mid, dry_run=True)
        return await self._order(info, "sell", volume, limit)

    async def balance(self) -> dict[str, float]:
        res = await self._private("Balance", {})
        return {k: float(v) for k, v in res.items()}
