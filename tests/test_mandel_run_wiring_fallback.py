"""The runner scores a batch-mapped harness even when the registry's experiments field lacks it (2026-10-29 orphan rows)."""

from mandel.experiments import run as R


def test_batch_mapped_harness_scores_its_theory_and_writes_the_experiments_field():
    h, tid = next(iter(R.BATCH_THEORY.items()))
    reg = {"theories": [{"id": tid, "status": "untested", "experiments": []}, {"id": "T-0", "status": "untested", "experiments": ["x"]}]}
    out = R._scored_theories(reg)
    assert out[h] == [tid] and reg["theories"][0]["experiments"] == [h] and out["x"] == ["T-0"]


def test_blocked_theory_keeps_its_status_but_the_runner_says_why(capsys):
    reg = {"theories": [{"id": "T-9", "status": "blocked", "results": []}]}
    R._apply_result(reg, ["T-9"], "X-test", "supported", False)
    assert reg["theories"][0]["status"] == "blocked" and reg["theories"][0]["results"] == []
    assert "stays blocked" in capsys.readouterr().out
