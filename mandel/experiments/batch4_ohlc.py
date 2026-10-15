"""
Batch 4, daily OHLC claims (group ``ohlc``)
==========================================

Seven library claims tested on archived Yahoo daily bars (open, high, low, close, adjclose): T-216 (opex pin, a
MODEL-PRICED 1-day SPY straddle), T-304 (55-day Donchian breakout with a 10-ATR trailing stop vs matched random
entries), T-324 (SPY/IVV twin z-score), T-332 (IBS < 0.2 next-day reversal), T-333 (overnight gap fade),
T-348 (overnight vs intraday) and T-421 (Corwin-Schultz spread shocks). Each claim is tested as worded: its window,
its pass rule and the costs it names.

Data conventions
----------------
* Bars come from ``daily-history-<SYM>``; a bar is used only if its ``available_at`` is not after the bundle's
  capture time (the same rule as ``underlying2.load_series``). The trading day is the UTC date of the bar time.
* ``close`` is split-adjusted only (the traded price for SPY, which never split); ``adjclose`` is also
  dividend-adjusted. Yahoo multiplies every close before an ex-date by (1 - D/C_{t-1}), so the cash dividend is
  recovered exactly as D_t = C_{t-1} (1 - f_{t-1}/f_t) with f = adjclose/close. Ratio moves under 1e-4 are float32
  rounding (about 1e-6) and are ignored. On SPY this finds 4 ex-dates a year, on quarterly third Fridays.
* Where a claim works on dividend-adjusted OHLC (T-304), open/high/low are multiplied by f of the same day.
* Overnight gaps (T-333, T-348) add the ex-date dividend back, (open_t + D_t)/close_{t-1} - 1, so the cash
  dividend that lands overnight is not read as a gap down.

Statistics
----------
* "95% CI" and "95% lower bound" are the ends of a two-sided 95% bootstrap interval (2.5% / 97.5% quantiles), the
  conservative reading of a one-sided bound. Circular block bootstrap unless the trial names another scheme
  (T-332: stationary bootstrap with mean block 20; T-304: cluster bootstrap by asset x entry year; T-324: cluster
  bootstrap by entry month).
* p-values test the null the trial states, except T-348: its claim is a gap of "at least 3 bps per trading day"
  and its pass is "Gap > 3 bps/day with p < 0.05", so the p criterion is against H0: gap <= 3 bps (the equal-means
  p is reported). For T-421 ("at least 1 point") the point estimate must clear the magnitude, the p criterion is
  against 0 and the p against the magnitude is reported. Bootstrap p-values are studentized
  (``block_bootstrap_pvalue``) for means and centred percentile for regression coefficients and clustered means.
* min_n is counted in the unit of the statistic: trades for per-trade statistics (T-304, T-324, T-333).
* DSR is ``deflated_sharpe_ratio`` with the trial count the claim states; the variance of trial Sharpes is that of
  the variants the archive supports (when there are at least two), floored at the zero-skill variance 1/(T-1).
* Annualisation: 252 trading days for US-listed instruments, 365 for crypto.
* ``_verdict`` from underlying2 decides: an implemented criterion that fails -> not_supported; a criterion that
  cannot be implemented (None) -> at best inconclusive.
* Below the trial's min_n (in the claim's own units) house rule 5 applies (``_rule5``): the statistics are still
  computed, the verdict is never supported, and a failing criterion still counts only when it fails decisively, its
  95% interval lying wholly on the wrong side of the claimed bound (the bootstrap CI of the mean, difference or
  coefficient at or below the bound; the halves' own CIs on opposite sides of 0, or a half's at or below 0 where both
  must be positive; for a DSR, the Sharpe's one-sided 95% upper bound at or below 0, since the deflation benchmark is
  never below 0; for T-304's trial correction, both of its routes). An interval decides only on >= 8 observations in
  >= 4 resampling units (blocks or clusters). Any other failure there is undecided (None), so the verdict is
  inconclusive; with too little data for the statistics at all the verdict is inconclusive. The criteria judged and
  the decisive failures are reported under ``rule5``.

Model pricing (T-216) is Black-Scholes with sigma = VIX/100, T = 1/252, r = 0 and labelled MODEL-PRICED: a flat
30-day index cannot see any expiry-specific premium that traded weekly options carry. The straddle settles on the
raw closes, |SPY_Fri - SPY_Thu|, as the procedure states; on an ex-dividend Friday the known cash dividend (declared
before the ex-date) is priced into the forward, S_thu - D. The r = q = 0 price without the dividend is reported as
the as-worded sensitivity. Its "exclude opex days with FOMC/CPI" control reads CPI release days from
``macro-release-cpi`` (ALFRED vintage dates of CPIAUCSL, 08:30 ET, revision-only vintages dropped by
``batch5_macro.release_days_from_rows``); the bundle is loaded only for that control, and without it the CPI part is
listed under ``not_run``.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple, Optional, Sequence

import numpy as np

from mandel.experiments.batch5_macro import release_days_from_rows, to_sessions
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _mean_ci, _sharpe_diff_lower, _sr, _verdict
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio, skewness, walk_forward_splits

EQ_PPY = 252
CRYPTO_PPY = 365
DSR_PASS = 0.95
DIV_TOL = 1e-4


# ================================================================================================ data access ==

class Bars(NamedTuple):
    days: list
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    adj: np.ndarray


def bars_from_rows(rows, captured_at: Optional[str] = None) -> Bars:
    """Daily bars from ``daily-history-*`` rows (or bare value dicts), one per UTC day, dropping rows that were not
    yet available at ``captured_at`` and bars with a missing or non-positive price. ``adj`` falls back to close."""
    by = {}
    for r in rows:
        if captured_at and r.get("available_at") and r["available_at"] > captured_at:
            continue
        v = r.get("value", r)
        px = [v.get(k) for k in ("open", "high", "low", "close")]
        if any(x is None for x in px):
            continue
        o, h, l, c = (float(x) for x in px)
        if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
            continue
        a = v.get("adjclose")
        a = float(a) if a is not None and math.isfinite(float(a)) and float(a) > 0 else c
        by[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = (o, h, l, c, a)
    days = sorted(by)
    arr = np.array([by[d] for d in days], dtype=float).reshape(-1, 5)
    return Bars(days, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4])


def ex_dividends(close: np.ndarray, adj: np.ndarray, tol: float = DIV_TOL) -> np.ndarray:
    """Cash dividend per share on each ex-date (0 elsewhere), inferred from the adjclose/close factor."""
    c = np.asarray(close, dtype=float); f = np.asarray(adj, dtype=float) / c
    out = np.zeros(len(c))
    if len(c) > 1:
        jump = 1.0 - f[:-1] / f[1:]
        out[1:] = np.where(jump > tol, c[:-1] * jump, 0.0)
    return out


def adjusted_ohlc(b: Bars) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Dividend-adjusted (open, high, low, close): each price times that day's adjclose/close."""
    f = b.adj / b.close
    return b.open * f, b.high * f, b.low * f, b.adj.copy()


_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        archive.get(name)
        return True
    except KeyError:
        return False


def _bundle(symbol: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)


def _bars(archive, symbol: str) -> Bars:
    name = _bundle(symbol)
    return _cached(archive, ("bars", symbol), lambda: bars_from_rows(archive.load(name), archive.get(name).created_at))


def _index(archive, name: str) -> dict:
    def load():
        cap = archive.get(name).created_at
        return index_closes(r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))
    return _cached(archive, ("index", name), load)


def _fomc_days(archive) -> set:
    def load():
        return {r["value"]["decision_day"] for r in archive.load("fomc-meetings") if r["value"].get("scheduled")}
    return _cached(archive, ("fomc",), load)


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


CPI_BUNDLE = "macro-release-cpi"


def _cpi_days(archive) -> Optional[list]:
    """CPI release days (08:30 ET) from ``macro-release-cpi``, rows available at the bundle's capture only, revision-only
    vintages dropped (``batch5_macro.release_days_from_rows``). None when the bundle is not archived."""
    if _missing(archive, [CPI_BUNDLE]):
        return None

    def load():
        cap = archive.get(CPI_BUNDLE).created_at
        return release_days_from_rows([r for r in archive.load(CPI_BUNDLE) if not (cap and r.get("available_at") and r["available_at"] > cap)], "cpi")[0]
    return _cached(archive, ("cpi",), load)


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


# ============================================================================================ statistics core ==

def _range_mask(ds: np.ndarray, start: Optional[str], end: Optional[str]) -> np.ndarray:
    m = np.ones(len(ds), dtype=bool)
    if start:
        m &= ds >= start
    if end:
        m &= ds <= end
    return m


def _circ_idx(n: int, block: int, rng) -> np.ndarray:
    nb = math.ceil(n / block)
    return ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n


def stationary_idx(n: int, mean_block: float, rng) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices: blocks of geometric length with mean ``mean_block``, wrapping."""
    new = rng.random(n) < 1.0 / mean_block
    new[0] = True
    last = np.maximum.accumulate(np.where(new, np.arange(n), 0))
    starts = rng.integers(0, n, n)
    return (starts[last] + np.arange(n) - last) % n


def _p_boot(boot: np.ndarray, obs: float, null: float = 0.0) -> float:
    """One-sided centred-bootstrap p for H0: theta <= null (share of resamples with theta* - obs >= obs - null)."""
    b = np.asarray(boot, dtype=float); b = b[np.isfinite(b)]
    if b.size == 0 or not math.isfinite(obs):
        return float("nan")
    return float((np.sum(b - obs >= obs - null) + 1) / (b.size + 1))


def _dsr(r: np.ndarray, n_trials: int, trial_sharpes: Optional[Sequence[float]] = None) -> float:
    """Deflated Sharpe of ``r`` against the best of ``n_trials``. The variance of trial Sharpes is the variance of the
    supplied variants' per-period Sharpes (>= 2 of them) floored at the zero-skill variance 1/(T-1); without
    variants it is that floor."""
    r = np.asarray(r, dtype=float)
    floor = 1.0 / max(1, r.size - 1)
    ts = [float(s) for s in (trial_sharpes or []) if s is not None and math.isfinite(float(s))]
    var = max(float(np.var(ts, ddof=1)), floor) if len(ts) >= 2 else floor
    return float(deflated_sharpe_ratio(r, n_trials=n_trials, var_trials_sr=var))


def flag_diff_series(x: np.ndarray, flag: np.ndarray) -> np.ndarray:
    """Series whose mean is mean(x[flag]) - mean(x[~flag]) and whose block-resampled mean has the within-group
    sampling spread of that difference: d_t = diff + w_t (x_t - m_g(t)), w = 1/p on flagged, -1/(1-p) elsewhere."""
    x = np.asarray(x, dtype=float); f = np.asarray(flag, dtype=bool)
    p = f.mean(); me, mo = x[f].mean(), x[~f].mean()
    w = np.where(f, 1.0 / p, -1.0 / (1.0 - p))
    return (me - mo) + w * (x - np.where(f, me, mo))


def group_diff(x: np.ndarray, flag: np.ndarray, block: int, n_boot: int = 4000, seed: int = 0) -> dict:
    """Flagged-minus-other difference in means: two-sided 95% circular-block CI and studentized one-sided p
    (H0: diff <= 0)."""
    x = np.asarray(x, dtype=float); f = np.asarray(flag, dtype=bool)
    ne, no = int(f.sum()), int((~f).sum())
    out = {"n_flag": ne, "n_other": no, "mean_flag": float(x[f].mean()) if ne else None, "mean_other": float(x[~f].mean()) if no else None,
           "diff": None, "ci": [None, None], "p": None}
    if ne < 2 or no < 2 or len(x) < 8:
        return out
    d = flag_diff_series(x, f)
    lo, hi = _mean_ci(d, block, n_boot, seed)
    out.update(diff=float(d.mean()), ci=[lo, hi], p=float(block_bootstrap_pvalue(d, np.zeros_like(d), n_boot=n_boot, block_len=block, seed=seed)))
    return out


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple[str, str]:
    if n < min_n:
        return "inconclusive", f"data cannot support the claim: {n} {unit}, below the trial's min_n {min_n}"
    return _verdict([(f">= {min_n} {unit}", True)] + crit)


# ================================================================================================ house rule 5 ==

MIN_DECISIVE_OBS = 8        # a 95% interval decides a failure below min_n only when it rests on >= 8 observations ...
MIN_DECISIVE_UNITS = 4      # ... spread over >= 4 resampling units (blocks or clusters): a one-block resample is a rotation


def _too_few(n: int, min_n: int, unit: str, what: str) -> tuple[str, str]:
    """Below min_n with too little data to compute the statistics at all: inconclusive (nothing can fail decisively)."""
    return "inconclusive", (f"data cannot support the claim: {n} {unit}, below the trial's min_n {min_n}, and too few for {what}, "
                            f"so no criterion can fail decisively (house rule 5)")


def _resolvable(n_obs: int, n_units: float) -> bool:
    return n_obs >= MIN_DECISIVE_OBS and n_units >= MIN_DECISIVE_UNITS


def _upper_dec(hi, bound: float, fmt, n_obs: int, n_units: float, strict: bool = False, what: str = "95% interval") -> tuple[bool, str]:
    """Decisive failure of a 'statistic > bound' (or >= bound with ``strict``) criterion: the upper end ``hi`` of its
    ``what`` lies at or below ``bound`` (below it with ``strict``), on an interval that can decide (_resolvable)."""
    if not _resolvable(n_obs, n_units):
        return False, f"{what} on {n_obs} observations in {n_units:.0f} resampling units, too few to decide"
    if hi is None or not math.isfinite(hi):
        return False, f"no {what}"
    dec = bool(hi < bound) if strict else bool(hi <= bound)
    rel = ("<" if strict else "<=") if dec else (">=" if strict else ">")
    return dec, f"upper end of the {what} {fmt(hi)} {rel} {fmt(bound)}"


def _dsr_dec(x, n_obs: int) -> tuple[bool, str]:
    """Decisive failure of 'DSR > 0.95': the Sharpe's one-sided 95% upper bound lies at or below 0 (the PSR test against a
    zero Sharpe is <= 0.05). The deflation benchmark, the expected best of the trial count's zero-skill Sharpes, is never
    below 0 (at min_n or any other sample size), so the DSR is then <= 0.05 against every benchmark the trial can face.
    ``n_obs`` counts the claim's independent units behind the series (trades, signals, events)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if n_obs < MIN_DECISIVE_OBS or x.size < MIN_DECISIVE_OBS:
        return False, f"{n_obs} observations, too few to bound the Sharpe"
    psr = float(deflated_sharpe_ratio(x, n_trials=1))
    dec = psr <= 1.0 - DSR_PASS
    return dec, f"PSR against a zero Sharpe {psr:.3f} {'<=' if dec else '>'} {1.0 - DSR_PASS:.2f}"


def _halves_dec(cis, n_obs, n_units, fmt, opposite: bool = False) -> tuple[bool, str]:
    """``cis``: [(label, lo, hi)] of the two halves. 'Positive in both halves' fails decisively when a half's resolvable 95%
    interval lies wholly at or below 0; 'same sign in both halves' (``opposite``) when the two halves' resolvable intervals lie
    strictly on opposite sides of 0."""
    ok = [_resolvable(o, u) and lo is not None and hi is not None and math.isfinite(lo) and math.isfinite(hi)
          for (_, lo, hi), o, u in zip(cis, n_obs, n_units)]
    txt = "; ".join(f"{lab} 95% interval {fmt(lo)}..{fmt(hi)}" if k else f"{lab} {o} observations, too few to decide"
                    for (lab, lo, hi), k, o in zip(cis, ok, n_obs))
    if opposite:
        if not all(ok):
            return False, txt
        (_, l0, h0), (_, l1, h1) = cis
        dec = bool((l0 > 0 and h1 < 0) or (h0 < 0 and l1 > 0))
        return dec, txt + ("; the halves lie on opposite sides of 0" if dec else "; not significantly of opposite sign")
    dec = any(k and hi <= 0 for (_, _, hi), k in zip(cis, ok))
    return dec, txt + ("; a half lies wholly at or below 0" if dec else "; no half lies wholly at or below 0")


def _rule5(rows, n: int, min_n: int, unit: str) -> tuple[str, str, list]:
    """House rule 5 below the trial's min_n (``n`` in the claim's own units). ``rows``: [(name, ok, decisive, note)] with ok
    True / False / None (not implemented) and decisive True when the failure stands below min_n (its 95% interval lies
    wholly on the wrong side of the claimed bound). A passing or decisively failing criterion keeps its bool, any other
    failure becomes None (undecided), and the unmet 'n >= trial min_n' criterion (None) keeps the verdict from
    'supported'. Returns (verdict, explanation, criteria judged)."""
    crit = []
    for name, ok, dec, note in rows:
        nt = f": {note}" if note else ""
        if ok is None:
            crit.append((name, None))
        elif ok:
            crit.append((name, True))
        elif dec:
            crit.append((f"{name} (fails decisively below min_n{nt})", False))
        else:
            crit.append((f"{name} (fails, not decisively, below min_n{nt}; undecided)", None))
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", None))
    v, why = _verdict(crit)
    v0, why0 = _verdict([(name, None if ok is None else bool(ok)) for name, ok, _, _ in rows])
    return v, (f"house rule 5: only {n} {unit}, below the trial's min_n {min_n}, so the verdict cannot be supported and a failing "
               f"criterion counts only when it fails decisively, its 95% interval wholly on the wrong side of the claimed bound: "
               f"{v}, {why} [criteria at face value: {v0}, {why0}]"), crit


def _apply_rule5(rep: dict, rows, n: int, min_n: int, unit: str) -> tuple[str, str]:
    """_rule5, recording the criteria judged and the decisive failures under ``rep['rule5']``."""
    v, why, crit = _rule5(rows, n, min_n, unit)
    rep["rule5"] = {"n": n, "min_n": min_n, "unit": unit, "criteria": [[c, ok] for c, ok in crit],
                    "decisive_failures": [name for name, ok, dec, _ in rows if ok is not None and not ok and dec]}
    return v, why


def _trailing_z(x: np.ndarray, window: int, include_current: bool = False) -> np.ndarray:
    """z_t = (x_t - mean)/sd (ddof=1) over the ``window`` values ending at t-1 (or at t when include_current)."""
    x = np.asarray(x, dtype=float); n = len(x); z = np.full(n, np.nan)
    if n <= window:
        return z
    W = np.lib.stride_tricks.sliding_window_view(x, window)          # row j covers x[j .. j+window-1]
    mu, sd = W.mean(axis=1), W.std(axis=1, ddof=1)
    if include_current:
        t = np.arange(window - 1, n); row = t - window + 1
    else:
        t = np.arange(window, n); row = t - window
    with np.errstate(invalid="ignore", divide="ignore"):
        z[t] = np.where(sd[row] > 0, (x[t] - mu[row]) / sd[row], np.nan)
    return z


def _rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=float); out = np.full(len(x), np.nan)
    if len(x) >= window:
        out[window - 1:] = np.lib.stride_tricks.sliding_window_view(x, window).mean(axis=1)
    return out


def _rolling_sd(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=float); out = np.full(len(x), np.nan)
    if len(x) >= window:
        out[window - 1:] = np.lib.stride_tricks.sliding_window_view(x, window).std(axis=1, ddof=1)
    return out


# =================================================================== T-348 overnight vs intraday (night effect) ==

def overnight_intraday(days: Sequence[str], opens, closes, divs=None, adj=None, start: Optional[str] = None, end: Optional[str] = None,
                       split: str = "2010-01-01", min_gap: float = 0.0003, block: int = 10, n_boot: int = 2000, min_n: int = 3000,
                       cost_rt: float = 0.0001, seed: int = 0) -> dict:
    """T-348: r_night = open_t/close_{t-1} - 1 + D_t/close_{t-1}; r_day = close_t/open_t - 1. Pass: mean(r_night -
    r_day) > 3 bps/day, studentized block-10 bootstrap p < 0.05 against the magnitude the claim names (H0: gap <= 3
    bps, since the claim is 'at least 3 bps per trading day'), gap positive in both halves. The p against the trial's
    equal-means null and the one-sided 95% lower bound of the gap are reported. Secondary (not in the pass): Sharpe of
    the overnight series net of a 1 bp round trip (2 bp sensitivity) vs buy-and-hold."""
    O = np.asarray(opens, dtype=float); C = np.asarray(closes, dtype=float)
    D = np.zeros(len(C)) if divs is None else np.asarray(divs, dtype=float)
    ds = np.array(days[1:])
    night = O[1:] / C[:-1] - 1 + D[1:] / C[:-1]
    dayr = C[1:] / O[1:] - 1
    bh = (np.asarray(adj, dtype=float)[1:] / np.asarray(adj, dtype=float)[:-1] - 1) if adj is not None else (C[1:] + D[1:]) / C[:-1] - 1
    m = _range_mask(ds, start, end)
    ds, night, dayr, bh = ds[m], night[m], dayr[m], bh[m]
    flat_open = float(np.mean(O[1:][m] == C[1:][m])) if m.any() else None
    n = len(ds)
    rep = {"n": n, "first": ds[0] if n else None, "last": ds[-1] if n else None, "n_ex_dividend_days": int(np.sum(D[1:][m] > 0)),
           "open_equals_close_share": flat_open}
    if n < min_n and n < MIN_DECISIVE_OBS:
        v, why = _too_few(n, min_n, "trading days", "a block-bootstrap interval")
        rep.update(verdict=v, reason=f"SPY overnight vs intraday: {n} days — {why}")
        return rep
    d = night - dayr
    gap = float(d.mean())
    lo, hi = _mean_ci(d, block, n_boot, seed)
    p_eq = float(block_bootstrap_pvalue(d, np.zeros(n), n_boot=n_boot, block_len=block, seed=seed))
    p_thr = float(block_bootstrap_pvalue(d, np.full(n, min_gap), n_boot=n_boot, block_len=block, seed=seed))
    rng = np.random.default_rng(seed)
    lo1 = float(np.quantile([d[_circ_idx(n, block, rng)].mean() for _ in range(n_boot)], 0.05))
    early = ds < split
    halves = [float(d[early].mean()) if early.any() else float("nan"), float(d[~early].mean()) if (~early).any() else float("nan")]
    halves_n = [int(early.sum()), int((~early).sum())]
    sr_night1, sr_night2 = _sr(night - cost_rt, EQ_PPY), _sr(night - 2 * cost_rt, EQ_PPY)
    sr_day, sr_bh = _sr(dayr, EQ_PPY), _sr(bh, EQ_PPY)
    crit = [(f"gap > {min_gap * 1e4:.0f} bps/day", gap > min_gap),
            (f"p < 0.05 vs gap <= {min_gap * 1e4:.0f} bps (studentized block-{block} bootstrap)", p_thr < 0.05),
            ("gap positive in both halves", all(math.isfinite(h) and h > 0 for h in halves))]
    if n < min_n:
        # rule 5: the gap and its p fail decisively when the gap's 95% CI lies wholly at or below 3 bps; the halves when a
        # half's own block-bootstrap 95% CI lies wholly at or below 0
        bps = lambda v_: f"{v_ * 1e4:+.2f} bps"
        gdec = _upper_dec(hi, min_gap, bps, n, math.ceil(n / block), what="gap's 95% CI")
        hcis = [(lab, *(_mean_ci(d[g_], block, n_boot, seed) if g_.sum() >= MIN_DECISIVE_OBS else (None, None)))
                for lab, g_ in ((f"<{split}", early), (f">={split}", ~early))]
        hdec = _halves_dec(hcis, halves_n, [math.ceil(k / block) for k in halves_n], bps)
        v, why = _apply_rule5(rep, [(*crit[0], *gdec), (*crit[1], *gdec), (*crit[2], *hdec)], n, min_n, "trading days")
    else:
        v, why = _decide(crit, n, min_n, "trading days")
    rep.update(mean_night_bps=float(night.mean() * 1e4), mean_day_bps=float(dayr.mean() * 1e4), gap_bps=gap * 1e4,
               gap_ci_bps=[lo * 1e4, hi * 1e4], gap_lower95_one_sided_bps=lo1 * 1e4, p_criterion="H0: gap <= threshold",
               p_equal_means=p_eq, p_gap_le_threshold=p_thr, halves_gap_bps=[h * 1e4 for h in halves],
               halves_n=halves_n, split=split, sharpe_overnight_net_1bp=sr_night1, sharpe_overnight_net_2bp=sr_night2,
               sharpe_intraday=sr_day, sharpe_buy_hold=sr_bh, verdict=v,
               reason=(f"SPY {rep['first']}..{rep['last']} ({n} days, {rep['n_ex_dividend_days']} ex-dividend nights with D/C added back): "
                       f"overnight {night.mean() * 1e4:+.2f} vs intraday {dayr.mean() * 1e4:+.2f} bps/day, gap {gap * 1e4:+.2f} bps "
                       f"(95% CI {lo * 1e4:+.2f}..{hi * 1e4:+.2f}; one-sided 95% lower bound {lo1 * 1e4:+.2f}; claim: at least "
                       f"{min_gap * 1e4:.0f} bps), p={p_thr:.3f} vs gap <= {min_gap * 1e4:.0f} bps (the pass criterion; p={p_eq:.4f} vs equal "
                       f"means, the trial's stated null, shows only that the gap is positive); halves <{split} {halves[0] * 1e4:+.2f} / >={split} {halves[1] * 1e4:+.2f} bps; "
                       f"secondary Sharpe overnight net 1 bp {sr_night1:.2f} (2 bp {sr_night2:.2f}) vs buy-hold {sr_bh:.2f}; "
                       f"open==close on {flat_open * 100:.1f}% of days (flagged) — {why}"))
    return rep


# ============================================================================== T-333 overnight gap fade ==

def gap_fade_series(opens, closes, thr: float = 0.005, cost_rt: float = 0.0002, divs=None):
    """(o, i, side, daily net) aligned to days[1:]: o = gap (open_t + D_t)/close_{t-1} - 1 with the ex-date cash
    dividend D added back (raw gap without ``divs``), i = open-to-close, side = +1 after o < -thr (buy the open),
    -1 after o > +thr (short the open), daily net = side*i - cost on trade days and 0 otherwise."""
    O = np.asarray(opens, dtype=float); C = np.asarray(closes, dtype=float)
    D = np.zeros(len(C)) if divs is None else np.asarray(divs, dtype=float)
    o = (O[1:] + D[1:]) / C[:-1] - 1; i = C[1:] / O[1:] - 1
    side = np.where(o < -thr, 1.0, np.where(o > thr, -1.0, 0.0))
    daily = np.where(side != 0, side * i - cost_rt, 0.0)
    return o, i, side, daily


def gap_fade(days: Sequence[str], opens, closes, start: Optional[str] = "2000-01-01", end: Optional[str] = "2026-09-30", thr: float = 0.005,
             cost_rt: float = 0.0002, split: str = "2013-01-01", block: int = 20, n_boot: int = 2000, seed: int = 0, min_n: int = 500,
             variant_sharpes: Optional[Sequence[float]] = None, n_trials: int = 6, divs=None) -> dict:
    """T-333: fade overnight gaps beyond +-0.5% from the open to the close. Pass: 95% lower bound of the mean net
    return per trade > 0 (block-20 bootstrap over trades in time order, 2,000 resamples) AND the same sign in the two
    halves AND DSR > 0.95 over the ``n_trials`` variants (daily series, zero on non-trade days). The DSR is None
    (not implemented) when no variant Sharpes are supplied. With ``divs`` the gap adds the ex-date dividend back and
    the raw-gap version is reported as a sensitivity."""
    ds = np.array(days[1:])
    o, i, side, daily = gap_fade_series(opens, closes, thr, cost_rt, divs)
    m = _range_mask(ds, start, end)
    raw = None
    if divs is not None:
        _, _, side_r, daily_r = gap_fade_series(opens, closes, thr, cost_rt)
        side_r, daily_r = side_r[m], daily_r[m]
        exd = (np.asarray(divs, dtype=float)[1:] > 0)[m]
        raw = {"n_trades": int(np.sum(side_r != 0)), "n_ex_dividend_days": int(exd.sum()),
               "n_trades_on_ex_dividend_days": int(np.sum((side[m] != 0) & exd)),
               "n_raw_trades_on_ex_dividend_days": int(np.sum((side_r != 0) & exd)),
               "n_side_changed": int(np.sum(side_r != side[m]))}
    ds, o, i, side, daily = ds[m], o[m], i[m], side[m], daily[m]
    tr = side != 0
    net = daily[tr]; tdays = ds[tr]
    n = int(tr.sum())
    rep = {"n": n, "n_days": int(len(ds)), "first": ds[0] if len(ds) else None, "last": ds[-1] if len(ds) else None,
           "n_long": int(np.sum(side > 0)), "n_short": int(np.sum(side < 0))}
    if n < min_n and n < MIN_DECISIVE_OBS:
        v, why = _too_few(n, min_n, "gap trades", "a block-bootstrap interval")
        rep.update(verdict=v, reason=f"gap fade: {n} trades — {why}")
        return rep
    mean = float(net.mean())
    lo, hi = _mean_ci(net, block, n_boot, seed)
    early = tdays < split
    halves = [float(net[early].mean()) if early.any() else float("nan"), float(net[~early].mean()) if (~early).any() else float("nan")]
    same_sign = all(math.isfinite(h) for h in halves) and np.sign(halves[0]) == np.sign(halves[1]) and halves[0] != 0
    dsr = _dsr(daily, n_trials, variant_sharpes) if variant_sharpes is not None else None
    corr = float(np.corrcoef(o, i)[0, 1])
    rng = np.random.default_rng(seed); cb = np.empty(n_boot)
    for k in range(n_boot):
        j = _circ_idx(len(o), block, rng); cb[k] = np.corrcoef(o[j], i[j])[0, 1]
    corr_ci = [float(np.quantile(cb, 0.025)), float(np.quantile(cb, 0.975))]
    dec = {}
    for d0 in sorted({x[:3] for x in tdays}):
        mm = np.array([x[:3] == d0 for x in tdays])
        dec[d0 + "0s"] = {"n": int(mm.sum()), "mean_net_bps": float(net[mm].mean() * 1e4)}
    by_side = {"long_after_gap_down_bps": float(net[side[tr] > 0].mean() * 1e4) if np.any(side[tr] > 0) else None,
               "short_after_gap_up_bps": float(net[side[tr] < 0].mean() * 1e4) if np.any(side[tr] < 0) else None}
    raw_txt = ""
    if raw is not None:
        rnet = daily_r[side_r != 0]
        if rnet.size >= 2:
            rlo, rhi = _mean_ci(rnet, block, n_boot, seed)
            raw.update(mean_net_bps=float(rnet.mean() * 1e4), ci_bps=[rlo * 1e4, rhi * 1e4])
            raw_txt = (f"; gap net of the ex-date dividend ({raw['n_ex_dividend_days']} ex-dividend days, {raw['n_trades_on_ex_dividend_days']} "
                       f"traded; raw-gap sensitivity: {raw['n_trades']} trades, {raw['n_raw_trades_on_ex_dividend_days']} on ex-dividend days, "
                       f"mean {rnet.mean() * 1e4:+.2f} bps, CI {rlo * 1e4:+.2f}..{rhi * 1e4:+.2f}; {raw['n_side_changed']} days change side)")
    crit = [("95% lower bound of mean net per trade > 0", lo > 0), (f"same sign in <{split} and >={split}", bool(same_sign)),
            (f"DSR > 0.95 over {n_trials} variants", None if dsr is None else dsr > DSR_PASS)]
    if n < min_n:
        # rule 5: the lower bound fails decisively when the whole 95% CI lies at or below 0; the halves when their own 95% CIs
        # lie on opposite sides of 0; the DSR when the daily series' Sharpe is significantly at or below 0
        bps = lambda v_: f"{v_ * 1e4:+.2f} bps"
        hn = [int(early.sum()), int((~early).sum())]
        hcis = [(lab, *(_mean_ci(net[g_], block, n_boot, seed) if k >= MIN_DECISIVE_OBS else (None, None)))
                for lab, g_, k in ((f"<{split}", early, hn[0]), (f">={split}", ~early, hn[1]))]
        r5 = [(*crit[0], *_upper_dec(hi, 0.0, bps, n, math.ceil(n / block), what="95% CI")),
                (*crit[1], *_halves_dec(hcis, hn, [math.ceil(k / block) for k in hn], bps, opposite=True)),
                (*crit[2], *((False, "") if dsr is None else _dsr_dec(daily, n)))]
        v, why = _apply_rule5(rep, r5, n, min_n, "gap trades")
    else:
        v, why = _decide(crit, n, min_n, "gap trades")
    rep.update(mean_net_bps=mean * 1e4, ci_bps=[lo * 1e4, hi * 1e4], halves_bps=[h * 1e4 for h in halves], dsr=dsr, n_trials=n_trials,
               corr_o_i=corr, corr_ci=corr_ci, by_decade=dec, by_side=by_side, threshold=thr, cost_rt=cost_rt,
               dividend_neutral_gap=divs is not None, raw_gap_sensitivity=raw, verdict=v,
               reason=(f"{n} gap trades |o|>{thr * 100:.2f}% {rep['first']}..{rep['last']} ({rep['n_long']} long, {rep['n_short']} short): "
                       f"mean net {mean * 1e4:+.2f} bps after {cost_rt * 1e4:.0f} bps RT (95% CI {lo * 1e4:+.2f}..{hi * 1e4:+.2f}){raw_txt}; "
                       f"halves <{split} {halves[0] * 1e4:+.2f} / >={split} {halves[1] * 1e4:+.2f} bps; "
                       f"DSR {'n/a' if dsr is None else f'{dsr:.3f}'} over {n_trials} variants; diagnostic corr(o,i) {corr:+.3f} "
                       f"(95% CI {corr_ci[0]:+.3f}..{corr_ci[1]:+.3f}) — {why}"))
    return rep


# ================================================================================ T-332 IBS daily reversal ==

def ibs(high, low, close) -> np.ndarray:
    """Internal bar strength (close - low)/(high - low); NaN when high == low."""
    H, L, C = (np.asarray(a, dtype=float) for a in (high, low, close))
    rngs = H - L
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(rngs > 0, (C - L) / np.where(rngs > 0, rngs, 1.0), np.nan)


def rsi_wilder(c, n: int = 2) -> np.ndarray:
    c = np.asarray(c, dtype=float); out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    dlt = np.diff(c); g = np.maximum(dlt, 0); l = np.maximum(-dlt, 0)
    ag, al = g[:n].mean(), l[:n].mean()
    for t in range(n, len(c)):
        if t > n:
            ag += (g[t - 1] - ag) / n; al += (l[t - 1] - al) / n
        out[t] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def reversal_rule_positions(high, low, close, adj) -> dict:
    """Positions held from close t to close t+1 for the declared 6-rule grid of the library entry: RSI(2) < 10;
    close below the 20-day 2-sd Bollinger band, held until the close is at or above the 20-day mean; IBS < 0.2;
    IBS long-short (< 0.2 long, > 0.8 short); three down closes, held until the first up close; IBS < 0.2 only when
    the close is above its 200-day mean. Indicators on adjusted closes, IBS on the day's own high/low/close."""
    a = np.asarray(adj, dtype=float); n = len(a)
    x = ibs(high, low, close)
    rsi = rsi_wilder(a, 2)
    ma20, sd20, ma200 = _rolling_mean(a, 20), _rolling_sd(a, 20), _rolling_mean(a, 200)
    boll = np.zeros(n); on = False
    for t in range(n):
        if not on and math.isfinite(ma20[t]) and a[t] < ma20[t] - 2 * sd20[t]:
            on = True
        elif on and a[t] >= ma20[t]:
            on = False
        boll[t] = on
    down3 = np.zeros(n); on = False
    for t in range(3, n):
        if not on and a[t] < a[t - 1] and a[t - 1] < a[t - 2] and a[t - 2] < a[t - 3]:
            on = True
        elif on and a[t] > a[t - 1]:
            on = False
        down3[t] = on
    with np.errstate(invalid="ignore"):
        return {"rsi2_lt10": (rsi < 10).astype(float), "bollinger_lower": boll, "ibs_lt02": (x < 0.2).astype(float),
                "ibs_long_short": np.where(x < 0.2, 1.0, np.where(x > 0.8, -1.0, 0.0)), "down3": down3,
                "ibs_lt02_above_ma200": ((x < 0.2) & (a > ma200)).astype(float)}


def rule_daily_net(pos: np.ndarray, adj, cost_side: float = 0.0001) -> np.ndarray:
    """Net daily return of a position held from close t to close t+1 (aligned to days[:-1]), 1 bp per side on changes."""
    a = np.asarray(adj, dtype=float); p = np.asarray(pos, dtype=float)[:-1]
    r = a[1:] / a[:-1] - 1
    turn = np.abs(np.diff(np.concatenate([[0.0], p])))
    return p * r - cost_side * turn


def _signal_diff_ci(r: np.ndarray, f: np.ndarray, mean_block: int, n_boot: int, rng) -> tuple:
    """Two-sided 95% stationary-bootstrap interval of mean(r[f]) - mean(r), resampling the paired (signal, return)
    series as ibs_reversal does; (None, None) when no resample holds a signal day."""
    n = len(r); bd = np.empty(n_boot)
    for k in range(n_boot):
        j = stationary_idx(n, mean_block, rng); fj = f[j]
        bd[k] = r[j][fj].mean() - r[j].mean() if fj.any() else np.nan
    bd = bd[np.isfinite(bd)]
    return (float(np.quantile(bd, 0.025)), float(np.quantile(bd, 0.975))) if bd.size else (None, None)


def ibs_reversal(days: Sequence[str], highs, lows, closes, adj, opens=None, start: str = "2000-01-01", end: str = "2026-09-30",
                 thr: float = 0.2, split: str = "2013-01-01", min_gap: float = 0.0002, mean_block: int = 20, n_boot: int = 2000,
                 seed: int = 0, min_n: int = 2000, grid_sharpes: Optional[Sequence[float]] = None, n_trials: int = 12,
                 cost_side: float = 0.0001) -> dict:
    """T-332: mean next-day close-to-close return after IBS < 0.2 minus the unconditional mean. Pass: 95% lower bound
    (stationary bootstrap, mean block 20, 2,000 resamples of the paired signal/return series) > 2 bps AND the same sign
    in both halves AND DSR > 0.95 of the IBS rule's net daily series over 12 trials (None without grid Sharpes).
    Diagnostics: block-shifted signal null p, next-open and next-close execution."""
    H, L, C, A = (np.asarray(x, dtype=float) for x in (highs, lows, closes, adj))
    nall = len(A)
    x = ibs(H, L, C)
    sd = np.array(days[:-1]); nd = np.array(days[1:])
    r = A[1:] / A[:-1] - 1
    m = (sd >= start) & (nd <= end) & np.isfinite(x[:-1])
    idx = np.where(m)[0]
    r_w = r[idx]; f = x[idx] < thr; sdays = sd[idx]
    n = len(idx)
    rep = {"n": n, "first": sdays[0] if n else None, "last": sdays[-1] if n else None, "n_signal": int(f.sum())}
    if n < min_n and (f.sum() < 2 or (~f).sum() < 2 or n <= 2 * mean_block):
        v, why = _too_few(n, min_n, "trading days", "the signal comparison and its block-shift null")
        rep.update(verdict=v, reason=f"IBS reversal: {n} days, {int(f.sum())} signals — {why}")
        return rep
    if f.sum() < 2 or (~f).sum() < 2:
        rep.update(verdict="inconclusive", reason=f"IBS reversal: {int(f.sum())} IBS<{thr} days of {n}, too few to compare — data cannot support the claim")
        return rep
    diff = float(r_w[f].mean() - r_w.mean())
    rng = np.random.default_rng(seed); bd = np.empty(n_boot)
    for k in range(n_boot):
        j = stationary_idx(n, mean_block, rng); fj = f[j]
        bd[k] = r_w[j][fj].mean() - r_w[j].mean() if fj.any() else np.nan
    bd = bd[np.isfinite(bd)]
    lo, hi = float(np.quantile(bd, 0.025)), float(np.quantile(bd, 0.975))
    sh = rng.integers(mean_block, n - mean_block, n_boot)
    null = np.array([r_w[np.roll(f, s)].mean() - r_w.mean() for s in sh])
    p_shift = float((np.sum(null >= diff) + 1) / (len(null) + 1))
    early = sdays < split
    halves = []
    for g in (early, ~early):
        halves.append(float(r_w[g & f].mean() - r_w[g].mean()) if (g & f).any() else float("nan"))
    same_sign = all(math.isfinite(h) for h in halves) and np.sign(halves[0]) == np.sign(halves[1]) and halves[0] != 0
    pos = np.zeros(nall); pos[idx] = f
    daily = rule_daily_net(pos, A, cost_side)[idx]
    dsr = _dsr(daily, n_trials, grid_sharpes) if grid_sharpes is not None else None
    diag = {}
    if opens is not None:
        O = np.asarray(opens, dtype=float)
        i_next = C[idx + 1] / O[idx + 1] - 1
        diag["next_open_to_close_diff_bps"] = float((i_next[f].mean() - i_next.mean()) * 1e4)
    ok2 = idx + 2 < nall
    r2 = A[idx[ok2] + 2] / A[idx[ok2] + 1] - 1
    diag["next_close_entry_diff_bps"] = float((r2[f[ok2]].mean() - r2.mean()) * 1e4)
    crit = [(f"95% lower bound of the difference > {min_gap * 1e4:.0f} bps", lo > min_gap),
            (f"same sign in <{split} and >={split}", bool(same_sign)),
            (f"DSR > 0.95 over {n_trials} trials", None if dsr is None else dsr > DSR_PASS)]
    if n < min_n:
        # rule 5: the lower bound fails decisively when the whole stationary-bootstrap 95% CI lies at or below 2 bps; the
        # halves when their own stationary-bootstrap 95% CIs lie on opposite sides of 0; the DSR when the rule's Sharpe is
        # significantly at or below 0. Intervals rest on the signal days, in blocks of mean length mean_block.
        bps = lambda v_: f"{v_ * 1e4:+.2f} bps"
        ns = int(f.sum())
        hrng = np.random.default_rng(seed + 1)
        hcis, hn, hu = [], [], []
        for lab, g_ in ((f"<{split}", early), (f">={split}", ~early)):
            k = int((g_ & f).sum()); hn.append(k); hu.append(g_.sum() / mean_block)
            hcis.append((lab, *(_signal_diff_ci(r_w[g_], f[g_], mean_block, n_boot, hrng)
                                 if k >= MIN_DECISIVE_OBS and (g_ & ~f).sum() >= 2 else (None, None))))
        r5 = [(*crit[0], *_upper_dec(hi, min_gap, bps, ns, n / mean_block, what="stationary-bootstrap 95% CI")),
                (*crit[1], *_halves_dec(hcis, hn, hu, bps, opposite=True)),
                (*crit[2], *((False, "") if dsr is None else _dsr_dec(daily, ns)))]
        v, why = _apply_rule5(rep, r5, n, min_n, "trading days")
    else:
        v, why = _decide(crit, n, min_n, "trading days")  # the statistic compares the signal days with all days, so n counts trading days
    rep.update(mean_after_signal_bps=float(r_w[f].mean() * 1e4), mean_unconditional_bps=float(r_w.mean() * 1e4), diff_bps=diff * 1e4,
               ci_bps=[lo * 1e4, hi * 1e4], p_block_shift=p_shift, halves_bps=[h * 1e4 for h in halves], dsr=dsr, n_trials=n_trials,
               rule_sharpe_net=_sr(daily, EQ_PPY), execution=diag, verdict=v,
               reason=(f"SPY IBS<{thr} on {int(f.sum())} of {n} days {rep['first']}..{rep['last']}: next-day {r_w[f].mean() * 1e4:+.2f} vs "
                       f"unconditional {r_w.mean() * 1e4:+.2f} bps, difference {diff * 1e4:+.2f} bps (95% stationary-bootstrap CI "
                       f"{lo * 1e4:+.2f}..{hi * 1e4:+.2f}; needs lower > {min_gap * 1e4:.0f}); block-shift p={p_shift:.4f}; halves "
                       f"{halves[0] * 1e4:+.2f} / {halves[1] * 1e4:+.2f} bps; DSR {'n/a' if dsr is None else f'{dsr:.3f}'} over {n_trials} trials; "
                       f"execution diagnostics: next-open-to-close {diag.get('next_open_to_close_diff_bps', float('nan')):+.2f} bps, "
                       f"next-close entry {diag['next_close_entry_diff_bps']:+.2f} bps — {why}"))
    return rep


# ==================================================================== T-421 Corwin-Schultz spread shocks ==

def corwin_schultz(high, low, close) -> np.ndarray:
    """Corwin-Schultz (2012) two-day high-low spread for the pair (t-1, t), with the paper's overnight adjustment
    (day t's range is shifted by any gap beyond the t-1 close) and negative estimates set to 0. S[0] is NaN."""
    H, L, C = (np.asarray(a, dtype=float) for a in (high, low, close))
    n = len(H); out = np.full(n, np.nan)
    if n < 2:
        return out
    h1, l1, c0 = H[1:].copy(), L[1:].copy(), C[:-1]
    up = l1 > c0
    h1[up] -= (l1[up] - c0[up]); l1[up] = c0[up]
    dn = h1 < c0
    l1[dn] += (c0[dn] - h1[dn]); h1[dn] = c0[dn]
    beta = np.log(h1 / l1) ** 2 + np.log(H[:-1] / L[:-1]) ** 2
    gamma = np.log(np.maximum(h1, H[:-1]) / np.minimum(l1, L[:-1])) ** 2
    k = 3.0 - 2.0 * math.sqrt(2.0)
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    s = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    out[1:] = np.maximum(s, 0.0)
    return out


def _hold_positions(n: int, signal_idx: Sequence[int], horizon: int) -> np.ndarray:
    """pos over return intervals k (close k-1 -> close k): bought at the close after the signal day s and held
    ``horizon`` days, i.e. pos[k] = 1 for k in [s+2, s+1+horizon]."""
    diff = np.zeros(n + 2)
    for s in signal_idx:
        a, b = s + 2, min(s + 1 + horizon, n - 1)
        if a <= b:
            diff[a] += 1; diff[b + 1] -= 1
    return (np.cumsum(diff)[:n] > 0).astype(float)


def _hold_net(pos: np.ndarray, adj: np.ndarray, cost_side: float) -> np.ndarray:
    r = np.zeros(len(adj)); r[1:] = adj[1:] / adj[:-1] - 1
    turn = np.abs(np.diff(np.concatenate([[0.0], pos])))
    return pos * r - cost_side * turn


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def spread_shock(days: Sequence[str], highs, lows, closes, adj, vix: dict, start: str = "2000-01-01", end: str = "2026-12-31",
                 window: int = 60, z_thr: float = 2.0, horizon: int = 20, min_coef: float = 0.01, block: int = 20, n_boot: int = 2000,
                 seed: int = 0, min_events: int = 60, n_trials: int = 32, cost_side: float = 0.0001,
                 exclude_years: Sequence[str] = ("2008", "2020")) -> dict:
    """T-421: regress the 20-day forward return (bought at the close after day t, R = A[t+21]/A[t+1] - 1) on a +2 sigma
    Corwin-Schultz shock indicator (spread vs its trailing 60 days) and the same-day VIX point change. Pass: >= 60
    non-overlapping shock events AND shock coefficient >= 1 point with p < 0.05 (H0 coefficient <= 0; 20-day circular
    block bootstrap) AND DSR >= 0.95 of the rule over 32 cells (zero-skill variance floor) AND the rule beats a
    VIX-only rule out of sample (walk-forward test windows, one-sided 95% lower bound of the Sharpe difference > 0).
    VIX-only rule: same holding after the same-day VIX change exceeds +2 sigma of its trailing 60 days."""
    H, L, C, A = (np.asarray(x, dtype=float) for x in (highs, lows, closes, adj))
    n = len(A); ds = np.array(days)
    S = corwin_schultz(H, L, C)
    z = _trailing_z(S, window)
    vd = sorted(vix); vv = np.array([vix[d] for d in vd], dtype=float)
    j = np.searchsorted(vd, list(days), side="right") - 1          # last VIX close on or before each SPY day
    v = np.where(j >= 0, vv[np.maximum(j, 0)], np.nan) if len(vd) else np.full(n, np.nan)
    dv = np.full(n, np.nan); dv[1:] = v[1:] - v[:-1]
    R = np.full(n, np.nan)
    if n > horizon + 1:
        R[: n - horizon - 1] = A[horizon + 1:] / A[1: n - horizon] - 1
    m = np.isfinite(z) & np.isfinite(dv) & np.isfinite(R) & _range_mask(ds, start, end)
    idx = np.where(m)[0]
    shock = z[idx] > z_thr
    ev, last = [], -10 ** 9
    for t in idx[shock]:
        if t - last >= horizon:
            ev.append(int(t)); last = t
    n_ev = len(ev)
    rep = {"n": n_ev, "n_rows": int(len(idx)), "n_shock_days": int(shock.sum()), "first": ds[idx[0]] if len(idx) else None,
           "last": ds[idx[-1]] if len(idx) else None}
    if n_ev < min_events and (shock.sum() < 2 or n_ev < 2):
        v_, why = _too_few(n_ev, min_events, "non-overlapping shock events", "the shock regression")
        rep.update(verdict=v_, reason=f"CS spread shock: {n_ev} non-overlapping events — {why}")
        return rep
    y = R[idx]; X = np.column_stack([np.ones(len(idx)), shock.astype(float), dv[idx]])
    coef = _ols(X, y); b = float(coef[1])
    rng = np.random.default_rng(seed); bb = np.full(n_boot, np.nan)
    for k in range(n_boot):
        j = _circ_idx(len(y), block, rng)
        if X[j, 1].sum() >= 2:
            bb[k] = _ols(X[j], y[j])[1]
    lo, hi = float(np.nanquantile(bb, 0.025)), float(np.nanquantile(bb, 0.975))
    p0, p1 = _p_boot(bb, b, 0.0), _p_boot(bb, b, min_coef)
    yrs = np.array([d[:4] for d in ds[idx]])
    keep = ~np.isin(yrs, list(exclude_years))
    b_ex = float(_ols(X[keep], y[keep])[1]) if X[keep, 1].sum() >= 2 else float("nan")
    uncond = float(y[shock].mean() - y.mean())
    # rules on the daily calendar of the window
    sig_all = np.where(np.isfinite(z) & (z > z_thr))[0]
    zv = _trailing_z(dv, window)
    sig_vix = np.where(np.isfinite(zv) & (zv > z_thr))[0]
    w = np.where(_range_mask(ds, start, end) & (np.arange(n) >= window + 1))[0]
    cs_net = _hold_net(_hold_positions(n, sig_all, horizon), A, cost_side)[w]
    vx_net = _hold_net(_hold_positions(n, sig_vix, horizon), A, cost_side)[w]
    dsr = _dsr(cs_net, n_trials)
    try:
        test = np.concatenate([te for _, te in walk_forward_splits(len(w), n_splits=4, min_train=len(w) // 3, embargo=horizon)])
        sd_obs, sd_lo = _sharpe_diff_lower(cs_net[test], vx_net[test], EQ_PPY, block, n_boot=n_boot, seed=seed, q=0.05)
        beats = bool(sd_obs > 0 and sd_lo > 0)
    except ValueError:
        if n_ev >= min_events:
            raise
        test, sd_obs, sd_lo, beats = np.zeros(0, dtype=int), float("nan"), float("nan"), None   # below min_n: window too short to split
    crit = [(f">= {min_events} non-overlapping events", True), (f"shock coefficient >= {min_coef * 100:.0f} point", b >= min_coef),
            ("p < 0.05 (H0 coefficient <= 0)", p0 < 0.05), (f"DSR >= 0.95 over {n_trials} cells", dsr >= DSR_PASS),
            ("beats the VIX-only rule out of sample", beats)]
    if n_ev < min_events:
        # rule 5: the coefficient fails decisively when its 95% CI lies wholly below 1 point, its p when the CI lies wholly at or
        # below 0, the DSR when the rule's daily Sharpe is significantly at or below 0, and the out-of-sample comparison when the
        # one-sided 95% upper bound of the Sharpe difference is at or below 0. Every interval needs >= 8 events.
        pts = lambda v_: f"{v_ * 100:+.2f} points"
        nu = math.ceil(len(y) / block)
        sd_hi = (_sharpe_diff_lower(cs_net[test], vx_net[test], EQ_PPY, block, n_boot=n_boot, seed=seed, q=0.95)[1]
                 if beats is not None and len(test) >= 2 else float("nan"))
        r5 = [(*crit[1], *_upper_dec(hi, min_coef, pts, n_ev, nu, strict=True, what="coefficient's 95% CI")),
                (*crit[2], *_upper_dec(hi, 0.0, pts, n_ev, nu, what="coefficient's 95% CI")),
                (*crit[3], *_dsr_dec(cs_net, n_ev)),
                (*crit[4], *((False, "walk-forward window too short") if beats is None else
                             _upper_dec(sd_hi, 0.0, lambda v_: f"{v_:+.2f}", n_ev, math.ceil(len(test) / block),
                                        what="one-sided 95% interval of the out-of-sample Sharpe difference")))]
        v_, why = _apply_rule5(rep, r5, n_ev, min_events, "non-overlapping shock events")
    else:
        v_, why = _decide(crit[1:], n_ev, min_events, "non-overlapping shock events")
    rep.update(coef_shock=b, coef_ci=[lo, hi], p_coef_le0=p0, p_coef_le_1pt=p1, coef_vix_change=float(coef[2]),
               coef_shock_ex_years=b_ex, excluded_years=list(exclude_years), shock_minus_unconditional=uncond, dsr=dsr, n_trials=n_trials,
               rule_sharpe=_sr(cs_net, EQ_PPY), vix_rule_sharpe=_sr(vx_net, EQ_PPY), oos_sharpe_diff=sd_obs, oos_sharpe_diff_lower95=sd_lo,
               oos_days=int(len(test)), mean_spread_bps=float(np.nanmean(S[idx]) * 1e4), verdict=v_,
               reason=(f"SPY {rep['first']}..{rep['last']}: {int(shock.sum())} shock days (CS spread > +{z_thr:g} sd of trailing {window}), "
                       f"{n_ev} non-overlapping events (need {min_events}); 20-day forward-return coefficient {b * 100:+.2f} points "
                       f"(95% CI {lo * 100:+.2f}..{hi * 100:+.2f}; need >= {min_coef * 100:.0f}) with p={p0:.3f} vs <= 0 (p={p1:.3f} vs <= 1 point), "
                       f"controlling for the VIX change; excluding {'/'.join(exclude_years)} {b_ex * 100:+.2f} points; rule DSR {dsr:.3f} "
                       f"over {n_trials} cells; out-of-sample Sharpe vs VIX-only rule {sd_obs:+.2f} (one-sided 95% lower {sd_lo:+.2f}) — {why}"))
    return rep


# ======================================================== T-304 Donchian breakout with ATR trailing stop ==

def atr_wilder(high, low, close, n: int = 20) -> np.ndarray:
    """Wilder ATR: TR_t = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|); seeded with the mean of the first n TRs."""
    H, L, C = (np.asarray(a, dtype=float) for a in (high, low, close))
    N = len(C); tr = np.full(N, np.nan); atr = np.full(N, np.nan)
    if N < 2:
        return atr
    tr[1:] = np.maximum(H[1:] - L[1:], np.maximum(np.abs(H[1:] - C[:-1]), np.abs(L[1:] - C[:-1])))
    if N > n:
        atr[n] = tr[1:n + 1].mean()
        for t in range(n + 1, N):
            atr[t] = atr[t - 1] + (tr[t] - atr[t - 1]) / n
    return atr


def donchian_atr_trades(high, low, close, n: int = 55, atr_n: int = 20, mult: float = 10.0, exit_n: Optional[int] = None):
    """Long-only N-day breakout. Signal at close t if close_t >= max(close_{t-N..t-1}); filled at close t+1. Exit signal
    at close s if close_s < min(close_{s-floor(N/4)..s-1}) or close_s < (highest close since entry) - mult x ATR_s;
    filled at close s+1. Returns (closed trades [(entry_idx, exit_idx)], open entry index or None)."""
    C = np.asarray(close, dtype=float); N = len(C)
    exit_n = exit_n or n // 4
    atr = atr_wilder(high, low, close, atr_n)
    trades = []; t = max(n, atr_n)
    while t < N - 1:
        if C[t] >= C[t - n:t].max():
            e = t + 1; peak = C[e]; s = e; x = None
            while s < N - 1:
                peak = max(peak, C[s])
                if C[s] < C[s - exit_n:s].min() or (math.isfinite(atr[s]) and C[s] < peak - mult * atr[s]):
                    x = s + 1
                    break
                s += 1
            if x is None:
                return trades, e
            trades.append((e, x)); t = x
            continue
        t += 1
    return trades, None


def breakout_vs_random(assets: dict, n: int = 55, atr_n: int = 20, mult: float = 10.0, n_random: int = 1000, n_boot: int = 5000,
                       seed: int = 0, min_n: int = 150, n_trials: int = 60, vix: Optional[dict] = None) -> dict:
    """T-304. ``assets``: name -> {days, high, low, close (dividend-adjusted OHLC), cost (per side), ppy}. For every rule
    trade draw ``n_random`` entries on the same asset with the same holding length (entries after the rule's warm-up,
    same cost); per-trade difference = rule net return - mean random net return. Pass: >= 150 pooled trades AND the
    asset x entry-year cluster-bootstrap 95% CI (5,000 draws) of the mean difference above 0 AND survives the
    60-trial correction: DSR > 0.95 on the rule's trade-return series or Holm-adjusted p < 0.05 (decided True when
    DSR passes or 60 p < 0.05, False when DSR fails and p >= 0.05, None when only the full 60-trial Holm ranking could
    decide). Fills at the close after the signal already carry any gap through the stop, so no extra slippage term."""
    rng = np.random.default_rng(seed)
    rows = []; per_asset = {}; open_trades = 0
    for name, a in assets.items():
        C = np.asarray(a["close"], dtype=float); Nn = len(C); cost = float(a["cost"]); days = a["days"]
        trades, open_e = donchian_atr_trades(a["high"], a["low"], C, n, atr_n, mult)
        open_trades += open_e is not None
        lo_e = max(n, atr_n) + 1
        nets = []
        pos = np.zeros(Nn)
        for e, x in trades:
            h = x - e
            net = C[x] / C[e] - 1 - 2 * cost
            hi_e = Nn - 1 - h
            if hi_e < lo_e:
                continue
            es = rng.integers(lo_e, hi_e + 1, n_random)
            rand = C[es + h] / C[es] - 1 - 2 * cost
            rows.append((name, days[e - 1], int(days[e][:4]), h, net, float(rand.mean()), float(rand.mean() + 2 * cost)))
            nets.append(net); pos[e + 1: x + 1] = 1.0
        r = np.zeros(Nn); r[1:] = C[1:] / C[:-1] - 1
        turn = np.abs(np.diff(np.concatenate([[0.0], pos])))
        live = slice(lo_e, Nn)
        rule_daily = (pos * r - cost * turn)[live]
        per_asset[name] = {"n_trades": len(nets), "mean_net": float(np.mean(nets)) if nets else None,
                           "rule_sharpe": _sr(rule_daily, a.get("ppy", EQ_PPY)), "buy_hold_sharpe": _sr(r[live], a.get("ppy", EQ_PPY)),
                           "first_day": days[lo_e] if Nn > lo_e else None}
    nt = len(rows)
    rep = {"n": nt, "assets": list(assets), "open_trades_dropped": int(open_trades), "per_asset": per_asset}
    if nt < min_n and nt < MIN_DECISIVE_OBS:
        v, why = _too_few(nt, min_n, "pooled trades", "a cluster-bootstrap interval")
        rep.update(verdict=v, reason=f"Donchian {n}/ATR x{mult:g}: {nt} pooled trades — {why}")
        return rep
    net = np.array([r_[4] for r_ in rows]); rnd = np.array([r_[5] for r_ in rows]); rnd_gross = np.array([r_[6] for r_ in rows])
    diff = net - rnd
    obs = float(diff.mean())
    keys = [(r_[0], r_[2]) for r_ in rows]
    uniq = {k: i for i, k in enumerate(sorted(set(keys)))}
    cid = np.array([uniq[k] for k in keys]); K = len(uniq)
    S = np.bincount(cid, weights=diff, minlength=K); Nk = np.bincount(cid, minlength=K).astype(float)
    draw = rng.integers(0, K, (n_boot, K))
    boot = S[draw].sum(axis=1) / Nk[draw].sum(axis=1)
    lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    p = _p_boot(boot, obs)
    dsr = _dsr(net, n_trials)
    bonf = min(1.0, n_trials * p)
    if dsr > DSR_PASS or bonf < 0.05:
        survive = True
    elif p >= 0.05:
        survive = False
    else:
        survive = None
    dec = {}
    for r_, d_ in zip(rows, diff):
        k = f"{str(r_[2])[:3]}0s"
        dec.setdefault(k, []).append(d_)
    dec = {k: {"n": len(v), "mean_diff": float(np.mean(v))} for k, v in sorted(dec.items())}
    terc = None
    if vix:
        vd = sorted(vix); vv = np.array([vix[d] for d in vd])
        lvl = []
        for r_ in rows:
            j = np.searchsorted(vd, r_[1], side="right") - 1
            lvl.append(vv[j] if j >= 0 else np.nan)
        lvl = np.array(lvl); ok = np.isfinite(lvl)
        if ok.sum() >= 6:
            q1, q2 = np.quantile(lvl[ok], [1 / 3, 2 / 3])
            terc = {nm: float(diff[ok & msk].mean()) if np.any(ok & msk) else None
                    for nm, msk in (("low", lvl <= q1), ("mid", (lvl > q1) & (lvl <= q2)), ("high", lvl > q2))}
    crit = [("mean difference > 0 with cluster-bootstrap 95% CI excluding 0", lo > 0),
            (f"survives the {n_trials}-trial correction (DSR > 0.95 or Holm p < 0.05)", survive)]
    if nt < min_n:
        # rule 5: the difference fails decisively when its cluster 95% CI lies wholly at or below 0; the trial correction when
        # both of its routes fail decisively: the rule's trade-return Sharpe significantly at or below 0 (no DSR can pass) and
        # the CI wholly at or below 0 (no Holm-adjusted p can reach 0.05)
        pct = lambda v_: f"{v_ * 100:+.2f}%"
        cdec = _upper_dec(hi, 0.0, pct, nt, K, what="cluster 95% CI")
        ddec = _dsr_dec(net, nt)
        r5 = [(*crit[0], *cdec), (*crit[1], cdec[0] and ddec[0], f"DSR route: {ddec[1]}; Holm route: {cdec[1]}")]
        v, why = _apply_rule5(rep, r5, nt, min_n, "pooled trades")
    else:
        v, why = _decide(crit, nt, min_n, "pooled trades")
    rep.update(mean_rule_net=float(net.mean()), mean_random_net=float(rnd.mean()), mean_diff=obs, ci=[lo, hi], p=p, p_bonferroni=bonf,
               dsr=dsr, n_trials=n_trials, n_clusters=K, mean_diff_vs_gross_random=float((net - rnd_gross).mean()),
               trade_skew=float(skewness(net)), mean_hold_days=float(np.mean([r_[3] for r_ in rows])), by_decade=dec, by_vix_tercile=terc,
               verdict=v,
               reason=(f"{nt} closed trades across {len(assets)} assets ({K} asset-year clusters): rule mean net {net.mean() * 100:+.2f}% vs matched "
                       f"random entries {rnd.mean() * 100:+.2f}% (same costs), difference {obs * 100:+.2f}% (cluster 95% CI {lo * 100:+.2f}..{hi * 100:+.2f}, "
                       f"p={p:.4f}, 60-trial Bonferroni {bonf:.3f}); trade-return DSR {dsr:.3f} over {n_trials}; vs cost-free random "
                       f"{(net - rnd_gross).mean() * 100:+.2f}%; trade skew {skewness(net):+.2f} — {why}"))
    return rep


# ========================================================================= T-324 SPY/IVV twin reversion ==

def twin_trades(z: np.ndarray, first: int, last: int, entry_z: float = 2.0, max_hold: int = 5) -> list:
    """Signals on closes first..last: |z_t| > entry_z -> position at close t+1 (side -1 = short A / long B when z > 0).
    Exit at the close after z crosses 0 (sign flips or hits 0), or at the close ``max_hold`` days after entry,
    whichever is first. One position at a time. Returns [(entry_idx, exit_idx, side)]."""
    N = len(z); out = []; t = first
    while t <= last and t < N - 1:
        if math.isfinite(z[t]) and abs(z[t]) > entry_z:
            sgn = 1.0 if z[t] > 0 else -1.0
            e = t + 1; cap = e + max_hold; x = None
            for s in range(e, min(cap, N - 1) + 1):
                if s == cap:
                    x = cap
                    break
                if math.isfinite(z[s]) and z[s] * sgn <= 0:
                    x = min(s + 1, cap)
                    break
            if x is None or x > N - 1:
                break
            out.append((e, x, -sgn)); t = x
            continue
        t += 1
    return out


def twin_reversion(days: Sequence[str], a, b, start: str = "2010-01-01", end: str = "2026-09-30", window: int = 60, entry_z: float = 2.0,
                   max_hold: int = 5, cost_rt: float = 0.0008, n_boot: int = 5000, seed: int = 0, min_n: int = 1000, n_trials: int = 5,
                   trial_sharpes: Optional[Sequence[float]] = None) -> dict:
    """T-324 on aligned adjusted closes of twins A and B: x = ln(A/B), z over the trailing 60 days (including t). Net
    return per trade = side x (A leg return - B leg return) - 8 bps (2 bps per leg per transaction, equal dollars).
    Pass: 95% lower bound of the mean net return per trade > 0 (bootstrap clustered by entry month) AND DSR > 0.95
    of the trade-return series across ``n_trials`` twin variants. min_n counts trades, the unit of the per-trade
    statistic (as for T-304 and T-333); below it the verdict is inconclusive and the statistics are still reported."""
    A = np.asarray(a, dtype=float); B = np.asarray(b, dtype=float); ds = np.array(days)
    x = np.log(A / B)
    z = _trailing_z(x, window, include_current=True)
    inw = _range_mask(ds, start, end) & np.isfinite(z)
    n_days = int(inw.sum())
    w = np.where(inw)[0]
    trades = twin_trades(z, int(w[0]), int(w[-1]), entry_z, max_hold) if n_days else []
    n_tr = len(trades)
    rep = {"n": n_tr, "n_trades": n_tr, "n_days": n_days, "first": ds[inw][0] if n_days else None, "last": ds[inw][-1] if n_days else None,
           "max_feasible_trades": n_days // 2}
    if n_tr < 2:
        v, why = _decide([], n_tr, min_n, "trades")
        if v != "inconclusive":
            v, why = "inconclusive", f"data cannot support the claim: {n_tr} trades, too few for a bootstrap interval"
        rep.update(verdict=v, reason=f"twin spread: {n_tr} trades on {n_days} days — {why}")
        return rep
    e_i = np.array([t[0] for t in trades]); x_i = np.array([t[1] for t in trades]); side = np.array([t[2] for t in trades])
    gross = side * ((A[x_i] / A[e_i] - 1) - (B[x_i] / B[e_i] - 1))
    net = gross - cost_rt
    mean = float(net.mean())
    months = np.array([ds[i - 1][:7] for i in e_i])
    uniq = {m_: k for k, m_ in enumerate(sorted(set(months)))}
    cid = np.array([uniq[m_] for m_ in months]); K = len(uniq)
    S = np.bincount(cid, weights=net, minlength=K); Nk = np.bincount(cid, minlength=K).astype(float)
    rng = np.random.default_rng(seed); draw = rng.integers(0, K, (n_boot, K))
    boot = S[draw].sum(axis=1) / Nk[draw].sum(axis=1)
    lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    dsr = _dsr(net, n_trials, trial_sharpes)
    xw = x[w]
    phi = float(np.polyfit(xw[:-1], xw[1:], 1)[0]) if len(xw) > 2 else float("nan")
    half_life = float(-math.log(2) / math.log(phi)) if 0 < phi < 1 else None
    mu60 = _rolling_mean(x, window)
    exc = np.abs(x[e_i - 1] - mu60[e_i - 1])
    mar20 = months == "2020-03"
    crit = [("95% lower bound of mean net return per trade > 0", lo > 0), (f"DSR > 0.95 across {n_trials} twin variants", dsr > DSR_PASS)]
    if n_tr < min_n:
        # rule 5: the lower bound fails decisively when the whole month-clustered 95% CI lies at or below 0; the DSR when the
        # trade-return Sharpe is significantly at or below 0
        bps = lambda v_: f"{v_ * 1e4:+.2f} bps"
        r5 = [(*crit[0], *_upper_dec(hi, 0.0, bps, n_tr, K, what="month-clustered 95% CI")), (*crit[1], *_dsr_dec(net, n_tr))]
        v, why = _apply_rule5(rep, r5, n_tr, min_n, "trades")
    else:
        v, why = _decide(crit, n_tr, min_n, "trades")
    below = ""
    if n_tr < min_n:
        failing = [nm for nm, ok in crit if not ok]
        below = (f"; min_n counted in trades (the statistic is per trade): {n_tr} trades, the window allows about {n_days // 2} at most; "
                 + (f"on the trades available the CI lies {'entirely below 0' if hi < 0 else 'across 0' if lo <= 0 else 'above 0'} and "
                    f"these criteria would fail: {'; '.join(failing)}" if failing else "on the trades available every criterion would pass"))
    rep.update(mean_gross_bps=float(gross.mean() * 1e4), mean_net_bps=mean * 1e4, ci_bps=[lo * 1e4, hi * 1e4],
               criteria_on_available_trades={nm: bool(ok) for nm, ok in crit},
               dsr=dsr, n_trials=n_trials, n_month_clusters=K, ar1_phi=phi, half_life_days=half_life,
               share_signals_excursion_gt_cost=float(np.mean(exc > cost_rt)), mean_hold_days=float(np.mean(x_i - e_i)),
               march_2020={"n": int(mar20.sum()), "mean_net_bps": float(net[mar20].mean() * 1e4) if mar20.any() else None},
               ex_march_2020_mean_net_bps=float(net[~mar20].mean() * 1e4) if (~mar20).any() else None, verdict=v,
               reason=(f"SPY/IVV {rep['first']}..{rep['last']} ({n_days} days): {len(trades)} trades at |z|>{entry_z:g}, mean gross "
                       f"{gross.mean() * 1e4:+.2f} bps, net {mean * 1e4:+.2f} bps after {cost_rt * 1e4:.0f} bps RT (month-clustered 95% CI "
                       f"{lo * 1e4:+.2f}..{hi * 1e4:+.2f}); DSR {dsr:.3f} across {n_trials} twins (variance of trial Sharpes "
                       f"{'from variants' if trial_sharpes and len(trial_sharpes) >= 2 else 'zero-skill floor: VOO, IAU, QQQM, FBTC not archived'}); "
                       f"AR(1) phi {phi:.3f}, half-life {'n/a' if half_life is None else f'{half_life:.1f}'} days; "
                       f"{np.mean(exc > cost_rt) * 100:.0f}% of signals with excursion > cost; March 2020 {int(mar20.sum())} trades{below} — {why}"))
    return rep


# ===================================================================== T-216 opex pin, MODEL-PRICED straddle ==

def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def thu_fri_straddles(days: Sequence[str], closes, vix: dict, divs=None, T: float = 1.0 / EQ_PPY):
    """One row per Friday whose previous trading day is the calendar Thursday and has a VIX close: (friday, pnl,
    as-worded pnl, premium) in fraction of spot for a short ATM straddle sold at Thursday's close (K = S_thu,
    sigma = VIX/100, r = 0) and settled on the raw closes, |S_fri - S_thu|, as the procedure states. ``pnl`` prices
    the straddle on the forward S_thu - D, with D the cash dividend going ex on that Friday (SPY declares it before
    the ex-date, so it is known at the sale); ``premium`` is that price. The as-worded pnl prices at r = q = 0 with no
    dividend (the two agree on Fridays without a dividend)."""
    C = np.asarray(closes, dtype=float); D = np.zeros(len(C)) if divs is None else np.asarray(divs, dtype=float)
    fri, K, sig, dv, raw = [], [], [], [], []
    for i in range(1, len(days)):
        df, dt = date.fromisoformat(days[i]), date.fromisoformat(days[i - 1])
        if df.weekday() != 4 or (df - dt).days != 1 or days[i - 1] not in vix:
            continue
        fri.append(days[i]); K.append(C[i - 1]); sig.append(vix[days[i - 1]] / 100.0); dv.append(D[i]); raw.append(C[i])
    if not fri:
        return [], np.array([]), np.array([]), np.array([])
    K, sig, dv, raw = (np.array(x, dtype=float) for x in (K, sig, dv, raw))
    F = K - dv
    prem = bs.price(F, K, T, 0.0, sig, "call") + bs.price(F, K, T, 0.0, sig, "put")
    prem0 = bs.price(K, K, T, 0.0, sig, "call") + bs.price(K, K, T, 0.0, sig, "put")
    pnl = (prem - np.abs(raw - K)) / K
    pnl_raw = (prem0 - np.abs(raw - K)) / K
    return fri, pnl, pnl_raw, prem / K


def opex_straddle(days: Sequence[str], closes, vix: dict, divs=None, fomc_days: Optional[set] = None, start: Optional[str] = None,
                  end: Optional[str] = None, block: int = 8, n_boot: int = 4000, seed: int = 0, min_n: int = 300, n_perm: int = 5000,
                  split: str = "2010-01-01", cpi_days: Optional[Sequence[str]] = None) -> dict:
    """T-216 (MODEL-PRICED): mean short-straddle P&L on monthly third-Friday expirations minus other Fridays. Pass:
    difference > 0 with the two-sided 95% block-bootstrap CI (block of ``block`` Fridays) excluding 0, over >= 300
    opex Fridays. Settlement on the raw closes |SPY_Fri - SPY_Thu|; the known ex-date dividend is priced into the
    forward. Secondary: distance of the Friday close to the nearest $1 strike, opex vs other (permutation test).
    Controls (reported, not criteria): FOMC-day exclusion, the trial's "exclude opex days with FOMC/CPI" (with
    ``cpi_days``: an opex Friday is dropped when it is the first session on or after a CPI release, whose 08:30 ET print
    falls inside the Thursday-close-to-Friday-close window, or when it or its Thursday is a scheduled FOMC decision day;
    reported with a block-bootstrap CI, with the same Fridays also out of the non-opex group, and with Thursday CPI
    releases, which come before the sale, also dropped), quarterly vs other opex, pre/post-2010. Sensitivities: the
    as-worded r = q = 0 price that ignores the dividend, and all ex-dividend Fridays dropped."""
    fri, pnl, pnl_raw, prem = thu_fri_straddles(days, closes, vix, divs)
    fr = np.array(fri)
    m = _range_mask(fr, start, end) if len(fr) else np.zeros(0, dtype=bool)
    fr, pnl, pnl_raw, prem = fr[m], pnl[m], pnl_raw[m], prem[m]
    tf = {third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in fr}
    ox = np.array([d in tf for d in fr], dtype=bool)
    n = int(ox.sum())
    rep = {"n": n, "n_other": int((~ox).sum()), "first": fr[0] if len(fr) else None, "last": fr[-1] if len(fr) else None,
           "label": "MODEL-PRICED"}
    if n < min_n and (n < 2 or (~ox).sum() < 2 or len(fr) < 8):
        v, why = _too_few(n, min_n, "opex Fridays", "a block-bootstrap difference")
        rep.update(verdict=v, reason=f"MODEL-PRICED opex straddle: {n} opex Fridays — {why}")
        return rep
    if (~ox).sum() < 2:
        v, why = _decide([], n, min_n, "opex Fridays")
        rep.update(verdict=v, reason=f"MODEL-PRICED opex straddle: {n} opex Fridays — {why}")
        return rep
    g = group_diff(pnl, ox, block, n_boot, seed)
    g_raw = group_diff(pnl_raw, ox, block, n_boot, seed)
    dmap = {} if divs is None else {d: float(x) for d, x in zip(days, np.asarray(divs, dtype=float))}
    exd = np.array([dmap.get(d, 0.0) > 0 for d in fr], dtype=bool)
    g_nodiv = group_diff(pnl[~exd], ox[~exd], block, n_boot, seed) if exd.any() else g
    nd_ok = g_nodiv["diff"] is not None
    nd_txt = (f"{g_nodiv['diff'] * 1e4:+.2f}, CI {g_nodiv['ci'][0] * 1e4:+.2f}..{g_nodiv['ci'][1] * 1e4:+.2f}" if nd_ok
              else f"n/a ({g_nodiv['n_flag']} opex Fridays left)")
    quarterly = np.array([int(d[5:7]) in (3, 6, 9, 12) for d in fr])
    ctrl = {"quarterly_opex_minus_other_bps": float((pnl[ox & quarterly].mean() - pnl[~ox].mean()) * 1e4) if np.any(ox & quarterly) else None,
            "monthly_only_opex_minus_other_bps": float((pnl[ox & ~quarterly].mean() - pnl[~ox].mean()) * 1e4) if np.any(ox & ~quarterly) else None}
    for nm, msk in (("pre_" + split[:4], fr < split), ("post_" + split[:4], fr >= split)):
        ctrl[nm + "_diff_bps"] = float((pnl[msk & ox].mean() - pnl[msk & ~ox].mean()) * 1e4) if np.any(msk & ox) and np.any(msk & ~ox) else None
    di = {d: i for i, d in enumerate(days)}
    near = np.zeros(len(fr), dtype=bool)
    if fomc_days:
        near = np.array([d in fomc_days or days[di[d] - 1] in fomc_days for d in fr], dtype=bool)
        k = ~(near & ox)
        ctrl["ex_fomc_opex_diff_bps"] = float((pnl[k & ox].mean() - pnl[k & ~ox].mean()) * 1e4)
        ctrl["n_opex_fomc_excluded"] = int((near & ox).sum())
    not_run, macro_txt = [], ""
    if cpi_days is not None:
        cs = set(to_sessions(cpi_days, list(days))[0])                   # first session on or after each 08:30 ET release
        cpi_fri = np.array([d in cs for d in fr], dtype=bool)             # released inside the Thu-close -> Fri-close window
        cpi_thu = np.array([days[di[d] - 1] in cs for d in fr], dtype=bool)   # released before Thursday's close (the sale)
        macro = near | cpi_fri

        def gd(keep):                                                   # opex-minus-other on the kept Fridays, in bps
            g_ = group_diff(pnl[keep], ox[keep], block, n_boot, seed)
            return {"n_opex": g_["n_flag"], "n_other": g_["n_other"], "diff_bps": None if g_["diff"] is None else g_["diff"] * 1e4,
                    "ci_bps": [None if c_ is None else c_ * 1e4 for c_ in g_["ci"]], "p": g_["p"]}
        gx = gd(~(macro & ox))
        kc = ~(cpi_fri & ox)
        ctrl["ex_cpi_opex_diff_bps"] = float((pnl[kc & ox].mean() - pnl[kc & ~ox].mean()) * 1e4) if np.any(kc & ox) else None
        ctrl["n_opex_cpi_excluded"] = int((cpi_fri & ox).sum())
        ctrl["ex_fomc_cpi_opex"] = {
            "rule": "opex Fridays dropped when the Friday is a CPI release session (08:30 ET, inside the straddle window) or the "
                    "Friday or its Thursday is a scheduled FOMC decision day; other Fridays kept",
            "n_opex_excluded": int((macro & ox).sum()), **gx,
            "macro_fridays_out_of_both_groups": {**gd(~macro), "n_fridays_dropped": int(macro.sum())},
            "also_thursday_cpi": {**gd(~((macro | cpi_thu) & ox)), "n_opex_thursday_cpi": int((cpi_thu & ox).sum()),
                                  "note": "a Thursday 08:30 ET release precedes the Thursday-close sale; dropped here as a sensitivity"}}
        e = ctrl["ex_fomc_cpi_opex"]
        ci_txt = lambda r: (f"{r['diff_bps']:+.2f} bps (CI {r['ci_bps'][0]:+.2f}..{r['ci_bps'][1]:+.2f})" if r["diff_bps"] is not None and r["ci_bps"][0] is not None
                            else ("n/a" if r["diff_bps"] is None else f"{r['diff_bps']:+.2f} bps"))
        macro_txt = (f"; control, opex Fridays with FOMC/CPI excluded ({e['n_opex_excluded']} dropped, {ctrl['n_opex_cpi_excluded']} for CPI): "
                     f"{ci_txt(e)}, same Fridays out of both groups {ci_txt(e['macro_fridays_out_of_both_groups'])}, "
                     f"Thursday CPI also dropped {ci_txt(e['also_thursday_cpi'])}")
    else:
        not_run.append("CPI part of the FOMC/CPI opex exclusion control (macro-release-cpi not archived)")
        macro_txt = "; CPI exclusion control not run (macro-release-cpi not archived)"
    C = np.asarray(closes, dtype=float)
    fri_i = [i for i, d in enumerate(days) if date.fromisoformat(d).weekday() == 4 and (not start or d >= start) and (not end or d <= end)]
    dist = np.array([abs(C[i] - round(C[i])) for i in fri_i])
    oxa = np.array([days[i] == third_friday(int(days[i][:4]), int(days[i][5:7])).isoformat() for i in fri_i], dtype=bool)
    pin = {}
    if oxa.any() and (~oxa).any():
        obs = float(dist[oxa].mean() - dist[~oxa].mean())
        rng = np.random.default_rng(seed); perm = np.empty(n_perm)
        for k in range(n_perm):
            s = rng.permutation(oxa); perm[k] = dist[s].mean() - dist[~s].mean()
        pin = {"opex_mean_distance": float(dist[oxa].mean()), "other_mean_distance": float(dist[~oxa].mean()), "diff": obs,
               "p_opex_closer": float((np.sum(perm <= obs) + 1) / (n_perm + 1))}
    lo, hi = g["ci"]
    crit = [("difference > 0", g["diff"] > 0), ("95% CI excludes 0", lo > 0)]
    crit_raw = [("difference > 0", g_raw["diff"] > 0), ("95% CI excludes 0", g_raw["ci"][0] > 0)]
    if n < min_n:
        # rule 5: both criteria fail decisively when the block-bootstrap 95% CI of the difference lies wholly at or below 0
        bps = lambda v_: f"{v_ * 1e4:+.2f} bps"
        nu = math.ceil(len(fr) / block)
        r5 = lambda cr, hi_: [(*c_, *_upper_dec(hi_, 0.0, bps, n, nu, what=f"block-{block} 95% CI")) for c_ in cr]
        v, why = _apply_rule5(rep, r5(crit, hi), n, min_n, "opex Fridays")
        v_raw = _rule5(r5(crit_raw, g_raw["ci"][1]), n, min_n, "opex Fridays")[0]
    else:
        v, why = _decide(crit, n, min_n, "opex Fridays")
        v_raw, _ = _decide(crit_raw, n, min_n, "opex Fridays")
    n_exd_opex = int((exd & ox).sum())
    rep.update(mean_opex_bps=g["mean_flag"] * 1e4, mean_other_bps=g["mean_other"] * 1e4, diff_bps=g["diff"] * 1e4,
               ci_bps=[lo * 1e4, hi * 1e4], p=g["p"], mean_premium_bps=float(prem.mean() * 1e4),
               settlement="raw closes |SPY_Fri - SPY_Thu|", pricing="BS on the forward S_thu - D (known ex-date dividend), r = 0",
               as_worded_r0_no_dividend={"diff_bps": g_raw["diff"] * 1e4, "ci_bps": [g_raw["ci"][0] * 1e4, g_raw["ci"][1] * 1e4],
                                         "p": g_raw["p"], "verdict": v_raw},
               verdict_depends_on_dividend_treatment=bool(v_raw != v), n_ex_dividend_opex=n_exd_opex,
               ex_dividend_fridays_excluded={"n_excluded": int(exd.sum()), "n_opex": g_nodiv["n_flag"],
                                             "diff_bps": g_nodiv["diff"] * 1e4 if nd_ok else None,
                                             "ci_bps": [g_nodiv["ci"][0] * 1e4, g_nodiv["ci"][1] * 1e4] if nd_ok else [None, None]},
               controls=ctrl, not_run=not_run, strike_pin=pin, verdict=v,
               reason=(f"MODEL-PRICED (BS, sigma = Thursday VIX, T=1/252): {n} opex vs {int((~ox).sum())} other Fridays "
                       f"{rep['first']}..{rep['last']}; short-straddle P&L {g['mean_flag'] * 1e4:+.2f} vs {g['mean_other'] * 1e4:+.2f} bps of spot, "
                       f"difference {g['diff'] * 1e4:+.2f} bps (95% block-{block} CI {lo * 1e4:+.2f}..{hi * 1e4:+.2f}, p={g['p']:.3f}); "
                       f"settled on raw closes |SPY_Fri - SPY_Thu| with the known dividend priced into the forward S_thu - D on the "
                       f"{int(exd.sum())} ex-dividend Fridays ({n_exd_opex} of them opex); as-worded sensitivity at r = q = 0 ignoring the dividend: "
                       f"{g_raw['diff'] * 1e4:+.2f}, CI {g_raw['ci'][0] * 1e4:+.2f}..{g_raw['ci'][1] * 1e4:+.2f} ({v_raw.replace('_', ' ')}"
                       f"{', so the verdict depends on how the dividend is treated' if v_raw != v else ''}); with all ex-dividend Fridays dropped: "
                       f"{nd_txt}{macro_txt}; $1-strike distance opex {pin.get('opex_mean_distance', float('nan')):.3f} vs "
                       f"{pin.get('other_mean_distance', float('nan')):.3f} (perm p={pin.get('p_opex_closer', float('nan')):.3f}) — {why}"))
    return rep


# ===================================================================================================== harnesses ==

def ohlc_opex_pin_straddle(archive):
    """T-216: MODEL-PRICED 1-day SPY short straddle, opex Fridays minus other Fridays, 1993-2026."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history"])
    if miss:
        return miss
    b = _bars(archive, "SPY")
    fomc = _fomc_days(archive) if _has(archive, "fomc-meetings") else None
    return _wrap(opex_straddle(b.days, b.close, _index(archive, "cboe-VIX-history"), ex_dividends(b.close, b.adj), fomc_days=fomc,
                               cpi_days=_cpi_days(archive)))


DONCHIAN_ASSETS = {"SPY": 0.0005, "QQQ": 0.0005, "GLD": 0.0005, "SLV": 0.0005, "XLK": 0.0005, "XLE": 0.0005,
                   "BTC-USD": 0.0035, "ETH-USD": 0.0035}


def ohlc_donchian_atr_breakout(archive):
    """T-304: pooled 55-day breakout / 10-ATR trailing stop trades vs matched random entries (8 ETFs and crypto pairs)."""
    miss = _missing(archive, [_bundle(s) for s in DONCHIAN_ASSETS])
    if miss:
        return miss
    assets = {}
    for s, cost in DONCHIAN_ASSETS.items():
        b = _bars(archive, s)
        _, h, l, c = adjusted_ohlc(b)
        assets[s] = {"days": b.days, "high": h, "low": l, "close": c, "cost": cost, "ppy": CRYPTO_PPY if s.endswith("-USD") else EQ_PPY}
    vix = _index(archive, "cboe-VIX-history") if _has(archive, "cboe-VIX-history") else None
    return _wrap(breakout_vs_random(assets, vix=vix))


def ohlc_spy_ivv_twin(archive):
    """T-324: SPY/IVV 60-day z-score twin rule, 2010-01..2026-09, 8 bps per round trip of both legs."""
    miss = _missing(archive, ["daily-history-SPY", "daily-history-IVV"])
    if miss:
        return miss
    sa, sb = _bars(archive, "SPY"), _bars(archive, "IVV")
    pa = dict(zip(sa.days, sa.adj)); pb = dict(zip(sb.days, sb.adj))
    days = sorted(set(pa) & set(pb))
    rep = twin_reversion(days, [pa[d] for d in days], [pb[d] for d in days])
    rep["missing_twins"] = ["SPY/VOO", "GLD/IAU", "QQQ/QQQM", "IBIT/FBTC"]
    return _wrap(rep)


def ohlc_ibs_reversal(archive):
    """T-332: SPY next-day return after IBS < 0.2 minus unconditional, 2000-01..2026-09, DSR over 6 rules x SPY/QQQ."""
    miss = _missing(archive, ["daily-history-SPY"])
    if miss:
        return miss
    b = _bars(archive, "SPY")
    sharpes = []
    for sym in ("SPY", "QQQ"):
        if not _has(archive, _bundle(sym)):
            continue
        bb = _bars(archive, sym); ds = np.array(bb.days[:-1]); nd = np.array(bb.days[1:])
        w = (ds >= "2000-01-01") & (nd <= "2026-09-30")
        for pos in reversal_rule_positions(bb.high, bb.low, bb.close, bb.adj).values():
            sharpes.append(sharpe_ratio(rule_daily_net(pos, bb.adj)[w]))
    rep = ibs_reversal(b.days, b.high, b.low, b.close, b.adj, opens=b.open, grid_sharpes=sharpes)
    rep["n_grid_variants_archived"] = len(sharpes)
    try:
        grid = []
        bb = b; ds = np.array(bb.days[:-1]); nd = np.array(bb.days[1:]); w = (ds >= "2000-01-01") & (nd <= "2026-09-30")
        for pos in reversal_rule_positions(bb.high, bb.low, bb.close, bb.adj).values():
            grid.append(rule_daily_net(pos, bb.adj)[w])
        rep["pbo_spy_6_rules"] = pbo_cscv(np.column_stack(grid), n_partitions=8)["pbo"]
    except Exception as exc:                       # diagnostic only
        rep["pbo_spy_6_rules"] = f"n/a ({exc})"
    return _wrap(rep)


def ohlc_gap_fade(archive):
    """T-333: SPY gap fade (|gap| > 0.5%, open to close, 2 bps RT), 2000-01..2026-09, gaps net of the ex-date dividend
    (raw gaps reported); DSR over SPY/QQQ x 3 thresholds; IBIT control reported."""
    miss = _missing(archive, ["daily-history-SPY"])
    if miss:
        return miss
    b = _bars(archive, "SPY")
    sharpes = []
    for sym in ("SPY", "QQQ"):
        if not _has(archive, _bundle(sym)):
            continue
        bb = _bars(archive, sym); ds = np.array(bb.days[1:]); w = (ds >= "2000-01-01") & (ds <= "2026-09-30")
        dv = ex_dividends(bb.close, bb.adj)
        for thr in (0.0025, 0.005, 0.01):
            sharpes.append(sharpe_ratio(gap_fade_series(bb.open, bb.close, thr, 0.0002, dv)[3][w]))
    rep = gap_fade(b.days, b.open, b.close, variant_sharpes=sharpes, divs=ex_dividends(b.close, b.adj))
    rep["variants"] = "SPY, QQQ x |gap| > 0.25%, 0.5%, 1.0%"
    if _has(archive, "daily-history-IBIT"):
        ib = _bars(archive, "IBIT")
        ctl = gap_fade(ib.days, ib.open, ib.close, start="2024-01-01", end="2026-09-30", min_n=1)
        rep["ibit_control"] = {k: ctl.get(k) for k in ("n", "first", "mean_net_bps", "ci_bps")}
        if ctl.get("mean_net_bps") is not None:
            head, sep, tail = rep["reason"].rpartition(" — ")
            rep["reason"] = f"{head}; IBIT control (expected no edge) {ctl['n']} trades, mean {ctl['mean_net_bps']:+.1f} bps{sep}{tail}"
    return _wrap(rep)


def ohlc_overnight_vs_intraday(archive):
    """T-348: SPY close-to-open (dividends added back on ex-dates) minus open-to-close, 1993-2026."""
    miss = _missing(archive, ["daily-history-SPY"])
    if miss:
        return miss
    b = _bars(archive, "SPY")
    return _wrap(overnight_intraday(b.days, b.open, b.close, ex_dividends(b.close, b.adj), adj=b.adj, start="1993-01-01", end="2026-12-31"))


def ohlc_cs_spread_shock(archive):
    """T-421: SPY Corwin-Schultz +2 sigma spread shocks and the 20-day forward return, 2000-2026, VIX-change control."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history"])
    if miss:
        return miss
    b = _bars(archive, "SPY")
    return _wrap(spread_shock(b.days, b.high, b.low, b.close, b.adj, _index(archive, "cboe-VIX-history")))


HARNESSES = {
    "ohlc_opex_pin_straddle": ohlc_opex_pin_straddle,
    "ohlc_donchian_atr_breakout": ohlc_donchian_atr_breakout,
    "ohlc_spy_ivv_twin": ohlc_spy_ivv_twin,
    "ohlc_ibs_reversal": ohlc_ibs_reversal,
    "ohlc_gap_fade": ohlc_gap_fade,
    "ohlc_overnight_vs_intraday": ohlc_overnight_vs_intraday,
    "ohlc_cs_spread_shock": ohlc_cs_spread_shock,
}

THEORY_MAP = {
    "T-216": "ohlc_opex_pin_straddle",
    "T-304": "ohlc_donchian_atr_breakout",
    "T-324": "ohlc_spy_ivv_twin",
    "T-332": "ohlc_ibs_reversal",
    "T-333": "ohlc_gap_fade",
    "T-348": "ohlc_overnight_vs_intraday",
    "T-421": "ohlc_cs_spread_shock",
}
