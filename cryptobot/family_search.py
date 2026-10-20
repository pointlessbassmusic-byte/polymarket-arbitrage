"""`family-search-2026-10`: every one- and two-feature threshold rule with a
barrier exit, over a dataset, scored as a FAMILY.

The point is not the best rule; it is how good the best rule of a
search this size looks when nothing is there. So the whole family goes
into the diagnostics the bounce-short was held to: the T x N daily P&L
matrix, the effective number of trials, CSCV probability of
overfitting, the in-sample best's deflated Sharpe at N_eff, and an
expanding-window walk-forward that each period trades the rule that
was best on everything before it.

Features from closes (and volume when present): returns over four
windows, rolling volatility, position in the rolling range, volume
ratio, and the clock (hour of day, or weekday). Terciles. Rules: every
single band and every two-feature cell, long and short. Exits: a
target/stop pair with a time stop, checked close to close.

    python -m cryptobot.family_search --set kalshi_hourly --scratch <dir>
    python -m cryptobot.family_search --set btc_hourly --scratch <dir>
    python -m cryptobot.family_search --set etf_daily --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import pickle
import statistics
import time
from array import array
from collections import defaultdict
from pathlib import Path
from typing import Optional

from . import stats as S
from .data.nasdaq import read_jsonl

SETS = {
    # name: (bar seconds, windows, vol/range window, geometries (target, stop, hold bars), round-trip cost, periods)
    "kalshi_hourly": {"bar": 3600, "windows": (1, 4, 24, 168), "roll": 24, "cost": 0.0018, "annual": 365,
                      "geometries": ((0.01, 0.005, 4), (0.01, 0.005, 24), (0.02, 0.01, 4), (0.02, 0.01, 24)),
                      "period": "month"},
    "btc_hourly": {"bar": 3600, "windows": (1, 4, 24, 168), "roll": 24, "cost": 0.0010, "annual": 365,
                   "geometries": ((0.01, 0.005, 4), (0.01, 0.005, 24), (0.02, 0.01, 4), (0.02, 0.01, 24)),
                   "period": "year"},
    "etf_daily": {"bar": 86400, "windows": (1, 5, 20, 60), "roll": 20, "cost": 0.0008, "annual": 252,
                  "geometries": ((0.03, 0.015, 5), (0.03, 0.015, 20), (0.06, 0.03, 5), (0.06, 0.03, 20)),
                  "period": "year"},
}
N_BANDS = 3
MIN_TRADES = 30


# ------------------------------------------------------------------- data

def load_set(name: str, scratch: Path) -> dict[str, list[tuple[int, float, Optional[float]]]]:
    """ticker -> [(ts, close, volume or None)] sorted."""
    out = {}
    if name == "kalshi_hourly":
        for p in sorted((scratch / "state_collect" / "kalshi_hourly").glob("*.jsonl")):
            rows = sorted({int(r["end_ts"]): (float(r["close"]), float(r.get("volume") or 0.0)) for r in read_jsonl(p)}.items())
            if len(rows) >= 24 * 14:
                out[p.stem] = [(ts, c, v) for ts, (c, v) in rows]
    elif name == "btc_hourly":
        old = pickle.load(open(scratch / "xasset" / "btc_hourly_2015_2019.pkl", "rb"))   # [t, low, high, open, close, vol]
        new = pickle.load(open(scratch / "btc_hourly.pkl", "rb"))                         # (t, open, high, low, close, vol)
        rows = {int(r[0]): (float(r[4]), float(r[5])) for r in old}
        rows.update({int(r[0]): (float(r[4]), float(r[5])) for r in new})
        out["BTC"] = [(ts, c, v) for ts, (c, v) in sorted(rows.items())]
    elif name == "etf_daily":
        for p in sorted((scratch / "tsmom").glob("*.json")):
            rows = json.loads(p.read_text())
            out[p.stem] = [(int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()), float(c), None) for d, c in rows]
    return out


# --------------------------------------------------------------- features

def features(series, cfg: dict) -> dict[str, list[Optional[float]]]:
    closes = [c for _, c, _ in series]
    vols = [v for _, _, v in series]
    n = len(closes)
    f: dict[str, list] = {}
    for w in cfg["windows"]:
        f[f"ret_{w}"] = [None] * w + [math.log(closes[i] / closes[i - w]) for i in range(w, n)]
    r1 = f[f"ret_{cfg['windows'][0]}"]
    roll = cfg["roll"]
    vol, rng, vr = [None] * n, [None] * n, [None] * n
    q, sm, sq = [], 0.0, 0.0
    hi_q, lo_q = [], []
    vq, vsum = [], 0.0
    for i in range(n):
        if r1[i] is not None:
            q.append(r1[i]); sm += r1[i]; sq += r1[i] ** 2
            if len(q) > roll:
                y = q.pop(0); sm -= y; sq -= y * y
            if len(q) >= roll:
                m = sm / len(q)
                vol[i] = math.sqrt(max(sq / len(q) - m * m, 0.0))
        hi_q.append(closes[i]); lo_q.append(closes[i])
        if len(hi_q) > roll:
            hi_q.pop(0); lo_q.pop(0)
        if len(hi_q) >= roll:
            h, l = max(hi_q), min(lo_q)
            rng[i] = (closes[i] - l) / (h - l) if h > l else 0.5
        if vols[i] is not None:
            vq.append(vols[i]); vsum += vols[i]
            if len(vq) > roll:
                vsum -= vq.pop(0)
            if len(vq) >= roll and vsum > 0:
                vr[i] = vols[i] / (vsum / len(vq))
    f["vol"], f["range_pos"] = vol, rng
    if any(v is not None for v in vols):
        f["vol_ratio"] = vr
    if cfg["bar"] < 86400:
        f["hour"] = [float(dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour) for ts, _, _ in series]
    else:
        f["weekday"] = [float(dt.datetime.fromtimestamp(ts, dt.timezone.utc).weekday()) for ts, _, _ in series]
    return f


def tercile_cuts(values: list[float], n: int = N_BANDS) -> list[float]:
    vs = sorted(v for v in values if v is not None)
    return [vs[int(len(vs) * k / n)] for k in range(1, n)] if vs else []


def band(v, cuts) -> int:
    if v is None:
        return -1
    return next((k for k, c in enumerate(cuts) if v < c), len(cuts))


def outcomes(closes: list[float], target: float, stop: float, hold: int) -> tuple[array, array, array]:
    """Per entry bar: net-of-nothing gross return of a long and of a short
    entered at that close, and the exit bar; barriers checked close to close."""
    n = len(closes)
    long_r, short_r, exit_i = array("d", [0.0] * n), array("d", [0.0] * n), array("l", [0] * n)
    for i in range(n - 1):
        e = closes[i]
        up, dn = e * (1 + target), e * (1 - stop)          # long barriers
        up_s, dn_s = e * (1 + stop), e * (1 - target)      # short barriers
        lr = sr = None
        li = si = min(i + hold, n - 1)
        for j in range(i + 1, min(i + hold, n - 1) + 1):
            c = closes[j]
            if lr is None and (c >= up or c <= dn):
                lr, li = c / e - 1.0, j
            if sr is None and (c <= dn_s or c >= up_s):
                sr, si = 1.0 - c / e, j
            if lr is not None and sr is not None:
                break
        if lr is None:
            lr = closes[li] / e - 1.0
        if sr is None:
            sr = 1.0 - closes[si] / e
        long_r[i], short_r[i], exit_i[i] = lr, sr, max(li, si)
    return long_r, short_r, exit_i


# ------------------------------------------------------------- the family

def rules(feature_names: list[str]) -> list[tuple]:
    out = [((f, b),) for f in feature_names for b in range(N_BANDS)]
    for f1, f2 in itertools.combinations(feature_names, 2):
        out.extend(((f1, b1), (f2, b2)) for b1 in range(N_BANDS) for b2 in range(N_BANDS))
    return out


def rule_name(rule: tuple, side: str, geo: tuple) -> str:
    return f"{side}:" + "&".join(f"{f}[{b}]" for f, b in rule) + f":+{geo[0]*100:g}/-{geo[1]*100:g}/{geo[2]}"


def build_matrix(data: dict, cfg: dict, cuts: Optional[dict] = None, verbose: bool = False) -> dict:
    """Daily net P&L of every rule x side x geometry, pooled across the
    instruments (one position per instrument per column, sum of trade
    returns booked on the entry day)."""
    t0 = time.time()
    feats = {tk: features(s, cfg) for tk, s in data.items()}
    names = sorted(set.intersection(*[set(f) for f in feats.values()]))
    if cuts is None:
        cuts = {f: tercile_cuts([v for tk in feats for v in feats[tk][f]]) for f in names}
    bands = {tk: {f: [band(v, cuts[f]) for v in feats[tk][f]] for f in names} for tk in feats}
    days = sorted({dt.datetime.fromtimestamp(ts, dt.timezone.utc).date() for s in data.values() for ts, _, _ in s})
    day_idx = {d: i for i, d in enumerate(days)}
    bar_day = {tk: [day_idx[dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()] for ts, _, _ in s] for tk, s in data.items()}
    outs = {tk: {g: outcomes([c for _, c, _ in s], *g) for g in cfg["geometries"]} for tk, s in data.items()}
    cost = cfg["cost"]
    cols, colnames, trades = [], [], []
    for rule in rules(names):
        fired = {}
        for tk in data:
            b = bands[tk]
            if len(rule) == 1:
                (f1, b1), = rule
                fired[tk] = [i for i, x in enumerate(b[f1]) if x == b1]
            else:
                (f1, b1), (f2, b2) = rule
                a1, a2 = b[f1], b[f2]
                fired[tk] = [i for i, x in enumerate(a1) if x == b1 and a2[i] == b2]
        for geo in cfg["geometries"]:
            for side in ("long", "short"):
                col = array("d", [0.0] * len(days))
                n_tr = 0
                for tk in data:
                    lr, sr, ex = outs[tk][geo]
                    r = lr if side == "long" else sr
                    bd = bar_day[tk]
                    busy = -1
                    for i in fired[tk]:
                        if i <= busy or i >= len(bd) - 1:
                            continue
                        col[bd[i]] += r[i] - cost
                        busy = ex[i]
                        n_tr += 1
                if n_tr >= MIN_TRADES:
                    cols.append(col); colnames.append(rule_name(rule, side, geo)); trades.append(n_tr)
    if verbose:
        print(f"  matrix: {len(cols)} columns x {len(days)} days in {time.time()-t0:.0f}s", flush=True)
    return {"days": days, "columns": cols, "names": colnames, "trades": trades, "cuts": cuts, "features": names}


def sharpe(xs, annual: int) -> float:
    if len(xs) < 3:
        return 0.0
    sd = statistics.pstdev(xs)
    return statistics.fmean(xs) / sd * math.sqrt(annual) if sd > 0 else 0.0


def walk_forward(data: dict, cfg: dict, mat: dict) -> dict:
    """Each period trades the column that had the best Sharpe on every day
    before it (selection on the in-sample-cut matrix, the one look-ahead
    left in; the chosen rule's test-period P&L is re-run with cuts
    fitted on the training days only)."""
    days = mat["days"]
    key = (lambda d: d.strftime("%Y-%m")) if cfg["period"] == "month" else (lambda d: str(d.year))
    periods = sorted({key(d) for d in days})
    series, chosen = [], []
    for per in periods[1:]:
        train_idx = [i for i, d in enumerate(days) if key(d) < per]
        test_idx = [i for i, d in enumerate(days) if key(d) == per]
        if len(train_idx) < 30:
            continue
        best, best_sr = None, -1e9
        for j, col in enumerate(mat["columns"]):
            xs = [col[i] for i in train_idx]
            if sum(1 for x in xs if x) < MIN_TRADES:
                continue
            sr = sharpe(xs, cfg["annual"])
            if sr > best_sr:
                best, best_sr = j, sr
        if best is None:
            continue
        name = mat["names"][best]
        # re-run the chosen rule on the test period with training-only cuts
        train_days = {days[i] for i in train_idx}
        train_data = {tk: [b for b in s if dt.datetime.fromtimestamp(b[0], dt.timezone.utc).date() in train_days] for tk, s in data.items()}
        train_data = {tk: s for tk, s in train_data.items() if len(s) > cfg["roll"] + max(cfg["windows"]) + 5}
        cuts = {f: tercile_cuts([v for tk in train_data for v in features(train_data[tk], cfg).get(f, [])]) for f in mat["features"]}
        test_col = one_rule(data, cfg, name, cuts)
        pnl = [test_col.get(days[i], 0.0) for i in test_idx]
        series.extend(pnl)
        chosen.append((per, name, best_sr, len(pnl), sum(pnl)))
    return {"series": series, "chosen": chosen}


def parse_name(name: str) -> tuple[str, tuple, tuple]:
    side, body, geo = name.split(":")
    rule = tuple((p.split("[")[0], int(p.split("[")[1].rstrip("]"))) for p in body.split("&"))
    t, s, h = geo.split("/")
    return side, rule, (float(t.lstrip("+")) / 100, float(s.lstrip("-")) / 100, int(h))


def one_rule(data: dict, cfg: dict, name: str, cuts: dict) -> dict:
    """day -> net P&L of one named rule with the given cuts."""
    side, rule, geo = parse_name(name)
    out: dict = defaultdict(float)
    for tk, s in data.items():
        f = features(s, cfg)
        if any(fn not in f for fn, _ in rule):
            continue
        closes = [c for _, c, _ in s]
        lr, sr, ex = outcomes(closes, *geo)
        r = lr if side == "long" else sr
        busy = -1
        for i in range(len(s) - 1):
            if i <= busy or any(band(f[fn][i], cuts[fn]) != b for fn, b in rule):
                continue
            out[dt.datetime.fromtimestamp(s[i][0], dt.timezone.utc).date()] += r[i] - cfg["cost"]
            busy = ex[i]
    return out


def run(data: dict, cfg: dict, verbose: bool = False) -> dict:
    mat = build_matrix(data, cfg, verbose=verbose)
    cols, names = mat["columns"], mat["names"]
    annual = cfg["annual"]
    srs = [sharpe(list(c), annual) for c in cols]
    order = sorted(range(len(cols)), key=lambda j: srs[j], reverse=True)
    top = [{"name": names[j], "sharpe": srs[j], "trades": mat["trades"][j],
            "net_per_trade": sum(cols[j]) / mat["trades"][j], "psr": S.psr(list(cols[j]))} for j in order[:10]]
    neff = S.n_eff_from_corr(cols) if len(cols) > 1 else {"n_eff_a3": 1.0, "n_eff_pr": 1.0, "rho": 1.0}
    n_eff = max(1.0, min(neff.get("n_eff_pr") or 1.0, neff.get("n_eff_a3") or 1.0))
    pbo = S.cscv_pbo(cols, n_blocks=10, metric="sharpe", named=order[0]) if len(cols) > 1 and len(mat["days"]) >= 40 else {"pbo": None}
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    best = cols[order[0]]
    dsr_eff = S.dsr(list(best), n_eff, var_sr)
    dsr_nom = S.dsr(list(best), len(cols), var_sr)
    wf = walk_forward(data, cfg, mat)
    wf_s = wf["series"]
    res = {"instruments": sorted(data), "days": len(mat["days"]), "n_columns": len(cols), "n_eff": n_eff, "rho": neff.get("rho"),
           "pbo": pbo.get("pbo"), "top": top, "best_dsr_eff": dsr_eff, "best_dsr_nominal": dsr_nom,
           "walk_forward": {"n": len(wf_s), "total": sum(wf_s), "sharpe": sharpe(wf_s, annual) if wf_s else 0.0,
                            "psr": S.psr(wf_s) if len(wf_s) > 2 else 0.0, "chosen": wf["chosen"]}}
    res["verdict"] = passes(res)
    return res


def passes(res: dict) -> tuple[str, str]:
    """Written before running: a candidate needs walk-forward PSR >= 0.95,
    family PBO <= 0.5 and the best rule's DSR at N_eff >= 0.95; a
    net-negative walk-forward closes the family; else recorded."""
    wf = res["walk_forward"]
    if wf["n"] and wf["total"] <= 0:
        return "closed", f"walk-forward net {wf['total']*100:+.1f}% over {wf['n']} days"
    if wf["psr"] >= 0.95 and (res["pbo"] is not None and res["pbo"] <= 0.5) and res["best_dsr_eff"] >= 0.95:
        return "candidate", f"{res['top'][0]['name']}"
    return "inconclusive", (f"walk-forward PSR {wf['psr']:.2f}, PBO {res['pbo'] if res['pbo'] is not None else 'n/a'}, "
                            f"best DSR {res['best_dsr_eff']:.2f} at N_eff {res['n_eff']:.0f}")


def render(res: dict, name: str) -> str:
    o = [f"family search [{name}]: {len(res['instruments'])} instruments, {res['days']} days, {res['n_columns']} rules with >= {MIN_TRADES} trades"]
    o.append(f"  N_eff {res['n_eff']:.0f} (mean pairwise corr {res['rho']:.2f}); CSCV PBO {res['pbo'] if res['pbo'] is not None else 'n/a'}; "
             f"in-sample best DSR {res['best_dsr_eff']:.2f} at N_eff ({res['best_dsr_nominal']:.2f} at nominal N)")
    o.append("  in-sample top 10:")
    for t in res["top"]:
        o.append(f"    {t['name']:48s} Sharpe {t['sharpe']:+.2f}  PSR {t['psr']:.2f}  {t['trades']:5d} trades  {t['net_per_trade']*1e4:+6.0f} bp/trade")
    wf = res["walk_forward"]
    o.append(f"  walk-forward (best-so-far rule each period, cuts refit): {wf['n']} days, net {wf['total']*100:+.1f}%, "
             f"Sharpe {wf['sharpe']:+.2f}, PSR {wf['psr']:.2f}")
    for per, nm, sr, n, pnl in wf["chosen"]:
        o.append(f"    {per}: {nm} (prior Sharpe {sr:+.2f}) -> {pnl*100:+.2f}% over {n} days")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=sorted(SETS), required=True)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    cfg = SETS[a.set]
    data = load_set(a.set, a.scratch)
    if not data:
        print("no data for", a.set)
        return 1
    print(f"loaded {len(data)} instruments, {sum(len(s) for s in data.values()):,} bars", flush=True)
    print(render(run(data, cfg, verbose=True), a.set))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
