"""`macro-relations-2026-10`: eight documented macro-to-asset relations as
LEADS on instruments the desk can trade.

Predictors are taken as of the prior session's close (no same-day
publication look-ahead). For each relation and horizon: OLS of the
forward log return on the standardised predictor with Newey-West t,
full sample and by era; a tercile rule in the literature's direction,
one position at a time, net of 8 bp a round trip, by half.

    python -m cryptobot.macro_study --state state
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
from pathlib import Path
from typing import Callable, Optional

from .crossasset_study import ols
from .data.macro import read_series

HORIZONS = (5, 20, 1)
ERAS = (("2017-2020", "2017-01-01", "2020-12-31"), ("2021-2023", "2021-01-01", "2023-12-31"), ("2024-2026", "2024-01-01", "2026-12-31"))
COST_BP = 8.0
NW_LAGS = 10

# (name, predictor builder, target, literature sign: +1 means a high predictor -> go long the target)
RELATIONS = (
    ("real yield 5d chg -> GLD", ("DFII10", "diff", 5), "GLD", -1),
    ("GDX/GLD 60d z -> GDX-GLD", ("GDX/GLD", "z", 60), "GDX-GLD", -1),
    ("WTI 20d mom -> XLE", ("DCOILWTICO", "logchg", 20), "XLE", +1),
    ("gas 20d mom -> UNG", ("DHHNGSP", "logchg", 20), "UNG", +1),
    ("dollar 20d chg -> EEM", ("DTWEXBGS", "logchg", 20), "EEM", -1),
    ("HY spread 5d chg -> IWM", ("BAMLH0A0HYM2", "diff", 5), "IWM", -1),
    ("2s10s 20d chg -> XLF", ("DGS10-DGS2", "diff", 20), "XLF", +1),
    ("VIX level -> SPY", ("VIXCLS", "level", 1), "SPY", +1),
)


def _series(state: Path, name: str) -> dict[str, float]:
    if "/" in name:
        a, b = name.split("/")
        sa, sb = dict(read_series(state, a)), dict(read_series(state, b))
        return {d: math.log(sa[d] / sb[d]) for d in sa if d in sb and sa[d] > 0 and sb[d] > 0}
    if "-" in name and not name.startswith("DCOIL"):
        a, b = name.split("-")
        sa, sb = dict(read_series(state, a)), dict(read_series(state, b))
        return {d: sa[d] - sb[d] for d in sa if d in sb}
    return dict(read_series(state, name))


def predictor(values: dict[str, float], kind: str, window: int) -> dict[str, float]:
    days = sorted(values)
    out = {}
    for i, d in enumerate(days):
        if kind == "level":
            out[d] = values[d]
        elif i >= window:
            a, b = values[days[i - window]], values[d]
            if kind == "diff":
                out[d] = b - a
            elif kind == "logchg" and a > 0 and b > 0:
                out[d] = math.log(b / a)
            elif kind == "z":
                win = [values[x] for x in days[i - window:i + 1]]
                sd = statistics.pstdev(win)
                out[d] = (b - statistics.fmean(win)) / sd if sd > 0 else 0.0
    return out


def target_returns(state: Path, name: str) -> tuple[list[str], dict[str, float]]:
    """Trading days and closes of the target (a spread target is a log ratio)."""
    if "-" in name:
        a, b = name.split("-")
        sa, sb = dict(read_series(state, a)), dict(read_series(state, b))
        px = {d: math.log(sa[d] / sb[d]) for d in sa if d in sb}
        days = sorted(px)
        return days, {d: px[d] for d in days}                       # already a log level
    px = dict(read_series(state, name))
    days = sorted(px)
    return days, {d: math.log(px[d]) for d in days}


def forward(days: list[str], logpx: dict[str, float], h: int) -> dict[str, float]:
    return {days[i]: logpx[days[i + h]] - logpx[days[i]] for i in range(len(days) - h)}


def prior_value(pred: dict[str, float], day: str, lookback_days: int = 7) -> Optional[float]:
    """The predictor as of the last date strictly before `day` (within a week)."""
    d = dt.date.fromisoformat(day)
    for k in range(1, lookback_days + 1):
        v = pred.get((d - dt.timedelta(days=k)).isoformat())
        if v is not None:
            return v
    return None


def standardise(xs: list[float]) -> list[float]:
    m, sd = statistics.fmean(xs), statistics.pstdev(xs)
    return [(x - m) / sd if sd > 0 else 0.0 for x in xs]


def relation_stats(pairs: list[tuple[str, float, float]]) -> dict:
    """pairs: (day, predictor, forward return)."""
    if len(pairs) < 60:
        return {"n": len(pairs)}
    xs = standardise([p for _, p, _ in pairs])
    ys = [r * 1e4 for _, _, r in pairs]
    res = ols(ys, [[x] for x in xs], nw_lags=NW_LAGS)
    out = {"n": len(pairs), "beta_bp": res["beta"][1], "t": res["t"][1], "eras": {}}
    for name, a, b in ERAS:
        sub = [(d, p, r) for d, p, r in pairs if a <= d <= b]
        if len(sub) >= 60:
            sx = standardise([p for _, p, _ in sub])
            r2 = ols([r * 1e4 for _, _, r in sub], [[x] for x in sx], nw_lags=NW_LAGS)
            out["eras"][name] = {"n": len(sub), "beta_bp": r2["beta"][1], "t": r2["t"][1]}
    return out


def rule(pairs: list[tuple[str, float, float]], sign: int, h: int, cost_bp: float = COST_BP) -> dict:
    """Top tercile -> sign, bottom tercile -> -sign, held h days, one at a time."""
    if len(pairs) < 60:
        return {"n": 0}
    first_half = pairs[: len(pairs) // 2]
    vs = sorted(p for _, p, _ in first_half)
    lo, hi = vs[len(vs) // 3], vs[2 * len(vs) // 3]
    trades, busy = [], None
    for i, (d, p, r) in enumerate(pairs):
        if busy is not None and i < busy:
            continue
        side = sign if p >= hi else -sign if p <= lo else 0
        if side == 0:
            continue
        trades.append((d, side * r * 1e4 - cost_bp))
        busy = i + h
    if len(trades) < 20:
        return {"n": len(trades)}
    nets = [x for _, x in trades]
    half = trades[len(trades) // 2][0]
    a = [x for d, x in trades if d < half]
    b = [x for d, x in trades if d >= half]
    sd = statistics.pstdev(nets)
    return {"n": len(nets), "net_bp": statistics.fmean(nets), "t": statistics.fmean(nets) / (sd / math.sqrt(len(nets))) if sd > 0 else 0.0,
            "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
            "first_half_bp": statistics.fmean(a) if a else None, "second_half_bp": statistics.fmean(b) if b else None,
            "per_year_pct": statistics.fmean(nets) * len(nets) / max(1.0, (dt.date.fromisoformat(trades[-1][0]) - dt.date.fromisoformat(trades[0][0])).days / 365) / 100}


def run(state: Path, start: str = "2017-01-01") -> dict:
    out = {"relations": {}, "trials": 0}
    for name, (pid, kind, window), tgt, sign in RELATIONS:
        try:
            pred = predictor(_series(state, pid), kind, window)
            days, logpx = target_returns(state, tgt)
        except Exception as exc:                      # noqa: BLE001
            out["relations"][name] = {"error": str(exc)}
            continue
        rel = {"target": tgt, "sign": sign, "horizons": {}}
        for h in HORIZONS:
            fwd = forward(days, logpx, h)
            pairs = [(d, pv, fwd[d]) for d in days if d >= start and d in fwd for pv in [prior_value(pred, d)] if pv is not None]
            st = relation_stats(pairs)
            st["rule"] = rule(pairs, sign, h)
            rel["horizons"][h] = st
            out["trials"] += 1 + (1 if st["rule"].get("n") else 0)
        rel["verdict"] = judge(rel)
        out["relations"][name] = rel
    out["candidates"] = [n for n, r in out["relations"].items() if r.get("verdict", ("",))[0] == "candidate"]
    out["verdict"] = ("inconclusive", "no candidate") if not out["candidates"] else ("candidate", ", ".join(out["candidates"]))
    return out


def judge(rel: dict) -> tuple[str, str]:
    """Written before running: candidate if full-sample |t| >= 2.5 with the
    literature's sign, |t| >= 1.5 with that sign in both latest eras, and
    the rule net positive in both halves, at the 5- or 20-day horizon;
    killed if the rule is net negative at every horizon."""
    sign = rel["sign"]
    nets = [h["rule"].get("net_bp") for h in rel["horizons"].values() if h.get("rule", {}).get("n")]
    for h in (5, 20):
        st = rel["horizons"].get(h) or {}
        if not st.get("n"):
            continue
        ok_full = sign * st["t"] >= 2.5
        eras = st.get("eras", {})
        ok_eras = all(sign * eras.get(e, {}).get("t", 0.0) >= 1.5 for e in ("2021-2023", "2024-2026"))
        r = st["rule"]
        ok_rule = bool(r.get("n")) and r["net_bp"] > 0 and (r.get("first_half_bp") or 0) > 0 and (r.get("second_half_bp") or 0) > 0
        if ok_full and ok_eras and ok_rule:
            return "candidate", f"{h}d: t {st['t']:+.1f}, rule {r['net_bp']:+.0f} bp/trade"
    if nets and all(n < 0 for n in nets):
        return "killed", "rule net negative at every horizon"
    best = max(((h, st) for h, st in rel["horizons"].items() if st.get("n")), key=lambda x: abs(x[1]["t"]), default=None)
    return "inconclusive", (f"best |t| {best[1]['t']:+.1f} at {best[0]}d" if best else "no data")


def render(res: dict) -> str:
    o = ["macro relations as leads, 2017-2026, predictor as of the prior close, 8 bp a round trip"]
    for name, rel in res["relations"].items():
        if "error" in rel:
            o.append(f"  {name:28s} ERROR {rel['error']}"); continue
        v, why = rel["verdict"]
        o.append(f"  {name:28s} [{v}] {why}")
        for h, st in rel["horizons"].items():
            if not st.get("n"):
                continue
            eras = " ".join(f"{e[:4]}-{e[-2:]}:{x['t']:+.1f}" for e, x in st.get("eras", {}).items())
            r = st["rule"]
            rl = (f"rule {r['net_bp']:+.0f} bp/trade (t {r['t']:+.1f}, n {r['n']}, halves {r['first_half_bp']:+.0f}/{r['second_half_bp']:+.0f}, {r['per_year_pct']:+.1f}%/yr)"
                  if r.get("n") else "rule n/a")
            o.append(f"      {h:2d}d: n {st['n']:5d} beta {st['beta_bp']:+6.1f} bp/sd  t {st['t']:+.1f}  eras {eras}  | {rl}")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    a = ap.parse_args(argv)
    print(render(run(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
