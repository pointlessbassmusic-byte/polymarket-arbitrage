"""
Paper-strategy tracker: one row per paper, live or forward test, Mandel's and the children's.
==============================================================================================

    python -m mandel.live.tracker [--journal PATH] [--out DIR]

Writes ``strategies.json`` (one row per test, the dashboard's table) and appends today's progress to
``history.jsonl`` (one row per test per day, the dashboard's progress chart). Sources, read-only:

  * Mandel's forward tests from the theory registry (status, decision rule) plus what each one counts:
    the paper journal for T-559 / T-560 (sessions, fills, fill gap vs the modelled price, realised P&L),
    archived option-chain capture days for T-541 / T-542, event days since registration for T-543;
  * the children's tests from ``state/children/forward_tests.json`` (their own figures, unverified).

The journal defaults to MANDEL_PAPER_STATE/journal.jsonl; point --journal at a copy of the Linode's journal.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

from mandel.paths import MANDEL_ROOT

OUT = MANDEL_ROOT / "state" / "tracker"
CHILD_TESTS = MANDEL_ROOT / "state" / "children" / "forward_tests.json"
ARCHIVE_INDEX = MANDEL_ROOT / "archive" / "INDEX.json"

# Mandel's own forward tests: what each counts toward its decision point.
MANDEL_TESTS = {
    "T-559": {"strategy": "Calendar sleeve (overnight QQQM, IBS, turn of month)", "venue": "Alpaca paper", "mode": "paper",
              "unit": "sessions", "n_target": 60, "decision": "fill gap <= 1.5 bp/side at 60 sessions; return at 250"},
    "T-560": {"strategy": "XSP put credit spread, trend-filtered", "venue": "Alpaca paper", "mode": "paper",
              "unit": "monthly cycles", "n_target": 12, "decision": "mean P&L per spread > 0 after 12 cycles"},
    "T-542": {"strategy": "SPX put-call parity band", "venue": "Cboe delayed chains", "mode": "forward",
              "unit": "capture days", "n_target": 20, "decision": ">= 16 of the first 20 days below 2%"},
    "T-541": {"strategy": "VIX call spreads at captured mids", "venue": "Cboe delayed chains", "mode": "forward",
              "unit": "settled spreads", "n_target": 200, "decision": "upper CI < 0 with a stress month"},
    "T-543": {"strategy": "BTC event-day straddle (FOMC, CPI)", "venue": "Deribit DVOL (model)", "mode": "forward",
              "unit": "event days", "n_target": 30, "decision": "event-day minus other-day P&L < 0, CI excludes 0"},
}
REGISTERED = {"T-541": "2026-10-15", "T-542": "2026-10-14", "T-543": "2026-10-15", "T-559": "2026-10-20", "T-560": "2026-10-20"}


def _registry() -> dict:
    from mandel.experiments.run import load_registry
    th = (load_registry() or {}).get("theories", [])
    return {t.get("id"): t for t in th} if isinstance(th, list) else th


def _journal(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return [r for r in out if not r.get("dry_run")]


def _bundles() -> dict:
    try:
        return json.loads(ARCHIVE_INDEX.read_text())["bundles"]
    except (OSError, ValueError, KeyError):
        return {}


def _rows_of(bundles: dict, name: str) -> list[dict]:
    b = bundles.get(name)
    if not b:
        return []
    p = MANDEL_ROOT.parent / b["path"]
    if not p.exists():
        return []
    with gzip.open(p, "rt") as f:
        return [json.loads(line) for line in f]


def calendar_progress(journal: list[dict]) -> dict:
    """T-559 from the journal: sessions decided, fills, mean fill gap vs the modelled (snapshot) price, P&L."""
    days = {str(r.get("day")) for r in journal if r.get("kind") == "close.decision"}
    fills = [r for r in journal if r.get("kind") == "order.fill" and str(r.get("client_order_id", "")).startswith("m-")
             and not str(r.get("client_order_id", "")).startswith("m-xsp") and r.get("filled_avg_price")]
    rejected = sum(1 for r in journal if r.get("kind") == "order.rejected")
    # Realised P&L from fills: sells minus buys, per symbol, over closed round trips (FIFO by quantity).
    pnl, book = 0.0, {}
    for r in sorted(fills, key=lambda r: str(r.get("filled_at"))):
        q, px, sym = float(r.get("filled_qty") or 0), float(r["filled_avg_price"]), r.get("symbol")
        lots = book.setdefault(sym, [])
        if r.get("side") == "buy":
            lots.append([q, px])
        else:
            while q > 0 and lots:
                take = min(q, lots[0][0])
                pnl += take * (px - lots[0][1])
                lots[0][0] -= take; q -= take
                if lots[0][0] <= 0:
                    lots.pop(0)
    return {"n_now": len(days), "fills": len(fills), "rejected": rejected, "pnl_usd": round(pnl, 2) if fills else None}


def spread_progress(journal: list[dict]) -> dict:
    opened = [r for r in journal if r.get("kind") == "order.sent" and str((r.get("order") or {}).get("client_order_id", "")).startswith("m-xsp-open")]
    closed = [r for r in journal if r.get("kind") == "order.sent" and str((r.get("order") or {}).get("client_order_id", "")).startswith("m-xsp-close")]
    plans = [r for r in journal if r.get("kind") == "spread.plan"]
    last = plans[-1]["reason"] if plans else None
    return {"n_now": len(closed), "opened": len(opened), "last_plan": last}


def archive_progress(bundles: dict, today: date) -> dict:
    spx = sorted(k for k in bundles if k.startswith("options-chain-SPX-"))
    vix = sorted(k for k in bundles if k.startswith("options-chain-VIX-"))
    since = date.fromisoformat(REGISTERED["T-543"])
    events = set()
    for r in _rows_of(bundles, "fomc-meetings"):
        d = (r.get("value") or {}).get("decision_day")
        if d and since < date.fromisoformat(d) <= today:
            events.add(d)
    for r in _rows_of(bundles, "macro-release-cpi"):
        d = (r.get("value") or {}).get("day")
        if d and since < date.fromisoformat(d) <= today:
            events.add(d)
    upcoming = sorted(((r.get("value") or {}).get("decision_day") for r in _rows_of(bundles, "fomc-meetings")
                       if ((r.get("value") or {}).get("decision_day") or "") > today.isoformat()))
    return {"T-542": {"n_now": len(spx), "last": spx[-1][-10:] if spx else None},
            "T-541": {"n_now": 0, "captures": len(vix), "last": vix[-1][-10:] if vix else None},
            "T-543": {"n_now": len(events), "next_fomc": upcoming[0] if upcoming else None}}


def _days_since(d: Optional[str], today: date) -> Optional[int]:
    return (today - date.fromisoformat(d)).days if d else None


def build(today: date, journal_path: Path) -> list[dict]:
    reg = _registry()
    journal = _journal(journal_path)
    bundles = _bundles()
    arch = archive_progress(bundles, today)
    cal, spr = calendar_progress(journal), spread_progress(journal)
    rows = []
    for tid, m in MANDEL_TESTS.items():
        t = reg.get(tid, {})
        row = {"id": tid, "owner": "Mandel", "strategy": m["strategy"], "venue": m["venue"], "mode": m["mode"],
               "registry_status": t.get("status"), "unit": m["unit"], "n_target": m["n_target"], "decision": m["decision"],
               "started": REGISTERED.get(tid), "read_date": None, "pnl_usd": None, "fills": None, "verified": "Mandel records",
               "source": "theory registry"}
        if tid == "T-559":
            row.update(n_now=cal["n_now"], fills=cal["fills"], pnl_usd=cal["pnl_usd"], capital_usd=None,
                       status="running" if cal["n_now"] else "waiting on the Linode install",
                       next_step="run deploy/paper/install.sh on the Linode" if not cal["n_now"] else "reconcile fills daily",
                       started=None if not cal["n_now"] else REGISTERED[tid], source="paper journal")
        elif tid == "T-560":
            row.update(n_now=spr["n_now"], status="running" if spr["opened"] else "waiting on the Linode install",
                       next_step=spr["last_plan"] or "first plan at 15:20 ET once installed",
                       started=None if not spr["opened"] else REGISTERED[tid], source="paper journal")
        elif tid == "T-542":
            stale = _days_since(arch["T-542"]["last"], today)
            row.update(n_now=arch["T-542"]["n_now"], status=f"stalled: last capture {arch['T-542']['last']}" if stale and stale > 3 else "recording",
                       next_step="restart the daily options capture on the Linode (options-fetch job)", source="archive captures")
        elif tid == "T-541":
            row.update(n_now=0, status=f"stalled: {arch['T-541']['captures']} capture days, last {arch['T-541']['last']}",
                       next_step="restart the daily options capture; first settlements follow the Nov VIX expiry", source="archive captures")
        elif tid == "T-543":
            row.update(n_now=arch["T-543"]["n_now"], status="recording",
                       next_step=f"next FOMC {arch['T-543']['next_fomc']}", source="archive calendars")
        rows.append(row)
    child = json.loads(CHILD_TESTS.read_text())
    for t in child["tests"]:
        rows.append({**{k: t.get(k) for k in ("id", "owner", "strategy", "venue", "mode", "unit", "n_now", "n_target", "read_date",
                                              "pnl_usd", "status", "next_step", "decision", "started", "capital_usd")},
                     "registry_status": None, "fills": None,
                     "verified": f"child's own figures as of {child['as_of']}" + (f"; Mandel check {t['mandel_check']}" if t.get("mandel_check") else ""),
                     "source": t.get("source")})
    for r in rows:
        if r.get("n_now") is None and r.get("unit") == "days" and r.get("started"):
            r["n_now"] = _days_since(r["started"], today)          # a dated forward record counts elapsed days
        st = (r.get("status") or "").lower()
        r["state"] = ("stalled" if "stalled" in st else "waiting" if "waiting" in st else "running")
        r["group"] = {"live": "Live money", "paper": "Paper", "forward": "Forward record"}[r["mode"]]
        r["progress"] = round(min(1.0, r["n_now"] / r["n_target"]), 4) if r.get("n_now") is not None and r.get("n_target") else None
        r["days_to_read"] = (date.fromisoformat(r["read_date"]) - today).days if r.get("read_date") else None
        r["as_of"] = today.isoformat()
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m mandel.live.tracker")
    p.add_argument("--journal", type=Path, default=Path(os.environ.get("MANDEL_PAPER_STATE") or (MANDEL_ROOT / "state" / "paper")) / "journal.jsonl")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--today", type=date.fromisoformat, default=date.today())
    a = p.parse_args(argv)
    rows = build(a.today, a.journal)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "strategies.json").write_text(json.dumps(rows, indent=1))
    hist = a.out / "history.jsonl"
    old = [json.loads(x) for x in hist.read_text().splitlines()] if hist.exists() else []
    old = [h for h in old if h["day"] != a.today.isoformat()]
    old += [{"day": a.today.isoformat(), "id": r["id"], "owner": r["owner"], "n_now": r["n_now"], "progress": r["progress"],
             "pnl_usd": r["pnl_usd"]} for r in rows]
    hist.write_text("".join(json.dumps(h) + "\n" for h in old))
    (a.out / "history.json").write_text(json.dumps(old, indent=1))       # the same rows as one JSON array, for upload
    print(f"{len(rows)} tests -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
