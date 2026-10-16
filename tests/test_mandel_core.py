"""Tests for Mandel's substrate: ledger, store, forecasts, children."""

import json

import pytest

from mandel.children import ChildRegistry
from mandel.forecasts import ForecastBook
from mandel.ledger import GENESIS_HASH, Ledger
from mandel.proposals import Criterion, ProposalBook
from mandel.store import InsightStore


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.jsonl")


# ---------------------------------------------------------------- ledger ---

class TestLedger:
    def test_empty_ledger(self, ledger):
        assert len(ledger) == 0
        assert ledger.head_hash == GENESIS_HASH
        assert ledger.verify() == (True, "ok: 0 events, head=000000000000")

    def test_chain_links_and_verifies(self, ledger):
        e0 = ledger.append("test.a", {"x": 1})
        e1 = ledger.append("test.b", {"y": [1, 2]}, actor="child:julia")
        assert e0.prev_hash == GENESIS_HASH
        assert e1.prev_hash == e0.hash
        assert e1.seq == 1
        ok, msg = ledger.verify()
        assert ok, msg

    def test_reload_continues_chain(self, tmp_path):
        p = tmp_path / "l.jsonl"
        a = Ledger(p)
        a.append("k", {"n": 1})
        b = Ledger(p)
        assert len(b) == 1
        b.append("k", {"n": 2})
        assert b.verify()[0]
        assert b.events()[1].prev_hash == b.events()[0].hash

    def test_tamper_detected(self, tmp_path):
        p = tmp_path / "l.jsonl"
        l = Ledger(p)
        l.append("k", {"n": 1})
        l.append("k", {"n": 2})
        lines = p.read_text().splitlines()
        d = json.loads(lines[0])
        d["payload"]["n"] = 999
        lines[0] = json.dumps(d)
        p.write_text("\n".join(lines) + "\n")
        ok, msg = Ledger(p).verify()
        assert not ok
        assert "seq=0" in msg

    def test_filter_by_kind_prefix(self, ledger):
        ledger.append("insight.recorded", {})
        ledger.append("insight.status", {})
        ledger.append("proposal.drafted", {})
        assert len(ledger.events(kind="insight")) == 2
        assert len(ledger.events(kind="proposal.drafted")) == 1
        assert [e.kind for e in ledger.tail(2)] == ["insight.status", "proposal.drafted"]

    def test_two_instances_on_one_file_keep_one_chain(self, tmp_path):
        p = tmp_path / "l.jsonl"
        a, b = Ledger(p), Ledger(p)
        a.append("k", {"n": 1}); b.append("k", {"n": 2}); a.append("k", {"n": 3})
        ok, msg = Ledger(p).verify()
        assert ok, msg
        assert [e.seq for e in Ledger(p).events()] == [0, 1, 2]

    def test_truncation_detected_by_head_anchor(self, tmp_path):
        p = tmp_path / "l.jsonl"
        l = Ledger(p)
        for n in range(4):
            l.append("k", {"n": n})
        lines = p.read_text().splitlines()
        p.write_text("\n".join(lines[:2]) + "\n")
        ok, msg = Ledger(p).verify()
        assert not ok and "truncated" in msg

    def test_missing_trailing_newline_is_repaired(self, tmp_path):
        p = tmp_path / "l.jsonl"
        l = Ledger(p)
        l.append("k", {"n": 1})
        p.write_bytes(p.read_bytes().rstrip(b"\n"))
        Ledger(p).append("k", {"n": 2})
        ok, msg = Ledger(p).verify()
        assert ok, msg and len(Ledger(p)) == 2

    def test_corrupt_line_reported_not_crashing(self, tmp_path):
        p = tmp_path / "l.jsonl"
        l = Ledger(p)
        l.append("k", {"n": 1})
        with p.open("a") as f:
            f.write('{"seq": 1, "ts": "x", "kind": "k", "act')
        l2 = Ledger(p)                      # constructor survives
        assert l2.corrupt is not None
        ok, msg = l2.verify()
        assert not ok and "corrupt" in msg
        with pytest.raises(RuntimeError):
            l2.append("k", {"n": 2})

    def test_external_anchor(self, ledger):
        e = ledger.append("k", {"n": 1})
        ledger.append("k", {"n": 2})
        assert ledger.verify(anchor=e.hash)[0]
        assert not ledger.verify(anchor="deadbeef" * 8)[0]

    def test_numpy_payload_is_coerced(self, ledger):
        import numpy as np
        ev = ledger.append("k", {"x": np.float64(1.5), "b": np.bool_(True), "arr": np.arange(2)})
        assert ev.payload == {"x": 1.5, "b": True, "arr": [0, 1]}


# ----------------------------------------------------------------- store ---

class TestInsightStore:
    def test_add_and_query(self, tmp_path, ledger):
        s = InsightStore(tmp_path / "i.jsonl", ledger)
        a = s.add("Brier score is a proper scoring rule", "fact", ["src:11"], 0.95, tags=["scoring"])
        s.add("Always pre-register criteria", "principle", ["adj:A1", "mandel:self"], 0.8, tags=["rsi"])
        assert s.summary()["total"] == 2
        assert [i.id for i in s.query(tag="scoring")] == [a.id]
        assert len(s.query(text_regex="pre-register")) == 1
        assert len(s.query(min_confidence=0.9)) == 1
        assert len(ledger.events(kind="insight.recorded")) == 2

    def test_validation_requires_provenance_and_range(self, tmp_path, ledger):
        s = InsightStore(tmp_path / "i.jsonl", ledger)
        with pytest.raises(ValueError):
            s.add("no provenance", "fact", [], 0.5)
        with pytest.raises(ValueError):
            s.add("bad confidence", "fact", ["src:01"], 1.5)
        with pytest.raises(ValueError):
            s.add("bad kind", "vibe", ["src:01"], 0.5)

    def test_status_transitions_persist(self, tmp_path, ledger):
        p = tmp_path / "i.jsonl"
        s = InsightStore(p, ledger)
        ins = s.add("claim", "heuristic", ["child:julia:report:1"], 0.4)
        s.set_status(ins.id, "validated", by="converge:src:01,src:02")
        s.update_confidence(ins.id, 0.7, reason="passed gate")
        again = InsightStore(p, ledger).get(ins.id)
        assert again.status == "validated"
        assert again.validated_by == ["converge:src:01,src:02"]
        assert again.confidence == 0.7
        assert len(s.query(status="validated")) == 1

    def test_validation_rules(self, tmp_path, ledger):
        book = ProposalBook(tmp_path / "p.jsonl", ledger)
        s = InsightStore(tmp_path / "i.jsonl", ledger, proposals=book)
        ins = s.add("claim", "fact", ["src:01"], 0.5)
        with pytest.raises(ValueError):                      # arbitrary string
            s.set_status(ins.id, "validated", by="because I said so")
        with pytest.raises(ValueError):                      # one ref is not convergence
            s.set_status(ins.id, "validated", by="converge:src:01")
        with pytest.raises(ValueError):                      # unknown proposal
            s.set_status(ins.id, "validated", by="P-00000000")
        prop = book.draft("t", "h", "mandel:x", "c", [Criterion("tests_pass", "==", 1.0)])
        with pytest.raises(ValueError):                      # not accepted yet
            s.set_status(ins.id, "validated", by=prop.id)
        book.preregister(prop.id); book.record_evidence(prop.id, {"tests_pass": 1})
        book.decide(prop.id, produces_insights=[ins.id])
        s.set_status(ins.id, "validated", by=prop.id)
        assert s.get(ins.id).validated_by == [prop.id]
        s.set_status(ins.id, "retired", by="src:02")
        with pytest.raises(ValueError):                      # retired cannot come back
            s.set_status(ins.id, "validated", by=prop.id)

    def test_provenance_rules(self, tmp_path, ledger):
        s = InsightStore(tmp_path / "i.jsonl", ledger)
        with pytest.raises(ValueError):
            s.add("x", "fact", ["wikipedia"], 0.5)
        ins = s.add("own inference", "heuristic", ["mandel:self"], 0.9)
        assert ins.confidence == 0.5                         # capped for self-only provenance
        ok = s.add("sourced", "fact", ["src:03", "mandel:self"], 0.9)
        assert ok.confidence == 0.9


# ------------------------------------------------------------- forecasts ---

class TestForecastBook:
    def test_record_resolve_score(self, tmp_path, ledger):
        fb = ForecastBook(tmp_path / "f.jsonl", ledger)
        for k in range(10):
            qid = f"q{k}"
            fb.record("child:julia", qid, "will it rain", p=0.9 if k < 8 else 0.1, market_p=0.6)
            fb.record("market:polymarket", qid, "will it rain", p=0.6)
        for k in range(10):
            fb.resolve(f"q{k}", outcome=1 if k < 8 else 0)
        board = fb.scoreboard()
        julia = next(s for s in board if s.source == "child:julia")
        market = next(s for s in board if s.source == "market:polymarket")
        assert julia.n == 10 and market.n == 10
        assert julia.brier < market.brier
        assert julia.skill_vs_market is not None and julia.skill_vs_market > 0
        assert board[0].source == "child:julia"
        assert fb.open_questions() == []

    def test_cannot_forecast_resolved_or_double_resolve(self, tmp_path, ledger):
        fb = ForecastBook(tmp_path / "f.jsonl", ledger)
        fb.record("mandel", "q1", "?", 0.5)
        fb.resolve("q1", 1)
        with pytest.raises(ValueError):
            fb.record("mandel", "q1", "?", 0.5)
        with pytest.raises(ValueError):
            fb.resolve("q1", 0)

    def test_latest_forecast_per_question_is_scored(self, tmp_path, ledger):
        fb = ForecastBook(tmp_path / "f.jsonl", ledger)
        fb.record("mandel", "q1", "?", 0.1)
        fb.record("mandel", "q1", "?", 0.9)
        fb.resolve("q1", 1)
        probs, outcomes, _, _ = fb.scored_pairs("mandel")
        assert probs == [0.9] and outcomes == [1]

    def test_market_reference_prefers_market_source(self, tmp_path, ledger):
        fb = ForecastBook(tmp_path / "f.jsonl", ledger)
        fb.record("market:polymarket", "q1", "rain?", 0.6)
        fb.record("child:julia", "q1", "rain?", 0.65, market_p=0.95)   # self-reported market_p is ignored
        fb.resolve("q1", 1)
        sc = fb.score_source("child:julia")
        assert sc.market_reference == "market-source"
        assert sc.skill_vs_market == pytest.approx(1 - (0.35 ** 2) / (0.4 ** 2))
        fb.record("child:julia", "q2", "snow?", 0.7, market_p=0.5)
        fb.resolve("q2", 1)
        assert fb.score_source("child:julia").market_reference == "mixed"

    def test_input_rules(self, tmp_path, ledger):
        fb = ForecastBook(tmp_path / "f.jsonl", ledger)
        with pytest.raises(ValueError):
            fb.record("mandel", "q1", "?", 0.5, market_p=5.0)
        with pytest.raises(ValueError):
            fb.resolve("never-forecast", 1)
        fb.record("mandel", " Q1 ", "Will it rain?", 0.5)
        assert fb.open_questions() == ["q1"]
        fb.resolve("q1", 1)
        with pytest.raises(ValueError):                      # same text under a new id
            fb.record("mandel", "q1-redo", "Will it rain?", 1.0)
        with pytest.raises(ValueError):                      # normalised id already resolved
            fb.record("mandel", "Q1", "other", 0.5)

    def test_reload(self, tmp_path, ledger):
        p = tmp_path / "f.jsonl"
        fb = ForecastBook(p, ledger)
        fb.record("mandel", "q1", "?", 0.3)
        fb.resolve("q1", 0)
        fb2 = ForecastBook(p, ledger)
        assert len(fb2.forecasts) == 1 and "q1" in fb2.resolutions


# -------------------------------------------------------------- children ---

class TestChildRegistry:
    def test_register_report_guidance(self, tmp_path, ledger):
        reg = ChildRegistry(tmp_path / "children", ledger)
        names = reg.suggest_names(3)
        assert len(names) == 3 and names[0][0] == "Julia"
        c = reg.register("Julia", "session_abc", "polymarket-arb", "cross-platform arbitrage bot")
        assert c.status == "active" and c.report_count == 0
        rep = reg.record_report("Julia", "first report", learnings=["fees matter"], metrics={"sharpe": 0.4},
                                questions=["how to size?"])
        g = reg.record_guidance("Julia", "sizing", insights=["I-123"], requests=["report brier weekly"])
        c = reg.get("Julia")
        assert c.report_count == 1 and c.guidance_count == 1
        assert c.metrics == {"sharpe": 0.4}
        assert c.last_contact == rep.ts
        assert reg.reports("Julia")[0].learnings == ["fees matter"]
        assert reg.guidance("Julia")[0].id == g.id
        assert reg.suggest_names(1)[0][0] == "Fatou"
        kinds = [e.kind for e in ledger.events(kind="child")]
        assert kinds == ["child.registered", "child.report", "child.guidance"]

    def test_duplicate_and_reload(self, tmp_path, ledger):
        reg = ChildRegistry(tmp_path / "children", ledger)
        reg.register("Fatou", "s1", "d", "x")
        with pytest.raises(ValueError):
            reg.register("Fatou", "s2", "d", "x")
        with pytest.raises(ValueError):
            reg.register("fatou", "s3", "d", "x")           # case-insensitive collision
        assert reg.get("FATOU").name == "Fatou"
        reg.record_report("fatou", "ok")
        assert reg.get("Fatou").report_count == 1 and len(reg.reports("Fatou")) == 1
        reg.set_status("Fatou", "paused")
        again = ChildRegistry(tmp_path / "children", ledger)
        assert again.get("Fatou").status == "paused"
        assert [c.name for c in again.all()] == ["Fatou"]


# ---------------------------------------------------------------- cycles ---

from mandel.cycles import CycleLog  # noqa: E402


class TestCycleLog:
    def test_start_finish_efficiency(self, tmp_path, ledger):
        log = CycleLog(tmp_path / "c.jsonl", ledger)
        c = log.start("validate min_edge change")
        assert log.current().id == c.id
        with pytest.raises(RuntimeError):
            log.start("second at once")
        log.note_action(c.id, "pre-registered P-1")
        with pytest.raises(ValueError):
            log.finish(c.id, {"gold": 1}, {})
        log.finish(c.id, {"agents": 3, "wall_seconds": 600}, {"proposals_accepted": 1, "insights_validated": 2})
        eff = log.efficiency()
        assert eff["cycles"] == 1 and eff["gains"] == 3
        assert eff["gains_per_unit"]["agents"] == 1.0
        assert eff["gains_per_unit"]["tokens_est"] is None
        assert log.current() is None
        assert [e.kind for e in ledger.events(kind="cycle")] == ["cycle.started", "cycle.finished"]
        again = CycleLog(tmp_path / "c.jsonl", ledger)
        assert again.all()[0].actions == ["pre-registered P-1"]
