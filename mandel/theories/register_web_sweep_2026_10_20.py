"""Pre-register the web sweep of 2026-10-20 (user request: strategies and asset patterns that use the learning program's
variables or adjacent ones), from mandel/knowledge/adjacent/web_sweep_2026-10-20.json, before any of them is run.

Every verified row the adversarial pass kept or fixed becomes a theory with its final registration text; a fixed row
that the verifier tied to an existing theory (duplicate_of) is a materially redesigned successor and records that
theory as its parent. Rows it dropped are not registered (the sweep file keeps them with the reason). Testable rows are 'untested', the rest
'blocked' with the missing data named. Usage: python3 mandel/theories/register_web_sweep_2026_10_20.py
"""

import hashlib
import json
import re
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402
from mandel.paths import MANDEL_ROOT  # noqa: E402

SWEEP = MANDEL_ROOT / "knowledge" / "adjacent" / "web_sweep_2026-10-20.json"
KINDS = {"underlying-strategy", "options-strategy", "volatility", "flow", "market-structure"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70]


def rows():
    sweep = json.loads(SWEEP.read_text())
    for c in sweep["clusters"]:
        research = {r["name"]: r for r in c["research"]["candidates"]}
        cross = {r["name"]: r for r in c["cross"]["rows"]}
        for v in c["verify"]["rows"]:
            if v["decision"] == "drop":
                continue
            yield c["cluster"], v, research.get(v["name"], {}), cross.get(v["name"], {})


def main():
    reg = json.load(open(REGISTRY))
    slugs = {t["slug"] for t in reg["theories"]}
    led = Ledger()
    out = []
    for cluster, v, r, x in rows():
        f = v["final"]
        slug = _slug(f["slug"]) or _slug(v["name"])
        if slug in slugs:
            print(f"skip {slug}: slug already registered")
            continue
        tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
        claim = f["claim"].strip()
        trial = {"statistic": f["statistic"], "null": f["null"], "procedure": f["procedure"], "data": f["data"],
                 "min_n": int(f["min_n"]), "pass": f["pass"], "controls": f["controls"]}
        testable = bool(v["testable_now"])
        sources = [s.get("url") for s in r.get("sources", []) if s.get("url")]
        reg["theories"].append({
            "id": tid, "slug": slug, "kind": f["kind"] if f["kind"] in KINDS else "underlying-strategy", "claim": claim,
            "origin": [f"web sweep 2026-10-20 ({cluster}): {v['name']}"] + sources[:4], "trial": trial, "experiments": [],
            "testable_now": testable, "status": "untested" if testable else "blocked",
            "blocked_on": "" if testable else (v.get("missing_data") or x.get("missing_data") or "data not archived"),
            "results": [], "parent": v.get("duplicate_of") or "", "web_sweep": {"cluster": cluster, "evidence_quality": r.get("evidence_quality"),
                                         "replication": r.get("replication"), "prior": x.get("prior"),
                                         "consistency": x.get("consistency"), "priority": x.get("priority"),
                                         "overlaps": x.get("overlaps"), "learnings": x.get("learnings"),
                                         "verifier": {k: v.get(k) for k in ("decision", "source_verified", "replication_concerns",
                                                                            "data_notes", "lookahead_risks", "reason")}},
            "notes": "pre-registered from the 2026-10-20 web sweep before any run; the adversarial verifier's notes are in web_sweep."})
        led.append("theory.preregistered", {"id": tid, "from": f"web sweep 2026-10-20 ({cluster})", "hash": hashlib.sha256(json.dumps(
            {"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16], "known_days": 0,
            "basis": "web-sweep-2026-10-20"}, actor="mandel")
        slugs.add(slug)
        out.append((tid, slug, "untested" if testable else "blocked"))
    save_registry(reg)
    for o in out:
        print(*o)
    print(f"{len(out)} registered")


if __name__ == "__main__":
    main()
