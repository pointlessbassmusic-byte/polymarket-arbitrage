"""tastytrade Open API: options, futures and futures options (CME micro
Bitcoin among them) behind an official OAuth2 API.

Plumbing for `btc-vrp-listed-options` and any future index-futures rule;
nothing registered trades it yet. The client reads accounts, balances
and positions, lists futures products (to confirm /MBT) and can dry-run
an order. Live orders need the same three gates as every venue: the
config says live, CRYPTOBOT_ARM_LIVE=yes, and the credentials exist.

Credentials are an OAuth2 personal app's client secret plus a refresh
token (my.tastytrade.com -> Manage -> API). Access tokens last about 15
minutes and are refreshed here on demand; the refresh token itself is
never sent anywhere but the token endpoint.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

PROD_URL = "https://api.tastyworks.com"
CERT_URL = "https://api.cert.tastyworks.com"      # sandbox


@dataclass
class TastytradeConfig:
    live: bool = False
    client_secret_env: str = "CRYPTOBOT_TASTY_CLIENT_SECRET"
    refresh_token_env: str = "CRYPTOBOT_TASTY_REFRESH_TOKEN"
    base_url: str = PROD_URL
    timeout_s: float = 20.0


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class TastytradeClient:
    def __init__(self, cfg: TastytradeConfig, client: Optional[httpx.AsyncClient] = None, *,
                 client_secret: Optional[str] = None, refresh_token: Optional[str] = None,
                 now: Callable[[], float] = time.time):
        self.cfg = cfg
        self._secret = client_secret if client_secret is not None else os.environ.get(cfg.client_secret_env, "")
        self._refresh = refresh_token if refresh_token is not None else os.environ.get(cfg.refresh_token_env, "")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self.has_key)
        if cfg.live and env_armed and not self.has_key:
            logger.warning("tastytrade armed but %s/%s missing — dry-run only",
                           cfg.client_secret_env, cfg.refresh_token_env)
        self._now = now
        self._token = ""
        self._token_exp = 0.0
        self._c = client or httpx.AsyncClient(timeout=cfg.timeout_s)
        self._owns = client is None
        self.token_refreshes = 0

    @property
    def has_key(self) -> bool:
        return bool(self._secret and self._refresh)

    @property
    def armed(self) -> bool:
        return self._armed

    async def close_client(self) -> None:
        if self._owns:
            await self._c.aclose()

    # -- auth ---------------------------------------------------------------

    async def access_token(self) -> str:
        if self._token and self._now() < self._token_exp - 60:
            return self._token
        r = await self._c.request("POST", self.cfg.base_url.rstrip("/") + "/oauth/token",
                                  data={"grant_type": "refresh_token", "refresh_token": self._refresh,
                                        "client_secret": self._secret})
        if r.status_code >= 400:
            raise RuntimeError(f"tastytrade token -> {r.status_code}: {r.text[:200]}")
        d = r.json()
        self._token = d.get("access_token", "")
        self._token_exp = self._now() + _f(d.get("expires_in"), 900.0)
        self.token_refreshes += 1
        if not self._token:
            raise RuntimeError("tastytrade token response had no access_token")
        return self._token

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                       json: Optional[dict] = None) -> dict:
        tok = await self.access_token()
        r = await self._c.request(method, self.cfg.base_url.rstrip("/") + path, params=params, json=json,
                                  headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
        if r.status_code >= 400:
            raise RuntimeError(f"tastytrade {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    # -- account -------------------------------------------------------------

    async def accounts(self) -> list[str]:
        d = await self._request("GET", "/customers/me/accounts")
        out = []
        for it in (d.get("data") or {}).get("items") or []:
            acct = it.get("account") or it
            n = acct.get("account-number")
            if n:
                out.append(n)
        return out

    async def balances(self, account: str) -> dict:
        """Shared keys (total_usd_balance = net liquidating value,
        available_margin = derivative buying power) plus the raw fields."""
        d = (await self._request("GET", f"/accounts/{account}/balances")).get("data") or {}
        return {"total_usd_balance": _f(d.get("net-liquidating-value")),
                "available_margin": _f(d.get("derivative-buying-power")) or _f(d.get("equity-buying-power")),
                "cash": _f(d.get("cash-balance")),
                "maintenance_requirement": _f(d.get("maintenance-requirement")),
                "futures_margin_requirement": _f(d.get("futures-margin-requirement"))}

    async def positions(self, account: str) -> list[dict]:
        d = (await self._request("GET", f"/accounts/{account}/positions")).get("data") or {}
        out = []
        for p in d.get("items") or []:
            q = _f(p.get("quantity"))
            if p.get("quantity-direction") == "Short":
                q = -abs(q)
            out.append({"symbol": p.get("symbol"), "type": p.get("instrument-type"), "qty": q,
                        "avg_price": _f(p.get("average-open-price"))})
        return out

    # -- instruments ------------------------------------------------------------

    async def future_products(self) -> list[dict]:
        d = (await self._request("GET", "/instruments/future-products")).get("data") or {}
        return list(d.get("items") or [])

    async def futures(self, product_code: str) -> list[dict]:
        d = (await self._request("GET", "/instruments/futures",
                                 params={"product-code[]": product_code})).get("data") or {}
        return [f for f in (d.get("items") or []) if f.get("active", True)]

    async def micro_bitcoin(self) -> list[str]:
        """Active CME micro Bitcoin contracts (/MBT...), empty if unlisted."""
        return [f.get("symbol") for f in await self.futures("MBT") if f.get("symbol")]

    # -- orders ----------------------------------------------------------------

    async def order(self, account: str, legs: list[dict], *, price: Optional[float] = None,
                    price_effect: str = "Debit", time_in_force: str = "Day", dry_run: bool = True) -> dict:
        """Submit (or dry-run) a tastytrade order. A leg is
        {"instrument-type": "Future", "symbol": "/MBTZ6", "action": "Buy to Open", "quantity": 1}.
        Live submission needs the three gates; dry-run only needs keys."""
        body: dict = {"time-in-force": time_in_force, "order-type": "Limit" if price is not None else "Market",
                      "legs": legs}
        if price is not None:
            body["price"] = f"{price:.2f}"
            body["price-effect"] = price_effect
        if not dry_run and not self._armed:
            logger.info("DRY-RUN tastytrade order (not armed): %s", body)
            return {"dry_run": True, "order": body}
        path = f"/accounts/{account}/orders" + ("/dry-run" if dry_run else "")
        return (await self._request("POST", path, json=body)).get("data") or {}
