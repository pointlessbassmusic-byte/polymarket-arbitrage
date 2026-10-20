"""`meme-froth-2026-10`: hype, froth and volume shocks in meme coins.

Daily Hyperliquid perps 2023-2026 (163 coins, 27 meme). At each daily
close, with only that day and earlier:

  vshock  = log(today's dollar volume / median of the prior 30 days)
  run7    = log(close / close 7 days ago)
  day     = log(close / open)

ranked cross-sectionally among coins with 30 days of volume that day.

  froth        vshock top decile AND run7 top decile   -> short, 3d / 7d
  capitulation vshock top decile AND run7 bottom decile -> long, 3d / 7d
  continuation vshock top decile AND day > 0            -> long, 1d
  Fear & Greed <= 20 -> long BTC, >= 80 -> short BTC, 7d / 30d

Entries at the close, exits at the close k days later, one event per
coin per k days, 18 bp a round trip, t clustered by entry date.

    python -m cryptobot.hype_study --scratch <dir> [--fetch]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pickle
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .binary_tails_study import cluster_t
from .crossasset_study import ols

COST_BP = 18.0
MEME = {"DOGE", "kPEPE", "kSHIB", "kBONK", "kFLOKI", "WIF", "FARTCOIN", "POPCAT", "MOODENG", "PNUT", "BRETT", "MEME",
        "TRUMP", "MELANIA", "SPX", "TURBO", "kNEIRO", "GOAT", "PENGU", "BOME", "PEOPLE", "CASHCAT", "GRIFFAIN", "AIXBT",
        "PUMP", "kLUNC", "PURR"}
KALSHI_PERPS = {"DOGE", "kSHIB", "VVV", "WLD", "HYPE", "ZEC", "BTC", "ETH", "SOL", "XRP", "ADA", "AAVE", "BCH", "BNB",
                "LINK", "LTC", "NEAR", "SUI", "UNI"}
FNG_URL = "https://api.alternative.me/fng/"


def load_daily(scratch: Path) -> dict[str, list[tuple]]:
    """coin -> [(day, open, high, low, close, volume_usd)] with volume > 0."""
    d = pickle.load(open(scratch / "hl_all_daily.pkl", "rb"))
    out = {}
    for coin, v in d.items():
        cs = next((x for x in v if isinstance(x, list)), None) if isinstance(v, tuple) else v
        if not cs:
            continue
        rows = []
        for c in cs:
            try:
                if c.volume_usd > 0 and c.open > 0 and c.close > 0:
                    rows.append((dt.datetime.fromtimestamp(c.ts, dt.timezone.utc).date().isoformat(),
                                 float(c.open), float(c.high), float(c.low), float(c.close), float(c.volume_usd)))
            except AttributeError:
                break
        if len(rows) >= 60:
            out[coin] = sorted(rows)
    return out


def features(daily: dict[str, list[tuple]]) -> dict[str, dict[str, dict]]:
    """day -> coin -> {vshock, run7, day, close, i}."""
    by_day: dict[str, dict[str, dict]] = defaultdict(dict)
    for coin, rows in daily.items():
        for i in range(30, len(rows)):
            vols = sorted(r[5] for r in rows[i - 30:i])
            med = vols[15]
            if med <= 0 or i < 7:
                continue
            d, o, h, l, c, v = rows[i]
            by_day[d][coin] = {"vshock": math.log(v / med), "run7": math.log(c / rows[i - 7][4]), "day": math.log(c / o),
                               "range": (h - l) / o * 1e4, "i": i}
    return by_day


def decile_flags(by_day: dict[str, dict[str, dict]], min_coins: int = 20) -> dict[str, dict[str, dict]]:
    for d, cs in by_day.items():
        if len(cs) < min_coins:
            for f in cs.values():
                f["ok"] = False
            continue
        for key in ("vshock", "run7"):
            xs = sorted(f[key] for f in cs.values())
            hi, lo = xs[int(0.9 * len(xs))], xs[int(0.1 * len(xs))]
            for f in cs.values():
                f[key + "_top"] = f[key] >= hi
                f[key + "_bot"] = f[key] <= lo
        for f in cs.values():
            f["ok"] = True
    return by_day


def events(daily, by_day, rule: str, hold: int, coins: Optional[set] = None) -> list[dict]:
    sign = -1 if rule == "froth" else 1
    last: dict[str, int] = {}
    out = []
    for d in sorted(by_day):
        for coin, f in by_day[d].items():
            if not f.get("ok") or (coins is not None and coin not in coins):
                continue
            hit = f["vshock_top"] and (f["run7_top"] if rule == "froth" else f["run7_bot"] if rule == "capitulation" else f["day"] > 0)
            if not hit:
                continue
            i = f["i"]
            if coin in last and i - last[coin] < hold:
                continue
            rows = daily[coin]
            if i + hold >= len(rows):
                continue
            # the exit row must be `hold` calendar days later (no gaps)
            d1 = dt.date.fromisoformat(rows[i + hold][0])
            if (d1 - dt.date.fromisoformat(rows[i][0])).days != hold:
                continue
            gross = sign * math.log(rows[i + hold][4] / rows[i][4]) * 1e4
            out.append({"date": d, "coin": coin, "gross_bp": gross, "net_bp": gross - COST_BP})
            last[coin] = i
    return out


def summarize(ev: list[dict]) -> dict:
    if len(ev) < 10:
        return {"n": len(ev)}
    nets = [e["net_bp"] for e in ev]
    ds = sorted(e["date"] for e in ev)
    mid = ds[len(ds) // 2]
    h1 = [e["net_bp"] for e in ev if e["date"] < mid]
    h2 = [e["net_bp"] for e in ev if e["date"] >= mid]
    return {"n": len(ev), "dates": len(set(ds)), "net_bp": statistics.fmean(nets), "median_bp": statistics.median(nets),
            "t": cluster_t(nets, [e["date"] for e in ev]), "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
            "h1": statistics.fmean(h1) if h1 else None, "h2": statistics.fmean(h2) if h2 else None,
            "kalshi_coins": sorted({e["coin"] for e in ev} & KALSHI_PERPS), "first": ds[0], "last": ds[-1]}


def range_on_shock(daily, by_day, coins: Optional[set] = None) -> dict:
    ys, xs = [], []
    for d, cs in by_day.items():
        for coin, f in cs.items():
            if coins is not None and coin not in coins:
                continue
            rows = daily[coin]
            i = f["i"]
            if i + 1 < len(rows):
                o, h, l = rows[i + 1][1], rows[i + 1][2], rows[i + 1][3]
                ys.append((h - l) / o * 1e4)
                xs.append([f["vshock"], f["range"]])
    if len(ys) < 200:
        return {}
    r = ols(ys, xs, nw_lags=5)
    return {"n": len(ys), "vshock_beta": r["beta"][1], "vshock_t": r["t"][1], "own_range_beta": r["beta"][2], "own_range_t": r["t"][2]}


def bounce_overlap(daily, ev: list[dict]) -> Optional[float]:
    """Share of froth events that the live bounce-short rule would also have
    flagged that day (yesterday's move top tercile, 3-day bottom tercile)."""
    if not ev:
        return None
    hits = 0
    for e in ev:
        rows = daily[e["coin"]]
        idx = {r[0]: k for k, r in enumerate(rows)}
        i = idx[e["date"]]
        if i < 60:
            continue
        one = [math.log(rows[k][4] / rows[k - 1][4]) for k in range(1, i)]
        three = [math.log(rows[k][4] / rows[k - 3][4]) for k in range(3, i)]
        o, t = sorted(one), sorted(three)
        y1 = math.log(rows[i][4] / rows[i - 1][4])
        y3 = math.log(rows[i][4] / rows[i - 3][4])
        if y1 >= o[2 * len(o) // 3] and y3 <= t[len(t) // 3]:
            hits += 1
    return hits / len(ev)


# ------------------------------------------------------------ fear & greed

def fetch_fng(scratch: Path, client=None) -> int:
    import httpx
    c = client or httpx.Client(timeout=30, headers={"User-Agent": "cryptobot-research/0.1"})
    j = c.get(FNG_URL, params={"limit": 0, "format": "json"}).json()
    rows = {dt.datetime.fromtimestamp(int(x["timestamp"]), dt.timezone.utc).date().isoformat(): int(x["value"]) for x in j["data"]}
    (scratch / "hype").mkdir(parents=True, exist_ok=True)
    (scratch / "hype" / "fng.json").write_text(json.dumps(rows, sort_keys=True))
    return len(rows)


def btc_closes(scratch: Path) -> dict[str, float]:
    """BTC daily closes (UTC) from the eleven-year hourly series, topped up
    with the options collector's daily file."""
    out: dict[str, float] = {}
    try:
        from .range_profile import load as load_bars
        data, _ = load_bars("btc_hourly", scratch)
        for b in data.get("BTC", []):
            out[dt.datetime.fromtimestamp(b[0], dt.timezone.utc).date().isoformat()] = float(b[4])   # last hour's close wins
    except (FileNotFoundError, OSError):
        pass
    p = scratch / "state_collect" / "options" / "btc_daily.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out.setdefault(r["date"], float(r["close"]))
    return out


def fng_events(fng: dict[str, int], closes: dict[str, float], side: str, hold: int) -> list[dict]:
    out, last = [], None
    days = sorted(set(fng) & set(closes))
    for d in days:
        v = fng[d]
        if (side == "fear" and v > 20) or (side == "greed" and v < 80):
            continue
        if last and (dt.date.fromisoformat(d) - dt.date.fromisoformat(last)).days < hold:
            continue
        d1 = (dt.date.fromisoformat(d) + dt.timedelta(days=hold)).isoformat()
        if d1 not in closes:
            continue
        sign = 1 if side == "fear" else -1
        gross = sign * math.log(closes[d1] / closes[d]) * 1e4
        out.append({"date": d, "coin": "BTC", "gross_bp": gross, "net_bp": gross - COST_BP})
        last = d
    return out


def run(scratch: Path) -> dict:
    daily = load_daily(scratch)
    by_day = decile_flags(features(daily))
    meme = {c for c in daily if c in MEME}
    res = {"coins": len(daily), "meme_coins": sorted(meme), "trials": {}, "descriptive": {}}
    for rule, holds in (("froth", (3, 7)), ("capitulation", (3, 7)), ("continuation", (1,))):
        for hold in holds:
            for label, cs in (("meme", meme), ("all", None)):
                ev = events(daily, by_day, rule, hold, cs)
                st = summarize(ev)
                if rule == "froth":
                    st["bounce_overlap"] = bounce_overlap(daily, ev)
                res["trials"][f"{rule} {hold}d {label}"] = st
    res["descriptive"]["range_on_shock_all"] = range_on_shock(daily, by_day)
    res["descriptive"]["range_on_shock_meme"] = range_on_shock(daily, by_day, meme)
    fp = scratch / "hype" / "fng.json"
    if fp.exists():
        fng = json.loads(fp.read_text())
        closes = btc_closes(scratch)
        for side in ("fear", "greed"):
            for hold in (7, 30):
                res["trials"][f"fng {side} {hold}d BTC"] = summarize(fng_events(fng, closes, side, hold))
    cands = []
    for k, st in res["trials"].items():
        if st.get("n", 0) >= 10 and st["net_bp"] >= 50 and st["t"] >= 2.5 and (st["h1"] or 0) > 0 and (st["h2"] or 0) > 0 and st.get("kalshi_coins"):
            cands.append(k)
    res["candidates"] = cands
    return res


def render(res: dict) -> str:
    o = [f"meme froth: {res['coins']} Hyperliquid perps with volume, {len(res['meme_coins'])} meme; 18 bp a round trip; t clustered by entry date"]
    o.append(f"  {'trial':26s} {'n':>5s} {'dates':>5s} {'net bp':>7s} {'median':>7s} {'t':>5s} {'hit':>4s}  {'halves':>13s}  Kalshi coins")
    for k, st in res["trials"].items():
        if st.get("n", 0) < 10:
            o.append(f"  {k:26s} {st.get('n', 0):5d}")
            continue
        extra = f"  bounce-short overlap {st['bounce_overlap']:.0%}" if st.get("bounce_overlap") is not None else ""
        o.append(f"  {k:26s} {st['n']:5d} {st['dates']:5d} {st['net_bp']:+7.0f} {st['median_bp']:+7.0f} {st['t']:+5.1f} {st['hit']:4.0%}  "
                 f"{st['h1']:+6.0f}/{st['h2']:+6.0f}  {','.join(st['kalshi_coins'][:6])}{extra}")
    for k, r in res["descriptive"].items():
        if r:
            o.append(f"  {k}: next-day range {r['vshock_beta']:+.0f} bp per log-unit of volume shock (t {r['vshock_t']:+.1f}), "
                     f"{r['own_range_beta']:+.2f} per bp of today's range (t {r['own_range_t']:+.1f}), n {r['n']}")
    o.append(f"verdict: {'candidate: ' + ', '.join(res['candidates']) if res['candidates'] else 'no candidate'}; {len(res['trials'])} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--fetch", action="store_true", help="refresh the Fear & Greed history first")
    a = ap.parse_args(argv)
    if a.fetch:
        print(f"fear & greed: {fetch_fng(a.scratch)} days")
    res = run(a.scratch)
    print(render(res))
    (a.scratch / "hype_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
