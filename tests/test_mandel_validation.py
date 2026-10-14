"""Tests for Mandel's validation statistics and gate."""

import math

import numpy as np
import pytest

from mandel.proposals import Criterion, IntegrityError, LifecycleError, ProposalBook
from mandel.ledger import Ledger
from mandel.validation import (
    brier_score, brier_skill_score, calibration_table, compare_strategies, deflated_sharpe_ratio,
    evaluate, evidence_from_comparison, expected_calibration_error, expected_max_sharpe, log_loss,
    murphy_decomposition, probabilistic_sharpe_ratio, sharpe_ratio, strategy_improvement_criteria,
    walk_forward_splits, code_change_criteria,
)
from mandel.validation.backtest_eval import block_bootstrap_pvalue, norm_cdf, norm_ppf


# --------------------------------------------------------------- scoring ---

class TestScoring:
    def test_brier_extremes(self):
        assert brier_score([1, 0, 1], [1, 0, 1]) == 0.0
        assert brier_score([0.5, 0.5], [1, 0]) == 0.25
        assert brier_score([0, 1], [1, 0]) == 1.0

    def test_log_loss_finite_when_certain_and_wrong(self):
        assert math.isfinite(log_loss([1.0], [0]))
        assert log_loss([0.9], [1]) < log_loss([0.6], [1])

    def test_input_validation(self):
        with pytest.raises(ValueError):
            brier_score([1.2], [1])
        with pytest.raises(ValueError):
            brier_score([0.5], [2])
        with pytest.raises(ValueError):
            brier_score([], [])

    def test_murphy_identity_exact(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0, 1, 400)
        o = (rng.uniform(0, 1, 400) < p).astype(int)
        m = murphy_decomposition(p, o)
        assert abs(m.reconstructed - m.brier) < 1e-12
        assert m.reliability < 0.02          # calibrated by construction
        assert m.resolution > 0.03           # informative
        assert abs(m.uncertainty - o.mean() * (1 - o.mean())) < 1e-12

    def test_calibration_table_and_ece(self):
        p = [0.05] * 10 + [0.95] * 10
        o = [0] * 10 + [1] * 10
        table = calibration_table(p, o, n_bins=10)
        assert [b.n for b in table] == [10, 10]
        assert expected_calibration_error(p, o) == pytest.approx(0.05)

    def test_skill_score_sign(self):
        o = [1, 1, 1, 0, 0, 0]
        good = [0.9, 0.8, 0.9, 0.1, 0.2, 0.1]
        market = [0.6, 0.6, 0.6, 0.4, 0.4, 0.4]
        assert brier_skill_score(good, o, market) > 0
        assert brier_skill_score(market, o, good) < 0
        assert brier_skill_score(market, o, market) == 0


# ---------------------------------------------------------- backtest_eval --

class TestBacktestEval:
    def test_normal_helpers(self):
        assert norm_cdf(0) == pytest.approx(0.5)
        assert norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-5)
        assert norm_ppf(0.5) == pytest.approx(0.0, abs=1e-9)
        for p in (0.001, 0.1, 0.9, 0.999):
            assert norm_cdf(norm_ppf(p)) == pytest.approx(p, abs=1e-7)

    def test_sharpe(self):
        assert sharpe_ratio([0.01, 0.01, 0.01]) == 0.0           # zero variance guard
        assert sharpe_ratio([1.0]) == 0.0
        r = [0.01, -0.005, 0.02, 0.0]
        assert sharpe_ratio(r, periods_per_year=252) == pytest.approx(sharpe_ratio(r) * math.sqrt(252))

    def test_psr_monotone_in_benchmark_and_sample(self):
        a = probabilistic_sharpe_ratio(0.1, 0.0, 100, 0.0, 3.0)
        b = probabilistic_sharpe_ratio(0.1, 0.05, 100, 0.0, 3.0)
        c = probabilistic_sharpe_ratio(0.1, 0.0, 1000, 0.0, 3.0)
        assert a > b and c > a
        assert probabilistic_sharpe_ratio(0.1, 0.0, 1, 0.0, 3.0) == 0.0

    def test_expected_max_sharpe_grows_with_trials(self):
        assert expected_max_sharpe(1, 0.1) == 0.0
        assert expected_max_sharpe(10, 0.1) < expected_max_sharpe(100, 0.1)
        assert expected_max_sharpe(100, 0.1) == pytest.approx(
            math.sqrt(0.1) * ((1 - 0.5772156649) * norm_ppf(1 - 1 / 100) + 0.5772156649 * norm_ppf(1 - 1 / (100 * math.e))))

    def test_dsr_penalises_more_trials(self):
        rng = np.random.default_rng(3)
        r = rng.normal(0.002, 0.01, 250)
        d1 = deflated_sharpe_ratio(r, n_trials=1)
        d50 = deflated_sharpe_ratio(r, n_trials=50, var_trials_sr=0.01)
        assert d1 > d50

    def test_bootstrap_p_detects_clear_edge_and_not_noise(self):
        rng = np.random.default_rng(5)
        inc = rng.normal(0, 0.01, 400)
        cand = inc + 0.004 + rng.normal(0, 0.002, 400)
        assert block_bootstrap_pvalue(cand, inc, n_boot=1000) < 0.01
        with pytest.raises(ValueError):
            block_bootstrap_pvalue([1.0] * 5, [0.0] * 5)        # too short for blocks
        # Under the null (independent, equal-mean series) p-values should be roughly uniform:
        # across many seeds the rejection rate at 0.05 must stay small.
        rejections = 0
        for s in range(40):
            r2 = np.random.default_rng(1000 + s)
            a, b = r2.normal(0, 0.01, 400), r2.normal(0, 0.01, 400)
            rejections += block_bootstrap_pvalue(a, b, n_boot=400, seed=s) < 0.05
        assert rejections <= 6, f"{rejections}/40 false rejections"
        with pytest.raises(ValueError):
            block_bootstrap_pvalue([1, 2], [1])

    def test_walk_forward_splits_are_ordered_and_embargoed(self):
        splits = list(walk_forward_splits(n=100, n_splits=4, min_train=40, embargo=5))
        assert len(splits) == 4
        prev_end = 0
        for train, test in splits:
            assert train[0] == 0
            assert test[0] - train[-1] - 1 == 5          # embargo gap
            assert test[0] >= prev_end
            prev_end = test[-1] + 1
        assert splits[-1][1][-1] == 99
        with pytest.raises(ValueError):
            list(walk_forward_splits(10, 3, 9, 2))

    def test_compare_strategies_pass_fail(self):
        rng = np.random.default_rng(7)
        inc = rng.normal(0, 0.01, 300)
        cand = inc + 0.005
        res = compare_strategies(cand, inc, n_trials=5, trial_sharpes=[0.0, 0.1, 0.05, -0.02, 0.5])
        assert res.passes()
        res2 = compare_strategies(inc, cand, n_trials=5)
        assert not res2.passes()
        assert any("variance floor" in n for n in res2.notes)
        ev = evidence_from_comparison(res, holdout_id="wf-2025Q3")
        assert ev["out_of_sample"] is True and ev["n_trials"] == 5 and ev["holdout_id"] == "wf-2025Q3"
        with pytest.raises(TypeError):
            evidence_from_comparison(res)                       # holdout_id is mandatory
        with pytest.raises(ValueError):
            evidence_from_comparison(res, holdout_id="  ")

    def test_dsr_deflates_best_of_many_by_default(self):
        """Best of 40 zero-skill series must rarely pass when n_trials is honestly declared,
        even when no trial Sharpes are supplied (the old default applied no deflation)."""
        rng = np.random.default_rng(21)
        passes = 0
        for _ in range(40):
            trials = rng.normal(0, 0.01, size=(40, 250))
            best = trials[np.argmax(trials.mean(axis=1) / trials.std(axis=1, ddof=1))]
            passes += deflated_sharpe_ratio(best, n_trials=40) >= 0.95
        assert passes <= 4, f"{passes}/40 lucky candidates passed"


# ---------------------------------------------------- proposals and gate ---

@pytest.fixture
def book(tmp_path):
    return ProposalBook(tmp_path / "p.jsonl", Ledger(tmp_path / "l.jsonl"))


class TestProposalsAndGate:
    def test_full_accept_path(self, book):
        p = book.draft("Tighter min_edge", "Raising min_edge to 1.5% improves net PnL per trade",
                       "repo:core/arb_engine.py", "min_edge 0.01 -> 0.015", strategy_improvement_criteria(),
                       n_trials_declared=5, baseline={"sharpe": 0.1})
        assert p.status == "drafted"
        book.preregister(p.id)
        rng = np.random.default_rng(11)
        inc = rng.normal(0, 0.01, 300)
        res = compare_strategies(inc + 0.005, inc, n_trials=5)
        book.record_evidence(p.id, evidence_from_comparison(res, holdout_id="wf-1"))
        g = evaluate(book.get(p.id))
        assert g.passed, g.rationale()
        book.decide(p.id, produces_insights=["I-1"])
        assert book.get(p.id).status == "accepted"
        assert book.get(p.id).gate_result["passed"] is True
        kinds = [e.kind for e in book.ledger.events(kind="proposal")]
        assert kinds == ["proposal.drafted", "proposal.preregistered", "proposal.evidence", "proposal.accepted"]
        # reload round-trip keeps criteria, hash and integrity
        again = ProposalBook(book.path, book.ledger)
        q = again.get(p.id)
        assert q.criteria_hash == p.criteria_hash and len(q.criteria) == 4
        again.check_integrity(q)
        assert again.reconcile() == []

    def test_in_sample_evidence_fails(self, book):
        p = book.draft("t", "h", "mandel:x", "c", strategy_improvement_criteria())
        book.preregister(p.id)
        book.record_evidence(p.id, {"sharpe_diff": 1, "mean_diff": 1, "bootstrap_p": 0.0, "dsr": 1.0})
        g = evaluate(book.get(p.id))
        assert not g.passed and any("out_of_sample" in r for r in g.reasons)
        assert any("n_trials not reported" in r for r in g.reasons)

    def test_non_finite_and_bool_values_fail(self, book):
        p = book.draft("t", "h", "mandel:x", "c", strategy_improvement_criteria())
        book.preregister(p.id)
        book.record_evidence(p.id, {"sharpe_diff": float("inf"), "mean_diff": True, "bootstrap_p": float("-inf"),
                                    "dsr": "high", "out_of_sample": True, "n_trials": 1})
        g = evaluate(book.get(p.id))
        assert not g.passed and all(not c.passed for c in g.checks)

    def test_evidence_is_write_once(self, book):
        p = book.draft("t", "h", "mandel:x", "c", strategy_improvement_criteria(), n_trials_declared=3)
        book.preregister(p.id)
        book.record_evidence(p.id, {"n_trials": 40, "out_of_sample": True})
        with pytest.raises(LifecycleError):
            book.record_evidence(p.id, {"n_trials": 3})
        book.record_evidence(p.id, {"n_trials": 40, "dsr": 0.99})   # same value is fine
        with pytest.raises(ValueError):
            book.record_evidence(p.id, {})

    def test_hand_edit_detected_against_ledger(self, book):
        import json
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("brier_delta", "<", 0.0)])
        book.preregister(p.id)
        # attacker loosens the criterion AND recomputes the hash in the file
        rows = [json.loads(l) for l in book.path.read_text().splitlines()]
        rows[0]["criteria"][0]["threshold"] = 0.5
        from mandel.proposals import _to_proposal
        rows[0]["criteria_hash"] = _to_proposal(rows[0]).compute_criteria_hash()
        book.path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        tampered = ProposalBook(book.path, book.ledger)
        with pytest.raises(IntegrityError):
            tampered.record_evidence(p.id, {"brier_delta": 0.3, "out_of_sample": True, "n_trials": 1})

    def test_duplicate_hypothesis_needs_supersedes(self, book):
        p = book.draft("t", "same hypothesis", "mandel:x", "c", code_change_criteria())
        book.preregister(p.id); book.record_evidence(p.id, {"tests_pass": 0}); book.decide(p.id)
        assert book.get(p.id).status == "rejected"
        with pytest.raises(LifecycleError):
            book.draft("t2", "same hypothesis", "mandel:x", "c", code_change_criteria())
        q = book.draft("t2", "same hypothesis", "mandel:x", "c", code_change_criteria(), supersedes=p.id)
        assert q.supersedes == p.id

    def test_reconcile_detects_flipped_status(self, book):
        import json
        p = book.draft("t", "h", "mandel:x", "c", code_change_criteria())
        book.preregister(p.id); book.record_evidence(p.id, {"tests_pass": 0}); book.decide(p.id)
        rows = [json.loads(l) for l in book.path.read_text().splitlines()]
        rows[0]["status"] = "accepted"
        book.path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        problems = ProposalBook(book.path, book.ledger).reconcile()
        assert problems and "file says accepted, ledger says rejected" in problems[0]

    def test_more_trials_than_declared_fails(self, book):
        p = book.draft("t", "h", "mandel:x", "c", strategy_improvement_criteria(), n_trials_declared=3)
        book.preregister(p.id)
        book.record_evidence(p.id, {"sharpe_diff": 1, "mean_diff": 1, "bootstrap_p": 0.0, "dsr": 1.0,
                                    "out_of_sample": True, "n_trials": 40})
        g = evaluate(book.get(p.id))
        assert not g.passed and any("re-register" in r for r in g.reasons)

    def test_missing_metric_fails(self, book):
        p = book.draft("t", "h", "mandel:x", "c", code_change_criteria())
        book.preregister(p.id)
        book.record_evidence(p.id, {"notes": "ran the suite but forgot the number"})
        g = evaluate(book.get(p.id))
        assert not g.passed and g.checks[0].note == "metric not reported"

    def test_lifecycle_guards(self, book):
        p = book.draft("t", "h", "mandel:x", "c", code_change_criteria())
        with pytest.raises(LifecycleError):
            book.record_evidence(p.id, {"tests_pass": 1})
        with pytest.raises(LifecycleError):
            book.decide(p.id)
        book.preregister(p.id)
        with pytest.raises(LifecycleError):
            book.edit_criteria(p.id, [Criterion("tests_pass", "==", 1.0)])
        with pytest.raises(LifecycleError):
            book.preregister(p.id)
        book.record_evidence(p.id, {"tests_pass": 1})
        with pytest.raises(LifecycleError):                  # evidence seen: must decide, not withdraw
            book.withdraw(p.id, "changed my mind")
        book.decide(p.id)
        assert book.get(p.id).status == "accepted"
        with pytest.raises(LifecycleError):
            book.withdraw(p.id, "late")
        book.roll_back(p.id, "regressed in production")
        assert book.get(p.id).status == "rolled_back"

    def test_criteria_tamper_detected(self, book, tmp_path):
        p = book.draft("t", "h", "mandel:x", "c", [Criterion("brier_delta", "<", 0.0)])
        book.preregister(p.id)
        # simulate hand-editing the frozen criteria
        book.get(p.id).criteria[0].threshold = 0.5
        with pytest.raises(IntegrityError):
            book.record_evidence(p.id, {"brier_delta": 0.3, "out_of_sample": True})

    def test_bad_criterion(self, book):
        with pytest.raises(ValueError):
            book.draft("t", "h", "x", "c", [Criterion("m", "~", 1.0)])
        with pytest.raises(ValueError):
            book.draft("t", "h", "x", "c", [])
        with pytest.raises(ValueError):
            book.draft("t", "h", "x", "c", [Criterion("m", ">", float("-inf"))])
        with pytest.raises(ValueError):
            book.draft("t", "h", "x", "c", [Criterion("m", ">", "abc")])
