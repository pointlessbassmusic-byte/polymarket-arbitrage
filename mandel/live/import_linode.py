"""
Pull the Linode's results into the tracker: the paper runner's journal (branch paper/journal) and the capture box's
summaries (branch capture/status: status.json, scores.json, calibration.json, shadow.jsonl, wide-journal.jsonl).

    python -m mandel.live.import_linode [--today YYYY-MM-DD]

Fetches both branches, copies their files to state/linode/<branch>/, writes state/tracker/capture_status.json and
calibration.json for the evidence graph, then rebuilds the tracker (with the paper journal) and the evidence graph.
Read-only on GitHub; the files hold no raw market data.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

from mandel.paths import MANDEL_ROOT

REPO = MANDEL_ROOT.parent
DEST = MANDEL_ROOT / "state" / "linode"
TRACKER = MANDEL_ROOT / "state" / "tracker"
BRANCHES = ("paper/journal", "capture/status")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True, text=True).stdout


def fetch() -> dict:
    out = {}
    for b in BRANCHES:
        try:
            _git("fetch", "-q", "origin", b)
        except subprocess.CalledProcessError:
            out[b] = []
            continue
        files = [f for f in _git("ls-tree", "--name-only", f"origin/{b}").split() if f]
        d = DEST / b.replace("/", "_")
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            (d / f).write_text(_git("show", f"origin/{b}:{f}"))
        out[b] = files
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.live.import_linode")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    a = ap.parse_args(argv)
    got = fetch()
    cap = DEST / "capture_status"
    for name, target in (("status.json", "capture_status.json"), ("calibration.json", "calibration.json")):
        if (cap / name).exists():
            TRACKER.mkdir(parents=True, exist_ok=True)
            shutil.copy(cap / name, TRACKER / target)
    from mandel.live import evidence_graph, tracker
    journal = DEST / "paper_journal" / "journal.jsonl"
    tracker.main(["--today", a.today.isoformat(), "--journal", str(journal)])
    print(json.dumps(evidence_graph.run(a.today)))
    print(json.dumps(got))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
