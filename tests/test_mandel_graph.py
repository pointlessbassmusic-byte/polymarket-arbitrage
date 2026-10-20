"""Tests for the concept graph generator behind the signal map."""

from pathlib import Path

from mandel.graph import build_graph, write_html, PLACEHOLDER

DOC = """# {title}
- **Coverage confidence:** 0.5

## What it says
- Shannon entropy and the Brier score; backtest with walk-forward; look-ahead bias is leakage.
- Precognition and presentiment are discussed{extra}.

## Evidence quality
**Rating: speculative.**

## What Mandel adopts
- Use proper scoring rules such as the Brier score.

## What Mandel holds loosely or rejects
- Precognition as a mechanism.

## Design implications for the RSI predictive substrate
- Add available_at timestamps (point-in-time).
"""


def _tree(tmp_path: Path, n: int = 4) -> Path:
    root = tmp_path / "knowledge"
    (root / "sources").mkdir(parents=True); (root / "adjacent").mkdir()
    for i in range(1, n + 1):
        extra = " and Markov chains" if i % 2 else ""
        (root / "sources" / f"{i:02d}-doc.md").write_text(DOC.format(title=f"Doc {i}", extra=extra))
    (root / "adjacent" / "A1-paper.md").write_text(DOC.format(title="Paper", extra=""))
    (root / "SYNTHESIS.md").write_text("# S\n\n## Tensions and contradictions\n- Precognition claims versus pre-registration and replication standards.\n\n## Other\n")
    return root


def test_build_graph_layers_and_edges(tmp_path):
    g = build_graph(knowledge_root=_tree(tmp_path), children=[{"name": "Julia", "domain": "arb", "status": "active", "report_count": 1, "guidance_count": 0}])
    ids = {n["id"] for n in g["nodes"]}
    assert "src:01" in ids and "adj:A1" in ids and "child:Julia" in ids
    assert all(f"c:{c}" in ids for c in ("store", "proposals", "gate", "ledger", "forecasts", "children", "cycles"))
    assert g["stats"]["layers"]["principles"] == 13 and g["stats"]["documents"] == 5
    types = {e["type"] for e in g["edges"]}
    assert {"provenance", "supports", "flow", "skeptical", "tension"} <= types
    # precognition is held loosely by every doc: those edges are negative and go to the anticipation concept
    sk = [e for e in g["edges"] if e["type"] == "skeptical"]
    assert sk and all(e["sign"] == -1 and e["t"] == "k:anticipation" for e in sk)
    # the tension bullet links anticipation with replication
    tn = [e for e in g["edges"] if e["type"] == "tension"]
    assert any({e["s"], e["t"]} == {"k:anticipation", "k:replication"} for e in tn)
    # every edge endpoint exists
    assert all(e["s"] in ids and e["t"] in ids for e in g["edges"])
    # concept nodes carry excerpts with provenance
    k = next(n for n in g["nodes"] if n["id"] == "k:proper_scoring")
    assert k["meta"]["documents"] == 5 and k["meta"]["excerpts"][0]["src"].startswith("src:")
    pr = next(n for n in g["nodes"] if n["id"] == "p:p02")
    assert pr["meta"]["short"] == "Pre-register"


def test_cooccurrence_pmi(tmp_path):
    root = tmp_path / "knowledge"
    (root / "sources").mkdir(parents=True); (root / "adjacent").mkdir()
    extras = [" with Markov chains and the Kelly criterion", " with Markov chains and the Kelly criterion",
              " about fractal dimension and Hausdorff measure", " about fractal dimension", " with the Kelly criterion", ""]
    for i, ex in enumerate(extras, 1):
        (root / "sources" / f"{i:02d}-doc.md").write_text(DOC.format(title=f"Doc {i}", extra=ex))
    g = build_graph(knowledge_root=root)
    co = [e for e in g["edges"] if e["type"] == "cooccur"]
    assert co, "expected co-occurrence edges"
    assert all("PMI" in e["label"] or "inverse" in e["label"] for e in co)
    # Markov and Kelly appear together in 2 of 6 files more often than chance: a positive edge
    assert any({e["s"], e["t"]} == {"k:markov", "k:kelly"} and e["sign"] == 1 for e in co)


def test_write_html_embeds_json(tmp_path):
    tpl = tmp_path / "t.html"; tpl.write_text("<title>x</title><script>const G = " + PLACEHOLDER + ";</script>")
    out = write_html(build_graph(knowledge_root=_tree(tmp_path)), template=tpl, out=tmp_path / "o.html")
    html = out.read_text()
    assert PLACEHOLDER not in html and '"nodes":[' in html and "</script>" in html


def test_evidence_overlay_tallies_verdicts(tmp_path):
    root = _tree(tmp_path)
    (root / "adjacent" / "A2-vol.md").write_text(DOC.format(title="Vol", extra=" and the variance risk premium and short interest"))
    theories = [{"slug": "vrp-a", "claim": "the variance risk premium pays", "status": "supported"},
                {"slug": "vrp-b", "claim": "a variance risk premium timing rule", "status": "not_supported"},
                {"slug": "vrp-c", "claim": "variance risk premium on BTC", "status": "supported"},
                {"slug": "si", "claim": "short interest predicts returns", "status": "not_supported"}]
    ledger = [{"test": "short interest squeeze", "verdict": "FAIL", "result": ""}]
    kids = [{"name": "Hurst", "domain": "", "status": "active", "report_count": 1, "guidance_count": 0,
             "text": "funding carry and the variance risk premium"}]
    g = build_graph(knowledge_root=root, children=kids, theories=theories, child_ledger=ledger)
    ids = {n["id"] for n in g["nodes"]}
    assert {"stream:theories", "stream:child-ledger"} <= ids
    ev = {(e["s"], e["t"]): e for e in g["edges"] if e["type"] == "evidence"}
    assert ev[("stream:theories", "k:vrp")]["sign"] == 1 and "2 of 3 decided passed" in ev[("stream:theories", "k:vrp")]["label"]
    assert ev[("stream:theories", "k:short_interest")]["sign"] == -1
    assert ev[("stream:child-ledger", "k:short_interest")]["sign"] == -1
    assert ("child:Hurst", "k:vrp") in ev
    k = next(n for n in g["nodes"] if n["id"] == "k:vrp")
    assert k["meta"]["verdicts"]["Mandel's tested theories"] == {"supported": 2, "not_supported": 1}
    assert all(e["s"] in ids and e["t"] in ids for e in g["edges"])
