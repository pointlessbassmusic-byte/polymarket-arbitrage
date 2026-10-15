"""Batch modules (data unlocks) wired into the runner: every harness is runnable, declares the bundles it loads, maps to a
registered theory and records that theory's null."""

import json

from mandel.experiments import run
from mandel.paths import MANDEL_ROOT


def _index_names() -> set[str]:
    idx = json.loads((MANDEL_ROOT / "archive" / "INDEX.json").read_text(encoding="utf-8"))["bundles"]
    return {e["name"] for e in (idx.values() if isinstance(idx, dict) else idx)}


def test_every_batch_harness_is_wired_with_declared_bundles():
    assert len(run.BATCH_HARNESSES) == 88
    for m in run.BATCH_MODULES:
        for h, fn in m.HARNESSES.items():
            assert run.HARNESSES[h] is fn, h
            assert run.BUNDLES_NEEDED[h], h                        # traced loads, never empty
            assert run.BUNDLES_NEEDED[h] == sorted(set(run.BUNDLES_NEEDED[h])), h
    assert set(run.BATCH_BUNDLES) == set(run.BATCH_HARNESSES)


def test_batch_bundles_are_archived_names():
    names = _index_names()
    for h, bundles in run.BATCH_BUNDLES.items():
        for b in bundles:                                         # a dated daily capture is declared as a name-* pattern
            assert (any(n.startswith(b[:-1]) for n in names) if b.endswith("*") else b in names), (h, b)


def test_batch_harness_names_do_not_shadow_earlier_harnesses():
    earlier = set(run.U2_HARNESSES) | set(run.OM2_HARNESSES) | set(run.XA_HARNESSES)
    assert not earlier & set(run.BATCH_HARNESSES)
    assert sum(len(m.HARNESSES) for m in run.BATCH_MODULES) == len(run.BATCH_HARNESSES)


def test_each_batch_harness_maps_to_one_registered_theory_and_records_its_null():
    reg = run.load_registry()
    ids = {t["id"]: t for t in reg["theories"]}
    for m in run.BATCH_MODULES:
        assert set(m.THEORY_MAP.values()) == set(m.HARNESSES), m.__name__
        for tid, h in m.THEORY_MAP.items():
            assert tid in ids, tid
            assert run.BATCH_THEORY[h] == tid
            assert run._null_for(h) == f"{tid}: {ids[tid]['trial']['null']}"
