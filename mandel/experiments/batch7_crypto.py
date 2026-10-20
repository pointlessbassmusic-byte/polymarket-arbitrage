"""
Batch 7, group ``crypto``: three crypto salvage successors pre-registered on 2026-10-20 (SALVAGE-2026-10-20.md).
=====================================================================================================================

Each claim is tested exactly as worded, on its own trial.pass and trial.min_n (MANDEL.md section 2, rules 1-12). The
parents' in-sample numbers that motivated the successors are not evidence and are not reused as the test sample: T-546
runs on the Coinbase altcoin universe with BTC and ETH removed (T-419 used only those two), T-554 on ETH (T-41 used BTC),
T-556 on the Coinbase spot candles with next-open fills (the child's own study used Hyperliquid candles and signal-close
fills).

  * T-546  (successor of T-419) point-in-time top 50 Coinbase USD products by trailing 30-day dollar volume, built by
           T-424's ``batch6c_cryptovenue.cb_members`` unchanged (days D-30..D-1, listed = traded on D-1, dead products
           included) from every ``coinbase-daily-<PID>-USD`` bundle, with T-424's declared stablecoin and wrapped / staked
           base lists, the ``fx_stablecoin`` ids of the latest ``coinbase-products-<day>`` snapshot, and BTC and ETH
           excluded (the claim). Events 2019-01-01..data end on the UTC calendar-day grid: dollar volume DV = close x
           volume; surprise x = ln DV - mean(ln DV over the trailing 50 days, today excluded; >= 30 observed); the
           universe's mean surprise xbar_t = mean x over the day's members; idiosyncratic u = x - b x xbar with b the
           trailing-50-day OLS slope of x on xbar (T-419's ``_roll_slope``, today excluded, >= 30 pairs); an event is a
           member whose u is above the 90th percentile of u across that day's members (the claim's "top decile among
           names that day") with |r_t| < 2 sigma (close-to-close return, sigma over the trailing 50 days, T-419's rule).
           Entry at the next UTC daily close (close of t+1, which must be a traded bar), exit at the close of t+11 (the
           last close at or before it for a product that stops trading), market = the equal-weight mean of the same
           10-day return over the members of t+1 that traded at t+1; net = R - M - 50 bp. Pass: the date-clustered 95% CI
           of the mean net excludes 0 on the positive side (two-sided 95% lower end > 0) - judged under rule 11 / rule 6
           with the event date as cluster AND with 20-day calendar blocks (2 x the 10-day overlap), both must pass - AND
           the random-day placebo p < 0.05 (each event's name keeps its event count, days drawn at random from that
           name's eligible member days, 2,000 draws) AND both date halves (split at the midpoint of the event span)
           positive. min_n 300 events.
  * T-554  (successor of T-41) T-41's alignment unchanged (``social.fear_greed_forward_returns``' join: the index of day
           t (its observed_at day; available_at = 00:00 UTC t+1) -> log(close(t+1+7) / close(t+1)) on the sorted
           ``daily-history-ETH-USD`` closes, i.e. entry at the close of t+1), signal days 2018-02-01..2026-09-30.
           Statistic d = mean forward return after F >= 75 minus the unconditional mean of the same aligned sample.
           Block-shift p as in T-41 (the index series circularly shifted against the returns by k in [h+1, n-h-2]),
           enumerated over every admissible shift (T-41 drew 2,000 of them at random; the full enumeration is the same
           null without Monte Carlo error), one-sided in the claim's direction: p = (1 + #{null d >= d}) / (1 + shifts).
           Halves on T-41's index halves, read both ways (rule 1/11): greed mean minus that half's own mean (T-41's
           helper) and greed mean minus the claim's full-sample unconditional mean; the criterion passes only when both
           readings are positive in both halves and is undecided when they disagree.
           Pass: d > 0 AND p < 0.05 AND both halves > 0. min_n 150 greed days.
  * T-556  independent check of the sibling session's armed live rule (cryptobot/perp_bot.py on branch
           claude/crypto-arbitrage-volatility-bot-qic8gv, read only): features of the child's ``perp_study.daily_features``
           (move_1d = c_i / c_{i-1} - 1, move_3d = c_i / c_{i-3} - 1, from candle index 30 = WARMUP_DAYS), terciles of the
           child's ``research.quantiles`` (sorted values at int(n k / 3)) refitted every day on the POOLED feature rows of
           both coins dated before the signal candle (the live bot pools its coins), ``bucket_of`` (first k with value <
           cut_k), rule move_1d bucket 2 AND move_3d bucket 0; one trade per coin per 14 days measured from entry. Fills
           (the claim): short at the open of the next UTC day E; for bars E..E+13: stop when the high reaches entry x 1.10
           (filled at max(stop, open), so a gap through the stop fills at the open), checked first; else target when the
           low trades through entry x 0.80 (filled at the target, never a better gap price); else exit at the close of
           E+13 (14 x 24 h after the entry). Net = (1 - exit / entry) - 18 bp - funding 0.01% per 8 h for every day held
           (through the end of the exit day; 0.42% at the time exit), charged as a cost (the claim's "after"). Signal
           candles 2021..2026-09-30, trades complete within the data. The history-length rule is the claim's "at least
           120 days" (distinct days in the pooled history); the child's literal reading (120 pooled rows) is reported.
           Pass: the pooled 95% CI of the mean net per trade (studentized bootstrap with trades clustered by entry month,
           ``batch6c_pub.cluster_stud``; two-sided 95% lower end) > 0 AND the mean net of DOGE and of SHIB each > 0.
           min_n 60 trades. Reported next to it: the child's benchmark fills on the same signals (entry at the signal
           close, barrier fills exactly +0.1982 / -0.1018 after 18 bp, the child's ``perp_study.outcome``), per-coin
           cuts, funding received instead of paid, halves, exits, and the DSR at the child's 4,512-trial search as
           deflation context (not re-run, not a criterion).

Conventions
  * Data: every bundle through ``archive.load`` (``batch6c_cryptovenue._stream``: rows available after the bundle's
    capture are dropped); a missing required bundle is inconclusive and named (rule 9).
  * Point in time (rules 4, 12): T-546 membership uses days before the signal day, the surprise, slope, sigma and decile
    are known at the signal close, the entry is a later close; T-554 enters at the close of t+1, after the index's
    available_at; T-556 decides on a closed candle and fills at the next open, exits on bars at or after the entry.
  * Rule 5: below min_n the verdict is never supported and a failing criterion counts only when its bound at the pass's
    own confidence lies wholly on the wrong side.
  * Rule 10: all three are signal-driven (event days, index days, signal candles): no grid phase is free. T-554 reports
    the per-start range of the non-overlapping 7-day subsamples.
  Verdicts via ``underlying2._verdict`` through ``batch6b_bw._decide``; stat dicts are JSON-safe; n is in the claim's
  units (events; greed days; trades).
"""

from __future__ import annotations

import bisect
import math
from collections import Counter, defaultdict
from datetime import date
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import _ci_crit, _decide, _f, _pc, _s, all_constructions, mc_escalate, resolve
from mandel.experiments.batch6c_cryptovenue import (CB_PRODUCTS_PREFIX, T419_MIN_VWIN, T419_SIG, T419_VWIN, T424_RANK_DAYS,
                                                    T424_STABLE, T424_WRAPPED, _cb_daily_map, _dday, _has, _missing, _names,
                                                    _num, _out, _roll_slope, _stream, cb_members, cbd)
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.social import _day, daily_closes
from mandel.validation.backtest_eval import deflated_sharpe_ratio

N_BOOT = 2000
SEED = 0
ALPHA = 0.05


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _iso(o: int) -> str:
    return date.fromordinal(int(o)).isoformat()


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _ci_txt(ci, scale: float = 100.0, unit: str = "%", nd: int = 2) -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _boot(x, labels: Sequence, n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """Cluster studentized bootstrap of a mean over seeds, escalated when the two-sided 95% lower end cannot be resolved
    against 0."""
    x = np.asarray(x, float)
    nb = N_BOOT if n_boot is None else int(n_boot)
    if x.size < 4:
        return {"est": _mean(x), "ci": [None, None], "ci90": [None, None], "n": int(x.size)}
    labs = [str(v) for v in labels]
    return mc_escalate(lambda seed: cluster_stud(x, labs, nb, seed),
                       lambda t: resolve((t.get("ci") or [None])[0], (t.get("ci_mc_se") or [0.0])[0], 0.0, "gt")[0],
                       reps, SEED, keys=("ci", "ci90", "ci_pct"))


def _pfmt(v) -> str:
    return _pc(v, 2)


# ============================================================================ T-546 altcoin high-volume premium ==

T546_TOP = 50
T546_EXCLUDE = T424_STABLE | T424_WRAPPED | frozenset({"BTC", "ETH"})
T546_START, T546_END = "2019-01-01", "2026-12-31"
T546_GRID_FIRST = "2018-06-01"          # 50-day surprise and 50-day slope warm-ups before the first event day
T546_MEMBERS_FIRST = "2018-08-01"
T546_PCT = 0.90
T546_H = 10
T546_COST = 0.005
T546_MIN_N = 300
T546_BLOCK_DAYS = 20                    # rule 6: clusters at least as long as the overlap (2 x the 10-day hold)
T546_N_PLACEBO = 2000


def _roll2(X: np.ndarray, w: int) -> np.ndarray:
    """Row-wise rolling sum over columns t-w..t-1 (today excluded); NaN for t < w (``_roll(incl=False)`` in 2-D)."""
    P, T = X.shape
    c = np.concatenate([np.zeros((P, 1)), np.cumsum(X, axis=1)], axis=1)
    out = np.full((P, T), np.nan)
    if T > w:
        out[:, w:] = c[:, w:T] - c[:, :T - w]
    return out


def _ffill(X: np.ndarray) -> np.ndarray:
    P, T = X.shape
    idx = np.where(np.isfinite(X), np.arange(T)[None, :], 0)
    np.maximum.accumulate(idx, axis=1, out=idx)
    out = X[np.arange(P)[:, None], idx]
    out[~np.isfinite(X[np.arange(P)[:, None], idx])] = np.nan
    return out


def alt_panel(daily: dict, members: dict, first: str, last: str) -> dict:
    """{'days', 'pids', 'C' (closes, NaN = no bar), 'V' (base volume), 'Mb' (member mask)} on the calendar grid."""
    o0, o1 = _ord(first), _ord(last)
    T = o1 - o0 + 1
    pids = sorted({p for ms in members.values() for p in ms})
    C = np.full((len(pids), T), np.nan)
    V = np.full((len(pids), T), np.nan)
    for i, p in enumerate(pids):
        for d, (c, v) in daily.get(p, {}).items():
            o = _ord(d) - o0
            if 0 <= o < T and c is not None and c > 0 and v is not None and v >= 0:
                C[i, o] = c
                V[i, o] = v
    pos = {p: i for i, p in enumerate(pids)}
    Mb = np.zeros((len(pids), T), bool)
    for d, ms in members.items():
        o = _ord(d) - o0
        if 0 <= o < T:
            for p in ms:
                Mb[pos[p], o] = True
    return {"days": [_iso(o0 + k) for k in range(T)], "pids": pids, "C": C, "V": V, "Mb": Mb}


def alt_hvp_signals(panel: dict, start: str = T546_START, end: str = T546_END, pct: float = T546_PCT, H: int = T546_H,
                    cost: float = T546_COST) -> dict:
    """Event mask and the per-(name, day) net market-adjusted forward return on every member day (NaN where the forward
    window is incomplete)."""
    days, C, V, Mb = panel["days"], panel["C"], panel["V"], panel["Mb"]
    P, T = C.shape
    with np.errstate(all="ignore"):
        DV = C * V
        lDV = np.where(DV > 0, np.log(DV), np.nan)
    fin = np.isfinite(lDV)
    cnt = _roll2(fin.astype(float), T419_VWIN)
    with np.errstate(all="ignore"):
        mean_l = _roll2(np.where(fin, lDV, 0.0), T419_VWIN) / cnt
        x = lDV - mean_l
    x[~(cnt >= T419_MIN_VWIN)] = np.nan
    xm = np.where(Mb & np.isfinite(x), x, np.nan)
    with np.errstate(all="ignore"):
        k = np.isfinite(xm).sum(axis=0)
        xbar = np.where(k > 0, np.nansum(xm, axis=0) / np.maximum(k, 1), np.nan)
    u = np.full((P, T), np.nan)
    for i in range(P):
        b = _roll_slope(x[i], xbar, T419_VWIN, T419_MIN_VWIN, incl=False)
        u[i] = x[i] - b * xbar
    r = np.full((P, T), np.nan)
    with np.errstate(all="ignore"):
        r[:, 1:] = C[:, 1:] / C[:, :-1] - 1.0
    rf = np.isfinite(r)
    rc = _roll2(rf.astype(float), T419_VWIN)
    r0 = np.where(rf, r, 0.0)
    with np.errstate(all="ignore"):
        mu = _roll2(r0, T419_VWIN) / rc
        s2 = (_roll2(r0 * r0, T419_VWIN) - rc * mu * mu) / (rc - 1)
    sig = np.sqrt(np.maximum(s2, 0.0))
    sig[~(rc >= T419_MIN_VWIN)] = np.nan
    Cf = _ffill(C)
    R = np.full((P, T), np.nan)
    with np.errstate(all="ignore"):
        R[:, :T - H - 1] = Cf[:, H + 1:] / C[:, 1:T - H] - 1.0       # entry close t+1 (a traded bar), exit close t+1+H
    M = np.full(T, np.nan)
    Mb_next = np.zeros_like(Mb)
    Mb_next[:, :-1] = Mb[:, 1:]
    with np.errstate(all="ignore"):
        ok = Mb_next & np.isfinite(R)
        kk = ok.sum(axis=0)
        M = np.where(kk > 0, np.where(ok, R, 0.0).sum(axis=0) / np.maximum(kk, 1), np.nan)
    net = R - M[None, :] - cost
    win = np.array([start <= d <= end for d in days], bool)
    elig = Mb & np.isfinite(net) & win[None, :]
    ev = np.zeros((P, T), bool)
    for t in np.flatnonzero(win):
        cand = Mb[:, t] & np.isfinite(u[:, t])
        if cand.sum() < 2:
            continue
        q = float(np.quantile(u[cand, t], pct))
        with np.errstate(invalid="ignore"):
            ev[:, t] = cand & (u[:, t] > q) & np.isfinite(sig[:, t]) & np.isfinite(r[:, t]) & (np.abs(r[:, t]) < T419_SIG * sig[:, t])
    n_top = int(ev.sum())
    ev &= elig
    return {"ev": ev, "elig": elig, "net": net, "R": R, "M": M, "n_flagged": n_top, "days": days, "pids": panel["pids"]}


def placebo_random_days(net: np.ndarray, ev: np.ndarray, elig: np.ndarray, obs: float, n_draw: int = T546_N_PLACEBO,
                        seed: int = SEED) -> dict:
    """Each name keeps its event count; its event days are replaced by days drawn at random (with replacement) from its
    eligible member days; p = (1 + #{placebo mean >= observed}) / (1 + draws)."""
    rng = np.random.default_rng(seed)
    tot = np.zeros(n_draw)
    n = 0
    for i in range(net.shape[0]):
        k = int(ev[i].sum())
        if not k:
            continue
        pool = net[i, elig[i]]
        idx = rng.integers(0, pool.size, (n_draw, k))
        tot += pool[idx].sum(axis=1)
        n += k
    if not n:
        return {"p": None, "n_draw": 0}
    m = tot / n
    p = float((1 + np.sum(m >= obs)) / (1 + n_draw))
    return {"p": p, "p_mc_se": math.sqrt(p * (1 - p) / n_draw), "n_draw": n_draw, "null_mean": float(m.mean()),
            "null_q95": float(np.quantile(m, 0.95))}


def alt_hvp_test(sig: dict, min_n: int = T546_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None,
                 n_draw: int = T546_N_PLACEBO) -> dict:
    ev, net, days, pids = sig["ev"], sig["net"], sig["days"], sig["pids"]
    ii, tt = np.nonzero(ev)
    x = net[ii, tt]
    n = int(x.size)
    ed = [days[t] for t in tt]
    m0 = _mean(x)
    b_date = _boot(x, ed, n_boot, reps)
    b_blk = _boot(x, [_ord(d) // T546_BLOCK_DAYS for d in ed], n_boot, reps)
    c_date = _ci_crit(b_date, "gt", 0.0, "event-date clusters", _pfmt)
    c_blk = _ci_crit(b_blk, "gt", 0.0, f"{T546_BLOCK_DAYS}-day calendar blocks", _pfmt)
    c_ci = all_constructions([c_date, c_blk], f"date-clustered 95% CI of the mean net 10-day market-adjusted return "
                                              f"{_pfmt(m0)} excludes 0 on the positive side")
    plc = placebo_random_days(net, ev, sig["elig"], m0, n_draw) if n else {"p": None}
    pok, pnote = resolve(plc.get("p"), plc.get("p_mc_se"), ALPHA, "lt") if plc.get("p") is not None else (None, "")
    c_p = (f"random-day placebo p {_f(plc.get('p'), 4)}{pnote} < {ALPHA} ({plc.get('n_draw')} draws)", pok, False)
    halves = None
    c_h = ("both date halves positive (n/a)", None, False)
    if n >= 4:
        lo, hi = min(ed), max(ed)
        mid = _iso((_ord(lo) + _ord(hi)) // 2)
        ea = np.array(ed)
        h1, h2 = x[ea < mid], x[ea >= mid]
        halves = {"split": mid, "first": {"n": int(h1.size), "mean": _mean(h1)}, "second": {"n": int(h2.size), "mean": _mean(h2)}}
        m1, m2 = halves["first"]["mean"], halves["second"]["mean"]
        c_h = (f"both date halves positive (split {mid}: {_pfmt(m1)} over {h1.size}, {_pfmt(m2)} over {h2.size})",
               None if (m1 is None or m2 is None) else bool(m1 > 0 and m2 > 0), False)
    crit = [c_ci, c_p, c_h]
    v, why = _decide(crit, n, min_n, "events")
    by_year = defaultdict(list)
    for d, val in zip(ed, x):
        by_year[d[:4]].append(val)
    gross = sig["R"][ii, tt] - sig["M"][tt]
    per_name = Counter(pids[i] for i in ii)
    return {"n": n, "mean_net": m0, "mean_gross_adj": _mean(gross), "mean_raw_10d": _mean(sig["R"][ii, tt]),
            "boot_date": {k: b_date.get(k) for k in ("est", "ci", "ci_mc_se", "clusters", "reps")},
            "boot_block": {k: b_blk.get(k) for k in ("est", "ci", "ci_mc_se", "clusters", "reps")},
            "placebo": plc, "halves": halves, "by_year": {y: {"n": len(v_), "mean": float(np.mean(v_))} for y, v_ in sorted(by_year.items())},
            "names_with_events": len(per_name), "top_names": per_name.most_common(10), "n_flagged_before_window": sig["n_flagged"],
            "first_event": min(ed) if n else None, "last_event": max(ed) if n else None,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b7_crypto_alt_high_volume_premium(archive):
    """T-546: top-decile idiosyncratic dollar-volume day without a 2-sigma move on the point-in-time top-50 Coinbase alt
    universe -> positive 10-day market-adjusted return after 50 bp."""
    prods = _names(archive, CB_PRODUCTS_PREFIX)
    daily_names = [nm for nm in _names(archive, "coinbase-daily-") if nm.endswith("-USD")]
    need = ([] if prods else ["coinbase-products-<day>"]) + ([] if daily_names else ["coinbase-daily-<PID>"])
    miss = _missing(archive, need)
    if miss:
        return miss
    stable_ids = set()
    for r in _stream(archive, prods[-1]):
        v = r.get("value") or {}
        if v.get("fx_stablecoin") and v.get("id"):
            stable_ids.add(v["id"])
    daily = {}
    for nm in daily_names:
        pid = nm[len("coinbase-daily-"):]
        if pid.split("-")[0] in T546_EXCLUDE or pid in stable_ids:
            continue
        daily[pid] = _cb_daily_map(archive, pid)
    last = max((max(m) for m in daily.values() if m), default=None)
    if last is None:
        v, why = _decide([("Coinbase daily candles available", None)], 0, T546_MIN_N, "events")
        return _out({"n_events": 0}, 0, v, "no Coinbase USD daily candles after exclusions — " + why)
    members = cb_members(daily, T546_MEMBERS_FIRST, last, exclude=T546_EXCLUDE, top=T546_TOP, window=T424_RANK_DAYS,
                         stable_ids=frozenset(stable_ids))
    panel = alt_panel(daily, members, T546_GRID_FIRST, last)
    sig = alt_hvp_signals(panel)
    j = alt_hvp_test(sig)
    sizes = [len(ms) for d, ms in members.items() if d >= T546_START]
    bd, bb, pl, hv = j["boot_date"], j["boot_block"], j["placebo"], j["halves"]
    reason = (f"{len(daily_names)} coinbase-daily USD bundles, {len(daily)} after excluding BTC, ETH, {len(T424_STABLE)} "
              f"stablecoin and {len(T424_WRAPPED) - 1} wrapped/staked bases and {len(stable_ids)} fx_stablecoin ids; point-in-time "
              f"top {T546_TOP} by trailing {T424_RANK_DAYS}-day dollar volume, mean size {_f(float(np.mean(sizes)) if sizes else None, 1)}, "
              f"{len(panel['pids'])} products ever members; events {j['first_event']}..{j['last_event']}: {j['n']} over "
              f"{j['names_with_events']} names; mean net 10-day market-adjusted return {_pfmt(j['mean_net'])} (before the 50 bp: "
              f"{_pfmt(j['mean_gross_adj'])}; raw 10-day {_pfmt(j['mean_raw_10d'])}); 95% CI event-date clusters "
              f"{_ci_txt(bd.get('ci'))} ({bd.get('clusters')} dates), 20-day blocks {_ci_txt(bb.get('ci'))}; placebo p "
              f"{_f(pl.get('p'), 4)} (null mean {_pfmt(pl.get('null_mean'))}); date halves "
              + (f"(split {hv['split']}) {_pfmt(hv['first']['mean'])} over {hv['first']['n']} / {_pfmt(hv['second']['mean'])} over "
                 f"{hv['second']['n']}" if hv else "n/a")
              + "; by year " + ", ".join(f"{y} {_pfmt(v_['mean'])} ({v_['n']})" for y, v_ in j["by_year"].items())
              + " — " + j["why"])
    stat = {"n_events": j["n"], "mean_net": j["mean_net"], "mean_gross_adj": j["mean_gross_adj"], "mean_raw_10d": j["mean_raw_10d"],
            "boot_date": bd, "boot_block": bb, "placebo": pl, "halves": hv, "by_year": j["by_year"],
            "names_with_events": j["names_with_events"], "top_names": j["top_names"], "universe_ever": len(panel["pids"]),
            "mean_universe_size": float(np.mean(sizes)) if sizes else None, "fx_stablecoin_ids": sorted(stable_ids),
            "excluded_bases": sorted(T546_EXCLUDE), "first_event": j["first_event"], "last_event": j["last_event"],
            "criteria": j["criteria"], "cost_round_trip": T546_COST,
            "rule10": "signal-driven events: no grid phase", "rule6": f"event-date clusters and {T546_BLOCK_DAYS}-day blocks both required"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================= T-554 ETH greed momentum ==

FNG_B = "crypto-fear-greed-history"
ETH_Y = "daily-history-ETH-USD"
T554_START, T554_END = "2018-02-01", "2026-09-30"
T554_HIGH = 75
T554_H = 7
T554_LAG = 1
T554_MIN_N = 150
T554_MIN_HALF = 5


def greed_align(fng: dict, closes: dict, start: str = T554_START, end: str = T554_END, h: int = T554_H, lag: int = T554_LAG) -> tuple:
    """T-41's join: index of day d -> log(close(days[i + lag + h]) / close(days[i + lag])) on the sorted close days."""
    days = sorted(closes)
    idx = {d: i for i, d in enumerate(days)}
    f, fwd, dd = [], [], []
    for d, val in sorted(fng.items()):
        if not (start <= d <= end):
            continue
        i = idx.get(d)
        if i is None or i + lag < 0 or i + lag + h >= len(days):
            continue
        c0, c1 = closes[days[i + lag]], closes[days[i + lag + h]]
        if c0 > 0 and c1 > 0:
            f.append(float(val)); fwd.append(math.log(c1 / c0)); dd.append(d)
    return np.array(f, float), np.array(fwd, float), dd


def greed_test(f: np.ndarray, fwd: np.ndarray, dd: Sequence[str], high: float = T554_HIGH, h: int = T554_H,
               min_n: int = T554_MIN_N) -> dict:
    n = int(f.size)
    g = f >= high
    ng = int(g.sum())
    out = {"n_aligned": n, "n_greed": ng}
    if n < 2 * h + 4 or ng == 0:
        v, why = _decide([("difference > 0 with block-shift p < 0.05 and both halves positive", None)], ng, min_n, "greed days")
        out.update(verdict=v, why=why, criteria=[], d=None, p=None, halves=[None, None])
        return out
    mu = float(fwd.mean())
    d = float(fwd[g].mean() - mu)
    ks = np.arange(h + 1, n - h - 1)
    gi = np.flatnonzero(g)
    null = np.array([fwd[(gi + k) % n].mean() for k in ks]) - mu  # the index (greed days) rolled k days against returns
    p = float((1 + np.sum(null >= d - 1e-15)) / (1 + ks.size))
    half = n // 2

    def _d(lo, hi, base=None):
        sub, m = fwd[lo:hi], g[lo:hi]
        if m.sum() < T554_MIN_HALF:
            return None
        return float(sub[m].mean() - (sub.mean() if base is None else base))
    hv = [_d(0, half), _d(half, n)]                                # T-41's helper: each half's own mean
    hv_full = [_d(0, half, mu), _d(half, n, mu)]                   # the claim's statistic: the full-sample unconditional mean
    # rule 1/11: the claim's "unconditional 7-day mean" is one full-sample number; T-41's per-half mean is a permitted
    # alternative reading. The criterion passes only when both readings agree on both halves, else it is undecided.
    if any(v_ is None for v_ in hv + hv_full):
        h_ok = None
    else:
        r_own, r_full = bool(hv[0] > 0 and hv[1] > 0), bool(hv_full[0] > 0 and hv_full[1] > 0)
        h_ok = r_own if r_own == r_full else None
    split = dd[half] if half < len(dd) else "n/a"
    c_d = (f"mean 7-day ETH log return after F >= {high:g} minus the unconditional mean {_s(d, 4)} > 0", d > 0, False)
    c_p = (f"block-shift p {_f(p, 4)} < {ALPHA} ({ks.size} circular shifts, one-sided)", p < ALPHA, False)
    c_h = (f"both halves positive under both readings (vs each half's own mean {_s(hv[0], 4)} / {_s(hv[1], 4)}; vs the "
           f"full-sample unconditional mean {_s(mu, 4)}: {_s(hv_full[0], 4)} / {_s(hv_full[1], 4)}; split {split}"
           + ("; the readings disagree, undecided" if h_ok is None and None not in hv + hv_full else "") + ")",
           h_ok, False)
    crit = [c_d, c_p, c_h]
    v, why = _decide(crit, ng, min_n, "greed days")
    phases = []
    for s0 in range(h):                                            # rule 10 report: non-overlapping 7-day subsamples
        sel = np.arange(s0, n, h)
        gs = g[sel]
        if gs.sum() >= T554_MIN_HALF:
            phases.append(float(fwd[sel][gs].mean() - fwd[sel].mean()))
    out.update(d=d, mean_greed=float(fwd[g].mean()), mean_all=mu, p=p, n_shifts=int(ks.size), null_q95=float(np.quantile(null, 0.95)),
               halves=hv, halves_vs_full_mean=hv_full, split=dd[half] if half < len(dd) else None, per_start=phases, criteria=[(c[0], c[1]) for c in crit],
               verdict=v, why=why, first=dd[0], last=dd[-1])
    return out


def b7_crypto_eth_greed_momentum(archive):
    """T-554: ETH's forward 7-day log return after Fear & Greed >= 75 exceeds its unconditional mean, both halves positive."""
    miss = _missing(archive, [FNG_B, ETH_Y])
    if miss:
        return miss
    fng = {}
    for r in _stream(archive, FNG_B):
        x = _num((r.get("value") or {}).get("value"))
        if x is not None and r.get("observed_at"):
            fng[_day(r["observed_at"])] = x
    closes = daily_closes(_stream(archive, ETH_Y)).get("ETH-USD", {})
    f, fwd, dd = greed_align(fng, closes)
    j = greed_test(f, fwd, dd)
    if j.get("d") is None:
        return _out(j, j["n_greed"], j["verdict"], f"{j['n_aligned']} aligned days, {j['n_greed']} greed days — {j['why']}")
    ps = j["per_start"]
    reason = (f"crypto-fear-greed-history x daily-history-ETH-USD, signal days {j['first']}..{j['last']} ({j['n_aligned']} "
              f"aligned; F of day t known 00:00 UTC t+1, entry close t+1, exit close t+8): {j['n_greed']} days with F >= "
              f"{T554_HIGH}; mean 7-day log return after greed {_s(j['mean_greed'], 4)} vs unconditional {_s(j['mean_all'], 4)}, "
              f"difference {_s(j['d'], 4)}; block-shift p {_f(j['p'], 4)} over {j['n_shifts']} shifts (null 95th percentile "
              f"{_s(j['null_q95'], 4)}); halves vs each half's own mean {_s(j['halves'][0], 4)} / {_s(j['halves'][1], 4)}, vs the "
              f"full-sample unconditional mean {_s(j['halves_vs_full_mean'][0], 4)} / {_s(j['halves_vs_full_mean'][1], 4)} "
              f"(split {j['split']}); "
              f"non-overlapping per-start range {_s(min(ps) if ps else None, 4)} to {_s(max(ps) if ps else None, 4)} over "
              f"{len(ps)} starts — " + j["why"])
    stat = {k: j.get(k) for k in ("n_aligned", "n_greed", "d", "mean_greed", "mean_all", "p", "n_shifts", "null_q95", "halves",
                                  "halves_vs_full_mean", "split", "per_start", "first", "last", "criteria")}
    stat.update(rule10="index days, overlapping windows handled by the block shift; per-start range reported",
                alignment="T-41 lag_days=1: entry close(t+1), F(t) available 00:00 UTC t+1")
    return _out(stat, j["n_greed"], j["verdict"], reason)


# ============================================================================ T-556 memecoin bounce short check ==

T556_COINS = ("DOGE-USD", "SHIB-USD")
T556_WARMUP = 30                       # cryptobot.perp_study.WARMUP_DAYS
T556_MIN_HIST = 120                    # PerpBotConfig.min_history_days
T556_TARGET, T556_STOP = 0.20, 0.10
T556_HOLD = 14
T556_COST = 0.0018
T556_FUND_DAY = 0.0001 * 3             # 0.01% per 8 hours
T556_FIRST_SIGNAL, T556_LAST_SIGNAL = "2021-01-01", "2026-09-30"
T556_MIN_N = 60
T556_CHILD_TRIALS = 4512


def _ohlc(archive, name: str) -> dict:
    by = {}
    for r in _stream(archive, name):
        v = r.get("value") or {}
        xs = [_num(v.get(k)) for k in ("open", "high", "low", "close")]
        if v.get("t") is not None and all(x is not None and x > 0 for x in xs):
            by[_dday(v["t"])] = xs
    days = sorted(by)
    A = np.array([by[d] for d in days], float).reshape(-1, 4)
    return {"days": days, "open": A[:, 0], "high": A[:, 1], "low": A[:, 2], "close": A[:, 3]}


def child_quantiles(vals_sorted: Sequence[float], n: int = 3) -> list:
    """cryptobot.research.quantiles on an already-sorted list."""
    m = len(vals_sorted)
    return [vals_sorted[int(m * k / n)] for k in range(1, n)]


def child_bucket(value: float, cuts: Sequence[float]) -> int:
    """cryptobot.research.bucket_of."""
    return next((k for k, c in enumerate(cuts) if value < c), len(cuts))


def child_features(bars: dict, warmup: int = T556_WARMUP) -> list:
    """(day, index, move_1d, move_3d) for candle indices >= warmup (cryptobot.perp_study.daily_features)."""
    c = bars["close"]
    out = []
    for i in range(warmup, len(c)):
        m1 = c[i] / c[i - 1] - 1.0 if c[i - 1] > 0 else 0.0
        m3 = c[i] / c[i - 3] - 1.0 if c[i - 3] > 0 else 0.0
        out.append((bars["days"][i], i, float(m1), float(m3)))
    return out


def child_signals(coins: dict, min_hist: int = T556_MIN_HIST, hist_mode: str = "days", pooled: bool = True) -> list:
    """[(coin, signal day, candle index)] where the child's rule fires: terciles refitted on every feature row dated
    before the signal day (pooled over the coins, or per coin), history of at least ``min_hist`` distinct days
    ('days', the claim) or pooled rows ('rows', the child's literal len(rows_hist) check)."""
    feats = {k: child_features(b) for k, b in coins.items()}
    by_day = defaultdict(list)
    for k, fs in feats.items():
        for row in fs:
            by_day[row[0]].append((k, row))
    groups = [None] if pooled else list(coins)
    sig = []
    for grp in groups:
        s1, s3, hist_days, n_rows = [], [], set(), 0
        for d in sorted(by_day):
            todays = [(k, row) for k, row in by_day[d] if grp is None or k == grp]
            enough = (len(hist_days) if hist_mode == "days" else n_rows) >= min_hist
            if enough and s1:
                c1, c3 = child_quantiles(s1), child_quantiles(s3)
                for k, (_, i, m1, m3) in todays:
                    if child_bucket(m1, c1) == 2 and child_bucket(m3, c3) == 0:
                        sig.append((k, d, i))
            for k, (_, i, m1, m3) in todays:
                bisect.insort(s1, m1)
                bisect.insort(s3, m3)
                n_rows += 1
            if todays:
                hist_days.add(d)
    return sorted(sig, key=lambda s: (s[1], s[0]))


def short_trades(coins: dict, signals: Sequence[tuple], first: str = T556_FIRST_SIGNAL, last: str = T556_LAST_SIGNAL,
                 hold: int = T556_HOLD, cost: float = T556_COST, fund_day: float = T556_FUND_DAY) -> list:
    """The claim's fills: short at the open of the next UTC day, stop (high >= entry x 1.10, fill max(stop, open)) before
    target (low < entry x 0.80, fill at the target) on bars E..E+13, else the close of E+13; one trade per coin per
    ``hold`` days from entry. Also the child's benchmark on the same signal: entry at the signal close, bars i+1..i+14,
    -stop / +target exactly, else the move to close i+14 (perp_study.outcome), minus ``cost``."""
    trades, next_ok = [], {}
    for coin, d, i in signals:
        if not (first <= d <= last):
            continue
        b = coins[coin]
        days, O, Hh, L, C = b["days"], b["open"], b["high"], b["low"], b["close"]
        e_ord = _ord(d) + 1
        if e_ord < next_ok.get(coin, -1):
            continue
        j = bisect.bisect_left(days, _iso(e_ord))
        if j >= len(days) or days[j] != _iso(e_ord):
            continue                                       # no next-day bar to enter on
        last_ord = e_ord + hold - 1
        if _ord(days[-1]) < last_ord:
            continue                                       # incomplete: the hold runs past the data
        entry = O[j]
        stop, tgt = entry * (1 + T556_STOP), entry * (1 - T556_TARGET)
        exit_px, why, k = None, "time", j
        while k < len(days) and _ord(days[k]) <= last_ord:
            if Hh[k] >= stop:
                exit_px, why = max(stop, O[k]), "stop"
                break
            if L[k] < tgt:
                exit_px, why = tgt, "target"
                break
            k += 1
        if exit_px is None:
            k = bisect.bisect_right(days, _iso(last_ord)) - 1
            exit_px = C[k]
        held = _ord(days[k]) - e_ord + 1
        gross = 1.0 - exit_px / entry
        fund = fund_day * held
        # the child's benchmark (perp_study.outcome, short side) on the same signal
        bentry = C[i]
        bstop, btgt = bentry * (1 + T556_STOP), bentry * (1 - T556_TARGET)
        bres, blast = None, min(i + hold, len(C) - 1)
        for q in range(i + 1, blast + 1):
            if Hh[q] >= bstop:
                bres = -T556_STOP
                break
            if L[q] <= btgt:
                bres = T556_TARGET
                break
        if bres is None:
            bres = -(C[blast] / bentry - 1.0)
        trades.append({"coin": coin, "signal": d, "entry_day": _iso(e_ord), "exit_day": days[k], "entry": float(entry),
                       "exit": float(exit_px), "why": why, "held_days": int(held), "gross": float(gross),
                       "net": float(gross - cost - fund), "net_funding_received": float(gross - cost + fund),
                       "bench_net": float(bres - cost)})
        next_ok[coin] = e_ord + hold
    return trades


def bounce_test(trades: Sequence[dict], coins: Sequence[str] = T556_COINS, min_n: int = T556_MIN_N, n_boot: Optional[int] = None,
                reps: Optional[int] = None) -> dict:
    n = len(trades)
    x = np.array([t["net"] for t in trades], float)
    months = [t["entry_day"][:7] for t in trades]
    bt = _boot(x, months, n_boot, reps)
    c_ci = _ci_crit(bt, "gt", 0.0, f"pooled 95% CI of the mean net per trade {_pfmt(_mean(x))} excludes 0 on the positive side "
                                   f"(month-clustered studentized bootstrap)", _pfmt)
    coarse = {}                                                    # reporting only: the pass's dependence on cluster width
    for lab, key in (("two_month", lambda m: f"{m[:4]}-B{(int(m[5:7]) - 1) // 2}"),
                     ("quarter", lambda m: f"{m[:4]}-Q{(int(m[5:7]) - 1) // 3}")):
        bc = _boot(x, [key(m) for m in months], n_boot, reps)
        coarse[lab] = {"ci": bc.get("ci"), "clusters": bc.get("clusters"),
                       "lower": (bc.get("ci") or [None])[0]}
    per = {}
    crit = [c_ci]
    for cn in coins:
        xs = np.array([t["net"] for t in trades if t["coin"] == cn], float)
        ms = [t["entry_day"][:7] for t in trades if t["coin"] == cn]
        b = _boot(xs, ms, n_boot, reps) if xs.size >= 4 else {"est": _mean(xs), "ci": [None, None]}
        per[cn] = {"n": int(xs.size), "mean": _mean(xs), "ci": b.get("ci"), "bench_mean": _mean([t["bench_net"] for t in trades if t["coin"] == cn])}
        hi = (b.get("ci") or [None, None])[1]
        crit.append((f"{cn} mean net {_pfmt(per[cn]['mean'])} > 0 ({xs.size} trades)",
                     None if per[cn]["mean"] is None else bool(per[cn]["mean"] > 0), hi is not None and hi < 0))
    v, why = _decide(crit, n, min_n, "trades")
    halves = None
    if n >= 4:
        ed = [t["entry_day"] for t in trades]
        mid = _iso((_ord(min(ed)) + _ord(max(ed))) // 2)
        a1 = [t["net"] for t in trades if t["entry_day"] < mid]
        a2 = [t["net"] for t in trades if t["entry_day"] >= mid]
        halves = {"split": mid, "first": {"n": len(a1), "mean": _mean(a1)}, "second": {"n": len(a2), "mean": _mean(a2)}}
    bench = np.array([t["bench_net"] for t in trades], float)
    at_bar = {"+0.1982": int(np.sum(np.isclose(bench, T556_TARGET - T556_COST))),
              "-0.1018": int(np.sum(np.isclose(bench, -T556_STOP - T556_COST)))}
    dsr = None
    if n >= 10 and x.std() > 0:
        dsr = float(deflated_sharpe_ratio(x, T556_CHILD_TRIALS))
    return {"n": n, "mean_net": _mean(x), "mean_gross": _mean([t["gross"] for t in trades]),
            "mean_net_funding_received": _mean([t["net_funding_received"] for t in trades]),
            "boot": {k: bt.get(k) for k in ("est", "ci", "ci_mc_se", "clusters", "reps")}, "boot_coarse": coarse, "per_coin": per, "halves": halves,
            "bench_mean": _mean(bench), "bench_at_barriers": at_bar, "exits": dict(Counter(t["why"] for t in trades)),
            "dsr_child_trials": dsr, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b7_crypto_memecoin_bounce_short(archive):
    """T-556: the child's bounce-short rule on Coinbase DOGE-USD / SHIB-USD, next-open entry, conservative later-bar exits."""
    need = [cbd(c) for c in T556_COINS]
    miss = _missing(archive, need)
    if miss:
        return miss
    coins = {c: _ohlc(archive, cbd(c)) for c in T556_COINS}
    sig = child_signals(coins)
    trades = short_trades(coins, sig)
    j = bounce_test(trades)
    alt = {}
    for label, kw in (("child_rows_120", {"hist_mode": "rows"}), ("per_coin_cuts", {"pooled": False})):
        tr = short_trades(coins, child_signals(coins, **kw))
        alt[label] = {"n": len(tr), "mean_net": _mean([t["net"] for t in tr]), "bench_mean": _mean([t["bench_net"] for t in tr])}
    pc, bt, hv = j["per_coin"], j["boot"], j["halves"]
    reason = (f"Coinbase daily {', '.join(f'{c} {coins[c]['days'][0]}..{coins[c]['days'][-1]}' for c in T556_COINS)}; "
              f"{len(sig)} rule firings (pooled expanding terciles, >= {T556_MIN_HIST} days of history), {j['n']} trades with "
              f"signal candles {T556_FIRST_SIGNAL[:4]}..{T556_LAST_SIGNAL} after the 14-day re-entry rule; next-open short, "
              f"stop-first later-bar exits: mean gross {_pfmt(j['mean_gross'])}, mean net {_pfmt(j['mean_net'])} after 18 bp and "
              f"0.01%/8h funding paid (funding received instead: {_pfmt(j['mean_net_funding_received'])}); month-clustered 95% "
              f"{_ci_txt(bt.get('ci'))} ({bt.get('clusters')} months; the trial's cluster, a pass that depends on the width: "
              f"two-month clusters lower end {_pfmt(j['boot_coarse']['two_month']['lower'])} "
              f"({j['boot_coarse']['two_month']['clusters']} clusters), quarterly "
              f"{_pfmt(j['boot_coarse']['quarter']['lower'])} ({j['boot_coarse']['quarter']['clusters']} clusters), "
              f"reported not criteria); "
              + "; ".join(f"{c} {pc[c]['n']} trades {_pfmt(pc[c]['mean'])} ({_ci_txt(pc[c]['ci'])})" for c in T556_COINS)
              + f"; exits {j['exits']}; halves "
              + (f"(split {hv['split']}) {_pfmt(hv['first']['mean'])} over {hv['first']['n']} / {_pfmt(hv['second']['mean'])} over "
                 f"{hv['second']['n']}" if hv else "n/a")
              + f"; the child's benchmark fills on the same signals (signal-close entry, barrier fills) mean "
              f"{_pfmt(j['bench_mean'])} per trade, {j['bench_at_barriers']['+0.1982']} at exactly +0.1982 and "
              f"{j['bench_at_barriers']['-0.1018']} at exactly -0.1018; the child's literal 120-row history "
              f"{alt['child_rows_120']['n']} trades {_pfmt(alt['child_rows_120']['mean_net'])}, per-coin cuts "
              f"{alt['per_coin_cuts']['n']} trades {_pfmt(alt['per_coin_cuts']['mean_net'])}; DSR at the child's "
              f"{T556_CHILD_TRIALS}-trial search {_f(j['dsr_child_trials'])} (context, not a criterion) — " + j["why"])
    stat = {"n_trades": j["n"], "n_firings": len(sig), "mean_net": j["mean_net"], "mean_gross": j["mean_gross"],
            "mean_net_funding_received": j["mean_net_funding_received"], "boot": bt, "boot_coarse": j["boot_coarse"],
            "per_coin": pc, "halves": hv,
            "exits": j["exits"], "bench_mean": j["bench_mean"], "bench_at_barriers": j["bench_at_barriers"],
            "sensitivity": alt, "dsr_child_trials": j["dsr_child_trials"], "child_trials": T556_CHILD_TRIALS,
            "criteria": j["criteria"], "trades": [{k: t[k] for k in ("coin", "signal", "entry_day", "exit_day", "why", "net", "bench_net")}
                                                  for t in trades],
            "rule10": "signal candles: no grid phase", "source_rule": "cryptobot/perp_bot.py @ origin/claude/crypto-arbitrage-volatility-bot-qic8gv (read only)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b7_crypto_alt_high_volume_premium": b7_crypto_alt_high_volume_premium,
    "b7_crypto_eth_greed_momentum": b7_crypto_eth_greed_momentum,
    "b7_crypto_memecoin_bounce_short": b7_crypto_memecoin_bounce_short,
}

THEORY_MAP = {
    "T-546": "b7_crypto_alt_high_volume_premium",
    "T-554": "b7_crypto_eth_greed_momentum",
    "T-556": "b7_crypto_memecoin_bounce_short",
}
