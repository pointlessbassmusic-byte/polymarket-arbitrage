"""
Batch 6, directional and ratio structures: jade lizard, 1x2 call ratio, 1-3-2 Christmas tree, stock repair, SKEW-timed risk
reversal, LEAPS and deep-ITM calls as stock substitutes, ZEBRA and 3%-OTM digital puts on SPY.
==========================================================================================================================

Nine options-library claims (T-113, T-133, T-135, T-136, T-138, T-139, T-140, T-154, T-516), each tested on its own claim,
trial.pass and trial.min_n. Every result is MODEL-PRICED: legs are priced by Black-Scholes at the IV proxy the claim names
(VIX/100 flat, or VIX3M/100 where the claim asks for it), never at traded quotes. The archive holds only two captured chain
days, so no traded version can be tested here; where the economics hinge on the IV level the reason reports the result at
IV scales 0.81 and 0.90 (the captured ATM IV / VIX ratio was about 0.81 on 2026-10-14) and says a traded test needs chain
history. The scales are sensitivities, never criteria: the verdict is for the claim's own proxy (scale 1.00).

Conventions (house rules).
  * Prices: SPY RAW closes (``close``, split-adjusted, not dividend-adjusted) for strikes and settlement. Cash dividends come
    from the step in the adjclose/close ratio on each ex-date: D = close(day before) * (1 - ratio(day before) / ratio(day)).
    SPY goes ex on the third Friday of Mar/Jun/Sep/Dec. When an ex-date falls inside an option's life (after the entry close,
    on or before the expiry close) the option is priced on the escrowed-dividend forward: Black-Scholes with spot
    S - PV(D) and q = 0. The amounts are the realised ones, treated as known at entry (SPY's schedule is fixed and the amount
    passes through dividends the constituents have declared); the error is a few basis points of spot per year.
  * Holding SPY (T-139, T-140, T-154) is total return (adjclose), the same dividend convention as the forward pricing.
  * Rates: FRED DTB3 is a discount yield published the next day, so a decision on day d uses the latest print dated before d,
    converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365). Bills accrue day by day at the rate known at the
    start of each day.
  * IV and SKEW: CBOE index closes, known at the close of their day, used at that close. VIX3M starts on 2009-09-18 in the
    archive; claims that ask for VIX3M (T-136, T-139) use VIX before that and say so.
  * Monthly cycles: non-overlapping 21-trading-day holds from the first SPY day (1993-01-29), entered at a close and settled
    at the close 21 sessions later; T = calendar days to that close / 365. A session without an IV print uses the last print
    (known at that close). Annual cycles hold 252 sessions; stock-repair episodes hold 63.

Statistics. CIs are 95% two-sided circular block bootstraps (2000 resamples, seed 0) of the statistic the claim names:
percentile unless the trial names a studentized interval (T-136, T-138: bootstrap-t with a Bartlett long-run s.e.). Monthly
cycles use blocks of 6 cycles; overlapping windows use blocks at least as long as the overlap (12 monthly-staggered annual
cycles for T-139; 21 days for T-140's daily returns, one roll cycle). Differences are bootstrapped PAIRED on one timeline
(a per-cycle difference series, or for top-minus-bottom SKEW quintiles a resample of whole months with their labels).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented ->
at best inconclusive; supported only when every criterion is implemented and passes. Below trial.min_n (in the claim's own
units) the verdict is never supported, and a failing criterion counts only when its interval lies wholly on the wrong side.

Why not ``structures.run_structure``: it prices with a constant q, the same-day DTB3 print and r = ln(1 + d), which the house
rules replace (dividend forward, prior print, discount-yield conversion). This module keeps its cycle logic but prices the
legs with ``mandel.options.bs`` and settles them with ``mandel.options.payoff.Position``.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.structure_claims import _ci_t
from mandel.experiments.underlying2 import _mdd, _mean_ci, _verdict
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.options.payoff import Leg, Position
from mandel.validation.backtest_eval import _hac_var

MONTH = 21                     # trading days per monthly cycle
YEAR = 252                     # trading days per annual cycle; equity annualisation
QUARTER = 63                   # stock-repair horizon and re-arm gap
BLOCK = 6                      # bootstrap block for monthly cycles
N_BOOT = 2000
SCALES = (0.81, 0.90)          # IV-scale sensitivities (not criteria)
START = "1993-01-01"
MODEL = "MODEL-PRICED, no transaction costs (none stated in the claim)"


# ------------------------------------------------------------------------------------------------ data access --

_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except KeyError:
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str):
    """Rows of a bundle that were available when the bundle was captured."""
    e = archive.get(name)
    cap = getattr(e, "created_at", None) if e is not None else None
    return (r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))


def _index(archive, name: str) -> dict:
    return _cached(archive, ("index", name), lambda: index_closes(_rows(archive, name)))


def _prices(archive, symbol: str):
    """(days, raw closes, adjcloses) of daily-history-<symbol>; a missing adjclose carries the previous adj/close ratio."""
    def load():
        name = "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = v.get("close")
            if c is None or not float(c) > 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float("nan"))
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, close, adj
    return _cached(archive, ("px", symbol), load)


# --------------------------------------------------------------------------------------------- market panel --

def cont_rate(discount_pct: float) -> float:
    """Continuous rate from a 3-month bill discount yield in percent (FRED DTB3)."""
    return -math.log(1.0 - discount_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def dividends_from_adj(close, adj, tol: float = 1e-4, cap: float = 0.05) -> np.ndarray:
    """Cash dividend D[i] going ex on day i, from the adjclose/close ratio step: D = close[i-1] * (1 - ratio[i-1]/ratio[i]).
    Steps under ``tol`` are rounding and steps over ``cap`` are data errors."""
    close = np.asarray(close, float); ratio = np.asarray(adj, float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if np.isfinite(ratio[i]) and np.isfinite(ratio[i - 1]) and ratio[i] > 0:
            y = 1.0 - ratio[i - 1] / ratio[i]
            if tol < y < cap:
                out[i] = close[i - 1] * y
    return out


def iv_series(days: Sequence[str], primary: dict, fallback: Optional[dict] = None) -> np.ndarray:
    """IV (fraction) per day: ``primary`` from its first print on (carrying its last print over a missing day), ``fallback``
    before that (carried the same way). NaN until the first print."""
    first = min(primary) if primary else None
    out = np.full(len(days), np.nan); last_p = last_f = float("nan")
    for i, d in enumerate(days):
        if fallback is not None and d in fallback:
            last_f = float(fallback[d])
        if d in primary:
            last_p = float(primary[d])
        use_p = fallback is None or (first is not None and d >= first)
        out[i] = (last_p if use_p else last_f) / 100.0
    return out


@dataclass
class Market:
    days: list
    close: np.ndarray          # raw closes
    adj: np.ndarray            # total-return closes
    div: np.ndarray            # cash dividend going ex on day i (0 otherwise)
    cal: np.ndarray            # calendar day ordinal
    rate: np.ndarray           # continuous bill rate known at day i's close (latest DTB3 print dated before day i)
    ex_idx: list

    def pv_div(self, a: int, b: int, r: float) -> float:
        """PV at day a of the dividends going ex in (a, b]."""
        lo, hi = bisect.bisect_right(self.ex_idx, a), bisect.bisect_right(self.ex_idx, b)
        return float(sum(self.div[k] * math.exp(-r * (self.cal[k] - self.cal[a]) / 365.0) for k in self.ex_idx[lo:hi]))

    def pv_div_path(self, t: np.ndarray, b: int) -> np.ndarray:
        """PV at each day t (t <= b) of the dividends going ex in (t, b], each discounted at rate[t]."""
        out = np.zeros(t.size)
        lo, hi = bisect.bisect_right(self.ex_idx, int(t.min())), bisect.bisect_right(self.ex_idx, b)
        for k in self.ex_idx[lo:hi]:
            m = t < k
            out[m] += self.div[k] * np.exp(-self.rate[t[m]] * (self.cal[k] - self.cal[t[m]]) / 365.0)
        return out


def make_market(days: Sequence[str], close, adj, bills: dict) -> Market:
    """``bills`` = {day: DTB3 discount yield in percent}."""
    days = list(days); close = np.asarray(close, float); adj = np.asarray(adj, float)
    div = dividends_from_adj(close, adj)
    bd = sorted(bills); bv = [cont_rate(float(bills[d])) for d in bd]
    rate = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        j = bisect.bisect_left(bd, d) - 1                       # latest print dated strictly before d
        if j >= 0:
            rate[i] = bv[j]
    cal = np.array([date.fromisoformat(d).toordinal() for d in days], float)
    return Market(days, close, adj, div, cal, rate, [int(i) for i in np.nonzero(div > 0)[0]])


def cycle_entries(m: Market, iv: np.ndarray, hold: int, start: str = START, step: Optional[int] = None) -> list:
    """Non-overlapping entry indices (each ``step`` sessions after the previous, default ``hold``) from ``start``; a day
    without an IV or a rate is skipped and the next day enters."""
    step = step or hold
    n = len(m.days); i = bisect.bisect_left(m.days, start); out = []
    while i + hold < n:
        if np.isfinite(iv[i]) and iv[i] > 0 and np.isfinite(m.rate[i]):
            out.append(i); i += step
        else:
            i += 1
    return out


def cycle_panel(m: Market, iv: np.ndarray, hold: int = MONTH, start: str = START, entries: Optional[list] = None) -> dict:
    """Per-cycle arrays: a (entry index), b (expiry index), day, S (raw close), F (S - PV of dividends in the life), ST (raw
    close at expiry), T (years), r, sig (IV at entry), tr (SPY total-return factor over the cycle)."""
    a = np.array(entries if entries is not None else cycle_entries(m, iv, hold, start), int)
    b = a + hold
    r = m.rate[a]
    S = m.close[a]
    F = S - np.array([m.pv_div(int(x), int(y), float(z)) for x, y, z in zip(a, b, r)])
    return {"a": a, "b": b, "day": [m.days[i] for i in a], "S": S, "F": F, "ST": m.close[b],
            "T": (m.cal[b] - m.cal[a]) / 365.0, "r": r, "sig": iv[a], "tr": m.adj[b] / m.adj[a], "n": int(a.size)}


# -------------------------------------------------------------------------------------------- pricing helpers --

def _px(F, K, T, r, sig, kind):
    return np.asarray(bs.price(F, K, T, r, sig, kind, 0.0), float)


def _strikes_for_delta(P: dict, sig, delta: float, kind: str) -> np.ndarray:
    return np.array([bs.strike_for_delta(f, t, r, s, delta, kind, 0.0) for f, t, r, s in zip(P["F"], P["T"], P["r"], sig)])


def _ncdf(x):
    return np.asarray(bs._ncdf(x), float)


def _d2(F, K, T, r, sig):
    return (np.log(F / K) + (r - 0.5 * sig ** 2) * T) / (sig * np.sqrt(T))


def settle(legs: list, ST) -> np.ndarray:
    """Payoff at expiry per cycle. legs: list of (kind, side, qty, strikes array); payoff via payoff.Position."""
    ST = np.asarray(ST, float); out = np.empty(ST.size)
    for j in range(ST.size):
        pos = Position([Leg(k, s, q, strike=float(K[j])) for k, s, q, K in legs])
        out[j] = float(pos.payoff(ST[j]))
    return out


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple:
    """Exact two-sided binomial CI."""
    def cdf(kk, p):
        if kk < 0:
            return 0.0
        if p <= 0:
            return 1.0
        if p >= 1:
            return 1.0 if kk >= n else 0.0
        lp, lq = math.log(p), math.log1p(-p)
        return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                            for i in range(0, kk + 1)))
    def solve(f, target):
        lo, hi = 0.0, 1.0                                   # f decreasing in p
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: -(1 - cdf(k - 1, p)), -alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p), alpha / 2)
    return lower, upper


# ------------------------------------------------------------------------------------------------ statistics --

def _ci(x, block: int = BLOCK, n_boot: int = N_BOOT) -> tuple:
    x = np.asarray(x, float)
    if x.size < 2:
        return float("nan"), float("nan")
    return _mean_ci(x, block, n_boot)


def _ci_stud(x, block: int = BLOCK, n_boot: int = N_BOOT) -> tuple:
    x = np.asarray(x, float)
    if x.size < 3:
        return float("nan"), float("nan")
    return _ci_t(x, block, n_boot)


def ci_t_group_diff(x, g1, g2, block: int = BLOCK, n_boot: int = N_BOOT, seed: int = 0) -> tuple:
    """Studentized circular block bootstrap of mean(x | g1) - mean(x | g2) on one timeline: resample whole periods with their
    group labels; each resample is studentized by the Bartlett long-run s.e. of its influence series
    (x - m1)/p1 on g1, -(x - m2)/p2 on g2, 0 elsewhere. Returns (difference, lower, upper)."""
    x = np.asarray(x, float); g1 = np.asarray(g1, bool); g2 = np.asarray(g2, bool); n = x.size
    def est(xs, a, b):
        if a.sum() < 2 or b.sum() < 2:
            return float("nan"), float("nan")
        p1, p2 = a.mean(), b.mean(); m1, m2 = xs[a].mean(), xs[b].mean()
        infl = np.where(a, (xs - m1) / p1, 0.0) - np.where(b, (xs - m2) / p2, 0.0)
        return float(m1 - m2), math.sqrt(float(_hac_var(infl[None, :], block)[0]) / n)
    d0, s0 = est(x, g1, g2)
    if not np.isfinite(d0):
        return d0, float("nan"), float("nan")
    rng = np.random.default_rng(seed); nb = math.ceil(n / block); ts, ds = [], []
    for _ in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        d, s = est(x[idx], g1[idx], g2[idx])
        if np.isfinite(d):
            ds.append(d)
            if s > 1e-12:
                ts.append((d - d0) / s)
    if not s0 > 1e-12 or len(ts) < 0.9 * n_boot:              # degenerate (no within-group spread): percentile interval
        return d0, float(np.quantile(ds, 0.025)), float(np.quantile(ds, 0.975))
    t = np.array(ts)
    return d0, d0 - float(np.quantile(t, 0.975)) * s0, d0 - float(np.quantile(t, 0.025)) * s0


class Criteria:
    """Criteria with the min_n rule: below min_n a failing criterion stands only when it fails decisively."""

    def __init__(self):
        self.items, self.decisive = [], []

    def add(self, name: str, ok, decisive: bool = False):
        self.items.append((name, None if ok is None else bool(ok))); self.decisive.append(bool(decisive))

    def ci(self, name: str, lo, hi, side: str, thr: float = 0.0):
        """side 'lower_gt': pass if lo > thr (decisive failure if hi < thr); 'upper_lt': pass if hi < thr (decisive if lo > thr)."""
        if not (np.isfinite(lo) and np.isfinite(hi)):
            self.add(name, None); return
        if side == "lower_gt":
            self.add(name, lo > thr, hi < thr)
        else:
            self.add(name, hi < thr, lo > thr)

    def finish(self, n: int, min_n: int, unit: str) -> tuple:
        crit = list(self.items)
        if n < min_n:
            crit = [(nm, None if (ok is not None and not ok and not dec) else ok) for (nm, ok), dec in zip(crit, self.decisive)]
        crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
        return _verdict(crit)


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


def _p(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _rng(lo, hi, nd: int = 3) -> str:
    return f"95% CI {_p(lo, nd)} to {_p(hi, nd)}"


def _halves(x) -> tuple:
    x = np.asarray(x, float); h = x.size // 2
    return (float(x[:h].mean()) if h else float("nan"), float(x[h:].mean()) if x.size - h else float("nan"))


def _sens(fn, key: str = "x") -> dict:
    out = {}
    for s in SCALES:
        v = np.asarray(fn(s)[key], float)
        out[f"{s:.2f}"] = float(v.mean()) if v.size else None
    return out


def _sens_txt(sens: dict, nd: int = 3) -> str:
    return ", ".join(f"s={k} {_p(v, nd)}" for k, v in sens.items())


# ----------------------------------------------------------------------------------------- T-113 jade lizard --

def jade_lizard(P: dict, scale: float = 1.0, width: float = 0.01, delta: float = 0.30, margin: float = 0.20) -> dict:
    """Short `delta` put + short `delta` call + long call `width`*S above it, at scale*IV. Enter only when the credit >= width*S.
    x = P&L at expiry (credit carried at r) / (margin * S) over entered cycles."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    Kp = _strikes_for_delta(P, sig, -delta, "put"); Kc = _strikes_for_delta(P, sig, delta, "call"); Kl = Kc + width * S
    credit = _px(F, Kp, T, r, sig, "put") + _px(F, Kc, T, r, sig, "call") - _px(F, Kl, T, r, sig, "call")
    enter = credit >= width * S
    payoff = settle([("put", "short", 1, Kp), ("call", "short", 1, Kc), ("call", "long", 1, Kl)], P["ST"])
    pnl = credit * np.exp(r * T) + payoff
    return {"x": (pnl / (margin * S))[enter], "enter": enter, "credit": credit / S, "Kp": Kp / S, "Kc": Kc / S,
            "days": [d for d, e in zip(P["day"], enter) if e], "n_total": int(S.size), "n_skipped": int((~enter).sum())}


def eval_jade_lizard(P: dict, min_n: int = 250, n_boot: int = N_BOOT) -> dict:
    res = jade_lizard(P); x = res["x"]; n = int(x.size)
    lo, hi = _ci(x, BLOCK, n_boot); h1, h2 = _halves(x)
    c = Criteria()
    c.ci("mean P&L / (0.2 S) lower CI > 0", lo, hi, "lower_gt")
    c.add("mean positive in both walk-forward halves", (h1 > 0 and h2 > 0) if n >= 2 else None)
    v, why = c.finish(n, min_n, "entered months")
    sens = _sens(lambda s: jade_lizard(P, s))
    reason = (f"{MODEL} (legs at VIX IV flat, 30-delta strikes solved at that IV on the dividend forward, r = prior DTB3 print): "
              f"SPY 1-month jade lizard, {n} entered of {res['n_total']} monthly cycles {P['day'][0] if P['n'] else ''} to "
              f"{P['day'][-1] if P['n'] else ''} ({res['n_skipped']} skipped with credit < 1% of S; median credit "
              f"{_p(float(np.median(res['credit'])) if res['credit'].size else float('nan'), 2)} of S); mean P&L / (0.2 S) {_p(x.mean() if n else float('nan'))} "
              f"({_rng(lo, hi)}, block-{BLOCK} percentile); walk-forward halves {_p(h1)} / {_p(h2)}; IV-scale sensitivity "
              f"(not in the pass rule; short premium, so the edge hinges on the IV level and a traded test needs chain history): "
              f"{_sens_txt(sens)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_total_months": res["n_total"], "n_skipped": res["n_skipped"],
            "mean_per_margin": float(x.mean()) if n else None, "ci": [lo, hi], "halves": [h1, h2],
            "median_credit_per_spot": float(np.median(res["credit"])) if res["credit"].size else None,
            "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ---------------------------------------------------------------------------------------- T-133 1x2 call ratio --

def zero_cost_k2(F, K1, T, r, sig) -> float:
    """K2 > K1 with 2 C(K2) = C(K1) (bisection on [K1, 4 K1])."""
    target = float(bs.price(F, K1, T, r, sig, "call")) / 2.0
    lo, hi = K1, 4.0 * K1
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if float(bs.price(F, mid, T, r, sig, "call")) > target else (lo, mid)
    return (lo + hi) / 2


def ratio_1x2(P: dict, scale: float = 1.0) -> dict:
    """Long 1 ATM call (K1 = S), short 2 at the zero-cost K2; x = P&L / S at expiry."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = S.copy(); K2 = np.array([zero_cost_k2(f, k, t, rr, s) for f, k, t, rr, s in zip(F, K1, T, r, sig)])
    net = _px(F, K1, T, r, sig, "call") - 2 * _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 1, K1), ("call", "short", 2, K2)], P["ST"])
    return {"x": (payoff - net * np.exp(r * T)) / S, "K2": K2 / S, "vix": P["sig"] * 100}


def tail_frequency(x, mult: float = 3.0, all_months: bool = False) -> dict:
    """Months with a loss larger than ``mult`` x the median gain (median P&L of the winning months; ``all_months`` uses the
    median P&L of every month instead, reported as a reading check), with a Clopper-Pearson CI."""
    x = np.asarray(x, float); gains = x if all_months else x[x > 0]
    if gains.size == 0 or not np.median(gains) > 0:
        return {"median_gain": None, "k": 0, "n": int(x.size), "freq": None, "ci": [None, None]}
    mg = float(np.median(gains)); k = int((x < -mult * mg).sum()); lo, hi = clopper_pearson(k, x.size)
    return {"median_gain": mg, "k": k, "n": int(x.size), "freq": k / x.size, "ci": [lo, hi]}


def eval_ratio_1x2(P: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    res = ratio_1x2(P); x = res["x"]; n = int(x.size)
    lo, hi = _ci(x, BLOCK, n_boot); tf = tail_frequency(x); tf_all = tail_frequency(x, all_months=True)
    c = Criteria()
    c.ci("mean P&L / S lower CI > 0", lo, hi, "lower_gt")
    if tf["freq"] is None:
        c.add("tail frequency lower CI > 3%", None)
    else:
        c.ci("frequency of losses > 3x median gain: lower CI > 3%", tf["ci"][0], tf["ci"][1], "lower_gt", 0.03)
    v, why = c.finish(n, min_n, "months")
    terc = {}
    if n >= 3:
        q1, q2 = np.quantile(res["vix"], [1 / 3, 2 / 3])
        for nm, msk in (("low", res["vix"] <= q1), ("mid", (res["vix"] > q1) & (res["vix"] <= q2)), ("high", res["vix"] > q2)):
            t = tail_frequency(x[msk]) if msk.any() else {"freq": None}
            terc[nm] = {"n": int(msk.sum()), "mean": float(x[msk].mean()) if msk.any() else None, "tail_freq": t["freq"]}
    sens = _sens(lambda s: ratio_1x2(P, s))
    reason = (f"{MODEL} (all legs at VIX IV flat, K2 solved for zero cost each month on the dividend forward): SPY 1-month 1x2 "
              f"call ratio, {n} monthly cycles; median K2 {_p(float(np.median(res['K2'])) - 1 if n else float('nan'), 2)} above spot; "
              f"mean P&L / S {_p(x.mean() if n else float('nan'))} ({_rng(lo, hi)}, block-{BLOCK} percentile); median gain "
              f"{_p(tf['median_gain'])}, losses > 3x it in {tf['k']} of {n} months = {_p(tf['freq'], 2)} (Clopper-Pearson "
              f"{_rng(tf['ci'][0], tf['ci'][1], 2)}; needs lower > 3%); reading check (report only): with the median of all months "
              f"({_p(tf_all['median_gain'])}) as the base, {_p(tf_all['freq'], 2)} (CI {_p(tf_all['ci'][0], 2)} to {_p(tf_all['ci'][1], 2)}); "
              f"by VIX tercile (mean, tail freq): "
              + ", ".join(f"{k} {_p(t['mean'])}/{_p(t['tail_freq'], 1)}" for k, t in terc.items())
              + f"; IV-scale sensitivity of the mean (not in the pass rule; a traded test needs chain history): {_sens_txt(sens)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "mean_per_spot": float(x.mean()) if n else None, "ci": [lo, hi],
            "tail": tf, "tail_all_month_median": tf_all, "by_vix_tercile": terc, "median_k2_moneyness": float(np.median(res["K2"])) if n else None,
            "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------ T-135 Christmas tree --

def christmas_tree(P: dict, scale: float = 1.0, w: float = 0.025, anchor: float = 1.0) -> dict:
    """1-3-2 call tree: long 1 at A = anchor*S, short 3 at A + 2w, long 2 at A + 3w (w = 2.5% of S). Profit zone
    [K1 + D, K4 - D/2] (D = debit); hit = 1{zone holds the expiry close}; rn = N(d2(L)) - N(d2(U)) from the same lognormal."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = anchor * S; K3 = K1 + 2 * w * S; K4 = K1 + 3 * w * S
    D = _px(F, K1, T, r, sig, "call") - 3 * _px(F, K3, T, r, sig, "call") + 2 * _px(F, K4, T, r, sig, "call")
    L, U = K1 + D, K4 - D / 2
    ok = U > L
    rn = np.where(ok, _ncdf(_d2(F, L, T, r, sig)) - _ncdf(_d2(F, np.maximum(U, L), T, r, sig)), 0.0)
    hit = ((P["ST"] > L) & (P["ST"] < U)).astype(float)
    return {"x": hit - rn, "hit": hit, "rn": rn, "debit": D / S, "L": L / S, "U": U / S}


def eval_christmas_tree(P: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    res = christmas_tree(P); x = res["x"]; n = int(x.size)
    lo, hi = _ci(x, BLOCK, n_boot)
    c = Criteria(); c.ci("hit rate - RN probability: lower CI > 0", lo, hi, "lower_gt")
    v, why = c.finish(n, min_n, "months")
    itm = christmas_tree(P, anchor=0.975); lo_i, hi_i = _ci(itm["x"], BLOCK, n_boot)
    sens = _sens(lambda s: christmas_tree(P, s))
    reason = (f"{MODEL} (4 strikes at VIX IV flat, dividend forward; zone and RN probability from the same lognormal): SPY 1-month "
              f"1-3-2 call tree, ATM anchor, w = 2.5%, {n} monthly cycles; median zone [{_p(float(np.median(res['L'])) - 1 if n else float('nan'), 2)}, "
              f"{_p(float(np.median(res['U'])) - 1 if n else float('nan'), 2)}] around spot; hit rate {_p(res['hit'].mean() if n else float('nan'), 1)} vs mean RN "
              f"{_p(res['rn'].mean() if n else float('nan'), 1)}: hit - RN {_p(x.mean() if n else float('nan'), 2)} ({_rng(lo, hi, 2)}, block-{BLOCK} percentile); "
              f"ITM anchor (A = 0.975 S, report only) hit - RN {_p(itm['x'].mean() if n else float('nan'), 2)} ({_rng(lo_i, hi_i, 2)}); hit - RN at IV scales "
              f"(not in the pass rule): {_sens_txt(sens, 2)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "hit_rate": float(res["hit"].mean()) if n else None,
            "rn_mean": float(res["rn"].mean()) if n else None, "diff": float(x.mean()) if n else None, "ci": [lo, hi],
            "itm_anchor": {"diff": float(itm["x"].mean()) if n else None, "ci": [lo_i, hi_i]},
            "median_debit_per_spot": float(np.median(res["debit"])) if n else None, "iv_scale_sensitivity": sens,
            "model_priced": True, "min_n": min_n}


# ---------------------------------------------------------------------------------------- T-136 stock repair --

def drawdown_episodes(close, trigger: float = 0.10, look: int = YEAR, rearm: int = QUARTER, hold: int = QUARTER,
                      new_crossing: bool = True) -> list:
    """(entry index, trailing high) for the first day of each >= trigger drawdown from the trailing ``look``-day high
    (inclusive of the day). Primary rule (``new_crossing=True``): an episode starts only when the drawdown newly crosses
    -trigger after having been above it since the last episode, with a ``rearm``-session lockout on top.
    ``new_crossing=False`` is the looser level trigger (robustness only): it re-fires every ``rearm`` sessions while the
    drawdown is still at or below -trigger, i.e. inside a drawdown already under way. Episodes whose ``hold`` window runs
    past the data are dropped."""
    c = np.asarray(close, float); n = c.size; out = []; next_ok = 0; recovered = True
    if n < look:
        return out
    hi = np.lib.stride_tricks.sliding_window_view(c, look).max(axis=1)          # hi[j] = max(c[j : j + look])
    for i in range(look - 1, n - hold):
        H = hi[i - look + 1]; dd = c[i] / H - 1
        if dd > -trigger:
            recovered = True
        if i >= next_ok and dd <= -trigger and (recovered or not new_crossing):
            out.append((i, float(H))); next_ok = i + rearm; recovered = False
    return out


def drawdown_refires(close, episodes: list, trigger: float = 0.10, look: int = YEAR) -> tuple:
    """(re-fires, spells with re-fires, distinct spells hit): an episode is a re-fire when it falls inside a continuous spell of
    drawdown <= -trigger (from the trailing ``look``-day high) that already holds an earlier episode."""
    c = np.asarray(close, float)
    if c.size < look or not episodes:
        return 0, 0, 0
    hi = np.lib.stride_tricks.sliding_window_view(c, look).max(axis=1)
    below = np.zeros(c.size, bool); below[look - 1:] = c[look - 1:] / hi - 1 <= -trigger
    spell = np.cumsum(np.r_[below[0], below[1:] & ~below[:-1]])                   # spell id, constant within a run
    counts: dict = {}
    for i, _ in episodes:
        counts[int(spell[i])] = counts.get(int(spell[i]), 0) + 1
    return sum(v - 1 for v in counts.values()), sum(1 for v in counts.values() if v > 1), len(counts)


def stock_repair(m: Market, iv: np.ndarray, episodes: list, hold: int = QUARTER, scale: float = 1.0) -> dict:
    """Stock + long 1 ATM call + short 2 calls at K2 = (B + S)/2; x = (repair - hold) P&L / S = the embedded 1x2 call ratio."""
    a = np.array([e[0] for e in episodes], int)
    if a.size == 0:
        return {"x": np.array([]), "net": np.array([]), "days": [], "k2": np.array([])}
    B = np.array([e[1] for e in episodes]); P = cycle_panel(m, iv, hold, entries=list(a))
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = S.copy(); K2 = (B + S) / 2
    net = _px(F, K1, T, r, sig, "call") - 2 * _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 1, K1), ("call", "short", 2, K2)], P["ST"])
    return {"x": (payoff - net * np.exp(r * T)) / S, "net": net / S, "days": P["day"], "k2": K2 / S}


def eval_stock_repair(m: Market, iv: np.ndarray, min_n: int = 30, n_boot: int = N_BOOT, block: int = 2,
                      second: Optional[tuple] = None, iv_note: str = "") -> dict:
    """Primary episodes: the first day each >= 10% drawdown newly crosses -10% (63-session lockout on top); min_n counts those
    drawdown episodes. The 63-session level-trigger re-arm (re-fires inside a continuing drawdown) is a robustness check.
    ``second`` = (label, Market, iv) for the QQQ sample (reported, not a criterion)."""
    eps = drawdown_episodes(m.close, new_crossing=True); res = stock_repair(m, iv, eps); x = res["x"]; n = int(x.size)
    lo, hi = _ci_stud(x, block, n_boot)
    c = Criteria(); c.ci("mean (repair - hold) / S lower CI > 0", lo, hi, "lower_gt")
    v, why = c.finish(n, min_n, "drawdown episodes")
    sd = float(x.std(ddof=1)) if n > 1 else float("nan"); mde = 2.8016 * sd / math.sqrt(n) if n > 1 else float("nan")
    eps_l = drawdown_episodes(m.close, new_crossing=False); alt = stock_repair(m, iv, eps_l); xa = alt["x"]; na = int(xa.size)
    lo_a, hi_a = _ci_stud(xa, block, n_boot)
    ca = Criteria(); ca.ci("mean (repair - hold) / S lower CI > 0", lo_a, hi_a, "lower_gt")
    v_a, _ = ca.finish(na, min_n, "episodes")
    ref, ref_sp, _ = drawdown_refires(m.close, eps_l)
    sens = _sens(lambda s: stock_repair(m, iv, eps, scale=s))
    sec_txt, sec = "", None
    if second is not None:
        lab, m2, iv2 = second; r2 = stock_repair(m2, iv2, drawdown_episodes(m2.close, new_crossing=True)); x2 = r2["x"]
        l2, h2 = _ci_stud(x2, block, n_boot)
        sec = {"label": lab, "n": int(x2.size), "mean": float(x2.mean()) if x2.size else None, "ci": [l2, h2]}
        sec_txt = (f"; {lab} (second sample, same first-crossing rule, overlaps SPY in time, not in the pass rule): {x2.size} "
                   f"episodes, mean {_p(x2.mean() if x2.size else float('nan'), 2)} ({_rng(l2, h2, 2)})")
    short = (f"; {n} drawdown episodes is {min_n - n} short of min_n {min_n}, and the CI failure is not decisive (upper bound "
             f"above 0), so the sample cannot decide the claim" if n < min_n and np.isfinite(hi) and lo <= 0 <= hi else
             (f"; {n} drawdown episodes is {min_n - n} short of min_n {min_n}" if n < min_n else ""))
    reason = (f"{MODEL} (calls at VIX3M IV{iv_note}, flat; dividend forward; raw closes): {n} SPY drawdown episodes (first day "
              f"the drawdown from the trailing 252-day high newly crosses -10% after having been above it, 63-session lockout), "
              f"{res['days'][0] if n else ''} to {res['days'][-1] if n else ''}; K2 = (B + S)/2 median "
              f"{_p(float(np.median(res['k2'])) - 1 if n else float('nan'), 2)} above "
              f"spot; median net premium {_p(float(np.median(res['net'])) if n else float('nan'), 2)} of S (negative = credit; the "
              f"fixed K2 rule is only roughly zero-cost); mean (repair - hold) / S = 1x2 ratio P&L {_p(x.mean() if n else float('nan'), 2)} "
              f"(studentized block-{block} bootstrap {_rng(lo, hi, 2)}){short}; power: sd {_p(sd, 2)}, minimum detectable mean at "
              f"80% power {_p(mde, 2)}; robustness (not the pass rule): the 63-session level-trigger re-arm, which re-fires while "
              f"the drawdown is still at or below -10%, gives {na} episodes, of which {ref} are re-fires inside {ref_sp} continuing "
              f"drawdown spells, mean {_p(xa.mean() if na else float('nan'), 2)} ({_rng(lo_a, hi_a, 2)}), verdict under that "
              f"reading {v_a}{sec_txt}; IV-scale sensitivity (not in the pass rule; a traded test needs chain history): "
              f"{_sens_txt(sens, 2)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "episode_rule": "first crossing of -10% after being above it, 63-session lockout",
            "mean": float(x.mean()) if n else None, "ci": [lo, hi],
            "episode_days": res["days"], "sd": sd, "min_detectable_mean_80pct": mde,
            "rearm_level_trigger_variant": {"n": na, "mean": float(xa.mean()) if na else None, "ci": [lo_a, hi_a],
                                            "verdict": v_a, "refires": ref, "spells_with_refires": ref_sp},
            "second_sample": sec, "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------- T-138 SKEW-timed risk reversal --

def risk_reversal(P: dict, scale: float = 1.0, up: float = 1.05, dn: float = 0.95) -> dict:
    """Long call at up*S, short put at dn*S, at scale*IV; x = P&L / S (entry premium carried at r)."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    Kc, Kp = up * S, dn * S
    prem = _px(F, Kc, T, r, sig, "call") - _px(F, Kp, T, r, sig, "put")
    payoff = settle([("call", "long", 1, Kc), ("put", "short", 1, Kp)], P["ST"])
    return {"x": (payoff - prem * np.exp(r * T)) / S, "premium": prem / S}


def skew_groups(entry_days: Sequence[str], skew: dict, q: float = 0.20) -> dict:
    """Top/bottom SKEW quintile flags at entry: full-history cutoffs (all daily SKEW values) and expanding-window cutoffs (SKEW
    values dated on or before the entry day). SKEW at entry = the latest close on or before the entry day."""
    sd = sorted(skew); sv = np.array([float(skew[d]) for d in sd])
    at = np.array([sv[bisect.bisect_right(sd, d) - 1] if bisect.bisect_right(sd, d) > 0 else np.nan for d in entry_days])
    lo_f, hi_f = np.quantile(sv, [q, 1 - q])
    top_e = np.zeros(len(entry_days), bool); bot_e = np.zeros(len(entry_days), bool)
    for i, d in enumerate(entry_days):
        k = bisect.bisect_right(sd, d)
        if k >= 2 and np.isfinite(at[i]):
            lo_e, hi_e = np.quantile(sv[:k], [q, 1 - q])
            top_e[i] = at[i] >= hi_e; bot_e[i] = at[i] <= lo_e
    fin = np.isfinite(at)
    return {"skew": at, "full": (fin & (at >= hi_f), fin & (at <= lo_f)), "expanding": (top_e, bot_e), "cutoffs_full": [lo_f, hi_f]}


def eval_risk_reversal(P: dict, skew: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    res = risk_reversal(P); x = res["x"]; n = int(x.size); g = skew_groups(P["day"], skew)
    c = Criteria(); out = {}
    for nm in ("full", "expanding"):
        top, bot = g[nm]; d, lo, hi = ci_t_group_diff(x, top, bot, BLOCK, n_boot)
        c.ci(f"{nm}-sample quintiles: top - bottom lower CI > 0", lo, hi, "lower_gt")
        out[nm] = {"n_top": int(top.sum()), "n_bottom": int(bot.sum()), "mean_top": float(x[top].mean()) if top.any() else None,
                   "mean_bottom": float(x[bot].mean()) if bot.any() else None, "diff": d, "ci": [lo, hi]}
    v, why = c.finish(n, min_n, "months")
    sens = _sens(lambda s: risk_reversal(P, s))
    txt = "; ".join(f"{k} quintiles: top {o['n_top']} months mean {_p(o['mean_top'], 2)}, bottom {o['n_bottom']} mean "
                    f"{_p(o['mean_bottom'], 2)}, difference {_p(o['diff'], 2)} (studentized block-{BLOCK} {_rng(o['ci'][0], o['ci'][1], 2)})"
                    for k, o in out.items())
    reason = (f"{MODEL} (both legs at VIX IV flat, so the entry premium does not vary with SKEW: this isolates the conditional "
              f"wing payoff, a SKEW timing test; under flat pricing the structure is a small debit, median "
              f"{_p(float(np.median(res['premium'])) if n else float('nan'), 2)} of S): SPY 1-month risk reversal (long 1.05 S call, "
              f"short 0.95 S put), {n} monthly cycles from 1993 (SPY inception, not 1990); full-history SKEW cutoffs "
              f"{g['cutoffs_full'][0]:.1f}/{g['cutoffs_full'][1]:.1f}; {txt}; IV-scale sensitivity of the all-month mean (not in the "
              f"pass rule): {_sens_txt(sens, 2)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "groups": out, "mean_all": float(x.mean()) if n else None,
            "skew_cutoffs_full": g["cutoffs_full"], "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------- funded calls (T-139, T-140) --

def funded_call_path(m: Market, iv: np.ndarray, entries: list, hold: int, moneyness: float, scale: float = 1.0) -> dict:
    """Long 1 call at K = moneyness*S per S of capital, the rest (S - C) in bills accruing at the rate known each day; the call
    is re-marked every session by Black-Scholes at that day's IV (``iv`` carried over gaps), the remaining time and the
    dividend forward, and settles at intrinsic on the raw close. Rolled at expiry into the next entry (entries[k+1] =
    entries[k] + hold). Returns the equity path (from 1), per-cycle returns, SPY total-return factors and entry premiums."""
    idx = [entries[0]]; V = [1.0]; R, RS, prem = [], [], []
    v = 1.0
    for a in entries:
        b = a + hold; S = m.close[a]; K = moneyness * S; r0 = m.rate[a]; T0 = (m.cal[b] - m.cal[a]) / 365.0
        C0 = float(bs.price(S - m.pv_div(a, b, r0), K, T0, r0, iv[a] * scale, "call"))
        u = v / S
        t = np.arange(a + 1, b + 1)
        bills = (S - C0) * np.exp(np.cumsum(m.rate[t - 1] * (m.cal[t] - m.cal[t - 1]) / 365.0))
        Tt = (m.cal[b] - m.cal[t]) / 365.0
        call = np.asarray(bs.price(m.close[t] - m.pv_div_path(t, b), K, Tt, m.rate[t], iv[t] * scale, "call"), float)
        path = u * (call + bills)
        R.append(path[-1] / v - 1); RS.append(m.adj[b] / m.adj[a] - 1); prem.append(C0 / S)
        idx.extend(t.tolist()); V.extend(path.tolist()); v = float(path[-1])
    idx = np.array(idx, int); V = np.array(V)
    return {"idx": idx, "V": V, "ret": V[1:] / V[:-1] - 1, "spy_ret": m.adj[idx[1:]] / m.adj[idx[:-1]] - 1,
            "R": np.array(R), "R_spy": np.array(RS), "premium": np.array(prem), "entries": list(entries)}


def _fill(x: np.ndarray) -> np.ndarray:
    out = np.array(x, float); last = float("nan")
    for i in range(out.size):
        if np.isfinite(out[i]) and out[i] > 0:
            last = out[i]
        else:
            out[i] = last
    return out


def leaps_cohorts(m: Market, iv: np.ndarray, scale: float = 1.0, moneyness: float = 0.80, hold: int = YEAR, n_cohorts: int = 12,
                  stagger: int = MONTH, start: str = START) -> dict:
    """12 monthly-staggered cohorts of annually rolled funded calls; cycles of all cohorts on one monthly grid."""
    ivf = _fill(iv)
    first = cycle_entries(m, ivf, hold, start)
    if not first:
        return {"cohorts": [], "grid": {"R": np.array([]), "R_spy": np.array([]), "day": []}}
    a0 = first[0]; cohorts = []; grid = []
    for c in range(n_cohorts):
        ent = list(range(a0 + c * stagger, len(m.days) - hold, hold))
        ent = [e for e in ent if e + hold < len(m.days)]
        if not ent:
            continue
        p = funded_call_path(m, ivf, ent, hold, moneyness, scale)
        cohorts.append(p)
        for e, r1, r2 in zip(ent, p["R"], p["R_spy"]):
            grid.append((e, r1, r2))
    grid.sort()
    return {"cohorts": cohorts, "grid": {"R": np.array([g[1] for g in grid]), "R_spy": np.array([g[2] for g in grid]),
                                         "day": [m.days[g[0]] for g in grid]}}


def ann_diff(R, R_spy) -> float:
    """Annualised geometric return difference from 1-year cycles: exp(mean log(1+R)) - exp(mean log(1+R_spy))."""
    return float(np.exp(np.mean(np.log1p(R))) - np.exp(np.mean(np.log1p(R_spy))))


def _boot_stat(n: int, fn, block: int, n_boot: int = N_BOOT, seed: int = 0, chunk: int = 100) -> np.ndarray:
    """Circular block bootstrap distribution of fn(idx) where idx is an (k, n) index matrix (vectorised in chunks)."""
    rng = np.random.default_rng(seed); nb = math.ceil(n / block); out = []
    for s in range(0, n_boot, chunk):
        k = min(chunk, n_boot - s)
        starts = rng.integers(0, n, (k, nb))
        idx = ((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n]) % n
        out.append(fn(idx))
    return np.concatenate(out)


def eval_leaps(m: Market, iv: np.ndarray, min_n: int = 30, n_boot: int = N_BOOT, block: int = 12, iv_note: str = "",
               start: str = START) -> dict:
    res = leaps_cohorts(m, iv, start=start); R, RS = res["grid"]["R"], res["grid"]["R_spy"]; n_grid = int(R.size)
    n = len(res["cohorts"][0]["R"]) if res["cohorts"] else 0
    c = Criteria()
    if n_grid >= 2 * block:
        d = ann_diff(R, RS)
        lr, ls = np.log1p(R), np.log1p(RS)
        dist = _boot_stat(n_grid, lambda ix: np.exp(lr[ix].mean(axis=1)) - np.exp(ls[ix].mean(axis=1)), block, n_boot)
        lo, hi = float(np.quantile(dist, 0.025)), float(np.quantile(dist, 0.975))
    else:
        d = lo = hi = float("nan")
    c.ci("annualised return difference (LEAPS + bills - SPY) upper CI < 0", lo, hi, "upper_lt")
    ratios, coh = [], []
    for p in res["cohorts"]:
        ms, mb = _mdd(p["ret"]), _mdd(p["spy_ret"])
        ratios.append(ms / mb if mb < 0 else float("nan"))
        coh.append({"start": m.days[p["entries"][0]], "cycles": int(p["R"].size), "ann_diff": ann_diff(p["R"], p["R_spy"]),
                    "mdd": ms, "mdd_spy": mb})
    ratios = np.array(ratios, float); mr = float(np.nanmean(ratios)) if np.isfinite(ratios).any() else float("nan")
    c.add("max-drawdown ratio (mean over the 12 cohorts) < 1", mr < 1 if np.isfinite(mr) else None)
    v, why = c.finish(n, min_n, "independent annual cycles")
    sens = {}
    for s in (0.90, 1.10):
        g = leaps_cohorts(m, iv, scale=s, start=start)["grid"]; sens[f"{s:.2f}"] = ann_diff(g["R"], g["R_spy"]) if g["R"].size else None
    prem = np.concatenate([p["premium"] for p in res["cohorts"]]) if res["cohorts"] else np.array([])
    reason = (f"{MODEL} (1-year call K = 0.8 S at VIX3M IV{iv_note}, flat, on the dividend forward with r = prior DTB3 print, re-marked "
              f"daily at that day's IV; S - C in 3-month bills; SPY total return, the same dividend convention): "
              f"{len(res['cohorts'])} monthly-staggered cohorts, {n_grid} annual cycles on one monthly grid ({n} independent annual "
              f"cycles in cohort 1, about 33 expected); median call premium {_p(float(np.median(prem)) if prem.size else float('nan'), 1)} of S; "
              f"annualised return difference {_p(d, 2)} (block-{block} percentile {_rng(lo, hi, 2)}; the difference is the embedded "
              f"20%-OTM put's P&L); max-drawdown ratio mean {mr:.2f} over cohorts (range {np.nanmin(ratios) if ratios.size else float('nan'):.2f}-"
              f"{np.nanmax(ratios) if ratios.size else float('nan'):.2f}); return difference at IV scale 0.90 {_p(sens.get('0.90'), 2)}, 1.10 "
              f"{_p(sens.get('1.10'), 2)} (1-year IV usually sits above VIX3M, so the put cost is understated; not in the pass rule) — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_grid_cycles": n_grid, "ann_return_diff": d, "ci": [lo, hi],
            "mdd_ratio_mean": mr, "mdd_ratios": ratios, "cohorts": coh, "iv_scale_sensitivity": sens, "model_priced": True,
            "min_n": min_n}


def eval_deep_itm(m: Market, iv: np.ndarray, min_n: int = 300, n_boot: int = N_BOOT, block: int = MONTH, start: str = START) -> dict:
    ivf = _fill(iv); ent = cycle_entries(m, ivf, MONTH, start)
    if not ent:
        c = Criteria(); c.add("correlation lower CI > 0.98", None); c.add("shortfall upper CI < 1 pp", None)
        v, why = c.finish(0, min_n, "monthly cycles")
        return {"verdict": v, "reason": f"{MODEL}: no monthly cycles — {why}", "n": 0, "model_priced": True, "min_n": min_n}
    ent = list(range(ent[0], len(m.days) - MONTH, MONTH))
    p = funded_call_path(m, ivf, ent, MONTH, 0.90); n = int(p["R"].size)
    rs, rb = p["ret"], p["spy_ret"]; N = rs.size
    corr = float(np.corrcoef(rs, rb)[0, 1])
    ls, lb = np.log1p(rs), np.log1p(rb)
    short = float(np.exp(YEAR * lb.mean()) - np.exp(YEAR * ls.mean()))
    def corr_fn(ix):
        a, b = rs[ix], rb[ix]; a = a - a.mean(axis=1, keepdims=True); b = b - b.mean(axis=1, keepdims=True)
        return (a * b).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    cd = _boot_stat(N, corr_fn, block, n_boot)
    sd_ = _boot_stat(N, lambda ix: np.exp(YEAR * lb[ix].mean(axis=1)) - np.exp(YEAR * ls[ix].mean(axis=1)), block, n_boot)
    clo, chi = float(np.quantile(cd, 0.025)), float(np.quantile(cd, 0.975))
    slo, shi = float(np.quantile(sd_, 0.025)), float(np.quantile(sd_, 0.975))
    c = Criteria()
    c.ci("daily-return correlation with SPY lower CI > 0.98", clo, chi, "lower_gt", 0.98)
    c.ci("annualised shortfall vs SPY upper CI < 1 pp", slo, shi, "upper_lt", 0.01)
    v, why = c.finish(n, min_n, "monthly cycles")
    sens = {}
    for s in SCALES:
        q = funded_call_path(m, ivf, ent, MONTH, 0.90, s)
        sens[f"{s:.2f}"] = float(np.exp(YEAR * np.log1p(q["spy_ret"]).mean()) - np.exp(YEAR * np.log1p(q["ret"]).mean()))
    reason = (f"{MODEL} (call K = 0.9 S at VIX IV flat on the dividend forward, re-marked daily at that day's VIX; S - C in "
              f"3-month bills at the prior DTB3 print; SPY total return): {n} monthly rolls, {N} daily returns "
              f"{m.days[p['idx'][0]]} to {m.days[p['idx'][-1]]}; median call premium {_p(float(np.median(p['premium'])), 1)} of S; "
              f"correlation {corr:.4f} (block-{block} percentile 95% CI {clo:.4f} to {chi:.4f}; needs lower > 0.98); annualised "
              f"shortfall {short * 100:+.2f} pp (95% CI {slo * 100:+.2f} to {shi * 100:+.2f} pp; needs upper < 1 pp; equals the embedded "
              f"10%-OTM put's P&L); shortfall at IV scales (not in the pass rule; a traded test needs chain history and deep-ITM "
              f"bid-ask): " + ", ".join(f"s={k} {v_ * 100:+.2f} pp" for k, v_ in sens.items()) + f" — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_days": int(N), "corr": corr, "corr_ci": [clo, chi], "shortfall": short,
            "shortfall_ci": [slo, shi], "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------------------ T-154 ZEBRA --

def zebra(P: dict, scale: float = 1.0, long_delta: float = 0.70) -> dict:
    """Long 2 calls at the `long_delta` strike, short 1 ATM call, plus (delta0*S - debit) in bills, against delta0 SPY shares
    (total return); x = difference / S."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = _strikes_for_delta(P, sig, long_delta, "call"); K2 = S.copy()
    d1 = np.asarray(bs.greeks(F, K1, T, r, sig, "call")["delta"], float); d2 = np.asarray(bs.greeks(F, K2, T, r, sig, "call")["delta"], float)
    delta0 = 2 * d1 - d2
    debit = 2 * _px(F, K1, T, r, sig, "call") - _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 2, K1), ("call", "short", 1, K2)], P["ST"])
    x = (payoff + (delta0 * S - debit) * np.exp(r * T) - delta0 * S * P["tr"]) / S
    extr = (2 * (_px(F, K1, T, r, sig, "call") - np.maximum(F - K1, 0)) - _px(F, K2, T, r, sig, "call") + np.maximum(F - K2, 0)) / S
    return {"x": x, "delta0": delta0, "net_extrinsic": extr, "K1": K1 / S}


def eval_zebra(P: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    res = zebra(P); x = res["x"]; n = int(x.size)
    lo, hi = _ci(x, BLOCK, n_boot)
    c = Criteria(); c.ci("mean (ZEBRA - delta0 x SPY) / S upper CI < 0", lo, hi, "upper_lt")
    v, why = c.finish(n, min_n, "months")
    sens = _sens(lambda s: zebra(P, s))
    reason = (f"{MODEL} (both strikes at VIX IV flat, 0.70-delta strike solved at that IV on the dividend forward; the cash "
              f"difference delta0*S - debit earns the prior DTB3 print; SPY total return): SPY 1-month call ZEBRA, {n} monthly cycles; "
              f"median entry delta {float(np.median(res['delta0'])) if n else float('nan'):.3f}, median 0.70-delta strike "
              f"{_p(float(np.median(res['K1'])) - 1 if n else float('nan'), 2)} vs spot, median net extrinsic paid "
              f"{_p(float(np.median(res['net_extrinsic'])) if n else float('nan'), 2)} of S; mean difference "
              f"{_p(x.mean() if n else float('nan'))} of S ({_rng(lo, hi)}, block-{BLOCK} percentile); IV-scale sensitivity "
              f"(not in the pass rule; the net extrinsic is priced off the IV level, so a traded test needs chain history): "
              f"{_sens_txt(sens)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "mean_diff": float(x.mean()) if n else None, "ci": [lo, hi],
            "median_delta0": float(np.median(res["delta0"])) if n else None,
            "median_net_extrinsic": float(np.median(res["net_extrinsic"])) if n else None,
            "iv_scale_sensitivity": sens, "model_priced": True, "min_n": min_n}


# ----------------------------------------------------------------------------------------------- T-516 digital --

def digital_put(P: dict, scale: float = 1.0, k: float = 0.97) -> dict:
    """RN probability N(-d2) of S_T < k*S at scale*IV (dividend forward, r = prior DTB3 print) and the outcome."""
    sig = P["sig"] * scale; K = k * P["S"]
    p = _ncdf(-_d2(P["F"], K, P["T"], P["r"], sig)); y = (P["ST"] < K).astype(float)
    return {"x": y - p, "p": p, "y": y}


def eval_digital(P: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    res = digital_put(P); x = res["x"]; n = int(x.size)
    lo, hi = _ci(x, BLOCK, n_boot)
    c = Criteria(); c.ci("realised - RN probability upper CI < 0", lo, hi, "upper_lt")
    v, why = c.finish(n, min_n, "21-day cycles")
    if n:
        y, p = res["y"], res["p"]; bs_rn = float(np.mean((p - y) ** 2)); clim = float(y.mean()); bs_cl = float(np.mean((clim - y) ** 2))
    else:
        bs_rn = bs_cl = clim = float("nan")
    sens = {}
    for s in SCALES:
        r2 = digital_put(P, s); sens[f"{s:.2f}"] = {"rn_mean": float(r2["p"].mean()) if n else None, "diff": float(r2["x"].mean()) if n else None}
    reason = (f"{MODEL} (N(-d2) at VIX IV flat, K = 0.97 S, dividend forward, r = prior DTB3 print): {n} non-overlapping 21-day "
              f"SPY cycles; realised frequency of S_T < K {_p(res['y'].mean() if n else float('nan'), 1)} vs mean N(-d2) "
              f"{_p(res['p'].mean() if n else float('nan'), 1)}: realised - RN {_p(x.mean() if n else float('nan'), 2)} ({_rng(lo, hi, 2)}, "
              f"block-{BLOCK} percentile); Brier N(-d2) {bs_rn:.4f} vs in-sample climatology {bs_cl:.4f} (report); at IV scales "
              f"(not in the pass rule; flat IV ignores skew, a traded digital needs chain history): "
              + ", ".join(f"s={k} RN {_p(o['rn_mean'], 1)}, diff {_p(o['diff'], 2)}" for k, o in sens.items()) + f" — {why}")
    return {"verdict": v, "reason": reason, "n": n, "realised": float(res["y"].mean()) if n else None,
            "rn_mean": float(res["p"].mean()) if n else None, "diff": float(x.mean()) if n else None, "ci": [lo, hi],
            "brier_rn": bs_rn, "brier_climatology": bs_cl, "climatology": clim, "iv_scale_sensitivity": sens,
            "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------------------- harnesses --

SPY_BASE = ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"]


def _market(archive, symbol: str = "SPY") -> Market:
    def build():
        days, close, adj = _prices(archive, symbol)
        return make_market(days, close, adj, _index(archive, "fred-DTB3"))
    return _cached(archive, ("market", symbol), build)


def _vix_panel(archive) -> dict:
    def build():
        m = _market(archive); iv = iv_series(m.days, _index(archive, "cboe-VIX-history"))
        return cycle_panel(m, iv, MONTH)
    return _cached(archive, ("panel", "VIX"), build)


def _iv3m(archive, m: Market) -> np.ndarray:
    return iv_series(m.days, _index(archive, "cboe-VIX3M-history"), _index(archive, "cboe-VIX-history"))


def _vix3m_note(archive, claim_switch: str = " (the archive's VIX3M starts there, not at the claim's 2007-12)") -> str:
    v3 = _index(archive, "cboe-VIX3M-history")
    return f" from {min(v3)}, VIX before{claim_switch}" if v3 else " (no VIX3M prints: VIX throughout)"


def b6_dir_jade_lizard(archive):
    """T-113: MODEL-PRICED SPY jade lizard, mean P&L / (0.2 S) > 0 (lower CI) and positive in both halves."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_jade_lizard(_vix_panel(archive)))


def b6_dir_ratio_1x2(archive):
    """T-133: MODEL-PRICED zero-cost 1x2 SPY call ratio: mean > 0 and losses > 3x median gain in > 3% of months."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_ratio_1x2(_vix_panel(archive)))


def b6_dir_christmas_tree(archive):
    """T-135: MODEL-PRICED 1-3-2 call tree; profit-zone hit rate above its risk-neutral probability."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_christmas_tree(_vix_panel(archive)))


def b6_dir_stock_repair(archive):
    """T-136: MODEL-PRICED stock repair after 10% SPY drawdowns vs holding; mean difference > 0 (studentized lower CI)."""
    miss = _missing(archive, SPY_BASE + ["cboe-VIX3M-history"])
    if miss:
        return miss
    m = _market(archive); iv = _iv3m(archive, m)
    second = None
    if _has(archive, "daily-history-QQQ"):
        mq = _market(archive, "QQQ")
        vxn = _index(archive, "cboe-VXN-history") if _has(archive, "cboe-VXN-history") else {}
        ivq = iv_series(mq.days, vxn, _index(archive, "cboe-VIX-history")) if vxn else iv_series(mq.days, _index(archive, "cboe-VIX-history"))
        second = ("QQQ (VXN IV from its first print, VIX before)" if vxn else "QQQ (VIX IV)", mq, ivq)
    return _wrap(eval_stock_repair(m, iv, second=second, iv_note=_vix3m_note(archive, "")))


def b6_dir_risk_reversal_skew(archive):
    """T-138: MODEL-PRICED SPY risk reversal; top minus bottom SKEW-quintile mean P&L > 0 (full and expanding cutoffs)."""
    miss = _missing(archive, SPY_BASE + ["cboe-SKEW-history"])
    if miss:
        return miss
    return _wrap(eval_risk_reversal(_vix_panel(archive), _index(archive, "cboe-SKEW-history")))


def b6_dir_leaps_replacement(archive):
    """T-139: MODEL-PRICED 1-year 20%-ITM SPY call + bills vs SPY: lower annualised return (upper CI < 0) and smaller MDD."""
    miss = _missing(archive, SPY_BASE + ["cboe-VIX3M-history"])
    if miss:
        return miss
    m = _market(archive)
    return _wrap(eval_leaps(m, _iv3m(archive, m), iv_note=_vix3m_note(archive)))


def b6_dir_deep_itm_call(archive):
    """T-140: MODEL-PRICED monthly 10%-ITM SPY call + bills: correlation > 0.98 and shortfall < 1 pp (CI bounds)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    m = _market(archive)
    return _wrap(eval_deep_itm(m, iv_series(m.days, _index(archive, "cboe-VIX-history"))))


def b6_dir_zebra(archive):
    """T-154: MODEL-PRICED SPY call ZEBRA vs a delta-matched SPY position: mean difference < 0 (upper CI)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_zebra(_vix_panel(archive)))


def b6_dir_digital_put(archive):
    """T-516: MODEL-PRICED 30-day 0.97 S digital put: realised frequency below N(-d2) at VIX IV (upper CI < 0)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_digital(_vix_panel(archive)))


HARNESSES = {
    "b6_dir_jade_lizard": b6_dir_jade_lizard,
    "b6_dir_ratio_1x2": b6_dir_ratio_1x2,
    "b6_dir_christmas_tree": b6_dir_christmas_tree,
    "b6_dir_stock_repair": b6_dir_stock_repair,
    "b6_dir_risk_reversal_skew": b6_dir_risk_reversal_skew,
    "b6_dir_leaps_replacement": b6_dir_leaps_replacement,
    "b6_dir_deep_itm_call": b6_dir_deep_itm_call,
    "b6_dir_zebra": b6_dir_zebra,
    "b6_dir_digital_put": b6_dir_digital_put,
}

THEORY_MAP = {
    "T-113": "b6_dir_jade_lizard",
    "T-133": "b6_dir_ratio_1x2",
    "T-135": "b6_dir_christmas_tree",
    "T-136": "b6_dir_stock_repair",
    "T-138": "b6_dir_risk_reversal_skew",
    "T-139": "b6_dir_leaps_replacement",
    "T-140": "b6_dir_deep_itm_call",
    "T-154": "b6_dir_zebra",
    "T-516": "b6_dir_digital_put",
}
