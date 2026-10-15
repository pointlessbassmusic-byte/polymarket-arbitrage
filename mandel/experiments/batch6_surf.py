"""
Batch 6a, group ``surf``: surface and index relative value.
===========================================================

Ten options-library claims, each tested on its own claim, trial.pass and trial.min_n as worded:

  * T-159  VIX/VIX3M regime filter: within each VIX tercile, the 21-day SPY variance risk premium is higher on contango days
           (VIX/VIX3M < 0.95) than on backwardation days (> 1.05). Data-only; a MODEL-PRICED short strangle is reported as
           the trial's secondary.
  * T-227  SKEW and realised left tails: windows starting with SKEW above its trailing 80th percentile do NOT carry 1 pp or
           more extra 21-day ^GSPC returns below -2 VIX-implied sigma, against windows starting below its 20th percentile.
  * T-228  The SKEW-implied 2-sigma probability (white-paper mapping 0.0228 + 0.0270 (SKEW - 100) / 10) exceeds the realised
           frequency of 21-day -2 VIX-sigma drops by more than 2 pp on average.
  * T-229  MODEL-PRICED 30-DTE 25d/10d SPX put spread: payoff / debit when bought in cheap-SKEW months against every month.
  * T-237  VXN - VIX 60-day z-score extremes: s [(VXN - VIX) - (RV_QQQ - RV_SPY)] over the next 21 days is positive.
  * T-239  MODEL-PRICED rolling 25-delta VIX call overlay (Black-76 on a VIX3M/VIX forward, VVIX as IV) on a 1%/yr budget
           cuts SPY's maximum drawdown by more than 25%.
  * T-240  VVIX exceeds the realised 21-day vol of daily log changes in spot VIX in more than 70% of non-overlapping months.
  * T-249  The 1-to-3-month forward variance premium fraction exceeds the spot 30-day premium fraction.
  * T-511  SPY Friday-to-Monday close variance is below 1.5 x the weekday single-night variance (the data-only part).
  * T-538  COR1M exceeds the realised average pairwise correlation of the index constituents (only a sector-SPDR proxy is
           archived; see the harness for why that caps the verdict).

Conventions (house rules)
  * Point in time. A decision at a close uses index closes of that day (CBOE indices are final at the close) and the prior
    FRED DTB3 print (published the next day), converted from the 91-day discount yield to a continuous rate
    r = -ln(1 - d/100 * 91/360) / (91/365). Forward windows start with the next day's return. Rows that were not yet
    available when their bundle was captured are dropped. Trailing percentiles use the 252 values BEFORE the decision day.
  * Realised variance is the sum of squared daily log returns annualised with 252 / window (no mean removed); realised vol
    in vol points is 100 sqrt(that). Equity realised variance uses dividend-adjusted closes (an ex-dividend price drop is not
    volatility). ^GSPC is a price index (no dividends), so its close is used as is. Option payoffs settle on RAW closes.
  * SPY options (T-159 secondary, T-239 put control) are priced on the dividend forward S - PV(D) when an ex-date falls in
    the option's life: D is derived from the adjclose/close ratio step, its amount forecast point in time as the last
    dividend gone ex at or before the decision (ex-dates follow SPY's fixed quarterly schedule). SPX options (T-229) carry
    a continuous yield q: SPY's trailing-12-month dividends over its close, known at the decision (before SPY's first full
    dividend year, 1994-01, the first full-year value is used: a stated approximation for 1991-1993).
  * MODEL-PRICED results price legs at the IV proxy the claim names and say so in the reason; the archive has only two
    captured chain days, so no traded version can be tested here.

Statistics
  * Intervals are circular block bootstraps (2000 resamples, seed 0) of the statistic the claim names. Means use the
    studentized (bootstrap-t) form: each resample's mean is studentized by its own Bartlett long-run s.e. with bandwidth =
    block (as backtest_eval.block_bootstrap_pvalue). A difference of two group means on one timeline is bootstrapped PAIRED:
    blocks of the shared timeline are resampled, each day keeping its labels, studentized by the long-run s.e. of the
    difference's influence function. Ratios (drawdown ratio, variance ratio) and proportions use percentile intervals.
    Overlapping windows use blocks at least as long as the overlap.
  * "Lower/upper 95% bound" in a pass rule is read as a ONE-SIDED 95% confidence bound (the test of the stated null at 5%);
    "95% CI" is two-sided. Every reason also prints the two-sided interval. A trial that names deflation over a declared
    set of variants applies Bonferroni over that set to the level or the p-value.
  * min_n is counted in the claim's own units. Below min_n a claim cannot be supported, and a failing criterion counts only
    when it fails decisively (its interval wholly on the wrong side); otherwise it is reported as not decisive.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented ->
at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timezone
from typing import Callable, Optional, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from mandel.experiments.options_market import _binom_two_sided_ci
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, index_closes
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

PPY = 252
MONTH = 21
N_BOOT = 2000
SQRT2 = math.sqrt(2.0)
MP = "MODEL-PRICED"

SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
QQQ_B = "daily-history-QQQ"
IWM_B = "daily-history-IWM"
VIX_B = "cboe-VIX-history"
VIX3M_B = "cboe-VIX3M-history"
VVIX_B = "cboe-VVIX-history"
SKEW_B = "cboe-SKEW-history"
VXN_B = "cboe-VXN-history"
RVX_B = "cboe-RVX-history"
COR1M_B = "cboe-COR1M-history"
DTB3_B = "fred-DTB3"
SPX_CHAIN_P = "options-chain-SPX-"
SMILE_P = "spy-smile-"
KAPPA_CHAIN = "options-chain-SPX-2026-10-14"          # T-229: kappa is calibrated once, on this capture
SECTORS_ALL = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")
SECTORS_LEGACY = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")   # listed 1998; XLRE 2015, XLC 2018


# =================================================================================================== statistics ==

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


def _blk(block: int, n: int) -> int:
    return max(1, min(int(block), n // 4))


def stud_mean(x, block: int, n_boot: int = N_BOOT, seed: int = 0) -> Optional[dict]:
    """Studentized circular block bootstrap of a mean: {est, se, t (bootstrap t-statistics), n, block}; None below 8 obs.
    ``t`` is None when the series is constant (no sampling variation)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None
    b = _blk(block, n)
    m = float(x.mean())
    se = math.sqrt(float(_hac_var(x[None, :], b)[0]) / n)
    out = {"est": m, "se": se, "t": None, "n": int(n), "block": b}
    if not se > 1e-14:
        out["se"] = 0.0
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        xb = x[_boot_idx(rng, n, b, k)]
        ts.append((xb.mean(axis=1) - m) / np.sqrt(_hac_var(xb, b) / n))
    out["t"] = np.concatenate(ts)
    return out


def stud_group(x, a, b, block: int, n_boot: int = N_BOOT, seed: int = 0, min_count: int = 4) -> Optional[dict]:
    """mean(x | a) - mean(x | b) for two masks on ONE timeline (they may overlap: a subset against all). Blocks of the
    shared timeline are resampled with their labels (paired), and each resample is studentized by the Bartlett long-run
    s.e. of the influence function psi_i = n (a_i (x_i - m_a) / n_a - b_i (x_i - m_b) / n_b)."""
    x = np.asarray(x, dtype=float)
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    n = x.size
    if n < 8 or a.sum() < min_count or b.sum() < min_count:
        return None
    bl = _blk(block, n)

    def stat(xb, ab, bb):
        ca, cb = ab.sum(axis=1), bb.sum(axis=1)
        na, nb = np.maximum(ca, 1), np.maximum(cb, 1)
        ma = (xb * ab).sum(axis=1) / na
        mb = (xb * bb).sum(axis=1) / nb
        psi = n * (ab * (xb - ma[:, None]) / na[:, None] - bb * (xb - mb[:, None]) / nb[:, None])
        return ma - mb, np.sqrt(_hac_var(psi, bl) / n), (ca > 0) & (cb > 0), ma, mb

    d0, se0, _, ma0, mb0 = stat(x[None, :], a[None, :], b[None, :])
    out = {"est": float(d0[0]), "se": float(se0[0]), "t": None, "n": int(n), "block": bl, "n_a": int(a.sum()),
           "n_b": int(b.sum()), "mean_a": float(ma0[0]), "mean_b": float(mb0[0])}
    if not out["se"] > 1e-14:
        out["se"] = 0.0
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        idx = _boot_idx(rng, n, bl, k)
        d, se, ok, _, _ = stat(x[idx], a[idx], b[idx])
        ok &= se > 1e-14
        ts.append((d[ok] - out["est"]) / se[ok])
    out["t"] = np.concatenate(ts)
    return out


def lower_bound(bt: Optional[dict], level: float = 0.95) -> Optional[float]:
    """One-sided lower confidence bound at ``level`` from a studentized bootstrap."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return bt["est"]
    return bt["est"] - float(np.quantile(bt["t"], level)) * bt["se"]


def upper_bound(bt: Optional[dict], level: float = 0.95) -> Optional[float]:
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return bt["est"]
    return bt["est"] - float(np.quantile(bt["t"], 1.0 - level)) * bt["se"]


def two_sided(bt: Optional[dict], level: float = 0.95) -> tuple:
    a = (1.0 - level) / 2.0
    return lower_bound(bt, 1.0 - a), upper_bound(bt, 1.0 - a)


def p_greater(bt: Optional[dict], c: float = 0.0) -> Optional[float]:
    """One-sided bootstrap-t p-value for H0: true value <= c."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return 0.0 if bt["est"] > c else 1.0
    t_obs = (bt["est"] - c) / bt["se"]
    return float((np.sum(bt["t"] >= t_obs) + 1) / (bt["t"].size + 1))


def p_less(bt: Optional[dict], c: float = 0.0) -> Optional[float]:
    """One-sided bootstrap-t p-value for H0: true value >= c."""
    if bt is None:
        return None
    if bt["t"] is None or bt["t"].size == 0:
        return 0.0 if bt["est"] < c else 1.0
    t_obs = (bt["est"] - c) / bt["se"]
    return float((np.sum(bt["t"] <= t_obs) + 1) / (bt["t"].size + 1))


def pct_means(x, block: int, n_boot: int = N_BOOT, seed: int = 0) -> np.ndarray:
    """Percentile circular block-bootstrap distribution of a mean (for proportions)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    b = _blk(block, n)
    rng = np.random.default_rng(seed)
    return np.concatenate([x[_boot_idx(rng, n, b, k)].mean(axis=1) for k in _chunks(n_boot, n)])


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively; otherwise
    it is reported as not decisive (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _ci_s(ci, nd: int = 2, scale: float = 1.0) -> str:
    lo, hi = ci
    if lo is None or hi is None:
        return "CI n/a"
    return f"95% CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


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


def _bt_summary(bt: Optional[dict]) -> dict:
    if bt is None:
        return {}
    return {k: v for k, v in bt.items() if k != "t"}


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if getattr(e, "name", "").startswith(prefix))


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str, filtered: bool = True) -> list:
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured."""
    cap = getattr(archive.get(name), "created_at", None) if filtered else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    """(days, raw close, adjclose); a bar without adjclose carries the previous adj/close ratio."""
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        if c is None or not float(c) > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float("nan"))
    days = sorted(by)
    close = np.array([by[d][0] for d in days], dtype=float)
    adj = np.array([by[d][1] for d in days], dtype=float)
    ratio = 1.0
    for i in range(len(days)):
        if np.isfinite(adj[i]):
            ratio = adj[i] / close[i]
        else:
            adj[i] = close[i] * ratio
    return days, close, adj


def _daily(archive, name: str) -> tuple:
    return _daily_from_rows(_rows(archive, name))


def _index(archive, name: str, filtered: bool = True) -> dict:
    return index_closes(_rows(archive, name, filtered))


def _series(archive, name: str) -> dict:
    out = {}
    for r in _rows(archive, name):
        v = r["value"]
        x = v.get("value", v.get("close"))
        try:
            x = float(x)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out[v["day"]] = x
    return out


def _smile(archive) -> Optional[Smile]:
    rows = [r for nm in _names(archive, SMILE_P) for r in archive.load(nm)]
    try:
        return Smile(rows) if rows else None
    except (KeyError, TypeError, ValueError):
        return None


# ================================================================================================= market data ==

def dtb3_continuous(d_pct: float) -> float:
    """Continuous rate from a 91-day discount yield in percent."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def bill_rates(days: Sequence[str], dtb3: dict) -> np.ndarray:
    """Continuous bill rate known at each day's close: the DTB3 print dated strictly before the day (FRED publishes a day
    late); before the first print, the first print."""
    ks = sorted(dtb3)
    if not ks:
        return np.zeros(len(days))
    vals = [dtb3_continuous(dtb3[k]) for k in ks]
    return np.array([vals[max(bisect_left(ks, d) - 1, 0)] for d in days], dtype=float)


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


def div_forecast(div) -> np.ndarray:
    """Point-in-time forecast of the next dividend: the last one gone ex at or before each day (the first before any)."""
    div = np.asarray(div, dtype=float)
    nz = np.nonzero(div > 0)[0]
    out = np.zeros(div.size)
    if nz.size == 0:
        return out
    last = float(div[nz[0]])
    for i in range(div.size):
        if div[i] > 0:
            last = float(div[i])
        out[i] = last
    return out


def trailing_yield(days: Sequence[str], close, adj) -> np.ndarray:
    """Trailing-12-month cash dividends / close, known at each close. Before one full year of dividend history the first
    full-year value is used (stated approximation)."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = dividends(close, adj)
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    cum = np.concatenate([[0.0], np.cumsum(div)])
    out = np.full(len(days), np.nan)
    j = 0
    for i in range(len(days)):
        while ords[j] <= ords[i] - 365:
            j += 1
        if ords[i] - ords[0] >= 365:
            out[i] = (cum[i + 1] - cum[j]) / close[i]
    good = np.nonzero(np.isfinite(out))[0]
    if good.size:
        out[: good[0]] = out[good[0]]
    else:
        out[:] = 0.0
    return out


def make_frame(days, close, adj=None, vix=None, rate=None, div=None, extra: Optional[dict] = None) -> dict:
    """Aligned daily arrays: ISO days, ordinals, raw close, adjclose, cash dividend by ex-day and its point-in-time
    forecast, VIX (vol points), continuous bill rate; ``extra`` arrays are carried as given."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = np.zeros(close.size) if div is None else np.asarray(div, dtype=float)
    fr = {"days": days, "ords": np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64),
          "close": close, "adj": close.copy() if adj is None else np.asarray(adj, dtype=float), "div": div,
          "fc": div_forecast(div), "vix": np.full(close.size, np.nan) if vix is None else np.asarray(vix, dtype=float),
          "rate": np.zeros(close.size) if rate is None else np.asarray(rate, dtype=float)}
    for k, v in (extra or {}).items():
        fr[k] = np.asarray(v, dtype=float)
    return fr


def frame_on(days, close, adj, keep: Sequence[str], dtb3: Optional[dict] = None, indices: Optional[dict] = None) -> dict:
    """A make_frame restricted to the days in ``keep`` (sorted subset of ``days``); a dividend going ex on a dropped day is
    paid on the next kept day. ``indices`` maps a name to a {day: close} dict; 'vix' fills the frame's vix."""
    keep_set = set(keep)
    div_full = dividends(close, adj)
    sel, div, carry = [], [], 0.0
    for i, d in enumerate(days):
        carry += div_full[i]
        if d in keep_set:
            sel.append(i)
            div.append(carry)
            carry = 0.0
    d2 = [days[i] for i in sel]
    idx = indices or {}
    extra = {k: [v[d] for d in d2] for k, v in idx.items() if k != "vix"}
    vix = [idx["vix"][d] for d in d2] if "vix" in idx else None
    return make_frame(d2, np.asarray(close)[sel], adj=np.asarray(adj)[sel], vix=vix,
                      rate=bill_rates(d2, dtb3) if dtb3 else None, div=np.array(div), extra=extra)


def _pv_div(fr: dict, t: int, e: int, r: float) -> float:
    """PV at day t of the dividends going ex on days t+1..e, each at the amount forecast at t."""
    ex = np.nonzero(fr["div"][t + 1:e + 1] > 0)[0] + t + 1
    return float(sum(fr["fc"][t] * math.exp(-r * (fr["ords"][k] - fr["ords"][t]) / 365.0) for k in ex))


def _fwd_rv(lr: np.ndarray, n: int, a: int, b: int, ppy: int = PPY) -> np.ndarray:
    """For t in 0..n-1: annualised realised variance of the daily log returns of days t+a .. t+b (inclusive), where
    lr[i] is the return from day i to day i+1."""
    c = np.concatenate([[0.0], np.cumsum(np.asarray(lr, dtype=float) ** 2)])
    t = np.arange(n)
    return (c[t + b] - c[t + a - 1]) * ppy / (b - a + 1)


def trailing_pctl(x, q: float, lookback: int = 252) -> np.ndarray:
    """q-quantile of the ``lookback`` values strictly before each day; nan for the first ``lookback`` days."""
    x = np.asarray(x, dtype=float)
    n = x.size
    out = np.full(n, np.nan)
    if n > lookback:
        w = sliding_window_view(x[:-1], lookback)
        out[lookback:] = np.quantile(w, q, axis=1)
    return out


def rolling_z(x, window: int) -> np.ndarray:
    """(x_t - mean) / sd (ddof 1) over the ``window`` values ending at t (t included: known at that close)."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.size, np.nan)
    if x.size >= window:
        w = sliding_window_view(x, window)
        sd = w.std(axis=1, ddof=1)
        z = np.where(sd > 0, (x[window - 1:] - w.mean(axis=1)) / np.where(sd > 0, sd, 1.0), np.nan)
        out[window - 1:] = z
    return out


def _roll_skew(lr: np.ndarray, n: int, window: int) -> np.ndarray:
    """Sample skewness (population moments, as backtest_eval.skewness) of the returns of days t+1..t+window."""
    w = sliding_window_view(np.asarray(lr, dtype=float), window)[:n]
    d = w - w.mean(axis=1, keepdims=True)
    s2 = (d ** 2).mean(axis=1)
    s3 = (d ** 3).mean(axis=1)
    return np.where(s2 > 0, s3 / np.where(s2 > 0, s2, 1.0) ** 1.5, 0.0)


def _align(*dicts) -> list:
    keys = set(dicts[0])
    for d in dicts[1:]:
        keys &= set(d)
    return sorted(keys)


# ========================================================================================== option pricing ==

def _N(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def _bs(S: float, K: float, T: float, r: float, q: float, sig: float, kind: str) -> float:
    if T <= 0 or sig <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    d2 = d1 - sq
    if kind == "call":
        return S * math.exp(-q * T) * _N(d1) - K * math.exp(-r * T) * _N(d2)
    return K * math.exp(-r * T) * _N(-d2) - S * math.exp(-q * T) * _N(-d1)


def _bs_delta(S: float, K: float, T: float, r: float, q: float, sig: float, kind: str) -> float:
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    return math.exp(-q * T) * (_N(d1) if kind == "call" else _N(d1) - 1.0)


def strike_for_delta_smile(S: float, T: float, r: float, q: float, sig_fn: Callable[[float], float], target: float, kind: str,
                           lo: float, hi: float, iters: int = 80) -> Optional[float]:
    """Strike whose Black-Scholes delta at its own smile vol sig_fn(K) equals ``target``; None without a sign change."""
    def f(K):
        return _bs_delta(S, K, T, r, q, sig_fn(K), kind) - target
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def b76_call(F: float, K: float, T: float, r: float, sig: float) -> float:
    """Black-76 call on a forward F."""
    if T <= 0 or sig <= 0:
        return math.exp(-r * max(T, 0.0)) * max(F - K, 0.0)
    sq = sig * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sig * sig * T) / sq
    return math.exp(-r * T) * (F * _N(d1) - K * _N(d1 - sq))


def b76_call_strike(F: float, T: float, sig: float, delta: float) -> float:
    """Strike of a Black-76 call with forward delta N(d1) = ``delta``."""
    from mandel.options.bs import _ninv
    sq = sig * math.sqrt(T)
    return F * math.exp(-_ninv(delta) * sq + 0.5 * sig * sig * T)


# ================================================================================ T-159: VRP by term regime ==

def vrp_regime(days, px, vix, vix3m, lo: float = 0.95, hi: float = 1.05, window: int = MONTH, block: int = 21,
               min_n: int = 60, n_thresholds: int = 4, min_half: int = 21, n_boot: int = N_BOOT, n_shift: int = 1000,
               seed: int = 0, excl_year: str = "2020") -> dict:
    """T-159. VRP_t = (VIX_t/100)^2 - RV(t+1..t+21) on aligned daily arrays (px dividend-adjusted). Within each VIX tercile
    (full-sample cut points: a stratification, not a signal): contango (VIX/VIX3M < lo) minus backwardation (> hi) mean
    VRP. Per tercile: studentized paired block bootstrap (block 21) p and the trial's block-shift null (the regime label
    circularly shifted against the VRP series) p; the larger, x ``n_thresholds`` (Bonferroni over the declared thresholds
    0.90/0.95/1.00/1.05), must be < 0.05, the difference > 0 in both walk-forward halves (a half with < ``min_half`` days in
    either cell is not testable), and >= 2 of 3 terciles must pass. A tercile with < ``min_n`` days in either regime is not
    testable. n = backwardation days (the scarce regime)."""
    days = list(days)
    px, vix, vix3m = (np.asarray(a, dtype=float) for a in (px, vix, vix3m))
    n = len(days) - window
    if n < 100:
        return {"n": max(n, 0), "verdict": "inconclusive", "reason": f"only {max(n, 0)} aligned days with a forward window — too few to test"}
    lr = np.diff(np.log(px))
    rv = _fwd_rv(lr, n, 1, window)
    vrp = (vix[:n] / 100.0) ** 2 - rv
    vrp_vol = vix[:n] - 100.0 * np.sqrt(rv)
    ratio = vix[:n] / vix3m[:n]
    q1, q2 = np.quantile(vix[:n], [1 / 3, 2 / 3])
    terc = np.digitize(vix[:n], [q1, q2])
    con, bwd = ratio < lo, ratio > hi
    rng = np.random.default_rng(seed + 7)
    shifts = rng.integers(window + 1, max(window + 2, n - window - 1), n_shift)
    h = n // 2
    first = np.arange(n) < h
    keep_ex = np.array([not d.startswith(excl_year) for d in days[:n]])
    rows = []
    for k in range(3):
        tk = terc == k
        a, b = con & tk, bwd & tk
        na, nb = int(a.sum()), int(b.sum())
        row = {"tercile": ["low", "mid", "high"][k], "vix_range": [float(vix[:n][tk].min()), float(vix[:n][tk].max())],
               "n_contango": na, "n_backwardation": nb, "testable": na >= min_n and nb >= min_n,
               "diff_var": float(vrp[a].mean() - vrp[b].mean()) if na and nb else None,
               "diff_volpts": float(vrp_vol[a].mean() - vrp_vol[b].mean()) if na and nb else None,
               "diff_var_ex_" + excl_year: (float(vrp[a & keep_ex].mean() - vrp[b & keep_ex].mean())
                                           if (a & keep_ex).any() and (b & keep_ex).any() else None)}
        if not row["testable"]:
            row["pass"] = None
            rows.append(row)
            continue
        bt = stud_group(vrp, a, b, block, n_boot, seed)
        d0 = bt["est"]
        p_st = p_greater(bt)
        null = []
        for s in shifts:
            rs = np.roll(ratio, int(s))
            a_s, b_s = (rs < lo) & tk, (rs > hi) & tk
            if a_s.any() and b_s.any():
                null.append(vrp[a_s].mean() - vrp[b_s].mean())
        null = np.asarray(null)
        p_sh = float((np.sum(null >= d0) + 1) / (null.size + 1)) if null.size else 1.0
        p_defl = min(1.0, n_thresholds * max(p_st, p_sh))
        halves = []
        for m in (first, ~first):
            aa, bb = a & m, b & m
            halves.append(float(vrp[aa].mean() - vrp[bb].mean()) if aa.sum() >= min_half and bb.sum() >= min_half else None)
        halves_ok = None if any(x is None for x in halves) else all(x > 0 for x in halves)
        comps = [d0 > 0, p_defl < 0.05, halves_ok]
        ok = False if any(c is False for c in comps) else (None if any(c is None for c in comps) else True)
        row.update({"ci_var": list(two_sided(bt)), "p_studentized": p_st, "p_block_shift": p_sh, "p_deflated": p_defl,
                    "halves_var": halves, "pass": ok})
        rows.append(row)
    n_true = sum(r["pass"] is True for r in rows)
    n_none = sum(r["pass"] is None for r in rows)
    terc_ok = True if n_true >= 2 else (False if n_true + n_none < 2 else None)
    n_bwd = int(bwd.sum())

    def _status(r):
        if not r["testable"]:
            return f"{r['tercile']} not testable ({r['n_backwardation']} backwardation / {r['n_contango']} contango days, need {min_n} each)"
        return f"{r['tercile']} " + {True: "passes", False: "fails", None: "undecided (a half not testable)"}[r["pass"]]
    crit = [("contango-minus-backwardation VRP > 0, deflated p < 0.05 and > 0 in both halves, in >= 2 of 3 VIX terciles ("
             + "; ".join(_status(r) for r in rows) + ")", terc_ok, False)]
    verdict, why = _decide(crit, n_bwd, min_n, "backwardation days")

    def _row_s(r):
        if r["diff_var"] is None:
            return f"{r['tercile']} (VIX {r['vix_range'][0]:.1f}-{r['vix_range'][1]:.1f}): {r['n_contango']} contango / {r['n_backwardation']} backwardation days, no difference"
        s = (f"{r['tercile']} (VIX {r['vix_range'][0]:.1f}-{r['vix_range'][1]:.1f}; {r['n_contango']}/{r['n_backwardation']} days) "
             f"diff {r['diff_var']*1e4:+.1f} %^2 ({r['diff_volpts']:+.2f} vol pts)")
        if not r["testable"]:
            return s + f" [not testable: < {min_n} days in a regime]"
        hv = "/".join("n/a" if x is None else f"{x*1e4:+.1f}" for x in r["halves_var"])
        return s + (f", {_ci_s(r['ci_var'], 1, 1e4)}, p stud {r['p_studentized']:.3f} / block-shift {r['p_block_shift']:.3f}"
                    f" -> deflated x{n_thresholds} {r['p_deflated']:.3f}, halves {hv} -> {'pass' if r['pass'] else ('n/a' if r['pass'] is None else 'fail')}")
    return {"n": n_bwd, "min_n": min_n, "n_days": int(n), "first_day": days[0], "last_entry": days[n - 1], "lo": lo, "hi": hi,
            "tercile_cuts": [float(q1), float(q2)], "terciles": rows, "share_backwardation": float(bwd.mean()),
            "share_contango": float(con.mean()), "terciles_passing": n_true, "verdict": verdict,
            "reason_core": "; ".join(_row_s(r) for r in rows), "why": why}


def short_strangle_cycles(fr: dict, scale: float = 1.0, delta: float = 0.16, hold: int = MONTH) -> dict:
    """MODEL-PRICED short 16-delta strangle, entered at a close, expiring at the close ``hold`` sessions later (T =
    calendar days / 365), legs at sigma = scale * VIX / 100 (flat smile) on the dividend forward; premium earns the bill
    to expiry; settles on the raw close. Returns entry indices and P&L / spot."""
    n = len(fr["days"])
    starts, pnl = [], []
    for t in range(0, n - hold, hold):
        e = t + hold
        S = float(fr["close"][t])
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        r = float(fr["rate"][t])
        sig = max(scale * float(fr["vix"][t]) / 100.0, 0.01)
        Sx = S - _pv_div(fr, t, e, r)
        Kc = strike_for_delta_smile(Sx, T, r, 0.0, lambda K: sig, delta, "call", Sx, 3 * Sx)
        Kp = strike_for_delta_smile(Sx, T, r, 0.0, lambda K: sig, -delta, "put", 0.2 * Sx, Sx)
        if Kc is None or Kp is None:
            continue
        prem = _bs(Sx, Kc, T, r, 0.0, sig, "call") + _bs(Sx, Kp, T, r, 0.0, sig, "put")
        S1 = float(fr["close"][e])
        pay = max(S1 - Kc, 0.0) + max(Kp - S1, 0.0)
        starts.append(t)
        pnl.append((prem * math.exp(r * T) - pay) / S)
    return {"start": np.array(starts, dtype=int), "pnl": np.array(pnl, dtype=float)}


# ================================================================= T-227: SKEW percentile and realised left tails ==

def skew_tail_frequency(days, close, skew, vix, start: str = "1991-01-01", window: int = MONTH, cut: tuple = (0.80, 0.20),
                        alt_cut: tuple = (0.90, 0.10), bound: float = 0.01, n_cuts: int = 2, split: str = "2009-01-01",
                        block: int = 21, lookback: int = 252, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300,
                        excl_months: tuple = ("2008-10", "2020-03"), n_placebo: int = 200) -> dict:
    """T-227 on aligned daily arrays (^GSPC close, SKEW, VIX). Windows start every day from ``start`` (trailing percentiles
    need ``lookback`` prior values). y_t = 1{ln(S_{t+21}/S_t) < -2 (VIX_t/100) sqrt(21/252)}. High: SKEW_t above the q_hi
    quantile of the prior 252 SKEW values; low: below q_lo. Pass: one-sided upper bound of freq_high - freq_low at 1 - 0.05 /
    ``n_cuts`` (95% deflated for the 80/20 and 90/10 cut pairs) < ``bound``; and in both halves (before / from ``split``)
    the realised-21d-skewness difference high - low is not significantly negative (one-sided p > 0.1). Bootstraps are
    studentized, paired on the timeline, block 21 (the window overlap). n = min(high, low) windows."""
    days = list(days)
    close, skew, vix = (np.asarray(a, dtype=float) for a in (close, skew, vix))
    n = len(days) - window
    lr = np.diff(np.log(close))
    r_w = np.log(close[window:] / close[:n])
    thr = -2.0 * (vix[:n] / 100.0) * math.sqrt(window / PPY)
    y = (r_w < thr).astype(float)
    sk_w = _roll_skew(lr, n, window)
    dd = np.array(days[:n])
    valid = (np.arange(n) >= lookback) & (dd >= start)
    idx = np.nonzero(valid)[0]
    if idx.size < 50:
        return {"n": 0, "verdict": "inconclusive", "reason": f"only {idx.size} windows from {start} with {lookback} prior SKEW values — too few to test"}
    level = 1.0 - 0.05 / n_cuts

    def groups(sig, q_hi, q_lo):
        ph, pl = trailing_pctl(sig, q_hi, lookback)[:n], trailing_pctl(sig, q_lo, lookback)[:n]
        with np.errstate(invalid="ignore"):
            return sig[:n] > ph, sig[:n] < pl

    def freq_test(hi_m, lo_m, sel):
        bt = stud_group(y[sel], hi_m[sel], lo_m[sel], block, n_boot, seed)
        return bt

    hi_m, lo_m = groups(skew, *cut)
    bt = freq_test(hi_m, lo_m, idx)
    if bt is None:
        return {"n": 0, "verdict": "inconclusive", "reason": "a SKEW group has fewer than 4 windows — too few to test"}
    ub = upper_bound(bt, level)
    ci = two_sided(bt)
    n_hi, n_lo = int(hi_m[idx].sum()), int(lo_m[idx].sum())
    n_min = min(n_hi, n_lo)
    sk_rows = []
    for lab, m in (("1991-2008", dd < split), ("2009-2026", dd >= split)):
        sel = idx[m[idx]]
        bts = stud_group(sk_w[sel], hi_m[sel], lo_m[sel], block, n_boot, seed) if sel.size >= 8 else None
        bth = stud_group(y[sel], hi_m[sel], lo_m[sel], block, n_boot, seed) if sel.size >= 8 else None
        sk_rows.append({"half": lab, "n_windows": int(sel.size), "skew_diff": None if bts is None else bts["est"],
                        "p_negative": p_less(bts), "skew_diff_ci": list(two_sided(bts)),
                        "freq_diff": None if bth is None else bth["est"], "freq_diff_upper": upper_bound(bth, level)})
    alt_hi, alt_lo = groups(skew, *alt_cut)
    bt_alt = freq_test(alt_hi, alt_lo, idx)
    # controls
    mon = np.array([d[:7] for d in days])
    bad = np.isin(mon, list(excl_months)).astype(int)
    cb = np.concatenate([[0], np.cumsum(bad)])
    touches = (cb[np.arange(n) + window + 1] - cb[np.arange(n)]) > 0
    sel_ex = idx[~touches[idx]]
    bt_ex = freq_test(hi_m, lo_m, sel_ex)
    dsk = np.full(len(days), np.nan)
    dsk[window:] = skew[window:] - skew[:-window]
    ch_hi, ch_lo = groups(np.where(np.isfinite(dsk), dsk, np.nanmedian(dsk)), *cut)
    sel_ch = idx[idx >= lookback + window]
    bt_ch = freq_test(ch_hi, ch_lo, sel_ch)
    vq = np.quantile(vix[idx], [1 / 3, 2 / 3])
    vt = np.digitize(vix[:n], vq)
    strat = []
    for k in range(3):
        m = idx[vt[idx] == k]
        h_, l_ = hi_m[m], lo_m[m]
        strat.append(float(y[m][h_].mean() - y[m][l_].mean()) if h_.any() and l_.any() else None)
    rng = np.random.default_rng(seed + 11)
    plc = []
    for _ in range(n_placebo):
        s = int(rng.integers(lookback, max(lookback + 1, idx.size - lookback)))
        hh, ll = np.roll(hi_m[idx], s), np.roll(lo_m[idx], s)
        if hh.any() and ll.any():
            plc.append(y[idx][hh].mean() - y[idx][ll].mean())
    plc = np.asarray(plc)
    crit = [(f"freq_high - freq_low one-sided {level:.1%} upper bound (95% deflated for {n_cuts} cut pairs) < {bound:.2f}",
             ub < bound, lower_bound(bt, level) >= bound)]
    for r in sk_rows:
        p = r["p_negative"]
        crit.append((f"realised-21d-skewness difference not significantly negative in {r['half']} (one-sided p > 0.1)",
                     None if p is None else p > 0.1, False))
    verdict, why = _decide(crit, n_min, min_n, "windows in the smaller SKEW group")
    reason = (f"^GSPC 21d log return below -2 VIX-sigma: high-SKEW (> trailing p{int(cut[0]*100)}) {bt['mean_a']*100:.2f}% of "
              f"{n_hi} windows vs low-SKEW (< p{int(cut[1]*100)}) {bt['mean_b']*100:.2f}% of {n_lo} ({days[idx[0]]}..{days[idx[-1]]}, "
              f"daily overlapping starts); difference {bt['est']*100:+.2f} pp, one-sided {level:.1%} upper bound {ub*100:+.2f} pp "
              f"(two-sided {_ci_s(tuple(x*100 for x in ci), 2)}) vs the {bound*100:.0f} pp margin; realised-skewness difference "
              + "; ".join(f"{r['half']} {_s(r['skew_diff'], 3)} (one-sided p for negative {_f(r['p_negative'], 3)})" for r in sk_rows)
              + f". Controls: halves' frequency difference " + "/".join(_s(None if r['freq_diff'] is None else r['freq_diff'] * 100, 2) for r in sk_rows)
              + f" pp; 90/10 cut {_s(bt_alt['est']*100 if bt_alt else None, 2)} pp (upper {_s(upper_bound(bt_alt, level)*100 if bt_alt else None, 2)});"
              f" excluding windows touching {'/'.join(excl_months)} {_s(bt_ex['est']*100 if bt_ex else None, 2)} pp (upper {_s(upper_bound(bt_ex, level)*100 if bt_ex else None, 2)});"
              f" 21-day SKEW change instead of level {_s(bt_ch['est']*100 if bt_ch else None, 2)} pp (upper {_s(upper_bound(bt_ch, level)*100 if bt_ch else None, 2)});"
              f" within VIX terciles " + "/".join(_s(None if x is None else x * 100, 2) for x in strat) + " pp;"
              f" shifted-SKEW placebo mean {_s(float(plc.mean())*100 if plc.size else None, 2)} pp")
    return {"n": n_min, "min_n": min_n, "n_high": n_hi, "n_low": n_lo, "freq_high": bt["mean_a"], "freq_low": bt["mean_b"],
            "diff": bt["est"], "upper_bound": ub, "bound_level": level, "ci95": list(ci), "halves": sk_rows,
            "alt_cut_diff": None if bt_alt is None else bt_alt["est"], "alt_cut_upper": upper_bound(bt_alt, level),
            "excl_months_diff": None if bt_ex is None else bt_ex["est"], "excl_months_upper": upper_bound(bt_ex, level),
            "skew_change_diff": None if bt_ch is None else bt_ch["est"], "skew_change_upper": upper_bound(bt_ch, level),
            "vix_tercile_diffs": strat, "placebo_mean": float(plc.mean()) if plc.size else None,
            "first_window": days[idx[0]], "last_window": days[idx[-1]], "verdict": verdict, "reason": reason + " — " + why}


# ===================================================================== T-228: SKEW-implied tail vs realised ==

def skew_tail_prob(skew) -> np.ndarray:
    """CBOE white-paper Gram-Charlier mapping: P(30-day log return < -2 sigma) = 0.0228 + 0.0270 (SKEW - 100) / 10."""
    return 0.0228 + 0.0270 * (np.asarray(skew, dtype=float) - 100.0) / 10.0


def skew_implied_gap(days, close, skew, vix, start: str = "1990-01-01", window: int = MONTH, margin: float = 0.02,
                     block: int = 6, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300,
                     thresholds: tuple = (125, 130, 135, 140), secondary: int = 135, table_max: float = 145.0,
                     n_placebo: int = 1000) -> dict:
    """T-228 on aligned daily arrays. Non-overlapping 21-day windows from ``start``; gap_t = P_SKEW(t) - y_t. Pass: one-sided
    95% lower bound of the mean gap > ``margin`` (studentized block bootstrap, block 6 windows) and the mean gap > 0 in at
    least 2 of 3 equal sub-periods. n = windows."""
    days = list(days)
    close, skew, vix = (np.asarray(a, dtype=float) for a in (close, skew, vix))
    t0 = next((i for i, d in enumerate(days) if d >= start), len(days))
    ts = np.arange(t0, len(days) - window, window)
    if ts.size < 8:
        return {"n": int(ts.size), "verdict": "inconclusive", "reason": f"only {ts.size} non-overlapping windows — too few to test"}
    r_w = np.log(close[ts + window] / close[ts])
    y = (r_w < -2.0 * (vix[ts] / 100.0) * math.sqrt(window / PPY)).astype(float)
    P = skew_tail_prob(skew[ts])
    gap = P - y
    bt = stud_mean(gap, block, n_boot, seed)
    lb = lower_bound(bt, 0.95)
    ci = two_sided(bt)
    thirds = [float(p.mean()) for p in np.array_split(gap, 3)]
    n_pos = sum(t > 0 for t in thirds)
    bt_norm = stud_mean(0.0228 - y, block, n_boot, seed)
    sk = skew[ts]
    cond = {}
    for thr in thresholds:
        m = sk > thr
        cond[str(thr)] = {"n": int(m.sum()), "gap": float(gap[m].mean()) if m.any() else None}
    above = sk > table_max
    R = gap[:, None] * (sk[:, None] > np.array(thresholds)[None, :])
    try:
        pbo = pbo_cscv(R, 8) if R.shape[0] >= 16 else None
    except (ValueError, ZeroDivisionError, FloatingPointError):
        pbo = None
    rng = np.random.default_rng(seed + 3)
    msec = sk > secondary
    plc_p = None
    if msec.any() and (~msec).any():
        obs = gap[msec].mean()
        null = np.array([gap[rng.permutation(msec)].mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= obs) + 1) / (n_placebo + 1))
    n = int(ts.size)
    crit = [(f"mean gap one-sided 95% lower bound > {margin:.2f}", lb > margin, upper_bound(bt, 0.95) <= margin),
            ("mean gap positive in >= 2 of 3 sub-periods", n_pos >= 2, False)]
    verdict, why = _decide(crit, n, min_n, "non-overlapping 21d windows")
    sec = cond.get(str(secondary), {})
    reason = (f"SKEW-implied P(21d < -2 VIX-sigma) averages {P.mean()*100:.2f}% vs realised {y.mean()*100:.2f}% over {n} "
              f"non-overlapping 21d ^GSPC windows ({days[ts[0]]}..{days[ts[-1]]}); mean gap {bt['est']*100:+.2f} pp, one-sided 95% "
              f"lower bound {lb*100:+.2f} pp (two-sided {_ci_s(tuple(x*100 for x in ci), 2)}) vs the {margin*100:.0f} pp margin; "
              f"sub-period gaps " + "/".join(f"{x*100:+.2f}" for x in thirds) + f" pp ({n_pos} of 3 positive). Controls: "
              f"constant-normal benchmark (P = 2.28%) gap {bt_norm['est']*100:+.2f} pp; SKEW > {secondary} conditional gap "
              f"{_s(None if sec.get('gap') is None else sec['gap']*100, 2)} pp (n={sec.get('n', 0)}, shuffled-SKEW placebo p={_f(plc_p, 3)}); "
              f"PBO across thresholds {'/'.join(map(str, thresholds))} {_f(pbo['pbo'] if pbo else None, 2)}; SKEW > {table_max:.0f} "
              f"(beyond the white-paper table, formula extrapolated) {int(above.sum())} windows, gap "
              f"{_s(float(gap[above].mean())*100 if above.any() else None, 2)} pp")
    return {"n": n, "min_n": min_n, "mean_p_skew": float(P.mean()), "realised_freq": float(y.mean()), "mean_gap": bt["est"],
            "lower_bound_95_one_sided": lb, "ci95": list(ci), "thirds": thirds, "normal_benchmark_gap": bt_norm["est"],
            "conditional": cond, "pbo": pbo, "placebo_p_secondary": plc_p, "n_above_table": int(above.sum()),
            "gap_above_table": float(gap[above].mean()) if above.any() else None, "first_window": days[ts[0]],
            "last_window": days[ts[-1]], "verdict": verdict, "reason": reason + " — " + why}


# ======================================================== T-229: SKEW-gated 25d/10d SPX put spread (model) ==

def _root(sym: str) -> str:
    return sym[:-15] if len(sym) > 15 else sym


def _chain_by_strike(vals, expiry: str, roots=("SPXW", "SPX")) -> tuple:
    """{strike: {'call': row, 'put': row}} for one expiry, preferring the first root in ``roots`` that lists it."""
    rows = [v for v in vals if v.get("expiry") == expiry]
    have = {_root(v.get("sym", "")) for v in rows}
    root = next((r for r in roots if r in have), None)
    out = {}
    for v in rows:
        if root is not None and _root(v.get("sym", "")) != root:
            continue
        out.setdefault(float(v["strike"]), {})[v["type"]] = v
    return root, out


def _mid(row) -> Optional[float]:
    if not row:
        return None
    b, a = row.get("bid") or 0.0, row.get("ask") or 0.0
    return 0.5 * (b + a) if b > 0 and a >= b else None


def _parity_forward(by: dict, T: float, r: float) -> Optional[tuple]:
    best = None
    for K, d in by.items():
        c, p = _mid(d.get("call")), _mid(d.get("put"))
        if c is None or p is None:
            continue
        if best is None or abs(c - p) < best[0]:
            best = (abs(c - p), K, c, p)
    if best is None:
        return None
    _, K, c, p = best
    return K + math.exp(r * T) * (c - p), K


def calibrate_skew_slope(vals, quote_day: str, r: float, vix_q: float, skew_q: float, target_dte: int = 30,
                         dmin: float = 0.08, dmax: float = 0.30) -> Optional[dict]:
    """T-229 calibration on one captured SPX chain: the expiry nearest ``target_dte`` calendar days from the quote day; F by
    put-call parity; ATM IV interpolated at F from the chain's put and call IVs; the slope of put IV on ln(K/F) through the
    ATM point (least squares) over puts with chain delta in [-dmax, -dmin] (the 25d..10d region the spread uses). Returns
    the ATM-to-VIX ratio and kappa = -slope / (SKEW_q - 100)."""
    qd = date.fromisoformat(quote_day)
    exps = sorted({v.get("expiry") for v in vals if v.get("expiry")})
    cands = [e for e in exps if (date.fromisoformat(e) - qd).days >= 7]
    if not cands:
        return None
    exp = min(cands, key=lambda e: abs((date.fromisoformat(e) - qd).days - target_dte))
    dte = (date.fromisoformat(exp) - qd).days
    T = dte / 365.0
    root, by = _chain_by_strike(vals, exp)
    fw = _parity_forward(by, T, r)
    if fw is None:
        return None
    F, _ = fw
    ks = sorted(K for K, d in by.items() if all((d.get(k) or {}).get("iv", 0) > 0 for k in ("call", "put")))
    if len(ks) < 2:
        return None
    j = bisect_left(ks, F)
    if j <= 0 or j >= len(ks):
        return None
    k0, k1 = ks[j - 1], ks[j]
    iv = lambda K: 0.5 * (by[K]["call"]["iv"] + by[K]["put"]["iv"])
    w = (math.log(F) - math.log(k0)) / (math.log(k1) - math.log(k0))
    atm = (1 - w) * iv(k0) + w * iv(k1)
    pts = [(math.log(K / F), d["put"]["iv"] - atm) for K, d in by.items()
           if d.get("put") and (d["put"].get("iv") or 0) > 0 and d["put"].get("delta") is not None
           and -dmax <= float(d["put"]["delta"]) <= -dmin]
    if len(pts) < 3:
        return None
    x = np.array([p[0] for p in pts])
    yv = np.array([p[1] for p in pts])
    slope = float((x * yv).sum() / (x * x).sum())
    rmse = float(np.sqrt(np.mean((yv - slope * x) ** 2)))
    return {"quote_day": quote_day, "expiry": exp, "root": root, "dte": dte, "forward": F, "atm_iv": atm, "vix": vix_q,
            "atm_ratio": atm / (vix_q / 100.0), "skew": skew_q, "slope": slope, "kappa": -slope / (skew_q - 100.0),
            "n_points": len(pts), "fit_rmse": rmse}


def put_spread_cycle(S: float, S1: float, T: float, r: float, q: float, sig_atm: float, slope: float,
                     d_long: float = -0.25, d_short: float = -0.10) -> Optional[tuple]:
    """One MODEL-PRICED put spread: long the ``d_long`` put, short the ``d_short`` put, legs at sigma(K) = sig_atm + slope
    ln(K/F) (floored at 1%), strikes solved at their own smile vol; returns (debit, payoff, K_long, K_short)."""
    F = S * math.exp((r - q) * T)
    sig = lambda K: max(sig_atm + slope * math.log(K / F), 0.01)
    k_long = strike_for_delta_smile(S, T, r, q, sig, d_long, "put", 0.15 * F, F)
    k_short = strike_for_delta_smile(S, T, r, q, sig, d_short, "put", 0.15 * F, F)
    if k_long is None or k_short is None or not k_short < k_long:
        return None
    debit = _bs(S, k_long, T, r, q, sig(k_long), "put") - _bs(S, k_short, T, r, q, sig(k_short), "put")
    if not debit > 0:
        return None
    payoff = max(k_long - S1, 0.0) - max(k_short - S1, 0.0)
    return debit, payoff, k_long, k_short


def put_spread_skew(days, spx, skew, vix, rate, qy, atm_ratio: float, kappa: float, start: str = "1991-01-01",
                    hold: int = MONTH, lookback: int = 252, pct: float = 0.20, mults: tuple = (0.5, 1.0, 2.0),
                    block: int = 6, n_boot: int = N_BOOT, seed: int = 0, min_n: int = 300, min_low: int = 60,
                    n_placebo: int = 2000) -> dict:
    """T-229 on aligned daily arrays (^GSPC close, SKEW, VIX, continuous bill rate, dividend yield). Monthly entries every
    ``hold`` sessions from ``start`` (after ``lookback`` SKEW values), held to expiry (the close ``hold`` sessions later;
    T = calendar days / 365). ATM IV = VIX/100 x atm_ratio; slope = -kappa x mult x (SKEW - 100). Statistic: mean(payoff /
    debit | SKEW_t < trailing p20) - mean(payoff / debit | all), studentized paired block bootstrap (block 6). Pass: > 0
    with the two-sided 95% CI excluding zero, >= ``min_low`` low-SKEW entries, and > 0 at kappa x0.5 and x2."""
    days = list(days)
    spx, skew, vix, rate, qy = (np.asarray(a, dtype=float) for a in (spx, skew, vix, rate, qy))
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    p_lo = trailing_pctl(skew, pct, lookback)
    t0 = max(lookback, next((i for i, d in enumerate(days) if d >= start), len(days)))
    ts = np.arange(t0, len(days) - hold, hold)
    if ts.size < 8:
        return {"n": int(ts.size), "verdict": "inconclusive", "reason": f"only {ts.size} monthly entries — too few to test"}
    res = {m: np.full(ts.size, np.nan) for m in mults}
    debits = {m: np.full(ts.size, np.nan) for m in mults}
    for i, t in enumerate(ts):
        e = t + hold
        T = (ords[e] - ords[t]) / 365.0
        for m in mults:
            c = put_spread_cycle(spx[t], spx[e], T, rate[t], qy[t], vix[t] / 100.0 * atm_ratio, -kappa * m * (skew[t] - 100.0))
            if c is not None:
                res[m][i] = c[1] / c[0]
                debits[m][i] = c[0] / spx[t]
    ok = np.all([np.isfinite(res[m]) for m in mults], axis=0)
    ts, low_all = ts[ok], (skew < p_lo)[ts[ok]] if ok.any() else np.zeros(0, bool)
    n = int(ts.size)
    n_drop = int((~ok).sum())
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} priceable monthly entries — too few to test"}
    allm = np.ones(n, dtype=bool)
    out_m = {}
    for m in mults:
        x = res[m][ok]
        bt = stud_group(x, low_all, allm, block, n_boot, seed)
        out_m[m] = {"diff": None if bt is None else bt["est"], "ci": list(two_sided(bt)),
                    "mean_low": None if bt is None else bt["mean_a"], "mean_all": float(x.mean()),
                    "mean_debit_pct_spot": float(np.nanmean(debits[m][ok]) * 100)}
    base = res[1.0][ok] if 1.0 in res else res[mults[0]][ok]
    b0 = out_m.get(1.0, out_m[mults[0]])
    n_low = int(low_all.sum())
    lo, hi = b0["ci"]
    others = [m for m in mults if m != 1.0]
    sens_ok = all(out_m[m]["diff"] is not None and out_m[m]["diff"] > 0 for m in others)
    # controls
    rng = np.random.default_rng(seed + 5)
    plc_p = None
    if 0 < n_low < n and b0["diff"] is not None:
        null = np.array([base[rng.choice(n, n_low, replace=False)].mean() - base.mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= b0["diff"]) + 1) / (n_placebo + 1))
    v15 = vix[ts] < 15
    bt15 = stud_group(base, v15, allm, block, n_boot, seed) if v15.sum() >= 4 else None
    vq = np.quantile(vix[ts], [1 / 3, 2 / 3])
    vt = np.digitize(vix[ts], vq)
    strat = [float(base[(vt == k) & low_all].mean() - base[vt == k].mean()) if ((vt == k) & low_all).any() else None for k in range(3)]
    try:
        dsr = float(deflated_sharpe_ratio(base[low_all] - 1.0, n_trials=2)) if n_low >= 8 else None
    except (ValueError, ZeroDivisionError):
        dsr = None
    crit = [("mean(payoff/debit | SKEW < trailing p20) - mean(all) > 0 with the two-sided 95% CI excluding zero",
             None if lo is None else (b0["diff"] > 0 and lo > 0), hi is not None and hi < 0),
            (f"at least {min_low} low-SKEW entries ({n_low})", n_low >= min_low, False),
            ("difference > 0 (sign unchanged) at kappa " + " and ".join(f"x{m}" for m in others), sens_ok,
             all(out_m[m]["ci"][1] is not None and out_m[m]["ci"][1] < 0 for m in others))]
    verdict, why = _decide(crit, n, min_n, "monthly entries")
    reason = (f"{MP} (BS legs: ATM IV = VIX x {atm_ratio:.3f}, put skew slope = -kappa (SKEW - 100) per unit ln(K/F), kappa "
              f"{kappa:.5f}, held fixed through history; payoff on ^GSPC closes): {n} monthly 30-DTE entries ({days[ts[0]]}..{days[ts[-1]]}"
              + (f"; {n_drop} unpriceable dropped" if n_drop else "") + f"), {n_low} with SKEW below its trailing 20th percentile; "
              f"mean payoff/debit low-SKEW {_f(b0['mean_low'], 3)} vs all {_f(b0['mean_all'], 3)}: difference {_s(b0['diff'], 3)} "
              f"({_ci_s(b0['ci'], 3)}); kappa sensitivity " + ", ".join(f"x{m} {_s(out_m[m]['diff'], 3)} ({_ci_s(out_m[m]['ci'], 3)})" for m in others)
              + f". Controls: random-timing placebo p={_f(plc_p, 3)}; VIX < 15 gate difference {_s(None if bt15 is None else bt15['est'], 3)}"
              f" (n={int(v15.sum())}); within VIX terciles " + "/".join(_s(x, 3) for x in strat)
              + f"; deflated Sharpe (2 gates) of the low-SKEW per-entry return {_f(dsr, 3)}. The debit hinges on the IV proxy; "
              "the traded version needs SPX chain history (2 capture days archived)")
    return {"n": n, "min_n": min_n, "n_low": n_low, "by_kappa_mult": {str(m): v for m, v in out_m.items()}, "atm_ratio": atm_ratio,
            "kappa": kappa, "placebo_p": plc_p, "vix15_diff": None if bt15 is None else bt15["est"], "vix_tercile_diffs": strat,
            "dsr_low_skew": dsr, "dropped_entries": n_drop, "first_entry": days[ts[0]], "last_entry": days[ts[-1]],
            "verdict": verdict, "reason": reason + " — " + why}


# ============================================================= T-237: VXN - VIX z-score vs realised spread ==

def vol_spread_events(days, iv_a, iv_b, px_a, px_b, window: int = 60, thr: float = 2.0, hold: int = MONTH, block: int = 2,
                      n_declared: int = 3) -> dict:
    """Event series for T-237 on aligned daily arrays: x = iv_a - iv_b; z = rolling z of x over ``window`` days (t
    included); an event is the first close where |z| passes ``thr`` (|z_{t-1}| <= thr < |z_t|) while no hold is open; s =
    sign(z). stat_t = s [x_t - (RV_a - RV_b)(t+1..t+hold)], realised vols in vol points from dividend-adjusted closes."""
    iv_a, iv_b, px_a, px_b = (np.asarray(v, dtype=float) for v in (iv_a, iv_b, px_a, px_b))
    n = len(days) - hold
    x = iv_a - iv_b
    rv_a = 100 * np.sqrt(_fwd_rv(np.diff(np.log(px_a)), max(n, 0), 1, hold)) if n > 0 else np.zeros(0)
    rv_b = 100 * np.sqrt(_fwd_rv(np.diff(np.log(px_b)), max(n, 0), 1, hold)) if n > 0 else np.zeros(0)
    stat_all = x[:max(n, 0)] - (rv_a - rv_b)
    z = rolling_z(x, window)
    ev_t, ev_s = [], []
    free = 0
    for t in range(max(window, 1), max(n, 0)):
        if t < free or not (np.isfinite(z[t]) and np.isfinite(z[t - 1])):
            continue
        if abs(z[t]) > thr and abs(z[t - 1]) <= thr:
            ev_t.append(t)
            ev_s.append(1 if z[t] > 0 else -1)
            free = t + hold
    ev_t, ev_s = np.array(ev_t, dtype=int), np.array(ev_s, dtype=int)
    return {"t": ev_t, "s": ev_s, "stat": ev_s * stat_all[ev_t] if ev_t.size else np.zeros(0), "stat_all": stat_all, "z": z}


def vol_spread_test(days, iv_a, iv_b, px_a, px_b, window: int = 60, alt_windows: tuple = (40, 120), thr: float = 2.0,
                    hold: int = MONTH, block: int = 2, win_req: float = 0.6, n_boot: int = N_BOOT, seed: int = 0,
                    min_n: int = 30, n_placebo: int = 2000, label: str = "VXN-VIX / QQQ-SPY") -> dict:
    """T-237. Pass: mean event statistic > 0 with the CI excluding zero (two-sided, Bonferroni over the 3 declared
    z-windows: 98.3%), win rate > 0.6, mean > 0 in both halves of the event sequence. n = events."""
    days = list(days)
    ev = vol_spread_events(days, iv_a, iv_b, px_a, px_b, window, thr, hold, block)
    x = ev["stat"]
    n = int(x.size)
    n_decl = 1 + len(alt_windows)
    level = 1.0 - 0.05 / n_decl
    bt = stud_mean(x, block, n_boot, seed)
    ci_d = two_sided(bt, level)
    ci95 = two_sided(bt)
    wr = float((x > 0).mean()) if n else None
    halves = [float(p.mean()) if p.size else None for p in np.array_split(x, 2)] if n >= 2 else [None, None]
    alt = {}
    for w in alt_windows:
        e2 = vol_spread_events(days, iv_a, iv_b, px_a, px_b, w, thr, hold, block)
        alt[str(w)] = {"n": int(e2["stat"].size), "mean": float(e2["stat"].mean()) if e2["stat"].size else None}
    sa = ev["stat_all"]
    bt_u = stud_mean(sa, hold, n_boot, seed) if sa.size >= 8 else None
    plc_p = None
    if n >= 2 and sa.size > n:
        rng = np.random.default_rng(seed + 9)
        sg = ev["s"]
        null = np.array([(sg * sa[rng.choice(sa.size, n, replace=False)]).mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= x.mean()) + 1) / (n_placebo + 1))
    wins = int((x > 0).sum())
    crit = [(f"mean > 0 with the {level:.1%} CI excluding zero (95% deflated for {n_decl} declared z-windows)",
             None if ci_d[0] is None else (bt["est"] > 0 and ci_d[0] > 0), ci_d[1] is not None and ci_d[1] < 0),
            (f"win rate > {win_req}", None if wr is None else wr > win_req, (wins + max(min_n - n, 0)) <= win_req * max(min_n, n)),
            ("mean > 0 in both halves", None if None in halves else all(h > 0 for h in halves), False)]
    verdict, why = _decide(crit, n, min_n, "events")
    first = days[ev["t"][0]] if n else None
    last = days[ev["t"][-1]] if n else None
    reason = (f"{label}: {n} events ({first}..{last}; z-window {window}, |z| > {thr}, non-overlapping {hold}d holds, "
              f"{int((ev['s'] > 0).sum())} wide / {int((ev['s'] < 0).sum())} narrow); mean s[(implied spread) - (realised spread)] "
              f"{_s(bt['est'] if bt else None, 2)} vol pts, {level:.1%} CI {_s(ci_d[0], 2)} to {_s(ci_d[1], 2)} (95% {_s(ci95[0], 2)} to "
              f"{_s(ci95[1], 2)}); win rate {_f(wr, 2)}; halves {_s(halves[0], 2)}/{_s(halves[1], 2)}. Controls: unconditional "
              f"implied-minus-realised spread {_s(bt_u['est'] if bt_u else None, 2)} vol pts ({_ci_s(two_sided(bt_u), 2)}); "
              f"random-entry placebo (matched count and signs) p={_f(plc_p, 3)}; other declared z-windows "
              + ", ".join(f"{w}d {_s(v['mean'], 2)} (n={v['n']})" for w, v in alt.items()))
    return {"n": n, "min_n": min_n, "mean": bt["est"] if bt else None, "ci_deflated": list(ci_d), "ci95": list(ci95),
            "ci_level": level, "win_rate": wr, "halves": halves, "alt_windows": alt, "unconditional_mean": bt_u["est"] if bt_u else None,
            "placebo_p": plc_p, "first_event": first, "last_event": last, "verdict": verdict, "reason": reason + " — " + why}


# ======================================================================== T-239: VIX call overlay (model) ==

def _mdd_rows(R) -> np.ndarray:
    """Maximum drawdown (positive fraction) of compounded per-period returns, row-wise (the equity curve starts at 1)."""
    R = np.atleast_2d(np.asarray(R, dtype=float))
    eq = np.concatenate([np.ones((R.shape[0], 1)), np.cumprod(1.0 + R, axis=1)], axis=1)
    return (1.0 - eq / np.maximum.accumulate(eq, axis=1)).max(axis=1)


def mdd_reduction_boot(r_hedged, r_base, block: int = 12, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """1 - MDD(hedged)/MDD(base) and its PAIRED percentile circular block bootstrap (same cycle blocks for both)."""
    a, b = np.asarray(r_hedged, dtype=float), np.asarray(r_base, dtype=float)
    n = a.size
    ma, mb = float(_mdd_rows(a)[0]), float(_mdd_rows(b)[0])
    out = {"mdd_hedged": ma, "mdd_base": mb, "reduction": 1.0 - ma / mb if mb > 0 else None, "lower_one_sided": None,
           "ci95": [None, None], "block": None}
    if n < 8:
        return out
    bl = _blk(block, n)
    rng = np.random.default_rng(seed)
    red = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, bl, k)
        da, db = _mdd_rows(a[idx]), _mdd_rows(b[idx])
        okm = db > 0
        red.append(1.0 - da[okm] / db[okm])
    red = np.concatenate(red)
    if red.size:
        out.update(lower_one_sided=float(np.quantile(red, 0.05)), ci95=[float(np.quantile(red, 0.025)), float(np.quantile(red, 0.975))])
    out["block"] = bl
    return out


def vix_call_overlay(fr: dict, budget: float = 0.01, hold: int = MONTH, delta: float = 0.25, vvix_scale: float = 1.0) -> dict:
    """Per-cycle returns of SPY (total return) and of SPY with a rolling MODEL-PRICED 25-delta VIX call overlay. ``fr`` needs
    vix, vix3m, vvix, adj, rate, ords. Each cycle (``hold`` sessions, T = calendar days / 365): F_adj = sqrt((93 VIX3M^2 -
    30 VIX^2)/63) exp(-sigma^2 T / 2), sigma = vvix_scale x VVIX / 100, Black-76 call at forward delta ``delta``, payoff
    on spot VIX at expiry (SOQ proxy). A fraction b = budget x hold/252 of the portfolio buys calls, the rest holds SPY."""
    n = len(fr["days"])
    ts = np.arange(0, n - hold, hold)
    b = budget * hold / PPY
    out = {k: [] for k in ("start", "r_spy", "r_hedged", "rf", "prem", "strike", "fwd", "payoff", "fwd_floored")}
    for t in ts:
        e = t + hold
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        r = float(fr["rate"][t])
        v, v3, vv = float(fr["vix"][t]), float(fr["vix3m"][t]), float(fr["vvix"][t])
        sig = max(vvix_scale * vv / 100.0, 0.05)
        fv = (93.0 * v3 * v3 - 30.0 * v * v) / 63.0
        floored = fv <= 0
        fwd = math.sqrt(v * v if floored else fv) * math.exp(-0.5 * sig * sig * T)
        K = b76_call_strike(fwd, T, sig, delta)
        prem = b76_call(fwd, K, T, r, sig)
        pay = max(float(fr["vix"][e]) - K, 0.0)
        r_spy = float(fr["adj"][e] / fr["adj"][t] - 1.0)
        out["start"].append(int(t))
        out["r_spy"].append(r_spy)
        out["r_hedged"].append((1.0 - b) * (1.0 + r_spy) + (b * pay / prem if prem > 0 else 0.0) - 1.0)
        out["rf"].append(math.exp(r * T) - 1.0)
        out["prem"].append(prem)
        out["strike"].append(K)
        out["fwd"].append(fwd)
        out["payoff"].append(pay)
        out["fwd_floored"].append(bool(floored))
    return {k: np.array(v) for k, v in out.items()} | {"budget_per_cycle": b}


def put_hedge_overlay(fr: dict, smile: Optional[Smile], budget: float = 0.01, hold: int = MONTH, delta: float = -0.10) -> dict:
    """Control for T-239: the same budget on a MODEL-PRICED 30-DTE 10-delta SPY put, sigma(K) = VIX/100 x the captured
    SPY smile ratio at K/S (flat VIX/100 without a smile), priced on the dividend forward, settled on the raw close."""
    n = len(fr["days"])
    b = budget * hold / PPY
    rh, ru = [], []
    for t in range(0, n - hold, hold):
        e = t + hold
        S = float(fr["close"][t])
        T = (fr["ords"][e] - fr["ords"][t]) / 365.0
        r = float(fr["rate"][t])
        V = float(fr["vix"][t]) / 100.0
        Sx = S - _pv_div(fr, t, e, r)
        sig = (lambda K: max(V * smile.ratio(K / S, 30), 0.01)) if smile is not None else (lambda K: max(V, 0.01))
        K = strike_for_delta_smile(Sx, T, r, 0.0, sig, delta, "put", 0.2 * Sx, Sx)
        r_spy = float(fr["adj"][e] / fr["adj"][t] - 1.0)
        if K is None:
            rh.append(r_spy)
        else:
            prem = _bs(Sx, K, T, r, 0.0, sig(K), "put")
            pay = max(K - float(fr["close"][e]), 0.0)
            rh.append((1.0 - b) * (1.0 + r_spy) + (b * pay / prem if prem > 0 else 0.0) - 1.0)
        ru.append(r_spy)
    return {"r_hedged": np.array(rh), "r_spy": np.array(ru)}


def vix_hedge_test(fr: dict, smile: Optional[Smile] = None, budget: float = 0.01, hold: int = MONTH, target: float = 0.25,
                   block: int = 12, scales: tuple = (0.8, 1.2), n_boot: int = N_BOOT, seed: int = 0, min_n: int = 180) -> dict:
    """T-239. Pass: one-sided 95% lower bound of 1 - MDD(hedged)/MDD(SPY) > ``target`` (paired percentile bootstrap of
    12-cycle blocks). The Sharpe difference (excess of the bill) is reported, not required. n = monthly cycles."""
    ov = vix_call_overlay(fr, budget, hold)
    n = int(ov["start"].size)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} monthly cycles — too few to test"}
    mr = mdd_reduction_boot(ov["r_hedged"], ov["r_spy"], block, n_boot, seed)
    ppy = PPY / hold
    sh_h, sh_u = sharpe_ratio(ov["r_hedged"] - ov["rf"], ppy), sharpe_ratio(ov["r_spy"] - ov["rf"], ppy)
    hedge_pnl = ov["budget_per_cycle"] * (ov["payoff"] / ov["prem"] - 1.0)
    sens = {}
    for s in scales:
        o2 = vix_call_overlay(fr, budget, hold, vvix_scale=s)
        sens[str(s)] = float(1.0 - _mdd_rows(o2["r_hedged"])[0] / _mdd_rows(o2["r_spy"])[0])
    ph = put_hedge_overlay(fr, smile, budget, hold)
    put_red = float(1.0 - _mdd_rows(ph["r_hedged"])[0] / _mdd_rows(ph["r_spy"])[0])
    b = ov["budget_per_cycle"]
    cash = (1.0 - b) * (1.0 + ov["r_spy"]) + b * (1.0 + ov["rf"]) - 1.0
    cash_red = float(1.0 - _mdd_rows(cash)[0] / _mdd_rows(ov["r_spy"])[0])
    lb, ci = mr["lower_one_sided"], mr["ci95"]
    crit = [(f"one-sided 95% lower bound of the drawdown reduction > {target:.0%}", None if lb is None else lb > target,
             ci[1] is not None and ci[1] < target)]
    verdict, why = _decide(crit, n, min_n, "monthly cycles")
    days = fr["days"]
    reason = (f"{MP} (Black-76 on F_adj = sqrt((93 VIX3M^2 - 30 VIX^2)/63) exp(-VVIX^2 T/2), sigma = VVIX/100, 25-delta strike, "
              f"payoff on spot VIX at expiry): {n} monthly cycles {days[ov['start'][0]]}..{days[ov['start'][-1] + hold]}, budget "
              f"{budget:.0%}/yr ({b*100:.3f}% per cycle); SPY total-return MDD {mr['mdd_base']*100:.1f}% vs hedged "
              f"{mr['mdd_hedged']*100:.1f}%: reduction {_s(None if mr['reduction'] is None else mr['reduction']*100, 1)}%, one-sided 95% "
              f"lower bound {_s(None if lb is None else lb*100, 1)}% (two-sided {_ci_s(tuple(None if x is None else x*100 for x in ci), 1)}) vs "
              f"{target:.0%}; Sharpe (excess of the bill) hedged {sh_h:.2f} vs SPY {sh_u:.2f} (difference {sh_h - sh_u:+.2f}, reported); hedge P&L "
              f"{hedge_pnl.mean()*1e4:+.2f} bp of the portfolio per cycle, calls paid in {int((ov['payoff'] > 0).sum())} of {n} cycles. "
              f"IV-scale sensitivity (VVIX x " + ", ".join(f"{k}: {v*100:+.1f}%" for k, v in sens.items()) + "). Controls: 10-delta SPY put "
              f"same budget ({'captured SPY smile' if smile is not None else 'flat VIX'}) reduction {put_red*100:+.1f}%; cash drag at the same budget "
              f"{cash_red*100:+.1f}%" + (f"; {int(ov['fwd_floored'].sum())} cycles with a negative forward variance used VIX" if ov['fwd_floored'].any() else "")
              + ". The traded version needs VIX option chain history (2 capture days archived)")
    return {"n": n, "min_n": min_n, "reduction": mr["reduction"], "lower_one_sided": lb, "ci95": ci, "mdd_spy": mr["mdd_base"],
            "mdd_hedged": mr["mdd_hedged"], "sharpe_hedged": sh_h, "sharpe_spy": sh_u, "hedge_pnl_per_cycle": float(hedge_pnl.mean()),
            "scale_sensitivity": sens, "put_control_reduction": put_red, "cash_drag_reduction": cash_red, "block": mr["block"],
            "verdict": verdict, "reason": reason + " — " + why}


# =========================================================================== T-240: VVIX vs realised VIX vol ==

def vvix_win_rate(days, vvix, vix, window: int = MONTH, bound: float = 0.70, block: int = 6, n_boot: int = N_BOOT,
                  seed: int = 0, min_n: int = 200, spx=None, n_placebo: int = 1000) -> dict:
    """T-240 on aligned daily arrays. Non-overlapping windows from the first day: win_t = 1{VVIX_t > 100 sqrt(252)
    sd(dlnVIX over t..t+21)} (21 changes, ddof 1). Pass: the one-sided 95% lower bound of the win rate > ``bound`` under
    BOTH the exact binomial (Clopper-Pearson) and a percentile block bootstrap (block 6 windows); mean premium VVIX - realised
    > 0 in both halves. ``spx`` (aligned closes) adds the SPX VRP win-rate control. n = windows."""
    days = list(days)
    vvix, vix = np.asarray(vvix, dtype=float), np.asarray(vix, dtype=float)
    lr = np.diff(np.log(vix))
    ts = np.arange(0, len(days) - window, window)
    if ts.size < 8:
        return {"n": int(ts.size), "verdict": "inconclusive", "reason": f"only {ts.size} windows — too few to test"}
    rv = np.array([100.0 * math.sqrt(PPY) * float(np.std(lr[t:t + window], ddof=1)) for t in ts])
    win = (vvix[ts] > rv).astype(float)
    k, n = int(win.sum()), int(ts.size)
    cp1 = _binom_two_sided_ci(k, n, 0.10)
    cp2 = _binom_two_sided_ci(k, n, 0.05)
    boot = pct_means(win, block, n_boot, seed)
    b_lo1 = float(np.quantile(boot, 0.05))
    lb = min(cp1[0], b_lo1)
    prem = vvix[ts] - rv
    halves = [float(p.mean()) for p in np.array_split(prem, 2)]
    hw = [float(p.mean()) for p in np.array_split(win, 2)]
    spx_wr = None
    if spx is not None:
        lrs = np.diff(np.log(np.asarray(spx, dtype=float)))
        rvs = np.array([float(np.sum(lrs[t:t + window] ** 2)) * PPY / window for t in ts])
        spx_wr = float(((vix[ts] / 100.0) ** 2 > rvs).mean())
    rng = np.random.default_rng(seed + 13)
    plc = float(np.mean([(rng.permutation(vvix[ts]) > rv).mean() for _ in range(n_placebo)]))
    crit = [(f"one-sided 95% lower bound of the win rate > {bound:.2f} (min of Clopper-Pearson and block bootstrap)", lb > bound,
             max(cp1[1], float(np.quantile(boot, 0.95))) < bound),
            ("mean premium VVIX - realised > 0 in both halves", all(h > 0 for h in halves), False)]
    verdict, why = _decide(crit, n, min_n, "non-overlapping 21d windows")
    reason = (f"VVIX above the realised 21d vol of daily log changes in spot VIX in {k} of {n} non-overlapping windows "
              f"({days[ts[0]]}..{days[ts[-1]]}): win rate {k/n:.3f}, one-sided 95% lower bound Clopper-Pearson {cp1[0]:.3f} / "
              f"block bootstrap {b_lo1:.3f} (two-sided exact {cp2[0]:.3f}-{cp2[1]:.3f}) vs {bound:.2f}; mean premium "
              f"{prem.mean():+.1f} vol pts, halves {halves[0]:+.1f}/{halves[1]:+.1f} (win rates {hw[0]:.2f}/{hw[1]:.2f}). Controls: "
              f"SPX VRP win rate (VIX^2 > RV) on the same windows {_f(spx_wr, 3)}; shuffled-VVIX placebo win rate {plc:.3f}. "
              "Spot VIX moves more than the futures VVIX refers to, so the comparison is conservative for the claim")
    return {"n": n, "min_n": min_n, "wins": k, "win_rate": k / n, "cp_lower_one_sided": cp1[0], "cp_two_sided": list(cp2),
            "boot_lower_one_sided": b_lo1, "lower_bound": lb, "mean_premium": float(prem.mean()), "premium_halves": halves,
            "win_rate_halves": hw, "spx_vrp_win_rate": spx_wr, "placebo_win_rate": plc, "first_window": days[ts[0]],
            "last_window": days[ts[-1]], "verdict": verdict, "reason": reason + " — " + why}


def vix_call_ratio_secondary(days, vix, vix3m, vvix, rate, hold: int = MONTH, k1_off: float = 4.0, k2_off: float = 10.0,
                             block: int = 6, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """T-240 secondary: MODEL-PRICED 1x2 VIX call ratio (long 1 at F_adj + 4, short 2 at K1 + 10), Black-76 on F_adj with
    VVIX as IV, settled on spot VIX; P&L in VIX points per cycle (premium received / paid carried at the bill)."""
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    pnl = []
    for t in range(0, len(days) - hold, hold):
        e = t + hold
        T = (ords[e] - ords[t]) / 365.0
        sig = max(vvix[t] / 100.0, 0.05)
        fv = (93.0 * vix3m[t] ** 2 - 30.0 * vix[t] ** 2) / 63.0
        F = math.sqrt(fv if fv > 0 else vix[t] ** 2) * math.exp(-0.5 * sig * sig * T)
        k1 = F + k1_off
        k2 = k1 + k2_off
        debit = b76_call(F, k1, T, rate[t], sig) - 2.0 * b76_call(F, k2, T, rate[t], sig)
        V = vix[e]
        pnl.append(max(V - k1, 0.0) - 2.0 * max(V - k2, 0.0) - debit * math.exp(rate[t] * T))
    x = np.array(pnl)
    bt = stud_mean(x, block, n_boot, seed)
    return {"n": int(x.size), "mean": float(x.mean()) if x.size else None, "ci95": list(two_sided(bt))}


# ==================================================================== T-249: forward vs spot variance premium ==

def forward_variance_premium(days, px, vix, vix3m, cycle: int = 63, block_daily: int = 63, block_cycle: int = 2,
                             n_boot: int = N_BOOT, seed: int = 0, min_n: int = 60, excl_year: str = "2020",
                             n_shift: int = 500) -> dict:
    """T-249 on aligned daily arrays (px dividend-adjusted). F^2 = (93 VIX3M^2 - 30 VIX^2)/63; forward premium fraction
    (F^2 - RV(22..63))/F^2, spot (VIX^2 - RV(1..21))/VIX^2; d = forward - spot. Pass: d > 0 with the two-sided 95% CI
    excluding zero, on the non-overlapping 63-day cycles (studentized, block 2) AND on all daily starts (studentized,
    block 63 = the overlap). The forward win rate (> 0.7) is reported, as the pass rule marks it. n = 63-day cycles."""
    days = list(days)
    px, vix, vix3m = (np.asarray(a, dtype=float) for a in (px, vix, vix3m))
    n = len(days) - 63
    if n < 100:
        return {"n": 0, "verdict": "inconclusive", "reason": f"only {max(n, 0)} aligned days with a 63-day forward window — too few to test"}
    lr = np.diff(np.log(px))
    rv_s, rv_f = _fwd_rv(lr, n, 1, 21), _fwd_rv(lr, n, 22, 63)

    def parts(v3):
        v2 = (vix[:n] / 100.0) ** 2
        f2 = (93.0 * (v3[:n] / 100.0) ** 2 - 30.0 * v2) / 63.0
        okm = f2 > 0
        pf = np.where(okm, (f2 - rv_f) / np.where(okm, f2, 1.0), np.nan)
        ps = (v2 - rv_s) / v2
        return f2, v2, okm, pf, ps

    f2, v2, okm, pf, ps = parts(vix3m)
    d = pf - ps
    cyc = np.arange(0, n, cycle)
    cyc = cyc[okm[cyc]]
    didx = np.nonzero(okm)[0]
    bt_c = stud_mean(d[cyc], block_cycle, n_boot, seed)
    bt_d = stud_mean(d[didx], block_daily, n_boot, seed)
    ci_c, ci_d = two_sided(bt_c), two_sided(bt_d)
    nc = int(cyc.size)
    win = float((f2[cyc] > rv_f[cyc]).mean()) if nc else None
    halves = [float(p.mean()) for p in np.array_split(d[cyc], 2)] if nc >= 2 else [None, None]
    keep = np.array([not days[i].startswith(excl_year) for i in cyc], dtype=bool)
    ex = float(d[cyc][keep].mean()) if keep.any() else None
    lvl = (f2 - rv_f) - (v2 - rv_s)
    bt_l = stud_mean(lvl[cyc], block_cycle, n_boot, seed)
    rng = np.random.default_rng(seed + 17)
    null = []
    for _ in range(n_shift):
        s = int(rng.integers(252, max(253, len(days) - 252)))
        _, _, ok2, pf2, ps2 = parts(np.roll(vix3m, s))
        c2 = np.arange(0, n, cycle)
        c2 = c2[ok2[c2]]
        if c2.size:
            null.append(float(np.mean(pf2[c2] - ps2[c2])))
    null = np.asarray(null)
    plc_p = float((np.sum(null >= bt_c["est"]) + 1) / (null.size + 1)) if (null.size and bt_c) else None
    crit = [("non-overlapping 63d cycles: paired difference > 0 with the 95% CI excluding zero",
             None if ci_c[0] is None else (bt_c["est"] > 0 and ci_c[0] > 0), ci_c[1] is not None and ci_c[1] < 0),
            ("all daily starts (63-day blocks): paired difference > 0 with the 95% CI excluding zero",
             None if ci_d[0] is None else (bt_d["est"] > 0 and ci_d[0] > 0), ci_d[1] is not None and ci_d[1] < 0)]
    verdict, why = _decide(crit, nc, min_n, "non-overlapping 63d cycles")
    reason = (f"forward premium fraction (F^2 - RV22..63)/F^2 minus spot (VIX^2 - RV1..21)/VIX^2 over {nc} non-overlapping 63d "
              f"cycles ({days[cyc[0]]}..{days[cyc[-1]]}): mean {_s(bt_c['est'] if bt_c else None, 3)} ({_ci_s(ci_c, 3)}); all "
              f"{didx.size} daily starts {_s(bt_d['est'] if bt_d else None, 3)} ({_ci_s(ci_d, 3)}); mean forward fraction "
              f"{np.nanmean(pf[cyc]):+.3f} vs spot {np.mean(ps[cyc]):+.3f}; forward win rate (F^2 > RV22..63) {_f(win, 2)} "
              f"(reported; the pass marks the 0.7 line as reported). Walk-forward halves {_s(halves[0], 3)}/{_s(halves[1], 3)}; "
              f"excluding {excl_year} {_s(ex, 3)}; level version (variance units) {_s(bt_l['est'] if bt_l else None, 4)} "
              f"({_ci_s(two_sided(bt_l), 4)}); shifted-VIX3M placebo p={_f(plc_p, 3)}"
              + (f"; {int((~okm).sum())} days with F^2 <= 0 excluded" if (~okm).any() else ""))
    return {"n": nc, "min_n": min_n, "mean_cycles": bt_c["est"] if bt_c else None, "ci_cycles": list(ci_c),
            "mean_daily": bt_d["est"] if bt_d else None, "ci_daily": list(ci_d), "n_daily": int(didx.size),
            "forward_win_rate": win, "halves": halves, "excl_year_mean": ex, "level_mean": bt_l["est"] if bt_l else None,
            "level_ci": list(two_sided(bt_l)), "placebo_p": plc_p, "first_cycle": days[cyc[0]], "last_cycle": days[cyc[-1]],
            "verdict": verdict, "reason_core": reason, "why": why}


def variance_strip(vals, expiry: str, quote_day: str, r: float, roots=("SPXW", "SPX")) -> Optional[dict]:
    """Model-free (CBOE VIX-method) implied variance of one captured expiry: F by put-call parity, K0 the first strike at or
    below F, out-of-the-money mids walked outward until two consecutive zero bids, sigma^2 = 2/T sum dK/K^2 e^{rT} Q(K) -
    (F/K0 - 1)^2 / T. T = calendar days / 365 from the quote day (settlement-time detail ignored)."""
    T = (date.fromisoformat(expiry) - date.fromisoformat(quote_day)).days / 365.0
    if T <= 0:
        return None
    root, by = _chain_by_strike(vals, expiry, roots)
    fw = _parity_forward(by, T, r)
    if fw is None:
        return None
    F, _ = fw
    ks = sorted(by)
    below = [K for K in ks if K <= F]
    if not below:
        return None
    K0 = below[-1]
    sel = {}
    for side, seq in (("put", [K for K in reversed(ks) if K < K0]), ("call", [K for K in ks if K > K0])):
        zeros = 0
        for K in seq:
            row = by[K].get(side)
            if not row or not (row.get("bid") or 0) > 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            m = _mid(row)
            if m is not None:
                sel[K] = m
    c0, p0 = _mid(by[K0].get("call")), _mid(by[K0].get("put"))
    if c0 is None or p0 is None:
        return None
    sel[K0] = 0.5 * (c0 + p0)
    kk = sorted(sel)
    if len(kk) < 5:
        return None
    tot = 0.0
    for i, K in enumerate(kk):
        dK = (kk[min(i + 1, len(kk) - 1)] - kk[max(i - 1, 0)]) / (2.0 if 0 < i < len(kk) - 1 else 1.0)
        tot += dK / (K * K) * math.exp(r * T) * sel[K]
    var = 2.0 / T * tot - (F / K0 - 1.0) ** 2 / T
    return {"expiry": expiry, "root": root, "T": T, "days": int(round(T * 365)), "forward": F, "K0": K0, "n_strikes": len(kk), "var": var}


def _bracket(strips: list, target: int) -> tuple:
    lo = [s["days"] for s in strips if s["days"] <= target]
    hi = [s["days"] for s in strips if s["days"] >= target]
    return tuple(x for x in (lo[-1] if lo else None, hi[0] if hi else None) if x is not None)


def strip_check(vals, quote_day: str, r: float, vix_q: Optional[float], vix3m_q: Optional[float]) -> Optional[dict]:
    """Strip discretisation check (T-249 procedure): strip variances interpolated (CBOE's linear-in-time total variance) to
    30 and 93 calendar days and compared with the VIX and VIX3M closes of the quote day, plus the 30-to-93-day forward."""
    qd = date.fromisoformat(quote_day)
    exps = sorted({v.get("expiry") for v in vals if v.get("expiry") and (date.fromisoformat(v["expiry"]) - qd).days >= 7})
    strips = [s for s in (variance_strip(vals, e, quote_day, r) for e in exps if (date.fromisoformat(e) - qd).days <= 130) if s and s["var"] > 0]

    def interp(target):
        lo = [s for s in strips if s["days"] <= target]
        hi = [s for s in strips if s["days"] >= target]
        if not lo or not hi:
            return None
        a, b = lo[-1], hi[0]
        if a["days"] == b["days"]:
            return a["var"]
        w = (b["days"] - target) / (b["days"] - a["days"])
        return (a["T"] * a["var"] * w + b["T"] * b["var"] * (1 - w)) * 365.0 / target
    v30, v93 = interp(30), interp(93)
    if v30 is None or v93 is None:
        return None
    out = {"quote_day": quote_day, "n_expiries": len(strips), "strip_30": 100 * math.sqrt(v30), "strip_93": 100 * math.sqrt(v93),
           "vix": vix_q, "vix3m": vix3m_q,
           "strikes_30": [s["n_strikes"] for s in strips if s["days"] in _bracket(strips, 30)],
           "strikes_93": [s["n_strikes"] for s in strips if s["days"] in _bracket(strips, 93)]}
    out["err_30"] = None if vix_q is None else out["strip_30"] - vix_q
    out["err_93"] = None if vix3m_q is None else out["strip_93"] - vix3m_q
    f2_s = (93 * v93 - 30 * v30) / 63
    out["fwd_strip"] = 100 * math.sqrt(f2_s) if f2_s > 0 else None
    if vix_q is not None and vix3m_q is not None:
        f2_i = (93 * vix3m_q ** 2 - 30 * vix_q ** 2) / 63
        out["fwd_index"] = math.sqrt(f2_i) if f2_i > 0 else None
    return out


# ======================================================================== T-511: weekend vs weekday variance ==

def _week_stats(days, px, winsor: Optional[float] = None) -> dict:
    """Per-ISO-week sufficient statistics of SPY close-to-close log returns labelled by calendar gap: weekend (Fri -> Mon,
    3 days) and weekday single nights (gap 1, starting Mon..Thu); holiday gaps are excluded. A return belongs to the week
    of its end day. With ``winsor`` the returns are clipped at that quantile of |r| (over the labelled returns)."""
    ords = np.array([date.fromisoformat(d).toordinal() for d in days])
    lr = np.diff(np.log(np.asarray(px, dtype=float)))
    gap = np.diff(ords)
    wd0 = np.array([date.fromordinal(int(o)).weekday() for o in ords[:-1]])
    we = (gap == 3) & (wd0 == 4)
    wk = (gap == 1) & (wd0 <= 3)
    hol = (gap >= 4) & (gap <= 5)
    used = we | wk
    if winsor is not None and used.any():
        cap = float(np.quantile(np.abs(lr[used]), winsor))
        lr = np.clip(lr, -cap, cap)
    keys = [date.fromordinal(int(o)).isocalendar()[:2] for o in ords[1:]]
    uk = sorted(set(keys[i] for i in np.nonzero(used)[0]))
    pos = {k: i for i, k in enumerate(uk)}
    W = len(uk)
    S = np.zeros((W, 15))      # weekend n, s, ss; then weekday k=0..3: n, s, ss
    for i in np.nonzero(used)[0]:
        w = pos[keys[i]]
        c = 0 if we[i] else 3 + 3 * int(wd0[i])
        S[w, c] += 1.0
        S[w, c + 1] += lr[i]
        S[w, c + 2] += lr[i] ** 2
    return {"S": S, "weeks": uk, "n_weekend": int(we.sum()), "n_weekday": int(wk.sum()),
            "holiday_var": float(np.var(lr[hol], ddof=1)) if hol.sum() > 1 else None, "n_holiday": int(hol.sum())}


def _ratio_from(S) -> np.ndarray:
    """Variance ratio from summed sufficient statistics (rows): Var(weekend) / mean over k of Var(weekday k)."""
    S = np.atleast_2d(S)

    def var(n, s, ss):
        return (ss - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1)
    num = var(S[:, 0], S[:, 1], S[:, 2])
    den = np.mean([var(S[:, 3 + 3 * k], S[:, 4 + 3 * k], S[:, 5 + 3 * k]) for k in range(4)], axis=0)
    return num / np.where(den > 0, den, np.nan)


def weekend_ratio_boot(S: np.ndarray, block: int = 4, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """R and its percentile circular block bootstrap over weeks (blocks of ``block`` weeks)."""
    W = S.shape[0]
    R = float(_ratio_from(S.sum(axis=0))[0]) if W else None
    out = {"R": R, "ci95": [None, None], "n_weeks": int(W)}
    if W < 8:
        return out
    b = _blk(block, W)
    rng = np.random.default_rng(seed)
    rs = []
    for k in _chunks(n_boot, W):
        idx = _boot_idx(rng, W, b, k)
        cnt = np.zeros((k, W))
        np.add.at(cnt, (np.repeat(np.arange(k), W), idx.ravel()), 1.0)
        rs.append(_ratio_from(cnt @ S))
    rs = np.concatenate(rs)
    rs = rs[np.isfinite(rs)]
    if rs.size:
        out["ci95"] = [float(np.quantile(rs, 0.025)), float(np.quantile(rs, 0.975))]
    return out


def weekend_variance_ratio(days, px, bound: float = 1.5, block_weeks: int = 4, n_boot: int = N_BOOT, seed: int = 0,
                           min_n: int = 1500, winsor: float = 0.99, raw_px=None) -> dict:
    """T-511. R = Var(Fri close -> Mon close) / mean over Mon..Thu starts of Var(single-night close -> next close). Pass:
    the upper end of the two-sided 95% CI of R < ``bound`` overall (the claim) and in both walk-forward halves (the pass
    rule); percentile bootstrap of 4-week blocks of weeks. n = weekend returns."""
    days = list(days)
    st = _week_stats(days, px)
    S = st["S"]
    W = S.shape[0]
    if W < 16:
        return {"n": st["n_weekend"], "verdict": "inconclusive", "reason": f"only {W} weeks of labelled returns — too few to test"}
    full = weekend_ratio_boot(S, block_weeks, n_boot, seed)
    h = W // 2
    hs = [weekend_ratio_boot(S[:h], block_weeks, n_boot, seed), weekend_ratio_boot(S[h:], block_weeks, n_boot, seed)]
    hl = [f"{st['weeks'][0][0]}w{st['weeks'][0][1]}..{st['weeks'][h - 1][0]}w{st['weeks'][h - 1][1]}",
          f"{st['weeks'][h][0]}w{st['weeks'][h][1]}..{st['weeks'][-1][0]}w{st['weeks'][-1][1]}"]
    one = weekend_ratio_boot(S, 1, n_boot, seed)
    wz = _week_stats(days, px, winsor)
    r_w = float(_ratio_from(wz["S"].sum(axis=0))[0])
    r_raw = None
    if raw_px is not None:
        r_raw = float(_ratio_from(_week_stats(days, raw_px)["S"].sum(axis=0))[0])
    tot = S.sum(axis=0)
    wd_var = float(np.mean([(tot[5 + 3 * k] - tot[4 + 3 * k] ** 2 / tot[3 + 3 * k]) / (tot[3 + 3 * k] - 1) for k in range(4)]))
    hol_ratio = st["holiday_var"] / wd_var if st["holiday_var"] is not None and wd_var > 0 else None
    n = st["n_weekend"]

    def crit_for(lab, b):
        lo, hi = b["ci95"]
        return (f"{lab}: upper end of the 95% CI of R < {bound}", None if hi is None else hi < bound, lo is not None and lo >= bound)
    crit = [crit_for("full sample (the claim)", full), crit_for(f"first half {hl[0]}", hs[0]), crit_for(f"second half {hl[1]}", hs[1])]
    verdict, why = _decide(crit, n, min_n, "Fri->Mon weekend returns")
    reason = (f"SPY (dividend-adjusted) Fri->Mon variance / mean Mon..Thu single-night variance: R {full['R']:.3f} "
              f"({_ci_s(full['ci95'], 3)}) over {n} normal weekends and {st['n_weekday']} weekday nights ({days[0]}..{days[-1]}, "
              f"holiday gaps excluded); halves {hs[0]['R']:.3f} ({_ci_s(hs[0]['ci95'], 3)}) and {hs[1]['R']:.3f} ({_ci_s(hs[1]['ci95'], 3)}) "
              f"vs {bound} (blocks of {block_weeks} weeks; with 1-week blocks the full-sample {_ci_s(one['ci95'], 3)}). Robustness: top "
              f"{100 - winsor * 100:.0f}% |returns| winsorised R {r_w:.3f}; raw closes R {_f(r_raw, 3)}; "
              f"holiday gaps (4-5 days, n={st['n_holiday']}) variance ratio {_f(hol_ratio, 3)}. Calendar-day pricing charges 3x; whether "
              "listed options do is the separate capture-driven check (Friday-close vs Monday ATM straddle marks), not tested here")
    return {"n": n, "min_n": min_n, "R": full["R"], "ci95": full["ci95"], "halves": [{"label": l, **b} for l, b in zip(hl, hs)],
            "n_weekday": st["n_weekday"], "ci95_one_week_blocks": one["ci95"], "R_winsorised": r_w, "R_raw": r_raw, "holiday_ratio": hol_ratio,
            "verdict": verdict, "reason": reason + " — " + why}


# ============================================================ T-538: implied vs realised average correlation ==

def realised_avg_corr(R: np.ndarray, w: Optional[np.ndarray] = None) -> float:
    """sum_{i != j} w_i w_j s_i s_j rho_ij / sum_{i != j} w_i w_j s_i s_j over the columns of R (rows = days): the
    realised analogue of the CBOE implied-correlation formula with the index variance of the w-weighted basket."""
    R = np.asarray(R, dtype=float)
    k = R.shape[1]
    w = np.full(k, 1.0 / k) if w is None else np.asarray(w, dtype=float)
    C = np.cov(R, rowvar=False, ddof=1)
    s = np.sqrt(np.diag(C))
    ws = w * s
    num = float(w @ C @ w - np.sum(ws ** 2))
    den = float(np.sum(ws) ** 2 - np.sum(ws ** 2))
    return num / den if den > 0 else float("nan")


def implied_vs_realised_corr(days, cor1m, comps: np.ndarray, names: Sequence[str], hold: int = MONTH, block: int = 6,
                             n_boot: int = N_BOOT, seed: int = 0, min_n: int = 240, start: str = "2006-01-01",
                             constituents: bool = False) -> dict:
    """T-538 on aligned daily arrays: COR1M (index points) and component closes (k x n, dividend-adjusted). Non-overlapping
    21-day windows from ``start``: gap = COR1M_t/100 - realised average correlation over t+1..t+21 (equal weights).
    With ``constituents`` False the components are a proxy, and the claim's statistic (the index constituents) and its
    straddle-book clause are not implemented; the proxy's interval is reported as a one-sided bound."""
    days = list(days)
    cor1m = np.asarray(cor1m, dtype=float)
    comps = np.asarray(comps, dtype=float)
    lr = np.diff(np.log(comps), axis=1)
    t0 = next((i for i, d in enumerate(days) if d >= start), len(days))
    ts = np.arange(t0, len(days) - hold, hold)
    if ts.size < 8:
        return {"n": int(ts.size), "verdict": "inconclusive", "reason": f"only {ts.size} monthly windows — too few to test"}
    rho = np.array([realised_avg_corr(lr[:, t:t + hold].T) for t in ts])
    gap = cor1m[ts] / 100.0 - rho
    bt = stud_mean(gap, block, n_boot, seed)
    ci = two_sided(bt)
    n = int(ts.size)
    halves = [float(p.mean()) for p in np.array_split(gap, 2)]
    if constituents:
        crit = [("lower 95% CI bound of mean(COR1M - realised constituent correlation) > 0", ci[0] > 0, ci[1] < 0)]
    else:
        crit = [(f"proxy ({len(names)} sector SPDRs) lower 95% CI bound > 0 (a sector proxy bounds the claim from one side "
                 "only: sector correlations exceed constituent ones, so a proxy shortfall is not a failure)",
                 True if ci[0] > 0 else None, False),
                ("realised average correlation of the index constituents (COR1M's top-50 S&P 500 names, cap-weighted): "
                 "constituent closes and weights are not archived", None, False)]
    crit.append(("vega-neutral short-index / long-constituent straddle book has positive mean P&L: needs index and "
                 "single-stock chain history", None, False))
    verdict, why = _decide(crit, n, min_n, "monthly windows")
    reason = (f"COR1M averages {cor1m[ts].mean():.1f} vs realised equal-weight average pairwise correlation of "
              f"{'the constituents' if constituents else 'the ' + str(len(names)) + ' sector SPDRs (' + '/'.join(names) + ')'} "
              f"{rho.mean()*100:.1f} over {n} non-overlapping 21d windows ({days[ts[0]]}..{days[ts[-1]]}); mean gap "
              f"{bt['est']*100:+.1f} pts ({_ci_s(tuple(x*100 for x in ci), 1)}), halves {halves[0]*100:+.1f}/{halves[1]*100:+.1f}")
    if not constituents:
        reason += (". Proxy verdict: NOT an acceptable stand-in under the claim's wording ('the index constituents'): sector "
                   "baskets diversify away idiosyncratic risk, so their pairwise correlation is far above single-stock "
                   "correlation (the gap above is dominated by that bias, not by the correlation premium); XLC/XLRE and "
                   "cap weights are also missing, so the verdict is capped at inconclusive")
    return {"n": n, "min_n": min_n, "mean_cor1m": float(cor1m[ts].mean() / 100), "mean_realised": float(rho.mean()),
            "mean_gap": bt["est"], "ci95": list(ci), "halves": halves, "components": list(names), "proxy": not constituents,
            "first_window": days[ts[0]], "last_window": days[ts[-1]], "verdict": verdict, "reason": reason + " — " + why}


# ==================================================================================================== harnesses ==

def b6_surf_vrp_term_regime(archive):
    """T-159: within each VIX tercile, SPY 21-day VRP higher in contango (< 0.95) than backwardation (> 1.05)."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B, DTB3_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    vix, v3 = _index(archive, VIX_B), _index(archive, VIX3M_B)
    keep = [d for d in sd if d in vix and d in v3 and d >= "2007-12-04"]
    pos = {d: i for i, d in enumerate(sd)}
    adj = np.array([sa[pos[d]] for d in keep])
    rep = vrp_regime(keep, adj, [vix[d] for d in keep], [v3[d] for d in keep])
    if "reason_core" not in rep:
        return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])
    fr = frame_on(sd, sc, sa, keep, _series(archive, DTB3_B), {"vix": vix})
    ratio = np.array([vix[d] / v3[d] for d in keep])
    sec = {}
    for s in (1.0, 0.81):
        cy = short_strangle_cycles(fr, s)
        rr = ratio[cy["start"]]
        c, b = cy["pnl"][rr < 0.95], cy["pnl"][rr > 1.05]
        sec[str(s)] = {"n_contango": int(c.size), "n_backwardation": int(b.size),
                       "mean_contango_bp": float(c.mean() * 1e4) if c.size else None,
                       "mean_backwardation_bp": float(b.mean() * 1e4) if b.size else None}
    rep["strangle_secondary"] = sec
    s1, s8 = sec["1.0"], sec["0.81"]
    reason = (f"21d SPY VRP (VIX^2 - next-21d realised variance) by VIX/VIX3M regime within VIX terciles, {rep['n_days']} daily "
              f"entries {rep['first_day']}..{rep['last_entry']} (the archive's VIX3M starts 2009-09-18, so the procedure's "
              f"2007-12-04..2009-09-17, including 2008, is not in the sample; the 'with 2008' control cannot be run); backwardation "
              f"(> 1.05) on {rep['share_backwardation']*100:.1f}% of days, contango (< 0.95) on {rep['share_contango']*100:.1f}%. "
              f"{rep['reason_core']}. Excluding 2020: " + "/".join(_s(None if r.get('diff_var_ex_2020') is None else r['diff_var_ex_2020'] * 1e4, 1) for r in rep['terciles'])
              + f" %^2. Secondary ({MP} short 16-delta 30-DTE strangle, flat smile, P&L per spot): contango "
              f"{_s(s1['mean_contango_bp'], 1)} bp (n={s1['n_contango']}) vs backwardation {_s(s1['mean_backwardation_bp'], 1)} bp "
              f"(n={s1['n_backwardation']}) at IV = VIX; at 0.81 x VIX {_s(s8['mean_contango_bp'], 1)} vs {_s(s8['mean_backwardation_bp'], 1)} bp "
              f"(the short-premium level hinges on the IV scale; the traded version needs SPY chain history)")
    rep.pop("reason_core")
    why = rep.pop("why")
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + why)


def _gspc_skew_vix(archive):
    gd, gc, _ = _daily(archive, GSPC_B)
    sk, vx = _index(archive, SKEW_B), _index(archive, VIX_B)
    keep = [i for i, d in enumerate(gd) if d in sk and d in vx]
    days = [gd[i] for i in keep]
    return days, gc[keep], np.array([sk[d] for d in days]), np.array([vx[d] for d in days])


def b6_surf_skew_tail_frequency(archive):
    """T-227: high-SKEW windows do not carry >= 1 pp more -2 VIX-sigma 21-day ^GSPC drops than low-SKEW windows."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B])
    if miss:
        return miss
    days, c, sk, vx = _gspc_skew_vix(archive)
    rep = skew_tail_frequency(days, c, sk, vx)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_skew_implied_tail_gap(archive):
    """T-228: SKEW-implied 2-sigma probability exceeds the realised 21-day frequency by more than 2 pp."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B])
    if miss:
        return miss
    days, c, sk, vx = _gspc_skew_vix(archive)
    rep = skew_implied_gap(days, c, sk, vx)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_skew_cheap_put_spread(archive):
    """T-229: MODEL-PRICED 25d/10d SPX put spread bought in cheap-SKEW months vs every month (payoff / debit)."""
    miss = _missing(archive, [GSPC_B, SKEW_B, VIX_B, DTB3_B, SPY_B, KAPPA_CHAIN])
    if miss:
        return miss
    days, c, sk, vx = _gspc_skew_vix(archive)
    dtb3 = _series(archive, DTB3_B)
    rate = bill_rates(days, dtb3)
    sd, sc, sa = _daily(archive, SPY_B)
    qy_spy = trailing_yield(sd, sc, sa)
    qy = np.array([qy_spy[max(bisect_right(sd, d) - 1, 0)] for d in days])      # SPY's yield known at that close
    chain = _rows(archive, KAPPA_CHAIN, filtered=False)
    qd = _quote_day(chain[0].get("available_at", "") if chain else "", days)
    sk_all, vx_all = _index(archive, SKEW_B, filtered=False), _index(archive, VIX_B, filtered=False)
    cal = None
    if qd and qd in sk_all and qd in vx_all:
        cal = calibrate_skew_slope([r["value"] for r in chain], qd, float(bill_rates([qd], dtb3)[0]), vx_all[qd], sk_all[qd])
    if cal is None or not cal["kappa"] > 0:
        return _out({"calibration": cal}, 0, "inconclusive",
                    f"the 30-DTE SPX smile could not be calibrated from {KAPPA_CHAIN} (quote day {qd}): kappa needs the chain's put IVs "
                    "and the quote day's VIX and SKEW — the claim's model-priced debit is undefined without it")
    rep = put_spread_skew(days, c, sk, vx, rate, qy, cal["atm_ratio"], cal["kappa"])
    rep["calibration"] = cal
    flat = put_spread_skew(days, c, sk, vx, rate, qy, 1.0, cal["kappa"], mults=(1.0,), n_boot=1000, n_placebo=10)
    fd = (flat.get("by_kappa_mult") or {}).get("1.0", {})
    rep["atm_ratio_1_sensitivity"] = fd
    spot = float(c[days.index(qd)]) if qd in days else None
    reason = (f"calibration on {KAPPA_CHAIN} (captured {chain[0].get('available_at', '')[:16]} UTC, before the US open: quote day "
              f"{cal['quote_day']}; the parity forward {cal['forward']:.1f} vs that day's ^GSPC close {_f(spot, 1)} suggests "
              f"extended-hours quotes; {cal['root']} {cal['expiry']}, {cal['dte']} DTE): ATM IV at the forward "
              f"{cal['atm_iv']*100:.2f} vs VIX {cal['vix']:.2f} (ratio {cal['atm_ratio']:.3f}), put slope {cal['slope']:+.3f} per unit "
              f"ln(K/F) over {cal['n_points']} puts (10-30 delta, rmse {cal['fit_rmse']*100:.2f} vol pts) at SKEW {cal['skew']:.2f} -> "
              f"kappa {cal['kappa']:.5f}. " + rep["reason"].replace(" — ", f"; ATM-ratio sensitivity (IV = VIX, ratio 1.0): difference "
              f"{_s(fd.get('diff'), 3)} ({_ci_s(tuple(fd.get('ci') or (None, None)), 3)}) — ", 1))
    return _out(rep, rep.get("n", 0), rep["verdict"], reason)


def b6_surf_cross_index_vol_spread(archive):
    """T-237: after the 60-day VXN-VIX z-score passes +/-2, s[(VXN-VIX) - (RV_QQQ - RV_SPY)] over 21 days is positive."""
    miss = _missing(archive, [SPY_B, QQQ_B, VIX_B, VXN_B])
    if miss:
        return miss
    sd, _, sa = _daily(archive, SPY_B)
    qd_, _, qa = _daily(archive, QQQ_B)
    vix, vxn = _index(archive, VIX_B), _index(archive, VXN_B)
    spy, qqq = dict(zip(sd, sa)), dict(zip(qd_, qa))
    days = _align(spy, qqq, vix, vxn)
    rep = vol_spread_test(days, [vxn[d] for d in days], [vix[d] for d in days], [qqq[d] for d in days], [spy[d] for d in days])
    if _has(archive, RVX_B) and _has(archive, IWM_B):
        idd, _, ia = _daily(archive, IWM_B)
        rvx, iwm = _index(archive, RVX_B), dict(zip(idd, ia))
        d2 = _align(spy, iwm, vix, rvx)
        rr = vol_spread_test(d2, [rvx[d] for d in d2], [vix[d] for d in d2], [iwm[d] for d in d2], [spy[d] for d in d2],
                             n_boot=1000, n_placebo=500, label="RVX-VIX / IWM-SPY")
        rep["rvx_replication"] = {k: rr.get(k) for k in ("n", "mean", "ci95", "win_rate", "halves")}
        rep["reason"] = rep["reason"].replace(" — ", f"; RVX-VIX / IWM replication: {rr.get('n')} events, mean {_s(rr.get('mean'), 2)} "
                                              f"(95% {_s(rr.get('ci95', [None])[0], 2)} to {_s(rr.get('ci95', [None, None])[1], 2)}), "
                                              f"win rate {_f(rr.get('win_rate'), 2)} — ", 1)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_vix_call_hedge(archive):
    """T-239: MODEL-PRICED 25-delta VIX call overlay at 1%/yr cuts SPY's maximum drawdown by more than 25%."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B, VVIX_B, DTB3_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    vix, v3, vv = _index(archive, VIX_B), _index(archive, VIX3M_B), _index(archive, VVIX_B)
    keep = [d for d in sd if d in vix and d in v3 and d in vv and "2009-09-01" <= d]
    fr = frame_on(sd, sc, sa, keep, _series(archive, DTB3_B), {"vix": vix, "vix3m": v3, "vvix": vv})
    rep = vix_hedge_test(fr, _smile(archive))
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_vvix_vs_realised(archive):
    """T-240: VVIX exceeds the realised 21-day vol of spot-VIX log changes in > 70% of non-overlapping months."""
    miss = _missing(archive, [VVIX_B, VIX_B])
    if miss:
        return miss
    vix, vv = _index(archive, VIX_B), _index(archive, VVIX_B)
    spx = None
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        g = dict(zip(gd, gc))
        days = _align(vix, vv, g)
        spx = [g[d] for d in days]
    else:
        days = _align(vix, vv)
    rep = vvix_win_rate(days, [vv[d] for d in days], [vix[d] for d in days], spx=spx)
    if _has(archive, VIX3M_B) and _has(archive, DTB3_B) and "reason" in rep:
        v3 = _index(archive, VIX3M_B)
        d3 = [d for d in days if d in v3]
        if len(d3) > 100:
            sec = vix_call_ratio_secondary(d3, np.array([vix[d] for d in d3]), np.array([v3[d] for d in d3]),
                                           np.array([vv[d] for d in d3]), bill_rates(d3, _series(archive, DTB3_B)))
            rep["call_ratio_secondary"] = sec
            rep["reason"] = rep["reason"].replace(" — ", f". Secondary ({MP} 1x2 VIX call ratio, long F_adj+4 / short 2x at +14, "
                                                  f"Black-76 at VVIX, {sec['n']} cycles from {d3[0]}): mean P&L {_s(sec['mean'], 2)} VIX pts "
                                                  f"({_ci_s(sec['ci95'], 2)}) — ", 1)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_forward_variance_premium(archive):
    """T-249: the 1-3 month forward variance premium fraction exceeds the spot 30-day premium fraction."""
    miss = _missing(archive, [SPY_B, VIX_B, VIX3M_B])
    if miss:
        return miss
    sd, _, sa = _daily(archive, SPY_B)
    vix, v3 = _index(archive, VIX_B), _index(archive, VIX3M_B)
    spy = dict(zip(sd, sa))
    days = _align(spy, vix, v3)
    rep = forward_variance_premium(days, [spy[d] for d in days], [vix[d] for d in days], [v3[d] for d in days])
    if "reason_core" not in rep:
        return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])
    checks = []
    if _has(archive, DTB3_B):
        dtb3 = _series(archive, DTB3_B)
        vx_all, v3_all = _index(archive, VIX_B, filtered=False), _index(archive, VIX3M_B, filtered=False)
        cal_days = sorted(set(sd) | set(vx_all))
        for nm in _names(archive, SPX_CHAIN_P):
            rows = _rows(archive, nm, filtered=False)
            if not rows:
                continue
            qd = _quote_day(rows[0].get("available_at", ""), cal_days)
            if not qd:
                continue
            try:
                chk = strip_check([r["value"] for r in rows], qd, float(bill_rates([qd], dtb3)[0]), vx_all.get(qd), v3_all.get(qd))
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                chk = None
            if chk:
                chk["bundle"] = nm
                checks.append(chk)
    rep["strip_checks"] = checks
    if checks:
        strip_s = "; ".join(f"{c['bundle']} (quotes {c['quote_day']}): 30d strip {c['strip_30']:.2f} vs VIX {_f(c['vix'], 2)} "
                            f"({_s(c['err_30'], 2)}; strikes {'/'.join(map(str, c['strikes_30']))}), 93d strip {c['strip_93']:.2f} vs "
                            f"VIX3M {_f(c['vix3m'], 2)} ({_s(c['err_93'], 2)}; strikes {'/'.join(map(str, c['strikes_93']))}), "
                            f"forward {_f(c['fwd_strip'], 2)} vs index {_f(c.get('fwd_index'), 2)}" for c in checks)
        strip_s += (" (both captures precede the US open, so their quotes may be extended-hours quotes rather than the quote "
                    "day's close; zero bids truncate the strip, which is part of the error measured)")
    else:
        strip_s = "no SPX chain capture could be stripped"
    reason = rep.pop("reason_core") + f". Strip discretisation (captured SPX chains, reported): {strip_s}"
    why = rep.pop("why")
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + why)


def b6_surf_weekend_variance(archive):
    """T-511 (data-only part): SPY Fri->Mon variance < 1.5 x the weekday single-night variance."""
    miss = _missing(archive, [SPY_B])
    if miss:
        return miss
    sd, sc, sa = _daily(archive, SPY_B)
    rep = weekend_variance_ratio(sd, sa, raw_px=sc)
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


def b6_surf_implied_correlation(archive):
    """T-538: COR1M exceeds the realised average pairwise correlation of the index constituents (sector-SPDR proxy)."""
    legacy = [f"daily-history-{s}" for s in SECTORS_LEGACY]
    miss = _missing(archive, [COR1M_B] + legacy)
    if miss:
        return miss
    cor = _index(archive, COR1M_B)
    px = {}
    for s in SECTORS_LEGACY:
        d, _, a = _daily(archive, f"daily-history-{s}")
        px[s] = dict(zip(d, a))
    days = _align(cor, *px.values())
    comps = np.array([[px[s][d] for d in days] for s in SECTORS_LEGACY])
    rep = implied_vs_realised_corr(days, [cor[d] for d in days], comps, SECTORS_LEGACY)
    absent = [s for s in SECTORS_ALL if s not in SECTORS_LEGACY]
    rep["sectors_not_used"] = {s: ("archived but listed only from 2015/2018" if _has(archive, f"daily-history-{s}") else "not archived") for s in absent}
    return _out(rep, rep.get("n", 0), rep["verdict"], rep["reason"])


HARNESSES = {
    "b6_surf_vrp_term_regime": b6_surf_vrp_term_regime,
    "b6_surf_skew_tail_frequency": b6_surf_skew_tail_frequency,
    "b6_surf_skew_implied_tail_gap": b6_surf_skew_implied_tail_gap,
    "b6_surf_skew_cheap_put_spread": b6_surf_skew_cheap_put_spread,
    "b6_surf_cross_index_vol_spread": b6_surf_cross_index_vol_spread,
    "b6_surf_vix_call_hedge": b6_surf_vix_call_hedge,
    "b6_surf_vvix_vs_realised": b6_surf_vvix_vs_realised,
    "b6_surf_forward_variance_premium": b6_surf_forward_variance_premium,
    "b6_surf_weekend_variance": b6_surf_weekend_variance,
    "b6_surf_implied_correlation": b6_surf_implied_correlation,
}

THEORY_MAP = {
    "T-159": "b6_surf_vrp_term_regime",
    "T-227": "b6_surf_skew_tail_frequency",
    "T-228": "b6_surf_skew_implied_tail_gap",
    "T-229": "b6_surf_skew_cheap_put_spread",
    "T-237": "b6_surf_cross_index_vol_spread",
    "T-239": "b6_surf_vix_call_hedge",
    "T-240": "b6_surf_vvix_vs_realised",
    "T-249": "b6_surf_forward_variance_premium",
    "T-511": "b6_surf_weekend_variance",
    "T-538": "b6_surf_implied_correlation",
}
