"""The hypothesis registry must stay loadable, complete and searchable."""

import importlib
import shlex

import pytest

from cryptobot import hypotheses as H


def test_registry_loads_and_validates():
    rows = H.load()
    assert len(rows) >= 20
    assert {r["verdict"] for r in rows} <= set(H.VERDICTS)


def test_the_two_live_strategies_are_registered_alive():
    alive = {r["id"] for r in H.load() if r["verdict"] == "alive"}
    assert {"perp-bounce-short", "funding-carry"} <= alive


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
