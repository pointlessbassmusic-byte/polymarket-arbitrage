"""Regression tests for the audit findings on the volatility, social and market harnesses (group 'vs'), synthetic data only.

OM-2/OM-3 implied_move_vs_realised (T-66), OM-7 skew_tail (T-52), OM-16 overlay_backtest (T-54..T-57),
OM-4/OM-12 attention_vs_abs_return (T-38), OM-10/OM-11 fear_greed_forward_returns (T-41, T-19),
OM-5 resolved_outcomes/price_at_horizons (T-01, T-02, T-13), OM-6 multiscale_edge (T-03), OM-13 bundle_arb_scan (T-04).
"""

import json
import math
from datetime import date, datetime, timedelta, timezone

import numpy as np

from mandel.experiments import markets
from mandel.experiments.markets import bundle_arb_scan, market_calibration, multiscale_edge, price_at_horizons, resolved_outcomes
from mandel.experiments.social import attention_ticker_days, attention_vs_abs_return, close_ts, daily_closes, fear_greed_forward_returns
from mandel.experiments.volatility import implied_move_vs_realised, overlay_backtest, overlay_verdict, skew_tail
from mandel.validation.backtest_eval import sharpe_ratio

UTC = timezone.utc


def _iso_days(start: date, n: int) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


# ------------------------------------------------------------------------------- OM-2 (T-66): dependence --

SYMS = ["SPY", "QQQ", "IWM", "TLT", "GLD", "SLV", "USO", "IBIT"]
VOL = np.array([0.010, 0.013, 0.014, 0.009, 0.011, 0.020, 0.022, 0.030])


def _surface_history(seed: int, n_cap: int, h: int = 21, rich: float = 0.0):
    """Pre-open daily captures of 8 cross-correlated symbols; capture on day c quotes close(c-1) and an expiry h sessions later.
    The implied move is exactly E|N(0, sigma^2 h)| (true null) times (1 + rich)."""
    rng = np.random.default_rng(seed)
    C = np.full((8, 8), 0.2); C[:3, :3] = 0.85; C[4, 5] = C[5, 4] = 0.7; np.fill_diagonal(C, 1.0)
    T = n_cap + h + 5
    z = rng.normal(size=(T, 8)) @ np.linalg.cholesky(C).T * VOL
    logp = np.vstack([np.zeros(8), np.cumsum(z, axis=0)])
    days = _iso_days(date(2027, 1, 1), T + 1)
    px = {s: {days[i]: 100 * math.exp(logp[i, j]) for i in range(T + 1)} for j, s in enumerate(SYMS)}
    rows = []
    for c in range(1, n_cap):
        for j, s in enumerate(SYMS):
            imp = VOL[j] * math.sqrt(h) * math.sqrt(2 / math.pi) * 100 * (1 + rich)
            rows.append({"available_at": days[c] + "T07:10:00+00:00",
                         "value": {"symbol": s, "dte": h + 1, "expiry": days[c - 1 + h], "implied_move_pct": imp, "underlying": px[s][days[c - 1]]}})
    return rows, px


def test_om2_gate_counts_independent_expiry_cycles_not_symbol_rows():
    rows, px = _surface_history(seed=1, n_cap=120, rich=0.5)        # implied 50% rich: the old harness called this supported
    rep = implied_move_vs_realised(rows, px)
    assert rep["n_symbol_captures"] == 8 * rep["n_resolved_captures"]  # one observation per capture day, not per symbol row
    assert rep["n_resolved_captures"] == 119 and rep["n_independent_cycles"] == 6
    assert rep["block_len"] >= 21                                       # block covers the realised window (in captures)
    assert rep["verdict"] == "inconclusive" and "6/30 independent" in rep["reason"]


def test_om2_null_size_near_nominal_with_30_plus_cycles():
    reps = [implied_move_vs_realised(*_surface_history(seed=s, n_cap=700), n_boot=499, seed=s) for s in range(20)]
    assert all(r["n_independent_cycles"] >= 30 for r in reps)
    false_pos = sum(r["verdict"] == "supported" for r in reps)
    assert false_pos <= 3                                               # was ~35-40% with 5-row blocks over symbol rows
    rich = implied_move_vs_realised(*_surface_history(seed=99, n_cap=700, rich=0.25), n_boot=499)
    assert rich["verdict"] == "supported"                               # power on a planted 25% premium


# ------------------------------------------------------------------------------- OM-3 (T-66): anchor at the quote's spot --

def test_om3_realised_move_starts_at_the_quotes_own_spot():
    days = _iso_days(date(2027, 3, 1), 60)
    closes = {d: (100.0 if i <= 10 else 110.0) for i, d in enumerate(days)}   # +10% on the capture day itself (day 11)
    for underlying in (100.0, None):                                    # row spot, else the quote day's close (day 10)
        v = {"symbol": "SPY", "expiry": days[40], "dte": 29, "implied_move_pct": 9.0}
        if underlying is not None:
            v["underlying"] = underlying
        rep = implied_move_vs_realised([{"available_at": days[11] + "T07:10:00+00:00", "value": v}], {"SPY": closes})
        assert rep["n_resolved_captures"] == 1
        assert abs(rep["mean_realised_pct"] - 100 * math.log(1.1)) < 1e-9   # was 0: the capture-day move was dropped
        assert rep["mean_diff_pct"] < 0 and rep["verdict"] == "inconclusive"


def test_om3_dte_from_quote_day_and_weekend_captures_collapse():
    start = date(2027, 1, 4)                                            # a Monday
    weekdays = [start + timedelta(days=i) for i in range(80) if (start + timedelta(days=i)).weekday() < 5]
    px = {"SPY": {d.isoformat(): 100.0 + 0.01 * i for i, d in enumerate(weekdays)}}
    fri, mon = date(2027, 1, 8), date(2027, 1, 11)
    e1, e2 = (fri + timedelta(days=28)).isoformat(), (mon + timedelta(days=31)).isoformat()   # 28 vs 34 days from the quote day
    caps = [fri + timedelta(days=k) for k in (1, 2, 3)]                 # Sat, Sun, Mon pre-open: all quote Friday's close
    rows = []
    for c in caps:
        rows.append({"available_at": c.isoformat() + "T07:10:00+00:00",
                     "value": {"symbol": "SPY", "expiry": e1, "dte": (date.fromisoformat(e1) - c).days, "implied_move_pct": 4.0, "underlying": px["SPY"][fri.isoformat()]}})
        rows.append({"available_at": c.isoformat() + "T07:10:00+00:00",
                     "value": {"symbol": "SPY", "expiry": e2, "dte": (date.fromisoformat(e2) - c).days, "implied_move_pct": 6.0, "underlying": px["SPY"][fri.isoformat()]}})
    rep = implied_move_vs_realised(rows, px)
    assert rep["n_resolved_captures"] == 1 and rep["n_symbol_captures"] == 3
    assert rep["mean_implied_pct"] == 4.0                               # Monday's row has dte 31 to e2, but from Friday's quotes e1 is nearer 30


# ------------------------------------------------------------------------------- OM-7 (T-52) --

def _skew_case(n: int, top_more_volatile: bool = True, seed: int = 0):
    rng = np.random.default_rng(seed)
    d0 = datetime(2000, 1, 3, tzinfo=UTC)
    days = [d0 + timedelta(days=i) for i in range(n)]
    trend = np.linspace(110, 150, n)                                    # first half never reaches the full-sample top quintile
    sk = trend + rng.normal(0, 3, n)
    hi = sk > np.quantile(sk, 0.8); lo = sk < np.quantile(sk, 0.2)
    vol = 0.010 + 0.012 * (hi if top_more_volatile else lo)
    S = 100 * np.exp(np.cumsum(rng.normal(0, 1, n) * vol))
    return ([{"value": {"day": d.strftime("%Y-%m-%d"), "close": float(x)}} for d, x in zip(days, sk)],
            [{"value": {"symbol": "SPY", "t": d.timestamp(), "close": float(x)}} for d, x in zip(days, S)])


def test_om7_untestable_half_caps_skew_tail_at_inconclusive():
    rep = skew_tail(*_skew_case(4000), symbol="SPY")
    assert rep["crash_prob_top_minus_bottom"] > 0 and rep["p_value"] < 0.05     # the old code returned supported here
    assert any(math.isnan(h) for h in rep["halves"]) and not rep["halves_testable"]
    assert rep["verdict"] == "inconclusive" and "half not testable" in rep["reason"]


def test_om7_failing_difference_is_still_not_supported_and_min_n_gates():
    rep = skew_tail(*_skew_case(4000, top_more_volatile=False), symbol="SPY", n_boot=300)
    assert rep["crash_prob_top_minus_bottom"] <= 0 and rep["verdict"] == "not_supported"
    short = skew_tail(*_skew_case(1500), symbol="SPY", n_boot=300)     # trial min_n is 2000 days (was 500)
    assert short["verdict"] == "inconclusive" and short["min_n"] == 2000


# ------------------------------------------------------------------------------- OM-16 (T-54..T-57) --

def _overlay_inputs(with_adj: bool):
    rng = np.random.default_rng(7)
    n = 2600
    d0 = 1_262_304_000
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    factor = 1.0001 ** np.arange(n)                                     # ~2.5% a year of dividends, reinvested in adjclose
    px = [{"value": {"symbol": "SPY", "t": d0 + 86400 * i, "close": float(c), **({"adjclose": float(c * f)} if with_adj else {})}}
          for i, (c, f) in enumerate(zip(closes, factor))]
    days = [datetime.fromtimestamp(d0 + 86400 * i, tz=UTC).strftime("%Y-%m-%d") for i in range(n)]
    vix = [{"value": {"day": d, "close": 16.0}} for d in days]
    rate = [{"value": {"day": d, "close": 3.0}} for d in days]
    return px, vix, rate, closes * factor


def test_om16_stock_legs_earn_dividends_and_sharpe_is_excess_of_bills():
    px, vix, rate, total = _overlay_inputs(True)
    px0, _, _, _ = _overlay_inputs(False)
    bh = overlay_backtest(px, vix, rate, "buy_and_hold")
    idx = np.arange(0, len(total) - 21, 21)
    assert np.allclose(bh["benchmark"], total[idx + 21] / total[idx] - 1)      # total-return benchmark
    assert np.allclose(bh["returns"], bh["benchmark"]) and bh["dividends_included"]
    cc, cc0 = overlay_backtest(px, vix, rate, "covered_call"), overlay_backtest(px0, vix, rate, "covered_call")
    assert np.all(cc["returns"] - cc0["returns"] > 0)                          # covered call collects the dividend too
    csp, csp0 = overlay_backtest(px, vix, rate, "cash_secured_put"), overlay_backtest(px0, vix, rate, "cash_secured_put")
    assert np.allclose(csp["returns"], csp0["returns"])                        # no stock leg: unchanged
    ppy = 252 / 21
    assert abs(csp["sharpe"] - sharpe_ratio(csp["returns"] - csp["bill_returns"], ppy)) < 1e-12
    assert abs(csp["benchmark_sharpe"] - sharpe_ratio(csp["benchmark"] - csp["bill_returns"], ppy)) < 1e-12
    assert np.allclose(csp["bill_returns"], math.exp(0.03 * 21 / 252) - 1)
    ss = overlay_backtest(px, vix, rate, "short_straddle")                    # unfunded: raw P&L is already an excess return
    assert abs(ss["sharpe"] - sharpe_ratio(ss["returns"], ppy)) < 1e-12
    v = overlay_verdict(csp, n_boot=200)
    assert "bill_returns" not in v and "returns" not in v


# ------------------------------------------------------------------------------- OM-4 (T-38): point in time --

def test_om4_close_ts_equity_dst_and_crypto():
    assert close_ts("SPY", "2026-10-14") == datetime(2026, 10, 14, 20, tzinfo=UTC).timestamp()
    assert close_ts("SPY", "2026-12-14") == datetime(2026, 12, 14, 21, tzinfo=UTC).timestamp()
    assert close_ts("BTC-USD", "2026-10-14") == datetime(2026, 10, 15, 0, tzinfo=UTC).timestamp()


def _px_rows(symbol, closes, start=date(2026, 6, 1)):
    t0 = datetime(start.year, start.month, start.day, 13, 30, tzinfo=UTC).timestamp()
    return [{"value": {"symbol": symbol, "t": t0 + 86400 * i, "close": float(c)}} for i, c in enumerate(closes)]


def test_om4_post_close_captures_are_not_joined_and_n_days_counts_contributing_days():
    rng = np.random.default_rng(4)
    n = 45
    start = date(2026, 6, 1)
    px = []; rows = []
    for t in ("AAA", "BBB", "CCC"):
        closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n + 1)))
        px += _px_rows(t, closes, start)
        for i in range(n):
            d = (start + timedelta(days=i)).isoformat()
            nxt = abs(math.log(closes[i + 1] / closes[i]))
            # mentions that "know" tomorrow's move, captured the next morning (after close(d)): pure look-ahead
            rows.append({"available_at": (start + timedelta(days=i + 1)).isoformat() + "T07:10:00+00:00",
                         "value": {"source": "reddit", "ticker": t, "day": d, "mentions": 1000 * nxt}})
    rep = attention_vs_abs_return(rows, px, n_perm=200)
    assert rep["n_days"] == 0 and rep["n_rows_after_decision_time"] == 3 * n and rep["verdict"] == "inconclusive"   # old: supported, rho ~1
    # same-day 21:30 UTC is after the 20:00 UTC equity close (summer) but before the 24:00 UTC crypto close
    btc = _px_rows("BTC-USD", [100, 101, 99])
    late = [{"available_at": "2026-06-01T21:30:00+00:00", "value": {"source": "stocktwits", "ticker": t, "day": "2026-06-01", "mentions": 5}} for t in ("AAA", "BTC")]
    joined, dropped = attention_ticker_days(late, daily_closes(px + btc))
    assert set(joined) == {("BTC-USD", "2026-06-01")} and dropped == 1
    # capture days with no joinable row do not count toward the 30-day gate
    ok = [{"available_at": (start + timedelta(days=i)).isoformat() + "T15:00:00+00:00",
           "value": {"source": "reddit", "ticker": "AAA", "day": (start + timedelta(days=i)).isoformat(), "mentions": float(i % 4)}} for i in range(5)]
    noise = [{"available_at": (start + timedelta(days=i)).isoformat() + "T15:00:00+00:00",
              "value": {"source": "reddit", "ticker": "ZZZ", "day": (start + timedelta(days=i)).isoformat(), "mentions": 3}} for i in range(40)]
    assert attention_vs_abs_return(ok + noise, px, n_perm=50)["n_days"] == 5   # old: 40


# ------------------------------------------------------------------------------- OM-12 (T-38): one row per ticker-day --

def test_om12_sources_summed_latest_valid_capture_per_source():
    closes = daily_closes(_px_rows("BTC-USD", [100.0, 103.0, 101.0], start=date(2026, 10, 14)))
    D = "2026-10-14"
    rows = [
        {"available_at": "2026-10-14T10:08:28+00:00", "value": {"source": "stocktwits", "ticker": "BTC", "day": D, "mentions": 96}},
        {"available_at": "2026-10-15T07:11:00+00:00", "value": {"source": "stocktwits", "ticker": "BTC", "day": D, "mentions": 10}},  # after close
        {"available_at": "2026-10-15T07:11:00+00:00", "value": {"source": "reddit", "ticker": "BTC", "day": D, "mentions": 6}},       # after close
        {"available_at": "2026-10-14T09:00:00+00:00", "value": {"source": "reddit", "ticker": "BTC", "day": D, "mentions": 4}},
        {"available_at": "2026-10-14T18:00:00+00:00", "value": {"source": "reddit", "ticker": "BTC", "day": D, "mentions": 5}},       # latest valid
        {"available_at": "2026-10-14T12:00:00+00:00", "value": {"source": "x", "ticker": "BTC", "day": D, "mentions": 100}},         # not in the claim
    ]
    joined, dropped = attention_ticker_days(rows, closes)
    assert list(joined) == [("BTC-USD", D)] and dropped == 2
    assert joined[("BTC-USD", D)]["mentions"] == 96 + 5
    assert abs(joined[("BTC-USD", D)]["abs_ret"] - abs(math.log(103 / 100))) < 1e-12
    # n_ticker_days counts ticker-days, not (source, capture) rows
    rng = np.random.default_rng(5)
    n = 40; start = date(2026, 6, 1); px = []; drows = []
    for t in ("AAA", "BBB", "CCC"):
        px += _px_rows(t, 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n + 1))), start)
        for i in range(n):
            d = (start + timedelta(days=i)).isoformat()
            for src in ("reddit", "stocktwits"):
                drows.append({"available_at": d + "T15:00:00+00:00", "value": {"source": src, "ticker": t, "day": d, "mentions": float(rng.poisson(10))}})
    rep = attention_vs_abs_return(drows, px, n_perm=100)
    assert rep["n_ticker_days"] == 3 * n and rep["n_days"] == n         # old: 6n "ticker-days"


# ------------------------------------------------------------------------------- OM-10 (T-41): conjunction --

def _fng_case(greed_drift: float, seed: int = 2, n: int = 3000):
    rng = np.random.default_rng(seed)
    d0 = datetime(2018, 2, 1, tzinfo=UTC)
    days = [d0 + timedelta(days=i) for i in range(n)]
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.97 * x[i - 1] + rng.normal(0, 1)
    fng = np.clip(50 + 9 * x, 0, 100)
    drift = np.roll(np.where(fng <= 25, 0.004, np.where(fng >= 75, greed_drift, -0.0005)), 1)
    P = 10000 * np.exp(np.cumsum(drift + rng.normal(0, 0.02, n)))
    return ([{"observed_at": d.strftime("%Y-%m-%dT00:00:00+00:00"), "value": {"value": float(v)}} for d, v in zip(days, fng)],
            [{"value": {"symbol": "BTC-USD", "t": d.timestamp(), "close": float(p)}} for d, p in zip(days, P)])


def test_om10_greed_side_contradicting_the_claim_is_not_supported():
    rep = fear_greed_forward_returns(*_fng_case(greed_drift=+0.004), n_boot=500)
    assert rep["d_fear"] > 0 and rep["p_fear"] < 0.05 and all(h > 0 for h in rep["d_fear_halves"])   # fear side alone passes
    assert rep["d_greed"] > 0                                          # greed side contradicts "falls short"
    assert rep["verdict"] == "not_supported" and "falls short" in rep["reason"]   # old: supported


# ------------------------------------------------------------------------------- OM-11 (T-19): lag semantics --

def test_om11_negative_lag_does_not_wrap_to_the_last_price():
    n = 60
    d0 = datetime(2024, 1, 1, tzinfo=UTC)
    fng = [{"observed_at": (d0 + timedelta(days=i)).isoformat(), "value": {"value": 50}} for i in range(n)]
    px = [{"value": {"symbol": "BTC-USD", "t": (d0 + timedelta(days=i)).timestamp(), "close": 100.0 + i}} for i in range(n)]
    naive = fear_greed_forward_returns(fng, px, lag_days=-1)
    assert naive["n"] == n - 7                                          # old: n - 6, the first day entered at days[-1]
    assert fear_greed_forward_returns(fng, px, lag_days=0)["n"] == n - 7


# ------------------------------------------------------------------------------- OM-5 (T-01, T-02, T-13): close anchor --

def _iso(ts):
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")


def _market(mid, closed, end, yes=True):
    return {"value": {"id": mid, "umaResolutionStatus": "resolved", "outcomePrices": json.dumps(["1", "0"] if yes else ["0", "1"]),
                      "outcomes": json.dumps(["Yes", "No"]), "closedTime": _iso(closed) if closed else None, "endDate": _iso(end) if end else None,
                      "question": mid}}


def test_om5_horizon_prices_are_taken_before_the_outcome_is_known():
    end = datetime(2024, 11, 5, 12, tzinfo=UTC).timestamp()
    slow = _market("slow", end + 30 * 86400, end)                     # UMA resolution a month after the event
    early = _market("early", end - 10 * 86400, end + 50 * 86400)      # resolved early: closedTime before endDate
    prices = []
    for k in range(-120, 40):
        t = end + k * 86400
        prices.append({"value": {"market_id": "slow", "t": t, "p": 0.6 if t <= end else 0.999}})
        prices.append({"value": {"market_id": "early", "t": t, "p": 0.3}})
    oc = resolved_outcomes([slow, early])
    assert oc["slow"]["close_ts"] == end and oc["slow"]["anchor"] == "endDate" and oc["slow"]["postponed_flag"]
    assert oc["early"]["close_ts"] == end - 10 * 86400 and oc["early"]["anchor"] == "closedTime" and not oc["early"]["postponed_flag"]
    byh = price_at_horizons(prices, oc, horizons_days=(1, 7))
    assert {m: p for p, _, m in byh[1]}["slow"] == 0.6                 # was 0.999, a post-event price
    # an outcome anchored after its endDate (e.g. built elsewhere from closedTime) loses its post-event cutoffs
    dropped = {}
    stale = {"slow": {**oc["slow"], "close_ts": end + 30 * 86400}}
    assert price_at_horizons(prices, stale, horizons_days=(1, 7, 90), dropped=dropped)[1] == []
    assert dropped == {1: 1, 7: 1, 90: 0}
    rep = market_calibration(prices, [slow, early], horizons_days=(1,))
    assert rep["close_anchor"]["anchored_at_endDate"] == 1 and rep["close_anchor"]["postponed_flagged"] == 1


# ------------------------------------------------------------------------------- OM-6 (T-03): signs at every horizon --

def _byh(means: dict, n: int = 300):
    """Rows (p=0.5, outcome, id) whose mean(outcome - price) is exactly the given value per horizon."""
    out = {}
    for h, m in means.items():
        k = int(round((m + 0.5) * n))
        out[h] = [(0.5, int(i < k), f"{h}-{i}") for i in range(n)]
    return out


def test_om6_one_significant_horizon_with_opposite_raw_signs_does_not_agree(monkeypatch):
    mixed = {1: -0.02, 3: -0.02, 7: -0.02, 30: 0.12, 90: 0.02}
    monkeypatch.setattr(markets, "price_at_horizons", lambda *a, **k: _byh(mixed))
    rep = multiscale_edge([], [])
    assert rep["n_scales_significant"] == 1 and rep["raw_signs"] == {"1": -1, "3": -1, "7": -1, "30": 1, "90": 1}
    assert rep["signs_agree"] is False                                  # old: True (non-significant horizons were ignored)
    same = {1: 0.02, 3: 0.02, 7: 0.02, 30: 0.12, 90: 0.02}
    monkeypatch.setattr(markets, "price_at_horizons", lambda *a, **k: _byh(same))
    assert multiscale_edge([], [])["signs_agree"] is True
    short = _byh(same); short[90] = short[90][:10]                      # 90d unscored: agreement at every horizon not shown
    monkeypatch.setattr(markets, "price_at_horizons", lambda *a, **k: short)
    assert multiscale_edge([], [])["signs_agree"] is False


# ------------------------------------------------------------------------------- OM-13 (T-04): gas per order --

def _book(ask_y, ask_n, size_y, size_n, bid_y=0.40, bid_n=0.40):
    lvl = lambda p, s: [{"price": str(p), "size": str(s)}]
    return {"value": {"question": "q", "books": {"yes": {"asks": lvl(ask_y, size_y), "bids": lvl(bid_y, 100)},
                                                  "no": {"asks": lvl(ask_n, size_n), "bids": lvl(bid_n, 100)}}}}


def test_om13_gas_is_charged_per_order_on_the_executable_size():
    rep = bundle_arb_scan([_book(0.48, 0.49, 1000, 1000)])
    assert rep["long_after_fees"] == 1                                  # old: 0 (gas subtracted from a per-share edge)
    ex = rep["examples_long"][0]
    assert abs(ex["net_usd"] - (1000 * (1 - 0.97 * 1.015) - 0.04)) < 0.006 and ex["size_shares"] == 1000
    assert abs(ex["net_edge"] - (1 - 0.97 * 1.015 - 0.04 / 1000)) < 1e-4
    assert bundle_arb_scan([_book(0.48, 0.49, 20, 1000)])["long_after_fees"] == 1     # q=20: +$0.27, depth $9.60
    assert bundle_arb_scan([_book(0.48, 0.49, 2, 1000)])["long_after_fees"] == 0      # q=2: gas exceeds the edge, depth < $5
    assert bundle_arb_scan([_book(0.497, 0.498, 1000, 1000)])["long_after_fees"] == 0  # below 1 gross but not after the fee
