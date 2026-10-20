"""
Markov state models for the batch-8 harnesses: a two-state Gaussian HMM (EM fit, forward filter) and a discrete
return-state chain. Point in time by construction: ``fit`` sees only the returns it is given, ``filter_probs`` gives
P(state | returns through t) from a forward pass (never the smoothed posterior, which uses returns after t).

Two states keep the recursions scalar, so the loops are plain floats (no scipy / numba in the house environment).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

LOG2PI = math.log(2 * math.pi)


@dataclass(frozen=True)
class HMM2:
    mu: tuple                 # (mu0, mu1)
    var: tuple                # (var0, var1); state 1 is the high-variance state after ``fit``
    P: tuple                  # ((p00, p01), (p10, p11))
    pi: tuple                 # initial probabilities
    loglik: float
    iters: int
    n: int

    @property
    def high(self) -> int:
        return 1


def _norm_pdf(x: float, mu: float, var: float) -> float:
    return math.exp(-0.5 * ((x - mu) ** 2 / var + math.log(var) + LOG2PI))


def init_params(x: Sequence[float]) -> tuple:
    """Means 0, variances at the 20th and 80th percentiles of rolling 21-day variance, sticky transitions (0.98)."""
    a = np.asarray(x, float)
    if a.size >= 42:
        c = np.cumsum(np.insert(a * a, 0, 0.0))
        rv = (c[21:] - c[:-21]) / 21
        v0, v1 = float(np.percentile(rv, 20)), float(np.percentile(rv, 80))
    else:
        v = float(a.var()) or 1e-6
        v0, v1 = 0.5 * v, 2.0 * v
    v0, v1 = max(v0, 1e-10), max(v1, 2e-10)
    return (float(a.mean()), float(a.mean())), (v0, v1), ((0.98, 0.02), (0.02, 0.98)), (0.5, 0.5)


def fit(x: Sequence[float], max_iter: int = 200, tol: float = 1e-8) -> HMM2:
    """Baum-Welch with scaling. Stops when the mean log-likelihood per observation improves by less than ``tol``. The
    returned states are ordered so that state 1 has the larger variance."""
    xs = [float(v) for v in x]
    n = len(xs)
    if n < 50:
        raise ValueError("too few returns to fit an HMM")
    (m0, m1), (v0, v1), ((a00, a01), (a10, a11)), (p0, p1) = init_params(xs)
    prev, ll, it = -math.inf, -math.inf, 0
    f0 = [0.0] * n; f1 = [0.0] * n; sc = [0.0] * n
    for it in range(1, max_iter + 1):
        # forward (scaled)
        ll = 0.0
        e0, e1 = _norm_pdf(xs[0], m0, v0), _norm_pdf(xs[0], m1, v1)
        a, b = p0 * e0, p1 * e1
        s = a + b or 1e-300
        f0[0], f1[0], sc[0] = a / s, b / s, s
        ll += math.log(s)
        for t in range(1, n):
            e0, e1 = _norm_pdf(xs[t], m0, v0), _norm_pdf(xs[t], m1, v1)
            a = (f0[t - 1] * a00 + f1[t - 1] * a10) * e0
            b = (f0[t - 1] * a01 + f1[t - 1] * a11) * e1
            s = a + b or 1e-300
            f0[t], f1[t], sc[t] = a / s, b / s, s
            ll += math.log(s)
        # backward with the same scales; accumulate the sufficient statistics on the way
        b0n, b1n = 1.0, 1.0
        g0s = g1s = 0.0; g0x = g1x = 0.0; g0xx = g1xx = 0.0
        x00 = x01 = x10 = x11 = 0.0
        g0_first = g1_first = 0.0
        for t in range(n - 1, -1, -1):
            g0, g1 = f0[t] * b0n, f1[t] * b1n
            gs = g0 + g1 or 1e-300
            g0, g1 = g0 / gs, g1 / gs
            xt = xs[t]
            g0s += g0; g1s += g1; g0x += g0 * xt; g1x += g1 * xt; g0xx += g0 * xt * xt; g1xx += g1 * xt * xt
            if t == 0:
                g0_first, g1_first = g0, g1
                break
            e0, e1 = _norm_pdf(xt, m0, v0), _norm_pdf(xt, m1, v1)
            # xi(t-1 -> t)
            c = sc[t]
            q00 = f0[t - 1] * a00 * e0 * b0n / c
            q01 = f0[t - 1] * a01 * e1 * b1n / c
            q10 = f1[t - 1] * a10 * e0 * b0n / c
            q11 = f1[t - 1] * a11 * e1 * b1n / c
            x00 += q00; x01 += q01; x10 += q10; x11 += q11
            nb0 = (a00 * e0 * b0n + a01 * e1 * b1n) / c
            nb1 = (a10 * e0 * b0n + a11 * e1 * b1n) / c
            b0n, b1n = nb0, nb1
        # M step
        m0, m1 = g0x / g0s, g1x / g1s
        v0 = max(g0xx / g0s - m0 * m0, 1e-12)
        v1 = max(g1xx / g1s - m1 * m1, 1e-12)
        r0, r1 = x00 + x01 or 1e-300, x10 + x11 or 1e-300
        a00, a01, a10, a11 = x00 / r0, x01 / r0, x10 / r1, x11 / r1
        p0, p1 = g0_first, g1_first
        if abs(ll - prev) / n < tol:
            break
        prev = ll
    if v0 > v1:                                     # order: state 1 = high variance
        m0, m1, v0, v1 = m1, m0, v1, v0
        a00, a01, a10, a11 = a11, a10, a01, a00
        p0, p1 = p1, p0
    return HMM2((m0, m1), (v0, v1), ((a00, a01), (a10, a11)), (p0, p1), ll, it, n)


def filter_probs(x: Sequence[float], h: HMM2) -> np.ndarray:
    """P(high-variance state | x[0..t]) for every t (forward filter under fixed parameters)."""
    (m0, m1), (v0, v1), ((a00, a01), (a10, a11)), (p0, p1) = h.mu, h.var, h.P, h.pi
    out = np.empty(len(x))
    f0, f1 = p0, p1
    for t, xt in enumerate(x):
        xt = float(xt)
        if t:
            f0, f1 = f0 * a00 + f1 * a10, f0 * a01 + f1 * a11
        a, b = f0 * _norm_pdf(xt, m0, v0), f1 * _norm_pdf(xt, m1, v1)
        s = a + b
        if s > 0:
            f0, f1 = a / s, b / s
        out[t] = f1
    return out


def one_step_sigma(p_high_filtered: float, h: HMM2) -> float:
    """One-day-ahead volatility forecast: predicted state probabilities (filtered x transition) mixing the two variances."""
    (a00, a01), (a10, a11) = h.P
    q1 = (1 - p_high_filtered) * a01 + p_high_filtered * a11
    return math.sqrt((1 - q1) * h.var[0] + q1 * h.var[1])


def yearly_refits(days: Sequence[str], x: Sequence[float], first_year: int, train_from: Optional[str] = None,
                  min_obs: int = 750) -> dict:
    """{year: HMM2 fitted on returns dated before Jan 1 of that year (and on or after ``train_from``)}."""
    days = list(days)
    xs = np.asarray(x, float)
    last_year = int(days[-1][:4])
    out = {}
    for y in range(first_year, last_year + 1):
        cut = f"{y}-01-01"
        m = np.array([(d < cut) and (train_from is None or d >= train_from) for d in days])
        if m.sum() >= min_obs:
            out[y] = fit(xs[m])
    return out


def filtered_high(days: Sequence[str], x: Sequence[float], fits: dict, train_from: Optional[str] = None) -> dict:
    """{day: P(high | returns from ``train_from`` through day)} under the fit of that day's year (point in time: the fit
    used on a day was estimated on returns before Jan 1 of its year; the filter runs over returns through the day)."""
    days = list(days)
    xs = np.asarray(x, float)
    keep = [i for i, d in enumerate(days) if train_from is None or d >= train_from]
    dd = [days[i] for i in keep]
    xx = xs[keep]
    out = {}
    for y, h in fits.items():
        p = filter_probs(xx, h)
        for d, v in zip(dd, p):
            if d[:4] == str(y):
                out[d] = float(v)
    return out


# ---------------------------------------------------------------------------------------- discrete chains --

def tercile_cuts(x: Sequence[float]) -> tuple:
    a = np.sort(np.asarray(x, float))
    return float(a[int(len(a) / 3)]), float(a[int(2 * len(a) / 3)])


def tercile_state(v: float, cuts: tuple) -> int:
    return 0 if v < cuts[0] else (1 if v < cuts[1] else 2)


def state_next_means(states: Sequence[int], nxt: Sequence[float], k: int) -> list:
    """Mean of the next value following each state (None where a state never occurs)."""
    s = np.asarray(states, int)
    v = np.asarray(nxt, float)
    return [float(v[s == j].mean()) if np.any(s == j) else None for j in range(k)]


def transition_matrix(states: Sequence[int], k: int) -> np.ndarray:
    s = np.asarray(states, int)
    M = np.zeros((k, k))
    for a, b in zip(s[:-1], s[1:]):
        M[a, b] += 1
    rs = M.sum(1, keepdims=True)
    return np.divide(M, rs, out=np.zeros_like(M), where=rs > 0)
