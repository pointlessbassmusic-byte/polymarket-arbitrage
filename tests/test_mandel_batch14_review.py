"""Batch 14 (weighting review 2026-10-29): T-743 Treasury-ETF 20-day reversal replication; T-552's BRR replication helper."""

import json
from datetime import date, datetime, timedelta, timezone

import numpy as np

from mandel.experiments import batch4_carry as C
from mandel.experiments import batch14_review as M


class _Entry:
    def __init__(self, name):
        self.name, self.created_at = name, None


class FakeArchive:
    def __init__(self, b):
        self.b = b

    def entries(self, kind=None, tag=None):
        return [_Entry(n) for n in self.b]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name)

    def load(self, name):
        return iter(self.b[name])


def _days(start, n):
    d = date.fromisoformat(start); out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _world(seed, reversal):
    """TLT/IEF adjclose over 2001-2024 with (or without) a planted 20-day reversal, and a DGS10 that moves against price."""
    rng = np.random.default_rng(seed)
    days = _days("2001-01-02", 6000)
    la = np.zeros(len(days)); y = np.full(len(days), 4.0)
    for t in range(1, len(days)):
        drift = 0.0
        if reversal and t > 20:
            drift = -0.004 * (la[t - 1] - la[t - 21])          # pull back a share of the last 20 days' move
        step = drift + 0.006 * rng.normal()
        la[t] = la[t - 1] + step
        y[t] = y[t - 1] - 8.0 * step + 0.01 * rng.normal()     # yields move against prices (duration)
    adj = 100 * np.exp(la)
    def rows(a):
        return [{"available_at": None, "value": {"t": int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()),
                                                  "close": float(a[i]), "adjclose": float(a[i])}} for i, d in enumerate(days)]
    fred = [{"available_at": None, "value": {"day": d.isoformat(), "value": float(y[i])}} for i, d in enumerate(days)]
    return FakeArchive({"daily-history-TLT": rows(adj), "daily-history-IEF": rows(adj * 0.9), "fred-DGS10": fred})


def test_planted_reversal_passes_and_random_walk_does_not():
    stat, n, v, reason = M.b14_treasury_20d_reversal(_world(3, True))
    json.dumps(stat, allow_nan=False)
    assert v == "supported" and n >= M.MIN_N, reason
    assert stat["TLT"]["own_r20_reversal"]["mean"] > 0 and stat["TLT"]["dgs10_d20_lead"]["mean"] > 0
    _stat0, _n0, v0, reason0 = M.b14_treasury_20d_reversal(_world(3, False))
    assert v0 in ("not_supported", "inconclusive") and " — " in reason0


def test_missing_bundle_is_rule_9():
    _stat, n, v, reason = M.b14_treasury_20d_reversal(FakeArchive({"daily-history-TLT": []}))
    assert v == "inconclusive" and "fred-DGS10" in reason and n == 0


def test_brr_replication_is_the_median_of_five_minute_vwap_partitions(monkeypatch):
    """A synthetic hour of 1-minute bars: Coinbase at 100 with volume 1, Kraken at 102 with volume 3 -> every partition's
    VWAP is 101.5; one partition with no volume is skipped; fewer than 6 partitions with volume -> NaN."""
    day = "2026-09-25"
    T0 = C.brr_ts(day) - C.HOUR - 600                       # grid starts ten minutes before the window
    N = 600
    g = {"T0": T0, "N": N, "kr_close": np.full(N, 102.0), "kr_vol": np.full(N, 3.0), "cb_close": np.full(N, 100.0), "cb_vol": np.full(N, 1.0)}
    g["kr_vol"][10 + 55:10 + 60] = 0.0; g["cb_vol"][10 + 55:10 + 60] = 0.0      # the last partition has no volume
    monkeypatch.setattr(C, "brr_replication", C.brr_replication)
    from mandel.experiments import batch6c_kraken as K
    monkeypatch.setattr(K, "stored_months", lambda archive, prefix, months: list(months))
    monkeypatch.setattr(K, "grid", lambda archive, kr, cb: g)
    out = C.brr_replication(None, [day])
    assert out[day][1] == 11 and abs(out[day][0] - 101.5) < 1e-9
    g["kr_vol"][:] = 0.0; g["cb_vol"][:] = 0.0; g["cb_vol"][10:35] = 1.0       # only 5 partitions with volume
    out2 = C.brr_replication(None, [day])
    assert out2[day][1] == 5 and np.isnan(out2[day][0])
