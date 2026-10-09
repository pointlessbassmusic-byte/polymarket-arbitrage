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
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from .perp_exchange import Fill, SizeTooSmall  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Contract:
    product_id: str
    units_per_contract: float      # in the bot's units (kPEPE = 1000 PEPE)
    display: str


# Bot coin name -> Coinbase US perpetual-style future.
CONTRACTS = {
    # units_per_contract is in the bot's price units: DOGE per DOGE; kPEPE
    # and kSHIB are priced per 1,000 coins (Hyperliquid's k-prefix, and
    # Coinbase's "1000PEPE"/"1000SHIB" products use the same quote), so
    # Coinbase's contract_size field (100,000 / 10,000) is ALREADY in those
    # units: one 1000PEPE contract is 100,000 x (1,000 PEPE) = $380-450.
    # Verified against the public product endpoint (contract_size x price).
    "DOGE": Contract("DOP-20DEC30-CDE", 5_000.0, "DOGE PERP"),
    "kPEPE": Contract("PEP-20DEC30-CDE", 100_000.0, "1000PEPE PERP"),
    "kSHIB": Contract("SHP-20DEC30-CDE", 10_000.0, "1000SHIB PERP"),
}
US_COINS = tuple(CONTRACTS)

# Round trip assumed for the sim book on this venue: Coinbase quotes
# futures fees "as low as 0.02%" per contract side and charged 0.05%
# during beta; 0.10% a side here is deliberately pessimistic. The rule
# survives a 0.60% round trip in backtest.
# Introductory US futures rate per side, all-in, with a per-contract floor.
TAKER_FEE = 0.0005
MIN_FEE_PER_CONTRACT = 0.20


def effective_fee(coin: str, mid: float) -> float:
    """Per-side fee as a fraction of notional for ONE contract at `mid`:
    the rate, or the floor when the contract is small (1000SHIB)."""
    c = CONTRACTS[coin]
    notional = c.units_per_contract * mid
    return max(TAKER_FEE, MIN_FEE_PER_CONTRACT / notional) if notional > 0 else TAKER_FEE




@dataclass
class CoinbaseExecConfig:
    live: bool = False
    key_name_env: str = "CRYPTOBOT_COINBASE_KEY_NAME"      # organizations/.../apiKeys/...
    key_secret_env: str = "CRYPTOBOT_COINBASE_KEY_SECRET"  # the EC private key PEM
    max_trade_usd: float = 500.0
    max_slippage: float = 0.01
    fill_polls: int = 6              # get_order attempts after placing
    fill_poll_s: float = 0.5


def _as_dict(res) -> dict:
    """SDK responses are typed objects with to_dict(); fakes may be dicts."""
    return res.to_dict() if hasattr(res, "to_dict") else dict(res)


class CoinbaseFuturesExecutor:
    def __init__(self, cfg: CoinbaseExecConfig, client=None, *,
                 key_name: Optional[str] = None, key_secret: Optional[str] = None):
        self.cfg = cfg
        self._name = key_name if key_name is not None else os.environ.get(cfg.key_name_env, "")
        secret = key_secret if key_secret is not None else os.environ.get(cfg.key_secret_env, "")
        self._secret = secret.replace("\\n", "\n")          # PEM pasted on one line in .env
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
        # +1e-9: the slot was itself computed as n * per_contract, and
        # floating point can make that ratio 2.9999999999999996.
        return int(math.floor(min(notional_usd, self.cfg.max_trade_usd) / per_contract + 1e-9))

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
        d = _as_dict(res)
        if not d.get("success", False):
            err = d.get("error_response") or {}
            raise RuntimeError(f"{coin} {side} rejected: "
                               f"{err.get('new_order_failure_reason') or err.get('error')}: "
                               f"{err.get('message') or err.get('error_details')}")
        order_id = (d.get("success_response") or {}).get("order_id")
        c = self.contract(coin)
        filled, px, fee = float(n), mid, None
        if order_id:
            # A market IOC fills within moments, but get_order right after
            # placement can still say PENDING with filled_size 0. Poll
            # briefly; a terminal unfilled state is a real failure, and an
            # order still unfilled after the polls is NOT booked.
            for attempt in range(self.cfg.fill_polls):
                try:
                    od = _as_dict(self._c().get_order(order_id)).get("order") or {}
                except Exception as exc:                   # the order stands either way
                    logger.warning("get_order %s failed: %s", order_id, exc)
                    break
                got = float(od.get("filled_size") or 0)
                status = str(od.get("status") or "").upper()
                if got > 0:
                    filled = got
                    px = float(od.get("average_filled_price") or 0) or mid
                    try:
                        fee = float(od["total_fees"]) if od.get("total_fees") not in (None, "") else None
                    except (TypeError, ValueError):
                        fee = None
                    break
                if status in ("CANCELLED", "EXPIRED", "FAILED", "REJECTED"):
                    raise RuntimeError(f"{coin} {side}: order {order_id} ended {status} unfilled")
                if attempt + 1 < self.cfg.fill_polls:
                    time.sleep(self.cfg.fill_poll_s)
            else:
                # Still not filled after the polls: book nothing. If it fills
                # later, reconcile shows it as venue-only and alerts.
                raise RuntimeError(f"{coin} {side}: order {order_id} unfilled after "
                                   f"{self.cfg.fill_polls} polls; not booked (check reconcile)")
        # Coinbase quotes 1000PEPE / 1000SHIB per thousand tokens, as the bot does.
        return Fill(coin, side, filled * c.units_per_contract, px, order_id=order_id, fee_usd=fee)

    async def preview(self, coin: str, n: int = 1) -> dict:
        """Ask Coinbase to price an n-contract market sell WITHOUT placing
        it: the account's real fee, margin and any rejection reason. Needs
        the key (not arming); the dry-run path never sends anything."""
        c = self.contract(coin)

        def _get():
            d = _as_dict(self._c().preview_market_order_sell(product_id=c.product_id, base_size=str(n)))
            pd = _as_dict(self._c().get_product(c.product_id, get_tradability_status=True))
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

    async def positions(self) -> dict[str, float]:
        """Open venue positions as coin -> signed units (short negative)."""
        by_pid = {c.product_id: (coin, c.units_per_contract) for coin, c in CONTRACTS.items()}

        def _get():
            d = _as_dict(self._c().list_futures_positions())
            out: dict[str, float] = {}
            for pos in d.get("positions") or []:
                hit = by_pid.get(pos.get("product_id"))
                if not hit:
                    continue
                coin, units = hit
                n = float(pos.get("number_of_contracts") or 0)
                if n:   # side is the enum string FUTURES_POSITION_SIDE_SHORT (or bare SHORT)
                    short = str(pos.get("side", "")).upper().endswith("SHORT")
                    out[coin] = -n * units if short else n * units
            return out
        return await asyncio.to_thread(_get)

    async def balance(self) -> dict:
        """Futures account figures (USD)."""
        def _get():
            d = _as_dict(self._c().get_futures_balance_summary())
            bs = d.get("balance_summary") or d
            return {k: float((bs.get(k) or {}).get("value", bs.get(k)) or 0.0)
                    for k in ("futures_buying_power", "total_usd_balance", "cfm_usd_balance",
                              "available_margin", "liquidation_threshold")}
        return await asyncio.to_thread(_get)
