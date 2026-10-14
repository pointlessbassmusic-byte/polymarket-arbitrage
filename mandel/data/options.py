"""
Options and volatility layer, free and point in time.
=====================================================

Sources (all without keys, verified 2026-10-14):
  * CBOE delayed option chains, ``cdn.cboe.com/api/global/delayed_quotes/options/<SYM>.json`` (indices as ``_SPX``):
    every listed contract with bid/ask, IV, Greeks, open interest, volume, and the underlying's price and IV30.
    Chain history does not exist for free; it starts accumulating the day this collector first runs.
  * CBOE volatility and dispersion index histories (CSV since 1990/2004/2009): VIX, VIX9D, VIX3M, VIX6M, VIX1D, VVIX,
    SKEW, GVZ (gold), OVX (oil), VXN (Nasdaq), RVX (Russell), VXD (Dow), VXTLT (bonds), VXEEM, COR1M (implied
    correlation), DSPX (dispersion), single names VXAPL/VXGOG/VXAZN.
  * FRED series (DTB3 3-month bill, DGS10 ...): the risk-free leg.
  * Deribit public API: DVOL (BTC/ETH implied-vol index) daily history, realised volatility, and the whole option
    book summary with mark IV. Deribit does not onboard US persons; this is data, not a venue.

Raw chains are large (SPY ~13k contracts, SPX ~30k), so the daily raw bundle stays out of git and a small
``options-surface-<day>`` summary (per symbol and expiry: ATM IV, 25-delta put/call IV, skew, open interest,
put/call ratios) is committed. ``available_at`` for a chain is the capture time; for an index close it is the
next day; for FRED it is the observation date plus one day.
"""

from __future__ import annotations

import csv
import io
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

import httpx

from mandel.data.fetch import Throttle, now_iso
from mandel.data.store import Observation, ObservationStore, iso

UA = {"User-Agent": "mandel-substrate research bot (contact: https://github.com/pointlessbassmusic-byte/polymarket-arbitrage/issues)"}
CBOE_INDICES = ["VIX", "VIX9D", "VIX3M", "VIX6M", "VIX1D", "VVIX", "SKEW", "GVZ", "OVX", "VXN", "RVX", "VXD", "VXTLT", "VXEEM", "COR1M", "DSPX", "VXAPL", "VXGOG", "VXAZN"]
FRED_SERIES = ["DTB3", "DGS10", "DGS2", "DFF"]
CHAIN_SYMBOLS = ["SPY", "QQQ", "IWM", "TLT", "GLD", "SLV", "USO", "IBIT", "ETHA", "TSLA", "NVDA", "AAPL", "_SPX", "_VIX"]
DERIBIT_CURRENCIES = ["BTC", "ETH"]
_OCC = re.compile(r"^(?P<root>[A-Z^._]+?)(?P<ymd>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")


def _client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=90, follow_redirects=True)


def _day_from_mdy(s: str) -> str:
    m, d, y = s.split("/")
    return f"{y}-{m}-{d}"


# ------------------------------------------------------------------ cboe indices --

def cboe_index_history(name: str, client: httpx.Client, throttle: Throttle) -> list[dict]:
    """Rows {day, open, high, low, close}; single-column indices (VVIX, SKEW, GVZ, OVX, VXTLT, DSPX) fill close only."""
    throttle.wait()
    r = client.get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv")
    if r.status_code != 200 or not r.text.startswith("DATE"):
        return []
    out = []
    for row in csv.DictReader(io.StringIO(r.text)):
        day = _day_from_mdy(row["DATE"])
        if "CLOSE" in row:
            try:
                out.append({"day": day, "open": float(row["OPEN"]), "high": float(row["HIGH"]), "low": float(row["LOW"]), "close": float(row["CLOSE"])})
            except (ValueError, KeyError):
                continue
        else:
            val = row.get(name) or next((v for k, v in row.items() if k != "DATE"), None)
            try:
                out.append({"day": day, "close": float(val)})
            except (TypeError, ValueError):
                continue
    return out


# ------------------------------------------------------------------------- fred --

def fred_series(series_id: str, client: httpx.Client, throttle: Throttle) -> list[dict]:
    throttle.wait()
    r = client.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
    if r.status_code != 200:
        return []
    out = []
    for row in csv.DictReader(io.StringIO(r.text)):
        day = row.get("observation_date") or row.get("DATE")
        v = row.get(series_id)
        if not day or v in (None, "", "."):
            continue
        try:
            out.append({"day": day, "value": float(v)})
        except ValueError:
            continue
    return out


# ------------------------------------------------------------------ cboe chains --

def parse_occ(symbol: str) -> Optional[dict]:
    m = _OCC.match(symbol.replace(" ", ""))
    if not m:
        return None
    ymd = m.group("ymd")
    return {"root": m.group("root"), "expiry": f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:6]}", "type": "call" if m.group("cp") == "C" else "put",
            "strike": int(m.group("strike")) / 1000.0}


def cboe_chain(symbol: str, client: httpx.Client, throttle: Throttle) -> Optional[dict]:
    """Returns {"meta": {...underlying fields...}, "timestamp": str, "options": [compact rows]} or None."""
    throttle.wait()
    r = client.get(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json")
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        return None
    j = r.json()
    d = j.get("data", {})
    meta = {k: v for k, v in d.items() if k != "options"}
    rows = []
    for o in d.get("options", []):
        p = parse_occ(o.get("option", ""))
        if not p:
            continue
        rows.append({"sym": o["option"], "expiry": p["expiry"], "type": p["type"], "strike": p["strike"],
                     "bid": o.get("bid"), "ask": o.get("ask"), "bid_size": o.get("bid_size"), "ask_size": o.get("ask_size"),
                     "iv": o.get("iv"), "oi": o.get("open_interest"), "vol": o.get("volume"),
                     "delta": o.get("delta"), "gamma": o.get("gamma"), "vega": o.get("vega"), "theta": o.get("theta"), "rho": o.get("rho"),
                     "theo": o.get("theo"), "last": o.get("last_trade_price"), "last_time": o.get("last_trade_time")})
    return {"meta": meta, "timestamp": j.get("timestamp"), "options": rows}


def surface_summary(symbol: str, chain: dict, capture_day: str) -> list[dict]:
    """Per expiry: ATM IV, 25-delta put/call IV, skew, straddle price, OI and volume, put/call ratios."""
    S = chain["meta"].get("current_price") or chain["meta"].get("close")
    if not S:
        return []
    by_exp: dict[str, list[dict]] = defaultdict(list)
    for o in chain["options"]:
        by_exp[o["expiry"]].append(o)
    out = []
    cap = datetime.strptime(capture_day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    for exp, rows in sorted(by_exp.items()):
        try:
            dte = (datetime.strptime(exp, "%Y-%m-%d").replace(tzinfo=timezone.utc) - cap).days
        except ValueError:
            continue
        if dte < 0:
            continue
        calls = [o for o in rows if o["type"] == "call" and (o.get("iv") or 0) > 0]
        puts = [o for o in rows if o["type"] == "put" and (o.get("iv") or 0) > 0]
        if not calls or not puts:
            continue
        atm_c = min(calls, key=lambda o: abs(o["strike"] - S)); atm_p = min(puts, key=lambda o: abs(o["strike"] - S))
        c25 = min(calls, key=lambda o: abs((o.get("delta") or 0) - 0.25)) if any(o.get("delta") for o in calls) else None
        p25 = min(puts, key=lambda o: abs((o.get("delta") or 0) + 0.25)) if any(o.get("delta") for o in puts) else None
        mid = lambda o: ((o.get("bid") or 0) + (o.get("ask") or 0)) / 2 if o.get("bid") is not None and o.get("ask") is not None else None
        oi_c = sum(o.get("oi") or 0 for o in rows if o["type"] == "call"); oi_p = sum(o.get("oi") or 0 for o in rows if o["type"] == "put")
        v_c = sum(o.get("vol") or 0 for o in rows if o["type"] == "call"); v_p = sum(o.get("vol") or 0 for o in rows if o["type"] == "put")
        atm_iv = (atm_c["iv"] + atm_p["iv"]) / 2
        straddle = (mid(atm_c) or 0) + (mid(atm_p) or 0)
        out.append({"symbol": symbol.lstrip("_"), "expiry": exp, "dte": dte, "underlying": S, "atm_strike": atm_c["strike"], "atm_iv": atm_iv,
                    "iv_call25d": c25["iv"] if c25 else None, "iv_put25d": p25["iv"] if p25 else None,
                    "skew25": (p25["iv"] - c25["iv"]) if (c25 and p25) else None,
                    "straddle_mid": straddle, "implied_move_pct": (straddle / S * 100) if S else None,
                    "oi_calls": oi_c, "oi_puts": oi_p, "vol_calls": v_c, "vol_puts": v_p,
                    "pc_oi": (oi_p / oi_c) if oi_c else None, "pc_vol": (v_p / v_c) if v_c else None, "n_contracts": len(rows)})
    return out


# ---------------------------------------------------------------------- deribit --

def deribit_dvol_history(currency: str, client: httpx.Client, throttle: Throttle, start_ms: int = 1_580_000_000_000) -> list[dict]:
    """Daily DVOL candles. The endpoint returns the most recent 1000 points before end_timestamp, so page BACKWARD."""
    out = []
    end_ms = int(time.time() * 1000)
    while end_ms > start_ms:
        throttle.wait()
        r = client.get("https://www.deribit.com/api/v2/public/get_volatility_index_data",
                       params={"currency": currency, "resolution": "86400", "start_timestamp": start_ms, "end_timestamp": end_ms})
        if r.status_code != 200:
            break
        data = (r.json().get("result") or {}).get("data") or []
        if not data:
            break
        out.extend(data)
        first = int(min(d[0] for d in data))
        if first >= end_ms or len(data) < 1000:
            break
        end_ms = first - 1
    seen, rows = set(), []
    for ts, o, h, l, c in sorted(out, key=lambda d: d[0]):
        if ts in seen:
            continue
        seen.add(ts); rows.append({"ts_ms": int(ts), "open": o, "high": h, "low": l, "close": c})
    return rows


def deribit_book(currency: str, client: httpx.Client, throttle: Throttle) -> list[dict]:
    throttle.wait()
    r = client.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency", params={"currency": currency, "kind": "option"})
    if r.status_code != 200:
        return []
    rows = []
    for o in r.json().get("result") or []:
        name = o.get("instrument_name", "")
        parts = name.split("-")
        if len(parts) != 4:
            continue
        rows.append({"instrument": name, "expiry": parts[1], "strike": float(parts[2]), "type": "call" if parts[3] == "C" else "put",
                     "bid": o.get("bid_price"), "ask": o.get("ask_price"), "mark": o.get("mark_price"), "mark_iv": o.get("mark_iv"),
                     "oi": o.get("open_interest"), "volume": o.get("volume"), "underlying": o.get("underlying_price") or o.get("estimated_delivery_price"),
                     "interest_rate": o.get("interest_rate")})
    return rows


# ------------------------------------------------------------------ collection --

def collect_options_history(store: ObservationStore, indices: Iterable[str] = CBOE_INDICES, fred: Iterable[str] = FRED_SERIES,
                            currencies: Iterable[str] = DERIBIT_CURRENCIES) -> dict:
    """One-off deep history: CBOE volatility indices, FRED rates, Deribit DVOL."""
    out: dict = {}
    with _client() as c:
        th = Throttle(0.7)
        for name in indices:
            rows = cboe_index_history(name, c, th)
            e = store.write_bundle(f"cboe-{name}-history", (Observation("cboe", "index", name, observed_at=r["day"] + "T21:15:00+00:00", available_at=r["day"] + "T21:30:00+00:00", value=r) for r in rows),
                                   recipe=f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv", tags=["volatility", "cboe", "history"], schema="value = {day, open?, high?, low?, close}")
            out[name] = e.rows
        for sid in fred:
            rows = fred_series(sid, c, th)
            e = store.write_bundle(f"fred-{sid}", (Observation("fred", "series", sid, observed_at=r["day"] + "T00:00:00+00:00", available_at=r["day"] + "T20:00:00+00:00", value=r) for r in rows),
                                   recipe=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", tags=["rates", "fred", "history"], schema="value = {day, value}")
            out[sid] = e.rows
        th2 = Throttle(1.2)
        for cur in currencies:
            rows = deribit_dvol_history(cur, c, th2)
            e = store.write_bundle(f"deribit-dvol-{cur}-history", (Observation("deribit", "dvol", cur, observed_at=iso(r["ts_ms"] / 1000), available_at=iso(r["ts_ms"] / 1000 + 86400), value=r) for r in rows),
                                   recipe=f"deribit /public/get_volatility_index_data currency={cur} resolution=86400 paginated", tags=["volatility", "crypto", "history"], schema="value = {ts_ms, open, high, low, close}")
            out[f"DVOL-{cur}"] = e.rows
    return out


def collect_options_daily(store: ObservationStore, capture_day: Optional[str] = None, symbols: Iterable[str] = CHAIN_SYMBOLS,
                          currencies: Iterable[str] = DERIBIT_CURRENCIES) -> dict:
    """Daily: raw chains (local disk only) + committed surface summary; Deribit books (local) + committed surface."""
    cap = now_iso()
    day = capture_day or cap[:10]
    out: dict = {"capture": cap, "chains": {}, "surface_rows": 0, "deribit": {}}
    surface: list[Observation] = []
    with _client() as c:
        th = Throttle(1.0)
        for sym in symbols:
            ch = cboe_chain(sym, c, th)
            if not ch:
                out["chains"][sym] = "unavailable"; continue
            e = store.archive.store(f"options-chain-{sym.lstrip('_')}-{day}", "data",
                                    ({"source": "cboe", "kind": "option", "key": o["sym"], "observed_at": ch["timestamp"], "available_at": cap, "value": o} for o in ch["options"]),
                                    recipe=f"https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json (delayed 15 min; raw kept on local disk, not in git)",
                                    tags=["options", "chain", day], schema="value = compact CBOE option row", in_git=False)
            out["chains"][sym] = e.rows
            for row in surface_summary(sym, ch, day):
                surface.append(Observation("cboe", "surface", f"{row['symbol']}:{row['expiry']}", observed_at=ch["timestamp"] or cap, available_at=cap, value=row))
        e = store.write_bundle(f"options-surface-{day}", surface, recipe="mandel.data.options.surface_summary over the day's CBOE chains", tags=["options", "surface", day],
                               schema="value = {symbol, expiry, dte, underlying, atm_iv, iv_call25d, iv_put25d, skew25, straddle_mid, implied_move_pct, oi/vol by side, pc ratios}")
        out["surface_rows"] = e.rows
        th2 = Throttle(1.2)
        for cur in currencies:
            rows = deribit_book(cur, c, th2)
            if not rows:
                out["deribit"][cur] = "unavailable"; continue
            e = store.archive.store(f"deribit-book-{cur}-{day}", "data",
                                    ({"source": "deribit", "kind": "option", "key": r["instrument"], "observed_at": cap, "available_at": cap, "value": r} for r in rows),
                                    recipe=f"deribit /public/get_book_summary_by_currency currency={cur} kind=option (raw kept on local disk)", tags=["options", "crypto", day],
                                    schema="value = {instrument, expiry, strike, type, bid, ask, mark, mark_iv, oi, volume, underlying}", in_git=False)
            out["deribit"][cur] = e.rows
            # committed per-expiry surface for crypto too
            by_exp: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                by_exp[r["expiry"]].append(r)
            dsurf = []
            for exp, rs in by_exp.items():
                S = next((r["underlying"] for r in rs if r.get("underlying")), None)
                ivs = [r for r in rs if (r.get("mark_iv") or 0) > 0 and S]
                if not ivs:
                    continue
                atm = min(ivs, key=lambda r: abs(r["strike"] - S))
                dsurf.append(Observation("deribit", "surface", f"{cur}:{exp}", observed_at=cap, available_at=cap,
                                         value={"currency": cur, "expiry": exp, "underlying": S, "atm_strike": atm["strike"], "atm_mark_iv": atm["mark_iv"],
                                                "oi_total": sum(r.get("oi") or 0 for r in rs), "n_contracts": len(rs)}))
            e = store.write_bundle(f"deribit-surface-{cur}-{day}", dsurf, recipe="per-expiry ATM mark IV from the day's Deribit book", tags=["options", "crypto", "surface", day],
                                   schema="value = {currency, expiry, underlying, atm_strike, atm_mark_iv, oi_total, n_contracts}")
            out["deribit"][f"{cur}-surface"] = e.rows
    return out
