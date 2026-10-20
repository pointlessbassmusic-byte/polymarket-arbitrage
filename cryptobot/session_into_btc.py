"""`us-session-into-btc-afterhours`: does the US session in AI, big tech and
the Nasdaq carry into BTC after the close?

Predictors: QQQ, an equal-weight AI basket and NVDA, close to close.
Targets: BTC 16:00-20:00 ET, 16:00-00:00 ET and 16:00 ET to 09:30 ET
next day, from hourly BTC (09:00 ET stands in for 09:30 when the exact
09:30 file is not on hand). Newey-West t, eras, a tercile rule net of
8 bp on the Kalshi BTC perp.

    python -m cryptobot.session_into_btc --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path
from typing import Optional

from .crossasset_study import ols
from .crossref_study import btc_at, load_btc_hourly

AI = ("NVDA", "MSFT", "META", "GOOGL", "AMZN", "AAPL", "PLTR", "AMD", "AVGO", "TSM")
ERAS = (("2017-2020", "2017-01-01", "2020-12-31"), ("2021-2023", "2021-01-01", "2023-12-31"), ("2024-2026", "2024-01-01", "2026-12-31"))
COST_BP = 8.0
START = "2017-01-01"


def closes(scratch: Path, sym: str) -> dict[str, float]:
    p = scratch / "universe" / "hist" / f"{sym}.json"
    if p.exists():
        return {r["date"]: r["close"] for r in json.loads(p.read_text())}
    p = scratch / "state_collect" / "macro" / f"{sym}.json"
    if p.exists():
        return {d: float(c) for d, c in json.loads(p.read_text())}
    return {}


def day_returns(px: dict[str, float]) -> dict[str, float]:
    days = sorted(px)
    return {days[i]: math.log(px[days[i]] / px[days[i - 1]]) for i in range(1, len(days))}


def basket_returns(scratch: Path, syms=AI) -> dict[str, float]:
    rs = [day_returns(closes(scratch, s)) for s in syms]
    rs = [r for r in rs if r]
    days = sorted(set.intersection(*[set(r) for r in rs])) if rs else []
    return {d: statistics.fmean(r[d] for r in rs) for d in days}


def btc_windows(hourly: dict[int, float], day: str, open_px: Optional[dict[str, float]] = None) -> Optional[dict]:
    a = btc_at(hourly, day, 16)
    if not a:
        return None
    b20 = btc_at(hourly, day, 20)
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    b00 = btc_at(hourly, nxt, 0)
    b09 = (open_px or {}).get(nxt) or btc_at(hourly, nxt, 9)
    out = {}
    if b20:
        out["16-20"] = math.log(b20 / a)
    if b00:
        out["16-00"] = math.log(b00 / a)
    if b09:
        out["16-0930"] = math.log(b09 / a)
    return out or None


def nw(pairs, lags=5) -> dict:
    if len(pairs) < 60:
        return {"n": len(pairs)}
    xs = [p for _, p, _ in pairs]
    m, sd = statistics.fmean(xs), statistics.pstdev(xs)
    res = ols([r * 1e4 for _, _, r in pairs], [[(x - m) / sd if sd > 0 else 0.0] for x in xs], nw_lags=lags)
    out = {"n": len(pairs), "beta_bp": res["beta"][1], "t": res["t"][1], "eras": {}}
    for name, a, b in ERAS:
        sub = [p for p in pairs if a <= p[0] <= b]
        if len(sub) >= 60:
            xs2 = [p for _, p, _ in sub]; m2, sd2 = statistics.fmean(xs2), statistics.pstdev(xs2)
            r2 = ols([r * 1e4 for _, _, r in sub], [[(x - m2) / sd2 if sd2 > 0 else 0.0] for x in xs2], nw_lags=lags)
            out["eras"][name] = r2["t"][1]
    return out


def rule(pairs, cost_bp=COST_BP) -> dict:
    if len(pairs) < 60:
        return {"n": 0}
    first = sorted(p for _, p, _ in pairs[: len(pairs) // 2])
    lo, hi = first[len(first) // 3], first[2 * len(first) // 3]
    trades = [(d, (1 if p >= hi else -1) * r * 1e4 - cost_bp) for d, p, r in pairs if p >= hi or p <= lo]
    if len(trades) < 30:
        return {"n": len(trades)}
    nets = [x for _, x in trades]
    half = trades[len(trades) // 2][0]
    a = [x for d, x in trades if d < half]; b = [x for d, x in trades if d >= half]
    sd = statistics.pstdev(nets)
    return {"n": len(nets), "net_bp": statistics.fmean(nets), "t": statistics.fmean(nets) / (sd / math.sqrt(len(nets))) if sd > 0 else 0.0,
            "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets), "h1": statistics.fmean(a) if a else None, "h2": statistics.fmean(b) if b else None,
            "per_year_pct": statistics.fmean(nets) * len(nets) / max(1.0, (dt.date.fromisoformat(trades[-1][0]) - dt.date.fromisoformat(trades[0][0])).days / 365) / 100}


def run(scratch: Path) -> dict:
    hourly = load_btc_hourly(scratch)
    open_file = scratch / "btc_open" / "btc_0930.json"
    open_px = {k: v for k, v in json.load(open(open_file)).items() if v} if open_file.exists() else {}
    preds = {"QQQ": day_returns(closes(scratch, "QQQ")), "AI basket": basket_returns(scratch), "NVDA": day_returns(closes(scratch, "NVDA"))}
    out = {"predictors": {}, "trials": 0, "candidates": [], "exact_0930_days": len(open_px)}
    for name, pr in preds.items():
        out["predictors"][name] = {}
        wins: dict[str, list] = {}
        for d, x in pr.items():
            if d < START:
                continue
            w = btc_windows(hourly, d, open_px)
            if not w:
                continue
            for k, v in w.items():
                wins.setdefault(k, []).append((d, x, v))
        for k, pairs in wins.items():
            pairs.sort()
            st = nw(pairs)
            st["rule"] = rule(pairs)
            out["predictors"][name][k] = st
            out["trials"] += 1
            e = st.get("eras", {})
            r = st["rule"]
            if (st.get("n") and st["t"] >= 2.5 and e.get("2021-2023", 0) >= 1.5 and e.get("2024-2026", 0) >= 1.5
                    and r.get("n") and r["net_bp"] > 0 and (r.get("h1") or 0) > 0 and (r.get("h2") or 0) > 0):
                out["candidates"].append(f"{name} -> BTC {k}")
    rules = [st["rule"] for p in out["predictors"].values() for st in p.values() if st.get("rule", {}).get("n")]
    if out["candidates"]:
        out["verdict"] = ("candidate", ", ".join(out["candidates"]))
    elif rules and all(r["net_bp"] < 0 for r in rules):
        out["verdict"] = ("killed", "every rule net negative")
    else:
        out["verdict"] = ("inconclusive", "no candidate")
    return out


def render(res: dict) -> str:
    o = [f"US session -> BTC after hours, 2017-2026, 8 bp on the Kalshi BTC perp ({res['exact_0930_days']} days with an exact 09:30 BTC print)"]
    for name, d in res["predictors"].items():
        for k, st in d.items():
            if not st.get("n"):
                o.append(f"  {name:10s} {k:8s} n {st.get('n', 0)}"); continue
            e = " ".join(f"{a[:4]}-{a[-2:]}:{t:+.1f}" for a, t in st.get("eras", {}).items())
            r = st["rule"]
            rl = (f"rule {r['net_bp']:+.0f} bp x{r['n']} (t {r['t']:+.1f}, hit {r['hit']*100:.0f}%, halves {r['h1']:+.0f}/{r['h2']:+.0f}, {r['per_year_pct']:+.1f}%/yr)"
                  if r.get("n") else "rule n/a")
            o.append(f"  {name:10s} {k:8s} n {st['n']:5d} beta {st['beta_bp']:+6.1f} bp/sd t {st['t']:+.1f}  eras {e} | {rl}")
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
