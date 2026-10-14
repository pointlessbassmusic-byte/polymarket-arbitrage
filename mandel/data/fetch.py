"""
Fetchers for the public market APIs, with throttling, retries and lossless storage.
===================================================================================

Everything fetched is stored as an archive bundle of ``Observation`` rows with the
raw payload under ``value`` and both timestamps. Each bundle's recipe is the
function call that produced it, so it can be rebuilt instead of re-found.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Iterable, Optional

import httpx

from mandel.data.store import Observation, ObservationStore, iso

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "mandel-substrate/0.1 (research; contact via repo)"}


class Throttle:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        gap = self.min_interval - (now - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


def _get(client: httpx.Client, url: str, params: Optional[dict], throttle: Throttle, retries: int = 4):
    for attempt in range(retries):
        throttle.wait()
        try:
            r = client.get(url, params=params, headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            time.sleep(1.0 * (attempt + 1))
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ Polymarket --

def polymarket_closed_markets(n: int = 4000, page: int = 100, min_interval: float = 0.3) -> list[dict]:
    """Closed markets ordered by lifetime volume. Raw Gamma rows."""
    out: list[dict] = []
    th = Throttle(min_interval)
    with httpx.Client() as c:
        offset = 0
        while len(out) < n:
            rows = _get(c, f"{GAMMA}/markets", {"closed": "true", "limit": page, "offset": offset, "order": "volumeNum", "ascending": "false"}, th)
            if not rows:
                break
            out.extend(rows)
            offset += page
            if len(rows) < page:
                break
    return out[:n]


def polymarket_active_markets(n: int = 500, page: int = 100, min_interval: float = 0.3) -> list[dict]:
    """Active markets ordered by 24h volume (Gamma serves at most 100 per page)."""
    out: list[dict] = []
    th = Throttle(min_interval)
    with httpx.Client() as c:
        offset = 0
        while len(out) < n:
            rows = _get(c, f"{GAMMA}/markets", {"active": "true", "closed": "false", "limit": page, "offset": offset, "order": "volume24hr", "ascending": "false"}, th)
            if not rows:
                break
            out.extend(rows)
            offset += page
            if len(rows) < page:
                break
    return out[:n]


def polymarket_price_history(token_id: str, client: httpx.Client, throttle: Throttle, fidelity: int = 1440) -> list[dict]:
    d = _get(client, f"{CLOB}/prices-history", {"market": token_id, "interval": "max", "fidelity": fidelity}, throttle)
    return (d or {}).get("history", []) or []


def polymarket_book(token_id: str, client: httpx.Client, throttle: Throttle) -> Optional[dict]:
    return _get(client, f"{CLOB}/book", {"token_id": token_id}, throttle)


def _tokens(m: dict) -> list[str]:
    t = m.get("clobTokenIds")
    if isinstance(t, str):
        try:
            t = json.loads(t)
        except json.JSONDecodeError:
            return []
    return list(t or [])


def fetch_polymarket(store: ObservationStore, n_markets: int = 4000, n_histories: int = 400, n_books: int = 300) -> dict:
    """Resolved markets, daily price histories for the largest, and live books for active markets."""
    t0 = time.time()
    fetched_at = now_iso()
    markets = polymarket_closed_markets(n_markets)
    obs = [Observation("polymarket", "market", str(m.get("id")), observed_at=iso(m.get("closedTime") or m.get("endDate") or fetched_at),
                       available_at=fetched_at, value=m) for m in markets]
    e1 = store.write_bundle("polymarket-closed-markets", obs, recipe=f"mandel.data.fetch.polymarket_closed_markets(n={n_markets}) via {GAMMA}/markets?closed=true&order=volumeNum",
                            tags=["polymarket", "markets", "resolved"], schema="value = raw Gamma market row; observed_at = closedTime")
    resolved = [m for m in markets if str(m.get("umaResolutionStatus", "")).lower() == "resolved" and _tokens(m)]
    hist_obs = []
    calls = 0
    with httpx.Client() as c:
        th = Throttle(0.15)
        for m in resolved[:n_histories]:
            tok = _tokens(m)[0]
            h = polymarket_price_history(tok, c, th); calls += 1
            for pt in h:
                hist_obs.append(Observation("polymarket", "price", tok, observed_at=iso(pt["t"]), available_at=iso(pt["t"]),
                                            value={"market_id": str(m.get("id")), "token": tok, "p": pt["p"], "t": pt["t"]}))
    e2 = store.write_bundle("polymarket-price-history-daily", hist_obs, recipe=f"CLOB /prices-history?interval=max&fidelity=1440 for the YES token of the {n_histories} largest resolved markets",
                            tags=["polymarket", "prices", "daily"], schema="value = {market_id, token, p, t}; one row per day")
    active = polymarket_active_markets(n_books)
    book_obs = []
    with httpx.Client() as c:
        th = Throttle(0.12)
        for m in active:
            toks = _tokens(m)
            if len(toks) != 2:
                continue
            books = {}
            for side, tok in zip(("yes", "no"), toks):
                b = polymarket_book(tok, c, th); calls += 1
                if b:
                    books[side] = {"bids": b.get("bids", []), "asks": b.get("asks", []), "timestamp": b.get("timestamp")}
            if len(books) == 2:
                ts = now_iso()
                book_obs.append(Observation("polymarket", "book", str(m.get("id")), observed_at=ts, available_at=ts,
                                            value={"question": m.get("question"), "tokens": toks, "books": books,
                                                   "volume24hr": m.get("volume24hr"), "negRisk": m.get("negRisk")}))
    e3 = store.write_bundle("polymarket-books-snapshot", book_obs, recipe=f"CLOB /book for both tokens of the {n_books} most active markets (one snapshot)",
                            tags=["polymarket", "books", "snapshot"], schema="value = {question, tokens, books{yes,no}{bids,asks}}")
    return {"markets": e1.rows, "resolved": len(resolved), "history_rows": e2.rows, "books": e3.rows, "api_calls": calls + 10,
            "wall_seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------- Kalshi --

def kalshi_settled_markets(n: int = 3000, min_interval: float = 0.6) -> list[dict]:
    out: list[dict] = []
    th = Throttle(min_interval)
    with httpx.Client() as c:
        cursor = None
        while len(out) < n:
            params = {"status": "settled", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            d = _get(c, f"{KALSHI}/markets", params, th)
            if not d:
                break
            out.extend(d.get("markets", []))
            cursor = d.get("cursor")
            if not cursor:
                break
    return out[:n]


def kalshi_candles(series: str, ticker: str, start_ts: int, end_ts: int, client: httpx.Client, throttle: Throttle, period: int = 60) -> list[dict]:
    d = _get(client, f"{KALSHI}/series/{series}/markets/{ticker}/candlesticks", {"start_ts": start_ts, "end_ts": end_ts, "period_interval": period}, throttle)
    return (d or {}).get("candlesticks", []) or []


def fetch_kalshi(store: ObservationStore, n_markets: int = 3000, n_candles: int = 120) -> dict:
    t0 = time.time()
    fetched_at = now_iso()
    markets = kalshi_settled_markets(n_markets)
    obs = [Observation("kalshi", "market", m.get("ticker", ""), observed_at=iso(m.get("settlement_ts") or m.get("close_time") or fetched_at),
                       available_at=fetched_at, value=m) for m in markets]
    e1 = store.write_bundle("kalshi-settled-markets", obs, recipe=f"mandel.data.fetch.kalshi_settled_markets(n={n_markets}) via {KALSHI}/markets?status=settled",
                            tags=["kalshi", "markets", "settled"], schema="value = raw Kalshi market row; observed_at = settlement_ts")
    def vol(m):
        try:
            return float(m.get("volume_fp") or m.get("volume") or 0)
        except (TypeError, ValueError):
            return 0.0
    traded = sorted([m for m in markets if vol(m) > 0 and m.get("open_time") and m.get("close_time")], key=vol, reverse=True)
    cand_obs = []
    calls = 0
    with httpx.Client() as c:
        th = Throttle(1.1)
        for m in traded[:n_candles]:
            series = m["event_ticker"].split("-")[0]
            try:
                start = int(datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp())
                end = int(datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp())
            except Exception:
                continue
            period = 60 if end - start < 86400 * 14 else 1440
            cs = kalshi_candles(series, m["ticker"], start, end, c, th, period); calls += 1
            for k in cs:
                ts = k.get("end_period_ts")
                cand_obs.append(Observation("kalshi", "candle", m["ticker"], observed_at=iso(ts), available_at=iso(ts),
                                            value={"ticker": m["ticker"], "period": period, "candle": k}))
    e2 = store.write_bundle("kalshi-candles", cand_obs, recipe=f"/series/{{series}}/markets/{{ticker}}/candlesticks for the {n_candles} most traded settled markets",
                            tags=["kalshi", "candles"], schema="value = {ticker, period, candle(raw)}")
    return {"markets": e1.rows, "traded": len(traded), "candle_rows": e2.rows, "api_calls": calls + 3, "wall_seconds": round(time.time() - t0, 1)}
