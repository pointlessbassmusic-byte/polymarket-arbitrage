"""
Social and flow layer: retail sentiment, attention and trade pre-notification, captured point-in-time.
======================================================================================================

Sources that work without credentials from a server: Reddit RSS feeds (r/wallstreetbets, r/options,
r/pennystocks, crypto threads), StockTwits public streams, alternative.me Fear & Greed, CoinGecko
trending and daily prices, Yahoo daily closes for a watchlist, the House of Representatives financial
disclosure index (periodic transaction reports). X/Twitter is collected only through the official API
when ``X_BEARER_TOKEN`` is set. SEC EDGAR refuses this host; its recipe is kept in the archive index.

Everything is stored as point-in-time observations: ``observed_at`` is the post or filing time,
``available_at`` the capture time. A derived bundle aggregates cashtag mentions and a small lexicon
sentiment per (source, ticker, day). None of this is a signal until a harness says so.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import httpx

from mandel.data.fetch import Throttle, _get, now_iso
from mandel.data.store import Observation, ObservationStore, iso

UA = {"User-Agent": "mandel-substrate research bot (contact: https://github.com/pointlessbassmusic-byte/polymarket-arbitrage/issues)"}
SUBREDDITS = ["wallstreetbets", "options", "pennystocks", "stocks", "CryptoCurrency", "SatoshiStreetBets", "thetagang", "Superstonk", "Bitcoin", "ethtrader"]
WATCHLIST = ["SPY", "QQQ", "TSLA", "NVDA", "GME", "AMC", "AAPL", "PLTR", "MSTR", "COIN"]
CRYPTO_ST = ["BTC.X", "ETH.X", "SOL.X", "DOGE.X"]
YAHOO = ["SPY", "QQQ", "TSLA", "NVDA", "GME", "AMC", "AAPL", "PLTR", "MSTR", "COIN", "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]
ATOM = "{http://www.w3.org/2005/Atom}"

POS = {"moon", "rocket", "calls", "call", "bull", "bullish", "long", "buy", "buying", "breakout", "squeeze", "tendies", "green",
       "ath", "undervalued", "upside", "rally", "pump", "🚀", "🌙", "💎", "📈", "gain", "gains", "printing", "lfg"}
NEG = {"puts", "put", "bear", "bearish", "short", "shorting", "sell", "selling", "dump", "dumping", "crash", "drill", "red",
       "bagholder", "bagholding", "overvalued", "rug", "scam", "🐻", "📉", "guh", "loss", "losses", "bleed", "tank", "tanking"}
_CASHTAG = re.compile(r"\$([A-Za-z]{1,5})(?:\.X)?\b")
_WORD = re.compile(r"[A-Za-z]+|[\U0001F300-\U0001FAFF]")
STOP_TICKERS = {"A", "I", "IT", "US", "ON", "OR", "AT", "BE", "DO", "GO", "SO", "NO", "UP", "ALL", "ANY", "ARE", "FOR", "THE",
                "AND", "YOU", "CEO", "IMO", "DD", "YOLO", "ATH", "FD", "OTM", "ITM", "IV", "PM", "AM", "ETF", "IPO", "EPS", "GDP",
                "FED", "SEC", "USA", "UK", "EU", "AI", "TA", "RSI", "PE", "WSB", "LOL", "WTF", "TLDR", "EDIT", "ELI", "CPI", "FOMC"}


# ------------------------------------------------------------------------- text --

def strip_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_tickers(text: str, known: Optional[set] = None) -> set[str]:
    """Cashtags always count; bare upper-case tokens only when in the known set (watchlist + trending)."""
    out = {m.group(1).upper() for m in _CASHTAG.finditer(text or "")}
    if known:
        for tok in re.findall(r"\b[A-Z]{2,5}\b", text or ""):
            if tok in known and tok not in STOP_TICKERS:
                out.add(tok)
    return {t for t in out if t not in STOP_TICKERS}


def lexicon_sentiment(text: str) -> dict:
    """Tiny finance lexicon: score in [-1, 1] = (pos - neg) / (pos + neg); 0 when neither appears."""
    toks = [t.lower() for t in _WORD.findall(text or "")]
    pos = sum(1 for t in toks if t in POS)
    neg = sum(1 for t in toks if t in NEG)
    score = (pos - neg) / (pos + neg) if (pos + neg) else 0.0
    return {"pos": pos, "neg": neg, "score": score}


# ----------------------------------------------------------------------- reddit --

def parse_reddit_atom(xml_text: str, subreddit: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall(f"{ATOM}entry"):
        author = e.find(f"{ATOM}author/{ATOM}name")
        link = e.find(f"{ATOM}link")
        content = e.find(f"{ATOM}content")
        cat = e.find(f"{ATOM}category")
        out.append({
            "id": (e.findtext(f"{ATOM}id") or "").strip(), "subreddit": subreddit,
            "title": (e.findtext(f"{ATOM}title") or "").strip(), "author": (author.text if author is not None else "").strip(),
            "published": (e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated") or "").strip(),
            "updated": (e.findtext(f"{ATOM}updated") or "").strip(), "link": link.get("href") if link is not None else "",
            "flair": cat.get("label") if cat is not None else "", "text": strip_html(content.text if content is not None else "")[:2000],
        })
    return out


def reddit_feed(subreddit: str, sort: str, client: httpx.Client, throttle: Throttle, limit: int = 100) -> list[dict]:
    throttle.wait()
    try:
        r = client.get(f"https://www.reddit.com/r/{subreddit}/{sort}/.rss", params={"limit": limit}, headers=UA, timeout=30)
        if r.status_code != 200:
            return []
        return parse_reddit_atom(r.text, subreddit)
    except (httpx.HTTPError, ET.ParseError):
        return []


# ------------------------------------------------------------------- stocktwits --

def stocktwits_messages(path: str, client: httpx.Client, throttle: Throttle) -> list[dict]:
    d = _get(client, f"https://api.stocktwits.com/api/2/streams/{path}.json", None, throttle)
    out = []
    for m in (d or {}).get("messages", []) or []:
        ent = m.get("entities") or {}
        out.append({"id": m.get("id"), "created_at": m.get("created_at"), "body": (m.get("body") or "")[:1000],
                    "user": (m.get("user") or {}).get("username"), "followers": (m.get("user") or {}).get("followers"),
                    "symbols": [s.get("symbol") for s in m.get("symbols", []) or []],
                    "sentiment": ((ent.get("sentiment") or {}) or {}).get("basic"), "likes": (m.get("likes") or {}).get("total")})
    return out


# ----------------------------------------------------------------------- crypto --

def fear_greed(client: httpx.Client, throttle: Throttle, limit: int = 60) -> list[dict]:
    d = _get(client, "https://api.alternative.me/fng/", {"limit": limit}, throttle)
    return (d or {}).get("data", []) or []


def coingecko_trending(client: httpx.Client, throttle: Throttle) -> list[dict]:
    d = _get(client, "https://api.coingecko.com/api/v3/search/trending", None, throttle)
    return [c.get("item", {}) for c in (d or {}).get("coins", []) or []]


def coingecko_daily(coin: str, client: httpx.Client, throttle: Throttle, days: int = 90) -> list[list]:
    d = _get(client, f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart", {"vs_currency": "usd", "days": days, "interval": "daily"}, throttle)
    return (d or {}).get("prices", []) or []


# ----------------------------------------------------------------------- prices --

def yahoo_daily(symbol: str, client: httpx.Client, throttle: Throttle, rng: str = "3mo") -> list[dict]:
    d = _get(client, f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", {"range": rng, "interval": "1d"}, throttle)
    try:
        res = d["chart"]["result"][0]
        ts = res["timestamp"]; q = res["indicators"]["quote"][0]
        return [{"t": t, "close": q["close"][i], "volume": q["volume"][i]} for i, t in enumerate(ts) if q["close"][i] is not None]
    except (KeyError, IndexError, TypeError):
        return []


def yahoo_history(symbol: str, client: httpx.Client, throttle: Throttle) -> list[dict]:
    """Full daily history via period1=0..now. (range=max silently downgrades to monthly bars; it is not used.)
    Yahoo sometimes answers with an HTML page; that and any non-daily granularity are treated as empty."""
    throttle.wait()
    try:
        r = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params={"period1": 0, "period2": int(time.time()), "interval": "1d"}, headers=UA, timeout=60)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
            return []
        res = r.json()["chart"]["result"][0]
        if res.get("meta", {}).get("dataGranularity", "1d") != "1d":
            return []
        ts = res["timestamp"]; q = res["indicators"]["quote"][0]
        return [{"t": t, "close": q["close"][i], "volume": q["volume"][i]} for i, t in enumerate(ts) if q["close"][i] is not None]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return []


def collect_history(store: ObservationStore, symbols: Iterable[str] = ("BTC-USD", "ETH-USD", "SPY", "QQQ")) -> dict:
    """One-off deep history: full Fear & Greed series (since 2018) and full daily closes for a few anchors.
    These are the long series the sentiment harnesses need; the daily capture only adds the recent tail."""
    cap = now_iso()
    out: dict = {}
    with httpx.Client() as c:
        fg = fear_greed(c, Throttle(1.5), limit=0)
        obs = [Observation("alternative.me", "fear_greed", "crypto", observed_at=iso(int(x["timestamp"])), available_at=iso(int(x["timestamp"]) + 86400), value={"value": int(x["value"]), "label": x.get("value_classification")}) for x in fg if x.get("timestamp")]
        e = store.write_bundle("crypto-fear-greed-history", obs, recipe="alternative.me /fng/?limit=0 (full history; available_at = day + 24h, the index is published for the day after it closes)",
                               tags=["sentiment", "crypto", "history"], schema="value = {value 0-100, label}")
        out["fear_greed"] = e.rows
        th = Throttle(1.5)
        for sym in symbols:
            rows = yahoo_history(sym, c, th)
            e = store.write_bundle(f"daily-history-{sym}", (Observation("yahoo", "price", sym, observed_at=iso(r["t"]), available_at=iso(r["t"] + 86400), value={"symbol": sym, **r}) for r in rows),
                                   recipe=f"yahoo /v8/finance/chart/{sym}?period1=0&period2=now&interval=1d (available_at = bar time + 24h: a daily close is usable the next day)",
                                   tags=["prices", "daily", "history"], schema="value = {symbol, t, close, volume}")
            out[sym] = e.rows
    out["capture"] = cap
    return out


# ------------------------------------------------------------- congress filings --

def house_ptr_index(year: int, client: httpx.Client, throttle: Throttle) -> list[dict]:
    """Periodic transaction reports (FilingType P) from the House clerk's yearly index."""
    throttle.wait()
    try:
        r = client.get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip", headers=UA, timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        name = [n for n in z.namelist() if n.endswith(".txt")][0]
        lines = z.read(name).decode("utf-8", "ignore").splitlines()
    except Exception:
        return []
    hdr = lines[0].split("\t")
    out = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != len(hdr):
            continue
        row = dict(zip(hdr, parts))
        if row.get("FilingType") != "P":
            continue
        out.append({"doc_id": row.get("DocID"), "last": row.get("Last"), "first": row.get("First"), "state_dst": row.get("StateDst"),
                    "filing_date": row.get("FilingDate"), "year": row.get("Year"),
                    "pdf": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{row.get('DocID')}.pdf"})
    return out


# ---------------------------------------------------------------------- x / twitter --

def x_recent_search(query: str, client: httpx.Client, throttle: Throttle, max_results: int = 100) -> Optional[list[dict]]:
    """Official X API v2 recent search; requires X_BEARER_TOKEN. Returns None when no token is set."""
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        return None
    throttle.wait()
    try:
        r = client.get("https://api.twitter.com/2/tweets/search/recent", params={"query": query, "max_results": max_results,
                       "tweet.fields": "created_at,public_metrics,author_id"}, headers={"Authorization": f"Bearer {token}", **UA}, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get("data", [])
    except httpx.HTTPError:
        return []


# ----------------------------------------------------------------- collection --

def _day(ts_iso: str) -> str:
    return (ts_iso or "")[:10]


def derive(reddit: list[dict], stocktwits: list[dict], known: set[str]) -> list[dict]:
    """Per (source, ticker, day): mentions, mean lexicon score, bullish/bearish tags."""
    agg: dict[tuple, dict] = defaultdict(lambda: {"mentions": 0, "score_sum": 0.0, "bullish": 0, "bearish": 0, "authors": set()})
    for p in reddit:
        text = f"{p.get('title', '')} {p.get('text', '')}"
        sent = lexicon_sentiment(text)
        for t in extract_tickers(text, known):
            a = agg[("reddit", t, _day(p.get("published")))]
            a["mentions"] += 1; a["score_sum"] += sent["score"]; a["authors"].add(p.get("author"))
            a["bullish"] += sent["score"] > 0; a["bearish"] += sent["score"] < 0
    for m in stocktwits:
        sent = lexicon_sentiment(m.get("body", ""))
        syms = set(m.get("symbols") or []) | extract_tickers(m.get("body", ""), known)
        for t in syms:
            a = agg[("stocktwits", t.replace(".X", ""), _day(m.get("created_at")))]
            a["mentions"] += 1; a["score_sum"] += sent["score"]; a["authors"].add(m.get("user"))
            tag = m.get("sentiment")
            a["bullish"] += (tag == "Bullish") or (tag is None and sent["score"] > 0)
            a["bearish"] += (tag == "Bearish") or (tag is None and sent["score"] < 0)
    rows = []
    for (src, t, day), a in agg.items():
        rows.append({"source": src, "ticker": t, "day": day, "mentions": a["mentions"], "unique_authors": len(a["authors"]),
                     "mean_score": a["score_sum"] / a["mentions"] if a["mentions"] else 0.0, "bullish": int(a["bullish"]), "bearish": int(a["bearish"])})
    return sorted(rows, key=lambda r: (-r["mentions"], r["source"], r["ticker"]))


def collect_social(store: ObservationStore, capture_day: Optional[str] = None, subreddits: Iterable[str] = SUBREDDITS,
                   watchlist: Iterable[str] = WATCHLIST, crypto_st: Iterable[str] = CRYPTO_ST, yahoo: Iterable[str] = YAHOO) -> dict:
    t0 = time.time()
    cap = now_iso()
    day = capture_day or cap[:10]
    summary: dict = {"capture": cap, "bundles": {}}
    with httpx.Client() as c:
        th = Throttle(1.0)
        # Reddit
        reddit = []
        for sub in subreddits:
            for sort in ("new", "hot"):
                reddit.extend(reddit_feed(sub, sort, c, th))
        seen = set(); reddit_u = []
        for p in reddit:
            if p["id"] and p["id"] not in seen:
                seen.add(p["id"]); reddit_u.append(p)
        e = store.write_bundle(f"social-reddit-{day}", (Observation("reddit", "post", p["id"], observed_at=p["published"] or cap, available_at=cap, value=p) for p in reddit_u),
                               recipe=f"reddit RSS /r/<sub>/{{new,hot}}/.rss?limit=100 for {list(subreddits)}", tags=["social", "reddit", day], schema="value = {id, subreddit, title, author, published, link, flair, text}")
        summary["bundles"]["reddit"] = e.rows
        # StockTwits
        st = []
        th2 = Throttle(0.8)
        for path in ["trending"] + [f"symbol/{s}" for s in list(watchlist) + list(crypto_st)]:
            st.extend(stocktwits_messages(path, c, th2))
        seen = set(); st_u = []
        for m in st:
            if m["id"] not in seen:
                seen.add(m["id"]); st_u.append(m)
        e = store.write_bundle(f"social-stocktwits-{day}", (Observation("stocktwits", "message", str(m["id"]), observed_at=m["created_at"] or cap, available_at=cap, value=m) for m in st_u),
                               recipe=f"stocktwits /api/2/streams/trending.json and /symbol/<S>.json for {list(watchlist) + list(crypto_st)}", tags=["social", "stocktwits", day], schema="value = {id, created_at, body, user, followers, symbols, sentiment, likes}")
        summary["bundles"]["stocktwits"] = e.rows
        # Crypto sentiment + trending + daily prices
        th3 = Throttle(1.5)
        fg = fear_greed(c, th3)
        trend = coingecko_trending(c, th3)
        crypto_obs = [Observation("alternative.me", "fear_greed", "crypto", observed_at=iso(int(x["timestamp"])), available_at=cap, value=x) for x in fg if x.get("timestamp")]
        crypto_obs += [Observation("coingecko", "trending", str(t.get("id")), observed_at=cap, available_at=cap, value={"id": t.get("id"), "symbol": t.get("symbol"), "rank": t.get("market_cap_rank"), "score": t.get("score")}) for t in trend]
        for coin in ("bitcoin", "ethereum", "solana", "dogecoin"):
            for ts_ms, price in coingecko_daily(coin, c, th3):
                crypto_obs.append(Observation("coingecko", "price", coin, observed_at=iso(ts_ms / 1000), available_at=iso(ts_ms / 1000), value={"coin": coin, "usd": price}))
        e = store.write_bundle(f"social-crypto-{day}", crypto_obs, recipe="alternative.me /fng/?limit=60; coingecko /search/trending; /coins/<coin>/market_chart?days=90&interval=daily",
                               tags=["social", "crypto", day], schema="fear_greed | trending | price rows")
        summary["bundles"]["crypto"] = e.rows
        # Equity/crypto daily closes
        th4 = Throttle(0.7)
        px = []
        for sym in yahoo:
            for row in yahoo_daily(sym, c, th4):
                px.append(Observation("yahoo", "price", sym, observed_at=iso(row["t"]), available_at=iso(row["t"]), value={"symbol": sym, **row}))
        e = store.write_bundle(f"social-prices-{day}", px, recipe=f"yahoo /v8/finance/chart/<sym>?range=3mo&interval=1d for {list(yahoo)}", tags=["prices", "daily", day], schema="value = {symbol, t, close, volume}")
        summary["bundles"]["prices"] = e.rows
        # Congress PTRs
        year = int(day[:4])
        ptr = house_ptr_index(year, c, Throttle(2.0))
        e = store.write_bundle(f"social-house-ptr-{day}", (Observation("house-clerk", "ptr", r["doc_id"], observed_at=r["filing_date"], available_at=cap, value=r) for r in ptr),
                               recipe=f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip, FilingType P rows", tags=["flow", "congress", day], schema="value = {doc_id, last, first, state_dst, filing_date, pdf}")
        summary["bundles"]["house_ptr"] = e.rows
        # X (official API only)
        xs = x_recent_search("($GME OR $TSLA OR $NVDA OR $SPY) -is:retweet lang:en", c, Throttle(1.0))
        if xs is None:
            summary["bundles"]["x"] = "skipped: set X_BEARER_TOKEN (official API) to collect"
        else:
            e = store.write_bundle(f"social-x-{day}", (Observation("x", "tweet", str(t.get("id")), observed_at=t.get("created_at") or cap, available_at=cap, value=t) for t in xs),
                                   recipe="X API v2 /tweets/search/recent (bearer token)", tags=["social", "x", day], schema="value = raw tweet")
            summary["bundles"]["x"] = e.rows
    # Derived
    known = set(watchlist) | {s.replace(".X", "") for s in crypto_st} | {str(t.get("symbol", "")).upper() for t in trend} | {s["symbol"] for m in st_u for s in [] }
    for m in st_u:
        known |= {str(s).replace(".X", "") for s in (m.get("symbols") or [])}
    rows = derive(reddit_u, st_u, known)
    e = store.write_bundle(f"social-derived-{day}", (Observation("derived", "ticker-day", f"{r['source']}:{r['ticker']}:{r['day']}", observed_at=r["day"] + "T00:00:00+00:00", available_at=cap, value=r) for r in rows),
                           recipe="mandel.data.social.derive(reddit, stocktwits) with the lexicon in social.py", tags=["social", "derived", day], schema="value = {source, ticker, day, mentions, unique_authors, mean_score, bullish, bearish}")
    summary["bundles"]["derived"] = e.rows
    summary["top_tickers"] = [f"{r['source']}:{r['ticker']}={r['mentions']}" for r in rows[:12]]
    summary["wall_seconds"] = round(time.time() - t0, 1)
    return summary
