"""
Command line for Mandel's substrate: ``python -m mandel <command>``.

Commands
--------
  status                      ledger integrity, counts of insights / proposals / forecasts / children
  insights [--status S] [--tag T] [--grep RX]
  insight-add TEXT --kind K --prov P [--prov P2] --conf C [--tag T]
  proposals [--status S]
  proposal-show ID
  forecasts                   scoreboard by source
  children                    registry
  names [N]                   suggest names for new children
  ledger [--kind PREFIX] [-n N]
  cycles                      improvement cycles and gains-per-cost efficiency
  ingest                      turn knowledge/*.md "adopts / skeptical / design" bullets into candidate insights
  verify                      recompute the hash chain
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from mandel import __version__
from mandel.children import ChildRegistry
from mandel.forecasts import ForecastBook
from mandel.ledger import Ledger
from mandel.paths import DATA_ROOT, KNOWLEDGE_ROOT
from mandel.proposals import ProposalBook
from mandel.store import InsightStore
from mandel.ingest import ingest_knowledge
from mandel.cycles import CycleLog


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_status(_args) -> int:
    ledger = Ledger()
    ok, msg = ledger.verify()
    store = InsightStore(ledger=ledger)
    props = ProposalBook(ledger=ledger)
    fb = ForecastBook(ledger=ledger)
    reg = ChildRegistry(ledger=ledger)
    sources = sorted(p.name for p in (KNOWLEDGE_ROOT / "sources").glob("*.md")) if (KNOWLEDGE_ROOT / "sources").exists() else []
    adjacent = sorted(p.name for p in (KNOWLEDGE_ROOT / "adjacent").glob("*.md")) if (KNOWLEDGE_ROOT / "adjacent").exists() else []
    _print({
        "mandel": __version__,
        "data_root": str(DATA_ROOT),
        "ledger": {"events": len(ledger), "integrity": msg, "ok": ok},
        "insights": store.summary(),
        "proposals": props.summary(),
        "forecasts": {"recorded": len(fb.forecasts), "resolved": len(fb.resolutions), "open": len(fb.open_questions()),
                      "scoreboard": [s.as_dict() for s in fb.scoreboard()]},
        "children": [{"name": c.name, "status": c.status, "domain": c.domain, "reports": c.report_count,
                      "guidance": c.guidance_count, "last_contact": c.last_contact} for c in reg.all()],
        "cycles": CycleLog(ledger=ledger).efficiency(),
        "knowledge": {"sources": len(sources), "adjacent": len(adjacent),
                      "synthesis": (KNOWLEDGE_ROOT / "SYNTHESIS.md").exists()},
    })
    return 0 if ok else 1


def cmd_insights(args) -> int:
    store = InsightStore()
    rows = store.query(status=args.status, tag=args.tag, text_regex=args.grep)
    for i in rows:
        print(f"{i.id}  [{i.status:9}] c={i.confidence:.2f} {i.kind:9} {i.text}  <- {', '.join(i.provenance)}")
    print(f"({len(rows)} insights)")
    return 0


def cmd_insight_add(args) -> int:
    store = InsightStore()
    ins = store.add(args.text, args.kind, args.prov, args.conf, tags=args.tag or [], notes=args.notes or "")
    _print(asdict(ins))
    return 0


def cmd_proposals(args) -> int:
    book = ProposalBook()
    for p in book.query(status=args.status):
        print(f"{p.id}  [{p.status:13}] {p.title}  -> {p.target}  (trials={p.n_trials_declared})")
    print(f"({len(book.all())} total)")
    return 0


def cmd_proposal_show(args) -> int:
    _print(asdict(ProposalBook().get(args.id)))
    return 0


def cmd_forecasts(_args) -> int:
    fb = ForecastBook()
    board = fb.scoreboard()
    if not board:
        print("no resolved forecasts yet")
    for s in board:
        skill = "n/a" if s.skill_vs_market is None else f"{s.skill_vs_market:+.3f}"
        print(f"{s.source:28} n={s.n:4d} brier={s.brier:.4f} logloss={s.log_loss:.4f} ece={s.ece:.3f} skill_vs_market={skill}")
    print(f"open questions: {len(fb.open_questions())}")
    return 0


def cmd_children(_args) -> int:
    reg = ChildRegistry()
    for c in reg.all():
        print(f"{c.name:12} [{c.status:8}] {c.domain:24} reports={c.report_count} guidance={c.guidance_count} session={c.session_id}")
    if not reg.all():
        print("no children registered yet; try `python -m mandel names`")
    return 0


def cmd_names(args) -> int:
    for name, why in ChildRegistry().suggest_names(args.n):
        print(f"{name:12} {why}")
    return 0


def cmd_ledger(args) -> int:
    ledger = Ledger()
    evs = ledger.events(kind=args.kind)
    for e in evs[-args.n:]:
        print(f"{e.seq:5d} {e.ts[:19]} {e.actor:16} {e.kind:24} {json.dumps(e.payload, default=str)[:120]}")
    return 0


def cmd_cycles(_args) -> int:
    log = CycleLog()
    for c in log.all():
        state = "open" if c.open else "done"
        print(f"{c.id}  [{state}] {c.started_at[:19]}  gains={c.gains()}  cost={c.cost}  {c.goal}")
    _print(log.efficiency())
    return 0


def cmd_ingest(_args) -> int:
    rep = ingest_knowledge(InsightStore())
    _print({"files": rep.files, "added": rep.added, "skipped_existing": rep.skipped_existing, "per_file": rep.per_file})
    return 0


def cmd_verify(_args) -> int:
    ok, msg = Ledger().verify()
    print(msg)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mandel", description="Mandel self-improving predictive substrate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    p = sub.add_parser("insights")
    p.add_argument("--status"); p.add_argument("--tag"); p.add_argument("--grep")
    p.set_defaults(fn=cmd_insights)

    p = sub.add_parser("insight-add")
    p.add_argument("text"); p.add_argument("--kind", required=True)
    p.add_argument("--prov", action="append", required=True); p.add_argument("--conf", type=float, required=True)
    p.add_argument("--tag", action="append"); p.add_argument("--notes")
    p.set_defaults(fn=cmd_insight_add)

    p = sub.add_parser("proposals"); p.add_argument("--status"); p.set_defaults(fn=cmd_proposals)
    p = sub.add_parser("proposal-show"); p.add_argument("id"); p.set_defaults(fn=cmd_proposal_show)
    sub.add_parser("forecasts").set_defaults(fn=cmd_forecasts)
    sub.add_parser("children").set_defaults(fn=cmd_children)
    p = sub.add_parser("names"); p.add_argument("n", nargs="?", type=int, default=5); p.set_defaults(fn=cmd_names)
    p = sub.add_parser("ledger"); p.add_argument("--kind"); p.add_argument("-n", type=int, default=30); p.set_defaults(fn=cmd_ledger)
    sub.add_parser("cycles").set_defaults(fn=cmd_cycles)
    sub.add_parser("ingest").set_defaults(fn=cmd_ingest)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
