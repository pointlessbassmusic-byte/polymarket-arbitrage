"""
Development verdicts for the learning program (T-577..T-580) from the result files in mandel/state/ml.
=====================================================================================================

    python -m mandel.ml.report            # prints the summary; mandel.experiments.batch12_ml records it

Each theory's cells are pooled across its runs (T-577: the Yahoo and crypto stages; T-580: its F3 cells counted
together with T-578's), the deflated Sharpe is recomputed with N = every cell of the theory (T-580: T-578 + T-580),
and a cell passes development only with DSR >= 0.95, a positive mean net return and at least the registered min_n
trades. The lockbox is not read here.
"""

from __future__ import annotations

import json
from collections import defaultdict

from mandel.ml import train as TR

MIN_N = {"T-577": 1000, "T-578": 200, "T-580": 200}
FILES = {"T-577": ["results_dev_yahoo.json", "results_dev_crypto.json"], "T-578": ["swing_dev.json"],
         "T-580": ["swing_dev_f3.json"]}


def _cells(names) -> list:
    out = []
    for n in names:
        p = TR.OUT / n
        if p.exists():
            out += [c for c in json.loads(p.read_text())["cells"] if "sr_period" in c]
    return out


def judged(tid: str) -> dict:
    cells = _cells(FILES[tid])
    pool = cells + (_cells(FILES["T-578"]) if tid == "T-580" else [])
    n_trials = len(pool)
    for c in cells:
        c["dsr"] = TR.deflated_sharpe(c["sr_period"], c["n_periods"], n_trials, c["skew"], c["kurt"])
        c["passes_dev"] = bool(c["dsr"] >= 0.95 and (c["mean_net_per_trade_bps"] or 0) > 0
                               and c["n_trades"] >= MIN_N[tid])
    return {"cells": cells, "n_trials": n_trials, "missing": [n for n in FILES[tid] if not (TR.OUT / n).exists()]}


def ablation(cells: list, key=("cls", "interval", "h", "model", "rule")) -> dict:
    """Mean IC and annual Sharpe per feature family, and how often each family is the best of its cell group."""
    by_fam = defaultdict(list)
    groups = defaultdict(dict)
    for c in cells:
        if c["model"] == "rule":
            continue
        by_fam[c["family"]].append(c)
        groups[tuple(c.get(k) for k in key)][c["family"]] = c["ic"]
    best = defaultdict(int)
    for g in groups.values():
        if g:
            best[max(g, key=lambda f: g[f] if g[f] == g[f] else -9)] += 1
    return {f: {"n": len(v), "mean_ic": sum(c["ic"] for c in v if c["ic"] == c["ic"]) / max(1, len(v)),
                "mean_sr_annual": sum(c["sr_annual"] for c in v) / max(1, len(v)),
                "share_net_positive": sum(1 for c in v if (c["mean_net_per_trade_bps"] or 0) > 0) / max(1, len(v)),
                "best_ic_in_group": best[f]} for f, v in sorted(by_fam.items())}


def paired_f3(f3_cells: list, base_cells: list) -> dict:
    """T-580's paired ablation: each F3 cell against the identical T-578 cell without F3."""
    base = {(c["cls"], c["h"], c["family"], c["model"], c["rule"]): c for c in base_cells}
    pairs = []
    for c in f3_cells:
        b = base.get((c["cls"], c["h"], {"F0F1F3": "F0F1", "ALLF3": "ALL"}[c["family"]], c["model"], c["rule"]))
        if b:
            pairs.append((c["ic"] - b["ic"], c["sr_annual"] - b["sr_annual"]))
    if not pairs:
        return {"n_pairs": 0}
    d_ic = [p[0] for p in pairs if p[0] == p[0]]
    d_sr = [p[1] for p in pairs]
    return {"n_pairs": len(pairs), "mean_d_ic": sum(d_ic) / len(d_ic), "share_ic_up": sum(x > 0 for x in d_ic) / len(d_ic),
            "mean_d_sr_annual": sum(d_sr) / len(d_sr), "share_sr_up": sum(x > 0 for x in d_sr) / len(d_sr)}


def top(cells: list, k: int = 5, by: str = "dsr") -> list:
    keep = ("cls", "interval", "h", "family", "model", "rule", "n_trades", "ic", "mean_net_per_trade_bps", "sr_annual", "dsr")
    return [{x: c.get(x) for x in keep if x in c} for c in sorted(cells, key=lambda c: -(c.get(by) or 0))[:k]]


def summary() -> dict:
    out = {}
    for tid in ("T-577", "T-578", "T-580"):
        j = judged(tid)
        cells = j["cells"]
        out[tid] = {"n_cells": len(cells), "n_trials": j["n_trials"], "missing": j["missing"],
                    "n_pass_dev": sum(c["passes_dev"] for c in cells),
                    "n_net_positive": sum(1 for c in cells if (c["mean_net_per_trade_bps"] or 0) > 0),
                    "passing": [c for c in cells if c["passes_dev"]], "top_dsr": top(cells),
                    "ablation": ablation(cells, ("cls", "interval", "model") if tid == "T-577" else ("cls", "h", "model", "rule"))}
    out["T-580"]["paired_vs_T-578"] = paired_f3(judged("T-580")["cells"], judged("T-578")["cells"])
    for name, tid in (("ic_scan.json", "T-579"), ("ic_scan_f3.json", "T-580-ic")):
        p = TR.OUT / name
        if p.exists():
            j = json.loads(p.read_text())
            rows = [r for r in j["rows"] if r.get("discovered")]
            out[tid] = {k: v for k, v in j.items() if k != "rows"} | {
                "confirmed": [{k: r.get(k) for k in ("scope", "cls", "horizon", "feature", "family", "sign", "disc_mean_ic",
                                                     "disc_t", "disc_q")} | {"conf_mean_ic": (r["conf"] or {}).get("mean_ic"),
                                                                             "conf_t": (r["conf"] or {}).get("t")}
                              for r in rows if r.get("confirmed")]}
    return out


def main() -> int:
    print(json.dumps(summary(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
