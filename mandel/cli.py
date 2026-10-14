"""
Command line for Mandel's substrate: ``python -m mandel <command>``.

Run ``python -m mandel --help`` for the command list and ``python -m mandel
<command> --help`` for its arguments. The commands are grouped as:

  status, verify, ledger            what is in the substrate and whether it is intact
  insights, insight-add, insight-status, insight-confidence
  proposals, proposal-show, proposal-draft, proposal-preregister, proposal-evidence, proposal-decide
  forecasts, forecast-record, forecast-resolve
  children, names, child-register, child-report, child-guide, child-show
  cycles, cycle-start, cycle-note, cycle-finish
  ingest, graph

Every domain error is printed as one line with a next step and exits 1; a
Python traceback means a bug, not a usage mistake.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict

from mandel import __version__, paths
from mandel.archive import Archive
from mandel.children import ChildRegistry
from mandel.cycles import COST_FIELDS, OUTCOME_FIELDS, CycleLog
from mandel.forecasts import ForecastBook
from mandel.graph import TEMPLATE_PATH, build_graph, write_graph, write_html
from mandel.ingest import ingest_knowledge
from mandel.experiments import ExperimentLog
from mandel.experiments.run import HARNESSES, load_registry, run_all, save_registry, REGISTRY
from mandel.ledger import Ledger, LedgerCorrupt
from mandel.paths import KNOWLEDGE_ROOT
from mandel.proposals import Criterion, IntegrityError, LifecycleError, ProposalBook
from mandel.store import InsightStore
from mandel.validation.gate import (code_change_criteria, evaluate, forecast_improvement_criteria,
                                    strategy_improvement_criteria)


class Ctx:
    """One ledger shared by every store a command touches."""

    def __init__(self):
        self.ledger = Ledger()
        self.proposals = ProposalBook(ledger=self.ledger)
        self.store = InsightStore(ledger=self.ledger, proposals=self.proposals)
        self.forecasts = ForecastBook(ledger=self.ledger)
        self.children = ChildRegistry(ledger=self.ledger)
        self.cycles = CycleLog(ledger=self.ledger)


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _kv(pairs):
    """Parse k=v pairs; numbers become floats, true/false become booleans, the rest strings."""
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise ValueError(f"expected key=value, got {item!r}")
        k, v = item.split("=", 1)
        lv = v.strip().lower()
        if lv in ("true", "false"):
            out[k] = lv == "true"
        else:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


CRITERIA_SETS = {"strategy": strategy_improvement_criteria, "forecast": forecast_improvement_criteria, "code": code_change_criteria}
_CRIT_RX = re.compile(r"^\s*([A-Za-z_]\w*)\s*(<=|>=|==|<|>)\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*$")


def parse_criterion(spec: str) -> Criterion:
    m = _CRIT_RX.match(spec)
    if not m:
        raise ValueError(f"bad criterion {spec!r}; use metric<op>threshold, e.g. \"dsr>=0.95\" or \"brier_delta<-1e-3\" (quote the operator)")
    return Criterion(m.group(1), m.group(2), float(m.group(3)))


# ------------------------------------------------------------------ status --

def cmd_status(_args) -> int:
    c = Ctx()
    ok, msg = c.ledger.verify()
    problems = c.proposals.reconcile() + c.store.reconcile() + c.forecasts.reconcile()
    warnings = []
    if not (KNOWLEDGE_ROOT / "SYNTHESIS.md").exists():
        warnings.append("knowledge/SYNTHESIS.md not written yet (the learning pass has not been synthesised)")
    if not (paths.MANDEL_ROOT / "ARCHITECTURE.md").exists():
        warnings.append("ARCHITECTURE.md not written yet (design phase pending)")
    cur = c.cycles.current()
    if cur:
        warnings.append(f"cycle {cur.id} is open: {cur.goal[:60]} (finish it with cycle-finish)")
    sources = sorted(p.name for p in (KNOWLEDGE_ROOT / "sources").glob("*.md")) if (KNOWLEDGE_ROOT / "sources").exists() else []
    adjacent = sorted(p.name for p in (KNOWLEDGE_ROOT / "adjacent").glob("A*.md")) if (KNOWLEDGE_ROOT / "adjacent").exists() else []
    _print({
        "mandel": __version__,
        "data_root": str(paths.DATA_ROOT),
        "ledger": {"events": len(c.ledger), "integrity": msg, "ok": ok, "head": c.ledger.head_hash,
                   "reconcile": problems or "ok"},
        "insights": c.store.summary(),
        "proposals": c.proposals.summary(),
        "forecasts": {"recorded": len(c.forecasts.forecasts), "resolved": len(c.forecasts.resolutions),
                      "open": len(c.forecasts.open_questions()), "scoreboard": [s.as_dict() for s in c.forecasts.scoreboard()]},
        "children": [{"name": ch.name, "status": ch.status, "domain": ch.domain, "reports": ch.report_count,
                      "guidance": ch.guidance_count, "last_contact": ch.last_contact} for ch in c.children.all()],
        "cycles": c.cycles.efficiency(),
        "knowledge": {"sources": len(sources), "adjacent": len(adjacent), "synthesis": (KNOWLEDGE_ROOT / "SYNTHESIS.md").exists()},
        "warnings": warnings,
    })
    return 0 if ok and not problems else 1


def cmd_verify(args) -> int:
    c = Ctx()
    if args.reanchor:
        h = c.ledger.anchor_now()
        print(f"re-anchored; new head {h[:12]} (record this hash in your commit message)")
    ok, msg = c.ledger.verify(anchor=args.anchor)
    print(msg)
    problems = c.proposals.reconcile() + c.store.reconcile() + c.forecasts.reconcile()
    for p in problems:
        print("reconcile:", p)
    if not problems:
        print("reconcile: proposals, insights and forecasts agree with the ledger")
    return 0 if ok and not problems else 1


def cmd_ledger(args) -> int:
    ledger = Ledger()
    for e in ledger.tail(args.n, kind=args.kind):
        print(f"{e.seq:5d} {e.ts[:19]} {e.actor:16} {e.kind:24} {json.dumps(e.payload, default=str)[:120]}")
    return 0


# ---------------------------------------------------------------- insights --

def cmd_insights(args) -> int:
    rows = Ctx().store.query(status=args.status, tag=args.tag, text_regex=args.grep, kind=args.kind)
    for i in rows:
        print(f"{i.id}  [{i.status:9}] c={i.confidence:.2f} {i.kind:9} {i.text}  <- {', '.join(i.provenance)}")
    print(f"({len(rows)} insights)")
    return 0


def cmd_insight_add(args) -> int:
    ins = Ctx().store.add(args.text, args.kind, args.prov, args.conf, tags=args.tag or [], notes=args.notes or "")
    _print(asdict(ins))
    return 0


def cmd_insight_status(args) -> int:
    ins = Ctx().store.set_status(args.id, args.status, by=args.by)
    print(f"{ins.id} -> {ins.status} (by {args.by})")
    return 0


def cmd_insight_confidence(args) -> int:
    ins = Ctx().store.update_confidence(args.id, args.confidence, reason=args.reason)
    print(f"{ins.id} confidence -> {ins.confidence}")
    return 0


# --------------------------------------------------------------- proposals --

def cmd_proposals(args) -> int:
    book = Ctx().proposals
    for p in book.query(status=args.status):
        print(f"{p.id}  [{p.status:13}] {p.title}  -> {p.target}  (trials={p.n_trials_declared})")
    print(f"({len(book.all())} total)")
    return 0


def cmd_proposal_show(args) -> int:
    _print(asdict(Ctx().proposals.get(args.id)))
    return 0


def cmd_proposal_draft(args) -> int:
    crits = CRITERIA_SETS[args.criteria_set]() if args.criteria_set else []
    crits += [parse_criterion(s) for s in (args.criterion or [])]
    p = Ctx().proposals.draft(args.title, args.hypothesis, args.target, args.change, crits, n_trials_declared=args.trials,
                              baseline=_kv(args.baseline), rollback=args.rollback or "", supersedes=args.supersedes)
    print(f"drafted {p.id} with {len(p.criteria)} criteria; next: python -m mandel proposal-preregister {p.id}")
    return 0


def cmd_proposal_preregister(args) -> int:
    p = Ctx().proposals.preregister(args.id)
    print(f"{p.id} pre-registered at {p.preregistered_at}; criteria hash {p.criteria_hash[:16]} is in the ledger")
    return 0


def cmd_proposal_evidence(args) -> int:
    book = Ctx().proposals
    p = book.record_evidence(args.id, _kv(args.kv))
    g = evaluate(p)
    print(g.rationale())
    print(f"status={p.status}; to decide: python -m mandel proposal-decide {p.id}" + ("" if g.passed else " --confirm-reject"))
    return 0


def cmd_proposal_decide(args) -> int:
    c = Ctx()
    p = c.proposals.get(args.id)
    insights = args.insight or []
    missing = [i for i in insights if not c.store.exists(i)]
    if missing:
        raise ValueError(f"unknown insight ids {missing}; add them first with insight-add")
    g = evaluate(p)
    if not g.passed and not args.confirm_reject:
        print(g.rationale())
        print("gate currently FAILS; add evidence with proposal-evidence, or pass --confirm-reject to record the rejection")
        return 1
    p = c.proposals.decide(p.id, produces_insights=insights)
    print(f"{p.id}: {'ACCEPTED' if p.status == 'accepted' else 'REJECTED'}")
    print(p.decision)
    if p.status == "accepted":
        for i in insights:
            c.store.set_status(i, "validated", by=p.id)
            print(f"insight {i} -> validated by {p.id}")
    return 0


# --------------------------------------------------------------- forecasts --

def cmd_forecasts(_args) -> int:
    fb = Ctx().forecasts
    board = fb.scoreboard()
    if not board:
        print("no resolved forecasts yet")
    for s in board:
        skill = "n/a" if s.skill_vs_market is None else f"{s.skill_vs_market:+.3f} ({s.market_reference})"
        print(f"{s.source:28} n={s.n:4d} brier={s.brier:.4f} logloss={s.log_loss:.4f} ece={s.ece:.3f} skill_vs_market={skill}")
    print(f"open questions: {len(fb.open_questions())}")
    return 0


def cmd_forecast_record(args) -> int:
    fc = Ctx().forecasts.record(args.source, args.question_id, args.question, args.p, market_p=args.market_p,
                                horizon=args.horizon or "", rationale=args.rationale or "", tags=args.tag or [])
    print(f"recorded {fc.id}: {fc.source} p={fc.p} on {fc.question_id}")
    return 0


def cmd_forecast_resolve(args) -> int:
    r = Ctx().forecasts.resolve(args.question_id, args.outcome, note=args.note or "")
    print(f"resolved {r.question_id} -> {r.outcome}")
    return 0


# ---------------------------------------------------------------- children --

def cmd_children(_args) -> int:
    reg = Ctx().children
    for ch in reg.all():
        print(f"{ch.name:12} [{ch.status:8}] {ch.domain:24} reports={ch.report_count} guidance={ch.guidance_count} session={ch.session_id}")
    if not reg.all():
        print("no children registered yet; try `python -m mandel names`")
    return 0


def cmd_names(args) -> int:
    for name, why in ChildRegistry().suggest_names(args.n):
        print(f"{name:12} {why}")
    return 0


def cmd_child_register(args) -> int:
    ch = Ctx().children.register(args.name, args.session, args.domain, args.desc, tags=args.tag or [])
    print(f"registered child {ch.name} ({ch.domain}) session={ch.session_id}")
    return 0


def cmd_child_report(args) -> int:
    rep = Ctx().children.record_report(args.name, args.summary, learnings=args.learning or [], metrics=_kv(args.metric),
                                       questions=args.question or [], artifacts=args.artifact or [])
    print(f"recorded report {rep.id} for {args.name}: {len(rep.learnings)} learnings, {len(rep.metrics)} metrics")
    return 0


def cmd_child_guide(args) -> int:
    g = Ctx().children.record_guidance(args.name, args.summary, insights=args.insight or [], warnings=args.warning or [],
                                       requests=args.request or [])
    print(f"recorded guidance {g.id} for {args.name}")
    return 0


def cmd_child_show(args) -> int:
    reg = Ctx().children
    _print({"child": asdict(reg.get(args.name)), "reports": [asdict(r) for r in reg.reports(args.name)][-args.n:],
            "guidance": [asdict(g) for g in reg.guidance(args.name)][-args.n:]})
    return 0


# ------------------------------------------------------------------ cycles --

def cmd_cycles(_args) -> int:
    log = Ctx().cycles
    for cy in log.all():
        print(f"{cy.id}  [{'open' if cy.open else 'done'}] {cy.started_at[:19]}  gains={cy.gains()}  cost={cy.cost}  {cy.goal}")
    _print(log.efficiency())
    return 0


def cmd_cycle_start(args) -> int:
    cy = Ctx().cycles.start(args.goal)
    print(f"started cycle {cy.id}: {cy.goal}")
    return 0


def cmd_cycle_note(args) -> int:
    cy = Ctx().cycles.note_action(args.id, args.text)
    print(f"{cy.id}: {len(cy.actions)} actions noted")
    return 0


def cmd_cycle_finish(args) -> int:
    cy = Ctx().cycles.finish(args.id, cost=_kv(args.cost), outcomes={k: int(v) for k, v in _kv(args.outcome).items()},
                             notes=args.notes or "")
    print(f"finished {cy.id}: gains={cy.gains()} cost={cy.cost}")
    return 0


# ------------------------------------------------- experiments, theories, archive --

def cmd_experiments(args) -> int:
    log = ExperimentLog(ledger=Ledger())
    rows = log.all()
    for r in rows[-args.n:]:
        print(f"{r.id}  {r.created_at[:19]}  {r.harness:22} n={r.n:6d}  {r.verdict:14} {r.reason}")
    print(f"({len(rows)} results; harnesses: {', '.join(HARNESSES)})")
    return 0


def cmd_experiment_run(args) -> int:
    only = None if args.harness == ["all"] else args.harness
    for h in (only or []):
        if h not in HARNESSES:
            raise ValueError(f"unknown harness {h}; choose from {', '.join(HARNESSES)} or all")
    results = run_all(only=only)
    for r in results:
        print(f"{r['id']}  {r['harness']:22} n={r['n']:6d}  {r['verdict']:14} {r['reason']}")
    return 0


def cmd_theories(args) -> int:
    reg = load_registry()
    if not reg:
        print(f"no registry at {REGISTRY}; the theory-extraction pass has not run")
        return 1
    rows = [t for t in reg["theories"] if (args.status is None or t.get("status") == args.status)]
    for t in rows:
        print(f"{t['id']}  [{t.get('status', '?'):13}] {t['kind']:14} {t['slug'][:48]:48} <- {','.join(t.get('origin', []))[:40]}  h={','.join(t.get('experiments', [])) or '-'}")
    counts = {}
    for t in reg["theories"]:
        counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
    print(f"({len(rows)} shown; by status {counts})")
    return 0


def cmd_theory_park(args) -> int:
    reg = load_registry()
    if not reg:
        raise ValueError("no registry")
    for t in reg["theories"]:
        if t["id"] == args.id:
            if args.unpark:
                t["status"] = t.get("status_before_park", "untested"); t["parked_reason"] = ""
            else:
                t["status_before_park"] = t.get("status", "untested"); t["status"] = "parked"; t["parked_reason"] = args.reason or ""
            save_registry(reg)
            Ledger().append("theory.unparked" if args.unpark else "theory.parked", {"id": args.id, "reason": args.reason or ""}, actor="mandel")
            print(f"{args.id} -> {t['status']}")
            return 0
    raise KeyError(args.id)


def cmd_archive(args) -> int:
    a = Archive()
    for e in a.entries(kind=args.kind):
        print(f"{e.name:36} {e.kind:9} rows={e.rows:7d} {e.bytes/1024:8.1f}KB {'git' if e.in_git else 'OFF-GIT'}  {e.created_at[:19]}  {('parked: ' + e.parked_reason) if e.parked_reason else ''}")
        if args.verbose:
            print(f"    recipe: {e.recipe}\n    schema: {e.schema}  sha256={e.sha256[:12]}")
    _print(a.summary())
    return 0


# --------------------------------------------------------- ingest and graph --

def cmd_ingest(_args) -> int:
    rep = ingest_knowledge(Ctx().store)
    _print({"files": rep.files, "added": rep.added, "skipped_existing": rep.skipped_existing, "per_file": rep.per_file})
    return 0


def cmd_graph(args) -> int:
    reg = Ctx().children
    kids = [{"name": ch.name, "domain": ch.domain, "status": ch.status, "report_count": ch.report_count,
             "guidance_count": ch.guidance_count} for ch in reg.all()]
    g = build_graph(children=kids)
    out = write_graph(children=kids)
    print(f"graph: {g['stats']} -> {out}")
    if TEMPLATE_PATH.exists() and not args.json_only:
        html = write_html(g)
        print(f"html: {html} ({html.stat().st_size // 1024} KB)")
    return 0


# ------------------------------------------------------------------ parser --

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mandel", description="Mandel: a self-improving predictive substrate. State lives under MANDEL_DATA_ROOT (default mandel/state).")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    def add(name, fn, help_, **kw):
        p = sub.add_parser(name, help=help_, description=help_, **kw)
        p.set_defaults(fn=fn)
        return p

    add("status", cmd_status, "Ledger integrity, counts of insights/proposals/forecasts/children, warnings.")
    p = add("verify", cmd_verify, "Recompute the ledger hash chain, check the head anchor and reconcile proposals.")
    p.add_argument("--anchor", help="a head hash copied from a git commit; verify fails if it is not in the chain")
    p.add_argument("--reanchor", action="store_true", help="write a fresh head anchor for a ledger created before anchors existed (logged as an event)")
    p = add("ledger", cmd_ledger, "Show the most recent ledger events.")
    p.add_argument("--kind", help="event kind prefix, e.g. proposal. or insight.recorded"); p.add_argument("-n", type=int, default=30)

    p = add("insights", cmd_insights, "List insights, optionally filtered.")
    p.add_argument("--status", choices=["candidate", "validated", "retired"]); p.add_argument("--kind"); p.add_argument("--tag"); p.add_argument("--grep", help="regex on the text")
    p = add("insight-add", cmd_insight_add, "Record a candidate insight with provenance.")
    p.add_argument("text"); p.add_argument("--kind", required=True, choices=["principle", "fact", "heuristic", "procedure", "metric", "question"])
    p.add_argument("--prov", action="append", required=True, help="src:NN | adj:AN | child:<name>:report:<id> | proposal:P-xxxxxxxx | ideas:N | user | mandel:self (repeatable)")
    p.add_argument("--conf", type=float, required=True, help="probability the claim is true as stated, 0-1"); p.add_argument("--tag", action="append"); p.add_argument("--notes")
    p = add("insight-status", cmd_insight_status, "Validate or retire an insight. Validation needs an accepted proposal id or converge:<ref>,<ref>.")
    p.add_argument("id"); p.add_argument("status", choices=["validated", "retired", "candidate"]); p.add_argument("--by", required=True)
    p = add("insight-confidence", cmd_insight_confidence, "Change an insight's confidence, with a reason that goes to the ledger.")
    p.add_argument("id"); p.add_argument("confidence", type=float); p.add_argument("--reason", required=True)

    p = add("proposals", cmd_proposals, "List proposals."); p.add_argument("--status")
    p = add("proposal-show", cmd_proposal_show, "Show one proposal in full."); p.add_argument("id")
    p = add("proposal-draft", cmd_proposal_draft, "Draft a proposal: hypothesis, change, and the criteria it must meet. Criteria freeze at pre-registration.")
    p.add_argument("title"); p.add_argument("--hypothesis", required=True, help="a falsifiable statement"); p.add_argument("--target", required=True, help="mandel:<module> | child:<name> | repo:<path>")
    p.add_argument("--change", required=True); p.add_argument("--criteria-set", choices=sorted(CRITERIA_SETS), help="strategy: sharpe/bootstrap/dsr; forecast: brier delta and skill vs market; code: tests pass")
    p.add_argument("--criterion", action="append", help='extra criterion metric<op>threshold, e.g. "dsr>=0.95" (repeatable)')
    p.add_argument("--trials", type=int, default=1, help="honest number of variants you will try (deflation uses it)")
    p.add_argument("--baseline", action="append", help="k=v measurements before the change"); p.add_argument("--rollback", help="how to undo")
    p.add_argument("--supersedes", help="id of the earlier proposal this retries")
    p = add("proposal-preregister", cmd_proposal_preregister, "Freeze the criteria; their hash goes to the ledger."); p.add_argument("id")
    p = add("proposal-evidence", cmd_proposal_evidence, "Record out-of-sample evidence (write-once per key) and preview the gate.",
            epilog="required keys for non-code criteria: out_of_sample=true n_trials=N (N <= declared) plus every metric the criteria name; keys are write-once")
    p.add_argument("id"); p.add_argument("kv", nargs="+", help="metric=value ...")
    p = add("proposal-decide", cmd_proposal_decide, "Apply the gate and record accept/reject. A failing gate is only recorded with --confirm-reject.")
    p.add_argument("id"); p.add_argument("--insight", action="append", help="insight id this proposal validates if accepted (must exist)")
    p.add_argument("--confirm-reject", action="store_true")

    add("forecasts", cmd_forecasts, "Scoreboard: Brier, log loss, calibration and skill versus the market, per source.")
    p = add("forecast-record", cmd_forecast_record, "Record a probabilistic forecast before the question resolves.")
    p.add_argument("source", help="mandel | child:<name> | market:<platform>"); p.add_argument("question_id"); p.add_argument("p", type=float)
    p.add_argument("--question", default="", help="question text (used to stop a resolved question being reopened under a new id)")
    p.add_argument("--market-p", type=float, dest="market_p", help="market price at forecast time (a market:* source on the same question overrides it)")
    p.add_argument("--horizon"); p.add_argument("--rationale"); p.add_argument("--tag", action="append")
    p = add("forecast-resolve", cmd_forecast_resolve, "Resolve a question to 0 or 1 (final; the question must have forecasts).")
    p.add_argument("question_id"); p.add_argument("outcome", type=int, choices=[0, 1]); p.add_argument("--note")

    add("children", cmd_children, "List the registered child sessions.")
    p = add("names", cmd_names, "Suggest names for new children."); p.add_argument("n", nargs="?", type=int, default=5)
    p = add("child-register", cmd_child_register, "Register a child session (names are case-insensitive).")
    p.add_argument("name"); p.add_argument("--session", required=True); p.add_argument("--domain", required=True); p.add_argument("--desc", required=True); p.add_argument("--tag", action="append")
    p = add("child-report", cmd_child_report, "Record what a child reports: learnings, metrics, questions.")
    p.add_argument("name"); p.add_argument("--summary", required=True); p.add_argument("--learning", action="append"); p.add_argument("--metric", action="append", help="k=v")
    p.add_argument("--question", action="append"); p.add_argument("--artifact", action="append")
    p = add("child-guide", cmd_child_guide, "Record guidance sent to a child: insights, warnings, measurement requests.")
    p.add_argument("name"); p.add_argument("--summary", required=True); p.add_argument("--insight", action="append"); p.add_argument("--warning", action="append"); p.add_argument("--request", action="append")
    p = add("child-show", cmd_child_show, "Show a child with its recent reports and guidance."); p.add_argument("name"); p.add_argument("-n", type=int, default=5)

    add("cycles", cmd_cycles, "Improvement cycles and gains per unit of cost.")
    p = add("cycle-start", cmd_cycle_start, "Open a cycle (only one may be open)."); p.add_argument("goal")
    p = add("cycle-note", cmd_cycle_note, "Note an action taken in the open cycle."); p.add_argument("id"); p.add_argument("text")
    p = add("cycle-finish", cmd_cycle_finish, f"Close a cycle with its cost and outcomes. cost keys: {', '.join(COST_FIELDS)}; outcome keys: {', '.join(OUTCOME_FIELDS)}.")
    p.add_argument("id"); p.add_argument("--cost", action="append", help="k=v"); p.add_argument("--outcome", action="append", help="k=v"); p.add_argument("--notes")

    p = add("experiments", cmd_experiments, "List recorded experiment results (the trial math, executed)."); p.add_argument("-n", type=int, default=30)
    p = add("experiment-run", cmd_experiment_run, "Run harnesses on the archived data and record results; updates theory statuses.")
    p.add_argument("harness", nargs="+", help="harness ids or 'all'")
    p = add("theories", cmd_theories, "List the theory registry with statuses."); p.add_argument("--status")
    p = add("theory-park", cmd_theory_park, "Park a theory (kept, not pursued now) with a reason, or --unpark it.")
    p.add_argument("id"); p.add_argument("--reason"); p.add_argument("--unpark", action="store_true")
    p = add("archive", cmd_archive, "List cold-storage bundles (data, results, knowledge) and their rebuild recipes.")
    p.add_argument("--kind"); p.add_argument("-v", "--verbose", action="store_true")
    add("ingest", cmd_ingest, "Turn knowledge/*.md adopt / skeptical / design bullets into candidate insights (idempotent).")
    p = add("graph", cmd_graph, "Rebuild viz/graph.json and viz/index.html (the signal map)."); p.add_argument("--json-only", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except KeyError as e:
        print(f"error: unknown id {e}; list ids with `python -m mandel proposals|insights|children`", file=sys.stderr)
        return 1
    except (ValueError, LifecycleError, IntegrityError, RuntimeError, LedgerCorrupt) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except re.error as e:
        print(f"error: bad regex: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
