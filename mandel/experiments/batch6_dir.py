"""
Batch 6, directional and ratio structures: jade lizard, 1x2 call ratio, 1-3-2 Christmas tree, stock repair, SKEW-timed risk
reversal, LEAPS and deep-ITM calls as stock substitutes, ZEBRA and 3%-OTM digital puts on SPY.
==========================================================================================================================

Nine options-library claims (T-113, T-133, T-135, T-136, T-138, T-139, T-140, T-154, T-516), each tested on its own claim,
trial.pass and trial.min_n. Every result is MODEL-PRICED: legs are priced by Black-Scholes at the IV proxy the claim names
(VIX/100 flat, or VIX3M/100 where the claim asks for it), never at traded quotes. The archive holds only two captured chain
days, so no traded version can be tested here; where the economics hinge on the IV level the reason reports the result at
IV scales 0.81 and 0.90 (the captured ATM IV / VIX ratio was about 0.81 on 2026-10-14) and says a traded test needs chain
history. The scales are sensitivities, never criteria: the verdict is for the claim's own proxy (scale 1.00).

Conventions (house rules).
  * Prices: SPY RAW closes (``close``, split-adjusted, not dividend-adjusted) for strikes and settlement. Cash dividends come
    from the step in the adjclose/close ratio on each ex-date: D = close(day before) * (1 - ratio(day before) / ratio(day)).
    SPY goes ex on the third Friday of Mar/Jun/Sep/Dec. When an ex-date falls inside an option's life (after the entry close,
    on or before the expiry close) the option is priced on the escrowed-dividend forward: Black-Scholes with spot
    S - PV(D) and q = 0. The amounts are the realised ones, treated as known at entry (SPY's schedule is fixed and the amount
    passes through dividends the constituents have declared); the error is a few basis points of spot per year.
  * Holding SPY (T-139, T-140, T-154) is total return (adjclose), the same dividend convention as the forward pricing.
  * Rates: FRED DTB3 is a discount yield published the next day, so a decision on day d uses the latest print dated before d,
    converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365). Bills (and any premium or cash leg carried to
    expiry) accrue day by day at the rate known at the start of each day (rate[t-1] over (t-1, t]).
  * IV and SKEW: CBOE index closes, known at the close of their day, used at that close. VIX3M starts on 2009-09-18 in the
    archive; claims that ask for VIX3M (T-136, T-139) use VIX before that and say so.

Entry calendars (house rule 10: a verdict must not depend on an arbitrary grid phase).
  * (a) A claim that names an expiry calendar is built on it. SPY's standard monthly expiry is the third Friday, or the
    prior session when that Friday is an exchange holiday. T-154 ("monthly 30-DTE") enters at the last session on or before
    30 calendar days ahead of each monthly expiry and settles at the expiry close; T-140 ("monthly-rolled") buys at one
    monthly expiry close and rolls at the next (28 or 35 days). The 21-session grid is reported for them as a robustness
    check only.
  * (b) A claim with a tenor but no calendar (T-113, T-133, T-135, T-138, T-516: 1-month / 21-day cycles; T-139: 1-year
    cycles) has hold equally valid start offsets for its non-overlapping grid. The PRIMARY statistic is the pooled
    all-offset estimate: one cycle entered at every valid daily close (overlapping holds), circular block bootstrap of the
    claimed statistic with blocks of 2 x hold days (studentized where the trial asks for it). Pass, fail and decisive are
    judged on it. The reason also reports, over every start offset of the non-overlapping grid, the min/max of the
    statistic and of its bound and how many offsets pass (per-offset CIs use blocks of 6 monthly cycles, or 2 annual cycles).
    n stays in the claim's units: the number of distinct non-overlapping holds in the window.
  * (c) T-136 is an event study on data-defined drawdown days, not a cycle grid; rule 10 does not apply.
  * A session without an IV print uses the last print (known at that close). T = calendar days to the expiry close / 365.

Statistics. CIs are 95% two-sided circular block bootstraps (2000 resamples, seed 0) of the statistic the claim names:
percentile unless the trial names a studentized interval (T-136, T-138: bootstrap-t with a Bartlett long-run s.e.).
Differences are bootstrapped PAIRED on one timeline (a per-cycle difference series, or for top-minus-bottom SKEW quintiles a
resample of whole blocks of entries with their labels).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented ->
at best inconclusive; supported only when every criterion is implemented and passes. Below trial.min_n (in the claim's own
units) the verdict is never supported, and a failing criterion counts only when its interval lies wholly on the wrong side.

Why not ``structures.run_structure``: it prices with a constant q, the same-day DTB3 print and r = ln(1 + d), which the house
rules replace (dividend forward, prior print, discount-yield conversion). This module keeps its cycle logic but prices the
legs with ``mandel.options.bs`` and settles them with ``mandel.options.payoff.Position``.
"""

from __future__ import annotations

import bisect
import math
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.structure_claims import _ci_t
from mandel.experiments.underlying2 import _mdd, _mean_ci, _verdict
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.options.payoff import Leg, Position
from mandel.validation.backtest_eval import _hac_var

MONTH = 21                     # trading days per monthly cycle
YEAR = 252                     # trading days per annual cycle; equity annualisation
QUARTER = 63                   # stock-repair horizon and re-arm gap
BLOCK = 6                      # bootstrap block for non-overlapping monthly cycles
ANNUAL_BLOCK = 2               # bootstrap block for non-overlapping annual cycles (per-offset reports)
N_BOOT = 2000
SCALES = (0.81, 0.90)          # IV-scale sensitivities (not criteria)
START = "1993-01-01"
DTE = 30                       # T-154 entry: about 30 calendar days before the monthly expiry
MODEL = "MODEL-PRICED, no transaction costs (none stated in the claim)"
CHAIN_NOTE = ("the trial's control 'recheck on chain mids at 60 days' is still pending: the archive holds 2 chain days, so a "
              "traded test needs chain history")


# ------------------------------------------------------------------------------------------------ data access --

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
    except KeyError:
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str):
    """Rows of a bundle that were available when the bundle was captured."""
    e = archive.get(name)
    cap = getattr(e, "created_at", None) if e is not None else None
    return (r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))


def _index(archive, name: str) -> dict:
    return _cached(archive, ("index", name), lambda: index_closes(_rows(archive, name)))


def _prices(archive, symbol: str):
    """(days, raw closes, adjcloses) of daily-history-<symbol>; a missing adjclose carries the previous adj/close ratio."""
    def load():
        name = "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)
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
    return _cached(archive, ("px", symbol), load)


# --------------------------------------------------------------------------------------------- market panel --

def cont_rate(discount_pct: float) -> float:
    """Continuous rate from a 3-month bill discount yield in percent (FRED DTB3)."""
    return -math.log(1.0 - discount_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def dividends_from_adj(close, adj, tol: float = 1e-4, cap: float = 0.05) -> np.ndarray:
    """Cash dividend D[i] going ex on day i, from the adjclose/close ratio step: D = close[i-1] * (1 - ratio[i-1]/ratio[i]).
    Steps under ``tol`` are rounding and steps over ``cap`` are data errors."""
    close = np.asarray(close, float); ratio = np.asarray(adj, float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if np.isfinite(ratio[i]) and np.isfinite(ratio[i - 1]) and ratio[i] > 0:
            y = 1.0 - ratio[i - 1] / ratio[i]
            if tol < y < cap:
                out[i] = close[i - 1] * y
    return out


def iv_series(days: Sequence[str], primary: dict, fallback: Optional[dict] = None) -> np.ndarray:
    """IV (fraction) per day: ``primary`` from its first print on (carrying its last print over a missing day), ``fallback``
    before that (carried the same way). NaN until the first print."""
    first = min(primary) if primary else None
    out = np.full(len(days), np.nan); last_p = last_f = float("nan")
    for i, d in enumerate(days):
        if fallback is not None and d in fallback:
            last_f = float(fallback[d])
        if d in primary:
            last_p = float(primary[d])
        use_p = fallback is None or (first is not None and d >= first)
        out[i] = (last_p if use_p else last_f) / 100.0
    return out


@dataclass
class Market:
    days: list
    close: np.ndarray          # raw closes
    adj: np.ndarray            # total-return closes
    div: np.ndarray            # cash dividend going ex on day i (0 otherwise)
    cal: np.ndarray            # calendar day ordinal
    rate: np.ndarray           # continuous bill rate known at day i's close (latest DTB3 print dated before day i)
    ex_idx: list
    cum: Optional[np.ndarray] = field(default=None, repr=False)     # cumulative log bill accrual (lazy)

    def pv_div(self, a: int, b: int, r: float) -> float:
        """PV at day a of the dividends going ex in (a, b]."""
        lo, hi = bisect.bisect_right(self.ex_idx, a), bisect.bisect_right(self.ex_idx, b)
        return float(sum(self.div[k] * math.exp(-r * (self.cal[k] - self.cal[a]) / 365.0) for k in self.ex_idx[lo:hi]))

    def pv_div_path(self, t: np.ndarray, b: int) -> np.ndarray:
        """PV at each day t (t <= b) of the dividends going ex in (t, b], each discounted at rate[t]."""
        out = np.zeros(t.size)
        lo, hi = bisect.bisect_right(self.ex_idx, int(t.min())), bisect.bisect_right(self.ex_idx, b)
        for k in self.ex_idx[lo:hi]:
            m = t < k
            out[m] += self.div[k] * np.exp(-self.rate[t[m]] * (self.cal[k] - self.cal[t[m]]) / 365.0)
        return out

    def accrual(self, a, b) -> np.ndarray:
        """Bill growth factor from day a's close to day b's close, accruing day by day at the rate known at the start of each
        day: exp(sum over t in (a, b] of rate[t-1] * (cal[t] - cal[t-1]) / 365)."""
        if self.cum is None:
            g = np.zeros(len(self.days))
            if len(self.days) > 1:
                g[1:] = np.nan_to_num(self.rate[:-1]) * np.diff(self.cal) / 365.0
            self.cum = np.cumsum(g)
        return np.exp(self.cum[np.asarray(b, int)] - self.cum[np.asarray(a, int)])


def make_market(days: Sequence[str], close, adj, bills: dict) -> Market:
    """``bills`` = {day: DTB3 discount yield in percent}."""
    days = list(days); close = np.asarray(close, float); adj = np.asarray(adj, float)
    div = dividends_from_adj(close, adj)
    bd = sorted(bills); bv = [cont_rate(float(bills[d])) for d in bd]
    rate = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        j = bisect.bisect_left(bd, d) - 1                       # latest print dated strictly before d
        if j >= 0:
            rate[i] = bv[j]
    cal = np.array([date.fromisoformat(d).toordinal() for d in days], float)
    return Market(days, close, adj, div, cal, rate, [int(i) for i in np.nonzero(div > 0)[0]])


def _valid(m: Market, iv: np.ndarray, i: int) -> bool:
    return bool(np.isfinite(iv[i]) and iv[i] > 0 and np.isfinite(m.rate[i]))


def cycle_entries(m: Market, iv: np.ndarray, hold: int, start: str = START, step: Optional[int] = None) -> list:
    """Non-overlapping entry indices (each ``step`` sessions after the previous, default ``hold``) from ``start``; a day
    without an IV or a rate is skipped and the next day enters. ``step=1`` gives every valid daily entry."""
    step = step or hold
    n = len(m.days); i = bisect.bisect_left(m.days, start); out = []
    while i + hold < n:
        if _valid(m, iv, i):
            out.append(i); i += step
        else:
            i += 1
    return out


def cycle_panel(m: Market, iv: np.ndarray, hold: int = MONTH, start: str = START, entries: Optional[list] = None,
                expiries: Optional[list] = None) -> dict:
    """Per-cycle arrays: a (entry index), b (expiry index: ``expiries`` or a + hold), day, S (raw close), F (S - PV of
    dividends in the life), ST (raw close at expiry), T (years), r, sig (IV at entry), tr (SPY total-return factor over the
    cycle), acc (bill growth factor over the cycle, day by day)."""
    a = np.array(entries if entries is not None else cycle_entries(m, iv, hold, start), int)
    b = np.array(expiries, int) if expiries is not None else a + hold
    r = m.rate[a]
    S = m.close[a]
    F = S - np.array([m.pv_div(int(x), int(y), float(z)) for x, y, z in zip(a, b, r)])
    return {"a": a, "b": b, "day": [m.days[i] for i in a], "S": S, "F": F, "ST": m.close[b],
            "T": (m.cal[b] - m.cal[a]) / 365.0, "r": r, "sig": iv[a], "tr": m.adj[b] / m.adj[a],
            "acc": m.accrual(a, b) if a.size else np.array([]), "n": int(a.size)}


# ----------------------------------------------------------------------------------- rule 10: entry calendars --

@dataclass
class Grid:
    """The cycles a claim is tested on. ``kind`` 'pooled' (rule 10b): P holds one cycle per valid daily entry (overlapping)
    and offsets[k] the positions in P of the non-overlapping grid that starts k sessions after the first entry;
    'calendar' (rule 10a): P holds the claim's calendar cycles and there are no offsets. ``n_holds`` is the claim-unit count
    (distinct non-overlapping holds in the window, or calendar cycles); ``block`` the primary bootstrap block (2 x hold
    entries when pooled) and ``off_block`` the per-offset block in cycles."""
    P: dict
    offsets: list
    hold: int
    n_holds: int
    kind: str
    label: str
    block: int
    off_block: int

    @property
    def pooled(self) -> bool:
        return self.kind == "pooled"


def offsets_grid(m: Market, iv: np.ndarray, hold: int = MONTH, start: str = START, off_block: int = BLOCK) -> Grid:
    """Rule 10(b): every valid daily entry (pooled) plus each start offset's non-overlapping grid."""
    daily = cycle_entries(m, iv, hold, start, step=1)
    P = cycle_panel(m, iv, hold, entries=daily)
    offs = []
    if daily:
        pos = {a: j for j, a in enumerate(daily)}
        i0 = daily[0]
        for k in range(hold):
            if i0 + k + hold >= len(m.days):
                break
            offs.append(np.array([pos[a] for a in cycle_entries(m, iv, hold, m.days[i0 + k])], int))
    n_holds = int((P["b"].max() - P["a"].min()) // hold) if daily else 0
    return Grid(P, offs, hold, n_holds, "pooled", f"{hold}-session grid, all start offsets pooled", 2 * hold, off_block)


def calendar_grid(m: Market, iv: np.ndarray, entries: list, expiries: list, label: str) -> Grid:
    """Rule 10(a): the claim's calendar cycles (entries[k] settles at expiries[k])."""
    P = cycle_panel(m, iv, entries=entries, expiries=expiries)
    hold = int(np.median(P["b"] - P["a"])) if P["n"] else MONTH
    return Grid(P, [], hold, P["n"], "calendar", label, BLOCK, BLOCK)


def third_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7 + 14)


def monthly_expiries(m: Market, start: str = START) -> list:
    """Session index of each SPY standard monthly expiry in the data: the third Friday, or the prior session when the third
    Friday is not a trading day (exchange holiday). Months whose third Friday is after the last day are dropped."""
    if not m.days:
        return []
    out = []; y, mo = int(m.days[0][:4]), int(m.days[0][5:7]); last = date.fromisoformat(m.days[-1])
    while date(y, mo, 1) <= last:
        tf = third_friday(y, mo)
        if tf <= last:
            j = bisect.bisect_right(m.days, tf.isoformat()) - 1
            if j >= 0 and m.days[j] >= start and tf.toordinal() - m.cal[j] <= 3:
                out.append(j)
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return out


def dte_cycles(m: Market, iv: np.ndarray, expiries: list, dte: int = DTE, start: str = START) -> tuple:
    """(entries, expiries): for each expiry the last session on or before ``dte`` calendar days ahead of it (about ``dte``
    DTE), stepping back over a session without an IV or a rate (at most 3 sessions); expiries without such an entry on or
    after ``start`` are dropped."""
    ents, exps = [], []
    for x in expiries:
        j = int(np.searchsorted(m.cal, m.cal[x] - dte, side="right")) - 1
        for _ in range(4):
            if j < 0 or m.days[j] < start or _valid(m, iv, j):
                break
            j -= 1
        if j >= 0 and m.days[j] >= start and _valid(m, iv, j) and j < x:
            ents.append(j); exps.append(int(x))
    return ents, exps


def roll_cycles(m: Market, iv: np.ndarray, expiries: list) -> tuple:
    """(entries, expiries) of an expiry-to-expiry roll: buy at one monthly expiry close, settle at the next."""
    ents, exps = [], []
    for a, b in zip(expiries[:-1], expiries[1:]):
        if _valid(m, iv, a):
            ents.append(int(a)); exps.append(int(b))
    return ents, exps


def _grid_txt(G: Grid) -> str:
    P = G.P
    if not P["n"]:
        return f"{G.label}: no cycles"
    if G.pooled:
        return (f"rule 10(b), the claim names no entry calendar: primary statistic pooled over all {len(G.offsets)} start "
                f"offsets of the non-overlapping {G.hold}-session grid = {P['n']} overlapping daily entries {P['day'][0]} to "
                f"{P['day'][-1]} (circular block bootstrap, {G.block}-day blocks = 2 x hold); n = {G.n_holds} distinct "
                f"{G.hold}-session holds in the window")
    dte = np.round(P["T"] * 365).astype(int)
    return (f"rule 10(a): {G.label}, {P['n']} cycles {P['day'][0]} to {P['day'][-1]} ({dte.min()}-{dte.max()} calendar "
            f"days to expiry)")


def _summ(rows: list, stat: str, bound: str, ok: str) -> Optional[dict]:
    """Per-offset summary: offsets passing ``ok``, and the min/max of ``stat`` and of ``bound`` over offsets."""
    if not rows:
        return None
    def rng(k):
        v = np.array([np.nan if r[k] is None else r[k] for r in rows], float); v = v[np.isfinite(v)]
        return [float(v.min()), float(v.max())] if v.size else [None, None]
    return {"offsets": len(rows), "pass": int(sum(bool(r[ok]) for r in rows)), "stat": rng(stat), "bound": rng(bound)}


def _summ_txt(s: Optional[dict], what: str, bound_name: str, f=None) -> str:
    if not s:
        return ""
    f = f or (lambda v: _p(v, 2))
    return (f"{what}: {s['pass']} of {s['offsets']} start offsets pass (per-offset {f(s['stat'][0])} to {f(s['stat'][1])}, "
            f"{bound_name} {f(s['bound'][0])} to {f(s['bound'][1])})")


# -------------------------------------------------------------------------------------------- pricing helpers --

def _px(F, K, T, r, sig, kind):
    return np.asarray(bs.price(F, K, T, r, sig, kind, 0.0), float)


def _strikes_for_delta(P: dict, sig, delta: float, kind: str) -> np.ndarray:
    return np.array([bs.strike_for_delta(f, t, r, s, delta, kind, 0.0) for f, t, r, s in zip(P["F"], P["T"], P["r"], sig)])


def _ncdf(x):
    return np.asarray(bs._ncdf(x), float)


def _d2(F, K, T, r, sig):
    return (np.log(F / K) + (r - 0.5 * sig ** 2) * T) / (sig * np.sqrt(T))


def settle(legs: list, ST) -> np.ndarray:
    """Payoff at expiry per cycle. legs: list of (kind, side, qty, strikes array); payoff via payoff.Position."""
    ST = np.asarray(ST, float); out = np.empty(ST.size)
    for j in range(ST.size):
        pos = Position([Leg(k, s, q, strike=float(K[j])) for k, s, q, K in legs])
        out[j] = float(pos.payoff(ST[j]))
    return out


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple:
    """Exact two-sided binomial CI."""
    def cdf(kk, p):
        if kk < 0:
            return 0.0
        if p <= 0:
            return 1.0
        if p >= 1:
            return 1.0 if kk >= n else 0.0
        lp, lq = math.log(p), math.log1p(-p)
        return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                            for i in range(0, kk + 1)))
    def solve(f, target):
        lo, hi = 0.0, 1.0                                   # f decreasing in p
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: -(1 - cdf(k - 1, p)), -alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p), alpha / 2)
    return lower, upper


# ------------------------------------------------------------------------------------------------ statistics --

def _ci(x, block: int = BLOCK, n_boot: int = N_BOOT) -> tuple:
    x = np.asarray(x, float)
    if x.size < 2:
        return float("nan"), float("nan")
    return _mean_ci(x, block, n_boot)


def _ci_stud(x, block: int = BLOCK, n_boot: int = N_BOOT) -> tuple:
    x = np.asarray(x, float)
    if x.size < 3:
        return float("nan"), float("nan")
    return _ci_t(x, block, n_boot)


def _boot_stat(n: int, fn, block: int, n_boot: int = N_BOOT, seed: int = 0, chunk: int = 100) -> np.ndarray:
    """Circular block bootstrap distribution of fn(idx) where idx is an (k, n) index matrix (vectorised in chunks)."""
    rng = np.random.default_rng(seed); nb = math.ceil(n / block); out = []
    for s in range(0, n_boot, chunk):
        k = min(chunk, n_boot - s)
        starts = rng.integers(0, n, (k, nb))
        idx = ((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n]) % n
        out.append(fn(idx))
    return np.concatenate(out)


def _q(dist) -> tuple:
    d = np.asarray(dist, float); d = d[np.isfinite(d)]
    return (float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))) if d.size else (float("nan"), float("nan"))


def _ci_masked(xf, block: int, n_boot: int = N_BOOT) -> tuple:
    """CI of the mean of the finite entries of ``xf`` (NaN = cycle not counted), resampling every entry's block so the
    resampled mean is over the counted entries that fall in it."""
    xf = np.asarray(xf, float); fin = np.isfinite(xf)
    if fin.sum() < 2:
        return float("nan"), float("nan")
    if fin.all():
        return _ci(xf, block, n_boot)
    v = np.where(fin, xf, 0.0); w = fin.astype(float)
    return _q(_boot_stat(xf.size, lambda ix: v[ix].sum(axis=1) / np.maximum(w[ix].sum(axis=1), 1.0), block, n_boot))


def ci_t_group_diff(x, g1, g2, block: int = BLOCK, n_boot: int = N_BOOT, seed: int = 0) -> tuple:
    """Studentized circular block bootstrap of mean(x | g1) - mean(x | g2) on one timeline: resample whole periods with their
    group labels; each resample is studentized by the Bartlett long-run s.e. of its influence series
    (x - m1)/p1 on g1, -(x - m2)/p2 on g2, 0 elsewhere. Returns (difference, lower, upper)."""
    x = np.asarray(x, float); g1 = np.asarray(g1, bool); g2 = np.asarray(g2, bool); n = x.size
    def est(xs, a, b):
        if a.sum() < 2 or b.sum() < 2:
            return float("nan"), float("nan")
        p1, p2 = a.mean(), b.mean(); m1, m2 = xs[a].mean(), xs[b].mean()
        infl = np.where(a, (xs - m1) / p1, 0.0) - np.where(b, (xs - m2) / p2, 0.0)
        return float(m1 - m2), math.sqrt(float(_hac_var(infl[None, :], block)[0]) / n)
    d0, s0 = est(x, g1, g2)
    if not np.isfinite(d0):
        return d0, float("nan"), float("nan")
    rng = np.random.default_rng(seed); nb = math.ceil(n / block); ts, ds = [], []
    for _ in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        d, s = est(x[idx], g1[idx], g2[idx])
        if np.isfinite(d):
            ds.append(d)
            if s > 1e-12:
                ts.append((d - d0) / s)
    if not s0 > 1e-12 or len(ts) < 0.9 * n_boot:              # degenerate (no within-group spread): percentile interval
        return d0, float(np.quantile(ds, 0.025)), float(np.quantile(ds, 0.975))
    t = np.array(ts)
    return d0, d0 - float(np.quantile(t, 0.975)) * s0, d0 - float(np.quantile(t, 0.025)) * s0


class Criteria:
    """Criteria with the min_n rule: below min_n a failing criterion stands only when it fails decisively."""

    def __init__(self):
        self.items, self.decisive = [], []

    def add(self, name: str, ok, decisive: bool = False):
        self.items.append((name, None if ok is None else bool(ok))); self.decisive.append(bool(decisive))

    def ci(self, name: str, lo, hi, side: str, thr: float = 0.0):
        """side 'lower_gt': pass if lo > thr (decisive failure if hi < thr); 'upper_lt': pass if hi < thr (decisive if lo > thr)."""
        if not (np.isfinite(lo) and np.isfinite(hi)):
            self.add(name, None); return
        if side == "lower_gt":
            self.add(name, lo > thr, hi < thr)
        else:
            self.add(name, hi < thr, lo > thr)

    def finish(self, n: int, min_n: int, unit: str) -> tuple:
        crit = list(self.items)
        if n < min_n:
            crit = [(nm, None if (ok is not None and not ok and not dec) else ok) for (nm, ok), dec in zip(crit, self.decisive)]
        crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
        return _verdict(crit)


def _mean_rule10(G: Grid, x, side: str, thr: float = 0.0, n_boot: int = N_BOOT) -> dict:
    """A mean criterion under rule 10 (percentile intervals): the primary mean and CI (pooled entries with ``G.block``, or
    the calendar cycles with BLOCK) and the per-offset rows (mean and CI over each start offset's non-overlapping cycles,
    ``G.off_block``). NaN entries of ``x`` are cycles not counted (e.g. skipped)."""
    x = np.asarray(x, float); fin = np.isfinite(x)
    ci = lambda v, b: _ci(v, b, n_boot)
    lo, hi = ci(x, G.block) if fin.all() else _ci_masked(x, G.block, n_boot)
    mean = float(x[fin].mean()) if fin.any() else float("nan")
    rows = []
    for idx in G.offsets:
        xi = x[idx]; xi = xi[np.isfinite(xi)]
        l, h = ci(xi, G.off_block)
        ok = (l > thr) if side == "lower_gt" else (h < thr)
        rows.append({"n": int(xi.size), "mean": float(xi.mean()) if xi.size else None, "lo": l, "hi": h,
                     "ok": bool(np.isfinite(l) and np.isfinite(h) and ok)})
    s = _summ(rows, "mean", "lo" if side == "lower_gt" else "hi", "ok")
    return {"mean": mean, "lo": lo, "hi": hi, "rows": rows, "summary": s}


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


def _p(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _rng(lo, hi, nd: int = 3) -> str:
    return f"95% CI {_p(lo, nd)} to {_p(hi, nd)}"


def _halves(x) -> tuple:
    x = np.asarray(x, float); h = x.size // 2
    return (float(x[:h].mean()) if h else float("nan"), float(x[h:].mean()) if x.size - h else float("nan"))


def _sens(fn, key: str = "x") -> dict:
    out = {}
    for s in SCALES:
        v = np.asarray(fn(s)[key], float); v = v[np.isfinite(v)]
        out[f"{s:.2f}"] = float(v.mean()) if v.size else None
    return out


def _sens_txt(sens: dict, nd: int = 3) -> str:
    return ", ".join(f"s={k} {_p(v, nd)}" for k, v in sens.items())


def _rule10(G: Grid, **summaries) -> dict:
    return {"kind": G.kind, "label": G.label, "hold": G.hold, "entries": G.P["n"], "n_holds": G.n_holds,
            "start_offsets": len(G.offsets), "bootstrap_block": G.block, "per_offset": summaries}


# ----------------------------------------------------------------------------------------- T-113 jade lizard --

def jade_lizard(P: dict, scale: float = 1.0, width: float = 0.01, delta: float = 0.30, margin: float = 0.20) -> dict:
    """Short `delta` put + short `delta` call + long call `width`*S above it, at scale*IV. Enter only when the credit >= width*S.
    x = P&L at expiry (credit carried in bills to expiry) / (margin * S) over entered cycles; x_all over every cycle."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    Kp = _strikes_for_delta(P, sig, -delta, "put"); Kc = _strikes_for_delta(P, sig, delta, "call"); Kl = Kc + width * S
    credit = _px(F, Kp, T, r, sig, "put") + _px(F, Kc, T, r, sig, "call") - _px(F, Kl, T, r, sig, "call")
    enter = credit >= width * S
    payoff = settle([("put", "short", 1, Kp), ("call", "short", 1, Kc), ("call", "long", 1, Kl)], P["ST"])
    x_all = (credit * P["acc"] + payoff) / (margin * S)
    return {"x": x_all[enter], "x_all": x_all, "enter": enter, "credit": credit / S, "Kp": Kp / S, "Kc": Kc / S,
            "days": [d for d, e in zip(P["day"], enter) if e], "n_total": int(S.size), "n_skipped": int((~enter).sum())}


def eval_jade_lizard(G: Grid, min_n: int = 250, n_boot: int = N_BOOT) -> dict:
    P = G.P; res = jade_lizard(P); en = res["enter"]; x = res["x"]; n_ent = int(x.size)
    frac = float(en.mean()) if en.size else 0.0
    n = int(round(G.n_holds * frac)) if G.pooled else n_ent                      # entered months in the claim's units
    mr = _mean_rule10(G, np.where(en, res["x_all"], np.nan), "lower_gt", 0.0, n_boot)
    lo, hi = mr["lo"], mr["hi"]; h1, h2 = _halves(x)
    for row, idx in zip(mr["rows"], G.offsets):
        a1, a2 = _halves(res["x_all"][idx][en[idx]])
        row["halves_ok"] = bool(a1 > 0 and a2 > 0); row["both_ok"] = bool(row["ok"] and row["halves_ok"])
    s_ci, s_h = mr["summary"], _summ(mr["rows"], "mean", "lo", "halves_ok") if mr["rows"] else None
    s_both = _summ(mr["rows"], "mean", "lo", "both_ok") if mr["rows"] else None
    c = Criteria()
    c.ci("mean P&L / (0.2 S) lower CI > 0", lo, hi, "lower_gt")
    c.add("mean positive in both walk-forward halves", (h1 > 0 and h2 > 0) if n_ent >= 2 else None)
    v, why = c.finish(n, min_n, "entered months")
    sens = _sens(lambda s: jade_lizard(P, s))
    med_credit = float(np.median(res["credit"][en])) if n_ent else float("nan")
    ent_rng = ""
    if mr["rows"]:
        ne = [r["n"] for r in mr["rows"]]
        ent_rng = f"; entered per offset {min(ne)}-{max(ne)} of about {G.n_holds}"
    off = ""
    if s_ci:
        off = (f"; per start offset (non-overlapping grid, block-{G.off_block} percentile): "
               f"{_summ_txt(s_ci, 'lower CI > 0', 'lower CI')}, both halves positive in {s_h['pass']} of {s_h['offsets']}, "
               f"both criteria in {s_both['pass']} of {s_both['offsets']}{ent_rng}")
    reason = (f"{MODEL} (legs at VIX IV flat, 30-delta strikes solved at that IV on the dividend forward, r = prior DTB3 print, "
              f"the credit carried in bills to expiry at the prior prints day by day): SPY 1-month jade lizard; {_grid_txt(G)}; "
              f"{n_ent} of {res['n_total']} entries entered ({res['n_skipped']} skipped with credit < 1% of S, "
              f"{(1 - frac) * 100:.1f}%), n = {n} entered months; median credit over entered cycles {_p(med_credit, 2)} of S; "
              f"mean P&L / (0.2 S) {_p(mr['mean'])} ({_rng(lo, hi)}); walk-forward halves {_p(h1)} / {_p(h2)}{off}; "
              f"IV-scale sensitivity (not in the pass rule; short premium, so the edge hinges on the IV level): "
              f"{_sens_txt(sens)}; {CHAIN_NOTE} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entered_entries": n_ent, "n_total_entries": res["n_total"],
            "n_skipped": res["n_skipped"], "mean_per_margin": mr["mean"], "ci": [lo, hi], "halves": [h1, h2],
            "median_credit_per_spot_entered": med_credit if n_ent else None, "iv_scale_sensitivity": sens,
            "rule10": _rule10(G, ci=s_ci, halves=s_h, both=s_both), "model_priced": True, "min_n": min_n}


# ---------------------------------------------------------------------------------------- T-133 1x2 call ratio --

def zero_cost_k2(F, K1, T, r, sig):
    """K2 > K1 with 2 C(K2) = C(K1) (bisection on [K1, 4 K1]); vectorised over arrays, a float for scalar inputs."""
    F, K1, T, r, sig = np.broadcast_arrays(*(np.asarray(v, float) for v in (F, K1, T, r, sig)))
    target = _px(F, K1, T, r, sig, "call") / 2.0
    lo, hi = K1.astype(float).copy(), 4.0 * K1
    for _ in range(80):
        mid = (lo + hi) / 2
        above = _px(F, mid, T, r, sig, "call") > target
        lo, hi = np.where(above, mid, lo), np.where(above, hi, mid)
    out = (lo + hi) / 2
    return float(out) if out.ndim == 0 else out


def ratio_1x2(P: dict, scale: float = 1.0) -> dict:
    """Long 1 ATM call (K1 = S), short 2 at the zero-cost K2; x = P&L / S at expiry."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = S.copy(); K2 = np.asarray(zero_cost_k2(F, K1, T, r, sig), float).reshape(-1) if S.size else np.array([])
    net = _px(F, K1, T, r, sig, "call") - 2 * _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 1, K1), ("call", "short", 2, K2)], P["ST"])
    return {"x": (payoff - net * P["acc"]) / S, "K2": K2 / S, "vix": P["sig"] * 100}


def tail_frequency(x, mult: float = 3.0, all_months: bool = False) -> dict:
    """Months with a loss larger than ``mult`` x the median gain (median P&L of the winning months; ``all_months`` uses the
    median P&L of every month instead, reported as a reading check), with a Clopper-Pearson CI."""
    x = np.asarray(x, float); gains = x if all_months else x[x > 0]
    if gains.size == 0 or not np.median(gains) > 0:
        return {"median_gain": None, "k": 0, "n": int(x.size), "freq": None, "ci": [None, None]}
    mg = float(np.median(gains)); k = int((x < -mult * mg).sum()); lo, hi = clopper_pearson(k, x.size)
    return {"median_gain": mg, "k": k, "n": int(x.size), "freq": k / x.size, "ci": [lo, hi]}


def tail_ci_boot(x, block: int, n_boot: int = N_BOOT, mult: float = 3.0, all_months: bool = False) -> tuple:
    """Block-bootstrap CI of the tail frequency (overlapping entries): the median gain is recomputed in each resample."""
    x = np.asarray(x, float)
    if x.size < 2:
        return float("nan"), float("nan")
    def fn(ix):
        xs = x[ix]; g = xs if all_months else np.where(xs > 0, xs, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mg = np.nanmedian(g, axis=1)
        mg = np.where(mg > 0, mg, np.nan)
        return np.where(np.isfinite(mg), (xs < -mult * mg[:, None]).mean(axis=1), np.nan)
    return _q(_boot_stat(x.size, fn, block, n_boot))


def eval_ratio_1x2(G: Grid, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    P = G.P; res = ratio_1x2(P); x = res["x"]; n = G.n_holds
    mr = _mean_rule10(G, x, "lower_gt", 0.0, n_boot); lo, hi = mr["lo"], mr["hi"]
    tf = tail_frequency(x); tf_all = tail_frequency(x, all_months=True)
    if G.pooled:                                     # overlapping entries: Clopper-Pearson assumes independence
        tf["ci"] = list(tail_ci_boot(x, G.block, n_boot)); tf_all["ci"] = list(tail_ci_boot(x, G.block, n_boot, all_months=True))
    c = Criteria()
    c.ci("mean P&L / S lower CI > 0", lo, hi, "lower_gt")
    if tf["freq"] is None:
        c.add("tail frequency lower CI > 3%", None)
    else:
        c.ci("frequency of losses > 3x median gain: lower CI > 3%", tf["ci"][0], tf["ci"][1], "lower_gt", 0.03)
    v, why = c.finish(n, min_n, "months")
    for row, idx in zip(mr["rows"], G.offsets):
        t = tail_frequency(x[idx]); row["tail"] = t["freq"]; row["tail_lo"] = t["ci"][0]
        row["tail_ok"] = bool(t["freq"] is not None and t["ci"][0] > 0.03); row["both_ok"] = bool(row["ok"] and row["tail_ok"])
    s_mean = mr["summary"]
    s_tail = _summ(mr["rows"], "tail", "tail_lo", "tail_ok") if mr["rows"] else None
    s_both = _summ(mr["rows"], "mean", "lo", "both_ok") if mr["rows"] else None
    terc = {}
    if x.size >= 3:
        q1, q2 = np.quantile(res["vix"], [1 / 3, 2 / 3])
        for nm, msk in (("low", res["vix"] <= q1), ("mid", (res["vix"] > q1) & (res["vix"] <= q2)), ("high", res["vix"] > q2)):
            t = tail_frequency(x[msk]) if msk.any() else {"freq": None}
            terc[nm] = {"n": int(msk.sum()), "mean": float(x[msk].mean()) if msk.any() else None, "tail_freq": t["freq"]}
    sens = _sens(lambda s: ratio_1x2(P, s))
    tail_ci_name = f"block-{G.block} bootstrap" if G.pooled else "Clopper-Pearson"
    off = ""
    if s_mean:
        off = (f"; per start offset (non-overlapping grid; mean block-{G.off_block} percentile, tail Clopper-Pearson): "
               f"{_summ_txt(s_mean, 'mean lower CI > 0', 'lower CI', lambda v: _p(v, 3))}; "
               f"{_summ_txt(s_tail, 'tail lower CI > 3%', 'tail lower CI')}; both criteria in {s_both['pass']} of {s_both['offsets']}")
    reason = (f"{MODEL} (all legs at VIX IV flat, K2 solved for zero cost each entry on the dividend forward, any net premium "
              f"carried in bills): SPY 1-month 1x2 call ratio; {_grid_txt(G)}; median K2 "
              f"{_p(float(np.median(res['K2'])) - 1 if x.size else float('nan'), 2)} above spot; mean P&L / S {_p(mr['mean'])} "
              f"({_rng(lo, hi)}); median gain {_p(tf['median_gain'])}, losses > 3x it in {tf['k']} of {x.size} entries = "
              f"{_p(tf['freq'], 2)} ({tail_ci_name} {_rng(tf['ci'][0], tf['ci'][1], 2)}; needs lower > 3%){off}; reading check "
              f"(report only): with the median of all entries ({_p(tf_all['median_gain'])}) as the base, {_p(tf_all['freq'], 2)} "
              f"(CI {_p(tf_all['ci'][0], 2)} to {_p(tf_all['ci'][1], 2)}); by VIX tercile (mean, tail freq): "
              + ", ".join(f"{k} {_p(t['mean'])}/{_p(t['tail_freq'], 1)}" for k, t in terc.items())
              + f"; IV-scale sensitivity of the mean (not in the pass rule): {_sens_txt(sens)}; {CHAIN_NOTE} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entries": int(x.size), "mean_per_spot": mr["mean"], "ci": [lo, hi],
            "tail": tf, "tail_all_month_median": tf_all, "by_vix_tercile": terc,
            "median_k2_moneyness": float(np.median(res["K2"])) if x.size else None, "iv_scale_sensitivity": sens,
            "rule10": _rule10(G, mean=s_mean, tail=s_tail, both=s_both), "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------ T-135 Christmas tree --

def christmas_tree(P: dict, scale: float = 1.0, w: float = 0.025, anchor: float = 1.0) -> dict:
    """1-3-2 call tree: long 1 at A = anchor*S, short 3 at A + 2w, long 2 at A + 3w (w = 2.5% of S). Profit zone
    [K1 + D, K4 - D/2] (D = debit); hit = 1{zone holds the expiry close}; rn = N(d2(L)) - N(d2(U)) from the same lognormal."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = anchor * S; K3 = K1 + 2 * w * S; K4 = K1 + 3 * w * S
    D = _px(F, K1, T, r, sig, "call") - 3 * _px(F, K3, T, r, sig, "call") + 2 * _px(F, K4, T, r, sig, "call")
    L, U = K1 + D, K4 - D / 2
    ok = U > L
    rn = np.where(ok, _ncdf(_d2(F, L, T, r, sig)) - _ncdf(_d2(F, np.maximum(U, L), T, r, sig)), 0.0)
    hit = ((P["ST"] > L) & (P["ST"] < U)).astype(float)
    return {"x": hit - rn, "hit": hit, "rn": rn, "debit": D / S, "L": L / S, "U": U / S}


def eval_christmas_tree(G: Grid, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    P = G.P; res = christmas_tree(P); x = res["x"]; n = G.n_holds; ne = int(x.size)
    mr = _mean_rule10(G, x, "lower_gt", 0.0, n_boot); lo, hi = mr["lo"], mr["hi"]
    c = Criteria(); c.ci("hit rate - RN probability: lower CI > 0", lo, hi, "lower_gt")
    v, why = c.finish(n, min_n, "months")
    itm = christmas_tree(P, anchor=0.975); lo_i, hi_i = _ci(itm["x"], G.block, n_boot)
    sens = _sens(lambda s: christmas_tree(P, s))
    if ne >= 2:                                      # mechanism (report only): realised vol vs VIX and the drift
        lf = np.log(P["ST"] / P["F"]); rv = float(np.std(lf, ddof=1) / math.sqrt(float(np.mean(P["T"]))))
        iv_m = float(np.mean(P["sig"])); drift = float(np.mean(np.log(P["ST"] / P["S"])))
    else:
        rv = iv_m = drift = float("nan")
    off = (f"; per start offset (non-overlapping grid, block-{G.off_block} percentile): "
           f"{_summ_txt(mr['summary'], 'lower CI > 0', 'lower CI')}" if mr["summary"] else "")
    reason = (f"{MODEL} (4 strikes at VIX IV flat, dividend forward; zone and RN probability from the same lognormal): SPY 1-month "
              f"1-3-2 call tree, ATM anchor, w = 2.5%; {_grid_txt(G)}; median zone "
              f"[{_p(float(np.median(res['L'])) - 1 if ne else float('nan'), 2)}, {_p(float(np.median(res['U'])) - 1 if ne else float('nan'), 2)}] "
              f"around spot; hit rate {_p(res['hit'].mean() if ne else float('nan'), 1)} vs mean RN {_p(res['rn'].mean() if ne else float('nan'), 1)}: "
              f"hit - RN {_p(mr['mean'], 2)} ({_rng(lo, hi, 2)}){off}; ITM anchor (A = 0.975 S, report only) hit - RN "
              f"{_p(itm['x'].mean() if ne else float('nan'), 2)} ({_rng(lo_i, hi_i, 2)}); mechanism (report only): annualised sd "
              f"of log(S_T/F) {_p(rv, 1)} vs mean VIX IV {_p(iv_m, 1)}, mean log return per cycle {_p(drift, 2)}; hit - RN at "
              f"IV scales (not in the pass rule): {_sens_txt(sens, 2)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entries": ne, "hit_rate": float(res["hit"].mean()) if ne else None,
            "rn_mean": float(res["rn"].mean()) if ne else None, "diff": mr["mean"] if ne else None, "ci": [lo, hi],
            "itm_anchor": {"diff": float(itm["x"].mean()) if ne else None, "ci": [lo_i, hi_i]},
            "median_debit_per_spot": float(np.median(res["debit"])) if ne else None, "iv_scale_sensitivity": sens,
            "mechanism": {"realised_vol_ann": rv, "mean_iv": iv_m, "mean_log_return": drift},
            "rule10": _rule10(G, ci=mr["summary"]), "model_priced": True, "min_n": min_n}


# ---------------------------------------------------------------------------------------- T-136 stock repair --

def drawdown_episodes(close, trigger: float = 0.10, look: int = YEAR, rearm: int = QUARTER, hold: int = QUARTER,
                      new_crossing: bool = True) -> list:
    """(entry index, trailing high) for the first day of each >= trigger drawdown from the trailing ``look``-day high
    (inclusive of the day). Primary rule (``new_crossing=True``): an episode starts only when the drawdown newly crosses
    -trigger after having been above it since the last episode, with a ``rearm``-session lockout on top.
    ``new_crossing=False`` is the looser level trigger (robustness only): it re-fires every ``rearm`` sessions while the
    drawdown is still at or below -trigger, i.e. inside a drawdown already under way. Episodes whose ``hold`` window runs
    past the data are dropped."""
    c = np.asarray(close, float); n = c.size; out = []; next_ok = 0; recovered = True
    if n < look:
        return out
    hi = np.lib.stride_tricks.sliding_window_view(c, look).max(axis=1)          # hi[j] = max(c[j : j + look])
    for i in range(look - 1, n - hold):
        H = hi[i - look + 1]; dd = c[i] / H - 1
        if dd > -trigger:
            recovered = True
        if i >= next_ok and dd <= -trigger and (recovered or not new_crossing):
            out.append((i, float(H))); next_ok = i + rearm; recovered = False
    return out


def drawdown_refires(close, episodes: list, trigger: float = 0.10, look: int = YEAR) -> tuple:
    """(re-fires, spells with re-fires, distinct spells hit): an episode is a re-fire when it falls inside a continuous spell of
    drawdown <= -trigger (from the trailing ``look``-day high) that already holds an earlier episode."""
    c = np.asarray(close, float)
    if c.size < look or not episodes:
        return 0, 0, 0
    hi = np.lib.stride_tricks.sliding_window_view(c, look).max(axis=1)
    below = np.zeros(c.size, bool); below[look - 1:] = c[look - 1:] / hi - 1 <= -trigger
    spell = np.cumsum(np.r_[below[0], below[1:] & ~below[:-1]])                   # spell id, constant within a run
    counts: dict = {}
    for i, _ in episodes:
        counts[int(spell[i])] = counts.get(int(spell[i]), 0) + 1
    return sum(v - 1 for v in counts.values()), sum(1 for v in counts.values() if v > 1), len(counts)


def stock_repair(m: Market, iv: np.ndarray, episodes: list, hold: int = QUARTER, scale: float = 1.0) -> dict:
    """Stock + long 1 ATM call + short 2 calls at K2 = (B + S)/2; x = (repair - hold) P&L / S = the embedded 1x2 call ratio
    (net premium carried in bills to expiry)."""
    a = np.array([e[0] for e in episodes], int)
    if a.size == 0:
        return {"x": np.array([]), "net": np.array([]), "days": [], "k2": np.array([])}
    B = np.array([e[1] for e in episodes]); P = cycle_panel(m, iv, hold, entries=list(a))
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = S.copy(); K2 = (B + S) / 2
    net = _px(F, K1, T, r, sig, "call") - 2 * _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 1, K1), ("call", "short", 2, K2)], P["ST"])
    return {"x": (payoff - net * P["acc"]) / S, "net": net / S, "days": P["day"], "k2": K2 / S}


def eval_stock_repair(m: Market, iv: np.ndarray, min_n: int = 30, n_boot: int = N_BOOT, block: int = 2,
                      second: Optional[tuple] = None, iv_note: str = "") -> dict:
    """Primary episodes: the first day each >= 10% drawdown newly crosses -10% (63-session lockout on top); min_n counts those
    drawdown episodes. The 63-session level-trigger re-arm (re-fires inside a continuing drawdown) is a robustness check.
    ``second`` = (label, Market, iv) for the QQQ sample (reported, not a criterion). Rule 10 does not apply (event study on
    data-defined drawdown days, no cycle grid)."""
    eps = drawdown_episodes(m.close, new_crossing=True); res = stock_repair(m, iv, eps); x = res["x"]; n = int(x.size)
    lo, hi = _ci_stud(x, block, n_boot)
    c = Criteria(); c.ci("mean (repair - hold) / S lower CI > 0", lo, hi, "lower_gt")
    v, why = c.finish(n, min_n, "drawdown episodes")
    sd = float(x.std(ddof=1)) if n > 1 else float("nan"); mde = 2.8016 * sd / math.sqrt(n) if n > 1 else float("nan")
    eps_l = drawdown_episodes(m.close, new_crossing=False); alt = stock_repair(m, iv, eps_l); xa = alt["x"]; na = int(xa.size)
    lo_a, hi_a = _ci_stud(xa, block, n_boot)
    ca = Criteria(); ca.ci("mean (repair - hold) / S lower CI > 0", lo_a, hi_a, "lower_gt")
    v_a, _ = ca.finish(na, min_n, "episodes")
    ref, ref_sp, _ = drawdown_refires(m.close, eps_l)
    sens = _sens(lambda s: stock_repair(m, iv, eps, scale=s))
    sec_txt, sec = "", None
    if second is not None:
        lab, m2, iv2 = second; r2 = stock_repair(m2, iv2, drawdown_episodes(m2.close, new_crossing=True)); x2 = r2["x"]
        l2, h2 = _ci_stud(x2, block, n_boot)
        sec = {"label": lab, "n": int(x2.size), "mean": float(x2.mean()) if x2.size else None, "ci": [l2, h2]}
        sec_txt = (f"; {lab} (second sample, same first-crossing rule, overlaps SPY in time, not in the pass rule): {x2.size} "
                   f"episodes, mean {_p(x2.mean() if x2.size else float('nan'), 2)} ({_rng(l2, h2, 2)})")
    short = (f"; {n} drawdown episodes is {min_n - n} short of min_n {min_n}, and the CI failure is not decisive (upper bound "
             f"above 0), so the sample cannot decide the claim" if n < min_n and np.isfinite(hi) and lo <= 0 <= hi else
             (f"; {n} drawdown episodes is {min_n - n} short of min_n {min_n}" if n < min_n else ""))
    reason = (f"{MODEL} (calls at VIX3M IV{iv_note}, flat; dividend forward; raw closes; net premium carried in bills): {n} SPY "
              f"drawdown episodes (first day the drawdown from the trailing 252-day high newly crosses -10% after having been "
              f"above it, 63-session lockout; rule 10(c): an event study on data-defined days, no cycle grid), "
              f"{res['days'][0] if n else ''} to {res['days'][-1] if n else ''}; K2 = (B + S)/2 median "
              f"{_p(float(np.median(res['k2'])) - 1 if n else float('nan'), 2)} above "
              f"spot; median net premium {_p(float(np.median(res['net'])) if n else float('nan'), 2)} of S (negative = credit; the "
              f"fixed K2 rule is only roughly zero-cost); mean (repair - hold) / S = 1x2 ratio P&L {_p(x.mean() if n else float('nan'), 2)} "
              f"(studentized block-{block} bootstrap {_rng(lo, hi, 2)}){short}; power: sd {_p(sd, 2)}, minimum detectable mean at "
              f"80% power {_p(mde, 2)}; robustness (not the pass rule): the 63-session level-trigger re-arm, which re-fires while "
              f"the drawdown is still at or below -10%, gives {na} episodes, of which {ref} are re-fires inside {ref_sp} continuing "
              f"drawdown spells, mean {_p(xa.mean() if na else float('nan'), 2)} ({_rng(lo_a, hi_a, 2)}), verdict under that "
              f"reading {v_a}{sec_txt}; IV-scale sensitivity (not in the pass rule; a traded test needs chain history): "
              f"{_sens_txt(sens, 2)} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "episode_rule": "first crossing of -10% after being above it, 63-session lockout",
            "mean": float(x.mean()) if n else None, "ci": [lo, hi],
            "episode_days": res["days"], "sd": sd, "min_detectable_mean_80pct": mde,
            "rearm_level_trigger_variant": {"n": na, "mean": float(xa.mean()) if na else None, "ci": [lo_a, hi_a],
                                            "verdict": v_a, "refires": ref, "spells_with_refires": ref_sp},
            "second_sample": sec, "iv_scale_sensitivity": sens,
            "rule10": {"kind": "not applicable", "why": "event study on data-defined drawdown days, no cycle grid"},
            "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------- T-138 SKEW-timed risk reversal --

def risk_reversal(P: dict, scale: float = 1.0, up: float = 1.05, dn: float = 0.95) -> dict:
    """Long call at up*S, short put at dn*S, at scale*IV; x = P&L / S (entry premium carried in bills to expiry)."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    Kc, Kp = up * S, dn * S
    prem = _px(F, Kc, T, r, sig, "call") - _px(F, Kp, T, r, sig, "put")
    payoff = settle([("call", "long", 1, Kc), ("put", "short", 1, Kp)], P["ST"])
    return {"x": (payoff - prem * P["acc"]) / S, "premium": prem / S}


def skew_groups(entry_days: Sequence[str], skew: dict, q: float = 0.20) -> dict:
    """Top/bottom SKEW quintile flags at entry: full-history cutoffs (all daily SKEW values) and expanding-window cutoffs (SKEW
    values dated on or before the entry day). SKEW at entry = the latest close on or before the entry day."""
    sd = sorted(skew); sv = np.array([float(skew[d]) for d in sd])
    at = np.array([sv[bisect.bisect_right(sd, d) - 1] if bisect.bisect_right(sd, d) > 0 else np.nan for d in entry_days])
    lo_f, hi_f = np.quantile(sv, [q, 1 - q])
    top_e = np.zeros(len(entry_days), bool); bot_e = np.zeros(len(entry_days), bool)
    for i, d in enumerate(entry_days):
        k = bisect.bisect_right(sd, d)
        if k >= 2 and np.isfinite(at[i]):
            lo_e, hi_e = np.quantile(sv[:k], [q, 1 - q])
            top_e[i] = at[i] >= hi_e; bot_e[i] = at[i] <= lo_e
    fin = np.isfinite(at)
    return {"skew": at, "full": (fin & (at >= hi_f), fin & (at <= lo_f)), "expanding": (top_e, bot_e), "cutoffs_full": [lo_f, hi_f]}


def eval_risk_reversal(G: Grid, skew: dict, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    P = G.P; res = risk_reversal(P); x = res["x"]; n = G.n_holds; ne = int(x.size); g = skew_groups(P["day"], skew)
    c = Criteria(); out = {}; summ = {}
    for nm in ("full", "expanding"):
        top, bot = g[nm]; d, lo, hi = ci_t_group_diff(x, top, bot, G.block, n_boot)
        c.ci(f"{nm}-sample quintiles: top - bottom lower CI > 0", lo, hi, "lower_gt")
        rows = []
        for idx in G.offsets:
            dk, lk, hk = ci_t_group_diff(x[idx], top[idx], bot[idx], G.off_block, n_boot)
            rows.append({"diff": dk, "lo": lk, "hi": hk, "ok": bool(np.isfinite(lk) and lk > 0)})
        summ[nm] = _summ(rows, "diff", "lo", "ok")
        out[nm] = {"n_top": int(top.sum()), "n_bottom": int(bot.sum()), "mean_top": float(x[top].mean()) if top.any() else None,
                   "mean_bottom": float(x[bot].mean()) if bot.any() else None, "diff": d, "ci": [lo, hi]}
    v, why = c.finish(n, min_n, "months")
    sens = _sens(lambda s: risk_reversal(P, s))
    unit = "entries" if G.pooled else "months"
    txt = "; ".join(f"{k} quintiles: top {o['n_top']} {unit} mean {_p(o['mean_top'], 2)}, bottom {o['n_bottom']} mean "
                    f"{_p(o['mean_bottom'], 2)}, difference {_p(o['diff'], 2)} (studentized block-{G.block} {_rng(o['ci'][0], o['ci'][1], 2)})"
                    + (f"; {_summ_txt(summ[k], 'per start offset lower CI > 0', 'lower CI')}" if summ[k] else "")
                    for k, o in out.items())
    reason = (f"{MODEL} (both legs at VIX IV flat, so the entry premium does not vary with SKEW: this isolates the conditional "
              f"wing payoff, a SKEW timing test; under flat pricing the structure is a small debit, median "
              f"{_p(float(np.median(res['premium'])) if ne else float('nan'), 2)} of S, carried in bills): SPY 1-month risk "
              f"reversal (long 1.05 S call, short 0.95 S put) from 1993 (SPY inception, not 1990); {_grid_txt(G)}; per-offset "
              f"intervals are studentized block-{G.off_block}; full-history SKEW cutoffs "
              f"{g['cutoffs_full'][0]:.1f}/{g['cutoffs_full'][1]:.1f}; {txt}; IV-scale sensitivity of the all-entry mean (not in "
              f"the pass rule): {_sens_txt(sens, 2)}; a real skew-premium test needs chain capture (60+ days, pending) — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entries": ne, "groups": out, "mean_all": float(x.mean()) if ne else None,
            "skew_cutoffs_full": g["cutoffs_full"], "iv_scale_sensitivity": sens,
            "rule10": _rule10(G, full=summ["full"], expanding=summ["expanding"]), "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------- funded calls (T-139, T-140) --

def funded_call_path(m: Market, iv: np.ndarray, entries: list, hold: Optional[int], moneyness: float, scale: float = 1.0,
                     expiries: Optional[list] = None) -> dict:
    """Long 1 call at K = moneyness*S per S of capital, the rest (S - C) in bills accruing at the rate known each day; the call
    is re-marked every session by Black-Scholes at that day's IV (``iv`` carried over gaps), the remaining time and the
    dividend forward, and settles at intrinsic on the raw close. Cycle k runs from entries[k] to expiries[k] (default
    entries[k] + hold) and rolls into the next entry (entries[k+1] = that expiry). Returns the equity path (from 1), per-cycle
    returns, SPY total-return factors and entry premiums."""
    idx = [entries[0]]; V = [1.0]; R, RS, prem = [], [], []
    v = 1.0
    for k, a in enumerate(entries):
        b = int(expiries[k]) if expiries is not None else a + hold
        S = m.close[a]; K = moneyness * S; r0 = m.rate[a]; T0 = (m.cal[b] - m.cal[a]) / 365.0
        C0 = float(bs.price(S - m.pv_div(a, b, r0), K, T0, r0, iv[a] * scale, "call"))
        u = v / S
        t = np.arange(a + 1, b + 1)
        bills = (S - C0) * np.exp(np.cumsum(m.rate[t - 1] * (m.cal[t] - m.cal[t - 1]) / 365.0))
        Tt = (m.cal[b] - m.cal[t]) / 365.0
        call = np.asarray(bs.price(m.close[t] - m.pv_div_path(t, b), K, Tt, m.rate[t], iv[t] * scale, "call"), float)
        path = u * (call + bills)
        R.append(path[-1] / v - 1); RS.append(m.adj[b] / m.adj[a] - 1); prem.append(C0 / S)
        idx.extend(t.tolist()); V.extend(path.tolist()); v = float(path[-1])
    idx = np.array(idx, int); V = np.array(V)
    return {"idx": idx, "V": V, "ret": V[1:] / V[:-1] - 1, "spy_ret": m.adj[idx[1:]] / m.adj[idx[:-1]] - 1,
            "R": np.array(R), "R_spy": np.array(RS), "premium": np.array(prem), "entries": list(entries)}


def funded_call_cycles(P: dict, moneyness: float, scale: float = 1.0) -> dict:
    """Per-cycle return of the funded call held to expiry (vectorised; equals funded_call_path's R): call at entry on the
    dividend forward, (S - C) in bills, intrinsic on the raw close at expiry; R_spy = SPY total return."""
    S, F, T, r = P["S"], P["F"], P["T"], P["r"]; K = moneyness * S
    C0 = _px(F, K, T, r, P["sig"] * scale, "call")
    return {"R": (np.maximum(P["ST"] - K, 0.0) + (S - C0) * P["acc"]) / S - 1, "R_spy": P["tr"] - 1, "premium": C0 / S}


def _fill(x: np.ndarray) -> np.ndarray:
    out = np.array(x, float); last = float("nan")
    for i in range(out.size):
        if np.isfinite(out[i]) and out[i] > 0:
            last = out[i]
        else:
            out[i] = last
    return out


def ann_diff(R, R_spy) -> float:
    """Annualised geometric return difference from 1-year cycles: exp(mean log(1+R)) - exp(mean log(1+R_spy))."""
    return float(np.exp(np.mean(np.log1p(R))) - np.exp(np.mean(np.log1p(R_spy))))


def _ann_diff_ci(R, RS, block: int, n_boot: int) -> tuple:
    R, RS = np.asarray(R, float), np.asarray(RS, float)
    if R.size < 2 * block:
        return float("nan"), float("nan")
    lr, ls = np.log1p(R), np.log1p(RS)
    return _q(_boot_stat(R.size, lambda ix: np.exp(lr[ix].mean(axis=1)) - np.exp(ls[ix].mean(axis=1)), block, n_boot))


def eval_leaps(m: Market, iv: np.ndarray, min_n: int = 30, n_boot: int = N_BOOT, iv_note: str = "", start: str = START) -> dict:
    """Rule 10(b), hold 252: the return difference is pooled over every daily entry (blocks of 504 days); the drawdown ratio
    is averaged over the paths of all 252 start offsets (each an annually rolled funded call)."""
    ivf = _fill(iv); G = offsets_grid(m, ivf, YEAR, start, ANNUAL_BLOCK); P = G.P; n = G.n_holds
    cyc = funded_call_cycles(P, 0.80); R, RS = cyc["R"], cyc["R_spy"]
    d = ann_diff(R, RS) if R.size else float("nan"); lo, hi = _ann_diff_ci(R, RS, G.block, n_boot)
    c = Criteria()
    c.ci("annualised return difference (LEAPS + bills - SPY) upper CI < 0", lo, hi, "upper_lt")
    rows = []
    for k, idx in enumerate(G.offsets):
        if idx.size == 0:
            continue
        dk = ann_diff(R[idx], RS[idx]); lk, hk = _ann_diff_ci(R[idx], RS[idx], G.off_block, n_boot)
        p = funded_call_path(m, ivf, [int(a) for a in P["a"][idx]], YEAR, 0.80)
        ms, mb = _mdd(p["ret"]), _mdd(p["spy_ret"])
        ratio = ms / mb if mb < 0 else float("nan")
        rows.append({"offset": k, "start": m.days[int(P["a"][idx[0]])], "cycles": int(idx.size), "ann_diff": dk, "lo": lk,
                     "hi": hk, "ok": bool(np.isfinite(hk) and hk < 0), "mdd": ms, "mdd_spy": mb, "mdd_ratio": ratio,
                     "mdd_ok": bool(np.isfinite(ratio) and ratio < 1)})
    ratios = np.array([r["mdd_ratio"] for r in rows], float)
    mr = float(np.nanmean(ratios)) if np.isfinite(ratios).any() else float("nan")
    c.add(f"max-drawdown ratio (mean over all {len(rows)} start offsets) < 1", mr < 1 if np.isfinite(mr) else None)
    v, why = c.finish(n, min_n, "independent annual cycles")
    for r in rows:
        r["both_ok"] = bool(r["ok"] and r["mdd_ok"])
    s_ret, s_mdd = _summ(rows, "ann_diff", "hi", "ok"), _summ(rows, "mdd_ratio", "mdd_ratio", "mdd_ok")
    s_both = _summ(rows, "ann_diff", "hi", "both_ok")
    coh = [r for r in rows if r["offset"] % MONTH == 0][:12]          # the trial's 12 monthly-staggered cohorts (report)
    if coh:
        ci_ = np.concatenate([G.offsets[r["offset"]] for r in coh])
        coh_d = ann_diff(R[ci_], RS[ci_]); coh_mr = float(np.nanmean([r["mdd_ratio"] for r in coh]))
    else:
        coh_d = coh_mr = float("nan")
    sens = {}
    for s in (0.90, 1.10):
        q = funded_call_cycles(P, 0.80, s); sens[f"{s:.2f}"] = ann_diff(q["R"], q["R_spy"]) if R.size else None
    f2 = lambda v_: "n/a" if v_ is None or not np.isfinite(v_) else f"{v_:.2f}"
    off = ""
    if rows:
        off = (f"; per start offset (non-overlapping annual cycles, block-{G.off_block} percentile): "
               f"{_summ_txt(s_ret, 'return difference upper CI < 0', 'upper CI')}; "
               f"drawdown ratio < 1: {s_mdd['pass']} of {s_mdd['offsets']} start offsets pass (per-offset ratio "
               f"{f2(s_mdd['stat'][0])} to {f2(s_mdd['stat'][1])}); both in {s_both['pass']} of {s_both['offsets']}")
    reason = (f"{MODEL} (1-year call K = 0.8 S at VIX3M IV{iv_note}, flat, on the dividend forward with r = prior DTB3 print, re-marked "
              f"daily at that day's IV; S - C in 3-month bills; SPY total return, the same dividend convention): {_grid_txt(G)} "
              f"(the trial expects about 33 independent annual cycles); median call premium "
              f"{_p(float(np.median(cyc['premium'])) if R.size else float('nan'), 1)} of S; pooled annualised return difference "
              f"{_p(d, 2)} ({_rng(lo, hi, 2)}; the difference is the embedded 20%-OTM put's P&L); max-drawdown ratio mean "
              f"{f2(mr)} over all {len(rows)} offset paths{off}; the trial's 12 monthly-staggered cohorts (offsets 0, 21, ..., "
              f"231; report only): return difference {_p(coh_d, 2)}, drawdown ratio mean {f2(coh_mr)}; pooled return "
              f"difference at IV scale 0.90 {_p(sens.get('0.90'), 2)}, 1.10 {_p(sens.get('1.10'), 2)} (1-year IV usually sits "
              f"above VIX3M, so the put cost is understated; not in the pass rule) — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entries": int(R.size), "ann_return_diff": d, "ci": [lo, hi],
            "mdd_ratio_mean": mr, "per_offset": rows, "cohorts_12": {"ann_diff": coh_d, "mdd_ratio_mean": coh_mr},
            "iv_scale_sensitivity": sens, "rule10": _rule10(G, ret=s_ret, mdd=s_mdd, both=s_both), "model_priced": True,
            "min_n": min_n}


def _daily_stats(p: dict, block: int, n_boot: int) -> dict:
    """Correlation of daily portfolio and SPY returns and the annualised shortfall, with block-bootstrap percentile CIs."""
    rs, rb = p["ret"], p["spy_ret"]; N = rs.size
    corr = float(np.corrcoef(rs, rb)[0, 1])
    ls, lb = np.log1p(rs), np.log1p(rb)
    short = float(np.exp(YEAR * lb.mean()) - np.exp(YEAR * ls.mean()))
    def corr_fn(ix):
        a, b = rs[ix], rb[ix]; a = a - a.mean(axis=1, keepdims=True); b = b - b.mean(axis=1, keepdims=True)
        return (a * b).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    clo, chi = _q(_boot_stat(N, corr_fn, block, n_boot))
    slo, shi = _q(_boot_stat(N, lambda ix: np.exp(YEAR * lb[ix].mean(axis=1)) - np.exp(YEAR * ls[ix].mean(axis=1)), block, n_boot))
    return {"corr": corr, "corr_ci": [clo, chi], "short": short, "short_ci": [slo, shi], "n_days": int(N),
            "corr_ok": bool(clo > 0.98), "short_ok": bool(shi < 0.01)}


def eval_deep_itm(m: Market, iv: np.ndarray, min_n: int = 300, n_boot: int = N_BOOT, block: int = MONTH, start: str = START) -> dict:
    """Rule 10(a): 'monthly-rolled' = SPY's standard monthly options, bought at one monthly expiry close and rolled at the
    next. The 21-session grid's start offsets are reported as a robustness check (not the pass rule)."""
    ivf = _fill(iv); ent, exp = roll_cycles(m, ivf, monthly_expiries(m, start))
    if not ent:
        c = Criteria(); c.add("correlation lower CI > 0.98", None); c.add("shortfall upper CI < 1 pp", None)
        v, why = c.finish(0, min_n, "monthly cycles")
        return {"verdict": v, "reason": f"{MODEL}: no monthly expiry cycles — {why}", "n": 0, "model_priced": True, "min_n": min_n}
    p = funded_call_path(m, ivf, ent, None, 0.90, expiries=exp); n = int(p["R"].size)
    st = _daily_stats(p, block, n_boot)
    c = Criteria()
    c.ci("daily-return correlation with SPY lower CI > 0.98", st["corr_ci"][0], st["corr_ci"][1], "lower_gt", 0.98)
    c.ci("annualised shortfall vs SPY upper CI < 1 pp", st["short_ci"][0], st["short_ci"][1], "upper_lt", 0.01)
    v, why = c.finish(n, min_n, "monthly cycles")
    sens = {}
    for s in SCALES:
        q = funded_call_path(m, ivf, ent, None, 0.90, s, expiries=exp)
        sens[f"{s:.2f}"] = float(np.exp(YEAR * np.log1p(q["spy_ret"]).mean()) - np.exp(YEAR * np.log1p(q["ret"]).mean()))
    rows = []                                                       # robustness: the 21-session grid's start offsets
    first = cycle_entries(m, ivf, MONTH, start)
    if first:
        for k in range(MONTH):
            e = list(range(first[0] + k, len(m.days) - MONTH, MONTH))
            if not e:
                continue
            rows.append(_daily_stats(funded_call_path(m, ivf, e, MONTH, 0.90), block, n_boot))
        for r in rows:
            r["both_ok"] = bool(r["corr_ok"] and r["short_ok"]); r["clo"] = r["corr_ci"][0]; r["shi"] = r["short_ci"][1]
    s_corr, s_short = _summ(rows, "corr", "clo", "corr_ok"), _summ(rows, "short", "shi", "short_ok")
    s_both = _summ(rows, "corr", "clo", "both_ok")
    f4 = lambda v_: "n/a" if v_ is None else f"{v_:.4f}"
    fpp = lambda v_: "n/a" if v_ is None else f"{v_ * 100:+.2f} pp"
    rob = ""
    if rows:
        rob = (f"; robustness (rule 10 grid reading, not the pass rule): the {len(rows)} start offsets of a 21-session roll grid: "
               f"{_summ_txt(s_corr, 'correlation lower CI > 0.98', 'lower CI', f4)}; "
               f"{_summ_txt(s_short, 'shortfall upper CI < 1 pp', 'upper CI', fpp)}; both in {s_both['pass']} of {s_both['offsets']}")
    dte = (m.cal[np.array(exp)] - m.cal[np.array(ent)]).astype(int)
    reason = (f"{MODEL} (call K = 0.9 S at VIX IV flat on the dividend forward, re-marked daily at that day's VIX; S - C in "
              f"3-month bills at the prior DTB3 prints; SPY total return): rule 10(a), 'monthly-rolled' = SPY's standard monthly "
              f"options (third Friday, prior session on a holiday), bought at one monthly expiry close and rolled at the next "
              f"({dte.min()}-{dte.max()} days); {n} monthly rolls, {st['n_days']} daily returns {m.days[p['idx'][0]]} to "
              f"{m.days[p['idx'][-1]]}; median call premium {_p(float(np.median(p['premium'])), 1)} of S; correlation "
              f"{st['corr']:.4f} (block-{block} percentile 95% CI {st['corr_ci'][0]:.4f} to {st['corr_ci'][1]:.4f}; needs lower > "
              f"0.98); annualised shortfall {st['short'] * 100:+.2f} pp (95% CI {st['short_ci'][0] * 100:+.2f} to "
              f"{st['short_ci'][1] * 100:+.2f} pp; needs upper < 1 pp; equals the embedded 10%-OTM put's P&L){rob}; shortfall at "
              f"IV scales (not in the pass rule; a traded test needs chain history and deep-ITM bid-ask): "
              + ", ".join(f"s={k} {v_ * 100:+.2f} pp" for k, v_ in sens.items()) + f" — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_days": st["n_days"], "corr": st["corr"], "corr_ci": st["corr_ci"],
            "shortfall": st["short"], "shortfall_ci": st["short_ci"], "iv_scale_sensitivity": sens,
            "rule10": {"kind": "calendar", "label": "SPY monthly expiry roll (expiry to expiry)", "cycles": n,
                       "grid_robustness": {"corr": s_corr, "shortfall": s_short, "both": s_both}},
            "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------------------ T-154 ZEBRA --

def zebra(P: dict, scale: float = 1.0, long_delta: float = 0.70) -> dict:
    """Long 2 calls at the `long_delta` strike, short 1 ATM call, plus (delta0*S - debit) in bills (accruing day by day),
    against delta0 SPY shares (total return); x = difference / S."""
    sig = P["sig"] * scale; S, F, T, r = P["S"], P["F"], P["T"], P["r"]
    K1 = _strikes_for_delta(P, sig, long_delta, "call"); K2 = S.copy()
    d1 = np.asarray(bs.greeks(F, K1, T, r, sig, "call")["delta"], float); d2 = np.asarray(bs.greeks(F, K2, T, r, sig, "call")["delta"], float)
    delta0 = 2 * d1 - d2
    debit = 2 * _px(F, K1, T, r, sig, "call") - _px(F, K2, T, r, sig, "call")
    payoff = settle([("call", "long", 2, K1), ("call", "short", 1, K2)], P["ST"])
    x = (payoff + (delta0 * S - debit) * P["acc"] - delta0 * S * P["tr"]) / S
    extr = (2 * (_px(F, K1, T, r, sig, "call") - np.maximum(F - K1, 0)) - _px(F, K2, T, r, sig, "call") + np.maximum(F - K2, 0)) / S
    return {"x": x, "delta0": delta0, "net_extrinsic": extr, "K1": K1 / S}


def eval_zebra(G: Grid, min_n: int = 300, n_boot: int = N_BOOT, robust: Optional[Grid] = None) -> dict:
    """``G``: the claim's calendar (monthly expiries entered about 30 DTE). ``robust``: the 21-session grid, all offsets
    pooled, reported only."""
    P = G.P; res = zebra(P); x = res["x"]; n = G.n_holds; ne = int(x.size)
    mr = _mean_rule10(G, x, "upper_lt", 0.0, n_boot); lo, hi = mr["lo"], mr["hi"]
    c = Criteria(); c.ci("mean (ZEBRA - delta0 x SPY) / S upper CI < 0", lo, hi, "upper_lt")
    v, why = c.finish(n, min_n, "months")
    sens = _sens(lambda s: zebra(P, s)); h1, h2 = _halves(x)
    rob, rob_d = "", None
    if robust is not None and robust.P["n"]:
        xr = zebra(robust.P)["x"]; rr = _mean_rule10(robust, xr, "upper_lt", 0.0, n_boot)
        rob_d = {"mean": rr["mean"], "ci": [rr["lo"], rr["hi"]], "per_offset": rr["summary"]}
        rob = (f"; robustness (not the claim's calendar, not the pass rule): the 21-session grid pooled over all "
               f"{len(robust.offsets)} start offsets ({robust.P['n']} daily entries, {robust.block}-day blocks) mean "
               f"{_p(rr['mean'])} ({_rng(rr['lo'], rr['hi'])}); "
               f"{_summ_txt(rr['summary'], 'upper CI < 0', 'upper CI', lambda v_: _p(v_, 3))}")
    reason = (f"{MODEL} (both strikes at VIX IV flat, 0.70-delta strike solved at that IV on the dividend forward; the cash "
              f"difference delta0*S - debit earns the prior DTB3 prints day by day; SPY total return): SPY call ZEBRA; "
              f"{_grid_txt(G)}; median entry delta {float(np.median(res['delta0'])) if ne else float('nan'):.3f}, median 0.70-delta "
              f"strike {_p(float(np.median(res['K1'])) - 1 if ne else float('nan'), 2)} vs spot, median net extrinsic paid "
              f"{_p(float(np.median(res['net_extrinsic'])) if ne else float('nan'), 2)} of S; mean difference {_p(mr['mean'])} of S "
              f"({_rng(lo, hi)}, block-{G.block} percentile); halves (report only) {_p(h1)} / {_p(h2)}{rob}; IV-scale "
              f"sensitivity (not in the pass rule; the net extrinsic is priced off the IV level): {_sens_txt(sens)}; "
              f"{CHAIN_NOTE} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "mean_diff": mr["mean"] if ne else None, "ci": [lo, hi], "halves": [h1, h2],
            "median_delta0": float(np.median(res["delta0"])) if ne else None,
            "median_net_extrinsic": float(np.median(res["net_extrinsic"])) if ne else None,
            "iv_scale_sensitivity": sens, "rule10": {"kind": G.kind, "label": G.label, "cycles": ne, "grid_robustness": rob_d},
            "model_priced": True, "min_n": min_n}


# ----------------------------------------------------------------------------------------------- T-516 digital --

def digital_put(P: dict, scale: float = 1.0, k: float = 0.97) -> dict:
    """RN probability N(-d2) of S_T < k*S at scale*IV (dividend forward, r = prior DTB3 print) and the outcome."""
    sig = P["sig"] * scale; K = k * P["S"]
    p = _ncdf(-_d2(P["F"], K, P["T"], P["r"], sig)); y = (P["ST"] < K).astype(float)
    return {"x": y - p, "p": p, "y": y}


def expanding_climatology(P: dict, y, min_resolved: int) -> np.ndarray:
    """Point-in-time climatology at each entry: the mean outcome of the cycles that had settled by the entry close
    (expiry index <= entry index); NaN until ``min_resolved`` have settled."""
    y = np.asarray(y, float); o = np.argsort(P["b"], kind="stable"); bs_ = P["b"][o]; cy = np.cumsum(y[o])
    k = np.searchsorted(bs_, P["a"], side="right")
    return np.where(k >= max(min_resolved, 1), cy[np.maximum(k, 1) - 1] / np.maximum(k, 1), np.nan)


def eval_digital(G: Grid, min_n: int = 300, n_boot: int = N_BOOT) -> dict:
    P = G.P; res = digital_put(P); x = res["x"]; n = G.n_holds; ne = int(x.size)
    mr = _mean_rule10(G, x, "upper_lt", 0.0, n_boot); lo, hi = mr["lo"], mr["hi"]
    c = Criteria(); c.ci("realised - RN probability upper CI < 0", lo, hi, "upper_lt")
    v, why = c.finish(n, min_n, "21-day cycles")
    y, p = res["y"], res["p"]
    brier = {"rn": None, "climatology": None, "diff": None, "ci": [None, None], "n": 0}
    if ne:                                           # Brier vs a point-in-time (expanding) climatology, paired CI
        clim = expanding_climatology(P, y, 12 * G.hold if G.pooled else 12); ok = np.isfinite(clim)
        if ok.sum() >= 2:
            d = (p[ok] - y[ok]) ** 2 - (clim[ok] - y[ok]) ** 2; bl, bh = _ci(d, G.block, n_boot)
            brier = {"rn": float(np.mean((p[ok] - y[ok]) ** 2)), "climatology": float(np.mean((clim[ok] - y[ok]) ** 2)),
                     "diff": float(d.mean()), "ci": [bl, bh], "n": int(ok.sum())}
    if brier["diff"] is None:
        skill = "not computable"
    elif brier["ci"][1] < 0:
        skill = "N(-d2) scores better than climatology"
    elif brier["ci"][0] > 0:
        skill = "N(-d2) scores worse than climatology"
    else:
        skill = "N(-d2) shows no skill over climatology (the difference is inside its CI)"
    sens = {}
    for s in SCALES:
        r2 = digital_put(P, s); l2, h2 = _ci(r2["x"], G.block, n_boot)
        sens[f"{s:.2f}"] = {"rn_mean": float(r2["p"].mean()) if ne else None, "diff": float(r2["x"].mean()) if ne else None,
                            "ci": [l2, h2]}
    def upper(s):
        return _ci(digital_put(P, s)["x"], G.block, n_boot)[1]
    be = None; be_txt = "n/a"
    if ne >= 2 and np.isfinite(hi):
        if hi >= 0:
            be_txt = "already fails at s = 1.00"
        elif upper(0.30) < 0:
            be, be_txt = 0.30, "below 0.30"
        else:
            a_, b_ = 0.30, 1.0
            for _ in range(10):
                mid = (a_ + b_) / 2
                a_, b_ = (mid, b_) if upper(mid) >= 0 else (a_, mid)
            be = round(b_, 3); be_txt = f"about {b_:.2f} x VIX"
    off = (f"; per start offset (non-overlapping grid, block-{G.off_block} percentile): "
           f"{_summ_txt(mr['summary'], 'upper CI < 0', 'upper CI')}" if mr["summary"] else "")
    reason = (f"{MODEL} (N(-d2) at VIX IV flat, K = 0.97 S, dividend forward, r = prior DTB3 print): SPY 21-session (about "
              f"30-day) digital puts; {_grid_txt(G)}; realised frequency of S_T < K {_p(y.mean() if ne else float('nan'), 1)} vs "
              f"mean N(-d2) {_p(p.mean() if ne else float('nan'), 1)}: realised - RN {_p(mr['mean'], 2)} ({_rng(lo, hi, 2)}){off}; "
              f"Brier (report only) N(-d2) {brier['rn'] if brier['rn'] is not None else float('nan'):.4f} vs point-in-time "
              f"expanding climatology {brier['climatology'] if brier['climatology'] is not None else float('nan'):.4f} over "
              f"{brier['n']} entries, difference {brier['diff'] if brier['diff'] is not None else float('nan'):+.4f} (95% CI "
              f"{brier['ci'][0] if brier['ci'][0] is not None else float('nan'):+.4f} to "
              f"{brier['ci'][1] if brier['ci'][1] is not None else float('nan'):+.4f}): {skill}; at IV scales (not in the "
              f"pass rule; flat IV ignores skew, a traded digital needs chain history): "
              + ", ".join(f"s={k} RN {_p(o['rn_mean'], 1)}, diff {_p(o['diff'], 2)} ({_rng(o['ci'][0], o['ci'][1], 2)})"
                          for k, o in sens.items())
              + f"; the upper CI reaches 0 at an IV scale {be_txt} — {why}")
    return {"verdict": v, "reason": reason, "n": n, "n_entries": ne, "realised": float(y.mean()) if ne else None,
            "rn_mean": float(p.mean()) if ne else None, "diff": mr["mean"] if ne else None, "ci": [lo, hi],
            "brier": brier, "iv_scale_sensitivity": sens, "breakeven_iv_scale": be,
            "rule10": _rule10(G, ci=mr["summary"]), "model_priced": True, "min_n": min_n}


# ------------------------------------------------------------------------------------------------- harnesses --

SPY_BASE = ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"]


def _market(archive, symbol: str = "SPY") -> Market:
    def build():
        days, close, adj = _prices(archive, symbol)
        return make_market(days, close, adj, _index(archive, "fred-DTB3"))
    return _cached(archive, ("market", symbol), build)


def _vix(archive) -> np.ndarray:
    return _cached(archive, ("iv", "VIX"), lambda: iv_series(_market(archive).days, _index(archive, "cboe-VIX-history")))


def _vix_grid(archive) -> Grid:
    """Rule 10(b): the 21-session grid of SPY at VIX, every start offset pooled."""
    return _cached(archive, ("grid", "VIX"), lambda: offsets_grid(_market(archive), _vix(archive), MONTH))


def _vix_dte_grid(archive, dte: int = DTE) -> Grid:
    """Rule 10(a): SPY standard monthly expiries, entered about ``dte`` calendar days before each."""
    def build():
        m = _market(archive); iv = _vix(archive)
        ent, exp = dte_cycles(m, iv, monthly_expiries(m), dte)
        return calendar_grid(m, iv, ent, exp, f"SPY standard monthly expiries (third Friday, prior session on a holiday), "
                                              f"entered at the last session on or before {dte} calendar days ahead")
    return _cached(archive, ("grid", "VIX", "dte", dte), build)


def _iv3m(archive, m: Market) -> np.ndarray:
    return iv_series(m.days, _index(archive, "cboe-VIX3M-history"), _index(archive, "cboe-VIX-history"))


def _vix3m_note(archive, claim_switch: str = " (the archive's VIX3M starts there, not at the claim's 2007-12)") -> str:
    v3 = _index(archive, "cboe-VIX3M-history")
    return f" from {min(v3)}, VIX before{claim_switch}" if v3 else " (no VIX3M prints: VIX throughout)"


def b6_dir_jade_lizard(archive):
    """T-113: MODEL-PRICED SPY jade lizard, mean P&L / (0.2 S) > 0 (lower CI) and positive in both halves."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_jade_lizard(_vix_grid(archive)))


def b6_dir_ratio_1x2(archive):
    """T-133: MODEL-PRICED zero-cost 1x2 SPY call ratio: mean > 0 and losses > 3x median gain in > 3% of months."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_ratio_1x2(_vix_grid(archive)))


def b6_dir_christmas_tree(archive):
    """T-135: MODEL-PRICED 1-3-2 call tree; profit-zone hit rate above its risk-neutral probability."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_christmas_tree(_vix_grid(archive)))


def b6_dir_stock_repair(archive):
    """T-136: MODEL-PRICED stock repair after 10% SPY drawdowns vs holding; mean difference > 0 (studentized lower CI)."""
    miss = _missing(archive, SPY_BASE + ["cboe-VIX3M-history"])
    if miss:
        return miss
    m = _market(archive); iv = _iv3m(archive, m)
    second = None
    if _has(archive, "daily-history-QQQ"):
        mq = _market(archive, "QQQ")
        vxn = _index(archive, "cboe-VXN-history") if _has(archive, "cboe-VXN-history") else {}
        ivq = iv_series(mq.days, vxn, _index(archive, "cboe-VIX-history")) if vxn else iv_series(mq.days, _index(archive, "cboe-VIX-history"))
        second = ("QQQ (VXN IV from its first print, VIX before)" if vxn else "QQQ (VIX IV)", mq, ivq)
    return _wrap(eval_stock_repair(m, iv, second=second, iv_note=_vix3m_note(archive, "")))


def b6_dir_risk_reversal_skew(archive):
    """T-138: MODEL-PRICED SPY risk reversal; top minus bottom SKEW-quintile mean P&L > 0 (full and expanding cutoffs)."""
    miss = _missing(archive, SPY_BASE + ["cboe-SKEW-history"])
    if miss:
        return miss
    return _wrap(eval_risk_reversal(_vix_grid(archive), _index(archive, "cboe-SKEW-history")))


def b6_dir_leaps_replacement(archive):
    """T-139: MODEL-PRICED 1-year 20%-ITM SPY call + bills vs SPY: lower annualised return (upper CI < 0) and smaller MDD."""
    miss = _missing(archive, SPY_BASE + ["cboe-VIX3M-history"])
    if miss:
        return miss
    m = _market(archive)
    return _wrap(eval_leaps(m, _iv3m(archive, m), iv_note=_vix3m_note(archive)))


def b6_dir_deep_itm_call(archive):
    """T-140: MODEL-PRICED monthly-rolled 10%-ITM SPY call + bills: correlation > 0.98 and shortfall < 1 pp (CI bounds)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_deep_itm(_market(archive), _vix(archive)))


def b6_dir_zebra(archive):
    """T-154: MODEL-PRICED monthly 30-DTE SPY call ZEBRA vs a delta-matched SPY position: mean difference < 0 (upper CI)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_zebra(_vix_dte_grid(archive), robust=_vix_grid(archive)))


def b6_dir_digital_put(archive):
    """T-516: MODEL-PRICED 30-day 0.97 S digital put: realised frequency below N(-d2) at VIX IV (upper CI < 0)."""
    miss = _missing(archive, SPY_BASE)
    if miss:
        return miss
    return _wrap(eval_digital(_vix_grid(archive)))


HARNESSES = {
    "b6_dir_jade_lizard": b6_dir_jade_lizard,
    "b6_dir_ratio_1x2": b6_dir_ratio_1x2,
    "b6_dir_christmas_tree": b6_dir_christmas_tree,
    "b6_dir_stock_repair": b6_dir_stock_repair,
    "b6_dir_risk_reversal_skew": b6_dir_risk_reversal_skew,
    "b6_dir_leaps_replacement": b6_dir_leaps_replacement,
    "b6_dir_deep_itm_call": b6_dir_deep_itm_call,
    "b6_dir_zebra": b6_dir_zebra,
    "b6_dir_digital_put": b6_dir_digital_put,
}

THEORY_MAP = {
    "T-113": "b6_dir_jade_lizard",
    "T-133": "b6_dir_ratio_1x2",
    "T-135": "b6_dir_christmas_tree",
    "T-136": "b6_dir_stock_repair",
    "T-138": "b6_dir_risk_reversal_skew",
    "T-139": "b6_dir_leaps_replacement",
    "T-140": "b6_dir_deep_itm_call",
    "T-154": "b6_dir_zebra",
    "T-516": "b6_dir_digital_put",
}
