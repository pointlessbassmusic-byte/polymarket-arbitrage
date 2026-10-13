"""`crypto-proxy-crossref-2026-10`: BTC against its listed proxies, meme
squeezes, and short interest, as tradable leads.

  pairs     residual of a proxy stock against beta x BTC (beta from the
            trailing 250 days), 60-day z-score, reversion over 5 and 20
            days; the trade is stock against the Kalshi BTC perp, 16 bp
  afterhours BTC's move 16:00-20:00 ET (after the stock close) and
            16:00-09:00 ET (overnight) against the next session's gap,
            open-to-close drift and the following close-to-close, 8 bp
  squeeze   +30% in 10 days on 3x volume -> the next 10 days, short
  shortint  bi-monthly change in days-to-cover -> the next two weeks

    python -m cryptobot.crossref_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pickle
import statistics
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from .crossasset_study import ols
from .data.nasdaq import HEADERS, read_jsonl

ET = ZoneInfo("America/New_York")
PROXIES = ("MSTR", "COIN", "MARA", "RIOT", "CLSK")
MEMES = ("GME", "AMC", "HOOD", "TSLA", "MSTR", "MARA", "RIOT", "COIN", "CLSK")
SI_NAMES = ("MSTR", "MARA", "COIN", "TSLA", "RIOT")
NW = 10
PAIRS_COST_BP, STOCK_COST_BP, BORROW_BP = 16.0, 8.0, 100.0
START = "2017-01-01"


# ------------------------------------------------------------------- data

def load_stocks(scratch: Path) -> dict[str, list[dict]]:
    out = {}
    for p in sorted((scratch / "state_collect" / "stocks").glob("*.json")):
        rows = json.loads(p.read_text())
        if len(rows) > 300:
            out[p.stem] = rows
    return out


def load_btc_daily(scratch: Path) -> dict[str, float]:
    return {r["date"]: float(r["close"]) for r in read_jsonl(scratch / "state_collect" / "options" / "btc_daily.jsonl")}


def load_btc_hourly(scratch: Path) -> dict[int, float]:
    new = pickle.load(open(scratch / "btc_hourly.pkl", "rb"))
    return {int(r[0]): float(r[4]) for r in new}


def btc_at(hourly: dict[int, float], day: str, hour_et: int) -> Optional[float]:
    t = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hour_et, 0), ET).astimezone(dt.timezone.utc)
    ts = int(t.timestamp())
    return hourly.get(ts) or hourly.get(ts - 3600)


def fetch_short_interest(symbols=SI_NAMES) -> dict[str, list[dict]]:
    out = {}
    for sym in symbols:
        try:
            r = httpx.get(f"https://api.nasdaq.com/api/quote/{sym}/short-interest", params={"assetClass": "stocks"}, headers=HEADERS, timeout=60)
            rows = (((r.json().get("data") or {}).get("shortInterestTable") or {}).get("rows")) or []
        except Exception:                             # noqa: BLE001
            rows = []
        out[sym] = sorted(({"date": dt.datetime.strptime(x["settlementDate"], "%m/%d/%Y").date().isoformat(),
                            "dtc": float(x["daysToCover"]), "interest": float(str(x["interest"]).replace(",", ""))} for x in rows),
                          key=lambda x: x["date"])
    return out


# ---------------------------------------------------------------- helpers

def nw(pairs: list[tuple[str, float, float]]) -> dict:
    if len(pairs) < 60:
        return {"n": len(pairs)}
    xs = [p for _, p, _ in pairs]
    m, sd = statistics.fmean(xs), statistics.pstdev(xs)
    z = [(x - m) / sd if sd > 0 else 0.0 for x in xs]
    res = ols([r * 1e4 for _, _, r in pairs], [[v] for v in z], nw_lags=NW)
    half = pairs[len(pairs) // 2][0]
    out = {"n": len(pairs), "beta_bp": res["beta"][1], "t": res["t"][1], "halves": []}
    for sub in ([p for p in pairs if p[0] < half], [p for p in pairs if p[0] >= half]):
        if len(sub) >= 60:
            xs2 = [p for _, p, _ in sub]
            m2, sd2 = statistics.fmean(xs2), statistics.pstdev(xs2)
            r2 = ols([r * 1e4 for _, _, r in sub], [[(x - m2) / sd2 if sd2 > 0 else 0.0] for x in xs2], nw_lags=NW)
            out["halves"].append(r2["t"][1])
    return out


def tercile_rule(pairs: list[tuple[str, float, float]], sign: int, hold: int, cost_bp: float) -> dict:
    if len(pairs) < 60:
        return {"n": 0}
    first = sorted(p for _, p, _ in pairs[: len(pairs) // 2])
    lo, hi = first[len(first) // 3], first[2 * len(first) // 3]
    trades, busy = [], -1
    for i, (d, p, r) in enumerate(pairs):
        if i < busy:
            continue
        side = sign if p >= hi else -sign if p <= lo else 0
        if not side:
            continue
        trades.append((d, side * r * 1e4 - cost_bp))
        busy = i + hold
    return _summ(trades)


def threshold_rule(events: list[tuple[str, float]], cost_bp: float) -> dict:
    return _summ([(d, r * 1e4 - cost_bp) for d, r in events])


def _summ(trades: list[tuple[str, float]]) -> dict:
    if len(trades) < 20:
        return {"n": len(trades)}
    nets = [x for _, x in trades]
    half = trades[len(trades) // 2][0]
    a = [x for d, x in trades if d < half]
    b = [x for d, x in trades if d >= half]
    sd = statistics.pstdev(nets)
    return {"n": len(nets), "net_bp": statistics.fmean(nets), "t": statistics.fmean(nets) / (sd / math.sqrt(len(nets))) if sd > 0 else 0.0,
            "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
            "h1": statistics.fmean(a) if a else None, "h2": statistics.fmean(b) if b else None}


# -------------------------------------------------------------- relations

def pairs_relation(stock: list[dict], btc: dict[str, float], horizons=(5, 20)) -> dict:
    """Residual z against beta x BTC -> forward residual return."""
    days = [r["date"] for r in stock if r["date"] in btc and r["date"] >= "2016-01-01"]
    s = {r["date"]: math.log(r["close"]) for r in stock}
    b = {d: math.log(btc[d]) for d in days}
    rs = [s[days[i]] - s[days[i - 1]] for i in range(1, len(days))]
    rb = [b[days[i]] - b[days[i - 1]] for i in range(1, len(days))]
    out = {}
    pairs_by_h: dict[int, list] = {h: [] for h in horizons}
    for i in range(250 + 60, len(days) - max(horizons)):
        xs, ys = rb[i - 250:i], rs[i - 250:i]
        vx = statistics.pvariance(xs)
        beta = (statistics.covariance(xs, ys) if vx > 0 else 0.0) / vx if vx > 0 else 0.0
        spread = [s[days[k]] - beta * b[days[k]] for k in range(i - 60, i + 1)]
        sd = statistics.pstdev(spread)
        z = (spread[-1] - statistics.fmean(spread)) / sd if sd > 0 else 0.0
        if days[i] < START:
            continue
        for h in horizons:
            fwd = (s[days[i + h]] - s[days[i]]) - beta * (b[days[i + h]] - b[days[i]])
            pairs_by_h[h].append((days[i], z, fwd))
    for h, pr in pairs_by_h.items():
        st = nw(pr)
        st["rule"] = tercile_rule(pr, -1, h, PAIRS_COST_BP)           # high z -> short the stock leg
        out[h] = st
    return out


def load_btc_open(scratch: Path) -> dict[str, float]:
    """BTC at exactly 09:30 ET by session date (scratch btc_open/btc_0930.json), if pulled."""
    p = scratch / "btc_open" / "btc_0930.json"
    if not p.exists():
        return {}
    return {k: float(v) for k, v in json.loads(p.read_text()).items() if v}


def afterhours_relation(stock: list[dict], hourly: dict[int, float], btc_open: Optional[dict[str, float]] = None) -> dict:
    """BTC 16:00-20:00 ET, 16:00-09:00 ET and (with the minute series) 16:00-09:30 ET moves -> the next session."""
    rows = [r for r in stock if r["date"] >= START]
    out = {}
    windows = [("afterclose", 20, False), ("overnight", 9, True)]
    if btc_open:
        windows.append(("to_0930", 930, True))
    for pname, h_end, next_day in windows:
        pairs = {"gap": [], "drift": [], "swing": []}
        for i in range(1, len(rows) - 2):
            d0, d1, d2 = rows[i - 1], rows[i], rows[i + 1]
            a = btc_at(hourly, d0["date"], 16)
            b = btc_open.get(d1["date"]) if h_end == 930 else btc_at(hourly, d1["date"] if next_day else d0["date"], h_end)
            if not a or not b:
                continue
            x = math.log(b / a)
            pairs["gap"].append((d1["date"], x, math.log(d1["open"] / d0["close"])))
            pairs["drift"].append((d1["date"], x, math.log(d1["close"] / d1["open"])))
            pairs["swing"].append((d1["date"], x, math.log(d2["close"] / d1["close"])))
        out[pname] = {}
        for tname, pr in pairs.items():
            st = nw(pr)
            st["rule"] = tercile_rule(pr, +1, 1, STOCK_COST_BP)
            out[pname][tname] = st
    return out


def squeeze_events(stocks: dict[str, list[dict]]) -> list[tuple[str, str, float]]:
    """(symbol, date, next-10-day log return) after +30% in 10 days on 3x volume."""
    ev = []
    for sym, rows in stocks.items():
        if sym not in MEMES:
            continue
        rows = [r for r in rows if r.get("volume")]
        busy = -1
        for i in range(70, len(rows) - 10):
            if i < busy or rows[i]["date"] < START:
                continue
            r10 = rows[i]["close"] / rows[i - 10]["close"] - 1
            v10 = statistics.fmean(r["volume"] for r in rows[i - 9:i + 1])
            v60 = statistics.fmean(r["volume"] for r in rows[i - 69:i - 9])
            if r10 >= 0.30 and v60 > 0 and v10 >= 3 * v60:
                ev.append((sym, rows[i]["date"], math.log(rows[i + 10]["close"] / rows[i]["close"])))
                busy = i + 10
    return sorted(ev, key=lambda e: e[1])


def short_interest_relation(si: dict[str, list[dict]], stocks: dict[str, list[dict]]) -> dict:
    pairs = []
    for sym, rows in si.items():
        px = {r["date"]: r["close"] for r in stocks.get(sym, [])}
        days = sorted(px)
        for a, b in zip(rows, rows[1:]):
            d_change = b["dtc"] - a["dtc"]
            # return over the two weeks after the settlement date is published (about 9 days later)
            i = next((k for k, d in enumerate(days) if d > b["date"]), None)
            if i is None or i + 7 + 10 >= len(days):
                continue
            pairs.append((b["date"], d_change, math.log(px[days[i + 17]] / px[days[i + 7]])))
    pairs.sort()
    st = nw(pairs)
    st["rule"] = tercile_rule(pairs, -1, 1, STOCK_COST_BP) if len(pairs) >= 60 else {"n": len(pairs)}
    return st


# --------------------------------------------------------------------- run

def candidate(st: dict, sign: int) -> bool:
    if not st.get("n") or len(st.get("halves", [])) < 2:
        return False
    r = st.get("rule") or {}
    return (sign * st["t"] >= 2.5 and all(sign * h >= 1.5 for h in st["halves"])
            and bool(r.get("n")) and r["net_bp"] > 0 and (r.get("h1") or 0) > 0 and (r.get("h2") or 0) > 0)


def run(scratch: Path, si: Optional[dict] = None) -> dict:
    stocks = load_stocks(scratch)
    btc_d, btc_h = load_btc_daily(scratch), load_btc_hourly(scratch)
    btc_o = load_btc_open(scratch)
    out = {"pairs": {}, "afterhours": {}, "squeeze": {}, "shortint": {}, "candidates": [], "trials": 0}
    for sym in PROXIES:
        if sym in stocks:
            out["pairs"][sym] = pairs_relation(stocks[sym], btc_d)
            out["trials"] += len(out["pairs"][sym])
            for h, st in out["pairs"][sym].items():
                if candidate(st, -1):
                    out["candidates"].append(f"pairs {sym} {h}d")
            out["afterhours"][sym] = afterhours_relation(stocks[sym], btc_h, btc_o)
            for pname, d in out["afterhours"][sym].items():
                for tname, st in d.items():
                    out["trials"] += 1
                    if tname != "gap" and candidate(st, +1):
                        out["candidates"].append(f"afterhours {sym} {pname}->{tname}")
    ev = squeeze_events(stocks)
    out["squeeze"] = {"events": len(ev), "mean_next10_bp": statistics.fmean(r for _, _, r in ev) * 1e4 if ev else None,
                      "short_8bp": threshold_rule([(d, -r) for _, d, r in ev], STOCK_COST_BP),
                      "short_8bp_plus_borrow": threshold_rule([(d, -r) for _, d, r in ev], STOCK_COST_BP + BORROW_BP)}
    out["trials"] += 2
    sq = out["squeeze"]["short_8bp"]
    if sq.get("n") and sq["net_bp"] > 0 and (sq.get("h1") or 0) > 0 and (sq.get("h2") or 0) > 0 and sq["t"] >= 2.5:
        out["candidates"].append("squeeze reversal")
    si = si if si is not None else fetch_short_interest()
    out["shortint"] = short_interest_relation(si, stocks)
    out["trials"] += 1
    out["verdict"] = ("candidate", ", ".join(out["candidates"])) if out["candidates"] else ("inconclusive", "no candidate")
    return out


def render(res: dict) -> str:
    def st_line(st):
        if not st.get("n"):
            return f"n {st.get('n', 0)}"
        r = st.get("rule") or {}
        hv = "/".join(f"{h:+.1f}" for h in st.get("halves", []))
        rl = f"rule {r['net_bp']:+.0f} bp x{r['n']} (t {r['t']:+.1f}, halves {r['h1']:+.0f}/{r['h2']:+.0f})" if r.get("n") else "rule n/a"
        return f"n {st['n']:5d} beta {st['beta_bp']:+6.1f} bp/sd t {st['t']:+.1f} halves {hv} | {rl}"
    o = ["BTC proxies, memes and short interest as leads, 2017-2026"]
    o.append("  pairs: residual z vs beta x BTC -> forward residual (short the stock leg when z is high), 16 bp:")
    for sym, d in res["pairs"].items():
        for h, st in d.items():
            o.append(f"    {sym:5s} {h:2d}d: {st_line(st)}")
    o.append("  after-hours BTC -> next session (long the stock when BTC rose), 8 bp:")
    for sym, d in res["afterhours"].items():
        for pname, dd in d.items():
            for tname, st in dd.items():
                o.append(f"    {sym:5s} {pname:10s} {tname:5s}: {st_line(st)}")
    sq = res["squeeze"]
    o.append(f"  squeeze (+30%/10d on 3x volume): {sq['events']} events, mean next 10 days {sq['mean_next10_bp'] or 0:+.0f} bp; "
             + "; ".join(f"{k}: {v['net_bp']:+.0f} bp x{v['n']} (t {v['t']:+.1f}, halves {v['h1']:+.0f}/{v['h2']:+.0f})" if v.get("n") else f"{k}: n {v.get('n', 0)}"
                         for k, v in (("short 8bp", sq["short_8bp"]), ("short +borrow", sq["short_8bp_plus_borrow"]))))
    o.append(f"  short interest (days-to-cover change -> next two weeks, 5 names): {st_line(res['shortint'])}")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    print(render(run(a.scratch)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
