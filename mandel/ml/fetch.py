"""
Bar store for the learning program: multi-asset intraday bars, kept local (mandel/ml_data/, gitignored vendor data).
==================================================================================================================

    python -m mandel.ml.fetch yahoo      # 5m/15m/30m (last 60 days) and 60m (2 years) for the Yahoo universe
    python -m mandel.ml.fetch coinbase   # 5-minute candles from 2026-01-01 for the Coinbase universe
    python -m mandel.ml.fetch context    # daily bars for the Yahoo universe, 10 years (swing horizons, T-578)
    python -m mandel.ml.fetch coinbase-daily   # daily candles from 2017 for the Coinbase universe

Every bar is stamped with its OPEN time (Yahoo and Coinbase both stamp bars by open); the feature builder treats a
bar as known only at open + bar length, so nothing from inside a bar leaks into a decision taken at its start.
Files: mandel/ml_data/bars/<interval>/<symbol>.csv.gz with columns t (UTC epoch seconds, bar open), o, h, l, c, v.
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from mandel.paths import MANDEL_ROOT

STORE = MANDEL_ROOT / "ml_data" / "bars"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}

EQUITY_ETF = ["SPY", "QQQ", "IWM", "DIA", "MDY", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLC",
              "XLRE", "SMH", "ARKK", "EEM", "EFA", "FXI", "EWJ", "EWZ", "VNQ", "TQQQ", "SQQQ", "IBIT", "ETHA"]
BOND_ETF = ["TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "AGG"]
COMMOD_ETF = ["GLD", "SLV", "GDX", "USO", "UNG", "DBA"]
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX", "JPM", "BAC", "XOM", "CVX",
          "UNH", "LLY", "COST", "WMT", "HD", "PLTR", "COIN", "MSTR", "SMCI", "INTC", "MU", "ORCL", "CRM", "ADBE"]
FUTURES = ["ES=F", "NQ=F", "YM=F", "RTY=F", "CL=F", "GC=F", "SI=F", "HG=F", "NG=F", "ZN=F", "ZB=F", "ZF=F", "6E=F", "BTC=F"]
FX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "DX-Y.NYB"]
INDEX = ["^VIX", "^TNX"]
YAHOO = EQUITY_ETF + BOND_ETF + COMMOD_ETF + STOCKS + FUTURES + FX + INDEX
COINBASE = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "LTC", "BCH", "SHIB", "UNI", "AAVE", "NEAR",
            "SUI", "APT", "ARB", "OP", "PEPE", "HBAR", "XLM", "ATOM", "FIL", "ICP", "INJ", "SEI", "TIA", "WIF", "BONK"]
ASSET_CLASS = {**{s: "equity_etf" for s in EQUITY_ETF}, **{s: "bond_etf" for s in BOND_ETF},
               **{s: "commodity_etf" for s in COMMOD_ETF}, **{s: "stock" for s in STOCKS}, **{s: "future" for s in FUTURES},
               **{s: "fx" for s in FX}, **{s: "index" for s in INDEX}, **{f"{c}-USD": "crypto" for c in COINBASE}}
YAHOO_PLAN = {"5m": "60d", "15m": "60d", "30m": "60d", "60m": "730d", "1d": "10y"}


def _safe(sym: str) -> str:
    return sym.replace("^", "IDX_").replace("=", "_").replace("/", "_")


def write(interval: str, sym: str, rows: list) -> Path:
    p = STORE / interval / f"{_safe(sym)}.csv.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    seen = {}
    if p.exists():
        with gzip.open(p, "rt") as f:
            next(f, None)
            for line in f:
                t, *rest = line.strip().split(",")
                seen[int(t)] = rest
    for r in rows:
        seen[int(r[0])] = [repr(float(x)) if x is not None else "" for x in r[1:]]
    buf = io.StringIO()
    buf.write("t,o,h,l,c,v\n")
    for t in sorted(seen):
        buf.write(f"{t}," + ",".join(seen[t]) + "\n")
    with gzip.open(p, "wt") as f:
        f.write(buf.getvalue())
    return p


def yahoo(client: httpx.Client, sym: str, interval: str, rng: str) -> list:
    """Yahoo chart API through curl: Yahoo's edge answers 429 to httpx's TLS fingerprint while curl gets 200
    (2026-10-20). ``client`` is unused, kept for the call signature."""
    import json as _json
    import subprocess
    import urllib.parse
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?"
           + urllib.parse.urlencode({"interval": interval, "range": rng, "includePrePost": "false"}))
    for attempt in range(5):
        p = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", "-w", "\n%{http_code}", url], capture_output=True, text=True,
                           timeout=60)
        body, _, code = p.stdout.rpartition("\n")
        if code == "200":
            break
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"yahoo {sym} {interval}: HTTP {code}")
    res = (_json.loads(body).get("chart") or {}).get("result") or []
    if not res:
        return []
    res = res[0]
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c, v = (q.get(k, [None] * len(ts))[i] for k in ("open", "high", "low", "close", "volume"))
        if None not in (o, h, l, c):
            rows.append((t, o, h, l, c, v or 0.0))
    return rows


def coinbase(client: httpx.Client, product: str, start: int, end: int, gran: int = 300) -> list:
    rows, step = [], gran * 300
    t = start
    while t < end:
        t2 = min(end, t + step)
        for attempt in range(4):
            r = client.get(f"https://api.exchange.coinbase.com/products/{product}/candles",
                           params={"granularity": gran, "start": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                                   "end": datetime.fromtimestamp(t2, timezone.utc).isoformat()}, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + 2 * attempt); continue
            r.raise_for_status(); break
        for c in r.json() or []:                     # [time, low, high, open, close, volume]
            rows.append((c[0], c[3], c[2], c[1], c[4], c[5]))
        t = t2
        time.sleep(0.25)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.ml.fetch")
    ap.add_argument("what", choices=["yahoo", "coinbase", "context", "coinbase-daily"])
    a = ap.parse_args(argv)
    client = httpx.Client()
    if a.what in ("yahoo", "context"):
        plan = {"1d": YAHOO_PLAN["1d"]} if a.what == "context" else {k: v for k, v in YAHOO_PLAN.items() if k != "1d"}
        for interval, rng in plan.items():
            for sym in YAHOO:
                try:
                    rows = yahoo(client, sym, interval, rng)
                    write(interval, sym, rows)
                    print(f"{interval} {sym} {len(rows)}", flush=True)
                except Exception as e:
                    print(f"{interval} {sym} FAILED {type(e).__name__}: {str(e)[:120]}", file=sys.stderr, flush=True)
                time.sleep(1.0)
    else:
        daily = a.what == "coinbase-daily"
        gran, interval = (86400, "1d") if daily else (300, "5m")
        start = int(datetime(2017 if daily else 2026, 1, 1, tzinfo=timezone.utc).timestamp())
        end = int(time.time()) // gran * gran                 # the bar still forming is never requested
        for c in COINBASE:
            try:
                rows = coinbase(client, f"{c}-USD", start, end, gran)
                write(interval, f"{c}-USD", rows)
                print(f"{interval} {c}-USD {len(rows)}", flush=True)
            except Exception as e:
                print(f"{interval} {c}-USD FAILED {type(e).__name__}: {str(e)[:120]}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
