"""First contact (MANDEL.md section 5) for the four sibling sessions, names chosen by the user on 2026-10-20.
Steps 2-4 only: register, record the first report, turn each claim into a CANDIDATE insight. No guidance is drafted
or sent; nothing in the children's sessions or repositories is touched."""
import json, sys
sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.children import ChildRegistry
from mandel.ledger import Ledger
from mandel.store import InsightStore

J = "/root/.claude/projects/-home-user-polymarket-arbitrage/9d0ec309-c258-503a-9a0c-4c2984e42dd2/subagents/workflows/wf_a1cb0c8e-ff4/journal.jsonl"
NAMES = {"cryptobot": "Hurst", "sportsbot-buildout": "Brier", "engine-optimization": "Kelly", "code-optimization": "Shannon"}
label, res = {}, {}
for line in open(J):
    r = json.loads(line)
    if r.get("type") == "started": label[r["key"]] = r["label"]
    if r.get("type") == "result": res[label.get(r["key"])] = r["result"]
led = Ledger(); reg = ChildRegistry(ledger=led); store = InsightStore(ledger=led)
NOTE = ("First-contact record written by Mandel from a read-only reading of the session transcript and repository on "
        "2026-10-20; the adversarial re-check of the headline numbers did not run (session limit), so every figure is the "
        "child's own and unverified. ")
for key, name in NAMES.items():
    c = res[f"read:{key}"]
    tags = ["first-contact-2026-10-20", f"source:{c['repo_branch'][:80]}"]
    if "pointless-repo" in c["repo_branch"]:
        tags.append("repo:pointless-repo")
    reg.register(name, c["session_id"], c["domain"][:400], (c["title"] + ". " + c["domain"])[:1200], tags=tags)
    metrics = {m["metric"][:80]: f"{m['value'][:300]} [{m['evidence_kind']}; {m['source'][:120]}]" for m in c["measures"]}
    rep = reg.record_report(name, NOTE + c["first_report_draft"],
                            learnings=[f"{x['claim']} | evidence: {x['evidence']}"[:900] for x in c["claims"]],
                            metrics=metrics,
                            questions=c["unsure_about"],
                            artifacts=[c["repo_branch"][:300], "live money / keys: " + c["live_money_and_keys"][:600]])
    n = 0
    for x in c["claims"]:
        store.add(text=f"[{name}] {x['claim']}"[:1500], kind="fact", provenance=[f"child:{name}:report:{rep.id}"], confidence=0.3,
                  tags=[f"child:{name}", "first-contact", "unverified"],
                  notes=("evidence: " + x["evidence"] + " | Mandel's view: " + x["mandel_view"])[:3000])
        n += 1
    print(name, c["session_id"], rep.id, "claims ->", n, "candidate insights")
