"""Tests for the archive, the point-in-time store, and the experiment harnesses on synthetic data."""

import numpy as np
import pytest

from mandel.archive import Archive
from mandel.data.store import Observation, ObservationStore, point_in_time
from mandel.experiments import ExperimentLog
from mandel.experiments.markov import markov_vs_persistence
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.scaling import hurst_with_interval, multifractal_test
from mandel.ledger import Ledger
from mandel.store import InsightStore


@pytest.fixture
def env(tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    return tmp_path, ledger, Archive(tmp_path / "archive", ledger)


class TestArchive:
    def test_store_load_verify_index(self, env):
        tmp, ledger, a = env
        e = a.store("sample", "data", ({"i": i, "v": i * 0.5} for i in range(100)), recipe="range(100)", tags=["t"], schema="{i, v}")
        assert e.rows == 100 and e.in_git and e.path.endswith("sample.jsonl.gz")
        rows = list(a.load("sample"))
        assert rows[0] == {"i": 0, "v": 0.0} and len(rows) == 100
        assert a.verify("sample")
        again = Archive(tmp / "archive", ledger)
        assert again.get("sample").sha256 == e.sha256 and again.summary()["bundles"] == 1
        assert [ev.kind for ev in ledger.events(kind="archive")] == ["archive.stored"]
        with pytest.raises(ValueError):
            a.store("x", "weird", [], recipe="")

    def test_park_and_unpark_insight(self, env):
        tmp, ledger, a = env
        store = InsightStore(tmp / "i.jsonl", ledger)
        ins = store.add("maybe later", "heuristic", ["src:03"], 0.4)
        a.park_insight(store, ins.id, "no data to test it this iteration")
        assert "parked" in store.get(ins.id).tags and "parked:" in store.get(ins.id).notes
        assert store.get(ins.id).status == "candidate"           # kept, not deleted
        a.unpark_insight(store, ins.id, "data arrived")
        assert "parked" not in store.get(ins.id).tags
        assert [ev.kind for ev in ledger.events(kind="insight.")][-2:] == ["insight.parked", "insight.unparked"]


class TestPointInTime:
    def test_filter_and_bundle_roundtrip(self, env):
        tmp, ledger, a = env
        st = ObservationStore(a)
        obs = [Observation("polymarket", "price", "tok", observed_at=f"2026-01-0{d}T00:00:00+00:00", available_at=f"2026-01-0{d}T00:00:00+00:00", value={"p": d / 10}) for d in range(1, 8)]
        st.write_bundle("prices", obs, recipe="synthetic")
        assert len(list(st.read("prices"))) == 7
        assert len(list(st.read("prices", decision_ts="2026-01-03T12:00:00+00:00"))) == 3
        assert list(point_in_time([{"available_at": "2026-02-01"}], "2026-01-01")) == []


class TestHarnesses:
    def test_pbo_null_and_signal(self):
        rng = np.random.default_rng(0)
        R = rng.normal(0, 0.01, (320, 12))
        assert 0.3 <= pbo_cscv(R)["pbo"] <= 0.75
        R[:, 2] += 0.005
        assert pbo_cscv(R)["pbo"] < 0.1

    def test_multifractal_null_and_hurst(self):
        rng = np.random.default_rng(1)
        bm = np.cumsum(rng.normal(0, 1, 1500))
        r = multifractal_test(bm, n_shuffles=40)
        assert r.n == 1500 and not r.exceeds_null
        h = hurst_with_interval(bm, n_null=40)
        assert 0.35 < h["H"] < 0.65 and not h["outside_null"]

    def test_markov_memoryless(self):
        rng = np.random.default_rng(2)
        p = 1 / (1 + np.exp(-np.cumsum(rng.normal(0, 0.1, 800))))
        r = markov_vs_persistence(p)
        assert r["n_test"] > 100 and abs(r["improvement_bits"]) < 0.05

    def test_experiment_log_records_to_ledger(self, env):
        tmp, ledger, _ = env
        log = ExperimentLog(tmp / "x.jsonl", ledger)
        res = log.record("markov_baseline", ["T-001"], {"gain": np.float64(0.01)}, "base rate", 100, "not_supported", "no gain")
        assert log.all()[0].statistic == {"gain": 0.01}
        assert ledger.events(kind="experiment.recorded")[0].payload["id"] == res.id
        with pytest.raises(ValueError):
            log.record("x", [], {}, "", 0, "maybe", "")
