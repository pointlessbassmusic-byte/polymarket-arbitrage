"""`kalshi-book-imbalance`: does the order-book imbalance on Kalshi's perps
predict the next minutes' mid beyond the cost of acting on it?

Rows come from cryptobot.book_recorder (one every 15 s per ticker). For
each row the forward log change of the mid over 1, 2 and 5 minutes is
taken from the first later row at or past that horizon. Registered
band and horizon: imbalance within 25 bp, 5 minutes; the 10 and 50 bp
bands and the shorter horizons are sensitivities. Statistics: OLS of
the forward change on the imbalance with Newey-West (20 lags) t, per
ticker and pooled; then the rule, long when the imbalance is in its top
tercile and short in its bottom tercile (terciles from the first half
of the sample), held 1 or 5 minutes, one position per ticker, net of
18 bp taker and separately 4 bp maker, pooled and by half.

    python -m cryptobot.book_study --state state [--min-days 7]
"""
from __future__ import annotations

import argparse
import bisect
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .crossasset_study import ols
from .data.nasdaq import read_jsonl

BANDS = (25, 10, 50)
HORIZONS_MIN = (5, 1, 2)
HOLDS_MIN = (1, 5)
TAKER_BP, MAKER_BP = 18.0, 4.0
NW_LAGS = 20
MIN_ROWS = 2000


def load(state_dir: Path) -> dict[str, list[dict]]:
    root = Path(state_dir) / "books"
    out = {}
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        rows = [r for p in sorted(d.glob("*.jsonl")) for r in read_jsonl(p) if r.get("mid") and r.get("imb_25") is not None]
        rows.sort(key=lambda r: r["ts"])
        if len(rows) >= MIN_ROWS:
            out[d.name] = rows
    return out


def forward_changes(rows: list[dict], minutes: int) -> list[Optional[float]]:
    """Log change of the mid from each row to the first row at or past
    `minutes` later (None when the sample ends or the gap is over 3x)."""
    ts = [r["ts"] for r in rows]
    out: list[Optional[float]] = [None] * len(rows)
    for i, t in enumerate(ts):
        j = bisect.bisect_left(ts, t + 60 * minutes)
        if j < len(ts) and ts[j] - t <= 3 * 60 * minutes:
            out[i] = math.log(rows[j]["mid"] / rows[i]["mid"])
    return out


def regression(rows: list[dict], band: int, minutes: int) -> dict:
    fwd = forward_changes(rows, minutes)
    pairs = [(r[f"imb_{band}"], f) for r, f in zip(rows, fwd) if f is not None]
    if len(pairs) < 100:
        return {"n": len(pairs)}
    res = ols([f * 1e4 for _, f in pairs], [[x] for x, _ in pairs], nw_lags=NW_LAGS)
    return {"n": len(pairs), "beta_bp": res["beta"][1], "t": res["t"][1], "r2": res.get("r2")}


def rule_trades(rows: list[dict], band: int, hold_min: int, cuts: tuple[float, float], cost_bp: float) -> list[dict]:
    fwd = forward_changes(rows, hold_min)
    lo, hi = cuts
    out, busy_until = [], -1.0
    for r, f in zip(rows, fwd):
        if f is None or r["ts"] <= busy_until:
            continue
        x = r[f"imb_{band}"]
        if x >= hi:
            side = 1
        elif x <= lo:
            side = -1
        else:
            continue
        out.append({"ts": r["ts"], "side": side, "net_bp": side * f * 1e4 - cost_bp, "gross_bp": side * f * 1e4})
        busy_until = r["ts"] + 60 * hold_min
    return out


def tercile_cuts(values: list[float]) -> tuple[float, float]:
    vs = sorted(values)
    return vs[len(vs) // 3], vs[2 * len(vs) // 3]


def summarize(trades: list[dict]) -> dict:
    if len(trades) < 30:
        return {"n": len(trades)}
    nets = [t["net_bp"] for t in trades]
    half = trades[len(trades) // 2]["ts"]
    a = [t["net_bp"] for t in trades if t["ts"] < half]
    b = [t["net_bp"] for t in trades if t["ts"] >= half]
    sd = statistics.pstdev(nets)
    return {"n": len(nets), "net_bp": statistics.fmean(nets), "gross_bp": statistics.fmean(t["gross_bp"] for t in trades),
            "t": statistics.fmean(nets) / (sd / math.sqrt(len(nets))) if sd > 0 else 0.0,
            "hit": statistics.fmean(1.0 if t["gross_bp"] > 0 else 0.0 for t in trades),
            "first_half_bp": statistics.fmean(a) if a else None, "second_half_bp": statistics.fmean(b) if b else None}


def run(data: dict[str, list[dict]]) -> dict:
    out = {"tickers": {}, "days": 0, "trials": len(BANDS) * len(HORIZONS_MIN) * len(HOLDS_MIN)}
    pooled_trades: dict[tuple, list[dict]] = defaultdict(list)
    pooled_pairs: dict[tuple, list] = defaultdict(list)
    for tk, rows in data.items():
        days = (rows[-1]["ts"] - rows[0]["ts"]) / 86400
        out["days"] = max(out["days"], days)
        half_rows = rows[: len(rows) // 2]
        t = {"rows": len(rows), "days": days, "regress": {}, "rules": {}}
        for band in BANDS:
            for minutes in HORIZONS_MIN:
                t["regress"][f"imb{band}->{minutes}m"] = regression(rows, band, minutes)
                fwd = forward_changes(rows, minutes)
                pooled_pairs[(band, minutes)].extend((r[f"imb_{band}"], f) for r, f in zip(rows, fwd) if f is not None)
            cuts = tercile_cuts([r[f"imb_{band}"] for r in half_rows])
            for hold in HOLDS_MIN:
                for label, cost in (("taker", TAKER_BP), ("maker", MAKER_BP)):
                    tr = rule_trades(rows, band, hold, cuts, cost)
                    t["rules"][f"imb{band} hold{hold}m {label}"] = summarize(tr)
                    pooled_trades[(band, hold, label)].extend(tr)
        out["tickers"][tk] = t
    out["pooled"] = {}
    for (band, minutes), pairs in pooled_pairs.items():
        if len(pairs) >= 100:
            res = ols([f * 1e4 for _, f in pairs], [[x] for x, _ in pairs], nw_lags=NW_LAGS)
            out["pooled"][f"imb{band}->{minutes}m"] = {"n": len(pairs), "beta_bp": res["beta"][1], "t": res["t"][1]}
    out["pooled_rules"] = {f"imb{b} hold{h}m {l}": summarize(sorted(tr, key=lambda x: x["ts"])) for (b, h, l), tr in pooled_trades.items()}
    out["verdict"] = passes(out)
    return out


def passes(res: dict) -> tuple[str, str]:
    """Written before the first snapshot: alive only if the pooled 25 bp /
    5-minute regression has HAC t >= 3.0 and the taker-cost rule (25 bp,
    5-minute hold) is net positive in both halves on DOGE and SHIB;
    maker-positive with taker-negative is inconclusive; negative at both
    costs is killed; under 30 days, collecting."""
    if res["days"] < 30:
        return "collecting", f"{res['days']:.1f} of 30 days"
    reg = res["pooled"].get("imb25->5m") or {}
    memes = [res["tickers"].get(t, {}).get("rules", {}) for t in ("KXDOGEPERP", "KXKSHIBPERP")]
    taker = [m.get("imb25 hold5m taker") or {} for m in memes]
    maker = [m.get("imb25 hold5m maker") or {} for m in memes]
    if any(not s.get("n") for s in taker):
        return "inconclusive", "no DOGE/SHIB rule trades"
    taker_ok = all(s["net_bp"] > 0 and (s["first_half_bp"] or 0) > 0 and (s["second_half_bp"] or 0) > 0 for s in taker)
    if reg.get("t", 0.0) >= 3.0 and taker_ok:
        return "alive", f"pooled t {reg['t']:+.1f}; DOGE/SHIB taker net {[round(s['net_bp'], 1) for s in taker]} bp"
    if all(s["net_bp"] < 0 for s in taker) and all((s.get("net_bp") or 0) < 0 for s in maker):
        return "killed", "net negative at taker and maker cost on DOGE and SHIB"
    return "inconclusive", f"pooled t {reg.get('t', 0.0):+.1f}; taker net {[round(s['net_bp'], 1) for s in taker]} bp"


def render(res: dict) -> str:
    o = [f"Kalshi order-book imbalance: {len(res['tickers'])} tickers, {res['days']:.1f} days of 15-second rows"]
    for name, r in sorted(res["pooled"].items()):
        o.append(f"  pooled {name:12s}: n {r['n']:7d}, beta {r['beta_bp']:+.2f} bp per unit imbalance, NW t {r['t']:+.1f}")
    for tk, t in res["tickers"].items():
        r = t["regress"].get("imb25->5m") or {}
        o.append(f"  {tk:14s} {t['rows']:6d} rows: imb25->5m beta {r.get('beta_bp', 0):+.2f} bp (t {r.get('t', 0):+.1f}); " +
                 "; ".join(f"{k}: {v['net_bp']:+.1f} bp x{v['n']}" for k, v in t["rules"].items() if v.get("n") and "imb25" in k))
    o.append("  pooled rules:")
    for k, v in sorted(res["pooled_rules"].items()):
        if v.get("n"):
            o.append(f"    {k:22s} n {v['n']:6d}: gross {v['gross_bp']:+.1f} bp, net {v['net_bp']:+.1f} bp (t {v['t']:+.1f}), hit {v['hit']*100:.0f}%, "
                     f"halves {v['first_half_bp']:+.1f} / {v['second_half_bp']:+.1f}")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    a = ap.parse_args(argv)
    data = load(a.state)
    if not data:
        print(f"no ticker has {MIN_ROWS} order-book rows yet")
        return 1
    print(render(run(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
