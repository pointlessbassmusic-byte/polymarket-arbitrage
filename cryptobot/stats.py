"""Selection-bias and overfitting diagnostics for the bounce-short rule.

The live rule ("short: move_1d[2] & move_3d[0], +20%/-10%, 14d") was the
best of a search: 7 daily features, every two-feature tercile cell, on
both sides, over a dozen barrier geometries. A walk-forward that refits
the cuts each year says nothing about how many other candidates were
looked at before this one was kept. This module measures that.

  psr / min_trl       probabilistic Sharpe ratio with sample skew and
                      kurtosis, and the track record length at which a
                      Sharpe ratio becomes significant (Bailey & Lopez de
                      Prado 2012).
  expected_max_sr     E[max] of N trials' Sharpe ratios under the null,
                      from the Euler-Mascheroni approximation; dsr() is
                      the PSR against that threshold (Bailey & LdP 2014,
                      "The Deflated Sharpe Ratio").
  n_eff_from_corr     effective number of independent trials, two ways:
                      the paper's appendix-A.3 estimate from the mean
                      pairwise correlation, and the participation ratio
                      of the correlation matrix, M^2 / trace(C^2). The
                      trace is exact for small M and a Hutchinson
                      estimate (random +-1 probes) for large M, because a
                      full eigendecomposition in pure Python is too slow.
  cscv_pbo            probability of backtest overfitting (Bailey,
                      Borwein, LdP, Zhu 2014): every symmetric split of S
                      time-contiguous blocks, select the in-sample best,
                      look at its out-of-sample rank. Per-block partial
                      sums make each split O(S) per column.
  cpcv_paths          combinatorial purged cross-validation of ONE rule,
                      cuts refitted on the training groups of each split,
                      stitched into backtest paths.
  trial_matrix        the T x N matrix of daily P&L for every candidate
                      that was in the running, built from perp_study.

Pure standard library: statistics.NormalDist supplies Phi and its inverse.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import math
import pickle
import random
import statistics
import time
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

from cryptobot.perp_study import (DAILY_FEATURES, collect, funding_by_year,
                                  parse_rule, round_trip_cost)
from cryptobot.research import Barrier, bucket_of, quantiles

EULER_GAMMA = 0.5772156649015329
DAY = 86400.0
_N01 = NormalDist()

# Barrier geometries actually swept before the live rule was kept
# (scratch rule_robust.py / hl_sweep.py): four target/stop pairs by three
# horizons.
DEFAULT_GEOMETRIES = tuple((t, s, h) for t, s in ((0.08, 0.04), (0.10, 0.05),
                                                   (0.15, 0.05), (0.20, 0.10))
                           for h in (3, 7, 14))


# ------------------------------------------------------------ Sharpe tests

def moments(returns) -> dict:
    """n, mean, sd (sample), skew, kurtosis (non-excess) of a series."""
    xs = list(returns)
    n = len(xs)
    if n < 3:
        return {"n": n, "mean": statistics.mean(xs) if xs else 0.0,
                "sd": 0.0, "skew": 0.0, "kurt": 3.0}
    m = statistics.fmean(xs)
    d = [x - m for x in xs]
    m2 = sum(v * v for v in d) / n
    if m2 <= 0:
        return {"n": n, "mean": m, "sd": 0.0, "skew": 0.0, "kurt": 3.0}
    m3 = sum(v ** 3 for v in d) / n
    m4 = sum(v ** 4 for v in d) / n
    return {"n": n, "mean": m, "sd": math.sqrt(m2 * n / (n - 1)),
            "skew": m3 / m2 ** 1.5, "kurt": m4 / (m2 * m2)}


def sharpe(returns) -> float:
    mo = moments(returns)
    return mo["mean"] / mo["sd"] if mo["sd"] > 0 else 0.0


def _sr_denominator(sr: float, skew: float, kurt: float) -> float:
    return math.sqrt(max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr, 1e-12))


def psr(returns, sr_star: float = 0.0) -> float:
    """Probability that the true Sharpe ratio exceeds `sr_star`, given
    the sample SR, its length and its non-normality:

        PSR = Phi[ (SR - SR*) sqrt(T - 1) / sqrt(1 - g3 SR + (g4 - 1)/4 SR^2) ]

    with g3 the skewness and g4 the (non-excess) kurtosis. SR and SR* are
    per observation, not annualised."""
    mo = moments(returns)
    if mo["n"] < 3 or mo["sd"] <= 0:
        return 0.0
    sr = mo["mean"] / mo["sd"]
    z = (sr - sr_star) * math.sqrt(mo["n"] - 1) / _sr_denominator(sr, mo["skew"], mo["kurt"])
    return _N01.cdf(z)


def min_trl(returns, sr_star: float = 0.0, alpha: float = 0.05) -> float:
    """Minimum track record length (in observations) for the sample SR to
    beat `sr_star` at confidence 1 - alpha. Infinite if SR <= SR*."""
    mo = moments(returns)
    if mo["n"] < 3 or mo["sd"] <= 0:
        return math.inf
    sr = mo["mean"] / mo["sd"]
    if sr <= sr_star:
        return math.inf
    z = _N01.inv_cdf(1.0 - alpha)
    return 1.0 + _sr_denominator(sr, mo["skew"], mo["kurt"]) ** 2 * (z / (sr - sr_star)) ** 2


def expected_max_sr(n_trials: float, var_sr: float) -> float:
    """E[max of N trials' SR] under the null that every true SR is zero:

        sqrt(V) * ((1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e)))

    g the Euler-Mascheroni constant. N may be fractional (an effective
    count); N <= 1 gives 0."""
    if n_trials <= 1.0 or var_sr <= 0:
        return 0.0
    z = ((1.0 - EULER_GAMMA) * _N01.inv_cdf(1.0 - 1.0 / n_trials)
         + EULER_GAMMA * _N01.inv_cdf(1.0 - 1.0 / (n_trials * math.e)))
    return max(0.0, math.sqrt(var_sr) * z)


def dsr(returns, n_trials: float, var_sr_across_trials: float) -> float:
    """Deflated Sharpe ratio: PSR against the expected maximum SR of the
    trials that were run. The variance must be measured on SRs at the
    same observation frequency as `returns`."""
    return psr(returns, expected_max_sr(n_trials, var_sr_across_trials))


# ------------------------------------------------- effective trial count

def _standardize(columns):
    """Zero-mean, unit-norm copies of the columns with variance (constant
    columns are dropped: they correlate with nothing)."""
    out = []
    for col in columns:
        xs = list(col)
        if len(xs) < 2:
            continue
        m = statistics.fmean(xs)
        d = [x - m for x in xs]
        norm = math.sqrt(sum(v * v for v in d))
        if norm <= 0:
            continue
        out.append(array("d", [v / norm for v in d]))
    return out


def _z_times(z, g):
    """Z g for column-major Z (list of T-vectors) and an M-vector g."""
    t = len(z[0])
    y = [0.0] * t
    for gi, col in zip(g, z):
        if gi:
            y = [a + gi * b for a, b in zip(y, col)]
    return y


def _zt_times(z, y):
    """Z^T y: one dot product per column."""
    return [sum(x * v for x, v in zip(col, y)) for col in z]


def n_eff_from_corr(columns, exact_limit: int = 400, probes: int = 24,
                    power_iters: int = 12, seed: int = 7) -> dict:
    """Effective number of independent trials among the columns.

    a3    Bailey & LdP (2014) appendix A.3:  N_eff = rho + (1 - rho) M,
          rho the mean pairwise correlation (clipped to [0, 1]).
    pr    participation ratio of the correlation matrix C (M x M):
          (sum lambda)^2 / sum lambda^2 = M^2 / trace(C^2). Exact for
          M <= exact_limit (all pairwise dot products); otherwise a
          Hutchinson estimate of trace(C^2) from `probes` Rademacher
          vectors, with its standard error. No eigendecomposition.
    top_share  lambda_1 / M from `power_iters` power iterations: how much
          of the trials' variance one common factor explains (a lower
          bound; power iteration converges from below).
    """
    z = _standardize(columns)
    m = len(z)
    if m == 0:
        return {"m": 0, "rho": 0.0, "n_eff_a3": 0.0, "n_eff_pr": 0.0,
                "pr_method": "none", "pr_se": 0.0, "top_share": 0.0}
    if m == 1:
        return {"m": 1, "rho": 1.0, "n_eff_a3": 1.0, "n_eff_pr": 1.0,
                "pr_method": "exact", "pr_se": 0.0, "top_share": 1.0}
    s = _z_times(z, [1.0] * m)
    rho = (sum(v * v for v in s) - m) / (m * (m - 1))
    rho_c = min(1.0, max(0.0, rho))
    n_eff_a3 = rho_c + (1.0 - rho_c) * m

    if m <= exact_limit:
        off = 0.0
        for i in range(m):
            zi = z[i]
            for j in range(i + 1, m):
                c = sum(x * y for x, y in zip(zi, z[j]))
                off += c * c
        tr2 = m + 2.0 * off
        method, se = "exact", 0.0
    elif probes <= 0:
        tr2 = m * m / n_eff_a3            # no estimate asked for: fall back to A.3
        method, se = "skipped, A.3 used", 0.0
    else:
        rng = random.Random(seed)
        ests = []
        for _ in range(probes):
            g = [1.0 if rng.random() < 0.5 else -1.0 for _ in range(m)]
            w = _zt_times(z, _z_times(z, g))
            ests.append(sum(v * v for v in w))
        tr2 = statistics.fmean(ests)
        se = statistics.stdev(ests) / math.sqrt(len(ests)) if len(ests) > 1 else 0.0
        method = f"hutchinson({probes})"
    n_eff_pr = m * m / tr2 if tr2 > 0 else float(m)
    pr_se = n_eff_pr * se / tr2 if tr2 > 0 else 0.0

    top = 0.0
    if power_iters > 0:
        rng = random.Random(seed + 1)
        v = [rng.gauss(0, 1) for _ in range(m)]
        for _ in range(power_iters):
            w = _zt_times(z, _z_times(z, v))
            lam = math.sqrt(sum(x * x for x in w))
            if lam <= 0:
                break
            v = [x / lam for x in w]
            top = lam
    return {"m": m, "rho": rho, "n_eff_a3": n_eff_a3, "n_eff_pr": n_eff_pr,
            "pr_method": method, "pr_se": pr_se, "top_share": top / m}


# -------------------------------------------------------------- CSCV / PBO

def _rank_avg(vals) -> list[float]:
    """1-based ranks, ties get the average rank (higher value = higher rank)."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def spearman(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    rx, ry = _rank_avg(xs), _rank_avg(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def _stats_of(seq) -> tuple:
    """(count, sum, sum of squares, nonzero count)."""
    s = ss = 0.0
    nz = 0
    for v in seq:
        s += v
        ss += v * v
        if v:
            nz += 1
    return (len(seq), s, ss, nz)


def _metric(metric: str, st: tuple) -> float:
    n, s, ss, nz = st
    if n <= 0:
        return 0.0
    if metric == "mean":
        return s / n
    if metric == "per_signal":
        return s / nz if nz else 0.0
    mean = s / n
    var = ss / n - mean * mean
    return mean / math.sqrt(var) if var > 1e-18 else 0.0


def _block_bounds(t: int, n_blocks: int) -> list[int]:
    return [round(t * k / n_blocks) for k in range(n_blocks + 1)]


def cscv_pbo(columns, n_blocks: int = 10, purge: int = 0, metric: str = "sharpe",
             named: int | None = None) -> dict:
    """Combinatorially symmetric cross-validation over N trials.

    `columns` is the T x N P&L matrix given as N columns of length T
    (or an object with a `.data` attribute holding them). The T rows are
    cut into `n_blocks` time-contiguous blocks; for every choice of half
    of the blocks as in-sample (IS) the rest is out-of-sample (OOS). The
    IS-best column by `metric` ('sharpe', 'mean' or 'per_signal') is
    looked up OOS; its relative OOS rank w in (0, 1) gives the logit
    ln(w / (1 - w)). PBO is the share of splits with a negative logit.

    `purge` drops that many rows from the head and tail of every IS block
    that borders an OOS block, so IS labels spanning `purge` days do not
    overlap OOS labels. Returns the PBO, the logit distribution, the mean
    IS-vs-OOS Spearman across splits, the OOS loss probability of the
    IS-best, and the OOS/IS rank distribution of column `named`.
    """
    data = getattr(columns, "data", columns)
    n = len(data)
    if n < 2:
        raise ValueError("need at least two trials")
    t = len(data[0])
    if n_blocks % 2 or n_blocks < 2:
        raise ValueError("n_blocks must be even and >= 2")
    bounds = _block_bounds(t, n_blocks)
    min_len = min(bounds[k + 1] - bounds[k] for k in range(n_blocks))
    if purge < 0 or 2 * purge > min_len:
        raise ValueError(f"purge {purge} too large for blocks of {min_len} rows")

    # per column, per block: full / head / tail stats
    full, head, tail = [], [], []
    for col in data:
        f, h, tl = [], [], []
        for k in range(n_blocks):
            seg = col[bounds[k]:bounds[k + 1]]
            f.append(_stats_of(seg))
            h.append(_stats_of(seg[:purge]) if purge else (0, 0.0, 0.0, 0))
            tl.append(_stats_of(seg[len(seg) - purge:]) if purge else (0, 0.0, 0.0, 0))
        full.append(f)
        head.append(h)
        tail.append(tl)

    half = n_blocks // 2
    logits, spearmans, loss, best_oos_metric = [], [], 0, []
    named_oos, named_is, named_best = [], [], 0
    per_split = []
    for is_blocks in itertools.combinations(range(n_blocks), half):
        in_is = [False] * n_blocks
        for k in is_blocks:
            in_is[k] = True
        oos_blocks = [k for k in range(n_blocks) if not in_is[k]]
        is_m, oos_m = [], []
        for c in range(n):
            cnt = s = ss = 0.0
            nz = 0
            for k in is_blocks:
                st = full[c][k]
                cnt += st[0]; s += st[1]; ss += st[2]; nz += st[3]
                if purge and k > 0 and not in_is[k - 1]:
                    st = head[c][k]
                    cnt -= st[0]; s -= st[1]; ss -= st[2]; nz -= st[3]
                if purge and k + 1 < n_blocks and not in_is[k + 1]:
                    st = tail[c][k]
                    cnt -= st[0]; s -= st[1]; ss -= st[2]; nz -= st[3]
            is_m.append(_metric(metric, (int(cnt), s, ss, nz)))
            cnt = s = ss = 0.0
            nz = 0
            for k in oos_blocks:
                st = full[c][k]
                cnt += st[0]; s += st[1]; ss += st[2]; nz += st[3]
            oos_m.append(_metric(metric, (int(cnt), s, ss, nz)))
        best = max(range(n), key=lambda c: is_m[c])
        oos_rank = _rank_avg(oos_m)
        w = oos_rank[best] / (n + 1.0)
        lam = math.log(w / (1.0 - w))
        logits.append(lam)
        rho = spearman(is_m, oos_m)
        spearmans.append(rho)
        loss += oos_m[best] < 0
        best_oos_metric.append(oos_m[best])
        rec = {"is_blocks": is_blocks, "best": best, "logit": lam, "spearman": rho,
               "best_oos": oos_m[best]}
        if named is not None:
            is_rank = _rank_avg(is_m)
            named_oos.append(oos_rank[named] / (n + 1.0))
            named_is.append(is_rank[named] / (n + 1.0))
            named_best += best == named
            rec["named_oos_rel"] = named_oos[-1]
            rec["named_is_rel"] = named_is[-1]
        per_split.append(rec)

    ns = len(logits)
    srt = sorted(logits)
    out = {
        "n_trials": n, "t": t, "n_blocks": n_blocks, "n_splits": ns, "purge": purge,
        "metric": metric,
        "pbo": sum(l < 0 for l in logits) / ns,
        "logit_mean": statistics.fmean(logits), "logit_median": statistics.median(logits),
        "logit_min": srt[0], "logit_max": srt[-1],
        "logit_q10": srt[int(0.10 * (ns - 1))], "logit_q90": srt[int(0.90 * (ns - 1))],
        "spearman_mean": statistics.fmean(spearmans),
        "spearman_min": min(spearmans), "spearman_max": max(spearmans),
        "prob_loss_oos": loss / ns,
        "best_oos_mean": statistics.fmean(best_oos_metric),
        "splits": per_split,
    }
    if named is not None:
        out["named"] = {
            "index": named, "oos_rel_mean": statistics.fmean(named_oos),
            "oos_rel_median": statistics.median(named_oos),
            "oos_rel_min": min(named_oos), "oos_rel_max": max(named_oos),
            "oos_above_median": sum(w > 0.5 for w in named_oos) / ns,
            "is_rel_mean": statistics.fmean(named_is),
            "is_best_share": named_best / ns,
        }
    return out


# ---------------------------------------------------------- trial matrix

@dataclass
class TrialMatrix:
    timestamps: list
    names: list
    data: list                      # N columns, each array('d') of length T
    signal_days: list
    trades: list
    nominal: int                    # cells before the signal-day filter
    meta: list = field(default_factory=list)
    fired: list = field(default_factory=list)      # per column, bytes mask of signal days
    uncond: dict = field(default_factory=dict)     # (side, target, stop, days) -> array
    build_seconds: float = 0.0

    @property
    def n(self) -> int:
        return len(self.data)

    @property
    def t(self) -> int:
        return len(self.timestamps)

    def index(self, name: str) -> int:
        return self.names.index(name)


def lift_columns(tm: TrialMatrix, mode: str = "same_day") -> list:
    """Each trial's lift over the unconditional side of its own column set.

    same_day   rule - unconditional on the days the rule fires, else 0:
               the cross-sectional edge, timing netted out
    always     rule - unconditional on every day: the rule's book against
               an always-on book of the same side, timing included
    """
    out = []
    for col, meta, mask in zip(tm.data, tm.meta, tm.fired):
        unc = tm.uncond[meta["set"]]
        if mode == "always":
            out.append(array("d", [c - u for c, u in zip(col, unc)]))
        else:
            out.append(array("d", [c - u if f else 0.0 for c, u, f in zip(col, unc, mask)]))
    return out


def geometry_label(target: float, stop: float, days: int) -> str:
    return f"+{100 * target:.0f}/-{100 * stop:.0f} {days}d"


def rule_label(rule: tuple, features=DAILY_FEATURES) -> str:
    """Canonical 'f1[b1] & f2[b2]' with f1 before f2 in feature order, the
    way research.candidate_rules names its cells."""
    (f1, b1), (f2, b2) = rule
    if features.index(f1) > features.index(f2):
        (f1, b1), (f2, b2) = (f2, b2), (f1, b1)
    return f"{f1}[{b1}] & {f2}[{b2}]"


def column_name(side: str, target: float, stop: float, days: int, rule: tuple) -> str:
    return f"{side} {geometry_label(target, stop, days)} {rule_label(rule)}"


def make_cost_fn(side: str, days: int, fy: dict, flat_cost: float | None = None):
    """Per-year round-trip cost: fees + slippage + realised funding over
    half the horizon, or a flat figure."""
    if flat_cost is not None:
        return lambda year: flat_cost
    return lambda year: round_trip_cost(days / 2.0, fy.get(year, 0.0), side)


def trial_matrix(pools, funding, geometries=DEFAULT_GEOMETRIES, sides=("long", "short"),
                 features=DAILY_FEATURES, min_signal_days: int = 30, n_bands: int = 3,
                 flat_cost: float | None = None) -> TrialMatrix:
    """Daily net P&L of every candidate rule, one column per
    (side, geometry, two-feature tercile cell).

    Rows come from perp_study.collect; the cuts for each column set are
    fitted on all of that set's rows, as research.validate does. Day t of
    a column is the mean net P&L (barrier outcome minus that year's round
    trip cost, or `flat_cost`) across the coins whose rule fires on t,
    and 0 on days with no signal. The timeline is the days present in
    every column set (the longest horizon trims the end). Columns with
    fewer than `min_signal_days` signal days are dropped but still
    counted in `nominal`.
    """
    t0 = time.time()
    fy = funding_by_year(funding) if funding else {}
    sets = []
    common = None
    for (target, stop, days) in geometries:
        for side in sides:
            rows = collect(pools, Barrier(target, stop), days, side)
            if not rows:
                continue
            ts = {r["ts"] for r in rows}
            common = ts if common is None else common & ts
            sets.append((side, target, stop, days, rows))
    timeline = sorted(common or [])
    idx = {ts: i for i, ts in enumerate(timeline)}
    big_t = len(timeline)
    pairs = list(itertools.combinations(features, 2))
    names, data, signal_days, trades, meta, fired, uncond = [], [], [], [], [], [], {}
    nominal = 0
    for side, target, stop, days, rows in sets:
        cost = make_cost_fn(side, days, fy, flat_cost)
        cuts = {f: quantiles(rows, f, n_bands) for f in features}
        buckets = {f: [bucket_of(r[f], cuts[f]) for r in rows] for f in features}
        day = [idx.get(r["ts"]) for r in rows]
        net = [r["pnl"] - cost(r["year"]) for r in rows]
        key = (side, target, stop, days)
        us, uc = [0.0] * big_t, [0] * big_t
        for d, v in zip(day, net):
            if d is not None:
                us[d] += v
                uc[d] += 1
        uncond[key] = array("d", [us[d] / uc[d] if uc[d] else 0.0 for d in range(big_t)])
        for f1, f2 in pairs:
            b1s, b2s = buckets[f1], buckets[f2]
            sums = [[0.0] * big_t for _ in range(n_bands * n_bands)]
            cnts = [[0] * big_t for _ in range(n_bands * n_bands)]
            for i in range(len(rows)):
                d = day[i]
                if d is None:
                    continue
                cell = b1s[i] * n_bands + b2s[i]
                sums[cell][d] += net[i]
                cnts[cell][d] += 1
            for b1 in range(n_bands):
                for b2 in range(n_bands):
                    cell = b1 * n_bands + b2
                    nominal += 1
                    cn = cnts[cell]
                    sd = sum(1 for c in cn if c)
                    if sd < min_signal_days:
                        continue
                    sm = sums[cell]
                    col = array("d", [sm[d] / cn[d] if cn[d] else 0.0 for d in range(big_t)])
                    names.append(column_name(side, target, stop, days, ((f1, b1), (f2, b2))))
                    data.append(col)
                    signal_days.append(sd)
                    trades.append(sum(cn))
                    fired.append(bytes(1 if c else 0 for c in cn))
                    meta.append({"side": side, "target": target, "stop": stop, "days": days,
                                 "rule": ((f1, b1), (f2, b2)), "set": key})
    return TrialMatrix(timeline, names, data, signal_days, trades, nominal, meta, fired,
                       uncond, time.time() - t0)


def block_sums(series, size: int) -> list[float]:
    """Sum of consecutive non-overlapping blocks; a trailing partial block
    is dropped."""
    n = len(series) // size
    return [sum(series[k * size:(k + 1) * size]) for k in range(n)]


def rule_series(rows, rule: tuple, cost_fn, cuts: dict | None = None, n_bands: int = 3) -> dict:
    """Calendar-day series for one two-feature rule from collect() rows.

    rule    mean net P&L across coins firing that day, 0 otherwise
    uncond  mean net P&L across every coin that day (the unconditional
            side on the same day)
    lift    rule - uncond on signal days, 0 otherwise
    Cuts default to terciles on all the rows (the selected backtest).
    """
    (f1, b1), (f2, b2) = rule
    if cuts is None:
        cuts = {f: quantiles(rows, f, n_bands) for f in (f1, f2)}
    ts = sorted({r["ts"] for r in rows})
    idx = {t: i for i, t in enumerate(ts)}
    big_t = len(ts)
    rs, rc, us, uc = [0.0] * big_t, [0] * big_t, [0.0] * big_t, [0] * big_t
    for r in rows:
        i = idx[r["ts"]]
        v = r["pnl"] - cost_fn(r["year"])
        us[i] += v
        uc[i] += 1
        if bucket_of(r[f1], cuts[f1]) == b1 and bucket_of(r[f2], cuts[f2]) == b2:
            rs[i] += v
            rc[i] += 1
    rule_d = [rs[i] / rc[i] if rc[i] else 0.0 for i in range(big_t)]
    unc_d = [us[i] / uc[i] if uc[i] else 0.0 for i in range(big_t)]
    lift = [rule_d[i] - unc_d[i] if rc[i] else 0.0 for i in range(big_t)]
    lift_always = [rule_d[i] - unc_d[i] for i in range(big_t)]
    return {"ts": ts, "rule": rule_d, "uncond": unc_d, "lift": lift,
            "lift_always": lift_always, "fired": rc,
            "n_trades": sum(rc), "signal_days": sum(1 for c in rc if c), "cuts": cuts}


# ------------------------------------------------------------------ CPCV

def cpcv_splits(timestamps, n_groups: int = 6, n_test: int = 2, purge_days: int = 0,
                embargo_days: int = 0) -> tuple[list, list]:
    """Time-contiguous groups of distinct days and every choice of
    `n_test` of them as the test set. Training days whose label window
    [t, t + purge] would touch a test window, or that fall within
    `embargo_days` after one, are left out."""
    ts = sorted(set(timestamps))
    big_t = len(ts)
    bounds = _block_bounds(big_t, n_groups)
    groups = [ts[bounds[k]:bounds[k + 1]] for k in range(n_groups)]
    purge, embargo = purge_days * DAY, embargo_days * DAY
    splits = []
    for test in itertools.combinations(range(n_groups), n_test):
        windows = [(groups[g][0], groups[g][-1]) for g in test if groups[g]]
        train = []
        for g in range(n_groups):
            if g in test:
                continue
            for t in groups[g]:
                if any(a - purge <= t <= e + purge + embargo for a, e in windows):
                    continue
                train.append(t)
        test_ts = sorted(t for g in test for t in groups[g])
        splits.append({"test_groups": test, "train": train, "test": test_ts})
    return groups, splits


def cpcv_paths(rows, rule: tuple, cost_fn, n_groups: int = 6, n_test: int = 2,
               purge_days: int = 0, embargo_frac: float = 0.01, n_bands: int = 3) -> dict:
    """Combinatorial purged cross-validation of one rule.

    For each of the C(n_groups, n_test) splits the tercile cuts are refit
    on the purged training days and the rule is scored on the test
    groups. Each group is a test group in C(n_groups - 1, n_test - 1)
    splits; the j-th of those feeds backtest path j, so every path is a
    full-length out-of-sample series stitched from different fits.

    Per path: daily Sharpe (calendar days, 0 when flat), net per trade,
    the unconditional side's net per trade, lift. Per split: the same on
    the test window only. Fractions of positive net and positive lift
    over both.
    """
    (f1, b1), (f2, b2) = rule
    ts_all = sorted({r["ts"] for r in rows})
    big_t = len(ts_all)
    embargo_days = math.ceil(embargo_frac * big_t)
    groups, splits = cpcv_splits(ts_all, n_groups, n_test, purge_days, embargo_days)
    group_of = {}
    for g, gts in enumerate(groups):
        for t in gts:
            group_of[t] = g
    by_ts: dict = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r)
    net_of = {id(r): r["pnl"] - cost_fn(r["year"]) for r in rows}

    results = {}            # (split index, group) -> per-day (rule sum, cnt, unc sum, cnt)
    split_rows = []
    for si, sp in enumerate(splits):
        train = [r for t in sp["train"] for r in by_ts.get(t, [])]
        if len(train) < 50:
            continue
        cuts = {f: quantiles(train, f, n_bands) for f in (f1, f2)}
        rsum = rcnt = usum = ucnt = 0.0
        for t in sp["test"]:
            g = group_of[t]
            day = results.setdefault((si, g), {})
            rs = rc = us = uc = 0.0
            for r in by_ts.get(t, []):
                v = net_of[id(r)]
                us += v
                uc += 1
                if bucket_of(r[f1], cuts[f1]) == b1 and bucket_of(r[f2], cuts[f2]) == b2:
                    rs += v
                    rc += 1
            day[t] = (rs, rc, us, uc)
            rsum += rs; rcnt += rc; usum += us; ucnt += uc
        net = rsum / rcnt if rcnt else 0.0
        bench = usum / ucnt if ucnt else 0.0
        split_rows.append({"split": si, "test_groups": sp["test_groups"], "n_train": len(train),
                           "n": int(rcnt), "net": net, "bench": bench, "lift": net - bench,
                           "cuts": cuts})

    n_paths = math.comb(n_groups - 1, n_test - 1)
    paths = []
    for j in range(n_paths):
        daily, rsum, rcnt, usum, ucnt = [], 0.0, 0.0, 0.0, 0.0
        for g in range(n_groups):
            owners = [si for si, sp in enumerate(splits) if g in sp["test_groups"]
                      and (si, g) in results]
            if j >= len(owners):
                continue
            day = results[(owners[j], g)]
            for t in groups[g]:
                rs, rc, us, uc = day.get(t, (0.0, 0.0, 0.0, 0.0))
                daily.append(rs / rc if rc else 0.0)
                rsum += rs; rcnt += rc; usum += us; ucnt += uc
        net = rsum / rcnt if rcnt else 0.0
        bench = usum / ucnt if ucnt else 0.0
        paths.append({"path": j, "days": len(daily), "n": int(rcnt), "sharpe": sharpe(daily),
                      "net": net, "bench": bench, "lift": net - bench,
                      "total": sum(daily), "daily": daily})
    out = {"n_groups": n_groups, "n_test": n_test, "purge_days": purge_days,
           "embargo_days": embargo_days, "n_splits": len(splits), "n_paths": len(paths),
           "paths": paths, "splits": split_rows}
    if paths:
        out["frac_paths_pos_net"] = sum(p["net"] > 0 for p in paths) / len(paths)
        out["frac_paths_pos_lift"] = sum(p["lift"] > 0 for p in paths) / len(paths)
        out["frac_paths_pos_sharpe"] = sum(p["sharpe"] > 0 for p in paths) / len(paths)
    if split_rows:
        out["frac_splits_pos_net"] = sum(s["net"] > 0 for s in split_rows) / len(split_rows)
        out["frac_splits_pos_lift"] = sum(s["lift"] > 0 for s in split_rows) / len(split_rows)
    return out


# ------------------------------------------------------------------- CLI

def _months(n_obs: float, days_per_obs: int) -> str:
    return "inf" if math.isinf(n_obs) else f"{n_obs * days_per_obs / 30.4:.0f}mo"


def _series_report(label: str, series, n_nominal: float, n_eff: float,
                   var_sr: float, per: str, days_per_obs: int) -> list[str]:
    mo = moments(series)
    sr = sharpe(series)
    lines = [f"  {label}: T={mo['n']} {per}, SR={sr:+.4f}/{per}, skew={mo['skew']:+.2f}, "
             f"kurt={mo['kurt']:.1f}, mean={100 * mo['mean']:+.3f}%"]
    p0 = psr(series, 0.0)
    trl0 = min_trl(series, 0.0)
    trl5 = min_trl(series, 0.5 * sr) if sr > 0 else math.inf
    lines.append(f"    PSR(SR*=0)={p0:.3f}  MinTRL(SR*=0)={trl0:.0f} {per} "
                 f"({_months(trl0, days_per_obs)})  MinTRL(SR*=0.5 SR)={trl5:.0f} {per} "
                 f"({_months(trl5, days_per_obs)})")
    e_nom = expected_max_sr(n_nominal, var_sr)
    e_eff = expected_max_sr(n_eff, var_sr)
    lines.append(f"    E[max SR] N={n_nominal:.0f}: {e_nom:+.4f}  N_eff={n_eff:.1f}: {e_eff:+.4f}  "
                 f"(var SR across trials {var_sr:.2e})")
    lines.append(f"    DSR N={n_nominal:.0f}: {dsr(series, n_nominal, var_sr):.3f}  "
                 f"N_eff={n_eff:.1f}: {dsr(series, n_eff, var_sr):.3f}")
    return lines


def _var_sr(columns) -> float:
    srs = [sharpe(c) for c in columns]
    return statistics.pvariance(srs) if len(srs) > 1 else 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--funding", type=Path)
    ap.add_argument("--rule", required=True, help="e.g. 'short:move_1d[2]&move_3d[0]'")
    ap.add_argument("--target", type=float, default=0.20)
    ap.add_argument("--stop", type=float, default=0.10)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--blocks", type=int, default=10, help="CSCV blocks (even)")
    ap.add_argument("--flat-cost", type=float, default=None,
                    help="flat round trip instead of fees + realised funding")
    ap.add_argument("--metric", choices=("sharpe", "mean", "per_signal"), default="sharpe")
    ap.add_argument("--sides", default="long,short",
                    help="sides in the trial matrix (the search looked at both)")
    ap.add_argument("--geometries", default=None,
                    help="comma list of target/stop/days, e.g. 0.2/0.1/14; default: the 12 swept")
    ap.add_argument("--min-signal-days", type=int, default=30)
    ap.add_argument("--probes", type=int, default=24, help="Hutchinson probes for N_eff")
    args = ap.parse_args(argv)
    t0 = time.time()

    pools = pickle.loads(args.cache.read_bytes())
    funding = pickle.loads(args.funding.read_bytes()) if args.funding else {}
    fy = funding_by_year(funding) if funding else {}
    side, _, rule_text = args.rule.partition(":")
    rule = parse_rule(rule_text)
    sides = tuple(s.strip() for s in args.sides.split(",") if s.strip())
    if args.geometries:
        geoms = []
        for g in args.geometries.split(","):
            t, s, d = g.split("/")
            geoms.append((float(t), float(s), int(d)))
    else:
        geoms = list(DEFAULT_GEOMETRIES)
    if (args.target, args.stop, args.days) not in geoms:
        geoms.append((args.target, args.stop, args.days))
    name = column_name(side, args.target, args.stop, args.days, rule)
    cost_label = (f"flat {100 * args.flat_cost:.2f}%" if args.flat_cost is not None
                  else "fees + slippage + realised funding by year")

    print(f"== data == {len(pools)} coins; rule {name}; cost {cost_label}")
    if fy and args.flat_cost is None:
        print("   funding/day by year: " + ", ".join(f"{y}: {100 * v:+.3f}%" for y, v in sorted(fy.items())))

    tm = trial_matrix(pools, funding, geoms, sides, min_signal_days=args.min_signal_days,
                      flat_cost=args.flat_cost)
    print(f"== trial matrix == {len(geoms)} geometries x {len(sides)} sides x "
          f"{tm.nominal // max(1, len(geoms) * len(sides))} cells = {tm.nominal} nominal; "
          f"{tm.n} kept (>= {args.min_signal_days} signal days); T={tm.t} days "
          f"{dt.datetime.utcfromtimestamp(tm.timestamps[0]):%Y-%m-%d}.."
          f"{dt.datetime.utcfromtimestamp(tm.timestamps[-1]):%Y-%m-%d}; built in {tm.build_seconds:.0f}s")
    if name not in tm.names:
        print(f"named rule {name!r} not in the matrix (too few signal days?)")
        return 1
    col = tm.index(name)
    print(f"   named column #{col}: {tm.signal_days[col]} signal days, {tm.trades[col]} trades")

    t1 = time.time()
    ne = n_eff_from_corr(tm.data, probes=args.probes)
    pr_se = f" +-{ne['pr_se']:.1f}" if ne["pr_se"] else ""
    print(f"== N_eff == M={ne['m']}  mean pairwise rho={ne['rho']:+.4f}  "
          f"A.3 N_eff={ne['n_eff_a3']:.1f}  participation ratio={ne['n_eff_pr']:.1f}{pr_se} "
          f"[{ne['pr_method']}]  top eigen share={100 * ne['top_share']:.1f}%  ({time.time() - t1:.0f}s)")
    n_eff = ne["n_eff_pr"]

    t1 = time.time()
    cv = cscv_pbo(tm, n_blocks=args.blocks, purge=args.days, metric=args.metric, named=col)
    nm = cv["named"]
    print(f"== CSCV == S={cv['n_blocks']} blocks, {cv['n_splits']} splits, metric={cv['metric']}, "
          f"purge={cv['purge']}d ({time.time() - t1:.0f}s)")
    print(f"   PBO={cv['pbo']:.3f}  logit mean={cv['logit_mean']:+.2f} median={cv['logit_median']:+.2f} "
          f"q10={cv['logit_q10']:+.2f} q90={cv['logit_q90']:+.2f} [{cv['logit_min']:+.2f}, {cv['logit_max']:+.2f}]")
    print(f"   IS-vs-OOS Spearman: mean={cv['spearman_mean']:+.3f} "
          f"[{cv['spearman_min']:+.3f}, {cv['spearman_max']:+.3f}]  "
          f"P(IS-best loses OOS)={cv['prob_loss_oos']:.3f}")
    print(f"   named rule: OOS rel. rank mean={nm['oos_rel_mean']:.3f} median={nm['oos_rel_median']:.3f} "
          f"[{nm['oos_rel_min']:.3f}, {nm['oos_rel_max']:.3f}]  above median in {100 * nm['oos_above_median']:.0f}% "
          f"of splits; IS rel. rank mean={nm['is_rel_mean']:.3f}; IS-best in {100 * nm['is_best_share']:.0f}%")

    rows = collect(pools, Barrier(args.target, args.stop), args.days, side)
    cost_fn = make_cost_fn(side, args.days, fy, args.flat_cost)
    rs = rule_series(rows, rule, cost_fn)
    print(f"== DSR / PSR == {rs['n_trades']} trades on {rs['signal_days']} of {len(rs['ts'])} days; "
          f"N={tm.n} nominal, N_eff={n_eff:.1f} [{ne['pr_method']}]; var SR across trials "
          f"measured on the matching lift columns")
    d = args.days
    variants = (("raw rule P&L", rs["rule"], tm.data),
                ("lift vs unconditional, same days (cross-sectional)", rs["lift"],
                 lift_columns(tm, "same_day")),
                ("lift vs always-short book (timing included)", rs["lift_always"],
                 lift_columns(tm, "always")))
    for label, series, cols in variants:
        var_daily = _var_sr(cols)
        var_block = _var_sr([block_sums(c, d) for c in cols])
        for line in _series_report(f"daily {label}", series, tm.n, n_eff, var_daily, "day", 1):
            print(line)
        for line in _series_report(f"{d}-day blocks {label}", block_sums(series, d), tm.n, n_eff,
                                   var_block, "blk", d):
            print(line)

    t1 = time.time()
    cp = cpcv_paths(rows, rule, cost_fn, n_groups=6, n_test=2, purge_days=args.days,
                    embargo_frac=0.01)
    print(f"== CPCV == groups={cp['n_groups']} test={cp['n_test']} purge={cp['purge_days']}d "
          f"embargo={cp['embargo_days']}d; {cp['n_splits']} splits -> {cp['n_paths']} paths ({time.time() - t1:.0f}s)")
    for p in cp["paths"]:
        print(f"   path {p['path']}: SR={p['sharpe']:+.4f}/day  net/trade={100 * p['net']:+.2f}%  "
              f"bench={100 * p['bench']:+.2f}%  lift={100 * p['lift']:+.2f}%  n={p['n']}  "
              f"sum={100 * p['total']:+.1f}%")
    print(f"   paths: net>0 {100 * cp.get('frac_paths_pos_net', 0):.0f}%  lift>0 "
          f"{100 * cp.get('frac_paths_pos_lift', 0):.0f}%  SR>0 {100 * cp.get('frac_paths_pos_sharpe', 0):.0f}%; "
          f"splits ({len(cp['splits'])}): net>0 {100 * cp.get('frac_splits_pos_net', 0):.0f}%  "
          f"lift>0 {100 * cp.get('frac_splits_pos_lift', 0):.0f}%")
    worst = min(cp["splits"], key=lambda s: s["lift"]) if cp["splits"] else None
    if worst:
        print(f"   worst split: test groups {worst['test_groups']} net={100 * worst['net']:+.2f}% "
              f"bench={100 * worst['bench']:+.2f}% n={worst['n']}")
    print(f"== done in {time.time() - t0:.0f}s ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
