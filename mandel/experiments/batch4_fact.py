"""
Factor and ETF-tilt harnesses, batch 4 (group ``fact``)
=======================================================

Twelve underlying-library claims on Ken French factors, AQR BAB and factor-ETF spreads: T-382 (HML), T-383 (QUAL
hedged alpha), T-385 (IJR-IWM), T-386 (RMW), T-387 (SPLV/SPHB betting against beta), T-388 (factor momentum),
T-389 (contrarian factor timing), T-397 (sin industries), T-445 (accruals), T-446 (UMD), T-447 (CMA), T-449 (net
share issuance). Each claim is tested as worded: its window, its pass rule and the costs it names. ``_verdict``
from underlying2 decides: an implemented criterion that fails -> not_supported; a criterion that cannot be
implemented with the archive (None) -> at best inconclusive.

Shared conventions
------------------
* Ken French returns are percent and are converted to decimals. Monthly series are built by compounding daily
  returns within calendar months, keeping complete months only. AQR BAB is decimal; AQR revises its history, so
  it is not point in time (the bundle's capture date is the vintage). The Ken French files are vintages too.
* ETF legs use dividend-adjusted closes (``adjclose``) through ``load_series``. A long-short book is reset to its
  target notionals at the close before the first trading day of each month (and, for T-387, when its ex-ante beta
  drifts); between resets the legs drift with prices. P&L is per unit of capital, so a monthly P&L is the sum of
  that month's daily P&L. Betas and hedge ratios for a reset at the close of day t use returns through day t-1.
* Means: annualised x252 (equity trading days), studentized (bootstrap-t) circular block bootstrap 95% interval;
  the standard error is a Bartlett long-run variance with bandwidth equal to the block length.
* Factor regressions: monthly OLS with Newey-West (Bartlett, 6 lags) standard errors.
* Sharpe differences: Ledoit-Wolf (2008) studentized circular block bootstrap with a delta-method HAC error.
* "Survives the family-wide DSR": deflated Sharpe ratio > 0.95 of the claim's daily return series with
  n_trials = 34 (the family size the claims state) and the variance of trial Sharpes estimated from the daily
  family variants the archive supports (``FAMILY``, 14 of the 34), floored at the zero-skill variance 1/(T-1).
* Ken French files currently end 2026-08 and AQR BAB 2026-07; windows that the claims state as ending 2026-09 are
  reported with the end actually used.
* Sample size (house rule 5, ``_decide``): at or above the trial's min_n (in the claim's own units: days or months)
  every criterion is judged at face value. Below min_n the verdict can never be supported, and a failing criterion
  still counts only when it fails decisively, i.e. its interval lies wholly on the wrong side of the claimed bound
  (none of these criteria has bounded outcomes, so "fails at min_n whatever the missing observations are" never
  applies): a 'lower 95% bound > 0' criterion when the whole 95% interval lies at or below 0; an 'NW t >= c'
  criterion when the coefficient's +/-c standard-error interval lies wholly at or below 0 (t <= -c); '|beta| < b'
  when the beta's 95% NW interval lies wholly outside (-b, b); a 'DSR > 0.95' criterion when the PSR's one-sided
  95% interval of the Sharpe lies wholly below the deflation benchmark (DSR <= 0.05), with the benchmark the trial
  would face at min_n (the 1/(T-1) floor of the trial-Sharpe variance taken at min_n, which can only lower it) and
  at least 8 observations. PBO and a QMJ loading given without an interval never fail decisively. Any other
  failure below min_n is undecided (None), so the verdict is inconclusive.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict, load_series
from mandel.experiments.volatility import index_closes
from mandel.validation.backtest_eval import deflated_sharpe_ratio, expected_max_sharpe, sharpe_ratio

FAMILY_TRIALS = 34
DSR_PASS = 0.95
NW_LAGS = 6
FF5 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


# =============================================================== statistics (pure) ==

def _lrv(x: np.ndarray, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance of a 2-D array (rows are samples), bandwidth ``bw``."""
    x = x - x.mean(axis=1, keepdims=True)
    n = x.shape[1]
    v = np.einsum("ij,ij->i", x, x) / n
    for k in range(1, max(1, bw)):
        v = v + 2.0 * (1.0 - k / bw) * np.einsum("ij,ij->i", x[:, k:], x[:, :-k]) / n
    return np.maximum(v, 1e-300)


def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def stud_mean_ci(x, block: int, n_boot: int = 10000, seed: int = 0, chunk: int = 500) -> tuple[float, float, float]:
    """(mean, lower 2.5%, upper 97.5%) of the mean of ``x`` by a studentized circular block bootstrap."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return (float(x.mean()) if n else float("nan")), float("nan"), float("nan")
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    se = math.sqrt(float(_lrv(x[None, :], block)[0]) / n)
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        s = x[_boot_idx(rng, n, block, k)]
        ts.append((s.mean(axis=1) - m) / np.sqrt(_lrv(s, block) / n))
        done += k
    q_lo, q_hi = np.quantile(np.concatenate(ts), [0.025, 0.975])
    return m, m - float(q_hi) * se, m - float(q_lo) * se


def ols_nw(y, X, lags: int = NW_LAGS) -> dict:
    """OLS of y on [1, X] with Newey-West (Bartlett) standard errors. coef[0] is the intercept."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    Z = np.column_stack([np.ones(len(y)), X])
    n, k = Z.shape
    ZtZi = np.linalg.pinv(Z.T @ Z)
    b = ZtZi @ Z.T @ y
    u = y - Z @ b
    g = Z * u[:, None]
    S = g.T @ g
    for lag in range(1, lags + 1):
        G = g[lag:].T @ g[:-lag]
        S = S + (1.0 - lag / (lags + 1)) * (G + G.T)
    V = ZtZi @ S @ ZtZi * n / max(n - k, 1)
    se = np.sqrt(np.maximum(np.diag(V), 1e-300))
    r2 = 1.0 - float(u @ u) / max(float(((y - y.mean()) ** 2).sum()), 1e-300)
    return {"coef": b, "se": se, "t": b / se, "n": int(n), "r2": r2}


def alpha_boot_ci(y, X, block: int = 12, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentile 95% interval of the regression intercept by a circular block bootstrap of (y, X) rows."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    Z = np.column_stack([np.ones(len(y)), X])
    n = len(y)
    block = max(1, min(block, n // 4))
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot)
    for j, idx in enumerate(_boot_idx(rng, n, block, n_boot)):
        out[j] = np.linalg.lstsq(Z[idx], y[idx], rcond=None)[0][0]
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def _sd_stat(A: np.ndarray, B: np.ndarray, bw: int) -> tuple[np.ndarray, np.ndarray]:
    """Row-wise Sharpe difference SR(A)-SR(B) (per period) and its delta-method HAC standard error (Ledoit-Wolf 2008)."""
    n = A.shape[1]
    mua, mub = A.mean(axis=1), B.mean(axis=1)
    ga, gb = (A * A).mean(axis=1), (B * B).mean(axis=1)
    sa = np.sqrt(np.maximum(ga - mua ** 2, 1e-300))
    sb = np.sqrt(np.maximum(gb - mub ** 2, 1e-300))
    d = mua / sa - mub / sb
    grad = np.stack([ga / sa ** 3, -gb / sb ** 3, -mua / (2 * sa ** 3), mub / (2 * sb ** 3)], axis=1)
    Y = np.stack([A - mua[:, None], B - mub[:, None], A * A - ga[:, None], B * B - gb[:, None]], axis=2)
    Psi = np.einsum("mti,mtj->mij", Y, Y) / n
    for k in range(1, max(1, bw)):
        G = np.einsum("mti,mtj->mij", Y[:, k:], Y[:, :-k]) / n
        Psi = Psi + (1.0 - k / bw) * (G + np.transpose(G, (0, 2, 1)))
    var = np.einsum("mi,mij,mj->m", grad, Psi, grad) / n
    return d, np.sqrt(np.maximum(var, 1e-300))


def sharpe_diff_ci(a, b, ppy: int, block: int, n_boot: int = 5000, seed: int = 0, chunk: int = 500) -> tuple[float, float, float]:
    """(annualised Sharpe difference a minus b, lower 2.5%, upper 97.5%) by a studentized circular block bootstrap
    of paired periods."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = a.size
    k_ann = math.sqrt(ppy)
    if n < 8 or a.std() == 0 or b.std() == 0:
        return float("nan"), float("nan"), float("nan")
    block = max(1, min(int(block), n // 4))
    d, se = _sd_stat(a[None, :], b[None, :], block)
    d, se = float(d[0]), float(se[0])
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        idx = _boot_idx(rng, n, block, k)
        ds, ses = _sd_stat(a[idx], b[idx], block)
        ts.append((ds - d) / ses)
        done += k
    q_lo, q_hi = np.quantile(np.concatenate(ts), [0.025, 0.975])
    return d * k_ann, (d - float(q_hi) * se) * k_ann, (d - float(q_lo) * se) * k_ann


def _family_var(family_sharpes, T: int) -> float:
    """Variance of the family's trial Sharpes (ddof 1; 0 with fewer than 2), floored at the zero-skill variance 1/(T-1)."""
    fs = np.asarray(list(family_sharpes), dtype=float)
    v = float(fs.var(ddof=1)) if fs.size > 1 else 0.0
    return max(v, 1.0 / max(1, T - 1))


def family_dsr(x, family_sharpes: Sequence[float], n_trials: int = FAMILY_TRIALS) -> dict:
    """DSR of ``x`` (per-period returns) against the best of ``n_trials`` trials whose Sharpe variance is estimated
    from ``family_sharpes`` (per-period Sharpes of the computable family members), floored at 1/(T-1)."""
    x = np.asarray(x, dtype=float)
    fs = np.asarray(list(family_sharpes), dtype=float)
    v = _family_var(fs, x.size)
    dsr = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=v))
    return {"dsr": dsr, "var_trials_sr": v, "n_trials": int(n_trials), "n_family_computed": int(fs.size),
            "sr_per_period": float(sharpe_ratio(x))}


# ============================================================ calendars and books ==

def _last_weekday(y: int, m: int) -> date:
    d = date(y, m, calendar.monthrange(y, m)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _first_weekday(y: int, m: int) -> date:
    d = date(y, m, 1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _month_complete(month: str, last_day: str) -> bool:
    return date.fromisoformat(last_day) >= _last_weekday(int(month[:4]), int(month[5:7])) - timedelta(days=3)


def _month_started(month: str, first_day: str) -> bool:
    return date.fromisoformat(first_day) <= _first_weekday(int(month[:4]), int(month[5:7])) + timedelta(days=3)


def _group_months(days, r) -> tuple[list[str], dict[str, list[float]]]:
    groups: dict[str, list[float]] = {}
    for d, x in zip(days, r):
        groups.setdefault(d[:7], []).append(float(x))
    ms = sorted(groups)
    if ms and not _month_complete(ms[-1], days[-1]):
        ms = ms[:-1]
    if ms and not _month_started(ms[0], days[0]):
        ms = ms[1:]
    return ms, groups


def compound_monthly(days, r) -> tuple[list[str], np.ndarray]:
    """Calendar-month compounded returns from daily decimal returns (complete months only)."""
    ms, g = _group_months(days, r)
    return ms, np.array([float(np.prod(1.0 + np.asarray(g[m])) - 1.0) for m in ms])


def sum_monthly(days, pnl) -> tuple[list[str], np.ndarray]:
    """Monthly P&L of a book reset monthly: sum of the daily P&L per unit capital. Months with any NaN day (book not
    yet live) and incomplete calendar months are dropped."""
    ms, g = _group_months(days, pnl)
    ms = [m for m in ms if np.all(np.isfinite(g[m]))]
    return ms, np.array([float(np.sum(g[m])) for m in ms])


def trailing_beta(y, x, window: int = 60, gap: int = 2) -> np.ndarray:
    """b[i] = OLS slope of y on x over the ``window`` returns ending at index i-gap. With gap=2 a position held over day
    i is set at the close of day i-1 with returns through day i-2 (data to t-1). NaN until enough data."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(y)

    def c(v):
        return np.concatenate([[0.0], np.cumsum(v)])

    cx, cy, cxx, cxy = c(x), c(y), c(x * x), c(x * y)
    b = np.full(n, np.nan)
    i = np.arange(n)
    hi = i - gap + 1
    lo = hi - window
    ok = lo >= 0
    hi, lo = hi[ok], lo[ok]
    sx, sy = cx[hi] - cx[lo], cy[hi] - cy[lo]
    vx = (cxx[hi] - cxx[lo]) - sx * sx / window
    cv = (cxy[hi] - cxy[lo]) - sx * sy / window
    with np.errstate(divide="ignore", invalid="ignore"):
        b[ok] = np.where(vx > 1e-18, cv / vx, np.nan)
    return b


def ls_book(days, rl, rs, wl, ws, rf=None, borrow: float = 0.0, fee: float = 0.0, fin_spread: float = 0.0,
            cost: float = 0.0, trigger: Optional[Callable[[int, float, float], bool]] = None, ppy: int = 252,
            return_pos: bool = False):
    """Daily P&L per unit capital of a long-short book: long ``wl[i]`` notional of rl, short ``ws[i]`` of rs.

    The book is (re)set to the target notionals on the first trading day of each month (at the prior close), when it is
    not yet live, or when ``trigger(i, L, S)`` says so; between resets the legs drift with prices. The net cash from
    the reset (ws - wl) earns rf[i] minus fin_spread/ppy (floored at 0) when positive and pays rf[i] plus
    fin_spread/ppy when negative (rf is a daily decimal rate). The short leg pays borrow/ppy a day, the long leg
    fee/ppy a day (only for fees a claim lists beyond NAV), and each reset that trades costs ``cost`` (a flat book
    reset to flat targets does not trade). NaN before the book is live. Returns (pnl, number of trading resets), plus
    the notionals (L, S) held over each day when ``return_pos``."""
    n = len(rl)
    out = np.full(n, np.nan)
    Lh, Sh = np.full(n, np.nan), np.full(n, np.nan)
    L = S = cash = 0.0
    live = False
    n_reb = 0
    for i in range(n):
        new_month = i == 0 or days[i][:7] != days[i - 1][:7]
        want = new_month or not live or (trigger is not None and trigger(i, L, S))
        c = 0.0
        if want and np.isfinite(wl[i]) and np.isfinite(ws[i]):
            traded = L != 0.0 or S != 0.0 or wl[i] != 0.0 or ws[i] != 0.0
            L, S = float(wl[i]), float(ws[i])
            cash = S - L
            live = True
            if traded:
                c = cost
                n_reb += 1
        if not live:
            continue
        Lh[i], Sh[i] = L, S
        r_f = float(rf[i]) if rf is not None and np.isfinite(rf[i]) else 0.0
        rate = r_f + fin_spread / ppy if cash < 0 else max(r_f - fin_spread / ppy, 0.0)
        out[i] = L * rl[i] - S * rs[i] + cash * rate - S * borrow / ppy - L * fee / ppy - c
        L *= 1.0 + rl[i]
        S *= 1.0 + rs[i]
    return (out, n_reb, Lh, Sh) if return_pos else (out, n_reb)


def _window(days, start: str, end: str) -> np.ndarray:
    return np.array([start <= d <= end for d in days], dtype=bool)


def _ann_means(days, r, spans) -> dict:
    out = {}
    for label, a, b in spans:
        m = _window(days, a, b)
        out[label] = float(np.mean(r[m]) * 252) if m.sum() > 20 else None
    return out


def _rolling(r: np.ndarray, w: int, ppy: int = 252) -> Optional[dict]:
    if r.size <= w:
        return None
    c = np.concatenate([[0.0], np.cumsum(r)])
    m = (c[w:] - c[:-w]) / w * ppy
    return {"min": float(m.min()), "max": float(m.max()), "share_positive": float((m > 0).mean()), "window": int(w)}


def _decide(rows: list, n: int, min_n: int, unit: str) -> tuple[str, str]:
    """``_verdict`` under house rule 5. rows: [(name, ok, decisive, evidence)] with ok True / False / None (not
    implemented), decisive True when a failure stands below min_n (its interval lies wholly on the wrong side of the
    claimed bound) and evidence a short note on that test. At or above min_n the sample-size criterion passes and every
    criterion is judged at face value. Below min_n a passing or decisively failing criterion keeps its bool, any other
    failure becomes None (undecided) and the unmet min_n criterion is None, so the verdict is never 'supported'."""
    face = [(name, ok) for name, ok, _, _ in rows]
    if n >= min_n:
        return _verdict([(f">= {min_n} {unit}", True)] + face)
    crit = []
    for name, ok, decisive, ev in rows:
        note = f": {ev}" if ev else ""
        if ok is None or ok:
            crit.append((name, ok))
        elif decisive:
            crit.append((f"{name} (fails decisively below min_n{note})", False))
        else:
            crit.append((f"{name} (fails, not decisively, below min_n{note}; undecided)", None))
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", None))
    v, why = _verdict(crit)
    v0, why0 = _verdict(face)
    return v, (f"only {n} {unit} in the window, below the trial's min_n {min_n}, so the verdict cannot be supported and a "
               f"failing criterion counts only when it fails decisively (house rule 5): {why} [criteria at face value: {v0}, {why0}]")


def _ci_row(name: str, lo: float, hi: float, hi_txt: str) -> tuple:
    """'lower 95% bound > 0': passes when lo > 0; fails decisively when the whole interval lies at or below 0 (hi <= 0)."""
    if not np.isfinite(hi):
        return (name, bool(lo > 0), False, "no interval (fewer than 8 observations or no variation)")
    dec = bool(hi <= 0)
    return (name, bool(lo > 0), dec, f"upper 95% bound {hi_txt} {'<=' if dec else '>'} 0")


def _t_row(name: str, t: Optional[float], c: float, strict: bool = False) -> tuple:
    """'NW t >= c' (``strict``: t > c): fails decisively when the coefficient's +/-c NW standard-error interval lies
    wholly at or below 0, i.e. t <= -c. None when the regression was not estimated."""
    if t is None:
        return (name, None, False, "")
    dec = bool(t <= -c)
    return (name, bool(t > c) if strict else bool(t >= c), dec,
            f"NW t {t:+.2f} {'<=' if dec else '>'} -{c:g}, so the +/-{c:g} se interval {'lies wholly at or below' if dec else 'reaches above'} 0")


def _dsr_row(name: str, ok: Optional[bool], x, n_trials: int, var_at_min_n: float) -> tuple:
    """'DSR > DSR_PASS'. The DSR is the PSR of the Sharpe against the deflation benchmark (the expected best of n_trials
    zero-skill Sharpes); a failure is decisive when that test's one-sided 95% interval of the Sharpe lies wholly below
    the benchmark the trial faces at min_n (trial-Sharpe variance ``var_at_min_n``): DSR <= 1 - DSR_PASS with the
    Sharpe under the benchmark. Needs >= 8 observations."""
    if ok is None or ok:
        return (name, ok, False, "")
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8 or not var_at_min_n > 0:
        return (name, ok, False, "too few observations to bound the Sharpe")
    sr0 = expected_max_sharpe(n_trials, var_at_min_n)
    d = float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=var_at_min_n))
    dec = bool(float(sharpe_ratio(x)) < sr0 and d <= 1.0 - DSR_PASS)
    return (name, ok, dec, f"DSR {d:.3f} against the min_n benchmark {'<=' if dec else '>'} {1.0 - DSR_PASS:.2f}")


def _trial_var(trial_sharpes: Sequence[float], T_at_min_n: int) -> float:
    """Trial-Sharpe variance as ``deflated_sharpe_ratio`` takes it from trial Sharpes (ddof 1), with its zero-skill
    fallback 1/(T-1) taken at min_n."""
    v = float(np.var(np.asarray(trial_sharpes, dtype=float), ddof=1)) if len(trial_sharpes) > 1 else 0.0
    return v if v > 0 else 1.0 / max(1, T_at_min_n - 1)


def _end_note(used_end: str, requested_end: str) -> str:
    """Flag a sample that stops before the month the claim names (the source file has not published it yet)."""
    return f" [data end {used_end}; claim window runs to {requested_end[:7]}]" if used_end and used_end[:7] < requested_end[:7] else ""


def _fmt_dsr(f: Optional[dict]) -> str:
    if f is None:
        return "family DSR not computed"
    return f"family DSR {f['dsr']:.3f} (needs > {DSR_PASS}; {f['n_trials']} trials, trial-Sharpe var {f['var_trials_sr']:.2e} from {f['n_family_computed']} computable variants)"


# ============================================================== core claim tests ==

def factor_mean_test(days, r, start: str, end: str, min_n: int, family_sharpes: Optional[Sequence[float]] = None,
                     label: str = "factor", regimes: Sequence[tuple] = (), roll_years: Optional[int] = None,
                     block: int = 20, n_boot: int = 10000, seed: int = 0) -> dict:
    """Daily factor mean claim (T-382 HML, T-386 RMW, T-446 UMD, T-447 CMA): lower 95% studentized block-bootstrap
    bound of the annualised mean > 0 over >= min_n days AND family-wide DSR > 0.95 (None when no family given)."""
    r = np.asarray(r, dtype=float)
    m = _window(days, start, end)
    x = r[m]
    d = [dd for dd, k in zip(days, m) if k]
    n = int(x.size)
    mean, lo, hi = stud_mean_ci(x, block, n_boot, seed) if n else (float("nan"),) * 3
    fd = family_dsr(x, family_sharpes) if (family_sharpes is not None and n > 1) else None
    rows = [_ci_row("lower 95% bound of the annualised mean > 0", lo, hi, f"{hi * 252:+.2%}/yr"),
            _dsr_row(f"family-wide DSR > {DSR_PASS}", None if fd is None else bool(fd["dsr"] > DSR_PASS), x, FAMILY_TRIALS,
                     _family_var(family_sharpes, max(n, min_n)) if fd is not None else 0.0)]
    v, why = _decide(rows, n, min_n, "daily observations")
    reg = _ann_means(d, x, regimes) if n else {}
    roll = _rolling(x, 252 * roll_years) if (roll_years and n) else None
    window_used = f"{d[0]}..{d[-1]}" if n else "empty"
    reg_s = ("; regimes " + ", ".join(f"{k} {val:+.2%}" for k, val in reg.items() if val is not None)) if reg else ""
    roll_s = f"; rolling {roll_years}y means {roll['min']:+.2%} to {roll['max']:+.2%} ({roll['share_positive']:.0%} > 0)" if roll else ""
    reason = (f"{label} {window_used}{_end_note(d[-1] if n else '', end)} (n={n} days): annualised mean {mean * 252:+.2%}, 95% studentized block-{block} CI "
              f"{lo * 252:+.2%} to {hi * 252:+.2%}; {_fmt_dsr(fd)}{reg_s}{roll_s} — {why}")
    return {"label": label, "n": n, "n_days": n, "window_requested": f"{start}..{end}", "window_used": window_used,
            "mean_ann": mean * 252, "ci_ann": [lo * 252, hi * 252], "sharpe_ann": float(sharpe_ratio(x, 252)) if n > 1 else None,
            "family": fd, "regimes": reg, "rolling": roll, "verdict": v, "reason": reason}


def hedged_spread(days, r_long, r_hedge, rf, window: int = 60, borrow: float = 0.0, fee: float = 0.0, cost: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Long $1 of r_long, short beta_m of r_hedge; beta_m is the trailing ``window``-day OLS beta through the
    second-to-last trading day of the previous month (to t-1 for a reset at the month's last close); monthly reset;
    net cash at rf (excess-return form). Returns (daily P&L, hedge ratio per day)."""
    b = trailing_beta(r_long, r_hedge, window, gap=2)
    n = len(days)
    ws = np.full(n, np.nan)
    cur = np.nan
    for i in range(n):
        if i == 0 or days[i][:7] != days[i - 1][:7]:
            cur = b[i]
        ws[i] = cur
    wl = np.where(np.isfinite(ws), 1.0, np.nan)
    pnl, _ = ls_book(days, r_long, r_hedge, wl, ws, rf=rf, borrow=borrow, fee=fee, cost=cost)
    return pnl, ws


def _align_months(ms, y, fac_months, F) -> tuple[list[str], np.ndarray, np.ndarray]:
    ix = {m: i for i, m in enumerate(fac_months)}
    keep = [j for j, m in enumerate(ms) if m in ix]
    return [ms[j] for j in keep], np.asarray(y)[keep], np.asarray(F)[[ix[ms[j]] for j in keep]]


def hedged_alpha_test(days, r_long, r_hedge, rf, fac_months, F, fac_names, start: str = "2013-08-01", end: str = "2026-09-30",
                      min_n: int = 150, borrow: float = 0.003, fee: float = 0.0015, cost: float = 0.0002,
                      qmj_loading: Optional[float] = None, family_sharpes: Optional[Sequence[float]] = None,
                      label: str = "QUAL-SPY", n_boot: int = 2000) -> dict:
    """T-383: beta-hedged long/short spread, monthly alpha against the given factors (FF5 + UMD): NW t >= 2.0 over
    >= min_n months AND QMJ loading > 0.5 (None when no QMJ series) AND family-wide DSR > 0.95."""
    pnl, beta = hedged_spread(days, r_long, r_hedge, rf, 60, borrow, fee, cost)
    m = _window(days, start, end) & np.isfinite(pnl)
    d = [dd for dd, k in zip(days, m) if k]
    x = pnl[m]
    ms, y = sum_monthly(d, x) if len(d) else ([], np.array([]))
    ms, y, X = _align_months(ms, y, fac_months, F)
    n = len(y)
    out = {"label": label, "n": n, "n_months": n, "window_requested": f"{start[:7]}..{end[:7]}",
           "window_used": f"{ms[0]}..{ms[-1]}" if n else "empty", "mean_hedge_ratio": float(np.nanmean(beta[m])) if m.any() else None}
    qmj_row = ("QMJ loading > 0.5 (validity)", None if qmj_loading is None else bool(qmj_loading > 0.5), False,
               "a loading given without an interval cannot fail decisively")
    days_at_min_n = max(int(x.size), min_n * 21)                 # the family-DSR floor works on daily T; ~21 days a month
    n_min_reg = max(12, len(fac_names) + 3)
    if n < n_min_reg:
        # the monthly regression is not estimable, but the family DSR (daily P&L) is, so a decisive DSR failure still counts
        fd = family_dsr(x, family_sharpes) if (family_sharpes is not None and x.size > 1) else None
        rows = [(f"FF5+UMD alpha NW t >= 2.0 (not estimated: {n} months, the {len(fac_names) + 1}-coefficient regression needs {n_min_reg})",
                 None, False, ""), qmj_row,
                _dsr_row(f"family-wide DSR > {DSR_PASS}", None if fd is None else bool(fd["dsr"] > DSR_PASS), x, FAMILY_TRIALS,
                         _family_var(family_sharpes, days_at_min_n) if fd is not None else 0.0)]
        v, why = _decide(rows, n, min_n, "monthly observations")
        return {**out, "family": fd, "verdict": v,
                "reason": f"{label}: {n} usable months ({x.size} daily P&L observations); {_fmt_dsr(fd)} — {why}"}
    reg = ols_nw(y, X, NW_LAGS)
    a, t = float(reg["coef"][0]), float(reg["t"][0])
    lo, hi = alpha_boot_ci(y, X, 12, n_boot)
    fd = family_dsr(x, family_sharpes) if family_sharpes is not None else None
    rows = [_t_row("FF5+UMD alpha NW t >= 2.0", t, 2.0), qmj_row,
            _dsr_row(f"family-wide DSR > {DSR_PASS}", None if fd is None else bool(fd["dsr"] > DSR_PASS), x, FAMILY_TRIALS,
                     _family_var(family_sharpes, days_at_min_n) if fd is not None else 0.0)]
    v, why = _decide(rows, n, min_n, "monthly observations")
    loads = {nm: {"beta": float(reg["coef"][j + 1]), "t": float(reg["t"][j + 1])} for j, nm in enumerate(fac_names)}
    sub = [j for j, mm in enumerate(ms) if "2020-01" <= mm <= "2022-12"]
    sub_t = float(ols_nw(y[sub], X[sub], NW_LAGS)["t"][0]) if len(sub) > len(fac_names) + 5 else None
    roll = []
    for j in range(36, n + 1):
        roll.append(float(np.linalg.lstsq(np.column_stack([np.ones(36), X[j - 36:j]]), y[j - 36:j], rcond=None)[0][0]) * 12)
    qmj_s = "QMJ loading not available" if qmj_loading is None else f"QMJ loading {qmj_loading:.2f}"
    reason = (f"{label} hedged spread {out['window_used']}{_end_note(ms[-1], end)} (n={n} months, net of {borrow:.2%} borrow, {fee:.2%} fee, {cost * 1e4:.0f} bp/month): "
              f"alpha {a * 12:+.2%}/yr, NW t {t:+.2f} (needs >= 2.0), bootstrap 95% CI {lo * 12:+.2%} to {hi * 12:+.2%}; {qmj_s}; {_fmt_dsr(fd)} — {why}")
    return {**out, "alpha_ann": a * 12, "alpha_t": t, "alpha_ci_ann": [lo * 12, hi * 12], "loadings": loads, "r2": reg["r2"],
            "alpha_t_2020_2022": sub_t, "rolling36_alpha_ann": {"min": min(roll), "max": max(roll)} if roll else None,
            "qmj_loading": qmj_loading, "family": fd, "verdict": v, "reason": reason}


def size_spread_test(days, r_long, r_short, fac_months, F5, start: str = "2000-06-01", end: str = "2026-09-30", min_n: int = 6000,
                     borrow: float = 0.003, cost: float = 0.0005, family_sharpes: Optional[Sequence[float]] = None,
                     label: str = "IJR-IWM", n_boot: int = 10000) -> dict:
    """T-385: dollar-neutral long/short spread (equal legs reset monthly; fee differential already in NAV): lower 95%
    bound of the annualised mean > 0 over >= min_n days AND RMW loading significantly positive (monthly FF5, NW t >
    1.96) AND family-wide DSR > 0.95."""
    m = _window(days, start, end)
    d = [dd for dd, k in zip(days, m) if k]
    rl, rs = np.asarray(r_long)[m], np.asarray(r_short)[m]
    one = np.ones(len(d))
    pnl, nreb = ls_book(d, rl, rs, one, one, borrow=borrow, cost=cost)
    n = int(np.isfinite(pnl).sum())
    mean, lo, hi = stud_mean_ci(pnl, 20, n_boot)
    ms, y = sum_monthly(d, pnl)
    ms, y, X = _align_months(ms, y, fac_months, F5)
    t_rmw = b_rmw = None
    if len(y) > 24:
        reg = ols_nw(y, X, NW_LAGS)
        b_rmw, t_rmw = float(reg["coef"][1 + FF5.index("RMW")]), float(reg["t"][1 + FF5.index("RMW")])
    fd = family_dsr(pnl, family_sharpes) if family_sharpes is not None else None
    rows = [_ci_row("lower 95% bound of the annualised mean > 0", lo, hi, f"{hi * 252:+.2%}/yr"),
            _t_row("RMW loading significantly positive (NW t > 1.96)", t_rmw, 1.96, strict=True),
            _dsr_row(f"family-wide DSR > {DSR_PASS}", None if fd is None else bool(fd["dsr"] > DSR_PASS), pnl, FAMILY_TRIALS,
                     _family_var(family_sharpes, max(int(pnl.size), min_n)) if fd is not None else 0.0)]
    v, why = _decide(rows, n, min_n, "daily observations")
    june = np.array([dd[5:7] != "06" for dd in d])
    reg_m = _ann_means(d, pnl, [("2000-2006", "2000-01-01", "2006-12-31"), ("2014-2026", "2014-01-01", "2026-12-31")])
    roll = _rolling(pnl, 252 * 5)
    rmw_s = "RMW loading not estimated" if t_rmw is None else f"RMW loading {b_rmw:+.2f} (NW t {t_rmw:+.2f}, needs > 1.96)"
    reason = (f"{label} {d[0] if d else ''}..{d[-1] if d else ''} (n={n} days, {borrow:.1%} borrow, {cost * 1e4:.0f} bp per monthly reset): "
              f"annualised mean {mean * 252:+.2%}, 95% studentized CI {lo * 252:+.2%} to {hi * 252:+.2%}; {rmw_s}; {_fmt_dsr(fd)}; "
              f"June-excluded {np.mean(pnl[june]) * 252:+.2%}/yr — {why}")
    return {"label": label, "n": n, "n_days": n, "window_used": f"{d[0]}..{d[-1]}" if d else "empty", "mean_ann": mean * 252,
            "ci_ann": [lo * 252, hi * 252], "rmw_loading": b_rmw, "rmw_t": t_rmw, "n_months_regression": int(len(y)),
            "june_excluded_mean_ann": float(np.mean(pnl[june]) * 252), "regimes": reg_m, "rolling5y": roll, "n_resets": nreb,
            "family": fd, "verdict": v, "reason": reason, "_pnl": pnl, "_days": d}


def bab_spread_test(days, r_low, r_high, r_mkt, rate, start: str = "2011-06-01", end: str = "2026-09-30", min_n: int = 3500,
                    window: int = 60, fin_spread: float = 0.01, borrow: float = 0.005, cost: float = 0.0002, drift: float = 0.15,
                    gross_cap: float = 2.0, family_sharpes: Optional[Sequence[float]] = None, n_boot: int = 10000) -> dict:
    """T-387: long the low-beta leg levered to ex-ante beta 1, short the high-beta leg de-levered to beta 1 (trailing
    ``window``-day betas to t-1, gross capped at 2x), reset monthly and when the book's ex-ante beta drifts beyond
    +/-``drift``; net cash financed at ``rate`` + fin_spread (earned at rate - fin_spread, floored at 0); short borrow
    ``borrow``. Pass: lower 95% bound of the annualised mean > 0 over >= min_n days AND |full-sample beta to the
    market| < 0.1 AND family-wide DSR > 0.95. ``rate`` is the annual decimal rate known before each day.

    Any pair of positive betas can be hedged (when a beta is small the gross cap scales both legs, keeping the book's
    ex-ante beta at 0). A reset (scheduled or drift) that finds a beta <= 0 or missing cannot hedge the book, so it
    goes flat (P&L 0 while flat) rather than carrying the previous positions; a held book whose beta cannot be
    measured is flattened at once. Flat days stay in the sample."""
    r_low, r_high, r_mkt, rate = (np.asarray(v, dtype=float) for v in (r_low, r_high, r_mkt, rate))
    bL = trailing_beta(r_low, r_mkt, window, 2)
    bH = trailing_beta(r_high, r_mkt, window, 2)
    inwin = _window(days, start, end)
    fin = np.isfinite(bL) & np.isfinite(bH)
    hedge = inwin & fin & (bL > 0) & (bH > 0)
    k0 = int(np.argmax(inwin & fin)) if (inwin & fin).any() else len(days)
    ready = inwin & (np.arange(len(days)) >= k0)          # the rule can be evaluated from the first in-window day with both betas
    with np.errstate(divide="ignore", invalid="ignore"):
        wl = np.where(hedge, 1.0 / bL, np.nan)
        ws = np.where(hedge, 1.0 / bH, np.nan)
    scale = np.minimum(1.0, gross_cap / (wl + ws))
    wl, ws = wl * scale, ws * scale
    unhedgeable = ready & ~hedge
    wl[unhedgeable] = 0.0
    ws[unhedgeable] = 0.0

    def trig(i, L, S):
        if not fin[i]:
            return L != 0.0 or S != 0.0                   # neutrality cannot be checked: flatten
        return bool(abs(L * bL[i] - S * bH[i]) > drift)

    pnl, nreb, Lh, Sh = ls_book(days, r_low, r_high, wl, ws, rf=rate / 252.0, borrow=borrow, fin_spread=fin_spread, cost=cost,
                                trigger=trig, return_pos=True)
    live = inwin & np.isfinite(pnl)
    x = pnl[live]
    d = [dd for dd, k in zip(days, live) if k]
    n = int(x.size)
    flat = (Lh[live] == 0.0) & (Sh[live] == 0.0)
    n_flat = int(flat.sum())
    with np.errstate(invalid="ignore"):
        exante = (Lh * bL - Sh * bH)[live]
    max_exante = float(np.nanmax(np.abs(exante))) if np.isfinite(exante).any() else float("nan")
    mean, lo, hi = stud_mean_ci(x, 20, n_boot) if n >= 8 else (float("nan"),) * 3
    beta = float(ols_nw(x, r_mkt[live], 0)["coef"][1]) if n > 30 else float("nan")
    fd = family_dsr(x, family_sharpes) if (family_sharpes is not None and n > 1) else None
    beta_row = ("|ex-post beta to the market| < 0.1", bool(abs(beta) < 0.1) if np.isfinite(beta) else None, False, "")
    if np.isfinite(beta) and not beta_row[1]:
        se_b = float(ols_nw(x, r_mkt[live], 20)["se"][1])        # 95% NW (20-lag) interval of the beta, for rule 5 only
        b_lo, b_hi = beta - 1.96 * se_b, beta + 1.96 * se_b
        dec = bool(b_lo >= 0.1 or b_hi <= -0.1)
        beta_row = (beta_row[0], False, dec, f"95% NW interval of the beta {b_lo:+.3f} to {b_hi:+.3f} "
                                             f"{'lies wholly outside' if dec else 'overlaps'} (-0.1, 0.1)")
    rows = [_ci_row("lower 95% bound of the annualised mean net excess return > 0", lo, hi, f"{hi * 252:+.2%}/yr"), beta_row,
            _dsr_row(f"family-wide DSR > {DSR_PASS}", None if fd is None else bool(fd["dsr"] > DSR_PASS), x, FAMILY_TRIALS,
                     _family_var(family_sharpes, max(n, min_n)) if fd is not None else 0.0)]
    v, why = _decide(rows, n, min_n, "daily observations")
    roll = _rolling(x, 252 * 3) if n else None
    reason = (f"BAB spread {d[0] if d else ''}..{d[-1] if d else ''} (n={n} days, {nreb} resets, financing at bill + {fin_spread:.1%}, "
              f"{borrow:.1%} borrow, {cost * 1e4:.0f} bp per reset; {n_flat} flat days held in cash because a reset found a trailing "
              f"beta <= 0 or missing; held ex-ante beta within +/-{max_exante:.3f}): annualised mean {mean * 252:+.2%}, 95% studentized CI "
              f"{lo * 252:+.2%} to {hi * 252:+.2%}; ex-post beta {beta:+.3f} (needs |b| < 0.1); {_fmt_dsr(fd)} — {why}")
    return {"n": n, "n_days": n, "window_requested": f"{start[:7]}..{end[:7]}", "window_used": f"{d[0]}..{d[-1]}" if d else "empty",
            "mean_ann": mean * 252, "ci_ann": [lo * 252, hi * 252], "ex_post_beta": beta, "n_resets": nreb,
            "n_flat_days": n_flat, "max_abs_exante_beta_held": max_exante,
            "mean_long_notional": float(np.nanmean(wl[live])) if n else None, "mean_short_notional": float(np.nanmean(ws[live])) if n else None,
            "rolling3y": roll, "family": fd, "verdict": v, "reason": reason, "_pnl": x, "_days": d, "_flat": flat}


# --------------------------------------------------------------- monthly factor portfolios --

def _risk(F: np.ndarray, i: int, win: int = 36, min_n: int = 12):
    X = F[max(0, i - win): i]
    if len(X) < min_n:
        return None, None
    return X.std(axis=0, ddof=1), np.atleast_2d(np.cov(X, rowvar=False, ddof=1))


def _target(w: np.ndarray, cov: np.ndarray, target: float = 0.10, ppy: int = 12) -> np.ndarray:
    v = float(w @ cov @ w) * ppy
    return w * (target / math.sqrt(v)) if v > 0 else np.zeros_like(w)


# formation (a, b): compounded return over months i-a .. i-b; b = 2 is the one-month skip.
FORMATIONS = {"ts_12_1": ("ts", 12, 2), "ts_1": ("ts", 2, 2), "ts_3": ("ts", 4, 2), "ts_6": ("ts", 7, 2), "xs_12_1": ("xs", 12, 2)}


def momentum_portfolios(F: np.ndarray, start: int = 12, cost: float = 0.0005, target: float = 0.10) -> tuple[np.ndarray, dict]:
    """Monthly returns from row ``start`` of the static equal-risk portfolio (inverse trailing 36-month vol to t-1,
    scaled to ``target`` vol with the trailing covariance) and each FORMATIONS variant: 'ts' holds a factor only when
    its formation return is > 0 (equal risk across held factors); 'xs' is long factors above the cross-sectional
    median and short those below. Costs: ``cost`` per unit of notional traded."""
    T, K = F.shape
    static = []
    var = {k: [] for k in FORMATIONS}
    prev = {}
    for i in range(start, T):
        sig, cov = _risk(F, i)
        if sig is None or np.any(sig <= 0):
            raise ValueError("not enough history for the risk model at the start row")
        inv = 1.0 / sig
        ws = _target(inv, cov, target)
        static.append(float(ws @ F[i]) - cost * float(np.abs(ws - prev.get("static", ws)).sum()))
        prev["static"] = ws
        for name, (kind, a, b) in FORMATIONS.items():
            p = np.prod(1.0 + F[i - a: i - b + 1], axis=0) - 1.0
            if kind == "ts":
                raw = np.where(p > 0, inv, 0.0)
            else:
                med = np.median(p)
                raw = np.where(p > med, inv, np.where(p < med, -inv, 0.0))
            w = _target(raw, cov, target) if np.any(raw != 0) else np.zeros(K)
            var[name].append(float(w @ F[i]) - cost * float(np.abs(w - prev.get(name, w)).sum()))
            prev[name] = w
    return np.array(static), {k: np.array(v) for k, v in var.items()}


def factor_momentum_test(months: Sequence[str], F: np.ndarray, names: Sequence[str], min_n: int = 600, post_from: str = "2019-01",
                         n_boot: int = 5000, seed: int = 0) -> dict:
    """T-388: time-series factor momentum (12-1, one-month skip, equal risk across held factors, 10% target vol)
    minus the static equal-risk portfolio of the same factors: lower 95% bound of the annualised Sharpe difference
    > 0 (studentized block-12 bootstrap) over >= min_n months AND DSR > 0.95 of the timed-minus-static series with the
    5 formation variants counted AND PBO < 0.5 (CSCV, 8 blocks, on the variants' timed-minus-static series)."""
    F = np.asarray(F, dtype=float)
    start = 12
    static, var = momentum_portfolios(F, start)
    ms = list(months)[start:]
    n = len(static)
    diffs = {k: v - static for k, v in var.items()}
    obs, lo, hi = sharpe_diff_ci(var["ts_12_1"], static, 12, 12, n_boot, seed)
    trial_sr = [float(sharpe_ratio(diffs[k])) for k in FORMATIONS]
    dsr = float(deflated_sharpe_ratio(diffs["ts_12_1"], n_trials=len(FORMATIONS), trial_sharpes=trial_sr))
    pbo = pbo_cscv(np.column_stack([diffs[k] for k in FORMATIONS]), n_partitions=8)
    post = np.array([m >= post_from for m in ms])
    post_diff = float(sharpe_ratio(var["ts_12_1"][post], 12) - sharpe_ratio(static[post], 12)) if post.sum() > 12 else None
    rows = [_ci_row("lower 95% bound of the Sharpe difference > 0", lo, hi, f"{hi:+.2f}"),
            _dsr_row(f"DSR > {DSR_PASS} with all 5 variants counted", bool(dsr > DSR_PASS), diffs["ts_12_1"], len(FORMATIONS),
                     _trial_var(trial_sr, max(n, min_n))),
            ("PBO < 0.5", bool(pbo["pbo"] < 0.5), False, "PBO is a share of CSCV splits of one sample, with no interval")]
    v, why = _decide(rows, n, min_n, "monthly observations")
    s_t, s_s = float(sharpe_ratio(var["ts_12_1"], 12)), float(sharpe_ratio(static, 12))
    reason = (f"{'/'.join(names)} {ms[0]}..{ms[-1]} (n={n} months): timed 12-1 Sharpe {s_t:.2f} vs static {s_s:.2f}, "
              f"difference {obs:+.2f} (95% studentized CI {lo:+.2f} to {hi:+.2f}); DSR {dsr:.3f} over 5 variants "
              f"(annualised Sharpe of each timed-minus-static series: {', '.join(f'{k} {s * math.sqrt(12):+.2f}' for k, s in zip(FORMATIONS, trial_sr))}); "
              f"PBO {pbo['pbo']:.2f}; post-{post_from[:4]} difference {post_diff if post_diff is None else round(post_diff, 2)} (reported) — {why}")
    return {"n": n, "n_months": n, "window_used": f"{ms[0]}..{ms[-1]}", "factors": list(names), "sharpe_timed": s_t, "sharpe_static": s_s,
            "sharpe_diff": obs, "ci": [lo, hi], "dsr": dsr, "pbo": pbo["pbo"], "variant_diff_sharpes_ann": {k: s * math.sqrt(12) for k, s in zip(FORMATIONS, trial_sr)},
            "post_sharpe_diff": post_diff, "verdict": v, "reason": reason}


def _tilt(z: np.ndarray) -> np.ndarray:
    """Contrarian tilt: zero for |z| <= 1, then -0.5 * (z - sign z) capped at +/-50% (full tilt at |z| >= 2)."""
    z = np.asarray(z, dtype=float)
    t = -0.5 * np.clip(z - np.sign(z), -1.0, 1.0)
    return np.where(np.isfinite(z) & (np.abs(z) > 1.0), t, 0.0)


def contrarian_portfolios(F: np.ndarray, months: Sequence[str], W: int, tilt_mask: np.ndarray, start: int,
                          embargo: int = 4, z_min: int = 12, cost: float = 0.0005, target: float = 0.10, return_tilts: bool = False):
    """(static, timed) monthly returns from row ``start``. Quarterly rebalance (Jan/Apr/Jul/Oct, plus the first row).
    Static: inverse trailing 36-month vol weights to t-1 scaled to ``target`` vol. Timed: static raw weights times
    (1 + tilt) where tilt comes from the expanding-window z-score of the trailing W-month factor return measured
    ``embargo`` months before the rebalance month (signal at the end of the quarter before the last: one quarter of
    embargo), then scaled to ``target`` vol. Costs: ``cost`` per unit of notional traded. With ``return_tilts`` a third
    element maps each rebalance month to its tilt vector."""
    T, K = F.shape
    RW = np.full((T, K), np.nan)
    for j in range(W - 1, T):
        RW[j] = np.prod(1.0 + F[j - W + 1: j + 1], axis=0) - 1.0
    Z = np.full((T, K), np.nan)
    for j in range(W - 1 + z_min - 1, T):
        hist = RW[W - 1: j + 1]
        sd = hist.std(axis=0, ddof=1)
        Z[j] = np.where(sd > 0, (RW[j] - hist.mean(axis=0)) / np.where(sd > 0, sd, 1.0), np.nan)
    static, timed = [], []
    tilts: dict[str, np.ndarray] = {}
    ws = wt = None
    for i in range(start, T):
        cs = ct = 0.0
        if ws is None or int(months[i][5:7]) in (1, 4, 7, 10):
            sig, cov = _risk(F, i)
            if sig is None or np.any(sig <= 0):
                raise ValueError("not enough history for the risk model at the start row")
            raw = 1.0 / sig
            z = Z[i - embargo] if i - embargo >= 0 else np.full(K, np.nan)
            tilt = _tilt(z) * tilt_mask
            tilts[months[i]] = tilt
            nws, nwt = _target(raw, cov, target), _target(raw * (1.0 + tilt), cov, target)
            if ws is not None:
                cs, ct = cost * float(np.abs(nws - ws).sum()), cost * float(np.abs(nwt - wt).sum())
            ws, wt = nws, nwt
        static.append(float(ws @ F[i]) - cs)
        timed.append(float(wt @ F[i]) - ct)
    if return_tilts:
        return np.array(static), np.array(timed), tilts
    return np.array(static), np.array(timed)


def contrarian_timing_test(months: Sequence[str], F: np.ndarray, names: Sequence[str], start_month: str = "1968-01", min_n: int = 600,
                           n_boot: int = 5000, seed: int = 0, value_spread_timed: Optional[np.ndarray] = None) -> dict:
    """T-389: static equal-risk portfolio tilted by 60-month reversal z-scores (expanding window, one-quarter embargo,
    quarterly) minus the static portfolio: lower 95% bound of the annualised Sharpe difference > 0 (studentized
    block-12 bootstrap) AND DSR > 0.95 over the 5 pre-registered trials ({36, 60} x {all, ex-HML} + value spread).
    The value-spread trial needs the BE/ME block of 6_Portfolios_2x3; ``value_spread_timed`` is that trial's monthly
    timed return series aligned with months[start:]. Without it the DSR criterion is not implemented (None, so the
    verdict is at best inconclusive); the DSR over 5 trials with the variance of the 4 computable trials is reported."""
    F = np.asarray(F, dtype=float)
    months = list(months)
    start = next(i for i, m in enumerate(months) if m >= start_month)
    K = F.shape[1]
    all_mask = np.ones(K)
    ex_hml = np.array([0.0 if nm == "HML" else 1.0 for nm in names])
    trials = {}
    static = None
    for W in (60, 36):
        for setn, mask in (("all", all_mask), ("exHML", ex_hml)):
            s, t = contrarian_portfolios(F, months, W, mask, start)
            static = s
            trials[f"z{W}_{setn}"] = t
    ms = months[start:]
    n = len(static)
    have_vs = value_spread_timed is not None
    if have_vs:
        vst = np.asarray(value_spread_timed, dtype=float)
        if vst.shape != static.shape:
            raise ValueError(f"value_spread_timed must have {n} monthly returns aligned with {ms[0]}..{ms[-1]}")
        trials["value_spread"] = vst
    diffs = {k: v - static for k, v in trials.items()}
    obs, lo, hi = sharpe_diff_ci(trials["z60_all"], static, 12, 12, n_boot, seed)
    tsr = [float(sharpe_ratio(diffs[k])) for k in trials]
    var_tsr = float(np.var(tsr, ddof=1))
    dsr = float(deflated_sharpe_ratio(diffs["z60_all"], n_trials=5, var_trials_sr=var_tsr if var_tsr > 0 else None))
    dsr_name = f"DSR > {DSR_PASS} over 5 trials" + ("" if have_vs else " (value-spread trial not computable)")
    rows = [_ci_row("lower 95% bound of the Sharpe difference > 0", lo, hi, f"{hi:+.2f}"),
            _dsr_row(dsr_name, bool(dsr > DSR_PASS) if have_vs else None, diffs["z60_all"], 5, _trial_var(tsr, max(n, min_n)))]
    v, why = _decide(rows, n, min_n, "monthly observations")
    s_t, s_s = float(sharpe_ratio(trials["z60_all"], 12)), float(sharpe_ratio(static, 12))
    dsr_s = (f"DSR {dsr:.3f} over 5 trials (needs > {DSR_PASS})" if have_vs else
             f"DSR {dsr:.3f} over 5 trials not decided: value-spread trial not computable (6_Portfolios_2x3 BE/ME not archived), so only "
             f"4 of the 5 trial Sharpes are in the variance (reported only)")
    reason = (f"{'/'.join(names)} {ms[0]}..{ms[-1]} (n={n} months): 60-month z tilt Sharpe {s_t:.2f} vs static {s_s:.2f}, difference "
              f"{obs:+.2f} (95% studentized CI {lo:+.2f} to {hi:+.2f}); {dsr_s}; annualised Sharpe of each timed-minus-static series "
              f"{', '.join(f'{k} {s * math.sqrt(12):+.2f}' for k, s in zip(trials, tsr))} — {why}")
    return {"n": n, "n_months": n, "window_used": f"{ms[0]}..{ms[-1]}", "factors": list(names), "sharpe_timed": s_t, "sharpe_static": s_s,
            "sharpe_diff": obs, "ci": [lo, hi], "dsr": dsr, "dsr_decided": have_vs,
            "trial_diff_sharpes_ann": {k: s * math.sqrt(12) for k, s in zip(trials, tsr)},
            "value_spread_trial": "computed" if have_vs else "not computable (BE/ME of 6_Portfolios_2x3 not archived)",
            "verdict": v, "reason": reason}


def industry_alpha_test(months: Sequence[str], port: np.ndarray, rf: np.ndarray, F5: np.ndarray, start: str = "2009-01", end: str = "2026-09",
                        min_n: int = 200, label: str = "Smoke/Beer/Guns EW", split: tuple = ("1965-01", "2008-12")) -> dict:
    """T-397: monthly FF5 alpha of the portfolio's excess return (port - rf): NW t >= 2 over >= min_n months in
    [start, end]; CAPM alpha, bootstrap CI and the pre-period split alongside."""
    months = list(months)
    y_all = np.asarray(port, dtype=float) - np.asarray(rf, dtype=float)
    F5 = np.asarray(F5, dtype=float)
    m = np.array([start <= mm <= end for mm in months])
    n = int(m.sum())
    out = {"label": label, "n": n, "n_months": n, "window_requested": f"{start}..{end}"}
    if n < 24:
        # below the module's 24-month floor for a monthly FF5 regression (6 coefficients, NW 6 lags) nothing is estimated
        v, why = _decide([(f"FF5 alpha NW t >= 2 (not estimated: {n} months, the FF5 regression needs 24)", None, False, "")],
                         n, min_n, "monthly observations")
        return {**out, "verdict": v, "reason": f"{label}: {n} months — {why}"}
    y, X = y_all[m], F5[m]
    reg = ols_nw(y, X, NW_LAGS)
    capm = ols_nw(y, X[:, 0], NW_LAGS)
    a, t = float(reg["coef"][0]), float(reg["t"][0])
    lo, hi = alpha_boot_ci(y, X, 12, 2000)
    pm = np.array([split[0] <= mm <= split[1] for mm in months])
    pre = ols_nw(y_all[pm], F5[pm], NW_LAGS) if pm.sum() > 24 else None
    v, why = _decide([_t_row("FF5 alpha NW t >= 2", t, 2.0)], n, min_n, "monthly observations")
    used = [mm for mm, k in zip(months, m) if k]
    pre_s = f"; {split[0][:4]}-{split[1][:4]} FF5 alpha {float(pre['coef'][0]) * 12:+.2%}/yr (t {float(pre['t'][0]):+.2f})" if pre else ""
    reason = (f"{label} {used[0]}..{used[-1]}{_end_note(used[-1], end)} (n={n} months): FF5 alpha {a * 12:+.2%}/yr, NW t {t:+.2f} (needs >= 2), bootstrap 95% CI "
              f"{lo * 12:+.2%} to {hi * 12:+.2%}; CAPM alpha {float(capm['coef'][0]) * 12:+.2%}/yr (t {float(capm['t'][0]):+.2f}){pre_s} — {why}")
    return {**out, "window_used": f"{used[0]}..{used[-1]}", "alpha_ann": a * 12, "alpha_t": t, "alpha_ci_ann": [lo * 12, hi * 12],
            "capm_alpha_ann": float(capm["coef"][0]) * 12, "capm_t": float(capm["t"][0]),
            "loadings": {nm: float(reg["coef"][j + 1]) for j, nm in enumerate(FF5)},
            "pre_alpha_ann": float(pre["coef"][0]) * 12 if pre else None, "pre_alpha_t": float(pre["t"][0]) if pre else None,
            "verdict": v, "reason": reason}


def sort_spread_test(months: Sequence[str], spread: np.ndarray, fac_months: Sequence[str], F5: np.ndarray, start: str, end: str,
                     min_n: int, label: str, split_before: Optional[str] = None, block: int = 12, n_boot: int = 10000) -> dict:
    """T-445 / T-449: monthly long-short sort spread (zero investment): lower 95% studentized block bootstrap bound of
    the mean > 0 over >= min_n months in [start, end] AND monthly FF5 alpha NW t >= 2."""
    months = list(months)
    spread = np.asarray(spread, dtype=float)
    m = np.array([start <= mm <= end for mm in months])
    x = spread[m]
    used = [mm for mm, k in zip(months, m) if k]
    n = int(x.size)
    mean, lo, hi = stud_mean_ci(x, block, n_boot) if n >= 8 else (float("nan"),) * 3
    ms, y, X = _align_months(used, x, fac_months, F5)
    a = t = None
    if len(y) > 24:
        reg = ols_nw(y, X, NW_LAGS)
        a, t = float(reg["coef"][0]), float(reg["t"][0])
    rows = [_ci_row("lower 95% bound of the mean monthly spread > 0", lo, hi, f"{hi * 100:+.2f}%/month"),
            _t_row("FF5 alpha NW t >= 2", t, 2.0)]
    v, why = _decide(rows, n, min_n, "monthly observations")
    pre = None
    if split_before:
        pm = np.array([mm < split_before for mm in months])
        pre = float(spread[pm].mean()) if pm.sum() else None
    pre_s = f"; before {split_before} mean {pre * 100:+.2f}%/month" if pre is not None else ""
    a_s = "FF5 alpha not estimated" if t is None else f"FF5 alpha {a * 100:+.2f}%/month (NW t {t:+.2f}, needs >= 2)"
    reason = (f"{label} {used[0] if used else ''}..{used[-1] if used else ''}{_end_note(used[-1] if used else '', end)} (n={n} months): mean {mean * 100:+.2f}%/month, 95% studentized "
              f"block-{block} CI {lo * 100:+.2f} to {hi * 100:+.2f}; {a_s}{pre_s} — {why}")
    return {"label": label, "n": n, "n_months": n, "window_requested": f"{start}..{end}", "window_used": f"{used[0]}..{used[-1]}" if used else "empty",
            "mean_month": mean, "ci_month": [lo, hi], "alpha_month": a, "alpha_t": t, "n_months_regression": int(len(y)),
            "pre_mean_month": pre, "verdict": v, "reason": reason}


# ================================================================== archive loaders ==

_MEMO: dict = {}


def _memo(key, fn):
    if key not in _MEMO:
        if len(_MEMO) > 512:
            _MEMO.clear()
        _MEMO[key] = fn()
    return _MEMO[key]


def _bkey(archive, name: str) -> tuple:
    e = archive.get(name)
    return (name, e.sha256, e.rows)


def _etf_name(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def _missing(archive, names: Sequence[str]) -> list[str]:
    out = []
    for nm in names:
        try:
            archive.get(nm)
            next(iter(archive.load(nm)), None)
        except (KeyError, FileNotFoundError):
            out.append(nm)
    return out


def _values(archive, name: str) -> list[dict]:
    def go():
        cap = archive.get(name).created_at
        return [r["value"] for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _memo(("values",) + _bkey(archive, name), go)


def french_daily(archive, name: str, cols: Sequence[str], scale: float = 0.01) -> tuple[list[str], dict]:
    """(days, {col: decimal returns}) from a Ken French daily bundle (rows lacking a column are skipped)."""
    def go():
        vals = sorted((v for v in _values(archive, name) if all(v.get(c) is not None for c in cols)), key=lambda v: v["day"])
        return [v["day"] for v in vals], {c: np.array([float(v[c]) * scale for v in vals]) for c in cols}
    return _memo(("fd", tuple(cols), scale) + _bkey(archive, name), go)


def french_monthly_sorts(archive, name: str, cols: Sequence[str]) -> tuple[list[str], dict]:
    def go():
        vals = sorted((v for v in _values(archive, name) if all(v.get(c) is not None for c in cols)), key=lambda v: v["day"])
        return [v["day"][:7] for v in vals], {c: np.array([float(v[c]) / 100.0 for v in vals]) for c in cols}
    return _memo(("fm", tuple(cols)) + _bkey(archive, name), go)


def _etf(archive, sym: str):
    return _memo(("etf",) + _bkey(archive, _etf_name(sym)), lambda: load_series(archive, sym, adjusted=True))


def aligned_returns(*series) -> tuple[list[str], list[np.ndarray]]:
    """Daily simple returns of several (days, closes) series on their common days."""
    common = sorted(set.intersection(*(set(d) for d, _ in series)))
    out = []
    for d, c in series:
        ix = {x: i for i, x in enumerate(d)}
        p = np.array([c[ix[x]] for x in common], dtype=float)
        out.append(p[1:] / p[:-1] - 1.0)
    return common[1:], out


def ff_monthly(archive) -> tuple[list[str], dict]:
    """Monthly FF5 + UMD + RF compounded from daily (decimal), on the days both daily files cover."""
    def go():
        days, f = french_daily(archive, "french-ff5-daily", FF5 + ["RF"])
        md, mo = french_daily(archive, "french-momentum-daily", ["Mom"])
        mom = dict(zip(md, mo["Mom"]))
        keep = [i for i, d in enumerate(days) if d in mom]
        dd = [days[i] for i in keep]
        cols = {c: f[c][keep] for c in FF5 + ["RF"]}
        cols["UMD"] = np.array([mom[d] for d in dd])
        out, months = {}, []
        for c, r in cols.items():
            months, out[c] = compound_monthly(dd, r)
        return months, out
    return _memo(("ffm",) + _bkey(archive, "french-ff5-daily") + _bkey(archive, "french-momentum-daily"), go)


def _rf_daily(archive, days) -> np.ndarray:
    fd, f = french_daily(archive, "french-ff5-daily", ["RF"])
    m = dict(zip(fd, f["RF"]))
    return np.array([m.get(d, np.nan) for d in days])


def _bill_rate(archive, days) -> np.ndarray:
    """Annual decimal 3-month bill rate known before each day: DTB3 (discount basis) converted to bond-equivalent
    yield 365 d / (360 - 91 d), the basis of the DGS3MO series the claim names; last value strictly before the day."""
    b = index_closes(archive.load("fred-DTB3"))
    ks = sorted(b)
    vals = np.array([b[k] for k in ks]) / 100.0
    bey = 365.0 * vals / (360.0 - 91.0 * vals)
    pos = np.searchsorted(np.array(ks), np.array(days), side="left") - 1
    return np.where(pos >= 0, bey[np.maximum(pos, 0)], np.nan)


def _bab_daily(archive) -> tuple[list[str], np.ndarray]:
    def go():
        vals = sorted((v for v in _values(archive, "aqr-bab-daily") if v.get("bab_usa") is not None), key=lambda v: v["day"])
        return [v["day"] for v in vals], np.array([float(v["bab_usa"]) for v in vals])
    return _memo(("bab",) + _bkey(archive, "aqr-bab-daily"), go)


def _ff_matrix(fm: dict, names: Sequence[str]) -> np.ndarray:
    return np.column_stack([fm[c] for c in names])


# --------------------------------------------------------------- family-wide DSR --

def _dollar_neutral(archive, long: str, short: str, start: str, end: str = "2026-09-30", borrow: float = 0.003, cost: float = 0.0005,
                    fee: float = 0.0) -> tuple[list[str], np.ndarray]:
    days, (rl, rs) = aligned_returns(_etf(archive, long), _etf(archive, short))
    m = _window(days, start, end)
    d = [x for x, k in zip(days, m) if k]
    one = np.ones(len(d))
    pnl, _ = ls_book(d, rl[m], rs[m], one, one, borrow=borrow, cost=cost, fee=fee)
    return d, pnl


def _qual_book(archive, long: str = "QUAL"):
    """(days, long returns, SPY returns, daily RF) on common days up to the last Ken French day."""
    days, (rq, rs) = aligned_returns(_etf(archive, long), _etf(archive, "SPY"))
    ff_last = french_daily(archive, "french-ff5-daily", ["RF"])[0][-1]
    m = np.array([d <= ff_last for d in days])
    days = [d for d, k in zip(days, m) if k]
    rq, rs = rq[m], rs[m]
    return days, rq, rs, _rf_daily(archive, days)


def _bab_inputs(archive):
    days, (rl, rh, rm) = aligned_returns(_etf(archive, "SPLV"), _etf(archive, "SPHB"), _etf(archive, "SPY"))
    return days, rl, rh, rm, _bill_rate(archive, days)


def _family_members(archive) -> dict[str, Callable[[], np.ndarray]]:
    def factor(name, col, start, end="2026-09-30"):
        def f():
            days, c = french_daily(archive, name, [col])
            return c[col][_window(days, start, end)]
        return f

    def qual(sym):
        def f():
            days, rq, rs, rf = _qual_book(archive, long=sym)
            pnl, _ = hedged_spread(days, rq, rs, rf, 60, 0.003, 0.0015 if sym == "QUAL" else 0.0, 0.0002)
            return pnl[_window(days, "2013-08-01" if sym == "QUAL" else "2017-01-01", "2026-09-30")]
        return f

    def bab_etf():
        days, rl, rh, rm, rate = _bab_inputs(archive)
        return bab_spread_test(days, rl, rh, rm, rate, n_boot=8)["_pnl"]

    def aqr():
        days, x = _bab_daily(archive)
        return x[_window(days, "2011-06-01", "2026-09-30")]

    return {
        "HML 1993-2026 (T-382)": factor("french-ff3-daily", "HML", "1993-01-01"),
        "IWD-IWF net spread (T-382 implementation)": lambda: _dollar_neutral(archive, "IWD", "IWF", "2000-06-01", borrow=0.005, fee=0.0035)[1],
        "QUAL beta-hedged vs SPY (T-383)": qual("QUAL"),
        "IJR-IWM dollar-neutral (T-385)": lambda: _dollar_neutral(archive, "IJR", "IWM", "2000-06-01")[1],
        "IWM-SPY raw size (T-385 variant)": lambda: _dollar_neutral(archive, "IWM", "SPY", "2000-06-01")[1],
        "SMB 2000-2026 (T-385 variant)": factor("french-ff3-daily", "SMB", "2000-06-01"),
        "RMW 2013-2026 (T-386)": factor("french-ff5-daily", "RMW", "2013-07-01"),
        "COWZ beta-hedged vs SPY (T-386 implementation)": qual("COWZ"),
        "SPLV/SPHB beta-neutral (T-387)": bab_etf,
        "AQR BAB 2011-2026 (T-387 reference)": aqr,
        "USMV-SPY (low-vol)": lambda: _dollar_neutral(archive, "USMV", "SPY", "2011-11-01")[1],
        "SPLV-SPY (low-vol)": lambda: _dollar_neutral(archive, "SPLV", "SPY", "2011-06-01")[1],
        "UMD 1993-2026 (T-446)": factor("french-momentum-daily", "Mom", "1993-01-01"),
        "CMA 2008-2026 (T-447)": factor("french-ff5-daily", "CMA", "2008-07-01"),
    }


FAMILY_BUNDLES = ["french-ff3-daily", "french-ff5-daily", "french-momentum-daily", "aqr-bab-daily", "fred-DTB3"] + \
    [_etf_name(s) for s in ("IWD", "IWF", "QUAL", "SPY", "IJR", "IWM", "COWZ", "SPLV", "SPHB", "USMV")]
FAMILY = list(_family_members(None).keys())


def family_sharpes(archive) -> dict[str, float]:
    """Per-day Sharpe of each family variant the archive supports (variants whose inputs are missing are skipped)."""
    present = [b for b in FAMILY_BUNDLES if not _missing(archive, [b])]
    key = ("family",) + tuple(_bkey(archive, b) for b in present)

    def go():
        out = {}
        for name, fn in _family_members(archive).items():
            try:
                x = np.asarray(fn(), dtype=float)
            except (KeyError, FileNotFoundError, ValueError, IndexError):
                continue
            x = x[np.isfinite(x)]
            if x.size > 250:
                out[name] = float(sharpe_ratio(x))
        return out
    return _memo(key, go)


# ===================================================================== harnesses ==

def _harness(bundles: Sequence[str]):
    def deco(fn):
        def h(archive):
            miss = _missing(archive, bundles)
            if miss:
                return ({"missing_bundles": miss}, 0, "inconclusive",
                        f"cannot test: bundles missing from the archive: {', '.join(miss)} — not implemented: every criterion (data missing)")
            rep = fn(archive)
            stat = {k: v for k, v in rep.items() if not k.startswith("_")}
            return stat, int(rep.get("n") or 0), rep["verdict"], rep["reason"]
        h.__doc__ = fn.__doc__
        h.__name__ = fn.__name__
        h.bundles = list(bundles)
        return h
    return deco


def _vintage(archive, *names) -> dict:
    return {nm: archive.get(nm).created_at for nm in names}


@_harness(["french-ff3-daily", _etf_name("IWD"), _etf_name("IWF")])
def fact_value_hml(archive) -> dict:
    """T-382: FF HML daily, 1993-01 to 2026-09: lower 95% studentized block-20 bootstrap bound (10,000 resamples) of the
    annualised mean > 0 over >= 8000 days AND family-wide DSR > 0.95. Diagnostics: IWD-IWF net spread (0.35% fees,
    0.5% borrow, 5 bp per monthly reset), capture ratio (slope on HML), rolling 10-year means, three regimes."""
    days, f = french_daily(archive, "french-ff3-daily", ["HML"])
    fam = family_sharpes(archive)
    rep = factor_mean_test(days, f["HML"], "1993-01-01", "2026-09-30", 8000, list(fam.values()), "HML",
                           [("1993-2006", "1993-01-01", "2006-12-31"), ("2007-2020", "2007-01-01", "2020-12-31"), ("2021-2026", "2021-01-01", "2026-12-31")], 10)
    d, sp = _dollar_neutral(archive, "IWD", "IWF", "2000-06-01", borrow=0.005, fee=0.0035)
    hm = dict(zip(days, f["HML"]))
    ok = [i for i, x in enumerate(d) if x in hm and np.isfinite(sp[i])]
    cap = float(ols_nw(sp[ok], np.array([hm[d[i]] for i in ok]), 0)["coef"][1]) if len(ok) > 100 else None
    diag = {"iwd_iwf_net_mean_ann": float(np.nanmean(sp) * 252), "iwd_iwf_capture_ratio": cap, "iwd_iwf_window": f"{d[0]}..{d[-1]}",
            "vintage": _vintage(archive, "french-ff3-daily")}
    head, tail = rep["reason"].split(" — ", 1)
    cap_s = "n/a" if cap is None else f"{cap:.2f}"
    rep["reason"] = f"{head}; diagnostic IWD-IWF net {diag['iwd_iwf_net_mean_ann']:+.2%}/yr, capture ratio {cap_s} — {tail}"
    return {**rep, **diag, "family_members": fam}


@_harness(["french-ff5-daily", "french-momentum-daily", _etf_name("QUAL"), _etf_name("SPY")])
def fact_quality_qual(archive) -> dict:
    """T-383: long QUAL / short SPY x trailing 60-day beta (to t-1, monthly reset), net of the 0.15% fee the claim lists,
    0.3% SPY borrow and 2 bp/month: monthly FF5+UMD alpha NW t (6 lags) >= 2.0 over >= 150 months AND QMJ loading > 0.5
    (AQR QMJ not archived: not implemented) AND family-wide DSR > 0.95. Window 2013-08 to 2026-09; the first month with
    a 60-day beta is 2013-11."""
    days, rq, rs, rf = _qual_book(archive)
    fm_months, fm = ff_monthly(archive)
    names = FF5 + ["UMD"]
    X = _ff_matrix(fm, names)
    fam = family_sharpes(archive)
    rep = hedged_alpha_test(days, rq, rs, rf, fm_months, X, names, family_sharpes=list(fam.values()))
    alt = hedged_alpha_test(days, rq, rs, rf, fm_months, X, names, fee=0.0, n_boot=10)
    rep["alpha_t_fee_in_nav_only"] = alt.get("alpha_t")
    rep["alpha_ann_fee_in_nav_only"] = alt.get("alpha_ann")
    rep["missing_for_validity"] = "AQR Quality-Minus-Junk-Factors-Daily (QMJ) is not in the archive"
    head, tail = rep["reason"].split(" — ", 1)
    extra = f"; without re-deducting the in-NAV fee alpha t {alt['alpha_t']:+.2f}" if alt.get("alpha_t") is not None else ""
    rep["reason"] = f"{head}{extra}; QMJ validity needs the AQR QMJ series (not archived) — {tail}"
    return {**rep, "family_members": fam, "vintage": _vintage(archive, "french-ff5-daily", "french-momentum-daily")}


@_harness(["french-ff5-daily", "french-momentum-daily", _etf_name("IJR"), _etf_name("IWM")])
def fact_size_ijr_iwm(archive) -> dict:
    """T-385: dollar-neutral IJR minus IWM (equal legs reset monthly; fees in NAV; 0.3% IWM borrow; 5 bp per reset),
    2000-06 to 2026-09: lower 95% studentized block-20 bound of the annualised mean > 0 over >= 6000 days AND RMW
    loading significantly positive (monthly FF5, NW t > 1.96) AND family-wide DSR > 0.95."""
    days, (rl, rs) = aligned_returns(_etf(archive, "IJR"), _etf(archive, "IWM"))
    fm_months, fm = ff_monthly(archive)
    fam = family_sharpes(archive)
    rep = size_spread_test(days, rl, rs, fm_months, _ff_matrix(fm, FF5), family_sharpes=list(fam.values()))
    return {**rep, "family_members": fam}


@_harness(["french-ff5-daily", "french-momentum-daily", _etf_name("COWZ"), _etf_name("SPY"), _etf_name("XLE"), _etf_name("XLK")])
def fact_profitability_rmw(archive) -> dict:
    """T-386: FF RMW daily, 2013-07 to 2026-09: lower 95% studentized block-20 bound of the annualised mean > 0 over
    >= 3000 days AND family-wide DSR > 0.95. Diagnostic: COWZ beta-hedged vs SPY monthly FF5 alpha with XLE and XLK
    excess-return controls."""
    days, f = french_daily(archive, "french-ff5-daily", ["RMW"])
    fam = family_sharpes(archive)
    rep = factor_mean_test(days, f["RMW"], "2013-07-01", "2026-09-30", 3000, list(fam.values()), "RMW",
                           [("2013-2019", "2013-07-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")], 5)
    diag = {}
    try:
        cd, rc, rs, rf = _qual_book(archive, long="COWZ")
        pnl, _ = hedged_spread(cd, rc, rs, rf, 60, 0.003, 0.0, 0.0002)
        ms, y = sum_monthly(cd, pnl)
        fm_months, fm = ff_monthly(archive)
        sect = {}
        for s in ("XLE", "XLK"):
            sd_, (rx,) = aligned_returns(_etf(archive, s))
            sm, sr = compound_monthly(sd_, rx)
            sect[s] = dict(zip(sm, sr))
        rfm = dict(zip(fm_months, fm["RF"]))
        keep = [j for j, mm in enumerate(ms) if mm in rfm and all(mm in sect[s] for s in sect)]
        fi = {mm: i for i, mm in enumerate(fm_months)}
        X = np.column_stack([_ff_matrix(fm, FF5)[[fi[ms[j]] for j in keep]],
                             [sect["XLE"][ms[j]] - rfm[ms[j]] for j in keep], [sect["XLK"][ms[j]] - rfm[ms[j]] for j in keep]])
        reg = ols_nw(y[keep], X, NW_LAGS)
        diag = {"cowz_alpha_ann": float(reg["coef"][0]) * 12, "cowz_alpha_t": float(reg["t"][0]), "cowz_xle_loading": float(reg["coef"][6]),
                "cowz_xle_t": float(reg["t"][6]), "cowz_rmw_loading": float(reg["coef"][4]), "cowz_months": len(keep)}
    except (KeyError, ValueError, IndexError):
        diag = {"cowz_diagnostic": "not computed"}
    if "cowz_alpha_t" in diag:
        head, tail = rep["reason"].split(" — ", 1)
        rep["reason"] = (f"{head}; diagnostic COWZ hedged FF5+XLE+XLK alpha {diag['cowz_alpha_ann']:+.2%}/yr (t {diag['cowz_alpha_t']:+.2f}), "
                         f"XLE loading {diag['cowz_xle_loading']:+.2f} — {tail}")
    return {**rep, **diag, "family_members": fam, "vintage": _vintage(archive, "french-ff5-daily")}


@_harness(["fred-DTB3", "french-ff5-daily", "french-momentum-daily", "aqr-bab-daily", _etf_name("SPLV"), _etf_name("SPHB"), _etf_name("SPY")])
def fact_bab_etf(archive) -> dict:
    """T-387: SPLV levered / SPHB de-levered to ex-ante beta 1 (trailing 60-day betas to t-1; monthly reset and when the
    book's ex-ante beta drifts beyond +/-0.15; gross <= 2x), net cash at the 3-month bill (DTB3 on a bond-equivalent
    basis, standing in for DGS3MO) + 1.0%, 0.5% borrow, 2 bp per reset; 2011-06 to 2026-09: lower 95% studentized
    block-20 bound of the annualised mean > 0 over >= 3500 days AND |ex-post beta to SPY| < 0.1 AND family-wide DSR
    > 0.95. A reset that finds a trailing beta <= 0 (or missing) holds the book flat in cash until a reset can hedge it.
    Diagnostics: monthly FF5 alpha, correlation with AQR BAB since 2014."""
    days, rl, rh, rm, rate = _bab_inputs(archive)
    fam = family_sharpes(archive)
    rep = bab_spread_test(days, rl, rh, rm, rate, family_sharpes=list(fam.values()))
    ms, y = sum_monthly(rep["_days"], rep["_pnl"])
    fm_months, fm = ff_monthly(archive)
    ms2, y2, X = _align_months(ms, y, fm_months, _ff_matrix(fm, FF5))
    reg = ols_nw(y2, X, NW_LAGS)
    bd, bx = _bab_daily(archive)
    bm, br = compound_monthly(bd, bx)
    bmap = dict(zip(bm, br))
    k = [j for j, mm in enumerate(ms) if mm >= "2014-01" and mm in bmap]
    corr = float(np.corrcoef(y[k], [bmap[ms[j]] for j in k])[0, 1]) if len(k) > 12 else None
    rep.update({"ff5_alpha_ann": float(reg["coef"][0]) * 12, "ff5_alpha_t": float(reg["t"][0]), "corr_aqr_bab_post2014": corr,
                "rate_basis": "DTB3 converted to bond-equivalent yield (DGS3MO is not archived)"})
    head, tail = rep["reason"].split(" — ", 1)
    rep["reason"] = f"{head}; diagnostic FF5 alpha {rep['ff5_alpha_ann']:+.2%}/yr (t {rep['ff5_alpha_t']:+.2f}), corr with AQR BAB since 2014 {'n/a' if corr is None else f'{corr:.2f}'} — {tail}"
    return {**rep, "family_members": fam}


def _factor_momentum_inputs(archive):
    fm_months, fm = ff_monthly(archive)
    bd, bx = _bab_daily(archive)
    bm, br = compound_monthly(bd, bx)
    bmap = dict(zip(bm, br))
    keep = [i for i, m in enumerate(fm_months) if m in bmap]
    months = [fm_months[i] for i in keep]
    names = ["HML", "SMB", "RMW", "CMA", "UMD", "BAB"]
    F = np.column_stack([fm[c][keep] for c in names[:5]] + [np.array([bmap[m] for m in months])])
    return months, F, names


@_harness(["french-ff5-daily", "french-momentum-daily", "aqr-bab-daily"])
def fact_factor_momentum(archive) -> dict:
    """T-388: HML, SMB, RMW, CMA, UMD (Ken French) and BAB (AQR), monthly compounded from daily, 1964-2026: hold each
    factor only after a positive 12-1 return (one-month skip), equal risk across held factors (inverse 36-month vol to
    t-1), 10% target vol, 5 bp per unit traded; vs the static equal-risk portfolio. Pass: lower 95% bound of the
    Sharpe difference > 0 over >= 600 months AND DSR > 0.95 with 5 variants (1-, 3-, 6-, 12-1 month time-series and
    12-1 cross-sectional) AND PBO < 0.5; post-2019 difference reported."""
    months, F, names = _factor_momentum_inputs(archive)
    rep = factor_momentum_test(months, F, names)
    rep["note"] = "AQR BAB is revised by AQR (not point in time); the ETF-rotation holdout is not run (factor ETFs too short / not archived)"
    return {**rep, "vintage": _vintage(archive, "french-ff5-daily", "french-momentum-daily", "aqr-bab-daily")}


@_harness(["french-ff5-daily", "french-momentum-daily"])
def fact_contrarian_timing(archive) -> dict:
    """T-389: static equal-risk FF5+UMD portfolio (Mkt-RF, SMB, HML, RMW, CMA, UMD; inverse 36-month vol to t-1; 10%
    target vol; quarterly) tilted by expanding-window z-scores of trailing 60-month factor returns (one-quarter
    embargo; overweight z < -1, underweight z > +1, tilt capped at +/-50%; 5 bp per unit traded), 1968-2026. Pass:
    lower 95% bound of the Sharpe difference > 0 AND DSR > 0.95 over 5 trials. The value-spread trial (5th of 5) needs
    the BE/ME block of 6_Portfolios_2x3, which is not archived, so the DSR criterion is not implemented and the verdict
    is at best inconclusive."""
    fm_months, fm = ff_monthly(archive)
    names = FF5 + ["UMD"]
    rep = contrarian_timing_test(fm_months, _ff_matrix(fm, names), names)
    return {**rep, "vintage": _vintage(archive, "french-ff5-daily", "french-momentum-daily")}


@_harness(["french-industry49-daily", "french-ff5-daily", "french-momentum-daily"])
def fact_sin_alpha(archive) -> dict:
    """T-397: equal-weight monthly average of the Ken French Smoke, Beer and Guns industry returns (value-weighted
    within industry; the archive holds the 49-industry daily file, whose Smoke/Beer/Guns match the 48-industry
    definitions), monthly compounded from daily, minus RF, on monthly FF5, 2009-01 to 2026-09: FF5 alpha NW t >= 2
    over >= 200 months."""
    days, ind = french_daily(archive, "french-industry49-daily", ["Smoke", "Beer", "Guns"])
    mi = {}
    for c in ("Smoke", "Beer", "Guns"):
        mm, r = compound_monthly(days, ind[c])
        mi[c] = dict(zip(mm, r))
    fm_months, fm = ff_monthly(archive)
    keep = [i for i, m in enumerate(fm_months) if all(m in mi[c] for c in mi)]
    months = [fm_months[i] for i in keep]
    port = np.array([np.mean([mi[c][m] for c in mi]) for m in months])
    rep = industry_alpha_test(months, port, fm["RF"][keep], _ff_matrix(fm, FF5)[keep])
    return {**rep, "vintage": _vintage(archive, "french-industry49-daily", "french-ff5-daily")}


@_harness(["french-accruals-monthly", "french-ff5-daily", "french-momentum-daily"])
def fact_accruals(archive) -> dict:
    """T-445: Ken French value-weighted accruals quintiles, Lo 20 minus Hi 20, 1996-07 to 2026-09: lower 95%
    studentized block-12 bound of the mean monthly spread > 0 over >= 300 months AND monthly FF5 alpha NW t >= 2."""
    months, s = french_monthly_sorts(archive, "french-accruals-monthly", ["Lo 20", "Hi 20"])
    fm_months, fm = ff_monthly(archive)
    rep = sort_spread_test(months, s["Lo 20"] - s["Hi 20"], fm_months, _ff_matrix(fm, FF5), "1996-07", "2026-09", 300,
                           "Accruals Lo20-Hi20", split_before="1996-07")
    return {**rep, "vintage": _vintage(archive, "french-accruals-monthly")}


@_harness(["french-momentum-daily", "french-ff3-daily", "french-ff5-daily"])
def fact_momentum_umd(archive) -> dict:
    """T-446: FF UMD (Mom) daily, 1993-01 to 2026-09: lower 95% studentized block-20 bound (10,000 resamples) of the
    annualised mean > 0 over >= 8000 days AND family-wide DSR > 0.95. MTUM diagnostic not run (MTUM not archived)."""
    days, f = french_daily(archive, "french-momentum-daily", ["Mom"])
    fam = family_sharpes(archive)
    rep = factor_mean_test(days, f["Mom"], "1993-01-01", "2026-09-30", 8000, list(fam.values()), "UMD",
                           [("1993-2008", "1993-01-01", "2008-12-31"), ("2009-2026", "2009-01-01", "2026-12-31")], 10)
    return {**rep, "family_members": fam, "note": "MTUM diagnostic not run: MTUM is not archived", "vintage": _vintage(archive, "french-momentum-daily")}


@_harness(["french-ff5-daily", "french-ff3-daily", "french-momentum-daily"])
def fact_investment_cma(archive) -> dict:
    """T-447: FF CMA daily, 2008-07 to 2026-09: lower 95% studentized block-20 bound of the annualised mean > 0 over
    >= 4000 days AND family-wide DSR > 0.95; rolling 5-year means reported. INV-quintile variant not run (not archived)."""
    days, f = french_daily(archive, "french-ff5-daily", ["CMA"])
    fam = family_sharpes(archive)
    rep = factor_mean_test(days, f["CMA"], "2008-07-01", "2026-09-30", 4000, list(fam.values()), "CMA",
                           [("2008-2019", "2008-07-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")], 5)
    return {**rep, "family_members": fam, "note": "Portfolios_Formed_on_INV variant not run: not archived", "vintage": _vintage(archive, "french-ff5-daily")}


@_harness(["french-net-issuance-monthly", "french-ff5-daily", "french-momentum-daily", _etf_name("PKW"), _etf_name("SPY")])
def fact_net_issuance(archive) -> dict:
    """T-449: Ken French net-share-issues portfolios, repurchasers ('< 0') minus the highest-issuance quintile ('Hi 20'),
    value-weighted, 2008-05 to 2026-09: lower 95% studentized block-12 bound of the mean monthly spread > 0 over >= 200
    months AND monthly FF5 alpha NW t >= 2 (beyond CMA). Diagnostic: PKW minus SPY monthly mean."""
    months, s = french_monthly_sorts(archive, "french-net-issuance-monthly", ["< 0", "Hi 20"])
    fm_months, fm = ff_monthly(archive)
    rep = sort_spread_test(months, s["< 0"] - s["Hi 20"], fm_months, _ff_matrix(fm, FF5), "2008-05", "2026-09", 200,
                           "Net issuance (<0)-Hi20", split_before="2008-05")
    pd_, (rp, rs) = aligned_returns(_etf(archive, "PKW"), _etf(archive, "SPY"))
    pm, pr = compound_monthly(pd_, rp)
    _, sr = compound_monthly(pd_, rs)
    rep["pkw_minus_spy_month"] = float(np.mean(pr - sr))
    rep["pkw_window"] = f"{pm[0]}..{pm[-1]}"
    head, tail = rep["reason"].split(" — ", 1)
    rep["reason"] = f"{head}; diagnostic PKW-SPY {rep['pkw_minus_spy_month'] * 100:+.2f}%/month {rep['pkw_window']} — {tail}"
    return {**rep, "vintage": _vintage(archive, "french-net-issuance-monthly")}


HARNESSES = {
    "fact_value_hml": fact_value_hml,
    "fact_quality_qual": fact_quality_qual,
    "fact_size_ijr_iwm": fact_size_ijr_iwm,
    "fact_profitability_rmw": fact_profitability_rmw,
    "fact_bab_etf": fact_bab_etf,
    "fact_factor_momentum": fact_factor_momentum,
    "fact_contrarian_timing": fact_contrarian_timing,
    "fact_sin_alpha": fact_sin_alpha,
    "fact_accruals": fact_accruals,
    "fact_momentum_umd": fact_momentum_umd,
    "fact_investment_cma": fact_investment_cma,
    "fact_net_issuance": fact_net_issuance,
}

THEORY_MAP = {
    "T-382": "fact_value_hml",
    "T-383": "fact_quality_qual",
    "T-385": "fact_size_ijr_iwm",
    "T-386": "fact_profitability_rmw",
    "T-387": "fact_bab_etf",
    "T-388": "fact_factor_momentum",
    "T-389": "fact_contrarian_timing",
    "T-397": "fact_sin_alpha",
    "T-445": "fact_accruals",
    "T-446": "fact_momentum_umd",
    "T-447": "fact_investment_cma",
    "T-449": "fact_net_issuance",
}
