"""
Model-priced option structures on SPY with a captured smile.
============================================================

One engine for the library's single-expiry structure claims. Each cycle (non-overlapping) prices every leg by Black-Scholes
at entry and settles at intrinsic value on the SPY close at expiry. Pricing modes:
  * ``("flat", s)``: every leg at sigma = s * VIX / 100 (the claims' ATM-scale grid, s in {0.81, 0.90, 1.00});
  * ``("smile", m)``: sigma(K) = VIX/100 * r(K/S) where r is the captured SPY smile (IV/VIX on the quote date, averaged over all
    ``spy-smile-*`` bundles, nearest of the 30- and 45-day shapes), flat beyond the captured grid; ``m`` multiplies the wing
    ratios beyond +/- 7% moneyness (1.0 = as captured; 1.5 and 2.0 are the claims' SKEW-range sensitivities).
The smile shape is held fixed through history and only its level moves with VIX: that is the stated proxy and its main
limitation. Every result is labelled MODEL-PRICED. Rates from the 3-month bill, q = 1.5% (SPY's long-run yield, approximate).
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from mandel.options import bs
from mandel.experiments.underlying2 import _mean_ci

Q = 0.015


class Smile:
    def __init__(self, smile_rows):
        acc: dict[int, dict[float, list]] = {30: {}, 45: {}}
        for r in smile_rows:
            v = r["value"]
            for k, x in v["ratio"].items():
                acc.setdefault(v["target_dte"], {}).setdefault(float(k), []).append(x)
        self.curves = {}
        for t, d in acc.items():
            if d:
                ks = np.array(sorted(d)); self.curves[t] = (ks, np.array([np.mean(d[k]) for k in ks]))
        self.n_days = len({r["value"]["quote_date"] for r in smile_rows})

    def ratio(self, m: float, dte: int, wing_mult: float = 1.0) -> float:
        t = min(self.curves, key=lambda x: abs(x - dte))
        ks, rs = self.curves[t]
        base = float(np.interp(m, ks, rs))                        # flat beyond the captured grid
        if wing_mult != 1.0 and abs(m - 1.0) > 0.07:
            atm = float(np.interp(1.0, ks, rs)); base = atm + (base - atm) * wing_mult
        return base


def run_structure(days, closes, vix: dict, rates: dict, legs, dte: int, hold: int, mode: tuple, smile: Optional[Smile] = None,
                  start: str = "1993-01-01", q: float = Q) -> dict:
    """legs: list of (kind, side, qty, strike_spec) with strike_spec = moneyness float, ('delta', d), or ('zero_cost_put',).
    Returns per-cycle arrays: debit (+ paid / - received), payoff, pnl, max_loss (>0), spot, vix."""
    T = dte / 365.0
    idx = [i for i, d in enumerate(days) if d >= start and d in vix]
    out = {k: [] for k in ("day", "debit", "payoff", "pnl", "max_loss", "spot", "vix", "strikes")}
    i = 0
    while i < len(idx):
        a = idx[i]
        if a + hold >= len(days):
            break
        d = days[a]; S = float(closes[a]); S1 = float(closes[a + hold]); V = vix[d] / 100
        r = math.log(1 + rates.get(d, rates[max(k for k in rates if k <= d)]) / 100) if rates else 0.0
        def sig(K):
            if mode[0] == "flat":
                return max(mode[1] * V, 0.01)
            return max(V * smile.ratio(K / S, dte, mode[1]), 0.01)
        strikes, prices = [], []
        for kind, side, qty, spec in legs:
            if kind == "underlying":
                strikes.append(None); prices.append(0.0); continue
            if isinstance(spec, tuple) and spec[0] == "delta":
                K = bs.strike_for_delta(S, T, r, V, spec[1], kind, q)
            elif isinstance(spec, tuple) and spec[0] == "zero_cost_put":
                K = None
            else:
                K = S * float(spec)
            strikes.append(K); prices.append(None if K is None else float(bs.price(S, K, T, r, sig(K), kind, q)))
        if any(k is None and l[0] != "underlying" for k, l in zip(strikes, legs)):          # solve the zero-cost put strike
            fixed = sum((1 if l[1] == "long" else -1) * l[2] * p for l, p in zip(legs, prices) if p is not None)
            j = next(n for n, k in enumerate(strikes) if k is None and legs[n][0] != "underlying")
            lo, hi = 0.5 * S, S
            for _ in range(60):
                mid = (lo + hi) / 2; pm = float(bs.price(S, mid, T, r, sig(mid), "put", q))
                tot = fixed + (1 if legs[j][1] == "long" else -1) * legs[j][2] * pm
                lo, hi = (mid, hi) if tot > 0 else (lo, mid)
            strikes[j] = (lo + hi) / 2; prices[j] = float(bs.price(S, strikes[j], T, r, sig(strikes[j]), "put", q))
        debit = sum((1 if l[1] == "long" else -1) * l[2] * p for l, p in zip(legs, prices))
        def pay(x):
            tot = 0.0
            for (kind, side, qty, _), K in zip(legs, strikes):
                v = (x - S) if kind == "underlying" else (max(x - K, 0) if kind == "call" else max(K - x, 0))
                tot += (1 if side == "long" else -1) * qty * v
            return tot
        grid = np.linspace(0.0, 2.0 * S, 801)
        pnl_grid = np.array([pay(x) for x in grid]) - debit
        out["day"].append(d); out["debit"].append(debit); out["payoff"].append(pay(S1)); out["pnl"].append(pay(S1) - debit)
        out["max_loss"].append(max(-pnl_grid.min(), 1e-9)); out["spot"].append(S); out["vix"].append(vix[d]); out["strikes"].append(list(strikes))
        i += hold
    return {k: (np.array(v) if k not in ("day", "strikes") else v) for k, v in out.items()}


def metric(res: dict, kind: str) -> np.ndarray:
    if kind == "per_premium":
        return res["pnl"] / np.abs(res["debit"])
    if kind == "per_max_loss":
        return res["pnl"] / res["max_loss"]
    if kind == "per_spot":
        return res["pnl"] / res["spot"]
    raise ValueError(kind)
