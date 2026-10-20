"""Every archive bundle stored with in_git=False must be ignored by git, so a routine `git add -A` cannot republish data
whose licence forbids it (the repo is public). The INDEX entry and recipe stay committed."""

import json
import shutil
import subprocess

import pytest

from mandel.paths import MANDEL_ROOT

REPO = MANDEL_ROOT.parent


def _entries():
    idx = json.loads((MANDEL_ROOT / "archive" / "INDEX.json").read_text(encoding="utf-8"))["bundles"]
    return list(idx.values()) if isinstance(idx, dict) else idx


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="needs a git checkout")
def test_local_only_bundles_are_git_ignored():
    local = [e["path"] for e in _entries() if e.get("in_git") is False]
    if not local:
        pytest.skip("no local-only bundles in the INDEX")
    out = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=REPO, input="\n".join(local),
                         capture_output=True, text=True).stdout.split()
    assert sorted(set(local) - set(out)) == []


def test_cboe_strategy_bundles_are_listed_in_gitignore():
    from mandel.data.cboe_strategy import STRATEGY_INDICES
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    missing = [s for s in STRATEGY_INDICES if f"mandel/archive/data/cboe-{s}-history.jsonl.gz" not in ignore]
    assert missing == []
