"""`binary-conditional-vol-2026-10`: pair the range profile with Kalshi's
crypto binaries. A binary pays on dispersion, not direction, and the
profile says dispersion is predictable (hour of day, recent range)
while direction is not. So: price every contract from the empirical
distribution of BTC's remaining-horizon return, built from 5-minute
bars strictly before the binaries sample, conditioned on the decision
hour and the last hour's range; compare with Kalshi's mid (Brier,
calibration); and trade the side whose model probability beats its
price by more than the quadratic fee plus a cent.

Series: KXBTCD (hourly strike ladder; decisions 30 and 15 minutes
before the print) and KXBTC15M (15-minute up/down against the slot's
opening index; decisions 10 and 5 minutes before). Variants, each a
trial: unconditional, hour only, hour x range tercile.

    python -m cryptobot.binary_vol_study --scratch <dir>
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .binary_tails_study import cluster_t, fee, load as load_binaries, quote_at

STEP = 300
CUTOFF = int(dt.datetime(2026, 9, 13, tzinfo=dt.timezone.utc).timestamp())
MARGIN = 0.01
SERIES = {  # series -> (state subdir, decision minutes before close)
    "KXBTCD": ("state_collect", (30, 15)),
    "KXBTC15M": ("state_binaries_15m", (10, 5)),
}
CONDITIONS = ("none", "hour", "hour_range")


class Model:
    """Empirical remaining-horizon return distributions from 5-minute bars."""

    def __init__(self, bars: list, cutoff: int = CUTOFF):
        self.close_at: dict[int, float] = {int(b[0]) + STEP: float(b[4]) for b in bars}
        self.hi_lo: dict[int, tuple[float, float]] = {int(b[0]) + STEP: (float(b[2]), float(b[3])) for b in bars}
        self.cutoff = cutoff
        self.times = sorted(self.close_at)
        self._dist: dict[tuple, list[float]] = {}
        self._tercile: dict[int, tuple[float, float]] = {}
        self._build_range_terciles()

    def range_ratio(self, ts: int) -> Optional[float]:
        """Last hour's high-low range over spot, at a bar close `ts`."""
        hs, ls = [], []
        for k in range(12):
            t = ts - k * STEP
            if t not in self.hi_lo:
                return None
            h, l = self.hi_lo[t]
            hs.append(h)
            ls.append(l)
        return (max(hs) - min(ls)) / self.close_at[ts]

    def _build_range_terciles(self) -> None:
        by_hour: dict[int, list[float]] = defaultdict(list)
        for ts in self.times:
            if ts >= self.cutoff:
                break
            r = self.range_ratio(ts)
            if r is not None:
                by_hour[hour_of(ts)].append(r)
        for h, xs in by_hour.items():
            xs.sort()
            self._tercile[h] = (xs[len(xs) // 3], xs[2 * len(xs) // 3])

    def tercile(self, ts: int) -> Optional[int]:
        r = self.range_ratio(ts)
        if r is None or hour_of(ts) not in self._tercile:
            return None
        lo, hi = self._tercile[hour_of(ts)]
        return 0 if r < lo else (1 if r < hi else 2)

    def key(self, cond: str, ts: int) -> Optional[tuple]:
        if cond == "none":
            return ()
        if cond == "hour":
            return (hour_of(ts),)
        t = self.tercile(ts)
        return None if t is None else (hour_of(ts), t)

    def dist(self, cond: str, horizon_s: int, key: tuple) -> list[float]:
        k = (cond, horizon_s, key)
        if k not in self._dist:
            out = []
            for ts in self.times:
                if ts + horizon_s >= self.cutoff:
                    break
                if self.key(cond, ts) != key:
                    continue
                p1 = self.close_at.get(ts + horizon_s)
                if p1:
                    out.append(math.log(p1 / self.close_at[ts]))
            out.sort()
            self._dist[k] = out
        return self._dist[k]

    def prob(self, cond: str, ts: int, horizon_s: int, spot: float, strike_type: str, strike: float) -> Optional[float]:
        key = self.key(cond, ts)
        if key is None:
            return None
        d = self.dist(cond, horizon_s, key)
        if len(d) < 200:
            return None
        x = math.log(strike / spot)
        if strike_type in ("greater", "greater_or_equal"):
            return 1.0 - bisect.bisect_right(d, x) / len(d)
        return bisect.bisect_left(d, x) / len(d)


def hour_of(ts: int) -> int:
    return (ts // 3600) % 24


def strike_of(m: dict) -> Optional[tuple[str, float]]:
    st = m.get("strike_type") or ""
    if st in ("greater", "greater_or_equal") and m.get("floor") is not None:
        return st, float(m["floor"])
    if st in ("less", "less_or_equal") and m.get("cap") is not None:
        return st, float(m["cap"])
    return None


def evaluate(model: Model, markets: list[dict], bars: dict[str, list], minutes_before: int, cond: str) -> dict:
    rows = []
    for m in markets:
        sk = strike_of(m)
        if sk is None or m.get("result") not in ("yes", "no"):
            continue
        ts = m["close_ts"] - minutes_before * 60
        if ts % STEP or ts not in model.close_at or ts < CUTOFF:
            continue
        q = quote_at(bars[m["ticker"]], ts)
        if q is None:
            continue
        bid, ask, _, _ = q
        spot = model.close_at[ts]
        p = model.prob(cond, ts, minutes_before * 60, spot, sk[0], sk[1])
        if p is None:
            continue
        y = 1.0 if m["result"] == "yes" else 0.0
        mid = (bid + ask) / 2
        side, price = None, None
        if p - ask - fee(ask) - MARGIN > 0:
            side, price = "yes", ask
        elif (1 - p) - (1 - bid) - fee(1 - bid) - MARGIN > 0:
            side, price = "no", 1 - bid
        net = None
        if side:
            win = y if side == "yes" else 1 - y
            net = (win - price - fee(price)) / price
        rows.append({"event": m["event"], "close_ts": m["close_ts"], "p": p, "mid": mid, "y": y,
                     "side": side, "price": price, "net": net})
    out = {"quoted": len(rows), "trades": 0}
    if not rows:
        return out
    out["brier_model"] = statistics.fmean((r["p"] - r["y"]) ** 2 for r in rows)
    out["brier_mid"] = statistics.fmean((r["mid"] - r["y"]) ** 2 for r in rows)
    cal = defaultdict(list)
    for r in rows:
        cal[min(int(r["p"] * 10), 9)].append(r["y"])
    out["calibration"] = {k: (round(statistics.fmean(v), 3), len(v)) for k, v in sorted(cal.items())}
    ts = [r for r in rows if r["side"]]
    out["trades"] = len(ts)
    if ts:
        nets = [r["net"] for r in ts]
        out["net_per_dollar"] = statistics.fmean(nets)
        out["t"] = cluster_t(nets, [r["event"] for r in ts])
        out["events"] = len({r["event"] for r in ts})
        out["hit"] = statistics.fmean(1.0 if r["net"] > 0 else 0.0 for r in ts)
        med = sorted(r["close_ts"] for r in ts)[len(ts) // 2]
        h1 = [r["net"] for r in ts if r["close_ts"] < med]
        h2 = [r["net"] for r in ts if r["close_ts"] >= med]
        out["halves"] = (statistics.fmean(h1) if h1 else None, statistics.fmean(h2) if h2 else None)
        out["yes_share"] = statistics.fmean(1.0 if r["side"] == "yes" else 0.0 for r in ts)
        out["avg_price"] = statistics.fmean(r["price"] for r in ts)
    return out


def basis(model: Model, markets: list[dict]) -> dict:
    """Settlement index minus the Coinbase close at the print, bp."""
    xs = []
    for m in markets:
        s = m.get("settle")
        c = model.close_at.get(m["close_ts"])
        if s and c:
            xs.append(1e4 * (float(s) - c) / c)
    xs = sorted(set(xs))
    if len(xs) < 3:
        return {}
    return {"n": len(xs), "mean_bp": statistics.fmean(xs), "sd_bp": statistics.pstdev(xs)}


def run(scratch: Path, series: Optional[list[str]] = None) -> dict:
    bars = json.loads((scratch / "btc5m" / "btc_5m.json").read_text())
    model = Model(bars)
    res = {"cutoff": CUTOFF, "series": {}}
    for s, (sub, minutes) in SERIES.items():
        if series and s not in series:
            continue
        d = scratch / sub
        if not (d / "kalshi_binaries" / "markets.jsonl").exists():
            res["series"][s] = {"missing": str(d)}
            continue
        markets, mbars = load_binaries(d)
        markets = [m for m in markets if m["series"] == s]
        row = {"markets": len(markets), "basis": basis(model, markets), "runs": {}}
        for mb in minutes:
            for cond in CONDITIONS:
                row["runs"][f"{mb}m/{cond}"] = evaluate(model, markets, mbars, mb, cond)
        res["series"][s] = row
    return res


def render(res: dict) -> str:
    o = [f"binary conditional vol: model from Coinbase 5-minute bars before {dt.datetime.fromtimestamp(res['cutoff'], dt.timezone.utc):%Y-%m-%d}; fee 0.07 p(1-p), margin {MARGIN:.2f}"]
    for s, row in res["series"].items():
        if "missing" in row:
            o.append(f"  {s}: no data at {row['missing']}")
            continue
        b = row["basis"]
        o.append(f"  {s}: {row['markets']} settled markets; settle minus Coinbase close: mean {b.get('mean_bp', 0):+.1f} bp, sd {b.get('sd_bp', 0):.1f} bp (n {b.get('n', 0)})")
        o.append("    decision/cond   quoted  brier model  brier mid   trades  net/$    t   hit   halves            yes%  avg px")
        for k, r in row["runs"].items():
            if r["quoted"] == 0:
                o.append(f"    {k:15s} 0")
                continue
            h = r.get("halves", (None, None))
            hs = " / ".join("-" if x is None else f"{x:+.1%}" for x in h)
            o.append(f"    {k:15s} {r['quoted']:6d}   {r['brier_model']:.4f}     {r['brier_mid']:.4f}   {r['trades']:6d}  "
                     + (f"{r['net_per_dollar']:+.1%}  {r['t']:+.1f}  {r['hit']:.0%}  {hs:16s}  {r['yes_share']:.0%}   {r['avg_price']:.2f}" if r["trades"] else ""))
        best = row["runs"].get(f"{SERIES[s][1][0]}m/hour_range") or {}
        if best.get("calibration"):
            o.append("    calibration (hour x range, first decision): model p decile -> realised share (n): "
                     + ", ".join(f"{k / 10:.1f}:{v[0]:.2f}({v[1]})" for k, v in best["calibration"].items()))
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--series", nargs="*", default=None)
    a = ap.parse_args(argv)
    res = run(a.scratch, a.series)
    print(render(res))
    (a.scratch / "binary_vol_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
