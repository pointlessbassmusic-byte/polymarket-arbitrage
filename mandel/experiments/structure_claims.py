"""
Library structure claims evaluated with the model-priced engine (mandel/experiments/structures.py).
Each entry restates the claim's pass rule in code; ``_verdict`` from underlying2 applies the shared rule (an implemented criterion
failing -> not_supported; a criterion not implemented caps the verdict at inconclusive). Verdicts are for the MODEL-PRICED proxy the
claim itself names, with the smile calibrated on the captured quote days stated in every reason.
"""

from __future__ import annotations

import numpy as np

from mandel.experiments.structures import Smile, metric, run_structure
from mandel.experiments.underlying2 import _mean_ci, _sharpe_diff_lower, _verdict

STRADDLE = [("call", "long", 1, 1.0), ("put", "long", 1, 1.0)]
FLATS = (0.81, 0.90, 1.00)


def _flip(legs):
    return [(k, "short" if s == "long" else "long", q, x) for k, s, q, x in legs]


class Ctx:
    def __init__(self, days, closes, vix, rates, smile_rows):
        self.days, self.closes, self.vix, self.rates = days, closes, vix, rates
        self.smile = Smile(smile_rows); self._cache = {}

    def run(self, legs, mode, dte=30, hold=21):
        key = (tuple(legs), mode, dte, hold)
        if key not in self._cache:
            self._cache[key] = run_structure(self.days, self.closes, self.vix, self.rates, legs, dte, hold, mode, self.smile)
        return self._cache[key]

    def m(self, legs, mode, kind, dte=30, hold=21):
        return metric(self.run(legs, mode, dte, hold), kind)


def _ci(x):
    return _mean_ci(x, 6)


def _fmt(name, x):
    lo, hi = _ci(x); return f"{name} mean {x.mean()*100:+.1f}% (95% CI {lo*100:+.1f} to {hi*100:+.1f})"


def evaluate(cid: str, c: Ctx) -> dict:
    SM = ("smile", 1.0)
    crit, parts = [], []
    def upper_lt0(name, x):
        lo, hi = _ci(x); crit.append((f"{name}: upper CI < 0", hi < 0)); parts.append(_fmt(name, x))
    def lower_gt0(name, x):
        lo, hi = _ci(x); crit.append((f"{name}: lower CI > 0", lo > 0)); parts.append(_fmt(name, x))
    if cid == "T-100":
        for s in FLATS:
            upper_lt0(f"s={s}", c.m(STRADDLE, ("flat", s), "per_premium"))
    elif cid == "T-102":
        upper_lt0("smile", c.m([("put", "long", 1, 0.95), ("call", "long", 1, 1.05)], SM, "per_premium")); crit.append(("SKEW-scaled put sensitivity", None))
    elif cid in ("T-104", "T-105"):
        fly = [("call", "long", 1, 0.95), ("call", "short", 2, 1.0), ("call", "long", 1, 1.05)]
        if cid == "T-104":
            lower_gt0("smile", c.m(fly, SM, "per_premium")); lower_gt0("s=0.90", c.m(fly, ("flat", 0.9), "per_premium"))
        else:
            upper_lt0("smile", c.m(_flip(fly), SM, "per_max_loss"))
    elif cid in ("T-106", "T-107"):
        ifly = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("call", "long", 1, 1.05), ("put", "long", 1, 0.95)]
        if cid == "T-106":
            lower_gt0("smile", c.m(ifly, SM, "per_max_loss")); lower_gt0("s=0.90", c.m(ifly, ("flat", 0.9), "per_max_loss"))
        else:
            upper_lt0("smile", c.m(_flip(ifly), SM, "per_premium")); upper_lt0("s=0.90", c.m(_flip(ifly), ("flat", 0.9), "per_premium"))
    elif cid in ("T-109", "T-110"):
        ic = [("put", "long", 1, 0.92), ("put", "short", 1, 0.95), ("call", "short", 1, 1.05), ("call", "long", 1, 1.08)]
        if cid == "T-109":
            lower_gt0("smile", c.m(ic, SM, "per_max_loss", 45, 31))
        else:
            upper_lt0("smile", c.m(_flip(ic), SM, "per_premium", 45, 31))
    elif cid == "T-114":
        bl = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("call", "long", 1, 1.02)]
        lower_gt0("smile", c.m(bl, SM, "per_max_loss")); lower_gt0("s=0.90", c.m(bl, ("flat", 0.9), "per_max_loss"))
    elif cid in ("T-115", "T-116"):
        strip = [("call", "long", 1, 1.0), ("put", "long", 2, 1.0)]; strap = [("call", "long", 2, 1.0), ("put", "long", 1, 1.0)]
        for s in FLATS:
            if cid == "T-115":
                upper_lt0(f"strip-straddle s={s}", c.m(strip, ("flat", s), "per_premium") - c.m(STRADDLE, ("flat", s), "per_premium"))
            else:
                lower_gt0(f"strap-strip s={s}", c.m(strap, ("flat", s), "per_premium") - c.m(strip, ("flat", s), "per_premium"))
    elif cid == "T-124":
        w = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("put", "long", 1, 0.90), ("call", "long", 1, 1.10)]
        lower_gt0("smile", c.m(w, SM, "per_max_loss")); lower_gt0("wings x1.5", c.m(w, ("smile", 1.5), "per_max_loss"))
    elif cid == "T-125":
        for s in (1.0, 0.9):
            upper_lt0(f"s={s}", c.m([("call", "long", 1, 1.0)], ("flat", s), "per_premium"))
    elif cid == "T-126":
        for s in (1.0, 0.9):
            upper_lt0(f"put-call s={s}", c.m([("put", "long", 1, 1.0)], ("flat", s), "per_premium") - c.m([("call", "long", 1, 1.0)], ("flat", s), "per_premium"))
    elif cid == "T-127":
        call = c.m([("call", "short", 1, 1.05)], ("flat", 1.0), "per_spot"); put = c.m([("put", "short", 1, 0.95)], ("flat", 1.0), "per_spot")
        obs, lo = _sharpe_diff_lower(put, call, 12, 6, q=0.05)
        crit.append(("Sharpe(put) > Sharpe(call), one-sided p < 0.05", lo > 0)); parts.append(f"Sharpe put minus call {obs:+.2f} (one-sided 95% lower {lo:+.2f})")
        lower_gt0("short call", call)
    elif cid in ("T-129", "T-130"):
        bcs = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05)]; bps = [("put", "long", 1, 1.0), ("put", "short", 1, 0.95)]
        if cid == "T-129":
            sp = c.m(bcs, ("flat", 1.0), "per_premium"); upper_lt0("bull call spread", sp)
            lower_gt0("spread - long call", sp - c.m([("call", "long", 1, 1.0)], ("flat", 1.0), "per_premium"))
        else:
            sp = c.m(bps, ("flat", 1.0), "per_premium"); upper_lt0("bear put spread", sp)
            upper_lt0("bear put - bull call", sp - c.m(bcs, ("flat", 1.0), "per_premium"))
    elif cid == "T-131":
        legs = [("put", "short", 1, 0.95), ("put", "long", 1, 0.90)]
        res = c.run(legs, ("flat", 1.0)); x = metric(res, "per_max_loss"); lower_gt0("bull put spread", x)
        win = float((res["pnl"] > 0).mean()); credit = np.median(-res["debit"]); worst = -res["pnl"].min()
        crit.append(("win rate > 0.85", win > 0.85)); crit.append(("worst loss > 10x median credit", worst / credit > 10))
        parts.append(f"win rate {win:.2f}, worst/median credit {worst/credit:.1f}")
    elif cid == "T-132":
        x = c.m([("call", "short", 1, 1.03), ("call", "long", 1, 1.06)], ("flat", 1.0), "per_max_loss")
        lo, hi = _ci(x); crit.append(("upper CI <= 0", hi <= 0)); parts.append(_fmt("bear call spread", x))
    elif cid == "T-134":
        legs = [("put", "short", 1, 1.0), ("put", "long", 2, ("delta", -0.25))]
        res = c.run(legs, ("flat", 1.0)); x = metric(res, "per_spot"); upper_lt0("all months", x)
        low = x[res["vix"] < 15]; lower_gt0(f"VIX<15 (n={low.size})", low)
    elif cid == "T-517":
        legs = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]
        x = c.m(legs, ("flat", 1.0), "per_spot"); lower_gt0("seagull", x)
        h = len(x) // 2; crit.append(("mean > 0 in both halves", x[:h].mean() > 0 and x[h:].mean() > 0)); parts.append(f"halves {x[:h].mean()*100:+.2f}%/{x[h:].mean()*100:+.2f}%")
    else:
        raise KeyError(cid)
    v, why = _verdict(crit)
    n = len(c.run(STRADDLE, ("flat", 1.0))["pnl"])
    return {"n_cycles": n, "smile_quote_days": c.smile.n_days, "verdict": v,
            "reason": "MODEL-PRICED proxy (smile from " + f"{c.smile.n_days} quote days, held fixed in shape): " + "; ".join(parts) + f" — {why}"}


CLAIMS = ["T-100", "T-102", "T-104", "T-105", "T-106", "T-107", "T-109", "T-110", "T-114", "T-115", "T-116", "T-124", "T-125", "T-126",
          "T-127", "T-129", "T-130", "T-131", "T-132", "T-134", "T-517"]
