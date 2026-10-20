"""Live evidence graph: wiring, stream health propagation, shared exposure, readiness and checkpoint sizing."""

from datetime import date

import pytest

from mandel.live import evidence_graph as G

TODAY = date(2026, 10, 20)


def _rows():
    return [{"id": "T-559", "owner": "Mandel", "strategy": "cal", "mode": "paper", "state": "running", "progress": 0.1},
            {"id": "T-542", "owner": "Mandel", "strategy": "parity", "mode": "forward", "state": "stalled", "progress": 0.1},
            {"id": "H-orb-qqq", "owner": "Hurst", "strategy": "orb", "mode": "paper", "state": "running", "progress": 1.0,
             "n_now": 60, "n_target": 60, "unit": "sessions"},
            {"id": "H-bounce-short", "owner": "Hurst", "strategy": "bounce", "mode": "live", "state": "running", "progress": None}]


def test_stale_stream_flags_downstream_and_live_is_critical():
    bundles = {"options-chain-SPX-2026-10-14": {}, "options-chain-SPX-2026-10-15": {}}
    g = G.build_graph(_rows(), bundles, TODAY, child_as_of="2026-10-01")
    assert G.downstream(g, "stream:options-chain-SPX") == ["T-542"]
    alerts = {a["node"]: a for a in G.monitors(g, _rows(), TODAY)}
    assert alerts["stream:options-chain-SPX"]["severity"] == "warning"
    # the child's figures are 19 days old: its recorder is stale, and the live bounce-short reads it -> critical
    assert alerts["stream:child:Hurst:kalshi-perp-books"]["severity"] == "critical"
    assert "H-bounce-short" in alerts["stream:child:Hurst:kalshi-perp-books"]["affected"]


def test_shared_account_and_factor_and_checkpoint():
    g = G.build_graph(_rows(), {}, TODAY, child_as_of="2026-10-20")
    alerts = {a["node"]: a for a in G.monitors(g, _rows(), TODAY)}
    assert alerts["account:alpaca-paper-1"]["severity"] == "warning"           # Hurst and Mandel in one account
    assert "T-559" in alerts["factor:us-equity-beta"]["affected"]
    assert alerts["H-orb-qqq"]["kind"] == "checkpoint" and alerts["H-orb-qqq"]["severity"] == "action"
    assert any(a["kind"] == "contradiction" for a in alerts.values())


def test_data_readiness_counts_capture_days_and_prefixes():
    b = {"fred-DTB3": {}, "options-chain-SPX-2026-10-14": {}, "options-chain-SPX-2026-10-15": {}}
    r, miss = G.data_readiness("options-chain-SPX-<date> (daily capture), fred-DTB3", b, "daily chain capture, 30 days")
    assert r == pytest.approx((2 / 30 + 1) / 2) and miss == ["options-chain-SPX-<date> (2/30)"]
    assert G.data_readiness("fred-DTB3, daily-history-SPY", b)[0] == pytest.approx(0.5)
    assert G.data_readiness("a forecast book", b)[0] is None


def test_inconclusive_without_new_data_is_discounted_and_forward_tests_are_not_ranked():
    b = {"daily-history-SPY": {"created_at": "2026-10-14T00:00:00"}}
    reg = [{"id": "T-1", "status": "inconclusive", "trial": {"data": "daily-history-SPY", "min_n": 100}, "results": ["X-1"]},
           {"id": "T-2", "status": "inconclusive", "trial": {"data": "daily-history-SPY", "min_n": 100}, "results": ["X-2"]},
           {"id": "T-3", "status": "blocked", "trial": {"data": "daily-history-SPY", "procedure": "forward test", "min_n": 20}}]
    out = {x["id"]: x for x in G.next_tests(reg, b, result_times={"X-1": "2026-10-15", "X-2": "2026-10-13"})}
    assert out["T-2"]["new_data"] is True and out["T-1"]["new_data"] is False
    assert out["T-2"]["score"] == pytest.approx(out["T-1"]["score"] * 5, abs=0.005)
    assert "T-3" not in out


def test_checkpoint_size_is_fractional_kelly_shrunk_by_dsr():
    assert G.checkpoint_size(0.001, 0.0001, dsr=0.4, cap_usd=5000) == 0                 # DSR below 0.5: nothing
    assert G.checkpoint_size(-0.001, 0.0001, dsr=0.99, cap_usd=5000) == 0
    assert G.checkpoint_size(0.0001, 0.0001, dsr=1.0, cap_usd=5000) == pytest.approx(1250)   # 0.25 x 1 x 5000
    assert G.checkpoint_size(0.0001, 0.0001, dsr=0.75, cap_usd=5000) == pytest.approx(625)
    assert G.checkpoint_size(0.01, 0.0001, dsr=1.0, cap_usd=5000) == 5000               # capped


def test_capture_status_freshens_streams():
    b = {"options-chain-SPX-2026-10-15": {}, "fred-DTB3": {"created_at": "2026-10-15T00:00:00"}}
    st = {"families": {"options-chain-SPX": {"latest": "2026-10-19", "count": 3}}, "undated": {"fred-DTB3": "2026-10-19T22:00:00"}}
    m = G.apply_capture_status(b, st)
    assert G.stream_health("options-chain-SPX", m, TODAY, None)["state"] == "ok"
    assert G.stream_health("fred-DTB3", m, TODAY, None)["state"] == "ok"
    assert G.stream_health("options-chain-SPX", b, TODAY, None)["state"] == "stale"
