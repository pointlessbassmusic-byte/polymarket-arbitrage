"""Kalshi perpetual futures ("margin") executor.

Kalshi is a CFTC-regulated DCM/DCO that US residents can use. Since June
2026 it lists perpetual futures on DOGE (100 DOGE a contract, ~$8),
SHIB (1,000 kSHIB = 1M SHIB, ~$5) and, listed but not yet active, PEPE.
Contracts fifty times smaller than Coinbase Derivatives' make the
whole-contract constraint irrelevant for a small account; fees are 4 bp
taker / 2 bp maker with no per-contract floor; margin allows ~2-3x on
shorts (the bot stays at 1x) and has no intraday/overnight switch.

API: REST under https://external-api.kalshi.com/trade-api/v2/margin/,
the same request signing as Kalshi's event-contract API (headers
KALSHI-ACCESS-KEY / -TIMESTAMP / -SIGNATURE; the signature is Ed25519 or
RSA-PSS-SHA256 over f"{timestamp_ms}{METHOD}{path}" with the path taken
WITHOUT query parameters). Production access is "rolling out member by
member", so /margin/enabled is the first thing preflight checks. Market
data endpoints need no key. Orders are limit orders in fixed-point
dollars; the bot sends immediate-or-cancel limits at mid +- max_slippage,
so an unfilled IOC is a definite non-fill, never a pending state.

Same arming rule as every executor: config live AND
CRYPTOBOT_ARM_LIVE=yes AND both key env vars present.
"""
from __future__ import annotations

import base64
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

from .perp_exchange import Fill, SizeTooSmall  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)

BASE = "https://external-api.kalshi.com/trade-api/v2"
DEMO_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
TAKER_FEE = 0.0004
MAKER_FEE = 0.0002


@dataclass(frozen=True)
class Contract:
    ticker: str
    units_per_contract: float     # in the bot's price units (kSHIB = 1,000 SHIB)
    display: str


# Verified against GET /margin/markets on 2026-10-08: contract_size x
# underlying_multiplier in the bot's units. "1K kSHIB" = 1,000 kSHIB units.
CONTRACTS = {
    "DOGE": Contract("KXDOGEPERP", 100.0, "100 DOGE"),
    "kSHIB": Contract("KXKSHIBPERP", 1_000.0, "1K kSHIB"),
    "kPEPE": Contract("KXKPEPEPERP", 1_000.0, "1K kPEPE"),   # listed, inactive on 2026-10-08
    # Index and metals perps: contract_size 0.001 of the index level, so a
    # bot price unit is one index point and a contract is ~$13.7 (US500),
    # ~$4.1 (gold). Plumbing only: no registered rule trades them yet.
    "US500": Contract("KXUS500PERP", 0.001, "US500"),
    "GOLD": Contract("KXGOLDPERP", 0.001, "Gold"),
}
US_COINS = ("DOGE", "kSHIB")          # the bounce-short universe; add kPEPE in config when it opens
TICK = 0.0001




@dataclass
class KalshiExecConfig:
    live: bool = False
    key_id_env: str = "CRYPTOBOT_KALSHI_KEY_ID"
    key_pem_env: str = "CRYPTOBOT_KALSHI_KEY_PEM"     # private key PEM; \\n for newlines in .env
    base_url: str = BASE
    max_trade_usd: float = 500.0
    max_slippage: float = 0.005                       # IOC limit distance from mid
    timeout_s: float = 20.0


def sign(pem: str, message: str) -> str:
    """Base64 signature of the pre-sign text with an Ed25519 or RSA key."""
    from cryptography.hazmat.primitives import hashes, serialization      # noqa: WPS433
    from cryptography.hazmat.primitives.asymmetric import ed25519, padding  # noqa: WPS433
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    data = message.encode()
    if isinstance(key, ed25519.Ed25519PrivateKey):
        sig = key.sign(data)
    else:
        sig = key.sign(data, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                         salt_length=hashes.SHA256.digest_size), hashes.SHA256())
    return base64.b64encode(sig).decode()


def presign_text(ts_ms: int, method: str, path: str) -> str:
    """Path WITHOUT query parameters, with the /trade-api/v2 prefix."""
    return f"{ts_ms}{method.upper()}{path.split('?', 1)[0]}"


def _fp(x: float, decimals: int = 4) -> str:
    return f"{x:.{decimals}f}"


def _as_float(v, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class KalshiPerpsExecutor:
    def __init__(self, cfg: KalshiExecConfig, client: Optional[httpx.AsyncClient] = None, *,
                 key_id: Optional[str] = None, key_pem: Optional[str] = None):
        self.cfg = cfg
        self._key_id = key_id if key_id is not None else os.environ.get(cfg.key_id_env, "")
        pem = key_pem if key_pem is not None else os.environ.get(cfg.key_pem_env, "")
        self._pem = pem.replace("\\n", "\n")
        env_armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        self._armed = bool(cfg.live and env_armed and self._key_id and self._pem)
        if cfg.live and env_armed and not (self._key_id and self._pem):
            logger.warning("kalshi perps armed but %s/%s missing — dry-run",
                           cfg.key_id_env, cfg.key_pem_env)
        self._c = client or httpx.AsyncClient(timeout=cfg.timeout_s)
        self._owns = client is None

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def has_key(self) -> bool:
        return bool(self._key_id and self._pem)

    async def close_client(self) -> None:
        if self._owns:
            await self._c.aclose()

    # -- signing -----------------------------------------------------------

    def headers(self, method: str, path: str) -> dict:
        ts = int(time.time() * 1000)
        return {"KALSHI-ACCESS-KEY": self._key_id,
                "KALSHI-ACCESS-TIMESTAMP": str(ts),
                "KALSHI-ACCESS-SIGNATURE": sign(self._pem, presign_text(ts, method, path)),
                "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                       json: Optional[dict] = None, auth: bool = True) -> dict:
        from urllib.parse import urlparse
        base = self.cfg.base_url.rstrip("/")
        full_path = urlparse(base).path + path         # "/trade-api/v2/margin/..."
        headers = self.headers(method, full_path) if auth else {}
        r = await self._c.request(method, base + path, params=params, json=json, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"kalshi {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    # -- sizing ----------------------------------------------------------------

    @staticmethod
    def contract(coin: str) -> Contract:
        try:
            return CONTRACTS[coin]
        except KeyError:
            raise ValueError(f"{coin} has no Kalshi perpetual") from None

    def contracts_for(self, coin: str, notional_usd: float, mid: float) -> int:
        c = self.contract(coin)
        per = c.units_per_contract * mid
        return int(math.floor(min(notional_usd, self.cfg.max_trade_usd) / per + 1e-9))

    # -- orders ----------------------------------------------------------------

    async def open_short(self, coin: str, notional_usd: float, mid: float) -> Fill:
        c = self.contract(coin)
        n = self.contracts_for(coin, notional_usd, mid)
        if n <= 0:
            raise SizeTooSmall(f"{coin}: one {c.display} contract is ${c.units_per_contract * mid:,.2f}, "
                               f"slot is ${notional_usd:,.0f}")
        px = c.units_per_contract * mid                 # Kalshi quotes the CONTRACT price
        limit = math.floor(px * (1.0 - self.cfg.max_slippage) / TICK) * TICK
        if not self._armed:
            logger.info("DRY-RUN kalshi short %s x%d (%s) ~$%.0f", c.ticker, n, coin, n * px)
            return Fill(coin, "short", n * c.units_per_contract, mid, dry_run=True)
        return await self._order(coin, "ask", n, limit, reduce_only=False, side_label="short", mid=mid)

    async def close(self, coin: str, qty: float, mid: float) -> Fill:
        c = self.contract(coin)
        n = max(1, int(round(qty / c.units_per_contract)))
        px = c.units_per_contract * mid
        limit = math.ceil(px * (1.0 + self.cfg.max_slippage) / TICK) * TICK
        if not self._armed:
            logger.info("DRY-RUN kalshi close %s x%d", c.ticker, n)
            return Fill(coin, "close", n * c.units_per_contract, mid, dry_run=True)
        return await self._order(coin, "bid", n, limit, reduce_only=True, side_label="close", mid=mid)

    async def _order(self, coin: str, side: str, n: int, limit: float, *, reduce_only: bool,
                     side_label: str, mid: float) -> Fill:
        c = self.contract(coin)
        body = {"ticker": c.ticker, "client_order_id": str(uuid.uuid4()), "side": side,
                "count": str(n), "price": _fp(limit), "time_in_force": "immediate_or_cancel",
                "self_trade_prevention_type": "taker_at_cross", "reduce_only": reduce_only}
        d = await self._request("POST", "/margin/orders", json=body)
        filled = _as_float(d.get("fill_count"))
        if filled <= 0:
            raise RuntimeError(f"{coin} {side_label}: IOC at {_fp(limit)} did not fill "
                               f"(order {d.get('order_id')})")
        avg_contract_px = _as_float(d.get("average_fill_price"), limit)
        fee = _as_float(d.get("average_fee_paid")) * filled or None
        price = avg_contract_px / c.units_per_contract      # back to the bot's per-unit price
        return Fill(coin, side_label, filled * c.units_per_contract, price,
                    order_id=d.get("order_id"), fee_usd=fee)

    # -- account -----------------------------------------------------------------

    async def enabled(self) -> bool:
        d = await self._request("GET", "/margin/enabled")
        return bool(d.get("enabled", d.get("is_enabled", False)))

    async def positions(self) -> dict[str, float]:
        """coin -> signed units (short negative)."""
        by_ticker = {c.ticker: (coin, c.units_per_contract) for coin, c in CONTRACTS.items()}
        d = await self._request("GET", "/margin/positions")
        out: dict[str, float] = {}
        for p in d.get("positions") or []:
            hit = by_ticker.get(p.get("market_ticker"))
            if not hit:
                continue
            coin, units = hit
            n = _as_float(p.get("position"))
            if n:
                out[coin] = n * units
        return out

    async def balance(self) -> dict:
        """Keys shared with the other venues (total_usd_balance,
        available_margin) plus Kalshi's own per-subaccount figures summed:
        account_equity, available_balance, maintenance_margin,
        initial_margin, position_value."""
        d = await self._request("GET", "/margin/balance")
        subs = d.get("subaccount_balances") or []
        tot = {k: sum(_as_float(s.get(k)) for s in subs)
               for k in ("account_equity", "available_balance", "maintenance_margin",
                         "initial_margin", "position_value", "cash_balance")}
        total = tot["account_equity"] or _as_float(d.get("settled_funds")) or tot["cash_balance"]
        return {"total_usd_balance": total, "available_margin": tot["available_balance"],
                "settled_funds": _as_float(d.get("settled_funds")), **tot}

    async def fills(self, limit: int = 100) -> list[dict]:
        d = await self._request("GET", "/margin/fills", params={"limit": limit})
        return list(d.get("fills") or [])
