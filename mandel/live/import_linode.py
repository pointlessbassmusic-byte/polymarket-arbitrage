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
BRANCHES = ("paper/journal", "capture/status", "live/journal")


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


def mirror_live_arming(journal: Path, ledger=None) -> int:
    """Copy the live runner's 'live.armed' and 'live.halted' rows into Mandel's ledger, once each, with actor "human":
    the switch those rows record exists only because the user wrote it into /etc/mandel-live.env (MANDEL.md rule 13 and
    the executor rule: no ledger event that changes live-money configuration lacks actor="human"). Returns rows added."""
    from mandel.ledger import Ledger
    if not journal.exists():
        return 0
    led = Ledger() if ledger is None else ledger        # an empty Ledger is falsy: never `ledger or Ledger()`
    seen = {(e.kind, (e.payload or {}).get("box_ts")) for e in led._iter_raw() if e.kind in ("live.armed", "live.halted")}
    n = 0
    for line in journal.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("kind") not in ("live.armed", "live.halted") or r.get("dry_run"):
            continue
        if r["kind"] == "live.armed" and not r.get("switch"):
            continue                                   # a read-only run before the switch is not an arming
        if (r["kind"], r.get("ts")) in seen:
            continue
        payload = {k: v for k, v in r.items() if k not in ("ts", "kind", "dry_run")}
        payload["box_ts"] = r.get("ts")
        payload["source"] = "live journal (branch live/journal); the switch was written by the user on the Linode"
        led.append(r["kind"], payload, actor="human")
        seen.add((r["kind"], r.get("ts")))
        n += 1
    return n


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
    live_journal = DEST / "live_journal" / "journal.jsonl"
    mirrored = mirror_live_arming(live_journal)
    tracker.main(["--today", a.today.isoformat(), "--journal", str(journal), "--live-journal", str(live_journal)])
    print(json.dumps(evidence_graph.run(a.today)))
    print(json.dumps({**got, "live_rows_mirrored_to_ledger": mirrored}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
