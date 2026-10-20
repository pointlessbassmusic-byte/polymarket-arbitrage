"""
Model-priced option structures on SPY with a captured smile.
============================================================

One engine for the library's single-expiry structure claims. Each cycle prices every leg by Black-Scholes at entry and settles
at intrinsic value on the SPY close at expiry. Entries (house rule 10, no arbitrary grid phase):
  * default: the non-overlapping ``hold``-day grid from the first valid day (one of its ``hold`` phases; kept for callers
    that pick their own phase);
  * ``step=1``: an entry on every valid day, i.e. every phase of that grid pooled (cycle ``k + j*hold`` of the result is
    phase k's j-th cycle);
  * ``schedule``: explicit (entry day, expiry day) cycles, e.g. ``monthly_cycles`` (the standard monthly expiry calendar);
    each cycle is priced at its own T = calendar days to expiry / 365.
Pricing modes:
  * ``("flat", s)``: every leg at sigma = s * VIX / 100 (the claims' ATM-scale grid, s in {0.81, 0.90, 1.00});
  * ``("smile", m)``: sigma(K) = VIX/100 * r(K/S) where r is the captured SPY smile (IV/VIX on the quote date, averaged over all
    ``spy-smile-*`` bundles, nearest of the 30- and 45-day shapes), flat beyond the captured grid; ``m`` scales the IV-ratio
    DEVIATION FROM ATM beyond +/- 7% moneyness, r -> r(1) + (r - r(1)) * m (1.0 = as captured). It is not a wing-PRICE
    multiplier (a call wing below the ATM ratio gets cheaper as m rises); claims that register wing-price multipliers apply
    them to the leg prices in structure_claims.
The smile shape is held fixed through history and only its level moves with VIX: that is the stated proxy and its main
limitation. Every result is labelled MODEL-PRICED. Rates from the 3-month bill; q defaults to 1.5% (SPY's long-run yield,
approximate) and a claim that registers its own q passes it in.
A ``("zero_cost_put",)`` strike is solved on [0.5 S, 1.5 S] so that net premium is zero; ``zero_cost_ok`` is False for a cycle
whose bracket holds no root (the trade then is not zero-cost).
"""

from __future__ import annotations

import bisect
import math
from datetime import date, timedelta
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
        """IV / VIX at moneyness m. wing_mult != 1 scales the deviation of the ratio from the ATM ratio beyond +/- 7%
        moneyness (not the wing price, and not the ratio itself)."""
        t = min(self.curves, key=lambda x: abs(x - dte))
        ks, rs = self.curves[t]
        base = float(np.interp(m, ks, rs))                        # flat beyond the captured grid
        if wing_mult != 1.0 and abs(m - 1.0) > 0.07:
            atm = float(np.interp(1.0, ks, rs)); base = atm + (base - atm) * wing_mult
        return base


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7 + 14)


def monthly_expiries(days) -> list:
    """Standard monthly option expiries inside the trading calendar ``days``: the third Friday of each month, or the prior
    session when that Friday is not a trading day (a holiday such as Good Friday)."""
    ds = [str(d) for d in days]
    if not ds:
        return []
    y, m = int(ds[0][:4]), int(ds[0][5:7]); out = []
    while (y, m) <= (int(ds[-1][:4]), int(ds[-1][5:7])):
        tf = third_friday(y, m).isoformat()
        if ds[0] <= tf <= ds[-1]:
            e = ds[bisect.bisect_right(ds, tf) - 1]                       # the session on or before the third Friday
            if not out or e != out[-1]:
                out.append(e)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def monthly_cycles(days) -> list:
    """The monthly roll on the standard expiry calendar: each cycle enters at the close of one monthly expiry and settles at
    the next (27-35 calendar days later)."""
    e = monthly_expiries(days)
    return list(zip(e[:-1], e[1:]))


def _rate_on_or_before(rates: dict, rate_days: list, d: str) -> float:
    """rates[d], else the latest print before d (rate_days = sorted(rates)); no print on or before d raises, as max() did."""
    if d in rates:
        return rates[d]
    i = bisect.bisect_right(rate_days, d) - 1
    if i < 0:
        raise ValueError(f"no rate on or before {d}")
    return rates[rate_days[i]]


def run_structure(days, closes, vix: dict, rates: dict, legs, dte: int, hold: int, mode: tuple, smile: Optional[Smile] = None,
                  start: str = "1993-01-01", q: float = Q, step: Optional[int] = None, schedule=None) -> dict:
    """legs: list of (kind, side, qty, strike_spec) with strike_spec = moneyness float, ('delta', d), or ('zero_cost_put',).
    Entries: every ``step`` valid days (default ``hold``: the non-overlapping grid from the first valid day; 1: every phase of
    that grid pooled), or the (entry day, expiry day) pairs of ``schedule`` (dte and hold then come from each pair).
    Returns per-cycle arrays: day (entry), exit, debit (+ paid / - received), payoff, pnl, max_loss (>0), spot, vix, zero_cost_ok."""
    if schedule is not None:
        pos = {str(d): i for i, d in enumerate(days)}
        cycles = [(pos[e], pos[x], (date.fromisoformat(x) - date.fromisoformat(e)).days / 365.0)
                  for e, x in schedule if e >= start and e in vix and e in pos and x in pos and x > e]
    else:
        idx = [i for i, d in enumerate(days) if d >= start and d in vix]
        cycles = []
        for i in range(0, len(idx), hold if step is None else step):
            if idx[i] + hold >= len(days):
                break
            cycles.append((idx[i], idx[i] + hold, dte / 365.0))
    out = {k: [] for k in ("day", "exit", "debit", "payoff", "pnl", "max_loss", "spot", "vix", "strikes", "zero_cost_ok")}
    rate_days = sorted(rates)
    for a, b, T in cycles:
        d = days[a]; S = float(closes[a]); S1 = float(closes[b]); V = vix[d] / 100
        r = math.log(1 + _rate_on_or_before(rates, rate_days, d) / 100) if rates else 0.0
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
        zc_ok = True
        if any(k is None and l[0] != "underlying" for k, l in zip(strikes, legs)):          # solve the zero-cost put strike
            fixed = sum((1 if l[1] == "long" else -1) * l[2] * p for l, p in zip(legs, prices) if p is not None)
            j = next(n for n, k in enumerate(strikes) if k is None and legs[n][0] != "underlying")
            sgn = 1 if legs[j][1] == "long" else -1                       # a put's price rises with K: a short put's net debit falls
            net = lambda K: fixed + sgn * legs[j][2] * float(bs.price(S, K, T, r, sig(K), "put", q))
            lo, hi = 0.5 * S, 1.5 * S                                     # the zero-cost strike can sit above spot (low VIX, high bills)
            zc_ok = (net(lo) > 0) != (net(hi) > 0)                        # no sign change: no zero-cost strike in the bracket
            for _ in range(60):
                mid = (lo + hi) / 2; tot = net(mid)
                lo, hi = (mid, hi) if (tot > 0) == (sgn < 0) else (lo, mid)
            strikes[j] = (lo + hi) / 2; prices[j] = float(bs.price(S, strikes[j], T, r, sig(strikes[j]), "put", q))
        debit = sum((1 if l[1] == "long" else -1) * l[2] * p for l, p in zip(legs, prices))
        def pay(x):
            tot = 0.0
            for (kind, side, qty, _), K in zip(legs, strikes):
                v = (x - S) if kind == "underlying" else (max(x - K, 0) if kind == "call" else max(K - x, 0))
                tot += (1 if side == "long" else -1) * qty * v
            return tot
        grid = np.linspace(0.0, 2.0 * S, 801); pnl_grid = np.zeros_like(grid)
        for (kind, side, qty, _), K in zip(legs, strikes):                # pay() on the whole grid, same terms in the same order
            v = (grid - S) if kind == "underlying" else (np.maximum(grid - K, 0) if kind == "call" else np.maximum(K - grid, 0))
            pnl_grid += (1 if side == "long" else -1) * qty * v
        pnl_grid = pnl_grid - debit
        out["day"].append(d); out["exit"].append(days[b]); out["debit"].append(debit); out["payoff"].append(pay(S1)); out["pnl"].append(pay(S1) - debit)
        out["max_loss"].append(max(-pnl_grid.min(), 1e-9)); out["spot"].append(S); out["vix"].append(vix[d]); out["strikes"].append(list(strikes)); out["zero_cost_ok"].append(bool(zc_ok))
    return {k: (np.array(v) if k not in ("day", "exit", "strikes") else v) for k, v in out.items()}


def metric(res: dict, kind: str) -> np.ndarray:
    if kind == "per_premium":
        return res["pnl"] / np.abs(res["debit"])
    if kind == "per_max_loss":
        return res["pnl"] / res["max_loss"]
    if kind == "per_spot":
        return res["pnl"] / res["spot"]
    raise ValueError(kind)
