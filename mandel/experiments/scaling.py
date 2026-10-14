"""
Scaling diagnostics: multifractal partition function, Hurst exponent with intervals.
====================================================================================

From resources 15, 16 and A4: roughness is a measured exponent with a scale
range and an interval, tested against a null. Nothing here is a pass
criterion for a strategy; these are diagnostics that attach to proposals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np


def _arr(x) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    return a


# ------------------------------------------------------------ partition function --

def partition_function(x: Sequence[float], qs: Sequence[float], dts: Sequence[int]) -> np.ndarray:
    """S_q(dt) = sum_i |X(t_i+dt) - X(t_i)|^q over non-overlapping increments; shape (len(qs), len(dts))."""
    X = _arr(x)
    out = np.full((len(qs), len(dts)), np.nan)
    for j, dt in enumerate(dts):
        if dt < 1 or dt * 4 > X.size:
            continue
        inc = np.abs(X[dt::dt][: (X.size - 1) // dt] - X[0:-dt:dt][: (X.size - 1) // dt])
        inc = inc[inc > 0]
        if inc.size < 4:
            continue
        for i, q in enumerate(qs):
            out[i, j] = np.sum(inc ** q)
    return out


def tau_q(x: Sequence[float], qs: Sequence[float], dts: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    """Scaling function tau(q): slope of log S_q(dt) against log dt, minus 1. Returns (tau, r2) per q."""
    S = partition_function(x, qs, dts)
    logdt = np.log(np.asarray(dts, dtype=float))
    tau = np.full(len(qs), np.nan)
    r2 = np.full(len(qs), np.nan)
    for i in range(len(qs)):
        y = np.log(S[i])
        m = np.isfinite(y)
        if m.sum() < 3:
            continue
        A = np.vstack([logdt[m], np.ones(m.sum())]).T
        coef, res, *_ = np.linalg.lstsq(A, y[m], rcond=None)
        tau[i] = coef[0] - 1.0
        yhat = A @ coef
        ss_res = float(np.sum((y[m] - yhat) ** 2)); ss_tot = float(np.sum((y[m] - y[m].mean()) ** 2))
        r2[i] = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return tau, r2


def concavity(tau: np.ndarray, qs: Sequence[float]) -> float:
    """Second-difference concavity statistic of tau(q): mean of -(tau[i+1]-2tau[i]+tau[i-1]); 0 for linear (unifractal)."""
    t = np.asarray(tau, dtype=float)
    q = np.asarray(qs, dtype=float)
    m = np.isfinite(t)
    if m.sum() < 3:
        return float("nan")
    t, q = t[m], q[m]
    d2 = (t[2:] - 2 * t[1:-1] + t[:-2]) / ((q[2:] - q[:-2]) / 2) ** 2
    return float(-np.mean(d2))


@dataclass
class MultifractalReport:
    n: int
    qs: list
    dts: list
    tau: list
    r2: list
    concavity: float
    null_concavity_q95: float
    null_mean: float
    exceeds_null: bool
    note: str

    def as_dict(self) -> dict:
        return {"n": self.n, "qs": self.qs, "dts": self.dts, "tau": self.tau, "r2": self.r2, "concavity": self.concavity,
                "null_concavity_q95": self.null_concavity_q95, "null_mean": self.null_mean, "exceeds_null": self.exceeds_null,
                "note": self.note}


def multifractal_test(x: Sequence[float], qs: Sequence[float] = (0.5, 1, 1.5, 2, 3, 4), dts: Optional[Sequence[int]] = None,
                      n_shuffles: int = 200, seed: int = 0) -> MultifractalReport:
    """Partition-function test with a shuffled-increments null (Lux 2004: shuffled data still produce
    curved tau(q) from fat tails alone, so concavity must beat the shuffle, not zero)."""
    X = _arr(x)
    n = X.size
    if n < 64:
        return MultifractalReport(n, list(qs), [], [], [], float("nan"), float("nan"), float("nan"), False, "too few points (<64)")
    if dts is None:
        maxdt = max(2, n // 8)
        dts = sorted(set(int(round(2 ** k)) for k in np.arange(0, math.log2(maxdt) + 1e-9, 0.5)))
    tau, r2 = tau_q(X, qs, dts)
    c = concavity(tau, qs)
    rng = np.random.default_rng(seed)
    inc = np.diff(X)
    nulls = []
    for _ in range(n_shuffles):
        xs = np.concatenate([[X[0]], X[0] + np.cumsum(rng.permutation(inc))])
        t_s, _ = tau_q(xs, qs, dts)
        cs = concavity(t_s, qs)
        if np.isfinite(cs):
            nulls.append(cs)
    nulls = np.asarray(nulls)
    q95 = float(np.quantile(nulls, 0.95)) if nulls.size else float("nan")
    note = f"scale range {dts[0]}..{dts[-1]} steps; {len(dts)} scales; shuffle null n={nulls.size}"
    return MultifractalReport(n, list(qs), list(map(int, dts)), [None if not np.isfinite(v) else float(v) for v in tau],
                              [None if not np.isfinite(v) else float(v) for v in r2], c, q95,
                              float(nulls.mean()) if nulls.size else float("nan"),
                              bool(np.isfinite(c) and nulls.size and c > q95), note)


# -------------------------------------------------------------------- Hurst / DFA --

def hurst_dfa(x: Sequence[float], min_box: int = 8, max_box: Optional[int] = None) -> tuple[float, float, int]:
    """Hurst exponent by detrended fluctuation analysis (order 1) on the profile of increments.
    Returns (H, r2, n_scales). H=0.5 for uncorrelated increments."""
    X = _arr(x)
    inc = np.diff(X)
    n = inc.size
    if n < 4 * min_box:
        return float("nan"), float("nan"), 0
    y = np.cumsum(inc - inc.mean())
    max_box = max_box or n // 4
    boxes = sorted(set(int(round(2 ** k)) for k in np.arange(math.log2(min_box), math.log2(max_box) + 1e-9, 0.5)))
    F, used = [], []
    for s in boxes:
        nseg = n // s
        if nseg < 2:
            continue
        segs = y[: nseg * s].reshape(nseg, s)
        t = np.arange(s)
        A = np.vstack([t, np.ones(s)]).T
        coef, *_ = np.linalg.lstsq(A, segs.T, rcond=None)
        resid = segs - (A @ coef).T
        f = math.sqrt(float(np.mean(resid ** 2)))
        if f > 0:                                  # constant segments carry no scaling information
            F.append(f)
            used.append(s)
    if len(used) < 3:
        return float("nan"), float("nan"), len(used)
    lx, ly = np.log(used), np.log(F)
    A = np.vstack([lx, np.ones(len(lx))]).T
    coef, *_ = np.linalg.lstsq(A, ly, rcond=None)
    yhat = A @ coef
    r2 = 1 - float(np.sum((ly - yhat) ** 2)) / float(np.sum((ly - ly.mean()) ** 2))
    return float(coef[0]), float(r2), len(used)


def hurst_with_interval(x: Sequence[float], n_null: int = 200, seed: int = 0) -> dict:
    """H by DFA with a shuffled-increments null interval (H should be ~0.5 under the null); reports
    the empirical null quantiles so 'H = 0.6 so it trends' can be judged against finite-sample noise."""
    X = _arr(x)
    H, r2, k = hurst_dfa(X)
    rng = np.random.default_rng(seed)
    inc = np.diff(X)
    nulls = []
    for _ in range(n_null):
        xs = np.concatenate([[X[0]], X[0] + np.cumsum(rng.permutation(inc))])
        h, _, _ = hurst_dfa(xs)
        if np.isfinite(h):
            nulls.append(h)
    nulls = np.asarray(nulls)
    lo, hi = (float(np.quantile(nulls, 0.025)), float(np.quantile(nulls, 0.975))) if nulls.size else (float("nan"), float("nan"))
    return {"H": H, "r2": r2, "n_scales": k, "n": int(X.size), "null_lo": lo, "null_hi": hi,
            "outside_null": bool(np.isfinite(H) and nulls.size and (H < lo or H > hi))}
