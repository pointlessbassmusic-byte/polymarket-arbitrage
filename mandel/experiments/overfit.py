"""
Backtest-overfitting harness: Probability of Backtest Overfitting (Bailey, Borwein, López de Prado,
Zhu 2014) by combinatorially symmetric cross-validation, plus the deflated Sharpe of the in-sample
winner. Demonstrated on a declared search so the theory "best-of-N looks real" is tested on data.
"""

from __future__ import annotations

import itertools
import math
from typing import Sequence

import numpy as np

from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio


def pbo_cscv(returns: np.ndarray, n_partitions: int = 8) -> dict:
    """returns: (T, N) per-period returns of N strategy variants. Returns PBO and the logit distribution.
    CSCV: split T into S even blocks; for every choice of S/2 blocks as 'train', pick the in-sample best
    variant and record its out-of-sample rank; PBO = fraction of combinations where the IS best is below
    the OOS median."""
    R = np.asarray(returns, dtype=float)
    T, N = R.shape
    S = n_partitions if n_partitions % 2 == 0 else n_partitions + 1
    T = (T // S) * S
    R = R[:T]
    blocks = np.array_split(np.arange(T), S)
    logits = []
    for train_idx in itertools.combinations(range(S), S // 2):
        tr = np.concatenate([blocks[i] for i in train_idx])
        te = np.concatenate([blocks[i] for i in range(S) if i not in train_idx])
        sr_is = np.array([sharpe_ratio(R[tr, j]) for j in range(N)])
        sr_oos = np.array([sharpe_ratio(R[te, j]) for j in range(N)])
        best = int(np.argmax(sr_is))
        rank = (np.sum(sr_oos < sr_oos[best]) + 0.5) / N          # relative OOS rank of the IS winner in (0,1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.asarray(logits)
    return {"pbo": float(np.mean(logits <= 0)), "n_combinations": int(logits.size), "n_variants": int(N), "n_periods": int(T),
            "median_logit": float(np.median(logits))}


def momentum_variants(prices: Sequence[Sequence[float]], lookbacks=(1, 2, 3, 5, 8, 13, 21), holds=(1, 2, 3)) -> tuple[np.ndarray, list[str]]:
    """A declared search of simple momentum rules on daily token prices (long if the price rose over
    `lookback` days, hold `hold` days). Pooled across markets by concatenating per-market return series
    aligned by index. Purely a test bed for PBO/DSR, not a strategy proposal."""
    series = [np.asarray(p, dtype=float) for p in prices if len(p) >= 60]
    names, cols = [], []
    for lb in lookbacks:
        for hd in holds:
            rets = []
            for s in series:
                r = np.diff(s) / np.maximum(s[:-1], 1e-6)
                sig = np.sign(s[lb:-1] - s[:-lb - 1]) if lb + 1 < s.size else np.array([])
                pnl = sig[:len(r) - lb] * r[lb:lb + len(sig)]
                rets.append(pnl[::hd] if hd > 1 else pnl)
            if rets:
                cols.append(np.concatenate(rets)); names.append(f"mom_lb{lb}_h{hd}")
    L = min(c.size for c in cols)
    return np.column_stack([c[:L] for c in cols]), names


def overfit_report(prices: Sequence[Sequence[float]]) -> dict:
    R, names = momentum_variants(prices)
    T, N = R.shape
    srs = np.array([sharpe_ratio(R[:, j]) for j in range(N)])
    best = int(np.argmax(srs))
    dsr_best = deflated_sharpe_ratio(R[:, best], n_trials=N, trial_sharpes=srs)
    p = pbo_cscv(R, n_partitions=8)
    return {"n_variants": N, "n_periods": T, "best_variant": names[best], "best_sharpe": float(srs[best]),
            "dsr_best": float(dsr_best), "pbo": p["pbo"], "pbo_combinations": p["n_combinations"]}
