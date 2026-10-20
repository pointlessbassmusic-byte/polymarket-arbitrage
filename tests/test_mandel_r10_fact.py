"""House rule 10 (no arbitrary grid phase) for batch4_fact (key 'fact'), on synthetic data. No archive, no network.

Only T-389 (contrarian factor timing) rests on a non-overlapping cycle grid: 'quarterly' tilts with no quarter calendar
named, so the rebalance has three valid phases. ``contrarian_timing_test`` now builds every book on all three, judges
both criteria on the pooled book (one third of capital per phase) and reports each phase. The other eleven harnesses
are daily series or calendar-month statistics; the last test pins that the monthly book engine is anchored to calendar
months (only the month of each day matters, not which day of the month it is)."""

import numpy as np
import pytest

from mandel.experiments import batch4_fact as bf

NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]


def _months(y, m, n):
    return [f"{y + (m - 1 + k) // 12:04d}-{(m - 1 + k) % 12 + 1:02d}" for k in range(n)]


def _world(T=760, seed=22):
    rng = np.random.default_rng(seed)
    t = np.arange(T)
    F = 0.004 + 0.02 * np.sin(2 * np.pi * t[:, None] / 80 + rng.uniform(0, 2 * np.pi, 6)[None, :]) + rng.normal(0, 0.015, (T, 6))
    return _months(1963, 7, T), F


def test_contrarian_portfolios_rebalance_on_each_quarterly_phase():
    ms, F = _world(300)
    start = 120
    for p, months_of_phase in enumerate(((1, 4, 7, 10), (2, 5, 8, 11), (3, 6, 9, 12))):
        _, _, tilts = bf.contrarian_portfolios(F, ms, 60, np.ones(6), start, return_tilts=True, phase=p)
        rebal = [m for m in tilts if m != ms[start]]                 # the first row always sets the book
        assert rebal and all(int(m[5:7]) in months_of_phase for m in rebal), (p, rebal[:6])
        assert len(rebal) == sum(int(m[5:7]) in months_of_phase for m in ms[start + 1:])
    s0, t0 = bf.contrarian_portfolios(F, ms, 60, np.ones(6), start)
    s0p, t0p = bf.contrarian_portfolios(F, ms, 60, np.ones(6), start, phase=0)
    assert np.array_equal(s0, s0p) and np.array_equal(t0, t0p)      # the default is the Jan/Apr/Jul/Oct phase
    s1, t1 = bf.contrarian_portfolios(F, ms, 60, np.ones(6), start, phase=1)
    assert not np.allclose(t0, t1)                                   # the phase matters, which is why rule 10 applies
    with pytest.raises(ValueError):
        bf.contrarian_portfolios(F, ms, 60, np.ones(6), start, phase=3)


def test_contrarian_timing_criteria_are_judged_on_the_pooled_all_phase_book():
    ms, F = _world()
    start = ms.index("1968-01")
    rep = bf.contrarian_timing_test(ms, F, NAMES, n_boot=400)
    statics, timed = [], []
    for p in range(3):
        s, t = bf.contrarian_portfolios(F, ms, 60, np.ones(6), start, phase=p)
        statics.append(s)
        timed.append(t)
    obs, lo, hi = bf.sharpe_diff_ci(np.mean(timed, axis=0), np.mean(statics, axis=0), 12, 12, 400, 0)
    assert rep["sharpe_diff"] == pytest.approx(obs) and rep["ci"] == pytest.approx([lo, hi])
    assert rep["n"] == rep["n_months"] == len(ms) - start               # n stays in months, the claim's unit
    r10 = rep["rule10"]
    assert r10["phases"] == list(bf.QUARTER_PHASES) and r10["block"] >= 2 * 3
    for p, label in enumerate(bf.QUARTER_PHASES):
        o, l, h = bf.sharpe_diff_ci(timed[p], statics[p], 12, 12, 400, 0)
        assert r10["per_phase"][label]["sharpe_diff"] == pytest.approx(o)
        assert r10["per_phase"][label]["ci"] == pytest.approx([l, h])
    d = [r10["per_phase"][k]["sharpe_diff"] for k in bf.QUARTER_PHASES]
    assert r10["sharpe_diff_range"] == pytest.approx([min(d), max(d)])
    assert r10["n_phases_ci_pass"] == sum(r10["per_phase"][k]["ci"][0] > 0 for k in bf.QUARTER_PHASES)
    head = rep["reason"].split(" — ")[0]
    assert "pooled over its 3 phases" in head and f"{r10['n_phases_ci_pass']} of 3 phases pass the lower bound" in head
    assert all(k in head for k in bf.QUARTER_PHASES)


def _fake_stats(lo_pooled, lo_phase):
    calls = []

    def fake(static, trials, n_boot, seed):
        lo = lo_pooled if not calls else lo_phase                     # the pooled book is evaluated first
        calls.append(lo)
        diffs = {k: v - static for k, v in trials.items()}
        return {"obs": lo + 0.05, "lo": lo, "hi": lo + 0.1, "tsr": [0.01, 0.02, 0.03, 0.04][:len(trials)] + [0.0] * (len(trials) - 4),
                "dsr": 0.99, "diffs": diffs, "sharpe_timed": 1.0, "sharpe_static": 0.9}
    return fake, calls


def test_pooled_estimate_decides_even_when_every_phase_disagrees(monkeypatch):
    ms, F = _world()
    vs = np.zeros(len(ms) - ms.index("1968-01"))
    fake, calls = _fake_stats(lo_pooled=0.02, lo_phase=-0.01)
    monkeypatch.setattr(bf, "_contrarian_stats", fake)
    rep = bf.contrarian_timing_test(ms, F, NAMES, n_boot=10, value_spread_timed=vs)
    assert len(calls) == 4
    assert rep["verdict"] == "supported" and rep["rule10"]["n_phases_ci_pass"] == 0
    assert "0 of 3 phases pass the lower bound" in rep["reason"]
    fake, calls = _fake_stats(lo_pooled=-0.01, lo_phase=0.02)
    monkeypatch.setattr(bf, "_contrarian_stats", fake)
    rep = bf.contrarian_timing_test(ms, F, NAMES, n_boot=10, value_spread_timed=vs)
    assert rep["verdict"] == "not_supported" and rep["rule10"]["n_phases_ci_pass"] == 3
    assert "failed: lower 95% bound of the Sharpe difference > 0" in rep["reason"]
    assert "3 of 3 phases pass the lower bound" in rep["reason"]


def test_value_spread_trial_per_phase_or_shared():
    ms, F = _world(500)
    start = ms.index("1968-01")
    n = len(ms) - start
    per = np.stack([bf.contrarian_portfolios(F, ms, 48, np.ones(6), start, phase=p)[1] for p in range(3)])
    a = bf.contrarian_timing_test(ms, F, NAMES, n_boot=200, value_spread_timed=per)
    b = bf.contrarian_timing_test(ms, F, NAMES, n_boot=200, value_spread_timed=per.mean(axis=0))
    assert a["dsr_decided"] and b["dsr_decided"] and len(a["trial_diff_sharpes_ann"]) == 5
    assert a["trial_diff_sharpes_ann"]["value_spread"] == pytest.approx(b["trial_diff_sharpes_ann"]["value_spread"])
    assert a["rule10"]["n_phases_dsr_pass"] is not None and a["rule10"]["n_phases_dsr_pass"] in (0, 1, 2, 3)
    with pytest.raises(ValueError):
        bf.contrarian_timing_test(ms, F, NAMES, n_boot=50, value_spread_timed=np.zeros((2, n)))


def test_monthly_book_is_anchored_to_calendar_months_not_to_day_positions():
    # T-383/T-385/T-387 and the diagnostics reset at calendar-month starts: relabelling every day to another day of the
    # same month (a different phase within the month would change the reset day) leaves the P&L unchanged
    rng = np.random.default_rng(3)
    days = [f"2020-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 21)]
    rl, rs = rng.normal(0, 0.01, len(days)), rng.normal(0, 0.01, len(days))
    one = np.ones(len(days))
    p1, n1 = bf.ls_book(days, rl, rs, one, one, borrow=0.003, cost=0.0005)
    relabel = [d[:8] + f"{int(d[8:]) + 5:02d}" for d in days]
    p2, n2 = bf.ls_book(relabel, rl, rs, one, one, borrow=0.003, cost=0.0005)
    assert np.allclose(p1, p2) and n1 == n2 == 12
