"""
Markov baseline (resource 11): a first-order transition model on price buckets is the null
predictor any state-conditioned forecaster must beat. Scored with log loss on held-out steps.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from mandel.validation.scoring import log_loss


def bucketize(prices: Sequence[float], n_buckets: int = 10) -> np.ndarray:
    p = np.clip(np.asarray(prices, dtype=float), 0.0, 1.0)
    return np.minimum((p * n_buckets).astype(int), n_buckets - 1)


def fit_transition(states: np.ndarray, n_states: int, alpha: float = 1.0) -> np.ndarray:
    """Row-stochastic transition matrix with Dirichlet(alpha) smoothing."""
    T = np.full((n_states, n_states), alpha, dtype=float)
    for a, b in zip(states[:-1], states[1:]):
        T[a, b] += 1
    return T / T.sum(axis=1, keepdims=True)


def markov_vs_persistence(prices: Sequence[float], n_buckets: int = 10, train_frac: float = 0.6) -> dict:
    """Compare the first-order Markov predictor of 'next price moves up' against persistence
    (p_up = base rate) on the held-out tail. Returns log losses and the held-out n."""
    p = np.asarray(prices, dtype=float)
    p = p[np.isfinite(p)]
    if p.size < 50:
        return {"n_test": 0, "note": "too few points"}
    up = (np.diff(p) > 0).astype(int)
    s = bucketize(p[:-1], n_buckets)
    cut = int(len(up) * train_frac)
    # Markov: P(up | bucket) from the training part
    counts = np.zeros((n_buckets, 2)) + 0.5
    for st, u in zip(s[:cut], up[:cut]):
        counts[st, u] += 1
    p_up_given = counts[:, 1] / counts.sum(axis=1)
    base = (up[:cut].mean() * cut + 0.5) / (cut + 1)
    test_s, test_u = s[cut:], up[cut:]
    if test_u.size < 20:
        return {"n_test": int(test_u.size), "note": "held-out too short"}
    ll_markov = log_loss(p_up_given[test_s], test_u)
    ll_base = log_loss(np.full(test_u.size, base), test_u)
    return {"n_test": int(test_u.size), "log_loss_markov": ll_markov, "log_loss_base": ll_base,
            "improvement_bits": float((ll_base - ll_markov) / np.log(2)), "n_buckets": n_buckets}
