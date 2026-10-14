"""Regression tests from the second adversarial review: the ledger is authoritative."""

import json

import numpy as np
import pytest

from mandel.forecasts import ForecastBook
from mandel.ledger import Ledger
from mandel.proposals import Criterion, IntegrityError, LifecycleError, ProposalBook
from mandel.store import InsightStore
from mandel.validation import code_change_criteria, compare_strategies, deflated_sharpe_ratio, strategy_improvement_criteria
from mandel.validation.backtest_eval import block_bootstrap_pvalue


@pytest.fixture
def env(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    book = ProposalBook(tmp_path / "p.jsonl", ledger)
    store = InsightStore(tmp_path / "i.jsonl", ledger, proposals=book)
    fb = ForecastBook(tmp_path / "f.jsonl", ledger)
    return tmp_path, ledger, book, store, fb


def _rewrite(path, mutate):
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    mutate(rows)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


class TestProposalsAgainstLedger:
    def test_clearing_memory_copy_does_not_allow_rewrite(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        book.record_evidence(p.id, {"dsr": 0.2, "out_of_sample": True, "n_trials": 1})
        book.get(p.id).evidence.clear()                    # attacker clears the in-memory copy
        with pytest.raises((LifecycleError, IntegrityError)):
            book.record_evidence(p.id, {"dsr": 0.99})

    def test_two_books_cannot_double_record(self, env):
        tmp, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        stale = ProposalBook(book.path, ledger)
        book.record_evidence(p.id, {"dsr": 0.1, "out_of_sample": True, "n_trials": 1})
        with pytest.raises((LifecycleError, IntegrityError)):
            stale.record_evidence(p.id, {"dsr": 0.99})

    def test_file_edit_then_decide_is_refused(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        book.record_evidence(p.id, {"dsr": 0.1, "out_of_sample": True, "n_trials": 1})
        def mutate(rows):
            rows[0]["evidence"]["dsr"] = 0.99
        _rewrite(book.path, mutate)
        tampered = ProposalBook(book.path, ledger)
        with pytest.raises(IntegrityError):
            tampered.decide(p.id)
        assert any("evidence differs" in x for x in tampered.reconcile())

    def test_rejected_cannot_be_redecided_after_status_flip(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        book.record_evidence(p.id, {"dsr": 0.1, "out_of_sample": True, "n_trials": 1})
        book.decide(p.id)
        assert book.get(p.id).status == "rejected"
        def mutate(rows):
            rows[0]["status"] = "evaluating"; rows[0]["evidence"]["dsr"] = 0.99
        _rewrite(book.path, mutate)
        tampered = ProposalBook(book.path, ledger)
        with pytest.raises(IntegrityError):
            tampered.decide(p.id)
        problems = tampered.reconcile()
        assert problems and any(p.id in x for x in problems)

    def test_fabricated_in_memory_evidence_without_events_is_refused(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        q = book.get(p.id)
        q.status = "evaluating"; q.evidence = {"dsr": 0.99, "out_of_sample": True, "n_trials": 1}
        with pytest.raises(IntegrityError):
            book.decide(p.id)

    def test_withdraw_after_evidence_blocked_even_if_status_flipped(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        book.record_evidence(p.id, {"dsr": 0.1, "out_of_sample": True, "n_trials": 1})
        book.get(p.id).status = "preregistered"
        with pytest.raises((LifecycleError, IntegrityError)):
            book.withdraw(p.id, "never mind")

    def test_loosened_criteria_caught_by_reconcile_before_evidence(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("dsr", ">=", 0.95)])
        book.preregister(p.id)
        def mutate(rows):
            rows[0]["criteria"][0]["threshold"] = 0.5
            from mandel.proposals import _to_proposal
            rows[0]["criteria_hash"] = _to_proposal(rows[0]).compute_criteria_hash()
        _rewrite(book.path, mutate)
        problems = ProposalBook(book.path, ledger).reconcile()
        assert any("criteria differ" in x for x in problems)

    def test_decision_recomputed_from_ledger(self, env):
        _, ledger, book, _, _ = env
        p = book.draft("t", "h", "mandel:x", "c", code_change_criteria())
        book.preregister(p.id); book.record_evidence(p.id, {"tests_pass": 1}); book.decide(p.id)
        assert book.get(p.id).status == "accepted"
        assert book.gate_from_ledger(p.id).passed
        assert book.reconcile() == []


class TestStoreAgainstLedger:
    def test_forged_acceptance_event_does_not_validate(self, env):
        _, ledger, book, store, _ = env
        ins = store.add("claim", "fact", ["src:01"], 0.5)
        p = book.draft("t", "h", "mandel:x", "c", code_change_criteria())
        book.preregister(p.id)
        # forge: append an accepted event with no evidence events, flip the file status
        ledger.append("proposal.accepted", {"id": p.id, "produces_insights": [ins.id], "rationale": "forged"}, actor="mandel")
        def mutate(rows):
            rows[0]["status"] = "accepted"
        _rewrite(book.path, mutate)
        store2 = InsightStore(store.path, ledger, proposals=ProposalBook(book.path, ledger))
        with pytest.raises(ValueError):
            store2.set_status(ins.id, "validated", by=p.id)
        assert ProposalBook(book.path, ledger).reconcile()        # history is not a legal lifecycle

    def test_retired_is_final(self, env):
        _, _, _, store, _ = env
        ins = store.add("claim", "fact", ["src:01"], 0.5)
        store.set_status(ins.id, "retired", by="src:02")
        with pytest.raises(ValueError):
            store.set_status(ins.id, "candidate", by="src:03")

    def test_converge_whitespace_and_canonical_form(self, env):
        _, _, _, store, _ = env
        ins = store.add("claim", "fact", ["src:01"], 0.5)
        with pytest.raises(ValueError):
            store.set_status(ins.id, "validated", by="converge:src:01, src:01")
        store.set_status(ins.id, "validated", by="converge: src:01 ,src:02")
        assert store.get(ins.id).validated_by == ["converge:src:01,src:02"]

    def test_self_only_cap_on_update(self, env):
        _, _, _, store, _ = env
        ins = store.add("own idea", "heuristic", ["mandel:self"], 0.3)
        with pytest.raises(ValueError):
            store.update_confidence(ins.id, 0.9, reason="felt right")
        store.update_confidence(ins.id, 0.5, reason="still self-only")

    def test_reconcile_detects_file_edits(self, env):
        _, ledger, _, store, _ = env
        ins = store.add("claim", "fact", ["src:01"], 0.5)
        assert store.reconcile() == []
        def mutate(rows):
            rows[0]["status"] = "validated"; rows[0]["confidence"] = 0.99
        _rewrite(store.path, mutate)
        problems = InsightStore(store.path, ledger).reconcile()
        assert problems and ins.id in problems[0]


class TestForecastsAgainstLedger:
    def test_reconcile_detects_probability_and_outcome_edits(self, env):
        _, ledger, _, _, fb = env
        fb.record("child:julia", "q1", "rain?", 0.6)
        fb.resolve("q1", 0)
        assert fb.reconcile() == []
        rows = [json.loads(l) for l in fb.path.read_text().splitlines() if l.strip()]
        rows[0]["p"] = 0.05; rows[1]["outcome"] = 1
        fb.path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        problems = ForecastBook(fb.path, ledger).reconcile()
        assert len(problems) == 2


class TestLedgerAnchor:
    def test_missing_head_fails_verify(self, tmp_path):
        p = tmp_path / "l.jsonl"
        l = Ledger(p)
        l.append("k", {"n": 1})
        l.head_path.unlink()
        ok, msg = Ledger(p).verify()
        assert not ok and "anchor" in msg
        Ledger(p).anchor_now()
        assert Ledger(p).verify()[0]

    def test_empty_file_without_head_is_anomalous(self, tmp_path):
        p = tmp_path / "l.jsonl"
        p.write_text("")
        ok, msg = Ledger(p).verify()
        assert not ok


class TestStatistics:
    def test_trial_count_must_match(self):
        r = np.random.default_rng(0).normal(0, 0.01, 100)
        with pytest.raises(ValueError):
            deflated_sharpe_ratio(r, n_trials=5, trial_sharpes=[0.1, 0.2])
        with pytest.raises(TypeError):
            compare_strategies(r, r)                      # n_trials is required

    def test_studentized_bootstrap_size_under_ar1(self):
        rej = 0
        for s in range(60):
            rng = np.random.default_rng(5000 + s)
            e = rng.normal(0, 1, 60); d = np.zeros(60)
            for t in range(1, 60):
                d[t] = 0.5 * d[t - 1] + e[t]
            rej += block_bootstrap_pvalue(d, np.zeros(60), n_boot=200, seed=s) < 0.05
        assert rej <= 9, f"{rej}/60 false rejections under AR(1)"
