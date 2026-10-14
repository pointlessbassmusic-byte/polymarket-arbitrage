"""`kalshi-crypto-binaries-all-horizons`: the favourite-longshot bias on
Kalshi's crypto event contracts, by horizon.

Every settled market with volume in every series pulled to scratch
(state_bin/<SERIES>, plus the KXBTCD and KXBTC15M sets) is grouped by
horizon class from its own open-to-close span: 15m, hourly, daily,
weekly, monthly-or-longer. At 50%, 25% and 10% of the market's life
before close, take the last candle at or before that moment (within
one candle interval), require a two-sided quote with a spread of at
most 5 cents, and buy the favourite (mid 0.85-0.97) at the ask with
Kalshi's quadratic fee. Net per dollar, t clustered by event, halves
by close date. Longshots (0.03-0.15) and calibration by decile are
reported descriptively.

    python -m cryptobot.binary_horizons_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .binary_tails_study import cluster_t, fee, load as load_binaries

CLASSES = (("15m", 0, 1200), ("hourly", 1200, 2 * 3600), ("daily", 2 * 3600, 2 * 86400),
           ("weekly", 2 * 86400, 10 * 86400), ("monthly+", 10 * 86400, 10 ** 10))
FRACTIONS = (0.5, 0.25, 0.10)
FAV_LO, FAV_HI = 0.85, 0.97
LONG_LO, LONG_HI = 0.03, 0.15
MAX_SPREAD = 0.05
MIN_EVENTS = 30


def horizon_class(span_s: float) -> str:
    for name, lo, hi in CLASSES:
        if lo <= span_s < hi:
            return name
    return "monthly+"


def quote(bars: list, ts: float, tol: float) -> Optional[tuple[float, float]]:
    best = None
    for b in bars:
        if b[0] <= ts:
            if ts - b[0] <= tol:
                best = b
        else:
            break
    if best is None:
        return None
    bid, ask = best[1], best[2]
    if bid is None or ask is None or bid <= 0 or ask >= 1 or ask < bid or ask - bid > MAX_SPREAD:
        return None
    return bid, ask


def bar_step(bars: list) -> float:
    if len(bars) < 2:
        return 60.0
    gaps = sorted(bars[i][0] - bars[i - 1][0] for i in range(1, len(bars)) if bars[i][0] > bars[i - 1][0])
    return float(gaps[len(gaps) // 2]) if gaps else 60.0


def collect(scratch: Path, since_ts: int = 0) -> tuple[list[dict], dict[str, list]]:
    dirs = [scratch / "state_collect", scratch / "state_binaries_15m"]
    sb = scratch / "state_bin"
    if sb.exists():
        dirs += sorted(p for p in sb.iterdir() if p.is_dir())
    dirs += [scratch] + sorted(p for p in scratch.iterdir() if p.is_dir() and (p / "kalshi_binaries").exists())
    markets, bars, seen = [], {}, set()
    for d in dirs:
        if not (d / "kalshi_binaries" / "markets.jsonl").exists():
            continue
        ms, bs = load_binaries(d)
        for m in ms:
            if m["ticker"] in seen or m.get("result") not in ("yes", "no") or m["close_ts"] < since_ts:
                continue
            seen.add(m["ticker"])
            markets.append(m)
            bars[m["ticker"]] = sorted(bs[m["ticker"]], key=lambda b: b[0])
    return markets, bars


def evaluate(markets: list[dict], bars: dict[str, list]) -> dict:
    trades: dict[tuple, list[dict]] = defaultdict(list)
    longs: dict[tuple, list[dict]] = defaultdict(list)
    calib: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    series_by_class: dict[str, set] = defaultdict(set)
    for m in markets:
        span = m["close_ts"] - m["open_ts"]
        if span <= 0:
            continue
        cls = horizon_class(span)
        series_by_class[cls].add(m["series"])
        b = bars.get(m["ticker"]) or []
        if not b:
            continue
        tol = max(60.0, bar_step(b))
        y = 1.0 if m["result"] == "yes" else 0.0
        for f in FRACTIONS:
            q = quote(b, m["close_ts"] - f * span, tol)
            if q is None:
                continue
            bid, ask = q
            mid = (bid + ask) / 2
            if f == FRACTIONS[0]:
                calib[cls][min(int(mid * 10), 9)].append(y)
            rec = {"event": m["event"], "series": m["series"], "close_ts": m["close_ts"]}
            if FAV_LO <= mid <= FAV_HI:
                win, price = y, ask
            elif FAV_LO <= 1 - mid <= FAV_HI:
                win, price = 1 - y, 1 - bid
            else:
                win = price = None
            if price is not None and price < 1:
                trades[(cls, f)].append(rec | {"net": (win - price - fee(price)) / price, "implied": price, "win": win})
            if LONG_LO <= mid <= LONG_HI:
                lw, lp = y, ask
            elif LONG_LO <= 1 - mid <= LONG_HI:
                lw, lp = 1 - y, 1 - bid
            else:
                lp = None
            if lp is not None and lp > 0:
                longs[(cls, f)].append(rec | {"net": (lw - lp - fee(lp)) / lp})
    out = {"classes": {}}
    for cls, _, _ in CLASSES:
        row = {"series": sorted(series_by_class.get(cls, ())), "markets": sum(1 for m in markets if horizon_class(m["close_ts"] - m["open_ts"]) == cls),
               "fav": {}, "long": {}, "calibration": {k: (round(statistics.fmean(v), 3), len(v)) for k, v in sorted(calib[cls].items())}}
        for f in FRACTIONS:
            row["fav"][f] = summarize(trades.get((cls, f), []))
            row["long"][f] = summarize(longs.get((cls, f), []))
        out["classes"][cls] = row
    cands, killed = [], []
    for cls, row in out["classes"].items():
        fs = [row["fav"][f] for f in FRACTIONS]
        for f, st in zip(FRACTIONS, fs):
            if st.get("events", 0) >= MIN_EVENTS and st["net"] >= 0.01 and st["t"] >= 2.5 and st["h1"] > 0 and st["h2"] > 0:
                cands.append(f"{cls} at {int(f * 100)}% of life")
        if all(st.get("events", 0) >= MIN_EVENTS for st in fs) and all(st["net"] < 0 for st in fs):
            killed.append(cls)
    out["candidates"], out["killed"] = cands, killed
    return out


def summarize(ts: list[dict]) -> dict:
    if len(ts) < 5:
        return {"n": len(ts), "events": len({t["event"] for t in ts})}
    nets = [t["net"] for t in ts]
    med = sorted(t["close_ts"] for t in ts)[len(ts) // 2]
    h1 = [t["net"] for t in ts if t["close_ts"] < med] or [0.0]
    h2 = [t["net"] for t in ts if t["close_ts"] >= med] or [0.0]
    out = {"n": len(ts), "events": len({t["event"] for t in ts}), "net": statistics.fmean(nets),
           "t": cluster_t(nets, [t["event"] for t in ts]), "h1": statistics.fmean(h1), "h2": statistics.fmean(h2)}
    if "win" in ts[0]:
        out["hit"] = statistics.fmean(t["win"] for t in ts)
        out["implied"] = statistics.fmean(t["implied"] for t in ts)
    return out


MAKER_FEE_RATE = 0.0175
MAKER_FRACTION = 0.25


def maker(markets: list[dict], bars: dict[str, list]) -> dict:
    """Resting order for the favourite at 25% of life left, filled only if a
    later candle's last trade goes strictly through the resting price."""
    res: dict[str, dict] = {}
    rows: dict[str, list[dict]] = defaultdict(list)
    tried: dict[str, int] = defaultdict(int)
    for m in markets:
        span = m["close_ts"] - m["open_ts"]
        if span <= 0:
            continue
        cls = horizon_class(span)
        b = bars.get(m["ticker"]) or []
        if not b:
            continue
        t0 = m["close_ts"] - MAKER_FRACTION * span
        q = quote(b, t0, max(60.0, bar_step(b)))
        if q is None:
            continue
        bid, ask = q
        mid = (bid + ask) / 2
        y = 1.0 if m["result"] == "yes" else 0.0
        later = [x for x in b if t0 < x[0] <= m["close_ts"] and x[3] is not None]
        if FAV_LO <= mid <= FAV_HI:              # buy YES at the bid
            price, win = bid, y
            filled = any(x[3] < bid for x in later)
        elif FAV_LO <= 1 - mid <= FAV_HI:        # buy NO at 1 - ask (sell YES at the ask)
            price, win = 1 - ask, 1 - y
            filled = any(x[3] > ask for x in later)
        else:
            continue
        tried[cls] += 1
        if filled and 0 < price < 1:
            rows[cls].append({"event": m["event"], "close_ts": m["close_ts"], "win": win, "implied": price,
                              "net": (win - price) / price,
                              "net_fee": (win - price - MAKER_FEE_RATE * price * (1 - price)) / price})
    for cls, _, _ in CLASSES:
        st = summarize(rows.get(cls, []))
        st["tried"] = tried.get(cls, 0)
        st["fill_rate"] = len(rows.get(cls, [])) / tried[cls] if tried.get(cls) else None
        if rows.get(cls):
            st["net_with_maker_fee"] = statistics.fmean(r["net_fee"] for r in rows[cls])
        res[cls] = st
    return res


def run(scratch: Path, since: str = "") -> dict:
    since_ts = int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()) if since else 0
    markets, bars = collect(scratch, since_ts)
    res = evaluate(markets, bars)
    res["maker"] = maker(markets, bars)
    res["markets"] = len(markets)
    res["series"] = len({m["series"] for m in markets})
    return res


def render(res: dict) -> str:
    o = [f"Kalshi crypto binaries, all horizons: {res['markets']} settled markets in {res['series']} series; favourite 0.85-0.97 at the ask, fee 0.07 p(1-p)"]
    for cls, row in res["classes"].items():
        o.append(f"  {cls}: {row['markets']} markets; series {', '.join(row['series'][:12])}{' ...' if len(row['series']) > 12 else ''}")
        for f in FRACTIONS:
            st, lg = row["fav"][f], row["long"][f]
            if st.get("n", 0) < 5:
                fs = f"favourite n {st.get('n', 0)}"
            else:
                fs = (f"favourite {st['n']:5d} trades / {st['events']:4d} events  net {st['net']:+.2%}  t {st['t']:+.1f}  "
                      f"hit {st['hit']:.1%} vs paid {st['implied']:.1%}  halves {st['h1']:+.2%}/{st['h2']:+.2%}"
                      + (f"  [too few events: under {MIN_EVENTS}, t not meaningful]" if st["events"] < MIN_EVENTS else ""))
            ls = f"longshot {lg['net']:+.0%} (t {lg['t']:+.1f}, n {lg['n']})" if lg.get("n", 0) >= 5 else f"longshot n {lg.get('n', 0)}"
            o.append(f"    at {int(f * 100):2d}% of life left: {fs}; {ls}")
        if row["calibration"]:
            o.append("    calibration at 50% left, mid decile -> realised (n): " + ", ".join(f"{k / 10:.1f}:{v[0]:.2f}({v[1]})" for k, v in row["calibration"].items()))
    if res.get("maker"):
        o.append(f"  MAKER: resting order for the favourite at {int(MAKER_FRACTION * 100)}% of life left, filled only if a later trade goes through it")
        for cls, st in res["maker"].items():
            if st.get("n", 0) < 5:
                o.append(f"    {cls:9s} tried {st.get('tried', 0)}, filled {st.get('n', 0)}")
                continue
            o.append(f"    {cls:9s} tried {st['tried']:5d}, filled {st['n']:5d} ({st['fill_rate']:.0%}) over {st['events']} events: net {st['net']:+.2%} per $ "
                     f"(t {st['t']:+.1f}, halves {st['h1']:+.2%}/{st['h2']:+.2%}), with a maker fee {st['net_with_maker_fee']:+.2%}; hit {st['hit']:.1%} vs paid {st['implied']:.1%}"
                     + ("  [too few events]" if st["events"] < MIN_EVENTS else ""))
    o.append(f"verdict: candidates {res['candidates'] or 'none'}; killed {res['killed'] or 'none'}; {len(CLASSES) * len(FRACTIONS)} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--since", default="", help="only markets closing on or after this date (the forward test)")
    a = ap.parse_args(argv)
    res = run(a.scratch, a.since)
    print(render(res))
    (a.scratch / "binary_horizons_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
