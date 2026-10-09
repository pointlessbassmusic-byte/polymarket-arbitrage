"""Kraken Pro spot margin: short DOGE, PEPE and SHIB from a US account.

Kraken opened spot margin to US retail on 2026-05-06 through Kraken
Derivatives US (NinjaTrader Clearing, a CFTC-registered FCM), long or
short. The eligible list that matters here: DOGE up to 10x, PEPE and
SHIB up to 5x (support.kraken.com "Getting started with US margin
trading", October 2026). It is the same REST API the carry bot's spot
leg already signs: AddOrder with `leverage`, `reduce_only` and
`validate`, positions from OpenPositions, equity from TradeBalance.

Why it is not the default venue: the borrow. A margin short pays an
opening fee plus a rollover fee every 4 hours (0.02-0.04% each for these
coins), on top of tier-1 trading fees of 0.40% maker / 0.80% taker since
2026-07-09. Replayed on the bounce-short (DOGE/PEPE/SHIB, 2022-2026) that
turns +1.92% per trade on Kalshi into -0.56% to -1.51% here; see the
`kraken-margin-venue` registry entry. The executor exists so the venue
can be selected, preflighted and paper-traded at its true cost.

Sizing differs from the perp venues: no contracts, only Kraken's order
minimums (DOGE 50, PEPE 1.5M, SHIB 770k: about $4-6 each), so a $100
account can hold every slot. Bot prices for kPEPE / kSHIB are per 1,000
coins (the Hyperliquid convention the strategy was validated on); orders
are converted to Kraken's per-coin units here and back on the fill.

Arming matches every other executor: config live AND CRYPTOBOT_ARM_LIVE=yes
AND both key variables. A key needs Query Funds, Query Open Orders &
Trades, Create & Modify Orders (and Query Ledger for the rollover
history) and NEVER withdrawal. `validate_short` asks Kraken to check an
order without placing it; preflight uses it to prove the account can
short each pair before any money moves.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from .kraken_spot import KrakenSpotExecutor, SpotExecConfig, floor_to
from .perp_exchange import Fill, SizeTooSmall  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)

# Max leverage for US retail, per Kraken's US margin page (2026-10).
US_MARGIN_LEVERAGE = {"DOGE": 10, "kPEPE": 5, "kSHIB": 5}
US_COINS = ("DOGE", "kPEPE", "kSHIB")


@dataclass
class KrakenMarginConfig:
    live: bool = False
    key_env: str = "CRYPTOBOT_KRAKEN_KEY"
    secret_env: str = "CRYPTOBOT_KRAKEN_SECRET"
    max_trade_usd: float = 500.0
    max_slippage: float = 0.005        # IOC limit from mid; books fill $1k within 1-3 bp
    leverage: int = 2                  # Kraken's minimum to open on margin: collateral = notional / 2
    fill_polls: int = 6
    fill_poll_s: float = 0.5


def units(coin: str) -> float:
    """Coins per bot unit: kPEPE / kSHIB are priced per 1,000 coins."""
    return 1000.0 if coin.startswith("k") and coin[1:].isupper() else 1.0


def parse_rollover(terms: str) -> Optional[float]:
    """'0.0200% per 4 hours' -> 0.0002 (fraction per 4 hours)."""
    m = re.search(r"([0-9.]+)\s*%\s*per\s*4\s*hour", terms or "")
    return float(m.group(1)) / 100.0 if m else None


def _ceil_to(x: float, decimals: int) -> float:
    q = 10 ** decimals
    return math.ceil(x * q - 1e-9) / q


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class KrakenMarginExecutor(KrakenSpotExecutor):
    def __init__(self, cfg: KrakenMarginConfig, client: Optional[httpx.AsyncClient] = None, *,
                 key: Optional[str] = None, secret: Optional[str] = None,
                 coins: tuple = US_COINS):
        # The parent's own arming (and its warning) is bypassed with live=False:
        # keys may be passed in explicitly here, so arming is decided below.
        super().__init__(SpotExecConfig(live=False, key_env=cfg.key_env, secret_env=cfg.secret_env,
                                        max_trade_usd=cfg.max_trade_usd, max_slippage=cfg.max_slippage),
                         client)
        self.mcfg = cfg
        self.coins = tuple(coins)
        if key is not None:
            self._key = key
        if secret is not None:
            self._secret = secret
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self._key and self._secret)
        if cfg.live and not env_armed:
            logger.warning("kraken margin live is true but CRYPTOBOT_ARM_LIVE!=yes — staying in dry-run")
        if cfg.live and env_armed and not self.has_key:
            logger.warning("kraken margin armed but %s/%s missing — dry-run", cfg.key_env, cfg.secret_env)

    @property
    def has_key(self) -> bool:
        return bool(self._key and self._secret)

    async def close_client(self) -> None:
        """Release the HTTP client (the spot executor's `close()`; here
        `close` is the perp interface's buy-back)."""
        await KrakenSpotExecutor.close(self)

    # -- orders ----------------------------------------------------------------

    def _leverage_for(self, coin: str) -> int:
        cap = US_MARGIN_LEVERAGE.get(coin, self.mcfg.leverage)
        return max(2, min(int(self.mcfg.leverage), cap))

    async def _short_order(self, coin: str, notional_usd: float, mid: float) -> tuple[dict, dict]:
        info = await self._pair_info(coin)
        k = units(coin)
        base_px = mid / k
        notional = min(notional_usd, self.mcfg.max_trade_usd)
        vol = floor_to(notional / base_px, info["lot_decimals"]) if base_px > 0 else 0.0
        if vol <= 0 or vol < info["ordermin"]:
            raise SizeTooSmall(f"{coin}: Kraken's minimum is {info['ordermin']:g} coins "
                               f"(~${info['ordermin'] * base_px:,.2f}); slot is ${notional_usd:,.2f}")
        limit = floor_to(base_px * (1.0 - self.mcfg.max_slippage), info["pair_decimals"])
        body = {"pair": info["name"], "type": "sell", "ordertype": "limit",
                "price": f"{limit:.{info['pair_decimals']}f}", "volume": f"{vol:.{info['lot_decimals']}f}",
                "leverage": str(self._leverage_for(coin)), "timeinforce": "IOC"}
        return info, body

    async def open_short(self, coin: str, notional_usd: float, mid: float) -> Fill:
        info, body = await self._short_order(coin, notional_usd, mid)
        k = units(coin)
        vol = float(body["volume"])
        if not self._armed:
            logger.info("DRY-RUN kraken margin short %s %s x%sx @ <= %s", info["name"], body["volume"],
                        body["leverage"], body["price"])
            return Fill(coin, "short", vol / k, mid, dry_run=True)
        return await self._margin_order(coin, info, body, "short")

    async def close(self, coin: str, qty: float, mid: float) -> Fill:   # type: ignore[override]
        """Buy back a short: reduce-only, so a stale state file can only
        flatten, never open a long."""
        info = await self._pair_info(coin)
        k = units(coin)
        vol = round(abs(qty) * k, info["lot_decimals"])
        base_px = mid / k
        limit = _ceil_to(base_px * (1.0 + self.mcfg.max_slippage), info["pair_decimals"])
        if not self._armed:
            logger.info("DRY-RUN kraken margin close %s %s", info["name"], vol)
            return Fill(coin, "close", abs(qty), mid, dry_run=True)
        body = {"pair": info["name"], "type": "buy", "ordertype": "limit",
                "price": f"{limit:.{info['pair_decimals']}f}", "volume": f"{vol:.{info['lot_decimals']}f}",
                "leverage": str(self._leverage_for(coin)), "timeinforce": "IOC", "reduce_only": "true"}
        return await self._margin_order(coin, info, body, "close")

    async def _margin_order(self, coin: str, info: dict, body: dict, label: str) -> Fill:
        res = await self._private("AddOrder", body)
        txid = (res.get("txid") or [None])[0]
        if not txid:
            raise RuntimeError(f"kraken AddOrder returned no txid: {res}")
        o: dict = {}
        for i in range(self.mcfg.fill_polls):
            o = (await self._private("QueryOrders", {"txid": txid})).get(txid) or {}
            if o.get("status") in ("closed", "canceled", "expired"):
                break
            await asyncio.sleep(self.mcfg.fill_poll_s)
        else:
            raise RuntimeError(f"{info['name']} margin {label} {txid}: state unknown after polling")
        filled = _f(o.get("vol_exec"))
        if filled <= 0:
            raise RuntimeError(f"{coin} {label}: IOC at {body['price']} did not fill (order {txid})")
        k = units(coin)
        px = _f(o.get("price"), float(body["price"]))
        return Fill(coin, label, filled / k, px * k, order_id=txid, fee_usd=_f(o.get("fee")) or None)

    async def validate_short(self, coin: str, notional_usd: float, mid: float) -> dict:
        """Ask Kraken to validate one short without placing it. Needs a
        key, not arming: nothing trades. {"coin", "ok", "error"}."""
        try:
            info, body = await self._short_order(coin, notional_usd, mid)
            await self._private("AddOrder", {**body, "validate": "true"})
            return {"coin": coin, "ok": True, "error": "", "pair": info["name"], "leverage": body["leverage"]}
        except Exception as exc:                   # noqa: BLE001 - reported, not raised
            return {"coin": coin, "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    # -- account ---------------------------------------------------------------

    async def _pair_to_coin(self) -> dict[str, str]:
        out = {}
        for coin in self.coins:
            try:
                out[(await self._pair_info(coin))["name"]] = coin
            except ValueError:
                continue
        return out

    async def open_positions(self) -> list[dict]:
        """One row per Kraken margin position, in bot units, with the
        rollover rate locked at entry."""
        by_pair = await self._pair_to_coin()
        res = await self._private("OpenPositions", {"docalcs": "true"})
        rows = []
        for posid, p in (res or {}).items():
            coin = by_pair.get(p.get("pair"))
            if coin is None:
                continue
            open_vol = _f(p.get("vol")) - _f(p.get("vol_closed"))
            sign = -1.0 if p.get("type") == "sell" else 1.0
            rows.append({"id": posid, "coin": coin, "units": sign * open_vol / units(coin),
                         "cost": _f(p.get("cost")), "fee": _f(p.get("fee")), "margin": _f(p.get("margin")),
                         "net": _f(p.get("net")), "opened": _f(p.get("time")),
                         "rollover_per_4h": parse_rollover(p.get("terms", ""))})
        return rows

    async def positions(self) -> dict[str, float]:        # type: ignore[override]
        """coin -> signed bot units (short negative), summed over Kraken's
        per-order positions."""
        out: dict[str, float] = {}
        for r in await self.open_positions():
            out[r["coin"]] = out.get(r["coin"], 0.0) + r["units"]
        return {c: v for c, v in out.items() if abs(v) > 1e-12}

    async def balance(self) -> dict:                       # type: ignore[override]
        """Shared keys (total_usd_balance = equity, available_margin = free
        margin) plus TradeBalance's own figures."""
        tb = await self._private("TradeBalance", {"asset": "ZUSD"})
        return {"total_usd_balance": _f(tb.get("e")), "available_margin": _f(tb.get("mf")),
                "margin_used": _f(tb.get("m")), "margin_level": _f(tb.get("ml")) if tb.get("ml") else None,
                "unrealized": _f(tb.get("n")), "trade_balance": _f(tb.get("tb"))}
