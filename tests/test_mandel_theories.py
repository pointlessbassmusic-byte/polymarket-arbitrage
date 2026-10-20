"""Theory registry: every entry is well formed, statuses are legal, and the markdown renders."""

import json

from mandel.experiments import VERDICTS
from mandel.theories import REGISTRY, load, registry_hash, render_markdown

LEGAL = set(VERDICTS) - {"error"} | {"untested", "blocked", "parked"}


def test_registry_entries_are_well_formed():
    reg = load(REGISTRY)
    ids = [t["id"] for t in reg["theories"]]
    assert len(ids) == len(set(ids)) >= 40
    for t in reg["theories"]:
        assert t["status"] in LEGAL, t["id"]
        assert t["claim"].strip().endswith(".") and len(t["claim"]) > 30
        for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls"):
            assert k in t["trial"], (t["id"], k)
        if t["status"] == "blocked":
            assert t["blocked_on"], t["id"]
        if t["status"] == "parked":
            assert t["parked_reason"] and t["status_before_park"] in LEGAL, t["id"]
        if t["status"] in ("supported", "not_supported", "inconclusive"):
            assert t["results"], t["id"]           # a verdict needs a recorded result


def test_render_mentions_every_theory_and_hash_is_stable():
    reg = load(REGISTRY)
    md = render_markdown(reg, [{"id": r, "verdict": "supported", "reason": "x"} for t in reg["theories"] for r in t.get("results", [])])
    for t in reg["theories"]:
        assert t["id"] in md
    assert registry_hash(reg) == registry_hash(json.loads(json.dumps(reg)))
