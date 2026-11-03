"""
Build the dataset files the consolidated dashboard reads (https://claude.ai/artifact/YW11NMqwusSM59jktjYmSW).

    python -m mandel.live.dashboard_export            # writes mandel/live/dashboard/data/*.json

Every file is derived from records the repo already holds: the paper journal and the capture box's pushed status
(state/linode/..., fetched by import_linode), the tracker and evidence-graph outputs (state/tracker), the theory
registry and the ledger. Nothing here is a forecast or a judgement; a number on the dashboard is a count or a sum of
something journaled. Uploading the files as the dashboard's assets and pointing its `datasets/<id>` documents at them
is the operator step described in mandel/live/dashboard/README.md.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from mandel.live import evidence_graph as G
from mandel.live import tracker as T
from mandel.paths import MANDEL_ROOT

OUT = MANDEL_ROOT / "live" / "dashboard" / "data"
JOURNAL = MANDEL_ROOT / "state" / "linode" / "paper_journal" / "journal.jsonl"
WIDE_JOURNAL = T.LINODE_CAPTURE / "wide-journal.jsonl"
STATUS = T.LINODE_CAPTURE / "status.json"
DAILY_LOG = G.DAILY_LOG
LEDGER = G.LEDGER_PATH

RULE_LABEL = {"ibs": "IBS SPYM", "tom": "turn-of-month SPYM"}


# ------------------------------------------------------------------------------------------------ paper sleeve --

def _id_parts(cid: str) -> "tuple[str, str, str] | None":
    """m-<cls|opg>-<SYM>-<YYYY-MM-DD>-<hex> -> (phase, symbol, day)."""
    p = str(cid).split("-")
    if len(p) < 7 or p[0] != "m":
        return None
    return ("close" if p[1] == "cls" else "open"), p[2], "-".join(p[3:6])


def _filled(journal: list[dict]) -> list[dict]:
    """One row per filled stock order, the tracker's rule: the reconcile re-journaled fills before 2026-10-26."""
    by_id = {}
    for r in journal:
        cid = str(r.get("client_order_id", ""))
        if r.get("kind") == "order.fill" and cid.startswith("m-") and not cid.startswith("m-xsp") and r.get("filled_avg_price"):
            by_id[cid] = r
    return sorted(by_id.values(), key=lambda r: str(r.get("filled_at")))


def _rules_by_day(journal: list[dict]) -> dict[str, str]:
    """Which SPYM rule(s) fired at each close, from the decision's own reasons (a firing reason says 'hold')."""
    out = {}
    for r in journal:
        if r.get("kind") == "close.decision":
            fired = [RULE_LABEL[k] for k in ("ibs", "tom") if "hold" in str((r.get("reasons") or {}).get(k, ""))]
            out[str(r.get("day"))] = " + ".join(fired) if fired else "SPYM"
    return out


def _prints(journal: list[dict]) -> dict:
    return {(r.get("symbol"), str(r.get("day"))): r for r in journal if r.get("kind") == "print.official"}


def _official(prints: dict, phase: str, symbol: str, day: str) -> "float | None":
    p = prints.get((symbol, day))
    if not p:
        return None
    return p.get("close") if phase == "close" else p.get("open")


def paper_fills(journal: list[dict]) -> list[dict]:
    prints, rules, out, last_rule = _prints(journal), _rules_by_day(journal), [], {}
    for r in _filled(journal):
        parts = _id_parts(r.get("client_order_id"))
        if not parts:
            continue
        phase, sym, day = parts
        px = float(r["filled_avg_price"])
        if r.get("side") == "buy":
            rule = "overnight QQQM" if sym == "QQQM" else rules.get(day, "SPYM")
            last_rule[sym] = rule
        else:
            rule = last_rule.get(sym, "overnight QQQM" if sym == "QQQM" else "SPYM")
        ref = _official(prints, phase, sym, day)
        out.append({"day": day, "phase": phase, "symbol": sym, "rule": rule, "side": r.get("side"),
                    "qty": int(float(r.get("filled_qty") or 0)), "price": px,
                    "filled_at": str(r.get("filled_at"))[:19].replace("T", " ") + "Z",
                    "official_print": ref, "gap_bp": round(abs(px - ref) / ref * 1e4, 2) if ref else None})
    return out


def round_trips(journal: list[dict]) -> list[dict]:
    """FIFO round trips per symbol, the tracker's accounting (its totals are the test): paper P&L and, where both legs
    have an official print, the same trip at the prints."""
    prints, out, lots = _prints(journal), [], defaultdict(list)
    rules = {(f["day"], f["symbol"], f["phase"]): f["rule"] for f in paper_fills(journal)}
    for r in _filled(journal):
        parts = _id_parts(r.get("client_order_id"))
        if not parts:
            continue
        phase, sym, day = parts
        q, px = float(r.get("filled_qty") or 0), float(r["filled_avg_price"])
        ref = _official(prints, phase, sym, day)
        if r.get("side") == "buy":
            lots[sym].append([q, px, ref, day, rules.get((day, sym, phase), "")])
            continue
        while q > 0 and lots[sym]:
            lot = lots[sym][0]
            take = min(q, lot[0])
            shadow = round(take * (ref - lot[2]), 2) if ref is not None and lot[2] is not None else None
            out.append({"symbol": sym, "rule": lot[4], "entry_day": lot[3], "exit_day": day, "qty": int(take),
                        "entry": lot[1], "exit": px, "pnl_usd": round(take * (px - lot[1]), 2), "shadow_pnl_usd": shadow})
            lot[0] -= take
            q -= take
            if lot[0] <= 0:
                lots[sym].pop(0)
    return out


def paper_sessions(journal: list[dict]) -> list[dict]:
    trips, out, cum = round_trips(journal), [], 0.0
    by_exit = defaultdict(list)
    for t in trips:
        by_exit[t["exit_day"]].append(t)
    for r in journal:
        if r.get("kind") != "close.decision":
            continue
        day = str(r.get("day"))
        snap = next((v for k, v in r.items() if k.startswith("snapshot") and isinstance(v, dict)), {})
        rng = (snap.get("high") or 0) - (snap.get("low") or 0)
        ibs = round(((snap.get("last") or 0) - (snap.get("low") or 0)) / rng, 3) if rng else None
        reasons = r.get("reasons") or {}
        targets = r.get("targets") or {}
        cum += sum(t["pnl_usd"] for t in by_exit.get(day, []))
        out.append({"day": day, "equity_usd": r.get("equity"), "realised_pnl_to_date_usd": round(cum, 2),
                    "round_trips_closed": len(by_exit.get(day, [])), "ibs_15_45": ibs,
                    "ibs_fired": "hold" in str(reasons.get("ibs", "")), "tom_window": "hold" in str(reasons.get("tom", "")),
                    "target_qqqm_usd": targets.get("QQQM"), "target_spym_usd": targets.get("SPYM")})
    return out


# ---------------------------------------------------------------------------------------------- widened sleeves --

def wide_orders(wide: list[dict]) -> list[dict]:
    """w-<SYM>-open|close-<day> (spreads) and w-<cls|opg>-<SYM>-<day>-<hex> (stock): the underlying is never 'cls'."""
    out = []
    for r in wide:
        if r.get("kind") != "order.fill":
            continue
        cid = str(r.get("client_order_id", ""))
        p = cid.split("-")
        if len(p) >= 6 and p[1] in ("cls", "opg"):
            und, kind, side, day = p[2], "stock", r.get("side") or "", "-".join(p[3:6])
        elif len(p) >= 6:
            und, kind, side, day = p[1], "spread", f"{p[2]} spread", "-".join(p[3:6])
        else:
            continue
        px = r.get("filled_avg_price")
        out.append({"order": cid, "underlying": und, "kind": kind, "side": side, "qty": int(float(r.get("qty") or 0)),
                    "price": float(px) if px not in (None, "") else None, "status": r.get("status"), "day": day})
    return sorted(out, key=lambda x: (x["day"], x["order"]))


# ----------------------------------------------------------------------------------------------------- registry --

def registry_status(theories: list[dict]) -> list[dict]:
    c = Counter(str(t.get("status")) for t in theories)
    return [{"status": k, "count": v} for k, v in sorted(c.items(), key=lambda kv: -kv[1])]


def registry_by_kind(theories: list[dict]) -> list[dict]:
    c = Counter((str(t.get("kind")), str(t.get("status"))) for t in theories)
    return [{"kind": k, "status": s, "count": n} for (k, s), n in sorted(c.items())]


def registry_timeline(ledger: list[dict]) -> list[dict]:
    days: dict[str, Counter] = defaultdict(Counter)
    for r in ledger:
        day = str(r.get("ts", ""))[:10]
        if r.get("kind") == "theory.preregistered":
            days[day]["pre"] += 1
        elif r.get("kind") == "experiment.recorded":
            days[day]["exp"] += 1
            days[day][str((r.get("payload") or {}).get("verdict"))] += 1
    out, cum = [], Counter()
    for day in sorted(days):
        cum.update(days[day])
        out.append({"day": day, "preregistered_cum": cum["pre"], "experiments_cum": cum["exp"],
                    "supported_cum": cum["supported"], "not_supported_cum": cum["not_supported"],
                    "inconclusive_cum": cum["inconclusive"], "experiments_today": days[day]["exp"]})
    return out


# -------------------------------------------------------------------------------------------------- capture box --

def capture_health(runs: list[dict]) -> list[dict]:
    out = []
    for r in runs:
        steps = r.get("steps") or []
        bad = [s for s in steps if s.get("rc") != 0]
        first = str((bad[0].get("tail") or [""])[-1]).strip() if bad else ""
        out.append({"day": str(r.get("ts"))[:10], "steps": len(steps), "failed": len(bad), "ok": not bad and bool(steps),
                    "first_error": first[:160]})
    return out


def capture_families(status: dict) -> list[dict]:
    fam = (status or {}).get("families") or {}
    return [{"family": k, "latest": v.get("latest"), "count": v.get("count")} for k, v in sorted(fam.items())]


# --------------------------------------------------------------------------------------------------------- main --

FORWARD_COLS = ("id", "owner", "strategy", "venue", "mode", "started", "unit", "n_now", "n_target", "read_date",
                "pnl_usd", "status", "next_step", "progress")


def forward_tests(rows: list[dict]) -> list[dict]:
    return [{k: r.get(k) for k in FORWARD_COLS} for r in rows]


def build(out: Path = OUT) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    journal = T._journal(JOURNAL) if JOURNAL.exists() else []
    wide = G._jsonl_rows(WIDE_JOURNAL)
    runs = G._jsonl_rows(DAILY_LOG)
    ledger = G._jsonl_rows(LEDGER)
    status = G._load(STATUS, {})
    reg = G._load(G.REGISTRY, {}).get("theories", [])
    reg = reg if isinstance(reg, list) else list(reg.values())
    rows = G._load(G.TRACKER / "strategies.json", [])
    files = {
        "paper_sessions": paper_sessions(journal), "paper_fills": paper_fills(journal),
        "paper_round_trips": round_trips(journal), "wide_orders": wide_orders(wide),
        "children_forward_tests": forward_tests(rows), "strategies": rows,
        "alerts": G._load(G.TRACKER / "alerts.json", []), "next_tests": G._load(G.TRACKER / "next_tests.json", []),
        "registry_status": registry_status(reg), "registry_by_kind": registry_by_kind(reg),
        "registry_timeline": registry_timeline(ledger),
        "capture_health": capture_health(runs), "capture_families": capture_families(status),
    }
    for name, data in files.items():
        (out / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
    return {k: len(v) for k, v in files.items()}


def main(argv=None) -> int:
    print(json.dumps(build()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
