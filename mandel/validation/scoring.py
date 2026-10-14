"""
Proper scoring rules and calibration diagnostics.
==================================================

A scoring rule is *proper* when the forecaster minimises expected score by
reporting their true belief. Brier and log loss are proper; accuracy at a
threshold is not. Mandel evaluates every probabilistic forecast (its own,
the children's, and the market's implied probability) with these rules so
that "improvement" means lower proper score out of sample, not a better
story.

Conventions: ``probs`` are probabilities of the event, ``outcomes`` are 0/1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


def _as_arrays(probs: Sequence[float], outcomes: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(probs, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    if p.shape != o.shape:
        raise ValueError(f"probs and outcomes must align: {p.shape} vs {o.shape}")
    if p.size == 0:
        raise ValueError("need at least one forecast")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must lie in [0, 1]")
    if np.any((o != 0) & (o != 1)):
        raise ValueError("outcomes must be 0 or 1")
    return p, o


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error between probability and outcome. 0 is perfect, 0.25 is the
    score of always saying 0.5, 1 is maximally wrong."""
    p, o = _as_arrays(probs, outcomes)
    return float(np.mean((p - o) ** 2))


def log_loss(probs: Sequence[float], outcomes: Sequence[int], eps: float = 1e-6) -> float:
    """Mean negative log likelihood. Clipped at ``eps`` so a single certain-and-wrong
    forecast is punished heavily but finitely."""
    p, o = _as_arrays(probs, outcomes)
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(o * np.log(p) + (1 - o) * np.log(1 - p)))


@dataclass(frozen=True)
class CalibrationBin:
    lo: float
    hi: float
    n: int
    mean_prob: float
    freq: float          # observed frequency of the event in the bin

    @property
    def gap(self) -> float:
        return self.freq - self.mean_prob


def calibration_table(probs: Sequence[float], outcomes: Sequence[int], n_bins: int = 10) -> list[CalibrationBin]:
    """Equal-width reliability bins. Empty bins are omitted."""
    p, o = _as_arrays(probs, outcomes)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    out: list[CalibrationBin] = []
    for b in range(n_bins):
        mask = idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        out.append(CalibrationBin(
            lo=float(edges[b]), hi=float(edges[b + 1]), n=n,
            mean_prob=float(p[mask].mean()), freq=float(o[mask].mean()),
        ))
    return out


def expected_calibration_error(probs: Sequence[float], outcomes: Sequence[int], n_bins: int = 10) -> float:
    """Weighted mean absolute gap between stated probability and observed frequency."""
    table = calibration_table(probs, outcomes, n_bins)
    total = sum(b.n for b in table)
    return float(sum(b.n / total * abs(b.gap) for b in table))


@dataclass(frozen=True)
class MurphyDecomposition:
    """Brier = reliability - resolution + uncertainty + residual (Murphy 1973, binned form).

    - uncertainty: base-rate variance o_bar(1-o_bar); not under the forecaster's control
    - resolution:  how far the bin frequencies move away from the base rate (higher is better)
    - reliability: how far stated probabilities sit from bin frequencies (lower is better)
    - residual:    within-bin variance of the probabilities minus twice the within-bin
                   covariance of probability and outcome; zero when every bin holds a
                   single probability value. Reported so the identity is exact.
    """
    brier: float
    reliability: float
    resolution: float
    uncertainty: float
    residual: float = 0.0

    @property
    def reconstructed(self) -> float:
        return self.reliability - self.resolution + self.uncertainty + self.residual


def murphy_decomposition(probs: Sequence[float], outcomes: Sequence[int], n_bins: int = 10) -> MurphyDecomposition:
    p, o = _as_arrays(probs, outcomes)
    n_total = p.size
    o_bar = float(o.mean())
    table = calibration_table(p, o, n_bins)
    rel = sum(b.n / n_total * (b.mean_prob - b.freq) ** 2 for b in table)
    res = sum(b.n / n_total * (b.freq - o_bar) ** 2 for b in table)
    unc = o_bar * (1 - o_bar)
    bs = brier_score(p, o)
    residual = bs - (rel - res + unc)
    return MurphyDecomposition(
        brier=bs, reliability=float(rel), resolution=float(res), uncertainty=float(unc), residual=float(residual)
    )


def brier_skill_score(probs: Sequence[float], outcomes: Sequence[int], reference_probs: Sequence[float]) -> float:
    """1 - BS/BS_ref. Positive means better than the reference (e.g. the market price at
    forecast time, or the climatological base rate). A model that cannot beat the market
    price has no edge, whatever its backtest says."""
    bs = brier_score(probs, outcomes)
    bs_ref = brier_score(reference_probs, outcomes)
    if bs_ref == 0:
        return 0.0 if bs == 0 else -math.inf
    return float(1.0 - bs / bs_ref)
