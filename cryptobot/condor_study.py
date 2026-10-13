"""`ibit-iron-condor-monthly`: the volatility premium in the one options
structure that fits a $1,000 account.

Sell the 25-delta call and put 30 days out, buy the 10-delta call and
put, hold to expiry, no hedging: the worst case is the wing width less
the credit, and that is the capital at risk. Priced with Black-Scholes
at DVOL on the entry day (flat skew, the known bias), settled on BTC's
terminal close; entered when 30-day implied exceeds 20-day realised by
the gate (5 points registered; none and 10 as sensitivities), one at a
time. Costs: 2.5% half-spread a leg on the premium and 0.65 USD a
contract on 100 IBIT shares (about 1.4 bp of notional a leg).

    python -m cryptobot.condor_study --state state [--short-delta 0.25 --wing-delta 0.10]
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import statistics
from pathlib import Path
from typing import Optional

from . import stats as S
from .vrp_study import ANNUAL, RV_DAYS, TENOR_DAYS, Closes, bs, gate_open, load, wing_strikes

GEOMETRIES = ((0.25, 0.10), (0.30, 0.15), (0.20, 0.05))     # (short delta, wing delta)
GATES = (5.0, None, 10.0)
HALF_SPREAD = 0.025
COMMISSION_FRAC = 0.00014


def condor_trades(iv: dict, px: Closes, gate: Optional[float], short_delta: float = 0.25, wing_delta: float = 0.10,
                  tenor: int = TENOR_DAYS, half_spread: float = HALF_SPREAD, commission_frac: float = COMMISSION_FRAC) -> list[dict]:
    trades, busy_until = [], None
    for d in sorted(iv):
        if (busy_until and d <= busy_until) or d.weekday() >= 5 or d not in px:
            continue
        rv20 = px.realised(d, RV_DAYS)
        if not gate_open(iv[d], rv20, gate):
            continue
        expiry = px.expiry_after(d, tenor)
        if expiry is None:
            continue
        S0, sigma, tau = px[d], iv[d], (expiry - d).days / ANNUAL
        Kc_s, Kp_s = wing_strikes(S0, sigma, tau, short_delta)       # the strangle sold
        Kc_w, Kp_w = wing_strikes(S0, sigma, tau, wing_delta)        # the wings bought
        c_s, _, _ = bs(S0, Kc_s, sigma, tau)
        _, p_s, _ = bs(S0, Kp_s, sigma, tau)
        c_w, _, _ = bs(S0, Kc_w, sigma, tau)
        _, p_w, _ = bs(S0, Kp_w, sigma, tau)
        credit = (c_s + p_s) * (1 - half_spread) - (c_w + p_w) * (1 + half_spread) - 4 * commission_frac * S0
        width = min(Kc_w - Kc_s, Kp_s - Kp_w)
        capital = width - credit
        if capital <= 0:
            continue
        ST = px[expiry]
        payoff = max(ST - Kc_s, 0.0) - max(ST - Kc_w, 0.0) + max(Kp_s - ST, 0.0) - max(Kp_w - ST, 0.0)
        pnl = credit - payoff
        trades.append({"entry": d, "exit": expiry, "iv": sigma * 100, "rv20": (rv20 or 0) * 100,
                       "credit_pct": credit / S0 * 100, "width_pct": width / S0 * 100, "move_pct": (ST / S0 - 1) * 100,
                       "pnl_pct_notional": pnl / S0 * 100, "pnl": pnl / capital * 100,
                       "outcome": "max" if payoff == 0 else "partial" if payoff < width else "wiped"})
        busy_until = expiry
    return trades


def monthly(trades: list[dict], first: dt.date, last: dt.date) -> list[float]:
    by: dict[str, float] = {}
    m = first.replace(day=1)
    while m <= last:
        by[m.strftime("%Y-%m")] = 0.0
        m = (m + dt.timedelta(days=32)).replace(day=1)
    for t in trades:
        by[t["entry"].strftime("%Y-%m")] = by.get(t["entry"].strftime("%Y-%m"), 0.0) + t["pnl"]
    return [by[k] for k in sorted(by)]


def summarize(trades: list[dict], first: dt.date, last: dt.date) -> dict:
    xs = monthly(trades, first, last)
    if not trades:
        return {"trades": 0, "months": len(xs)}
    sd = statistics.pstdev(xs) if len(xs) > 2 else 0.0
    cum, peak, mdd = 0.0, 0.0, 0.0
    for v in xs:
        cum += v
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    by_year: dict[int, float] = {}
    for t in trades:
        by_year[t["entry"].year] = by_year.get(t["entry"].year, 0.0) + t["pnl"]
    return {"trades": len(trades), "months": len(xs), "mean_trade": statistics.fmean(t["pnl"] for t in trades),
            "win": statistics.fmean(1.0 if t["pnl"] > 0 else 0.0 for t in trades),
            "credit_pct": statistics.fmean(t["credit_pct"] for t in trades), "width_pct": statistics.fmean(t["width_pct"] for t in trades),
            "outcomes": {k: sum(1 for t in trades if t["outcome"] == k) for k in ("max", "partial", "wiped")},
            "mean_month": statistics.fmean(xs), "sharpe": statistics.fmean(xs) / sd * math.sqrt(12) if sd > 0 else 0.0,
            "psr": S.psr(xs) if len(xs) > 2 else 0.0, "max_drawdown": mdd, "worst_month": min(xs), "total": cum,
            "by_year": by_year, "net_2024_on": sum(v for y, v in by_year.items() if y >= 2024), "monthly": xs}


def run(iv: dict, px: Closes) -> dict:
    first, last = min(iv), max(iv)
    out = {"first": first, "last": last, "variants": {}}
    for sd_, wd in GEOMETRIES:
        for g in GATES:
            name = f"{int(sd_*100)}/{int(wd*100)} delta, gate {'none' if g is None else int(g)}"
            out["variants"][name] = summarize(condor_trades(iv, px, g, sd_, wd), first, last)
    out["trials"] = len(out["variants"])
    srs = [v["sharpe"] for v in out["variants"].values() if v.get("trades")]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    for v in out["variants"].values():
        if v.get("trades"):
            v["dsr"] = S.dsr(v["monthly"], out["trials"], var_sr)
    out["registered"] = "25/10 delta, gate 5"
    out["verdict"] = passes(out["variants"][out["registered"]])
    return out


def passes(s: dict) -> tuple[str, str]:
    """Written before running: alive if net Sharpe >= 0.7, PSR >= 0.95, DSR
    >= 0.95 at 9 trials, worst month better than -60% of the capital at
    risk and 2024-2026 net positive; killed if net at or below zero."""
    if not s.get("trades"):
        return "inconclusive", "no trades"
    if s["mean_month"] <= 0:
        return "killed", f"net {s['mean_month']:+.1f}% a month of capital at risk"
    if s["sharpe"] >= 0.7 and s["psr"] >= 0.95 and s.get("dsr", 0) >= 0.95 and s["worst_month"] > -60 and s["net_2024_on"] > 0:
        return "alive", "clears the bar"
    return "inconclusive", (f"Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}, DSR {s.get('dsr', 0):.2f}, "
                            f"worst month {s['worst_month']:+.0f}%, 2024 on {s['net_2024_on']:+.0f}%")


def render(res: dict) -> str:
    o = [f"IBIT iron condor, monthly, unhedged, DVOL {res['first']} .. {res['last']}; returns in % of the capital at risk (wing width less credit)"]
    for name, s in res["variants"].items():
        if not s.get("trades"):
            o.append(f"  {name:26s} no trades"); continue
        yrs = " ".join(f"{y}:{v:+.0f}" for y, v in sorted(s["by_year"].items()))
        o.append(f"  {name:26s} {s['trades']:3d} trades, credit {s['credit_pct']:.1f}% of spot on a {s['width_pct']:.1f}% width, "
                 f"win {s['win']*100:.0f}% ({s['outcomes']['max']} max/{s['outcomes']['partial']} partial/{s['outcomes']['wiped']} wiped), "
                 f"per month {s['mean_month']:+.1f}%, Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}, DSR {s.get('dsr', 0):.2f}, "
                 f"worst {s['worst_month']:+.0f}%, max DD {s['max_drawdown']:+.0f}% | {yrs}" + ("   <- registered" if name == res["registered"] else ""))
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why}); {res['trials']} trials")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    a = ap.parse_args(argv)
    iv, px = load(a.state)
    if not iv or not len(px):
        print("no DVOL/BTC rows (python -m cryptobot.vrp_study --state state --fetch)")
        return 1
    print(render(run(iv, px)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
