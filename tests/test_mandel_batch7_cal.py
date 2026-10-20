"""Synthetic tests for mandel.experiments.batch7_cal (T-547, T-548, T-549, T-558, T-555): a planted effect that passes and a
null that does not, per core function, plus the harness contract (missing bundles named and inconclusive, JSON-safe stat,
verdict set) on fake archives. No network, no real archive."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch7_cal as M

UTC = timezone.utc
VERDICTS = {"supported", "not_supported", "inconclusive"}


class _Entry:
    def __init__(self, name):
        self.name = name
        self.created_at = None


class FakeArchive:
    def __init__(self, bundles: dict):
        self.b = bundles

    def entries(self, kind=None, tag=None):
        return [_Entry(n) for n in self.b]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name)

    def load(self, name):
        return iter(self.b[name])


def weekdays(start: str, end: str) -> list:
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _ts(day: str, hour: int = 14, minute: int = 30) -> float:
    return datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), hour, minute, tzinfo=UTC).timestamp()


def bar_rows(days, o, h, l, c, adj=None):
    adj = c if adj is None else adj
    return [{"available_at": None, "value": {"t": _ts(d), "open": float(o[i]), "high": float(h[i]), "low": float(l[i]),
                                             "close": float(c[i]), "adjclose": float(adj[i])}} for i, d in enumerate(days)]


def _json_ok(stat):
    json.dumps(stat, allow_nan=False)


# ============================================================================================ statistics ==

def test_holm_and_count():
    assert M.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert M.holm([None, 0.01]) == [None, 0.02]
    assert M._count_crit([True, True, False], 2) is True
    assert M._count_crit([True, None, False], 2) is None
    assert M._count_crit([True, False, False], 2) is False


def test_cluster_boot_planted_and_null():
    rng = np.random.default_rng(1)
    g = np.repeat(np.arange(200), 20)
    pg, pl, ci = M.cluster_boot(rng.normal(0.5, 1.0, g.size), g, n_boot=500)
    assert pg < 0.01 and ci[0] > 0
    pg0, pl0, _ = M.cluster_boot(rng.normal(0.0, 1.0, g.size), g, n_boot=500)
    assert pg0 > 0.01 or pl0 > 0.01


def test_tom_flags_window_and_anchor():
    days = weekdays("2020-01-01", "2020-03-31")
    fl, anc = M.tom_flags(days)
    jan = [i for i, d in enumerate(days) if d.startswith("2020-01")]
    feb = [i for i, d in enumerate(days) if d.startswith("2020-02")]
    assert all(fl[i] for i in jan[:3] + jan[-4:]) and not fl[jan[3]]
    assert anc[feb[0]] == "2020-01" and anc[feb[3]] == "2020-02"


# ================================================================================================ T-547 ==

def _tom_series(effect: float, n_etf: int = 21, seed: int = 0, start="1999-11-01", end="2026-09-30"):
    days = weekdays(start, end)
    fl, _ = M.tom_flags(days)
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.006, len(days))
    out = {}
    for k in range(n_etf):
        r = common + rng.normal(0, 0.004, len(days)) + effect * fl
        out[f"E{k:02d}"] = (days, 50 * np.cumprod(1 + r))
    return out


def test_tom_panel_planted_passes():
    rep = M.tom_panel(_tom_series(0.0015), n_expected=21, n_boot=500)
    assert rep["verdict"] == "supported", rep["reason"] + rep["why"]
    assert rep["n_months"] >= 200 and rep["net_diff_bps"] > 3


def test_tom_panel_null_fails():
    rep = M.tom_panel(_tom_series(0.0, seed=3), n_expected=21, n_boot=500)
    assert rep["verdict"] != "supported"


# ================================================================================================ T-548 ==

def _season_series(winter_extra_month: float, n_etf: int = 21, seed: int = 0):
    days = weekdays("1999-11-01", "2026-09-30")
    rng = np.random.default_rng(seed)
    w = np.array([int(d[5:7]) in (11, 12, 1, 2, 3, 4) for d in days])
    common = rng.normal(0, 0.008, len(days))
    out = {}
    for k in range(n_etf):
        r = common + rng.normal(0, 0.004, len(days)) + w * winter_extra_month / 21.0
        out[f"E{k:02d}"] = (days, 30 * np.cumprod(1 + r))
    return out


def test_halloween_planted_passes():
    rep = M.halloween_panel(_season_series(0.03), n_expected=21, n_boot=500)
    assert rep["verdict"] == "supported", rep["reason"] + rep["why"]
    assert rep["n_months"] == 321


def test_halloween_null_fails():
    rep = M.halloween_panel(_season_series(-0.01, seed=5), n_expected=21, n_boot=500)
    assert rep["verdict"] == "not_supported"


# ================================================================================================ T-549 ==

def _night_bars(night_mu: float, seed: int = 0, start="2000-01-03", end="2013-12-31"):
    days = weekdays(start, end)
    rng = np.random.default_rng(seed)
    n = len(days)
    O, C = np.empty(n), np.empty(n)
    C_prev = 100.0
    for i in range(n):
        O[i] = C_prev * (1 + night_mu + rng.normal(0, 0.004))
        C[i] = O[i] * (1 + rng.normal(0, 0.006))
        C_prev = C[i]
    H, L = np.maximum(O, C) * 1.002, np.minimum(O, C) * 0.998
    return OHLC.Bars(days, O, H, L, C, C.copy())


def test_overnight_planted_passes():
    bars = {"QQQ": _night_bars(0.0006, 1), "IWM": _night_bars(0.0006, 2)}
    rep = M.overnight_family(bars, {"QQQ": "2000-01-01", "IWM": "2000-01-01"}, end="2013-12-31", n_boot=500)
    assert rep["verdict"] == "supported", rep["reason"] + rep["why"]
    assert rep["n"] >= 2500


def test_overnight_null_fails():
    bars = {"QQQ": _night_bars(0.0, 3), "IWM": _night_bars(0.0, 4)}
    rep = M.overnight_family(bars, {"QQQ": "2000-01-01", "IWM": "2000-01-01"}, end="2013-12-31", n_boot=500)
    assert rep["verdict"] == "not_supported"


def test_open_quality_reads_first_hourly_bar():
    b = _night_bars(0.0, 9, start="2024-01-02", end="2024-02-29")
    hv = [{"t": _ts(d, 14, 30), "open": float(b.open[i]) * 1.0001} for i, d in enumerate(b.days)]
    q = M.open_quality(b, hv)
    assert q["n_days"] == len(b.days) - 1 and q["median_abs_diff_bps"] == pytest.approx(1.0, abs=0.05)


# ================================================================================================ T-558 ==

def _ibs_bars(effect: float, seed: int = 0, start="2001-01-02", end="2010-12-31"):
    days = weekdays(start, end)
    rng = np.random.default_rng(seed)
    n = len(days)
    u = rng.uniform(0.01, 0.99, n)
    r = rng.normal(0.0002, 0.01, n)
    r[1:] += effect * (u[:-1] < 0.2)
    C = 100 * np.cumprod(1 + r)
    H, L = C * (1 + (1 - u) * 0.01), C * (1 - u * 0.01)
    return OHLC.Bars(days, C.copy(), H, L, C, C.copy())


def test_ibs_planted_passes():
    bars = {s: _ibs_bars(0.004, k) for k, s in enumerate(M.T558_SYMS)}
    rep = M.ibs_family(bars, end="2010-12-31", n_boot=500, parent=False)
    assert rep["verdict"] == "supported", rep["reason"] + rep["why"]


def test_ibs_null_fails():
    bars = {s: _ibs_bars(0.0, 10 + k) for k, s in enumerate(M.T558_SYMS)}
    rep = M.ibs_family(bars, end="2010-12-31", n_boot=500, parent=False)
    assert rep["verdict"] == "not_supported"


# ================================================================================================ T-555 ==

class _FlatBills:
    def __init__(self, r=0.02):
        self.r = r

    def growth(self, d0, d1):
        return math.exp(self.r * (date.fromisoformat(d1) - date.fromisoformat(d0)).days / 365.0)


def _gold(excess_ann: float, seed: int = 0):
    days = weekdays("2004-12-01", "2026-09-30")
    rng = np.random.default_rng(seed)
    b = _FlatBills()
    rg = rng.normal(0.0003, 0.01, len(days))
    acc = np.r_[0.0, [b.growth(days[i - 1], days[i]) - 1 for i in range(1, len(days))]]
    rf = rg - acc + excess_ann / 252 + rng.normal(0, 0.002, len(days))
    fl = M.MISC.roll_flags(days, M.MISC.GC_MONTHS, 2)
    rf[fl] += 0.002                                      # contango roll jumps inside the mask must not matter
    return days, 1500 * np.cumprod(1 + rf), 100 * np.cumprod(1 + rg), b


def test_gold_carry_planted_passes():
    days, F, A, b = _gold(0.02)
    rep = M.gold_carry(days, F, A, b)
    assert rep["verdict"] == "supported", rep["criteria"]
    assert rep["ann_diff"] == pytest.approx(0.02, abs=0.012) and rep["n"] >= 3000
    assert rep["roll_profile"]["per_roll_inside_mask"] > 0.005


def test_gold_carry_null_fails():
    days, F, A, b = _gold(0.0, seed=7)
    rep = M.gold_carry(days, F, A, b)
    assert rep["verdict"] == "not_supported"


# ============================================================================================ harnesses ==

def test_every_harness_names_missing_bundles():
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    assert all(k.startswith("b7_cal_") for k in M.HARNESSES)
    for name, fn in M.HARNESSES.items():
        stat, n, v, reason = fn(FakeArchive({}))
        assert v == "inconclusive" and n == 0 and stat["missing_bundles"], name
        assert " — " in reason


def _gold_archive(excess_ann: float, seed: int = 0):
    days, F, A, _ = _gold(excess_ann, seed)
    fut = [{"available_at": None, "value": {"t": _ts(d, 4, 0), "close": float(F[i]), "adjclose": float(F[i])}} for i, d in enumerate(days)]
    gld = [{"available_at": None, "value": {"t": _ts(d), "close": float(A[i]), "adjclose": float(A[i])}} for i, d in enumerate(days)]
    bills = [{"available_at": None, "value": {"day": d, "value": "1.98"}} for d in days]
    return FakeArchive({M.dh("GC=F"): fut, M.dh("GLD"): gld, M.DTB3_B: bills})


def test_gold_harness_end_to_end():
    stat, n, v, reason = M.b7_cal_gold_futures_bills_vs_gld(_gold_archive(0.03))
    _json_ok(stat)
    assert v in VERDICTS and n == stat["n"] and " — " in reason
    assert v == "supported" and stat["ann_diff"] > 0.005
    assert "implied financing" in reason and "roll profile" in reason


def test_overnight_harness_end_to_end():
    b1, b2 = _night_bars(0.0006, 1, start="1999-03-01", end="2010-12-31"), _night_bars(0.0006, 2, start="2000-05-01", end="2011-12-31")
    arch = FakeArchive({M.dh("QQQ"): bar_rows(b1.days, b1.open, b1.high, b1.low, b1.close),
                        M.dh("IWM"): bar_rows(b2.days, b2.open, b2.high, b2.low, b2.close)})
    stat, n, v, reason = M.b7_cal_overnight_qqq_iwm(arch)
    _json_ok(stat)
    assert v in VERDICTS and "open-quality check not run" in reason and " — " in reason
