"""Coinbase Derivatives (US) execution for the bounce-short's perp leg.

Coinbase Financial Markets lists CFTC-regulated "perpetual-style" futures
for US clients: hourly funding like a perp, a five-year expiry on paper.
Three of this project's memecoins trade there, in whole contracts:

    DOGE   DOP-20DEC30-CDE   5,000 DOGE per contract      (~$480)
    kPEPE  PEP-20DEC30-CDE   100,000 PEPE = 100 kPEPE     (~$440)
    kSHIB  SHP-20DEC30-CDE   10,000 SHIB  = 10 kSHIB      (~$60)

Orders go through the official `coinbase-advanced-py` SDK (imported
lazily; paper trading never needs it), authenticated with a CDP API key:
ES256 only, the key name as `kid`, a two-minute JWT per request. The SDK
builds that. Cash deposited to the spot account is swept to the futures
account automatically to meet margin.

Whole contracts change the sizing contract with the bot: a slot smaller
than one contract cannot trade, and `open_short` says so with
`SizeTooSmall` rather than rounding up. Shorts are market IOC orders
(these books are thin and a resting limit on the wrong side is a naked
position); closes use the SDK's close_position, which cannot flip a
position the way an oversized opposite order could.

Arming follows the project rule: config live AND CRYPTOBOT_ARM_LIVE=yes
AND both key variables present.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import uuid
from dataclasses import dataclass
from typing import Optional

from .perp_exchange import Fill

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Contract:
    product_id: str
    units_per_contract: float      # in the bot's units (kPEPE = 1000 PEPE)
    display: str


# Bot coin name -> Coinbase US perpetual-style future.
CONTRACTS = {
    "DOGE": Contract("DOP-20DEC30-CDE", 5_000.0, "DOGE PERP"),
    "kPEPE": Contract("PEP-20DEC30-CDE", 100.0, "1000PEPE PERP"),
    "kSHIB": Contract("SHP-20DEC30-CDE", 10.0, "1000SHIB PERP"),
}
US_COINS = tuple(CONTRACTS)

# Round trip assumed for the sim book on this venue: Coinbase quotes
# futures fees "as low as 0.02%" per contract side and charged 0.05%
# during beta; 0.10% a side here is deliberately pessimistic. The rule
# survives a 0.60% round trip in backtest.
TAKER_FEE = 0.0010


class SizeTooSmall(ValueError):
    pass


@dataclass
class CoinbaseExecConfig:
    live: bool = False
    key_name_env: str = "CRYPTOBOT_COINBASE_KEY_NAME"      # organizations/.../apiKeys/...
    key_secret_env: str = "CRYPTOBOT_COINBASE_KEY_SECRET"  # the EC private key PEM
    max_trade_usd: float = 500.0
    max_slippage: float = 0.01


class CoinbaseFuturesExecutor:
    def __init__(self, cfg: CoinbaseExecConfig, client=None):
        self.cfg = cfg
        self._name = os.environ.get(cfg.key_name_env, "")
        self._secret = os.environ.get(cfg.key_secret_env, "").replace("\\n", "\n")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self._name and self._secret)
        if cfg.live and env_armed and not (self._name and self._secret):
            logger.warning("coinbase futures armed but %s/%s missing — dry-run",
                           cfg.key_name_env, cfg.key_secret_env)
        self._client = client

    @property
    def armed(self) -> bool:
        return self._armed

    def _c(self):
        if self._client is None:
            from coinbase.rest import RESTClient          # noqa: WPS433
            self._client = RESTClient(api_key=self._name, api_secret=self._secret)
        return self._client

    @staticmethod
    def contract(coin: str) -> Contract:
        try:
            return CONTRACTS[coin]
        except KeyError:
            raise ValueError(f"{coin} has no Coinbase US perpetual-style future") from None

    def contracts_for(self, coin: str, notional_usd: float, mid: float) -> int:
        """Whole contracts that fit in `notional_usd` at `mid`, capped by
        max_trade_usd. Zero when one contract is more than the slot."""
        c = self.contract(coin)
        per_contract = c.units_per_contract * mid
        return int(math.floor(min(notional_usd, self.cfg.max_trade_usd) / per_contract))

    async def open_short(self, coin: str, notional_usd: float, mid: float) -> Fill:
        c = self.contract(coin)
        n = self.contracts_for(coin, notional_usd, mid)
        if n <= 0:
            raise SizeTooSmall(f"{coin}: one {c.display} contract is "
                               f"${c.units_per_contract * mid:,.0f}, slot is ${notional_usd:,.0f}")
        qty = n * c.units_per_contract
        if not self._armed:
            logger.info("DRY-RUN coinbase short %s x%d (%s) ~$%.0f", c.product_id, n, coin,
                        qty * mid)
            return Fill(coin, "short", qty, mid, dry_run=True)
        return await asyncio.to_thread(self._sell, coin, n, mid)

    async def close(self, coin: str, qty: float, mid: float) -> Fill:
        c = self.contract(coin)
        n = max(1, int(round(qty / c.units_per_contract)))
        if not self._armed:
            logger.info("DRY-RUN coinbase close %s x%d", c.product_id, n)
            return Fill(coin, "close", n * c.units_per_contract, mid, dry_run=True)
        return await asyncio.to_thread(self._close, coin, n, mid)

    # -- SDK calls (sync, run in a thread) --------------------------------------

    def _sell(self, coin: str, n: int, mid: float) -> Fill:
        c = self.contract(coin)
        res = self._c().market_order_sell(client_order_id=str(uuid.uuid4()),
                                          product_id=c.product_id, base_size=str(n))
        return self._fill_from(res, coin, "short", n, mid)

    def _close(self, coin: str, n: int, mid: float) -> Fill:
        c = self.contract(coin)
        res = self._c().close_position(client_order_id=str(uuid.uuid4()),
                                       product_id=c.product_id, size=str(n))
        return self._fill_from(res, coin, "close", n, mid)

    def _fill_from(self, res, coin: str, side: str, n: int, mid: float) -> Fill:
        d = res.to_dict() if hasattr(res, "to_dict") else dict(res)
        if not d.get("success", False):
            err = d.get("error_response") or {}
            raise RuntimeError(f"{coin} {side} rejected: "
                               f"{err.get('new_order_failure_reason') or err.get('error')}: "
                               f"{err.get('message') or err.get('error_details')}")
        order_id = (d.get("success_response") or {}).get("order_id")
        c = self.contract(coin)
        filled, px = float(n), mid
        if order_id:
            try:
                o = self._c().get_order(order_id)
                od = (o.to_dict() if hasattr(o, "to_dict") else dict(o)).get("order") or {}
                filled = float(od.get("filled_size") or n)
                px = float(od.get("average_filled_price") or 0) or mid
            except Exception as exc:                       # the order stands either way
                logger.warning("get_order %s failed: %s", order_id, exc)
        if filled <= 0:
            raise RuntimeError(f"{coin} {side}: IOC order did not fill")
        # Coinbase quotes 1000PEPE / 1000SHIB per thousand tokens, as the bot does.
        return Fill(coin, side, filled * c.units_per_contract, px, order_id=order_id)

    async def preview(self, coin: str, n: int = 1) -> dict:
        """Ask Coinbase to price an n-contract market sell WITHOUT placing
        it: the account's real fee, margin and any rejection reason. Needs
        the key (not arming); the dry-run path never sends anything."""
        c = self.contract(coin)

        def _get():
            r = self._c().preview_market_order_sell(product_id=c.product_id, base_size=str(n))
            d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            p = self._c().get_product(c.product_id, get_tradability_status=True)
            pd = p.to_dict() if hasattr(p, "to_dict") else dict(p)
            return {
                "coin": coin, "product_id": c.product_id, "contracts": n,
                "order_total": float(d.get("order_total") or 0),
                "commission": float(d.get("commission_total") or 0),
                "margin": float(d.get("order_margin_total") or 0),
                "errs": list(d.get("errs") or []),
                "warnings": list(d.get("warning") or []),
                "tradable": not (pd.get("trading_disabled") or pd.get("is_disabled")
                                 or pd.get("view_only") or pd.get("status") not in (None, "online")),
                "status": pd.get("status"),
            }
        return await asyncio.to_thread(_get)

    async def balance(self) -> dict:
        """Futures account figures (USD)."""
        def _get():
            r = self._c().get_futures_balance_summary()
            d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            bs = d.get("balance_summary") or d
            return {k: float((bs.get(k) or {}).get("value", bs.get(k)) or 0.0)
                    for k in ("futures_buying_power", "total_usd_balance", "cfm_usd_balance",
                              "available_margin", "liquidation_threshold")}
        return await asyncio.to_thread(_get)
