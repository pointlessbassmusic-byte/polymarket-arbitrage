"""End-to-end CLI tests: a fresh session should be able to run the loop from the shell."""

import json

import pytest

from mandel import cli


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MANDEL_DATA_ROOT", str(tmp_path / "state"))
    # paths.DATA_ROOT is read at import; patch the module attribute used by data_path
    import mandel.paths as paths
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "state")
    return tmp_path / "state"


def run(*argv):
    return cli.main(list(argv))


def test_proposal_loop_from_cli(data_root, capsys):
    assert run("proposal-draft", "Tighter edge", "--hypothesis", "min_edge 1.5% beats 1%", "--target", "repo:core/arb_engine.py",
               "--change", "min_edge 0.01->0.015", "--criteria-set", "strategy", "--trials", "3") == 0
    out = capsys.readouterr().out
    pid = out.split()[1]
    assert run("proposal-preregister", pid) == 0
    assert run("proposal-evidence", pid, "sharpe_diff=0.2", "mean_diff=0.001", "bootstrap_p=0.01", "dsr=0.97",
               "n_trials=3", "out_of_sample=true") == 0
    assert "PASS" in capsys.readouterr().out
    assert run("insight-add", "edge survives fees", "--kind", "heuristic", "--prov", "src:12", "--conf", "0.6") == 0
    iid = json.loads(capsys.readouterr().out)["id"]
    assert run("proposal-decide", pid, "--insight", "I-doesnotexist") == 1      # unknown insight refused
    capsys.readouterr()
    assert run("proposal-decide", pid, "--insight", iid) == 0
    out = capsys.readouterr().out
    assert "ACCEPTED" in out and f"insight {iid} -> validated" in out
    assert run("insights", "--status", "validated") == 0
    assert iid in capsys.readouterr().out
    assert run("proposals", "--status", "accepted") == 0
    assert pid in capsys.readouterr().out
    assert run("verify") == 0


def test_child_and_forecast_cli(data_root, capsys):
    assert run("names", "2") == 0
    assert "Julia" in capsys.readouterr().out
    assert run("child-register", "Julia", "--session", "session_1", "--domain", "arb", "--desc", "the arb bot") == 0
    assert run("child-report", "Julia", "--summary", "week 1", "--learning", "fees dominate", "--metric", "sharpe=0.3") == 0
    assert run("child-guide", "Julia", "--summary", "sizing", "--request", "report brier weekly") == 0
    capsys.readouterr()
    assert run("child-show", "Julia") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["child"]["report_count"] == 1 and shown["reports"][0]["metrics"] == {"sharpe": 0.3}
    assert run("forecast-record", "child:Julia", "q1", "0.8", "--market-p", "0.6") == 0
    assert run("forecast-record", "market:polymarket", "q1", "0.6") == 0
    assert run("forecast-resolve", "q1", "1") == 0
    assert run("forecasts") == 0
    out = capsys.readouterr().out
    assert "child:Julia" in out and "skill_vs_market=+" in out
    capsys.readouterr()
    assert run("status") == 0
    st = json.loads(capsys.readouterr().out)
    assert st["ledger"]["ok"] and st["children"][0]["name"] == "Julia" and st["forecasts"]["resolved"] == 1


def test_bad_criterion_rejected(data_root, capsys):
    assert run("proposal-draft", "t", "--hypothesis", "h", "--target", "x", "--change", "c", "--criterion", "dsr~0.9") == 1
    assert "bad criterion" in capsys.readouterr().err
    assert run("proposal-draft", "t", "--hypothesis", "h", "--target", "x", "--change", "c", "--criterion", "dsr>=1.2.3") == 1


def test_failing_gate_needs_confirmation_and_cycles(data_root, capsys):
    assert run("cycle-start", "try a thing") == 0
    cid = capsys.readouterr().out.split()[2].rstrip(":")
    assert run("cycle-start", "another") == 1                                   # only one open cycle
    capsys.readouterr()
    assert run("proposal-draft", "t", "--hypothesis", "h", "--target", "mandel:x", "--change", "c",
               "--criteria-set", "code", "--criterion", "brier_delta<-1e-3") == 0
    pid = capsys.readouterr().out.split()[1]
    assert run("proposal-preregister", pid) == 0
    assert run("proposal-evidence", pid, "tests_pass=1", "brier_delta=0.2", "out_of_sample=true", "n_trials=1") == 0
    capsys.readouterr()
    assert run("proposal-decide", pid) == 1                                     # gate fails: not recorded
    assert "confirm-reject" in capsys.readouterr().out
    assert run("proposal-evidence", pid, "brier_delta=-0.5") == 1               # write-once
    assert run("proposal-decide", pid, "--confirm-reject") == 0
    assert "REJECTED" in capsys.readouterr().out
    assert run("cycle-note", cid, "rejected " + pid) == 0
    assert run("cycle-finish", cid, "--cost", "agents=2", "--outcome", "proposals_rejected=1") == 0
    assert run("cycle-finish", cid, "--cost", "agents=2") == 1                  # already finished
    assert run("proposal-show", "P-nope") == 1                                  # unknown id, no traceback
    err = capsys.readouterr().err
    assert "unknown id" in err
    assert run("verify") == 0
