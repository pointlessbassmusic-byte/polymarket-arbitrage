"""`kalshi-funding-carry-us`: short a Kalshi crypto perp when its trailing
14-day funding annualises above 8%, hedged long spot, held 14 days.

Positive funding is paid by longs to shorts. The hedged return of one
hold = funding collected + (short perp return - long spot return) -
58 bp (perp 2 x 4 bp, spot 2 x 25 bp at Alpaca crypto taker rates).

    python -m cryptobot.kalshi_carry_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from .binary_tails_study import cluster_t
from .crossasset_study import ols

THRESHOLD = 0.08
HOLD = 14
COST = 0.0058
SPOT = {"KXBTCPERP": "btc", "KXETHPERP": "ETH", "KXSOLPERP": "SOL", "KXXRPPERP": "XRP", "KXDOGEPERP": "DOGE",
        "KXKSHIBPERP": "SHIB", "KXLINKPERP": "LINK", "KXLTCPERP": "LTC", "KXBCHPERP": "BCH", "KXADAPERP": "ADA",
        "KXSUIPERP": "SUI", "KXNEARPERP": "NEAR", "KXAVAXPERP": "AVAX"}


def daily_funding(prints: list) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for d, x in prints:
        out[d] += float(x)
    return dict(out)


def daily_close_perp(path: Path) -> dict[str, float]:
    out = {}
    for line in path.open():
        if line.strip():
            r = json.loads(line)
            d = dt.datetime.fromtimestamp(int(r["end_ts"]), dt.timezone.utc)
            if d.hour == 0:
                out[(d - dt.timedelta(seconds=1)).date().isoformat()] = float(r["close"])   # close of the prior UTC day
    return out


def daily_close_spot(path: Path) -> dict[str, float]:
    rows = json.loads(path.read_text())
    out = {}
    for r in rows:
        d = dt.datetime.fromtimestamp(int(r[0]) + 300, dt.timezone.utc)
        out[d.date().isoformat()] = float(r[4])   # last 5-minute close of the day wins
    return out


def run(scratch: Path) -> dict:
    fund = json.loads((scratch / "funding" / "kalshi_funding.json").read_text())
    res = {"perps": {}, "holds": []}
    pairs = []
    for perp, coin in SPOT.items():
        if perp not in fund:
            continue
        f = daily_funding(fund[perp])
        days = sorted(f)
        if len(days) < 60:
            continue
        pp = scratch / "state_collect" / "kalshi_hourly" / f"{perp}.jsonl"
        sp = scratch / "btc5m" / f"{coin}_5m.json"
        pc = daily_close_perp(pp) if pp.exists() else {}
        sc = daily_close_spot(sp) if sp.exists() else {}
        all_days = [(dt.date.fromisoformat(days[0]) + dt.timedelta(days=k)).isoformat()
                    for k in range((dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days + 1)]
        fd = [f.get(d, 0.0) for d in all_days]
        n_hold = 0
        k = HOLD
        while k + HOLD <= len(all_days):
            trail = sum(fd[k - HOLD:k]) * 365 / HOLD
            nxt = sum(fd[k:k + HOLD])
            pairs.append((trail, nxt * 365 / HOLD, all_days[k]))
            if trail > THRESHOLD:
                d0, d1 = all_days[k - 1], all_days[k + HOLD - 1]
                basis = None
                if d0 in pc and d1 in pc and d0 in sc and d1 in sc:
                    basis = -(pc[d1] / pc[d0] - 1) + (sc[d1] / sc[d0] - 1)
                ret = nxt + (basis or 0.0) - COST
                res["holds"].append({"perp": perp, "start": d0, "trail_ann": trail, "funding": nxt, "basis": basis,
                                     "ret": ret, "hedged": basis is not None})
                n_hold += 1
            k += 1
        res["perps"][perp] = {"days": len(all_days), "ann_funding": sum(fd) * 365 / len(fd), "holds": n_hold}
    if len(pairs) > 30:
        reg = ols([b for _, b, _ in pairs], [[a] for a, _, _ in pairs], nw_lags=HOLD)
        res["persistence"] = {"n": len(pairs), "slope": reg["beta"][1], "t": reg["t"][1]}
    # holds start on overlapping days (stepping one day); keep non-overlapping per perp for the verdict
    keep, last = [], {}
    for h in sorted(res["holds"], key=lambda h: (h["perp"], h["start"])):
        s = dt.date.fromisoformat(h["start"])
        if h["perp"] in last and (s - last[h["perp"]]).days < HOLD:
            continue
        keep.append(h)
        last[h["perp"]] = s
    res["nonoverlap"] = keep
    if keep:
        rets = [h["ret"] for h in keep]
        res["rule"] = {"n": len(keep), "hedged_share": statistics.fmean(1.0 if h["hedged"] else 0.0 for h in keep),
                       "mean": statistics.fmean(rets), "funding_mean": statistics.fmean(h["funding"] for h in keep),
                       "basis_mean": statistics.fmean([h["basis"] for h in keep if h["basis"] is not None] or [0.0]),
                       "t": cluster_t(rets, [h["start"] for h in keep]), "hit": statistics.fmean(1.0 if r > 0 else 0.0 for r in rets)}
    return res


def render(res: dict) -> str:
    o = [f"Kalshi funding carry, short perp + long spot, 14-day holds when trailing funding > {THRESHOLD:.0%}/yr, cost {COST * 1e4:.0f} bp"]
    for p, v in res["perps"].items():
        o.append(f"  {p:14s} {v['days']:4d} days, mean funding {v['ann_funding']:+.1%}/yr, qualifying starts {v['holds']}")
    if res.get("persistence"):
        pr = res["persistence"]
        o.append(f"  persistence: next 14 days' funding on the trailing 14 days', slope {pr['slope']:+.2f} (t {pr['t']:+.1f}, n {pr['n']} overlapping)")
    r = res.get("rule")
    if r:
        o.append(f"  rule, non-overlapping holds: {r['n']} ({r['hedged_share']:.0%} with both price legs on file), net {r['mean']:+.2%} a hold "
                 f"(funding {r['funding_mean']:+.2%}, basis {r['basis_mean']:+.2%}, cost -{COST:.2%}), t {r['t']:+.1f}, hit {r['hit']:.0%}")
        for h in res["nonoverlap"][:20]:
            o.append(f"    {h['perp']:12s} {h['start']} trailing {h['trail_ann']:+.0%}/yr -> funding {h['funding']:+.2%}, basis "
                     + (f"{h['basis']:+.2%}" if h['basis'] is not None else "n/a") + f", net {h['ret']:+.2%}")
    else:
        o.append("  rule: no qualifying holds")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    print(render(run(a.scratch)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
