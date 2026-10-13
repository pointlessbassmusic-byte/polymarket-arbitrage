"""Swings, ranges and seasonality of crypto at every horizon, with the
regressions that say whether any of it is a signal.

For each coin and horizon (5 minutes to 37 days, built from the finest
bars on hand): the distribution of the absolute move and of the
high-low range, annualised volatility, and the share of bars whose
move or range exceeds the venue's round trip (18 bp). Seasonality: mean
range, volume share and signed return by UTC hour and by weekday, with
Newey-West t on the signed return. Volume: the next bar's range and
return regressed on the volume ratio. Macro: daily BTC return and
range regressed on VIX (level and change), 10-year yield change, the
dollar, WTI, SPY and QQQ, same day (comovement) and prior day (lead).

    python -m cryptobot.range_profile --source kalshi_hourly --scratch <dir>
    python -m cryptobot.range_profile --source coinbase5m --scratch <dir>
    python -m cryptobot.range_profile --source hl_daily --scratch <dir>
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

from .crossasset_study import ols
from .data.nasdaq import read_jsonl

COST_BP = 18.0
HORIZONS = (("5m", 300), ("15m", 900), ("30m", 1800), ("1h", 3600), ("2h", 7200), ("4h", 14400), ("12h", 43200),
            ("1d", 86400), ("3d", 3 * 86400), ("7d", 7 * 86400), ("14d", 14 * 86400), ("30d", 30 * 86400), ("37d", 37 * 86400))
Bar = tuple  # (ts, open, high, low, close, volume)


# ------------------------------------------------------------------- data

def load(source: str, scratch: Path, coins: Optional[list[str]] = None) -> tuple[dict[str, list[Bar]], int]:
    out = {}
    if source == "coinbase5m":
        for p in sorted((scratch / "btc5m").glob("*_5m.json")) + sorted((scratch / "btc5m").glob("btc_5m.json")):
            name = p.stem.split("_")[0].upper()
            rows = json.loads(p.read_text())
            if len(rows) > 2000:
                out[name] = [tuple(r) for r in rows]
        base = 300
    elif source == "kalshi_hourly":
        for p in sorted((scratch / "state_collect" / "kalshi_hourly").glob("*.jsonl")):
            rows = sorted({int(r["end_ts"]): (int(r["end_ts"]) - 3600, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r.get("volume") or 0))
                           for r in read_jsonl(p)}.items())
            if len(rows) >= 24 * 14:
                out[p.stem.replace("KX", "").replace("PERP", "")] = [v for _, v in rows]
        base = 3600
    elif source == "btc_hourly":
        old = pickle.load(open(scratch / "xasset" / "btc_hourly_2015_2019.pkl", "rb"))   # [t, low, high, open, close, vol]
        new = pickle.load(open(scratch / "btc_hourly.pkl", "rb"))                         # (t, open, high, low, close, vol)
        rows = {int(r[0]): (int(r[0]), float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])) for r in old}
        rows.update({int(r[0]): (int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in new})
        out["BTC"] = [rows[k] for k in sorted(rows)]
        base = 3600
    elif source == "hl_daily":
        d = pickle.load(open(scratch / "hl_all_daily.pkl", "rb"))
        for coin, v in d.items():
            cs = v[0] if isinstance(v, tuple) else v
            try:
                rows = [(int(c.ts), float(c.open), float(c.high), float(c.low), float(c.close), float(getattr(c, "volume_usd", 0) or 0)) for c in cs]
            except AttributeError:
                continue
            if len(rows) >= 365:
                out[coin] = sorted(rows)
        base = 86400
    else:
        raise ValueError(source)
    if coins:
        out = {k: v for k, v in out.items() if k in coins}
    out = {k: clean(v) for k, v in out.items()}
    return out, base


def clean(bars: list[Bar]) -> list[Bar]:
    """Drop bars with a non-positive price or a high/low more than 50% from
    the open (bad prints in the oldest hourly files)."""
    return [b for b in bars if b[1] > 0 and b[4] > 0 and b[3] > 0 and 0.5 * b[1] <= b[3] <= b[1] * 1.0001 and b[1] * 0.9999 <= b[2] <= 1.5 * b[1]
            or (b[1] > 0 and b[4] > 0 and b[3] > 0 and b[2] >= b[3] and 0.5 * b[1] <= b[3] and b[2] <= 1.5 * b[1])]


def resample(bars: list[Bar], seconds: int) -> list[Bar]:
    by: dict[int, list[Bar]] = defaultdict(list)
    for b in bars:
        by[(b[0] // seconds) * seconds].append(b)
    out = []
    for k in sorted(by):
        g = sorted(by[k])
        out.append((k, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4], sum(x[5] for x in g)))
    return out


# ---------------------------------------------------------------- profile

def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def horizon_profile(bars: list[Bar], base: int) -> dict[str, dict]:
    out = {}
    for name, sec in HORIZONS:
        if sec < base:
            continue
        rs = resample(bars, sec) if sec > base else bars
        if len(rs) < 30:
            continue
        moves = [abs(math.log(b[4] / b[1])) * 1e4 for b in rs if b[1] > 0 and b[4] > 0]
        ranges = [(b[2] - b[3]) / b[1] * 1e4 for b in rs if b[1] > 0 and b[2] >= b[3]]
        rets = [math.log(rs[i][4] / rs[i - 1][4]) for i in range(1, len(rs)) if rs[i - 1][4] > 0 and rs[i][4] > 0]
        per_year = 365 * 86400 / sec
        out[name] = {"n": len(rs), "move_mean_bp": statistics.fmean(moves), "move_median_bp": statistics.median(moves),
                     "move_p90_bp": _pct(moves, 0.9), "range_mean_bp": statistics.fmean(ranges), "range_median_bp": statistics.median(ranges),
                     "range_p90_bp": _pct(ranges, 0.9), "ann_vol": statistics.pstdev(rets) * math.sqrt(per_year) if len(rets) > 2 else None,
                     "share_move_gt_cost": statistics.fmean(1.0 if m > COST_BP else 0.0 for m in moves),
                     "share_range_gt_2cost": statistics.fmean(1.0 if r > 2 * COST_BP else 0.0 for r in ranges)}
    return out


def seasonality(bars: list[Bar], base: int) -> dict:
    """By UTC hour (hourly or finer data) and by weekday: mean range, volume share, signed return with NW t."""
    hourly = resample(bars, 3600) if base < 3600 else bars
    out = {"hour": {}, "weekday": {}}
    def stats(groups: dict[int, list]):
        total_vol = sum(sum(v for _, _, v in g) for g in groups.values()) or 1.0
        res = {}
        for k, g in sorted(groups.items()):
            rets = [r for r, _, _ in g]
            if len(rets) < 30:
                continue
            sd = statistics.pstdev(rets)
            res[k] = {"n": len(rets), "ret_bp": statistics.fmean(rets) * 1e4,
                      "t": statistics.fmean(rets) / (sd / math.sqrt(len(rets))) if sd > 0 else 0.0,
                      "range_bp": statistics.fmean(x for _, x, _ in g), "vol_share": sum(v for _, _, v in g) / total_vol}
        return res
    by_h, by_w = defaultdict(list), defaultdict(list)
    for b in hourly:
        if b[1] <= 0 or b[4] <= 0:
            continue
        t = dt.datetime.fromtimestamp(b[0], dt.timezone.utc)
        rec = (math.log(b[4] / b[1]), (b[2] - b[3]) / b[1] * 1e4, b[5])
        by_h[t.hour].append(rec)
    daily = resample(bars, 86400) if base < 86400 else bars
    for b in daily:
        if b[1] <= 0 or b[4] <= 0:
            continue
        by_w[dt.datetime.fromtimestamp(b[0], dt.timezone.utc).weekday()].append((math.log(b[4] / b[1]), (b[2] - b[3]) / b[1] * 1e4, b[5]))
    out["hour"] = stats(by_h) if base <= 3600 else {}
    out["weekday"] = stats(by_w)
    return out


def volume_signal(bars: list[Bar], base: int) -> dict:
    """Next bar's range and signed return on the volume ratio (bar / trailing 24)."""
    out = {}
    for name, sec in (("base", base), ("1h", 3600), ("1d", 86400)):
        if sec < base or (name != "base" and sec == base):
            continue
        rs = resample(bars, sec) if sec > base else bars
        pairs_r, pairs_a = [], []
        for i in range(24, len(rs) - 1):
            v24 = statistics.fmean(x[5] for x in rs[i - 24:i])
            if v24 <= 0 or rs[i][1] <= 0 or rs[i + 1][1] <= 0 or rs[i + 1][4] <= 0:
                continue
            ratio = math.log(rs[i][5] / v24) if rs[i][5] > 0 else None
            if ratio is None:
                continue
            pairs_a.append((ratio, (rs[i + 1][2] - rs[i + 1][3]) / rs[i + 1][1] * 1e4))
            pairs_r.append((ratio, math.log(rs[i + 1][4] / rs[i + 1][1]) * 1e4))
        if len(pairs_r) < 100:
            continue
        ra = ols([y for _, y in pairs_a], [[x] for x, _ in pairs_a], nw_lags=5)
        rr = ols([y for _, y in pairs_r], [[x] for x, _ in pairs_r], nw_lags=5)
        out[name] = {"n": len(pairs_r), "range_beta": ra["beta"][1], "range_t": ra["t"][1], "ret_beta": rr["beta"][1], "ret_t": rr["t"][1]}
    return out


def macro_regressions(bars: list[Bar], base: int, scratch: Path) -> dict:
    """Daily BTC return and range on macro variables, same day and prior day."""
    from .data.macro import read_series
    md = scratch / "state_collect"
    series = {k: dict(read_series(md, k)) for k in ("VIXCLS", "DGS10", "DTWEXBGS", "DCOILWTICO", "SPY", "QQQ")}
    daily = resample(bars, 86400) if base < 86400 else bars
    rows = {dt.datetime.fromtimestamp(b[0], dt.timezone.utc).date().isoformat(): b for b in daily}
    days = sorted(rows)
    def chg(s, d0, d1, log=True):
        a, b = s.get(d0), s.get(d1)
        if a is None or b is None or (log and (a <= 0 or b <= 0)):
            return None
        return math.log(b / a) if log else b - a
    preds = {"VIX level": lambda d0, d1: series["VIXCLS"].get(d1), "VIX chg": lambda d0, d1: chg(series["VIXCLS"], d0, d1),
             "10y chg": lambda d0, d1: chg(series["DGS10"], d0, d1, log=False), "dollar chg": lambda d0, d1: chg(series["DTWEXBGS"], d0, d1),
             "WTI chg": lambda d0, d1: chg(series["DCOILWTICO"], d0, d1), "SPY ret": lambda d0, d1: chg(series["SPY"], d0, d1),
             "QQQ ret": lambda d0, d1: chg(series["QQQ"], d0, d1)}
    out = {}
    for name, fn in preds.items():
        same, lead = [], []
        for i in range(2, len(days)):
            d2, d1, d0 = days[i], days[i - 1], days[i - 2]
            b = rows[d2]
            if b[1] <= 0:
                continue
            ret, rng = math.log(b[4] / b[1]) * 1e4, (b[2] - b[3]) / b[1] * 1e4
            x_same, x_lead = fn(d1, d2), fn(d0, d1)
            if x_same is not None:
                same.append((x_same, ret, rng))
            if x_lead is not None:
                lead.append((x_lead, ret, rng))
        rec = {}
        for label, pairs in (("same", same), ("lead", lead)):
            if len(pairs) < 100:
                continue
            xs = [p for p, _, _ in pairs]; m, sd = statistics.fmean(xs), statistics.pstdev(xs)
            z = [[(x - m) / sd if sd > 0 else 0.0] for x in xs]
            r_ret = ols([r for _, r, _ in pairs], z, nw_lags=5)
            r_rng = ols([g for _, _, g in pairs], z, nw_lags=5)
            rec[label] = {"n": len(pairs), "ret_beta_bp": r_ret["beta"][1], "ret_t": r_ret["t"][1], "range_beta_bp": r_rng["beta"][1], "range_t": r_rng["t"][1]}
        out[name] = rec
    return out


# -------------------------------------------------------------------- run

def run(source: str, scratch: Path, coins: Optional[list[str]] = None, macro_coin: str = "BTC") -> dict:
    data, base = load(source, scratch, coins)
    out = {"source": source, "base": base, "coins": {}, "pooled": {}}
    for coin, bars in data.items():
        out["coins"][coin] = {"profile": horizon_profile(bars, base), "season": seasonality(bars, base), "volume": volume_signal(bars, base)}
    # pooled profile: median across coins per horizon
    for name, _ in HORIZONS:
        vals = [c["profile"][name] for c in out["coins"].values() if name in c["profile"]]
        if vals:
            out["pooled"][name] = {k: statistics.median(v[k] for v in vals if v.get(k) is not None) for k in vals[0] if k != "n"} | {"coins": len(vals)}
    if macro_coin in data:
        out["macro"] = macro_regressions(data[macro_coin], base, scratch)
    return out


def render(res: dict, detail_coins: int = 6) -> str:
    o = [f"range profile [{res['source']}]: {len(res['coins'])} coins, base bar {res['base']}s"]
    o.append("  pooled across coins (median), per horizon: move = |close/open|, range = high-low, bp; cost 18 bp a round trip")
    o.append(f"    {'horizon':7s} {'coins':>5s} {'move med':>9s} {'move p90':>9s} {'range med':>10s} {'range p90':>10s} {'ann vol':>8s} {'move>cost':>10s} {'range>2x':>9s}")
    for name, p in res["pooled"].items():
        o.append(f"    {name:7s} {p['coins']:5d} {p['move_median_bp']:9.0f} {p['move_p90_bp']:9.0f} {p['range_median_bp']:10.0f} {p['range_p90_bp']:10.0f} "
                 f"{(p['ann_vol'] or 0)*100:7.0f}% {p['share_move_gt_cost']*100:9.0f}% {p['share_range_gt_2cost']*100:8.0f}%")
    for coin, c in list(res["coins"].items())[:detail_coins]:
        s = c["season"]
        if s.get("hour"):
            hs = s["hour"]
            top = sorted(hs.items(), key=lambda kv: kv[1]["range_bp"], reverse=True)[:4]
            low = sorted(hs.items(), key=lambda kv: kv[1]["range_bp"])[:3]
            sig = [(h, v) for h, v in hs.items() if abs(v["t"]) >= 2.5]
            o.append(f"  {coin}: busiest UTC hours by range " + ", ".join(f"{h:02d}h {v['range_bp']:.0f}bp ({v['vol_share']*100:.1f}% vol)" for h, v in top)
                     + "; quietest " + ", ".join(f"{h:02d}h {v['range_bp']:.0f}bp" for h, v in low)
                     + ("; hours with |t|>=2.5 on signed return: " + ", ".join(f"{h:02d}h {v['ret_bp']:+.1f}bp t{v['t']:+.1f}" for h, v in sig) if sig else "; no hour with |t|>=2.5 on signed return"))
        if s.get("weekday"):
            ws = s["weekday"]
            o.append(f"  {coin}: weekday range " + ", ".join(f"{'MTWTFSS'[k]} {v['range_bp']:.0f}bp" for k, v in ws.items())
                     + "; signed " + ", ".join(f"{'MTWTFSS'[k]} {v['ret_bp']:+.0f}bp(t{v['t']:+.1f})" for k, v in ws.items()))
        for k, v in c["volume"].items():
            o.append(f"  {coin}: volume ratio -> next {k} bar: range {v['range_beta']:+.0f} bp per log-unit (t {v['range_t']:+.1f}); return {v['ret_beta']:+.1f} bp (t {v['ret_t']:+.1f})")
    if res.get("macro"):
        o.append("  macro, daily BTC (per sd of the predictor): same day = comovement, prior day = lead")
        for name, rec in res["macro"].items():
            parts = []
            for label in ("same", "lead"):
                r = rec.get(label)
                if r:
                    parts.append(f"{label}: ret {r['ret_beta_bp']:+.0f}bp (t {r['ret_t']:+.1f}), range {r['range_beta_bp']:+.0f}bp (t {r['range_t']:+.1f})")
            o.append(f"    {name:11s} " + " | ".join(parts))
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=("coinbase5m", "kalshi_hourly", "btc_hourly", "hl_daily"), required=True)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--coins", nargs="*", default=None)
    ap.add_argument("--detail", type=int, default=6)
    a = ap.parse_args(argv)
    res = run(a.source, a.scratch, a.coins)
    print(render(res, a.detail))
    (a.scratch / f"range_profile_{a.source}.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
