"""
Batch 12, group ``ml``: the day-to-month learning program (T-577..T-580), 2026-10-20.
====================================================================================

The models run outside the harness runner (``python -m mandel.ml.train / swing / ic``, minutes to hours on local bar
files that are not archive bundles); these harnesses read their result files in mandel/state/ml and apply each
theory's registered pass rule through ``mandel.ml.report``:

  * T-577  intraday (5-60 min, h = 1 bar): a cell passes development with DSR >= 0.95 over every T-577 cell, positive
           mean net and >= 1000 trades; with no passing cell the theory fails (its lockbox is never read).
  * T-578  daily swing holds (1/5/20 days, sign and cross-sectional rules): the same with >= 200 trades.
  * T-580  T-578 plus options-implied features: the same, N = T-578 + T-580 cells; the paired ablation is reported.
  * T-579  feature correlation scan: Benjamini-Hochberg discoveries confirmed in their own sign on unseen periods; the
           intraday confirmation is the lockbox, read once (``python -m mandel.ml.ic --confirm``).
A passing development cell leaves the verdict inconclusive until its lockbox is read, once.
"""

from __future__ import annotations

import json

from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.ml import report as R
from mandel.ml import train as TR


# archive bundles the model runs read (the bars themselves are local vendor files, not bundles)
INPUTS = {"T-577": ["fomc-meetings", "macro-release-cpi"], "T-578": ["fomc-meetings", "macro-release-cpi"],
          "T-579": ["fomc-meetings", "macro-release-cpi"],
          "T-580": ["fomc-meetings", "macro-release-cpi", "cboe-VIX-history", "cboe-VIX3M-history", "cboe-vx-futures",
                    "deribit-dvol-BTC-history", "deribit-funding-BTC-PERPETUAL"]}


def _inputs(archive, tid: str):
    return B7C._missing(archive, INPUTS[tid])


def _f(x, nd=2):
    return "n/a" if x is None or x != x else f"{x:+.{nd}f}"


def _model_theory(archive, tid: str):
    miss = _inputs(archive, tid)
    if miss:
        return miss
    j = R.judged(tid)
    if j["missing"]:
        return _out({"missing": j["missing"]}, 0, "inconclusive", f"result files not written yet: {', '.join(j['missing'])}")
    cells = j["cells"]
    passing = [c for c in cells if c["passes_dev"]]
    n_trades = sum(c["n_trades"] for c in cells)
    best = R.top(cells, 3)
    ab = R.ablation(cells, ("cls", "interval", "model") if tid == "T-577" else ("cls", "h", "model", "rule"))
    stat = {"n_cells": len(cells), "n_trials": j["n_trials"], "n_pass_dev": len(passing),
            "n_net_positive": sum(1 for c in cells if (c["mean_net_per_trade_bps"] or 0) > 0), "top_dsr": best,
            "ablation": ab, "passing": R.top(passing, 20)}
    if tid == "T-580":
        stat["paired_vs_T-578"] = R.paired_f3(cells, R.judged("T-578")["cells"])
    fam = "; ".join(f"{f} IC {_f(v['mean_ic'], 3)} SR {_f(v['mean_sr_annual'])} net>0 {v['share_net_positive']:.0%}"
                    for f, v in ab.items())
    b = best[0] if best else {}
    head = (f"{len(cells)} cells (DSR over N = {j['n_trials']}), {stat['n_net_positive']} with positive mean net; best DSR "
            f"{_f(b.get('dsr'), 3)} ({b.get('cls')} {b.get('interval') or str(b.get('h')) + 'd'} {b.get('family')} {b.get('model')}"
            f"{' ' + b['rule'] if b.get('rule') else ''}: {b.get('n_trades')} trades, net {_f(b.get('mean_net_per_trade_bps'))} bp, "
            f"annual SR {_f(b.get('sr_annual'))}); families: {fam}")
    if tid == "T-580":
        p = stat["paired_vs_T-578"]
        if p.get("n_pairs"):
            head += (f"; paired vs T-578: IC {_f(p['mean_d_ic'], 4)} ({p['share_ic_up']:.0%} up), annual SR "
                     f"{_f(p['mean_d_sr_annual'])} ({p['share_sr_up']:.0%} up) over {p['n_pairs']} pairs")
    if passing:
        return _out(stat, n_trades, "inconclusive",
                    head + f" — {len(passing)} cell(s) pass development; the lockbox is read once for them before any verdict")
    return _out(stat, n_trades, "not_supported", head + " — no cell passes development (DSR >= 0.95, net > 0, "
                f">= {R.MIN_N[tid]} trades): the lockbox stays sealed and unread")


def b12_ml_intraday(archive):
    """T-577."""
    return _model_theory(archive, "T-577")


def b12_ml_swing(archive):
    """T-578."""
    return _model_theory(archive, "T-578")


def b12_ml_implied(archive):
    """T-580."""
    return _model_theory(archive, "T-580")


def b12_ml_ic_scan(archive):
    """T-579."""
    miss = _inputs(archive, "T-579")
    if miss:
        return miss
    p = TR.OUT / "ic_scan.json"
    if not p.exists():
        return _out({}, 0, "inconclusive", "ic_scan.json not written yet")
    j = json.loads(p.read_text())
    rows = j["rows"]
    disc = [r for r in rows if r.get("discovered")]
    conf = [r for r in disc if r.get("confirmed")]
    by_scope = {s: {"discovered": sum(1 for r in disc if r["scope"] == s),
                    "judged": sum(1 for r in disc if r["scope"] == s and r.get("confirmed") is not None),
                    "confirmed": sum(1 for r in conf if r["scope"] == s)} for s in ("intraday", "daily")}
    keep = ("scope", "cls", "horizon", "feature", "family", "sign", "disc_mean_ic", "disc_t", "disc_q")
    stat = {k: j[k] for k in ("n_triples", "n_discovered", "n_judged", "n_confirmed", "confirmed_fraction")} | {
        "by_scope": by_scope, "intraday_confirmation_read": j["intraday_confirmation_read"],
        "confirmed": [{k: r.get(k) for k in keep} | {"conf_mean_ic": r["conf"]["mean_ic"], "conf_t": r["conf"]["t"]}
                      for r in conf]}
    head = (f"{j['n_triples']} feature x class x horizon triples; {j['n_discovered']} discovered (BH q < 0.05), "
            f"{j['n_judged']} judged on unseen periods, {j['n_confirmed']} confirmed in their sign"
            f" ({_f((j['confirmed_fraction'] or 0) * 100, 0)}% vs 5% by chance); intraday "
            f"{by_scope['intraday']['confirmed']}/{by_scope['intraday']['judged']}, daily "
            f"{by_scope['daily']['confirmed']}/{by_scope['daily']['judged']}")
    if conf:
        top = sorted(conf, key=lambda r: -abs(r["disc_t"] or 0))[:6]
        head += "; strongest: " + ", ".join(f"{r['feature']} {r['sign']} ({r['cls']} {r['horizon']}, IC {_f(r['disc_mean_ic'], 3)}"
                                            f" -> {_f(r['conf']['mean_ic'], 3)})" for r in top)
    if not j["intraday_confirmation_read"] and by_scope["intraday"]["discovered"]:
        return _out(stat, j["n_judged"], "inconclusive", head + " — the intraday confirmation (lockbox) is not read yet")
    verdict = "supported" if conf else "not_supported"
    return _out(stat, j["n_judged"], verdict, head + (" — at least one discovered relationship holds out of sample; a "
                                                     "correlation is not a trade" if conf else " — nothing discovered holds"))


HARNESSES = {"b12_ml_intraday": b12_ml_intraday, "b12_ml_swing": b12_ml_swing, "b12_ml_implied": b12_ml_implied,
             "b12_ml_ic_scan": b12_ml_ic_scan}
THEORY_MAP = {"T-577": "b12_ml_intraday", "T-578": "b12_ml_swing", "T-580": "b12_ml_implied", "T-579": "b12_ml_ic_scan"}
