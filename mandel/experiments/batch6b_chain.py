"""
Batch 6b, group ``chain``: captured-chain arbitrage and financing claims, and the MODEL-PRICED SPY short strangle.
===================================================================================================================

Ten options-library claims, each tested against its claim, trial.pass and trial.min_n as worded.

Captured CBOE delayed chains (options-chain-<SYM>-<capture date>; two capture days so far, 2026-10-14 and 2026-10-15,
both pre-open, so each carries the previous session's 16:15 ET closing quotes: quote days 2026-10-13 and 2026-10-14):
  * T-153 SPY 30/60-DTE mid jelly roll vs bill carry K(e^{-rT1} - e^{-rT2}) - PV(div), strikes within +/- 5%: share of
    strikes within half the four legs' summed spreads >= 95% on EVERY capture (one failing capture falsifies),
    confirmation at 60 captures; min_n 200 strikes (pooled over captures);
  * T-182 SPY conversion lending rate ln(K / (S_ask + P_ask - C_bid)) / T below the 3-month bill in >= 95% of (K, T)
    pairs (30-64 DTE before the 2026-12-18 ex-date, +/- 5%) on day one and on >= 80% of captured days; min_n 100 pairs;
  * T-184 SPY ATM synthetic-long financing rate (call ask, put bid, trailing four distributions) - bill < 50 bp in >= 80%
    of 180-365 DTE expiries on day one and on >= 80% of captured days; min_n 20 EXPIRIES, which one capture day cannot
    reach (SPY lists four or five such expiries), so n counts expiry observations pooled over capture days;
  * T-185 SPY ATM synthetic-short implicit borrow r_bill - r_impl (C_bid - P_ask = S - K e^{-rT}) < 50 bp in >= 80% of
    (K, T) pairs within +/- 2% (30-64 DTE before the ex-date) on day one and on >= 80% of days; min_n 20 pairs;
  * T-191 among SPY puts with K/S >= 1.10, the at-intrinsic share (|P_mid - (K - S)| <= one tick + half the spread) is
    > 30 pp higher where K(1 - e^{-rT}) > C_mid + PV(D) than where it is not, 95% CI excluding 30 pp on day one, stable
    over 20 captured days; min_n 100 puts;
  * T-500 executable credit butterflies (ask wings, bid body; adjacent equally spaced listed strikes within +/- 20%, all
    expiries) on SPX and on SPY: share < 0.5% with the 95% upper bound < 0.5% on day one and on >= 80% of days;
  * T-501 SPY same-strike adjacent-expiry calendars bought for a credit (far ask < near bid): share < 0.1% on day one and
    on >= 80% of days; min_n 5000 pairs;
  * T-507 SPY: S_ask + P_ask < C_ask + K e^{-r_bill T} in >= 60% of strikes (30-64 DTE before the ex-date, +/- 5%) on day
    one and on >= 80% of days; min_n 50;
  * T-508 adjacent-strike verticals violating monotonicity (executable debit < 0) or the width bound (executable credit >
    width; discounted for European SPX) on SPY, SPX, QQQ, GLD and IBIT: share < 0.1% on day one and on >= 80% of days.
Units (house rule 3). Every claim above except T-184 counts strike-expiry objects on the capture day (pairs, strikes,
puts, butterflies, verticals), so day one can meet min_n; every "on >= 80% of captured days" criterion needs at least
MIN_DAYS = 5 capture days to be judged (4 of 5 is the smallest count that can show 80%), T-191's stability 20 days and
T-153's confirmation 60. With two capture days those criteria are undecided (None) unless they already fail whatever
the missing days show (_days_share), so these claims are at best inconclusive today and can fail on day one.

MODEL-PRICED:
  * T-103 30-DTE SPY short strangle at +/- 5% strikes vs the ATM short straddle, both priced with the smile-scaled VIX
    model (sigma(K) = VIX/100 x r(K/S), r the captured spy-smile-* IV/VIX shape, structures.Smile), on the short-straddle
    harness's entry dates (the monthly expiry calendar), 1993-2026: paired Sharpe difference (strangle - straddle) of
    per-cycle excess returns on notional, one-sided p < 0.05, with the same sign under flat VIX and the SKEW-scaled
    smile; min_n 390 monthly cycles; the trial's proxy cap holds the verdict at inconclusive until 60 capture days
    refit the smile ratios.

Conventions
  * Captures and point in time. A capture's quote day comes from its CBOE timestamp (volatility._quote_day: before 13:30
    UTC it carries the previous session's quotes). Intraday captures (13:30-21:15 UTC) are skipped: their quotes are not
    synchronous with any close. A later capture of an already-used quote day is skipped. T = calendar days from the
    quote day to expiry / 365; expiries on or before the quote day are excluded.
  * Quotes. A leg is usable when bid > 0 and ask >= bid (crossed or one-sided quotes, e.g. a bid with ask 0 on far SPX
    LEAPS, are not executable). Every claim's "drop / exclude zero-bid legs" is applied this way; T-501's bought far leg
    only needs an offer (ask > 0, ask >= bid), as its control drops zero-bid NEAR legs only.
  * Spot (the data limit that decides most of these claims). The archive holds no underlying quote synchronous with the
    16:15 ET option close: daily-history has the 16:00 ET close (used only when the bundle was captured after it), and
    the surface's "underlying" is a pre-market print on the 2026-10-14 capture. Two spots are therefore carried as
    variants: "close" (the quote-day RAW close, as batch-6a's xc group) and "sync" (the quote-synchronous spot implied by
    the short-dated parity: median of K e^{-rT} + C_mid - P_mid + PV(D) over the 4 strikes nearest the close at 1-10 DTE,
    accurate to about 1 bp of spot; it differs from the close by +1.6 bp on 2026-10-13 and -7.0 bp on 2026-10-14, which
    moves a 30-64 DTE parity rate by up to 70 bp/yr). "Stock at the ask" adds an ASSUMED half-spread of $0.005 (SPY's
    one-cent quoted spread; the underlying's bid/ask is not archived; 0.6 bp/yr at 37 DTE). T-182's data and T-507's
    procedure name the underlying quote, so until a bid/ask at the option close is archived each carries a not-yet-
    implementable criterion for it (rules 2 and 9): the assumed ask caps their verdict at inconclusive.
  * Bills (house rule 1). T-182, T-184, T-185, T-191, T-507 and T-508 name FRED DGS3MO (a bond-equivalent yield,
    r = ln(1 + y/100 x 91/365)/(91/365)), so DGS3MO alone decides them, under batch6_xc's T-199 rule: the archived
    fred-DGS3MO print dated before the quote day when present, else the two FRED prints batch-6a's xc group read on
    2026-10-15 (DGS3MO_REF), used only when they carry the same date as the latest DTB3 print (named_bills). FRED DTB3 (a
    discount yield, prior print, r = -ln(1 - d/100 x 91/360)/(91/365); about 7-9 bp below DGS3MO) is computed on the
    same pairs and reported beside the result, never deciding; a quote day with no DGS3MO print is left unjudged (a data
    limit). T-153's trial names only "the FRED 3-month bill", so it is evaluated on both bills (bill_variants).
  * Robust decision. A day's criterion is evaluated on every deciding (spot, bill) variant and passes only when every
    variant passes, fails only when every variant fails, and is MARGINAL (None, so at best inconclusive) when they
    disagree: the archive cannot say which spot is right. Rule 5's decisive failure (below min_n) needs every variant to
    fail decisively.
  * SPY dividends: amounts from the adjclose/close ratio step; future ex-dates projected on SPY's schedule (third Friday
    of Mar/Jun/Sep/Dec, the Thursday before when Juneteenth closes that Friday): 2026-12-18 is the next one. PV(D) at the
    bill. T-153 and T-191 forecast every future dividend as the last one paid; T-184 maps the trailing four distributions
    to the matching quarters, as it says, and reports +/- 10%.
  * Exercise style as each claim states it: SPY, QQQ, GLD and IBIT options are American (undiscounted vertical width
    bound, no European fair-value assumption beyond what a claim's own formula states); SPX/SPXW are European
    (discounted width bound). T-153's fair value is the claim's European formula applied to American SPY legs, as worded;
    its SPX control uses each SPXW expiry's parity forward.
  * Intervals. Shares: one-sided Clopper-Pearson bounds at the pass's confidence (95%), and for T-500 also the percentile
    cluster bootstrap over expiries the trial names (the larger upper bound is used). T-191: percentile bootstrap of the
    group difference across strikes (stratified), with an expiry-cluster bootstrap reported. T-103: studentized circular
    block bootstrap of the paired per-cycle Sharpe difference (delta-method Bartlett HAC s.e., bandwidth = block).
  * House rule 10. The captured-chain claims are statistics on fixed capture days (no cycle grid). T-103 names its entry
    calendar: "same entry dates as the short-straddle harness", which is run.short_straddle_model ->
    volatility.overlay_backtest(strategy='short_straddle') on its default calendar='monthly_expiry' (T-101's procedure
    names the same function): over the sessions with a SPY and a VIX close, each cycle writes at one standard monthly
    expiry close (third Friday, prior session on a holiday) and settles at the next (rule 10(a); monthly_cycle_pairs).
    Every criterion is decided on those cycles (T from each cycle's own dates; non-overlapping, so studentized blocks of
    2, 3, 6 and 12 cycles x seeds 0-2), and n counts them. The 21-session daily all-start grid (pooled estimate, blocks
    of 42 and 126 entries, and each of the 21 start offsets with its smile, flat-VIX and SKEW-scaled differences) is
    reported as a diagnostic only.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not
implemented gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, monthly_expiry_sessions
from mandel.options import bs
from mandel.validation.backtest_eval import (_hac_var, block_bootstrap_pvalue, kurtosis, probabilistic_sharpe_ratio,
                                             skewness)

SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
HIST_B = {"SPY": SPY_B, "SPX": GSPC_B, "QQQ": "daily-history-QQQ", "GLD": "daily-history-GLD", "IBIT": "daily-history-IBIT"}
DTB3_B = "fred-DTB3"
DGS3MO_B = "fred-DGS3MO"
VIX_B = "cboe-VIX-history"
SKEW_B = "cboe-SKEW-history"
SMILE_P = "spy-smile-"
CHAIN_P = "options-chain-"
MP = "MODEL-PRICED"

# FRED DGS3MO prints (percent, bond-equivalent) read once from fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO on
# 2026-10-15 by batch-6a's xc group (batch6_xc.DGS3MO_REF; the same file's DTB3 column matches the archived fred-DTB3).
# Used only until fred-DGS3MO is archived and only for a quote day whose latest DTB3 print carries the same date
# (batch6_xc's T-199 rule). It decides the claims whose trial names DGS3MO (named_bills); T-153 uses it as one variant.
DGS3MO_REF = {"2026-10-09": 4.25, "2026-10-13": 4.26}
EX_DATE = "2026-12-18"           # next SPY ex-dividend date named by T-182, T-185, T-507
SPY_HALF_SPREAD = 0.005          # ASSUMED: SPY's one-cent quoted spread (the underlying bid/ask is not archived)
SPY_TICK = 0.01                  # SPY options quote in pennies
SPX_TICK = 0.10                  # SPX options at or above $3
DEEP_DELTA = 0.90                # "deep ITM": |chain delta| >= 0.90
MIN_DAYS = 5                     # fewest capture days that can resolve an ">= 80% of captured days" share
N_BOOT = 2000

T153_MIN_N, T153_CONFIRM = 200, 60
T182_MIN_N = 100
T184_MIN_N = 20
T185_MIN_N = 20
T191_MIN_N, T191_STABLE = 100, 20
T500_MIN_N = 1000
T501_MIN_N = 5000
T507_MIN_N = 50
T508_MIN_N = 5000
T103_MIN_N, T103_HOLD, T103_SMILE_DAYS = 390, 21, 60
T103_BLOCKS = (2, 3, 6, 12)      # monthly-expiry cycles (non-overlapping): studentized blocks in cycles, as batch6_var
T103_GRID_BLOCKS = (42, 126)     # the 21-session daily grid diagnostic: blocks >= 2 x hold
T103_SEEDS = (0, 1, 2)


# ================================================================================================== formatting ==

def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pct(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.{nd}f}%"


def _ok_txt(ok) -> str:
    return "undecided" if ok is None else ("pass" if ok else "fail")


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


# ============================================================================================ exact binomials ==

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta function (modified Lentz)."""
    tiny, eps = 1e-300, 3e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 20000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) (no scipy)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k), X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return betainc(k, n - k + 1, p)


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k)."""
    return 1.0 - binom_sf(k + 1, n, p)


def _bisect(f, lo: float = 0.0, hi: float = 1.0, it: int = 80) -> float:
    """Root of a decreasing-in-p predicate boundary: f(p) True means p is still too small."""
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        if f(mid):
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cp_upper(k: int, n: int, conf: float = 0.95) -> Optional[float]:
    """One-sided Clopper-Pearson upper bound of a binomial share at ``conf``."""
    if n <= 0:
        return None
    if k >= n:
        return 1.0
    a = 1.0 - conf
    return _bisect(lambda p: binom_cdf(k, n, p) > a)


def cp_lower(k: int, n: int, conf: float = 0.95) -> Optional[float]:
    """One-sided Clopper-Pearson lower bound."""
    if n <= 0:
        return None
    if k <= 0:
        return 0.0
    a = 1.0 - conf
    return _bisect(lambda p: binom_sf(k, n, p) < a)


# ================================================================================================= bootstraps ==

def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def _chunks(n_boot: int, n: int):
    k = max(1, min(n_boot, 2_000_000 // max(n, 1)))
    done = 0
    while done < n_boot:
        yield min(k, n_boot - done)
        done += k


def _lrv(x, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance, identical to backtest_eval._hac_var; long bandwidths use FFT autocovariances."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    bw = max(1, int(bw))
    if bw <= 24:
        return _hac_var(x, bw)
    n = x.shape[1]
    xc = x - x.mean(axis=1, keepdims=True)
    m = 1 << int(math.ceil(math.log2(2 * n)))
    f = np.fft.rfft(xc, m, axis=1)
    ac = np.fft.irfft(f * np.conj(f), m, axis=1)[:, :min(bw, n)]
    k = np.arange(ac.shape[1])
    w = np.where(k == 0, 1.0, 2.0 * (1.0 - k / bw))
    return np.maximum((ac * w).sum(axis=1) / n, 1e-300)


def _sr_diff_and_se(a: np.ndarray, b: np.ndarray, bw: int):
    """Row-wise per-period Sharpe(a) - Sharpe(b) (population sd) and its delta-method HAC s.e. (Ledoit-Wolf 2008)."""
    n = a.shape[1]
    mu_a, mu_b = a.mean(axis=1), b.mean(axis=1)
    g_a, g_b = (a * a).mean(axis=1), (b * b).mean(axis=1)
    va, vb = np.maximum(g_a - mu_a ** 2, 1e-300), np.maximum(g_b - mu_b ** 2, 1e-300)
    d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
    grad = (1.0 / np.sqrt(va) + mu_a ** 2 / va ** 1.5, -(1.0 / np.sqrt(vb) + mu_b ** 2 / vb ** 1.5),
            -mu_a / (2 * va ** 1.5), mu_b / (2 * vb ** 1.5))
    z = (grad[0][:, None] * (a - mu_a[:, None]) + grad[1][:, None] * (b - mu_b[:, None])
         + grad[2][:, None] * (a * a - g_a[:, None]) + grad[3][:, None] * (b * b - g_b[:, None]))
    return d, np.sqrt(_lrv(z, bw) / n)


def sharpe_diff_test(a, b, block: int, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Per-period Sharpe(a) - Sharpe(b) on paired periods: studentized circular block bootstrap (blocks of ``block``),
    one-sided p of H0: difference <= 0, two-sided p and the two-sided 95% CI."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = a.size
    out = {"n": int(n), "block": int(block), "seed": int(seed), "diff": None, "se": None, "p_gt0": None, "p_two": None,
           "ci": [None, None]}
    if n < 8 or b.size != n:
        return out
    block = max(1, min(int(block), n // 4))
    d0, se0 = _sr_diff_and_se(a[None, :], b[None, :], block)
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(diff=d0, se=se0, block=block)
    if not se0 > 1e-150:
        out.update(ci=[d0, d0], p_gt0=0.0 if d0 > 0 else 1.0, p_two=0.0 if d0 != 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        d, se = _sr_diff_and_se(a[idx], b[idx], block)
        ok = se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
    t = np.concatenate(ts)
    t0 = d0 / se0
    out["ci"] = [d0 - float(np.quantile(t, 0.975)) * se0, d0 - float(np.quantile(t, 0.025)) * se0]
    out["p_gt0"] = float((np.sum(t >= t0) + 1) / (t.size + 1))
    out["p_two"] = float(min(1.0, (np.sum(np.abs(t) >= abs(t0)) + 1) / (t.size + 1)))
    return out


def cluster_share_upper(k_by: Sequence[float], n_by: Sequence[float], conf: float = 0.95, n_boot: int = N_BOOT,
                        seed: int = 0) -> Optional[float]:
    """Percentile cluster-bootstrap upper bound (one-sided ``conf``) of a pooled share: whole clusters (expiries)
    resampled with replacement, share = total hits / total objects. None with fewer than 2 clusters."""
    k = np.asarray(k_by, dtype=float)
    m = np.asarray(n_by, dtype=float)
    if k.size < 2 or m.sum() <= 0:
        return None
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, k.size, size=(n_boot, k.size))
    s = k[pick].sum(axis=1) / np.maximum(m[pick].sum(axis=1), 1.0)
    return float(np.quantile(s, conf))


def diff_share_ci(met_at: Sequence[bool], fail_at: Sequence[bool], conf: float = 0.95, n_boot: int = N_BOOT,
                  seed: int = 0) -> dict:
    """Difference in shares (met - failed) with a two-sided percentile bootstrap CI that resamples strikes within each
    group (stratified). None fields when a group is empty."""
    a = np.asarray(met_at, dtype=float)
    b = np.asarray(fail_at, dtype=float)
    out = {"n_met": int(a.size), "n_failed": int(b.size), "share_met": float(a.mean()) if a.size else None,
           "share_failed": float(b.mean()) if b.size else None, "diff": None, "ci": [None, None]}
    if a.size == 0 or b.size == 0:
        return out
    rng = np.random.default_rng(seed)
    da = a[rng.integers(0, a.size, size=(n_boot, a.size))].mean(axis=1)
    db = b[rng.integers(0, b.size, size=(n_boot, b.size))].mean(axis=1)
    d = da - db
    al = (1.0 - conf) / 2.0
    out.update(diff=float(a.mean() - b.mean()), ci=[float(np.quantile(d, al)), float(np.quantile(d, 1.0 - al))])
    return out


def diff_share_cluster_ci(rows: Sequence[dict], conf: float = 0.95, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """The same difference with whole expiries resampled (rows carry 'expiry', 'met', 'at'); draws missing a group
    are dropped and counted."""
    by = defaultdict(lambda: [0, 0, 0, 0])               # met hits, met n, failed hits, failed n
    for r in rows:
        c = by[r["expiry"]]
        if r["met"]:
            c[0] += int(r["at"]); c[1] += 1
        else:
            c[2] += int(r["at"]); c[3] += 1
    arr = np.array(list(by.values()), dtype=float)
    out = {"n_expiries": int(arr.shape[0]) if arr.size else 0, "ci": [None, None], "dropped_draws": 0}
    if arr.size == 0 or arr[:, 1].sum() == 0 or arr[:, 3].sum() == 0 or arr.shape[0] < 2:
        return out
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, arr.shape[0], size=(n_boot, arr.shape[0]))
    s = arr[pick].sum(axis=1)
    ok = (s[:, 1] > 0) & (s[:, 3] > 0)
    d = s[ok, 0] / s[ok, 1] - s[ok, 2] / s[ok, 3]
    al = (1.0 - conf) / 2.0
    out.update(ci=[float(np.quantile(d, al)), float(np.quantile(d, 1.0 - al))] if d.size else [None, None],
               dropped_draws=int((~ok).sum()))
    return out


# =================================================================================================== decisions ==

def _robust(oks: Sequence[Optional[bool]]) -> Optional[bool]:
    """True when every variant passes, False when every variant fails, None (MARGINAL) otherwise or when none exist."""
    oks = list(oks)
    if not oks or any(o is None for o in oks):
        return None
    if all(bool(o) for o in oks):
        return True
    if not any(bool(o) for o in oks):
        return False
    return None


def _all_ok(oks: Sequence[Optional[bool]]) -> Optional[bool]:
    """Conjunction of criteria (not variants): False when any fails, None when any is undecided, else True."""
    oks = list(oks)
    if any(o is not None and not bool(o) for o in oks):
        return False
    if not oks or any(o is None for o in oks):
        return None
    return True


def _eff(t: dict, n_ref: int, min_n: int) -> Optional[bool]:
    """Rule 5 at the level of one test: a failure on fewer than min_n objects that is not decisive is undecided."""
    ok = t.get("pass")
    if ok is not None and not ok and n_ref < min_n and not t.get("decisive"):
        return None
    return ok


def share_test(k: int, n: int, need: float, kind: str = "ge", conf: float = 0.95, min_n: int = 0, bound: bool = False,
               extra_upper: Optional[float] = None) -> dict:
    """One share criterion. kind 'ge': passes when k/n >= need; it fails decisively when the one-sided ``conf`` upper
    bound is below need, or the share stays below need even if every observation up to min_n were a hit. kind 'lt':
    passes when k/n < need (and, with ``bound``, when the upper bound - the larger of Clopper-Pearson and
    ``extra_upper`` - is below need); it fails decisively when the lower bound is >= need, or k/min_n >= need."""
    if n <= 0:
        return {"n": 0, "k": 0, "share": None, "upper": None, "lower": None, "pass": None, "decisive": False}
    s = k / n
    up, lo = cp_upper(k, n, conf), cp_lower(k, n, conf)
    if kind == "ge":
        ok = s >= need
        dec = up < need or (n < min_n and (k + (min_n - n)) / min_n < need)
        ub = up
    else:
        ub = up if extra_upper is None else max(up, extra_upper)
        ok = s < need and (ub < need if bound else True)
        dec = lo >= need or (n < min_n and k / min_n >= need)
    return {"n": int(n), "k": int(k), "share": s, "upper": up, "lower": lo, "upper_used": ub, "pass": bool(ok),
            "decisive": bool(dec) and not ok}


def _days_share(passes: Sequence[Optional[bool]], need: float, min_days: int) -> Optional[bool]:
    """'Passes on >= need of the captured days'. With at least ``min_days`` days: True when the share holds even if
    every unjudged (None) day failed, False when it fails even if every unjudged day passed, else None. Fewer days:
    False only when the share would stay below ``need`` even if every missing or unjudged day passed, else None."""
    p = list(passes)
    k = sum(1 for v in p if v is not None and bool(v))
    u = sum(1 for v in p if v is None)
    if len(p) >= min_days:
        if k / len(p) >= need:
            return True
        return False if (k + u) / len(p) < need else None
    if (k + u + (min_days - len(p))) / min_days < need:
        return False
    return None


def _decide(rows: list, n: int, min_n: int, unit: str) -> tuple:
    """rows: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (rule 5);
    otherwise it is reported as not decisive (None). Appends the min_n criterion."""
    crit = []
    for name, ok, dec in rows:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            crit.append((name + " [fails, not decisively, below min_n]", None))
        else:
            crit.append((name, None if ok is None else bool(ok)))
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(crit)


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    """Bundle indexed AND loadable on this machine (large chain bundles are kept off git)."""
    try:
        archive.get(name)
    except (KeyError, AttributeError):
        return False
    try:
        it = iter(archive.load(name))
        next(it, None)
        close = getattr(it, "close", None)
        if close:
            close()
        return True
    except (FileNotFoundError, OSError, KeyError):
        return False


def _names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if getattr(e, "name", "").startswith(prefix))


def _capture_names(archive, sym: str) -> list:
    """options-chain-<SYM>-<YYYY-MM-DD> bundles that are loadable, oldest first."""
    pat = re.compile(rf"^{re.escape(CHAIN_P + sym)}-(\d{{4}}-\d{{2}}-\d{{2}})$")
    return [n for n in _names(archive, CHAIN_P + sym + "-") if pat.match(n) and _has(archive, n)]


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if (n.endswith("<date>") or n.endswith("*")) or not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _created(archive, name: str) -> str:
    try:
        return str(getattr(archive.get(name), "created_at", "") or "")
    except (KeyError, AttributeError):
        return ""


def _rows(archive, name: str, filtered: bool = True) -> list:
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured."""
    cap = _created(archive, name) if filtered else ""
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    by = {}
    for r in rows:
        v = r.get("value") or {}
        c = v.get("close")
        if c is None or v.get("t") is None:
            continue
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if not c > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (c, float(a) if a is not None and float(a) > 0 else c)
    days = sorted(by)
    return days, np.array([by[d][0] for d in days], dtype=float), np.array([by[d][1] for d in days], dtype=float)


def _spot_history(archive, name: str) -> tuple:
    """(days, RAW close, adjclose, created_at). Unfiltered: a quote-day close is used only when the bundle was captured
    after that session's close (_close_final)."""
    return _daily_from_rows(_rows(archive, name, filtered=False)) + (_created(archive, name),)


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED series (missing prints skipped)."""
    out = {}
    for r in _rows(archive, name):
        v = r.get("value") or {}
        try:
            x = float(v.get("value", v.get("close")))
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and v.get("day"):
            out[v["day"]] = x
    return out


def _index(archive, name: str) -> dict:
    """{day: close} of a CBOE index history."""
    out = {}
    for r in _rows(archive, name):
        v = r.get("value") or {}
        try:
            x = float(v.get("close"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and x > 0 and v.get("day"):
            out[v["day"]] = x
    return out


# ======================================================================================================= rates ==

def dtb3_continuous(d_pct: float) -> float:
    """Continuous rate from a 91-day discount yield in percent (house rule 7)."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def bey_continuous(y_pct: float) -> float:
    """Continuous rate from a 91-day bond-equivalent yield in percent (FRED DGS3MO)."""
    return math.log(1.0 + y_pct / 100.0 * 91.0 / 365.0) / (91.0 / 365.0)


def prior_print(series: dict, day: str) -> Optional[tuple]:
    """(print day, value) of the latest observation dated strictly before ``day`` (FRED publishes a day late)."""
    ks = sorted(series)
    j = bisect_left(ks, day) - 1
    return (ks[j], float(series[ks[j]])) if j >= 0 else None


def bill_variants(dtb3: dict, dgs3mo: dict, quote_day: str) -> list:
    """[(label, continuous rate)]: DTB3 (prior print) and DGS3MO (archived prior print, else DGS3MO_REF when it carries
    the same date as the latest DTB3 print)."""
    out = []
    pd = prior_print(dtb3, quote_day) if dtb3 else None
    if pd:
        out.append((f"DTB3 {pd[0]}", dtb3_continuous(pd[1])))
    if dgs3mo:
        pg = prior_print(dgs3mo, quote_day)
        if pg:
            out.append((f"DGS3MO {pg[0]}", bey_continuous(pg[1])))
    else:
        pg = prior_print(DGS3MO_REF, quote_day)
        if pg and pd and pg[0] == pd[0]:
            out.append((f"DGS3MO {pg[0]} (ref)", bey_continuous(pg[1])))
    return out


def named_bills(dtb3: dict, dgs3mo: dict, quote_day: str) -> tuple:
    """(deciding, reported) bills of a claim whose trial names FRED DGS3MO (house rule 1; batch6_xc's T-199 rule):
    deciding = [DGS3MO] (archived prior print, else DGS3MO_REF when it carries the date of the latest DTB3 print; [] when
    neither exists, and the day is then left unjudged as a data limit); reported = [DTB3 prior print], shown beside the
    result and never deciding."""
    allv = bill_variants(dtb3, dgs3mo, quote_day)
    return [v for v in allv if v[0].startswith("DGS3MO")], [v for v in allv if v[0].startswith("DTB3")]


# ================================================================================================ chain parsing ==

_ROOT = re.compile(r"^([A-Z]+)")


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def chain_by_root(values) -> dict:
    """{(root, expiry): {'call': {K: (bid, ask, delta, iv)}, 'put': {...}}} from compact CBOE option rows."""
    by = defaultdict(lambda: {"call": {}, "put": {}})
    for v in values:
        t = v.get("type")
        if t not in ("call", "put") or v.get("bid") is None or v.get("ask") is None or v.get("strike") is None or not v.get("expiry"):
            continue
        b, a, k = _num(v.get("bid")), _num(v.get("ask")), _num(v.get("strike"))
        if b is None or a is None or k is None:
            continue
        m = _ROOT.match(v.get("sym") or "")
        root = m.group(1) if m else "?"
        by[(root, v["expiry"])][t][k] = (b, a, _num(v.get("delta")), _num(v.get("iv")))
    return by


def _ok(q) -> bool:
    """Usable two-sided quote: bid > 0 and not crossed."""
    return q is not None and q[0] > 0 and q[1] >= q[0]


def _buyable(q) -> bool:
    """An offer exists (ask > 0) and the quote is not crossed."""
    return q is not None and q[1] > 0 and q[1] >= q[0]


def _mid(q) -> float:
    return 0.5 * (q[0] + q[1])


def _dte(expiry: str, quote_day: str) -> int:
    return (date.fromisoformat(expiry) - date.fromisoformat(quote_day)).days


def _expiries(by: dict, root: str, quote_day: str) -> list:
    return sorted(e for (rt, e) in by if rt == root and _dte(e, quote_day) >= 1)


# =============================================================================================== SPY dividends ==

def dividends(close, adj) -> np.ndarray:
    """Cash dividend going ex on each day (0 otherwise) from the adjclose/close ratio step: D = close[i-1](1 - f[i-1]/f[i])."""
    close = np.asarray(close, dtype=float)
    f = np.asarray(adj, dtype=float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if f[i] > f[i - 1] * (1 + 1e-5):
            d = close[i - 1] * (1.0 - f[i - 1] / f[i])
            if 0 < d < 0.05 * close[i - 1]:
                out[i] = d
    return out


def dividend_events(days, close, adj) -> list:
    """[(ex-day, amount)] in date order."""
    div = dividends(close, adj)
    return [(days[i], float(div[i])) for i in range(len(days)) if div[i] > 0]


def last_dividend(events: Sequence[tuple], before: str) -> Optional[float]:
    amt = [a for d, a in events if d <= before]
    return amt[-1] if amt else None


def trailing_four(events: Sequence[tuple], before: str) -> dict:
    """{quarter month (3, 6, 9, 12): amount} of the last four distributions gone ex on or before ``before``."""
    out = {}
    for d, a in [e for e in events if e[0] <= before][-4:]:
        m = int(d[5:7])
        out[3 * ((m - 1) // 3) + 3] = a
    return out


def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def spy_ex_date(y: int, m: int) -> date:
    """Projected SPY ex-date: the third Friday of the quarter-end month, or the Thursday before when Juneteenth
    (observed) closes the market that Friday."""
    tf = _third_friday(y, m)
    if m == 6:
        j = date(y, 6, 19)
        observed = j if j.weekday() < 5 else (j - timedelta(days=1) if j.weekday() == 5 else j + timedelta(days=1))
        if observed == tf:
            return tf - timedelta(days=1)
    return tf


def ex_dates_between(a: str, b: str) -> list:
    """Projected SPY ex-dates in (a, b]."""
    lo, hi = date.fromisoformat(a), date.fromisoformat(b)
    out = []
    for y in range(lo.year, hi.year + 1):
        for m in (3, 6, 9, 12):
            x = spy_ex_date(y, m)
            if lo < x <= hi:
                out.append(x)
    return out


def pv_div(quote_day: str, a: str, b: str, amount, r: float) -> float:
    """PV at the quote day of the forecast dividends going ex in (a, b]. ``amount``: a number (every dividend the same)
    or {quarter month: amount} (the trailing-four mapping); None or 0 gives 0."""
    if not amount:
        return 0.0
    q = date.fromisoformat(quote_day)
    pv = 0.0
    for x in ex_dates_between(a, b):
        amt = amount.get(x.month, 0.0) if isinstance(amount, dict) else float(amount)
        pv += amt * math.exp(-r * (x - q).days / 365.0)
    return pv


# ================================================================================================= spot timing ==

def sync_spot(by: dict, spot: float, quote_day: str, r: float, div_amount=None, root: Optional[str] = None,
              dte_range=(1, 10), n_near: int = 4) -> Optional[dict]:
    """Quote-synchronous spot from the short-dated parity: median of K e^{-rT} + C_mid - P_mid + PV(D) over the n_near
    usable strikes nearest the close at every expiry with dte in dte_range. None without such pairs."""
    xs = []
    for (rt, e), legs in by.items():
        if root is not None and rt != root:
            continue
        dte = _dte(e, quote_day)
        if not dte_range[0] <= dte <= dte_range[1]:
            continue
        T = dte / 365.0
        pvd = pv_div(quote_day, quote_day, e, div_amount, r)
        ks = sorted((k for k in legs["call"] if k in legs["put"] and _ok(legs["call"][k]) and _ok(legs["put"][k])),
                    key=lambda k: (abs(k - spot), k))[:n_near]
        for k in ks:
            xs.append(k * math.exp(-r * T) + _mid(legs["call"][k]) - _mid(legs["put"][k]) + pvd)
    if not xs:
        return None
    s = float(np.median(xs))
    return {"spot": s, "close": float(spot), "offset_bp": (s / spot - 1.0) * 1e4, "n": len(xs)}


# ==================================================================================================== captures ==

def _capture_meta(rows: list, trading_days: list) -> tuple:
    """(quote day, why-skipped). A capture between 13:30 and 21:15 UTC is intraday: its quotes are not synchronous with
    any close."""
    if not rows:
        return None, "empty capture"
    obs = str(rows[0].get("observed_at") or rows[0].get("available_at") or "")
    hhmm = obs[11:16]
    if "13:30" <= hhmm < "21:15":
        return None, f"intraday capture at {obs} UTC (quotes not synchronous with a close)"
    return _quote_day(obs, trading_days), ""


def _close_final(created_at: str, quote_day: str) -> bool:
    """The daily bundle was captured after the quote day's 16:00 ET close (21:15 UTC covers EST and EDT)."""
    return bool(created_at) and created_at[:16].replace(" ", "T") >= f"{quote_day}T21:15"


def load_captures(archive, sym: str, notes: list, hist: Optional[tuple], trading: Sequence[str], need_close: bool = True) -> list:
    """[{'sym', 'name', 'quote_day', 'close', 'values', 'by'}] per loadable options-chain-<sym>-<date> bundle, one per
    quote day (a later capture of the same session's quotes is skipped). 'close' is the RAW quote-day close (None when
    not needed)."""
    trading = list(trading)
    px, created = {}, ""
    if hist is not None:
        days, close, _, created = hist
        px = dict(zip(days, close))
    out, seen = [], set()
    for nm in _capture_names(archive, sym):
        rows = list(archive.load(nm))
        qd, why = _capture_meta(rows, trading)
        if qd is None:
            notes.append(f"{nm} skipped: {why or 'no trading day before it'}")
            continue
        if need_close and (qd not in px or not _close_final(created, qd)):
            notes.append(f"{nm} skipped: no final {sym} close on its quote day {qd}")
            continue
        if qd in seen:
            notes.append(f"{nm} skipped: a capture of the {qd} quotes is already used")
            continue
        seen.add(qd)
        vals = [r["value"] for r in rows if isinstance(r.get("value"), dict)]
        out.append({"sym": sym, "name": nm, "quote_day": qd, "close": float(px[qd]) if qd in px else None,
                    "values": vals, "by": chain_by_root(vals)})
    return sorted(out, key=lambda c: c["quote_day"])


def _variants(cap: dict, bills: list, div_amount=None, sync: bool = True, root: Optional[str] = None) -> tuple:
    """[(label, spot, r)] over (close, sync spot) x bills, and the sync-spot record. The sync spot uses the first bill."""
    var, si, _ = _named_variants(cap, bills, [], div_amount, sync, root)
    return var, si


def _named_variants(cap: dict, bills: list, reported: list, div_amount=None, sync: bool = True,
                    root: Optional[str] = None) -> tuple:
    """(deciding variants, sync-spot record, reported variants): [(label, spot, r)] over (close, sync spot) x the
    deciding bills and x the reported (never deciding) bills, on the same spots. The sync spot uses the first deciding
    bill, or the first reported one when no bill decides."""
    spots = [("close", cap["close"])]
    si = None
    r_sync = (list(bills) or list(reported) or [(None, None)])[0][1]
    if sync and r_sync is not None and cap["close"]:
        si = sync_spot(cap["by"], cap["close"], cap["quote_day"], r_sync, div_amount, root=root)
        if si:
            spots.append(("sync", si["spot"]))
    return ([(f"{sl}/{bl}", s, r) for sl, s in spots for bl, r in bills], si,
            [(f"{sl}/{bl}", s, r) for sl, s in spots for bl, r in reported])


def _var_txt(variants: dict, fmt) -> str:
    return ", ".join(f"{lab} {fmt(v)}" for lab, v in variants.items())


# ======================================================================================== T-153: jelly roll ==

def jelly_pair(by: dict, quote_day: str, root: str = "SPY", near: int = 30, far: int = 60,
               no_ex_span: bool = False) -> Optional[tuple]:
    """(near expiry, far expiry): the listed expiries nearest ``near`` and ``far`` DTE (ties to the earlier). With
    no_ex_span, the far leg is the expiry nearest ``far`` DTE whose (near, far] window holds no projected ex-date."""
    exps = _expiries(by, root, quote_day)
    if not exps:
        return None
    e1 = min(exps, key=lambda e: (abs(_dte(e, quote_day) - near), e))
    pool = [e for e in exps if e > e1 and (not no_ex_span or not ex_dates_between(e1, e))]
    if not pool:
        return None
    e2 = min(pool, key=lambda e: (abs(_dte(e, quote_day) - far), e))
    return e1, e2


def jelly_roll_day(by: dict, spot: float, quote_day: str, r: float, div_amount, e1: str, e2: str, root: str = "SPY",
                   band: float = 0.05, max_spread: float = 0.05) -> dict:
    """Mid jelly roll (far synthetic minus near synthetic) at every strike within +/- band of spot, against the claim's
    carry K(e^{-rT1} - e^{-rT2}) - PV(div in (T1, T2]); within when |roll - fair| <= half the four legs' summed spreads.
    Legs need bid > 0, ask >= bid and spread <= max_spread x mid (the trial's exclusions)."""
    L1, L2 = by.get((root, e1)), by.get((root, e2))
    T1, T2 = _dte(e1, quote_day) / 365.0, _dte(e2, quote_day) / 365.0
    pvd = pv_div(quote_day, e1, e2, div_amount, r)
    rows, excluded = [], 0
    if L1 and L2:
        ks = set(L1["call"]) & set(L1["put"]) & set(L2["call"]) & set(L2["put"])
        for k in sorted(ks):
            if abs(k / spot - 1.0) > band:
                continue
            qs = (L1["call"][k], L1["put"][k], L2["call"][k], L2["put"][k])
            if not all(_ok(q) and (q[1] - q[0]) <= max_spread * _mid(q) for q in qs):
                excluded += 1
                continue
            roll = (_mid(qs[2]) - _mid(qs[3])) - (_mid(qs[0]) - _mid(qs[1]))
            fair = k * (math.exp(-r * T1) - math.exp(-r * T2)) - pvd
            tol = 0.5 * sum(q[1] - q[0] for q in qs)
            rows.append({"K": k, "roll": roll, "fair": fair, "dev": roll - fair, "tol": tol, "within": abs(roll - fair) <= tol})
    n, k = len(rows), sum(1 for x in rows if x["within"])
    devs = np.array([x["dev"] for x in rows]) if rows else np.zeros(0)
    return {"near": e1, "far": e2, "dte1": _dte(e1, quote_day), "dte2": _dte(e2, quote_day), "pv_div": pvd,
            "ex_dates": [x.isoformat() for x in ex_dates_between(e1, e2)], "n": n, "k": k, "excluded": excluded,
            "share": k / n if n else None, "median_dev": float(np.median(devs)) if n else None,
            "median_abs_dev_cents": float(np.median(np.abs(devs)) * 100) if n else None,
            "binom_p": binom_sf(k, n, 0.95) if n else None, "rows": rows}


def spx_roll_control(by: dict, spot: float, quote_day: str, r: float, band: float = 0.05, max_spread: float = 0.05,
                     n_fwd: int = 6) -> Optional[dict]:
    """SPX (European) control: the SPXW 30/60-DTE roll against e^{-rT2}(F2 - K) - e^{-rT1}(F1 - K), each expiry's
    forward F = median of K + (C_mid - P_mid) e^{rT} over the n_fwd usable strikes nearest spot (bill discounting)."""
    pair = jelly_pair(by, quote_day, "SPXW")
    if pair is None:
        return None
    e1, e2 = pair
    L1, L2 = by[("SPXW", e1)], by[("SPXW", e2)]
    T1, T2 = _dte(e1, quote_day) / 365.0, _dte(e2, quote_day) / 365.0

    def fwd(L, T):
        ks = sorted((k for k in L["call"] if k in L["put"] and _ok(L["call"][k]) and _ok(L["put"][k])), key=lambda k: abs(k - spot))[:n_fwd]
        return float(np.median([k + (_mid(L["call"][k]) - _mid(L["put"][k])) * math.exp(r * T) for k in ks])) if ks else None
    F1, F2 = fwd(L1, T1), fwd(L2, T2)
    if F1 is None or F2 is None:
        return None
    n = k = 0
    for K in sorted(set(L1["call"]) & set(L1["put"]) & set(L2["call"]) & set(L2["put"])):
        if abs(K / spot - 1.0) > band:
            continue
        qs = (L1["call"][K], L1["put"][K], L2["call"][K], L2["put"][K])
        if not all(_ok(q) and (q[1] - q[0]) <= max_spread * _mid(q) for q in qs):
            continue
        roll = (_mid(qs[2]) - _mid(qs[3])) - (_mid(qs[0]) - _mid(qs[1]))
        fair = math.exp(-r * T2) * (F2 - K) - math.exp(-r * T1) * (F1 - K)
        n += 1
        k += abs(roll - fair) <= 0.5 * sum(q[1] - q[0] for q in qs)
    return {"near": e1, "far": e2, "n": n, "k": k, "share": k / n if n else None}


def jelly_roll_claim(days: Sequence[dict], need: float = 0.95, min_n: int = T153_MIN_N, confirm: int = T153_CONFIRM) -> dict:
    """T-153. days (oldest first): {'quote_day', 'capture', 'primary': {bill: jelly_roll_day}, 'alt': {bill: ...} or
    None, 'spx': spx_roll_control or None}. A capture passes when the share is >= need under every reading (the 30/60
    roll as worded, and the nearest non-ex-dividend-spanning pair the controls report separately) and bill; fails when
    every one fails; else MARGINAL. Every capture must pass; one robust failure falsifies (below min_n only when every
    reading's one-sided 95% upper bound is below need)."""
    if not days:
        return {"verdict": "inconclusive", "n": 0, "stat": {"n_captures": 0}, "reason": "no SPY capture with a 30/60-DTE roll"}
    n_tot = sum(next(iter(d["primary"].values()))["n"] for d in days)
    per, fails, txt = [], [], []
    for d in days:
        tests = {}
        for tag in ("primary", "alt"):
            for bl, res in (d.get(tag) or {}).items():
                tests[f"{tag}/{bl}"] = share_test(res["k"], res["n"], need, "ge")
        ok = _robust([t["pass"] for t in tests.values()])
        dec = ok is False and all(t["decisive"] for t in tests.values())
        per.append({"quote_day": d["quote_day"], "capture": d.get("capture"), "pass": ok, "decisive": dec, "tests": tests})
        if ok is False:
            fails.append((d["quote_day"], dec))
        p0 = next(iter(d["primary"].values()))
        alt0 = next(iter((d.get("alt") or {}).values()), None)
        t0 = next(iter(tests.values()))
        txt.append(f"{d['quote_day']} quotes ({d.get('capture')}): roll {p0['near']}/{p0['far']} ({p0['dte1']}/{p0['dte2']} DTE"
                   + (f", spans the {', '.join(p0['ex_dates'])} ex-date, PV(div) {p0['pv_div']:.3f}" if p0["ex_dates"] else ", no ex-date inside")
                   + f") {p0['k']}/{p0['n']} strikes within tolerance ({_pct(p0['share'])}; one-sided 95% upper bound {_pct(t0['upper'])}, "
                   f"binomial p of H0 share < 95%: {_f(p0['binom_p'], 3)}; median deviation {_s(p0['median_dev'], 3)}, median |dev| "
                   f"{_f(p0['median_abs_dev_cents'], 1)} cents; {p0['excluded']} strikes excluded by the zero-bid / 5%-spread rule); by bill "
                   + _var_txt({k_: v for k_, v in tests.items() if k_.startswith("primary/")}, lambda v: _pct(v["share"]))
                   + (f"; ex-dividend-free pair (the controls' separate report, also required to fail) {alt0['near']}/{alt0['far']} "
                      f"({alt0['dte1']}/{alt0['dte2']} DTE) {alt0['k']}/{alt0['n']} ({_pct(alt0['share'])}, one-sided 95% upper bound "
                      f"{_pct(next(t for lab, t in tests.items() if lab.startswith('alt/'))['upper'])}, median deviation "
                      f"{_s(alt0['median_dev'], 3)}; by bill " + _var_txt({k_: v for k_, v in tests.items() if k_.startswith('alt/')}, lambda v: _pct(v['share'])) + ")"
                      if alt0 else "; no ex-dividend-free pair")
                   + (f"; SPX control (SPXW {d['spx']['near']}/{d['spx']['far']}, parity forwards) {d['spx']['k']}/{d['spx']['n']} "
                      f"({_pct(d['spx']['share'])})" if d.get("spx") and d["spx"]["n"] else "")
                   + f" -> {_ok_txt(ok)}" + (" (decisive: every reading's upper bound below 95%)" if dec else ""))
    if fails:
        every = False
        dec_all = any(dec for _, dec in fails)
    elif any(p["pass"] is None for p in per):
        every, dec_all = None, False
    else:
        every, dec_all = True, False
    rows = [(f"share >= {need:.0%} on every capture ({sum(1 for p in per if p['pass'])} pass, {len(fails)} fail, "
             f"{sum(1 for p in per if p['pass'] is None)} undecided of {len(per)}; one failing capture falsifies)", every, dec_all),
            (f"confirmation at {confirm} captures ({len(per)} so far)", (True if every else None) if len(per) >= confirm else None, False)]
    verdict, why = _decide(rows, n_tot, min_n, "strikes over captures")
    reason = ("SPY mid jelly roll vs bill carry K(e^-rT1 - e^-rT2) - PV(div), strikes within +/- 5% of the quote-day close "
              "(a positive deviation is a roll richer than bill carry): " + "; ".join(txt)
              + ". The 30/60 pair spans the projected ex-date; the ex-dividend-free pair, which no dividend touches, is held to the "
              f"same test, so neither the dividend forecast nor American early exercise around the ex-date decides the verdict — {why}")
    stat = {"n_captures": len(per), "n_strikes": n_tot, "per_capture": per, "verdict": verdict,
            "days": [{k: v for k, v in d.items() if k not in ("primary", "alt")} | {
                "primary": {bl: {k: v for k, v in res.items() if k != "rows"} for bl, res in d["primary"].items()},
                "alt": {bl: {k: v for k, v in res.items() if k != "rows"} for bl, res in (d.get("alt") or {}).items()}} for d in days]}
    return {"verdict": verdict, "n": n_tot, "reason": reason, "stat": stat}


# ============================================================================= share claims on capture days ==

def share_claim(days: Sequence[dict], *, need: float, kind: str, min_n: int, unit: str, label: str, n_mode: str = "day_one",
                days_need: float = 0.80, min_days: int = MIN_DAYS, bound: bool = False) -> dict:
    """Generic 'share on day one and on >= days_need of captured days'. days (oldest first): {'quote_day', 'variants':
    {label: {'n', 'k', optional 'extra_upper'}}, optional 'reported': {label: {'n', 'k'}}}. A day passes when every
    deciding variant passes (robust), fails when every one fails, else MARGINAL; 'reported' variants (DTB3 beside a
    DGS3MO-named claim) are tested and shown but never decide, and a day with no deciding variant is unjudged (None: no
    DGS3MO print, a data limit). Day one fails decisively (rule 5) when every variant does. n = day-one objects of the
    first variant (n_mode 'day_one') or the first variant's objects summed over days ('total')."""
    per = []
    for d in days:
        st = lambda v: share_test(v["k"], v["n"], need, kind, min_n=min_n, bound=bound, extra_upper=v.get("extra_upper"))
        per.append({"quote_day": d["quote_day"], "tests": {lab: st(v) for lab, v in d["variants"].items()},
                    "reported": {lab: st(v) for lab, v in (d.get("reported") or {}).items()}})
    if not per:
        return {"rows": [], "n": 0, "per_day": []}
    first = lambda d: next(iter(d["tests"].values()), None) or next(iter(d["reported"].values()), {"n": 0})
    n_tot = sum(first(p)["n"] for p in per)
    n = first(per[0])["n"] if n_mode == "day_one" else n_tot
    for p in per:                           # a day's own sample (or the pooled one, n_mode 'total') is held to min_n
        p["pass"] = _robust([_eff(t, t["n"] if n_mode == "day_one" else n_tot, min_n) for t in p["tests"].values()])
        p["decisive"] = p["pass"] is False and all(t["decisive"] for t in p["tests"].values())
        p["unjudged"] = not p["tests"]
    d0 = per[0]
    if d0["pass"] is None and d0["tests"] and all(t["pass"] is False for t in d0["tests"].values()):
        d0["pass"] = False                  # every variant fails, not decisively: _decide reports it as below min_n
    days_ok = _days_share([p["pass"] for p in per], days_need, min_days)
    cmp_ = ">=" if kind == "ge" else "<"
    bnd = (lambda t: f", one-sided 95% upper {_pct(t['upper'], 1)}") if kind == "ge" else (lambda t: f", one-sided 95% bounds {_pct(t['lower'], 3)} to {_pct(t['upper_used'], 3)}")
    rows = [(f"day one ({d0['quote_day']} quotes): {label} {cmp_} {need:.1%}"
             + (" with the 95% upper bound below it" if bound else "") + " ("
             + (_var_txt(d0["tests"], lambda t: f"{_pct(t['share'], 2)} of {t['n']}" + bnd(t)) if d0["tests"]
                else "no DGS3MO print for this quote day: unjudged, a data limit")
             + (("; DTB3 beside it, not deciding: " + _var_txt(d0["reported"], lambda t: f"{_pct(t['share'], 2)} of {t['n']}"))
                if d0["reported"] else "")
             + ")" + (" [MARGINAL: the spot variants disagree]" if d0["pass"] is None and len(d0["tests"]) > 1 else ""),
             d0["pass"], d0["decisive"]),
            (f"on >= {days_need:.0%} of captured days ({sum(1 for p in per if p['pass'])} pass, "
             f"{sum(1 for p in per if p['pass'] is False)} fail, {sum(1 for p in per if p['pass'] is None)} undecided of {len(per)}"
             + (f", {sum(1 for p in per if p['unjudged'])} without a DGS3MO print" if any(p["unjudged"] for p in per) else "")
             + f"; needs >= {min_days} days)", days_ok, days_ok is False)]
    return {"rows": rows, "n": n, "per_day": per, "days_ok": days_ok}


def _first_var(d: dict) -> tuple:
    """(label, variant) of a day's first deciding variant, else its first reported one, else (None, None)."""
    for key in ("variants", "reported"):
        for lab, v in (d.get(key) or {}).items():
            return lab, v
    return None, None


def _counted(d: dict, count) -> dict:
    """A share_claim day from a rate day: count(variant) -> {'n', 'k', ...} for the deciding and the reported variants."""
    return {"quote_day": d["quote_day"], "variants": {lab: count(v) for lab, v in d["variants"].items()},
            "reported": {lab: count(v) for lab, v in (d.get("reported") or {}).items()}}


# T-182's data ("CBOE delayed SPY chain with underlying bid/ask") and T-507's procedure ("SPY chain and underlying quote")
# name a quote the archive does not hold: until one at the option close is archived the assumed ask caps the verdict.
SASK_CRIT = (f"stock at the ask: underlying bid/ask at the option close not archived (S_ask ASSUMED = spot + ${SPY_HALF_SPREAD:.3f})",
             None, False)


def _finish(core: dict, min_n: int, unit: str, head: str, extra: str, stat: dict) -> dict:
    if not core["rows"]:
        return {"verdict": "inconclusive", "n": 0, "reason": head + ": no usable capture day — no data", "stat": stat}
    verdict, why = _decide(core["rows"], core["n"], min_n, unit)
    day_txt = "; ".join(f"{p['quote_day']}: " + (_var_txt(p["tests"], lambda t: f"{_pct(t['share'], 1)} of {t['n']}") if p["tests"]
                                                 else "no DGS3MO print (unjudged)") + f" -> {_ok_txt(p['pass'])}"
                        + (" (DTB3 beside it, not deciding: " + _var_txt(p["reported"], lambda t: f"{_pct(t['share'], 1)} of {t['n']}") + ")"
                           if p.get("reported") else "")
                        for p in core["per_day"])
    reason = f"{head}: {day_txt}{extra} — {why}"
    stat = dict(stat, per_day=core["per_day"], n=core["n"], verdict=verdict)
    return {"verdict": verdict, "n": core["n"], "reason": reason, "stat": stat}


# ================================================================================== T-182: conversion rate ==

def conversion_pairs(by: dict, spot: float, quote_day: str, root: str = "SPY", dte_range=(30, 64), ex_date: str = EX_DATE,
                     band: float = 0.05, half_spread: float = SPY_HALF_SPREAD, deep_delta: float = DEEP_DELTA) -> tuple:
    """Per (K, T): r_conv_exec = ln(K / (S_ask + P_ask - C_bid)) / T with S_ask = spot + half_spread, and the mid
    version. Zero-bid or crossed legs dropped; pairs whose short call is deep ITM (chain delta >= deep_delta) flagged."""
    rows, dropped = [], 0
    for (rt, e), legs in sorted(by.items()):
        dte = _dte(e, quote_day)
        if rt != root or not (dte_range[0] <= dte <= dte_range[1] and e < ex_date):
            continue
        T = dte / 365.0
        for k in sorted(set(legs["call"]) & set(legs["put"])):
            if abs(k / spot - 1.0) > band:
                continue
            c, p = legs["call"][k], legs["put"][k]
            if not (_ok(c) and _ok(p)):
                dropped += 1
                continue
            cost = spot + half_spread + p[1] - c[0]
            mid_cost = spot + _mid(p) - _mid(c)
            if cost <= 0 or mid_cost <= 0:
                continue
            rows.append({"expiry": e, "dte": dte, "K": k, "r_exec": math.log(k / cost) / T, "r_mid": math.log(k / mid_cost) / T,
                         "deep_itm_call": c[2] is not None and c[2] >= deep_delta})
    return rows, dropped


def spxw_box_rate(by: dict, spot: float, quote_day: str, target: str, grid: float = 25.0, moneyness: float = 0.10,
                  min_width: float = 0.05) -> Optional[dict]:
    """Median mid box rate ln(W / box_mid) / T at the SPXW expiry nearest ``target``: strike pairs on the $grid within
    +/- moneyness of spot, width >= min_width x spot, every leg usable (a control, not a criterion)."""
    exps = _expiries(by, "SPXW", quote_day)
    if not exps:
        return None
    e = min(exps, key=lambda x: (abs(_dte(x, target)), x))
    legs = by[("SPXW", e)]
    T = _dte(e, quote_day) / 365.0
    ks = [k for k in sorted(legs["call"]) if k in legs["put"] and _ok(legs["call"][k]) and _ok(legs["put"][k])
          and abs(k / spot - 1) <= moneyness and abs(k / grid - round(k / grid)) < 1e-9]
    rates = []
    for i, k1 in enumerate(ks):
        for k2 in ks[i + 1:]:
            if k2 - k1 < min_width * spot:
                continue
            m = _mid(legs["call"][k1]) - _mid(legs["call"][k2]) - _mid(legs["put"][k1]) + _mid(legs["put"][k2])
            if m > 0:
                rates.append(math.log((k2 - k1) / m) / T)
    return {"expiry": e, "rate": float(np.median(rates)), "n": len(rates)} if rates else None


def _box_by_day(spx_caps: dict, quote_day: str, target: str) -> Optional[dict]:
    cap = spx_caps.get(quote_day)
    return spxw_box_rate(cap["by"], cap["close"], quote_day, target) if cap and cap.get("close") else None


def conversion_claim(days: Sequence[dict], need: float = 0.95, min_n: int = T182_MIN_N) -> dict:
    """T-182. days: {'quote_day', 'variants': {label: {'rows', 'r_bill', 'dropped'}}, 'box': {...} or None, 'sync'}.
    The share counts pairs with r_conv_exec < r_bill among pairs whose short call is not deep ITM (the control's drop)."""
    vdays, ctl = [], []

    def count(v):
        main = [x for x in v["rows"] if not x["deep_itm_call"]]
        return {"n": len(main), "k": sum(1 for x in main if x["r_exec"] < v["r_bill"]),
                "all_n": len(v["rows"]), "all_k": sum(1 for x in v["rows"] if x["r_exec"] < v["r_bill"])}
    for d in days:
        vd = _counted(d, count)
        vdays.append(vd)
        var = dict(vd["reported"], **vd["variants"])
        lab0, v0 = _first_var(d)
        if v0 and v0["rows"]:
            ex = np.array([(x["r_exec"] - v0["r_bill"]) * 1e4 for x in v0["rows"]])
            md = np.array([(x["r_mid"] - v0["r_bill"]) * 1e4 for x in v0["rows"]])
            box = d.get("box")
            ctl.append(f"{d['quote_day']} ({lab0}): median r_conv_exec - bill {np.median(ex):+.1f} bp, mid {np.median(md):+.1f} bp"
                       + (f" vs SPXW box {(box['rate'] - v0['r_bill']) * 1e4:+.1f} bp over the bill ({box['expiry']}, {box['n']} boxes)" if box else "")
                       + f"; {sum(1 for x in v0['rows'] if x['deep_itm_call'])} deep-ITM-call pairs dropped, all-pairs share "
                       f"{_pct(var[lab0]['all_k'] / var[lab0]['all_n'] if var[lab0]['all_n'] else None)}"
                       + (f"; sync spot {d['sync']['spot']:.3f} ({_s(d['sync']['offset_bp'], 1)} bp vs the close)" if d.get("sync") else ""))
    core = share_claim(vdays, need=need, kind="ge", min_n=min_n, unit="pairs on day one",
                       label="share of (K, T) pairs with r_conv_exec below the bill (FRED DGS3MO)")
    if core["rows"]:
        core["rows"].append(SASK_CRIT)
    head = (f"SPY conversion lending rate ln(K/(S_ask + P_ask - C_bid))/T (S_ask = spot + ${SPY_HALF_SPREAD:.3f}, ASSUMED), "
            f"30-64 DTE expiries before {EX_DATE}, strikes within +/- 5%, vs the trial's 3-month bill FRED DGS3MO (continuous), per spot variant")
    return _finish(core, min_n, "pairs on day one", head, "; controls: " + "; ".join(ctl), {"controls": ctl})


# ========================================================================= T-185: synthetic short borrow cost ==

def synthetic_short_pairs(by: dict, spot: float, quote_day: str, r_bill: float, root: str = "SPY", dte_range=(30, 64),
                          ex_date: Optional[str] = EX_DATE, band: float = 0.02) -> list:
    """Per (K, T) within +/- band: r_impl from C_bid - P_ask = S - K e^{-rT}, borrow = r_bill - r_impl; mid version."""
    rows = []
    for (rt, e), legs in sorted(by.items()):
        dte = _dte(e, quote_day)
        if rt != root or not dte_range[0] <= dte <= dte_range[1] or (ex_date and not e < ex_date):
            continue
        T = dte / 365.0
        for k in sorted(set(legs["call"]) & set(legs["put"])):
            if abs(k / spot - 1.0) > band:
                continue
            c, p = legs["call"][k], legs["put"][k]
            if not (_ok(c) and _ok(p)):
                continue
            x, xm = spot - c[0] + p[1], spot - _mid(c) + _mid(p)
            if x <= 0 or xm <= 0:
                continue
            ri, rm = -math.log(x / k) / T, -math.log(xm / k) / T
            rows.append({"expiry": e, "dte": dte, "K": k, "r_impl": ri, "borrow": r_bill - ri, "borrow_mid": r_bill - rm})
    return rows


def synthetic_short_claim(days: Sequence[dict], need: float = 0.80, min_n: int = T185_MIN_N, cap_bp: float = 50.0) -> dict:
    """T-185. days: {'quote_day', 'variants': {label: {'rows'}}, 'box', 'sync', 'replications': {sym: (n, k, median bp)}}."""
    vdays, ctl = [], []
    for d in days:
        vdays.append(_counted(d, lambda v: {"n": len(v["rows"]), "k": sum(1 for x in v["rows"] if x["borrow"] * 1e4 < cap_bp)}))
        lab0, v0 = _first_var(d)
        if v0 and v0["rows"]:
            b = np.array([x["borrow"] * 1e4 for x in v0["rows"]])
            bm = np.array([x["borrow_mid"] * 1e4 for x in v0["rows"]])
            box = d.get("box")
            ctl.append(f"{d['quote_day']} ({lab0}): median executable borrow {np.median(b):+.1f} bp, mid {np.median(bm):+.1f} bp"
                       + (f"; SPXW box - bill {(box['rate'] - v0['r_bill']) * 1e4:+.1f} bp ({box['expiry']})" if box else "")
                       + "".join(f"; {s} replication (no dividend, expense ratio not removed) {k}/{n} below {cap_bp:.0f} bp, median {m:+.1f} bp"
                                 for s, (n, k, m) in sorted((d.get("replications") or {}).items()) if n))
    core = share_claim(vdays, need=need, kind="ge", min_n=min_n, unit="pairs on day one",
                       label=f"share of near-ATM pairs with r_bill - r_impl_exec < {cap_bp:.0f} bp (r_bill = FRED DGS3MO)")
    head = (f"SPY ATM synthetic short, r_impl from C_bid - P_ask = S - K e^-rT, 30-64 DTE before {EX_DATE}, strikes within "
            f"+/- 2% of spot, implicit borrow r_bill - r_impl")
    return _finish(core, min_n, "pairs on day one", head, "; controls: " + "; ".join(ctl) + "; stale-quote filter not implementable "
                   "(the capture carries no per-quote timestamps)", {"controls": ctl})


# =============================================================================== T-507: synthetic call cost ==

def synthetic_call_rows(by: dict, spot: float, quote_day: str, r: float, root: str = "SPY", dte_range=(30, 64),
                        ex_date: str = EX_DATE, band: float = 0.05, half_spread: float = SPY_HALF_SPREAD,
                        r_alt: Optional[float] = None) -> list:
    """Per (K, T): cheaper = (S_ask + P_ask) < (C_ask + K e^{-rT}); also at r_alt (the SPX box rate control) and at mids."""
    rows = []
    for (rt, e), legs in sorted(by.items()):
        dte = _dte(e, quote_day)
        if rt != root or not (dte_range[0] <= dte <= dte_range[1] and e < ex_date):
            continue
        T = dte / 365.0
        for k in sorted(set(legs["call"]) & set(legs["put"])):
            if abs(k / spot - 1.0) > band:
                continue
            c, p = legs["call"][k], legs["put"][k]
            if not (_ok(c) and _ok(p)):
                continue
            lhs, rhs = spot + half_spread + p[1], c[1] + k * math.exp(-r * T)
            rows.append({"expiry": e, "K": k, "cheaper": lhs < rhs, "gap": rhs - lhs,
                         "cheaper_mid": spot + _mid(p) < _mid(c) + k * math.exp(-r * T),
                         "cheaper_box": None if r_alt is None else lhs < c[1] + k * math.exp(-r_alt * T)})
    return rows


def synthetic_call_claim(days: Sequence[dict], need: float = 0.60, min_n: int = T507_MIN_N) -> dict:
    vdays, ctl = [], []
    for d in days:
        vdays.append(_counted(d, lambda v: {"n": len(v["rows"]), "k": sum(1 for x in v["rows"] if x["cheaper"])}))
        lab0, v0 = _first_var(d)
        if v0 and v0["rows"]:
            n0 = len(v0["rows"])
            mid = sum(1 for x in v0["rows"] if x["cheaper_mid"]) / n0
            bx = [x["cheaper_box"] for x in v0["rows"] if x["cheaper_box"] is not None]
            ctl.append(f"{d['quote_day']} ({lab0}): mid-price share {_pct(mid)}"
                       + (f", with the SPXW box rate in place of the bill {_pct(sum(bx) / len(bx))}" if bx else "")
                       + f", median cost gap {np.median([x['gap'] for x in v0['rows']]):+.3f}"
                       + "".join(f"; {s} replication (no dividend) {k}/{n}" for s, (n, k) in sorted((d.get("replications") or {}).items()) if n))
    core = share_claim(vdays, need=need, kind="ge", min_n=min_n, unit="strikes on day one",
                       label="share of strikes with S_ask + P_ask < C_ask + K e^(-r_bill T) (r_bill = FRED DGS3MO)")
    if core["rows"]:
        core["rows"].append(SASK_CRIT)
    head = (f"SPY protective put vs call + bills (S_ask = spot + ${SPY_HALF_SPREAD:.3f}, ASSUMED), 30-64 DTE before {EX_DATE}, "
            f"strikes within +/- 5%")
    return _finish(core, min_n, "strikes on day one", head, "; controls: " + "; ".join(ctl), {"controls": ctl})


# ========================================================================= T-184: synthetic long financing ==

def synthetic_long_expiries(by: dict, spot: float, quote_day: str, r_bill: float, divs, root: str = "SPY",
                            dte_range=(180, 365), div_scale: float = 1.0) -> list:
    """Per expiry with dte in dte_range: the ATM strike (nearest spot with both legs usable), r_impl_exec solving
    C_ask - P_bid = S - PV(D) - K e^{-rT} (dividends discounted at the bill), r_impl_mid, and the gap to the bill."""
    out = []
    amt = ({m: a * div_scale for m, a in divs.items()} if isinstance(divs, dict) else (divs * div_scale if divs else None))
    for (rt, e), legs in sorted(by.items()):
        dte = _dte(e, quote_day)
        if rt != root or not dte_range[0] <= dte <= dte_range[1]:
            continue
        ks = [k for k in legs["call"] if k in legs["put"] and _ok(legs["call"][k]) and _ok(legs["put"][k])]
        if not ks:
            continue
        k = min(ks, key=lambda x: (abs(x - spot), x))
        c, p = legs["call"][k], legs["put"][k]
        T = dte / 365.0
        pvd = pv_div(quote_day, quote_day, e, amt, r_bill)
        x, xm = spot - pvd - (c[1] - p[0]), spot - pvd - (_mid(c) - _mid(p))
        if x <= 0 or xm <= 0:
            continue
        ri, rm = -math.log(x / k) / T, -math.log(xm / k) / T
        out.append({"expiry": e, "dte": dte, "K": k, "pv_div": pvd, "r_impl": ri, "gap_bp": (ri - r_bill) * 1e4,
                    "gap_mid_bp": (rm - r_bill) * 1e4})
    return out


def synthetic_long_claim(days: Sequence[dict], need: float = 0.80, min_n: int = T184_MIN_N, cap_bp: float = 50.0) -> dict:
    """T-184. days: {'quote_day', 'variants': {label: {'rows'}}, 'div_lo', 'div_hi' (rows at -/+ 10% dividends, first
    variant), 'replications'}. n counts expiry observations pooled over capture days (one day lists 4-5 such expiries)."""
    vdays, ctl = [], []
    for d in days:
        vdays.append(_counted(d, lambda v: {"n": len(v["rows"]), "k": sum(1 for x in v["rows"] if x["gap_bp"] < cap_bp)}))
        lab0, v0 = _first_var(d)
        if v0 and v0["rows"]:
            sens = []
            for tag in ("div_lo", "div_hi"):
                rs = d.get(tag) or []
                if rs:
                    sens.append(f"dividends {'-' if tag == 'div_lo' else '+'}10%: {sum(1 for x in rs if x['gap_bp'] < cap_bp)}/{len(rs)}")
            ctl.append(f"{d['quote_day']} ({lab0}): " + ", ".join(f"{x['expiry']} K {x['K']:.0f} {x['gap_bp']:+.1f} bp (mid {x['gap_mid_bp']:+.1f}, "
                                                                 f"PV(D) {x['pv_div']:.2f})" for x in v0["rows"])
                       + ("; " + "; ".join(sens) if sens else "")
                       + "".join(f"; {s} replication (no dividend) gaps " + ", ".join(f"{g:+.0f}" for g in gs) + " bp"
                                 for s, gs in sorted((d.get("replications") or {}).items()) if gs))
    core = share_claim(vdays, need=need, kind="ge", min_n=min_n, unit="expiry observations over capture days",
                       label=f"share of 180-365 DTE expiries with r_impl_exec - r_bill < {cap_bp:.0f} bp (r_bill = FRED DGS3MO)", n_mode="total")
    head = ("SPY ATM synthetic long, call at ask / put at bid, PV(D) from the trailing four distributions on the projected "
            "quarterly ex-dates, r_impl_exec - bill per expiry")
    return _finish(core, min_n, "expiry observations over capture days", head, "; detail: " + "; ".join(ctl)
                   + "; QQQ/IWM replications not run (their ex-dividend schedules are not archived)", {"controls": ctl})


# ===================================================================== T-191: early exercise of deep ITM puts ==

def itm_put_rows(by: dict, spot: float, quote_day: str, r: float, div_amount, root: str = "SPY", min_ratio: float = 1.10,
                 tick: float = SPY_TICK, skip_zero_bid_calls: bool = False) -> tuple:
    """Puts with K/S >= min_ratio (bid > 0, not crossed) and a quoted same-strike call: at = |P_mid - (K - S)| <= tick +
    half the put's spread; met = K (1 - e^{-rT}) > C_mid + PV(D in (quote day, expiry])."""
    rows, dropped = [], 0
    for (rt, e), legs in sorted(by.items()):
        dte = _dte(e, quote_day)
        if rt != root or dte < 1:
            continue
        T = dte / 365.0
        pvd = pv_div(quote_day, quote_day, e, div_amount, r)
        for k, p in legs["put"].items():
            if k / spot < min_ratio:
                continue
            if not _ok(p):
                dropped += 1
                continue
            c = legs["call"].get(k)
            if c is None or not _buyable(c) or (skip_zero_bid_calls and c[0] <= 0):
                continue
            rows.append({"expiry": e, "dte": dte, "K": k, "met": k * (1.0 - math.exp(-r * T)) > _mid(c) + pvd,
                         "at": abs(_mid(p) - (k - spot)) <= tick + 0.5 * (p[1] - p[0]), "dev": _mid(p) - (k - spot)})
    return rows, dropped


def spx_itm_control(by: dict, spot: float, quote_day: str, r: float, min_ratio: float = 1.10, tick: float = SPX_TICK) -> dict:
    """SPX/SPXW (European) deep ITM puts: share pinned at undiscounted intrinsic K - S (within a tick + half-spread), and
    share at or below discounted intrinsic K e^{-rT} - S (within the same tolerance)."""
    n = pinned = below = 0
    for (rt, e), legs in by.items():
        dte = _dte(e, quote_day)
        if dte < 1:
            continue
        T = dte / 365.0
        for k, p in legs["put"].items():
            if k / spot < min_ratio or not _ok(p):
                continue
            n += 1
            tol = tick + 0.5 * (p[1] - p[0])
            pinned += abs(_mid(p) - (k - spot)) <= tol
            below += _mid(p) - (k * math.exp(-r * T) - spot) <= tol
    return {"n": n, "pinned": pinned / n if n else None, "at_or_below": below / n if n else None}


def early_exercise_claim(days: Sequence[dict], margin: float = 0.30, min_n: int = T191_MIN_N, stable: int = T191_STABLE) -> dict:
    """T-191. days: {'quote_day', 'variants': {spot/DGS3MO: {'rows', 'ci', 'cluster'}}, 'reported': {spot/DTB3: ...},
    'spx', 'no_zero_bid_calls'}. Day passes (per variant) when diff > margin and the 95% CI lower bound > margin; fails
    decisively when the upper bound < margin. Robust over the deciding variants; the reported (DTB3) ones are shown
    beside them and never decide; a day with no deciding variant (no DGS3MO print) is unjudged. Stability: no failing
    day among the first ``stable`` captured days, all passing once there are ``stable``."""
    per, txt = [], []

    def judge(v):
        ci = v["ci"]
        if ci["diff"] is None:
            return {"pass": None, "decisive": False, **ci}
        lo, hi = ci["ci"]
        return {"pass": bool(ci["diff"] > margin and lo > margin), "decisive": bool(hi < margin), **ci}
    for d in days:
        tests = {lab: judge(v) for lab, v in d["variants"].items()}
        reported = {lab: judge(v) for lab, v in (d.get("reported") or {}).items()}
        ok = _robust([t["pass"] for t in tests.values()])
        lab0, v0 = _first_var(d)
        per.append({"quote_day": d["quote_day"], "pass": ok, "decisive": ok is False and all(t["decisive"] for t in tests.values()),
                    "tests": tests, "reported": reported, "unjudged": not tests, "n": len(v0["rows"]) if v0 else 0})
        if v0 is None:
            txt.append(f"{d['quote_day']}: no bill print -> undecided")
            continue
        c0, cl = v0["ci"], v0.get("cluster") or {}
        txt.append(f"{d['quote_day']}: {per[-1]['n']} puts; criterion met {c0['n_met']} (at intrinsic {_pct(c0['share_met'])}), failed "
                   f"{c0['n_failed']} (at intrinsic {_pct(c0['share_failed'])}); difference ({lab0}) {_s(None if c0['diff'] is None else 100 * c0['diff'], 1)} pp, "
                   f"95% CI across strikes {_s(None if c0['ci'][0] is None else 100 * c0['ci'][0], 1)} to {_s(None if c0['ci'][1] is None else 100 * c0['ci'][1], 1)} pp"
                   + (f" (expiry-cluster CI {_s(100 * cl['ci'][0], 1)} to {_s(100 * cl['ci'][1], 1)} pp over {cl['n_expiries']} expiries)" if cl.get("ci", [None])[0] is not None else "")
                   + ("; by variant " + _var_txt(tests, lambda t: f"{_s(None if t['diff'] is None else 100 * t['diff'], 1)} pp")
                      if tests else "; no DGS3MO print for this quote day (unjudged, a data limit)")
                   + ("; DTB3 beside it, not deciding: " + _var_txt(reported, lambda t: f"{_s(None if t['diff'] is None else 100 * t['diff'], 1)} pp")
                      if reported else "")
                   + (f"; excluding zero-bid calls {_s(100 * d['no_zero_bid_calls']['diff'], 1)} pp" if d.get("no_zero_bid_calls") and d["no_zero_bid_calls"]["diff"] is not None else "")
                   + (f"; SPX control (European): {_pct(d['spx']['pinned'])} of {d['spx']['n']} deep ITM puts pinned at undiscounted intrinsic, "
                      f"{_pct(d['spx']['at_or_below'])} at or below discounted intrinsic" if d.get("spx") and d["spx"]["n"] else "")
                   + f" -> {_ok_txt(ok)}")
    if not per:
        return {"verdict": "inconclusive", "n": 0, "reason": "no SPY capture with deep ITM puts", "stat": {}}
    d0 = per[0]
    first = per[:stable]
    if any(p["pass"] is False for p in first):
        stab = False
    elif len(per) >= stable and all(p["pass"] for p in first):
        stab = True
    else:
        stab = None
    rows = [(f"day one ({d0['quote_day']}): difference > {margin:.0%} with the 95% CI excluding {margin:.0%}", d0["pass"], d0["decisive"]),
            (f"stable over {stable} captured days ({len(per)} so far; no failing day)", stab, stab is False)]
    verdict, why = _decide(rows, d0["n"], min_n, "puts on day one")
    reason = ("SPY puts with K/S >= 1.10 (bid > 0), at intrinsic when |P_mid - (K - S)| <= $0.01 + half-spread, grouped by "
              "K(1 - e^-rT) > C_mid + PV(D) with r the trial's FRED DGS3MO (continuous): " + "; ".join(txt) + "; the QQQ/IWM replication is not run (their ex-dividend "
              f"schedules are not archived) — {why}")
    return {"verdict": verdict, "n": d0["n"], "reason": reason, "stat": {"per_day": per, "stable": stab, "verdict": verdict}}


# ================================================================================ T-500: butterfly convexity ==

def butterfly_scan(by: dict, spot: float, quote_day: str, band: float = 0.20, core: float = 0.10) -> dict:
    """Equally spaced butterflies on adjacent LISTED strikes (per root, expiry, type), all three within +/- band of spot
    and every leg usable (bid > 0, ask >= bid). B_exec = ask(K1) - 2 bid(K2) + ask(K3); B_mid likewise at mids. Returns
    counts, per-expiry clusters and the core (all strikes within +/- core) / wing split."""
    n = k = km = 0
    clusters = defaultdict(lambda: [0, 0])
    split = {"core": [0, 0], "wing": [0, 0]}
    dropped = 0
    for (rt, e), legs in by.items():
        if _dte(e, quote_day) < 1:
            continue
        for typ in ("call", "put"):
            q = legs[typ]
            ks = sorted(q)
            for i in range(1, len(ks) - 1):
                k1, k2, k3 = ks[i - 1], ks[i], ks[i + 1]
                if abs((k2 - k1) - (k3 - k2)) > 1e-9 or any(abs(x / spot - 1.0) > band for x in (k1, k2, k3)):
                    continue
                if not all(_ok(q[x]) for x in (k1, k2, k3)):
                    dropped += 1
                    continue
                b = q[k1][1] - 2.0 * q[k2][0] + q[k3][1]
                bm = _mid(q[k1]) - 2.0 * _mid(q[k2]) + _mid(q[k3])
                v = b < -1e-12
                n += 1; k += v; km += bm < -1e-12
                clusters[(rt, e)][0] += v; clusters[(rt, e)][1] += 1
                s = split["core" if all(abs(x / spot - 1.0) <= core for x in (k1, k2, k3)) else "wing"]
                s[0] += v; s[1] += 1
    return {"n": n, "k": k, "k_mid": km, "dropped": dropped, "clusters": dict(clusters), "split": split}


def butterfly_claim(days: Sequence[dict], chains: Sequence[str] = ("SPX", "SPY"), need: float = 0.005, min_n: int = T500_MIN_N,
                    days_need: float = 0.80, min_days: int = MIN_DAYS) -> dict:
    """T-500. days: {'quote_day', 'scans': {chain: butterfly_scan}} (oldest first). Per chain: share < need with the 95%
    upper bound (max of Clopper-Pearson and the expiry-cluster bootstrap) < need; every named chain must be captured."""
    per, txt = [], []
    for d in days:
        tests = {}
        for ch in chains:
            sc = d["scans"].get(ch)
            if not sc or not sc["n"]:
                tests[ch] = {"pass": None, "decisive": False, "n": 0, "k": 0, "share": None}
                continue
            cl = list(sc["clusters"].values())
            up = cluster_share_upper([c[0] for c in cl], [c[1] for c in cl])
            t = share_test(sc["k"], sc["n"], need, "lt", min_n=min_n, bound=True, extra_upper=up)
            t["cluster_upper"] = up
            tests[ch] = t
        ok = _all_ok([_eff(t, t.get("n", 0), min_n) for t in tests.values()])  # every chain passes; rule 5 per chain
        per.append({"quote_day": d["quote_day"], "tests": tests, "pass": ok,
                    "decisive": ok is False and any(t.get("decisive") for t in tests.values() if t.get("pass") is False)})
        txt.append(f"{d['quote_day']}: " + "; ".join(
            f"{ch} {d['scans'][ch]['k']}/{d['scans'][ch]['n']} credit butterflies ({_pct(tests[ch]['share'], 3)}, 95% upper "
            f"{_pct(tests[ch].get('upper_used'), 3)}; mid-price negative {_pct(d['scans'][ch]['k_mid'] / d['scans'][ch]['n'], 1)}; core "
            f"{d['scans'][ch]['split']['core'][0]}/{d['scans'][ch]['split']['core'][1]}, wings {d['scans'][ch]['split']['wing'][0]}/"
            f"{d['scans'][ch]['split']['wing'][1]}; {d['scans'][ch]['dropped']} dropped for a zero-bid or crossed leg)"
            if d["scans"].get(ch) and d["scans"][ch]["n"] else f"{ch} not captured" for ch in chains))
    if not per:
        return {"verdict": "inconclusive", "n": 0, "reason": "no SPX or SPY capture", "stat": {}}
    d0 = per[0]
    rows = []
    for ch in chains:                       # rule 5 per chain: each chain's day-one sample is held to min_n
        t = d0["tests"][ch]
        ok = t["pass"]
        name = (f"day one {ch}: share < {need:.1%} with the 95% upper bound < {need:.1%} ({_pct(t.get('share'), 3)} of {t.get('n', 0)}, "
                f"upper {_pct(t.get('upper_used'), 3)})")
        if ok is False and t.get("n", 0) < min_n and not t.get("decisive"):
            name, ok = name + " [fails, not decisively, below min_n]", None
        rows.append((name, ok, t.get("decisive", False)))
    absent = [ch for ch in chains if not any(p["tests"][ch]["n"] for p in per)]
    rows.append(("every named chain captured" + (f" (missing {absent})" if absent else ""), None if absent else True, False))
    days_ok = _days_share([p["pass"] for p in per], days_need, min_days)
    rows.append((f"on >= {days_need:.0%} of captured days ({sum(1 for p in per if p['pass'])} of {len(per)}; needs >= {min_days} days)",
                 days_ok, days_ok is False))
    n0 = sum(t["n"] for t in d0["tests"].values())
    verdict, why = _decide(rows, n0, min_n, "butterflies on day one")
    reason = ("Executable credit butterflies (ask wings, bid body), adjacent equally spaced listed strikes within +/- 20% of the "
              "quote-day close, all expiries, every leg bid > 0 and not crossed: " + "; ".join(txt) + f" — {why}")
    return {"verdict": verdict, "n": n0, "reason": reason, "stat": {"per_day": per, "days_ok": days_ok, "verdict": verdict,
                                                                  "scans": [{ch: {k: v for k, v in sc.items() if k != "clusters"} for ch, sc in d["scans"].items()} for d in days]}}


# ============================================================================== T-501: calendar arbitrage ==

def calendar_scan(by: dict, spot: float, quote_day: str, root: str = "SPY", deep_delta: float = DEEP_DELTA) -> dict:
    """Same-strike call/put pairs at adjacent listed expiries: violation when far_ask < near_bid. The near leg needs
    bid > 0 (the control's exclusion) and an uncrossed quote; the far leg an offer. Deep ITM calls (near |delta| >=
    deep_delta) whose pair straddles a projected ex-date are separated (reported, not in the share)."""
    exps = _expiries(by, root, quote_day)
    n = k = km = 0
    sep = [0, 0]
    dropped = {"zero_bid_near": 0, "no_offer_far": 0}
    for e1, e2 in zip(exps[:-1], exps[1:]):
        straddles = bool(ex_dates_between(e1, e2))
        for typ in ("call", "put"):
            q1, q2 = by[(root, e1)][typ], by[(root, e2)][typ]
            for K in sorted(set(q1) & set(q2)):
                nq, fq = q1[K], q2[K]
                if not _ok(nq):
                    dropped["zero_bid_near"] += 1
                    continue
                if not _buyable(fq):
                    dropped["no_offer_far"] += 1
                    continue
                v = fq[1] < nq[0]
                if typ == "call" and straddles and nq[2] is not None and abs(nq[2]) >= deep_delta:
                    sep[0] += v; sep[1] += 1
                    continue
                n += 1; k += v
                km += (0.5 * (fq[0] + fq[1])) < _mid(nq)
    return {"n": n, "k": k, "k_mid": km, "separated": sep, "dropped": dropped}


def total_variance_scan(by: dict, spot: float, quote_day: str, min_dte: int = 7, moneyness: float = 0.10) -> Optional[dict]:
    """SPX companion (European): per root, adjacent expiries, the far expiry's total implied variance iv^2 T at the near
    expiry's OTM forward-moneyness points ln(K/F) (linear interpolation, inside the far range only); a violation when it
    is below the near one. F per expiry from OLS of C_mid - P_mid on K over strikes within +/- moneyness."""
    def fwd(legs):
        ks = [x for x in sorted(legs["call"]) if x in legs["put"] and _ok(legs["call"][x]) and _ok(legs["put"][x]) and abs(x / spot - 1) <= moneyness]
        if len(ks) < 5:
            return None
        K = np.array(ks)
        y = np.array([_mid(legs["call"][x]) - _mid(legs["put"][x]) for x in ks])
        b, a = np.polyfit(K, y, 1)
        return float(-a / b) if b < 0 else None

    n = k = 0
    roots = sorted({rt for rt, _ in by})
    for rt in roots:
        exps = [e for e in _expiries(by, rt, quote_day) if _dte(e, quote_day) >= min_dte]
        pts = {}
        for e in exps:
            F = fwd(by[(rt, e)])
            if F is None:
                continue
            T = _dte(e, quote_day) / 365.0
            xs = []
            for K, q in by[(rt, e)]["put"].items():
                if K < F and _ok(q) and q[3] and q[3] > 0:
                    xs.append((math.log(K / F), q[3] ** 2 * T))
            for K, q in by[(rt, e)]["call"].items():
                if K >= F and _ok(q) and q[3] and q[3] > 0:
                    xs.append((math.log(K / F), q[3] ** 2 * T))
            if len(xs) >= 5:
                xs.sort()
                pts[e] = (np.array([x for x, _ in xs]), np.array([w for _, w in xs]))
        es = sorted(pts)
        for e1, e2 in zip(es[:-1], es[1:]):
            x1, w1 = pts[e1]
            x2, w2 = pts[e2]
            sel = (x1 >= x2.min()) & (x1 <= x2.max())
            if not sel.any():
                continue
            w2i = np.interp(x1[sel], x2, w2)
            n += int(sel.sum())
            k += int((w2i < w1[sel]).sum())
    return {"n": n, "k": k, "share": k / n if n else None}


def calendar_claim(days: Sequence[dict], need: float = 0.001, min_n: int = T501_MIN_N) -> dict:
    vdays, ctl = [], []
    for d in days:
        sc = d["scan"]
        vdays.append({"quote_day": d["quote_day"], "variants": {"executable": {"n": sc["n"], "k": sc["k"]}}})
        tv = d.get("tv")
        ctl.append(f"{d['quote_day']}: mid-price inversions {_pct(sc['k_mid'] / sc['n'] if sc['n'] else None, 2)}; deep ITM calls straddling "
                   f"the ex-date (separated) {sc['separated'][0]}/{sc['separated'][1]}; dropped {sc['dropped']['zero_bid_near']} zero-bid near "
                   f"and {sc['dropped']['no_offer_far']} offerless far legs"
                   + (f"; SPX total-variance companion {tv['k']}/{tv['n']} ({_pct(tv['share'], 2)}) points with far total variance "
                      f"below near at the same forward-moneyness" if tv and tv["n"] else ""))
    core = share_claim(vdays, need=need, kind="lt", min_n=min_n, unit="pairs on day one",
                       label="share of same-strike adjacent-expiry pairs with far ask < near bid")
    head = "SPY (American) calendars bought for a credit, same strike, adjacent listed expiries"
    return _finish(core, min_n, "pairs on day one", head, "; " + "; ".join(ctl) + "; the Deribit total-variance replication is not "
                   "run (only per-expiry ATM marks are archived)", {"controls": ctl})


# ===================================================================================== T-508: vertical bounds ==

def vertical_scan(by: dict, quote_day: str, r: float, european: bool) -> dict:
    """Adjacent listed strikes per (root, expiry, type), both legs usable. Calls K1 < K2: debit = ask(K1) - bid(K2),
    credit = bid(K1) - ask(K2); puts: debit = ask(K2) - bid(K1), credit = bid(K2) - ask(K1). Violation when debit < 0
    (monotonicity) or credit > width bound ((K2 - K1) e^{-rT} European, K2 - K1 American); mids as a diagnostic."""
    n = k = mono = width = km = dropped = 0
    for (rt, e), legs in by.items():
        dte = _dte(e, quote_day)
        if dte < 1:
            continue
        T = dte / 365.0
        for typ in ("call", "put"):
            q = legs[typ]
            ks = sorted(q)
            for k1, k2 in zip(ks[:-1], ks[1:]):
                a1, a2 = q[k1], q[k2]
                if not (_ok(a1) and _ok(a2)):
                    dropped += 1
                    continue
                wb = (k2 - k1) * (math.exp(-r * T) if european else 1.0)
                if typ == "call":
                    debit, credit, mid = a1[1] - a2[0], a1[0] - a2[1], _mid(a1) - _mid(a2)
                else:
                    debit, credit, mid = a2[1] - a1[0], a2[0] - a1[1], _mid(a2) - _mid(a1)
                m_, w_ = debit < -1e-12, credit > wb + 1e-12
                n += 1; k += m_ or w_; mono += m_; width += w_
                km += mid < -1e-12 or mid > wb + 1e-12
    return {"n": n, "k": k, "mono": mono, "width": width, "k_mid": km, "dropped": dropped}


def vertical_claim(days: Sequence[dict], chains: Sequence[str] = ("SPY", "SPX", "QQQ", "GLD", "IBIT"), need: float = 0.001,
                   min_n: int = T508_MIN_N, days_need: float = 0.80, min_days: int = MIN_DAYS) -> dict:
    """T-508. days: {'quote_day', 'scans': {bill label: {chain: vertical_scan}}, optional 'reported_scans': {DTB3 label:
    ...}}. Criteria on day one: the pooled share across the named chains and each named chain's own share (house rule 1)
    below need; every chain captured; >= 80% of captured days. 'scans' carries the trial's DGS3MO (it discounts SPX's
    width bound); 'reported_scans' (DTB3) are shown beside it and never decide; a day without 'scans' (no DGS3MO print)
    is unjudged."""
    per, txt = [], []

    def tests_of(scan_by_bill):
        tests = {}
        for bl, scans in scan_by_bill.items():
            pooled_n = sum(s["n"] for s in scans.values())
            pooled_k = sum(s["k"] for s in scans.values())
            tests[f"{bl}/pooled"] = share_test(pooled_k, pooled_n, need, "lt", min_n=min_n)
            for ch in chains:
                s = scans.get(ch)
                tests[f"{bl}/{ch}"] = share_test(s["k"], s["n"], need, "lt", min_n=min_n) if s and s["n"] else {"pass": None, "decisive": False, "n": 0, "share": None}
        return tests
    for d in days:
        tests, reported = tests_of(d["scans"]), tests_of(d.get("reported_scans") or {})
        by_bill = defaultdict(list)
        for lab, t in tests.items():
            by_bill[lab.rsplit("/", 1)[0]].append(_eff(t, t.get("n", 0), min_n))
        ok = _robust([_all_ok(v) for v in by_bill.values()])               # every chain and the pool, robust over bills
        per.append({"quote_day": d["quote_day"], "tests": tests, "reported": reported, "pass": ok, "unjudged": not tests})
        bl0, sc0 = next(iter((d["scans"] or d.get("reported_scans") or {"none": {}}).items()))
        rp = [(lab, t) for lab, t in reported.items() if lab.endswith("/pooled") or lab.endswith("/SPX")]
        txt.append(f"{d['quote_day']} ({bl0}" + ("" if d["scans"] else ": no DGS3MO print, unjudged") + "): " + "; ".join(
            f"{ch} {sc0[ch]['k']}/{sc0[ch]['n']} ({_pct(sc0[ch]['k'] / sc0[ch]['n'], 3)}; monotonicity {sc0[ch]['mono']}, width {sc0[ch]['width']}; "
            f"mid-price violations {_pct(sc0[ch]['k_mid'] / sc0[ch]['n'], 2)}; {sc0[ch]['dropped']} dropped)"
            if sc0.get(ch) and sc0[ch]["n"] else f"{ch} not captured" for ch in chains)
                   + ("; DTB3 beside it, not deciding: " + ", ".join(f"{lab} {_pct(t.get('share'), 3)}" for lab, t in rp) if rp else ""))
    if not per:
        return {"verdict": "inconclusive", "n": 0, "reason": "no chain capture", "stat": {}}
    d0 = per[0]

    def crit(key):
        ts = [t for lab, t in d0["tests"].items() if lab.endswith("/" + key)]
        if not ts:                          # no DGS3MO print on day one: unjudged, the reported (DTB3) result shown
            rs = [t for lab, t in d0["reported"].items() if lab.endswith("/" + key)]
            return None, False, (rs[0] if rs else {"n": 0, "k": 0, "share": None})
        ok = _robust([t["pass"] for t in ts])
        dec = ok is False and all(t.get("decisive") for t in ts)
        return ok, dec, ts[0]
    rows = []
    ok, dec, t = crit("pooled")
    rows.append((f"day one pooled share < {need:.1%} ({t['k']}/{t['n']} = {_pct(t['share'], 3)})", ok, dec))
    for ch in chains:                       # rule 5 per chain: each chain's day-one sample is held to min_n
        ok, dec, t = crit(ch)
        name = f"day one {ch} share < {need:.1%} ({_pct(t.get('share'), 3)} of {t.get('n', 0)})"
        if ok is False and t.get("n", 0) < min_n and not dec:
            name, ok = name + " [fails, not decisively, below min_n]", None
        rows.append((name, ok, dec))
    absent = [ch for ch in chains if not any(next(iter((d["scans"] or d.get("reported_scans") or {"none": {}}).values())).get(ch, {}).get("n")
                                             for d in days)]
    rows.append(("every named chain captured" + (f" (missing {absent})" if absent else ""), None if absent else True, False))
    days_ok = _days_share([p["pass"] for p in per], days_need, min_days)
    rows.append((f"on >= {days_need:.0%} of captured days ({sum(1 for p in per if p['pass'])} of {len(per)}; needs >= {min_days} days)",
                 days_ok, days_ok is False))
    n0 = crit("pooled")[2]["n"]
    verdict, why = _decide(rows, n0, min_n, "verticals on day one")
    reason = ("Adjacent-strike verticals at executable prices (debit < 0, or credit above the width bound: undiscounted for "
              "American SPY/QQQ/GLD/IBIT, discounted for European SPX at the trial's FRED DGS3MO), both legs bid > 0 and not crossed: "
              + "; ".join(txt) + f" — {why}")
    return {"verdict": verdict, "n": n0, "reason": reason, "stat": {"per_day": per, "days_ok": days_ok, "verdict": verdict,
                                                                  "scans": [d["scans"] for d in days],
                                                                  "reported_scans": [d.get("reported_scans") for d in days]}}


# ============================================================================ T-103: strangle vs straddle ==

def projected_ex_sessions(trading: Sequence[str]) -> list:
    """SPY's quarterly ex-dates projected on the trading calendar: the third Friday of Mar/Jun/Sep/Dec, or the prior
    session when that Friday is not a trading day."""
    ds = list(trading)
    if not ds:
        return []
    out = []
    for y in range(int(ds[0][:4]), int(ds[-1][:4]) + 2):
        for m in (3, 6, 9, 12):
            tf = _third_friday(y, m).isoformat()
            if tf <= ds[-1]:
                j = bisect_right(ds, tf) - 1
                if j >= 0:
                    out.append(ds[j])
            else:
                out.append(tf)
    return sorted(set(out))


def monthly_cycle_pairs(days: Sequence[str], vix: dict) -> list:
    """[(entry, exit)] session indices into ``days`` of the short-straddle harness's calendar (run.short_straddle_model ->
    volatility.overlay_backtest(calendar='monthly_expiry'), house rule 10(a)): over the sessions with a SPY and a VIX
    close, each cycle writes at one standard monthly expiry close (third Friday, prior session on a holiday) and settles
    at the next."""
    days = list(days)
    pos = {d: i for i, d in enumerate(days)}
    vdays = [d for d in days if d in vix]
    ex = monthly_expiry_sessions(vdays)
    return [(pos[vdays[i]], pos[vdays[j]]) for i, j in zip(ex[:-1], ex[1:])]


def strangle_panel(days: Sequence[str], close, adj, vix: dict, dtb3: dict, hold: int = T103_HOLD, start: str = "1993-01-01",
                   end: str = "9999-12-31", cycles: Optional[Sequence[tuple]] = None) -> dict:
    """Entries with a VIX close and a DTB3 print before them, from ``start``, whose exit close is <= end: the (entry,
    exit) session pairs of ``cycles`` (a named calendar, house rule 10(a)), else every session held ``hold`` sessions
    (the daily all-start grid, rule 10(b)). Per entry: S, S1 (raw closes at entry and exit), T (calendar days between
    them / 365), r (prior DTB3, continuous), PV(D) of the forecast dividends (last paid at or before entry) on projected
    ex-dates in (entry, exit]."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    events = dividend_events(days, close, adj)
    exs = projected_ex_sessions(days)
    dk = sorted(dtb3)
    pairs = list(cycles) if cycles is not None else [(i, i + hold) for i in range(max(0, len(days) - hold))]
    idx, out_, r, pvd = [], [], [], []
    for i, i1 in pairs:
        d = days[i]
        if d < start or i1 >= len(days) or i1 <= i or days[i1] > end or d not in vix:
            continue
        j = bisect_left(dk, d) - 1
        if j < 0:
            continue
        rr = dtb3_continuous(dtb3[dk[j]])
        amt = last_dividend(events, d)
        pv = 0.0
        if amt:
            q = date.fromisoformat(d)
            lo, hi = bisect_right(exs, d), bisect_right(exs, days[i1])
            for x in exs[lo:hi]:
                pv += amt * math.exp(-rr * (date.fromisoformat(x) - q).days / 365.0)
        idx.append(i); out_.append(i1); r.append(rr); pvd.append(pv)
    idx, ex_ = np.array(idx, dtype=np.int64), np.array(out_, dtype=np.int64)
    cal = "monthly_expiry" if cycles is not None else "daily_grid"
    if idx.size == 0:
        return {"idx": idx, "exit": ex_, "days": days, "hold": hold, "calendar": cal}
    ords = np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)
    return {"idx": idx, "exit": ex_, "days": days, "hold": hold, "calendar": cal, "S": close[idx], "S1": close[ex_],
            "T": (ords[ex_] - ords[idx]) / 365.0, "r": np.array(r), "pvd": np.array(pvd),
            "vix": np.array([vix[days[i]] for i in idx]) / 100.0, "entry_days": [days[i] for i in idx],
            "exit_days": [days[i] for i in ex_]}


def leg_ratios(panel: dict, mode: str, smile: Optional[Smile] = None, skew: Optional[dict] = None, skew_ref: Optional[float] = None,
               width: float = 0.05) -> Optional[dict]:
    """IV / VIX multipliers per entry for the ATM legs and the +/- width legs. 'flat': 1; 'smile': the captured shape r(K/S)
    (nearest of its 30/45-day curves to each entry's calendar DTE); 'skew': r(1) + (r(m) - r(1)) (SKEW_t - 100) /
    (SKEW_ref - 100), SKEW_t the entry day's close (None where missing)."""
    m = panel["idx"].size
    if mode == "flat":
        one = np.ones(m)
        return {"atm": one, "put": one, "call": one}
    if smile is None:
        return None
    dte = np.rint(panel["T"] * 365).astype(int)
    cache = {}

    def rat(x, t):
        key = (x, t)
        if key not in cache:
            cache[key] = smile.ratio(x, int(t))
        return cache[key]
    r1 = np.array([rat(1.0, t) for t in dte])
    rp = np.array([rat(1.0 - width, t) for t in dte])
    rc = np.array([rat(1.0 + width, t) for t in dte])
    if mode == "smile":
        return {"atm": r1, "put": rp, "call": rc}
    if mode == "skew":
        if not skew or not skew_ref or not skew_ref > 100.5:
            return None
        f = np.array([(skew[d] - 100.0) / (skew_ref - 100.0) if d in skew else np.nan for d in panel["entry_days"]])
        return {"atm": r1, "put": r1 + (rp - r1) * f, "call": r1 + (rc - r1) * f}
    raise ValueError(mode)


def structure_returns(panel: dict, ratios: dict, scale: float = 1.0, haircut: float = 0.05, width: float = 0.05) -> dict:
    """Per-cycle excess returns on notional of the short strangle (put at (1 - width) S, call at (1 + width) S) and the
    short ATM straddle, each leg priced by Black-Scholes on the dividend forward S - PV(D) at sigma = scale x ratio x
    VIX/100 (floor 1%), the premium cut by ``haircut`` and grown at the bill to expiry, settled at intrinsic on the raw
    close: x = (premium (1 - haircut) e^{rT} - payoff) / S. NaN where a ratio is missing."""
    S, S1, T, r = panel["S"], panel["S1"], panel["T"], panel["r"]
    F = S - panel["pvd"]
    V = panel["vix"]

    def px(K, ratio, kind):
        sig = np.maximum(scale * ratio * V, 0.01)
        sig = np.where(np.isfinite(sig), sig, 0.01)
        return bs.price(F, K, T, r, sig, kind, 0.0)
    kp, kc = (1.0 - width) * S, (1.0 + width) * S
    prem_str = px(kp, ratios["put"], "put") + px(kc, ratios["call"], "call")
    prem_atm = px(S, ratios["atm"], "put") + px(S, ratios["atm"], "call")
    pay_str = np.maximum(kp - S1, 0.0) + np.maximum(S1 - kc, 0.0)
    pay_atm = np.abs(S1 - S)
    g = (1.0 - haircut) * np.exp(r * T)
    xs = (prem_str * g - pay_str) / S
    xa = (prem_atm * g - pay_atm) / S
    bad = ~(np.isfinite(ratios["put"]) & np.isfinite(ratios["call"]) & np.isfinite(ratios["atm"]))
    xs = np.where(bad, np.nan, xs)
    xa = np.where(bad, np.nan, xa)
    return {"strangle": xs, "straddle": xa, "prem_strangle": prem_str / S, "prem_straddle": prem_atm / S}


def _mdd(x: np.ndarray) -> float:
    c = np.cumprod(1.0 + np.asarray(x, dtype=float))
    return float((c / np.maximum.accumulate(c) - 1.0).min()) if c.size else 0.0


def _psr(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    if x.size < 8 or not x.std(ddof=1) > 0:
        return None
    return float(probabilistic_sharpe_ratio(float(x.mean() / x.std(ddof=1)), 0.0, int(x.size), skewness(x), kurtosis(x)))


def _sr1(x: np.ndarray) -> Optional[float]:
    return float(x.mean() / x.std()) if x.size > 2 and x.std() > 0 else None


def _sr_diff(rr: Optional[dict], sel: Optional[np.ndarray] = None) -> Optional[dict]:
    """Point per-cycle Sharpe difference (strangle - straddle, population sd) of one structure_returns run on ``sel``."""
    if rr is None:
        return None
    m = np.isfinite(rr["strangle"]) & np.isfinite(rr["straddle"])
    if sel is not None:
        m &= sel
    sa, sb = _sr1(rr["strangle"][m]), _sr1(rr["straddle"][m])
    return {"diff": None if sa is None or sb is None else sa - sb, "n": int(m.sum()), "sr_strangle": sa, "sr_straddle": sb}


def grid_diagnostics(panel: dict, runs: dict, blocks=T103_GRID_BLOCKS, n_boot: int = N_BOOT, offset_block: int = 6) -> dict:
    """T-103's 21-session daily all-start grid, a DIAGNOSTIC only (the claim names its calendar, rule 10(a)): pooled
    smile / flat-VIX / SKEW-scaled Sharpe differences with the smile one's studentized test at ``blocks`` entries (seed 0),
    and per start offset (that offset's own non-overlapping grid) the smile difference with its one-sided p and the
    compare_strategies mean-difference p, the flat-VIX and SKEW-scaled differences, PSR and max drawdowns."""
    hold, idx = panel["hold"], panel["idx"]
    sm = runs["smile"]
    ok = np.isfinite(sm["strangle"]) & np.isfinite(sm["straddle"])
    pooled = {k: _sr_diff(runs.get(k)) for k in ("smile", "flat", "skew")}
    tests = [sharpe_diff_test(sm["strangle"][ok], sm["straddle"][ok], blk, n_boot, 0) for blk in blocks]
    off = (idx - idx[0]) % hold
    per = []
    for o in range(hold):
        sel = (off == o) & ok
        xa, xb = sm["strangle"][sel], sm["straddle"][sel]
        if xa.size < 8:
            continue
        t = sharpe_diff_test(xa, xb, offset_block, 1000, 0)
        try:
            p_mean = float(block_bootstrap_pvalue(xa, xb, n_boot=1000, block_len=offset_block, seed=0))
        except ValueError:
            p_mean = None
        fl, sk = _sr_diff(runs.get("flat"), off == o), _sr_diff(runs.get("skew"), off == o)
        per.append({"offset": o, "n": int(xa.size), "diff": t["diff"], "p_gt0": t["p_gt0"], "p_mean_diff": p_mean,
                    "flat_diff": fl["diff"] if fl else None, "skew_diff": sk["diff"] if sk else None,
                    "psr_strangle": _psr(xa), "psr_straddle": _psr(xb), "mdd_strangle": _mdd(xa), "mdd_straddle": _mdd(xb)})

    def rng(key):
        v = [p[key] for p in per if p[key] is not None]
        return [min(v), max(v)] if v else [None, None]
    keys = ("diff", "p_gt0", "p_mean_diff", "flat_diff", "skew_diff", "psr_strangle", "psr_straddle", "mdd_strangle", "mdd_straddle")
    return {"hold": hold, "n_entries": int(idx.size), "first_entry": panel["entry_days"][0], "last_entry": panel["entry_days"][-1],
            "pooled": pooled, "pooled_tests": tests, "per_offset": per, "ranges": {k: rng(k) for k in keys},
            "offsets_passing": sum(1 for p in per if p["diff"] is not None and p["diff"] > 0 and p["p_gt0"] is not None and p["p_gt0"] < 0.05),
            "negative_offsets": {k: sum(1 for p in per if p[k] is not None and p[k] < 0) for k in ("diff", "flat_diff", "skew_diff")},
            "known_offsets": {k: sum(1 for p in per if p[k] is not None) for k in ("diff", "flat_diff", "skew_diff")}}


def _grid_txt(g: Optional[dict]) -> str:
    if not g:
        return ""
    pt, rg, ng, kn = g["pooled"], g["ranges"], g["negative_offsets"], g["known_offsets"]
    d = lambda k: _s((pt.get(k) or {}).get("diff"), 4)
    return (f"; DIAGNOSTIC only (not the named calendar, never a criterion): the {g['hold']}-session daily all-start grid, "
            f"{g['n_entries']} entries {g['first_entry']}..{g['last_entry']}, pooled smile {d('smile')} (one-sided p "
            + ", ".join(f"{_f(t['p_gt0'], 4)} at block {t['block']}" for t in g["pooled_tests"]) + f"), flat VIX {d('flat')}, "
            f"SKEW-scaled {d('skew')}; per start offset ({len(g['per_offset'])} of {g['hold']}): smile {_s(rg['diff'][0], 4)} to "
            f"{_s(rg['diff'][1], 4)} ({g['offsets_passing']} pass at one-sided p < 0.05, {ng['diff']} negative), flat VIX "
            f"{_s(rg['flat_diff'][0], 4)} to {_s(rg['flat_diff'][1], 4)} ({ng['flat_diff']} of {kn['flat_diff']} offsets negative), "
            f"SKEW-scaled {_s(rg['skew_diff'][0], 4)} to {_s(rg['skew_diff'][1], 4)} ({ng['skew_diff']} of {kn['skew_diff']} negative), "
            f"compare_strategies mean-difference p {_f(rg['p_mean_diff'][0], 4)} to {_f(rg['p_mean_diff'][1], 4)}, max drawdown "
            f"strangle {_pct(rg['mdd_strangle'][0])} to {_pct(rg['mdd_strangle'][1])}, straddle {_pct(rg['mdd_straddle'][0])} to "
            f"{_pct(rg['mdd_straddle'][1])}")


def strangle_vs_straddle(panel: dict, runs: dict, n_smile_days: int, min_n: int = T103_MIN_N, blocks=T103_BLOCKS,
                         seeds=T103_SEEDS, n_boot: int = N_BOOT, smile_days_needed: int = T103_SMILE_DAYS,
                         grid: Optional[dict] = None, mean_block: int = 6) -> dict:
    """T-103 on the named calendar. panel: the short-straddle harness's monthly-expiry cycles (strangle_panel with
    monthly_cycle_pairs: one non-overlapping entry per cycle, T from each cycle's own dates); runs: {'smile', 'flat',
    'skew' or None, 'iv0.9', 'iv1.1'} (structure_returns on that panel). Criteria: the smile-scaled paired per-cycle
    Sharpe difference (strangle - straddle) > 0 with one-sided p < 0.05 on every (block, seed) variant (blocks in
    cycles); the flat-VIX and SKEW-scaled point differences > 0; the proxy cap (smile refit on ``smile_days_needed``
    capture days) as a not-yet-implementable criterion; n = monthly cycles (the claim's min_n units). grid:
    grid_diagnostics on the 21-session daily all-start grid, reported beside the result and never deciding."""
    idx = panel["idx"]
    sm = runs["smile"]
    ok = np.isfinite(sm["strangle"]) & np.isfinite(sm["straddle"])
    a, b = sm["strangle"][ok], sm["straddle"][ok]
    n = int(ok.sum())
    tests = [sharpe_diff_test(a, b, blk, n_boot, sd) for blk in blocks for sd in seeds]
    d0 = tests[0]["diff"]
    passes = [None if t["p_gt0"] is None else bool(t["diff"] > 0 and t["p_gt0"] < 0.05) for t in tests]
    prim = _robust(passes)
    sign = {key: _sr_diff(runs.get(key)) for key in ("flat", "skew", "iv0.9", "iv1.1")}
    try:
        p_mean = float(block_bootstrap_pvalue(a, b, n_boot=n_boot, block_len=mean_block, seed=0))
    except ValueError:
        p_mean = None
    fl, sk = sign.get("flat"), sign.get("skew")
    ps = [t["p_gt0"] for t in tests if t["p_gt0"] is not None]
    rows = [(f"{MP} smile-scaled: paired per-cycle Sharpe difference (strangle - straddle) > 0 with one-sided p < 0.05 on every "
             f"bootstrap variant (blocks {list(blocks)} cycles x seeds {list(seeds)}): difference {_s(d0, 4)}, one-sided p "
             f"{_f(min(ps) if ps else None, 4)} to {_f(max(ps) if ps else None, 4)}", prim, prim is False),
            (f"same sign under flat VIX (difference {_s(fl['diff'] if fl else None, 4)})", None if not fl or fl["diff"] is None else bool(fl["diff"] > 0), False),
            (f"same sign under the SKEW-scaled smile (difference {_s(sk['diff'] if sk else None, 4)})", None if not sk or sk["diff"] is None else bool(sk["diff"] > 0), False),
            (f"proxy cap: smile ratios refit on >= {smile_days_needed} capture days ({n_smile_days} so far)",
             True if n_smile_days >= smile_days_needed else None, False)]
    verdict, why = _decide(rows, n, min_n, "monthly-expiry cycles")
    t0 = tests[0]
    sa, sb = _sr1(a), _sr1(b)
    dte = np.rint(panel["T"][ok] * 365).astype(int) if n else np.zeros(0, dtype=int)
    first, last = panel["entry_days"][0], panel.get("exit_days", panel["entry_days"])[-1]
    reason = (f"{MP} 30-DTE SPY short strangle (+/- 5% strikes) vs ATM short straddle, smile-scaled VIX model (captured spy-smile "
              f"IV/VIX on {n_smile_days} quote days, held fixed through history), dividend forward, DTB3, 5%-of-premium haircut on both, "
              f"settled on raw closes, per-cycle excess return on notional; on the short-straddle harness's entry dates (rule 10(a): "
              f"overlay_backtest's monthly expiry calendar, written at one third-Friday expiry close and settled at the next): {n} cycles "
              f"{first}..{last} ({_f(float(dte.min()) if dte.size else None, 0)}-{_f(float(dte.max()) if dte.size else None, 0)} "
              f"calendar days): per-cycle Sharpe strangle {_f(sa, 4)} vs straddle {_f(sb, 4)} (x sqrt(12) annualised "
              f"{_f(None if sa is None else sa * math.sqrt(12), 3)} vs {_f(None if sb is None else sb * math.sqrt(12), 3)}), difference "
              f"{_s(d0, 4)} (95% CI {_s(t0['ci'][0], 4)} to {_s(t0['ci'][1], 4)}, two-sided p {_f(t0['p_two'], 4)}; one-sided p by "
              f"(block, seed) " + ", ".join(f"({t['block']}, {t['seed']}) {_f(t['p_gt0'], 4)}" for t in tests) + "); compare_strategies "
              f"mean-difference p {_f(p_mean, 4)} (block {mean_block}); flat VIX {_s(fl['diff'] if fl else None, 4)}, SKEW-scaled "
              f"{_s(sk['diff'] if sk else None, 4)}; IV scale 0.9 {_s((sign.get('iv0.9') or {}).get('diff'), 4)}, 1.1 "
              f"{_s((sign.get('iv1.1') or {}).get('diff'), 4)}; PSR strangle {_f(_psr(a), 3)}, straddle {_f(_psr(b), 3)}; max drawdown "
              f"strangle {_pct(_mdd(a))}, straddle {_pct(_mdd(b))}; skew of per-cycle returns strangle {_f(skewness(a), 2)}, straddle "
              f"{_f(skewness(b), 2)}" + _grid_txt(grid) + f" — {why}")
    stat = {"calendar": "monthly expiry (overlay_backtest calendar='monthly_expiry'): third-Friday expiry close to the next",
            "n_cycles": n, "first_entry": first, "last_exit": last, "cycle_calendar_days": [int(dte.min()), int(dte.max())] if dte.size else None,
            "sr_strangle": sa, "sr_straddle": sb, "diff": d0, "tests": tests, "primary": prim, "sensitivities": sign,
            "p_mean_diff": p_mean, "psr_strangle": _psr(a), "psr_straddle": _psr(b), "mdd_strangle": _mdd(a), "mdd_straddle": _mdd(b),
            "n_smile_days": n_smile_days, "skew_strangle": skewness(a), "skew_straddle": skewness(b),
            "mean_prem_strangle": float(np.nanmean(sm["prem_strangle"])), "mean_prem_straddle": float(np.nanmean(sm["prem_straddle"])),
            "grid_diagnostic": grid, "label": MP, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# =================================================================================================== harnesses ==

def _base(archive, notes: list, syms: Sequence[str], need_close: Sequence[str] = ("SPY",)) -> dict:
    """Shared inputs: bills, SPY dividend events, the trading calendar and the captures of ``syms``."""
    hist = {}
    for s in set(syms) | {"SPY"}:
        if _has(archive, HIST_B[s]):
            hist[s] = _spot_history(archive, HIST_B[s])
    trading = hist["SPY"][0] if "SPY" in hist else []
    dtb3 = _series(archive, DTB3_B) if _has(archive, DTB3_B) else {}
    dgs3mo = _series(archive, DGS3MO_B) if _has(archive, DGS3MO_B) else {}
    events = dividend_events(*hist["SPY"][:3]) if "SPY" in hist else []
    caps = {}
    for s in syms:
        nc = s in need_close
        if nc and s not in hist:
            notes.append(f"{s}: {HIST_B[s]} not archived, its captures cannot be priced")
            caps[s] = []
            continue
        caps[s] = load_captures(archive, s, notes, hist.get(s) if nc else None, hist[s][0] if s in hist else trading, need_close=nc)
    return {"hist": hist, "trading": trading, "dtb3": dtb3, "dgs3mo": dgs3mo, "events": events, "caps": caps}


def _skip_txt(notes: list) -> str:
    return f" [skipped: {'; '.join(notes)}]" if notes else ""


def _with_notes(reason: str, notes: list) -> str:
    """Insert the skip notes before the final ' — ' so the reason still ends with the _verdict explanation."""
    if not notes:
        return reason
    head, sep, tail = reason.rpartition(" — ")
    return (head + _skip_txt(notes) + sep + tail) if sep else reason + _skip_txt(notes)


def _chain_need(archive, syms: Sequence[str]) -> list:
    return [f"{CHAIN_P}{s}-<date>" for s in syms if not _capture_names(archive, s)]


def _named_bill_need(archive) -> list:
    """A DGS3MO-named claim needs fred-DGS3MO, or fred-DTB3 for the DGS3MO_REF date check (batch6_xc's T-199 rule)."""
    return [] if _has(archive, DGS3MO_B) else [DTB3_B]


def b6b_chain_jelly_roll(archive):
    """T-153: SPY 30/60-DTE mid jelly roll vs bill carry on every capture."""
    miss = _missing(archive, [SPY_B, DTB3_B] + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    B = _base(archive, notes, ["SPY", "SPX"] if _capture_names(archive, "SPX") and _has(archive, GSPC_B) else ["SPY"], ("SPY", "SPX"))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}
    days = []
    for cap in B["caps"]["SPY"]:
        qd = cap["quote_day"]
        bills = bill_variants(B["dtb3"], B["dgs3mo"], qd)
        if not bills:
            notes.append(f"{cap['name']} skipped: no bill print before {qd}")
            continue
        div = last_dividend(B["events"], qd)
        pair = jelly_pair(cap["by"], qd)
        if pair is None:
            notes.append(f"{cap['name']}: no 30/60-DTE expiry pair")
            continue
        alt = jelly_pair(cap["by"], qd, no_ex_span=True)
        prim = {bl: jelly_roll_day(cap["by"], cap["close"], qd, r, div, *pair) for bl, r in bills}
        if not next(iter(prim.values()))["n"]:
            notes.append(f"{cap['name']}: no strike passes the leg filters")
            continue
        altd = {bl: jelly_roll_day(cap["by"], cap["close"], qd, r, div, *alt) for bl, r in bills} if alt and alt != pair else None
        if altd and not next(iter(altd.values()))["n"]:
            altd = None
        sc = spx.get(qd)
        days.append({"quote_day": qd, "capture": cap["name"][-10:], "primary": prim, "alt": altd,
                     "spx": spx_roll_control(sc["by"], sc["close"], qd, bills[0][1]) if sc else None})
    rep = jelly_roll_claim(days)
    t181 = _t181_compare(B, [d["quote_day"] for d in days], spx)
    reason = rep["reason"]
    if t181:
        head, sep, tail = reason.rpartition(" — ")
        reason = head + "; T-181 parity_check on SPX (C - P regressed on K, 10 strikes, >= 30 DTE), implied rate minus bill: " + ", ".join(
            f"{x['day']} {_s(x['median_rate_gap_bp'], 0)} bp" for x in t181) + sep + tail
    return _out(dict(rep["stat"], skipped=notes, t181_parity_check=t181), rep["n"], rep["verdict"], _with_notes(reason, notes))


def _t181_compare(B: dict, quote_days: Sequence[str], spx: dict) -> Optional[list]:
    """T-153's control: options_market.parity_check (T-181) on the SPX captures of the same quote days."""
    caps = [(qd, "SPX", spx[qd]["close"], [{"value": v} for v in spx[qd]["values"]]) for qd in quote_days if qd in spx]
    if not caps or not B["dtb3"]:
        return None
    try:
        from mandel.experiments.options_market import parity_check
        pc = parity_check(caps, [{"value": {"day": d, "value": v}} for d, v in B["dtb3"].items()])
    except Exception:                      # a control must not break the harness
        return None
    return [{k: x.get(k) for k in ("day", "symbol", "pairs", "median_rate_gap_bp")} for x in pc.get("per_day", [])] or None


def _rate_days(B: dict, notes: list, fn, sync: bool = True, extra=None) -> list:
    """Per SPY capture: {'quote_day', 'variants': {spot/DGS3MO: {'rows', 'r_bill'}}, 'reported': {spot/DTB3: ...}, 'sync'}
    with rows = fn(cap, S, r). The trial's DGS3MO decides (named_bills); DTB3 is reported beside it; a quote day with no
    DGS3MO print keeps only the reported variants and is unjudged."""
    out = []
    for cap in B["caps"]["SPY"]:
        qd = cap["quote_day"]
        bills, rep = named_bills(B["dtb3"], B["dgs3mo"], qd)
        if not bills and not rep:
            notes.append(f"{cap['name']} skipped: no bill print before {qd}")
            continue
        if not bills:
            notes.append(f"{cap['name']}: no DGS3MO print before {qd} (unjudged; DTB3 shown beside it)")
        div = last_dividend(B["events"], qd)
        var, si, rvar = _named_variants(cap, bills, rep, div, sync=sync, root="SPY")
        d = {"quote_day": qd, "variants": {lab: {"rows": fn(cap, S, r), "r_bill": r} for lab, S, r in var},
             "reported": {lab: {"rows": fn(cap, S, r), "r_bill": r} for lab, S, r in rvar}, "sync": si, "cap": cap,
             "bills": bills or rep}
        if extra:
            extra(d)
        d.pop("cap")
        out.append(d)
    return out


def b6b_chain_conversion(archive):
    """T-182: SPY executable conversion lending rate vs the 3-month bill."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    has_spx = bool(_capture_names(archive, "SPX")) and _has(archive, GSPC_B)
    B = _base(archive, notes, ["SPY", "SPX"] if has_spx else ["SPY"], ("SPY", "SPX"))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}

    def box(d):
        rows = _first_var(d)[1]["rows"]
        exps = sorted({x["expiry"] for x in rows})
        d["box"] = _box_by_day(spx, d["quote_day"], exps[len(exps) // 2]) if exps else None
    days = _rate_days(B, notes, lambda cap, S, r: conversion_pairs(cap["by"], S, cap["quote_day"])[0], extra=box)
    rep = conversion_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_synthetic_short(archive):
    """T-185: SPY ATM synthetic short implicit borrow cost vs 50 bp."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    syms = ["SPY"] + (["SPX"] if _capture_names(archive, "SPX") and _has(archive, GSPC_B) else []) + \
           [s for s in ("GLD", "IBIT") if _capture_names(archive, s) and _has(archive, HIST_B[s])]
    B = _base(archive, notes, syms, tuple(syms))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}
    reps = {s: {c["quote_day"]: c for c in B["caps"].get(s, [])} for s in ("GLD", "IBIT")}

    def extra(d):
        rows = _first_var(d)[1]["rows"]
        exps = sorted({x["expiry"] for x in rows})
        d["box"] = _box_by_day(spx, d["quote_day"], exps[len(exps) // 2]) if exps else None
        r0 = d["bills"][0][1]
        d["replications"] = {}
        for s, caps in reps.items():
            c = caps.get(d["quote_day"])
            if c:
                rr = synthetic_short_pairs(c["by"], c["close"], d["quote_day"], r0, root=s, ex_date=None)
                d["replications"][s] = (len(rr), sum(1 for x in rr if x["borrow"] * 1e4 < 50), float(np.median([x["borrow"] * 1e4 for x in rr])) if rr else None)
    days = _rate_days(B, notes, lambda cap, S, r: synthetic_short_pairs(cap["by"], S, cap["quote_day"], r), extra=extra)
    rep = synthetic_short_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_synthetic_call(archive):
    """T-507: SPY stock + put at the ask vs call at the ask + bills."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    syms = ["SPY"] + (["SPX"] if _capture_names(archive, "SPX") and _has(archive, GSPC_B) else []) + \
           [s for s in ("GLD", "IBIT") if _capture_names(archive, s) and _has(archive, HIST_B[s])]
    B = _base(archive, notes, syms, tuple(syms))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}
    reps = {s: {c["quote_day"]: c for c in B["caps"].get(s, [])} for s in ("GLD", "IBIT")}

    def fn(cap, S, r):
        rows0 = synthetic_call_rows(cap["by"], S, cap["quote_day"], r)
        exps = sorted({x["expiry"] for x in rows0})
        bx = _box_by_day(spx, cap["quote_day"], exps[len(exps) // 2]) if exps else None
        return synthetic_call_rows(cap["by"], S, cap["quote_day"], r, r_alt=bx["rate"] if bx else None) if bx else rows0

    def extra(d):
        d["replications"] = {}
        for s, caps in reps.items():
            cc = caps.get(d["quote_day"])
            if cc:
                rr = synthetic_call_rows(cc["by"], cc["close"], d["quote_day"], d["bills"][0][1], root=s, ex_date="9999-12-31")
                d["replications"][s] = (len(rr), sum(1 for x in rr if x["cheaper"]))
    days = _rate_days(B, notes, fn, extra=extra)
    rep = synthetic_call_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_synthetic_long(archive):
    """T-184: SPY 180-365 DTE ATM synthetic-long financing rate vs bill + 50 bp."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    syms = ["SPY"] + [s for s in ("GLD", "IBIT") if _capture_names(archive, s) and _has(archive, HIST_B[s])]
    B = _base(archive, notes, syms, tuple(syms))
    reps = {s: {c["quote_day"]: c for c in B["caps"].get(s, [])} for s in ("GLD", "IBIT")}

    def fn(cap, S, r):
        return synthetic_long_expiries(cap["by"], S, cap["quote_day"], r, trailing_four(B["events"], cap["quote_day"]))

    def extra(d):
        cap, (bl, r0) = d["cap"], d["bills"][0]
        t4 = trailing_four(B["events"], d["quote_day"])
        d["div_lo"] = synthetic_long_expiries(cap["by"], cap["close"], d["quote_day"], r0, t4, div_scale=0.9)
        d["div_hi"] = synthetic_long_expiries(cap["by"], cap["close"], d["quote_day"], r0, t4, div_scale=1.1)
        d["replications"] = {}
        for s, caps in reps.items():
            c = caps.get(d["quote_day"])
            if c:
                d["replications"][s] = [x["gap_bp"] for x in synthetic_long_expiries(c["by"], c["close"], d["quote_day"], r0, None, root=s)]
    days = _rate_days(B, notes, fn, extra=extra)
    if not B["events"]:
        notes.append("no SPY dividend history: PV(D) = 0")
    rep = synthetic_long_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_itm_put_exercise(archive):
    """T-191: deep ITM SPY puts pinned at intrinsic where early exercise for interest is optimal."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    has_spx = bool(_capture_names(archive, "SPX")) and _has(archive, GSPC_B)
    B = _base(archive, notes, ["SPY", "SPX"] if has_spx else ["SPY"], ("SPY", "SPX"))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}
    days = []
    for cap in B["caps"]["SPY"]:
        qd = cap["quote_day"]
        bills, repb = named_bills(B["dtb3"], B["dgs3mo"], qd)
        if not bills and not repb:
            notes.append(f"{cap['name']} skipped: no bill print before {qd}")
            continue
        if not bills:
            notes.append(f"{cap['name']}: no DGS3MO print before {qd} (unjudged; DTB3 shown beside it)")
        div = last_dividend(B["events"], qd)
        var, si, rvar = _named_variants(cap, bills, repb, div, root="SPY")

        def group(vs):
            out = {}
            for lab, S, r in vs:
                rows, _ = itm_put_rows(cap["by"], S, qd, r, div)
                out[lab] = {"rows": rows, "ci": diff_share_ci([x["at"] for x in rows if x["met"]], [x["at"] for x in rows if not x["met"]]),
                            "cluster": diff_share_cluster_ci(rows)}
            return out
        dv, dr = group(var), group(rvar)
        r0 = (bills or repb)[0][1]
        rows_nz, _ = itm_put_rows(cap["by"], cap["close"], qd, r0, div, skip_zero_bid_calls=True)
        sc = spx.get(qd)
        days.append({"quote_day": qd, "variants": dv, "reported": dr, "sync": si,
                     "no_zero_bid_calls": diff_share_ci([x["at"] for x in rows_nz if x["met"]], [x["at"] for x in rows_nz if not x["met"]], n_boot=200),
                     "spx": spx_itm_control(sc["by"], sc["close"], qd, r0) if sc else None})
    rep = early_exercise_claim(days)
    stat = rep["stat"]
    for p in stat.get("per_day", []):
        for t in p["tests"].values():
            t.pop("rows", None)
    return _out(dict(stat, skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_butterfly_arb(archive):
    """T-500: executable credit butterflies on the SPX and SPY chains."""
    miss = _missing(archive, [SPY_B, GSPC_B] + _chain_need(archive, ["SPX", "SPY"]))
    if miss:
        return miss
    notes = []
    B = _base(archive, notes, ["SPX", "SPY"], ("SPX", "SPY"))
    by_day = defaultdict(dict)
    for s in ("SPX", "SPY"):
        for c in B["caps"][s]:
            by_day[c["quote_day"]][s] = butterfly_scan(c["by"], c["close"], c["quote_day"])
    days = [{"quote_day": qd, "scans": sc} for qd, sc in sorted(by_day.items())]
    rep = butterfly_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_calendar_arb(archive):
    """T-501: SPY calendars bought for a credit (far ask < near bid)."""
    miss = _missing(archive, [SPY_B] + _chain_need(archive, ["SPY"]))
    if miss:
        return miss
    notes = []
    has_spx = bool(_capture_names(archive, "SPX")) and _has(archive, GSPC_B)
    B = _base(archive, notes, ["SPY", "SPX"] if has_spx else ["SPY"], ("SPY", "SPX"))
    spx = {c["quote_day"]: c for c in B["caps"].get("SPX", [])}
    days = []
    for cap in B["caps"]["SPY"]:
        sc = spx.get(cap["quote_day"])
        days.append({"quote_day": cap["quote_day"], "scan": calendar_scan(cap["by"], cap["close"], cap["quote_day"]),
                     "tv": total_variance_scan(sc["by"], sc["close"], cap["quote_day"]) if sc else None})
    rep = calendar_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


T508_CHAINS = ("SPY", "SPX", "QQQ", "GLD", "IBIT")


def b6b_chain_vertical_bounds(archive):
    """T-508: vertical-spread monotonicity and width-bound violations on SPY, SPX, QQQ, GLD and IBIT."""
    miss = _missing(archive, [SPY_B] + _named_bill_need(archive) + _chain_need(archive, T508_CHAINS))
    if miss:
        return miss
    notes = []
    B = _base(archive, notes, list(T508_CHAINS), need_close=())
    by_day = defaultdict(dict)
    for s in T508_CHAINS:
        for c in B["caps"][s]:
            by_day[c["quote_day"]][s] = c
    days = []
    for qd, caps in sorted(by_day.items()):
        bills, repb = named_bills(B["dtb3"], B["dgs3mo"], qd)
        if not bills and not repb:
            notes.append(f"{qd} skipped: no bill print before it")
            continue
        if not bills:
            notes.append(f"{qd}: no DGS3MO print before it (unjudged; DTB3 shown beside it)")
        scan = lambda bl_r: {bl: {s: vertical_scan(c["by"], qd, r, european=(s == "SPX")) for s, c in caps.items()} for bl, r in bl_r}
        days.append({"quote_day": qd, "scans": scan(bills), "reported_scans": scan(repb)})
    rep = vertical_claim(days)
    return _out(dict(rep["stat"], skipped=notes), rep["n"], rep["verdict"], _with_notes(rep["reason"], notes))


def b6b_chain_strangle_vs_straddle(archive):
    """T-103: MODEL-PRICED short strangle vs short straddle Sharpe, smile-scaled VIX model, 1993-2026."""
    smiles = [n for n in _names(archive, SMILE_P) if _has(archive, n)]
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B] + ([] if smiles else [SMILE_P + "<date>"]))
    if miss:
        return miss
    notes = []
    days, close, adj = _daily_from_rows(_rows(archive, SPY_B))
    vix = _index(archive, VIX_B)
    dtb3 = _series(archive, DTB3_B)
    srows = [r for n in smiles for r in _rows(archive, n)]
    smile = Smile(srows)
    skew = _index(archive, SKEW_B) if _has(archive, SKEW_B) else {}
    if not skew:
        notes.append(f"{SKEW_B} not archived: the SKEW-scaled sensitivity is not implemented")
    qds = sorted({r["value"]["quote_date"] for r in srows})
    ref = [skew[q] for q in qds if q in skew]
    skew_ref = float(np.mean(ref)) if ref else None
    if skew and not ref:
        notes.append(f"no SKEW close on the smile quote days {qds}: the SKEW-scaled sensitivity is not implemented")
    def runs_for(panel):
        sm_r = leg_ratios(panel, "smile", smile)
        sk = leg_ratios(panel, "skew", smile, skew, skew_ref) if skew_ref else None
        return {"smile": structure_returns(panel, sm_r), "flat": structure_returns(panel, leg_ratios(panel, "flat")),
                "iv0.9": structure_returns(panel, sm_r, scale=0.9), "iv1.1": structure_returns(panel, sm_r, scale=1.1),
                "skew": structure_returns(panel, sk) if sk is not None else None}
    # rule 10(a): the trial's "same entry dates as the short-straddle harness" = overlay_backtest's monthly expiry calendar
    panel = strangle_panel(days, close, adj, vix, dtb3, start="1993-01-01", cycles=monthly_cycle_pairs(days, vix))
    if panel["idx"].size < 30:
        return _out({"n_cycles": int(panel["idx"].size)}, int(panel["idx"].size), "inconclusive",
                    "too few monthly-expiry cycles with a VIX close and a bill print — no data")
    grid_panel = strangle_panel(days, close, adj, vix, dtb3, start="1993-01-01")
    grid = grid_diagnostics(grid_panel, runs_for(grid_panel)) if grid_panel["idx"].size >= 30 * T103_HOLD else None
    rep = strangle_vs_straddle(panel, runs_for(panel), smile.n_days, grid=grid)
    return _out(dict(rep["stat"], skipped=notes, smile_quote_days=qds, skew_ref=skew_ref), rep["n"], rep["verdict"],
                _with_notes(rep["reason"], notes))


HARNESSES = {
    "b6b_chain_jelly_roll": b6b_chain_jelly_roll,
    "b6b_chain_conversion": b6b_chain_conversion,
    "b6b_chain_synthetic_long": b6b_chain_synthetic_long,
    "b6b_chain_synthetic_short": b6b_chain_synthetic_short,
    "b6b_chain_itm_put_exercise": b6b_chain_itm_put_exercise,
    "b6b_chain_butterfly_arb": b6b_chain_butterfly_arb,
    "b6b_chain_calendar_arb": b6b_chain_calendar_arb,
    "b6b_chain_synthetic_call": b6b_chain_synthetic_call,
    "b6b_chain_vertical_bounds": b6b_chain_vertical_bounds,
    "b6b_chain_strangle_vs_straddle": b6b_chain_strangle_vs_straddle,
}

THEORY_MAP = {
    "T-153": "b6b_chain_jelly_roll",
    "T-182": "b6b_chain_conversion",
    "T-184": "b6b_chain_synthetic_long",
    "T-185": "b6b_chain_synthetic_short",
    "T-191": "b6b_chain_itm_put_exercise",
    "T-500": "b6b_chain_butterfly_arb",
    "T-501": "b6b_chain_calendar_arb",
    "T-507": "b6b_chain_synthetic_call",
    "T-508": "b6b_chain_vertical_bounds",
    "T-103": "b6b_chain_strangle_vs_straddle",
}
