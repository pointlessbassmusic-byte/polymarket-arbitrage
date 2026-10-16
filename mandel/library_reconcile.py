"""Reconcile verifier-corrected strategy libraries with the theory registry (never rewrites a tested claim)."""

from __future__ import annotations

import json
from pathlib import Path

from mandel.library import theories_from_strategies


def _norm(s: str) -> str:
    return " ".join((s or "").split()).strip().rstrip(".").lower()


def reconcile(reg: dict, strategies: list[dict], kind: str, origin_prefix: str, id_start: int, family_verified: dict[str, bool]) -> dict:
    by_slug = {t["slug"]: t for t in reg["theories"] if t["kind"] == kind}
    ids = {t["id"] for t in reg["theories"]}
    updated, superseded, unchanged, new = [], [], [], []
    fresh = []
    for s in strategies:
        t = by_slug.get(s["slug"][:60])
        verified = family_verified.get(s["family"], False)
        if t is None:
            fresh.append(s); continue
        claim = (s.get("claim") or "").strip(); claim = claim if claim.endswith(".") else claim + "."
        tr = s.get("trial", {})
        changed = _norm(claim) != _norm(t["claim"]) or _norm(tr.get("pass", "")) != _norm(t["trial"].get("pass", ""))
        if not changed:
            if verified and "verifier: confirmed" not in t["notes"]:
                t["notes"] += " | verifier: confirmed"
            unchanged.append(t["id"]); continue
        if t.get("results"):
            fresh.append({**s, "_supersedes": t["id"]}); superseded.append(t["id"]); continue
        t["claim"] = claim
        t["trial"] = {k: tr.get(k, t["trial"].get(k, "")) for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        t["testable_now"] = bool(s.get("testable_now"))
        if t["status"] in ("untested", "blocked"):
            t["status"] = "untested" if s.get("testable_now") else "blocked"
            t["blocked_on"] = "" if s.get("testable_now") else (s.get("blocked_on") or "a harness and the data it names")
        t["notes"] = t["notes"].replace(" | verifier pass pending (usage limit); engine-checked", "").replace(" | verifier pass pending (usage limit)", "") + " | verifier: corrected claim/trial"
        updated.append(t["id"])
    if fresh:
        nt = theories_from_strategies(fresh, id_start, kind, origin_prefix, ids)
        for t, s in zip(nt, fresh):
            if s.get("_supersedes"):
                t["supersedes"] = s["_supersedes"]
                t["notes"] += f" | verifier-corrected restatement of {s['_supersedes']}, whose verdict tested the earlier wording and stands"
                for old in reg["theories"]:
                    if old["id"] == s["_supersedes"]:
                        old["notes"] += f" | superseded by {t['id']} (verifier-corrected wording)"
                        # its verdict stands: unmap its harnesses so run_all no longer re-scores (rewrites) it
                        frozen = old.setdefault("experiments_frozen", [])
                        for h in old.get("experiments", []):
                            if h not in frozen:
                                frozen.append(h)
                        old["experiments"] = []
            else:
                t["notes"] += " | added by the verifier pass"
        reg["theories"] += nt
        new = [t["id"] for t in nt]
    for t in reg["theories"]:
        if t["kind"] == kind and family_verified.get(t["origin"][0].split(":", 1)[-1], False):
            t["notes"] = t["notes"].replace(" | verifier pass pending (usage limit); engine-checked", "").replace(" | verifier pass pending (usage limit)", "")
    reg["theories"].sort(key=lambda t: (len(t["id"]), t["id"]))
    return {"updated": updated, "superseded": superseded, "unchanged": unchanged, "new": new}
