"""
Theory registry: one falsifiable statement per theory, with its trial math.
===========================================================================

``registry.json`` is the source of truth. Statuses: ``untested`` (a harness exists or the data is
reachable), ``blocked`` (names what is missing), ``supported`` / ``not_supported`` / ``inconclusive``
(set only by a recorded experiment result), ``parked`` (set only by a ledgered park event, keeps
``status_before_park``). Nothing is deleted. ``THEORIES.md`` is rendered from the registry.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from mandel._io import atomic_write_text
from mandel.paths import MANDEL_ROOT

REGISTRY = MANDEL_ROOT / "theories" / "registry.json"
THEORIES_MD = MANDEL_ROOT / "theories" / "THEORIES.md"
ORDER = ["supported", "not_supported", "inconclusive", "untested", "blocked", "parked"]


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def registry_hash(reg: dict) -> str:
    return hashlib.sha256(json.dumps(reg["theories"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def render_markdown(reg: dict, experiments: list[dict] | None = None) -> str:
    by_result = {e["id"]: e for e in (experiments or [])}
    counts = Counter(t.get("status", "?") for t in reg["theories"])
    lines = ["# Theories and their trial math", "",
             f"Rendered from `registry.json` (hash `{registry_hash(reg)}`). {len(reg['theories'])} theories. "
             + ", ".join(f"{k} {counts[k]}" for k in ORDER if counts.get(k)) + ".", "",
             "A theory is one falsifiable statement. Its status moves only through a recorded experiment result or a ledgered park/unpark event. "
             "Parked theories are kept in full so they can be picked up without re-deriving them.", ""]
    for status in ORDER:
        group = [t for t in reg["theories"] if t.get("status") == status]
        if not group:
            continue
        lines += [f"## {status.replace('_', ' ').title()} ({len(group)})", ""]
        for t in group:
            tr = t["trial"]
            lines += [f"### {t['id']} · {t['slug']}", "", f"**Claim.** {t['claim']}", "",
                      f"- kind: {t['kind']} · origin: {', '.join(t['origin'])}",
                      f"- statistic: {tr['statistic']}", f"- null: {tr['null']}", f"- procedure: {tr['procedure']}",
                      f"- data: {tr['data']} · min n: {tr['min_n']}", f"- pass: {tr['pass']}", f"- controls: {tr['controls']}"]
            if t.get("experiments"):
                lines.append(f"- harness: {', '.join(t['experiments'])}")
            if t.get("results"):
                for rid in t["results"][-3:]:
                    e = by_result.get(rid)
                    lines.append(f"- result {rid}: {e['verdict']} — {e['reason']}" if e else f"- result {rid}")
            if t.get("blocked_on"):
                lines.append(f"- blocked on: {t['blocked_on']}")
            if status == "parked":
                lines.append(f"- parked (was {t.get('status_before_park', '?')}): {t.get('parked_reason', '')}")
            if t.get("notes"):
                lines.append(f"- note: {t['notes']}")
            lines.append("")
    return "\n".join(lines)


def write_markdown(reg: dict, experiments: list[dict] | None = None, path: Path = THEORIES_MD) -> Path:
    atomic_write_text(path, render_markdown(reg, experiments))
    return path
