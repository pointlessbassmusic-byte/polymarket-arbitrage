"""
Batch 6b, group ``bw``: buy-write and put-write claims on Cboe strategy-index histories and on model-priced overlays.
====================================================================================================================

Eleven options-library claims, each tested on its own claim, trial.pass and trial.min_n as worded.

Traded index histories (``cboe-<SYM>-history``, built by ``mandel.data.cboe_strategy`` from Cboe's published files):
  * T-161  BXM monthly excess return regressed on SPY total-return excess return: annualised Jensen alpha, 2002-03..2026-10.
  * T-162  Sharpe(BXMD) - Sharpe(BXM), 2002-03..2026-10 (studentized CBB and the Ledoit-Wolf test the trial names: rule 11).
  * T-163  Sharpe(BXMW) - Sharpe(BXM), 2012-06..2026-10, split pre/post 2020 as the trial's procedure says.
  * T-164  Sharpe(BXMH) - Sharpe(BXM), 2002-03..2026-10.
  * T-170  Sharpe(PUT) - Sharpe(BXM), 2007-01..2026-10.
  * T-172  Sharpe(CMBO) - Sharpe(BXY), 1988-06..2026-10.
  * T-202  annualised return (CAGR) of PUT minus BXM over their common daily history (PUT is daily from 2007-01-03).
MODEL-PRICED (Black-Scholes legs at a stated multiple of VIX/100; never traded prices; every reason says MODEL-PRICED):
  * T-128  SPY 1-month ATM put-write (PUT-index construction: puts on the full account, premium and collateral in
           3-month bills) against SPY total return, 1993-2026, at IV scale 1.0 and 0.9.
  * T-171  SPX wheel whose call strike is floored at the cost basis against the same wheel writing the 30-delta call.
  * T-174  short SPX + short monthly ATM SPX put with bill interest on the proceeds: share of rolling 120-month windows
           with a negative CAGR.
  * T-527  short-ATM / long-5%-OTM call-spread overwrite against the ATM covered call on SPX.
  T-171, T-174 and T-527 require the pricer to pass a calibration gate first: the same pricer, run on the BXM rule
  (2002-, ATM call at the first 5-point strike at or above the index) and the PUT rule (2007-, ATM put at the first
  5-point strike at or below, premium and K in bills), must reproduce the indices' monthly roll-to-roll returns with a
  tracking error (sd of the monthly difference x sqrt 12) below 2%/yr (T-527: BXM only). T-171 and T-527 name the gate
  in their pass; T-174's procedure requires it, so it is a criterion there too.

Conventions (house rules)
  * Sampling. The index claims name month-end excess returns: each series is sampled on the last day of every calendar
    month on the pair's COMMON calendar (a month-end missing from one file falls back to the last common day), so rule
    10(a) applies (named calendar, no grid phase). The indices roll on the third Friday; roll-date sampling (the last
    common day on or before each third Friday) is reported as a sensitivity, never a criterion. The final month is used
    only when complete (its last common day is the month's last trading day), so October 2026 (data to 10-14) is out.
    Rows flagged by ``cboe_strategy.annotate`` (suspect prints, rows on market-closed days) are left out.
  * Back-tested rows. Each index's values before its launch date (``INDEX_META``) are Cboe back-tests published at launch.
    ASSUMPTION, stated in every such reason: these claims describe the published index histories, not what a trader knew,
    so back-tested months are used. A verdict whose sample holds any is labelled BACK-TESTED INDEX VALUES (stat 'label')
    with the count, and the statistic on post-launch months alone (both constructions, with its min_n shortfall) is
    reported next to the main one.
  * Bills and Sharpe (rule 7). FRED DTB3 is a 91-day discount yield published the next day: on calendar day o the rate
    known is the print dated strictly before o, converted to r = -ln(1 - d/100 * 91/360) / (91/365), and each calendar
    day accrues at the rate known that day. Excess return = period return - bill growth over the same days. Sharpe =
    mean / sd (ddof 1) of monthly excess returns x sqrt(12). Funded strategies only (all of these are fully funded).
  * Intervals (rule 6). Sharpe differences: paired studentized circular block bootstrap (12-month blocks, the trials'
    stated length; 2000 resamples per seed, the mean of 5 seeds), the sample and every resample studentized by the same
    Bartlett-HAC s.e. (the Ledoit-Wolf delta-method gradient with a fixed Bartlett long-run variance, bandwidth = block):
    the "studentized CBB (Bartlett-HAC)". It is NOT the Ledoit-Wolf test. The index claims also run Ledoit & Wolf (2008)
    boot.time.inference (``lw_test``: prewhitened Parzen HAC s.e. on the sample, Goetze-Kuensch block s.e. in circular-block
    resamples, b = 12, symmetric 95% interval). Rule 11: where the trial names it as an alternative (T-162: "studentized
    block bootstrap ... (or Ledoit-Wolf test)") the full-sample criterion passes only when both constructions pass and is
    undecided when they disagree; elsewhere (T-163, T-164, T-170, T-172 name only a studentized block bootstrap) it is
    reported next to the criterion. Block lengths 6, 24 and 36 are reported sensitivities. "95% CI > 0" is the lower end of
    the two-sided 95% interval. The CAGR difference
    (T-202) is studentized the same way through its influence function. T-161's alpha uses the stationary block bootstrap
    the trial names (mean block 12 months, percentile CI) and reports the Newey-West (12 lags) t. "Same sign in both
    halves" means the half's point estimate has the claimed sign (the criterion row says so and shows the half CIs);
    walk-forward halves are equal-count halves unless the trial names the split (T-163: pre/post 2020).
  * One information set (rule 12). The index claims take no decision. The MODEL-PRICED engines choose the strike, price
    the option and fill on the entry-day close as the live proxy for all three (the bill rate is the last print known
    then); no gate is applied at a decision.
  * Below min_n (rule 5), never supported; a failing criterion counts only when decisive: its 95% interval lies wholly on
    the wrong side, or (T-174's window share) the failure would persist if every missing window went the claim's way.
  * MODEL-PRICED engines. SPX: ^GSPC raw closes (strikes, settlement at the expiry-session close as the SOQ proxy, house
    rule 8), the VIX close of the entry session (VIX closes at 16:15 ET, the index at 16:00: a declared 15-minute
    mismatch), the bill rate known then, and a continuous dividend yield q known at
    entry (SPY's trailing-12-month dividends over its close; before SPY's first full year an ASSUMED q = 3.0%, stated ex
    ante). The held index earns total return: SPX price plus dividends accrued every session at the yield q known at the
    prior close (the ASSUMED 3.0% until SPY's first full year, 1990-01..1994-01), as BXM and PUT accrue SPX constituent
    dividends day by day; SPY's quarterly ex-date lumps are not used for the index, because crediting a quarter's
    dividends on the March/June/September/December expiry session puts a timing error into the cycle returns the
    calibration gate compares. SPY (T-128): raw closes, $1 strikes, the escrowed-dividend forward
    S - PV(D) when a projected ex-date (SPY's quarterly third-Friday schedule) falls in (entry, expiry], D = the last
    dividend gone ex at or before entry; SPY buy-and-hold is total return (adjclose). Cycles follow the standard monthly
    expiry (third Friday, the prior session on a holiday): each option is written at one expiry's close and settles at the
    next (28 or 35 calendar days), rule 10(a). IV-scale sensitivities (0.90, 0.81; the captured SPX ATM IV / VIX ratio
    was about 0.79) are reported; only a scale the trial names is a criterion.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
-> at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.data.cboe_strategy import INDEX_META, trading_days
from mandel.experiments.underlying2 import _verdict
from mandel.options import bs
from mandel.validation.backtest_eval import _hac_var, kurtosis, probabilistic_sharpe_ratio, sharpe_ratio, skewness

PPY = 12                       # monthly periods per year
BLOCK = 12                     # bootstrap block, months (the trials' stated 12-month blocks)
N_BOOT = 2000
SEED = 0
TE_MAX = 0.02                  # calibration gate: tracking error < 2%/yr
SCALES = (0.90, 0.81)          # IV-scale sensitivities
PRE_YIELD = 0.03               # assumed S&P 500 dividend yield before SPY's trailing yield is computable (stated ex ante)
SPX_STEP = 5.0                 # SPX strike grid (points)
SPY_STEP = 1.0                 # SPY strike grid ($)
MP = "MODEL-PRICED"
GSPC_B = "daily-history--GSPC"
SPY_B = "daily-history-SPY"
VIX_B = "cboe-VIX-history"
SKEW_B = "cboe-SKEW-history"
DTB3_B = "fred-DTB3"
KAPPA_CHAIN = "options-chain-SPX-2026-10-14"


def cboe_b(sym: str) -> str:
    return f"cboe-{sym}-history"


# ================================================================================================= data access ==

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
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    cap = getattr(archive.get(name), "created_at", None)
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def cboe_index(archive, sym: str) -> dict:
    """{'close': {day: level}, 'backtest': {day: bool}, 'flagged': {day: why}} of ``cboe-<SYM>-history``. Flagged rows
    (suspect prints, rows on market-closed days) are kept out of 'close'."""
    def load():
        close, bt, fl = {}, {}, {}
        for r in _rows(archive, cboe_b(sym)):
            v = r["value"]
            d, c = v.get("day"), v.get("close")
            if d is None or c is None:
                continue
            if v.get("flag"):
                fl[d] = v["flag"]
                continue
            c = float(c)
            if c > 0 and math.isfinite(c):
                close[d], bt[d] = c, bool(v.get("backtest"))
        return {"close": close, "backtest": bt, "flagged": fl}
    return _cached(archive, ("cboe", sym), load)


def _daily(archive, name: str) -> tuple:
    """(days, raw close, adjclose) of a daily-history bundle; a bar without adjclose carries the previous adj/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = v.get("close")
            if c is None or not float(c) > 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float("nan"))
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, close, adj
    return _cached(archive, ("daily", name), load)


def _closes(archive, name: str) -> dict:
    """{day: value} of a cboe index (close) or FRED series (value) bundle."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = v.get("close", v.get("value"))
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("closes", name), load)


# ========================================================================================================= bills ==

def dtb3_cont(d_pct: float) -> float:
    """Continuous rate from a 91-day bill discount yield in percent (FRED DTB3)."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def _ord(d) -> int:
    return (date.fromisoformat(d) if isinstance(d, str) else d).toordinal()


class Bills:
    """FRED DTB3 as a continuous rate known on each calendar day (the print dated strictly before it: FRED publishes a day
    late), accrued calendar day by calendar day at the rate known that day."""

    def __init__(self, dtb3: dict):
        ks = sorted(dtb3)
        if not ks:
            raise ValueError("no DTB3 prints")
        self.p = np.array([_ord(k) for k in ks], np.int64)
        self.r = np.array([dtb3_cont(float(dtb3[k])) for k in ks], float)
        self.lo, self.hi = int(self.p[0]), int(self.p[-1]) + 1
        o = np.arange(self.lo, self.hi + 1)
        rate = self.r[np.maximum(np.searchsorted(self.p, o, side="left") - 1, 0)]
        self.cum = np.concatenate([[0.0], np.cumsum(rate / 365.0)])         # cum[k]: accrual from day lo to day lo + k

    def rate(self, d) -> float:
        j = int(np.searchsorted(self.p, _ord(d), side="left")) - 1
        return float(self.r[max(j, 0)])

    def _c(self, o: int) -> float:
        if o <= self.lo:
            return (o - self.lo) * float(self.r[0]) / 365.0
        if o > self.hi:
            return float(self.cum[self.hi - self.lo]) + (o - self.hi) * float(self.r[-1]) / 365.0
        return float(self.cum[o - self.lo])

    def growth(self, d0, d1) -> float:
        """Bill growth factor from day d0 to day d1."""
        return math.exp(self._c(_ord(d1)) - self._c(_ord(d0)))


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_closes(archive, DTB3_B)))


# ============================================================================================= monthly panels ==

def _last_trading_day(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).isoformat()
    td = trading_days(f"{month}-01", last)
    return td[-1] if td else last


def common_days(levels: dict, start: str = "", end: str = "9999-12-31") -> list:
    keys = None
    for v in levels.values():
        keys = set(v) if keys is None else keys & set(v)
    return sorted(d for d in (keys or ()) if start <= d <= end)


def month_end_days(levels: dict, start: str = "", end: str = "9999-12-31") -> list:
    """The last common day of each calendar month; the final month only when complete."""
    last = {}
    for d in common_days(levels, start, end):
        last[d[:7]] = d
    days = [last[m] for m in sorted(last)]
    if days and days[-1] < _last_trading_day(days[-1][:7]):
        days = days[:-1]
    return days


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7 + 14)


def roll_days(levels: dict, start: str = "", end: str = "9999-12-31") -> list:
    """Roll-date sampling: the last common day on or before each month's third Friday, within 3 calendar days."""
    cd = common_days(levels, start, end)
    if not cd:
        return []
    out, y, m = [], int(cd[0][:4]), int(cd[0][5:7])
    last = date.fromisoformat(cd[-1])
    while date(y, m, 1) <= last:
        tf = third_friday(y, m)
        j = bisect.bisect_right(cd, tf.isoformat()) - 1
        if j >= 0 and (tf - date.fromisoformat(cd[j])).days <= 3 and cd[j][:7] == tf.isoformat()[:7]:
            out.append(cd[j])
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def panel(levels: dict, bills: Bills, days: Sequence[str]) -> dict:
    """Returns between consecutive sample days: 'ret'[name], 'bill', 'ex'[name] (excess over the bill), 'months' (the
    month of each period's end day), 'days' (the sample days)."""
    days = list(days)
    a, b = days[:-1], days[1:]
    bill = np.array([bills.growth(x, y) - 1.0 for x, y in zip(a, b)], float)
    ret = {k: np.array([v[y] / v[x] - 1.0 for x, y in zip(a, b)], float) for k, v in levels.items()}
    return {"days": days, "start": a, "end": b, "months": [d[:7] for d in b], "bill": bill, "ret": ret,
            "ex": {k: r - bill for k, r in ret.items()}, "n": len(b)}


def monthly_panel(levels: dict, bills: Bills, start: str = "", end: str = "9999-12-31") -> dict:
    return panel(levels, bills, month_end_days(levels, start, end))


# ================================================================================================== statistics ==

def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def _stationary_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (circular), geometric block lengths with mean ``mean_block``."""
    p = 1.0 / max(float(mean_block), 1.0)
    idx = np.empty((k, n), np.int64)
    idx[:, 0] = rng.integers(0, n, k)
    for t in range(1, n):
        new = rng.random(k) < p
        idx[:, t] = np.where(new, rng.integers(0, n, k), (idx[:, t - 1] + 1) % n)
    return idx


def _chunks(n_boot: int, n: int):
    k = max(1, min(n_boot, 1_000_000 // max(n, 1)))
    done = 0
    while done < n_boot:
        m = min(k, n_boot - done)
        yield m
        done += m


def _stud(stat: Callable, cols: Sequence[np.ndarray], block: int, n_boot: Optional[int] = None, seed: int = SEED,
          level: float = 0.95) -> dict:
    """Studentized (bootstrap-t) circular block bootstrap of a statistic of paired columns. ``stat`` maps row-wise
    resamples (k, n) of each column to (estimate, s.e.) arrays of length k. Returns est, se, two-sided ``level`` CI,
    p (one-sided, H0: est <= 0) and p_lt (H0: est >= 0)."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    cols = [np.asarray(c, float) for c in cols]
    n = cols[0].size
    out = {"est": None, "se": None, "ci": [None, None], "p": None, "p_lt": None, "block": None, "n": int(n)}
    if n < 8:
        return out
    bl = max(1, min(int(block), n // 4))
    d0, se0 = stat(*[c[None, :] for c in cols], bl)
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(est=d0, se=se0, block=bl)
    if not se0 > 1e-14:
        out.update(ci=[d0, d0], p=0.0 if d0 > 0 else 1.0, p_lt=0.0 if d0 < 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts, ds = [], []
    for k in _chunks(n_boot, len(cols) * n):
        idx = _boot_idx(rng, n, bl, k)
        d, se = stat(*[c[idx] for c in cols], bl)
        ok = se > 1e-14
        ts.append((d[ok] - d0) / se[ok])
        ds.append(d)
    t, dd = np.concatenate(ts), np.concatenate(ds)
    a = (1.0 - level) / 2.0
    t_obs = d0 / se0
    out.update(ci=[d0 - float(np.quantile(t, 1 - a)) * se0, d0 - float(np.quantile(t, a)) * se0],
               ci_pct=[float(np.quantile(dd, a)), float(np.quantile(dd, 1 - a))],
               p=float((np.sum(t >= t_obs) + 1) / (t.size + 1)), p_lt=float((np.sum(t <= t_obs) + 1) / (t.size + 1)))
    return out


def mc_reps(fn: Callable, reps: Optional[int] = None, seed: int = SEED, keys: Sequence[str] = ("ci", "ci_pct"), **kw) -> dict:
    """``fn(seed=...)`` repeated over ``reps`` bootstrap seeds: interval ends and p-values are the replicate means, with
    their Monte Carlo s.e. (replicate sd / sqrt(reps)) under '<key>_mc_se', so a decision does not hinge on one seed."""
    reps = REPS if reps is None else reps
    rs = [fn(seed=seed + k, **kw) for k in range(max(1, int(reps)))]
    out = dict(rs[0])
    r_ = len(rs)
    for key in keys:
        if key not in out:
            continue
        arr = np.array([[np.nan if v is None else v for v in r[key]] for r in rs], float)
        if np.isfinite(arr).all():
            out[key] = [float(v) for v in arr.mean(axis=0)]
            out[key + "_mc_se"] = [float(v) for v in (arr.std(axis=0, ddof=1) / math.sqrt(r_) if r_ > 1 else np.zeros(arr.shape[1]))]
    for key in ("p", "p_lt"):
        vals = [r.get(key) for r in rs]
        if all(v is not None for v in vals):
            out[key] = float(np.mean(vals))
            out[key + "_mc_se"] = float(np.std(vals, ddof=1) / math.sqrt(r_)) if r_ > 1 else 0.0
    out["reps"] = r_
    return out


def resolve(value: Optional[float], mc_se: Optional[float], thr: float, side: str, k: float = 2.0) -> tuple:
    """Is ``value`` above (side 'gt') or below ('lt') ``thr`` beyond k Monte Carlo s.e.? (True / False / None = the Monte
    Carlo error cannot resolve it) and a note for the reason."""
    if value is None:
        return None, " [not available]"
    e = k * (mc_se or 0.0)
    above, below = value - e > thr, value + e < thr
    if side == "lt":
        above, below = below, above
    if above:
        return True, ""
    if below:
        return False, ""
    return None, f" [within {k:g} Monte Carlo s.e. ({mc_se:.4f}) of {thr:g}: unresolved]"


def _sr_diff_stat(A, B, bw):
    """Row-wise per-period Sharpe(A) - Sharpe(B) (population moments) and its s.e. from the Ledoit-Wolf delta-method
    gradient with a FIXED-bandwidth Bartlett long-run variance (bandwidth ``bw``), on the sample and in every resample.
    This is the Bartlett-HAC studentizer of the house CBB, not Ledoit-Wolf's (2008) test: see ``lw_test``."""
    n = A.shape[1]
    ma, mb = A.mean(axis=1), B.mean(axis=1)
    ga, gb = (A * A).mean(axis=1), (B * B).mean(axis=1)
    va, vb = np.maximum(ga - ma ** 2, 1e-300), np.maximum(gb - mb ** 2, 1e-300)
    d = ma / np.sqrt(va) - mb / np.sqrt(vb)
    z = ((ga / va ** 1.5)[:, None] * (A - ma[:, None]) - (ma / (2 * va ** 1.5))[:, None] * (A * A - ga[:, None])
         - (gb / vb ** 1.5)[:, None] * (B - mb[:, None]) + (mb / (2 * vb ** 1.5))[:, None] * (B * B - gb[:, None]))
    return d, np.sqrt(_hac_var(z, bw) / n)


def sharpe_diff_test(a, b, ppy: int = PPY, block: int = BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Annualised Sharpe(a) - Sharpe(b) (ddof 1, as ``sharpe_ratio``) with a paired studentized circular block bootstrap:
    diff, se, two-sided 95% CI, p (H0: diff <= 0), p_lt (H0: diff >= 0)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = a.size
    out = {"n": int(n), "sharpe_a": float(sharpe_ratio(a, ppy)) if n > 1 else None,
           "sharpe_b": float(sharpe_ratio(b, ppy)) if n > 1 else None, "diff": None, "se": None, "ci": [None, None],
           "p": None, "p_lt": None, "block": None}
    if n > 1:
        out["diff"] = out["sharpe_a"] - out["sharpe_b"]
    if n < 8 or b.size != n:
        return out
    c = math.sqrt(ppy) * math.sqrt((n - 1) / n)          # population-moment per-period Sharpe -> ddof-1 annualised
    r = _stud(_sr_diff_stat, [a, b], block, n_boot, seed)
    sc = lambda v: [None if x is None else x * c for x in v]
    out.update(diff=r["est"] * c, se=r["se"] * c, ci=sc(r["ci"]), ci_pct=sc(r.get("ci_pct", [None, None])), p=r["p"],
               p_lt=r["p_lt"], block=r["block"])
    return out


# ---------------------------------------------------------------------------- Ledoit-Wolf (2008) Sharpe test ----
# A port of Ledoit & Wolf (2008), "Robust performance hypothesis testing with the Sharpe ratio", J. Empirical Finance
# 15, 850-859, and its R code (compute.se.Parzen.pw, boot.time.inference, cbb.sequence). The sample s.e. is a
# prewhitened HAC: VAR(1) on the four moment deviations, its singular values capped at +-0.97, a Parzen kernel at the
# Andrews (1991) automatic bandwidth S* = 2.6614 (alpha T)^0.2 on the whitened residuals, recoloured by (I - A)^-1. Each
# circular-block resample (block b) is studentized by the Goetze-Kuensch block s.e.: the mean of (sqrt(b) x block mean
# of the influence)^2 over the floor(T/b) whole blocks. p (two-sided, H0: Delta = 0) = (1 + #{|D* - D| / se* >= |D| /
# se}) / (M + 1); the 95% interval is the symmetric studentized one, D +- q95(|D* - D| / se*) x se.

def _parzen(x: float) -> float:
    x = abs(x)
    if x <= 0.5:
        return 1.0 - 6.0 * x * x + 6.0 * x ** 3
    if x <= 1.0:
        return 2.0 * (1.0 - x) ** 3
    return 0.0


def _lw_moments(a: np.ndarray, b: np.ndarray) -> tuple:
    """(gradient of SR_a - SR_b in (mu_a, mu_b, gamma_a, gamma_b), the T x 4 moment deviations V)."""
    m1, m2 = a.mean(), b.mean()
    g1, g2 = (a * a).mean(), (b * b).mean()
    v1, v2 = max(g1 - m1 * m1, 1e-300), max(g2 - m2 * m2, 1e-300)
    grad = np.array([g1 / v1 ** 1.5, -g2 / v2 ** 1.5, -0.5 * m1 / v1 ** 1.5, 0.5 * m2 / v2 ** 1.5])
    return grad, np.column_stack([a - m1, b - m2, a * a - g1, b * b - g2])


def _lw_alpha(V: np.ndarray) -> float:
    """Andrews' alpha(2) from a univariate AR(1) (OLS with intercept on the demeaned column, as R's ar.ols) per column."""
    num = den = 0.0
    for i in range(V.shape[1]):
        x = V[:, i] - V[:, i].mean()
        X = np.column_stack([np.ones(x.size - 1), x[:-1]])
        coef = np.linalg.lstsq(X, x[1:], rcond=None)[0]
        rho = float(np.clip(coef[1], -0.99, 0.99))
        s2 = float(np.mean((x[1:] - X @ coef) ** 2))
        num += 4.0 * rho * rho * s2 * s2 / (1.0 - rho) ** 8
        den += s2 * s2 / (1.0 - rho) ** 4
    return num / den if den > 0 else 0.0


def _lw_psi(V: np.ndarray) -> tuple:
    """Parzen-kernel long-run covariance at the automatic bandwidth, with the T / (T - 4) small-sample factor."""
    T = V.shape[0]
    S = 2.6614 * (_lw_alpha(V) * T) ** 0.2
    psi = V.T @ V / T
    j = 1
    while j < S and j < T:
        G = V[j:].T @ V[:-j] / T
        psi = psi + _parzen(j / S) * (G + G.T)
        j += 1
    return psi * T / (T - 4), S


def lw_se(a, b) -> dict:
    """Ledoit-Wolf prewhitened Parzen HAC s.e. of the per-period Sharpe difference (compute.se.Parzen.pw)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    grad, V = _lw_moments(a, b)
    T = V.shape[0]
    X, Y = V[:-1], V[1:]
    A = np.linalg.lstsq(X, Y, rcond=None)[0].T
    U, sv, Vt = np.linalg.svd(A)
    Ah = U @ np.diag(np.clip(sv, -0.97, 0.97)) @ Vt
    D = np.linalg.inv(np.eye(4) - Ah)
    psi, S = _lw_psi(Y - X @ Ah.T)
    psi = D @ psi @ D.T
    return {"se": math.sqrt(max(float(grad @ psi @ grad), 0.0) / T), "bandwidth": float(S),
            "singular_values": [float(x) for x in sv]}


def lw_test(a, b, ppy: int = PPY, block: int = BLOCK, n_boot: Optional[int] = None, seed: int = SEED,
            level: float = 0.95) -> dict:
    """Ledoit-Wolf (2008) boot.time.inference of Sharpe(a) - Sharpe(b) (ddof-1 Sharpe ratios), annualised x sqrt(ppy):
    diff, se (prewhitened Parzen HAC), the symmetric studentized ``level`` CI, two-sided bootstrap p, and the plain HAC
    test (normal p and CI on the same s.e.) under 'hac'."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    a, b = np.asarray(a, float), np.asarray(b, float)
    T = a.size
    out = {"n": int(T), "diff": None, "se": None, "ci": [None, None], "p": None, "block": None, "bandwidth": None,
           "hac": None, "method": "Ledoit-Wolf (2008) boot.time.inference"}
    if T < 8 or b.size != T:
        return out
    bl = max(1, min(int(block), T // 4))
    l = T // bl
    c = math.sqrt(ppy)
    d0 = float(a.mean() / a.std(ddof=1) - b.mean() / b.std(ddof=1))
    s = lw_se(a, b)
    se0 = s["se"]
    z = NormalDist().inv_cdf(0.5 + level / 2.0)
    out.update(diff=d0 * c, se=se0 * c, block=bl, bandwidth=s["bandwidth"])
    if not se0 > 1e-14:
        out.update(ci=[d0 * c, d0 * c], p=0.0 if d0 != 0 else 1.0)
        return out
    out["hac"] = {"se": se0 * c, "z": d0 / se0, "p": math.erfc(abs(d0 / se0) / math.sqrt(2.0)),
                  "ci": [(d0 - z * se0) * c, (d0 + z * se0) * c]}
    d_obs = abs(d0) / se0
    rng = np.random.default_rng(seed)
    ds = []
    for k in _chunks(n_boot, 2 * T):
        idx = _boot_idx(rng, T, bl, k)                # cbb.sequence: ceil(T/b) circular blocks, cut to T
        A, B = a[idx], b[idx]
        ma, mb = A.mean(axis=1), B.mean(axis=1)
        ga, gb = (A * A).mean(axis=1), (B * B).mean(axis=1)
        va, vb = np.maximum(ga - ma ** 2, 1e-300), np.maximum(gb - mb ** 2, 1e-300)
        dd = ma / A.std(axis=1, ddof=1) - mb / B.std(axis=1, ddof=1)
        infl = ((ga / va ** 1.5)[:, None] * (A - ma[:, None]) - (gb / vb ** 1.5)[:, None] * (B - mb[:, None])
                - (0.5 * ma / va ** 1.5)[:, None] * (A * A - ga[:, None]) + (0.5 * mb / vb ** 1.5)[:, None] * (B * B - gb[:, None]))
        zeta = infl[:, :l * bl].reshape(k, l, bl).mean(axis=2) * math.sqrt(bl)     # g' zeta_j over the l whole blocks
        se = np.sqrt((zeta ** 2).mean(axis=1) / T)
        ok = se > 1e-14
        ds.append(np.abs(dd[ok] - d0) / se[ok])
    dstar = np.concatenate(ds)
    q = float(np.quantile(dstar, level))
    out.update(ci=[(d0 - q * se0) * c, (d0 + q * se0) * c], p=float((np.sum(dstar >= d_obs) + 1) / (dstar.size + 1)),
               q=q)
    return out



def _cagr_diff_stat_factory(ppy: int):
    def stat(LA, LB, bw):
        n = LA.shape[1]
        ma, mb = LA.mean(axis=1), LB.mean(axis=1)
        ea, eb = np.exp(ppy * ma), np.exp(ppy * mb)
        z = ppy * ea[:, None] * (LA - ma[:, None]) - ppy * eb[:, None] * (LB - mb[:, None])
        return ea - eb, np.sqrt(_hac_var(z, bw) / n)
    return stat


def _mean_stat(X, bw):
    n = X.shape[1]
    return X.mean(axis=1), np.sqrt(_hac_var(X, bw) / n)


def cagr_diff_test(a, b, ppy: int = PPY, block: int = BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """CAGR(a) - CAGR(b) of periodic simple returns (CAGR = exp(ppy x mean log(1 + r)) - 1), studentized through its
    influence function; also the arithmetic annualised difference ppy x mean(a - b) with its studentized CI."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    la, lb = np.log1p(a), np.log1p(b)
    r = _stud(_cagr_diff_stat_factory(ppy), [la, lb], block, n_boot, seed)
    m = _stud(_mean_stat, [ppy * (a - b)], block, n_boot, seed)
    cg = lambda l: float(math.exp(ppy * l.mean()) - 1) if l.size else None
    return {"n": int(a.size), "cagr_a": cg(la), "cagr_b": cg(lb), "diff": r["est"], "se": r["se"], "ci": r["ci"],
            "ci_pct": r.get("ci_pct", [None, None]), "p": r["p"], "p_lt": r["p_lt"], "block": r["block"], "arith_diff": m["est"],
            "arith_ci": m["ci"]}


def ols_hac(y, x, lag: int = 12) -> dict:
    """OLS y = alpha + beta x with Newey-West (Bartlett, ``lag`` lags) standard errors."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size
    X = np.column_stack([np.ones(n), x])
    XtXi = np.linalg.inv(X.T @ X)
    coef = XtXi @ X.T @ y
    e = y - X @ coef
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        w = 1.0 - l / (lag + 1.0)
        G = u[l:].T @ u[:-l]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    return {"alpha": float(coef[0]), "beta": float(coef[1]), "se_alpha": float(se[0]), "se_beta": float(se[1]),
            "resid_sd": float(e.std(ddof=2)) if n > 2 else None}


def alpha_test(y, x, ppy: int = PPY, mean_block: float = BLOCK, n_boot: Optional[int] = None, seed: int = SEED, lag: int = 12,
               level: float = 0.95) -> dict:
    """Jensen alpha of y on x: annualised intercept (ppy x alpha), beta, Newey-West t, and the stationary-bootstrap
    (mean block ``mean_block``) percentile CI of the annualised alpha and of beta."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size
    out = {"n": int(n), "alpha_ann": None, "beta": None, "t_hac": None, "ci": [None, None], "beta_ci": [None, None]}
    if n < 8:
        return out
    o = ols_hac(y, x, lag)
    out.update(alpha_ann=ppy * o["alpha"], beta=o["beta"], se_ann=ppy * o["se_alpha"],
               t_hac=o["alpha"] / o["se_alpha"] if o["se_alpha"] > 0 else None)
    rng = np.random.default_rng(seed)
    al, be = [], []
    for k in _chunks(n_boot, 2 * n):
        idx = _stationary_idx(rng, n, mean_block, k)
        Y, X = y[idx], x[idx]
        xm, ym = X.mean(axis=1), Y.mean(axis=1)
        vx = ((X - xm[:, None]) ** 2).sum(axis=1)
        b = np.where(vx > 0, ((X - xm[:, None]) * (Y - ym[:, None])).sum(axis=1) / np.maximum(vx, 1e-300), 0.0)
        al.append(ppy * (ym - b * xm))
        be.append(b)
    al, be = np.concatenate(al), np.concatenate(be)
    q = (1 - level) / 2
    out.update(ci=[float(np.quantile(al, q)), float(np.quantile(al, 1 - q))],
               beta_ci=[float(np.quantile(be, q)), float(np.quantile(be, 1 - q))])
    return out


def max_drawdown(r) -> float:
    c = np.cumprod(1.0 + np.asarray(r, float))
    c = np.concatenate([[1.0], c])
    return float((c / np.maximum.accumulate(c) - 1.0).min())


def cagr(r, ppy: int = PPY) -> Optional[float]:
    r = np.asarray(r, float)
    return float(math.exp(ppy * np.log1p(r).mean()) - 1.0) if r.size else None


def psr(x, bench_sr_per_period: float = 0.0) -> Optional[float]:
    x = np.asarray(x, float)
    if x.size < 4:
        return None
    return float(probabilistic_sharpe_ratio(float(sharpe_ratio(x)), bench_sr_per_period, x.size, skewness(x), kurtosis(x)))


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


# ================================================================================================= formatting ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _pu(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _sd_txt(t: dict, nd: int = 3) -> str:
    return f"{_s(t.get('diff'), nd)} ({_ci(t.get('ci'), nd)})"


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


# ===================================================================================================== judges ==

def _parts(labels: Sequence[str], split: Optional[str]) -> tuple:
    """(index arrays, names) of the two walk-forward parts: equal-count halves, or labels < split / >= split."""
    n = len(labels)
    if split:
        i1 = np.array([k for k, m in enumerate(labels) if m < split], int)
        i2 = np.array([k for k, m in enumerate(labels) if m >= split], int)
        return (i1, i2), (f"pre-{split[:4]}", f"{split[:4]}-")
    h = n // 2
    i1, i2 = np.arange(h), np.arange(h, n)
    nm = lambda ii: f"{labels[ii[0]]}..{labels[ii[-1]]}" if ii.size else "empty"
    return (i1, i2), (f"first half {nm(i1)}", f"second half {nm(i2)}")


REPS = 5                       # bootstrap replicates (seeds) behind every decisive interval end or p-value
REPS_MAX = 25                  # replicates when 5 cannot resolve a bound against its threshold


def mc_escalate(fn: Callable, check: Callable, reps: Optional[int] = None, seed: int = SEED, keys: Sequence[str] = ("ci", "ci_pct")) -> dict:
    """``mc_reps`` with ``reps`` seeds; when ``check`` (the resolved criterion, None = unresolved) cannot decide, again
    with REPS_MAX seeds."""
    reps = REPS if reps is None else reps
    t = mc_reps(fn, reps, seed, keys)
    if check(t) is None and REPS_MAX > reps:
        t = mc_reps(fn, REPS_MAX, seed, keys)
    return t


def _ci_crit(t: dict, side: str, thr: float, label: str, fmt: Callable = None) -> tuple:
    """A criterion on an interval end resolved against Monte Carlo error. side 'gt': the lower end must exceed ``thr``
    (decisive failure: the upper end below it); 'lt': the upper end must lie below ``thr`` (decisive: the lower end above).
    Returns (name, ok, decisive)."""
    fmt = fmt or (lambda v: _s(v))
    lo, hi = t.get("ci") or (None, None)
    se_lo, se_hi = t.get("ci_mc_se") or (0.0, 0.0)
    if side == "gt":
        ok, note = resolve(lo, se_lo, thr, "gt")
        dec = hi is not None and resolve(hi, se_hi, thr, "lt")[0] is True
        return f"{label} (lower {fmt(lo)}){note}", ok, dec
    ok, note = resolve(hi, se_hi, thr, "lt")
    dec = lo is not None and resolve(lo, se_lo, thr, "gt")[0] is True
    return f"{label} (upper {fmt(hi)}){note}", ok, dec


def all_constructions(rows: Sequence[tuple], label: str) -> tuple:
    """Rule 11: one criterion judged under every construction the trial names (rows = (name, ok, decisive) each). It
    passes only when every construction passes and fails only when every one fails (decisively only when every failure is
    decisive); when they disagree, or one is unresolved, it is undecided (None), never taken from the one that passes."""
    oks = [r[1] for r in rows]
    if all(o is True for o in oks):
        ok = True
    elif all(o is False for o in oks):
        ok = False
    else:
        ok = None
    dec = ok is False and all(bool(r[2]) for r in rows)
    note = ""
    if ok is None:
        note = (" [the named constructions disagree: undecided under rule 11]" if (True in oks and False in oks)
                else " [not every named construction resolves: undecided under rule 11]")
    return f"{label}: " + "; ".join(r[0] for r in rows) + note, ok, dec


LW_NAME = "Ledoit-Wolf (2008) test"
CBB_NAME = "studentized CBB (Bartlett-HAC)"


def judge_sharpe(xa, xb, labels: Sequence[str], min_n: int, names: tuple = ("A", "B"), split: Optional[str] = None,
                 unit: str = "months", block: int = BLOCK, n_boot: Optional[int] = None, seed: int = SEED, reps: Optional[int] = None,
                 lw: Optional[str] = None) -> dict:
    """Pass: the full-sample 95% CI of Sharpe(A) - Sharpe(B) lies above 0 (its lower end resolved beyond 2 Monte Carlo
    s.e. over ``reps`` seeds) AND the point-estimate difference is positive in both walk-forward parts. Decisive failures
    (rule 5): the full CI wholly below 0; a part's CI wholly below 0.

    ``lw``: None, 'report' (the Ledoit-Wolf (2008) test is run on the full sample and reported, not a criterion: the trial
    names only a studentized block bootstrap) or 'criterion' (the trial names the LW test as an alternative: rule 11, the
    full-sample criterion must pass under both constructions, and a part fails decisively only when both CIs are wholly
    below 0)."""
    xa, xb = np.asarray(xa, float), np.asarray(xb, float)
    n = xa.size
    full = mc_escalate(lambda seed: sharpe_diff_test(xa, xb, PPY, block, n_boot, seed),
                       lambda t: _ci_crit(t, "gt", 0.0, "")[1], reps, seed)
    lwf = None
    if lw:
        lwf = mc_escalate(lambda seed: lw_test(xa, xb, PPY, block, n_boot, seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1],
                          reps, seed, keys=("ci",))
    (i1, i2), pn = _parts(labels, split)
    halves = [sharpe_diff_test(xa[ii], xb[ii], PPY, block, n_boot, seed) for ii in (i1, i2)]
    lw_halves = [lw_test(xa[ii], xb[ii], PPY, block, n_boot, seed) for ii in (i1, i2)] if lw == "criterion" else None
    A, B = names
    label = f"full-sample 95% CI of Sharpe({A}) - Sharpe({B}) > 0"
    if lw == "criterion":
        crit = [all_constructions([_ci_crit(full, "gt", 0.0, CBB_NAME), _ci_crit(lwf, "gt", 0.0, LW_NAME + " (symmetric)")],
                                  label + " under both constructions the trial names (rule 11)")]
    else:
        crit = [_ci_crit(full, "gt", 0.0, label + f" ({CBB_NAME})")]
    for k, (nm, h, ii) in enumerate(zip(pn, halves, (i1, i2))):
        d = h["diff"]
        dec = h["ci"][1] is not None and h["ci"][1] < 0
        cis = f"{CBB_NAME} {_ci(h['ci'])}"
        if lw_halves is not None:
            hl = lw_halves[k]
            dec = dec and hl["ci"][1] is not None and hl["ci"][1] < 0
            cis += f"; {LW_NAME} {_ci(hl['ci'])}"
        crit.append((f"{nm} ({ii.size} {unit}): point-estimate difference > 0 ({_s(d)}; judged on the point estimate, "
                     f"{cis})", None if d is None else d > 0, dec))
    v, why = _decide(crit, n, min_n, unit)
    return {"n": int(n), "full": full, "lw": lwf, "lw_mode": lw, "halves": halves, "lw_halves": lw_halves,
            "part_names": list(pn), "part_n": [int(i1.size), int(i2.size)],
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def judge_alpha(y, x, labels: Sequence[str], min_n: int, unit: str = "months", n_boot: Optional[int] = None, seed: int = SEED,
                reps: Optional[int] = None) -> dict:
    """T-161 pass: the stationary-bootstrap 95% CI of the annualised alpha lies above 0, and the alpha point estimate is
    positive in both halves. Decisive failures: the full CI wholly below 0; a half's CI wholly below 0."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size
    full = mc_escalate(lambda seed: alpha_test(y, x, n_boot=n_boot, seed=seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1],
                       reps, seed, keys=("ci", "beta_ci"))
    (i1, i2), pn = _parts(labels, None)
    halves = [alpha_test(y[ii], x[ii], n_boot=n_boot, seed=seed) for ii in (i1, i2)]
    crit = [_ci_crit(full, "gt", 0.0, "stationary-bootstrap 95% CI of annualised alpha > 0", lambda v: _pc(v))]
    for nm, h in zip(pn, halves):
        a = h["alpha_ann"]
        crit.append((f"{nm}: alpha > 0 ({_pc(a)}/yr)", None if a is None else a > 0, h["ci"][1] is not None and h["ci"][1] < 0))
    v, why = _decide(crit, n, min_n, unit)
    return {"n": int(n), "full": full, "halves": halves, "part_names": list(pn),
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def judge_band(ra, rb, min_n: int, lo_band: float = 0.0, hi_band: float = 0.015, unit: str = "months",
               n_boot: Optional[int] = None, seed: int = SEED, reps: Optional[int] = None) -> dict:
    """T-202 pass: the 95% CI of CAGR(A) - CAGR(B) lies inside (lo_band, hi_band). Decisive failures: the CI wholly at
    or below lo_band (lower end), wholly at or above hi_band (upper end)."""
    chk = lambda t: (None if None in (_ci_crit(t, "gt", lo_band, "")[1], _ci_crit(t, "lt", hi_band, "")[1])
                     else True)
    t = mc_escalate(lambda seed: cagr_diff_test(ra, rb, PPY, BLOCK, n_boot, seed), chk, reps, seed,
                    keys=("ci", "ci_pct", "arith_ci"))
    pp = lambda v: "n/a" if v is None else f"{v * 100:+.2f} pp"
    crit = [_ci_crit(t, "gt", lo_band, f"95% CI lower end > {lo_band * 100:.1f} pp/yr", pp),
            _ci_crit(t, "lt", hi_band, f"95% CI upper end < {hi_band * 100:.1f} pp/yr", pp)]
    v, why = _decide(crit, t["n"], min_n, unit)
    return {"n": t["n"], "test": t, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def judge_putwrite(runs: dict, min_n: int, unit: str = "monthly cycles", n_boot: Optional[int] = None, seed: int = SEED,
                   reps: Optional[int] = None) -> dict:
    """T-128 pass: p < 0.05 (H0: Sharpe(putwrite) <= Sharpe(SPY)) at IV scale 1.0 and 0.9, in the full sample and in both
    walk-forward halves. ``runs`` = {scale: (x_putwrite, x_spy)} (excess returns per cycle). p-values are means over
    ``reps`` seeds, resolved against 0.05 beyond 2 Monte Carlo s.e. Decisive failure: the difference significantly
    NEGATIVE at 5% (p_lt < 0.05)."""
    crit, res = [], {}
    n = int(np.asarray(runs[1.0][0]).size)
    for sc in (1.0, 0.9):
        xp, xs = (np.asarray(v, float) for v in runs[sc])
        h = xp.size // 2
        tests = [mc_escalate(lambda seed, sl=sl: sharpe_diff_test(xp[sl], xs[sl], PPY, BLOCK, n_boot, seed),
                             lambda t: resolve(t["p"], t.get("p_mc_se"), 0.05, "lt")[0], reps, seed)
                 for sl in (slice(0, xp.size), slice(0, h), slice(h, None))]
        res[f"{sc:.2f}"] = {"full": tests[0], "halves": tests[1:]}
        for nm, t in zip(("full sample", "first half", "second half"), tests):
            ok, note = resolve(t["p"], t.get("p_mc_se"), 0.05, "lt")
            crit.append((f"IV x{sc:.2f} {nm}: p < 0.05 (diff {_s(t['diff'])}, p={_f(t['p'])}){note}", ok,
                         t["p_lt"] is not None and t["p_lt"] < 0.05))
    v, why = _decide(crit, n, min_n, unit)
    return {"n": n, "by_scale": res, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def judge_gate_and_sharpe(xa, xb, gate_ok: Optional[bool], gate_name: str, min_n: int, side: str = "lt",
                          halves: bool = False, unit: str = "monthly cycles", n_boot: Optional[int] = None, seed: int = SEED,
                          reps: Optional[int] = None) -> dict:
    """Calibration gate AND a Sharpe-difference CI. side 'lt' (T-171): the full 95% CI lies below 0. side 'gt' with
    ``halves`` (T-527): each half's 95% CI lies above 0. The gate is a deterministic check of the pricer: its failure is
    decisive at any n."""
    xa, xb = np.asarray(xa, float), np.asarray(xb, float)
    n = xa.size
    def test(sl, sd):
        return mc_escalate(lambda seed: sharpe_diff_test(xa[sl], xb[sl], PPY, BLOCK, n_boot, seed),
                           lambda t: _ci_crit(t, sd, 0.0, "")[1], reps, seed)
    full = test(slice(0, n), "lt" if side == "lt" else "gt")
    crit = [(gate_name, gate_ok, True)]
    hv = []
    if side == "lt":
        crit.append(_ci_crit(full, "lt", 0.0, "95% CI of the Sharpe difference < 0"))
    else:
        h = n // 2
        parts = (("first half", slice(0, h)), ("second half", slice(h, None))) if halves else (("full sample", slice(0, n)),)
        for nm, sl in parts:
            t = test(sl, "gt")
            hv.append(t)
            crit.append(_ci_crit(t, "gt", 0.0, f"{nm}: 95% CI of the Sharpe difference > 0"))
    v, why = _decide(crit, n, min_n, unit)
    return {"n": int(n), "full": full, "halves": hv, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def window_log_growth(r, window: int) -> np.ndarray:
    lg = np.log(np.maximum(1.0 + np.asarray(r, float), 1e-12))
    c = np.concatenate([[0.0], np.cumsum(lg)])
    return c[window:] - c[:-window] if lg.size >= window else np.zeros(0)


def judge_window_share(r, gate_ok: Optional[bool], gate_name: str, min_n: int, window: int = 120, thr: float = 0.9,
                       unit: str = "rolling 120-month windows") -> dict:
    """T-174: share of rolling ``window``-cycle windows whose compound growth is below 1 (CAGR < 0) >= ``thr``, after
    the calibration gate. Below min_n the share fails decisively only when it would still fail if every missing window
    were negative."""
    w = window_log_growth(r, window)
    n = int(w.size)
    neg = int(np.sum(w < 0))
    share = neg / n if n else None
    worst_case = (neg + max(min_n - n, 0)) / max(n, min_n, 1)
    crit = [(gate_name, gate_ok, True),
            (f"share of {window}-month windows with CAGR < 0 >= {thr:.2f} ({neg} of {n} = {_f(share)})",
             None if share is None else share >= thr, worst_case < thr)]
    v, why = _decide(crit, n, min_n, unit)
    return {"n": n, "negative": neg, "share": share, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why,
            "window_cagr_range": [float(math.exp(w.min() * 12 / window) - 1), float(math.exp(w.max() * 12 / window) - 1)] if n else None}


def calibration_gate(pairs: dict, te_max: float = TE_MAX, ppy: int = PPY) -> dict:
    """``pairs`` = {index: (model monthly returns, actual monthly returns)} on identical cycles. Tracking error = sd (ddof
    1) of the monthly difference x sqrt(ppy); passes when below ``te_max`` for every index (and >= 24 cycles each)."""
    out, ok_all = {}, True
    for nm, (m, a) in pairs.items():
        m, a = np.asarray(m, float), np.asarray(a, float)
        d = m - a
        n = int(d.size)
        te = float(d.std(ddof=1) * math.sqrt(ppy)) if n > 1 else None
        ok = bool(n >= 24 and te is not None and te < te_max)
        big = np.argsort(-np.abs(d))[:3] if n else []
        out[nm] = {"n": n, "te": te, "bias_ann": float(d.mean() * ppy) if n else None,
                   "corr": float(np.corrcoef(m, a)[0, 1]) if n > 2 else None, "ok": ok, "largest_abs_diff_idx": [int(i) for i in big]}
        ok_all = ok_all and ok
    return {"indices": out, "ok": bool(ok_all and out), "te_max": te_max}


def _gate_txt(g: dict) -> str:
    """The gate's numbers (the claim's pricer at IV x1.00, closes, no costs, against the indices' roll-to-roll returns)."""
    parts = []
    for nm, v in g["indices"].items():
        big = ", ".join(f"{x['cycle_end']} {_pc(x['model_minus_index'], 1)}" for x in v.get("largest", []))
        parts.append(f"{nm} TE {_pu(v['te'])}/yr over {v['n']} cycles (bias {_pc(v['bias_ann'])}/yr, corr {_f(v['corr'])}"
                     + (f"; largest monthly gaps {big}" if big else "") + ")")
    return "; ".join(parts) or "no index cycles to compare"


# =========================================================================================== MODEL-PRICED engines ==

@dataclass
class Frame:
    """Aligned daily arrays on one session calendar. close: raw closes; tr: total-return level; vix: VIX close as of the
    session (points); skew: SKEW as of the session (or NaN); rate: continuous bill rate known at the close; q: continuous
    dividend yield known at the close (SPX frames; 0 for SPY); divpts: dividend points accrued on the session (SPX: the
    prior close x q at the prior close over the calendar days elapsed) or the cash dividend going ex (SPY); divfc: the last cash dividend gone ex at or before the session (SPY); q_assumed: q is PRE_YIELD."""
    days: list
    ords: np.ndarray
    close: np.ndarray
    tr: np.ndarray
    vix: np.ndarray
    skew: np.ndarray
    rate: np.ndarray
    q: np.ndarray
    divpts: np.ndarray
    divfc: np.ndarray
    q_assumed: np.ndarray
    kind: str


def asof(days: Sequence[str], series: dict, max_age: int = 15) -> np.ndarray:
    """The last print at or before each day (NaN before the first or when older than ``max_age`` calendar days)."""
    ks = sorted(series)
    vals = [float(series[k]) for k in ks]
    ko = [_ord(k) for k in ks]
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        o = _ord(d)
        j = bisect.bisect_right(ko, o) - 1
        if j >= 0 and o - ko[j] <= max_age:
            out[i] = vals[j]
    return out


def spy_dividends(close, adj) -> np.ndarray:
    """Cash dividend going ex on each day from the adjclose/close ratio step: D = close[i-1] (1 - f[i-1]/f[i])."""
    close = np.asarray(close, float)
    f = np.asarray(adj, float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if np.isfinite(f[i]) and np.isfinite(f[i - 1]) and f[i] > f[i - 1] * (1 + 1e-5):
            d = close[i - 1] * (1.0 - f[i - 1] / f[i])
            if 0 < d < 0.05 * close[i - 1]:
                out[i] = d
    return out


def spx_frame(gd, gc, vix: dict, skew: Optional[dict], bills: Bills, spy: Optional[tuple], start: str = "1990-01-01",
              pre_yield: float = PRE_YIELD) -> Frame:
    """SPX frame on ^GSPC sessions from ``start`` (and the first VIX print). Dividends from SPY (``spy`` = (days, close,
    adj)): q = SPY's trailing-12-month cash dividends / its close, known at each session (PRE_YIELD before SPY has one full
    year). Dividend points accrue every session, G[i-1] (exp(q[i-1] days / 365) - 1), at the yield known at the prior
    close, as the Cboe indices accrue SPX constituent dividends daily. SPY's own dividends go ex in quarterly lumps on the
    March/June/September/December expiry session; crediting them there would put a quarter's dividends (about 0.45% of
    the index) into one cycle in three and none into the rest."""
    first_vix = min(vix) if vix else "9999"
    keep = [i for i, d in enumerate(gd) if d >= start and d >= first_vix]
    days = [gd[i] for i in keep]
    G = np.asarray(gc, float)[keep]
    ords = np.array([_ord(d) for d in days], np.int64)
    n = len(days)
    vx = asof(days, vix)
    sk = asof(days, skew) if skew else np.full(n, np.nan)
    rate = np.array([bills.rate(d) for d in days], float)
    q = np.full(n, pre_yield)
    q_assumed = np.ones(n, bool)
    divpts = np.zeros(n)
    if spy is not None and len(spy[0]):
        sd, sc, sa = spy
        D = spy_dividends(sc, sa)
        so = np.array([_ord(d) for d in sd], np.int64)
        cum = np.concatenate([[0.0], np.cumsum(D)])
        spy0 = so[0]
        for i, d in enumerate(days):
            o = ords[i]
            j = int(np.searchsorted(so, o, side="right")) - 1
            if j >= 0 and o - spy0 >= 365:
                lo = int(np.searchsorted(so, o - 365, side="right"))
                q[i] = (cum[j + 1] - cum[lo]) / sc[j]
                q_assumed[i] = False
    for i in range(1, n):                       # daily accrual at the yield known at the prior close (no quarterly lumps)
        divpts[i] = G[i - 1] * (math.exp(q[i - 1] * (ords[i] - ords[i - 1]) / 365.0) - 1.0)
    tr = np.empty(n)
    if n:
        tr[0] = 1.0
        for i in range(1, n):
            tr[i] = tr[i - 1] * (G[i] + divpts[i]) / G[i - 1]
    return Frame(days, ords, G, tr, vx, sk, rate, q, divpts, np.zeros(n), q_assumed, "spx")


def spy_frame(sd, sc, sa, vix: dict, bills: Bills) -> Frame:
    """SPY frame on SPY sessions from the first VIX print: raw closes, adjclose as total return, cash dividends by ex-day
    and their point-in-time forecast (the last one gone ex at or before each session; 0 before the first)."""
    first_vix = min(vix) if vix else "9999"
    keep = [i for i, d in enumerate(sd) if d >= first_vix]
    days = [sd[i] for i in keep]
    c, a = np.asarray(sc, float)[keep], np.asarray(sa, float)[keep]
    D = spy_dividends(c, a)
    fc = np.zeros(len(days))
    last = 0.0
    for i in range(len(days)):
        if D[i] > 0:
            last = float(D[i])
        fc[i] = last
    n = len(days)
    return Frame(days, np.array([_ord(d) for d in days], np.int64), c, a, asof(days, vix), np.full(n, np.nan),
                 np.array([bills.rate(d) for d in days], float), np.zeros(n), D, fc, np.zeros(n, bool), "spy")


def monthly_expiries(days: Sequence[str]) -> list:
    """Session index of each standard monthly expiry: the third Friday, or the prior session within 3 calendar days."""
    if not len(days):
        return []
    out, y, m = [], int(days[0][:4]), int(days[0][5:7])
    last = date.fromisoformat(days[-1])
    while date(y, m, 1) <= last:
        tf = third_friday(y, m)
        if tf <= last:
            j = bisect.bisect_right(days, tf.isoformat()) - 1
            if j >= 0 and (tf - date.fromisoformat(days[j])).days <= 3 and days[j][:7] == tf.isoformat()[:7]:
                out.append(j)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def cycles(fr: Frame, bills: Bills, start: str = "", end: str = "9999-12-31") -> dict:
    """Expiry-to-expiry monthly cycles (written at one expiry's close, settled at the next) with a VIX print at entry."""
    ex = monthly_expiries(fr.days)
    a = np.array([x for x, y in zip(ex[:-1], ex[1:]) if fr.days[x] >= start and fr.days[y] <= end and np.isfinite(fr.vix[x])], np.int64)
    b = np.array([y for x, y in zip(ex[:-1], ex[1:]) if fr.days[x] >= start and fr.days[y] <= end and np.isfinite(fr.vix[x])], np.int64)
    cum = np.concatenate([[0.0], np.cumsum(fr.divpts)])
    C = {"a": a, "b": b, "day0": [fr.days[i] for i in a], "day1": [fr.days[i] for i in b], "S0": fr.close[a], "ST": fr.close[b],
         "T": (fr.ords[b] - fr.ords[a]) / 365.0, "r": fr.rate[a], "q": fr.q[a], "vix": fr.vix[a], "skew": fr.skew[a],
         "g": np.array([bills.growth(fr.days[x], fr.days[y]) for x, y in zip(a, b)], float),
         "D": cum[b + 1] - cum[a + 1], "trf": fr.tr[b] / fr.tr[a], "n": int(a.size), "q_assumed": fr.q_assumed[a]}
    if fr.kind == "spy":                         # projected ex-dates: the expiry sessions of Mar, Jun, Sep, Dec
        proj = [e for e in ex if int(fr.days[e][5:7]) in (3, 6, 9, 12)]
        pv = np.zeros(a.size)
        for k, (x, y) in enumerate(zip(a, b)):
            for e in proj[bisect.bisect_right(proj, int(x)):bisect.bisect_right(proj, int(y))]:
                pv[k] += fr.divfc[x] * math.exp(-fr.rate[x] * (fr.ords[e] - fr.ords[x]) / 365.0)
        C["pv_div"] = pv
    return C


def bs_px(S, K, T, r, q, sig, kind: str) -> np.ndarray:
    return np.asarray(bs.price(np.asarray(S, float), np.asarray(K, float), np.asarray(T, float), np.asarray(r, float),
                               np.maximum(np.asarray(sig, float), 1e-6), kind, np.asarray(q, float)), float)


def smile_vol(F, K, sig_atm, skew, kappa: Optional[float]):
    """Flat VIX (kappa None) or the SKEW-adjusted line sigma(K) = sigma_atm - kappa (SKEW - 100) ln(K/F), floored at 1%."""
    if kappa is None:
        return np.asarray(sig_atm, float) * np.ones_like(np.asarray(K, float))
    return np.maximum(np.asarray(sig_atm, float) - kappa * (np.asarray(skew, float) - 100.0) * np.log(np.asarray(K, float) / np.asarray(F, float)), 0.01)


def _delta(S, K, T, r, q, sig, kind: str) -> float:
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    nd = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
    return math.exp(-q * T) * (nd if kind == "call" else nd - 1.0)


def strike_for_delta(S, T, r, q, sig, target: float, kind: str, skew=None, kappa: Optional[float] = None) -> float:
    """Strike with BS delta ``target``: closed form at a flat vol; with the SKEW line, bisection at each strike's own vol."""
    if kappa is None:
        return float(bs.strike_for_delta(S, T, r, sig, target, kind, q))
    F = S * math.exp((r - q) * T)
    f = lambda K: _delta(S, K, T, r, q, float(smile_vol(F, K, sig, skew, kappa)), kind) - target
    lo, hi = 0.3 * S, 2.0 * S
    flo = f(lo)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _ceil(x, step):
    return step * np.ceil(np.asarray(x, float) / step - 1e-9)


def _floor(x, step):
    return step * np.floor(np.asarray(x, float) / step + 1e-9)


def bxm_model(C: dict, scale: float = 1.0, slip: float = 0.0, step: float = SPX_STEP) -> np.ndarray:
    """BXM rule: long the index (total return), short the 1-month call at the first strike at or above the index, premium
    netted from the base (BXM methodology): R = (S_T + D - (S_T - K)+) / (S_0 - C + slip S_0) - 1."""
    S0, ST = C["S0"], C["ST"]
    K = _ceil(S0, step)
    c = bs_px(S0, K, C["T"], C["r"], C["q"], scale * C["vix"] / 100.0, "call")
    return (ST + C["D"] - np.maximum(ST - K, 0.0)) / (S0 - c + slip * S0) - 1.0


def put_model(C: dict, scale: float = 1.0, step: float = SPX_STEP) -> np.ndarray:
    """PUT rule: short puts at the first strike at or below the index on the whole account (N = account / K), premium and
    collateral in bills: R = (1 + P/K) g - (K - S_T)+ / K - 1."""
    S0, ST = C["S0"], C["ST"]
    K = _floor(S0, step)
    p = bs_px(S0, K, C["T"], C["r"], C["q"], scale * C["vix"] / 100.0, "put")
    return (1.0 + p / K) * C["g"] - np.maximum(K - ST, 0.0) / K - 1.0


def covered_put_model(C: dict, scale: float = 1.0, collateral: bool = False, step: float = SPX_STEP) -> np.ndarray:
    """Short the index + short the ATM put (PUT strike rule), per unit of notional S_0: the short and put proceeds earn
    bills, dividends are owed on the short: r = (S_0 - S_T - D - (K - S_T)+ + P g + S_0 (g - 1)) / S_0 (+ (g - 1) when the
    margin collateral also earns bills)."""
    S0, ST, g = C["S0"], C["ST"], C["g"]
    K = _floor(S0, step)
    p = bs_px(S0, K, C["T"], C["r"], C["q"], scale * C["vix"] / 100.0, "put")
    r = (S0 - ST - C["D"] - np.maximum(K - ST, 0.0) + p * g + S0 * (g - 1.0)) / S0
    return r + (g - 1.0) if collateral else r


def short_index_model(C: dict, collateral: bool = False) -> np.ndarray:
    S0, ST, g = C["S0"], C["ST"], C["g"]
    r = (S0 - ST - C["D"] + S0 * (g - 1.0)) / S0
    return r + (g - 1.0) if collateral else r


def call_spread_model(C: dict, scale: float = 1.0, wing: float = 0.05, slip: float = 0.0005, kappa: Optional[float] = None,
                      step: float = SPX_STEP) -> dict:
    """ATM covered call (BXM strike rule) and the call-spread overwrite (also long the call at the first strike at or above
    (1 + wing) S_0), both on the index's total return, premiums netted from the base, ``slip`` x S_0 per option leg. The
    wing is priced at VIX (flat) or on the SKEW line when ``kappa`` is given."""
    S0, ST, T, r, q = C["S0"], C["ST"], C["T"], C["r"], C["q"]
    sig = scale * C["vix"] / 100.0
    F = S0 * np.exp((r - q) * T)
    K1, K2 = _ceil(S0, step), _ceil(S0 * (1.0 + wing), step)
    c1 = bs_px(S0, K1, T, r, q, smile_vol(F, K1, sig, C["skew"], kappa), "call")
    c2 = bs_px(S0, K2, T, r, q, smile_vol(F, K2, sig, C["skew"], kappa), "call")
    up = ST + C["D"] - np.maximum(ST - K1, 0.0)
    r_cc = up / (S0 - c1 + slip * S0) - 1.0
    r_cs = (up + np.maximum(ST - K2, 0.0)) / (S0 - c1 + c2 + 2 * slip * S0) - 1.0
    return {"cc": r_cc, "cs": r_cs, "c1": c1 / S0, "c2": c2 / S0}


def wheel_model(C: dict, constrained: bool, scale: float = 1.0, delta: float = 0.30, slip: float = 0.001,
                kappa: Optional[float] = None, atm: bool = False, const_iv: Optional[float] = None, step: float = SPX_STEP) -> dict:
    """The wheel on monthly expiry-to-expiry cycles. Cash phase: sell puts at the ``delta`` strike (nearest 5 points; ATM =
    PUT rule) on the whole account (N = account / K), premium to bills; settled below K = assigned: buy N units at K.
    Stock phase: hold the units (total return; dividends to cash), sell N calls at the ``delta`` strike (ATM = BXM rule);
    ``constrained``: the call strike is at least the cost basis = assignment strike - premiums collected since the wheel
    cycle began (puts and calls), rounded up to the grid; settled above K = called away at K. ``slip`` x the index level per
    option written and per index trade at assignment or call-away. Monthly return = account value change at the close."""
    n = C["n"]
    R, Ks, prem = np.zeros(n), np.zeros(n), np.zeros(n)
    stock_m = np.zeros(n, bool)
    cash, units, stock, cum, k_asg = 1.0, 0.0, False, 0.0, None
    n_asg = n_call = n_floor = 0
    for k in range(n):
        S0, ST, T, r, q, g, D = (float(C[x][k]) for x in ("S0", "ST", "T", "r", "q", "g", "D"))
        sk = float(C["skew"][k])
        sig = const_iv if const_iv is not None else scale * float(C["vix"][k]) / 100.0
        F = S0 * math.exp((r - q) * T)
        vol = lambda K: float(smile_vol(F, K, sig, sk, kappa))
        V0 = cash + units * S0
        stock_m[k] = stock
        if not stock:
            if atm:
                K = float(_floor(S0, step))
            else:
                K = float(step * round(strike_for_delta(S0, T, r, q, sig, -delta, "put", sk, kappa) / step))
            P = float(bs_px(S0, K, T, r, q, vol(K), "put"))
            Ks[k], prem[k] = K, P
            N = V0 / K
            cash = (cash + N * P - slip * N * S0) * g
            cum += P
            if ST < K:
                cash -= N * K + slip * N * ST
                units, stock, k_asg = N, True, K
                n_asg += 1
        else:
            if atm:
                K = float(_ceil(S0, step))
            else:
                K = float(step * round(strike_for_delta(S0, T, r, q, sig, delta, "call", sk, kappa) / step))
            if constrained:
                kb = float(_ceil(k_asg - cum, step))
                if kb > K:
                    K, n_floor = kb, n_floor + 1
            Cc = float(bs_px(S0, K, T, r, q, vol(K), "call"))
            Ks[k], prem[k] = K, Cc
            N = units
            cash = (cash + N * Cc - slip * N * S0) * g + N * D
            cum += Cc
            if ST > K:
                cash += N * K - slip * N * ST
                units, stock, cum, k_asg = 0.0, False, 0.0, None
                n_call += 1
        V1 = cash + units * ST
        R[k] = V1 / V0 - 1.0
    return {"R": R, "stock": stock_m, "K": Ks, "premiums": prem, "assigned": n_asg, "called": n_call, "basis_floor_binds": n_floor}


def spy_putwrite(C: dict, scale: float = 1.0, step: float = SPY_STEP, exact_atm: bool = False) -> dict:
    """T-128 PUT-index construction on SPY: the put at the nearest $1 strike at or below the close (or exactly ATM), priced
    on the escrowed-dividend forward S - PV(D), on the whole account (N = account / K); premium and collateral earn bills.
    R = (1 + P/K) g - (K - S_T)+ / K - 1; SPY total return over the same cycle."""
    S0, ST = C["S0"], C["ST"]
    K = S0.copy() if exact_atm else _floor(S0, step)
    Sx = S0 - C.get("pv_div", np.zeros(S0.size))
    p = bs_px(Sx, K, C["T"], C["r"], np.zeros(S0.size), scale * C["vix"] / 100.0, "put")
    R = (1.0 + p / K) * C["g"] - np.maximum(K - ST, 0.0) / K - 1.0
    return {"R": R, "R_spy": C["trf"] - 1.0, "prem": p / K}


# ==================================================================================== shared harness pieces ==

def _bt_info(archive, syms: Sequence[str], P: dict) -> dict:
    """Per index: launch date and the number of panel periods that use a back-tested level (either end)."""
    out = {}
    for s in syms:
        bt = cboe_index(archive, s)["backtest"]
        k = sum(1 for a, b in zip(P["start"], P["end"]) if bt.get(a) or bt.get(b))
        out[s] = {"launch": INDEX_META.get(s, {}).get("launch"), "backtested_periods": int(k), "periods": P["n"]}
    return out


def _bt_txt(info: dict) -> str:
    parts = [f"{s} launched {v['launch']}: {v['backtested_periods']} of {v['periods']} months use back-tested values"
             for s, v in info.items() if v["backtested_periods"]]
    if not parts:
        return "every month uses post-launch (live) index values"
    return ("; ".join(parts) + " (Cboe back-tests published at launch; the claim describes the index histories, so they are "
            "used, not treated as known at the time)")


def _post_launch(P: dict, syms: Sequence[str]) -> tuple:
    """Indices of panel periods starting on or after every listed index's launch date, and that date."""
    launch = max((INDEX_META.get(s, {}).get("launch") or "") for s in syms)
    ii = np.array([k for k, d in enumerate(P["start"]) if d >= launch], int)
    return ii, launch


def _beta_matched(archive, syms: Sequence[str], start: str, bills: Bills) -> Optional[dict]:
    """Each index's beta and annualised alpha against SPY total return (excess over bills, month ends on the common
    calendar), and SPY's own excess Sharpe there (a beta-matched SPY-TR/bill blend has SPY's Sharpe)."""
    if not _has(archive, SPY_B):
        return None
    sd, sc, sa = _daily(archive, SPY_B)
    spy = dict(zip(sd, sa))
    lv = {s: cboe_index(archive, s)["close"] for s in syms}
    lv["SPY"] = spy
    P = monthly_panel(lv, bills, start)
    if P["n"] < 12:
        return None
    out = {"months": P["n"], "spy_sharpe": float(sharpe_ratio(P["ex"]["SPY"], PPY))}
    for s in syms:
        o = ols_hac(P["ex"][s], P["ex"]["SPY"], 12)
        out[s] = {"beta": o["beta"], "alpha_ann": PPY * o["alpha"], "t_hac": o["alpha"] / o["se_alpha"] if o["se_alpha"] else None,
                  "sharpe": float(sharpe_ratio(P["ex"][s], PPY))}
    return out


def _bm_txt(bm: Optional[dict], syms: Sequence[str]) -> str:
    if not bm:
        return "beta-matched SPY-TR blend not run (daily-history-SPY missing)"
    return (f"beta-matched SPY-TR/bill blends ({bm['months']} common months; a blend has SPY's excess Sharpe {_f(bm['spy_sharpe'])}): "
            + ", ".join(f"{s} beta {_f(bm[s]['beta'], 2)}, alpha {_pc(bm[s]['alpha_ann'])}/yr (t {_f(bm[s]['t_hac'], 2)})" for s in syms))


BLOCK_SENS = (6, 24, 36)       # block-length sensitivities of the index Sharpe differences (months; never criteria)


def index_sharpe_claim(archive, A: str, B: str, start: str, min_n: int, split: Optional[str] = None,
                       end: str = "9999-12-31", n_boot: Optional[int] = None, lw: str = "report") -> dict:
    """The shared core of the index Sharpe-difference claims: month-end panel, the judge (the Ledoit-Wolf (2008) test is
    a criterion only when ``lw`` = 'criterion', i.e. when the trial names it; otherwise it is reported), roll-date,
    block-length and post-launch sensitivities, back-test counts."""
    bills = _bills(archive)
    lv = {A: cboe_index(archive, A)["close"], B: cboe_index(archive, B)["close"]}
    P = monthly_panel(lv, bills, start, end)
    if P["n"] < 8:
        return {"P": P, "j": None}
    xa, xb = P["ex"][A], P["ex"][B]
    j = judge_sharpe(xa, xb, P["months"], min_n, (A, B), split, n_boot=n_boot, lw=lw)
    R = panel(lv, bills, roll_days(lv, start, end))
    roll = sharpe_diff_test(R["ex"][A], R["ex"][B], n_boot=n_boot) if R["n"] >= 8 else None
    ii, launch = _post_launch(P, (A, B))
    post = sharpe_diff_test(xa[ii], xb[ii], n_boot=n_boot) if ii.size >= 8 else None
    post_lw = lw_test(xa[ii], xb[ii], n_boot=n_boot) if ii.size >= 8 else None
    blocks = {str(bl): sharpe_diff_test(xa, xb, PPY, bl, n_boot) for bl in BLOCK_SENS if bl <= P["n"] // 4}
    return {"P": P, "j": j, "roll": roll, "roll_n": R["n"], "post": post, "post_lw": post_lw, "post_n": int(ii.size),
            "launch": launch, "min_n": int(min_n), "bt": _bt_info(archive, (A, B), P), "blocks": blocks}


def _bt_label(core: dict) -> Optional[str]:
    """The verdict label when back-tested index values are in the sample (None when every month is live)."""
    bt = {s: v for s, v in core["bt"].items() if v["backtested_periods"]}
    if not bt:
        return None
    return ("BACK-TESTED INDEX VALUES: " + "; ".join(f"{v['backtested_periods']} of {v['periods']} months use {s} values "
                                                     f"back-tested by Cboe before its {v['launch']} launch" for s, v in bt.items()))


def _lw_txt(t: Optional[dict]) -> str:
    if not t or t.get("diff") is None:
        return "n/a"
    hac = t.get("hac") or {}
    return (f"{_s(t['diff'])} (symmetric {_ci(t['ci'])}, two-sided bootstrap p {_f(t['p'])}"
            + (f", mean of {t['reps']} seeds" if t.get("reps") else "")
            + f"; its prewhitened Parzen HAC test alone: s.e. {_f(hac.get('se'), 4)}, p {_f(hac.get('p'))}, {_ci(hac.get('ci'))})")


def _index_reason_head(core: dict, A: str, B: str) -> str:
    P, j = core["P"], core["j"]
    f = j["full"]
    hv = "; ".join(f"{nm} {_sd_txt(h)}" for nm, h in zip(j["part_names"], j["halves"]))
    lbl = _bt_label(core)
    post = core["post"]
    role = ("a criterion: the trial names it as the alternative to the studentized block bootstrap, so the full-sample "
            "criterion must pass under both (rule 11)" if j["lw_mode"] == "criterion" else
            "reported, not a criterion: the trial names only a studentized block bootstrap")
    blk = ", ".join(f"{b} months {_ci(t['ci'])}" for b, t in core["blocks"].items())
    return ((f"{lbl}. ASSUMPTION: the claim describes the published index histories, so back-tested months are used; they "
             f"were not known at the time they describe (published at launch) and Cboe chose each index design after seeing "
             f"that history. " if lbl else "")
            + f"{A} vs {B} month-end excess returns over the 3-month bill (DTB3 discount yield -> continuous, accrued daily "
            f"at the prior print), {P['n']} months {P['months'][0]}..{P['months'][-1]} on the common calendar (rule 10(a): the "
            f"claim names month-end sampling; the indices roll on the third Friday). Annualised Sharpe {A} {_f(f['sharpe_a'])} vs "
            f"{B} {_f(f['sharpe_b'])}: difference {_sd_txt(f)} by the {CBB_NAME}: paired circular block bootstrap, 12-month "
            f"blocks, each resample studentized by the Ledoit-Wolf delta-method gradient with a fixed Bartlett(12) long-run "
            f"variance (mean of {f.get('reps', 1)} seeds x {N_BOOT} resamples, Monte Carlo s.e. of the lower end "
            f"{_f((f.get('ci_mc_se') or [None])[0], 4)}; percentile {_ci(f.get('ci_pct'))}; one-sided p {_f(f['p'])}). "
            f"{LW_NAME} (boot.time.inference: prewhitened Parzen HAC s.e. on the sample, Goetze-Kuensch block s.e. in "
            f"circular-block resamples, b = 12; {role}): {_lw_txt(j['lw'])}. Parts (judged on point estimates): {hv}. "
            f"Post-launch months only (from {core['launch']}, {core['post_n']} months"
            + (f", below min_n {core['min_n']}" if core["post_n"] < core["min_n"] else "")
            + f"): {_sd_txt(post) if post else 'n/a'}; {LW_NAME} {_lw_txt(core['post_lw']) if core['post_lw'] else 'n/a'}. "
            + ("" if lbl else f"{_bt_txt(core['bt'])}. ") + f"Block-length sensitivity ({CBB_NAME}): {blk or 'n/a'}. Roll-date sampling sensitivity "
            f"({core['roll_n']} roll-to-roll periods): {_sd_txt(core['roll']) if core['roll'] else 'n/a'}")


def _index_stat(core: dict) -> dict:
    P, j = core["P"], core["j"]
    lwf = j["lw"] or {}
    pl = core["post_lw"] or {}
    out = {"n": j["n"], "months": [P["months"][0], P["months"][-1]], "sharpe_a": j["full"]["sharpe_a"],
           "sharpe_b": j["full"]["sharpe_b"], "diff": j["full"]["diff"], "ci": j["full"]["ci"], "p": j["full"]["p"],
           "ci_mc_se": j["full"].get("ci_mc_se"), "method": CBB_NAME,
           "ledoit_wolf": {"role": "criterion (rule 11)" if j["lw_mode"] == "criterion" else "reported, not a criterion",
                           "diff": lwf.get("diff"), "ci": lwf.get("ci"), "ci_mc_se": lwf.get("ci_mc_se"), "p": lwf.get("p"),
                           "se": lwf.get("se"), "bandwidth": lwf.get("bandwidth"), "hac": lwf.get("hac")},
           "parts": [{"name": nm, "n": nn, "diff": h["diff"], "ci": h["ci"],
                      "lw_ci": (j["lw_halves"][k]["ci"] if j["lw_halves"] else None)}
                     for k, (nm, nn, h) in enumerate(zip(j["part_names"], j["part_n"], j["halves"]))],
           "parts_judged_on": "point estimates",
           "post_launch": {"from": core["launch"], "n": core["post_n"], "below_min_n": core["post_n"] < core["min_n"],
                           "diff": (core["post"] or {}).get("diff"), "ci": (core["post"] or {}).get("ci"),
                           "lw_ci": pl.get("ci"), "lw_p": pl.get("p")},
           "block_length_sensitivity": {b: {"diff": t["diff"], "ci": t["ci"], "ci_pct": t.get("ci_pct")} for b, t in core["blocks"].items()},
           "roll_date_sampling": {"n": core["roll_n"], "diff": (core["roll"] or {}).get("diff"), "ci": (core["roll"] or {}).get("ci")},
           "backtest": core["bt"], "criteria": j["criteria"], "sampling": "month-end (named by the claim)"}
    lbl = _bt_label(core)
    if lbl:
        out["label"] = lbl
        out["assumption"] = "the claim describes the published index histories (back-tested values included)"
    return out


def _short(A: str, B: str, core: dict) -> Optional[tuple]:
    if core["j"] is None:
        v, why = _verdict([("at least 8 common months", None)])
        return _out({"n": core["P"]["n"]}, core["P"]["n"], v, f"{A} and {B} share only {core['P']['n']} complete months — {why}")
    return None


# =================================================================================================== harnesses ==

def b6b_bw_bxm_alpha(archive):
    """T-161: BXM monthly excess return regressed on SPY total-return excess return, 2002-03..2026-10: positive alpha."""
    miss = _missing(archive, [cboe_b("BXM"), SPY_B, DTB3_B])
    if miss:
        return miss
    bills = _bills(archive)
    sd, sc, sa = _daily(archive, SPY_B)
    bxm = cboe_index(archive, "BXM")["close"]
    lv = {"BXM": bxm, "SPY": dict(zip(sd, sa))}
    P = monthly_panel(lv, bills, "2002-03-01")
    if P["n"] < 8:
        v, why = _verdict([("at least 8 months of BXM and SPY", None)])
        return _out({"n": P["n"]}, P["n"], v, f"only {P['n']} common months — {why}")
    j = judge_alpha(P["ex"]["BXM"], P["ex"]["SPY"], P["months"], 280)
    f = j["full"]
    # controls: price-only S&P 500 (^GSPC) benchmark; arms
    ctrl = {}
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        Pg = monthly_panel({"BXM": bxm, "GSPC": dict(zip(gd, gc))}, bills, "2002-03-01")
        if Pg["n"] >= 8:
            o = ols_hac(Pg["ex"]["BXM"], Pg["ex"]["GSPC"], 12)
            ctrl["price_only_gspc"] = {"n": Pg["n"], "alpha_ann": PPY * o["alpha"], "beta": o["beta"]}
    arms = {}
    for s in ("BXMD", "BXY", "BXMH", "BXMC", "BXMW"):
        if _has(archive, cboe_b(s)):
            Pa = monthly_panel({s: cboe_index(archive, s)["close"], "SPY": dict(zip(sd, sa))}, bills, "2002-03-01")
            if Pa["n"] >= 24:
                o = ols_hac(Pa["ex"][s], Pa["ex"]["SPY"], 12)
                arms[s] = {"n": Pa["n"], "from": Pa["months"][0], "alpha_ann": PPY * o["alpha"], "beta": o["beta"],
                           "t_hac": o["alpha"] / o["se_alpha"] if o["se_alpha"] else None}
    blend_sr = float(sharpe_ratio(P["ex"]["SPY"], PPY))
    bt = _bt_info(archive, ("BXM",), P)
    hv = "; ".join(f"{nm} {_pc(h['alpha_ann'])}/yr ({_ci(h['ci'], 2, 100, '%')})" for nm, h in zip(j["part_names"], j["halves"]))
    po = ctrl.get("price_only_gspc")
    reason = (f"BXM month-end excess return on SPY total-return (adjclose) excess return, both over the 3-month bill (DTB3 "
              f"discount yield -> continuous, accrued daily at the prior print), {P['n']} months {P['months'][0]}..{P['months'][-1]} "
              f"(rule 10(a): month-end sampling named by the trial). Annualised alpha {_pc(f['alpha_ann'])}/yr, stationary "
              f"bootstrap (mean block 12 months; mean of {f.get('reps', 1)} seeds x {N_BOOT} resamples) 95% {_ci(f['ci'], 2, 100, '%')}, "
              f"Newey-West(12) t {_f(f['t_hac'], 2)}; beta "
              f"{_f(f['beta'])} ({_ci(f['beta_ci'], 3)}; the claim's '~0.63' is descriptive, not a pass criterion). Halves: {hv}. "
              f"Controls: BXM excess Sharpe {_f(float(sharpe_ratio(P['ex']['BXM'], PPY)))} vs the beta-matched SPY-TR/bill blend "
              f"{_f(blend_sr)} (= SPY's); price-only ^GSPC benchmark alpha {_pc((po or {}).get('alpha_ann'))}/yr (beta "
              f"{_f((po or {}).get('beta'))}; biased toward BXM by the omitted dividends); arms vs SPY TR: "
              + (", ".join(f"{s} {_pc(v['alpha_ann'])}/yr (beta {_f(v['beta'], 2)}, from {v['from']})" for s, v in arms.items()) or "none archived")
              + f" (BXN/BXR need NDX/RUT benchmarks; not run). {_bt_txt(bt)} — {j['why']}")
    stat = {"n": j["n"], "months": [P["months"][0], P["months"][-1]], "alpha_ann": f["alpha_ann"], "ci": f["ci"],
            "t_hac": f["t_hac"], "beta": f["beta"], "beta_ci": f["beta_ci"],
            "halves": [{"name": nm, "alpha_ann": h["alpha_ann"], "ci": h["ci"]} for nm, h in zip(j["part_names"], j["halves"])],
            "controls": ctrl, "arms": arms, "blend_sharpe": blend_sr, "backtest": bt, "criteria": j["criteria"]}
    return _out(stat, j["n"], j["verdict"], reason)


def b6b_bw_bxmd_vs_bxm(archive):
    """T-162: Sharpe(BXMD) - Sharpe(BXM) on month-end excess returns, 2002-03..2026-10."""
    miss = _missing(archive, [cboe_b("BXMD"), cboe_b("BXM"), DTB3_B])
    if miss:
        return miss
    core = index_sharpe_claim(archive, "BXMD", "BXM", "2002-03-01", 280, lw="criterion")
    s = _short("BXMD", "BXM", core)
    if s:
        return s
    P = core["P"]
    bills = _bills(archive)
    extra = []
    stat = _index_stat(core)
    fr = fragility(P, "BXMD", "BXM")
    stat["fragility"] = fr
    for arm in ("BXY", "BXMC"):
        if _has(archive, cboe_b(arm)):
            Pa = monthly_panel({arm: cboe_index(archive, arm)["close"], "BXM": cboe_index(archive, "BXM")["close"]}, bills, "2002-03-01")
            if Pa["n"] >= 8:
                t = sharpe_diff_test(Pa["ex"][arm], Pa["ex"]["BXM"])
                stat[f"arm_{arm}_minus_BXM"] = {"n": Pa["n"], "diff": t["diff"], "ci": t["ci"]}
                extra.append(f"{arm} - BXM {_sd_txt(t)}" + (" (BXMC is the VIX-conditional buy-write, a separate arm)" if arm == "BXMC" else ""))
    conv = None
    if _has(archive, GSPC_B):
        gd, gc, _ = _daily(archive, GSPC_B)
        Pg = monthly_panel({"BXMD": cboe_index(archive, "BXMD")["close"], "BXM": cboe_index(archive, "BXM")["close"],
                            "SPX": dict(zip(gd, gc))}, bills, "2002-03-01")
        if Pg["n"] >= 12:
            x = Pg["ret"]["SPX"]
            y = Pg["ret"]["BXMD"] - Pg["ret"]["BXM"]
            X = np.column_stack([np.ones(x.size), x, x * x])
            cf = np.linalg.lstsq(X, y, rcond=None)[0]
            conv = {"n": Pg["n"], "slope": float(cf[1]), "quad": float(cf[2])}
            stat["convexity"] = conv
    bm = _beta_matched(archive, ("BXMD", "BXM"), "2002-03-01", bills)
    stat["beta_matched"] = bm
    reason = (_index_reason_head(core, "BXMD", "BXM") + f". {_fragility_txt(fr)}. Arms: " + ("; ".join(extra) or "none archived")
              + (f". BXMD-BXM monthly spread on the SPX price return: slope {_f(conv['slope'])}, quadratic {_f(conv['quad'], 2)} "
                 f"(the 30-delta write keeps more upside)" if conv else "") + f". {_bm_txt(bm, ('BXMD', 'BXM'))} — {core['j']['why']}")
    return _out(stat, core["j"]["n"], core["j"]["verdict"], reason)


def fragility(P: dict, A: str, B: str, n_boot: Optional[int] = None) -> dict:
    """Sensitivities of the full-sample interval's lower end (never criteria): log excess returns, a 3-month-block
    percentile CI, and leaving out each calendar year in turn (studentized CBB, 12-month blocks, seed 0)."""
    xa, xb = P["ex"][A], P["ex"][B]
    lb = np.log1p(P["bill"])
    lg = sharpe_diff_test(np.log1p(P["ret"][A]) - lb, np.log1p(P["ret"][B]) - lb, n_boot=n_boot)
    b3 = sharpe_diff_test(xa, xb, PPY, 3, n_boot)
    yrs = sorted({m[:4] for m in P["months"]})
    loyo = []
    for yr in yrs:
        keep = np.array([m[:4] != yr for m in P["months"]])
        t = sharpe_diff_test(xa[keep], xb[keep], n_boot=n_boot)
        loyo.append({"year": yr, "diff": t["diff"], "lower": t["ci"][0]})
    loyo.sort(key=lambda r: (r["lower"] is None, r["lower"]))
    flips = [r["year"] for r in loyo if r["lower"] is not None and r["lower"] <= 0]
    return {"log_excess": {"diff": lg["diff"], "ci": lg["ci"]}, "block3_percentile": {"diff": b3["diff"], "ci_pct": b3.get("ci_pct")},
            "leave_one_year_out_lowest": loyo[:6], "years_whose_removal_puts_lower_end_at_or_below_0": flips}


def _fragility_txt(fr: dict) -> str:
    lo = fr["leave_one_year_out_lowest"]
    return (f"Fragility of the lower end (sensitivities, not criteria): log excess returns {_ci(fr['log_excess']['ci'])}; "
            f"3-month-block percentile {_ci(fr['block3_percentile']['ci_pct'])}; leave-one-year-out lowest lower ends "
            + ", ".join(f"{r['year']} {_s(r['lower'])}" for r in lo[:4])
            + f" ({len(fr['years_whose_removal_puts_lower_end_at_or_below_0'])} years whose removal puts it at or below 0"
            + (": " + ", ".join(fr["years_whose_removal_puts_lower_end_at_or_below_0"]) if fr["years_whose_removal_puts_lower_end_at_or_below_0"] else "")
            + ")")


def b6b_bw_bxmw_vs_bxm(archive):
    """T-163: Sharpe(BXMW) - Sharpe(BXM) on month-end excess returns from 2012-06-29, split pre/post 2020."""
    miss = _missing(archive, [cboe_b("BXMW"), cboe_b("BXM"), DTB3_B])
    if miss:
        return miss
    core = index_sharpe_claim(archive, "BXMW", "BXM", "2012-06-29", 160, split="2020-01")
    s = _short("BXMW", "BXM", core)
    if s:
        return s
    P = core["P"]
    stat = _index_stat(core)
    eq = judge_sharpe(P["ex"]["BXMW"], P["ex"]["BXM"], P["months"], 160, ("BXMW", "BXM"), None)
    cost = sharpe_diff_test(P["ex"]["BXMW"] - 4 * 0.0005, P["ex"]["BXM"] - 0.0005)
    stat["equal_halves"] = [{"name": nm, "diff": h["diff"], "ci": h["ci"]} for nm, h in zip(eq["part_names"], eq["halves"])]
    stat["cost_sensitivity"] = {"bxmw_cost_per_month": 0.002, "bxm_cost_per_month": 0.0005, "diff": cost["diff"], "ci": cost["ci"]}
    bm = _beta_matched(archive, ("BXMW", "BXM"), "2012-06-29", _bills(archive))
    stat["beta_matched"] = bm
    reason = (_index_reason_head(core, "BXMW", "BXM") + " (the trial's procedure names the pre/post-2020 split; equal-count halves "
              + ", ".join(f"{nm} {_s(h['diff'])}" for nm, h in zip(eq["part_names"], eq["halves"]))
              + f"). Cost sensitivity (4 rolls x 0.05% of notional a month for BXMW, 1 x 0.05% for BXM): {_sd_txt(cost)}. "
              f"{_bm_txt(bm, ('BXMW', 'BXM'))} — {core['j']['why']}")
    return _out(stat, core["j"]["n"], core["j"]["verdict"], reason)


def b6b_bw_bxmh_vs_bxm(archive):
    """T-164: Sharpe(BXMH) - Sharpe(BXM) on month-end excess returns, 2002-03..2026-10."""
    miss = _missing(archive, [cboe_b("BXMH"), cboe_b("BXM"), DTB3_B])
    if miss:
        return miss
    core = index_sharpe_claim(archive, "BXMH", "BXM", "2002-03-01", 280)
    s = _short("BXMH", "BXM", core)
    if s:
        return s
    stat = _index_stat(core)
    bills = _bills(archive)
    txt = []
    if _has(archive, SPY_B):
        sd, sc, sa = _daily(archive, SPY_B)
        Pb = monthly_panel({"BXM": cboe_index(archive, "BXM")["close"], "SPY": dict(zip(sd, sa))}, bills, "2002-03-01")
        if Pb["n"] >= 8:
            bl = {}
            for w in (0.25, 0.5, 0.75, 1.0):
                x = w * Pb["ret"]["BXM"] + (1 - w) * Pb["ret"]["SPY"] - Pb["bill"]
                bl[f"{w:.2f}"] = float(sharpe_ratio(x, PPY))
            stat["blends_w_bxm_plus_spy_tr"] = bl
            txt.append("synthetic monthly-rebalanced blends w BXM + (1-w) SPY TR, excess Sharpe "
                       + ", ".join(f"w={k} {_f(v)}" for k, v in bl.items()))
    if _has(archive, cboe_b("BXMC")):
        Pc = monthly_panel({"BXMC": cboe_index(archive, "BXMC")["close"], "BXM": cboe_index(archive, "BXM")["close"]}, bills, "2002-03-01")
        if Pc["n"] >= 8:
            t = sharpe_diff_test(Pc["ex"]["BXMC"], Pc["ex"]["BXM"])
            stat["arm_BXMC_minus_BXM"] = {"n": Pc["n"], "diff": t["diff"], "ci": t["ci"]}
            txt.append(f"BXMC (VIX-conditional w) - BXM {_sd_txt(t)}")
    bm = _beta_matched(archive, ("BXMH", "BXM"), "2002-03-01", bills)
    stat["beta_matched"] = bm
    reason = (_index_reason_head(core, "BXMH", "BXM") + ". Secondary: " + ("; ".join(txt) or "none") + f". {_bm_txt(bm, ('BXMH', 'BXM'))}"
              " (ETF fee drag of 0.35-0.60%/yr applies only to replication and is not charged to the indices)"
              f" — {core['j']['why']}")
    return _out(stat, core["j"]["n"], core["j"]["verdict"], reason)


def b6b_bw_put_vs_bxm(archive):
    """T-170: Sharpe(PUT) - Sharpe(BXM) on month-end excess returns, 2007-01..2026-10 (PUT is daily from 2007-01-03)."""
    miss = _missing(archive, [cboe_b("PUT"), cboe_b("BXM"), DTB3_B])
    if miss:
        return miss
    core = index_sharpe_claim(archive, "PUT", "BXM", "2007-01-01", 220)
    s = _short("PUT", "BXM", core)
    if s:
        return s
    stat = _index_stat(core)
    bills = _bills(archive)
    P = core["P"]
    put, bxm = cboe_index(archive, "PUT")["close"], cboe_index(archive, "BXM")["close"]
    lv = {"PUT": put, "BXM": bxm}
    # sample window: the first return ends at the first month end after the 2007-01 month end; the last month only if complete
    before = [d for d in put if d < "2007-01-01"]
    cd = common_days(lv, "2007-01-01")
    edge = {"first_return_month": P["months"][0], "last_return_month": P["months"][-1],
            "put_last_row_before_2007": max(before) if before else None, "first_common_day": cd[0] if cd else None,
            "last_common_day": cd[-1] if cd else None}
    part_days = ([cd[0]] if cd and cd[0] < P["days"][0] else []) + list(P["days"]) + ([cd[-1]] if cd and cd[-1] > P["days"][-1] else [])
    Pp_ = panel(lv, bills, part_days)
    partial = sharpe_diff_test(Pp_["ex"]["PUT"], Pp_["ex"]["BXM"]) if Pp_["n"] > P["n"] else None
    edge["with_partial_months"] = None if not partial else {"n": Pp_["n"], "from": Pp_["days"][0], "to": Pp_["days"][-1],
                                                            "diff": partial["diff"], "ci": partial["ci"]}
    stat["window"] = edge
    arms, with_edge, ran = [], [], []
    arm_name = {"PUTY": "2% OTM (PUTY)", "WPUT": "weekly (WPUT)", "PUTD": "dynamic (PUTD)"}
    for arm in ("PUTY", "WPUT", "PUTD"):
        if _has(archive, cboe_b(arm)):
            alv = {arm: cboe_index(archive, arm)["close"], "BXM": bxm}
            row = {}
            for key, st in (("full_common_history", "2002-03-01"), ("from_2007", "2007-01-01")):
                Pa = monthly_panel(alv, bills, st)
                if Pa["n"] >= 8:
                    t = sharpe_diff_test(Pa["ex"][arm], Pa["ex"]["BXM"])
                    row[key] = {"n": Pa["n"], "from": Pa["months"][0], "diff": t["diff"], "ci": t["ci"]}
            if row:
                ran.append(arm_name[arm])
                if any(v["ci"][0] is not None and v["ci"][0] > 0 for v in row.values()):
                    with_edge.append(arm_name[arm])
                stat[f"arm_{arm}_minus_BXM"] = row
                arms.append(f"{arm} - BXM " + "; ".join(f"{v['n']} months from {v['from']} {_sd_txt(v)}" for v in row.values()))
    par = None
    if _has(archive, cboe_b("PUTY")) and _has(archive, cboe_b("BXY")):
        Pp = monthly_panel({"PUTY": cboe_index(archive, "PUTY")["close"], "BXY": cboe_index(archive, "BXY")["close"]}, bills, "1988-06-01")
        if Pp["n"] >= 8:
            par = sharpe_diff_test(Pp["ex"]["PUTY"], Pp["ex"]["BXY"])
            stat["control_PUTY_minus_BXY"] = {"n": Pp["n"], "from": Pp["months"][0], "diff": par["diff"], "ci": par["ci"]}
            ran.append("the PUTY - BXY parity control")
            if par["ci"][0] is not None and par["ci"][0] > 0:
                with_edge.append("the PUTY - BXY parity control")
    none_ = [x for x in ran if x not in with_edge]
    scope = ("Scope: the support covers the PUT and BXM indices only (the claim names them)"
             + (f"; {', '.join(none_)} show{'s' if len(none_) == 1 else ''} no put-write edge (no 95% CI above 0)" if none_ else "")
             + (f"; {', '.join(with_edge)} show{'s' if len(with_edge) == 1 else ''} one (95% CI above 0)" if with_edge else ""))
    first_txt = (f"the first monthly return is {edge['first_return_month']} (PUT_History.csv has no 2006-12 month-end row: its "
                 f"last row before 2007 is {edge['put_last_row_before_2007']}, and daily rows start {edge['first_common_day']}), so "
                 f"the claim's 2007-01 is missing" if edge["first_return_month"] > "2007-01" else
                 f"the first monthly return is {edge['first_return_month']}")
    last_txt = (f"the last is {edge['last_return_month']}" + (f" (the final month, data to {edge['last_common_day']}, is incomplete)"
                                                              if edge["last_common_day"] and edge["last_common_day"][:7] > edge["last_return_month"] else ""))
    reason = (_index_reason_head(core, "PUT", "BXM")
              + f". Window: {first_txt}; {last_txt}. With the partial first and last months added "
              f"({edge['with_partial_months']['from'] if partial else 'n/a'}..{edge['with_partial_months']['to'] if partial else 'n/a'}): "
              f"{_sd_txt(partial) if partial else 'n/a'}. Secondary arms (not criteria): " + ("; ".join(arms) or "none archived")
              + (f". Parity control PUTY - BXY (both 2% OTM, {stat['control_PUTY_minus_BXY']['n']} months from "
                 f"{stat['control_PUTY_minus_BXY']['from']}): {_sd_txt(par)}" if par else "") + f". {scope} — {core['j']['why']}")
    return _out(stat, core["j"]["n"], core["j"]["verdict"], reason)


def b6b_bw_cmbo_vs_bxy(archive):
    """T-172: Sharpe(CMBO) - Sharpe(BXY) on month-end excess returns, 1988-06..2026-10."""
    miss = _missing(archive, [cboe_b("CMBO"), cboe_b("BXY"), DTB3_B])
    if miss:
        return miss
    core = index_sharpe_claim(archive, "CMBO", "BXY", "1988-06-01", 400)
    s = _short("CMBO", "BXY", core)
    if s:
        return s
    P = core["P"]
    stat = _index_stat(core)
    k = max(1, int(round(0.05 * P["n"])))
    worst = {s_: float(np.sort(P["ret"][s_])[:k].mean()) for s_ in ("CMBO", "BXY")}
    stat["worst_5pct_months_mean"] = worst
    bills = _bills(archive)
    puty = None
    if _has(archive, cboe_b("PUTY")):
        Pp = monthly_panel({"PUTY": cboe_index(archive, "PUTY")["close"], "BXY": cboe_index(archive, "BXY")["close"]}, bills, "1988-06-01")
        if Pp["n"] >= 8:
            puty = sharpe_diff_test(Pp["ex"]["PUTY"], Pp["ex"]["BXY"])
            stat["arm_PUTY_minus_BXY"] = {"n": Pp["n"], "diff": puty["diff"], "ci": puty["ci"]}
    bm = _beta_matched(archive, ("CMBO", "BXY"), "1993-01-29", bills)
    stat["beta_matched"] = bm
    reason = (_index_reason_head(core, "CMBO", "BXY") + f". Worst 5% of months ({k}): mean CMBO {_pc(worst['CMBO'])}, BXY "
              f"{_pc(worst['BXY'])}. Put-only arm PUTY - BXY: {_sd_txt(puty) if puty else 'n/a'}. {_bm_txt(bm, ('CMBO', 'BXY'))} "
              f"(SPY exists from 1993) — {core['j']['why']}")
    return _out(stat, core["j"]["n"], core["j"]["verdict"], reason)


def b6b_bw_put_bxm_return_gap(archive):
    """T-202: CAGR(PUT) - CAGR(BXM) over their common daily history lies inside (0, 1.5) pp/yr (95% CI)."""
    miss = _missing(archive, [cboe_b("PUT"), cboe_b("BXM"), DTB3_B])
    if miss:
        return miss
    bills = _bills(archive)
    put, bxm = cboe_index(archive, "PUT")["close"], cboe_index(archive, "BXM")["close"]
    lv = {"PUT": put, "BXM": bxm}
    P = monthly_panel(lv, bills, "2007-01-03")
    if P["n"] < 8:
        v, why = _verdict([("at least 8 common months", None)])
        return _out({"n": P["n"]}, P["n"], v, f"PUT and BXM share only {P['n']} complete months — {why}")
    j = judge_band(P["ret"]["PUT"], P["ret"]["BXM"], 200)
    t = j["test"]
    decades = {}
    for nm, lo, hi in (("2007-2016", "0000", "2017-01"), ("2017-2026", "2017-01", "9999")):
        ii = np.array([k for k, m in enumerate(P["months"]) if lo <= m < hi], int)
        if ii.size >= 8:
            d = cagr_diff_test(P["ret"]["PUT"][ii], P["ret"]["BXM"][ii])
            decades[nm] = {"n": int(ii.size), "diff": d["diff"], "ci": d["ci"]}
    corr = float(np.corrcoef(P["ret"]["PUT"], P["ret"]["BXM"])[0, 1])
    bill_ann = cagr(P["bill"])
    dd = {}
    for yr in ("2008", "2020"):
        ii = np.array([k for k, m in enumerate(P["months"]) if m[:4] == yr], int)
        if ii.size:
            dd[yr] = {s: max_drawdown(P["ret"][s][ii]) for s in ("PUT", "BXM")}
    bxmd = None
    if _has(archive, cboe_b("BXMD")):
        Pd = monthly_panel({"PUT": put, "BXMD": cboe_index(archive, "BXMD")["close"]}, bills, "2007-01-03")
        if Pd["n"] >= 8:
            bxmd = cagr_diff_test(Pd["ret"]["PUT"], Pd["ret"]["BXMD"])
    bt = _bt_info(archive, ("PUT", "BXM"), P)
    ii, launch = _post_launch(P, ("PUT", "BXM"))
    post = cagr_diff_test(P["ret"]["PUT"][ii], P["ret"]["BXM"][ii]) if ii.size >= 8 else None
    pct = lambda ci: _ci(ci, 2, 100, " pp")
    reason = (f"PUT and BXM month-end total returns over their common daily history ({P['n']} months {P['months'][0]}.."
              f"{P['months'][-1]}; PUT_History.csv is daily only from 2007-01-03; rule 10(a): monthly sampling). Annualised return "
              f"(CAGR) PUT {_pc(t['cagr_a'])} vs BXM {_pc(t['cagr_b'])}: difference {_s(t['diff'] * 100, 2)} pp/yr, studentized "
              f"block-bootstrap (12-month blocks, mean of {t.get('reps', 1)} seeds) 95% {pct(t['ci'])} (percentile {pct(t.get('ci_pct'))}); "
              f"arithmetic 12 x mean difference {_s(t['arith_diff'] * 100, 2)} pp "
              f"({pct(t['arith_ci'])}). Decades: " + ", ".join(f"{k} {_s(v['diff'] * 100, 2)} pp ({pct(v['ci'])})" for k, v in decades.items())
              + f". Monthly correlation {_f(corr)}; bill return over the window {_pc(bill_ann)}/yr (PUT's collateral income; BXM holds "
              f"the index instead); max drawdowns within 2008: PUT {_pc(dd.get('2008', {}).get('PUT'))}, BXM {_pc(dd.get('2008', {}).get('BXM'))}; "
              f"2020: PUT {_pc(dd.get('2020', {}).get('PUT'))}, BXM {_pc(dd.get('2020', {}).get('BXM'))}. Strike control PUT - BXMD "
              f"{_s(None if not bxmd else bxmd['diff'] * 100, 2)} pp ({pct(bxmd['ci']) if bxmd else 'n/a'}). {_bt_txt(bt)}; post-launch "
              f"(from {launch}, {ii.size} months) {_s(None if not post else post['diff'] * 100, 2)} pp ({pct(post['ci']) if post else 'n/a'}) — {j['why']}")
    stat = {"n": j["n"], "months": [P["months"][0], P["months"][-1]], "cagr_put": t["cagr_a"], "cagr_bxm": t["cagr_b"],
            "diff": t["diff"], "ci": t["ci"], "arith_diff": t["arith_diff"], "arith_ci": t["arith_ci"], "decades": decades,
            "monthly_corr": corr, "bill_cagr": bill_ann, "drawdowns": dd,
            "control_put_minus_bxmd": None if not bxmd else {"diff": bxmd["diff"], "ci": bxmd["ci"]},
            "post_launch": None if not post else {"from": launch, "n": int(ii.size), "diff": post["diff"], "ci": post["ci"]},
            "backtest": bt, "criteria": j["criteria"]}
    return _out(stat, j["n"], j["verdict"], reason)


# -------------------------------------------------------------------------------------------- MODEL-PRICED ----

def _spx(archive) -> Frame:
    def load():
        gd, gc, _ = _daily(archive, GSPC_B)
        spy = _daily(archive, SPY_B) if _has(archive, SPY_B) else None
        skew = _closes(archive, SKEW_B) if _has(archive, SKEW_B) else None
        return spx_frame(gd, gc, _closes(archive, VIX_B), skew, _bills(archive), spy)
    return _cached(archive, ("spx_frame",), load)


def _gate(archive, indices: Sequence[str] = ("BXM", "PUT"), scale: float = 1.0) -> dict:
    """The calibration gate: the claim's pricer (BS at scale x VIX, closes, no costs) on the BXM and PUT rules against the
    indices' roll-to-roll returns on the same expiry sessions (BXM from its first roll in the file, PUT from 2007-01-03)."""
    def run():
        fr, bills = _spx(archive), _bills(archive)
        C = cycles(fr, bills)
        pairs, meta = {}, {}
        for sym in indices:
            lv = cboe_index(archive, sym)["close"]
            first = "2007-01-03" if sym == "PUT" else min(lv) if lv else "9999"
            ok = np.array([d0 >= first and d0 in lv and d1 in lv for d0, d1 in zip(C["day0"], C["day1"])], bool)
            if not ok.any():
                continue
            sub = {k: (v[ok] if isinstance(v, np.ndarray) else [x for x, o in zip(v, ok) if o]) for k, v in C.items() if k != "n"}
            sub["n"] = int(ok.sum())
            model = bxm_model(sub, scale) if sym == "BXM" else put_model(sub, scale)
            actual = np.array([lv[d1] / lv[d0] - 1 for d0, d1 in zip(sub["day0"], sub["day1"])])
            pairs[sym] = (model, actual)
            meta[sym] = {"first": sub["day1"][0], "last": sub["day1"][-1], "skipped": int((~ok).sum()), "ends": sub["day1"]}
        g = calibration_gate(pairs) if pairs else {"indices": {}, "ok": False, "te_max": TE_MAX}
        for sym, v in g["indices"].items():
            ends = meta[sym].pop("ends")
            v.update(meta[sym])
            d = pairs[sym][0] - pairs[sym][1]
            v["largest"] = [{"cycle_end": ends[i], "model_minus_index": float(d[i])} for i in v.pop("largest_abs_diff_idx")]
        return g
    return _cached(archive, ("gate", tuple(indices), scale), run)


def _gate_name(g: dict, names: str) -> str:
    te = ", ".join(f"{nm} {_pu(v['te'])}" for nm, v in g["indices"].items()) or "no cycles"
    return (f"calibration gate: the BS-at-VIX pricer tracks {names} monthly roll-to-roll returns within {TE_MAX * 100:.0f}%/yr "
            f"(TE {te})")


def _kappa(archive) -> Optional[dict]:
    """SKEW slope kappa calibrated once on the archived SPX chain (batch6_surf.calibrate_skew_slope), or None."""
    if not _has(archive, KAPPA_CHAIN):
        return None

    def run():
        from mandel.experiments.batch6_surf import calibrate_skew_slope
        from mandel.experiments.volatility import _quote_day
        chain = list(archive.load(KAPPA_CHAIN))
        fr = _spx(archive)
        qd = _quote_day(chain[0].get("available_at", "") if chain else "", fr.days)
        sk, vx = _closes(archive, SKEW_B) if _has(archive, SKEW_B) else {}, _closes(archive, VIX_B)
        if not qd or qd not in sk or qd not in vx:
            return None
        try:
            return calibrate_skew_slope([r["value"] for r in chain], qd, _bills(archive).rate(qd), vx[qd], sk[qd])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None
    return _cached(archive, ("kappa",), run)


def _model_window(C: dict, spx: bool = True) -> str:
    qa = int(np.sum(C["q_assumed"]))
    dte = np.round(C["T"] * 365).astype(int)
    txt = (f"{C['n']} monthly expiry-to-expiry cycles {C['day0'][0]}..{C['day1'][-1]} (rule 10(a): the standard monthly "
           f"expiry, third Friday or the prior session; {int(dte.min())}-{int(dte.max())} calendar days)")
    if not spx:
        return txt
    return txt + (f"; the held index accrues dividends every session at the q known at the prior close, as BXM and PUT "
                  f"accrue SPX dividends daily (not in SPY's quarterly ex-date lumps); {qa} cycles price with, and accrue, "
                  f"the ASSUMED q = {PRE_YIELD:.1%} (before SPY's first full year)")


def b6b_bw_putwrite_vs_spy(archive):
    """T-128: MODEL-PRICED SPY 1-month ATM put-write (PUT construction) vs SPY total return: higher Sharpe, p < 0.05 at IV
    scale 1.0 and 0.9 in the full sample and both halves."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    bills = _bills(archive)
    sd, sc, sa = _daily(archive, SPY_B)
    fr = spy_frame(sd, sc, sa, _closes(archive, VIX_B), bills)
    C = cycles(fr, bills)
    if C["n"] < 8:
        v, why = _verdict([("at least 8 monthly cycles", None)])
        return _out({"n": C["n"]}, C["n"], v, f"only {C['n']} SPY monthly cycles with a VIX print — {why}")
    runs, sens = {}, {}
    for sc_ in (1.0, 0.9, 0.81):
        pw = spy_putwrite(C, sc_)
        x_p, x_s = pw["R"] - (C["g"] - 1), pw["R_spy"] - (C["g"] - 1)
        if sc_ in (1.0, 0.9):
            runs[sc_] = (x_p, x_s)
        else:
            sens[f"{sc_:.2f}"] = sharpe_diff_test(x_p, x_s)
    j = judge_putwrite(runs, 300)
    pw = spy_putwrite(C, 1.0)
    x_p, x_s = runs[1.0]
    ex = spy_putwrite(C, 1.0, exact_atm=True)
    exact = sharpe_diff_test(ex["R"] - (C["g"] - 1), x_s)
    mdd_p, mdd_s = max_drawdown(pw["R"]), max_drawdown(pw["R_spy"])
    desc = {"skew": float(skewness(x_p)), "kurtosis": float(kurtosis(x_p)),
            "psr_vs_spy_sharpe": psr(x_p, float(sharpe_ratio(x_s))), "mdd_putwrite": mdd_p, "mdd_spy": mdd_s,
            "mdd_ratio": mdd_p / mdd_s if mdd_s else None, "mean_premium_pct_of_strike": float(pw["prem"].mean())}
    bench = None
    if _has(archive, cboe_b("PUT")):
        lv = cboe_index(archive, "PUT")["close"]
        ok = np.array([d0 >= "2007-01-03" and d0 in lv and d1 in lv for d0, d1 in zip(C["day0"], C["day1"])], bool)
        if ok.sum() >= 24:
            act = np.array([lv[d1] / lv[d0] - 1 for d0, d1, o in zip(C["day0"], C["day1"], ok) if o])
            d = pw["R"][ok] - act
            bench = {"n": int(ok.sum()), "te": float(d.std(ddof=1) * math.sqrt(12)), "bias_ann": float(d.mean() * 12),
                     "corr": float(np.corrcoef(pw["R"][ok], act)[0, 1]), "sharpe_model": float(sharpe_ratio(x_p[ok], PPY)),
                     "sharpe_put": float(sharpe_ratio(act - (C["g"][ok] - 1), PPY))}
    f1, f9 = j["by_scale"]["1.00"], j["by_scale"]["0.90"]
    hv = lambda r: ", ".join(f"{nm} {_s(h['diff'])} (p {_f(h['p'])})" for nm, h in zip(("first half", "second half"), r["halves"]))
    reason = (f"{MP} (Black-Scholes put at VIX/100 x scale on SPY's escrowed-dividend forward; no transaction costs, none "
              f"stated): SPY 1-month put at the nearest $1 strike at or below the close, written at each monthly expiry close on "
              f"the whole account (PUT-index construction: premium and K collateral in 3-month bills), settled on SPY's raw close "
              f"(SOQ proxy); {_model_window(C, spx=False)}. SPY buy-and-hold is total return (adjclose: dividends reinvested). "
              f"Excess-return Sharpe putwrite {_f(f1['full']['sharpe_a'])} vs SPY {_f(f1['full']['sharpe_b'])}: IV x1.00 difference "
              f"{_sd_txt(f1['full'])}, p {_f(f1['full']['p'])} ({hv(f1)}); IV x0.90 {_sd_txt(f9['full'])}, p {_f(f9['full']['p'])} "
              f"({hv(f9)}); x0.81 sensitivity {_sd_txt(sens['0.81'])}; exact-ATM strike (x1.00) {_sd_txt(exact)}. VIX overstates "
              f"SPY's ATM IV, so x1.00 flatters the put-write. Putwrite excess skew {_f(desc['skew'], 2)}, kurtosis "
              f"{_f(desc['kurtosis'], 1)}, PSR vs SPY's Sharpe {_f(desc['psr_vs_spy_sharpe'])}; max drawdown putwrite "
              f"{_pc(mdd_p, 1)} vs SPY {_pc(mdd_s, 1)} (ratio {_f(desc['mdd_ratio'], 2)}). Benchmark check vs the actual Cboe PUT "
              + (f"({bench['n']} roll-to-roll cycles from 2007): tracking error {_pu(bench['te'])}/yr, bias {_pc(bench['bias_ann'])}/yr, "
                 f"corr {_f(bench['corr'])}; Sharpe model {_f(bench['sharpe_model'])} vs PUT {_f(bench['sharpe_put'])}"
                 if bench else "not available") + f" — {j['why']}")
    stat = {"n": j["n"], "cycles": [C["day0"][0], C["day1"][-1]], "label": MP,
            "by_scale": {k: {"full": {kk: v["full"][kk] for kk in ("diff", "ci", "p", "sharpe_a", "sharpe_b")},
                             "halves": [{kk: h[kk] for kk in ("diff", "ci", "p")} for h in v["halves"]]} for k, v in j["by_scale"].items()},
            "iv_scale_sensitivity": {k: {"diff": v["diff"], "ci": v["ci"], "p": v["p"]} for k, v in sens.items()},
            "exact_atm_strike": {"diff": exact["diff"], "ci": exact["ci"], "p": exact["p"]}, "describe": desc,
            "benchmark_vs_PUT": bench, "criteria": j["criteria"], "rule10": "calendar: standard monthly expiry"}
    return _out(stat, j["n"], j["verdict"], reason)


def b6b_bw_wheel_basis(archive):
    """T-171: MODEL-PRICED SPX wheel with the call strike floored at the cost basis has a LOWER Sharpe than the
    unconstrained 30-delta wheel (95% CI < 0), after the BXM/PUT calibration gate."""
    miss = _missing(archive, [GSPC_B, VIX_B, DTB3_B, SPY_B, cboe_b("BXM"), cboe_b("PUT")])
    if miss:
        return miss
    fr, bills = _spx(archive), _bills(archive)
    C = cycles(fr, bills, start="1990-01-01")
    if C["n"] < 8:
        v, why = _verdict([("at least 8 monthly cycles", None)])
        return _out({"n": C["n"]}, C["n"], v, f"only {C['n']} SPX monthly cycles — {why}")
    g = _gate(archive, ("BXM", "PUT"))
    ex = C["g"] - 1

    def pair(**kw):
        wc, wu = wheel_model(C, True, **kw), wheel_model(C, False, **kw)
        return wc, wu, wc["R"] - ex, wu["R"] - ex
    wc, wu, xc, xu = pair()
    j = judge_gate_and_sharpe(xc, xu, g["ok"], _gate_name(g, "BXM (2002-) and PUT (2007-)"), 400, side="lt")
    f = j["full"]
    sens = {}
    for nm, kw in (("iv_x0.90", {"scale": 0.9}), ("iv_x0.81", {"scale": 0.81}), ("no_slippage", {"slip": 0.0}),
                   ("constant_iv_20pct", {"const_iv": 0.20})):
        _, _, a_, b_ = pair(**kw)
        sens[nm] = sharpe_diff_test(a_, b_, n_boot=1000)
    kap = _kappa(archive)
    if kap and kap.get("kappa") and _has(archive, SKEW_B) and np.isfinite(C["skew"]).all():
        _, _, a_, b_ = pair(kappa=kap["kappa"])
        sens["skew_line"] = sharpe_diff_test(a_, b_, n_boot=1000)
    atm_chk = None
    lv = cboe_index(archive, "PUT")["close"]
    wa = wheel_model(C, False, atm=True, slip=0.0)
    ok = np.array([d0 >= "2007-01-03" and d0 in lv and d1 in lv for d0, d1 in zip(C["day0"], C["day1"])], bool)
    if ok.sum() >= 24:
        act = np.array([lv[d1] / lv[d0] - 1 for d0, d1, o in zip(C["day0"], C["day1"], ok) if o])
        d = wa["R"][ok] - act
        atm_chk = {"n": int(ok.sum()), "te": float(d.std(ddof=1) * math.sqrt(12)), "corr": float(np.corrcoef(wa["R"][ok], act)[0, 1])}
    reason = (f"{MP} (Black-Scholes at VIX/100 on ^GSPC closes with SPY's trailing dividend yield; settled on the expiry-session "
              f"close as the SOQ proxy): {_model_window(C)}. Wheel: sell the 30-delta put (nearest 5-point strike) on the whole "
              f"cash account; when assigned, hold the index (total return) and sell 30-delta calls until called away; the "
              f"constrained arm floors the call strike at the cost basis (assignment strike minus premiums since the wheel cycle "
              f"began). 10 bps of the index per option written and per index trade at assignment or call-away. The trial's "
              f"30-45 DTE band is not met exactly: a continuously invested wheel on the standard calendar has 28- or 35-day "
              f"cycles. Excess-return Sharpe constrained {_f(f['sharpe_a'])} vs unconstrained {_f(f['sharpe_b'])}: difference "
              f"{_sd_txt(f)} (studentized paired block bootstrap, 12-cycle blocks, mean of {f.get('reps', 1)} seeds; one-sided p "
              f"for a negative difference {_f(f['p_lt'])}); time in "
              f"stock {np.mean(wc['stock']) * 100:.0f}% vs {np.mean(wu['stock']) * 100:.0f}%, assignments {wc['assigned']} vs "
              f"{wu['assigned']}, basis floor binding in {wc['basis_floor_binds']} call months. Sensitivities (not criteria): "
              + ", ".join(f"{k} {_sd_txt(v)}" for k, v in sens.items())
              + (f" (SKEW line kappa {kap['kappa']:.5f} from {KAPPA_CHAIN})" if "skew_line" in sens else
                 " (SKEW-line sensitivity not run: no SKEW series or chain calibration)")
              + (f". External check: ATM-both-phases wheel vs the actual PUT index ({atm_chk['n']} cycles): TE "
                 f"{_pu(atm_chk['te'])}/yr, corr {_f(atm_chk['corr'])}" if atm_chk else "")
              + f". Gate (the claim's pricer at IV x1.00, closes, no costs): {_gate_txt(g)}" + ("" if g["ok"] else "; the pricer misses the gate, so by the trial's rule the comparison "
                                               "does not count") + f" — {j['why']}")
    stat = {"n": j["n"], "label": MP, "cycles": [C["day0"][0], C["day1"][-1]], "gate": g,
            "sharpe_constrained": f["sharpe_a"], "sharpe_unconstrained": f["sharpe_b"], "diff": f["diff"], "ci": f["ci"],
            "p_lt": f["p_lt"], "stock_share": [float(np.mean(wc["stock"])), float(np.mean(wu["stock"]))],
            "assignments": [wc["assigned"], wu["assigned"]], "basis_floor_binds": wc["basis_floor_binds"],
            "sensitivities": {k: {"diff": v["diff"], "ci": v["ci"]} for k, v in sens.items()}, "kappa": kap,
            "atm_wheel_vs_PUT": atm_chk, "criteria": j["criteria"], "rule10": "calendar: standard monthly expiry"}
    return _out(stat, j["n"], j["verdict"], reason)


def b6b_bw_covered_put(archive):
    """T-174: MODEL-PRICED short SPX + short monthly ATM SPX put with bill interest on proceeds: CAGR < 0 in >= 90% of
    rolling 120-month windows, 1990-2026, after the BXM/PUT calibration gate."""
    miss = _missing(archive, [GSPC_B, VIX_B, DTB3_B, SPY_B, cboe_b("BXM"), cboe_b("PUT")])
    if miss:
        return miss
    fr, bills = _spx(archive), _bills(archive)
    C = cycles(fr, bills, start="1990-01-01")
    if C["n"] < 8:
        v, why = _verdict([("at least 8 monthly cycles", None)])
        return _out({"n": C["n"]}, C["n"], v, f"only {C['n']} SPX monthly cycles — {why}")
    g = _gate(archive, ("BXM", "PUT"))
    r = covered_put_model(C, 1.0)
    j = judge_window_share(r, g["ok"], _gate_name(g, "BXM (2002-) and PUT (2007-)"), 300)
    sens = {}
    for nm, rr in (("iv_x0.90", covered_put_model(C, 0.9)), ("iv_x0.81", covered_put_model(C, 0.81)),
                   ("collateral_also_earns_bills", covered_put_model(C, 1.0, collateral=True)),
                   ("short_SPX_alone", short_index_model(C)), ("short_SPX_alone_collateral_earns", short_index_model(C, True))):
        w = window_log_growth(rr, 120)
        sens[nm] = {"share_negative": float(np.mean(w < 0)) if w.size else None, "cagr_full": cagr(rr)}
    reason = (f"{MP} (Black-Scholes put at VIX/100 on ^GSPC with SPY's trailing dividend yield; no transaction costs, none "
              f"stated): {_model_window(C)}. Per unit of notional, each month: short the index and the ATM put (PUT rule: first "
              f"5-point strike at or below), the short-sale and put proceeds earn the 3-month bill, dividends are owed on the "
              f"short, the put settles on the expiry close. Full-period CAGR {_pc(cagr(r))}; {j['negative']} of {j['n']} rolling "
              f"120-month windows have CAGR < 0 (share {_f(j['share'])}; window CAGRs {_pc(j['window_cagr_range'][0])} to "
              f"{_pc(j['window_cagr_range'][1])}). Sensitivities (share negative): "
              + ", ".join(f"{k} {_f(v['share_negative'])}" for k, v in sens.items())
              + f". The trial requires the pricer to pass the BXM/PUT calibration gate first (the claim's pricer at IV x1.00, closes, "
              f"no costs): {_gate_txt(g)} — {j['why']}")
    stat = {"n": j["n"], "label": MP, "cycles": [C["day0"][0], C["day1"][-1]], "share_negative": j["share"],
            "negative_windows": j["negative"], "window_cagr_range": j["window_cagr_range"], "cagr_full": cagr(r), "gate": g,
            "sensitivities": sens, "criteria": j["criteria"], "rule10": "calendar: standard monthly expiry; every 120-month window"}
    return _out(stat, j["n"], j["verdict"], reason)


def b6b_bw_call_spread_overwrite(archive):
    """T-527: MODEL-PRICED short-ATM / long-5%-OTM call-spread overwrite vs the ATM covered call on SPX, 1990-2026: Sharpe
    difference CI > 0 in both halves, after the BXM calibration gate."""
    miss = _missing(archive, [GSPC_B, VIX_B, DTB3_B, SPY_B, cboe_b("BXM")])
    if miss:
        return miss
    fr, bills = _spx(archive), _bills(archive)
    C = cycles(fr, bills, start="1990-01-01")
    if C["n"] < 8:
        v, why = _verdict([("at least 8 monthly cycles", None)])
        return _out({"n": C["n"]}, C["n"], v, f"only {C['n']} SPX monthly cycles — {why}")
    g = _gate(archive, ("BXM",))
    ex = C["g"] - 1
    m = call_spread_model(C, 1.0)
    j = judge_gate_and_sharpe(m["cs"] - ex, m["cc"] - ex, g["ok"], _gate_name(g, "BXM (2002-)"), 400, side="gt", halves=True)
    f = j["full"]
    sens = {}
    for nm, kw in (("iv_x0.90", {"scale": 0.9}), ("iv_x0.81", {"scale": 0.81}), ("no_slippage", {"slip": 0.0})):
        mm = call_spread_model(C, **kw)
        sens[nm] = sharpe_diff_test(mm["cs"] - ex, mm["cc"] - ex, n_boot=1000)
    kap = _kappa(archive)
    if kap and kap.get("kappa") and np.isfinite(C["skew"]).all():
        mm = call_spread_model(C, kappa=kap["kappa"])
        sens["skew_wing"] = sharpe_diff_test(mm["cs"] - ex, mm["cc"] - ex, n_boot=1000)
    hv = ", ".join(f"{nm} {_sd_txt(h)}" for nm, h in zip(("first half", "second half"), j["halves"]))
    reason = (f"{MP} (Black-Scholes at VIX/100 on ^GSPC with SPY's trailing dividend yield, flat IV, which overprices the "
              f"5%-OTM wing relative to the skewed market): {_model_window(C)}. Both arms hold the index (total return) and sell "
              f"the call at the first 5-point strike at or above the index (BXM rule); the spread arm also buys the call at the "
              f"first strike at or above 1.05 x the index; premiums netted from the base; 5 bps of the index per option leg. Mean "
              f"premium ATM {np.mean(m['c1']) * 100:.2f}%, wing {np.mean(m['c2']) * 100:.2f}% of the index. Excess-return Sharpe "
              f"spread {_f(f['sharpe_a'])} vs covered call {_f(f['sharpe_b'])}: full sample {_sd_txt(f)}; {hv} (studentized paired "
              f"block bootstrap, 12-cycle blocks). Sensitivities (not criteria): " + ", ".join(f"{k} {_sd_txt(v)}" for k, v in sens.items())
              + (f" (SKEW-line wing, kappa {kap['kappa']:.5f} from {KAPPA_CHAIN})" if "skew_wing" in sens else " (SKEW wing not run)")
              + ". The trial's chain-priced re-test needs about 24 monthly cohorts of captured SPY chains (2 capture days archived). "
              f"Gate (the claim's pricer at IV x1.00, closes, no costs): {_gate_txt(g)} — {j['why']}")
    stat = {"n": j["n"], "label": MP, "cycles": [C["day0"][0], C["day1"][-1]], "gate": g, "sharpe_spread": f["sharpe_a"],
            "sharpe_cc": f["sharpe_b"], "diff": f["diff"], "ci": f["ci"],
            "halves": [{"diff": h["diff"], "ci": h["ci"]} for h in j["halves"]],
            "mean_premium": {"atm": float(np.mean(m["c1"])), "wing": float(np.mean(m["c2"]))},
            "sensitivities": {k: {"diff": v["diff"], "ci": v["ci"]} for k, v in sens.items()}, "kappa": kap,
            "criteria": j["criteria"], "rule10": "calendar: standard monthly expiry (3rd-Friday rolls)"}
    return _out(stat, j["n"], j["verdict"], reason)


HARNESSES = {
    "b6b_bw_putwrite_vs_spy": b6b_bw_putwrite_vs_spy,
    "b6b_bw_bxm_alpha": b6b_bw_bxm_alpha,
    "b6b_bw_bxmd_vs_bxm": b6b_bw_bxmd_vs_bxm,
    "b6b_bw_bxmw_vs_bxm": b6b_bw_bxmw_vs_bxm,
    "b6b_bw_bxmh_vs_bxm": b6b_bw_bxmh_vs_bxm,
    "b6b_bw_put_vs_bxm": b6b_bw_put_vs_bxm,
    "b6b_bw_wheel_basis": b6b_bw_wheel_basis,
    "b6b_bw_cmbo_vs_bxy": b6b_bw_cmbo_vs_bxy,
    "b6b_bw_covered_put": b6b_bw_covered_put,
    "b6b_bw_put_bxm_return_gap": b6b_bw_put_bxm_return_gap,
    "b6b_bw_call_spread_overwrite": b6b_bw_call_spread_overwrite,
}

THEORY_MAP = {
    "T-128": "b6b_bw_putwrite_vs_spy",
    "T-161": "b6b_bw_bxm_alpha",
    "T-162": "b6b_bw_bxmd_vs_bxm",
    "T-163": "b6b_bw_bxmw_vs_bxm",
    "T-164": "b6b_bw_bxmh_vs_bxm",
    "T-170": "b6b_bw_put_vs_bxm",
    "T-171": "b6b_bw_wheel_basis",
    "T-172": "b6b_bw_cmbo_vs_bxy",
    "T-174": "b6b_bw_covered_put",
    "T-202": "b6b_bw_put_bxm_return_gap",
    "T-527": "b6b_bw_call_spread_overwrite",
}
