"""Archive.store writes a bundle whole and renames it into place: a write that dies part-way leaves the stored bundle
(and its INDEX entry) intact, and rows may stream from the stored bundle while its replacement is written."""

import pytest

from mandel.archive import Archive
from mandel.ledger import Ledger


def _archive(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def _rows(n, tag="a"):
    return [{"value": {"i": i, "tag": tag}, "observed_at": "2026-01-01T00:00:00+00:00",
             "available_at": "2026-01-01T00:00:00+00:00"} for i in range(n)]


def test_failed_rewrite_keeps_the_stored_bundle(tmp_path):
    a = _archive(tmp_path)
    e = a.store("b", kind="data", rows=_rows(5), recipe="r", in_git=False)

    def dying():
        yield from _rows(3, "b")
        raise KeyboardInterrupt("killed mid-write")

    with pytest.raises(KeyboardInterrupt):
        a.store("b", kind="data", rows=dying(), recipe="r", in_git=False)
    assert [r["value"]["tag"] for r in a.load("b")] == ["a"] * 5
    assert a.get("b").sha256 == e.sha256 and a.verify("b")
    assert not list((tmp_path / "archive" / "data").glob("*.partial"))


def test_rewrite_can_stream_from_the_stored_bundle(tmp_path):
    a = _archive(tmp_path)
    a.store("b", kind="data", rows=_rows(4), recipe="r", in_git=False)
    a.store("b", kind="data", rows=({**r, "value": {**r["value"], "tag": "x"}} for r in a.load("b")), recipe="r", in_git=False)
    assert [r["value"] for r in a.load("b")] == [{"i": i, "tag": "x"} for i in range(4)]
    assert a.verify("b")
