"""`universe-screen-2026-10`: the 400 most-traded US stocks plus the AI
names. Two outputs: a descriptive STANDOUTS report (today's extremes on
realised volatility, short interest, volume shock, 10-day move) and the
pre-registered cross-sectional tests (monthly decile sorts on 60-day
volatility, 20/60-day volume ratio and days-to-cover; top-minus-bottom
spread, 8 bp a side).

    python -m cryptobot.universe_study --scratch <dir> [--standouts-only]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from . import stats as S

COST_BP = 8.0
DECILES = 10
START = "2017-01-01"


def load_universe(scratch: Path) -> tuple[dict, dict[str, list[dict]], dict[str, list[dict]]]:
    u = json.loads((scratch / "universe" / "universe.json").read_text())
    hist, si = {}, {}
    for p in (scratch / "universe" / "hist").glob("*.json"):
        rows = json.loads(p.read_text())
        if len(rows) >= 250:
            hist[p.stem] = rows
    for p in (scratch / "universe" / "si").glob("*.json"):
        rows = json.loads(p.read_text())
        if rows:
            si[p.stem] = sorted(({"date": dt.datetime.strptime(x["settlementDate"], "%m/%d/%Y").date().isoformat(),
                                  "dtc": float(x["daysToCover"]), "interest": float(str(x["interest"]).replace(",", ""))} for x in rows),
                                key=lambda x: x["date"])
    return u, hist, si


# ------------------------------------------------------------- features

def features_at(rows: list[dict], i: int) -> Optional[dict]:
    """Realised vol (60d), volume ratio (20/60), 10-day move, at row i."""
    if i < 70:
        return None
    rets = [math.log(rows[k]["close"] / rows[k - 1]["close"]) for k in range(i - 59, i + 1)]
    vol = statistics.pstdev(rets) * math.sqrt(252)
    v20 = statistics.fmean(r.get("volume") or 0 for r in rows[i - 19:i + 1])
    v60 = statistics.fmean(r.get("volume") or 0 for r in rows[i - 59:i + 1])
    return {"vol": vol, "vol_ratio": v20 / v60 if v60 > 0 else None, "ret_10": rows[i]["close"] / rows[i - 10]["close"] - 1,
            "ret_60": rows[i]["close"] / rows[i - 60]["close"] - 1, "dollar_volume": v20 * rows[i]["close"]}


def standouts(u: dict, hist: dict, si: dict, top: int = 15) -> dict:
    """Today's extremes, descriptive."""
    rows = []
    for sym, h in hist.items():
        f = features_at(h, len(h) - 1)
        if not f:
            continue
        f["symbol"] = sym
        f["sector"] = (u["meta"].get(sym) or {}).get("sector")
        f["dtc"] = si[sym][-1]["dtc"] if sym in si and si[sym] else None
        f["si_change"] = (si[sym][-1]["interest"] / si[sym][-2]["interest"] - 1) if sym in si and len(si[sym]) >= 2 and si[sym][-2]["interest"] else None
        rows.append(f)
    def pick(key, reverse=True):
        xs = [r for r in rows if r.get(key) is not None]
        return [{k: r[k] for k in ("symbol", "sector", "vol", "vol_ratio", "ret_10", "dtc")} for r in sorted(xs, key=lambda r: r[key], reverse=reverse)[:top]]
    return {"asof": max(h[-1]["date"] for h in hist.values()), "n": len(rows),
            "most_volatile": pick("vol"), "least_volatile": pick("vol", reverse=False),
            "volume_shock": pick("vol_ratio"), "biggest_10d_gain": pick("ret_10"), "biggest_10d_loss": pick("ret_10", reverse=False),
            "highest_days_to_cover": pick("dtc"), "short_interest_rising": pick("si_change")}


# ------------------------------------------------------ cross-sectional

def month_ends(hist: dict) -> list[str]:
    days = sorted({r["date"] for h in hist.values() for r in h if r["date"] >= START})
    by: dict[str, str] = {}
    for d in days:
        by[d[:7]] = d
    return [by[m] for m in sorted(by)]


def decile_spreads(hist: dict, si: dict, key: str) -> dict:
    """Monthly top-minus-bottom decile spread on `key` ('vol', 'vol_ratio', 'dtc')."""
    idx = {sym: {r["date"]: i for i, r in enumerate(h)} for sym, h in hist.items()}
    mes = month_ends(hist)
    spread, top_ret, bot_ret, months = [], [], [], []
    for a, b in zip(mes, mes[1:]):
        scored = []
        for sym, h in hist.items():
            i, j = idx[sym].get(a), idx[sym].get(b)
            if i is None or j is None:
                continue
            if key == "dtc":
                prints = [x for x in si.get(sym, []) if x["date"] <= a]
                if not prints or (dt.date.fromisoformat(a) - dt.date.fromisoformat(prints[-1]["date"])).days > 45:
                    continue
                val = prints[-1]["dtc"]
            else:
                f = features_at(h, i)
                val = f.get(key) if f else None
            if val is None:
                continue
            scored.append((val, math.log(h[j]["close"] / h[i]["close"])))
        if len(scored) < 50:
            continue
        scored.sort()
        n = len(scored) // DECILES
        bot = statistics.fmean(r for _, r in scored[:n])
        top_ = statistics.fmean(r for _, r in scored[-n:])
        cost = 2 * COST_BP / 1e4
        spread.append(top_ - bot - 2 * cost)
        top_ret.append(top_ - cost); bot_ret.append(bot - cost); months.append(b[:7])
    return {"months": months, "spread": spread, "top": top_ret, "bottom": bot_ret}


def summarize(xs: list[float], months: list[str]) -> dict:
    if len(xs) < 24:
        return {"n": len(xs)}
    sd = statistics.pstdev(xs)
    half = months[len(months) // 2]
    a = [x for x, m in zip(xs, months) if m < half]; b = [x for x, m in zip(xs, months) if m >= half]
    return {"n": len(xs), "mean_bp": statistics.fmean(xs) * 1e4, "t": statistics.fmean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else 0.0,
            "sharpe": statistics.fmean(xs) / sd * math.sqrt(12) if sd > 0 else 0.0, "psr": S.psr(xs),
            "h1_bp": statistics.fmean(a) * 1e4 if a else None, "h2_bp": statistics.fmean(b) * 1e4 if b else None}


SORTS = (("vol", -1, "high volatility underperforms"), ("dtc", -1, "high days-to-cover underperforms"), ("vol_ratio", +1, "volume shock outperforms"))


def run(scratch: Path, standouts_only: bool = False) -> dict:
    u, hist, si = load_universe(scratch)
    out = {"universe": len(hist), "with_si": len(si), "standouts": standouts(u, hist, si)}
    if standouts_only:
        return out
    out["sorts"], out["trials"], out["candidates"] = {}, 0, []
    for key, sign, label in SORTS:
        d = decile_spreads(hist, si, key)
        sp = summarize(d["spread"], d["months"])
        tp, bt = summarize(d["top"], d["months"]), summarize(d["bottom"], d["months"])
        out["sorts"][key] = {"label": label, "sign": sign, "spread": sp, "top": tp, "bottom": bt}
        out["trials"] += 2
        if sp.get("n") and sign * sp["t"] >= 2.5 and sign * (sp.get("h1_bp") or 0) > 0 and sign * (sp.get("h2_bp") or 0) > 0:
            out["candidates"].append(label)
    out["verdict"] = ("candidate", ", ".join(out["candidates"])) if out["candidates"] else ("inconclusive", "no candidate")
    return out


def render(res: dict) -> str:
    st = res["standouts"]
    o = [f"universe: {res['universe']} names with history, {res['with_si']} with short interest; standouts as of {st['asof']} ({st['n']} scored)"]

    def lst(key, fmt):
        return ", ".join(fmt(r) for r in st[key][:10])
    o.append("  most volatile (60d ann.):     " + lst("most_volatile", lambda r: f"{r['symbol']} {r['vol']*100:.0f}%"))
    o.append("  least volatile:               " + lst("least_volatile", lambda r: f"{r['symbol']} {r['vol']*100:.0f}%"))
    o.append("  volume shock (20d/60d):       " + lst("volume_shock", lambda r: f"{r['symbol']} {r['vol_ratio']:.1f}x"))
    o.append("  biggest 10-day gains:         " + lst("biggest_10d_gain", lambda r: f"{r['symbol']} {r['ret_10']*100:+.0f}%"))
    o.append("  biggest 10-day losses:        " + lst("biggest_10d_loss", lambda r: f"{r['symbol']} {r['ret_10']*100:+.0f}%"))
    o.append("  highest days-to-cover:        " + lst("highest_days_to_cover", lambda r: f"{r['symbol']} {r['dtc']:.1f}d"))
    if "sorts" in res:
        o.append("  monthly decile sorts, 2017-2026, top minus bottom after 8 bp a side:")
        for key, d in res["sorts"].items():
            sp, tp, bt = d["spread"], d["top"], d["bottom"]
            if not sp.get("n"):
                o.append(f"    {key:10s} n {sp.get('n', 0)} months"); continue
            o.append(f"    {key:10s} ({d['label']}): {sp['n']} months, spread {sp['mean_bp']:+.0f} bp/mo (t {sp['t']:+.1f}, Sharpe {sp['sharpe']:+.2f}, halves {sp['h1_bp']:+.0f}/{sp['h2_bp']:+.0f}); "
                     f"top decile {tp['mean_bp']:+.0f} bp/mo, bottom {bt['mean_bp']:+.0f} bp/mo")
        v, why = res["verdict"]
        o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--standouts-only", action="store_true")
    a = ap.parse_args(argv)
    print(render(run(a.scratch, a.standouts_only)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
