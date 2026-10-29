"""
Weighting review: re-rank the map, the next-test score and the learning program's scan under alternative weightings and
report what moves (the 2026-10-29 review found a concept with zero attached tests, a blocked theory whose data had
arrived and a scan cell that was a regime). Read-only; writes state/tracker/weighting_review.json.

    python -m mandel weighting-review
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Optional

from mandel.paths import MANDEL_ROOT

GRAPH = MANDEL_ROOT / "viz" / "graph.json"
IC_SCAN = MANDEL_ROOT / "state" / "ml" / "ic_scan.json"
IC_SCAN_F3 = MANDEL_ROOT / "state" / "ml" / "ic_scan_f3.json"
OUT = MANDEL_ROOT / "state" / "tracker" / "weighting_review.json"


def map_rankings(graph: dict, top: int = 8) -> dict:
    """Concept rankings under alternative weights, the gaps between talk and tests, and concepts with no tests."""
    k = {n["id"]: n for n in graph["nodes"] if n["id"].startswith("k:")}
    ten = collections.Counter()
    for e in graph["edges"]:
        if e["type"] == "tension":
            ten[e["s"]] += 1; ten[e["t"]] += 1
    rows = []
    for i, n in k.items():
        m = n.get("meta") or {}
        v = m.get("verdicts") or {}
        tested = sum(sum(t.values()) for t in v.values())
        passed = sum(t.get("supported", 0) + t.get("PASS", 0) for t in v.values())
        failed = sum(t.get("not_supported", 0) + t.get("FAIL", 0) for t in v.values())
        rows.append({"id": i[2:], "size": n.get("size", 0), "mentions": m.get("mentions", 0), "docs": m.get("documents", 0),
                     "tested": tested, "passed": passed, "failed": failed, "tension": ten[i]})

    def rank(key, rev=True):
        return [r["id"] for r in sorted(rows, key=key, reverse=rev)[:top]]
    out = {"by_size": rank(lambda r: r["size"]), "by_documents": rank(lambda r: r["docs"]), "by_tests": rank(lambda r: r["tested"]),
           "by_pass_share": rank(lambda r: (r["passed"] / (r["tested"] or 1), r["tested"])),
           "by_fail_share": rank(lambda r: (r["failed"] / (r["tested"] or 1), r["tested"])),
           "by_tensions": rank(lambda r: r["tension"]),
           "talked_untested": rank(lambda r: r["mentions"] / (1 + r["tested"])),
           "tested_untalked": rank(lambda r: r["tested"] / (1 + r["mentions"])),
           "zero_tests": sorted(r["id"] for r in rows if r["tested"] == 0),
           "theories_unmatched": graph.get("theories_unmatched") or []}
    return out


def next_test_sensitivity(registry: list, bundles: dict, result_times: Optional[dict] = None, top: int = 10) -> dict:
    """Top-10 of the next-test ranking under the current weights and four alternatives; ids that enter only under an alternative."""
    from mandel.live import evidence_graph as G
    base_ids = [r["id"] for r in G.next_tests(registry, bundles, top=400, result_times=result_times)[:top]]
    out = {"current": base_ids, "alternatives": {}}
    orig = dict(G.STATUS_WEIGHT)
    try:
        for label, sw in (("blocked_weight_1.0", {**orig, "blocked": 1.0}), ("blocked_weight_0.1", {**orig, "blocked": 0.1}),
                          ("untested_weight_1.0", {**orig, "untested": 1.0})):
            G.STATUS_WEIGHT.clear(); G.STATUS_WEIGHT.update(sw)
            ids = [r["id"] for r in G.next_tests(registry, bundles, top=400, result_times=result_times)[:top]]
            out["alternatives"][label] = {"top": ids, "enters": [i for i in ids if i not in base_ids]}
    finally:
        G.STATUS_WEIGHT.clear(); G.STATUS_WEIGHT.update(orig)
    rows = G.next_tests(registry, bundles, top=400, result_times=result_times)
    for r in rows:                                               # ignore the new-data factor
        if r["status"] == "inconclusive" and r["new_data"] is False:
            r["score"] *= 5
    rows.sort(key=lambda x: (-x["score"], x["id"]))
    ids = [r["id"] for r in rows[:top]]
    out["alternatives"]["ignore_new_data"] = {"top": ids, "enters": [i for i in ids if i not in base_ids]}
    out["unblocked_with_data"] = [r["id"] for r in rows if r.get("unblocked")]
    return out


def scan_reweighting(top: int = 5) -> Optional[dict]:
    """The IC scan's triples grouped by family / class / horizon / scope under five weightings; groups in the top 3 under
    at least four of them; sign stability by relationship type; the confirmed cells with |t| > 2."""
    if not IC_SCAN.exists():
        return None
    rows = json.loads(IC_SCAN.read_text())["rows"]
    if IC_SCAN_F3.exists():
        rows = rows + json.loads(IC_SCAN_F3.read_text())["rows"]
    rows = [r for r in rows if r.get("conf") and r["conf"].get("mean_ic") is not None]

    def agg(keyf):
        g = collections.defaultdict(list)
        for r in rows:
            g[keyf(r)].append(r)
        out = {}
        for k, rs in g.items():
            n = len(rs); disc = [r for r in rs if r.get("discovered")]; conf = [r for r in disc if r.get("confirmed")]
            stab = [r for r in rs if (r["disc_mean_ic"] > 0) == (r["conf"]["mean_ic"] > 0) and abs(r["disc_t"]) > 1 and abs(r["conf"]["t"]) > 1]
            wic = [abs(r["conf"]["mean_ic"]) * r["conf"]["n_periods"] for r in disc]; wn = [r["conf"]["n_periods"] for r in disc]
            out[k] = {"n": n, "disc": len(disc) / n, "conf_of_disc": (len(conf) / len(disc)) if disc else 0.0, "stable": len(stab) / n,
                      "w_abs_ic": (sum(wic) / sum(wn)) if wn else 0.0, "tprod": sum(1 for r in rs if r["disc_t"] * r["conf"]["t"] > 1) / n}
        return out
    res = {}
    for name, keyf in (("family", lambda r: r["family"]), ("class", lambda r: r["cls"]), ("horizon", lambda r: r["horizon"]), ("scope", lambda r: r["scope"])):
        o = agg(keyf)
        ranks = {m: sorted(o, key=lambda k: -o[k][m])[:top] for m in ("disc", "conf_of_disc", "stable", "w_abs_ic", "tprod")}
        cnt = collections.Counter(k for m in ranks for k in ranks[m][:3])
        res[name] = {"ranks": ranks, "consensus_top3": [k for k, c in cnt.items() if c >= 4], "groups": o}
    by = collections.defaultdict(list)
    for r in rows:
        by[r.get("sign")].append((r["disc_mean_ic"] > 0) == (r["conf"]["mean_ic"] > 0))
    strong = sorted([r for r in rows if r.get("confirmed") and abs(r["conf"]["t"]) > 2], key=lambda r: -abs(r["conf"]["mean_ic"]))
    res["sign_stability"] = {k: {"share": sum(v) / len(v), "n": len(v)} for k, v in by.items()}
    res["strongest_confirmed"] = [{k: r[k] for k in ("scope", "cls", "horizon", "feature", "family", "sign")} | {"conf_ic": r["conf"]["mean_ic"], "conf_t": r["conf"]["t"], "conf_n": r["conf"]["n_periods"]} for r in strong[:12]]
    res["note"] = ("a group that tops every weighting is where signal concentrates, not evidence it pays; register it as a replication on "
                   "years the scan never saw (harness rule 13; T-743 failed that test)")
    return res


def run(out: Path = OUT) -> dict:
    from mandel.live import evidence_graph as G
    graph = json.loads(GRAPH.read_text()) if GRAPH.exists() else {"nodes": [], "edges": []}
    reg = G._load(G.REGISTRY, {}).get("theories", [])
    reg = reg if isinstance(reg, list) else list(reg.values())
    bundles = G._bundles()
    cap = G._load(G.TRACKER / "capture_status.json", None)
    if cap:
        bundles = G.apply_capture_status(bundles, cap)
    rep = {"map": map_rankings(graph), "next_tests": next_test_sensitivity(reg, bundles), "scan": scan_reweighting()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, default=str))
    return rep


def summary(rep: dict) -> str:
    m, nt, sc = rep["map"], rep["next_tests"], rep.get("scan")
    lines = [f"map: {len(m['zero_tests'])} concepts with zero attached tests: {', '.join(m['zero_tests'][:10])}{'...' if len(m['zero_tests']) > 10 else ''}",
             f"map: {len(m['theories_unmatched'])} theories no concept matches (the overlay is blind to them)",
             f"map: talked about but untested: {', '.join(m['talked_untested'][:5])}; tested but barely discussed: {', '.join(m['tested_untalked'][:5])}",
             f"next tests: current top {', '.join(nt['current'][:6])}"]
    for label, a in nt["alternatives"].items():
        if a["enters"]:
            lines.append(f"next tests: under {label} these enter the top 10: {', '.join(a['enters'])}")
    if nt.get("unblocked_with_data"):
        lines.append(f"next tests: blocked theories whose data is present: {', '.join(nt['unblocked_with_data'])} (check coverage, then unblock)")
    if sc:
        for name in ("family", "class", "horizon"):
            lines.append(f"scan: {name} top-3 under >= 4 of 5 weightings: {', '.join(sc[name]['consensus_top3']) or 'none'}")
        ss = sc["sign_stability"]
        lines.append("scan: sign stability " + ", ".join(f"{k} {v['share']:.2f} (n {v['n']})" for k, v in ss.items()))
    return "\n".join(lines)
