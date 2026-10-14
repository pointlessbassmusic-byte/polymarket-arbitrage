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
    assert run("proposal-decide", pid, "--insight", "I-x") == 0
    assert "ACCEPTED" in capsys.readouterr().out
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


def test_bad_criterion_rejected(data_root):
    with pytest.raises(SystemExit):
        run("proposal-draft", "t", "--hypothesis", "h", "--target", "x", "--change", "c", "--criterion", "dsr~0.9")
