"""
Command line for Mandel's substrate: ``python -m mandel <command>``.

Commands
--------
  status                      ledger integrity, counts of insights / proposals / forecasts / children
  insights [--status S] [--tag T] [--grep RX]
  insight-add TEXT --kind K --prov P [--prov P2] --conf C [--tag T]
  proposals [--status S]
  proposal-show ID
  proposal-draft TITLE --hypothesis H --target T --change C [--criteria-set strategy|forecast|code] [--criterion "dsr>=0.95"]... [--trials N]
  proposal-preregister ID     freeze criteria (hash goes to the ledger)
  proposal-evidence ID k=v... record out-of-sample evidence and preview the gate
  proposal-decide ID          apply the gate and record accept/reject
  child-register NAME --session S --domain D --desc TEXT
  child-report NAME --summary S [--learning L]... [--metric k=v]... [--question Q]...
  child-guide NAME --summary S [--insight I]... [--warning W]... [--request R]...
  child-show NAME
  forecast-record SOURCE QID P [--market-p M] [--question TEXT]
  forecast-resolve QID OUTCOME
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
from mandel.proposals import Criterion, ProposalBook
from mandel.validation.gate import (code_change_criteria, evaluate, forecast_improvement_criteria,
                                    strategy_improvement_criteria)
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


def _kv(pairs):
    """Parse k=v pairs; numbers become floats, 'true'/'false' become booleans."""
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"expected key=value, got {item!r}")
        k, v = item.split("=", 1)
        lv = v.lower()
        if lv in ("true", "false"):
            out[k] = lv == "true"
        else:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


CRITERIA_SETS = {
    "strategy": strategy_improvement_criteria,
    "forecast": forecast_improvement_criteria,
    "code": code_change_criteria,
}


def cmd_proposal_draft(args) -> int:
    book = ProposalBook()
    if args.criteria_set:
        crits = CRITERIA_SETS[args.criteria_set]()
    else:
        crits = []
    for spec in args.criterion or []:
        # format: metric<op>threshold, e.g. "brier_delta<0" or "dsr>=0.95"
        import re as _re
        m = _re.match(r"^\s*([A-Za-z_][\w]*)\s*(<=|>=|==|<|>)\s*(-?[\d.]+)\s*$", spec)
        if not m:
            raise SystemExit(f"bad criterion {spec!r}; use metric<op>threshold")
        crits.append(Criterion(m.group(1), m.group(2), float(m.group(3))))
    p = book.draft(args.title, args.hypothesis, args.target, args.change, crits,
                   n_trials_declared=args.trials, baseline=_kv(args.baseline), rollback=args.rollback or "")
    print(f"drafted {p.id} with {len(p.criteria)} criteria; next: python -m mandel proposal-preregister {p.id}")
    return 0


def cmd_proposal_preregister(args) -> int:
    p = ProposalBook().preregister(args.id)
    print(f"{p.id} pre-registered at {p.preregistered_at}; criteria hash {p.criteria_hash[:16]}")
    return 0


def cmd_proposal_evidence(args) -> int:
    book = ProposalBook()
    p = book.record_evidence(args.id, _kv(args.kv))
    g = evaluate(p)
    print(g.rationale())
    print(f"status={p.status}; to decide: python -m mandel proposal-decide {p.id}")
    return 0


def cmd_proposal_decide(args) -> int:
    book = ProposalBook()
    p = book.get(args.id)
    g = evaluate(p)
    book.decide(p.id, g.passed, g.rationale(), produces_insights=args.insight or [])
    print(f"{p.id}: {'ACCEPTED' if g.passed else 'REJECTED'}")
    print(g.rationale())
    return 0


def cmd_child_register(args) -> int:
    c = ChildRegistry().register(args.name, args.session, args.domain, args.desc, tags=args.tag or [])
    print(f"registered child {c.name} ({c.domain}) session={c.session_id}")
    return 0


def cmd_child_report(args) -> int:
    rep = ChildRegistry().record_report(args.name, args.summary, learnings=args.learning or [],
                                        metrics=_kv(args.metric), questions=args.question or [],
                                        artifacts=args.artifact or [])
    print(f"recorded report {rep.id} for {args.name}: {len(rep.learnings)} learnings, {len(rep.metrics)} metrics")
    return 0


def cmd_child_guide(args) -> int:
    g = ChildRegistry().record_guidance(args.name, args.summary, insights=args.insight or [],
                                        warnings=args.warning or [], requests=args.request or [])
    print(f"recorded guidance {g.id} for {args.name}")
    return 0


def cmd_child_show(args) -> int:
    reg = ChildRegistry()
    _print({"child": asdict(reg.get(args.name)),
            "reports": [asdict(r) for r in reg.reports(args.name)][-args.n:],
            "guidance": [asdict(g) for g in reg.guidance(args.name)][-args.n:]})
    return 0


def cmd_forecast_record(args) -> int:
    fc = ForecastBook().record(args.source, args.question_id, args.question, args.p, market_p=args.market_p,
                               horizon=args.horizon or "", rationale=args.rationale or "", tags=args.tag or [])
    print(f"recorded {fc.id}: {fc.source} p={fc.p} on {fc.question_id}")
    return 0


def cmd_forecast_resolve(args) -> int:
    r = ForecastBook().resolve(args.question_id, args.outcome, note=args.note or "")
    print(f"resolved {r.question_id} -> {r.outcome}")
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
    p = sub.add_parser("proposal-draft")
    p.add_argument("title"); p.add_argument("--hypothesis", required=True); p.add_argument("--target", required=True)
    p.add_argument("--change", required=True); p.add_argument("--criteria-set", choices=sorted(CRITERIA_SETS))
    p.add_argument("--criterion", action="append", help="metric<op>threshold, repeatable")
    p.add_argument("--trials", type=int, default=1); p.add_argument("--baseline", action="append", help="k=v")
    p.add_argument("--rollback")
    p.set_defaults(fn=cmd_proposal_draft)
    p = sub.add_parser("proposal-preregister"); p.add_argument("id"); p.set_defaults(fn=cmd_proposal_preregister)
    p = sub.add_parser("proposal-evidence"); p.add_argument("id"); p.add_argument("kv", nargs="+", help="metric=value ...")
    p.set_defaults(fn=cmd_proposal_evidence)
    p = sub.add_parser("proposal-decide"); p.add_argument("id"); p.add_argument("--insight", action="append")
    p.set_defaults(fn=cmd_proposal_decide)

    p = sub.add_parser("child-register")
    p.add_argument("name"); p.add_argument("--session", required=True); p.add_argument("--domain", required=True)
    p.add_argument("--desc", required=True); p.add_argument("--tag", action="append")
    p.set_defaults(fn=cmd_child_register)
    p = sub.add_parser("child-report")
    p.add_argument("name"); p.add_argument("--summary", required=True); p.add_argument("--learning", action="append")
    p.add_argument("--metric", action="append", help="k=v"); p.add_argument("--question", action="append")
    p.add_argument("--artifact", action="append")
    p.set_defaults(fn=cmd_child_report)
    p = sub.add_parser("child-guide")
    p.add_argument("name"); p.add_argument("--summary", required=True); p.add_argument("--insight", action="append")
    p.add_argument("--warning", action="append"); p.add_argument("--request", action="append")
    p.set_defaults(fn=cmd_child_guide)
    p = sub.add_parser("child-show"); p.add_argument("name"); p.add_argument("-n", type=int, default=5); p.set_defaults(fn=cmd_child_show)

    p = sub.add_parser("forecast-record")
    p.add_argument("source"); p.add_argument("question_id"); p.add_argument("p", type=float)
    p.add_argument("--question", default=""); p.add_argument("--market-p", type=float, dest="market_p")
    p.add_argument("--horizon"); p.add_argument("--rationale"); p.add_argument("--tag", action="append")
    p.set_defaults(fn=cmd_forecast_record)
    p = sub.add_parser("forecast-resolve"); p.add_argument("question_id"); p.add_argument("outcome", type=int)
    p.add_argument("--note"); p.set_defaults(fn=cmd_forecast_resolve)

    sub.add_parser("cycles").set_defaults(fn=cmd_cycles)
    sub.add_parser("ingest").set_defaults(fn=cmd_ingest)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
