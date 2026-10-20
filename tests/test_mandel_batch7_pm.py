"""Synthetic tests for mandel.experiments.batch7_pm (T-544, T-557): a planted effect that passes and a null that does not, per
core function, plus the harness contract (missing bundles named and inconclusive, JSON-safe stat, verdict set) on fake
archives. No network, no real archive."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import numpy as np
import pytest

from mandel.experiments import batch6c_pmcal as PMCAL
from mandel.experiments import batch7_pm as M

UTC = timezone.utc
HOUR = 3600
DAY = 86_400.0
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


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================================================================ T-544 ==

def test_fee_rounding():
    assert M.kalshi_fee_6dp(0.5) == pytest.approx(0.0175)
    assert M.kalshi_fee_6dp(0.33) >= 0.07 * 0.33 * 0.67 - 1e-12
    assert M.kalshi_fee_cent(0.5) == pytest.approx(0.02)
    assert M.kalshi_fee_cent(0.01) == pytest.approx(0.01)


def test_market_and_candle_readers():
    close = int(datetime(2025, 3, 1, 22, tzinfo=UTC).timestamp())
    rows = [{"value": {"ticker": "KXBTCD-25MAR0117-T85249.99", "event_ticker": "KXBTCD-25MAR0117", "close_time": _iso(close), "result": "yes",
                       "floor_strike": None, "strike_type": "greater", "expiration_value": "86001.09"}},
            {"value": {"ticker": "KXBTCD-25MAR0117-T90000", "close_time": _iso(close), "result": "", "floor_strike": 90000}}]
    mk = M.kxbtcd_markets(rows)
    assert list(mk) == ["KXBTCD-25MAR0117-T85249.99"]
    assert mk["KXBTCD-25MAR0117-T85249.99"]["strike"] == pytest.approx(85249.99) and mk["KXBTCD-25MAR0117-T85249.99"]["result"] == 1
    end = close - 5 * HOUR
    crow = [{"value": {"ticker": "A", "candle": {"end_period_ts": end, "yes_bid": {"close": "0.40"}, "yes_ask": {"close": "0.43"}}}},
            {"value": {"ticker": "A", "candle": {"end_period_ts": end + 30, "yes_bid": {"close_dollars": "0.41"}, "yes_ask": {"close_dollars": "0.44"}}}}]
    c = M.kxbtcd_candles(crow)
    assert c["A"][0] == (end // HOUR, 0.40, 0.43)          # on the hour: decision hour = end / 3600
    assert c["A"][1][0] == end // HOUR + 1                    # mid-hour end: the next hour start (no look-ahead)


def _kalshi_world(planted: bool, n_events: int = 200, seed: int = 0):
    """Events with 4 strikes each; truth q per market, outcomes Bernoulli(q). p_RN = truth + small noise. Planted: the Kalshi
    book sits 12 points below the truth (YES cheap) on half the markets and above it (NO cheap) on the rest; null: the book is
    centred on the truth with a 2-cent spread."""
    rng = np.random.default_rng(seed)
    t0 = int(datetime(2025, 1, 2, 22, tzinfo=UTC).timestamp())
    markets, table = {}, {}
    for e in range(n_events):
        close = t0 + int(e * 3.2 * DAY) // HOUR * HOUR
        for j in range(4):
            q = float(rng.uniform(0.2, 0.8))
            o = int(rng.random() < q)
            tk = f"KXBTCD-E{e}-T{j}"
            markets[tk] = {"close_s": close, "result": o, "strike": 100000.0 + j, "event": f"E{e}", "expiration_value": 100000.0}
            rows = []
            for h in range(1, 13):
                H = close // HOUR - h
                prn = q + 0.01 * rng.normal()
                if planted:
                    mid = q - 0.12 if (j % 2 == 0) else q + 0.12
                else:
                    mid = q + 0.02 * rng.normal()
                b, a = round(mid - 0.01, 2), round(mid + 0.01, 2)
                rows.append((H, b, a, prn, prn + 0.003 * rng.normal()))
            table[tk] = sorted(rows)
    return markets, table


def test_kxbtcd_trades_planted_positive_and_null_not():
    mk, tb = _kalshi_world(True)
    tr = M.kxbtcd_trades(mk, tb, 5.0, "svi", "first")
    assert len(tr) == len(mk)                                  # every market qualifies once
    st = M.trade_stats(tr, n_boot=300)
    assert st["lower95_one_sided"] > 0
    assert {"yes", "no"} == set(st["by_side"])
    mk0, tb0 = _kalshi_world(False)
    tr0 = M.kxbtcd_trades(mk0, tb0, 5.0, "svi", "first")
    assert len(tr0) < 0.2 * len(mk0)                           # the null book rarely sits 6 points away from p_RN
    if tr0:
        st0 = M.trade_stats(tr0, n_boot=300)
        assert not (st0["lower95_one_sided"] is not None and st0["lower95_one_sided"] > 0 and st0["n"] >= 300)


def test_kxbtcd_trades_entry_rule_and_net():
    mk = {"T": {"close_s": 100 * HOUR, "result": 1, "strike": 1.0, "event": "E", "expiration_value": None}}
    tb = {"T": [(90, 0.40, 0.42, 0.47, 0.49), (91, 0.40, 0.42, 0.49, 0.49)]}
    tr = M.kxbtcd_trades(mk, tb, 5.0, "svi", "first")          # 0.47 - 0.42 = 5 points: not > 6
    assert len(tr) == 1 and tr[0]["hour"] == 91 and tr[0]["side"] == "yes"
    assert tr[0]["net"] == pytest.approx(1 - 0.42 - M.kalshi_fee_6dp(0.42) - 0.01)
    assert len(M.kxbtcd_trades(mk, tb, 5.0, "cubic", "any")) == 2
    tbn = {"T": [(90, 0.60, 0.62, 0.50, 0.50)]}
    trn = M.kxbtcd_trades(mk, tbn, 5.0, "svi", "first")
    assert trn[0]["side"] == "no" and trn[0]["price"] == pytest.approx(0.40) and trn[0]["net"] == pytest.approx(0 - 0.40 - M.kalshi_fee_6dp(0.40) - 0.01)


def test_t544_tables_planted_supported_null_not():
    mk, tb = _kalshi_world(True, n_events=200)
    from collections import Counter
    stat, n, v, reason = M._t544_from_tables(mk, tb, Counter(markets_in_window=len(mk)), n_boot=300)
    json.dumps(stat)
    assert n == 800 and v == "supported", reason
    assert " — " in reason
    mk0, tb0 = _kalshi_world(False, n_events=200)
    stat0, n0, v0, r0 = M._t544_from_tables(mk0, tb0, Counter(), n_boot=300)
    assert v0 != "supported"


def test_prn_table_filters_books_and_close_hour():
    close = 1000 * HOUR
    mk = {"T": {"close_s": close, "result": 1, "strike": 1.0, "event": "E"}}
    cand = {"T": [(998, 0.4, 0.45), (999, 0.4, 0.45), (1000, 0.4, 0.45), (997, 0.0, 0.05), (996, 0.3, 0.5)]}
    tb, cnt = M.prn_table(mk, cand, lambda H, K, t: {"svi": 0.5, "cubic": 0.5}, window=(0, 10 ** 12))
    assert [r[0] for r in tb["T"]] == [998, 999]
    assert cnt["invalid_book"] == 2 and cnt["hours_within_1h_of_close_or_after"] == 1


def test_settlement_basis_reported():
    close = 1000 * HOUR
    mk = {"T": {"close_s": close, "result": 1, "strike": 1.0, "event": "E", "expiration_value": 101.0}}
    b = M.settlement_basis(mk, {999: (0, 100.0)}, window=(0, 10 ** 12))
    assert b["n_measured"] == 1 and b["median_pct"] == pytest.approx(100 * math.log(1.01))


def test_dsr_over_cells_planted_high_null_low():
    rng = np.random.default_rng(1)
    hi = M.dsr_over_cells(0.1 + 0.3 * rng.normal(size=500), [0.3, 0.2, 0.1, 0.0, -0.1, 0.05, 0.1, None])
    lo = M.dsr_over_cells(0.3 * rng.normal(size=500), [0.0, 0.01, -0.02, 0.03, None, None, 0.0, 0.0])
    assert hi > 0.95 and lo < 0.95


def test_t544_missing_bundles_inconclusive_named():
    stat, n, v, reason = M.b7_pm_kalshi_vs_deribit_digital(FakeArchive({}))
    assert v == "inconclusive" and n == 0 and "hourly-BTC-USD" in reason and "kalshi-candles-hourly-KXBTCD-<YYYY-MM>" in reason and " — " in reason


def _deribit_rows(H0: int, H1: int, F: float, iv: float, expiry: str):
    rows = []
    for h in range(H0, H1):
        for K in (80000, 90000, 95000, 100000, 105000, 110000, 120000):
            k = math.log(K / F)
            rows.append({"kind": "option-trade", "value": {"iv": iv * 100 * (1 + 0.5 * k * k), "strike": K, "index_price": F,
                                                            "timestamp": (h * HOUR + 600) * 1000, "expiry": expiry}})
    return rows


def test_t544_harness_runs_on_fake_archive():
    F = 100000.0
    close = int(datetime(2025, 3, 3, 22, tzinfo=UTC).timestamp())
    expiry = "2025-03-04"
    H0 = close // HOUR - 30
    settled = [{"value": {"ticker": f"KXBTCD-25MAR0317-T{K}", "event_ticker": "KXBTCD-25MAR0317", "close_time": _iso(close), "result": "yes" if K < F else "no",
                          "floor_strike": K, "strike_type": "greater", "expiration_value": "100100"}} for K in (95000, 100000, 105000)]
    candles = []
    for K in (95000, 100000, 105000):
        for H in range(H0 + 3, close // HOUR + 1):
            candles.append({"value": {"ticker": f"KXBTCD-25MAR0317-T{K}", "candle": {"end_period_ts": H * HOUR, "yes_bid": {"close": "0.30"}, "yes_ask": {"close": "0.33"}}}})
    spot = [{"value": {"t": h * HOUR, "close": F}, "available_at": _iso((h + 1) * HOUR)} for h in range(H0 - 5, close // HOUR + 2)]
    arch = FakeArchive({"hourly-BTC-USD": spot, M.KS_BTCD + "2025-03": settled, M.KH_BTCD + "2025-03": candles,
                        M.DRB + "2025-03": _deribit_rows(H0 - 2, close // HOUR + 1, F, 0.5, expiry)})
    stat, n, v, reason = M.b7_pm_kalshi_vs_deribit_digital(arch, n_boot=100)
    json.dumps(stat)
    assert v in VERDICTS and v != "supported" and " — " in reason
    assert stat["selection"]["markets_with_candles"] == 3
    assert stat["selection"]["decision_hours"] > 0


# ============================================================================================================ T-557 ==

def _pm_market(mid: str, end_ts: float, outcome: int, event: str, closed_ts: float = None) -> dict:
    return {"id": mid, "umaResolutionStatus": "resolved", "outcomePrices": json.dumps(["1", "0"] if outcome else ["0", "1"]),
            "outcomes": json.dumps(["Yes", "No"]), "closedTime": _iso(closed_ts if closed_ts is not None else end_ts + 3600), "endDate": _iso(end_ts),
            "startDate": _iso(end_ts - 60 * DAY), "volumeNum": 50_000.0, "events": [{"id": event}], "feesEnabled": False, "feeType": None,
            "umaEndDate": _iso(end_ts), "question": f"Will thing {mid} happen?", "negRisk": False}


def _pm_world(planted: bool, n: int = 900, seed: int = 0):
    """Cheap markets priced ~0.03 at end - 7 d. Planted: they resolve YES 9% of the time (underpriced); null: 3% (calibrated)."""
    rng = np.random.default_rng(seed)
    t0 = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    markets, daily = [], []
    for i in range(n):
        end = t0 + (i % 700) * DAY
        p = float(rng.uniform(0.01, 0.05))
        o = int(rng.random() < (p + 0.06 if planted else p))
        mid = f"m{i}"
        markets.append({"value": _pm_market(mid, end, o, f"e{i // 2}")})
        for d in range(30, 0, -1):
            daily.append({"value": {"market_id": mid, "token": "t", "p": p, "t": end - d * DAY}, "available_at": _iso(end - d * DAY)})
    return markets, daily


def _pm_rows(planted: bool, seed: int = 0):
    markets, daily = _pm_world(planted, seed=seed)
    arch = FakeArchive({"polymarket-closed-markets-2024-01": markets, "polymarket-price-history-daily-2024-01": daily})
    PMCAL._CACHE.clear()
    meta, outs, series = PMCAL._closed_meta(arch), PMCAL._outcomes(arch), PMCAL._daily_series(arch)
    return M.cheap_yes_rows(outs, series, meta, set())


def test_cheap_yes_planted_passes_null_does_not():
    rows, cnt = _pm_rows(True)
    res = M.cheap_yes_stats(rows, n_boot=400)
    crit = M.cheap_yes_criteria(res)
    assert res["n"] == 900 and all(ok for _, ok, _ in crit), crit
    rows0, _ = _pm_rows(False)
    res0 = M.cheap_yes_stats(rows0, n_boot=400)
    crit0 = M.cheap_yes_criteria(res0)
    assert not crit0[0][1]


def test_cheap_yes_rows_exclusion_and_point_in_time():
    end = datetime(2025, 6, 1, tzinfo=UTC).timestamp()
    outs = {"a": {"outcome": 1, "close_ts": end, "end_ts": end, "closed_ts": end + 3600, "question": "x"},
            "b": {"outcome": 0, "close_ts": end, "end_ts": end, "closed_ts": end + 3600, "question": "y"},
            "c": {"outcome": 0, "close_ts": end, "end_ts": end, "closed_ts": end + 3600, "question": "z"}}
    ts = np.array([end - 8 * DAY, end - 6 * DAY]); series = {"a": (ts, np.array([0.05, 0.9])), "b": (ts, np.array([0.05, 0.05])),
                                                              "c": (np.array([end - 12 * DAY]), np.array([0.05]))}
    rows, cnt = M.cheap_yes_rows(outs, series, {}, exclude={"b"})
    assert [r["mid"] for r in rows] == ["a"] and rows[0]["p"] == pytest.approx(0.05)   # the end - 6 d point is after the cutoff
    assert cnt["excluded_t02"] == 1 and cnt["no_price_at_horizon"] == 1                 # c is > 3 days stale


def _fetch_log_rows(markets, reason_of=lambda mid: "sample", rate=1.0, month="2024-01"):
    rows = [{"value": {"product": "daily-sample", "id": month, "month": month, "sample_rate": rate}}]
    for m in markets:
        mid = m["value"]["id"]
        rows.append({"value": {"product": "daily", "id": mid, "month": month, "reason": reason_of(mid)}})
    return rows


def test_t557_missing_and_harness_contract():
    stat, n, v, reason = M.b7_pm_cheap_yes_archived_panel(FakeArchive({}))
    assert v == "inconclusive" and n == 0 and "polymarket-closed-markets" in reason and " — " in reason
    markets, daily = _pm_world(True)
    legacy = [markets[0]]
    arch = FakeArchive({"polymarket-closed-markets": legacy, "polymarket-price-history-daily": [daily[0]],
                        "polymarket-fetch-log": _fetch_log_rows(markets), "polymarket-closed-markets-2024-01": markets, "polymarket-price-history-daily-2024-01": daily})
    PMCAL._CACHE.clear()
    stat, n, v, reason = M.b7_pm_cheap_yes_archived_panel(arch, n_boot=300)
    json.dumps(stat)
    assert n == 899 and v == "supported", reason
    assert stat["n_excluded_ids_t02"] == 1 and " — " in reason
    markets0, daily0 = _pm_world(False)
    arch0 = FakeArchive({"polymarket-closed-markets": [markets0[0]], "polymarket-price-history-daily": [],
                         "polymarket-fetch-log": _fetch_log_rows(markets0), "polymarket-closed-markets-2024-01": markets0, "polymarket-price-history-daily-2024-01": daily0})
    PMCAL._CACHE.clear()
    _, _, v0, r0 = M.b7_pm_cheap_yes_archived_panel(arch0, n_boot=300)
    assert v0 != "supported", r0


def test_t557_primary_is_panel_weighted_regression():
    """Regression (reporting defect): daily history covers every priority market (event family, long-lived) but only a hash
    sample of the rest, so the unweighted mean is a property of the selection. Here the priority strata are calibrated
    longshots that lose (YES 0%) and the 10% sample is underpriced (YES ~ p + 0.08): the panel-weighted primary, weighting
    'sample' markets by 1 / 0.10, must pass while the unweighted all-history mean is negative; and without a fetch log
    the harness is inconclusive, never a verdict from the unweighted mean."""
    rng = np.random.default_rng(3)
    t0 = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    markets, daily, reason = [], [], {}
    for i in range(1200):
        end = t0 + (i % 700) * DAY
        p = float(rng.uniform(0.01, 0.05))
        smp = i % 4 == 0
        o = int(rng.random() < (p + 0.10)) if smp else 0
        mid = f"m{i}"
        reason[mid] = "sample" if smp else ("long-lived" if i % 2 else "family:us-election")
        markets.append({"value": _pm_market(mid, end, o, f"e{i}")})
        for d in range(30, 0, -1):
            daily.append({"value": {"market_id": mid, "token": "t", "p": p, "t": end - d * DAY}, "available_at": _iso(end - d * DAY)})
    arch = FakeArchive({"polymarket-closed-markets": [], "polymarket-price-history-daily": [],
                        "polymarket-fetch-log": _fetch_log_rows(markets, reason.get, rate=0.10),
                        "polymarket-closed-markets-2024-01": markets, "polymarket-price-history-daily-2024-01": daily})
    PMCAL._CACHE.clear()
    stat, n, v, r = M.b7_pm_cheap_yes_archived_panel(arch, n_boot=300)
    json.dumps(stat)
    assert stat["unweighted_all_history"]["mean"] < 0
    assert stat["primary"]["mean"] > 0 and stat["primary"]["ci"][0] > 0 and n == 1200
    assert stat["primary"]["weight_share_sample"] == pytest.approx(300 * 10 / (300 * 10 + 900))
    assert v == "supported" and "panel-weighted" in r and "classic longshot" not in r, r
    w = M.panel_weights(arch)
    assert w["m0"] == pytest.approx(10.0) and w["m1"] == 1.0
    arch_nolog = FakeArchive({k: val for k, val in arch.b.items() if k != "polymarket-fetch-log"})
    PMCAL._CACHE.clear()
    _, n2, v2, r2 = M.b7_pm_cheap_yes_archived_panel(arch_nolog, n_boot=100)
    assert v2 == "inconclusive" and "polymarket-fetch-log" in r2


def test_t557_non_yes_no_outcomes_dropped_regression():
    """Regression: markets whose outcomes are not ['Yes', 'No'] (Over/Under, candidate names) are not YES contracts."""
    end = datetime(2025, 6, 1, tzinfo=UTC).timestamp()
    outs = {k: {"outcome": 0, "close_ts": end, "end_ts": end, "closed_ts": end + 3600, "question": k} for k in ("a", "b", "c")}
    series = {k: (np.array([end - 8 * DAY]), np.array([0.05])) for k in outs}
    meta = {"a": {"id": "a", "outcomes": json.dumps(["Yes", "No"])}, "b": {"id": "b", "outcomes": json.dumps(["Over", "Under"])}, "c": {"id": "c", "outcomes": ["Trump", "Harris"]}}
    rows, cnt = M.cheap_yes_rows(outs, series, meta, set())
    assert [r["mid"] for r in rows] == ["a"] and cnt["not_yes_no_outcomes"] == 2


def test_registry_maps():
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    assert all(k.startswith("b7_pm_") for k in M.HARNESSES)
