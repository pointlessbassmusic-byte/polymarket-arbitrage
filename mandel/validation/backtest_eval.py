"""
Out-of-sample strategy comparison.
==================================

The failure mode this module exists to prevent: a candidate strategy looks
better than the incumbent because the search that produced it tried many
variants and kept the luckiest. Three defences, used together:

1. Walk-forward splits with an embargo gap, so every evaluated period is
   strictly after the data used to fit or select the candidate.
2. A block bootstrap on the paired per-period differences, which respects
   autocorrelation and gives a p-value for "candidate beats incumbent".
3. The Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014), which raises
   the bar for the observed Sharpe according to how many trials were run,
   and corrects for non-normal returns and short samples.

All functions accept plain sequences of per-period returns (or PnL).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence

import numpy as np

EULER_MASCHERONI = 0.5772156649015329


# --------------------------------------------------------------------------
# Normal distribution helpers (no scipy dependency)
# --------------------------------------------------------------------------

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse normal CDF, Acklam's rational approximation (rel. error ~1e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


# --------------------------------------------------------------------------
# Moments and Sharpe
# --------------------------------------------------------------------------

def _arr(x: Sequence[float]) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if a.ndim != 1:
        raise ValueError("expected a 1-D sequence of per-period returns")
    return a


def skewness(returns: Sequence[float]) -> float:
    r = _arr(returns)
    if r.size < 3:
        return 0.0
    m = r.mean()
    s = r.std(ddof=0)
    return float(np.mean((r - m) ** 3) / s ** 3) if s > 0 else 0.0


def kurtosis(returns: Sequence[float]) -> float:
    """Non-excess kurtosis (normal = 3), as used in the PSR formula."""
    r = _arr(returns)
    if r.size < 4:
        return 3.0
    m = r.mean()
    s = r.std(ddof=0)
    return float(np.mean((r - m) ** 4) / s ** 4) if s > 0 else 3.0


def sharpe_ratio(returns: Sequence[float], periods_per_year: Optional[float] = None) -> float:
    """Per-period Sharpe (mean/std, ddof=1); annualised by sqrt(periods_per_year) if given."""
    r = _arr(returns)
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    if s == 0:
        return 0.0
    sr = float(r.mean() / s)
    return sr * math.sqrt(periods_per_year) if periods_per_year else sr


def probabilistic_sharpe_ratio(sr_hat: float, sr_benchmark: float, n_obs: int, skew: float, kurt: float) -> float:
    """PSR = P[true SR > sr_benchmark | observed sr_hat], Bailey & Lopez de Prado (2012).

    Uses per-period (non-annualised) Sharpe. ``kurt`` is non-excess kurtosis.
    """
    if n_obs < 2:
        return 0.0
    denom = 1.0 - skew * sr_hat + (kurt - 1.0) / 4.0 * sr_hat ** 2
    if denom <= 0:
        return 0.0
    z = (sr_hat - sr_benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return norm_cdf(z)


def expected_max_sharpe(n_trials: int, var_trials_sr: float) -> float:
    """Expected maximum Sharpe among ``n_trials`` independent zero-skill trials whose
    Sharpe estimates have variance ``var_trials_sr`` (Bailey & Lopez de Prado 2014).

    E[max] ~= sqrt(V) * ((1 - gamma) Z^-1(1 - 1/N) + gamma Z^-1(1 - 1/(N e)))
    """
    if n_trials <= 1 or var_trials_sr <= 0:
        return 0.0
    g = EULER_MASCHERONI
    return math.sqrt(var_trials_sr) * (
        (1 - g) * norm_ppf(1 - 1.0 / n_trials) + g * norm_ppf(1 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(
    returns: Sequence[float],
    n_trials: int,
    var_trials_sr: Optional[float] = None,
    trial_sharpes: Optional[Sequence[float]] = None,
) -> float:
    """Probability that the selected strategy's Sharpe is genuinely above the Sharpe one
    would expect from the *best of N* zero-skill trials.

    Supply either the variance of per-trial Sharpe estimates or the trial Sharpes
    themselves. With ``n_trials=1`` this reduces to PSR against a zero benchmark.
    """
    r = _arr(returns)
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if trial_sharpes is not None:
        ts = _arr(trial_sharpes)
        if ts.size != n_trials:
            raise ValueError(f"got {ts.size} trial Sharpes but n_trials={n_trials}; the trial count must match")
        var_trials_sr = float(ts.var(ddof=1)) if ts.size > 1 else 0.0
    if n_trials > 1 and (var_trials_sr is None or var_trials_sr <= 0):
        # No information about the spread of trial Sharpes: assume every trial was a
        # zero-skill series of this length. Var(SR_hat) under the iid null is 1/(T-1).
        # Without this floor a best-of-N candidate was deflated by nothing at all.
        var_trials_sr = 1.0 / max(1, r.size - 1)
    if var_trials_sr is None:
        var_trials_sr = 0.0
    sr_star = expected_max_sharpe(n_trials, var_trials_sr)
    return probabilistic_sharpe_ratio(
        sr_hat=sharpe_ratio(r), sr_benchmark=sr_star, n_obs=r.size,
        skew=skewness(r), kurt=kurtosis(r),
    )


# --------------------------------------------------------------------------
# Resampling and splits
# --------------------------------------------------------------------------

def _hac_var(x: np.ndarray, bandwidth: int) -> np.ndarray:
    """Row-wise Bartlett (Newey-West) long-run variance of the mean's numerator, bandwidth ``bandwidth``."""
    x = x - x.mean(axis=1, keepdims=True)
    n = x.shape[1]
    lrv = np.sum(x * x, axis=1) / n
    for k in range(1, max(1, bandwidth)):
        w = 1.0 - k / bandwidth
        lrv = lrv + 2.0 * w * np.sum(x[:, k:] * x[:, :-k], axis=1) / n
    return np.maximum(lrv, 1e-300)


def block_bootstrap_pvalue(
    candidate: Sequence[float],
    incumbent: Sequence[float],
    n_boot: int = 2000,
    block_len: Optional[int] = None,
    seed: int = 0,
) -> float:
    """One-sided p-value for H0: mean(candidate - incumbent) <= 0, by a studentized (bootstrap-t)
    circular block bootstrap of the paired differences. Small is good for the candidate.

    The statistic is t = mean / sqrt(LRV / n) with a Bartlett long-run variance whose bandwidth is
    the block length; each resample is studentized the same way, which keeps the test close to its
    nominal size under autocorrelated differences, where a centred percentile bootstrap over-rejects.
    ``block_len`` defaults to about n^(1/3) and is capped at n//4, so there are always at least four
    blocks; a single-block "bootstrap" is a rotation of the data and proves nothing."""
    c, i = _arr(candidate), _arr(incumbent)
    if c.size != i.size:
        raise ValueError("candidate and incumbent must be aligned per period")
    d = c - i
    n = d.size
    if n < 8:
        raise ValueError(f"need at least 8 aligned periods for a block bootstrap, got {n}")
    if block_len is None:
        block_len = max(1, int(round(n ** (1.0 / 3.0))))
    block_len = max(1, min(int(block_len), n // 4))
    observed = d.mean()
    t_obs = observed / math.sqrt(float(_hac_var(d[None, :], block_len)[0]) / n)
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block_len)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offsets = np.arange(block_len)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_boot, -1)[:, :n] % n
    samples = d[idx]
    t_boot = (samples.mean(axis=1) - observed) / np.sqrt(_hac_var(samples, block_len) / n)
    return float((np.sum(t_boot >= t_obs) + 1) / (n_boot + 1))


def walk_forward_splits(
    n: int,
    n_splits: int,
    min_train: int,
    embargo: int = 0,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window splits. Each test window starts ``embargo`` periods after the end
    of its training window, so leakage through autocorrelated labels is removed."""
    if n_splits < 1 or min_train < 1 or min_train + embargo >= n:
        raise ValueError("not enough periods for the requested splits")
    test_total = n - min_train - embargo
    test_len = test_total // n_splits
    if test_len < 1:
        raise ValueError("test windows would be empty")
    for k in range(n_splits):
        test_start = min_train + embargo + k * test_len
        test_end = n if k == n_splits - 1 else test_start + test_len
        train_end = test_start - embargo
        yield np.arange(0, train_end), np.arange(test_start, test_end)


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    n_periods: int
    candidate_sharpe: float
    incumbent_sharpe: float
    mean_diff: float
    bootstrap_p: float
    candidate_dsr: float
    n_trials: int
    notes: list[str] = field(default_factory=list)

    def passes(self, max_p: float = 0.05, min_dsr: float = 0.95) -> bool:
        return self.mean_diff > 0 and self.bootstrap_p <= max_p and self.candidate_dsr >= min_dsr

    def as_dict(self) -> dict:
        return {
            "n_periods": self.n_periods,
            "candidate_sharpe": round(self.candidate_sharpe, 6),
            "incumbent_sharpe": round(self.incumbent_sharpe, 6),
            "mean_diff": self.mean_diff,
            "bootstrap_p": round(self.bootstrap_p, 6),
            "candidate_dsr": round(self.candidate_dsr, 6),
            "n_trials": self.n_trials,
            "notes": list(self.notes),
        }


def compare_strategies(
    candidate: Sequence[float],
    incumbent: Sequence[float],
    *,
    n_trials: int,
    trial_sharpes: Optional[Sequence[float]] = None,
    n_boot: int = 2000,
    block_len: Optional[int] = None,
    seed: int = 0,
) -> ComparisonResult:
    """Compare out-of-sample per-period returns of a candidate against the incumbent.

    ``n_trials`` is required and must be the honest count of variants tried while searching
    for the candidate; understating it is the classic way to fool this test. When
    ``trial_sharpes`` is given its length must equal ``n_trials``.
    """
    c, i = _arr(candidate), _arr(incumbent)
    notes: list[str] = []
    if c.size < 30:
        notes.append(f"only {c.size} periods; statistics are weak below ~30")
    if n_trials <= 1:
        notes.append("n_trials=1: no selection-bias correction applied")
    elif trial_sharpes is None:
        notes.append(f"n_trials={n_trials} without trial Sharpes: deflating with the zero-skill variance floor 1/(n-1)")
    res = ComparisonResult(
        n_periods=int(c.size),
        candidate_sharpe=sharpe_ratio(c),
        incumbent_sharpe=sharpe_ratio(i),
        mean_diff=float((c - i).mean()) if c.size else 0.0,
        bootstrap_p=block_bootstrap_pvalue(c, i, n_boot=n_boot, block_len=block_len, seed=seed),
        candidate_dsr=deflated_sharpe_ratio(c, n_trials=n_trials, trial_sharpes=trial_sharpes),
        n_trials=n_trials,
        notes=notes,
    )
    return res
