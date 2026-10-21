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
LINODE_CAPTURE = MANDEL_ROOT / "state" / "linode" / "capture_status"      # the capture box's pushed records (import_linode)

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
    "T-565": {"strategy": "Shadow: HMM regime filter for putwriting", "venue": "record only (Linode)", "mode": "forward",
              "unit": "month-end decisions", "n_target": 36, "decision": "drawdown -30% vs always-PUT, Sharpe cost <= 0.05"},
    "T-566": {"strategy": "Shadow: HMM volatility scaling of QQQM overnight", "venue": "record only (Linode)", "mode": "forward",
              "unit": "weighted nights", "n_target": 200, "decision": "Sharpe gain lower bound > 0 on T-559's fills"},
    "T-573": {"strategy": "Shadow: EWMA volatility scaling of QQQM overnight", "venue": "record only (Linode)", "mode": "forward",
              "unit": "weighted nights", "n_target": 200, "decision": "Sharpe gain lower bound > 0 on T-559's fills"},
    "T-576": {"strategy": "IEF over the month's last session (Treasury month-end)", "venue": "Alpaca paper", "mode": "paper",
              "unit": "month-end holds", "n_target": 24, "decision": "fills <= 1.5 bp at 10; mean net > 0 at 24"},
    "T-567": {"strategy": "Pre-holiday IWM (1-day hold)", "venue": "Alpaca paper", "mode": "paper",
              "unit": "holiday events", "n_target": 27, "decision": "fills <= 1.5 bp at 10 events; mean net > 0 at 27"},
    "T-568": {"strategy": "GLD / TLT / USO put spreads (9-24 day holds)", "venue": "Alpaca paper", "mode": "paper",
              "unit": "closed spreads", "n_target": 36, "decision": "mean P&L per spread > 0, no loss beyond max"},
}
REGISTERED = {"T-541": "2026-10-15", "T-542": "2026-10-14", "T-543": "2026-10-15", "T-559": "2026-10-20", "T-560": "2026-10-20",
              "T-565": "2026-10-20", "T-566": "2026-10-20", "T-567": "2026-10-20", "T-568": "2026-10-20", "T-573": "2026-10-20", "T-576": "2026-10-20"}


def _registry() -> dict:
    # Read the file directly: mandel.experiments.run imports numpy, which the paper box does not install.
    path = MANDEL_ROOT / "theories" / "registry.json"
    th = (json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}).get("theories", [])
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
    expired = sum(1 for r in journal if r.get("kind") == "order.fill" and str(r.get("client_order_id", "")).startswith("m-")
                  and not str(r.get("client_order_id", "")).startswith("m-xsp") and r.get("status") == "expired")
    last = [r for r in journal if r.get("kind") == "close.decision"][-1:]
    old_code = bool(last and "SPLG" in (last[0].get("targets") or {}))        # the pre-2026-10-21 runner (SPLG, auction orders)
    return {"n_now": len(days), "fills": len(fills), "rejected": rejected, "expired": expired, "old_code": old_code,
            "pnl_usd": round(pnl, 2) if fills else None}


def spread_progress(journal: list[dict]) -> dict:
    opened = [r for r in journal if r.get("kind") == "order.sent" and str((r.get("order") or {}).get("client_order_id", "")).startswith("m-xsp-open")]
    closed = [r for r in journal if r.get("kind") == "order.sent" and str((r.get("order") or {}).get("client_order_id", "")).startswith("m-xsp-close")]
    plans = [r for r in journal if r.get("kind") == "spread.plan"]
    last = plans[-1]["reason"] if plans else None
    expired = sum(1 for r in journal if r.get("kind") == "order.fill" and str(r.get("client_order_id", "")).startswith("m-xsp-open")
                  and r.get("status") == "expired")
    filled = sum(1 for r in journal if r.get("kind") == "order.fill" and str(r.get("client_order_id", "")).startswith("m-xsp-open")
                 and r.get("status") == "filled")
    return {"n_now": len(closed), "opened": len(opened), "filled": filled, "expired": expired, "last_plan": last}


def linode_progress(base: Path = LINODE_CAPTURE) -> dict:
    """The capture box's own records: shadow lines per test, the wide sleeve's decisions and fills, chain capture days."""
    shadow = _jsonl(base / "shadow.jsonl")
    wide = _jsonl(base / "wide-journal.jsonl")
    out = {}
    for tid in ("T-565", "T-566", "T-573"):
        days = sorted({r.get("day") for r in shadow if r.get(tid)})
        out[tid] = {"n_now": len(days), "first": days[0] if days else None, "last": days[-1] if days else None}
    dec = [r for r in wide if r.get("kind") == "close.decision"]
    for tid, flag in (("T-567", "pre_holiday_next"), ("T-576", "month_end_next")):
        out[tid] = {"days": len({r.get("day") for r in dec}), "n_now": sum(1 for r in dec if r.get(flag)),
                    "last": dec[-1].get("day") if dec else None}
    fills = [r for r in wide if r.get("kind") == "order.fill" and "-open-" in str(r.get("client_order_id", ""))]
    out["T-568"] = {"filled": sum(1 for r in fills if r.get("status") == "filled"),
                    "expired": sum(1 for r in fills if r.get("status") == "expired"),
                    "n_now": sum(1 for r in wide if r.get("kind") == "order.fill" and "-close-" in str(r.get("client_order_id", ""))
                                 and r.get("status") == "filled")}
    try:
        fam = json.loads((base / "status.json").read_text()).get("families", {})
    except (OSError, ValueError):
        fam = {}
    out["chains"] = {s: fam.get(f"options-chain-{s}") for s in ("SPX", "VIX")}
    return out


def _jsonl(p: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    except OSError:
        return []


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


def build(today: date, journal_path: Path, out: Path = OUT) -> list[dict]:
    reg = _registry()
    journal = _journal(journal_path)
    bundles = _bundles()
    arch = archive_progress(bundles, today)
    cal, spr = calendar_progress(journal), spread_progress(journal)
    box = linode_progress()
    rows = []
    for tid, m in MANDEL_TESTS.items():
        t = reg.get(tid, {})
        row = {"id": tid, "owner": "Mandel", "strategy": m["strategy"], "venue": m["venue"], "mode": m["mode"],
               "registry_status": t.get("status"), "unit": m["unit"], "n_target": m["n_target"], "decision": m["decision"],
               "started": REGISTERED.get(tid), "read_date": None, "pnl_usd": None, "fills": None, "verified": "Mandel records",
               "source": "theory registry"}
        if tid == "T-559":
            blocked = cal["n_now"] and not cal["fills"] and (cal["rejected"] or cal["expired"])
            row.update(n_now=cal["n_now"] if cal["fills"] else 0, fills=cal["fills"], pnl_usd=cal["pnl_usd"], capital_usd=None,
                       status=(f"waiting: {cal['n_now']} session(s) decided, {cal['rejected']} order(s) rejected and {cal['expired']} "
                               "expired, 0 filled (SPLG renamed SPYM; paper runs no auction)" if blocked else
                               "running" if cal["n_now"] else ("installed: first close orders at the next 3:44 pm ET close" if journal
                                                                else "waiting on the Linode install")),
                       next_step=("re-pin the Linode paper checkout to the fixed commit (deploy/paper/install.sh with PIN)"
                                  if blocked and cal["old_code"] else "run deploy/paper/install.sh on the Linode"
                                  if not (cal["n_now"] or journal) else "reconcile fills daily"),
                       started=None if not cal["n_now"] else REGISTERED[tid], source="paper journal")
        elif tid == "T-560":
            row.update(n_now=spr["n_now"], status=(f"running: {spr['opened']} opening order(s), {spr['filled']} filled, "
                                                   f"{spr['expired']} expired at the mid" if spr["opened"] else
                                                   ("installed: waiting for a qualifying spread" if journal else "waiting on the Linode install")),
                       next_step=spr["last_plan"] or "first plan at 15:20 ET once installed",
                       started=None if not spr["opened"] else REGISTERED[tid], source="paper journal")
        elif tid in ("T-541", "T-542"):
            sym = "SPX" if tid == "T-542" else "VIX"
            boxed = box["chains"].get(sym) or {}
            last = max(filter(None, (arch[tid].get("last"), boxed.get("latest"))), default=None)
            stale = _days_since(last, today)
            n = arch[tid]["n_now"] if tid == "T-542" else 0
            row.update(n_now=n, status=(f"stalled: last capture {last}" if stale is None or stale > 3 else
                                        f"recording: chains captured through {last} ({boxed.get('count', 0)} on the box)"),
                       next_step=("restart the daily options capture on the Linode (options-fetch job)" if stale is None or stale > 3 else
                                  "none: the capture box records daily" if tid == "T-542" else
                                  "first settlements follow the November VIX expiry"),
                       source="capture box + archive captures")
        elif tid in ("T-565", "T-566", "T-573"):
            p = box[tid]
            installed = (out / "capture_status.json").exists()
            row.update(n_now=p["n_now"], status=(f"recording: {p['n_now']} shadow day(s), first {p['first']}" if p["n_now"] else
                                                 "installed: first record after tonight's run" if installed else
                                                 "waiting on the Linode capture install"),
                       next_step="none: runs on its timers" if installed else "run deploy/capture/install.sh on the Linode",
                       started=p["first"], source="capture box shadow.jsonl")
        elif tid in ("T-567", "T-576"):
            p = box[tid]
            row.update(n_now=p["n_now"], status=(f"running: {p['days']} session(s) decided, {p['n_now']} signal day(s) so far"
                                                 if p["days"] else "installed: first record after tonight's run"),
                       next_step="none: runs on its timers", started=REGISTERED.get(tid) if p["days"] else None,
                       source="capture box wide-journal.jsonl")
        elif tid == "T-568":
            p = box[tid]
            row.update(n_now=p["n_now"], fills=p["filled"], status=(f"running: {p['filled']} spread(s) open, {p['expired']} opening "
                                                                    "order(s) expired at the mid" if (p["filled"] or p["expired"])
                                                                    else "installed: first record after tonight's run"),
                       next_step="none: runs on its timers", started=REGISTERED.get(tid) if p["filled"] else None,
                       source="capture box wide-journal.jsonl")
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
        r["state"] = ("stalled" if "stalled" in st else "waiting" if "waiting" in st else "proposed" if "proposed" in st else "running")
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
