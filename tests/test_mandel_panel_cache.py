"""The cached daily panel serves exactly what batch6c_cal._daily returns per bundle."""

import math

import numpy as np

from mandel.experiments import panel_cache as PC


class _E:
    def __init__(self, name, sha):
        self.name, self.sha256, self.rows, self.created_at = name, sha, 3, "2026-01-01T00:00:00+00:00"


class _Arch:
    def __init__(self, data):
        self.data = data
        self.probed = []

    def entries(self):
        return [_E(n, str(len(v))) for n, v in self.data.items()]

    def get(self, name):
        self.probed.append(name)
        return _E(name, "x")

    def load(self, name):
        return iter(self.data[name])


def _row(day_epoch, c, a=None):
    return {"available_at": "2025-01-01T00:00:00+00:00",
            "value": {"t": day_epoch, "open": c, "high": c, "low": c, "close": c, "adjclose": a, "volume": 10}}


def test_panel_matches_daily_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "CACHE", tmp_path / "p.npz")
    PC._MEMO.clear()
    d0 = 1_700_000_000
    arch = _Arch({"daily-history-AAA": [_row(d0, 10.0, 5.0), _row(d0 + 86400, 12.0, None), _row(d0 + 2 * 86400, -1.0, 1.0)],
                  "daily-history-BBB": [_row(d0 + 86400, 3.0, 3.0)]})
    p = PC.daily_panel(arch)
    assert list(p.symbols) == ["AAA", "BBB"] and len(p.days) == 2           # the non-positive close is skipped
    a = p.col("AAA", "adjclose")
    assert a[0] == 5.0 and math.isclose(a[1], 12.0 * 0.5)                  # missing adjclose carries the ratio forward
    assert np.isnan(p.col("BBB", "close")[0]) and p.col("BBB", "close")[1] == 3.0
    assert set(arch.probed) >= {"daily-history-AAA", "daily-history-BBB"}
    PC._MEMO.clear()
    q = PC.daily_panel(arch)                                               # served from the cache file
    assert np.array_equal(np.nan_to_num(q.adjclose), np.nan_to_num(p.adjclose))
