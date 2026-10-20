"""
Markov-switching multifractal volatility (Calvet & Fisher), binomial, k components.
=====================================================================================

sigma_t^2 = sigma^2 * prod_k M_{k,t}, M in {m0, 2 - m0}, switching probability
gamma_k = 1 - (1 - gamma_1)^(b^(k-1)). The 2^k-state chain has a closed-form likelihood via the
Bayesian filter. Fitted by a coarse grid over (m0, gamma_1, b, sigma) because the parameter space is
tiny; compared out of sample with a rolling-variance baseline on the log score of realised squared
returns. This is the estimable successor of resource A4's model.
"""

from __future__ import annotations

import itertools
import math
from typing import Sequence

import numpy as np


def _states(k: int, m0: float) -> tuple[np.ndarray, np.ndarray]:
    combos = np.array(list(itertools.product([m0, 2 - m0], repeat=k)))      # (2^k, k)
    return combos, combos.prod(axis=1)


def _transition(k: int, gamma1: float, b: float) -> np.ndarray:
    gammas = [1 - (1 - gamma1) ** (b ** i) for i in range(k)]
    P = np.ones((1, 1))
    for g in gammas:
        Pk = np.array([[1 - g / 2, g / 2], [g / 2, 1 - g / 2]])
        P = np.kron(P, Pk)
    return P


def filter_loglik(r: np.ndarray, k: int, m0: float, gamma1: float, b: float, sigma: float) -> tuple[float, np.ndarray]:
    """Log-likelihood and filtered conditional variance path."""
    _, prod = _states(k, m0)
    var = sigma ** 2 * prod                                   # (S,)
    P = _transition(k, gamma1, b)
    S = var.size
    pi = np.full(S, 1.0 / S)
    ll = 0.0
    cond_var = np.empty(r.size)
    for t in range(r.size):
        pred = pi @ P
        cond_var[t] = float(pred @ var)
        dens = np.exp(-0.5 * r[t] ** 2 / var) / np.sqrt(2 * math.pi * var)
        w = pred * dens
        s = w.sum()
        if s <= 0 or not np.isfinite(s):
            return -1e18, cond_var
        ll += math.log(s)
        pi = w / s
    return ll, cond_var


def fit_msm(r: np.ndarray, k: int = 4) -> dict:
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    sig0 = float(r.std(ddof=1)) if r.size > 1 else 1.0
    best = {"ll": -1e18}
    for m0 in (1.2, 1.4, 1.6, 1.8):
        for g1 in (0.02, 0.1, 0.3, 0.6):
            for b in (2.0, 4.0, 8.0):
                for sm in (0.6, 0.8, 1.0, 1.2):
                    ll, _ = filter_loglik(r, k, m0, g1, b, sig0 * sm)
                    if ll > best["ll"]:
                        best = {"ll": ll, "m0": m0, "gamma1": g1, "b": b, "sigma": sig0 * sm}
    return best


def msm_vs_rolling(returns: Sequence[float], k: int = 4, train_frac: float = 0.6, window: int = 20) -> dict:
    """Out-of-sample Gaussian log score of one-step variance forecasts: MSM (fitted on the train part,
    filtered through the test part) against a rolling-window variance baseline."""
    r = np.asarray(returns, dtype=float); r = r[np.isfinite(r)]
    if r.size < 120:
        return {"n_test": 0, "note": "too few returns"}
    cut = int(r.size * train_frac)
    overall = float(r[:cut].var(ddof=1))
    if not np.isfinite(overall) or overall <= 0:
        return {"n_test": 0, "note": "degenerate series (zero variance in the training part)"}
    floor = 1e-3 * overall                        # no forecaster may claim a variance below 0.1% of the series variance
    fit = fit_msm(r[:cut], k)
    _, cv = filter_loglik(r, k, fit["m0"], fit["gamma1"], fit["b"], fit["sigma"])
    test = slice(cut, r.size)
    msm_var = np.maximum(cv[test], floor)
    roll = np.array([r[max(0, t - window):t].var(ddof=1) if t >= 5 else overall for t in range(cut, r.size)])
    roll = np.where(np.isfinite(roll), roll, overall)
    roll = np.maximum(roll, floor)
    def score(v):
        return float(np.mean(-0.5 * np.log(2 * math.pi * v) - 0.5 * r[test] ** 2 / v))
    return {"n_test": int(r.size - cut), "k": k, "fit": fit, "logscore_msm": score(msm_var), "logscore_rolling": score(roll),
            "gain_nats_per_obs": score(msm_var) - score(roll)}
