"""Hyperliquid perp execution — the real leg of the short book.

Hyperliquid is a perpetuals DEX: orders are EIP-712 messages signed by a
wallet key and posted to the exchange endpoint, so going live is a key
in an environment variable, no KYC and no exchange account. The signing
and the order encoding live in the official `hyperliquid-python-sdk`,
imported lazily so paper trading never needs it installed.

Arming follows the same belt-and-braces rule as the spot wallet: the
config must say live AND the environment must say CRYPTOBOT_ARM_LIVE=yes
AND a key must be present. Anything less is a dry run that logs what it
would have sent.

Orders are IOC limit orders at mid x (1 ± max_slippage): a market order
with a worst-price cap. Reduce-only is set on closes so a stale state
file can never flip a position instead of flattening it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PerpExecConfig:
    live: bool = False
    private_key_env: str = "CRYPTOBOT_PRIVATE_KEY"
    max_trade_usd: float = 50.0
    max_slippage: float = 0.01          # worst fill vs mid, per order
    leverage: int = 1                   # isolated, 1x: a short at 1x can
                                        # still lose >100% in a squeeze,
                                        # which is what the stop is for


@dataclass
class Fill:
    coin: str
    side: str            # "short" | "close"
    qty: float
    price: float
    order_id: Optional[int] = None
    dry_run: bool = False


class PerpExecutor:
    def __init__(self, cfg: PerpExecConfig):
        self.cfg = cfg
        self._key = os.environ.get(cfg.private_key_env, "")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self._key)
        if cfg.live and not env_armed:
            logger.warning("perp execution.live is true but CRYPTOBOT_ARM_LIVE!=yes "
                           "— staying in dry-run")
        if cfg.live and env_armed and not self._key:
            logger.warning("perp execution armed but %s is empty — dry-run",
                           cfg.private_key_env)
        self._exchange = None
        self._info = None

    @property
    def armed(self) -> bool:
        return self._armed

    def _connect(self):
        """Build the SDK clients on first use; only reached when armed."""
        if self._exchange is not None:
            return
        from eth_account import Account                      # noqa: WPS433
        from hyperliquid.exchange import Exchange            # noqa: WPS433
        from hyperliquid.info import Info                    # noqa: WPS433
        from hyperliquid.utils import constants              # noqa: WPS433
        wallet = Account.from_key(self._key)
        self._info = Info(constants.MAINNET_API_URL, skip_ws=True)
        self._exchange = Exchange(wallet, constants.MAINNET_API_URL)
        logger.info("hyperliquid executor connected as %s", wallet.address)

    def _sz_decimals(self, coin: str) -> int:
        meta = self._info.meta()
        for u in meta["universe"]:
            if u["name"] == coin:
                return int(u["szDecimals"])
        raise ValueError(f"{coin} not in Hyperliquid universe")

    async def open_short(self, coin: str, notional_usd: float, mid: float) -> Fill:
        notional_usd = min(notional_usd, self.cfg.max_trade_usd)
        qty = notional_usd / mid
        limit = mid * (1.0 - self.cfg.max_slippage)      # sell no lower than this
        if not self._armed:
            logger.info("DRY-RUN short %s %.6g @ <= %.6g ($%.2f)", coin, qty, limit,
                        notional_usd)
            return Fill(coin, "short", qty, mid, dry_run=True)
        return await asyncio.to_thread(self._order, coin, False, qty, limit, False)

    async def close(self, coin: str, qty: float, mid: float) -> Fill:
        limit = mid * (1.0 + self.cfg.max_slippage)      # buy no higher than this
        if not self._armed:
            logger.info("DRY-RUN close %s %.6g @ <= %.6g", coin, qty, limit)
            return Fill(coin, "close", qty, mid, dry_run=True)
        return await asyncio.to_thread(self._order, coin, True, qty, limit, True)

    async def positions(self) -> dict[str, float]:
        """Open venue positions as coin -> signed size (short negative)."""
        def _get():
            self._connect()
            from eth_account import Account                  # noqa: WPS433
            st = self._info.user_state(Account.from_key(self._key).address)
            out = {}
            for ap in st.get("assetPositions") or []:
                pos = ap.get("position") or {}
                szi = float(pos.get("szi") or 0)
                if szi:
                    out[pos["coin"]] = szi
            return out
        return await asyncio.to_thread(_get)

    def _order(self, coin: str, is_buy: bool, qty: float, limit: float,
               reduce_only: bool) -> Fill:
        self._connect()
        qty = round(qty, self._sz_decimals(coin))
        if qty <= 0:
            raise ValueError(f"{coin}: size rounds to zero")
        if not reduce_only:
            self._exchange.update_leverage(self.cfg.leverage, coin, is_cross=False)
        res = self._exchange.order(coin, is_buy, qty, float(f"{limit:.5g}"),
                                   {"limit": {"tif": "Ioc"}}, reduce_only=reduce_only)
        statuses = (((res or {}).get("response") or {}).get("data") or {}).get("statuses") or []
        for st in statuses:
            if "filled" in st:
                f = st["filled"]
                return Fill(coin, "close" if reduce_only else "short",
                            float(f["totalSz"]), float(f["avgPx"]),
                            order_id=int(f["oid"]))
            if "error" in st:
                raise RuntimeError(f"{coin} order rejected: {st['error']}")
        raise RuntimeError(f"{coin} IOC order did not fill: {res}")
