"""
Library structure claims evaluated with the model-priced engine (mandel/experiments/structures.py).
Each entry restates the claim's pass rule in code; ``_verdict`` from underlying2 applies the shared rule (an implemented criterion
failing -> not_supported; a criterion not implemented caps the verdict at inconclusive). Verdicts are for the MODEL-PRICED proxy the
claim itself names, with the smile calibrated on the captured quote days stated in every reason.
CIs are 95% circular block bootstraps (block 6 cycles): studentized (bootstrap-t, Bartlett HAC s.e.) for the claims whose
trial.statistic names a studentized CI (STUDENTIZED), percentile otherwise. n_cycles is the shortest full-sample series a
criterion actually tests (in the claim's own cycles); below trial.min_n (MIN_N) a pass cannot confirm and only a decisive
failure (CI wholly on the wrong side of zero) can decide.
"""

from __future__ import annotations

import math

import numpy as np

from mandel.experiments.structures import Q, Smile, metric, run_structure
from mandel.experiments.underlying2 import _mean_ci, _sharpe_diff_lower, _verdict
from mandel.validation.backtest_eval import _hac_var

STRADDLE = [("call", "long", 1, 1.0), ("put", "long", 1, 1.0)]
FLATS = (0.81, 0.90, 1.00)
# Claims whose trial.statistic names a studentized block-bootstrap CI (registry.json).
STUDENTIZED = {"T-100", "T-102", "T-104", "T-106", "T-109", "T-115", "T-124", "T-125"}
# trial.min_n per claim (registry.json), in the claim's own units: non-overlapping cycles of the claim's tenor.
MIN_N = {"T-100": 390, "T-102": 390, "T-104": 390, "T-105": 390, "T-106": 390, "T-107": 390, "T-109": 260, "T-110": 260,
         "T-114": 390, "T-115": 390, "T-116": 390, "T-124": 390, "T-125": 300, "T-126": 300, "T-127": 300, "T-129": 300,
         "T-130": 300, "T-131": 300, "T-132": 300, "T-134": 300, "T-517": 300}


def _flip(legs):
    return [(k, "short" if s == "long" else "long", q, x) for k, s, q, x in legs]


class Ctx:
    def __init__(self, days, closes, vix, rates, smile_rows):
        self.days, self.closes, self.vix, self.rates = days, closes, vix, rates
        self.smile = Smile(smile_rows); self._cache = {}

    def run(self, legs, mode, dte=30, hold=21, q=Q):
        key = (tuple(legs), mode, dte, hold, q)
        if key not in self._cache:
            self._cache[key] = run_structure(self.days, self.closes, self.vix, self.rates, legs, dte, hold, mode, self.smile, q=q)
        return self._cache[key]

    def m(self, legs, mode, kind, dte=30, hold=21, q=Q):
        return metric(self.run(legs, mode, dte, hold, q), kind)


def _ci(x):
    return _mean_ci(x, 6)


def _ci_t(x, block=6, n_boot=2000, seed=0):
    """Studentized (bootstrap-t) circular block-bootstrap 95% CI of the mean. Each resample's mean is studentized by its own
    Bartlett long-run s.e. (bandwidth = block, the studentization of backtest_eval.block_bootstrap_pvalue) and the t quantiles
    are inverted, so a right-skewed series (long-option payoffs) gets the long right tail a percentile interval misses."""
    x = np.asarray(x, float); n = x.size
    if n < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed); nb = math.ceil(n / block)
    starts = np.stack([rng.integers(0, n, nb) for _ in range(n_boot)])          # same draw order as _mean_ci
    xb = x[((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]) % n]
    m0, s0 = float(x.mean()), math.sqrt(float(_hac_var(x[None, :], block)[0]) / n)
    t = (xb.mean(axis=1) - m0) / np.sqrt(_hac_var(xb, block) / n)
    return m0 - float(np.quantile(t, 0.975)) * s0, m0 - float(np.quantile(t, 0.025)) * s0


def _fmt(name, x, lo, hi):
    return f"{name} mean {x.mean()*100:+.1f}% (95% CI {lo*100:+.1f} to {hi*100:+.1f})"


def evaluate(cid: str, c: Ctx) -> dict:
    SM = ("smile", 1.0)
    ci = _ci_t if cid in STUDENTIZED else _ci
    crit, parts, sizes, decisive = [], [], [], {}
    def _ci_crit(name, x, label, ok_fn, wrong_side_fn, full):
        """A CI criterion; full=False marks a conditional subsample (not counted against trial.min_n)."""
        lo, hi = ci(x); finite = bool(np.isfinite(lo) and np.isfinite(hi))
        decisive[len(crit)] = finite and wrong_side_fn(lo, hi)                 # CI wholly on the wrong side of zero
        crit.append((f"{name}: {label}", ok_fn(lo, hi) if finite else None)); parts.append(_fmt(name, x, lo, hi))
        if full:
            sizes.append(int(np.asarray(x).size))
    def upper_lt0(name, x, full=True):
        _ci_crit(name, x, "upper CI < 0", lambda lo, hi: hi < 0, lambda lo, hi: lo > 0, full)
    def lower_gt0(name, x, full=True):
        _ci_crit(name, x, "lower CI > 0", lambda lo, hi: lo > 0, lambda lo, hi: hi < 0, full)
    if cid == "T-100":
        for s in FLATS:                                                           # controls: q = 0 in pricing
            upper_lt0(f"s={s}", c.m(STRADDLE, ("flat", s), "per_premium", q=0.0))
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
        lower_gt0("smile", c.m(bl, SM, "per_max_loss"))
        st = c.run(bl[:2], ("flat", 0.9)); cl = c.run(bl[2:], SM)        # procedure: straddle at s*VIX, +2% call at VIX x r(1.02)
        ml = np.maximum(st["spot"] + st["debit"] + cl["debit"], 1e-9)     # downside max loss at S_T = 0: K_put - net credit
        lower_gt0("s=0.90 (call at VIX x r(1.02))", (st["pnl"] + cl["pnl"]) / ml)
    elif cid in ("T-115", "T-116"):
        strip = [("call", "long", 1, 1.0), ("put", "long", 2, 1.0)]; strap = [("call", "long", 2, 1.0), ("put", "long", 1, 1.0)]
        for s in FLATS:
            if cid == "T-115":
                upper_lt0(f"strip-straddle s={s}", c.m(strip, ("flat", s), "per_premium") - c.m(STRADDLE, ("flat", s), "per_premium"))
            else:
                lower_gt0(f"strap-strip s={s}", c.m(strap, ("flat", s), "per_premium") - c.m(strip, ("flat", s), "per_premium"))
    elif cid == "T-124":
        w = [("call", "short", 1, 1.0), ("put", "short", 1, 1.0), ("put", "long", 1, 0.90), ("call", "long", 1, 1.10)]
        base = c.run(w, SM); lower_gt0("smile", metric(base, "per_max_loss"))
        wings = c.run([("put", "long", 1, 0.90)], SM)["debit"] + c.run([("call", "long", 1, 1.10)], SM)["debit"]
        for mult in (1.5, 2.0):                         # wing-PRICE multipliers: extra debit paid, max loss up by the same amount
            extra = (mult - 1.0) * wings; x = (base["pnl"] - extra) / (base["max_loss"] + extra)
            if mult == 1.5:
                lower_gt0("wing prices x1.5", x)
            else:
                lo, hi = ci(x); parts.append(_fmt("wing prices x2.0 (sensitivity, not in the pass rule)", x, lo, hi))
    elif cid == "T-125":
        for q in (0.0, 0.018):                          # procedure: run q = 0 and q = 1.8%; the pass rule must hold under each
            for s in (1.0, 0.9):
                upper_lt0(f"s={s} q={q:.1%}", c.m([("call", "long", 1, 1.0)], ("flat", s), "per_premium", q=q))
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
        _ci_crit("bear call spread", x, "upper CI <= 0", lambda lo, hi: hi <= 0, lambda lo, hi: lo > 0, True)
    elif cid == "T-134":
        legs = [("put", "short", 1, 1.0), ("put", "long", 2, ("delta", -0.25))]
        res = c.run(legs, ("flat", 1.0)); x = metric(res, "per_spot"); upper_lt0("all months", x)
        low = x[res["vix"] < 15]; lower_gt0(f"VIX<15 (n={low.size})", low, full=False)   # trial.min_n counts all months
    elif cid == "T-517":
        legs = [("call", "long", 1, 1.0), ("call", "short", 1, 1.05), ("put", "short", 1, ("zero_cost_put",))]
        res = c.run(legs, ("flat", 1.0)); x = metric(res, "per_spot"); lower_gt0("seagull", x)
        bad = int((~res["zero_cost_ok"]).sum())
        crit.append(("net premium zero in every cycle", True if bad == 0 else None))   # otherwise not the claim's zero-cost trade
        if bad:
            parts.append(f"{bad} cycles with no zero-cost put strike in [0.5 S, 1.5 S]")
        h = len(x) // 2; crit.append(("mean > 0 in both halves", x[:h].mean() > 0 and x[h:].mean() > 0)); parts.append(f"halves {x[:h].mean()*100:+.2f}%/{x[h:].mean()*100:+.2f}%")
    else:
        raise KeyError(cid)
    n, mn = min(sizes), MIN_N[cid]                      # the series actually tested, in the claim's own cycles
    if n < mn:                                          # below trial.min_n only a decisive failure decides; a pass cannot confirm
        crit = [(nm, None if ok is not None and not bool(ok) and not decisive.get(i, False) else ok) for i, (nm, ok) in enumerate(crit)]
    crit.append((f"n >= trial min_n ({n} of {mn} cycles)", True if n >= mn else None))
    v, why = _verdict(crit)
    kind = "studentized" if cid in STUDENTIZED else "percentile"
    return {"n_cycles": n, "min_n": mn, "ci": f"{kind} block bootstrap, block 6", "smile_quote_days": c.smile.n_days, "verdict": v,
            "reason": "MODEL-PRICED proxy (smile from " + f"{c.smile.n_days} quote days, held fixed in shape; {n} cycles, trial min_n {mn}; "
                      f"{kind} block-bootstrap CIs): " + "; ".join(parts) + f" — {why}"}


CLAIMS = ["T-100", "T-102", "T-104", "T-105", "T-106", "T-107", "T-109", "T-110", "T-114", "T-115", "T-116", "T-124", "T-125", "T-126",
          "T-127", "T-129", "T-130", "T-131", "T-132", "T-134", "T-517"]
