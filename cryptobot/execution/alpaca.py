"""Alpaca: US stocks, ETFs and options through an official REST API.

Why this broker: commission-free US equities and options, a paper
endpoint that speaks the same API, and free IEX market data. The
investigation queue's equity items (`orb-qqq-pilot`, `pead-revisit`)
need an equity broker and intraday bars; Alpaca supplies both for no
monthly fee. Fidelity has no retail API (RESEARCH-2026-10.md, addendum 5).

Three modes, decided at construction:

  dry-run   no keys, or `live: true` without CRYPTOBOT_ARM_LIVE=yes:
            orders are logged and nothing is sent
  paper     keys present and `live: false`: orders go to
            paper-api.alpaca.markets (fake money, real API, real quotes)
  live      `live: true` AND CRYPTOBOT_ARM_LIVE=yes AND keys: api.alpaca.markets

Orders are IOC limit orders at mid x (1 +- max_slippage), whole shares
(Alpaca only accepts short sales and IOC orders in whole shares;
fractional orders must be market/day and are not sent from here).
Closes go through the positions endpoint, so a stale state file can
never flip a position instead of flattening it. Keys never leave the
process; the headers are the only place they are used.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .perp_exchange import Fill, SizeTooSmall  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
TERMINAL = ("filled", "canceled", "expired", "rejected", "done_for_day", "replaced")


@dataclass
class AlpacaConfig:
    live: bool = False
    key_env: str = "CRYPTOBOT_ALPACA_KEY_ID"
    secret_env: str = "CRYPTOBOT_ALPACA_SECRET_KEY"
    paper_url: str = PAPER_URL
    live_url: str = LIVE_URL
    data_url: str = DATA_URL
    feed: str = "iex"                 # the free feed; "sip" needs the paid data plan
    max_trade_usd: float = 500.0
    max_slippage: float = 0.002       # 20 bp IOC limit from mid; large caps quote 1-2 bp wide
    timeout_s: float = 20.0
    fill_polls: int = 10
    fill_poll_s: float = 0.5


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class AlpacaExecutor:
    def __init__(self, cfg: AlpacaConfig, client: Optional[httpx.AsyncClient] = None, *,
                 key_id: Optional[str] = None, secret: Optional[str] = None):
        self.cfg = cfg
        self._key = key_id if key_id is not None else os.environ.get(cfg.key_env, "")
        self._secret = secret if secret is not None else os.environ.get(cfg.secret_env, "")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self.has_key)
        if cfg.live and not env_armed:
            logger.warning("alpaca live is true but CRYPTOBOT_ARM_LIVE!=yes — staying in dry-run")
        if cfg.live and env_armed and not self.has_key:
            logger.warning("alpaca armed but %s/%s missing — dry-run", cfg.key_env, cfg.secret_env)
        if self._armed:
            self.mode = "live"
        elif self.has_key and not cfg.live:
            self.mode = "paper"
        else:
            self.mode = "dry-run"
        self.base = cfg.live_url if self._armed else cfg.paper_url
        self._c = client or httpx.AsyncClient(timeout=cfg.timeout_s)
        self._owns = client is None

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def has_key(self) -> bool:
        return bool(self._key and self._secret)

    @property
    def sends_orders(self) -> bool:
        """Paper and live both talk to Alpaca; dry-run never does."""
        return self.mode != "dry-run"

    async def close_client(self) -> None:
        if self._owns:
            await self._c.aclose()

    # -- transport ---------------------------------------------------------

    def headers(self) -> dict:
        return {"APCA-API-KEY-ID": self._key, "APCA-API-SECRET-KEY": self._secret,
                "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                       json: Optional[dict] = None, base: Optional[str] = None):
        url = (base or self.base).rstrip("/") + path
        r = await self._c.request(method, url, params=params, json=json, headers=self.headers())
        if r.status_code >= 400:
            raise RuntimeError(f"alpaca {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    # -- account -----------------------------------------------------------

    async def account(self) -> dict:
        return await self._request("GET", "/v2/account")

    async def balance(self) -> dict:
        """Shared keys (total_usd_balance, available_margin) plus Alpaca's
        own: cash, status, shorting_enabled, pattern_day_trader,
        daytrade_count, multiplier."""
        a = await self.account()
        return {"total_usd_balance": _f(a.get("equity")), "available_margin": _f(a.get("buying_power")),
                "cash": _f(a.get("cash")), "status": a.get("status"),
                "shorting_enabled": bool(a.get("shorting_enabled")),
                "pattern_day_trader": bool(a.get("pattern_day_trader")),
                "daytrade_count": int(_f(a.get("daytrade_count"))), "multiplier": _f(a.get("multiplier"), 1.0),
                "mode": self.mode}

    async def positions(self) -> dict[str, float]:
        """symbol -> signed shares (short negative)."""
        out: dict[str, float] = {}
        for p in await self._request("GET", "/v2/positions") or []:
            q = _f(p.get("qty"))
            if q:
                out[p["symbol"]] = -abs(q) if p.get("side") == "short" else q
        return out

    async def clock(self) -> dict:
        return await self._request("GET", "/v2/clock")

    async def mid(self, symbol: str) -> float:
        d = await self._request("GET", "/v2/stocks/quotes/latest",
                                params={"symbols": symbol, "feed": self.cfg.feed}, base=self.cfg.data_url)
        q = (d.get("quotes") or {}).get(symbol) or {}
        bid, ask = _f(q.get("bp")), _f(q.get("ap"))
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        t = await self._request("GET", "/v2/stocks/trades/latest",
                                params={"symbols": symbol, "feed": self.cfg.feed}, base=self.cfg.data_url)
        px = _f(((t.get("trades") or {}).get(symbol) or {}).get("p"))
        if px <= 0:
            raise RuntimeError(f"alpaca: no quote for {symbol}")
        return px

    # -- sizing and orders ---------------------------------------------------

    def shares_for(self, notional_usd: float, mid: float) -> int:
        return int(math.floor(min(notional_usd, self.cfg.max_trade_usd) / mid + 1e-9)) if mid > 0 else 0

    async def open_long(self, symbol: str, notional_usd: float, mid: float) -> Fill:
        return await self._open(symbol, notional_usd, mid, "buy", "long")

    async def open_short(self, symbol: str, notional_usd: float, mid: float) -> Fill:
        return await self._open(symbol, notional_usd, mid, "sell", "short")

    async def _open(self, symbol: str, notional_usd: float, mid: float, side: str, label: str) -> Fill:
        n = self.shares_for(notional_usd, mid)
        if n <= 0:
            raise SizeTooSmall(f"{symbol}: one share is ${mid:,.2f}, slot is ${notional_usd:,.0f}")
        limit = _limit(mid, self.cfg.max_slippage, side)
        if not self.sends_orders:
            logger.info("DRY-RUN alpaca %s %s x%d ~$%.0f", side, symbol, n, n * mid)
            return Fill(symbol, label, float(n), mid, dry_run=True)
        return await self._order(symbol, side, n, limit, label)

    async def close(self, symbol: str, qty: float, mid: float) -> Fill:
        """Flatten through the positions endpoint (never a fresh order
        that could overshoot into the opposite side)."""
        if not self.sends_orders:
            logger.info("DRY-RUN alpaca close %s x%.0f", symbol, abs(qty))
            return Fill(symbol, "close", abs(qty), mid, dry_run=True)
        d = await self._request("DELETE", f"/v2/positions/{symbol}")
        return await self._await_fill(symbol, "close", d.get("id"), fallback_px=mid)

    async def _order(self, symbol: str, side: str, n: int, limit: float, label: str) -> Fill:
        body = {"symbol": symbol, "qty": str(n), "side": side, "type": "limit",
                "time_in_force": "ioc", "limit_price": f"{limit:.2f}",
                "client_order_id": str(uuid.uuid4())}
        d = await self._request("POST", "/v2/orders", json=body)
        return await self._await_fill(symbol, label, d.get("id"), fallback_px=limit, first=d)

    async def _await_fill(self, symbol: str, label: str, order_id: Optional[str], *,
                          fallback_px: float, first: Optional[dict] = None) -> Fill:
        d = first or {}
        for i in range(self.cfg.fill_polls):
            if d.get("status") in TERMINAL or (i and d.get("status") == "partially_filled"):
                break
            if i:
                await asyncio.sleep(self.cfg.fill_poll_s)
            d = await self._request("GET", f"/v2/orders/{order_id}") if order_id else d
        filled = _f(d.get("filled_qty"))
        if filled <= 0:
            raise RuntimeError(f"{symbol} {label}: IOC order {order_id} did not fill (status {d.get('status')})")
        return Fill(symbol, label, filled, _f(d.get("filled_avg_price"), fallback_px), order_id=order_id)

    async def fills(self, limit: int = 100) -> list[dict]:
        return list(await self._request("GET", "/v2/account/activities/FILL",
                                        params={"page_size": limit}) or [])


def _limit(mid: float, slip: float, side: str) -> float:
    """Worst acceptable price, rounded away from mid to the cent so the
    cap is never tighter than intended."""
    if side == "buy":
        return math.ceil(mid * (1.0 + slip) * 100) / 100
    return math.floor(mid * (1.0 - slip) * 100) / 100
