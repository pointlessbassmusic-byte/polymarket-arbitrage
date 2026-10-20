"""Widened sleeves (T-567, T-568), the shadow recorder (T-565, T-566) and the capture status. No network."""

import json
from datetime import date, datetime, time as dtime, timedelta

import pytest

from mandel.live import wide as W
from mandel.live import shadow as SH


def _sess(start=date(2026, 6, 25), end=date(2026, 7, 15), closed=(date(2026, 7, 3),), early=None):
    out, d = {}, start
    while d <= end:
        if d.weekday() < 5 and d not in closed:
            out[d] = (early or {}).get(d, dtime(16, 0))
        d += timedelta(days=1)
    return out


def test_pre_holiday_detection_and_target():
    s = _sess()                                       # 2026-07-03 (Fri) observed Independence Day: Jul 2 is pre-holiday
    assert W.is_pre_holiday(date(2026, 7, 2), s) and not W.is_pre_holiday(date(2026, 7, 1), s)
    assert not W.is_pre_holiday(date(2026, 7, 10), s)            # a normal Friday before a weekend
    assert W.prehol_target(date(2026, 7, 1), s) is True          # buy at Jul 1 close, hold over Jul 2
    assert W.prehol_target(date(2026, 7, 2), s) is False         # sell at the pre-holiday close


def test_close_window_follows_the_sessions_close_time():
    ny = W.ET
    assert W.in_close_window(datetime(2026, 12, 24, 12, 46, tzinfo=ny), dtime(13, 0))
    assert not W.in_close_window(datetime(2026, 12, 24, 15, 46, tzinfo=ny), dtime(13, 0))
    assert W.in_close_window(datetime(2026, 12, 23, 15, 46, tzinfo=ny), dtime(16, 0))
    assert not W.in_close_window(datetime(2026, 12, 23, 12, 46, tzinfo=ny), dtime(16, 0))


def test_spread_plan_uses_the_underlyings_width_and_budget():
    today = date(2026, 10, 21)
    exp = date(2026, 11, 20)
    book = {exp: {k: (0.50, 0.60) if k == 90.0 else (0.20, 0.30) for k in (85.0, 88.0, 90.0, 91.0)}}
    plan, why = W.plan_spread("TLT", today, 95.0, book, 500)            # 95% of 95 = 90.25 -> short 90, long 88
    assert plan and plan.short_strike == 90.0 and plan.long_strike == 88.0 and plan.credit_mid == pytest.approx(0.30)
    assert plan.max_loss == pytest.approx(170.0)
    g = W.plan_spread("GLD", today, 95.0, book, 500)[0]                # GLD width 5: short 90, long 85, max loss 470
    assert g and g.long_strike == 85.0 and g.max_loss == pytest.approx(470.0)
    assert W.plan_spread("TLT", today, 95.0, book, 100)[0] is None      # over budget


class FakeApi:
    live = False

    def __init__(self, cash="10000"):
        self.sent, self.cash = [], cash

    def calendar(self, a, b):
        return [{"date": d.isoformat(), "close": "16:00"} for d in _sess(date.fromisoformat(a), date.fromisoformat(b))]

    def account(self):
        return {"equity": "10000", "cash": self.cash}

    def positions(self):
        return []

    def stock_snapshots(self, syms):
        return {s: {"latestTrade": {"p": 200.0}} for s in syms}

    def submit(self, o):
        self.sent.append(o); return {"id": "x", "status": "accepted"}


def test_wide_close_buys_iwm_before_a_pre_holiday_and_never_borrows(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(W, "STATE", tmp_path); monkeypatch.setattr(W, "KILL", tmp_path / "KILL")
    monkeypatch.setattr(W, "JOURNAL", tmp_path / "j.jsonl")
    api = FakeApi()
    W.phase_close(api, dry=True, now=datetime(2026, 7, 1, 15, 46, tzinfo=W.ET))
    out = capsys.readouterr().out
    assert '"qty": "10"' in out and "IWM" in out and api.sent == []          # 40% of 5,000 = 2,000 / 200 = 10 shares
    api2 = FakeApi(cash="450")
    W.phase_close(api2, dry=True, now=datetime(2026, 7, 1, 15, 46, tzinfo=W.ET))
    assert '"qty": "2"' in capsys.readouterr().out                        # capped by cash: 450 / 200 = 2


def test_shadow_record_from_bars_is_point_in_time():
    models = SH.load_models()
    import numpy as np
    rng = np.random.default_rng(3)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    bars = [{"t": f"2026-{1 + i // 28 % 12:02d}-{1 + i % 28:02d}T04:00:00Z", "c": float(p)} for i, p in enumerate(px)]
    full = SH.record_from_bars(bars, bars, models)
    part = SH.record_from_bars(bars[:200], bars[:200], models)
    assert 0 <= full["T-565"]["p_high"] <= 1 and 0 < full["T-566"]["w"] <= 1
    assert part["T-565"]["n_returns"] == 199 and full["T-565"]["n_returns"] == 299


def test_capture_status_summarises_families(monkeypatch, tmp_path):
    from mandel.archive import Archive
    from mandel.ledger import Ledger
    from mandel.live import capture as C
    a = Archive(root=tmp_path / "arch", ledger=Ledger(tmp_path / "l.jsonl"))
    for d in ("2026-10-21", "2026-10-22"):
        a.store(f"options-chain-SPX-{d}", "data", [{"x": 1}], recipe="test", in_git=False)
    monkeypatch.setattr(C, "OUT", tmp_path / "out")
    monkeypatch.setattr("mandel.archive.ARCHIVE_ROOT", tmp_path / "arch")
    import mandel.archive as AR
    monkeypatch.setattr(AR.Archive.__init__, "__defaults__", (tmp_path / "arch", Ledger(tmp_path / "l.jsonl")))
    st = C.status()
    assert st["families"]["options-chain-SPX"] == {"latest": "2026-10-22", "count": 2, "bytes": st["families"]["options-chain-SPX"]["bytes"]}
    assert json.loads((tmp_path / "out" / "status.json").read_text())["families"]
