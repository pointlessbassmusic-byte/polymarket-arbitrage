"""
Batch 6a, group ``var``: variance risk premium and short-premium claims on SPY and the S&P 500.
==============================================================================================

Nine options-library claims, each tested against its claim, trial.pass and trial.min_n as worded.

Model-free (VIX as the variance-swap strike, no option prices):
  * T-540 short 30-day variance struck at VIX^2, settled on the next 21 SPY close-to-close returns (%^2 per month);
  * T-234 the win rate of VIX^2 over the next 21-day ^GSPC realised variance (> 75% of non-overlapping months);
  * T-235 a short variance position scaled by max(z, 0), z the z-score of VIX minus a walk-forward HAR(1,5,22) forecast;
  * T-529 the VIX1D-implied next-day variance, (VIX1D/100)^2/365, against the next ^GSPC squared log return.

MODEL-PRICED (Black-Scholes legs at a stated multiple of VIX/100; every result is labelled MODEL-PRICED):
  * T-101 30-DTE ATM short straddle at 0.90 x VIX: top-minus-bottom tercile of VIX - RV21, tercile cut-points from the
    training window of ``walk_forward_splits`` and applied out of sample;
  * T-123 30-DTE ATM long straddle at 0.90 x VIX, delta-hedged daily at the entry vol, 1 bp per share traded: P&L / vega;
  * T-233 the same straddle sold at 0.81 x VIX (and at the ATM-IV / VIX ratio measured on the captured SPY smile), hedged
    daily, after a 0.5 vol-point round trip: P&L / premium;
  * T-156 45-DTE 0.16-delta short strangle at VIX: 21-DTE exit vs hold to expiry, P&L per day in the trade;
  * T-157 weekly ladder of quarter-size 0.16-delta short puts vs one full-size monthly entry, both managed at 50% of the
    credit or 21 DTE: ratio of maximum drawdowns.

Conventions (shared):
  * Cycles. A "30-DTE monthly" cycle is entered at a close and expires 21 trading days later; T is the calendar time between
    the two closes / 365 (28-32 days, about 30). Cycles do not overlap. 45-DTE positions expire on the last trading day on
    or before entry + 45 calendar days.
  * Point in time. Entries use the VIX and SPY closes of the entry day (both known at the close); forward windows start
    with the next day's return. The 3-month bill (FRED DTB3, a discount yield published the next day) enters as the prior
    print, converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365).
  * Options settle on RAW closes (close, not adjclose). SPY dividends come from the adjclose/close ratio step: on an ex-day
    i, D = close[i-1] * (1 - f[i-1]/f[i]) with f = adjclose/close. An option whose life spans an ex-date is priced on the
    dividend forward, S - PV(D), with the amount forecast point in time as the last dividend paid at or before the
    decision (ex-dates follow SPY's quarterly schedule). A hedge that holds shares across an ex-date receives (or, short,
    pays) the actual dividend in cash. The hedged P&L runs through a cash account that earns the bill rate.
  * Realised variance is the sum of squared close-to-close log returns, annualised with 252 / window (no mean removed).
  * Intervals. Studentized (bootstrap-t) circular block bootstraps: the statistic is studentized by a Bartlett long-run
    s.e. with bandwidth = block (as in backtest_eval.block_bootstrap_pvalue). Differences are bootstrapped PAIRED on a
    shared timeline. A drawdown ratio (T-157) has no closed-form s.e., so its interval is a percentile block bootstrap of
    paired daily P&L paths. Blocks cover the overlap of overlapping windows.
  * min_n is counted in the claim's own units (cycles, months, entries, days). Below min_n a claim cannot be supported,
    and a failing criterion counts only when it fails decisively (its interval wholly on the wrong side); otherwise the
    criterion is reported as not decisive and the verdict is inconclusive.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not implemented
gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.options_market import _binom_two_sided_ci
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, index_closes, variance_risk_premium
from mandel.options import bs
from mandel.validation.backtest_eval import (_hac_var, deflated_sharpe_ratio, kurtosis, sharpe_ratio, skewness,
                                             walk_forward_splits)

PPY = 252
HOLD = 21
SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
VIX_B = "cboe-VIX-history"
VIX1D_B = "cboe-VIX1D-history"
DTB3_B = "fred-DTB3"
SMILE_P = "spy-smile-"
SPX_CHAIN_P = "options-chain-SPX-"
EVENT_B = {"FOMC": "fomc-meetings", "CPI": "macro-release-cpi", "NFP": "macro-release-employment-situation"}
COMM_PER_SHARE = 0.65 / 100.0          # $0.65 per contract of 100 shares, per leg per fill
MP = "MODEL-PRICED"
TRADED_NOTE = "the traded version needs SPY chain history (2 capture days archived)"


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


def stud_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Two-sided studentized circular block-bootstrap CI of the mean at ``level``: (lo, hi), or (None, None) below 8
    observations. Each resample's mean is studentized by its own Bartlett long-run s.e. (bandwidth = block)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    v0 = float(_hac_var(x[None, :], block)[0])
    if v0 <= 1e-30:
        return m, m
    se = math.sqrt(v0 / n)
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        xb = x[_boot_idx(rng, n, block, k)]
        ts.append((xb.mean(axis=1) - m) / np.sqrt(_hac_var(xb, block) / n))
    t = np.concatenate(ts)
    a = (1.0 - level) / 2.0
    return m - float(np.quantile(t, 1.0 - a)) * se, m - float(np.quantile(t, a)) * se


def pct_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Percentile circular block-bootstrap CI of the mean (used for a proportion, whose s.e. vanishes near 0 or 1)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    ms = np.concatenate([x[_boot_idx(rng, n, block, k)].mean(axis=1) for k in _chunks(n_boot, n)])
    a = (1.0 - level) / 2.0
    return float(np.quantile(ms, a)), float(np.quantile(ms, 1.0 - a))


def stud_ci_group_diff(x, top, bot, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> dict:
    """mean(x | top) - mean(x | bot) for two disjoint groups of one timeline, with a studentized circular block-bootstrap
    CI: blocks of the shared timeline are resampled (each cycle keeps its label), and each resample is studentized by the
    Bartlett long-run s.e. of the difference's influence function psi_i = n (1top_i (x_i - m_top)/n_top -
    1bot_i (x_i - m_bot)/n_bot)."""
    x = np.asarray(x, dtype=float)
    top = np.asarray(top, dtype=bool)
    bot = np.asarray(bot, dtype=bool)
    n = x.size
    out = {"n": int(n), "n_top": int(top.sum()), "n_bottom": int(bot.sum()), "diff": None, "ci": [None, None],
           "mean_top": None, "mean_bottom": None}
    if top.sum() < 4 or bot.sum() < 4 or n < 8:
        return out
    block = max(1, min(int(block), n // 4))

    def stat(xb, tb, bb):
        nt, nbb = tb.sum(axis=1), bb.sum(axis=1)
        ok = (nt > 0) & (nbb > 0)
        nt, nbb = np.maximum(nt, 1), np.maximum(nbb, 1)
        mt = (xb * tb).sum(axis=1) / nt
        mb = (xb * bb).sum(axis=1) / nbb
        psi = n * (tb * (xb - mt[:, None]) / nt[:, None] - bb * (xb - mb[:, None]) / nbb[:, None])
        return mt - mb, np.sqrt(_hac_var(psi, block) / n), ok, mt, mb

    d0, se0, _, mt0, mb0 = stat(x[None, :], top[None, :], bot[None, :])
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(diff=d0, mean_top=float(mt0[0]), mean_bottom=float(mb0[0]), se=se0)
    if se0 <= 1e-150:
        out["ci"] = [d0, d0]
        return out
    rng = np.random.default_rng(seed)
    ts, ds = [], []
    for k in _chunks(n_boot, n):
        idx = _boot_idx(rng, n, block, k)
        d, se, ok, _, _ = stat(x[idx], top[idx], bot[idx])
        ok &= se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
        ds.append(d[ok])
    t, dd = np.concatenate(ts), np.concatenate(ds)
    a = (1.0 - level) / 2.0
    out["ci"] = [d0 - float(np.quantile(t, 1.0 - a)) * se0, d0 - float(np.quantile(t, a)) * se0]
    out["ci_percentile"] = [float(np.quantile(dd, a)), float(np.quantile(dd, 1.0 - a))]
    return out


def _sr_diff_and_se(a: np.ndarray, b: np.ndarray, bw: int):
    """Row-wise per-period Sharpe(a) - Sharpe(b) and its delta-method HAC s.e. (Ledoit and Wolf 2008)."""
    n = a.shape[1]
    mu_a, mu_b = a.mean(axis=1), b.mean(axis=1)
    g_a, g_b = (a * a).mean(axis=1), (b * b).mean(axis=1)
    va, vb = np.maximum(g_a - mu_a ** 2, 1e-300), np.maximum(g_b - mu_b ** 2, 1e-300)
    d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
    grad = (g_a / va ** 1.5, -g_b / vb ** 1.5, -mu_a / (2 * va ** 1.5), mu_b / (2 * vb ** 1.5))
    z = (grad[0][:, None] * (a - mu_a[:, None]) + grad[1][:, None] * (b - mu_b[:, None])
         + grad[2][:, None] * (a * a - g_a[:, None]) + grad[3][:, None] * (b * b - g_b[:, None]))
    return d, np.sqrt(_hac_var(z, bw) / n)


def sharpe_diff_test(a, b, block: int, n_boot: int = 2000, seed: int = 0) -> dict:
    """One-sided studentized circular block bootstrap of Sharpe(a) - Sharpe(b) on paired periods (H0: difference <= 0).
    Returns the per-period difference, its s.e., the p-value and a two-sided 95% CI."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = a.size
    if n < 8 or b.size != n:
        return {"diff": None, "se": None, "p": None, "ci": [None, None]}
    block = max(1, min(int(block), n // 4))
    d0, se0 = _sr_diff_and_se(a[None, :], b[None, :], block)
    d0, se0 = float(d0[0]), float(se0[0])
    if not se0 > 1e-150:
        return {"diff": d0, "se": 0.0, "p": 0.0 if d0 > 0 else 1.0, "ci": [d0, d0]}
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        d, se = _sr_diff_and_se(a[idx], b[idx], block)
        ok = se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
    t = np.concatenate(ts)
    t_obs = d0 / se0
    return {"diff": d0, "se": se0, "p": float((np.sum(t >= t_obs) + 1) / (t.size + 1)),
            "ci": [d0 - float(np.quantile(t, 0.975)) * se0, d0 - float(np.quantile(t, 0.025)) * se0]}


def _mdd_abs(pnl) -> np.ndarray:
    """Maximum drawdown (absolute, >= 0) of the additive equity curve cumsum(pnl) starting at 0, row-wise."""
    p = np.atleast_2d(np.asarray(pnl, dtype=float))
    eq = np.concatenate([np.zeros((p.shape[0], 1)), np.cumsum(p, axis=1)], axis=1)
    return (np.maximum.accumulate(eq, axis=1) - eq).max(axis=1)


def mdd_ratio_ci(pl_a, pl_b, block: int = 63, n_boot: int = 1000, seed: int = 0, level: float = 0.95) -> dict:
    """MDD(a) / MDD(b) of additive daily P&L paths, with a percentile CI over PAIRED circular block-bootstrap paths (the
    same day blocks for both books)."""
    a = np.asarray(pl_a, dtype=float)
    b = np.asarray(pl_b, dtype=float)
    n = a.size
    ma, mb = float(_mdd_abs(a)[0]), float(_mdd_abs(b)[0])
    out = {"n_days": int(n), "mdd_a": ma, "mdd_b": mb, "ratio": ma / mb if mb > 0 else None, "ci": [None, None]}
    if n < 8 * block // 4 or n < 8:
        return out
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    rs = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        da, db = _mdd_abs(a[idx]), _mdd_abs(b[idx])
        ok = db > 0
        rs.append(da[ok] / db[ok])
    r = np.concatenate(rs)
    if r.size:
        al = (1.0 - level) / 2.0
        out["ci"] = [float(np.quantile(r, al)), float(np.quantile(r, 1.0 - al))]
    return out


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (its
    interval wholly on the wrong side); otherwise it is reported as not decisive (None). Appends the min_n criterion."""
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
    return f"CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


def _thirds(x) -> list:
    x = np.asarray(x, dtype=float)
    return [float(p.mean()) if p.size else None for p in np.array_split(x, 3)]


def _halves(x) -> list:
    x = np.asarray(x, dtype=float)
    h = x.size // 2
    return [float(x[:h].mean()) if h else None, float(x[h:].mean()) if x.size - h else None]


def _desc(x) -> dict:
    x = np.asarray(x, dtype=float)
    if x.size < 3:
        return {}
    return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)), "skew": float(skewness(x)), "kurtosis": float(kurtosis(x)),
            "min": float(x.min()), "max": float(x.max())}


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


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
    """Bundle names starting with ``prefix`` (index lookup only)."""
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
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured (a bar still open)."""
    cap = getattr(archive.get(name), "created_at", None) if filtered else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        if c is None or not float(c) > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float(c))
    days = sorted(by)
    return days, np.array([by[d][0] for d in days], dtype=float), np.array([by[d][1] for d in days], dtype=float)


def _daily(archive, name: str) -> tuple:
    """(days, raw close, adjclose) of a daily-history bundle, bars not yet available at capture dropped."""
    return _daily_from_rows(_rows(archive, name))


def _index(archive, name: str, filtered: bool = True) -> dict:
    return index_closes(_rows(archive, name, filtered))


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED series, missing prints skipped."""
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
    """Point-in-time forecast of an upcoming dividend at each close: the last dividend gone ex at or before that day (the
    first dividend before any has been paid)."""
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


def make_frame(days, close, vix, rate=None, div=None, adj=None) -> dict:
    """Aligned daily arrays for the option engines: ISO days, ordinal dates, raw close, adjclose, cash dividend by
    ex-day, its point-in-time forecast, VIX close (vol points) and the continuous bill rate known at each close."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    div = np.zeros(close.size) if div is None else np.asarray(div, dtype=float)
    return {"days": days, "ords": np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64),
            "close": close, "adj": close.copy() if adj is None else np.asarray(adj, dtype=float),
            "div": div, "fc": div_forecast(div), "vix": np.asarray(vix, dtype=float),
            "rate": np.zeros(close.size) if rate is None else np.asarray(rate, dtype=float)}


def _spy_frame(archive) -> dict:
    """SPY raw closes on SPY days that have a VIX close, with dividends, VIX and the prior-print bill rate."""
    days, close, adj = _daily(archive, SPY_B)
    vix = _index(archive, VIX_B)
    dtb3 = _series(archive, DTB3_B)
    div_full = dividends(close, adj)
    keep = np.array([d in vix for d in days], dtype=bool)
    div = np.zeros(len(days))
    carry = 0.0
    for i in range(len(days)):                      # a dividend on a dropped day is paid on the next kept day
        carry += div_full[i]
        if keep[i]:
            div[i], carry = carry, 0.0
    sel = np.nonzero(keep)[0]
    d2 = [days[i] for i in sel]
    return make_frame(d2, close[sel], [vix[d] for d in d2], rate=bill_rates(d2, dtb3), div=div[sel], adj=adj[sel])


def _pv_divs(ex, fc, tt, r) -> np.ndarray:
    """PV at each column j of the forecast dividends going ex at columns k > j of the same path (rows = positions)."""
    m, w = ex.shape
    out = np.zeros((m, w))
    if not ex.any():
        return out
    for j in range(w - 1):
        for k in range(j + 1, w):
            hit = ex[:, k]
            if hit.any():
                out[:, j] += np.where(hit, fc * np.exp(-r * (tt[:, k] - tt[:, j]) / 365.0), 0.0)
    return out


# ============================================================================================ straddle engine ==

def straddle_cycles(fr: dict, scale: float, side: int = -1, hold: int = HOLD, first: int = 0, hedge: bool = True,
                    hedge_every: int = 1, cost_bps: float = 0.0, vol_cost: float = 0.0, div_pricing: bool = True) -> dict:
    """Non-overlapping ATM straddle cycles: entered at the close of day a (strike = that close), priced by Black-Scholes at
    sigma = scale * VIX_a / 100 on the dividend forward, expiring at the close of a + hold (raw close). ``side`` +1 long,
    -1 short. With ``hedge`` the straddle delta (at the entry vol) is hedged at each close (every ``hedge_every`` days),
    1 share = 1 unit; ``cost_bps`` is charged on the value of every share traded (opening, rebalancing and unwinding);
    ``vol_cost`` (vol, e.g. 0.005) is charged once as entry vega x vol_cost. P&L is the final value of a self-financing
    cash account (premium, hedge trades, dividends on hedge shares, interest at the entry bill rate) plus the payoff."""
    n = len(fr["days"])
    starts = np.arange(first, n - hold, hold)
    keys = ("start", "pnl", "prem", "vega", "spot", "sig", "payoff", "rv", "var_term", "traded")
    if starts.size == 0:
        return {k: np.zeros(0) for k in keys} | {"day": []}
    I = starts[:, None] + np.arange(hold + 1)[None, :]
    S = fr["close"][I]
    tt = fr["ords"][I].astype(float)
    T = (tt[:, -1:] - tt) / 365.0
    r = fr["rate"][starts]
    sig = np.maximum(scale * fr["vix"][starts] / 100.0, 0.01)
    K = S[:, 0].copy()
    D = fr["div"][I].copy()
    D[:, 0] = 0.0
    pvd = _pv_divs(D > 0, fr["fc"][starts], tt, r) if div_pricing else np.zeros_like(S)
    Sx = S - pvd
    prem = bs.price(Sx[:, 0], K, T[:, 0], r, sig, "call") + bs.price(Sx[:, 0], K, T[:, 0], r, sig, "put")
    vega = 2.0 * bs.greeks(Sx[:, 0], K, T[:, 0], r, sig, "call")["vega"]
    payoff = np.abs(S[:, -1] - K)
    g = bs.greeks(Sx[:, :hold], K[:, None], T[:, :hold], r[:, None], sig[:, None], "call")
    gam = 2.0 * g["gamma"]
    if hedge:
        delta = 2.0 * g["delta"] - 1.0                                  # call + put delta, q = 0 on the dividend forward
        if hedge_every > 1:
            delta = delta[:, (np.arange(hold) // hedge_every) * hedge_every]
        h = -side * delta
    else:
        h = np.zeros((starts.size, hold))
    c = cost_bps / 1e4
    cash = -side * prem - h[:, 0] * S[:, 0] - c * np.abs(h[:, 0]) * S[:, 0]
    traded = np.abs(h[:, 0]).copy()
    for j in range(hold):
        dt = (tt[:, j + 1] - tt[:, j]) / 365.0
        cash = cash * np.exp(r * dt) + h[:, j] * D[:, j + 1]
        if j + 1 < hold:
            dh = h[:, j + 1] - h[:, j]
            cash = cash - dh * S[:, j + 1] - c * np.abs(dh) * S[:, j + 1]
            traded += np.abs(dh)
        else:
            cash = cash + h[:, j] * S[:, j + 1] - c * np.abs(h[:, j]) * S[:, j + 1]
            traded += np.abs(h[:, j])
    pnl = cash + side * payoff - vol_cost * vega
    gross = (S[:, 1:] + D[:, 1:]) / S[:, :-1]
    rv = (PPY / hold) * np.sum(np.log(gross) ** 2, axis=1)
    dtm = (tt[:, 1:] - tt[:, :-1]) / 365.0
    var_term = side * np.sum(0.5 * gam * S[:, :hold] ** 2 * ((gross - 1.0) ** 2 - sig[:, None] ** 2 * dtm), axis=1)
    return {"start": starts, "day": [fr["days"][a] for a in starts], "pnl": pnl, "prem": prem, "vega": vega, "spot": K,
            "sig": sig, "payoff": payoff, "rv": rv, "var_term": var_term, "traded": traded}


def trailing_rv_vol(logret_end: np.ndarray, idx, window: int = HOLD) -> np.ndarray:
    """Annualised realised vol of the ``window`` log returns ending at each close in ``idx`` (logret_end[k] = ln C_k/C_{k-1})."""
    out = np.full(len(idx), np.nan)
    for i, a in enumerate(idx):
        if a - window + 1 >= 1:
            seg = logret_end[a - window + 1:a + 1]
            out[i] = math.sqrt(PPY / window * float(np.sum(seg ** 2)))
    return out


def _logret_end(c) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    out = np.full(c.size, np.nan)
    out[1:] = np.log(c[1:] / c[:-1])
    return out


# ================================================================================ T-101 tercile short straddle ==

def tercile_oos(signal, x_by_scale: dict, n_pre: int, n_splits: int = 5, block: int = 6, n_boot: int = 2000, seed: int = 0,
                min_train_fallback: int = 60) -> dict:
    """Walk-forward tercile test. ``signal`` lists every cycle in time order: ``n_pre`` training-only cycles first (no
    P&L), then the P&L cycles that ``x_by_scale[s]`` covers. Splits come from ``walk_forward_splits`` with min_train =
    n_pre (or ``min_train_fallback`` P&L cycles when n_pre < 24); in each split the 1/3 and 2/3 quantiles of the training
    window's signal label the test window (top: above the 2/3 cut; bottom: at or below the 1/3 cut). The pooled out-of-
    sample top-minus-bottom difference of mean x gets a studentized block-bootstrap CI per scale."""
    signal = np.asarray(signal, dtype=float)
    n_all = signal.size
    min_train = n_pre if n_pre >= 24 else max(n_pre, min_train_fallback)
    label = np.full(n_all, -1)
    cuts = []
    for tr, te in walk_forward_splits(n_all, n_splits, min_train):
        lo, hi = np.quantile(signal[tr], [1 / 3, 2 / 3])
        cuts.append([float(lo), float(hi)])
        label[te] = np.where(signal[te] > hi, 2, np.where(signal[te] <= lo, 0, 1))
    oos = np.nonzero(label >= 0)[0]
    pi = oos - n_pre
    top, bot = label[oos] == 2, label[oos] == 0
    res = {}
    for s, x in x_by_scale.items():
        xs = np.asarray(x, dtype=float)[pi]
        res[s] = stud_ci_group_diff(xs, top, bot, block, 0.95, n_boot, seed)
        res[s]["mean_middle"] = float(xs[label[oos] == 1].mean()) if (label[oos] == 1).any() else None
    return {"n_oos": int(oos.size), "n_pre": int(n_pre), "min_train": int(min_train), "n_splits": n_splits, "cuts": cuts,
            "by_scale": res, "oos_index": pi, "top": top, "bottom": bot}


def straddle_tercile(fr: dict, pre_signal=None, scales=(0.81, 0.90, 1.00), main: float = 0.90, n_splits: int = 5,
                     block: int = 6, n_boot: int = 20000, seed: int = 0, haircut: float = 0.05, min_n: int = 390,
                     pre_note: str = "") -> dict:
    """T-101: short 30-DTE ATM SPY straddles at BS(s * VIX/100); mean P&L / premium, top minus bottom tercile of VIX - RV21
    at entry, cut-points from walk-forward training windows, out of sample. Pass: CI excludes 0 at s = 0.90 (on the
    claimed side, top higher) and the same sign at s = 0.81 and 1.00; min_n 390 out-of-sample cycles."""
    res = {s: straddle_cycles(fr, s, side=-1, hedge=False, first=HOLD) for s in scales}
    starts = res[scales[0]]["start"]
    sig = fr["vix"][starts] - 100.0 * trailing_rv_vol(_logret_end(fr["adj"]), starts)
    pre = np.asarray([] if pre_signal is None else pre_signal, dtype=float)
    x = {s: res[s]["pnl"] / res[s]["prem"] for s in scales}
    if starts.size + pre.size < 30:
        return {"verdict": "inconclusive", "n": 0, "reason": f"only {starts.size} SPY cycles — too few to split"}
    t = tercile_oos(np.concatenate([pre, sig]), x, pre.size, n_splits, block, n_boot, seed)
    n = t["n_oos"]
    crit, parts = [], []
    m = t["by_scale"][main]
    lo, hi = m["ci"]
    crit.append((f"s={main:.2f}: OOS top-bottom > 0 with 95% CI excluding 0",
                 None if lo is None else bool(lo > 0), lo is not None and hi < 0))
    for s in scales:
        if s == main:
            continue
        ms = t["by_scale"][s]
        crit.append((f"s={s:.2f}: same sign (top-bottom > 0)", None if ms["diff"] is None else bool(ms["diff"] > 0),
                     ms["ci"][1] is not None and ms["ci"][1] < 0))
    for s in scales:
        ms = t["by_scale"][s]
        parts.append(f"s={s:.2f}: top {_s(ms['mean_top'] and ms['mean_top'] * 100, 1)}% vs bottom "
                     f"{_s(ms['mean_bottom'] and ms['mean_bottom'] * 100, 1)}% of premium, diff "
                     f"{_s(ms['diff'] and ms['diff'] * 100, 1)} pts ({_ci_s(ms['ci'], 1, 100)}; n top/bottom "
                     f"{ms['n_top']}/{ms['n_bottom']})")
    # reported controls
    xm = x[main]
    top_series = xm[t["oos_index"]][t["top"]]
    xo = xm[t["oos_index"]]
    block_sens = {b: stud_ci_group_diff(xo, t["top"], t["bottom"], b, 0.95, max(2000, n_boot // 5), seed)["ci"] for b in (3, 12)}
    parts.append(f"s={main:.2f} interval sensitivity: percentile {_ci_s(m.get('ci_percentile', (None, None)), 1, 100)}, studentized "
                 + ", ".join(f"block {b} {_ci_s(ci, 1, 100)}" for b, ci in block_sens.items())
                 + f" ({n_boot} draws, block {block} as declared)"
                 + ("; MARGINAL: the declared interval excludes 0 but an alternative interval does not"
                    if lo is not None and lo > 0 and any(c[0] is not None and c[0] <= 0
                                                          for c in [m.get("ci_percentile", (None, None)), *block_sens.values()]) else ""))
    uncond = {s: {"mean": float(x[s].mean()), "ci": list(stud_ci(x[s], block, 0.95, n_boot, seed))} for s in scales}
    spot_pnl = res[main]["pnl"] / res[main]["spot"]
    extras = {"unconditional": uncond, "s_main_desc": _desc(xm),
              "psr_all_cycles": float(deflated_sharpe_ratio(xm, 1)),
              "dsr_top_tercile_oos_n_trials_3": float(deflated_sharpe_ratio(top_series, 3)) if top_series.size > 3 else None,
              "max_drawdown_pct_of_spot": float(_mdd_abs(spot_pnl)[0] * 100),
              "haircut_5pct": {"mean_top": None if m["mean_top"] is None else m["mean_top"] - haircut,
                               "mean_bottom": None if m["mean_bottom"] is None else m["mean_bottom"] - haircut,
                               "diff": m["diff"], "note": "a constant per-premium haircut leaves the tercile difference unchanged"}}
    hc = extras["haircut_5pct"]
    parts.append(f"5%-of-premium round-trip haircut: top {_s(hc['mean_top'] and hc['mean_top'] * 100, 1)}% vs bottom "
                 f"{_s(hc['mean_bottom'] and hc['mean_bottom'] * 100, 1)}% (difference unchanged)")
    parts.append(f"unconditional mean at s={main:.2f} {xm.mean() * 100:+.1f}% of premium "
                 f"({_ci_s(uncond[main]['ci'], 1, 100)}), skew {extras['s_main_desc'].get('skew', float('nan')):.2f}, "
                 f"PSR {extras['psr_all_cycles']:.2f}, DSR(top tercile, 3 trials) {_f(extras['dsr_top_tercile_oos_n_trials_3'])}")
    verdict, why = _decide(crit, n, min_n, "out-of-sample cycles")
    reason = (f"{MP} short 30-DTE ATM SPY straddle at s x VIX on the dividend forward, settled on raw closes; {n} OOS cycles "
              f"({t['n_splits']} walk-forward test windows, cut-points on the training window's VIX - RV21{pre_note}): "
              + "; ".join(parts) + f"; the tercile spread is model-priced (IV level only scales premium; {TRADED_NOTE})"
              + f" — {why}")
    stat = {"model_priced": True, "n_oos_cycles": n, "n_spy_cycles": int(starts.size), "n_pre_training_cycles": int(pre.size),
            "min_train": t["min_train"], "cuts_by_split": t["cuts"], "n_boot": n_boot, "block": block,
            "block_sensitivity_ci": {str(b): ci for b, ci in block_sens.items()},
            "by_scale": {str(s): {k: v for k, v in t["by_scale"][s].items()} for s in scales}, **extras,
            "first_entry": res[main]["day"][0] if res[main]["day"] else None, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ============================================================================== T-123 gamma scalping long straddle ==

def _flip_scale(fr: dict, grid, cost_bps: float) -> Optional[float]:
    """Smallest s on ``grid`` where mean hedged long-straddle P&L/vega crosses from positive to negative (interpolated)."""
    ms = []
    for s in grid:
        r = straddle_cycles(fr, s, side=1, hedge=True, cost_bps=cost_bps)
        ms.append(float(np.mean(r["pnl"] / r["vega"])) if r["pnl"].size else float("nan"))
    for i in range(len(grid) - 1):
        a, b = ms[i], ms[i + 1]
        if math.isfinite(a) and math.isfinite(b) and a >= 0 > b:
            return float(grid[i] + (grid[i + 1] - grid[i]) * a / (a - b))
    return None


def gamma_scalp(fr: dict, scales=(0.81, 0.90, 1.00), main: float = 0.90, cost_bps: float = 1.0, block: int = 6,
                n_boot: int = 2000, seed: int = 0, flip_grid=None, min_n: int = 390) -> dict:
    """T-123: long 30-DTE ATM SPY straddle bought at BS(s * VIX), delta-hedged at each close at the entry vol, 1 bp per share
    traded; mean P&L / vega over non-overlapping cycles. Pass: upper 95% CI < 0 at s = 0.90; min_n 390 cycles."""
    res = {s: straddle_cycles(fr, s, side=1, hedge=True, cost_bps=cost_bps) for s in scales}
    n = int(res[main]["pnl"].size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles"}
    by = {}
    for s in scales:
        r = res[s]
        y = r["pnl"] / r["vega"]
        lo, hi = stud_ci(y, block, 0.95, n_boot, seed)
        excess = r["rv"] - r["sig"] ** 2
        by[s] = {"mean_vol_pts": float(y.mean() * 100), "ci_vol_pts": [None if lo is None else lo * 100, None if hi is None else hi * 100],
                 "corr_pnl_rv_minus_implied_var": float(np.corrcoef(y, excess)[0, 1]) if y.size > 2 else None,
                 "mean_var_term_per_vega_vol_pts": float(np.mean(r["var_term"] / r["vega"]) * 100),
                 "mean_hedge_error_per_vega_vol_pts": float(np.mean((r["pnl"] - r["var_term"]) / r["vega"]) * 100),
                 "mean_shares_traded_per_cycle": float(r["traded"].mean()), "desc": _desc(y * 100), "thirds_vol_pts": [v * 100 for v in _thirds(y)]}
    rm = res[main]
    btz = [i for i, d in enumerate(rm["day"]) if d <= "2007-12-31"]
    btz_anchor = float(np.mean(((rm["sig"][btz] / main) ** 2 - rm["rv"][btz]) * 1e4 / 12.0)) if btz else None
    q0 = straddle_cycles(fr, main, side=1, hedge=True, cost_bps=cost_bps, div_pricing=False)
    q0m = float(np.mean(q0["pnl"] / q0["vega"]) * 100)
    grid = np.round(np.arange(0.50, 1.301, 0.02), 2) if flip_grid is None else np.asarray(flip_grid, dtype=float)
    flip = _flip_scale(fr, grid, cost_bps)
    m = by[main]
    lo, hi = m["ci_vol_pts"]
    crit = [(f"s={main:.2f}: upper 95% CI of mean P&L/vega < 0", None if hi is None else bool(hi < 0), lo is not None and lo > 0)]
    parts = [f"s={s:.2f}: mean {by[s]['mean_vol_pts']:+.2f} vol pts per unit vega ({_ci_s(by[s]['ci_vol_pts'])}), "
             f"corr with RV-(s VIX)^2 {_f(by[s]['corr_pnl_rv_minus_implied_var'])}" for s in scales]
    parts.append(f"variance term {m['mean_var_term_per_vega_vol_pts']:+.2f} vs hedging error and costs "
                 f"{m['mean_hedge_error_per_vega_vol_pts']:+.2f} vol pts at s={main:.2f}")
    parts.append(f"sign flips at s = {_f(flip, 3) if flip is not None else 'none on ' + str(grid[0]) + '-' + str(grid[-1])}")
    parts.append(f"q=0 control (no dividend forward) {q0m:+.2f}")
    if btz_anchor is not None:
        parts.append(f"BTZ anchor: mean (VIX^2 - RV21)/12 over the {len(btz)} cycles to 2007 {btz_anchor:+.1f} %^2/month")
    verdict, why = _decide(crit, n, min_n, "cycles")
    reason = (f"{MP} long 30-DTE ATM SPY straddle at s x VIX, delta-hedged daily at the entry vol on raw closes, 1 bp per share "
              f"traded, cash at the bill rate; {n} non-overlapping cycles {res[main]['day'][0]}..{res[main]['day'][-1]}: "
              + "; ".join(parts) + f" — {why}")
    stat = {"model_priced": True, "n_cycles": n, "cost_bps_per_share": cost_bps, "by_scale": {str(s): by[s] for s in scales},
            "sign_flip_scale": flip, "flip_grid": [float(grid[0]), float(grid[-1])], "q0_control_mean_vol_pts": q0m,
            "btz_anchor_pct2_per_month_to_2007": btz_anchor,
            "first_entry": res[main]["day"][0], "last_entry": res[main]["day"][-1], "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ========================================================================= T-233 hedged short straddle (VRP) ==

def vrp_hedged_short(fr: dict, measured_scale: Optional[float], measured_note: str = "", main: float = 0.81,
                     vol_cost: float = 0.005, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300) -> dict:
    """T-233: short 30-DTE ATM SPY straddle at ATM IV = s x VIX, delta-hedged at each close, 0.5 vol-point round trip charged
    as entry vega x 0.005; mean cycle P&L / premium. Pass: mean > 0 with the 95% CI excluding 0 at s = 0.81 and at the
    scale measured on the capture; deflated Sharpe p < 0.05 (DSR > 0.95) over the IV scales and hedge frequencies tried;
    positive in all three thirds; min_n 300 cycles."""
    scales = [main] + ([measured_scale] if measured_scale is not None else [])
    variants = {}
    for s in sorted(set([1.0, 0.9, main] + ([round(measured_scale, 4)] if measured_scale is not None else []))):
        for he in (1, 5):
            r = straddle_cycles(fr, s, side=-1, hedge=True, hedge_every=he, vol_cost=vol_cost)
            variants[(s, he)] = r["pnl"] / r["prem"] if r["pnl"].size else np.zeros(0)
    base = straddle_cycles(fr, main, side=-1, hedge=True, vol_cost=vol_cost)
    n = int(base["pnl"].size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles"}
    crit, parts, by = [], [], {}
    for j, s in enumerate(scales):
        y = variants[(round(s, 4) if j == 1 else s, 1)]
        lo, hi = stud_ci(y, block, 0.95, n_boot, seed)
        th = _thirds(y)
        by["measured" if j == 1 else f"{s:.4f}"] = {"scale": s, "mean": float(y.mean()), "ci": [lo, hi], "thirds": th, "desc": _desc(y)}
        tag = f"s={s:.3f}" + (" (measured on the capture)" if j == 1 else "")
        crit.append((f"{tag}: mean > 0 with 95% CI excluding 0", None if lo is None else bool(lo > 0), hi is not None and hi < 0))
        crit.append((f"{tag}: mean > 0 in all three thirds", all(v is not None and v > 0 for v in th), False))
        parts.append(f"{tag}: mean {y.mean() * 100:+.2f}% of premium ({_ci_s((lo, hi), 2, 100)}), thirds "
                     + "/".join(f"{v * 100:+.1f}%" for v in th))
    if measured_scale is None:
        crit.append(("s measured on the captured SPY smile: mean > 0 with CI excluding 0 and positive thirds", None, False))
        parts.append("no captured SPY smile: the measured ATM/VIX scale is not available")
    keys = sorted(variants)
    srs = [sharpe_ratio(variants[k]) for k in keys]
    dsr = float(deflated_sharpe_ratio(variants[(main, 1)], len(keys), trial_sharpes=srs))
    crit.append((f"deflated Sharpe p < 0.05 (DSR > 0.95; {len(keys)} variants: IV scales x hedge daily/weekly)", bool(dsr > 0.95), False))
    parts.append(f"DSR {dsr:.3f} over {len(keys)} variants")
    unhedged = straddle_cycles(fr, main, side=-1, hedge=False, vol_cost=vol_cost)
    uh = unhedged["pnl"] / unhedged["prem"]
    rng = np.random.default_rng(seed)
    shuffled = dict(fr, vix=fr["vix"][rng.permutation(len(fr["vix"]))])
    pl = straddle_cycles(shuffled, main, side=-1, hedge=True, vol_cost=vol_cost)
    one_bp = straddle_cycles(fr, main, side=-1, hedge=True, vol_cost=vol_cost, cost_bps=1.0)
    sens = {f"{k[0]:.4f}/{'daily' if k[1] == 1 else 'weekly'}": float(v.mean()) for k, v in variants.items()}
    parts.append("IV-scale sensitivity (daily hedge, mean % of premium) " + ", ".join(
        f"s={k[0]:.2f} {variants[k].mean() * 100:+.1f}" for k in keys if k[1] == 1))
    parts.append(f"controls: unhedged {uh.mean() * 100:+.2f}%, shuffled-VIX placebo {np.mean(pl['pnl'] / pl['prem']) * 100:+.2f}%, "
                 f"+1 bp/share hedge cost {np.mean(one_bp['pnl'] / one_bp['prem']) * 100:+.2f}%")
    verdict, why = _decide(crit, n, min_n, "cycles")
    reason = (f"{MP} short 30-DTE ATM SPY straddle, delta-hedged daily at the entry vol on raw closes, dividend forward, "
              f"0.5 vol-pt round trip; {n} cycles {base['day'][0]}..{base['day'][-1]}{measured_note}: " + "; ".join(parts)
              + f"; the edge hinges on the IV level ({TRADED_NOTE})" + f" — {why}")
    stat = {"model_priced": True, "n_cycles": n, "measured_scale": measured_scale, "by_scale": by, "dsr": dsr,
            "variant_means": sens, "unhedged_mean": float(uh.mean()), "shuffled_vix_placebo_mean": float(np.mean(pl["pnl"] / pl["prem"])),
            "hedge_cost_1bp_mean": float(np.mean(one_bp["pnl"] / one_bp["prem"])), "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ================================================================================== short option path engine ==

def _smile_ratio(smile: Smile, m, dte) -> np.ndarray:
    m, dte = np.broadcast_arrays(np.asarray(m, dtype=float), np.asarray(dte, dtype=float))
    keys = np.array(sorted(smile.curves), dtype=float)
    near = keys[np.argmin(np.abs(dte[..., None] - keys), axis=-1)]
    out = np.empty(m.shape)
    for t in keys:
        sel = near == t
        ks, rs = smile.curves[int(t)]
        out[sel] = np.interp(m[sel], ks, rs)
    return out


def short_option_paths(fr: dict, entries, legs, dte: int = 45, iv_scale: float = 1.0, smile: Optional[Smile] = None) -> dict:
    """Short option legs entered at the close of each entry day, expiring on the last trading day on or before entry +
    ``dte`` calendar days. legs: [(kind, delta)]; strikes at the target BS delta on the dividend forward at
    sigma = iv_scale * VIX/100. Marked to model at every close at the same scale of that day's VIX (or the captured smile
    level: VIX_j/100 x IV/VIX ratio at K/S_j) to expiry, where the mark is the intrinsic value on the raw close."""
    days, ords, n = fr["days"], fr["ords"], len(fr["days"])
    e = np.asarray(entries, dtype=np.int64)
    xs = np.searchsorted(ords, ords[e] + dte, side="right") - 1
    ok = (xs > e) & (ords[e] + dte <= ords[-1])
    e, xs = e[ok], xs[ok]
    if e.size == 0:
        return {"n": 0}
    W = int((xs - e).max())
    I = e[:, None] + np.arange(W + 1)[None, :]
    live = I <= xs[:, None]
    I = np.minimum(I, n - 1)
    S = fr["close"][I]
    tt = ords[I].astype(float)
    tx = ords[xs].astype(float)
    T = np.maximum(tx[:, None] - tt, 0.0) / 365.0
    r = fr["rate"][e]
    v = fr["vix"][I] / 100.0
    D = np.where(live, fr["div"][I], 0.0)
    D[:, 0] = 0.0
    Sx = S - _pv_divs(D > 0, fr["fc"][e], tt, r)
    sig0 = np.maximum(iv_scale * v[:, 0], 0.01)
    marks = np.zeros(S.shape)
    strikes, itm = [], np.zeros(e.size, dtype=int)
    col_x = xs - e
    for kind, dl in legs:
        K = np.array([bs.strike_for_delta(Sx[i, 0], T[i, 0], r[i], sig0[i], dl, kind) for i in range(e.size)])
        if smile is None:
            sig = np.maximum(iv_scale * v, 0.01)
        else:
            sig = np.maximum(v * _smile_ratio(smile, K[:, None] / S, T * 365.0), 0.01)
        marks += bs.price(Sx, K[:, None], T, r[:, None], sig, kind)
        sx = S[np.arange(e.size), col_x]
        itm += ((sx - K) > 0 if kind == "call" else (K - sx) > 0).astype(int)
        strikes.append(K)
    credit = marks[:, 0].copy()
    return {"n": int(e.size), "entries": e, "xs": xs, "col_x": col_x, "I": I, "live": live, "tt": tt, "tx": tx,
            "marks": np.where(live, marks, np.nan), "credit": credit, "strikes": strikes, "spot": S[:, 0], "itm": itm,
            "n_legs": len(legs), "days": [days[a] for a in e]}


def _first_true(mask) -> np.ndarray:
    has = mask.any(axis=1)
    return np.where(has, mask.argmax(axis=1), -1)


def exit_columns(p: dict, exit_dte: int = 21, target: float = 0.5) -> dict:
    """Exit column per position for: hold (expiry), dte21 (first close with <= exit_dte calendar days left), target (first
    close at or below target x credit, else expiry), target_or_dte (the earlier of target and dte21)."""
    m, w = p["marks"].shape
    col = np.arange(w)[None, :]
    left = p["tx"][:, None] - p["tt"]
    before_x = col < p["col_x"][:, None]
    c21 = _first_true((left <= exit_dte) & p["live"] & (col >= 1))
    c21 = np.where(c21 < 0, p["col_x"], c21)
    with np.errstate(invalid="ignore"):
        hit = (p["marks"] <= target * p["credit"][:, None]) & p["live"] & (col >= 1) & before_x
    ctg = _first_true(hit)
    return {"hold": p["col_x"].copy(), "dte21": c21, "target50": np.where(ctg >= 0, ctg, p["col_x"]),
            "target50_or_dte21": np.where((ctg >= 0) & (ctg < c21), ctg, c21)}


def rule_pnl(p: dict, cols, comm: float = COMM_PER_SHARE) -> dict:
    """Per-position P&L (per share) of closing at ``cols``: credit - mark - commissions (open every leg; close every leg
    when exiting before expiry, only the in-the-money legs at expiry), days in the trade and P&L per day / entry spot."""
    rows = np.arange(p["n"])
    mark = p["marks"][rows, cols]
    early = cols < p["col_x"]
    n_close = np.where(early, p["n_legs"], p["itm"])
    pnl = p["credit"] - mark - comm * (p["n_legs"] + n_close)
    days_in = p["tt"][rows, cols] - p["tt"][:, 0]
    return {"pnl": pnl, "days": days_in, "ppd": pnl / p["spot"] / np.maximum(days_in, 1.0)}


# ===================================================================================== T-156 45-DTE strangle ==

def exit_rule_test(diff, n_rules: int = 3, block: int = 6, n_boot: int = 2000, seed: int = 0) -> dict:
    """Paired (by entry) difference of two exit rules: full-sample and per-half means with studentized block-bootstrap CIs at
    the Bonferroni level 1 - 0.05 / n_rules (the deflation for the rules compared)."""
    d = np.asarray(diff, dtype=float)
    level = 1.0 - 0.05 / n_rules
    h = d.size // 2
    out = {"level": level, "n": int(d.size), "mean": float(d.mean()) if d.size else None,
           "ci": list(stud_ci(d, block, level, n_boot, seed)), "halves": []}
    for part in (d[:h], d[h:]):
        out["halves"].append({"n": int(part.size), "mean": float(part.mean()) if part.size else None,
                              "ci": list(stud_ci(part, block, level, n_boot, seed))})
    out["dsr_n_trials"] = float(deflated_sharpe_ratio(d, n_rules)) if d.size > 3 else None
    return out


def _month_starts(days) -> np.ndarray:
    return np.array([i for i in range(len(days)) if i == 0 or days[i][:7] != days[i - 1][:7]], dtype=np.int64)


def _week_starts(days) -> np.ndarray:
    wk = [date.fromisoformat(d).isocalendar()[:2] for d in days]
    return np.array([i for i in range(len(days)) if i == 0 or wk[i] != wk[i - 1]], dtype=np.int64)


def theta_harvest(fr: dict, smile: Optional[Smile] = None, daily: bool = True, delta: float = 0.16, dte: int = 45,
                  block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300) -> dict:
    """T-156: 45-DTE 0.16-delta SPY short strangle priced and marked at VIX (flat). Statistic: mean P&L per day in the trade
    (P&L / entry spot / calendar days), 21-DTE exit minus hold to expiry, paired by entry. CIs on non-overlapping monthly
    entries (first trading day of each month; block 6 covers the 45-day overlap), Bonferroni level for the three rules.
    Pass: > 0 with the CI excluding 0 in both halves; min_n 300 monthly entries. Commissions $0.65 per contract."""
    legs = [("put", -delta), ("call", delta)]
    me = _month_starts(fr["days"])

    def run(entries, scale=1.0, sm=None):
        p = short_option_paths(fr, entries, legs, dte, scale, sm)
        if p["n"] == 0:
            return p, {}
        cols = exit_columns(p)
        return p, {k: rule_pnl(p, c) for k, c in cols.items()}

    p, rules = run(me)
    n = int(p.get("n", 0))
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} monthly entries"}
    diff = rules["dte21"]["ppd"] - rules["hold"]["ppd"]
    t = exit_rule_test(diff, 3, block, n_boot, seed)
    bp = 1e4
    crit, parts = [], []
    for i, hpart in enumerate(t["halves"]):
        lo, hi = hpart["ci"]
        crit.append((f"half {i + 1}: (21-DTE - hold) P&L/day > 0, {t['level'] * 100:.2f}% CI (Bonferroni, 3 rules) excludes 0",
                     None if lo is None else bool(lo > 0), hi is not None and hi < 0))
        parts.append(f"half {i + 1} ({hpart['n']} entries): {_s(hpart['mean'] and hpart['mean'] * bp, 3)} bp/day "
                     f"({_ci_s(hpart['ci'], 3, bp)})")
    means = {k: float(v["ppd"].mean() * bp) for k, v in rules.items()}
    sds = {k: float(v["ppd"].std(ddof=1) * bp) for k, v in rules.items()}
    parts.insert(0, f"full sample {t['mean'] * bp:+.3f} bp of spot per day ({_ci_s(t['ci'], 3, bp)}); P&L/day by rule (bp, sd): "
                 + ", ".join(f"{k} {means[k]:+.2f} ({sds[k]:.2f})" for k in ("hold", "dte21", "target50", "target50_or_dte21")))
    sens = {}
    for s in (0.81, 0.90):
        _, rr = run(me, s)
        sens[f"{s:.2f}"] = float((rr["dte21"]["ppd"] - rr["hold"]["ppd"]).mean() * bp)
    if smile is not None:
        _, rr = run(me, 1.0, smile)
        sens["captured_smile"] = float((rr["dte21"]["ppd"] - rr["hold"]["ppd"]).mean() * bp)
    parts.append("IV sensitivity of the mean difference (bp/day) " + ", ".join(f"{k} {v:+.3f}" for k, v in sens.items())
                 + ("" if smile is not None else "; captured-smile (skew) sensitivity not run: no spy-smile bundle"))
    daily_est = None
    if daily:
        _, rd = run(np.arange(len(fr["days"])))
        if rd:
            daily_est = float((rd["dte21"]["ppd"] - rd["hold"]["ppd"]).mean() * bp)
            parts.append(f"daily entries ({rd['hold']['ppd'].size}) point estimate {daily_est:+.3f} bp/day")
    verdict, why = _decide(crit, n, min_n, "monthly entries")
    reason = (f"{MP} 45-DTE 0.16-delta SPY short strangle at VIX on the dividend forward, marked daily at VIX, settled on raw "
              f"closes, $0.65/contract; {n} monthly entries {p['days'][0]}..{p['days'][-1]}, P&L per day in bp of entry spot: "
              + "; ".join(parts) + f"; margin-time cost not charged (P&L per day already scales by time); {TRADED_NOTE}" + f" — {why}")
    stat = {"model_priced": True, "n_monthly_entries": n, "test": t, "mean_ppd_bp": means, "sd_ppd_bp": sds,
            "mean_days_in_trade": {k: float(v["days"].mean()) for k, v in rules.items()}, "iv_sensitivity_bp": sens,
            "daily_entries_estimate_bp": daily_est, "commission_per_contract": 0.65, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ======================================================================================= T-157 theta ladder ==

def put_book(fr: dict, entries, size: float, delta: float = -0.16, dte: int = 45, iv_scale: float = 1.0,
             comm: float = COMM_PER_SHARE) -> dict:
    """Daily P&L of a book of short puts (0.16 delta, 45 DTE, closed at 50% of the credit or 21 DTE), each sized at ``size``
    units of strike notional (size / K shares). P&L per unit notional, marked to model at each close; commissions per share
    on every fill. Returns the daily P&L and open notional on the frame's calendar."""
    n = len(fr["days"])
    pnl = np.zeros(n)
    expo = np.zeros(n)
    p = short_option_paths(fr, entries, [("put", delta)], dte, iv_scale)
    if p["n"] == 0:
        return {"pnl": pnl, "exposure": expo, "n_positions": 0, "first": None, "last": None}
    cols = exit_columns(p)["target50_or_dte21"]
    q = size / p["strikes"][0]
    marks = np.where(p["live"], p["marks"], 0.0)
    w = marks.shape[1]
    col = np.arange(w)[None, :]
    step = np.zeros_like(marks)
    step[:, 1:] = -(marks[:, 1:] - marks[:, :-1])
    held = (col >= 1) & (col <= cols[:, None])
    daily = np.where(held, step, 0.0) * q[:, None]
    daily[:, 0] -= comm * q                                             # open
    rows = np.arange(p["n"])
    early = cols < p["col_x"]
    daily[rows, cols] -= comm * q * np.where(early, 1, p["itm"])         # close (expiry: only if in the money)
    np.add.at(pnl, p["I"].ravel(), daily.ravel())
    open_ = (col < cols[:, None]) & p["live"]
    np.add.at(expo, p["I"][open_], size)
    return {"pnl": pnl, "exposure": expo, "n_positions": int(p["n"]), "first": int(p["entries"][0]),
            "last": int((p["entries"] + cols).max()), "mean_moneyness": float(np.mean(p["strikes"][0] / p["spot"])),
            "trade_pnl_per_notional": (p["credit"] - p["marks"][rows, cols]) / p["strikes"][0]}


def ladder_verdict(pl_ladder, pl_single, block: int = 63, n_boot: int = 1000, seed: int = 0, bound: float = 0.85) -> dict:
    """Drawdown ratio (ladder / single) on the full span and in each half, with a paired percentile block-bootstrap CI.
    Criteria: in each half, ratio < ``bound`` and CI upper < 1."""
    a = np.asarray(pl_ladder, dtype=float)
    b = np.asarray(pl_single, dtype=float)
    h = a.size // 2
    full = mdd_ratio_ci(a, b, block, n_boot, seed)
    halves = [mdd_ratio_ci(a[:h], b[:h], block, n_boot, seed), mdd_ratio_ci(a[h:], b[h:], block, n_boot, seed)]
    crit = []
    for i, hv in enumerate(halves):
        ok = None if hv["ratio"] is None or hv["ci"][1] is None else bool(hv["ratio"] < bound and hv["ci"][1] < 1.0)
        dec = hv["ci"][0] is not None and hv["ci"][0] >= bound          # interval wholly at or above the bound
        crit.append((f"half {i + 1}: drawdown ratio < {bound} with bootstrap CI upper < 1", ok, dec))
    return {"full": full, "halves": halves, "crit": crit}


def theta_ladder(fr: dict, block: int = 63, n_boot: int = 4000, seed: int = 0, min_n: int = 300) -> dict:
    """T-157: weekly ladder of quarter-size 0.16-delta short puts vs a full-size monthly entry, both 45 DTE and closed at 50%
    of the credit or 21 DTE, priced and marked at VIX. Pass: drawdown ratio < 0.85 with the bootstrap CI upper < 1 in both
    halves; min_n 300 months."""
    single = put_book(fr, _month_starts(fr["days"]), 1.0)
    ladder = put_book(fr, _week_starts(fr["days"]), 0.25)
    if single["first"] is None or ladder["first"] is None:
        return {"verdict": "inconclusive", "n": 0, "reason": "no complete positions"}
    a0 = min(single["first"], ladder["first"])
    a1 = max(single["last"], ladder["last"]) + 1
    L, S = ladder["pnl"][a0:a1], single["pnl"][a0:a1]
    months = len({d[:7] for d in fr["days"][a0:a1]})
    v = ladder_verdict(L, S, block, n_boot, seed)
    crit = v["crit"]
    sens = {}
    for s in (0.81, 0.90):
        s1 = put_book(fr, _month_starts(fr["days"]), 1.0, iv_scale=s)
        l1 = put_book(fr, _week_starts(fr["days"]), 0.25, iv_scale=s)
        mb = float(_mdd_abs(s1["pnl"][a0:a1])[0])
        sens[f"{s:.2f}"] = float(_mdd_abs(l1["pnl"][a0:a1])[0]) / mb if mb > 0 else None

    def monthly(pl, ex):
        ms = {}
        for d, x in zip(fr["days"][a0:a1], pl):
            ms[d[:7]] = ms.get(d[:7], 0.0) + x
        arr = np.array(list(ms.values()))
        m_ex = float(np.mean(ex[a0:a1]))
        return {"mean_per_margin": float(arr.mean() / m_ex) if m_ex > 0 else None,
                "sd_per_margin": float(arr.std(ddof=1) / m_ex) if m_ex > 0 else None, "mean_open_notional": m_ex}

    mo = {"ladder": monthly(L, ladder["exposure"]), "single": monthly(S, single["exposure"])}
    f = v["full"]
    parts = [f"full span ratio {_f(f['ratio'], 3)} (MDD ladder {f['mdd_a'] * 100:.1f}% vs single {f['mdd_b'] * 100:.1f}% of notional, "
             f"95% CI {_f(f['ci'][0], 2)}-{_f(f['ci'][1], 2)})"]
    for i, hv in enumerate(v["halves"]):
        parts.append(f"half {i + 1}: ratio {_f(hv['ratio'], 3)} (CI {_f(hv['ci'][0], 2)}-{_f(hv['ci'][1], 2)})")
    parts.append(f"mean monthly P&L per unit margin ladder {mo['ladder']['mean_per_margin'] * 100:+.2f}% (sd {mo['ladder']['sd_per_margin'] * 100:.2f}%) "
                 f"vs single {mo['single']['mean_per_margin'] * 100:+.2f}% (sd {mo['single']['sd_per_margin'] * 100:.2f}%); open notional "
                 f"{mo['ladder']['mean_open_notional']:.2f} vs {mo['single']['mean_open_notional']:.2f}")
    parts.append(f"delta-matched (both 0.16 at entry): mean K/S {ladder['mean_moneyness']:.3f} vs {single['mean_moneyness']:.3f}")
    parts.append("IV sensitivity of the full-span ratio " + ", ".join(f"s={k} {_f(x, 3)}" for k, x in sens.items()))
    verdict, why = _decide(crit, months, min_n, "months")
    reason = (f"{MP} 0.16-delta 45-DTE SPY short puts at VIX on the dividend forward, marked daily, closed at 50% of credit or "
              f"21 DTE, $0.65/contract per fill (four times the fills for the ladder); {ladder['n_positions']} ladder rungs vs "
              f"{single['n_positions']} monthly entries over {months} months {fr['days'][a0]}..{fr['days'][a1 - 1]}; drawdowns of the "
              f"additive P&L per unit notional, paired percentile block bootstrap (block {block} days): " + "; ".join(parts)
              + f"; {TRADED_NOTE}" + f" — {why}")
    stat = {"model_priced": True, "n_months": months, "full": f, "halves": v["halves"], "monthly": mo, "iv_sensitivity_ratio": sens,
            "n_ladder_rungs": ladder["n_positions"], "n_single_entries": single["n_positions"], "block_days": block, "verdict": verdict}
    return {"verdict": verdict, "n": months, "reason": reason, "stat": stat}


# =============================================================================== model-free variance claims ==

def _cycles_rv(closes, idx_start: int = 0, hold: int = HOLD):
    """Non-overlapping cycles from idx_start: entries a, forward realised variance over returns a+1..a+hold (annualised)."""
    c = np.asarray(closes, dtype=float)
    lr = np.log(c[1:] / c[:-1])
    starts = np.arange(idx_start, c.size - hold, hold)
    rv = np.array([PPY / hold * float(np.sum(lr[a:a + hold] ** 2)) for a in starts])
    return starts, rv


def short_variance_units(days, close, vix, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 390,
                         checks: Optional[dict] = None) -> dict:
    """T-540: short 30-day variance struck at VIX_t^2 settled on the next 21 close-to-close log returns; P&L = (VIX^2 -
    RV21) / 12 in %^2 per month over non-overlapping cycles. Pass: lower 95% studentized CI > 0; min_n 390 cycles.
    ``checks``: {label: closes aligned to ``days``} for basis checks on the same cycle dates."""
    vix = np.asarray(vix, dtype=float)
    starts, rv = _cycles_rv(close)
    n = int(starts.size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles"}
    x = (vix[starts] ** 2 - rv * 1e4) / 12.0
    lo, hi = stud_ci(x, block, 0.95, n_boot, seed)
    worst = int(np.argmin(x))
    ex = np.delete(x, worst)
    d = _desc(x)
    rep = {}
    for lab, cc in (checks or {}).items():
        cc = np.asarray(cc, dtype=float)
        ok = np.isfinite(cc)
        sel = [i for i, a in enumerate(starts) if ok[a] and ok[a + HOLD] and ok[a:a + HOLD + 1].all()]
        if sel:
            _, rv2 = _cycles_rv(cc)
            y = (vix[starts[sel]] ** 2 - rv2[sel] * 1e4) / 12.0
            rep[lab] = {"n": len(sel), "mean": float(y.mean())}
    crit = [("lower 95% CI of mean (VIX^2 - RV21)/12 > 0", None if lo is None else bool(lo > 0), hi is not None and hi < 0)]
    verdict, why = _decide(crit, n, min_n, "cycles")
    reason = (f"short variance struck at VIX^2, {n} non-overlapping 21-day cycles {days[starts[0]]}..{days[starts[-1]]}: mean "
              f"{x.mean():+.2f} %^2/month (studentized 95% {_ci_s((lo, hi))}), skew {d['skew']:.2f}, kurtosis {d['kurtosis']:.1f}, "
              f"worst cycle {x[worst]:+.1f} on {days[starts[worst]]}, mean ex-worst {ex.mean():+.2f}"
              + "".join(f"; {k} basis {v['mean']:+.2f} (n {v['n']})" for k, v in rep.items()) + f" — {why}")
    stat = {"n_cycles": n, "mean_pct2_per_month": float(x.mean()), "ci95": [lo, hi], **{f"desc_{k}": v for k, v in d.items()},
            "worst_cycle": float(x[worst]), "worst_day": days[starts[worst]], "mean_ex_worst": float(ex.mean()),
            "share_positive": float((x > 0).mean()), "thirds": _thirds(x), "checks": rep, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def vix2_win_rate(days, close, vix, bound: float = 0.75, block: int = 6, n_boot: int = 2000, seed: int = 0, min_n: int = 300,
                  checks: Optional[dict] = None, truncation: Optional[list] = None) -> dict:
    """T-234: share of non-overlapping 21-day cycles with (VIX_t/100)^2 > RV_{t,t+21}. Pass: lower 95% bound (exact
    Clopper-Pearson, two-sided, and the percentile block bootstrap) > 0.75, and the win rate > 0.75 in all three thirds;
    min_n 300 cycles. The strip truncation error on the captured chain is reported, not part of the pass."""
    vix = np.asarray(vix, dtype=float)
    starts, rv = _cycles_rv(close)
    n = int(starts.size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles"}
    iv = (vix[starts] / 100.0) ** 2
    win = (iv > rv).astype(float)
    k = int(win.sum())
    cp = _binom_two_sided_ci(k, n)
    bb = pct_ci(win, block, 0.95, n_boot, seed)
    th = _thirds(win)
    crit = [(f"exact binomial lower 95% bound > {bound}", bool(cp[0] > bound), cp[1] < bound),
            (f"block-bootstrap lower 95% bound > {bound}", None if bb[0] is None else bool(bb[0] > bound), bb[1] is not None and bb[1] < bound),
            (f"win rate > {bound} in all three thirds", all(t > bound for t in th), False)]
    logr = np.log(np.maximum(rv, 1e-12) / iv)
    pnl_vega1 = (vix[starts] ** 2 - rv * 1e4) / (2.0 * vix[starts])     # short variance swap, vega notional 1 per vol point
    rep = {}
    for lab, cc in (checks or {}).items():
        cc = np.asarray(cc, dtype=float)
        okc = np.isfinite(cc)
        sel = [i for i, a in enumerate(starts) if okc[a:a + HOLD + 1].all()]
        if sel:
            _, rv2 = _cycles_rv(np.where(okc, cc, 1.0))
            rep[lab] = {"n": len(sel), "win_rate": float(np.mean(iv[sel] > rv2[sel]))}
    rng = np.random.default_rng(seed)
    lr = np.log(np.asarray(close, dtype=float)[1:] / np.asarray(close, dtype=float)[:-1])
    sh = rng.permutation(lr)
    rv_sh = np.array([PPY / HOLD * float(np.sum(sh[a:a + HOLD] ** 2)) for a in starts])
    placebo = float(np.mean(iv > rv_sh))
    parts = [f"win rate {k}/{n} = {k / n:.3f} (Clopper-Pearson {cp[0]:.3f}-{cp[1]:.3f}; block bootstrap {_f(bb[0], 3)}-{_f(bb[1], 3)})",
             "thirds " + "/".join(f"{t:.3f}" for t in th),
             f"mean ln(RV/VIX^2) {logr.mean():+.3f}, short var swap (vega notional 1) {pnl_vega1.mean():+.2f} per cycle",
             f"shuffled-returns placebo win rate {placebo:.3f}"]
    parts += [f"{lab} check win rate {v['win_rate']:.3f} (n {v['n']})" for lab, v in rep.items()]
    if truncation:
        parts.append("strip vs VIX^2 on the captured SPX chain (reported, not in the pass): " + ", ".join(
            f"{t['quote_day']} {_s(t.get('error') and t['error'] * 100, 1)}%" for t in truncation))
    else:
        parts.append("strip truncation check not run (no captured SPX chain)")
    verdict, why = _decide(crit, n, min_n, "cycles")
    reason = (f"model-free: (VIX/100)^2 vs next 21-day ^GSPC realised variance (price returns), {n} non-overlapping cycles "
              f"{days[starts[0]]}..{days[starts[-1]]}: " + "; ".join(parts) + f" — {why}")
    stat = {"n_cycles": n, "wins": k, "win_rate": k / n, "clopper_pearson": list(cp), "block_bootstrap": list(bb), "thirds": th,
            "mean_log_rv_over_vix2": float(logr.mean()), "short_var_swap_vega1_mean": float(pnl_vega1.mean()),
            "shuffled_returns_placebo": placebo, "checks": rep, "truncation": truncation or [], "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def har_forecast(closes, refit_mask, min_obs: int = 500) -> np.ndarray:
    """Walk-forward HAR(1,5,22) forecast of the next-21-day annualised realised variance at each close. Regressors at close
    i: 252 r_i^2, 252 mean(r_{i-4..i}^2), 252 mean(r_{i-21..i}^2); target 252 mean(r_{i+1..i+21}^2). Refit (OLS, expanding
    window) at each day where ``refit_mask`` is True using only samples whose target window has closed (i + 21 <= refit
    day); a day's forecast uses the latest refit on or before it. NaN before the first refit with ``min_obs`` samples."""
    c = np.asarray(closes, dtype=float)
    n = c.size
    r2 = np.zeros(n)
    r2[1:] = np.log(c[1:] / c[:-1]) ** 2
    cs = np.concatenate([[0.0], np.cumsum(r2)])
    X = np.full((n, 4), np.nan)
    y = np.full(n, np.nan)
    for i in range(22, n):
        X[i] = [1.0, PPY * r2[i], PPY * (cs[i + 1] - cs[i - 4]) / 5.0, PPY * (cs[i + 1] - cs[i - 21]) / 22.0]
    for i in range(22, n - HOLD):
        y[i] = PPY * (cs[i + HOLD + 1] - cs[i + 1]) / HOLD
    valid = np.isfinite(y) & np.isfinite(X).all(axis=1)
    Xv = np.where(valid[:, None], X, 0.0)
    yv = np.where(valid, y, 0.0)
    cXX = np.cumsum(Xv[:, :, None] * Xv[:, None, :], axis=0)
    cXy = np.cumsum(Xv * yv[:, None], axis=0)
    cN = np.cumsum(valid)
    out = np.full(n, np.nan)
    beta = None
    for d in range(n):
        if refit_mask[d] and d - HOLD >= 0 and cN[d - HOLD] >= min_obs:
            try:
                beta = np.linalg.solve(cXX[d - HOLD], cXy[d - HOLD])
            except np.linalg.LinAlgError:
                pass
        if beta is not None and np.isfinite(X[d]).all():
            out[d] = float(X[d] @ beta)
    return out


def scaled_short_variance(days, closes, vix: dict, start: str = "1991-01-01", block: int = 6, n_boot: int = 2000, seed: int = 0,
                          min_n: int = 300, min_hist: int = 120) -> dict:
    """T-235: monthly (21-day) short variance P&L (VIX_t/100)^2 - RV_{t,t+21} on ^GSPC closes; scaled by N_t = max(z_t, 0)
    with z_t the expanding z-score of VIX/100 minus the walk-forward HAR vol forecast (history of daily spreads strictly
    before t). Pass: Sharpe(scaled) - Sharpe(constant) > 0 at one-sided p < 0.05 (studentized block bootstrap) and PBO < 0.3
    across the declared rules {linear max(z,0), on/off z > 0.5, on/off z > 1}; min_n 300 cycles."""
    days = list(days)
    c = np.asarray(closes, dtype=float)
    refit = np.array([i == 0 or days[i][:7] != days[i - 1][:7] for i in range(len(days))])
    f = har_forecast(c, refit)
    has_v = np.array([d in vix for d in days])
    vv = np.array([vix.get(d, np.nan) for d in days], dtype=float) / 100.0
    spread = np.where(has_v & np.isfinite(f), vv - np.sqrt(np.maximum(f, 1e-8)), np.nan)
    lr = np.zeros(c.size)
    lr[1:] = np.log(c[1:] / c[:-1])
    first = next((i for i, d in enumerate(days) if d >= start), None)
    if first is None:
        return {"verdict": "inconclusive", "n": 0, "reason": f"no data after {start}"}
    starts = np.arange(first, c.size - HOLD, HOLD)
    starts = starts[has_v[starts] & np.isfinite(spread[starts])]
    # expanding z-score of the spread from the days strictly before each entry
    sp_ok = np.isfinite(spread)
    s1 = np.concatenate([[0.0], np.cumsum(np.where(sp_ok, spread, 0.0))])
    s2 = np.concatenate([[0.0], np.cumsum(np.where(sp_ok, spread ** 2, 0.0))])
    cnt = np.concatenate([[0], np.cumsum(sp_ok)])
    z = np.full(starts.size, np.nan)
    zv = np.full(starts.size, np.nan)
    vl = np.where(has_v, vv, np.nan)
    v_ok = np.isfinite(vl)
    v1 = np.concatenate([[0.0], np.cumsum(np.where(v_ok, vl, 0.0))])
    v2 = np.concatenate([[0.0], np.cumsum(np.where(v_ok, vl ** 2, 0.0))])
    vc = np.concatenate([[0], np.cumsum(v_ok)])
    for j, a in enumerate(starts):
        k = cnt[a]
        if k >= min_hist:
            m = s1[a] / k
            sd = math.sqrt(max(s2[a] / k - m * m, 1e-12))
            z[j] = (spread[a] - m) / sd
        kv = vc[a]
        if kv >= min_hist:
            m = v1[a] / kv
            sd = math.sqrt(max(v2[a] / kv - m * m, 1e-12))
            zv[j] = (vl[a] - m) / sd
    keep = np.isfinite(z)
    starts, z, zv = starts[keep], z[keep], zv[keep]
    n = int(starts.size)
    if n < 16:
        return {"verdict": "inconclusive", "n": n, "reason": f"only {n} cycles with a HAR forecast and spread history"}
    rv = np.array([PPY / HOLD * float(np.sum(lr[a + 1:a + HOLD + 1] ** 2)) for a in starts])
    base = vv[starts] ** 2 - rv
    rules = {"linear max(z,0)": np.maximum(z, 0.0), "on/off z>0.5": (z > 0.5).astype(float), "on/off z>1": (z > 1.0).astype(float)}
    R = np.column_stack([w * base for w in rules.values()])
    ppy = PPY / HOLD
    t = sharpe_diff_test(R[:, 0], base, block, n_boot, seed)
    pbo = pbo_cscv(R, 8) if n >= 32 else {"pbo": None}
    sr = {k: float(sharpe_ratio(R[:, i], ppy)) for i, k in enumerate(rules)}
    sr_c = float(sharpe_ratio(base, ppy))
    vix_only = np.maximum(np.nan_to_num(zv, nan=0.0), 0.0) * base
    rng = np.random.default_rng(seed)
    placebo = np.maximum(rng.permutation(z), 0.0) * base
    top = np.maximum(z, 0) * base
    q = np.quantile(z, 2 / 3)
    top_share = float(top[z > q].sum() / top.sum()) if top.sum() != 0 else None
    crit = [("Sharpe(linear max(z,0)) - Sharpe(constant) > 0 at one-sided p < 0.05",
             None if t["p"] is None else bool(t["diff"] > 0 and t["p"] < 0.05), t["ci"][1] is not None and t["ci"][1] < 0),
            ("PBO < 0.3 across the three declared rules", None if pbo.get("pbo") is None else bool(pbo["pbo"] < 0.3), False)]
    verdict, why = _decide(crit, n, min_n, "cycles")
    reason = (f"model-free short 21-day ^GSPC variance struck at VIX^2, {n} monthly cycles {days[starts[0]]}..{days[starts[-1]]}, "
              f"HAR(1,5,22) refit monthly on an expanding window: annualised Sharpe scaled {sr['linear max(z,0)']:.2f} vs constant "
              f"{sr_c:.2f} (per-cycle difference {_s(t['diff'], 3)}, studentized one-sided p {_f(t['p'], 3)}, 95% {_ci_s(t['ci'], 3)}); "
              f"on/off z>0.5 {sr['on/off z>0.5']:.2f}, z>1 {sr['on/off z>1']:.2f}; PBO {_f(pbo.get('pbo'), 3)}; controls: "
              f"VIX-level-only scaling Sharpe {sharpe_ratio(vix_only, ppy):.2f}, random-z placebo {sharpe_ratio(placebo, ppy):.2f}, "
              f"top-tercile-z share of scaled P&L {_f(top_share, 2)}" + f" — {why}")
    stat = {"n_cycles": n, "sharpe_annual": sr, "sharpe_constant": sr_c, "sharpe_diff_test": t, "pbo": pbo.get("pbo"),
            "pbo_detail": pbo, "vix_level_only_sharpe": float(sharpe_ratio(vix_only, ppy)),
            "random_z_placebo_sharpe": float(sharpe_ratio(placebo, ppy)), "top_tercile_share": top_share,
            "mean_z": float(z.mean()), "share_z_positive": float((z > 0).mean()), "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


def vix1d_premium(days, closes, vix1d: dict, vix: Optional[dict] = None, events: Optional[dict] = None, block: int = 5,
                  n_boot: int = 2000, seed: int = 0, min_n: int = 500) -> dict:
    """T-529: x_t = (VIX1D_t/100)^2/365 - r_{t+1}^2 with r_{t+1} the next trading day's ^GSPC close-to-close log return.
    Pass: mean > 0 with the 95% studentized block-bootstrap CI (5-day blocks) excluding 0, and positive in both halves;
    min_n 500 one-day windows. /252 and VIX-implied daily variance ((VIX/100)^2 x 30/365 / 21) reported; event days
    (FOMC decision, CPI, employment report) reported separately."""
    days = list(days)
    c = np.asarray(closes, dtype=float)
    idx = [i for i in range(len(days) - 1) if days[i] in vix1d]
    if len(idx) < 8:
        return {"verdict": "inconclusive", "n": len(idx), "reason": f"only {len(idx)} VIX1D days with a next ^GSPC close"}
    ii = np.array(idx)
    v = np.array([vix1d[days[i]] for i in idx]) / 100.0
    r2 = np.log(c[ii + 1] / c[ii]) ** 2
    x = v ** 2 / 365.0 - r2
    x252 = v ** 2 / 252.0 - r2
    n = int(x.size)
    lo, hi = stud_ci(x, block, 0.95, n_boot, seed)
    hv = _halves(x)
    crit = [("mean > 0 with 95% CI excluding 0 (/365)", None if lo is None else bool(lo > 0), hi is not None and hi < 0),
            ("mean > 0 in both halves", all(h is not None and h > 0 for h in hv), False)]
    s = 1e4
    parts = [f"mean {x.mean() * s:+.4f} %^2 per day ({_ci_s((lo, hi), 4, s)}), halves {hv[0] * s:+.4f}/{hv[1] * s:+.4f}",
             f"/252 convention {x252.mean() * s:+.4f}", f"implied {np.mean(v ** 2 / 365) * s:.4f} vs realised {r2.mean() * s:.4f}"]
    rep = {}
    if vix:
        vx = np.array([vix.get(days[i], np.nan) for i in idx]) / 100.0
        ok = np.isfinite(vx)
        if ok.any():
            xv = vx[ok] ** 2 * (30.0 / 365.0) / HOLD - r2[ok]
            rep["vix_scaled_daily_premium"] = float(xv.mean())
            rep["vix1d_premium_same_days"] = float(x[ok].mean())
            parts.append(f"VIX-scaled 1-day premium {xv.mean() * s:+.4f} on the same {int(ok.sum())} days")
    if events:
        evd = set().union(*events.values()) if events else set()
        nxt = np.array([days[i + 1] in evd for i in idx])
        if nxt.any():
            rep["event_days"] = {"n": int(nxt.sum()), "mean": float(x[nxt].mean()), "non_event_mean": float(x[~nxt].mean())}
            lo2, hi2 = stud_ci(x[~nxt], block, 0.95, n_boot, seed)
            rep["ex_events_ci"] = [lo2, hi2]
            parts.append(f"next day an event ({'/'.join(sorted(events))}) on {int(nxt.sum())} days: mean {x[nxt].mean() * s:+.4f}; "
                         f"ex-events {x[~nxt].mean() * s:+.4f} ({_ci_s((lo2, hi2), 4, s)})")
    verdict, why = _decide(crit, n, min_n, "one-day windows")
    reason = (f"model-free: (VIX1D/100)^2/365 vs next-day ^GSPC squared log return, {n} days {days[idx[0]]}..{days[idx[-1]]}: "
              + "; ".join(parts) + f" — {why}")
    stat = {"n_days": n, "mean": float(x.mean()), "ci95": [lo, hi], "halves": hv, "mean_252": float(x252.mean()),
            "mean_implied": float(np.mean(v ** 2 / 365)), "mean_realised": float(r2.mean()), **rep, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ================================================================================ VIX strip on a captured chain ==

def strip_variance(chain_values, quote_day: str, r: float, target_days: int = 30, root: str = "SPXW") -> Optional[dict]:
    """CBOE VIX-method 30-day variance from one captured SPX chain (PM-settled ``root`` series): mid quotes of OTM options,
    strikes after two consecutive zero bids dropped, forward from the strike with the smallest |C - P|, near and next
    terms bracketing ``target_days`` interpolated in total variance. T in calendar days / 365 from the quote day close."""
    by: dict = {}
    for v in chain_values:
        sym = v.get("sym") or ""
        mt = re.match(r"([A-Z]+)", sym)
        if not mt or mt.group(1) != root:
            continue
        b, a = v.get("bid"), v.get("ask")
        if b is None or a is None or a <= 0:
            continue
        by.setdefault(v["expiry"], {}).setdefault(float(v["strike"]), {})[v["type"]] = ((float(b) + float(a)) / 2.0, float(b))
    q = date.fromisoformat(quote_day)
    terms = sorted(((date.fromisoformat(e) - q).days, e) for e in by if (date.fromisoformat(e) - q).days > 0)
    near = [t for t in terms if t[0] <= target_days]
    nxt = [t for t in terms if t[0] > target_days]
    if not near or not nxt:
        return None

    def one(e, nd):
        T = nd / 365.0
        rec = by[e]
        both = [K for K in sorted(rec) if "call" in rec[K] and "put" in rec[K] and rec[K]["call"][1] > 0 and rec[K]["put"][1] > 0]
        if not both:
            return None
        ks = min(both, key=lambda K: abs(rec[K]["call"][0] - rec[K]["put"][0]))
        F = ks + math.exp(r * T) * (rec[ks]["call"][0] - rec[ks]["put"][0])
        below = [K for K in sorted(rec) if K <= F]
        if not below:
            return None
        K0 = below[-1]
        sel = {}
        zeros = 0
        for K in sorted((K for K in rec if K < K0), reverse=True):
            p = rec[K].get("put")
            if p is None or p[1] <= 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            sel[K] = p[0]
        zeros = 0
        for K in sorted(K for K in rec if K > K0):
            cl = rec[K].get("call")
            if cl is None or cl[1] <= 0:
                zeros += 1
                if zeros >= 2:
                    break
                continue
            zeros = 0
            sel[K] = cl[0]
        mids = [x[0] for x in (rec[K0].get("put"), rec[K0].get("call")) if x is not None]
        if not mids:
            return None
        sel[K0] = float(np.mean(mids))
        ks_sorted = sorted(sel)
        tot = 0.0
        for i, K in enumerate(ks_sorted):
            if len(ks_sorted) == 1:
                dk = 1.0
            elif i == 0:
                dk = ks_sorted[1] - K
            elif i == len(ks_sorted) - 1:
                dk = K - ks_sorted[i - 1]
            else:
                dk = (ks_sorted[i + 1] - ks_sorted[i - 1]) / 2.0
            tot += dk / K ** 2 * math.exp(r * T) * sel[K]
        return {"var": 2.0 / T * tot - (F / K0 - 1.0) ** 2 / T, "T": T, "forward": F, "n_strikes": len(sel), "expiry": e}

    a, b = one(near[-1][1], near[-1][0]), one(nxt[0][1], nxt[0][0])
    if a is None or b is None:
        return None
    n1, n2, n30 = near[-1][0], nxt[0][0], target_days
    w = (n2 - n30) / (n2 - n1)
    var30 = (a["T"] * a["var"] * w + b["T"] * b["var"] * (1 - w)) * 365.0 / n30
    return {"var30": var30, "vol30": math.sqrt(max(var30, 0.0)) * 100, "near": a, "next": b}


# =================================================================================================== harnesses ==

def _measured_scale(smile: Optional[Smile]) -> tuple:
    if smile is None or not smile.curves:
        return None, ""
    s = float(smile.ratio(1.0, 30))
    return s, f"; measured ATM IV / VIX = {s:.3f} at 30 DTE (mean of {smile.n_days} captured SPY smile quote days)"


def b6_var_short_straddle_tercile(archive):
    """T-101: tercile-conditioned short straddle (top minus bottom of VIX - RV21), walk-forward out of sample."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    fr = _spy_frame(archive)
    pre, note = None, " from SPY cycles only (no ^GSPC history archived)"
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        vix = _index(archive, VIX_B)
        first = fr["days"][0] if fr["days"] else "9999"
        sel = [i for i, d in enumerate(gd) if d < first and d in vix]
        if len(sel) > 2 * HOLD:
            d2 = [gd[i] for i in sel]
            c2 = gc[sel]
            st = np.arange(HOLD, len(d2), HOLD)
            pre = np.array([vix[d2[a]] for a in st]) - 100.0 * trailing_rv_vol(_logret_end(c2), st)
            note = (f"; the first training window is the {st.size} pre-SPY cycles {d2[st[0]]}..{d2[st[-1]]} with RV21 from ^GSPC "
                    f"price returns (SPY starts {first}); every SPY cycle is out of sample")
    rep = straddle_tercile(fr, pre_signal=pre, pre_note=note)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_gamma_scalp_long_straddle(archive):
    """T-123: delta-hedged long straddle at 0.90 x VIX; mean P&L / vega, upper CI < 0."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    rep = gamma_scalp(_spy_frame(archive))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_theta_harvest_45dte(archive):
    """T-156: 45-DTE 0.16-delta strangle, 21-DTE exit vs hold, P&L per day."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    rep = theta_harvest(_spy_frame(archive), smile=_smile(archive))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_theta_ladder(archive):
    """T-157: 4-rung weekly quarter-size put ladder vs monthly full-size entry, drawdown ratio."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    rep = theta_ladder(_spy_frame(archive))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_vrp_short_straddle_hedged(archive):
    """T-233: daily delta-hedged short straddle at 0.81 x VIX (and the measured ATM/VIX scale), after 0.5 vol pt."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    s, note = _measured_scale(_smile(archive))
    rep = vrp_hedged_short(_spy_frame(archive), s, note)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def _truncation_checks(archive, vix_full: dict, dtb3: dict) -> list:
    out = []
    tdays = sorted(vix_full)
    for nm in _names(archive, SPX_CHAIN_P):
        rows = list(archive.load(nm))
        if not rows:
            continue
        qd = _quote_day(rows[0].get("available_at") or "", tdays)
        if qd is None or qd not in vix_full:
            continue
        r = float(bill_rates([qd], dtb3)[0])
        sv = strip_variance([x["value"] for x in rows], qd, r)
        if sv is None:
            out.append({"bundle": nm, "quote_day": qd, "error": None})
            continue
        vx2 = (vix_full[qd] / 100.0) ** 2
        out.append({"bundle": nm, "quote_day": qd, "vix": vix_full[qd], "strip_vol30": sv["vol30"], "error": sv["var30"] / vx2 - 1.0,
                    "near": {k: sv["near"][k] for k in ("expiry", "n_strikes", "forward")},
                    "next": {k: sv["next"][k] for k in ("expiry", "n_strikes", "forward")}})
    return out


def b6_var_variance_strip_win_rate(archive):
    """T-234: VIX^2 > next 21-day ^GSPC realised variance in > 75% of non-overlapping months since 1990."""
    miss = _missing(archive, [GSPC_B, VIX_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    vix = _index(archive, VIX_B)
    days = [d for d in gd if d in vix and d >= "1990-01-01"]
    pos = {d: i for i, d in enumerate(gd)}
    close = np.array([gc[pos[d]] for d in days])
    checks = {}
    if _has(archive, SPY_B):
        sd, _, sa = _daily(archive, SPY_B)
        sp = dict(zip(sd, sa))
        checks["dividend-adjusted SPY"] = np.array([sp.get(d, np.nan) for d in days])
    trunc = None
    if _names(archive, SPX_CHAIN_P):
        vix_full = _index(archive, VIX_B, filtered=False)
        trunc = _truncation_checks(archive, vix_full, _series(archive, DTB3_B) if _has(archive, DTB3_B) else {})
    rep = vix2_win_rate(days, close, [vix[d] for d in days], checks=checks, truncation=trunc)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_iv_rv_spread_scaled(archive):
    """T-235: short variance scaled by max(z, 0) of VIX minus a walk-forward HAR forecast vs constant notional."""
    miss = _missing(archive, [GSPC_B, VIX_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    rep = scaled_short_variance(gd, gc, _index(archive, VIX_B))
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_variance_swap_units(archive):
    """T-540: short variance struck at VIX^2 settled on next-21-day SPY RV, %^2 per month."""
    miss = _missing(archive, [SPY_B, VIX_B])
    if miss:
        return miss
    spy_rows = _rows(archive, SPY_B)
    vix_rows = _rows(archive, VIX_B)
    sd, sc, sa = _daily_from_rows(spy_rows)
    vix = index_closes(vix_rows)
    keep = [i for i, d in enumerate(sd) if d in vix]
    days = [sd[i] for i in keep]
    checks = {"dividend-adjusted SPY": sa[keep]}
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        gp = dict(zip(gd, gc))
        checks["^GSPC (SPX vs SPY)"] = np.array([gp.get(d, np.nan) for d in days])
    rep = short_variance_units(days, sc[keep], [vix[d] for d in days], checks=checks)
    if "stat" in rep:
        ov = variance_risk_premium(vix_rows, spy_rows, window=HOLD, symbol="SPY")
        rep["stat"]["overlapping_vol_units_T48"] = {k: ov.get(k) for k in ("n", "vrp_vol_points", "vrp_variance_points", "p_value",
                                                                          "share_positive", "halves")}
        rep["reason"] = rep["reason"].replace(" — ", f"; overlapping daily windows (T-48 vol units) VRP {ov.get('vrp_vol_points', float('nan')) * 100:+.2f} vol pts, "
                                                     f"p {ov.get('p_value', float('nan')):.4f} (reported) — ", 1)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


def b6_var_vix1d_premium(archive):
    """T-529: (VIX1D/100)^2/365 exceeds the next day's squared ^GSPC log return on average."""
    miss = _missing(archive, [VIX1D_B, GSPC_B])
    if miss:
        return miss
    gd, gc, _ = _daily(archive, GSPC_B)
    vix = _index(archive, VIX_B) if _has(archive, VIX_B) else None
    events = {}
    for lab, nm in EVENT_B.items():
        if _has(archive, nm):
            ds = set()
            for r in _rows(archive, nm):
                v = r["value"]
                d = v.get("decision_day") or v.get("day")
                if d and not v.get("future"):
                    ds.add(d)
            events[lab] = ds
    rep = vix1d_premium(gd, gc, _index(archive, VIX1D_B), vix=vix, events=events or None)
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep["n"], rep["verdict"], rep["reason"])


HARNESSES = {
    "b6_var_short_straddle_tercile": b6_var_short_straddle_tercile,
    "b6_var_gamma_scalp_long_straddle": b6_var_gamma_scalp_long_straddle,
    "b6_var_theta_harvest_45dte": b6_var_theta_harvest_45dte,
    "b6_var_theta_ladder": b6_var_theta_ladder,
    "b6_var_vrp_short_straddle_hedged": b6_var_vrp_short_straddle_hedged,
    "b6_var_variance_strip_win_rate": b6_var_variance_strip_win_rate,
    "b6_var_iv_rv_spread_scaled": b6_var_iv_rv_spread_scaled,
    "b6_var_variance_swap_units": b6_var_variance_swap_units,
    "b6_var_vix1d_premium": b6_var_vix1d_premium,
}

THEORY_MAP = {
    "T-101": "b6_var_short_straddle_tercile",
    "T-123": "b6_var_gamma_scalp_long_straddle",
    "T-156": "b6_var_theta_harvest_45dte",
    "T-157": "b6_var_theta_ladder",
    "T-233": "b6_var_vrp_short_straddle_hedged",
    "T-234": "b6_var_variance_strip_win_rate",
    "T-235": "b6_var_iv_rv_spread_scaled",
    "T-540": "b6_var_variance_swap_units",
    "T-529": "b6_var_vix1d_premium",
}
