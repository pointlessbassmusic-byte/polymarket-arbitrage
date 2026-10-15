"""
Crypto, metals, oil and bond options claims from the library, tested on archived index histories.
=================================================================================================

Model-free claims compare an implied-vol index (DVOL for BTC/ETH, GVZ for gold, OVX for oil, VXTLT for bonds, VIX for SPX)
with subsequently realised volatility of the matching ETF or coin. Model-priced claims reuse the structure engine with the
index as a flat implied vol (the claims say "flat IV", so no smile). Calendar conventions: equity ETFs use trading days and
252/yr; BTC/ETH use calendar days and 365/yr. Verdicts follow the shared rule in underlying2._verdict. Below the trial's
min_n (in the claim's own units: non-overlapping signals, entries, episodes or cycles) house rule 5 applies before _verdict
(see _rule5): the verdict is never supported, and a failing criterion still counts only when it fails decisively (its
interval lies wholly on the wrong side of the claimed bound, or the failure would persist at min_n whatever the missing
observations are); any other failure there is undecided (None), so the verdict is inconclusive.

House rule 10 (no arbitrary grid phase). The option-writing claims name monthly options (T-253/T-254/T-270/T-279 'each month',
T-176 'the last-Friday cycle'), so their cycles follow the standard monthly expiry, written at one expiry and settled at the next:
the third Friday (the prior session on a holiday) for GLD; Deribit's last Friday of the month (08:00 UTC) for BTC, whose daily close
is 24:00 UTC, so the BTC cycles run between the last closes before expiry (the Thursdays) and T-176 settles at the Friday's 08:00
delivery price. Claims on a cycle grid that names no calendar (T-245's 21-day variance cycles, T-514's 20-day samples, T-267's
30-day put rolls, and the 21- or 30-day variance-premium cycles of T-244/T-246/T-271/T-512) take the pooled all-phase estimate as
the primary statistic for every criterion: an entry on every day (every phase of the grid), a circular block bootstrap with blocks
of at least twice the hold, n and min_n in the claim's own cycles; each reason reports the per-phase range and how many of the
phases pass on their own. Unaffected: T-175/T-177 (statistics on the daily series), and the event-triggered entries of
ratio_extremes (T-247/T-266), ratio_mean_reversion_signal (T-274) and conditional_straddle (T-256/T-272), where each entry is fixed by
its signal, not by a grid phase (conditional_straddle's all-days arm already pools every day with blocks of twice the hold).
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from typing import Optional

import numpy as np

from mandel.experiments.structures import monthly_cycles, run_structure
from mandel.experiments.underlying2 import _mdd, _mean_ci, _sharpe_diff_lower, _sr, _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

# Per-trial settings for functions that run.py wires to two theories, keyed by (function, label). The values are the registry's
# min_n in each claim's own units (and T-266's level statistic). An explicit argument always wins over this table.
_TRIAL = {
    ("ratio_extremes", "GVZ/VIX"): {"min_n": 40, "statistic": "log"},          # T-247: non-overlapping 21-day signals
    ("ratio_extremes", "ETH/BTC DVOL"): {"min_n": 25, "statistic": "level"},   # T-266: mean of RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC
    ("conditional_straddle", "DVOL"): {"min_n": 25},                           # T-256: non-overlapping low-DVOL entries
    ("conditional_straddle", "GVZ"): {"min_n": 20},                            # T-272: non-overlapping low-GVZ entries
    ("covered_call_vs_hold", "DVOL"): {"min_n": 60, "calendar": "deribit"},    # T-253: monthly cycles
    ("covered_call_vs_hold", "GVZ"): {"min_n": 100, "calendar": "monthly"},    # T-270
    ("short_put_mean", "DVOL"): {"min_n": 60, "calendar": "deribit"},          # T-254
    ("short_put_mean", "GVZ"): {"min_n": 100, "calendar": "monthly"},          # T-279
    # gap_test: claims stated on non-overlapping cycles (rule 10: the daily series is their pooled all-phase estimate); keyed by label,
    # plus ' thirds' for T-244, which shares T-271's label. T-175 and T-177 are daily statistics and have no entry.
    ("gap_test", "GVZ^2 vs GLD thirds"): {"cycle": 21, "min_n": 180},           # T-244: non-overlapping 21-day cycles
    ("gap_test", "GVZ^2 vs GLD"): {"cycle": 21, "min_n": 150},                  # T-271: non-overlapping windows (21 trading days)
    ("gap_test", "DVOL^2 vs BTC"): {"cycle": 30, "min_n": 60},                  # T-246: non-overlapping 30-calendar-day cycles
    ("gap_test", "OVX^2 vs USO"): {"cycle": 21, "min_n": 150},                  # T-512
}


def _trial(fn: str, label: str, key: str, given, default):
    return given if given is not None else _TRIAL.get((fn, label), {}).get(key, default)


def _rule5(rows, n: int, min_n: Optional[int], unit: str) -> tuple[str, str]:
    """House rule 5, applied before _verdict. rows: [(name, ok, decisive)] with ok True / False / None (not implemented) and decisive
    True when a failure stands below min_n: the criterion's interval lies wholly on the wrong side of the claimed bound, or the failure
    would persist at min_n whatever the missing observations turn out to be. At or above min_n (or with no min_n) every criterion is
    judged as it is. Below min_n a passing or decisively failing criterion keeps its bool, any other failure becomes None (undecided),
    and an unmet min_n criterion (None) keeps the verdict from 'supported'."""
    face = [(name, None if ok is None else bool(ok)) for name, ok, _ in rows]
    if not min_n or n >= min_n:
        return _verdict(face)
    crit = [(name, None) if ok is None else (name, True) if ok else (name + " (fails decisively below min_n)", False) if decisive
            else (name + " (fails, not decisively, below min_n: undecided)", None) for name, ok, decisive in rows]
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", None))
    v, why = _verdict(crit)
    v0, why0 = _verdict(face)
    return v, (f"only {n} {unit}, below the trial's min_n {min_n}, so the verdict cannot be supported and a failing criterion counts only "
               f"when it fails decisively (house rule 5): {v}, {why} (criteria: {v0}, {why0})")


def _rate_fails_at_min_n(hits: int, n: int, min_n: Optional[int], need: float) -> bool:
    """A 'rate > need' criterion fails at min_n even if every missing observation were a hit: (hits + min_n - n) / min_n <= need."""
    return bool(min_n) and n < min_n and (hits + min_n - n) / min_n <= need


def _first_half_fails_at_min_n(n: int, min_n: Optional[int], first_half_ok) -> bool:
    """A 'positive in both halves' criterion fails at min_n whatever comes when the first half at min_n (the first min_n // 2
    observations, already observed once n >= min_n // 2; later data only appends) already fails. first_half_ok(h) judges the first
    h observations."""
    h = (min_n or 0) // 2
    return bool(min_n) and h >= 1 and h <= n < min_n and not first_half_ok(h)


def _settled_windows_bad(n_rows: int, min_rows: int, bad) -> int:
    """A '>= 2 of 3 windows' criterion at min_n: how many of the three windows of the first min_rows rows (np.array_split) are already
    fully observed (later data only appends) and fail. bad(s) judges the rows s."""
    return sum(bool(bad(s)) for s in np.array_split(np.arange(min_rows), 3) if len(s) and s[-1] < n_rows)


def _phases_txt(stats, passes, fmt: str = "{:+.2f}") -> str:
    """Rule 10: the claimed statistic on each phase of the grid on its own, and how many phases pass all criteria."""
    return f"per phase {fmt.format(min(stats))} to {fmt.format(max(stats))}, {sum(bool(p) for p in passes)} of {len(passes)} phases pass on their own"


def _deribit_expiry_sessions(days) -> list:
    """Deribit's standard monthly BTC expiry is 08:00 UTC on the last Friday of the month. A daily close is 24:00 UTC, so the last close
    before expiry is the Thursday's (the prior available day when it is missing). Only months whose Thursday lies inside the data."""
    ds = [str(d) for d in days]; out = []
    if not ds:
        return out
    y, m = int(ds[0][:4]), int(ds[0][5:7])
    while (y, m) <= (int(ds[-1][:4]), int(ds[-1][5:7])):
        last = date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)
        thu = (last - timedelta(days=(last.weekday() - 4) % 7 + 1)).isoformat()      # the day before the month's last Friday
        if ds[0] <= thu <= ds[-1]:
            e = ds[bisect_right(ds, thu) - 1]
            if not out or e != out[-1]:
                out.append(e)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _calendar_cycles(days, calendar) -> tuple[list, str]:
    """(entry, expiry) cycles of a named expiry calendar (house rule 10), and its description. 'monthly': the standard monthly expiry
    (third Friday, the prior session on a holiday); 'deribit': Deribit's last-Friday monthly expiry, between the last closes before
    each expiry; a list of (entry, expiry) pairs is used as given."""
    if calendar == "monthly":
        return monthly_cycles(days), "standard monthly expiry calendar (third Friday, the prior session on a holiday), each written at one expiry close and settled at the next"
    if calendar == "deribit":
        e = _deribit_expiry_sessions(days)
        return list(zip(e[:-1], e[1:])), ("Deribit monthly expiry calendar (last Friday 08:00 UTC), each written at the last daily close before one expiry "
                                          "(the Thursday) and settled at the last close before the next")
    if isinstance(calendar, (list, tuple)):
        return [tuple(c) for c in calendar], "explicit (entry, expiry) schedule"
    raise ValueError(f"calendar must be 'monthly', 'deribit' or a list of (entry, expiry) pairs, got {calendar!r}")


def _asof(series: dict):
    """Point-in-time lookup: the value on day d, else the last value before d."""
    keys = sorted(series)
    def get(d):
        if d in series:
            return series[d]
        k = bisect_right(keys, d)
        if k == 0:
            raise KeyError(f"no value on or before {d}")
        return series[keys[k - 1]]
    return get


def _block_mean_draws(x: np.ndarray, block: int, n_boot: int = 2000, seed: int = 0) -> np.ndarray:
    """Circular block-bootstrap draws of the mean of x."""
    rng = np.random.default_rng(seed); n = len(x); b = max(1, min(int(block), n)); nb = math.ceil(n / b); m = np.empty(n_boot)
    for i in range(n_boot):
        m[i] = x[((rng.integers(0, n, nb)[:, None] + np.arange(b)[None, :]).ravel()[:n]) % n].mean()
    return m


def _align(days, closes, idx: dict):
    keep = [i for i, d in enumerate(days) if d in idx]
    return [days[i] for i in keep], closes[keep], np.array([idx[days[i]] for i in keep])


def _fwd_rv(closes, i, n, ppy):
    r = np.diff(np.log(closes[i:i + n + 1])); return float(np.sqrt(np.sum(r ** 2) * ppy / n))


def iv_minus_rv(days, closes, idx, n, ppy, units="vol", start=None):
    """Daily series of IV - forward realised over n periods; units 'vol' (vol points) or 'var' (annualised variance)."""
    d, c, iv = _align(days, closes, idx)
    out, ds = [], []
    for i in range(len(c) - n):
        if start and d[i] < start:
            continue
        rv = _fwd_rv(c, i, n, ppy)
        out.append((iv[i] - rv * 100) if units == "vol" else ((iv[i] / 100) ** 2 - rv ** 2)); ds.append(d[i])
    return ds, np.array(out)


def gap_test(days, closes, idx, n, ppy, threshold, units, block, thirds=False, start=None, label="", cycle: Optional[int] = None, min_n: Optional[int] = None):
    """Mean of implied minus forward realised over n periods, on the daily series. A claim stated on the daily series (T-175, T-177)
    is judged on it as before. A claim stated on non-overlapping `cycle`-day cycles (T-244, T-246, T-271, T-512; cycle and min_n
    default to the _TRIAL entry for the label, plus ' thirds' when thirds is set) names no entry calendar, so under house rule 10 the
    daily series is its pooled all-phase estimate and the primary statistic for every criterion: blocks of at least 2 x cycle days,
    n and min_n in cycles (house rule 5 below it), and the reason reports each of the `cycle` phases (x[k::cycle], blocks of 3 cycles)."""
    ds, x = iv_minus_rv(days, closes, idx, n, ppy, units, start)
    key = label + " thirds" if thirds else label
    cycle = _trial("gap_test", key, "cycle", cycle, None); min_n = _trial("gap_test", key, "min_n", min_n, None)
    if cycle:
        block = max(block, 2 * cycle)

    def judge(v, b):                              # (lo, hi, [(criterion, passes)], text) for the series v with blocks of b
        lo, hi = _mean_ci(v, b)
        if thirds:
            t3 = [float(z.mean()) for z in np.array_split(v, 3)]
            shape = ("positive in >= 2 of 3 thirds", sum(z > 0 for z in t3) >= 2); txt = f", thirds " + "/".join(f"{z:+.4f}" for z in t3)
        else:
            h = len(v) // 2; halves = [float(v[:h].mean()), float(v[h:].mean())]
            shape = ("same sign in both halves", np.sign(halves[0]) == np.sign(halves[1]) == np.sign(v.mean())); txt = f", halves {halves[0]:+.4f}/{halves[1]:+.4f}"
        return lo, hi, [(f"lower 95% CI > {threshold}", lo > threshold), shape], txt

    lo, hi, crit, extra = judge(x, block)
    unit = "vol pts" if units == "vol" else "variance"
    if not cycle:
        v, why = _verdict(crit)
        return {"n": int(len(x)), "first_day": ds[0], "mean": float(x.mean()), "ci": [lo, hi], "verdict": v,
                "reason": f"{label} implied minus realised over {n} periods: {x.mean():+.4f} {unit} since {ds[0]} (95% CI {lo:+.4f} to {hi:+.4f}){extra} — {why}"}
    phases = [judge(x[k::cycle], 3) for k in range(min(cycle, len(x)))]
    p_mean = [float(x[k::cycle].mean()) for k in range(len(phases))]; p_ok = [all(bool(ok) for _, ok in p[2]) for p in phases]
    n_cyc = len(x[0::cycle])                      # non-overlapping cycles, the claim's unit (the most any phase holds)
    if thirds:                                    # >= 2 of the 3 windows at min_n already observed and not positive
        dec_shape = bool(min_n) and n_cyc < min_n and _settled_windows_bad(len(x), min_n * cycle, lambda s: not x[s].mean() > 0) >= 2
    else:
        dec_shape = _first_half_fails_at_min_n(n_cyc, min_n, lambda k: x[:k * cycle].mean() > 0)
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([(crit[0][0], crit[0][1], hi <= threshold), (crit[1][0], crit[1][1], dec_shape)], n_cyc, min_n, f"non-overlapping {cycle}-day cycles")
    return {"n": int(n_cyc), "n_days": int(len(x)), "cycle": cycle, "min_n": min_n, "first_day": ds[0], "mean": float(x.mean()), "ci": [lo, hi], "block": int(block),
            "phase_means": p_mean, "phase_pass": p_ok, "verdict": v,
            "reason": f"{label} implied minus realised over {n} periods, pooled over every daily entry (all {cycle} phases of the non-overlapping {cycle}-day "
                      f"cycles, house rule 10; {len(x)} days = {n_cyc} cycles, blocks of {block} days): {x.mean():+.4f} {unit} since {ds[0]} "
                      f"(95% CI {lo:+.4f} to {hi:+.4f}){extra}; {_phases_txt(p_mean, p_ok, '{:+.4f}')} — {why}"}


def multi_asset_short_variance(legs: dict, n: int = 21, block: int = 3, min_n: int = 180):
    """T-245: equal-vega short 21-day variance on SPX, GLD, USO, TLT (pnl_i = (K_i^2 - RV_i^2) / (2 K_i)) vs SPX alone:
    Sharpe difference > 0 with one-sided p < 0.05, positive in both halves. Non-overlapping 21-day cycles on common dates, with no entry
    calendar named, so (house rule 10) the primary statistic pools every phase of the n-day grid: an entry on every common day, Sharpe
    ratios of the overlapping n-day P&L (12 a year), a circular block bootstrap of the paired difference with blocks of
    max(2, block) x n days, halves of the pooled series; n_cycles counts non-overlapping cycles (the most any phase holds), and the
    reason reports each phase (every n-th entry, blocks of `block` cycles) on its own. Below min_n cycles (house rule 5) the Sharpe
    criterion fails decisively only when the one-sided 95% upper bound of the difference is <= 0, and the halves criterion only when
    the first half at min_n (the entries of cycles [0, min_n // 2), already observed) is <= 0."""
    common = sorted(set.intersection(*(set(d for d in v[0] if d in v[2]) for v in legs.values())))
    series = {}
    for k, (days, closes, idx) in legs.items():
        pos = {d: i for i, d in enumerate(days)}
        series[k] = (pos, closes, idx)
    port, spx, js = [], [], []
    for j in range(0, len(common) - n):                   # every common day: all n phases of the old first-day grid (j % n == phase)
        d0 = common[j]; vals = {}
        ok = True
        for k, (pos, closes, idx) in series.items():
            i = pos[d0]
            if i + n >= len(closes):
                ok = False; break
            K = idx[d0] / 100; rv = _fwd_rv(closes, i, n, 252)
            vals[k] = (K ** 2 - rv ** 2) / (2 * K)
        if ok:
            port.append(np.mean(list(vals.values()))); spx.append(vals["SPX"]); js.append(j)
    port, spx, js = np.array(port), np.array(spx), np.array(js)
    B = max(2, block) * n
    obs, lo = _sharpe_diff_lower(port, spx, 12, B, q=0.05)
    _, up = _sharpe_diff_lower(port, spx, 12, B, q=0.95)                  # same draws: the one-sided 95% upper bound
    h = len(port) // 2
    halves = [_sr(port[:h], 12) - _sr(spx[:h], 12), _sr(port[h:], 12) - _sr(spx[h:], 12)]
    p_diff, p_ok, p_n = [], [], []
    for k in range(n):                                     # each phase on its own, as the old harness judged phase 0
        p, s = port[js % n == k], spx[js % n == k]
        if len(p) < 4:
            continue
        o, l = _sharpe_diff_lower(p, s, 12, block, q=0.05); hp = len(p) // 2
        p_diff.append(o); p_n.append(len(p))
        p_ok.append(o > 0 and l > 0 and _sr(p[:hp], 12) - _sr(s[:hp], 12) > 0 and _sr(p[hp:], 12) - _sr(s[hp:], 12) > 0)
    n_cyc = max(p_n) if p_n else 0
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([("Sharpe diff > 0 with one-sided p < 0.05", obs > 0 and lo > 0, up <= 0),
                     ("positive in both halves", all(x > 0 for x in halves),
                      _first_half_fails_at_min_n(n_cyc, min_n, lambda k: _sr(port[:k * n], 12) - _sr(spx[:k * n], 12) > 0))],
                    n_cyc, min_n, "non-overlapping 21-day cycles")
    ph = _phases_txt(p_diff, p_ok) if p_diff else "no phase with 4 cycles"
    return {"n_cycles": int(n_cyc), "n_entries": int(len(port)), "sharpe_portfolio": _sr(port, 12), "sharpe_spx": _sr(spx, 12), "diff": obs, "lower": lo, "upper": up,
            "halves": halves, "block_days": int(B), "phase_diffs": p_diff, "phase_pass": p_ok, "verdict": v,
            "reason": f"equal-vega short variance on SPX/GLD/USO/TLT Sharpe {_sr(port,12):.2f} vs SPX alone {_sr(spx,12):.2f}, pooled over all {n} phases of the "
                      f"non-overlapping {n}-day cycles (house rule 10; {len(port)} daily entries = {n_cyc} cycles since {common[0]}, blocks of {B} days): "
                      f"diff {obs:+.2f}, one-sided lower {lo:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}; {ph} — {why}"}


def ratio_extremes(a_days, a_closes, b_days, b_closes, ia: dict, ib: dict, n: int = 21, ppy: int = 252, window: int = 756, lo_q=0.10, hi_q=0.90, block=3, win_req=0.6, label="GVZ/VIX",
                   statistic: Optional[str] = None, min_n: Optional[int] = None):
    """T-247 / T-266 shape: after the implied ratio ia/ib leaves its trailing window's [lo_q, hi_q] band (s = +1 below the band, -1 above),
    the signed gap between the realised vol ratio over the next n periods and the entry implied ratio. statistic 'log' (T-247):
    s*[ln(RV_a/RV_b) - ln(ia/ib)]; 'level' (T-266): s*[RV_a/RV_b - ia/ib]. Non-overlapping signals. The unconditional mean of the same
    unsigned statistic over every post-warm-up day is reported for comparison. Below min_n signals (house rule 5) the mean criterion
    fails decisively only when its 95% CI lies wholly at or below 0, and the win-rate criterion only when it would fail at min_n even
    if every missing signal won. statistic and min_n default to the _TRIAL entry for the label (else 'log' and 10)."""
    statistic = _trial("ratio_extremes", label, "statistic", statistic, "log")
    min_n = _trial("ratio_extremes", label, "min_n", min_n, 10)
    if statistic not in ("log", "level"):
        raise ValueError(f"statistic must be 'log' or 'level', got {statistic!r}")
    pa = {d: i for i, d in enumerate(a_days)}; pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb and d in ia and d in ib]
    ratio = np.log(np.array([ia[d] / ib[d] for d in common]))

    def gap(t):                                   # unsigned statistic at entry t, or None without a full forward window
        d = common[t]; i, j = pa[d], pb[d]
        if i + n >= len(a_closes) or j + n >= len(b_closes):
            return None
        rv = _fwd_rv(a_closes, i, n, ppy) / _fwd_rv(b_closes, j, n, ppy)
        return math.log(rv) - ratio[t] if statistic == "log" else rv - math.exp(ratio[t])

    x, sig_days = [], []
    t = window
    while t < len(common) - n:
        w = ratio[t - window:t]; lo = np.quantile(w, lo_q); hi = np.quantile(w, hi_q) if hi_q is not None else np.inf
        s = 1 if ratio[t] < lo else (-1 if ratio[t] > hi else 0)
        if s:
            g = gap(t)
            if g is not None:
                x.append(s * g); sig_days.append(common[t]); t += n; continue
        t += 1
    x = np.array(x)
    unc = [g for g in (gap(t) for t in range(window, len(common) - n)) if g is not None]
    unc_mean = float(np.mean(unc)) if unc else float("nan")
    units = "log units" if statistic == "log" else "ratio points"
    unc_txt = f"unconditional mean over all {len(unc)} post-warm-up days {unc_mean:+.3f}"
    if len(x) < 2:
        return {"n": len(x), "statistic": statistic, "min_n": min_n, "unconditional_mean": unc_mean, "signal_days": sig_days, "verdict": "inconclusive",
                "reason": f"{label}: only {len(x)} non-overlapping extreme signals (min_n {min_n}); {unc_txt}"}
    lo, hi = _mean_ci(x, block); win = float((x > 0).mean())
    # (name, passes, fails decisively below min_n)
    rows = [("mean > 0 with CI excluding 0", x.mean() > 0 and lo > 0, hi <= 0)]
    if win_req is not None:
        rows.append((f"win rate > {win_req}", win > win_req, _rate_fails_at_min_n(int((x > 0).sum()), len(x), min_n, win_req)))
    v, why = _rule5(rows, len(x), min_n, "non-overlapping signals")
    return {"n": int(len(x)), "statistic": statistic, "min_n": min_n, "mean": float(x.mean()), "ci": [lo, hi], "win_rate": win, "unconditional_mean": unc_mean,
            "signal_days": sig_days, "verdict": v,
            "reason": f"{label} extremes: {len(x)} non-overlapping signals, mean {x.mean():+.3f} {units} (95% CI {lo:+.3f} to {hi:+.3f}), win rate {win:.2f}; {unc_txt} — {why}"}


def ratio_mean_reversion_signal(a_days, a_closes, b_days, b_closes, window: int = 1260, q: float = 0.90, horizon_days: int = 180, start: str = "2011-01-01",
                                min_n: int = 15):
    """T-274: when GLD/SLV exceeds its trailing 5-year (1260 trading days) 90th percentile, the 180-day forward log change of the ratio
    (to the first common trading day at or after entry + 180 calendar days) is negative at 90% confidence, judged one-sided by the
    bootstrap 0.90 quantile of the mean being < 0, with hit rate > 60%. Non-overlapping episodes. Below min_n episodes (house rule 5) the
    mean criterion fails decisively only when the one-sided 90% lower bound (bootstrap 0.10 quantile) is >= 0, and the hit rate only when
    it would be <= 60% at min_n even if every missing episode were a hit."""
    pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb]
    pa = {d: i for i, d in enumerate(a_days)}
    lr = np.log(np.array([a_closes[pa[d]] / b_closes[pb[d]] for d in common]))
    x, eps, t = [], [], window
    while t < len(lr):
        if common[t] >= start and lr[t] > np.quantile(lr[t - window:t], q):
            j = bisect_left(common, (date.fromisoformat(common[t]) + timedelta(days=horizon_days)).isoformat())
            if j >= len(lr):
                break                                 # no full horizon left for this or any later signal
            x.append(lr[j] - lr[t]); eps.append((common[t], common[j])); t = j
        else:
            t += 1
    x = np.array(x)
    if len(x) < 3:
        return {"n": len(x), "n_signals": len(x), "episodes": eps, "verdict": "inconclusive", "reason": f"only {len(x)} independent episodes (min_n {min_n})"}
    rng = np.random.default_rng(0); bs = np.array([rng.choice(x, x.size).mean() for _ in range(4000)])
    upper90 = float(np.quantile(bs, 0.90)); hit = float((x < 0).mean())      # one-sided 90% upper bound of the mean
    lower90 = float(np.quantile(bs, 0.10))                                   # the bound on the wrong side, for rule 5
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([("mean < 0 at 90% confidence (one-sided)", upper90 < 0, lower90 >= 0),
                     ("hit rate > 60%", hit > 0.6, _rate_fails_at_min_n(int((x < 0).sum()), len(x), min_n, 0.6))],
                    len(x), min_n, "independent episodes")
    return {"n_signals": int(len(x)), "mean": float(x.mean()), "upper90": upper90, "lower90": lower90, "hit_rate": hit, "changes": x.tolist(), "episodes": eps, "verdict": v,
            "reason": f"GLD/SLV above its 5-year 90th percentile: {len(x)} independent episodes, {horizon_days}-calendar-day change {x.mean():+.3f} (one-sided 90% upper {upper90:+.3f}), hit rate {hit:.2f} — {why}"}


def zscore_slope(days, a_idx: dict, b_idx: dict, window: int = 252, horizon: int = 20, start: str = "2010-01-01", min_n: int = 150):
    """T-514: OLS slope of the 20-day forward change in log(a/b) on its z-score vs the trailing 252-day mean; slope 95% CI < 0 in both
    halves. The trial's samples are non-overlapping 20-day ones with no entry calendar named, so (house rule 10) the primary statistic
    pools every phase of the 20-day grid: a sample on every day from `start` (after the warm-up), each half's slope CI from a circular
    block bootstrap of (z, change) pairs with blocks of 2 x horizon days; n counts non-overlapping samples (the most any phase holds),
    and the reason reports each phase (every horizon-th day, iid bootstrap as before) on its own. Below min_n samples (house rule 5) a
    half's criterion fails decisively only when its slope 95% CI lies wholly at or above 0 (lower bound >= 0)."""
    common = [d for d in sorted(set(a_idx) & set(b_idx))]
    lr = np.log(np.array([a_idx[d] / b_idx[d] for d in common]))
    z, f, ds, ph = [], [], [], []
    for t in range(window, len(lr) - horizon):            # every day: all horizon phases of the old grid (range(window, ..., horizon))
        if common[t] < start:
            continue
        w = lr[t - window:t]; sd = w.std()
        if sd > 0:
            z.append((lr[t] - w.mean()) / sd); f.append(lr[t + horizon] - lr[t]); ds.append(common[t]); ph.append((t - window) % horizon)
    z, f, ph = np.array(z), np.array(f), np.array(ph)

    def slope_ci(zz, ff, block, seed=0):                  # (OLS slope, 2.5% and 97.5% quantiles) by circular block bootstrap of pairs
        rng = np.random.default_rng(seed); n = len(zz); b = max(1, min(int(block), n)); nb = math.ceil(n / b); bs = np.empty(2000)
        for r in range(2000):
            i = ((rng.integers(0, n, nb)[:, None] + np.arange(b)[None, :]).ravel()[:n]) % n
            zc = zz[i] - zz[i].mean(); bs[r] = float(zc @ (ff[i] - ff[i].mean()) / (zc @ zc))
        zc = zz - zz.mean()
        return float(zc @ (ff - ff.mean()) / (zc @ zc)), float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))

    def halves(zz, ff, block):
        h = len(zz) // 2
        return slope_ci(zz[:h], ff[:h], block), slope_ci(zz[h:], ff[h:], block, 1)

    B = 2 * horizon
    (s1, l1, u1), (s2, l2, u2) = halves(z, f, B)
    p_slope, p_ok, p_n = [], [], []
    for k in range(horizon):
        m = ph == k
        if m.sum() < 8:
            continue
        (a1, _, v1), (a2, _, v2) = halves(z[m], f[m], 1)
        p_slope += [a1, a2]; p_ok.append(v1 < 0 and v2 < 0); p_n.append(int(m.sum()))
    n_s = max(p_n) if p_n else 0
    # (name, passes, fails decisively below min_n: the half's CI lies wholly at or above 0)
    v, why = _rule5([("first-half slope CI < 0", u1 < 0, l1 >= 0), ("second-half slope CI < 0", u2 < 0, l2 >= 0)],
                    n_s, min_n, "non-overlapping 20-day samples")
    ph_txt = (f"half slopes {_phases_txt(p_slope, p_ok, '{:+.4f}')}" if p_slope else "no phase with 8 samples")
    return {"n": int(n_s), "n_entries": int(len(z)), "slopes": [s1, s2], "lower": [l1, l2], "upper": [u1, u2], "block_days": B, "phase_slopes": p_slope, "phase_pass": p_ok,
            "verdict": v,
            "reason": f"GVZ/VIX 20-day reversion, pooled over all {horizon} phases of the non-overlapping {horizon}-day samples (house rule 10; {len(z)} daily "
                      f"entries = {n_s} samples, blocks of {B} days): slope on z-score {s1:+.4f} (upper {u1:+.4f}) and {s2:+.4f} (upper {u2:+.4f}) in the two halves; "
                      f"{ph_txt} — {why}"}


# ------------------------------------------------------------ model-priced (flat index IV) --

def _cycles(days, closes, idx, rates, legs, dte, hold, start, schedule=None):
    """Model-priced cycles at the index as flat IV. With `schedule` ((entry, expiry) pairs, e.g. _calendar_cycles) each cycle is priced
    at its own T = calendar days to expiry / 365. Without one, the first-day grid of `hold` days: one of `hold` equally valid phases
    (house rule 10), so no verdict here rests on it alone."""
    if schedule is None:
        return run_structure(days, closes, idx, rates, legs, dte, hold, ("flat", 1.0), None, start=start, q=0.0)
    return run_structure(days, closes, idx, rates, legs, dte, hold, ("flat", 1.0), None, start=start, q=0.0, schedule=schedule)


def covered_call_vs_hold(days, closes, idx, rates, delta, dte, hold, ppy_cycles, start, label, dsr_variants=(0.15, 0.25, 0.35), min_n: Optional[int] = None,
                         calendar=None):
    """T-253 / T-270: monthly delta-d covered call (priced at the index as flat IV) vs holding: pooled Sharpe-difference 95% CI excludes 0,
    sign holds in both halves, deflated Sharpe > 0 over the declared delta variants. deflated_sharpe_ratio returns a probability
    (PSR against the expected best-of-N zero-skill Sharpe SR*), so 'deflated Sharpe > 0' (SR_hat > SR*) is DSR probability > 0.5.
    The claim's 'higher Sharpe' is its own criterion (difference > 0), so a CI excluding 0 on the negative side fails the claim.
    Cycles (house rule 10): the claims write monthly options, so `calendar` (default: the _TRIAL entry for the label, else 'monthly';
    see _calendar_cycles) sets them: GLD on the standard monthly expiry, BTC on Deribit's last-Friday expiry, each written at one
    expiry and settled at the next with its own T (dte and hold are the trial's nominal 30 days / month).
    Below min_n cycles (default: the _TRIAL entry for the label; house rule 5) only that criterion can fail decisively, when the 95% CI of
    the difference lies wholly at or below 0; a straddling CI, a halves sign flip or a DSR shortfall there is undecided."""
    min_n = _trial("covered_call_vs_hold", label, "min_n", min_n, 0)
    sched, cal = _calendar_cycles(days, _trial("covered_call_vs_hold", label, "calendar", calendar, "monthly"))
    def run(d):
        res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None), ("call", "short", 1, ("delta", d))], dte, hold, start, sched)
        return res["pnl"] / res["spot"]
    cc = run(delta)
    hold_res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None)], dte, hold, start, sched)
    bh = hold_res["pnl"] / hold_res["spot"]
    if len(cc) < 4:
        return {"n_cycles": int(len(cc)), "calendar": cal, "verdict": "inconclusive",
                "reason": f"MODEL-PRICED at flat {label}: only {len(cc)} cycles on the {cal} (min_n {min_n})"}
    obs, lo = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.025); _, hi = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.975)
    h = len(cc) // 2; halves = [_sr(cc[:h], ppy_cycles) - _sr(bh[:h], ppy_cycles), _sr(cc[h:], ppy_cycles) - _sr(bh[h:], ppy_cycles)]
    dsr = deflated_sharpe_ratio(cc - bh, n_trials=len(dsr_variants), trial_sharpes=[sharpe_ratio(run(d) - bh) for d in dsr_variants])
    # (name, passes, fails decisively below min_n). A failing two-sided 'excludes 0' CI straddles 0, so it is never wholly on the wrong
    # side; the halves' signs and the DSR at min_n depend on the missing cycles.
    v, why = _rule5([("covered call Sharpe higher than hold (Sharpe difference > 0)", obs > 0, hi <= 0),
                     ("Sharpe diff 95% CI excludes 0", lo > 0 or hi < 0, False),
                     ("sign holds in both halves", np.sign(halves[0]) == np.sign(halves[1]) == np.sign(obs), False),
                     ("deflated Sharpe > 0 (DSR probability > 0.5)", dsr > 0.5, False)],
                    len(cc), min_n, "cycles")
    return {"n_cycles": int(len(cc)), "calendar": cal, "first_day": hold_res["day"][0], "sharpe_cc": _sr(cc, ppy_cycles), "sharpe_hold": _sr(bh, ppy_cycles), "diff": obs, "ci": [lo, hi],
            "halves": halves, "dsr": float(dsr), "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {delta:.2f}-delta covered call Sharpe {_sr(cc,ppy_cycles):.2f} vs hold {_sr(bh,ppy_cycles):.2f} over {len(cc)} cycles "
                      f"from {hold_res['day'][0]} on the {cal} (diff {obs:+.2f}, 95% CI {lo:+.2f} to {hi:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}), DSR probability {dsr:.2f} "
                      f"(deflated Sharpe > 0 needs > 0.5), MDD {_mdd(cc)*100:.0f}% vs {_mdd(bh)*100:.0f}% — {why}"}


def short_put_mean(days, closes, idx, rates, delta, dte, hold, start, label, min_n: Optional[int] = None, calendar=None):
    """T-254 / T-279: monthly delta-d short put at flat index IV, P&L = (premium - payoff)/K: 95% CI of the mean > 0, positive in both halves.
    Cycles (house rule 10): monthly options, so `calendar` (default: the _TRIAL entry for the label, else 'monthly'; see
    _calendar_cycles) sets them, each written at one expiry and settled at the next with its own T.
    Below min_n cycles (default: the _TRIAL entry for the label; house rule 5) the CI criterion fails decisively only when the CI lies
    wholly at or below 0, and the halves criterion only when the first half at min_n (cycles [0, min_n // 2), already observed) is <= 0."""
    min_n = _trial("short_put_mean", label, "min_n", min_n, 0)
    sched, cal = _calendar_cycles(days, _trial("short_put_mean", label, "calendar", calendar, "monthly"))
    res = _cycles(days, closes, idx, rates, [("put", "short", 1, ("delta", delta))], dte, hold, start, sched)
    K = np.array([k[0] for k in res["strikes"]])
    x = res["pnl"] / K
    if len(x) < 4:
        return {"n_cycles": int(len(x)), "calendar": cal, "verdict": "inconclusive",
                "reason": f"MODEL-PRICED at flat {label}: only {len(x)} cycles on the {cal} (min_n {min_n})"}
    lo, hi = _mean_ci(x, 3); h = len(x) // 2
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([("95% CI of the mean > 0", lo > 0, hi <= 0),
                     ("positive in both halves", x[:h].mean() > 0 and x[h:].mean() > 0, _first_half_fails_at_min_n(len(x), min_n, lambda k: x[:k].mean() > 0))],
                    len(x), min_n, "cycles")
    return {"n_cycles": int(len(x)), "calendar": cal, "first_day": res["day"][0], "mean": float(x.mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {abs(delta):.2f}-delta short put mean {x.mean()*100:+.2f}% of strike per cycle over {len(x)} cycles from {res['day'][0]} "
                      f"on the {cal} (95% CI {lo*100:+.2f} to {hi*100:+.2f}), halves {x[:h].mean()*100:+.2f}/{x[h:].mean()*100:+.2f} — {why}"}


def conditional_straddle(days, closes, idx, rates, dte, hold, start, window, pct, label, report_conditional=True, min_n: Optional[int] = None, block: int = 2):
    """T-256 / T-272: ATM straddles (BS at the index as flat IV, held `hold` periods to expiry) bought when the index is below its
    trailing-window pct-percentile vs bought on all days: conditional minus unconditional mean return on premium, 95% CI > 0.
    The conditional set is non-overlapping, as both trials specify: after a low-index entry the next `hold` days are skipped. The
    unconditional mean is over every daily entry. CI: paired circular block bootstrap of the difference on the daily timeline (blocks of
    `block` x `hold` rows, about `block` conditional entries each) of z = 1[entry] x / p - x, p = share of rows that are entries, whose
    mean is exactly mean_low - mean_all; both means move together in every draw, so their positive covariance is kept.
    n_entries counts the non-overlapping conditional entries (the trials' unit). Below min_n (default: the _TRIAL entry for the label;
    house rule 5) the verdict cannot be supported, and the CI criterion fails decisively only when the CI lies wholly at or below 0;
    a straddling CI there is inconclusive."""
    min_n = _trial("conditional_straddle", label, "min_n", min_n, 0)
    d, c, iv = _align(days, closes, idx)
    T = dte / 365.0
    from mandel.options import bs
    rate = _asof(rates)
    rows = []
    for i in range(window, len(c) - hold):
        if d[i] < start:
            continue
        S, V = c[i], iv[i] / 100; r = math.log(1 + rate(d[i]) / 100)
        prem = float(bs.price(S, S, T, r, V, "call")) + float(bs.price(S, S, T, r, V, "put"))
        ret = (abs(c[i + hold] - S) - prem) / prem
        rows.append((d[i], ret, bool(iv[i] < np.quantile(iv[i - window:i], pct))))
    x = np.array([r for _, r, _ in rows]); m = np.array([f for _, _, f in rows], dtype=bool)
    cond, k = [], 0
    while k < len(rows):                                  # greedy non-overlapping conditional entries
        if rows[k][2]:
            cond.append(k); k += hold
        else:
            k += 1
    nc = len(cond); entry_days = [rows[k][0] for k in cond]
    if nc < 2:
        return {"n_entries": nc, "n_days": int(len(x)), "n_low_days": int(m.sum()), "entry_days": entry_days, "min_n": min_n, "verdict": "inconclusive",
                "reason": f"MODEL-PRICED at flat {label}: only {nc} non-overlapping low-{label} entries (min_n {min_n})"}
    xc = x[cond]
    flag = np.zeros(len(x), bool); flag[cond] = True
    z = np.where(flag, x, 0.0) / flag.mean() - x                  # paired difference series: mean(z) == xc.mean() - x.mean()
    draws = _block_mean_draws(z, block * hold, seed=0)
    lo, hi = float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))
    dmean = float(xc.mean() - x.mean())
    v, why = _rule5([("difference 95% CI > 0", lo > 0, hi <= 0)], nc, min_n, "non-overlapping conditional entries")   # (name, passes, decisive)
    return {"n_entries": nc, "n_days": int(len(x)), "n_low_days": int(m.sum()), "entry_days": entry_days, "mean_all": float(x.mean()), "mean_low": float(xc.mean()),
            "conditional_mean_positive": bool(xc.mean() > 0), "diff": dmean, "ci": [lo, hi], "min_n": min_n, "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {dte}-day ATM straddles bought with {label} below its trailing {pct:.0%} quantile return {xc.mean()*100:+.1f}% on premium "
                      f"over {nc} non-overlapping entries (conditional mean {'>' if xc.mean() > 0 else '<='} 0) vs {x.mean()*100:+.1f}% on all {len(x)} daily entries "
                      f"(diff {dmean*100:+.1f}, 95% CI {lo*100:+.1f} to {hi*100:+.1f}; {int(m.sum())} low-{label} days in all) — {why}"}


def protective_put_calmar(days, closes, idx, rates, start, label="DVOL", dte: int = 90, roll: int = 30, delta: float = -0.10, block: int = 6,
                          ppy: int = 365, min_n: int = 20):
    """T-267: 1 BTC plus one 10-delta 90-DTE put (BS at the index as flat IV, q = 0), rolled monthly as the trial's procedure states: every
    `roll` days the held put (then dte - roll days to expiry) is sold at its BS mark and a new 90-DTE 10-delta put is bought; vs buy-and-hold.
    Both arms are marked daily (spot plus the put at BS with that day's index and bill rate), and Calmar = CAGR / |max drawdown of the daily
    path|. Pass: bootstrap 95% lower bound of the Calmar difference > 0 and positive in >= 2 of 3 windows.
    Roll dates (house rule 10): 'monthly rolls' of a 90-DTE put name no calendar, so each of the `roll` start days is an equally valid
    phase: sleeve k rolls on days start + k, start + k + roll, ... The primary statistic pools every phase: the mean over the `roll`
    sleeves of the claimed Calmar difference, each on the same daily path (the days on which every sleeve holds a put), with one joint
    circular block bootstrap of those days (blocks of max(2, block) x roll days, every sleeve and buy-and-hold resampled alike) and
    thirds of that path as the windows; n counts roll periods (the most any sleeve holds). It is the claimed strategy at an unknown
    phase, not a ladder rebalanced across sleeves (whose rebalancing would add a return none of the phases earns). Each sleeve on its
    own over its own span (the old harness was sleeve 0: blocks of `block` roll periods, each keeping its daily path) is reported as the
    per-phase range.
    Below min_n roll periods (house rule 5) the CI criterion fails decisively only when the bootstrap 95% CI lies wholly at or below 0
    (upper bound <= 0), and the windows criterion only when at least 2 of the 3 windows at min_n (np.array_split of the first
    min_n x roll days) are already fully observed and not positive."""
    from mandel.options import bs
    vol, rate = _asof(idx), _asof(rates)
    i0 = next((k for k, d in enumerate(days) if d >= start and d in idx), len(days))

    def sleeve(i):                                    # roll periods from day index i: per-period cumulative growth (hedged, hold), premium cost
        GH, GB, cost = [], [], []
        while i + roll < len(days):
            d0 = days[i]; S0 = float(closes[i]); V0 = vol(d0) / 100; r0 = math.log(1 + rate(d0) / 100)
            K = bs.strike_for_delta(S0, dte / 365.0, r0, V0, delta, "put", 0.0); P0 = float(bs.price(S0, K, dte / 365.0, r0, V0, "put", 0.0))
            dk = days[i + 1:i + roll + 1]; Sk = np.asarray(closes[i + 1:i + roll + 1], dtype=float)
            tau = np.array([(dte - (date.fromisoformat(x) - date.fromisoformat(d0)).days) / 365.0 for x in dk])
            Pk = bs.price(Sk, K, tau, np.array([math.log(1 + rate(x) / 100) for x in dk]), np.array([vol(x) / 100 for x in dk]), "put", 0.0)
            GH.append((Sk + Pk) / (S0 + P0)); GB.append(Sk / S0); cost.append(P0 / S0); i += roll
        return np.array(GH).reshape(-1, roll), np.array(GB).reshape(-1, roll), cost

    sleeves = [sleeve(i0 + k) for k in range(roll)]
    n = len(sleeves[0][0])                            # roll periods, the claim's unit (sleeve 0, the old harness, holds the most)
    if n < 3:
        return {"n_cycles": n, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat {label}: only {n} monthly roll periods (min_n {min_n})"}

    def path(G):                                      # daily equity path from per-period cumulative growth
        starts = np.concatenate([[1.0], np.cumprod(G[:, -1])[:-1]])
        return np.concatenate([[1.0], (starts[:, None] * G).ravel()])

    def calmar_g(e, n_days):                          # Calmar of an equity path over n_days days
        dd = abs(float((e / np.maximum.accumulate(e) - 1).min())); cagr = e[-1] ** (ppy / n_days) - 1
        return cagr / dd if dd > 0 else float("nan")

    def calmar(G):
        return calmar_g(path(G), len(G) * roll)

    # each sleeve on its own (sleeve 0 is the old harness): Calmar difference, its period-block bootstrap, thirds
    p_diff, p_ok = [], []
    for k, (GH, GB, _) in enumerate(sleeves):
        m = len(GH)
        if m < 3:
            continue
        rng = np.random.default_rng(0); b = max(1, min(block, m)); dr = []
        for _ in range(2000):
            j = ((rng.integers(0, m, math.ceil(m / b))[:, None] + np.arange(b)[None, :]).ravel()[:m]) % m; dr.append(calmar(GH[j]) - calmar(GB[j]))
        th = [calmar(GH[s]) - calmar(GB[s]) for s in np.array_split(np.arange(m), 3)]
        p_diff.append(calmar(GH) - calmar(GB)); p_ok.append(float(np.nanquantile(dr, 0.025)) > 0 and sum(t > 0 for t in th) >= 2)
    # pooled over every phase: each sleeve's daily returns on the days every sleeve holds a put, the claimed Calmar difference averaged
    # over the sleeves (no rebalancing between them), one joint block bootstrap of those days
    R = np.full((roll, len(days)), np.nan)
    for k, (GH, _, _) in enumerate(sleeves):
        if len(GH):
            g = (GH / np.concatenate([np.ones((len(GH), 1)), GH[:, :-1]], axis=1)).ravel()
            R[k, i0 + k + 1:i0 + k + 1 + g.size] = g
    on = np.flatnonzero(np.isfinite(R).all(axis=0))
    if len(on) < 3 * roll:
        return {"n_cycles": n, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat {label}: only {len(on)} days on which all {roll} roll phases hold a put"}
    RH = R[:, on]; gB = np.asarray(closes, dtype=float)[on] / np.asarray(closes, dtype=float)[on - 1]
    nd = len(on); first = days[on[0] - 1]

    def paths(G):                                     # equity paths (rows) from gross daily returns (rows)
        G = np.atleast_2d(G); return np.concatenate([np.ones((len(G), 1)), np.cumprod(G, axis=1)], axis=1)

    def mdds(G):
        E = paths(G); return (E / np.maximum.accumulate(E, axis=1) - 1).min(axis=1)

    def calmars(G):
        dd = np.abs(mdds(G)); cagr = paths(G)[:, -1] ** (ppy / np.atleast_2d(G).shape[1]) - 1
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(dd > 0, cagr / dd, np.nan)

    def pooled(j):                                    # mean over the sleeves of Calmar(sleeve) - Calmar(hold) on the days j
        return float(np.nanmean(calmars(RH[:, j]))) - float(calmars(gB[j])[0])

    allj = np.arange(nd)
    obs = pooled(allj)
    B = max(2, block) * roll
    rng = np.random.default_rng(0); b = max(1, min(B, nd)); draws = []
    for _ in range(2000):
        j = ((rng.integers(0, nd, math.ceil(nd / b))[:, None] + np.arange(b)[None, :]).ravel()[:nd]) % nd; draws.append(pooled(j))
    lo, hi = float(np.nanquantile(draws, 0.025)), float(np.nanquantile(draws, 0.975))
    thirds = [pooled(s) for s in np.array_split(allj, 3)]
    # windows at min_n that are already fully observed (later days only append) and not positive: >= 2 fails at min_n whatever comes
    settled_bad = _settled_windows_bad(nd, min_n * roll, lambda s: not (pooled(s) > 0)) if min_n and n < min_n else 0
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([("Calmar difference 95% CI > 0", lo > 0, hi <= 0),
                     ("positive in >= 2 of 3 windows", sum(t > 0 for t in thirds) >= 2, settled_bad >= 2)],
                    n, min_n, "monthly roll periods")
    cH, cB = float(np.nanmean(calmars(RH))), float(calmars(gB)[0])
    mh, mb = float(mdds(RH).mean()), float(mdds(gB)[0])
    annual_cost = float(np.mean([c for _, _, cs in sleeves for c in cs]) * ppy / roll)
    return {"n_cycles": int(n), "n_days": int(nd), "first_day": first, "calmar_hedged": cH, "calmar_hold": cB, "diff": obs, "lower": lo, "upper": hi,
            "thirds": thirds, "block_days": int(B), "phase_diffs": p_diff, "phase_pass": p_ok, "mdd_hedged": mh, "mdd_hold": mb, "annual_premium": annual_cost, "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: BTC + 10-delta {dte}-DTE puts rolled every {roll} days, pooled over all {roll} roll phases (house rule 10: the "
                      f"mean over the phases on the {nd} days since {first} on which all of them hold a put; n = {n} roll periods, the most any phase holds; "
                      f"blocks of {B} days) Calmar {cH:.2f} vs hold "
                      f"{cB:.2f} (daily-path MDD {mh*100:.0f}% (mean over phases) vs {mb*100:.0f}%, gross premium {annual_cost*100:.1f}% of spot a year; diff {obs:+.2f}, "
                      f"95% lower {lo:+.2f}; thirds " + "/".join(f"{t:+.2f}" for t in thirds) + f"; {_phases_txt(p_diff, p_ok)}) — {why}"}


def delivery_prices(rows) -> dict:
    """{ISO date: Deribit 08:00 UTC delivery price} from deribit-delivery-prices-btc rows ({'value': {'date', 'delivery_price'}})."""
    out = {}
    for r in rows:
        v = r.get("value", r)
        if v.get("delivery_price"):
            out[v["date"]] = float(v["delivery_price"])
    return out


def inverse_covered_call_btc(days, closes, idx, rates, start, delivery: Optional[dict] = None, calendar="deribit", min_n: int = 60):
    """T-176: 25-delta 30-day BTC call written against 1 BTC, the registry statistic in BTC: c - max(S_T - K, 0)/S_T - 2 x 0.0003 BTC fee,
    with c = USD premium / S_0 (the BTC received at inception). Pass: 95% CI of the mean > 0. Black-76 at DVOL on the forward
    F = S e^{rT} equals BS with q = 0, which _cycles uses. Cycles (house rule 10): the trial names the monthly roll on the last-Friday
    cycle, so `calendar` defaults to 'deribit' (see _calendar_cycles): each call is written at the last daily close (24:00 UTC) before
    one last-Friday expiry and expires at the next, priced at its own T (28 or 35 days, from 00:00 UTC Friday to 00:00 UTC Friday).
    Settlement: `delivery` ({date: Deribit delivery price}, see delivery_prices) on the day after each cycle's last close, i.e. the
    expiry Friday's 08:00 UTC delivery. Cycles without a delivery price are dropped. Without `delivery`, spot at that last close stands
    in and the claim's 'settlement at Deribit delivery prices' criterion is not implemented (None), so the verdict is at best
    inconclusive. Below min_n cycles (house rule 5) the verdict cannot be supported, and the CI criterion fails decisively only when the
    CI lies wholly at or below 0."""
    sched, cal = _calendar_cycles(days, calendar)
    res = _cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, start, sched)
    if not len(res["day"]):
        return {"n_cycles": 0, "dropped": 0, "calendar": cal, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat DVOL: no cycle on the {cal} (min_n {min_n})"}
    K = np.array([s[0] for s in res["strikes"]])
    premium_btc = -res["debit"] / res["spot"]                     # c: BTC received at inception (debit < 0 for a short call)
    if delivery is not None:
        settle = np.array([delivery.get((date.fromisoformat(x) + timedelta(days=1)).isoformat(), np.nan) for x in res["exit"]], dtype=float)
        src = "Deribit delivery prices at each expiry (08:00 UTC, the day after the last close before it)"
    else:
        pos = {d: i for i, d in enumerate(days)}
        settle = np.array([closes[pos[x]] for x in res["exit"]], dtype=float)
        src = "spot at the last close before each expiry stands in for Deribit delivery prices"
    ok = np.isfinite(settle); dropped = int((~ok).sum())
    x = premium_btc[ok] - np.maximum(settle[ok] - K[ok], 0) / settle[ok] - 0.0006
    if len(x) < 2:
        return {"n_cycles": int(len(x)), "dropped": dropped, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat DVOL: only {len(x)} cycles settle on {src} (min_n {min_n})"}
    lo, hi = _mean_ci(x, 3)
    # (name, passes, fails decisively below min_n)
    v, why = _rule5([("95% CI of the mean > 0", lo > 0, hi <= 0), ("settled at Deribit delivery prices", True if delivery is not None else None, False)],
                    len(x), min_n, "monthly cycles")
    return {"n_cycles": int(len(x)), "dropped": dropped, "calendar": cal, "first_day": res["day"][0], "mean_btc": float(x.mean()), "mean_premium_btc": float(premium_btc[ok].mean()),
            "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat DVOL: 25-delta 30-day BTC call against 1 BTC earns {x.mean():+.4f} BTC per cycle on average (premium {premium_btc[ok].mean():.4f} BTC at S_0) "
                      f"over {len(x)} cycles from {res['day'][0]} on the {cal} (95% CI {lo:+.4f} to {hi:+.4f}); {src}" + (f", {dropped} cycles without one dropped" if dropped else "") + f" — {why}"}
