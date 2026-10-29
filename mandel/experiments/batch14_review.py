"""
Batch 14, the 2026-10-29 weighting review: one replication the re-weighted IC scan pointed at.
================================================================================================

  * T-743  Treasury-ETF 20-day reversal replication on pre-discovery years (2002-07..2023-12; the scan's 2024-2026
           confirmation periods are excluded from the pass). Two readings under rule 11: (i) TLT's own trailing 20-day
           return, long the bottom quintile / short the top; (ii) the 10-year yield's trailing 20-day change (DGS10),
           long the top quintile / short the bottom. Quintile cut points come from the trailing 250 observations of the
           signal (exclusive of the decision day). Decisions are non-overlapping within a phase (one per 20 sessions);
           the 20 start-day phases are pooled (rule 10) and reported as a range; the bootstrap runs on the daily
           series of the rule's signed net return with blocks of 3 x 20 days (three decisions' worth), so the overlap
           of horizons is respected. Net of 1 bp a side (a round trip is 2 bp). Pass: for TLT under BOTH readings,
           pooled mean > 0 with that one-sided studentized block bootstrap p < 0.05, and both halves (2002-07..2012-12, 2013-01..2023-12) positive; IEF reported.
           Disagreement between the readings leaves the criterion undecided. min_n 250 non-overlapping decisions per
           phase. The scan (2,254 triples) is the discovery family and is disclosed; this is one pre-registered trial.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch11_xasset import _series

WINDOW = ("2002-07-30", "2023-12-31")
SPLIT = "2013-01-01"
H = 20
LOOK = 250
COST_SIDE = 0.0001
MIN_N = 250
BLOCK = 3
BUNDLES = ("daily-history-TLT", "daily-history-IEF", "fred-DGS10")


def _align_yield(days: list, ydays: list, y: np.ndarray) -> np.ndarray:
    """DGS10 on each trading day: the last published value on or before it (FRED skips holidays), NaN before the first."""
    out = np.full(len(days), np.nan)
    j = -1
    for i, d in enumerate(days):
        while j + 1 < len(ydays) and ydays[j + 1] <= d:
            j += 1
        if j >= 0:
            out[i] = y[j]
    return out


def decisions(days: list, sig: np.ndarray, fwd: np.ndarray, long_bottom: bool) -> dict:
    """The quintile rule's signed net 20-day return on every eligible day (overlapping horizons), with the cut points
    from the trailing LOOK observations of the signal. The bootstrap runs on that daily series with blocks of
    BLOCK x H days (three decisions' worth), which respects the overlap; the 20 start-day phases (t mod 20) are
    reported as a range (rule 10), and n counts non-overlapping decisions (the smallest phase)."""
    lo_d, hi_d = WINDOW
    n = len(days)
    ts, xs = [], []
    phase_dec = [0] * H
    halves = {"first": [], "second": []}
    for t in range(LOOK + H, n - H):
        if days[t] < lo_d or days[t] > hi_d:
            continue
        hist = sig[t - LOOK:t]
        if np.isnan(sig[t]) or np.isnan(fwd[t]) or np.sum(~np.isnan(hist)) < LOOK // 2:
            continue
        phase_dec[t % H] += 1
        q20, q80 = np.nanquantile(hist, 0.2), np.nanquantile(hist, 0.8)
        if sig[t] <= q20:
            pos = 1.0 if long_bottom else -1.0
        elif sig[t] >= q80:
            pos = -1.0 if long_bottom else 1.0
        else:
            continue
        x = pos * fwd[t] - 2 * COST_SIDE
        ts.append(t); xs.append(x)
        halves["first" if days[t] < SPLIT else "second"].append(x)
    x_all = np.array(xs, float)
    phase_means = []
    for k in range(H):
        xk = [x for t, x in zip(ts, xs) if t % H == k]
        if xk:
            phase_means.append(float(np.mean(xk)))
    pg, pl, draws = (CAL.studentized_p_escalated(x_all, BLOCK * H, None, CAL.SEED, 5, CAL.MAX_SEEDS) if x_all.size > 3 * BLOCK * H
                     else (None, None, 0))
    return {"n_active_days": int(x_all.size), "mean": float(x_all.mean()) if x_all.size else None,
            "p_greater": pg, "p_less": pl, "draws": draws, "block_days": BLOCK * H, "phase_means": phase_means,
            "phase_range": [min(phase_means), max(phase_means)] if phase_means else None,
            "n_decisions_min_phase": min(phase_dec) if phase_dec else 0,
            "halves": {k: (float(np.mean(v)) if v else None) for k, v in halves.items()},
            "halves_n": {k: len(v) for k, v in halves.items()}}


def _reading_ok(r: dict) -> tuple:
    """(ok, decisive_fail) for 'mean > 0 with one-sided p < 0.05'."""
    if r["mean"] is None or r["p_greater"] is None:
        return None, False
    if r["mean"] <= 0:
        return False, CAL.decide_p(r["p_less"], r["draws"]) is True
    ok = CAL.decide_p(r["p_greater"], r["draws"])
    return ok, False


def analyse(days: list, adj: np.ndarray, y10: np.ndarray) -> dict:
    la = np.log(adj)
    r20 = np.full(len(days), np.nan); r20[H:] = la[H:] - la[:-H]
    d20 = np.full(len(days), np.nan); d20[H:] = y10[H:] - y10[:-H]
    fwd = np.full(len(days), np.nan); fwd[:-H] = adj[H:] / adj[:-H] - 1.0
    return {"own_r20_reversal": decisions(days, r20, fwd, long_bottom=True),
            "dgs10_d20_lead": decisions(days, d20, fwd, long_bottom=False)}


def _fmt(x: Optional[float], nd: int = 2, bp: bool = True) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return f"{x * 1e4:+.{nd}f} bp" if bp else f"{x:.{nd}f}"


def b14_treasury_20d_reversal(archive):
    """T-743: TLT 20-day reversal / 10-year-yield lead, 2002-07..2023-12, both readings, net of 1 bp a side."""
    missing = []
    for b in BUNDLES:
        try:
            archive.get(b)
        except KeyError:
            missing.append(b)
    if missing:
        return _out({"missing": missing}, 0, "inconclusive", f"not archived: {', '.join(missing)} (rule 9)")
    ydays, y = _series(archive, "fred-DGS10")
    res = {}
    for sym in ("TLT", "IEF"):
        days, vals = CAL._daily(archive, f"daily-history-{sym}")
        adj = np.asarray(vals, float)
        res[sym] = analyse(list(days), adj, _align_yield(list(days), ydays, y))
    T = res["TLT"]
    a, b = T["own_r20_reversal"], T["dgs10_d20_lead"]
    ok_a, dec_a = _reading_ok(a)
    ok_b, dec_b = _reading_ok(b)
    halves_ok = (None if any(v is None for r in (a, b) for v in r["halves"].values())
                 else all(v > 0 for r in (a, b) for v in r["halves"].values()))
    n = min(a["n_decisions_min_phase"], b["n_decisions_min_phase"])
    rows = [((f"TLT pooled mean > 0 with one-sided studentized block-bootstrap p < 0.05 under BOTH readings (rule 11): "
             f"(i) own 20-day reversal mean {_fmt(a['mean'])} per decision, p {CAL._mc(a['p_greater'], a['draws'])}, "
             f"{a['n_active_days']} active days; (ii) DGS10 20-day lead mean {_fmt(b['mean'])}, p {CAL._mc(b['p_greater'], b['draws'])}, "
             f"{b['n_active_days']} active days; studentized block bootstrap, blocks of {BLOCK * H} days"), CAL._agree([ok_a, ok_b]), bool(dec_a and dec_b)),
            ((f"both halves positive under both readings (2002-07..2012-12 / 2013-01..2023-12): (i) {_fmt(a['halves']['first'])} / "
              f"{_fmt(a['halves']['second'])}; (ii) {_fmt(b['halves']['first'])} / {_fmt(b['halves']['second'])}"), halves_ok, False),
            (f"n >= {MIN_N} non-overlapping decisions in every phase (smallest phase {n})", True if n >= MIN_N else None, False)]
    verdict, why, crit = CAL._judge(CAL._undecided(rows), n, MIN_N, "decisions")
    I = res["IEF"]
    stat = {"n": n, "window": WINDOW, "split": SPLIT, "horizon_days": H, "lookback": LOOK, "cost_per_side": COST_SIDE,
            "TLT": {k: {kk: vv for kk, vv in v.items() if kk != "x"} for k, v in T.items()},
            "IEF": {k: {kk: vv for kk, vv in v.items() if kk != "x"} for k, v in I.items()},
            "criteria": crit, "discovery_family": "2026-10-20 IC scan, 2,254 triples (disclosed); this replication is one trial",
            "note": "the bond-ETF cross-section is ~one factor (duration): this is a time-series duration call, tested on years the scan never saw"}
    reason = (f"TLT 2002-07..2023-12, 20 start-day phases pooled (rule 10; per-phase mean range (i) {_fmt(a['phase_range'][0]) if a['phase_range'] else 'n/a'}.."
              f"{_fmt(a['phase_range'][1]) if a['phase_range'] else 'n/a'}, (ii) {_fmt(b['phase_range'][0]) if b['phase_range'] else 'n/a'}.."
              f"{_fmt(b['phase_range'][1]) if b['phase_range'] else 'n/a'}); IEF reported: (i) {_fmt(I['own_r20_reversal']['mean'])} "
              f"p {CAL._mc(I['own_r20_reversal']['p_greater'], I['own_r20_reversal']['draws'])}, (ii) {_fmt(I['dgs10_d20_lead']['mean'])} "
              f"p {CAL._mc(I['dgs10_d20_lead']['p_greater'], I['dgs10_d20_lead']['draws'])}; discovery family: the 2,254-triple IC scan, disclosed — {why}")
    return _out(stat, n, verdict, reason)


HARNESSES = {"b14_treasury_20d_reversal": b14_treasury_20d_reversal}
THEORY_MAP = {"T-743": "b14_treasury_20d_reversal"}
