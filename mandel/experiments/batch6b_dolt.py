"""
Batch 6b, group ``dolt``: four SPY ratio and ladder claims on the DoltHub end-of-day option chain history (2019-2026).
=====================================================================================================================

Data: ``dolt-chain-SPY`` (``mandel.data.dolt_options``; post-no-preference via DoltHub, CC BY-SA 4.0): end-of-day QUOTES
(bid, ask, vendor IV and greeks; no trades, volume or open interest) for 3-4 expiries at 11-66 DTE and strikes at K/S
0.70-1.30 (0.85-1.15 in 2019). Snapshots were weekly in 2019 (Saturdays quoting Friday), Mon/Wed/Fri 2020-2023 and daily
from 2025. Settlement and spot come from ``daily-history-SPY`` RAW closes; the stress criterion uses ``cboe-VIX-history``.

Claims (each tested on its claim, trial.pass and trial.min_n as worded):
  * T-119  60-DTE SPY 1:2 call backspread (short 1 ATM call, long 2 25-delta calls) entered at mid and held to expiry:
           mean P&L / max loss < 0, pass "upper CI < 0 at mid fills"; min_n 250 entry days.
  * T-121  45-DTE SPY put front-ratio (long 1 40-delta put, short 2 20-delta puts) at mid, held to expiry: positive mean
           P&L / naked-leg margin; pass "lower CI > 0 at bid/ask with a stress month in the sample"; min_n 250 entry days.
  * T-539  45-DTE SPY long put ladder (long 40-delta put, short 25-delta and 15-delta puts) at mid, held to expiry:
           positive mean P&L / naked-leg margin; same pass and min_n as T-121.
  * T-173  SPY 30-DTE overlays on the monthly expiry: the 1x2 overlay (short 2 5%-OTM calls, long 1 10%-OTM call) minus
           the single 5%-OTM covered call (the stock legs cancel, so the spread is short 1 5%-OTM call, long 1 10%-OTM
           call); top-minus-bottom quartile difference of its mean P&L by the entry-day 5%-to-10% OTM call IV slope, pass
           "95% CI of the difference > 0"; min_n 24 monthly expiry cohorts.

Conventions
  * Snapshots and point in time. A snapshot quotes the close of its ``quote_date`` (the last NYSE session on or before the
    snapshot date, or the session the module's stale check moved it to). Each quote day is used once: when two snapshots
    quote the same session (a Saturday or holiday snapshot and the session's own, or a stale snapshot moved onto a day
    that has its own), the one taken on the quote day and not flagged stale is kept, else the earliest. An entry trades at
    the quote day's close at those quotes (they were the market's public closing quotes then; DoltHub's publication time
    is provenance, per the data module), with the spot = SPY's raw close that day. Strike selection uses only that
    snapshot (vendor deltas, vendor IVs, strikes vs that close). Rows of a weekend, holiday or stale-moved snapshot (every
    2019 snapshot is a Saturday) carry the module's conservative available_at on the SNAPSHOT evening, after that close;
    the harness still enters at the quote-day close because it uses nothing but those closing quotes and that close,
    which participants saw at the time. A strict sensitivity drops those entries (available_at after the entry close)
    and is reported for every claim.
  * Expiry. The listed expiry nearest the claim's DTE (calendar days from the quote day), ties to the longer-dated, used
    only within +/- DTE_TOL = 7 days (one weekly listing interval; DoltHub lists only 3-4 expiries, so a 45- or 60-DTE
    expiry is missing on many days); +/- 4 and +/- 14 days are reported as sensitivities. T-173 names the monthly
    calendar ("monthly P&L", "expiry cohorts"), so its expiry must be the standard monthly (third Friday, the prior session
    when that Friday is a holiday) at 23-37 DTE (30 +/- 7).
  * Strikes. Delta legs: the usable listed strike whose |vendor delta| is nearest the target, within DELTA_TOL = 0.075
    (the thin grid's strike steps are up to ~0.12 delta near the money). ATM: the strike nearest the spot within 2%.
    Moneyness legs (T-173): the strike nearest 1.05 S and 1.10 S, each within 2% of S. A leg is usable when bid > 0 and
    ask >= bid. The structure's strike order must hold (T-119 K_25d > K_ATM; T-121 K_40d > K_20d; T-539 K_40d > K_25d >
    K_15d; T-173 K_10% > K_5%), else the day is skipped (counted by reason).
  * Fills. Mid = (bid + ask) / 2 for every leg, as each claim says; executable = buy at the ask, sell at the bid (reported
    for every claim; it is the pass's fill for T-121 and T-539). No commissions are stated; $0.65/contract per leg is a
    reported sensitivity.
  * Settlement. Held to expiry and settled at intrinsic on SPY's RAW close of the expiry date (house rule 8). SPY options
    are American; early exercise is ignored as the claims say "held to expiry". For the call claims (T-119, T-173) an
    early-exercise sensitivity is reported: SPY goes ex-dividend on the third Friday of Mar/Jun/Sep/Dec, so a call is
    exercised at the cum-dividend close (the session before an ex-date inside the life) when the dividend exceeds its
    remaining time value, approximated at r = 0 by the Black-Scholes put on the ex-dividend price at the leg's entry
    vendor IV (a model-assisted exercise rule; it errs towards exercising); such a leg (short calls assigned, long calls
    exercised) settles at that close's intrinsic value. Dividends are read from the adjclose/close ratio steps of
    daily-history-SPY (used ex post, for this settlement sensitivity only). Put early exercise is ignored (an assigned
    short put becomes stock held to expiry, the same price exposure up to carry). Trades whose expiry is after the last
    archived close are unresolved and left out (counted).
  * Denominators. T-119: max loss = (K2 - K1) - net credit (at S_T = K2), at the same fill as the P&L. T-121, T-539:
    naked-leg margin = Reg-T/CBOE naked equity put requirement on ONE uncovered short put, premium + max(20% x S - OTM
    amount, 10% x K) with OTM = max(S - K, 0) and premium = that put's fill price (mid, or bid when executable). The
    uncovered put is the lowest-margin pairing a broker uses: T-121 one of the two 20-delta puts (the other is covered by
    the long 40-delta put), T-539 the 15-delta put (the 25-delta put is covered by the long 40-delta put). The statistic
    is the mean of the per-trade ratios; the ratio of mean P&L to mean denominator is reported.
  * Entries and house rule 10. T-119, T-121 and T-539 name no entry calendar: every snapshot quote day with a valid trade
    is an entry (the trials' "250 entry days"; overlapping trades), so n counts entry days. The pooled all-start mean is
    the primary statistic, with a studentized circular block bootstrap over calendar WEEKS (entries clustered by week,
    empty weeks kept, ratio-of-sums mean, each resample studentized by the Bartlett long-run s.e. of its influence
    function at bandwidth = block) with blocks of 2 x and 4 x the longest hold (DTE + tolerance, rounded up to weeks); a
    criterion passes only when both blocks pass, fails only when both fail, and is marginal (None) otherwise. The
    non-overlapping grids are reported: from every entry day in the first hold window, a chain of trades each entered on
    the first entry day on or after the previous expiry (studentized CI, block 2 trades), with the per-start range of
    the mean and bound and how many pass. T-173 names the monthly calendar: entries are every capture day at 23-37 DTE
    of a monthly expiry (the trial's "overlapping cohorts"), the bootstrap resamples blocks of whole expiry cohorts (the
    trial's "block bootstrap by expiry cohort"; 2 and 4 cohorts, so blocks cover the up-to-9-day overlap between
    adjacent cohorts), and n counts cohorts.
  * T-173's quartiles are the full-sample quartiles of the entry-day slope (the trial's statistic is the quartile
    contrast of the sample); the slope is the vendor call IV linearly interpolated in K/S at 1.10 minus that at 1.05, per
    unit of moneyness, on the cohort's expiry, known at the entry close. Expanding point-in-time quartiles (cut from
    earlier entries only, after 12 cohorts), one entry per cohort (nearest 30 DTE), executable fills, dollar P&L, the
    early-exercise sensitivity and the difference without its most favourable cohort(s) are reported, not judged.
  * Stress month (T-121, T-539 pass). A calendar month with a VIX close >= 40; it is "in the sample" when at least one
    resolved trade was open across such a session (entry < session <= expiry). Months where SPY closed >= 10% below its
    63-session high are reported beside it. Without one the criterion is None (the trial's control caps at inconclusive).
  * Rule 5. Below min_n the verdict is never supported and a failing criterion counts only when decisive (its 95%
    interval wholly on the wrong side at both blocks). Rule 9: a missing bundle or too few entries is inconclusive and
    names what is missing. Controls on GLD and IBIT (T-119, T-173) cannot run: DoltHub has neither symbol.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not implemented
gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.data.dolt_options import is_trading_day
from mandel.experiments.underlying2 import _verdict
from mandel.options import bs
from mandel.validation.backtest_eval import _hac_var

CHAIN_B = "dolt-chain-SPY"
SPY_B = "daily-history-SPY"
VIX_B = "cboe-VIX-history"

DTE_TOL = 7                      # calendar days around the claim's DTE (one weekly listing interval)
DTE_SENS = (4, 14)               # reported tolerance sensitivities
DELTA_TOL = 0.075                # |vendor delta| within this of the target
ATM_TOL = 0.02                   # ATM strike within 2% of the spot
MONEY_TOL = 0.02                 # nearest-strike moneyness legs within 2% of S of the target
BAND_TOL = 0.01                  # T-173 reported: nearest strikes within 1% of S of both targets
SLOPE_GAP = 0.06                 # IV interpolation and exact-moneyness mixtures: bracketing strikes at most this far apart in K/S
PREV_EXP_TOL = 14                # T-173 previous-close reading: the capture's listing nearest 30 DTE within this, if it lacks the cohort's expiry
STRESS_VIX = 40.0                # stress session: VIX close >= 40
STRESS_DD = 0.10                 # reported: SPY >= 10% below its 63-session high
DD_WINDOW = 63
BLOCK_HOLDS = (2, 4)             # pooled weekly-cluster blocks, in multiples of the longest hold (rule 10: >= 2x)
COHORT_BLOCKS = (2, 4)           # T-173 blocks of expiry cohorts
CHAIN_BLOCK = 2                  # per-start non-overlapping chains: block of trades
MIN_CLUSTERS = 8                 # fewest non-empty clusters for an interval
PIT_MIN_COHORTS = 12             # T-173 expanding quartiles: cohorts of history before the first label
COMM = 0.0065                    # $0.65 per contract per leg, per share
N_BOOT = 2000
SEED = 0
LEVEL = 0.95

T119_MIN_N, T119_DTE = 250, 60
T121_MIN_N, T121_DTE = 250, 45
T539_MIN_N, T539_DTE = 250, 45
T173_MIN_N, T173_DTE = 24, 30
FILLS = ("mid", "exec")
EVENING = "T22:00:00+00:00"      # the data module's available_at time on a quote day's evening
FILL_UTC = "T20:15:00+00:00"     # the 16:15 ET fill at its earliest in UTC (EDT): rows known before the fill are stamped before it
NO_CONTROL = "the GLD and IBIT controls cannot run (DoltHub has neither symbol)"


# ===================================================================================================== formatting ==

def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _ci_s(ci, nd: int = 3, scale: float = 1.0) -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


def _pct(x, nd: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{nd}f}%"


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


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ===================================================================================================== statistics ==

def _lrv(x, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance (backtest_eval._hac_var, bandwidth ``bw``); long bandwidths via an FFT."""
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


def cluster_mean_ci(S, N, block: int, level: float = LEVEL, n_boot: Optional[int] = None, seed: int = SEED) -> tuple:
    """Studentized circular block-bootstrap CI of the ratio-of-sums mean sum(S) / sum(N) over time-ordered clusters
    (S = sum of the statistic in a cluster, N = its count; empty clusters stay in the timeline). Each resample is
    studentized by the Bartlett long-run s.e. (bandwidth = block) of the influence function psi_c = (S_c - m N_c) / Nbar.
    (None, None) with fewer than MIN_CLUSTERS non-empty clusters."""
    S = np.asarray(S, dtype=float)
    N = np.asarray(N, dtype=float)
    W = S.size
    if W == 0 or int((N > 0).sum()) < MIN_CLUSTERS:
        return None, None
    n_boot = N_BOOT if n_boot is None else n_boot
    block = max(1, min(int(block), W // 4))
    tot = float(N.sum())
    m = float(S.sum() / tot)
    psi = (S - m * N) / (tot / W)
    v0 = float(_lrv(psi[None, :], block)[0])
    if v0 <= 1e-30:
        return m, m
    se = math.sqrt(v0 / W)
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, W):
        idx = _boot_idx(rng, W, block, k)
        Sb, Nb = S[idx], N[idx]
        tb = Nb.sum(axis=1)
        ok = tb > 0
        if not ok.any():
            continue
        Sb, Nb, tb = Sb[ok], Nb[ok], tb[ok]
        mb = Sb.sum(axis=1) / tb
        pb = (Sb - mb[:, None] * Nb) / (tb / W)[:, None]
        sb = np.sqrt(_lrv(pb, block) / W)
        good = sb > 1e-150
        ts.append((mb[good] - m) / sb[good])
    t = np.concatenate(ts) if ts else np.zeros(0)
    if t.size < 10:
        return None, None
    a = (1.0 - level) / 2.0
    return m - float(np.quantile(t, 1.0 - a)) * se, m - float(np.quantile(t, a)) * se


def cluster_diff_ci(St, Nt, Sb, Nb, block: int, level: float = LEVEL, n_boot: Optional[int] = None,
                    seed: int = SEED) -> dict:
    """mean(top) - mean(bottom) over time-ordered clusters (per-cluster sums and counts of each group), with a
    studentized circular block-bootstrap CI over clusters; psi_c = C [(St_c - mt Nt_c)/Nt - (Sb_c - mb Nb_c)/Nb]."""
    St, Nt, Sb, Nb = (np.asarray(a, dtype=float) for a in (St, Nt, Sb, Nb))
    C = St.size
    out = {"diff": None, "ci": [None, None], "mean_top": None, "mean_bottom": None, "n_top": int(Nt.sum()),
           "n_bottom": int(Nb.sum()), "n_clusters": int(((Nt + Nb) > 0).sum()), "block": int(block)}
    if C == 0 or Nt.sum() < 4 or Nb.sum() < 4 or out["n_clusters"] < MIN_CLUSTERS:
        return out
    n_boot = N_BOOT if n_boot is None else n_boot
    block = max(1, min(int(block), C // 4))

    def stat(st, nt, sb, nb):
        tt, tb = nt.sum(axis=1), nb.sum(axis=1)
        ok = (tt > 0) & (tb > 0)
        tt, tb = np.maximum(tt, 1), np.maximum(tb, 1)
        mt, mb = st.sum(axis=1) / tt, sb.sum(axis=1) / tb
        psi = C * ((st - mt[:, None] * nt) / tt[:, None] - (sb - mb[:, None] * nb) / tb[:, None])
        return mt - mb, np.sqrt(_lrv(psi, block) / C), ok, mt, mb

    d0, se0, _, mt0, mb0 = stat(St[None], Nt[None], Sb[None], Nb[None])
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(diff=d0, mean_top=float(mt0[0]), mean_bottom=float(mb0[0]), se=se0, block=int(block))
    if se0 <= 1e-150:
        out["ci"] = [d0, d0]
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, C):
        idx = _boot_idx(rng, C, block, k)
        d, se, ok, _, _ = stat(St[idx], Nt[idx], Sb[idx], Nb[idx])
        ok &= se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
    t = np.concatenate(ts)
    if t.size < 10:
        return out
    a = (1.0 - level) / 2.0
    out["ci"] = [d0 - float(np.quantile(t, 1.0 - a)) * se0, d0 - float(np.quantile(t, a)) * se0]
    return out


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def week_clusters(days: Sequence[str], x) -> tuple:
    """(S, N) per calendar week (Monday-anchored) from the first to the last entry; empty weeks kept."""
    x = np.asarray(x, dtype=float)
    if not len(days):
        return np.zeros(0), np.zeros(0)
    o = np.array([_ord(d) for d in days], dtype=np.int64)
    first = int(o.min())
    mon = first - date.fromordinal(first).weekday()
    w = (o - mon) // 7
    W = int(w.max()) + 1
    S, N = np.zeros(W), np.zeros(W)
    np.add.at(S, w, x)
    np.add.at(N, w, 1.0)
    return S, N


def _robust(oks: Sequence[Optional[bool]]) -> Optional[bool]:
    """True when every variant passes, False when every variant fails, None when any is undecided or they disagree."""
    if not oks or any(o is None for o in oks):
        return None
    if all(oks):
        return True
    if not any(oks):
        return False
    return None


def pooled_mean_test(days: Sequence[str], x, hold_days: int, side: int, holds: Sequence[int] = BLOCK_HOLDS,
                     level: float = LEVEL, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Rule-10 pooled all-start mean over every entry (weekly clusters), CI at blocks of h x ``hold_days`` (in weeks) for
    each h in ``holds``. side +1: a pass is lower bound > 0 (decisive fail: upper < 0); side -1: upper < 0 (decisive
    fail: lower > 0). ``ok`` is robust over the blocks."""
    x = np.asarray(x, dtype=float)
    S, N = week_clusters(days, x)
    rows = []
    for h in holds:
        bw = int(math.ceil(h * hold_days / 7.0))
        lo, hi = cluster_mean_ci(S, N, bw, level, n_boot, seed)
        if lo is None:
            ok = dec = None
        else:
            ok = bool(lo > 0) if side > 0 else bool(hi < 0)
            dec = bool(hi < 0) if side > 0 else bool(lo > 0)
        rows.append({"holds": int(h), "block_weeks": bw, "ci": [lo, hi], "ok": ok, "decisive_fail": dec})
    return {"mean": float(x.mean()) if x.size else None, "n_entries": int(x.size), "n_weeks": int(S.size),
            "by_block": rows, "ok": _robust([r["ok"] for r in rows]),
            "decisive_fail": bool(rows) and all(r["decisive_fail"] is True for r in rows)}


def week_weighted(days: Sequence[str], x, hold_days: int, holds: int = BLOCK_HOLDS[0], n_boot: Optional[int] = None,
                  seed: int = SEED) -> dict:
    """Calendar-weighted sensitivity: the mean of weekly means (each week with entries counts once, so the denser
    snapshot cadence of later years does not weigh more), CI over weeks at a block of ``holds`` x the hold."""
    S, N = week_clusters(days, x)
    has = N > 0
    if not has.any():
        return {"mean": None, "ci": [None, None], "n_weeks": 0}
    Sw = np.where(has, S / np.maximum(N, 1.0), 0.0)
    Nw = has.astype(float)
    lo, hi = cluster_mean_ci(Sw, Nw, int(math.ceil(holds * hold_days / 7.0)), LEVEL, n_boot, seed)
    return {"mean": float(Sw.sum() / Nw.sum()), "ci": [lo, hi], "n_weeks": int(has.sum())}


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (rule 5);
    otherwise it is reported as not decisive (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


# ============================================================================================ archive plumbing ==

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
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — "
                "not implemented: every criterion (no data)")
    return None


def _created(archive, name: str) -> str:
    try:
        return getattr(archive.get(name), "created_at", "") or ""
    except (KeyError, AttributeError):
        return ""


def closes_from_rows(rows, created: str = "") -> tuple:
    """(days, raw close, adjclose) from daily-history rows (``value.t`` = bar open, UTC). A bar dated on or after the
    bundle's capture day is dropped unless the capture came after 21:00 UTC (the bar may still have been open)."""
    by = {}
    for r in rows:
        v = r.get("value") or {}
        c = _num(v.get("close"))
        if c is None or c <= 0:
            continue
        if v.get("t") is not None:
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        elif v.get("day"):
            d = str(v["day"])[:10]
        else:
            continue
        if created and (d > created[:10] or (d == created[:10] and created[11:16] < "21:00")):
            continue
        a = _num(v.get("adjclose"))
        by[d] = (c, a if a is not None and a > 0 else c)
    days = sorted(by)
    return (days, np.array([by[d][0] for d in days], dtype=float), np.array([by[d][1] for d in days], dtype=float))


def dividend_events(days: Sequence[str], close, adj, min_step: float = 1e-4) -> list:
    """[(ex_day, amount)] from the adjclose/close ratio steps: on ex-day i, D = close[i-1] (1 - f[i-1]/f[i])."""
    close = np.asarray(close, dtype=float)
    adj = np.asarray(adj, dtype=float)
    if close.size < 2:
        return []
    f = adj / close
    out = []
    for i in range(1, close.size):
        if f[i - 1] > 0 and f[i] / f[i - 1] > 1.0 + min_step:
            out.append((days[i], float(close[i - 1] * (1.0 - f[i - 1] / f[i]))))
    return out


def index_closes(rows) -> dict:
    out = {}
    for r in rows:
        v = r.get("value") or {}
        c = _num(v.get("close"))
        d = v.get("day")
        if c is not None and d:
            out[str(d)[:10]] = c
    return out


# =============================================================================================== the chain ==

def chain_days(rows, spot_by_day: dict) -> tuple:
    """({quote_date: day}, info). One snapshot per quote day (kept: not stale and taken on the quote day, else the
    earliest). day = {quote_date, snapshot_date, stale, available_at, spot, exp: {expiry: {"call": [...], "put": [...]}}},
    legs {strike, bid, ask, iv, delta} sorted by strike."""
    snaps = defaultdict(list)
    for r in rows:
        v = r.get("value") or {}
        if v.get("snapshot_date") and v.get("expiry") and v.get("type") in ("call", "put") and _num(v.get("strike")):
            snaps[v["snapshot_date"]].append(r)
    best = {}
    for s, rs in snaps.items():
        q = rs[0]["value"].get("quote_date") or s
        stale = any(r["value"].get("stale") is True for r in rs)
        key = (stale, s != q, s)
        if q not in best or key < best[q][0]:
            best[q] = (key, s, rs, stale)
    out = {}
    for q, (key, s, rs, stale) in best.items():
        exp = defaultdict(lambda: {"call": [], "put": []})
        for r in rs:
            v = r["value"]
            exp[v["expiry"]][v["type"]].append({"strike": float(v["strike"]), "bid": _num(v.get("bid")),
                                                "ask": _num(v.get("ask")), "iv": _num(v.get("iv")),
                                                "delta": _num(v.get("delta"))})
        for e in exp.values():
            e["call"].sort(key=lambda l: l["strike"])
            e["put"].sort(key=lambda l: l["strike"])
        out[q] = {"quote_date": q, "snapshot_date": s, "stale": stale,
                  "available_at": max((r.get("available_at") or "") for r in rs), "spot": spot_by_day.get(q),
                  "exp": dict(exp)}
    info = {"snapshots": len(snaps), "quote_days": len(out), "duplicate_snapshots_dropped": len(snaps) - len(out),
            "moved_stale_kept": sum(1 for d in out.values() if d["stale"]),
            "no_spot": sum(1 for d in out.values() if d["spot"] is None),
            "first": min(out) if out else None, "last": max(out) if out else None}
    return out, info


def dte(expiry: str, quote_day: str) -> int:
    return _ord(expiry) - _ord(quote_day)


def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def monthly_expiries(y0: int, y1: int) -> set:
    """Standard monthly expiries: the third Friday, or the prior NYSE session when that Friday is a holiday."""
    out = set()
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            d = third_friday(y, m)
            while not is_trading_day(d):
                d -= timedelta(days=1)
            out.add(d.isoformat())
    return out


def pick_expiry(day: dict, target: int, tol: int, allowed: Optional[set] = None) -> Optional[str]:
    """The listed expiry nearest ``target`` calendar days (ties to the longer-dated), or None beyond ``tol``."""
    q = day["quote_date"]
    best = None
    for e in day["exp"]:
        if allowed is not None and e not in allowed:
            continue
        d = dte(e, q)
        if d <= 0:
            continue
        key = (abs(d - target), -d)
        if best is None or key < best[0]:
            best = (key, e)
    if best is None or best[0][0] > tol:
        return None
    return best[1]


def usable(leg: dict) -> bool:
    b, a = leg.get("bid"), leg.get("ask")
    return b is not None and a is not None and b > 0 and a >= b


def mid(leg: dict) -> float:
    return 0.5 * (leg["bid"] + leg["ask"])


def pick_delta(legs: Sequence[dict], target: float, tol: float = DELTA_TOL) -> Optional[dict]:
    """The usable leg whose |vendor delta| is nearest ``target`` (ties to the lower strike), None beyond ``tol``."""
    best = None
    for l in legs:
        d = l.get("delta")
        if not usable(l) or d is None or not 0 < abs(d) < 1:
            continue
        key = (abs(abs(d) - target), l["strike"])
        if best is None or key < best[0]:
            best = (key, l)
    if best is None or best[0][0] > tol:
        return None
    return best[1]


def pick_moneyness(legs: Sequence[dict], spot: float, ratio: float, tol: float) -> Optional[dict]:
    """The usable leg whose K/S is nearest ``ratio`` (ties to the lower strike), None beyond ``tol``."""
    best = None
    for l in legs:
        if not usable(l):
            continue
        key = (abs(l["strike"] / spot - ratio), l["strike"])
        if best is None or key < best[0]:
            best = (key, l)
    if best is None or best[0][0] > tol:
        return None
    return best[1]


def mix_legs(legs: Sequence[dict], k_target: float, gap: float) -> Optional[list]:
    """The claim's exact moneyness from tradable quotes: [(leg, weight)] over the two usable listed strikes bracketing
    ``k_target`` (weights sum to 1 and put the average strike exactly at the target; one leg at weight 1 when a usable
    strike sits on it). None when a side has no usable strike or the bracket is wider than ``gap`` (in $)."""
    us = [l for l in legs if usable(l)]
    lo = [l for l in us if l["strike"] <= k_target]
    hi = [l for l in us if l["strike"] >= k_target]
    if not lo or not hi:
        return None
    a, b = max(lo, key=lambda l: l["strike"]), min(hi, key=lambda l: l["strike"])
    if b["strike"] == a["strike"]:
        return [(a, 1.0)]
    if b["strike"] - a["strike"] > gap:
        return None
    w = (b["strike"] - k_target) / (b["strike"] - a["strike"])
    return [(a, w), (b, 1.0 - w)]


def iv_at(legs: Sequence[dict], spot: float, ratio: float, tol: float = MONEY_TOL, gap: float = SLOPE_GAP) -> Optional[float]:
    """Vendor IV at K/S = ``ratio``: linear in K/S between the bracketing strikes (at most ``gap`` apart), else the
    nearest strike within ``tol``."""
    pts = sorted((l["strike"] / spot, l["iv"]) for l in legs if l.get("iv") is not None and l["iv"] > 0)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    j = bisect_left(xs, ratio)
    if j < len(xs) and abs(xs[j] - ratio) < 1e-12:
        return float(pts[j][1])
    if 0 < j < len(xs) and xs[j] - xs[j - 1] <= gap:
        w = (ratio - xs[j - 1]) / (xs[j] - xs[j - 1])
        return float(pts[j - 1][1] + w * (pts[j][1] - pts[j - 1][1]))
    k = min(range(len(xs)), key=lambda i: abs(xs[i] - ratio))
    return float(pts[k][1]) if abs(xs[k] - ratio) <= tol else None


# ============================================================================================== structures ==

def _leg(l: dict, kind: str, qty: int) -> dict:
    return {"kind": kind, "strike": l["strike"], "qty": int(qty), "bid": l["bid"], "ask": l["ask"], "mid": mid(l),
            "iv": l.get("iv"), "delta": l.get("delta")}


def _trade(day: dict, expiry: str, legs: list, **extra) -> dict:
    return {"entry": day["quote_date"], "snapshot": day["snapshot_date"], "expiry": expiry,
            "dte": dte(expiry, day["quote_date"]), "spot": float(day["spot"]), "legs": legs,
            "late_stamp": bool((day.get("available_at") or "") > day["quote_date"] + EVENING), **extra}


def leg_px(leg: dict, fill: str) -> float:
    if fill == "mid":
        return leg["mid"]
    return leg["ask"] if leg["qty"] > 0 else leg["bid"]


def net_credit(trade: dict, fill: str) -> float:
    """Premium received (negative = paid) at ``fill``: mid, or exec (buy at the ask, sell at the bid)."""
    return -sum(l["qty"] * leg_px(l, fill) for l in trade["legs"])


def intrinsic(kind: str, k: float, s: float) -> float:
    return max(s - k, 0.0) if kind == "call" else max(k - s, 0.0)


def payoff(trade: dict, s_t: float) -> float:
    return sum(l["qty"] * intrinsic(l["kind"], l["strike"], s_t) for l in trade["legs"])


def contracts(trade: dict) -> int:
    return sum(abs(l["qty"]) for l in trade["legs"])


def _base_checks(day: dict, target: int, tol: int, allowed: Optional[set] = None):
    if day.get("spot") is None:
        return None, "no SPY close on the quote day"
    e = pick_expiry(day, target, tol, allowed)
    if e is None:
        return None, f"no {'monthly ' if allowed is not None else ''}expiry within {target} +/- {tol} DTE"
    return e, None


def backspread_trade(day: dict, target: int = T119_DTE, tol: int = DTE_TOL):
    """T-119: short 1 ATM call (strike nearest the spot, within 2%), long 2 calls at the 25-delta strike."""
    e, why = _base_checks(day, target, tol)
    if e is None:
        return None, why
    calls, S = day["exp"][e]["call"], day["spot"]
    k1 = pick_moneyness(calls, S, 1.0, ATM_TOL)
    if k1 is None:
        return None, "no usable ATM call"
    k2 = pick_delta(calls, 0.25)
    if k2 is None:
        return None, "no usable 25-delta call"
    if k2["strike"] <= k1["strike"]:
        return None, "25-delta strike not above the ATM strike"
    return _trade(day, e, [_leg(k1, "call", -1), _leg(k2, "call", 2)]), None


def front_ratio_trade(day: dict, target: int = T121_DTE, tol: int = DTE_TOL):
    """T-121: long 1 put at the 40-delta strike, short 2 puts at the 20-delta strike."""
    e, why = _base_checks(day, target, tol)
    if e is None:
        return None, why
    puts = day["exp"][e]["put"]
    p40, p20 = pick_delta(puts, 0.40), pick_delta(puts, 0.20)
    if p40 is None or p20 is None:
        return None, "no usable 40- or 20-delta put"
    if p40["strike"] <= p20["strike"]:
        return None, "40-delta strike not above the 20-delta strike"
    return _trade(day, e, [_leg(p40, "put", 1), _leg(p20, "put", -2)], naked=1), None


def ladder_trade(day: dict, target: int = T539_DTE, tol: int = DTE_TOL):
    """T-539: long 1 put at the 40-delta strike, short 1 at the 25-delta and 1 at the 15-delta strike."""
    e, why = _base_checks(day, target, tol)
    if e is None:
        return None, why
    puts = day["exp"][e]["put"]
    p40, p25, p15 = pick_delta(puts, 0.40), pick_delta(puts, 0.25), pick_delta(puts, 0.15)
    if p40 is None or p25 is None or p15 is None:
        return None, "no usable 40-, 25- or 15-delta put"
    if not p40["strike"] > p25["strike"] > p15["strike"]:
        return None, "strikes not in 40 > 25 > 15-delta order"
    return _trade(day, e, [_leg(p40, "put", 1), _leg(p25, "put", -1), _leg(p15, "put", -1)], naked=2), None


def overlay_trade(day: dict, monthly: set, target: int = T173_DTE, tol: int = DTE_TOL):
    """T-173: the 1x2-minus-single overlay spread on the monthly expiry (short 1 call nearest 1.05 S, long 1 call
    nearest 1.10 S) with the entry-day slope IV(1.10) - IV(1.05) per unit of moneyness."""
    e, why = _base_checks(day, target, tol, monthly)
    if e is None:
        return None, why
    calls, S = day["exp"][e]["call"], day["spot"]
    c5, c10 = pick_moneyness(calls, S, 1.05, MONEY_TOL), pick_moneyness(calls, S, 1.10, MONEY_TOL)
    if c5 is None or c10 is None:
        return None, "no usable 5%- or 10%-OTM call"
    if c10["strike"] <= c5["strike"]:
        return None, "10%-OTM strike not above the 5%-OTM strike"
    i5, i10 = iv_at(calls, S, 1.05), iv_at(calls, S, 1.10)
    if i5 is None or i10 is None:
        return None, "no vendor IV at 5% or 10% OTM"
    return _trade(day, e, [_leg(c5, "call", -1), _leg(c10, "call", 1)], cohort=e, signal=(i10 - i5) / 0.05,
                  iv5=i5, iv10=i10), None


def naked_put_margin(leg: dict, spot: float, fill: str) -> float:
    """Reg-T/CBOE naked equity put: premium + max(20% x S - OTM amount, 10% x K), OTM = max(S - K, 0); premium = the
    put's fill price (mid, or the bid it is sold at)."""
    prem = leg["mid"] if fill == "mid" else leg["bid"]
    k = leg["strike"]
    return prem + max(0.20 * spot - max(spot - k, 0.0), 0.10 * k)


def backspread_max_loss(trade: dict, fill: str) -> float:
    k1 = next(l["strike"] for l in trade["legs"] if l["qty"] < 0)
    k2 = next(l["strike"] for l in trade["legs"] if l["qty"] > 0)
    return (k2 - k1) - net_credit(trade, fill)


def exercise_early(s_cum: float, k: float, amount: float, tau: float, iv: Optional[float]) -> bool:
    """Is an American call exercised at the cum-dividend close? Exercise value S - K beats holding, worth about
    (S - D - K) + P(S - D, K) at r = 0 (put-call parity on the ex-dividend price), when D > P: the remaining time value.
    P is a Black-Scholes put at the leg's entry vendor IV (r = q = 0, so it errs towards exercising); without an IV the
    rule is S - K > D."""
    if s_cum - k <= 0:
        return False
    if iv is None or not iv > 0 or tau <= 0:
        return s_cum - k > amount
    p = float(bs.price(max(s_cum - amount, 1e-9), k, tau, 0.0, iv, "put"))
    return amount > p


def early_exercise_payoff(trade: dict, s_t: float, divs: Sequence[tuple], days: Sequence[str], close_by: dict) -> float:
    """Payoff when each call that ``exercise_early`` exercises at the cum-dividend close (the session before an ex-date
    in (entry, expiry]) is settled there at that close's intrinsic value (short calls assigned, long calls exercised);
    other legs at expiry."""
    tot = 0.0
    for l in trade["legs"]:
        val = None
        if l["kind"] == "call":
            for ex, amt in divs:
                if not trade["entry"] < ex <= trade["expiry"]:
                    continue
                j = bisect_left(days, ex) - 1
                if j < 0 or days[j] <= trade["entry"]:
                    continue
                sc = close_by.get(days[j])
                tau = (_ord(trade["expiry"]) - _ord(days[j])) / 365.0
                if sc is not None and exercise_early(sc, l["strike"], amt, tau, l.get("iv")):
                    val = sc - l["strike"]
                    break
        if val is None:
            val = intrinsic(l["kind"], l["strike"], s_t)
        tot += l["qty"] * val
    return tot


# ========================================================================================== trade building ==

def build_trades(chain: dict, builder: Callable, **kw) -> tuple:
    trades, skips = [], Counter()
    for q in sorted(chain):
        t, why = builder(chain[q], **kw)
        if t is None:
            skips[why] += 1
        else:
            trades.append(t)
    return trades, skips


def resolve(trades: list, close_by: dict, last_day: str) -> tuple:
    """Attach s_t (raw close on the expiry date). Returns (resolved, counts)."""
    out, cnt = [], Counter()
    for t in trades:
        c = close_by.get(t["expiry"])
        if c is not None:
            out.append(dict(t, s_t=float(c)))
        elif t["expiry"] > last_day:
            cnt["unresolved (expiry after the last archived close)"] += 1
        else:
            cnt["no SPY close on the expiry date"] += 1
    return out, cnt


def n_holds(days: Sequence[str], hold_days: int) -> int:
    if not len(days):
        return 0
    o = [_ord(d) for d in days]
    return int((max(o) - min(o)) // hold_days + 1)


def start_chains(trades: Sequence[dict], hold_days: int) -> list:
    """Rule 10: from every entry day in the first ``hold_days`` calendar days, the non-overlapping chain that enters on
    the first entry day on or after the previous trade's expiry. Returns lists of trade indices (trades sorted by entry)."""
    ents = [t["entry"] for t in trades]
    if not ents:
        return []
    o0 = _ord(ents[0])
    starts = [i for i, d in enumerate(ents) if _ord(d) - o0 < hold_days]
    chains = []
    for s in starts:
        seq, cur = [s], s
        while True:
            j = bisect_left(ents, trades[cur]["expiry"])
            if j >= len(ents):
                break
            seq.append(j)
            cur = j
        chains.append(seq)
    return chains


def chain_scan(trades: Sequence[dict], x, hold_days: int, side: int, block: int = CHAIN_BLOCK, level: float = LEVEL,
               n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Per-start non-overlapping chains: mean, studentized CI (block ``block`` trades), pass flag; plus the range."""
    x = np.asarray(x, dtype=float)
    rows, seen = [], set()
    for seq in start_chains(trades, hold_days):
        xs = x[seq]
        lo, hi = cluster_mean_ci(xs, np.ones(xs.size), block, level, n_boot, seed)
        ok = None if lo is None else (bool(lo > 0) if side > 0 else bool(hi < 0))
        rows.append({"start": trades[seq[0]]["entry"], "n": int(xs.size), "mean": float(xs.mean()) if xs.size else None,
                     "ci": [lo, hi], "ok": ok})
        seen.add(tuple(seq))
    good = [r for r in rows if r["ci"][0] is not None]
    b = [r["ci"][0] if side > 0 else r["ci"][1] for r in good]
    return {"rows": rows, "n_starts": len(rows), "n_distinct": len(seen), "n_pass": sum(1 for r in rows if r["ok"]),
            "n_min": min((r["n"] for r in rows), default=0), "n_max": max((r["n"] for r in rows), default=0),
            "mean_min": min((r["mean"] for r in good), default=None), "mean_max": max((r["mean"] for r in good), default=None),
            "bound_min": min(b, default=None), "bound_max": max(b, default=None), "side": side}


def _chain_txt(cs: dict, nd: int = 3) -> str:
    if not cs["n_starts"]:
        return "per-start grids: none"
    b = "lower" if cs["side"] > 0 else "upper"
    if cs["mean_min"] is None:
        return (f"per start (rule 10: {cs['n_starts']} non-overlapping chains, {cs['n_distinct']} distinct, "
                f"{cs['n_min']}-{cs['n_max']} trades each): too few trades for intervals")
    return (f"per start (rule 10: {cs['n_starts']} non-overlapping chains from the entry days of the first hold, "
            f"{cs['n_distinct']} distinct, {cs['n_min']}-{cs['n_max']} trades each, block {CHAIN_BLOCK} trades): mean "
            f"{_s(cs['mean_min'], nd)} to {_s(cs['mean_max'], nd)}, {b} bound {_s(cs['bound_min'], nd)} to "
            f"{_s(cs['bound_max'], nd)}, {cs['n_pass']}/{cs['n_starts']} pass")


def _pool_txt(p: dict, nd: int = 3) -> str:
    cis = "; ".join(f"block {r['block_weeks']} weeks ({r['holds']}x hold) {_ci_s(r['ci'], nd)}" for r in p["by_block"])
    return f"mean {_s(p['mean'], nd)} (pooled over {p['n_entries']} entry days in {p['n_weeks']} weeks; {cis})"


def _ok_txt(ok) -> str:
    return "n/a" if ok is None else ("yes" if ok else "no")


# ================================================================================================= stress ==

def stress_sessions(vix: dict, level: float = STRESS_VIX) -> list:
    return sorted(d for d, v in vix.items() if v is not None and v >= level)


def stress_hits(trades: Sequence[dict], sessions: Sequence[str]) -> list:
    """Months of stress sessions that some trade was open across (entry < session <= expiry)."""
    if not trades or not sessions:
        return []
    ents = sorted((t["entry"], t["expiry"]) for t in trades)
    hits = set()
    for s in sessions:
        if any(e < s <= x for e, x in ents):
            hits.add(s[:7])
    return sorted(hits)


def drawdown_months(days: Sequence[str], close, dd: float = STRESS_DD, window: int = DD_WINDOW, start: str = "") -> list:
    c = np.asarray(close, dtype=float)
    out = set()
    for i in range(c.size):
        if days[i] < start:
            continue
        hi = c[max(0, i - window + 1):i + 1].max()
        if c[i] <= (1.0 - dd) * hi:
            out.add(days[i][:7])
    return sorted(out)


# ================================================================================================= judges ==

def _by_year(trades: Sequence[dict], x) -> dict:
    by = defaultdict(list)
    for t, v in zip(trades, x):
        by[t["entry"][:4]].append(float(v))
    return {y: {"n": len(v), "mean": float(np.mean(v))} for y, v in sorted(by.items())}


def _desc(x) -> dict:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {}
    return {"mean": float(x.mean()), "median": float(np.median(x)), "sd": float(x.std(ddof=1)) if x.size > 1 else None,
            "min": float(x.min()), "max": float(x.max()), "share_positive": float((x > 0).mean())}


def mean_claim(trades: Sequence[dict], ratios: dict, *, hold_days: int, min_n: int, criteria: Sequence[tuple],
               stress: Optional[list] = None, stress_name: str = "", n_boot: Optional[int] = None,
               seed: int = SEED) -> dict:
    """Judge a per-trade mean claim. ``ratios``: {fill: per-trade statistic}. ``criteria``: [(label, fill, side)];
    side +1 claims a positive mean (pass lower > 0), -1 a negative mean (pass upper < 0). ``stress``: months in the
    sample (None = not a criterion). n = entry days."""
    days = [t["entry"] for t in trades]
    n = len(trades)
    pooled = {f: pooled_mean_test(days, ratios[f], hold_days, side, n_boot=n_boot, seed=seed)
              for f, side in {f: s for _, f, s in criteria}.items()}
    for f in ratios:
        if f not in pooled:
            pooled[f] = pooled_mean_test(days, ratios[f], hold_days, 1, n_boot=n_boot, seed=seed)
    crit, parts, weekly = [], [], {}
    for label, f, side in criteria:
        p = pooled[f]
        want = "lower 95% CI > 0" if side > 0 else "upper 95% CI < 0"
        crit.append((f"{label}: {want} for the mean, robust over blocks of "
                     f"{'/'.join(str(r['holds']) for r in p['by_block'])}x the hold", p["ok"], p["decisive_fail"]))
        weekly[f] = week_weighted(days, ratios[f], hold_days, n_boot=n_boot, seed=seed)
        parts.append(f"{label}: {_pool_txt(p)} -> {want}: {_ok_txt(p['ok'])} (week-weighted, reported: mean "
                     f"{_s(weekly[f]['mean'], 3)}, {_ci_s(weekly[f]['ci'])})")
    keep = [i for i, t in enumerate(trades) if not t.get("late_stamp")]
    strict = {"n": len(keep), "n_dropped": n - len(keep)}
    if len(keep) >= MIN_CLUSTERS:
        for label, f, side in criteria:
            ps = pooled_mean_test([days[i] for i in keep], np.asarray(ratios[f], dtype=float)[keep], hold_days, side,
                                  holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed)
            strict[f] = {"mean": ps["mean"], "ci": ps["by_block"][0]["ci"]}
    parts.append(f"strict available_at sensitivity (drops the {n - len(keep)} entries whose rows are stamped available "
                 f"after the entry close: weekend, holiday or moved snapshots): "
                 + "; ".join(f"{f} mean {_s(strict[f]['mean'], 3)} ({_ci_s(strict[f]['ci'])})"
                             for _, f, _ in criteria if f in strict))
    if stress is not None:
        crit.append((stress_name, True if stress else None, False))
    verdict, why = _decide(crit, n, min_n, "entry days")
    scans = {f: chain_scan(trades, ratios[f], hold_days, side, n_boot=n_boot, seed=seed) for _, f, side in criteria}
    return {"verdict": verdict, "why": why, "n": n, "pooled": pooled, "scans": scans, "parts": parts,
            "week_weighted": weekly, "strict_available_at": strict, "n_holds": n_holds(days, hold_days)}


def quartile_claim(trades: Sequence[dict], x, signal, *, min_n: int, blocks: Sequence[int] = COHORT_BLOCKS,
                   labels: Optional[tuple] = None, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-173: top-minus-bottom quartile difference of mean x by ``signal`` (full-sample quartiles unless ``labels`` =
    (top, bottom) masks are given), clustered by expiry cohort (time order), CI at each cohort block; pass lower > 0
    robust over the blocks. n = cohorts."""
    x = np.asarray(x, dtype=float)
    sig = np.asarray(signal, dtype=float)
    cohorts = sorted({t["cohort"] for t in trades})
    n = len(cohorts)
    if labels is None:
        if sig.size:
            q1, q3 = np.quantile(sig, [0.25, 0.75])
            top, bot = sig >= q3, sig <= q1
        else:
            q1 = q3 = None
            top = bot = np.zeros(0, dtype=bool)
    else:
        q1 = q3 = None
        top, bot = labels
    ci_ = {c: i for i, c in enumerate(cohorts)}
    St, Nt, Sb, Nb = (np.zeros(n) for _ in range(4))
    for t, v, a, b in zip(trades, x, top, bot):
        i = ci_[t["cohort"]]
        if a:
            St[i] += v
            Nt[i] += 1
        if b:
            Sb[i] += v
            Nb[i] += 1
    rows = [cluster_diff_ci(St, Nt, Sb, Nb, b, LEVEL, n_boot, seed) for b in blocks]
    oks = [None if r["ci"][0] is None else bool(r["ci"][0] > 0) for r in rows]
    decs = [r["ci"][1] is not None and r["ci"][1] < 0 for r in rows]
    return {"n": n, "rows": rows, "ok": _robust(oks), "decisive_fail": bool(rows) and all(decs), "q1": q1, "q3": q3,
            "diff": rows[0]["diff"] if rows else None, "mean_top": rows[0]["mean_top"] if rows else None,
            "mean_bottom": rows[0]["mean_bottom"] if rows else None, "n_top": int(np.sum(top)),
            "n_bottom": int(np.sum(bot)), "n_entries": int(x.size)}


def drop_influential(trades: Sequence[dict], x, top, bot, block: int = COHORT_BLOCKS[0], k: int = 1,
                     n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Fragility check: remove the ``k`` cohorts whose influence on the top-minus-bottom difference is most in its
    favour (largest (St_c - mt Nt_c)/Nt - (Sb_c - mb Nb_c)/Nb), keep every other entry's label, and recompute."""
    x = np.asarray(x, dtype=float)
    top = np.asarray(top, dtype=bool)
    bot = np.asarray(bot, dtype=bool)
    if not top.any() or not bot.any():
        return {"dropped": [], "diff": None, "ci": [None, None]}
    mt, mb = float(x[top].mean()), float(x[bot].mean())
    infl = defaultdict(float)
    for t, v, a, b in zip(trades, x, top, bot):
        infl[t["cohort"]] += (v - mt) / top.sum() * a - (v - mb) / bot.sum() * b
    drop = [c for c, _ in sorted(infl.items(), key=lambda kv: -kv[1])[:k]]
    keep = np.array([t["cohort"] not in drop for t in trades], dtype=bool)
    q = quartile_claim([t for t, kk in zip(trades, keep) if kk], x[keep], np.zeros(int(keep.sum())), min_n=0,
                       blocks=(block,), labels=(top[keep], bot[keep]), n_boot=n_boot, seed=seed)
    return {"dropped": drop, "diff": q["diff"], "ci": q["rows"][0]["ci"], "mean_top": q["mean_top"],
            "mean_bottom": q["mean_bottom"]}


def expanding_labels(trades: Sequence[dict], signal, min_cohorts: int = PIT_MIN_COHORTS) -> tuple:
    """Point-in-time quartile labels: each entry is labelled by the quartiles of the signals of entries made strictly
    before it, once those come from at least ``min_cohorts`` distinct cohorts; earlier entries are unlabelled."""
    sig = np.asarray(signal, dtype=float)
    top = np.zeros(sig.size, dtype=bool)
    bot = np.zeros(sig.size, dtype=bool)
    for i, t in enumerate(trades):
        prior = [j for j in range(sig.size) if trades[j]["entry"] < t["entry"]]
        if len({trades[j]["cohort"] for j in prior}) < min_cohorts:
            continue
        q1, q3 = np.quantile(sig[prior], [0.25, 0.75])
        top[i], bot[i] = sig[i] >= q3, sig[i] <= q1
    return top, bot


def _qrows_txt(q: dict, scale: float = 100.0, unit: str = "% of S", nd: int = 2) -> str:
    cis = "; ".join(f"block {r['block']} cohorts {_ci_s(r['ci'], nd, scale)}" for r in q["rows"])
    return (f"top quartile {_s(q['mean_top'] and q['mean_top'] * scale, nd)} vs bottom "
            f"{_s(q['mean_bottom'] and q['mean_bottom'] * scale, nd)}{unit} (n {q['n_top']} / {q['n_bottom']} entries), "
            f"difference {_s(q['diff'] and q['diff'] * scale, nd)}{unit} ({cis})")


# ============================================================================================ data access ==

def _world(archive) -> dict:
    def build():
        days, close, adj = closes_from_rows(archive.load(SPY_B), _created(archive, SPY_B))
        close_by = dict(zip(days, (float(c) for c in close)))
        chain, info = chain_days(archive.load(CHAIN_B), close_by)
        return {"days": days, "close": close, "adj": adj, "close_by": close_by, "chain": chain, "info": info,
                "divs": dividend_events(days, close, adj), "last": days[-1] if days else ""}
    return _cached(archive, "world", build)


def _vix(archive) -> dict:
    return _cached(archive, "vix", lambda: index_closes(archive.load(VIX_B)))


def _data_txt(W: dict) -> str:
    i = W["info"]
    return (f"DoltHub end-of-day SPY quotes {i['first']}..{i['last']} ({i['quote_days']} quote days from "
            f"{i['snapshots']} snapshots; {i['duplicate_snapshots_dropped']} duplicate snapshots of a quote day dropped, "
            f"{i['moved_stale_kept']} stale-moved kept on their quote day)")


def _skips_txt(skips: Counter, unres: Counter) -> str:
    c = skips + unres
    return "; ".join(f"{k} {v}" for k, v in c.most_common()) or "none"


def _too_few(stat: dict, n: int, min_n: int, unit: str, head: str, extra: str = ""):
    why = f"not implemented: every criterion (too few entries to judge); n >= trial min_n ({n} of {min_n} {unit})"
    return _out(stat, n, "inconclusive", f"{head}: too few resolved entries ({n}){extra} — {why}")


def _tol_sens(W: dict, builder: Callable, metric: Callable, target: int, side: int, n_boot: Optional[int]) -> dict:
    """The primary fill's pooled mean and 2x-hold CI at the sensitivity DTE tolerances."""
    out = {}
    for tol in DTE_SENS:
        tr, _ = build_trades(W["chain"], builder, target=target, tol=tol)
        tr, _ = resolve(tr, W["close_by"], W["last"])
        x = np.array([metric(t) for t in tr], dtype=float)
        ok = np.isfinite(x)
        tr = [t for t, k in zip(tr, ok) if k]
        x = x[ok]
        if len(tr) < MIN_CLUSTERS:
            out[str(tol)] = {"n": len(tr), "mean": None, "ci": [None, None]}
            continue
        p = pooled_mean_test([t["entry"] for t in tr], x, target + tol, side, holds=(BLOCK_HOLDS[0],), n_boot=n_boot)
        out[str(tol)] = {"n": len(tr), "mean": p["mean"], "ci": p["by_block"][0]["ci"]}
    return out


def _tol_txt(sens: dict, nd: int = 3) -> str:
    return "; ".join(f"+/-{k} DTE: n {v['n']}, mean {_s(v['mean'], nd)} ({_ci_s(v['ci'], nd)})" for k, v in sens.items())


# ============================================================================================== T-119 ==

def backspread_metrics(t: dict, W: Optional[dict] = None) -> dict:
    """P&L, max loss and ratio at mid and exec; the upper breakeven; the early-exercise-sensitivity ratio at mid."""
    out = {}
    pay = payoff(t, t["s_t"])
    for f in FILLS:
        cr = net_credit(t, f)
        ml = backspread_max_loss(t, f)
        pnl = pay + cr
        out[f] = {"credit": cr, "max_loss": ml, "pnl": pnl, "ratio": pnl / ml if ml > 0 else float("nan")}
    k1 = next(l["strike"] for l in t["legs"] if l["qty"] < 0)
    k2 = next(l["strike"] for l in t["legs"] if l["qty"] > 0)
    out["upper_be"] = k2 + (k2 - k1) - out["mid"]["credit"]
    out["above_be"] = bool(t["s_t"] > out["upper_be"])
    out["exec_comm_ratio"] = ((out["exec"]["pnl"] - COMM * contracts(t)) / out["exec"]["max_loss"]
                              if out["exec"]["max_loss"] > 0 else float("nan"))
    if W is not None:
        pe = early_exercise_payoff(t, t["s_t"], W["divs"], W["days"], W["close_by"])
        out["early_ratio"] = (pe + out["mid"]["credit"]) / out["mid"]["max_loss"] if out["mid"]["max_loss"] > 0 else float("nan")
    return out


def backspread_claim(trades: Sequence[dict], mets: Sequence[dict], *, min_n: int = T119_MIN_N, hold_days: int,
                     n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    ratios = {f: np.array([m[f]["ratio"] for m in mets], dtype=float) for f in FILLS}
    return mean_claim(trades, ratios, hold_days=hold_days, min_n=min_n,
                      criteria=[("mid fills (the claim and the pass)", "mid", -1)], n_boot=n_boot, seed=seed)


def b6b_dolt_backspread(archive):
    """T-119: 60-DTE SPY 1:2 call backspread (short ATM, long 2x 25-delta) at mid, held to expiry: mean P&L / max loss
    < 0 (upper 95% CI < 0 at mid)."""
    miss = _missing(archive, [CHAIN_B, SPY_B])
    if miss:
        return miss
    W = _world(archive)
    head = (f"T-119 SPY 1:2 call backspread (short 1 ATM call, long 2 25-delta calls; expiry nearest {T119_DTE} DTE within "
            f"+/-{DTE_TOL} days; {_data_txt(W)}; settled at intrinsic on SPY's raw close on the expiry date, early "
            "exercise ignored as the claim holds to expiry)")
    trades, skips = build_trades(W["chain"], backspread_trade, target=T119_DTE, tol=DTE_TOL)
    trades, unres = resolve(trades, W["close_by"], W["last"])
    mets = [backspread_metrics(t, W) for t in trades]
    keep = [i for i, m in enumerate(mets) if math.isfinite(m["mid"]["ratio"]) and math.isfinite(m["exec"]["ratio"])]
    trades, mets = [trades[i] for i in keep], [mets[i] for i in keep]
    hold = T119_DTE + DTE_TOL
    stat = {"claim": "T-119", "n_entry_days": len(trades), "skips": dict(skips + unres), "data": W["info"],
            "dte_tol": DTE_TOL, "delta_tol": DELTA_TOL, "hold_days": hold}
    if len(trades) < MIN_CLUSTERS:
        return _too_few(stat, len(trades), T119_MIN_N, "entry days", head)
    core = backspread_claim(trades, mets, hold_days=hold)
    early = np.array([m["early_ratio"] for m in mets], dtype=float)
    ep = pooled_mean_test([t["entry"] for t in trades], early, hold, -1, holds=(BLOCK_HOLDS[0],))
    comm = np.array([m["exec_comm_ratio"] for m in mets], dtype=float)
    credit_mid = np.array([m["mid"]["credit"] for m in mets])
    credit_exec = np.array([m["exec"]["credit"] for m in mets])
    above = np.array([m["above_be"] for m in mets])
    pnl_mid = np.array([m["mid"]["pnl"] for m in mets])
    ml_mid = np.array([m["mid"]["max_loss"] for m in mets])
    spots = np.array([t["spot"] for t in trades])
    deltas = np.array([next(l["delta"] for l in t["legs"] if l["qty"] > 0) for t in trades])
    sens = _tol_sens(W, backspread_trade, lambda t: backspread_metrics(t)["mid"]["ratio"], T119_DTE, -1, None)
    pe, px = core["pooled"]["mid"], core["pooled"]["exec"]
    parts = [f"{len(trades)} entry days ({core['n_holds']} distinct {hold}-day holds), {trades[0]['entry']}..{trades[-1]['entry']}",
             *core["parts"], _chain_txt(core["scans"]["mid"]),
             f"executable (sell the ATM call at the bid, buy the 25-delta calls at the ask), reported: {_pool_txt(px)}",
             f"credit/debit (control, descriptive): credit at mid on {_pct(float((credit_mid > 0).mean()))} of entries "
             f"(mean net credit {_s(float(credit_mid.mean()))} = {_s(float((credit_mid / spots).mean()) * 100)}% of S; "
             f"executable {_s(float(credit_exec.mean()))}); mean max loss {_f(float(ml_mid.mean()))} = "
             f"{_f(float((ml_mid / spots).mean()) * 100)}% of S",
             f"the claim's mechanism (reported, no threshold stated): {_pct(float(above.mean()))} of trades settled above "
             f"the upper breakeven K2 + (K2 - K1) - credit",
             f"ratio of means (mean P&L / mean max loss at mid) {_s(float(pnl_mid.mean() / ml_mid.mean()), 3)}",
             f"early-exercise sensitivity (a call is exercised at a cum-dividend close when the dividend exceeds its time "
             f"value, BS put at the entry vendor IV, r = 0): "
             f"mean {_s(ep['mean'], 3)} ({_ci_s(ep['by_block'][0]['ci'])})",
             f"with $0.65/contract per leg at executable fills: mean {_s(float(np.nanmean(comm)), 3)}",
             f"DTE tolerance sensitivity at mid: {_tol_txt(sens)}",
             f"25-delta leg vendor delta {_f(float(deltas.min()))}-{_f(float(deltas.max()))}; skipped quote days: "
             f"{_skips_txt(skips, unres)}; {NO_CONTROL}"]
    stat.update({"n_distinct_holds": core["n_holds"], "first_entry": trades[0]["entry"], "last_entry": trades[-1]["entry"],
                 "mean_ratio_mid": pe["mean"], "pooled_mid": pe, "pooled_exec": px, "week_weighted": core["week_weighted"], "strict_available_at": core["strict_available_at"],
                 "per_start_mid": {k: v for k, v in core["scans"]["mid"].items()},
                 "credit_share_mid": float((credit_mid > 0).mean()), "mean_credit_mid": float(credit_mid.mean()),
                 "mean_credit_exec": float(credit_exec.mean()), "share_above_upper_breakeven": float(above.mean()),
                 "ratio_of_means_mid": float(pnl_mid.mean() / ml_mid.mean()), "early_exercise_sensitivity": ep,
                 "exec_with_commission_mean": float(np.nanmean(comm)), "dte_tolerance_sensitivity": sens,
                 "by_year_mid": _by_year(trades, [m["mid"]["ratio"] for m in mets]),
                 "desc_mid": _desc([m["mid"]["ratio"] for m in mets]), "controls": NO_CONTROL})
    return _out(stat, core["n"], core["verdict"], head + ": " + "; ".join(parts) + " — " + core["why"])


# ======================================================================================== T-121, T-539 ==

def margin_metrics(t: dict) -> dict:
    """P&L, naked-leg margin and ratio at mid and exec (plus exec with commissions)."""
    naked = t["legs"][t["naked"]]
    pay = payoff(t, t["s_t"])
    out = {}
    for f in FILLS:
        cr = net_credit(t, f)
        mg = naked_put_margin(naked, t["spot"], f)
        pnl = pay + cr
        out[f] = {"credit": cr, "margin": mg, "pnl": pnl, "ratio": pnl / mg if mg > 0 else float("nan")}
    out["exec_comm_ratio"] = (out["exec"]["pnl"] - COMM * contracts(t)) / out["exec"]["margin"]
    return out


def margin_claim(trades: Sequence[dict], mets: Sequence[dict], *, min_n: int, hold_days: int, stress: list,
                 n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    ratios = {f: np.array([m[f]["ratio"] for m in mets], dtype=float) for f in FILLS}
    name = (f"a stress month in the sample (a resolved trade open across a VIX close >= {STRESS_VIX:.0f}): "
            + (", ".join(stress) if stress else "none"))
    return mean_claim(trades, ratios, hold_days=hold_days, min_n=min_n,
                      criteria=[("mid fills (the claim)", "mid", 1), ("bid/ask fills (the pass)", "exec", 1)],
                      stress=stress, stress_name=name, n_boot=n_boot, seed=seed)


MARGIN_TXT = ("naked-leg margin = Reg-T/CBOE naked put on one uncovered short put: premium + max(20% x S - OTM amount, "
              "10% x K), OTM = max(S - K, 0), premium at the fill")


def _put_harness(archive, *, claim: str, builder: Callable, target: int, min_n: int, desc: str, naked_desc: str):
    miss = _missing(archive, [CHAIN_B, SPY_B, VIX_B])
    if miss:
        return miss
    W = _world(archive)
    head = (f"{claim} SPY {desc} (expiry nearest {target} DTE within +/-{DTE_TOL} days, strikes by vendor delta within "
            f"{DELTA_TOL}; {_data_txt(W)}; settled at intrinsic on SPY's raw close on the expiry date, early exercise "
            f"ignored as the claim holds to expiry; {MARGIN_TXT}, the uncovered leg being {naked_desc})")
    trades, skips = build_trades(W["chain"], builder, target=target, tol=DTE_TOL)
    trades, unres = resolve(trades, W["close_by"], W["last"])
    hold = target + DTE_TOL
    stat = {"claim": claim, "n_entry_days": len(trades), "skips": dict(skips + unres), "data": W["info"],
            "dte_tol": DTE_TOL, "delta_tol": DELTA_TOL, "hold_days": hold, "margin_formula": MARGIN_TXT}
    if len(trades) < MIN_CLUSTERS:
        return _too_few(stat, len(trades), min_n, "entry days", head)
    mets = [margin_metrics(t) for t in trades]
    vix = _vix(archive)
    sess = stress_sessions({d: v for d, v in vix.items() if trades[0]["entry"] <= d <= W["last"]})
    hits = stress_hits(trades, sess)
    ddm = drawdown_months(W["days"], W["close"], start=trades[0]["entry"])
    core = margin_claim(trades, mets, min_n=min_n, hold_days=hold, stress=hits)
    pm, px = core["pooled"]["mid"], core["pooled"]["exec"]
    credit_mid = np.array([m["mid"]["credit"] for m in mets])
    margin_mid = np.array([m["mid"]["margin"] for m in mets])
    pnl_x = np.array([m["exec"]["pnl"] for m in mets])
    margin_x = np.array([m["exec"]["margin"] for m in mets])
    spots = np.array([t["spot"] for t in trades])
    comm = np.array([m["exec_comm_ratio"] for m in mets], dtype=float)
    rx = np.array([m["exec"]["ratio"] for m in mets])
    worst = int(np.argmin(rx))
    sens = _tol_sens(W, builder, lambda t: margin_metrics(t)["exec"]["ratio"], target, 1, None)
    in_stress = np.array([any(t["entry"] < s <= t["expiry"] for s in sess) for t in trades])
    ex_stress = rx[~in_stress]
    parts = [f"{len(trades)} entry days ({core['n_holds']} distinct {hold}-day holds), {trades[0]['entry']}..{trades[-1]['entry']}",
             *core["parts"], f"bid/ask {_chain_txt(core['scans']['exec'])}", f"mid {_chain_txt(core['scans']['mid'])}",
             f"stress: VIX >= {STRESS_VIX:.0f} months with an open trade {', '.join(hits) or 'none'}; months with SPY >= "
             f"{STRESS_DD * 100:.0f}% below its {DD_WINDOW}-session high (reported) {', '.join(ddm) or 'none'}; "
             f"{int(in_stress.sum())} trades open across a stress session, mean bid/ask ratio "
             f"{_s(float(rx[in_stress].mean()) if in_stress.any() else None, 3)}, without them "
             f"{_s(float(ex_stress.mean()) if ex_stress.size else None, 3)}",
             f"worst trade (bid/ask) {_s(float(rx[worst]), 3)} entered {trades[worst]['entry']}, expiry "
             f"{trades[worst]['expiry']}",
             f"credit at mid on {_pct(float((credit_mid > 0).mean()))} of entries (mean {_s(float(credit_mid.mean()))}); "
             f"mean naked-leg margin {_f(float(margin_mid.mean()))} = {_f(float((margin_mid / spots).mean()) * 100)}% of S; "
             f"ratio of means at bid/ask {_s(float(pnl_x.mean() / margin_x.mean()), 3)}",
             f"with $0.65/contract per leg at bid/ask: mean {_s(float(np.nanmean(comm)), 3)}",
             f"DTE tolerance sensitivity at bid/ask: {_tol_txt(sens)}",
             f"skipped quote days: {_skips_txt(skips, unres)}"]
    stat.update({"n_distinct_holds": core["n_holds"], "first_entry": trades[0]["entry"], "last_entry": trades[-1]["entry"],
                 "mean_ratio_mid": pm["mean"], "mean_ratio_exec": px["mean"], "pooled_mid": pm, "pooled_exec": px, "week_weighted": core["week_weighted"], "strict_available_at": core["strict_available_at"],
                 "per_start_exec": core["scans"]["exec"], "per_start_mid": core["scans"]["mid"],
                 "stress_months_in_sample": hits, "stress_sessions": len(sess), "drawdown_months": ddm,
                 "n_trades_in_stress": int(in_stress.sum()),
                 "mean_exec_in_stress": float(rx[in_stress].mean()) if in_stress.any() else None,
                 "mean_exec_ex_stress": float(ex_stress.mean()) if ex_stress.size else None,
                 "worst_exec": {"ratio": float(rx[worst]), "entry": trades[worst]["entry"], "expiry": trades[worst]["expiry"]},
                 "credit_share_mid": float((credit_mid > 0).mean()), "mean_margin_pct_spot": float((margin_mid / spots).mean()),
                 "ratio_of_means_exec": float(pnl_x.mean() / margin_x.mean()),
                 "exec_with_commission_mean": float(np.nanmean(comm)), "dte_tolerance_sensitivity": sens,
                 "by_year_exec": _by_year(trades, rx), "desc_exec": _desc(rx)})
    return _out(stat, core["n"], core["verdict"], head + ": " + "; ".join(parts) + " — " + core["why"])


def b6b_dolt_put_front_ratio(archive):
    """T-121: 45-DTE SPY put front-ratio (long 40-delta, short 2x 20-delta) held to expiry: positive mean P&L / naked-leg
    margin; pass lower 95% CI > 0 at bid/ask with a stress month in the sample."""
    return _put_harness(archive, claim="T-121", builder=front_ratio_trade, target=T121_DTE, min_n=T121_MIN_N,
                        desc="put front-ratio (long 1 40-delta put, short 2 20-delta puts)",
                        naked_desc="one 20-delta put (the other is covered by the long 40-delta put)")


def b6b_dolt_put_ladder(archive):
    """T-539: 45-DTE SPY long put ladder (long 40-delta, short 25- and 15-delta) held to expiry: positive mean P&L /
    naked-leg margin; pass lower 95% CI > 0 at bid/ask with a stress month in the sample."""
    return _put_harness(archive, claim="T-539", builder=ladder_trade, target=T539_DTE, min_n=T539_MIN_N,
                        desc="long put ladder (long 1 40-delta put, short 1 25-delta and 1 15-delta put)",
                        naked_desc="the 15-delta put (the 25-delta put is covered by the long 40-delta put)")


# ============================================================================================== T-173 ==

def overlay_values(t: dict, W: Optional[dict] = None) -> dict:
    """Overlay spread (1x2 minus single = short C5, long C10) P&L per unit of the entry spot at mid and exec, in $ at
    mid, and under the early-exercise sensitivity."""
    pay = payoff(t, t["s_t"])
    out = {f: (pay + net_credit(t, f)) / t["spot"] for f in FILLS}
    out["usd"] = pay + net_credit(t, "mid")
    if W is not None:
        pe = early_exercise_payoff(t, t["s_t"], W["divs"], W["days"], W["close_by"])
        out["early"] = (pe + net_credit(t, "mid")) / t["spot"]
    return out


def one_per_cohort(trades: Sequence[dict], target: int = T173_DTE) -> list:
    """Indices of the entry nearest ``target`` DTE in each cohort (ties to the longer-dated, i.e. the earlier entry)."""
    best = {}
    for i, t in enumerate(trades):
        key = (abs(t["dte"] - target), -t["dte"])
        if t["cohort"] not in best or key < best[t["cohort"]][0]:
            best[t["cohort"]] = (key, i)
    return sorted(i for _, i in best.values())


def b6b_dolt_ratio_overlay_skew(archive):
    """T-173: SPY 30-DTE 1x2 overlay minus the single 5%-OTM covered call, top minus bottom quartile of the entry-day
    5%-to-10% OTM call IV slope; pass 95% CI of the difference > 0; min_n 24 monthly expiry cohorts."""
    miss = _missing(archive, [CHAIN_B, SPY_B])
    if miss:
        return miss
    W = _world(archive)
    days = W["days"]
    monthly = monthly_expiries(int(days[0][:4]), int(days[-1][:4]) + 1) if days else set()
    head = (f"T-173 SPY overlay spread (1x2 overlay short 2 5%-OTM calls + long 1 10%-OTM call, minus the single 5%-OTM "
            f"covered call: the stock legs cancel, leaving short 1 call nearest 1.05 S, long 1 nearest 1.10 S, each within "
            f"{MONEY_TOL * 100:.0f}% of S) on the standard monthly expiry at {T173_DTE} +/- {DTE_TOL} DTE, every capture day "
            f"an entry (the trial's overlapping cohorts), mid fills, P&L per unit of the entry spot, settled on SPY's raw "
            f"close on the expiry date, early exercise ignored; signal = entry-day vendor call IV slope (IV at 1.10 S minus "
            f"IV at 1.05 S, linear in K/S, per unit moneyness); {_data_txt(W)}")
    trades, skips = build_trades(W["chain"], overlay_trade, monthly=monthly, target=T173_DTE, tol=DTE_TOL)
    trades, unres = resolve(trades, W["close_by"], W["last"])
    stat = {"claim": "T-173", "n_entries": len(trades), "skips": dict(skips + unres), "data": W["info"],
            "dte_tol": DTE_TOL, "money_tol": MONEY_TOL}
    n_coh = len({t["cohort"] for t in trades})
    if len(trades) < MIN_CLUSTERS or n_coh < MIN_CLUSTERS:
        return _too_few(stat, n_coh, T173_MIN_N, "monthly expiry cohorts", head)
    vals = [overlay_values(t, W) for t in trades]
    x = np.array([v["mid"] for v in vals])
    sig = np.array([t["signal"] for t in trades])
    core = quartile_claim(trades, x, sig, min_n=T173_MIN_N)
    crit = [(f"95% CI of the top-minus-bottom quartile difference > 0 (studentized block bootstrap over expiry cohorts, "
             f"robust over blocks of {'/'.join(str(b) for b in COHORT_BLOCKS)} cohorts)", core["ok"], core["decisive_fail"])]
    verdict, why = _decide(crit, core["n"], T173_MIN_N, "monthly expiry cohorts")
    # reported sensitivities
    xe = np.array([v["exec"] for v in vals])
    xu = np.array([v["usd"] for v in vals])
    xa = np.array([v["early"] for v in vals])
    q_exec = quartile_claim(trades, xe, sig, min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],))
    q_usd = quartile_claim(trades, xu, sig, min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],))
    q_early = quartile_claim(trades, xa, sig, min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],))
    pit = expanding_labels(trades, sig)
    q_pit = quartile_claim(trades, x, sig, min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],), labels=pit)
    one = one_per_cohort(trades)
    tr1 = [trades[i] for i in one]
    q_one = quartile_claim(tr1, x[one], sig[one], min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],))
    tol_sens = {}
    for tol in DTE_SENS:
        tr2, _ = build_trades(W["chain"], overlay_trade, monthly=monthly, target=T173_DTE, tol=tol)
        tr2, _ = resolve(tr2, W["close_by"], W["last"])
        if len({t["cohort"] for t in tr2}) < MIN_CLUSTERS:
            tol_sens[str(tol)] = {"n_cohorts": len({t["cohort"] for t in tr2}), "diff": None, "ci": [None, None]}
            continue
        q2 = quartile_claim(tr2, np.array([overlay_values(t)["mid"] for t in tr2]),
                            np.array([t["signal"] for t in tr2]), min_n=T173_MIN_N, blocks=(COHORT_BLOCKS[0],))
        tol_sens[str(tol)] = {"n_cohorts": q2["n"], "n_entries": q2["n_entries"], "diff": q2["diff"],
                              "ci": q2["rows"][0]["ci"]}
    keep = [i for i, t in enumerate(trades) if not t.get("late_stamp")]
    q_strict = quartile_claim([trades[i] for i in keep], x[keep], sig[keep], min_n=T173_MIN_N,
                              blocks=(COHORT_BLOCKS[0],)) if len(keep) >= MIN_CLUSTERS else None
    full_lab = (sig >= core["q3"], sig <= core["q1"])
    drop1 = drop_influential(trades, x, *full_lab, k=1)
    drop2 = drop_influential(trades, x, *full_lab, k=2)
    per_coh = defaultdict(list)
    for t in trades:
        per_coh[t["cohort"]].append(t)
    yrs = sorted({t["entry"][:4] for t in trades})
    by_year = {y: {"n_top": int(sum(1 for t, a in zip(trades, full_lab[0]) if a and t["entry"][:4] == y)),
                   "n_bottom": int(sum(1 for t, b in zip(trades, full_lab[1]) if b and t["entry"][:4] == y))} for y in yrs}
    parts = [f"{len(trades)} entries in {core['n']} monthly cohorts ({min(per_coh)}..{max(per_coh)}; "
             f"{min(len(v) for v in per_coh.values())}-{max(len(v) for v in per_coh.values())} entries per cohort)",
             f"slope quartiles Q1 {_s(core['q1'], 3)}, Q3 {_s(core['q3'], 3)} (vol per unit moneyness; median "
             f"{_s(float(np.median(sig)), 3)})",
             f"mid: {_qrows_txt(core)} -> CI > 0: {_ok_txt(core['ok'])}",
             f"unconditional mean spread {_s(float(x.mean()) * 100, 3)}% of S",
             f"fragility (reported): without the most favourable cohort ({', '.join(drop1['dropped'])}) difference "
             f"{_s(drop1['diff'] and drop1['diff'] * 100)}% of S ({_ci_s(drop1['ci'], 2, 100)}); without the two most "
             f"favourable ({', '.join(drop2['dropped'])}) {_s(drop2['diff'] and drop2['diff'] * 100)}% "
             f"({_ci_s(drop2['ci'], 2, 100)}); top/bottom entries by year "
             + ", ".join(f"{y} {v['n_top']}/{v['n_bottom']}" for y, v in by_year.items()),
             f"reported, not judged: executable (sell 5% at the bid, buy 10% at the ask) {_qrows_txt(q_exec)}; in $ "
             f"{_qrows_txt(q_usd, 1.0, ' $')}; early-exercise sensitivity (a call is exercised at a cum-dividend close "
             f"when the dividend exceeds its time value, BS put at the entry vendor IV, r = 0) {_qrows_txt(q_early)}; "
             f"point-in-time expanding quartiles (after {PIT_MIN_COHORTS} cohorts) {_qrows_txt(q_pit)}; one entry per "
             f"cohort (nearest {T173_DTE} DTE) {_qrows_txt(q_one)}; DTE window "
             + "; ".join(f"+/-{k}: {v['n_cohorts']} cohorts, difference {_s(v['diff'] and v['diff'] * 100)}% of S "
                         f"({_ci_s(v['ci'], 2, 100)})" for k, v in tol_sens.items())
             + f"; strict available_at (drops the {len(trades) - len(keep)} entries whose rows are stamped after the "
               f"entry close) " + (f"{q_strict['n']} cohorts, {_qrows_txt(q_strict)}" if q_strict else "too few entries"),
             f"skipped quote days: {_skips_txt(skips, unres)}; {NO_CONTROL}"]
    stat.update({"n_cohorts": core["n"], "quartile_test": core, "q1": core["q1"], "q3": core["q3"],
                 "diff_mid": core["diff"], "mean_spread_mid": float(x.mean()),
                 "sens_exec": q_exec, "sens_usd": q_usd, "sens_early_exercise": q_early, "sens_point_in_time": q_pit,
                 "sens_one_per_cohort": q_one, "drop_most_favourable_cohort": drop1,
                 "drop_two_most_favourable_cohorts": drop2, "quartile_entries_by_year": by_year,
                 "dte_window_sensitivity": tol_sens, "sens_strict_available_at": q_strict,
                 "first_cohort": min(per_coh), "last_cohort": max(per_coh), "controls": NO_CONTROL})
    return _out(stat, core["n"], verdict, head + ": " + "; ".join(parts) + " — " + why)


# ============================================================================================== registry ==

HARNESSES = {
    "b6b_dolt_backspread": b6b_dolt_backspread,
    "b6b_dolt_put_front_ratio": b6b_dolt_put_front_ratio,
    "b6b_dolt_ratio_overlay_skew": b6b_dolt_ratio_overlay_skew,
    "b6b_dolt_put_ladder": b6b_dolt_put_ladder,
}

THEORY_MAP = {
    "T-119": "b6b_dolt_backspread",
    "T-121": "b6b_dolt_put_front_ratio",
    "T-173": "b6b_dolt_ratio_overlay_skew",
    "T-539": "b6b_dolt_put_ladder",
}
