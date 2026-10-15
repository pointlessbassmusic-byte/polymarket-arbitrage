"""
Batch 5, hourly bars: market intraday momentum (T-427) and the closing-auction reversal (T-428) on SPY.
=======================================================================================================

Two library claims tested on archived Yahoo 1h bars (``hourly-<SYM>``) and Yahoo daily OHLC (``daily-history-<SYM>``).
Each test follows the claim and its trial.pass as worded.

Sessions.
  * Yahoo labels a 1h bar by its START time in UTC. Bars are converted to New York time with zoneinfo
    (America/New_York, DST aware). A regular session has bars starting 09:30, 10:30, ... 15:30; the 09:30 bar ends at
    10:30 and the 15:30 bar is the last half hour (15:30-16:00).
  * "Price at 10:30" = close of the 09:30 bar. "15:30" = open of the 15:30 bar. "Official close" and "official open" are
    the daily-history ``close`` and ``open`` (split-adjusted, not dividend-adjusted, like the intraday bars). The 15:30
    bar's own last trade is not the closing-auction print and is not used as an exit.
  * Early-close sessions (bars 09:30, 10:30, 11:30 and a 13:00 close tick) have no 15:30-16:00 half hour and are
    excluded and counted. Days whose 09:30 or 15:30 bar is missing are excluded from the tests that need that bar and
    counted. A bar or daily row is used only if its ``available_at`` precedes its bundle's capture time.
  * Dividends: the previous close and the next open are put in day-t terms with the Yahoo dividend factor
    f = adjclose / close, so r1 = P(10:30) / (C(t-1) f(t-1)/f(t)) - 1 and the overnight return
    CO(t+1) = O(t+1) / (C(t) f(t)/f(t+1)) - 1 are total returns (ex-dividend drops are not read as price moves).
    Dividend amounts and ex-dates are declared weeks ahead, so the adjustment uses no future information.
  * Window: the claim names 2023-11 to 2026-10. Days outside [2023-11-01, 2026-10-31] are dropped; the archived window
    (Yahoo keeps about 730 days of 1h bars) is stated in every reason, and a window shorter than the claimed one
    (first usable day after 2023-11-30 or last before 2026-10-01) is named as a data limit and leaves the criterion
    "archived window covers the claimed 2023-11..2026-10" not implemented, so the verdict is at best inconclusive.

T-427 (intraday half-hour momentum). r1 = previous official close to the 10:30 price (known at 10:30). At the 15:30
bar open go long SPY if r1 > 0 and short if r1 < 0 (no trade at r1 = 0) and exit at the official close. Net return =
signed return - 2 bps per round trip. Statistics: mean net daily return with a Newey-West (Bartlett) HAC t-stat, a
two-sided 95% circular-block-bootstrap CI and the studentized block-bootstrap p (``block_bootstrap_pvalue``,
H0: mean <= 0). "p < 0.05 after deflation over 60 cells" is 1 - DSR, with ``deflated_sharpe_ratio(net, n_trials=60)``:
the per-day Sharpe is tested against the expected maximum of 60 zero-skill Sharpes of this length. The 60-cell grid
itself (sign x threshold x conditioning x 5 assets, BTC on Coinbase) is not run; the deflation charges for all 60
cells. "Same sign on QQQ and IWM" = the same rule's mean net return is > 0 on both (the claimed sign). Diagnostic:
OLS slope of the last-half-hour return on r1 (HAC t). Regime diagnostics: scheduled FOMC decision days, CPI release
days and monthly option-expiration Fridays.

T-428 (closing-auction reversal). L = official close / 15:30 bar open - 1; R = 15:30 bar open / official open - 1 (the
day's open-to-15:30 return); y = CO(t+1). OLS y = a + b L + c R (the intercept is the unconditional overnight mean),
Newey-West HAC standard errors, one-sided p for H0: b >= 0, deflated over the 32 declared cells with the Sidak
correction p_defl = 1 - (1 - p)^32 (the probability that the best of 32 independent null cells is at least this
extreme), and a pairs circular-block-bootstrap 95% CI for b. Pass: b <= -0.2 and p_defl < 0.01.
The reversal leg must be sized on the 15:45 state (the MOC cutoff is 15:50) and is filled at the official close, then
exited at the next official open with 1 bp at the open and no spread at the close print. Hourly bars carry no price
between 15:30 and 16:00, so the 15:45 state cannot be observed: that criterion is NOT IMPLEMENTED from hourly data and
the verdict is at best inconclusive. ``closing_reversal`` takes an optional ``l_decision`` (L measured to 15:45, e.g.
from minute bars) and then implements it. The proxy that sizes on L measured to the official close uses the fill
price in its own signal (LOOK-AHEAD) and is reported as a diagnostic only.

Annualisation: 252 equity trading days. No results here are model-priced. Verdicts use ``underlying2._verdict``: any
implemented criterion failing -> not_supported; any criterion not implemented -> at best inconclusive; supported only
when every criterion is implemented and passes. Fewer than 500 usable days, or an archived window that does not
cover the claimed 2023-11..2026-10 (data limits) -> at best inconclusive.

House rule 5 (``_rule5``). Below the trial's min_n (500 usable days) the unmet 'at least 500 days' criterion keeps the
verdict from supported, and a failing criterion still counts only when it fails decisively: its 95% interval lies
wholly on the wrong side of the claimed bound. T-427: the mean criterion when the mean's 95% block-bootstrap CI lies
wholly at or below 0; the deflated-p criterion, a one-sided 95% test (DSR > 0.95), at the same confidence: when the
Sharpe's one-sided 95% upper bound lies at or below 0, i.e. the PSR against a zero Sharpe
(``deflated_sharpe_ratio(net, n_trials=1)``) is <= 0.05 (the deflation benchmark, the expected best of 60 zero-skill
Sharpes, is >= 0 at any sample size, so the DSR is then <= 0.05 too), or when the mean's 95% CI lies wholly at or
below 0 (a one-sided 97.5% bound on the same sign); the PSR is reported in ``rule5`` and the reason. The QQQ/IWM
criterion when either asset's 95% HAC interval of its mean net return lies wholly at or below 0 (HAC t <= -1.96, at
least 8 days). T-428: the slope criterion when the slope's 95% block-bootstrap CI lies wholly above -0.2, the
deflated-p criterion when it lies wholly at or above 0, and the reversal leg (when a 15:45 signal is supplied) when its
annualised Sharpe's 95% block-bootstrap interval lies wholly at or below 0.5. A zero-width interval decides nothing. Any other failure there is undecided (None), so the verdict is inconclusive;
under 8 (T-427) or 10 (T-428) usable days nothing is computed. At or above min_n every criterion is judged at face
value, exactly as before. Below min_n the report's ``rule5`` holds the face-value and judged criteria and the decisive
failures.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments.underlying2 import _mean_ci, _verdict
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio

NY = ZoneInfo("America/New_York")
EQ_PPY = 252
CLAIM_START, CLAIM_END = "2023-11-01", "2026-10-31"
CLAIM_LABEL = "2023-11..2026-10"
MIN_N = 500
FIRST_BAR, LAST_BAR, EARLY_CLOSE_TICK = "09:30", "15:30", "13:00"


# ------------------------------------------------------------------------------------------------- statistics --

def _nw_lag(n: int) -> int:
    """Newey-West rule-of-thumb bandwidth floor(4 (n/100)^(2/9))."""
    return max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def nw_mean_t(x, lag: Optional[int] = None) -> Optional[float]:
    """HAC (Bartlett / Newey-West) t-stat of the mean of ``x``."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return None
    lag = _nw_lag(n) if lag is None else lag
    e = x - x.mean()
    s = float(e @ e) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(e[l:] @ e[:-l]) / n
    if s <= 0:
        return None
    return float(x.mean() / math.sqrt(s / n))


def ols_hac(y, X, lag: Optional[int] = None):
    """(beta, HAC standard errors) of OLS y = X beta, Bartlett kernel with bandwidth ``lag`` (Newey-West rule by
    default). No small-sample correction."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    n = X.shape[0]
    lag = _nw_lag(n) if lag is None else lag
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ (X.T @ y)
    u = X * (y - X @ b)[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    V = xtx_inv @ S @ xtx_inv
    return b, np.sqrt(np.maximum(np.diag(V), 0.0))


def slope_block_ci(y, X, j: int, block: int, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Two-sided 95% pairs circular-block-bootstrap interval for coefficient ``j``."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    rng = np.random.default_rng(seed)
    n = len(y)
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    out = np.empty(n_boot)
    for i in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        out[i] = np.linalg.lstsq(X[idx], y[idx], rcond=None)[0][j]
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def sidak(p: float, k: int) -> float:
    """Probability that the smallest of ``k`` independent null p-values is <= p."""
    return float(1.0 - (1.0 - min(max(p, 0.0), 1.0)) ** k)


def _block(n: int) -> int:
    return max(1, min(int(round(n ** (1.0 / 3.0))), max(1, n // 4)))


def sharpe_block_ci(x, block: int, n_boot: int = 2000, seed: int = 0, ppy: int = EQ_PPY) -> tuple[float, float]:
    """Two-sided 95% circular-block-bootstrap interval of the annualised Sharpe of ``x`` (a resample with zero spread
    counts as Sharpe 0)."""
    x = np.asarray(x, float)
    n = len(x)
    rng = np.random.default_rng(seed)
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    idx = ((rng.integers(0, n, (n_boot, nb))[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]) % n
    s = x[idx]
    sd = s.std(axis=1, ddof=1)
    sr = np.where(sd > 0, s.mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0) * math.sqrt(ppy)
    return float(np.quantile(sr, 0.025)), float(np.quantile(sr, 0.975))


# ------------------------------------------------------------------------------------------------ house rule 5 --

Z95 = 1.959964


def _ci_below(ci, bound: float) -> bool:
    """The 95% interval lies wholly at or below ``bound``. False without an interval and for a zero-width one."""
    lo, hi = ci
    return lo is not None and hi is not None and lo < hi and hi <= bound


def _ci_above(ci, bound: float, strict: bool = False) -> bool:
    """The 95% interval lies wholly at or above ``bound`` (strictly above with ``strict``). False as in ``_ci_below``."""
    lo, hi = ci
    return lo is not None and hi is not None and lo < hi and (lo > bound if strict else lo >= bound)


def _rule5(crit, decisive, n: int, min_n: int) -> tuple[str, str, dict]:
    """House rule 5 below the trial's min_n usable days (at or above min_n callers judge their criteria at face value with
    ``_verdict``, exactly as before). ``crit``: the face-value criteria [(name, ok)] other than the day count;
    ``decisive``: one flag per criterion, True when its failure stands below min_n (its 95% interval lies wholly on the
    wrong side of the claimed bound). A passing or decisively failing criterion keeps its bool, any other failure becomes
    None (undecided), and the unmet day-count criterion (None) keeps the verdict from 'supported'.
    Returns (verdict, why, rule-5 record)."""
    crit = [(name, None if ok is None else bool(ok)) for name, ok in crit]
    judged = [(f"at least {min_n} days (only {n}: data limit)", None)]
    judged += [(name, ok) if ok is None or ok else (name + " (fails decisively below min_n)", False) if d
               else (name + " (fails, not decisively, below min_n: undecided)", None) for (name, ok), d in zip(crit, decisive)]
    failed = [name for (name, ok), d in zip(crit, decisive) if ok is False and d]
    v, why = _verdict(judged)
    v0, why0 = _verdict(crit)
    why = (f"only {n} usable days, below the trial's min_n {min_n}, so the verdict cannot be supported and a failing "
           f"criterion counts only when it fails decisively, its 95% interval wholly on the wrong side of the claimed bound "
           f"(house rule 5). Decisive failures: {'; '.join(failed) if failed else 'none'}. {v}: {why} "
           f"(criteria at face value: {v0}, {why0})")
    return v, why, {"min_n": min_n, "n": n, "unit": "usable days", "criteria": [[c, ok] for c, ok in judged],
                    "criteria_at_face_value": [[c, ok] for c, ok in crit], "decisive_failures": failed}


# ------------------------------------------------------------------------------------------------- sessions --

def _utc_day(t) -> str:
    return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d")


def ny_bars(hourly_values) -> dict[str, dict[str, dict]]:
    """{New York day: {New York bar start 'HH:MM': bar value}} from 1h bar values labelled by UTC start time."""
    bars: dict = defaultdict(dict)
    for v in hourly_values:
        ts = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).astimezone(NY)
        bars[ts.strftime("%Y-%m-%d")][ts.strftime("%H:%M")] = v
    return bars


def build_sessions(hourly_values, daily_values, start: str = CLAIM_START, end: str = CLAIM_END) -> dict:
    """Per-session prices for every daily trading day inside the hourly coverage and [start, end].

    Returns {"days", "prev_close", "open", "p1030", "o1530", "close", "co_next" (arrays aligned with days; NaN when a
    piece is missing), "calendar" (all daily trading days), "excluded" {early_close, missing_0930_bar,
    missing_1530_bar, no_hourly_bars, no_daily_bar}, "hourly_first", "hourly_last"}.
    prev_close is C(t-1) f(t-1)/f(t) and co_next is O(t+1) / (C(t) f(t)/f(t+1)) - 1 with f = adjclose/close."""
    bars = ny_bars(hourly_values)
    dly: dict[str, tuple[float, float, float]] = {}
    for v in daily_values:
        if v.get("open") is None or v.get("close") is None:
            continue
        o, c = float(v["open"]), float(v["close"])
        if not (o > 0 and c > 0):
            continue
        adj = v.get("adjclose")
        dly[_utc_day(v["t"])] = (o, c, float(adj) / c if adj is not None and float(adj) > 0 else 1.0)
    cal = sorted(dly)
    pos = {d: i for i, d in enumerate(cal)}
    hdays = sorted(bars)
    excl = {k: [] for k in ("early_close", "missing_0930_bar", "missing_1530_bar", "no_hourly_bars", "no_daily_bar")}
    cols = {k: [] for k in ("prev_close", "open", "p1030", "o1530", "close", "co_next")}
    days: list[str] = []
    out = {"days": days, "calendar": cal, "excluded": excl,
           "hourly_first": hdays[0] if hdays else None, "hourly_last": hdays[-1] if hdays else None}
    if hdays:
        cand = sorted(set(hdays) | {d for d in cal if hdays[0] <= d <= hdays[-1]})
        for d in cand:
            if not (start <= d <= end):
                continue
            b = bars.get(d, {})
            if d not in pos:
                excl["no_daily_bar"].append(d)
                continue
            if not b:
                excl["no_hourly_bars"].append(d)
                continue
            if LAST_BAR not in b and EARLY_CLOSE_TICK in b:
                excl["early_close"].append(d)
                continue
            if FIRST_BAR not in b:
                excl["missing_0930_bar"].append(d)
            if LAST_BAR not in b:
                excl["missing_1530_bar"].append(d)
            i = pos[d]
            o, c, f = dly[d]
            nan = float("nan")
            prev = nan
            if i > 0:
                _, pc, pf = dly[cal[i - 1]]
                prev = pc * pf / f
            co = nan
            if i + 1 < len(cal):
                no, _, nf = dly[cal[i + 1]]
                co = no / (c * f / nf) - 1.0
            days.append(d)
            cols["prev_close"].append(prev)
            cols["open"].append(o)
            cols["p1030"].append(float(b[FIRST_BAR]["close"]) if FIRST_BAR in b else nan)
            cols["o1530"].append(float(b[LAST_BAR]["open"]) if LAST_BAR in b else nan)
            cols["close"].append(c)
            cols["co_next"].append(co)
    for k, v in cols.items():
        out[k] = np.array(v, float)
    return out


def _sel(sess: dict, mask: np.ndarray) -> list[str]:
    return [d for d, k in zip(sess["days"], mask) if k]


def window_short(first: Optional[str], last: Optional[str]) -> bool:
    """True when the usable sessions do not cover the claimed 2023-11..2026-10 (start after November 2023 or end
    before October 2026)."""
    return not first or not last or first > "2023-11-30" or last < "2026-10-01"


def window_note(first: Optional[str], last: Optional[str], hourly_first: Optional[str] = None) -> str:
    """States the archived window and whether it covers the claimed 2023-11..2026-10."""
    if not first:
        return f"no usable sessions inside the claimed {CLAIM_LABEL}"
    short = window_short(first, last)
    base = f"archived window {first}..{last}"
    if hourly_first and hourly_first != first:
        base += f" (1h bars from {hourly_first})"
    if short:
        return base + f", shorter than the claimed {CLAIM_LABEL} (data limit: Yahoo keeps about 730 days of 1h bars)"
    return base + f", inside the claimed {CLAIM_LABEL}"


# ------------------------------------------------------------------------------------------------ calendars --

def third_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def expiration_days(calendar: Sequence[str], months=tuple(range(1, 13))) -> set[str]:
    """Third Friday of each listed month, or the last trading day before it in that month (holiday)."""
    cal = sorted(calendar)
    by_month: dict[str, list[str]] = defaultdict(list)
    for d in cal:
        by_month[d[:7]].append(d)
    out = set()
    for ym, ds in by_month.items():
        y, m = int(ym[:4]), int(ym[5:7])
        if m not in months:
            continue
        tf = third_friday(y, m).isoformat()
        c = [d for d in ds if d <= tf]
        if c and (c[-1] == tf or tf <= cal[-1]):
            out.add(c[-1])
    return out


def month_end_days(calendar: Sequence[str]) -> set[str]:
    """Last trading day of each month, excluding the calendar's final (possibly incomplete) month."""
    last: dict[str, str] = {}
    for d in sorted(calendar):
        last[d[:7]] = d
    if not last:
        return set()
    final = max(last)
    return {d for m, d in last.items() if m != final}


def cpi_release_days(values) -> list[str]:
    """CPI release days from ``macro-release-cpi`` values: a February vintage followed within 7 days by another is the
    seasonal-factor revision and is replaced by the later one; any other vintage under 14 days after the previous kept
    one is a correction and is dropped."""
    keep: list[str] = []
    for d in sorted({v["day"] for v in values}):
        if keep:
            gap = (date.fromisoformat(d) - date.fromisoformat(keep[-1])).days
            if gap < 14:
                if gap <= 7 and d[5:7] == "02" and keep[-1][5:7] == "02":
                    keep[-1] = d
                continue
        keep.append(d)
    return keep


# ---------------------------------------------------------------------------------------- T-427 intraday momentum --

def momentum_leg(sess: dict, cost_rt: float = 0.0002, threshold: float = 0.0) -> dict:
    """Signed last-half-hour returns: position sign(r1) (0 when |r1| <= threshold) from the 15:30 bar open to the
    official close; net = gross - cost_rt per traded day."""
    pc, p1, o3, c = sess["prev_close"], sess["p1030"], sess["o1530"], sess["close"]
    m = np.isfinite(pc) & np.isfinite(p1) & np.isfinite(o3) & np.isfinite(c) & (pc > 0) & (o3 > 0)
    r1 = p1[m] / pc[m] - 1.0
    last = c[m] / o3[m] - 1.0
    pos = np.sign(r1) * (np.abs(r1) > threshold)
    gross = pos * last
    net = gross - cost_rt * (pos != 0)
    return {"days": _sel(sess, m), "r1": r1, "last": last, "pos": pos, "gross": gross, "net": net}


def _bps(x) -> Optional[float]:
    return None if x is None else float(x) * 1e4


def _leg_summary(leg: dict) -> dict:
    n = len(leg["net"])
    if n == 0:
        return {"n": 0, "mean_net_bps": None, "mean_gross_bps": None, "hac_t": None}
    return {"n": n, "first": leg["days"][0], "last": leg["days"][-1],
            "mean_net_bps": _bps(leg["net"].mean()), "mean_gross_bps": _bps(leg["gross"].mean()),
            "hac_t": nw_mean_t(leg["net"]), "trades": int((leg["pos"] != 0).sum())}


def _regime_split(leg: dict, regimes: Optional[dict]) -> dict:
    out = {}
    for name, days in (regimes or {}).items():
        f = np.array([d in days for d in leg["days"]], bool)
        out[name] = {"n_on": int(f.sum()),
                     "mean_net_on_bps": _bps(leg["net"][f].mean()) if f.any() else None,
                     "mean_net_off_bps": _bps(leg["net"][~f].mean()) if (~f).any() else None}
    return out


def intraday_momentum(spy: dict, others: Optional[dict] = None, cost_rt: float = 0.0002, n_cells: int = 60,
                      min_n: int = MIN_N, alpha: float = 0.05, regimes: Optional[dict] = None, n_boot: int = 2000,
                      seed: int = 0) -> dict:
    """T-427 on sessions from ``build_sessions``. ``others`` = {"QQQ": sessions or None, "IWM": sessions or None}.
    Below ``min_n`` usable days house rule 5 applies: never supported; the mean criterion fails decisively when the
    mean's 95% block-bootstrap CI lies wholly at or below 0; the deflated-p criterion (a one-sided 95% test) when the PSR
    against a zero Sharpe is <= ``alpha`` (the Sharpe's one-sided 95% upper bound at or below 0; the deflation benchmark
    is >= 0) or that mean CI lies wholly at or below 0; the QQQ/IWM criterion when either asset's HAC t of its mean net
    return is <= -1.96. The PSR is reported in ``rule5`` and the reason. Under 8 usable days nothing is computed."""
    others = {"QQQ": None, "IWM": None} if others is None else others
    leg = momentum_leg(spy, cost_rt)
    n = len(leg["net"])
    ex = spy.get("excluded", {})
    first, last = (leg["days"][0], leg["days"][-1]) if n else (None, None)
    wnote = window_note(first, last, spy.get("hourly_first"))
    rep: dict = {"n": n, "window": {"first": first, "last": last, "hourly_first": spy.get("hourly_first"),
                                    "hourly_last": spy.get("hourly_last"), "claimed": CLAIM_LABEL, "note": wnote},
                 "excluded": {k: len(v) for k, v in ex.items()}, "excluded_days": {k: list(v) for k, v in ex.items() if v},
                 "cost_round_trip_bps": cost_rt * 1e4, "n_cells": n_cells, "annualisation": EQ_PPY}
    if n < 8:
        v, why = _verdict([(f"at least {min_n} days (only {n} usable sessions: data limit)", None)])
        rep.update(verdict=v, reason=f"SPY: {n} usable sessions; {wnote} — {why}")
        return rep
    net = leg["net"]
    mean_net = float(net.mean())
    t_hac = nw_mean_t(net)
    ci = _mean_ci(net, _block(n), n_boot=n_boot, seed=seed)
    p_raw = block_bootstrap_pvalue(net, np.zeros(n), n_boot=n_boot, seed=seed)
    dsr = float(deflated_sharpe_ratio(net, n_trials=n_cells))
    p_defl = 1.0 - dsr
    X = np.column_stack([np.ones(n), leg["r1"]])
    b, se = ols_hac(leg["last"], X)
    per = {}
    for sym, s in others.items():
        per[sym] = _leg_summary(momentum_leg(s, cost_rt)) if s is not None else None
    rep.update({
        "mean_net_bps": mean_net * 1e4, "mean_gross_bps": float(leg["gross"].mean()) * 1e4,
        "trades": int((leg["pos"] != 0).sum()), "long_days": int((leg["pos"] > 0).sum()),
        "short_days": int((leg["pos"] < 0).sum()), "hit_rate_net": float((net > 0).mean()),
        "hac_t": t_hac, "hac_lag": _nw_lag(n), "ci95_mean_net_bps": [ci[0] * 1e4, ci[1] * 1e4],
        "p_raw_block_bootstrap": p_raw, "dsr": dsr, "p_deflated": p_defl,
        "sharpe_net_annual": sharpe_ratio(net, EQ_PPY), "sharpe_net_per_day": sharpe_ratio(net),
        "diagnostic_slope_last_on_r1": float(b[1]), "diagnostic_slope_hac_t": float(b[1] / se[1]) if se[1] > 0 else None,
        "others": per, "regimes": _regime_split(leg, regimes),
        "not_run": "the rest of the 60-cell grid (reversal sign, 0.5-sigma threshold, high-VIX / FOMC-CPI conditioning, "
                   "GLD and the Coinbase BTC session variant); the deflation still charges for 60 cells",
    })
    oth_txt = "; ".join(
        f"{s} mean net {per[s]['mean_net_bps']:+.2f} bps (n={per[s]['n']}, HAC t {per[s]['hac_t']:+.2f})"
        if per[s] and per[s]["n"] and per[s]["hac_t"] is not None else f"{s} not available" for s in per)
    exc = rep["excluded"]
    head = (f"SPY {first}..{last}, n={n} sessions ({exc.get('early_close', 0)} early closes, "
            f"{exc.get('missing_0930_bar', 0)} day(s) without the 09:30 bar, {exc.get('missing_1530_bar', 0)} without "
            f"the 15:30 bar and {exc.get('no_daily_bar', 0)} without an available daily bar excluded); {wnote}. Rule sign(prev close->10:30) held 15:30 bar open->official close: "
            f"mean net {mean_net * 1e4:+.2f} bps/day (gross {rep['mean_gross_bps']:+.2f} bps, cost {cost_rt * 1e4:.0f} bps "
            f"round trip on {rep['trades']} trades), HAC t {t_hac:+.2f}, 95% block-bootstrap CI "
            f"[{ci[0] * 1e4:+.2f}, {ci[1] * 1e4:+.2f}] bps, raw p {p_raw:.3f}, annualised net Sharpe "
            f"{rep['sharpe_net_annual']:+.2f}; DSR over {n_cells} cells {dsr:.3f} -> deflated p {p_defl:.3f} "
            f"(needs < {alpha}); {oth_txt}; diagnostic slope of the last half hour on r1 {b[1]:+.4f} "
            f"(HAC t {rep['diagnostic_slope_hac_t']:+.2f})")
    same = None
    if all(per.get(s) and per[s]["n"] for s in ("QQQ", "IWM")):
        same = bool(per["QQQ"]["mean_net_bps"] > 0 and per["IWM"]["mean_net_bps"] > 0)
    if n < min_n:
        # rule 5: the mean fails decisively when its 95% CI lies wholly at or below 0. The deflated p (DSR > 1 - alpha, a
        # one-sided test of SR > SR* >= 0) is mirrored at its own confidence: the Sharpe's one-sided 95% upper bound lies
        # at or below 0, i.e. the PSR against a zero Sharpe (the same draws) is <= alpha; SR* >= 0 at any length, so the
        # DSR is then <= alpha against every benchmark. A mean CI wholly at or below 0 (one-sided 97.5%) also decides it.
        # The QQQ/IWM sign when either asset's 95% HAC interval lies wholly at or below 0 (HAC t <= -1.96).
        down = _ci_below(ci, 0.0)
        psr0 = float(deflated_sharpe_ratio(net, n_trials=1))
        dsr0_down = bool(mean_net < 0 and psr0 <= alpha)
        oth_down = any(per.get(s) and per[s]["n"] >= 8 and per[s]["hac_t"] is not None and per[s]["hac_t"] <= -Z95
                       for s in ("QQQ", "IWM"))
        v, why, r5 = _rule5([
            (f"archived window covers the claimed {CLAIM_LABEL}", None if window_short(first, last) else True),
            ("SPY mean net return > 0", mean_net > 0),
            (f"deflated p < {alpha} over {n_cells} cells", p_defl < alpha),
            ("same sign on QQQ and IWM (mean net return > 0 on both)", same),
        ], [False, down, dsr0_down or down, oth_down], n, min_n)
        r5["psr_vs_zero_sharpe"] = psr0
        psr_txt = (f"; PSR against a zero Sharpe {psr0:.3f} (the deflated-p criterion fails decisively below min_n when "
                   f"<= {alpha}, the Sharpe's one-sided {1 - alpha:.0%} upper bound at or below 0)")
        rep.update(verdict=v, reason=head + psr_txt + " — " + why, rule5=r5)
        return rep
    v, why = _verdict([
        (f"at least {min_n} days", n >= min_n),
        (f"archived window covers the claimed {CLAIM_LABEL}", None if window_short(first, last) else True),
        ("SPY mean net return > 0", mean_net > 0),
        (f"deflated p < {alpha} over {n_cells} cells", p_defl < alpha),
        ("same sign on QQQ and IWM (mean net return > 0 on both)", same),
    ])
    rep.update(verdict=v, reason=head + " — " + why)
    return rep


# ------------------------------------------------------------------------------------- T-428 closing reversal --

def reversal_data(sess: dict) -> dict:
    """Aligned regression inputs: L (15:30 bar open -> official close), R (official open -> 15:30), y = CO(t+1)."""
    o, o3, c, y = sess["open"], sess["o1530"], sess["close"], sess["co_next"]
    m = np.isfinite(o) & np.isfinite(o3) & np.isfinite(c) & np.isfinite(y) & (o > 0) & (o3 > 0)
    return {"mask": m, "days": _sel(sess, m), "L": c[m] / o3[m] - 1.0, "R": o3[m] / o[m] - 1.0, "y": y[m]}


def _slope_only(sess: Optional[dict]) -> Optional[dict]:
    if sess is None:
        return None
    d = reversal_data(sess)
    n = len(d["y"])
    if n < 10:
        return {"n": n, "slope": None, "hac_t": None}
    b, se = ols_hac(d["y"], np.column_stack([np.ones(n), d["L"], d["R"]]))
    return {"n": n, "slope": float(b[1]), "hac_t": float(b[1] / se[1]) if se[1] > 0 else None}


def closing_reversal(sess: dict, l_decision=None, open_cost: float = 0.0001, n_cells: int = 32,
                     slope_max: float = -0.2, alpha: float = 0.01, sharpe_min: float = 0.5, min_n: int = MIN_N,
                     others: Optional[dict] = None, regimes: Optional[dict] = None, n_boot: int = 2000,
                     seed: int = 0) -> dict:
    """T-428 on sessions from ``build_sessions``. ``l_decision``: optional array aligned with ``sess['days']`` holding
    the last-half-hour return measured to 15:45 (the MOC decision state); without it the reversal-leg criterion is not
    implemented. ``others`` = {symbol: sessions} for the other declared assets (diagnostic slopes). Below ``min_n``
    usable days house rule 5 applies: never supported; the slope fails decisively when its 95% block-bootstrap CI lies
    wholly above ``slope_max``, the deflated p when it lies wholly at or above 0, and the reversal leg when its
    annualised Sharpe's 95% block-bootstrap interval lies wholly at or below ``sharpe_min``. Under 10 usable days
    nothing is computed."""
    d = reversal_data(sess)
    n = len(d["y"])
    ex = sess.get("excluded", {})
    first, last = (d["days"][0], d["days"][-1]) if n else (None, None)
    wnote = window_note(first, last, sess.get("hourly_first"))
    rep: dict = {"n": n, "window": {"first": first, "last": last, "hourly_first": sess.get("hourly_first"),
                                    "hourly_last": sess.get("hourly_last"), "claimed": CLAIM_LABEL, "note": wnote},
                 "excluded": {k: len(v) for k, v in ex.items()}, "excluded_days": {k: list(v) for k, v in ex.items() if v},
                 "open_cost_bps": open_cost * 1e4, "n_cells": n_cells, "annualisation": EQ_PPY}
    if n < 10:
        v, why = _verdict([(f"at least {min_n} days (only {n} usable close-to-open pairs: data limit)", None)])
        rep.update(verdict=v, reason=f"SPY: {n} usable close-to-open pairs; {wnote} — {why}")
        return rep
    L, R, y = d["L"], d["R"], d["y"]
    X = np.column_stack([np.ones(n), L, R])
    b, se = ols_hac(y, X)
    t = float(b[1] / se[1]) if se[1] > 0 else 0.0
    p_one = _phi(t)                 # P(Z <= t): one-sided p for H0 b >= 0 against b < 0
    p_defl = sidak(p_one, n_cells)
    ci = slope_block_ci(y, X, 1, _block(n), n_boot=n_boot, seed=seed)
    bu, seu = ols_hac(y, np.column_stack([np.ones(n), L]))
    # LOOK-AHEAD proxy: sized on L measured to the official close, which is the fill price itself.
    pos_p = -np.sign(L)
    net_p = pos_p * y - open_cost * (pos_p != 0)
    thr = np.abs(L) > 0.002
    net_thr = net_p[thr]
    rep.update({
        "slope_L": float(b[1]), "slope_hac_se": float(se[1]), "slope_hac_t": t, "hac_lag": _nw_lag(n),
        "p_one_sided": p_one, "p_deflated_sidak": p_defl, "slope_ci95": list(ci),
        "intercept_overnight_mean_bps": float(b[0]) * 1e4, "coef_open_to_1530": float(b[2]),
        "coef_open_to_1530_hac_t": float(b[2] / se[2]) if se[2] > 0 else None,
        "slope_univariate": float(bu[1]), "slope_univariate_hac_t": float(bu[1] / seu[1]) if seu[1] > 0 else None,
        "mean_L_bps": float(L.mean()) * 1e4, "sd_L_bps": float(L.std(ddof=1)) * 1e4,
        "mean_co_next_bps": float(y.mean()) * 1e4,
        "proxy_reversal_LOOK_AHEAD": {
            "note": "position -sign(L) with L measured to the official close (the fill price): not tradable at the "
                    "15:50 MOC cutoff; diagnostic only",
            "mean_net_bps": float(net_p.mean()) * 1e4, "sharpe_net_annual": sharpe_ratio(net_p, EQ_PPY),
            "abs_L_over_20bps": {"n": int(thr.sum()),
                                 "mean_net_bps": float(net_thr.mean()) * 1e4 if thr.any() else None,
                                 "sharpe_net_annual": sharpe_ratio(net_thr, EQ_PPY) if thr.sum() > 2 else None}},
        "others": {s: _slope_only(v) for s, v in (others or {}).items()},
    })
    reg = {}
    for name, days in (regimes or {}).items():
        f = np.array([dd in days for dd in d["days"]], bool)
        k = int(f.sum())
        entry = {"n": k, "proxy_mean_net_bps": float(net_p[f].mean()) * 1e4 if k else None}
        if k >= 10:
            bb, ss = ols_hac(y[f], np.column_stack([np.ones(k), L[f]]), lag=0)
            entry.update(slope_univariate=float(bb[1]), slope_t=float(bb[1] / ss[1]) if ss[1] > 0 else None)
        reg[name] = entry
    rep["regimes"] = reg
    leg_txt, leg_ok, leg_net = "", None, None
    if l_decision is not None:
        ld = np.asarray(l_decision, float)[d["mask"]]
        pos = -np.sign(np.where(np.isfinite(ld), ld, 0.0))
        net = leg_net = pos * y - open_cost * (pos != 0)
        sh = sharpe_ratio(net, EQ_PPY)
        rep["reversal_leg"] = {"signal": "L measured to 15:45 (supplied)", "mean_net_bps": float(net.mean()) * 1e4,
                               "sharpe_net_annual": sh, "trades": int((pos != 0).sum())}
        leg_ok = bool(sh > sharpe_min)
        leg_txt = (f"reversal leg sized on the 15:45 state: net {net.mean() * 1e4:+.2f} bps/day, annualised net Sharpe "
                   f"{sh:+.2f} (needs > {sharpe_min})")
    else:
        rep["reversal_leg"] = None
        lp = rep["proxy_reversal_LOOK_AHEAD"]
        leg_txt = (f"reversal leg sized on the 15:45 state not built (1h bars hold no price between 15:30 and the "
                   f"close); LOOK-AHEAD proxy sized on L to the official close: net {lp['mean_net_bps']:+.2f} bps/day, "
                   f"annualised Sharpe {lp['sharpe_net_annual']:+.2f}, diagnostic only")
    oth = rep["others"]
    oth_txt = "; ".join(f"{s} slope {o['slope']:+.3f} (HAC t {o['hac_t']:+.2f}, n={o['n']})"
                        if o and o.get("slope") is not None and o.get("hac_t") is not None else f"{s} not available"
                        for s, o in oth.items())
    exc = rep["excluded"]
    no_next = int((np.isfinite(sess["o1530"]) & ~np.isfinite(sess["co_next"])).sum())
    head = (f"SPY {first}..{last}, n={n} close-to-next-open pairs ({exc.get('early_close', 0)} early closes, "
            f"{exc.get('missing_1530_bar', 0)} day(s) without the 15:30 bar and {exc.get('no_daily_bar', 0)} without an "
            f"available daily bar excluded; {no_next} without an archived next open); {wnote}. "
            f"OLS CO(t+1) = a + b L + c R(open->15:30): b = {b[1]:+.3f} (HAC t {t:+.2f}, one-sided p {p_one:.4f}, "
            f"Sidak over {n_cells} cells {p_defl:.4f}, 95% block-bootstrap CI [{ci[0]:+.3f}, {ci[1]:+.3f}]) vs "
            f"b <= {slope_max} and deflated p < {alpha}; a = {b[0] * 1e4:+.2f} bps, c = {b[2]:+.3f}; univariate "
            f"b {bu[1]:+.3f}; {leg_txt}" + (f"; {oth_txt}" if oth_txt else ""))
    if n < min_n:
        # rule 5: the slope fails decisively when its 95% block-bootstrap CI lies wholly above -0.2, the deflated p when
        # it lies wholly at or above 0; the reversal leg when its Sharpe's 95% block-bootstrap interval lies wholly at or
        # below 0.5
        sh_ci = sharpe_block_ci(leg_net, _block(n), n_boot, seed) if leg_net is not None else (None, None)
        v, why, r5 = _rule5([
            (f"archived window covers the claimed {CLAIM_LABEL}", None if window_short(first, last) else True),
            (f"slope <= {slope_max}", bool(b[1] <= slope_max)),
            (f"deflated (Sidak, {n_cells} cells) one-sided p < {alpha}", p_defl < alpha),
            (f"reversal-leg net Sharpe > {sharpe_min} sized on the 15:45 state (needs sub-hourly bars)", leg_ok),
        ], [False, _ci_above(ci, slope_max, strict=True), _ci_above(ci, 0.0), _ci_below(sh_ci, sharpe_min)], n, min_n)
        r5["reversal_leg_sharpe_ci95"] = list(sh_ci)
        sh_txt = (f"; reversal-leg Sharpe 95% block-bootstrap interval [{sh_ci[0]:+.2f}, {sh_ci[1]:+.2f}]"
                  if sh_ci[0] is not None else "")
        rep.update(verdict=v, reason=head + sh_txt + " — " + why, rule5=r5)
        return rep
    v, why = _verdict([
        (f"at least {min_n} days", n >= min_n),
        (f"archived window covers the claimed {CLAIM_LABEL}", None if window_short(first, last) else True),
        (f"slope <= {slope_max}", bool(b[1] <= slope_max)),
        (f"deflated (Sidak, {n_cells} cells) one-sided p < {alpha}", p_defl < alpha),
        (f"reversal-leg net Sharpe > {sharpe_min} sized on the 15:45 state (needs sub-hourly bars)", leg_ok),
    ])
    rep.update(verdict=v, reason=head + " — " + why)
    return rep


# ------------------------------------------------------------------------------------------------ data access --

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except KeyError:
        return False


def _values(archive, name: str) -> list[dict]:
    """Row values of a bundle, keeping only rows available when the bundle was captured."""
    e = archive.get(name)
    cap = getattr(e, "created_at", None) if e is not None else None
    return [r["value"] for r in archive.load(name)
            if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_name(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def _sessions(archive, sym: str) -> Optional[dict]:
    h, dname = "hourly-" + sym, _daily_name(sym)
    if not (_has(archive, h) and _has(archive, dname)):
        return None
    return build_sessions(_values(archive, h), _values(archive, dname))


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _clean(x):
    """JSON-safe copy (numpy scalars/arrays to Python, non-finite floats to None)."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_clean(v) for v in (sorted(x) if isinstance(x, set) else x)]
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


# --------------------------------------------------------------------------------------------------- harnesses --

def hourly_half_hour_momentum(archive):
    """T-427: SPY 15:30->close in the direction of prev close->10:30, net of 2 bps, 2023-11..2026-10, QQQ/IWM sign."""
    miss = _missing(archive, ["hourly-SPY", "daily-history-SPY"])
    if miss:
        return miss
    spy = _sessions(archive, "SPY")
    others = {s: _sessions(archive, s) for s in ("QQQ", "IWM")}
    regimes = {"monthly_opex": expiration_days(spy["calendar"])}
    if _has(archive, "fomc-meetings"):
        regimes["fomc_scheduled"] = {v["decision_day"] for v in _values(archive, "fomc-meetings") if v.get("scheduled")}
    if _has(archive, "macro-release-cpi"):
        regimes["cpi_release"] = set(cpi_release_days(_values(archive, "macro-release-cpi")))
    return _wrap(intraday_momentum(spy, others, regimes=regimes))


def hourly_closing_reversal(archive):
    """T-428: slope of SPY close-to-next-open on the last-half-hour return (15:30 bar open to official close)."""
    miss = _missing(archive, ["hourly-SPY", "daily-history-SPY"])
    if miss:
        return miss
    spy = _sessions(archive, "SPY")
    others = {s: _sessions(archive, s) for s in ("QQQ", "IWM", "GLD")}
    regimes = {"month_end": month_end_days(spy["calendar"]),
               "triple_witching": expiration_days(spy["calendar"], months=(3, 6, 9, 12))}
    return _wrap(closing_reversal(spy, l_decision=None, others=others, regimes=regimes))


HARNESSES = {
    "hourly_half_hour_momentum": hourly_half_hour_momentum,
    "hourly_closing_reversal": hourly_closing_reversal,
}

THEORY_MAP = {
    "T-427": "hourly_half_hour_momentum",
    "T-428": "hourly_closing_reversal",
}
