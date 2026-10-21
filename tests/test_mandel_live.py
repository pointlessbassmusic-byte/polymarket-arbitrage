"""Paper sleeves (T-559, T-560): decision logic and the runner on a fake broker. No network."""

import json
from datetime import date, timedelta

import pytest

from mandel.live import alpaca as A
from mandel.live import sleeves as S


def _sessions(start=date(2026, 9, 1), end=date(2026, 12, 31)):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_turn_of_month_window_is_minus4_to_plus3():
    ss = _sessions()
    oct_days = [d for d in ss if d.month == 10]
    window = [d for d in oct_days if S.in_tom_window(d, ss)]
    assert window == oct_days[:3] + oct_days[-4:]


def test_close_decision_holds_tom_and_skips_the_last_two_days_on_the_monthend_signal():
    ss = _sessions()
    oct_days = [d for d in ss if d.month == 10]
    flat_bar = {"high": 100, "low": 90, "last": 99}            # IBS 0.9: no IBS trade
    day_before_m4 = oct_days[-5]                              # holding over return day -4
    d = S.close_decision(day_before_m4, ss, 1000, flat_bar, 0.05, 0.0)
    assert d.targets["SPYM"] == pytest.approx(300) and d.targets["QQQM"] == pytest.approx(400)
    before_m2 = oct_days[-3]                                  # next session is day -2
    assert S.close_decision(before_m2, ss, 1000, flat_bar, 0.05, 0.0).targets["SPYM"] == 0        # SPY beat TLT: skip
    assert S.close_decision(before_m2, ss, 1000, flat_bar, 0.01, 0.0).targets["SPYM"] == pytest.approx(300)
    last = oct_days[-1]                                        # next session is Nov +1: back in
    assert S.close_decision(last, ss, 1000, flat_bar, 0.05, 0.0).targets["SPYM"] == pytest.approx(300)
    mid = oct_days[10]
    assert S.close_decision(mid, ss, 1000, flat_bar, None, None).targets["SPYM"] == 0
    low_bar = {"high": 100, "low": 90, "last": 91}            # IBS 0.1
    assert S.close_decision(mid, ss, 1000, low_bar, None, None).targets["SPYM"] == pytest.approx(300)


def test_ibs_and_whole_shares():
    assert S.ibs(10, 10, 10) is None and S.ibs(11, 10, 10.1) == pytest.approx(0.1)
    assert S.shares_for(300, 92.4) == 3 and S.shares_for(80, 92.4) == 0


def test_put_spread_plan_trend_filter_dte_and_budget():
    today = date(2026, 10, 21)
    exp = S.third_friday(2026, 11)                            # 2026-11-20, 30 days
    weekly = date(2026, 11, 27)
    book = {exp: {k: (0.30, 0.40) if k == 730.0 else (0.10, 0.20) for k in (720.0, 727.0, 730.0, 740.0)},
            weekly: {730.0: (1.0, 1.1), 727.0: (0.1, 0.2)}}
    plan, why = S.plan_put_spread(today, 770.0, book, 400, True)
    assert plan and plan.expiry == exp and plan.short_strike == 730.0 and plan.long_strike == 727.0
    assert plan.credit_mid == pytest.approx(0.20) and plan.max_loss == pytest.approx(280)
    assert S.plan_put_spread(today, 770.0, book, 400, False)[0] is None
    assert S.plan_put_spread(today, 770.0, book, 100, True)[0] is None          # over the risk budget
    assert S.spread_exit(today, exp, 0.20, 0.09) and S.spread_exit(date(2026, 10, 31), exp, 0.20, 0.19)
    assert S.spread_exit(today, exp, 0.20, 0.15) is None
    assert S.occ_symbol("XSP", exp, "put", 730) == "XSP261120P00730000"
    assert S.trend_ok([100] * 9 + [120]) is True and S.trend_ok([100] * 5) is None


def test_live_is_refused_without_the_users_switch(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "k"); monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    monkeypatch.delenv("MANDEL_ALPACA_LIVE", raising=False)
    with pytest.raises(A.LiveRefused):
        A.Alpaca(live=True)
    assert A.Alpaca().base == A.PAPER


def test_order_shapes():
    o = A.auction_order("SPYM", 3, "buy", "cls", "m-1")
    assert o["time_in_force"] == "cls" and o["qty"] == "3"
    assert A.auction_order("SPYM", 3, "buy", "cls", "m-1", paper=True)["time_in_force"] == "day"   # paper runs no auction
    sp = A.spread_order("XSP261120P00730000", "XSP261120P00727000", 1, 0.2, True, "m-2")
    assert sp["order_class"] == "mleg" and sp["legs"][0]["position_intent"] == "sell_to_open"


class FakeApi:
    live = False

    def __init__(self, today):
        self.today = today; self.sent = []

    def calendar(self, start, end):
        return [{"date": d.isoformat()} for d in _sessions(date.fromisoformat(start), date.fromisoformat(end))]

    def account(self):
        return {"equity": "750", "cash": "750"}

    def stock_snapshots(self, syms):
        return {s: {"dailyBar": {"h": 93.0, "l": 92.0}, "latestTrade": {"p": 92.05 if s == "SPYM" else 250.0}} for s in syms}

    def daily_bars(self, syms, start):
        return {s: [] for s in syms}

    def positions(self):
        return []

    def submit(self, o):
        self.sent.append(o); return {"id": "x", "status": "accepted"}


def test_runner_close_dry_run_places_nothing(monkeypatch, tmp_path, capsys):
    from mandel.live import runner as R
    monkeypatch.setattr(R, "STATE", tmp_path); monkeypatch.setattr(R, "KILL", tmp_path / "KILL")
    monkeypatch.setattr(R, "JOURNAL", tmp_path / "j.jsonl")

    class D:  # freeze "today" to a session
        @staticmethod
        def now(tz=None):
            import datetime as dt
            return dt.datetime(2026, 10, 14, 15, 45, tzinfo=tz)
    monkeypatch.setattr(R, "datetime", D)
    api = FakeApi(date(2026, 10, 14))
    R.phase_close(api, dry=True)
    assert api.sent == [] and not (tmp_path / "j.jsonl").exists()
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "QQQM" in out                 # 450 x 0.4 = 180 < 250: no QQQM share; SPYM IBS 0.05
    (tmp_path / "KILL").write_text("stop")
    with pytest.raises(SystemExit):
        R.phase_close(api, dry=True)


def test_tracker_counts_journal_sessions_fills_and_round_trip_pnl(tmp_path):
    from mandel.live import tracker as T
    j = tmp_path / "journal.jsonl"
    recs = [{"kind": "close.decision", "day": "2026-10-21"}, {"kind": "close.decision", "day": "2026-10-22"},
            {"kind": "close.decision", "day": "2026-10-23", "dry_run": True},
            {"kind": "order.fill", "client_order_id": "m-cls-QQQM-1", "symbol": "QQQM", "side": "buy", "filled_qty": "2",
             "filled_avg_price": "250.0", "filled_at": "2026-10-21T20:00:00Z"},
            {"kind": "order.fill", "client_order_id": "m-opg-QQQM-2", "symbol": "QQQM", "side": "sell", "filled_qty": "2",
             "filled_avg_price": "251.5", "filled_at": "2026-10-22T13:30:00Z"}]
    j.write_text("".join(json.dumps(r) + "\n" for r in recs))
    c = T.calendar_progress(T._journal(j))
    assert c == {"n_now": 2, "fills": 2, "rejected": 0, "expired": 0, "old_code": False, "pnl_usd": 3.0}
    rows = T.build(date(2026, 10, 23), j)
    t559 = next(r for r in rows if r["id"] == "T-559")
    assert t559["state"] == "running" and t559["progress"] == pytest.approx(2 / 60, abs=1e-4)
    assert {r["owner"] for r in rows} >= {"Mandel", "Hurst", "Kelly", "Brier", "Shannon"}


def test_sleeve_trades_fixed_capital_and_never_borrows():
    from mandel.live import runner as R
    assert R.sleeve_capital(97176.97) == R.SLEEVE_CAPITAL == 5000
    assert R.calendar_capital(97176.97, 1341.92, 0.0) == pytest.approx(1341.92)      # shared account, little cash
    assert R.calendar_capital(97176.97, 50000, 0.0) == pytest.approx(3000)            # 60% of the fixed 5,000
    assert R.calendar_capital(97176.97, 100, 2900) == pytest.approx(3000)             # own holdings count back in
    assert R.calendar_capital(750, 750, 0.0) == pytest.approx(450)                    # small account: equity binds
