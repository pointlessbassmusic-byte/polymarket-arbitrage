"""
Minimal Alpaca client for the paper sleeves. PAPER BY DEFAULT.
==============================================================

Keys come from the environment (ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY) and are never written anywhere. The live
endpoint is refused unless the caller passes live=True AND the environment carries MANDEL_ALPACA_LIVE=I-UNDERSTAND:
Mandel does not switch itself to real money (MANDEL.md section 6); the user does.

Endpoints used (docs.alpaca.markets): /v2/account, /v2/positions, /v2/calendar, /v2/orders (time_in_force 'cls' must
be submitted by 15:50 ET, 'opg' by 09:28 ET; whole shares), order_class 'mleg' for the XSP spread (European,
cash-settled index options; uncovered short legs are rejected), /v2/options/contracts; market data
/v2/stocks/snapshots and /v2/stocks/bars (IEX feed), /v1beta1/options/snapshots (indicative feed).
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

PAPER = "https://paper-api.alpaca.markets"
LIVE = "https://api.alpaca.markets"
DATA = "https://data.alpaca.markets"


class LiveRefused(RuntimeError):
    pass


class Alpaca:
    def __init__(self, live: bool = False, client: Optional[httpx.Client] = None, key: Optional[str] = None,
                 secret: Optional[str] = None):
        if live and os.environ.get("MANDEL_ALPACA_LIVE") != "I-UNDERSTAND":
            raise LiveRefused("live trading needs live=True and MANDEL_ALPACA_LIVE=I-UNDERSTAND (the user's switch)")
        self.base = LIVE if live else PAPER
        self.live = live
        key = key or os.environ.get("ALPACA_API_KEY_ID")
        secret = secret or os.environ.get("ALPACA_API_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY are not set")
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.c = client or httpx.Client(timeout=20)

    def _req(self, method: str, url: str, **kw) -> Any:
        r = self.c.request(method, url, headers=self.h, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else None

    # trading
    def account(self) -> dict:
        return self._req("GET", f"{self.base}/v2/account")

    def positions(self) -> list[dict]:
        return self._req("GET", f"{self.base}/v2/positions")

    def calendar(self, start: str, end: str) -> list[dict]:
        return self._req("GET", f"{self.base}/v2/calendar", params={"start": start, "end": end})

    def orders(self, status: str = "all", after: Optional[str] = None, limit: int = 200) -> list[dict]:
        p = {"status": status, "limit": limit, "nested": "true"}
        if after:
            p["after"] = after
        return self._req("GET", f"{self.base}/v2/orders", params=p)

    def submit(self, order: dict) -> dict:
        return self._req("POST", f"{self.base}/v2/orders", json=order)

    def option_contracts(self, underlying: str, kind: str, exp_gte: str, exp_lte: str) -> list[dict]:
        out, token = [], None
        while True:
            p = {"underlying_symbols": underlying, "type": kind, "expiration_date_gte": exp_gte,
                 "expiration_date_lte": exp_lte, "limit": 1000}
            if token:
                p["page_token"] = token
            d = self._req("GET", f"{self.base}/v2/options/contracts", params=p)
            out += d.get("option_contracts", [])
            token = d.get("next_page_token")
            if not token:
                return out

    # market data
    def stock_snapshots(self, symbols: list[str]) -> dict:
        return self._req("GET", f"{DATA}/v2/stocks/snapshots", params={"symbols": ",".join(symbols), "feed": "iex"})

    def daily_bars(self, symbols: list[str], start: str) -> dict:
        out: dict[str, list] = {}
        token = None
        while True:
            p = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start, "feed": "iex",
                 "adjustment": "all", "limit": 10000}
            if token:
                p["page_token"] = token
            d = self._req("GET", f"{DATA}/v2/stocks/bars", params=p)
            for s, bars in (d.get("bars") or {}).items():
                out.setdefault(s, []).extend(bars)
            token = d.get("next_page_token")
            if not token:
                return out

    def option_snapshots(self, symbols: list[str]) -> dict:
        out: dict[str, Any] = {}
        for i in range(0, len(symbols), 100):
            d = self._req("GET", f"{DATA}/v1beta1/options/snapshots",
                          params={"symbols": ",".join(symbols[i:i + 100]), "feed": "indicative"})
            out.update(d.get("snapshots") or {})
        return out


def auction_order(symbol: str, qty: int, side: str, when: str, client_id: str, paper: bool = False) -> dict:
    """Market-on-close ('cls') or market-on-open ('opg') order for whole shares.

    Alpaca's paper simulator does not run the auctions: a 'cls' order there is a market order at the close that can
    partially fill or expire (the first paper close, 2026-10-20, expired unfilled). On paper the order is therefore a
    plain 'day' market order sent at the decision time (15:44 ET for the close, pre-open for the open, so it executes
    at the open); the reconcile phase measures what that costs against the official close and open."""
    assert when in ("cls", "opg") and qty > 0 and side in ("buy", "sell")
    return {"symbol": symbol, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day" if paper else when,
            "client_order_id": client_id}


def spread_held(positions: list[dict], short_sym: str) -> bool:
    """True when the account holds the spread's short leg. The runners write a spread to state when its opening 'mleg'
    order is SENT, but a day limit order at the mid can expire unfilled (3 of the first 4 paper opens did, 2026-10-20);
    a spread whose short leg is not in the positions list was never opened, and a close order against it is rejected
    ('position intent mismatch')."""
    for p in positions:
        try:
            if p.get("symbol") == short_sym and abs(float(p.get("qty") or 0)) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def spread_order(short_sym: str, long_sym: str, qty: int, limit: float, opening: bool, client_id: str) -> dict:
    """Put credit spread as one 'mleg' limit order. Opening: sell the short, buy the long (limit = credit, entered as
    a negative net price per Alpaca's convention for credits). Closing: buy back the short, sell the long."""
    legs = ([{"symbol": short_sym, "ratio_qty": "1", "side": "sell", "position_intent": "sell_to_open"},
             {"symbol": long_sym, "ratio_qty": "1", "side": "buy", "position_intent": "buy_to_open"}] if opening else
            [{"symbol": short_sym, "ratio_qty": "1", "side": "buy", "position_intent": "buy_to_close"},
             {"symbol": long_sym, "ratio_qty": "1", "side": "sell", "position_intent": "sell_to_close"}])
    price = -abs(limit) if opening else abs(limit)
    return {"order_class": "mleg", "qty": str(qty), "type": "limit", "limit_price": f"{price:.2f}",
            "time_in_force": "day", "legs": legs, "client_order_id": client_id}
