"""The hypothesis registry must stay loadable, complete and searchable."""

import importlib
import shlex

import pytest

from cryptobot import hypotheses as H


def test_registry_loads_and_validates():
    rows = H.load()
    assert len(rows) >= 20
    assert {r["verdict"] for r in rows} <= set(H.VERDICTS)


def test_deployed_strategies_carry_their_diagnostics():
    """The deployed strategies must be registered, and anything selected
    from a search must record how big the search was. The bounce-short
    is 'inconclusive' since the Deflated Sharpe run; carry is still
    'alive' and has not been through the diagnostics."""
    rows = {r["id"]: r for r in H.load()}
    assert rows["funding-carry"]["verdict"] == "alive"
    for rid in ("perp-bounce-short", "bounce-short-us3"):
        r = rows[rid]
        assert r["verdict"] == "inconclusive"
        assert r["trials_run"] >= 4000 and 0 < r["n_eff"] < r["trials_run"]
        assert 0 <= r["pbo"] <= 1 and 0 <= r["dsr"] <= 1


def test_rerun_commands_point_at_real_modules():
    for r in H.load():
        cmd = r["rerun"]
        if not cmd.startswith("python -m "):
            continue
        mod = shlex.split(cmd)[2]
        importlib.import_module(mod)


def test_validate_rejects_bad_entries():
    good = {k: "x" for k in H.REQUIRED} | {"verdict": "killed"}
    with pytest.raises(ValueError, match="missing"):
        H.validate([{**good, "claim": ""}])
    with pytest.raises(ValueError, match="verdict"):
        H.validate([{**good, "verdict": "maybe"}])
    with pytest.raises(ValueError, match="duplicate"):
        H.validate([good, dict(good)])


def test_similar_surfaces_an_already_killed_idea():
    hits = H.similar(H.load(), "short newly listed perps after launch")
    assert hits and hits[0][1]["id"] == "short-new-listings"


def test_similar_returns_nothing_for_unrelated_text():
    assert H.similar(H.load(), "zzz qqq") == []
