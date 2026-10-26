"""
Official daily prints for the paper runner's fills (Yahoo chart, keyless, read-only).
=====================================================================================

The calendar rules and their backtests (T-549, T-332, T-59, T-345) are defined on the official closing and opening
prints. Alpaca's paper venue runs no auctions, so the runner's orders fill at 15:44 ET and a few minutes after the open
(2026-10-23: 09:33 ET). The reconcile phase journals the day's official open and close per filled symbol as
``print.official`` rows and the tracker marks every closed round trip at those prints beside the paper fill, so the
forward test reports the rule's own P&L and the paper venue's slippage separately. Never raises into the reconcile.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

UA = {"User-Agent": "mandel-substrate/0.1 (research; contact via repo)"}
HOSTS = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")


def _parse(body: dict) -> dict[str, dict]:
    res = (body.get("chart") or {}).get("result") or []
    if not res:
        return {}
    r = res[0]
    tz = ZoneInfo((r.get("meta") or {}).get("exchangeTimezoneName") or "America/New_York")
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    out = {}
    for i, t in enumerate(r.get("timestamp") or []):
        try:
            o, c = q["open"][i], q["close"][i]
        except (KeyError, IndexError, TypeError):
            continue
        if o is None or c is None:
            continue
        out[datetime.fromtimestamp(int(t), tz).strftime("%Y-%m-%d")] = {"open": float(o), "close": float(c)}
    return out


def official_prints(symbols: list[str], days: int = 10, client: Optional[httpx.Client] = None) -> dict[str, dict[str, dict]]:
    """{symbol: {YYYY-MM-DD: {open, close}}} for the last ``days`` sessions; a symbol Yahoo refuses is simply absent."""
    own = client is None
    c = client or httpx.Client(timeout=20.0, headers=UA)
    out: dict[str, dict[str, dict]] = {}
    try:
        for sym in symbols:
            for host in HOSTS:
                try:
                    r = c.get(f"{host}/v8/finance/chart/{sym}", params={"range": f"{days}d", "interval": "1d"})
                    if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                        by_day = _parse(r.json())
                        if by_day:
                            out[sym] = by_day
                            break
                except (httpx.HTTPError, ValueError):
                    continue
    finally:
        if own:
            c.close()
    return out
