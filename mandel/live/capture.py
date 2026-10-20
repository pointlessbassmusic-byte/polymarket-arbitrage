"""
Linode data captures: Mandel's daily and weekly fetches, run where they can run every day, with the raw data kept there.
=======================================================================================================================

    python -m mandel.live.capture daily     # after the US close: CBOE chains + surfaces, Deribit books, histories, social
    python -m mandel.live.capture weekly    # Sunday: the slower histories (Yahoo OHLC, factors, FOMC, Deribit, VX, AQR)
    python -m mandel.live.capture score     # forward-test statistics that need the raw chains (T-542's parity share)
    python -m mandel.live.capture status    # a data-free summary: newest day and count per bundle family

Run with MANDEL_ARCHIVE_ROOT and MANDEL_DATA_ROOT pointing outside the checkout (deploy/capture/install.sh sets both),
so the pinned checkout never changes. Raw chains are Cboe's delayed data and stay on the box (in_git=False). Only
``status.json`` and ``scores.json`` (names, dates, counts and statistics; no rows) are pushed, to branch
capture/status, for Mandel to read. Every step runs even if an earlier one fails; failures are recorded in status.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mandel.paths import DATA_ROOT

DAILY = [["options-fetch"], ["options-fetch", "--smile"], ["options-fetch", "--history"], ["social-fetch"],
         ["book-snapshot"]]
WEEKLY = [["unlock-fetch", "all"],
          ["-c", "from mandel.archive import Archive; from mandel.data.cboe_strategy import fetch_cboe_strategy as f; "
                 "f(Archive(), symbols=['PUT', 'BXM'])"]]       # the PUT index for T-565's forward read
OUT = Path(os.environ.get("MANDEL_CAPTURE_OUT") or (DATA_ROOT / "capture"))
_DATED = re.compile(r"^(?P<family>.+?)-(?P<day>\d{4}-\d{2}-\d{2})$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_steps(steps: list, log_name: str) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for args in steps:
        t0 = time.time()
        cmd = [sys.executable, *args] if args[0] == "-c" else [sys.executable, "-m", "mandel", *args]
        p = subprocess.run(cmd, capture_output=True, text=True)
        tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
        results.append({"step": " ".join(args)[:120], "rc": p.returncode, "seconds": round(time.time() - t0, 1), "tail": tail})
        print(f"{' '.join(args)}: rc {p.returncode} in {time.time() - t0:.0f}s")
    with open(OUT / log_name, "a") as f:
        f.write(json.dumps({"ts": _now(), "steps": results}) + "\n")
    return results


def status() -> dict:
    """Newest day and count per dated bundle family, created_at of undated bundles, plus the last run's step results."""
    from mandel.archive import Archive
    entries = {e.name: {"bytes": e.bytes, "created_at": e.created_at} for e in Archive().entries()}
    fams: dict = {}
    undated: dict = {}
    for name, e in entries.items():
        m = _DATED.match(name)
        if m:
            f = fams.setdefault(m.group("family"), {"latest": "", "count": 0, "bytes": 0})
            f["latest"] = max(f["latest"], m.group("day")); f["count"] += 1; f["bytes"] += int(e.get("bytes") or 0)
        else:
            undated[name] = str(e.get("created_at", ""))[:19]
    last = {}
    for log in ("daily.jsonl", "weekly.jsonl"):
        p = OUT / log
        if p.exists():
            lines = p.read_text().splitlines()
            if lines:
                last[log.split(".")[0]] = json.loads(lines[-1])
    st = {"as_of": _now(), "families": fams, "undated": undated, "last_runs": last}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.json").write_text(json.dumps(st, indent=1))
    return st


def score() -> dict:
    """T-542's per-day parity share on every capture day this box holds (T-505's parity_v2), written to scores.json.
    The two capture days before the box existed (2026-10-14: 2.2%, 2026-10-15: 0.5%) are in T-542's registration."""
    from mandel.archive import Archive
    from mandel.experiments import options_market as om
    from mandel.experiments.run import _chain_captures
    a = Archive()
    out = {"as_of": _now()}
    try:
        rep = om.parity_v2(_chain_captures(a, "SPX"), a.load("fred-DTB3"))
        out["T-542"] = {k: rep.get(k) for k in ("n_days", "verdict", "reason", "per_day", "days")} | {
            "note": "parity_v2 (T-505's construction) on this box's captures; T-542 counts days below 2% among the first 20"}
    except Exception as e:                                       # recorded, not raised: the other scores still run
        out["T-542"] = {"error": f"{type(e).__name__}: {e}"[:400]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scores.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.live.capture")
    ap.add_argument("what", choices=["daily", "weekly", "score", "status"])
    a = ap.parse_args(argv)
    if a.what == "daily":
        run_steps(DAILY, "daily.jsonl"); status()
    elif a.what == "weekly":
        run_steps(WEEKLY, "weekly.jsonl"); status()
    elif a.what == "score":
        print(json.dumps(score(), default=str)[:2000])
    else:
        st = status()
        print(json.dumps({k: v for k, v in st["families"].items()}, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
