"""Batch-6c pmxv harnesses (T-336 cross-venue convergence, T-409 lead-lag, T-337 Polymarket vs Deribit digitals, T-358
event-uncertainty premium, T-360 Kalshi CPI vs the Cleveland Fed nowcast) on synthetic data only: for every core function
a planted effect passes and a null does not; the pair rule checks, the hourly alignment, the SVI / cubic smiles and the
Breeden-Litzenberger digital, the resolution-time parser, the nowcast sigma and the bar quote are checked directly; every
harness runs JSON-safe on a fake archive, and missing bundles give inconclusive. Regression tests cover the skeptic fixes:
T-336's secondary under both named constructions (exit rule vs pure arb held to settlement with the point-in-time T-bill
carry), T-409's DTB3 rate at each entry hour, T-337's point-in-time forward (hourly spot close, else the latest Deribit
trade index) and T-360's entry threshold as worded. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from mandel.experiments import batch6c_pmxv as m

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
H = 3600


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 200)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


class FakeArchive:
    def __init__(self, bundles: dict, created="2099-01-01T00:00:00+00:00"):
        self.b = bundles
        self.created = created

    def entries(self, kind=None, tag=None):
        return [SimpleNamespace(name=n, created_at=self.created, kind="data", tags=[]) for n in sorted(self.b)]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return SimpleNamespace(name=name, created_at=self.created, recipe="fake")

    def load(self, name):
        for r in self.b[name]:
            yield r


def row(value, observed=None, available=None, kind="x", key="k"):
    return {"source": "fake", "kind": kind, "key": key, "observed_at": observed or "2020-01-01T00:00:00+00:00",
            "available_at": available or observed or "2020-01-01T00:00:00+00:00", "value": value}


def iso(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------- pair builders --

def pm_leg(mid, tok, start_h, end_h, sign=1, label="x"):
    return {"market_id": str(mid), "condition_id": "0x", "yes_token": tok, "label": label, "sign": sign, "start": iso(start_h * H),
            "end": iso(end_h * H), "end_date": iso(end_h * H), "market_end_date": iso(end_h * H), "end_date_mismatch_hours": None, "volumeNum": 1.0}


def k_leg(ticker, start_h, end_h, sign=1, label="Above 0.3%", series="KXCPI"):
    return {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0], "series": series, "label": label, "sign": sign,
            "open_time": iso(start_h * H), "close_time": iso(end_h * H), "settlement_ts": iso(end_h * H + 600)}


def fomc_pair(i, start_h, end_h):
    return {"pair_id": f"fomc:2025-{i:02d}:{i}", "family": "fomc", "key": f"2025-{i:02d}", "template": "FOMC outcome atoms (bps move sets) equal on both sides",
            "relation": "sum(sign*p_pm) = const + sum(sign*p_kalshi)", "const": 0.0,
            "pm": [pm_leg(1000 + i, f"tok{i}", start_h, end_h, 1, "25 bps decrease")],
            "kalshi": [k_leg(f"KXFEDDECISION-25M{i:02d}-C25", start_h, end_h, 1, "Cut 25bps", "KXFEDDECISION")],
            "pm_rules": "The resolution source for this market is the FOMC statement of the Federal Reserve", "kalshi_rules": "If the Federal Reserve does a Cut of 25bps",
            "timing_gap_hours": -17.9, "timing_suspect": False, "basis_note": "same FOMC statement", "audited": False, "frozen_at": "2026-10-15T23:38:25+00:00"}


def cpi_pair(i, start_h, end_h, two_legs=True):
    legs = [k_leg(f"KXCPI-25M{i:02d}-T0.3", start_h, end_h, 1, "Above 0.3%"), k_leg(f"KXCPI-25M{i:02d}-T0.4", start_h, end_h, -1, "Above 0.4%")]
    return {"pair_id": f"cpi_mom:2025-{i:02d}:{i}", "family": "cpi_mom", "key": f"2025-{i:02d}", "template": "CPI bucket eq 0.4 = 0 + +K(above 0.3) -K(above 0.4)",
            "relation": "sum(sign*p_pm) = const + sum(sign*p_kalshi)", "const": 0.0, "pm": [pm_leg(2000 + i, f"ctok{i}", start_h, end_h, 1, "0.4%")],
            "kalshi": legs if two_legs else legs[:1],
            "pm_rules": "Consumer Price Index published by the Bureau of Labor Statistics", "kalshi_rules": "If the Consumer Price Index (CPI) increases by more than 0.3%",
            "timing_gap_hours": -1.4, "timing_suspect": False, "basis_note": "same BLS print (one decimal)", "audited": False, "frozen_at": "2026-10-15T23:38:25+00:00"}


def btc_pair():
    return {"pair_id": "btc:2026-10-14T17ET:1", "family": "btc", "key": "2026-10-14T17ET", "template": "PM above X at the hour = Kalshi above X - 0.01 at the same ET hour",
            "relation": "sum(sign*p_pm) = const + sum(sign*p_kalshi)", "const": 0.0, "pm": [pm_leg(5700022, "btok", 100, 103, 1, "83,000")],
            "kalshi": [k_leg("KXBTCD-26OCT1417-T82999.99", 80, 103, 1, "$83,000 or above", "KXBTCD")],
            "pm_rules": "The resolution source for this market is Binance BTC/USDT", "kalshi_rules": "If the simple average of CF Benchmarks' Bitcoin Real-Time Index (BRTI) is above 82999.99",
            "timing_gap_hours": 0.0, "timing_suspect": False, "basis_note": "resolution basis differs: Binance BTCUSDT candle close (PM) vs CF Benchmarks BRTI", "audited": False}


# ------------------------------------------------------------------------------------------- rule checks --

def test_pair_rule_checks_families_and_failures():
    good = m.pair_rule_checks(fomc_pair(1, 0, 100))
    assert good["audited"] and good["source_ok"] and good["timing_ok"] and good["strike_ok"] and not good["basis_flag"]
    cpi = m.pair_rule_checks(cpi_pair(1, 0, 100))
    assert cpi["audited"] and cpi["strike_ok"]
    bad_strike = cpi_pair(2, 0, 100)
    bad_strike["kalshi"][1]["ticker"] = "KXCPI-25M02-T0.5"
    assert not m.pair_rule_checks(bad_strike)["strike_ok"]
    btc = m.pair_rule_checks(btc_pair())
    assert btc["audited"] and btc["basis_flag"] and btc["strike_ok"]
    off = btc_pair()
    off["pm"][0]["label"] = "83,250"
    assert not m.pair_rule_checks(off)["strike_ok"]
    late = fomc_pair(3, 0, 100)
    late["timing_gap_hours"], late["timing_suspect"] = -1829.0, True
    assert not m.pair_rule_checks(late)["timing_ok"] and not m.pair_rule_checks(late)["audited"]
    mism = fomc_pair(4, 0, 100)
    mism["pm"][0]["end_date_mismatch_hours"] = 456.0
    assert not m.pair_rule_checks(mism)["end_date_ok"]
    # differently resolved pairs are flagged from the stored outcomes only
    p = cpi_pair(5, 0, 100)
    c = m.pair_rule_checks(p, {"2005": 1}, {"KXCPI-25M05-T0.3": 1, "KXCPI-25M05-T0.4": 0})
    assert c["mismatch_resolved"] is False
    c = m.pair_rule_checks(p, {"2005": 1}, {"KXCPI-25M05-T0.3": 1, "KXCPI-25M05-T0.4": 1})
    assert c["mismatch_resolved"] is True
    assert m.pair_rule_checks(p, {"2005": None}, {})["mismatch_resolved"] is None


def test_coverage_gaps_and_holm():
    pairs = [fomc_pair(1, 0, 10), cpi_pair(2, 0, 10), btc_pair()]
    checks = {p["pair_id"]: m.pair_rule_checks(p) for p in pairs}
    g = m.coverage_gaps(pairs, checks)
    assert g["families"] == {"fomc": 1, "cpi_mom": 1, "btc": 1} and g["btc_days"] == 1 and g["audit_failures"] == {}
    assert m.holm_adjusted([0.01, 0.03, 0.2, 0.5, 0.9], 0) == pytest.approx(0.05)
    assert m.holm_adjusted([0.01, 0.03, 0.2, 0.5, 0.9], 1) == pytest.approx(0.12)
    assert m.holm_adjusted([0.2, None], 0) == pytest.approx(0.4)
    assert m.wilson_lower(40, 50) == pytest.approx(0.6696, abs=1e-3) and m.wilson_upper(40, 50) > 0.88


# ------------------------------------------------------------------------------------------- alignment --

def test_align_pair_hour_grid_ffill_and_spread_filter():
    pair = cpi_pair(1, 10, 60)
    hours = np.arange(10, 60)
    pm = {"ctok1": (hours[hours != 30], np.full(49, 0.40))}                      # one missing hour: forward-filled
    bid = np.full(50, 0.30)
    ask = np.full(50, 0.34)
    k = {"KXCPI-25M01-T0.3": (hours, np.full(50, 0.60), np.full(50, 0.64), np.full(50, 5.0)),
         "KXCPI-25M01-T0.4": (hours[::2], bid[::2], ask[::2], np.full(25, 3.0))}  # every other hour: forward-filled
    k["KXCPI-25M01-T0.3"][1][20] = 0.0                                             # an illiquid hour: bid 0 / ask 1
    k["KXCPI-25M01-T0.3"][2][20] = 1.0
    al = m.align_pair(pair, pm, k, {"2001": 0.05}, 0.01, {"2001": {h: 2.0 for h in range(0, 60)}})
    assert al["hours"][0] == 10 and al["hours"][-1] == 59 and al["close_hour"] == 60
    assert al["valid"].sum() == 49 and not al["valid"][20]
    assert al["P"][0] == pytest.approx(0.40) and al["K"][0] == pytest.approx(0.62 - 0.32)
    assert al["Kask"][0] == pytest.approx(0.64 - 0.30) and al["Kbid"][0] == pytest.approx(0.60 - 0.34)
    assert al["Pask"][0] == pytest.approx(0.41) and al["fee_pm"][0] == pytest.approx(0.05 * 0.4 * 0.6)
    assert al["fee_k"][0] == pytest.approx(0.07 * (0.62 * 0.38 + 0.32 * 0.68))
    assert al["vol_k"][1] == pytest.approx(5.0) and al["vol_k"][0] == pytest.approx(8.0) and al["vol_pm"][3] == 2.0
    assert m.align_pair(pair, {}, k) is None
    al2 = m.align_pair(pair, pm, k, pm_volume={})                                 # no PM volume for the leg: NaN
    assert np.isnan(al2["vol_pm"]).all()
    assert m.align_pair(pair, pm, k, pm_volume={}, require_volume=True) is None
    # the liquidity filter: hours whose PM leg had no taker volume in the previous 24 hours are invalid
    al3 = m.align_pair(pair, pm, k, pm_volume={"2001": {h: 1.0 for h in range(0, 30)}})
    assert al3["valid"][:20].all() and al3["valid"][19] and not al3["valid"][44:].any() and al3["valid"][43]
    # a Kalshi quote forward-filled beyond the staleness cap is invalid
    k2 = {"KXCPI-25M01-T0.3": (np.array([10]), np.array([0.6]), np.array([0.64]), np.array([5.0])),
          "KXCPI-25M01-T0.4": (np.array([10]), np.array([0.3]), np.array([0.34]), np.array([3.0]))}
    al4 = m.align_pair(pair, pm, k2, k_stale_max=5)
    assert al4["valid"][:6].all() and not al4["valid"][6:].any()


def make_aligned(P, K, spread=0.02, hs=0.01, vol_pm=None, vol_k=None, d_res=0.0, pid="p", event="e", cat="macro"):
    P, K = np.asarray(P, float), np.asarray(K, float)
    n = P.size
    return {"pair_id": pid, "family": "fomc", "category": cat, "event": event, "hours": np.arange(n), "P": P, "K": K,
            "Kask": K + spread / 2, "Kbid": K - spread / 2, "Pask": P + hs, "Pbid": P - hs, "fee_pm": np.zeros(n),
            "fee_k": m.KALSHI_FEE * K * (1 - K), "valid": np.ones(n, dtype=bool),
            "vol_pm": np.full(n, 1.0) if vol_pm is None else np.asarray(vol_pm, float), "vol_k": np.full(n, 1.0) if vol_k is None else np.asarray(vol_k, float),
            "close_hour": n, "start_hour": 0, "n_pm_legs": 1, "n_k_legs": 1, "d_res": d_res, "available_at": "2025-01-01"}


# ------------------------------------------------------------------------------------------- T-336 --

def gap_series(rng, n, convergent, n_ep=12, sigma=0.6):
    """Kalshi mid flat at 0.5 with small noise; PM = K + gap (points). Convergent: an AR(1) gap (0.7 an hour) with jumps
    of 6-10 points; null: a random walk with step sd 2 points, reflected at +/-20 (the same realised hourly volatility
    the harness matches its null to)."""
    K = 0.5 + rng.normal(0, 0.002, n)
    gap = np.zeros(n)
    if convergent:
        jumps = set(rng.choice(np.arange(5, n - 40), n_ep, replace=False).tolist())
        for t in range(1, n):
            gap[t] = 0.7 * gap[t - 1] + rng.normal(0, sigma) + (rng.choice([-1, 1]) * rng.uniform(6, 10) if t in jumps else 0.0)
    else:
        for t in range(1, n):
            x = gap[t - 1] + rng.normal(0, 2.0)
            gap[t] = x if abs(x) <= 20 else np.sign(x) * (40 - abs(x))
    return K + gap / 100.0, K


def test_episodes_and_halving_test_planted_vs_null():
    rng = np.random.default_rng(1)
    for convergent in (True, False):
        eps = []
        for i in range(12):
            P, K = gap_series(rng, 500, convergent)
            al = make_aligned(P, K, pid=f"p{i}", event=f"ev{i % 6}")
            d = 100 * (al["P"] - al["K"])
            dd = np.diff(d)
            sigma = float(np.std(dd))
            for e in m.episodes_halving(al["hours"], d, al["valid"]):
                if e.get("halved") is not None:
                    e["event"] = al["event"]
                    e["null_p"] = m.rw_null_halving(e["d0"], sigma, rng=rng)
                    eps.append(e)
        ht = m.halving_test(eps, n_boot=200)
        assert ht["n"] >= 50
        if convergent:
            assert ht["rate"] > 0.9 and ht["wilson_lower"] > 0.7 and ht["cluster_lower"] > 0.7 and ht["p_vs_null"] < 0.05
        else:
            # a high-volatility random walk can clear 70% on its own: the null criterion is the clustered p, which
            # must not reject when the gaps are random walks with that volatility
            assert ht["p_vs_null"] > 0.05 and abs(ht["rate_with_null"] - ht["null_rate"]) < 0.1


def test_episode_rules_fresh_crossing_truncation_and_sparse_window():
    hours = np.arange(200)
    d = np.zeros(200)
    d[10:40] = 8.0                                 # starts mid-run: fresh (previous valid hour had |d| <= 5)
    d[100] = 7.0
    d[101:125] = 2.0                               # halves in the window
    d[190] = 9.0                                   # too close to the grid end: truncated
    v = np.ones(200, bool)
    eps = m.episodes_halving(hours, d, v)
    assert [e["start"] for e in eps] == [10, 100, 190]
    assert eps[0]["halved"] is False and eps[1]["halved"] is True and eps[1]["hours_to_half"] == 1 and eps[2]["truncated"]
    v[101:120] = False                             # sparse window: not counted
    eps = m.episodes_halving(hours, d, v)
    assert eps[1].get("sparse") and eps[1]["halved"] is None
    d2 = np.full(200, 8.0)                         # a standing gap never fresh: no episode
    assert m.episodes_halving(hours, d2, np.ones(200, bool)) == []
    assert m.rw_null_halving(8.0, 3.0, rng=np.random.default_rng(0)) > m.rw_null_halving(8.0, 1.0, rng=np.random.default_rng(0))
    assert m.rw_null_halving(8.0, 0.0) == 0.0


def test_convergence_pnl_captures_the_gap_net_of_costs():
    P = np.array([0.50, 0.58, 0.55, 0.505, 0.50])
    K = np.full(5, 0.50)
    al = make_aligned(P, K, spread=0.02, hs=0.01)
    d = 100 * (P - K)
    t = m.convergence_pnl(al, 1, d, 0.0)
    assert t["exit"] == "gap<1" and t["hours_held"] == 2
    fees = 100 * (al["fee_k"][1] + al["fee_k"][3])
    assert t["net"] == pytest.approx(100 * ((0.57 - 0.51) - (0.515 - 0.49)) - fees)
    held = m.convergence_pnl(make_aligned([0.5, 0.6, 0.6], [0.5, 0.5, 0.5]), 1, np.array([0, 10, 10.0]), 0.0)
    assert held["exit"] == "resolution" and held["net"] == pytest.approx(100 * (0.59 - 0.51) - 100 * 0.07 * 0.25)
    bad = m.convergence_pnl(make_aligned([0.5, 0.6, 0.6], [0.5, 0.5, 0.5]), 1, np.array([0, 10, 10.0]), 100.0)
    assert bad["net"] < -50
    assert m.convergence_pnl(make_aligned([0.5, 0.6, 0.6], [0.5, 0.5, 0.5]), 1, np.array([0, 10, 10.0]), None) is None


# ------------------------------------------------------------------------------------------- T-409 --

def leadlag_pair(rng, n, follows, pid):
    """PM leads (higher volume): jumps of +/-8 cents with alternating signs; Kalshi follows by 8 cents the next hour
    when ``follows`` (a 1-cent spread and 1.75 cents of fee a side leave about +3.5 cents), else moves at random."""
    P = np.full(n, 0.5)
    K = np.full(n, 0.5)
    jumps = np.sort(rng.choice(np.arange(2, n - 5, 6), n // 20, replace=False))
    for i, j in enumerate(jumps):
        s = 1 if i % 2 == 0 else -1
        P[j:] += s * 0.08
        if follows:
            K[j + 1:] += s * 0.08
        else:
            K[j + 1:] += rng.choice([-1, 1]) * 0.08 * rng.random()
    P, K = np.clip(P, 0.05, 0.95), np.clip(K, 0.05, 0.95)
    return make_aligned(P, K, spread=0.01, hs=0.005, vol_pm=np.full(n, 10.0), vol_k=np.full(n, 1.0), pid=pid)


def test_follow_trades_planted_lead_lag_vs_null():
    rng = np.random.default_rng(2)
    good = [t for i in range(20) for t in m.follow_trades(leadlag_pair(rng, 300, True, f"g{i}"), 3.0, 1)]
    null = [t for i in range(20) for t in m.follow_trades(leadlag_pair(rng, 300, False, f"n{i}"), 3.0, 1)]
    assert len(good) >= 100 and all(t["leader"] == "pm" for t in good)
    tg, tn = m._pair_test(good), m._pair_test(null)
    assert tg["mean"] > 1.0 and tg["ci"][0] > 0 and tg["robust_ci"][0] > 0
    assert not (tn["ci"][0] > 0)
    # the follower must have moved less than half as much, and the signal needs |Delta| >= c
    al = make_aligned([0.5, 0.56, 0.56, 0.56], [0.5, 0.55, 0.55, 0.55], vol_pm=np.full(4, 10.0))
    assert m.follow_trades(al, 3.0, 1) == []
    al = make_aligned([0.5, 0.52, 0.52, 0.52], [0.5, 0.5, 0.5, 0.5], vol_pm=np.full(4, 10.0))
    assert m.follow_trades(al, 3.0, 1) == []
    al = make_aligned([0.5, 0.56, 0.56, 0.56], [0.5, 0.5, 0.55, 0.55], vol_pm=np.full(4, 10.0))
    tr = m.follow_trades(al, 3.0, 1)
    assert len(tr) == 1 and tr[0]["dir"] == 1 and tr[0]["net"] == pytest.approx(100 * (0.54 - 0.51) - 100 * 0.07 * (0.25 + 0.55 * 0.45))
    # a pair without Polymarket volume cannot name a leader; an untraded follower is not bought
    al["vol_pm"] = np.full(4, np.nan)
    assert m.follow_trades(al, 3.0, 1) == []
    al = make_aligned([0.5, 0.56, 0.56, 0.56], [0.5, 0.5, 0.55, 0.55], vol_pm=np.full(4, 10.0), vol_k=np.zeros(4))
    assert m.follow_trades(al, 3.0, 1) == []


def test_follow_trades_volume_timing_and_three_hour_exit():
    # Polymarket volume of hour t is known only at t+1: a burst at hour t must not make PM the leader at t
    P = np.array([0.5, 0.5, 0.56, 0.56, 0.56, 0.56])
    K = np.array([0.5, 0.5, 0.50, 0.55, 0.55, 0.55])
    al = make_aligned(P, K, vol_pm=np.array([0, 0, 100.0, 0, 0, 0]), vol_k=np.array([1, 1, 1, 1, 1, 1.0]))
    assert m.follow_trades(al, 3.0, 1) == []                                      # Kalshi leads by known volume: no Kalshi signal
    al = make_aligned(P, K, vol_pm=np.array([100.0, 0, 0, 0, 0, 0]), vol_k=np.ones(6))
    assert len(m.follow_trades(al, 3.0, 1)) == 1
    # 3-hour hold exits early once the gap closes below 1 point
    P = np.array([0.5, 0.56, 0.56, 0.56, 0.56, 0.56, 0.56])
    K = np.array([0.5, 0.50, 0.52, 0.555, 0.60, 0.60, 0.60])
    al = make_aligned(P, K, vol_pm=np.full(7, 10.0))
    tr = m.follow_trades(al, 3.0, 3)
    assert len(tr) == 1 and tr[0]["exit_hours"] == 2


def test_arb_trades_and_cells():
    P = np.array([0.50, 0.50, 0.40, 0.40])
    K = np.array([0.50, 0.50, 0.50, 0.50])
    al = make_aligned(P, K, spread=0.02, hs=0.01, d_res=0.0)
    tr = m.arb_trades(al, 3.0, 0.04)
    assert len(tr) == 1 and tr[0]["hour"] == 2
    edge = 100 * (0.49 - 0.41) - 100 * (0.07 * 0.25)
    assert tr[0]["net"] == pytest.approx(edge - 100 * 0.04 * (2 / 24) / 365)
    assert m.arb_trades(make_aligned(P, K, d_res=None), 3.0) == []
    assert m.arb_trades(make_aligned(P, K, vol_k=np.zeros(4)), 3.0) == []          # an untraded Kalshi quote is not hit
    assert m.arb_trades(make_aligned(P, K, vol_pm=np.zeros(4)), 3.0) == []
    assert m.arb_trades(make_aligned(P, K, d_res=-100.0), 3.0)[0]["net"] < -90  # PM resolved 0, Kalshi 1: the long-PM arb loses
    assert m.arb_trades(make_aligned(P, K, d_res=100.0), 3.0)[0]["net"] > 90     # the opposite mismatch is a windfall
    cells = m.leadlag_cells([al, leadlag_pair(np.random.default_rng(3), 200, True, "x")])
    assert len(cells) == 32 and all(len(v) == 0 for k, v in cells.items() if "sports" in k)
    assert len(cells["c3|h1|follow|macro"]) > 0 and len(cells["c3|h1|arb|macro"]) >= 1


# ------------------------------------------------------------------------------------------- T-337 --

def test_smiles_and_digital_probability():
    tau, sig = 5 / 365, 0.5
    k = np.linspace(-0.08, 0.08, 9)
    flat = np.full(9, sig * sig * tau)
    for fit in (m.svi_fit(k, flat), m.cubic_fit(k, flat)):
        for kk in (-0.03, 0.0, 0.02):
            d2 = -kk / (sig * math.sqrt(tau)) - sig * math.sqrt(tau) / 2
            assert m.digital_prob(kk, lambda x: m.smile_w(fit, x), tau) == pytest.approx(m.norm_cdf(d2), abs=1e-6)
    skew = sig * sig * tau * (1 - 2 * k)                       # vol falling in k raises P(S > K) above the flat value
    p_svi = m.digital_prob(0.02, lambda x: m.smile_w(m.svi_fit(k, skew), x), tau)
    p_cub = m.digital_prob(0.02, lambda x: m.smile_w(m.cubic_fit(k, skew), x), tau)
    flat_p = m.norm_cdf(-0.02 / (sig * math.sqrt(tau)) - sig * math.sqrt(tau) / 2)
    assert p_svi > flat_p + 0.01 and p_cub == pytest.approx(p_svi, abs=0.005)
    svi = m.svi_fit(k, skew)
    assert svi["c"] >= abs(svi["d"]) - 1e-12 and svi["sse"] < 1e-8
    true = 0.001 + 0.05 * (-0.4 * k + np.sqrt(k * k + 0.05 ** 2))
    assert m.svi_fit(k, true)["sse"] < 1e-8
    assert m.svi_fit(k[:3], flat[:3]) is None and m.cubic_fit(k[:3], flat[:3]) is None


def synthetic_groups(hours, expiries, sig=0.5, skew=0.0, F=100000.0, strikes=None):
    """Deribit-style groups {(hour, expiry): {strike: [iv sum, n], 'F': [sum, n]}} with a flat (or linearly skewed) smile."""
    strikes = strikes or [F * x for x in (0.94, 0.96, 0.98, 0.99, 1.0, 1.01, 1.02, 1.04, 1.06)]
    g = {}
    for h in hours:
        for e in expiries:
            d = {"F": [F * 3, 3]}
            for K in strikes:
                kk = math.log(K / F)
                d[K] = [(sig + skew * kk) * 100 * 2, 2]
                g[(h, e)] = d
    return g


def test_smile_book_interpolation_and_sparse():
    H0 = 1_700_000_000 // H
    e1, e2 = "2023-11-16", "2023-11-17"
    ets = {e1: int(datetime(2023, 11, 16, 8, tzinfo=UTC).timestamp()), e2: int(datetime(2023, 11, 17, 8, tzinfo=UTC).timestamp())}
    H0 = ets[e1] // H - 30
    book = m.SmileBook(synthetic_groups(range(H0 - 3, H0 + 2), [e1, e2]), ets)
    t_res = ets[e1] + 12 * H                                   # between the two expiries
    r = book.p_rn(H0, 100000.0, t_res)
    tau = (t_res - H0 * H) / m.YEAR_S
    assert r["n_expiries"] == 2 and r["svi"] == pytest.approx(m.norm_cdf(-0.5 * math.sqrt(tau) / 2), abs=1e-3)
    assert r["cubic"] == pytest.approx(r["svi"], abs=1e-6)
    assert book.p_rn(H0, 100000.0, ets[e2] + 48 * H)["n_expiries"] == 1          # beyond the last expiry: flat scaling
    assert book.p_rn(H0, 150000.0, t_res) is None                                   # outside the strike range
    assert book.p_rn(H0, 100000.0, H0 * H + 600) is None                            # resolves within the hour
    sparse = m.SmileBook(synthetic_groups(range(H0 - 3, H0 + 2), [e1], strikes=[99000.0, 100000.0, 101000.0]), ets)
    assert sparse.p_rn(H0, 100000.0, t_res) is None and sparse.n_sparse >= 1
    # the decision at the start of hour H uses hours H-2 and H-1 only
    book2 = m.SmileBook(synthetic_groups([H0], [e1]), ets)
    assert book2.p_rn(H0, 100000.0, t_res) is None and book2.p_rn(H0 + 1, 100000.0, t_res) is not None


def fade_market(rng, mid, hours, offset, noise, planted=True):
    """Planted: Polymarket sits ``offset`` above a fair 0.5 (outcome ~ Bernoulli(0.5)). Null: Polymarket IS the fair
    probability (a martingale path resolved consistently) and the option-implied estimate carries noise, so fading
    Polymarket can only lose the fees and the haircut."""
    if planted:
        p_rn = np.full(hours.size, 0.5)
        p_poly = np.clip(0.5 + offset + rng.normal(0, noise, hours.size), 0.02, 0.98)
        outcome = int(rng.random() < 0.5)
    else:
        q = np.clip(0.5 + np.cumsum(rng.normal(0, 0.03, hours.size)), 0.03, 0.97)
        p_poly = q
        p_rn = np.clip(q + rng.normal(0, noise, hours.size), 0.01, 0.99)
        outcome = int(rng.random() < q[-1])
    return m.fade_trades(hours, p_poly, p_rn, int(hours[-1] * H + 2 * H), outcome, mid)


def test_fade_trades_planted_mispricing_vs_calibrated_polymarket():
    rng = np.random.default_rng(4)
    hours = np.arange(1000, 1024)
    planted = [t for i in range(300) for t in fade_market(rng, f"m{i}", hours, 0.08, 0.005)]
    null = [t for i in range(300) for t in fade_market(rng, f"n{i}", hours, 0.0, 0.05, planted=False)]
    assert len(planted) >= 300 and all(t["side"] == "no" for t in planted)
    xp = np.array([t["net"] for t in planted]) * 100
    xn = np.array([t["net"] for t in null]) * 100
    cp = m.cluster_stud(xp, [t["market_id"] for t in planted], 200)
    cn = m.cluster_stud(xn, [t["market_id"] for t in null], 200)
    assert cp["ci90"][0] > 0 and cp["est"] > 3
    assert cn["est"] < 0 and not (cn["ci90"][0] > 0)
    # exits: a closing gap exits at |gap| < 1 with a second fee; the tail filter and one position at a time
    hs = np.arange(5)
    tr = m.fade_trades(hs, np.array([0.60, 0.58, 0.505, 0.60, 0.60]), np.full(5, 0.5), int(10 * H), 1, "x")
    assert len(tr) == 2 and tr[0]["exit"] == "gap<1" and tr[0]["hours_held"] == 2 and tr[1]["exit"] == "resolution"
    assert tr[0]["net"] == pytest.approx((1 - 0.505) - 0.40 - 0.07 * 0.6 * 0.4 - 0.07 * 0.505 * 0.495 - 0.01)
    assert m.fade_trades(hs, np.full(5, 0.10), np.full(5, 0.03), int(10 * H), 0, "tail") == []
    assert m.fade_trades(hs, np.full(5, 0.60), np.full(5, 0.5), int(10 * H), None, "unresolved") == []


def test_btc_market_spec_parser():
    base = {"id": "1", "clobTokenIds": '["111", "222"]', "outcomePrices": '["1", "0"]', "question": "Will the price of Bitcoin be above $72,000 on October 15?",
            "groupItemTitle": "72,000", "endDate": "2026-10-15T16:00:00Z", "description": 'candle for BTC/USDT closing at 12:00 in the ET timezone (noon) on the date specified in the title',
            "_event_slug": "bitcoin-above-on-october-15-2026", "_event_end": "2026-10-15T16:00:00Z"}
    s = m.btc_market_spec(base)
    assert s["strike"] == 72000 and s["token"] == "111" and s["outcome"] == 1 and s["variant"] == "noon"
    assert s["t_res"] == int(datetime(2026, 10, 15, 12, tzinfo=ET).timestamp())
    five = dict(base, _event_slug="bitcoin-above-on-may-6-2026-5pm-et", endDate="2026-05-06T21:00:00Z", description="")
    s5 = m.btc_market_spec(five)
    assert s5["variant"] == "5pm" and s5["t_res"] == int(datetime(2026, 5, 6, 17, tzinfo=ET).timestamp())
    weekly = dict(base, groupItemTitle="", question="Bitcoin above $70,000 on Friday?", _event_slug="bitcoin-above-70000-on-friday",
                  description="Binance 1 minute candle for BTCUSDT 22 Mar '24 12:00 in the ET timezone (noon)", endDate="2024-03-22T07:00:00Z")
    sw = m.btc_market_spec(weekly)
    assert sw["strike"] == 70000 and sw["t_res"] == int(datetime(2024, 3, 22, 12, tzinfo=ET).timestamp())
    june = dict(weekly, description="Binance 1 minute candle for BTCUSDT 14 June '24 12:00 in the ET timezone (noon)", _event_slug="bitcoin-above-71000-on-june-14")
    assert m.btc_market_spec(june)["t_res"] == int(datetime(2024, 6, 14, 12, tzinfo=ET).timestamp())
    suffixed = dict(base, _event_slug="bitcoin-above-106000-on-july-4-651", description="BTC/USDT 12:00 in the ET timezone (noon) on the date", endDate="2025-07-04T16:00:00Z")
    assert m.btc_market_spec(suffixed)["t_res"] == int(datetime(2025, 7, 4, 12, tzinfo=ET).timestamp())
    assert m.btc_market_spec(dict(base, _event_slug="btc-above-100k-till-2025-end")) is None
    assert m.btc_market_spec(dict(base, outcomePrices='["0.5", "0.5"]'))["outcome"] is None


# ------------------------------------------------------------------------------------------- T-358 --

def sessions_from(start="2021-01-04", n=1500):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def test_event_regression_planted_slope_vs_null_and_placebo():
    rng = np.random.default_rng(5)
    sess = sessions_from()
    closes = 100 * np.cumprod(1 + rng.normal(0, 0.004, len(sess)))
    idx = np.sort(rng.choice(np.arange(10, len(sess) - 5), 150, replace=False))
    dates = [sess[i] for i in idx]
    U = rng.uniform(0.02, 0.25, 150)
    # plant: the two-session return into each event is 0.08 x U plus noise
    planted = closes.copy()
    for i, u in zip(idx, U):
        planted[i:] *= 1 + 0.08 * u + rng.normal(0, 0.002)
    reg = m.event_regression(dates, U, sess, planted, [0] * 150, n_boot=300)
    assert reg["n"] == 150 and reg["slope"]["slope"] > 0.04 and reg["slope"]["p_two"] < 0.05 and reg["slope"]["ci"][0] > 0
    assert reg["halves"]["first"]["slope"] > 0 and reg["halves"]["second"]["slope"] > 0
    assert reg["placebo"]["p_two"] > 0.05 and abs(reg["placebo"]["slope"]) < 0.02
    null = m.event_regression(dates, U, sess, closes, [0] * 150, n_boot=300)
    assert not (null["slope"]["p_two"] < 0.05 and null["slope"]["slope"] > 0)
    # the election exit offset uses the next session's close
    one = m.event_regression([sess[20]], np.array([0.2]), sess, closes, [1])
    assert one["n"] == 1 and one["returns"][0] == pytest.approx(closes[21] / closes[18] - 1)


def test_event_day_mapping_and_cutoff():
    cal = ["2024-01-31", "2024-03-20", "2024-05-01"]
    assert m._event_day("2024-03-20", cal) == "2024-03-20"
    assert m._event_day("2024-03-18", cal) == "2024-03-20"           # closes two days before the decision
    assert m._event_day("2024-03-25", cal) == "2024-03-20"           # a market end a few days after
    assert m._event_day("2024-04-15", cal) is None
    cut = m._cutoff_ts("2024-03-15")
    assert datetime.fromtimestamp(cut, ET).hour == 23 and datetime.fromtimestamp(cut, UTC).strftime("%Y-%m-%d") == "2024-03-16"


# ------------------------------------------------------------------------------------------- T-360 --

def test_implied_q_sigma_and_day_before_nowcast():
    assert m.implied_q(0.3, 0.36, 1e-9) == 1.0 and m.implied_q(0.3, 0.30, 1e-9) == 0.0 and m.implied_q(0.3, 0.35, 1e-9) == 0.5
    assert m.implied_q(0.3, 0.35, 0.1) == pytest.approx(0.5) and m.implied_q(0.3, 0.45, 0.1) > 0.8
    nc = {"2024-01": {"2024-02-09": 0.30, "2024-02-12": 0.35}, "2024-02": {"2024-03-08": 0.40, "2024-03-11": 0.42}}
    act = {"2024-01": ("2024-02-13", 0.3), "2024-02": ("2024-03-12", 0.4)}
    assert m.day_before_nowcast(nc, "2024-01", "2024-02-13") == ("2024-02-12", 0.35)
    assert m.day_before_nowcast(nc, "2024-01", "2024-02-12") == ("2024-02-09", 0.30)   # Monday release: Friday's label
    assert m.day_before_nowcast(nc, "2024-03", "2024-04-10") is None
    assert m.nowcast_sigma(nc, act, "2024-04-10", min_n=2) == pytest.approx(math.sqrt((0.05 ** 2 + 0.02 ** 2) / 2))
    assert m.nowcast_sigma(nc, act, "2024-03-12", min_n=2) is None                   # only one prior release
    assert m._prev_weekday("2024-03-11") == "2024-03-08"
    assert m.cpi_market_target("KXCPI-25MAR-T0.2") == "2025-03" and m.cpi_market_target("FEDDECISION-24JAN31") is None
    cands = [(100, 0.3, 0.34), (150, 0.4, 0.44), (200, 0.0, 1.0)]
    assert m.bar_quote(cands, 150) == (0.4, 0.44) and m.bar_quote(cands, 170) == (0.4, 0.44) and m.bar_quote(cands, 200) is None
    assert m.bar_quote(cands, 150 + 8 * 86400) is None


def cpi_world(rng, n_rel, informative, start=date(2021, 7, 13)):
    """Releases every 30 days with 5 thresholds; the true print ~ N(nowcast, 0.05) when the nowcast is informative, and
    the market asks are flat 0.5 (uninformative) in that case; the null has a calibrated market and a noise nowcast."""
    markets, candles, rel_days, nc, act = [], {}, [], {}, {}
    # prior history for sigma: 36 target months before the first release
    for j in range(36):
        tgt = (start - timedelta(days=30 * (36 - j))).strftime("%Y-%m")
        rel = (start - timedelta(days=30 * (35 - j))).isoformat()
        truth = rng.normal(0.3, 0.15)
        nc[tgt] = {m._prev_weekday(rel): truth + rng.normal(0, 0.05)}
        act[tgt] = (rel, truth)
    for i in range(n_rel):
        rel = start + timedelta(days=30 * i)
        rel_days.append(rel.isoformat())
        tgt = (rel - timedelta(days=15)).strftime("%Y-%m")
        truth = rng.normal(0.3, 0.15)
        nowc = truth + rng.normal(0, 0.05) if informative else rng.normal(0.3, 0.15)
        nc[tgt] = {m._prev_weekday(rel.isoformat()): nowc}
        act[tgt] = (rel.isoformat(), truth)
        printed = round(truth, 1)
        d1 = date.fromisoformat(m._prev_weekday(rel.isoformat()))
        bar = int(datetime(d1.year, d1.month, d1.day, 16, tzinfo=ET).timestamp())
        for k in (0.1, 0.2, 0.3, 0.4, 0.5):
            tk = f"KXCPI-{tgt[2:4]}{['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'][int(tgt[5:7]) - 1]}-T{k}"
            res = "yes" if printed > k + 1e-9 else "no"
            markets.append({"ticker": tk, "close_time": rel.isoformat() + "T12:29:00Z", "open_time": (rel - timedelta(days=20)).isoformat() + "T14:00:00Z",
                            "result": res, "floor_strike": k})
            mid = 0.5 if informative else 1 - m.norm_cdf((k + 0.05 - truth) / 0.05) * 0.0 - (m.norm_cdf((k + 0.05 - truth) / 0.08))
            mid = min(max(mid + rng.normal(0, 0.03), 0.03), 0.97)
            candles[tk] = [(bar - 5 * H, mid - 0.03, mid + 0.01), (bar, mid - 0.02, mid + 0.02)]
    return markets, candles, rel_days, nc, act


def test_cpi_trades_planted_nowcast_edge_vs_calibrated_null():
    rng = np.random.default_rng(6)
    ms, cd, rd, nc, act = cpi_world(rng, 50, True)
    res = m.cpi_trades(ms, cd, rd, nc, act, 0.10)
    assert len(res["releases"]) >= 40 and len(res["trades"]) >= 100
    assert m.release_stat(res["trades"]) > 5
    par, rb = m.parametric_null(res["trades"], 300), m.release_bootstrap(res["trades"], 300)
    assert par["p"] < 0.05 and rb["p"] < 0.05 and rb["ci"][0] > 0
    assert m.parametric_null(res["trades"], 300, comonotone=True)["p"] < 0.05
    ms, cd, rd, nc, act = cpi_world(rng, 50, False)
    null = m.cpi_trades(ms, cd, rd, nc, act, 0.10)
    if null["trades"]:
        assert not (m.parametric_null(null["trades"], 300)["p"] < 0.05 and m.release_bootstrap(null["trades"], 300).get("p", 1) < 0.05)
    fav = m.cpi_trades(ms, cd, rd, {}, {}, 0.10, rule="favourite")
    assert fav["trades"] and all(t["price"] >= 0.5 - 0.05 for t in fav["trades"])
    # a quote that fails the spread filter, an unopened market and an unresolved one are skipped and counted
    ms2 = [dict(ms[0], result="", ticker="X1"), dict(ms[0], open_time="2099-01-01T00:00:00Z", ticker="X2"), dict(ms[0], ticker="X3")]
    cd2 = {"X3": [(0, 0.0, 1.0)]}
    sk = m.cpi_trades(ms2, cd2, rd, nc, act, 0.10)["skipped"]
    assert sk == {"unresolved": 1, "not_open": 1, "no_quote": 1}


# ------------------------------------------------------------------------------------------- harnesses --

def hourly_rows(token, mid, hours, ps, month):
    return [row({"market_id": str(mid), "token": token, "p": float(p), "t": int(h * H + 3)}, iso(h * H + 3), kind="price") for h, p in zip(hours, ps)]


def candle_rows(ticker, hours, bids, asks, vols, period=60):
    return [row({"ticker": ticker, "period": period, "candle": {"end_period_ts": int(h * H), "volume": str(v), "open_interest": "1",
                                                              "price": {"close": None}, "yes_bid": {"close": f"{b:.4f}"}, "yes_ask": {"close": f"{a:.4f}"}}},
                iso(h * H), kind="candle") for h, b, a, v in zip(hours, bids, asks, vols)]


def gamma_market(mid, token, q, end, slug, outcome=1, fees=False, fee_type=None, group=None, desc=""):
    return {"id": str(mid), "question": q, "slug": slug, "endDate": end, "startDate": "2025-01-01T00:00:00Z", "outcomePrices": '["1", "0"]' if outcome == 1 else '["0", "1"]',
            "clobTokenIds": json.dumps([token, token + "n"]), "feesEnabled": fees, "feeType": fee_type, "groupItemTitle": group, "description": desc, "volumeNum": 100.0}


def dtb3_rows(days_values):
    """fred-DTB3 rows (discount yield in %, available at 20:00 UTC of the day)."""
    return [row({"day": d, "value": v}, d + "T00:00:00+00:00", d + "T20:00:00+00:00", kind="series", key="DTB3") for d, v in days_values]


def pair_bundles(rng, n_pairs=6, hours_per=360, convergent=True, k_half_spread=0.01, with_dtb3=True):
    """Pairs + hourly prices + candles + events + settled markets (+ fred-DTB3) for the T-336 / T-409 fakes."""
    pairs, pm_rows, k_rows, ev_markets, settled, vol_rows = [], [], [], [], [], []
    base = 1_735_689_600 // H                                  # 2025-01-01
    for i in range(1, n_pairs + 1):
        h0, h1 = base + i * 1000, base + i * 1000 + hours_per
        p = fomc_pair(i, h0, h1)
        pairs.append(row(p, p["frozen_at"], iso(h0 * H), kind="pair", key=p["pair_id"]))
        P, K = gap_series(rng, hours_per, convergent, n_ep=10)
        hours = np.arange(h0, h1)
        pm_rows += hourly_rows(f"tok{i}", 1000 + i, hours, P, "2025-01")
        k_rows += candle_rows(f"KXFEDDECISION-25M{i:02d}-C25", hours, K - k_half_spread, K + k_half_spread, np.full(hours.size, 2.0))
        vol_rows += [row({"market_id": str(1000 + i), "condition_id": "0x", "t": int(h * H), "n": 1, "shares": 5.0, "usd": 2.5}, iso(h * H), iso(h * H + H), kind="volume")
                     for h in range(h0 - 24, h1)]                   # volume from a day before the grid: every hour liquid
        ev_markets.append(gamma_market(1000 + i, f"tok{i}", "25 bps decrease?", iso(h1 * H), f"fed-decision-{i}", 1))
        settled.append(row({"ticker": f"KXFEDDECISION-25M{i:02d}-C25", "event_ticker": f"KXFEDDECISION-25M{i:02d}", "result": "yes", "close_time": iso(h1 * H),
                            "open_time": iso(h0 * H), "settlement_ts": iso(h1 * H + 60)}, iso(h1 * H), kind="market"))
    events = [row({"id": "e1", "slug": "fed-decision-in-january", "endDate": "2025-01-29T00:00:00Z", "markets": ev_markets}, kind="event")]
    out = {m.PAIRS_B: pairs, m.PMH + "2025-01": pm_rows, m.KH + "KXFEDDECISION": k_rows, m.EV_MACRO_B: events, m.EV_BTC_B: [],
           m.KS + "KXFEDDECISION": settled, m.PMV + "2025-01": vol_rows}
    if with_dtb3:
        out[m.DTB3_B] = dtb3_rows([("2024-12-31", 4.30), ("2025-03-03", 4.20), ("2025-06-02", 4.10), ("2025-12-01", 3.60)])
    return out


def assert_json(stat, n, verdict, reason):
    json.dumps(stat)
    assert isinstance(n, int) and verdict in ("supported", "not_supported", "inconclusive") and " — " in reason


def test_harness_t336_and_t409_on_fake_archive():
    rng = np.random.default_rng(7)
    a = FakeArchive(pair_bundles(rng, 8, 400, True), created="2099-01-01T00:00:00+00:00")
    stat, n, verdict, reason = m.b6c_pmxv_cross_venue_convergence(a)
    assert_json(stat, n, verdict, reason)
    assert n >= 50 and stat["n_audited"] == 8 and stat["halving"]["rate"] > 0.85 and stat["coverage"]["aligned"] == 8
    assert verdict in ("supported", "inconclusive", "not_supported") and "Wilson" in reason
    stat, n, verdict, reason = m.b6c_pmxv_leadlag(a)
    assert_json(stat, n, verdict, reason)
    assert stat["n_pairs_with_volume"] == 8 and n == 8 and len(stat["cells"]) == 32
    # 8 pairs are below min_n 40: the size criterion is undecided, so the verdict is inconclusive unless the follow
    # trade fails decisively (its OOS CI wholly below zero under both constructions: rule 5)
    assert stat["criteria"][1][1] is None and verdict in ("inconclusive", "not_supported")
    if verdict == "not_supported":
        assert stat["claim_cell"]["out_of_sample"]["ci"][1] < 0 and stat["claim_cell"]["out_of_sample"]["robust_ci"][1] < 0
    assert stat["frozen_at"] < stat["first_price_bundle"] and stat["criteria"][0][1] is True and "Claim cell" in reason
    # T-409 fix: the arb carry uses the DTB3 rate known at each entry hour, reported as a range
    assert "point-in-time DTB3" in reason and stat["costs"]["bill_source"].startswith(m.DTB3_B)
    arb_n = sum(v["n"] for k, v in stat["cells"].items() if "|arb|" in k)
    if arb_n:
        lo, hi = stat["costs"]["bill_rate_range"]
        assert 0.03 < lo <= hi < 0.05
    miss = m.b6c_pmxv_leadlag(FakeArchive({}))
    assert miss[2] == "inconclusive" and m.PAIRS_B in miss[0]["missing_bundles"]


# ------------------------------------------------------------------------------- regression tests (skeptic fixes) --

def test_convergence_pnl_hold_prices_the_pure_arb_variant():
    """T-336: the trial's pure-arb construction holds the entry to settlement, pays nothing to exit and charges the T-bill
    carry on the locked dollar until the later leg's close; a wide Kalshi spread makes the exit-rule construction lose
    while the held position keeps the entry edge."""
    P = np.array([0.50, 0.58, 0.58, 0.505, 0.50])
    K = np.full(5, 0.50)
    al = make_aligned(P, K, spread=0.08, hs=0.01)                # Kalshi 8-point spread (within the 10-point filter)
    al["last_close_hour"] = 5 + 24 * 10                          # the Kalshi leg settles 10 days after the grid end
    d = 100 * (P - K)
    a = m.convergence_pnl(al, 1, d, 0.0)
    b = m.convergence_pnl_hold(al, 1, d, 0.0, bill_rate=0.05)
    entry = 100 * ((0.58 - 0.01) - (0.50 + 0.04))                # +3 cents: sell PM at its bid, buy Kalshi at its ask
    fee = 100 * 0.07 * 0.25
    assert a["exit"] == "gap<1" and a["entry_edge"] == pytest.approx(entry) and a["entry_fees"] == pytest.approx(fee)
    assert a["exit_cost"] == pytest.approx(100 * ((0.505 + 0.01) - (0.50 - 0.04)) + fee)       # two spreads and the fee again
    assert a["net"] < 0 < b["net"]
    lock_h = al["last_close_hour"] - 1
    assert b["hours_held"] == lock_h and b["carry"] == pytest.approx(100 * 0.05 * lock_h / 24 / 365)
    assert b["gross"] == pytest.approx(entry - fee) and b["net"] == pytest.approx(entry - fee - b["carry"]) and b["exit"] == "settlement"
    assert b["mismatch"] is False and b["bill_rate"] == 0.05
    # a differently resolved pair pays the +/-100 mismatch; unknown outcome or unknown rate: no trade
    mm = m.convergence_pnl_hold(al, 1, d, 100.0, 0.05)
    assert mm["mismatch"] is True and mm["net"] < -90
    assert m.convergence_pnl_hold(al, 1, d, None, 0.05) is None and m.convergence_pnl_hold(al, 1, d, 0.0, None) is None
    # without last_close_hour the lock runs to the grid end
    al2 = make_aligned(P, K, spread=0.08, hs=0.01)
    assert m.convergence_pnl_hold(al2, 1, d, 0.0, 0.05)["hours_held"] == 4


def test_t336_secondary_disagreement_between_named_constructions_is_undecided():
    """T-336: judged on the exit-rule construction alone the secondary fails (not_supported); under rule 11 the two named
    constructions disagree, so the criterion is undecided and the verdict inconclusive."""
    primary = [("audit", True, False), ("halving rate > 70%", True, False), ("above the random-walk null", True, False)]
    single = primary + [("secondary: exit at |d| < 1: mean -3.98 cents > 0", False, True)]
    assert m._decide(single, 1772, 50, "episodes")[0] == "not_supported"
    rows = [("(a) exit at |d| < 1 point or resolution: mean -3.98 cents", False, True),
            ("(b) pure-arb variant held to settlement: mean +1.06 cents", True, False)]
    both = primary + [m.all_constructions(rows, "secondary: convergence-trade mean net return per episode > 0")]
    verdict, why = m._decide(both, 1772, 50, "episodes")
    assert verdict == "inconclusive" and "the named constructions disagree: undecided under rule 11" in why
    agree = primary + [m.all_constructions([(rows[0][0], False, True), (rows[1][0], False, True)], "secondary")]
    assert m._decide(agree, 1772, 50, "episodes")[0] == "not_supported"


def test_harness_t336_wide_kalshi_spread_constructions_disagree_on_fake_archive():
    """T-336 harness regression: with a 6-point Kalshi spread the exit rule pays two spreads on every episode and loses,
    while the same entries held to settlement keep a positive edge, so the secondary is undecided and the verdict
    inconclusive, not not_supported; the carry is priced at the DTB3 rate known at each entry."""
    rng = np.random.default_rng(11)
    a = FakeArchive(pair_bundles(rng, 10, 480, True, k_half_spread=0.03), created="2099-01-01T00:00:00+00:00")
    stat, n, verdict, reason = m.b6c_pmxv_cross_venue_convergence(a)
    assert_json(stat, n, verdict, reason)
    ct = stat["convergence_trade"]
    assert n >= 50 and ct["n"] > 20 and ct["hold_to_settlement"]["n"] == ct["n"]
    assert ct["exit_rule"]["mean"] < 0 < ct["hold_to_settlement"]["mean"] and ct["constructions_agree"] is False
    assert ct["exit_rule"]["exit_leg_cost_mean"] > 5.0                     # two spreads (1 + 3 cents) and the fee again
    assert ct["hold_to_settlement"]["carry_cents_mean"] > 0 and 0.03 < ct["hold_to_settlement"]["bill_rate_range"][0] <= ct["hold_to_settlement"]["bill_rate_range"][1] < 0.05
    sec = [c for c in stat["criteria"] if c[0].startswith("secondary")][0]
    assert sec[1] is None and "undecided under rule 11" in sec[0] and "converges with certainty at settlement" in sec[0]
    assert all(c[1] is True for c in stat["criteria"] if not c[0].startswith("secondary"))
    assert verdict == "inconclusive" and "pure-arb variant" in reason
    # without fred-DTB3 the carry is unknown: construction (b) does not resolve and names the bundle
    a2 = FakeArchive(pair_bundles(np.random.default_rng(11), 10, 480, True, k_half_spread=0.03, with_dtb3=False))
    stat2, n2, verdict2, reason2 = m.b6c_pmxv_cross_venue_convergence(a2)
    sec2 = [c for c in stat2["criteria"] if c[0].startswith("secondary")][0]
    assert sec2[1] is None and m.DTB3_B in sec2[0] and "not every named construction resolves" in sec2[0] and verdict2 == "inconclusive"


def test_bill_curve_and_arb_trades_point_in_time_rate():
    """T-409: the arb carry uses the DTB3 rate available at the entry hour, not the latest archived value."""
    a = FakeArchive({m.DTB3_B: dtb3_rows([("2025-01-02", 4.30), ("2025-06-02", 4.00)])})
    curve = m._bill_curve(a)
    r1 = -math.log(1 - 0.043 * 91 / 360) / (91 / 365)
    r2 = -math.log(1 - 0.040 * 91 / 360) / (91 / 365)
    jan3 = int(datetime(2025, 1, 3, tzinfo=UTC).timestamp())
    jul1 = int(datetime(2025, 7, 1, tzinfo=UTC).timestamp())
    assert m.bill_rate_at(curve, jan3) == pytest.approx(r1) and m.bill_rate_at(curve, jul1) == pytest.approx(r2)
    assert m.bill_rate_at(curve, int(datetime(2025, 1, 2, 19, tzinfo=UTC).timestamp())) is None     # before 20:00 UTC of the first day
    assert m.bill_rate_at(None, jul1) is None and m._bill_curve(FakeArchive({})) is None
    P = np.array([0.50, 0.50, 0.40, 0.40])
    K = np.array([0.50, 0.50, 0.50, 0.50])
    for h0, rate in ((jan3 // H, r1), (jul1 // H, r2)):
        al = make_aligned(P, K, spread=0.02, hs=0.01, d_res=0.0)
        al["hours"] = np.arange(h0, h0 + 4)
        al["last_close_hour"] = h0 + 4 + 48
        tr = m.arb_trades(al, 3.0, lambda ts: m.bill_rate_at(curve, ts))
        assert len(tr) == 1 and tr[0]["bill_rate"] == pytest.approx(rate) and tr[0]["exit_hours"] == 50
        assert tr[0]["carry"] == pytest.approx(100 * rate * 50 / 24 / 365)
        edge = 100 * (0.49 - 0.41) - 100 * (0.07 * 0.25)
        assert tr[0]["net"] == pytest.approx(edge - tr[0]["carry"])
    const = m.arb_trades(make_aligned(P, K, spread=0.02, hs=0.01, d_res=0.0), 3.0, 0.04)[0]
    assert const["bill_rate"] == 0.04 and const["carry"] == pytest.approx(100 * 0.04 * (2 / 24) / 365)


def test_smile_book_uses_a_point_in_time_forward():
    """T-337: the smile is placed relative to the forward known at H (spot close of the bar ending at H, else the latest
    Deribit trade index before H), not the two-hour mean index; the staleness of the mean index is recorded."""
    e1 = "2023-11-16"
    ets = {e1: int(datetime(2023, 11, 16, 8, tzinfo=UTC).timestamp())}
    H0 = ets[e1] // H - 30
    t_res = ets[e1] - 6 * H
    tau = (t_res - H0 * H) / m.YEAR_S
    F_avg, F_spot = 100000.0, 100500.0
    groups = synthetic_groups(range(H0 - 3, H0 + 2), [e1], F=F_avg)
    stale = m.SmileBook(groups, ets)
    fresh = m.SmileBook(groups, ets, forward={H0: F_spot})
    last = m.SmileBook(groups, ets, last_idx={H0 - 1: (H0 * H * 1000 - 500, F_spot)})
    for K in (100000.0, 100500.0, 101500.0):
        d2_fresh = -math.log(K / F_spot) / (0.5 * math.sqrt(tau)) - 0.5 * math.sqrt(tau) / 2
        d2_stale = -math.log(K / F_avg) / (0.5 * math.sqrt(tau)) - 0.5 * math.sqrt(tau) / 2
        assert fresh.p_rn(H0, K, t_res)["svi"] == pytest.approx(m.norm_cdf(d2_fresh), abs=1e-3)
        assert last.p_rn(H0, K, t_res)["svi"] == pytest.approx(m.norm_cdf(d2_fresh), abs=1e-3)
        assert stale.p_rn(H0, K, t_res)["svi"] == pytest.approx(m.norm_cdf(d2_stale), abs=1e-3)
    assert fresh.p_rn(H0, 100500.0, t_res)["svi"] > stale.p_rn(H0, 100500.0, t_res)["svi"] + 0.04      # a 0.5% spot move shifts N(d2) by points
    assert fresh.p_rn(H0, 100500.0, t_res)["F"] == F_spot and stale.p_rn(H0, 100500.0, t_res)["F"] == F_avg
    assert fresh.fwd_source == {"spot": 1} and last.fwd_source == {"deribit_last_trade": 1} and stale.fwd_source == {"mean_index": 1}
    assert fresh.staleness()["abs_ln_pct_quantiles"]["0.5"] == pytest.approx(100 * abs(math.log(F_avg / F_spot)), abs=1e-6)
    assert stale.staleness()["abs_ln_pct_quantiles"]["0.9"] == 0.0
    # the spot of a later hour is not used at H (only forward[H]); a trade in hour H itself is not used either
    only_later = m.SmileBook(groups, ets, forward={H0 + 1: F_spot}, last_idx={H0: (H0 * H * 1000 + 5, F_spot)})
    assert only_later.p_rn(H0, 100500.0, t_res)["F"] == F_avg and only_later.fwd_source == {"mean_index": 1}


def test_hourly_spot_and_deribit_last_index_are_point_in_time():
    t0 = 1_729_036_800                                        # 2024-10-16 00:00 UTC bar start
    rows = [row({"symbol": "BTC-USD", "t": t0 + i * H, "close": 60000.0 + i}, iso(t0 + i * H), iso(t0 + (i + 1) * H), kind="bar1h") for i in range(3)]
    rows.append(row({"symbol": "BTC-USD", "t": t0 + 3 * H + 1500, "close": 70000.0}, iso(t0 + 3 * H + 1500), iso(t0 + 4 * H + 1500), kind="bar1h"))
    spot = m._hourly_spot(FakeArchive({m.HBTC_B: rows}))
    assert spot == {t0 // H + 1: 60000.0, t0 // H + 2: 60001.0, t0 // H + 3: 60002.0}       # the partial bar stamped after its hour is dropped
    assert m._hourly_spot(FakeArchive({})) == {}
    drb = []
    for h, F in ((100, 50000.0), (100, 50100.0), (101, 50200.0)):
        for K in (49000.0, 50000.0):
            drb.append(row({"timestamp": h * H * 1000 + (10 if F == 50000.0 else 2000), "iv": 50.0, "index_price": F, "expiry": "2024-01-05", "strike": K}, kind="option-trade"))
    groups, ets, n, last_idx = m._deribit_groups(FakeArchive({m.DRB + "2024-01": drb}), ["2024-01"])
    assert n == 6 and last_idx == {100: (100 * H * 1000 + 2000, 50100.0), 101: (101 * H * 1000 + 2000, 50200.0)}
    assert groups[(100, "2024-01-05")]["F"] == [2 * 50000.0 + 2 * 50100.0, 4]


def test_harness_t337_forward_from_hourly_spot_on_fake_archive():
    """T-337 harness regression: with hourly-BTC-USD archived the forward at H is the bar close (point in time) and the
    staleness of the two-hour mean index is reported; without it the latest Deribit trade index stands in."""
    rng = np.random.default_rng(12)
    ets = {"2025-03-07": int(datetime(2025, 3, 7, 8, tzinfo=UTC).timestamp()), "2025-03-08": int(datetime(2025, 3, 8, 8, tzinfo=UTC).timestamp())}
    H0 = ets["2025-03-07"] // H - 40
    hours = np.arange(H0, H0 + 30)
    F, F_spot = 100000.0, 100200.0
    drb = []
    for h in range(H0 - 3, H0 + 31):
        for e in ets:
            for K in (94000, 96000, 98000, 99000, 100000, 101000, 102000, 104000, 106000):
                drb.append(row({"trade_id": f"{h}{K}", "timestamp": int(h * H * 1000 + 1000), "iv": 50.0, "index_price": F, "expiry": e, "strike": float(K)}, kind="option-trade"))
    spot_rows = [row({"symbol": "BTC-USD", "t": int((h - 1) * H), "close": F_spot}, iso((h - 1) * H), iso(h * H), kind="bar1h") for h in range(H0 - 3, H0 + 31)]
    markets, pm_rows = [], []
    t_res = ets["2025-03-07"] + 12 * H
    for i in range(30):
        tok = f"b{i}"
        ps = np.clip(0.5 + 0.12 + rng.normal(0, 0.005, hours.size), 0.02, 0.98)
        pm_rows += hourly_rows(tok, 9000 + i, hours, ps, "2025-03")
        markets.append(gamma_market(9000 + i, tok, "Will the price of Bitcoin be above $100,000 on March 7?", iso(t_res), "bitcoin-above-on-march-7-2025", outcome=int(rng.random() < 0.5),
                                    fees=True, fee_type="crypto_fees_v2", group="100,000", desc='BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title'))
    ev = [row({"id": "ev", "slug": "bitcoin-above-on-march-7-2025", "endDate": iso(t_res), "markets": markets, "description": ""}, kind="event")]
    base = {m.EV_BTC_B: ev, m.EV_MACRO_B: [], m.PMH + "2025-03": pm_rows, m.DRB + "2025-03": drb}
    stat, n, verdict, reason = m.b6c_pmxv_pm_vs_deribit_digital(FakeArchive(dict(base, **{m.HBTC_B: spot_rows})))
    assert_json(stat, n, verdict, reason)
    fw = stat["forward"]
    assert fw["spot_bundle"] == m.HBTC_B and fw["sources"] == {"spot": stat["deribit"]["fits"]} and fw["spot_hours"] == 34
    assert fw["staleness_of_two_hour_mean_index"]["abs_ln_pct_quantiles"]["0.5"] == pytest.approx(100 * abs(math.log(F / F_spot)), abs=1e-6)
    assert "hourly-BTC-USD close of the bar ending at H" in reason and n >= 30
    stat2, n2, verdict2, reason2 = m.b6c_pmxv_pm_vs_deribit_digital(FakeArchive(base))
    fw2 = stat2["forward"]
    assert fw2["spot_bundle"] is None and set(fw2["sources"]) == {"deribit_last_trade"} and fw2["staleness_of_two_hour_mean_index"]["abs_ln_pct_quantiles"]["0.99"] == 0.0
    # the fresh forward sits 0.2% above the stale mean index, so p_RN is higher and the NO fades are entered at a smaller gap
    assert stat["fits"]["svi"]["mean"] is not None and stat2["fits"]["svi"]["mean"] is not None


def test_cpi_trades_entry_threshold_as_worded_fee_in_pnl_only():
    """T-360: the claim enters when the nowcast-implied probability exceeds the ask by more than 10 pp; the fee is charged in
    the P&L, not added to the threshold (the fee-inclusive threshold is a variant that drops the marginal trades)."""
    rel = "2024-03-12"
    d1 = date.fromisoformat(m._prev_weekday(rel))
    bar = int(datetime(d1.year, d1.month, d1.day, 16, tzinfo=ET).timestamp())
    nc = {"2024-02": {m._prev_weekday(rel): 0.40}}
    act = {f"2010-{i:02d}": (f"2010-{i:02d}-15", 0.3) for i in range(1, 13)}
    for tgt in list(act):
        nc[tgt] = {m._prev_weekday(act[tgt][0]): 0.3}
    act.update({f"2011-{i:02d}": (f"2011-{i:02d}-15", 0.3) for i in range(1, 13)})
    for tgt in [k for k in act if k.startswith("2011")]:
        nc[tgt] = {m._prev_weekday(act[tgt][0]): 0.3 + (0.1 if int(tgt[5:]) % 2 else -0.1)}
    sigma = m.nowcast_sigma(nc, act, rel, min_n=24)
    assert sigma == pytest.approx(math.sqrt(0.01 * 12 / 24))
    q = m.implied_q(0.3, 0.40, sigma)                              # P(print > 0.3) given N = 0.40
    ask = round(q - 0.105, 4)                                       # the edge is 10.5 pp: above 10 pp, below 10 pp + fee
    fee = m.KALSHI_FEE * ask * (1 - ask)
    assert 0.10 < q - ask < 0.10 + fee
    mk = [{"ticker": "KXCPI-24FEB-T0.3", "close_time": rel + "T12:29:00Z", "open_time": "2024-02-20T14:00:00Z", "result": "yes", "floor_strike": 0.3}]
    cd = {"KXCPI-24FEB-T0.3": [(bar, ask - 0.02, ask)]}
    worded = m.cpi_trades(mk, cd, [rel], nc, act, 0.10)
    assert len(worded["trades"]) == 1 and worded["trades"][0]["side"] == "yes" and worded["trades"][0]["price"] == ask
    assert worded["trades"][0]["net_cents"] == pytest.approx(100 * (1 - ask - fee))                    # the fee stays in the P&L
    assert m.cpi_trades(mk, cd, [rel], nc, act, 0.10, fee_in_threshold=True)["trades"] == []
    cd_small = {"KXCPI-24FEB-T0.3": [(bar, q - 0.11, q - 0.09)]}                                       # edge 9 pp: no trade either way
    assert m.cpi_trades(mk, cd_small, [rel], nc, act, 0.10)["trades"] == []
    # the NO side mirrors the rule
    mk_no = [dict(mk[0], result="no", floor_strike=0.6, ticker="KXCPI-24FEB-T0.6")]
    q_no = 1 - m.implied_q(0.6, 0.40, sigma)
    bid_no = round(1 - (q_no - 0.105), 4)                           # no_ask = 1 - bid
    tr_no = m.cpi_trades(mk_no, {"KXCPI-24FEB-T0.6": [(bar, bid_no, bid_no + 0.02)]}, [rel], nc, act, 0.10)["trades"]
    assert len(tr_no) == 1 and tr_no[0]["side"] == "no" and tr_no[0]["win"] is True
    assert m.cpi_trades(mk_no, {"KXCPI-24FEB-T0.6": [(bar, bid_no, bid_no + 0.02)]}, [rel], nc, act, 0.10, fee_in_threshold=True)["trades"] == []


def test_harness_t337_on_fake_archive():
    rng = np.random.default_rng(8)
    ets = {"2025-03-07": int(datetime(2025, 3, 7, 8, tzinfo=UTC).timestamp()), "2025-03-08": int(datetime(2025, 3, 8, 8, tzinfo=UTC).timestamp())}
    H0 = ets["2025-03-07"] // H - 40
    hours = np.arange(H0, H0 + 30)
    F = 100000.0
    drb = []
    for h in range(H0 - 3, H0 + 31):
        for e, ets_ in ets.items():
            for K in (94000, 96000, 98000, 99000, 100000, 101000, 102000, 104000, 106000):
                drb.append(row({"trade_id": f"{h}{K}", "timestamp": int(h * H * 1000 + 1000), "instrument_name": "x", "price": 0.01, "mark_price": 0.01, "iv": 50.0,
                                "index_price": F, "amount": 0.1, "direction": "buy", "currency": "BTC", "expiry": e, "strike": float(K), "type": "call"}, kind="option-trade"))
    markets, pm_rows = [], []
    for i in range(40):
        tok = f"b{i}"
        t_res = ets["2025-03-07"] + 12 * H                       # noon-ish between the two expiries
        ps = np.clip(0.5 + 0.10 + rng.normal(0, 0.005, hours.size), 0.02, 0.98)   # Polymarket 10 points above the fair 0.5
        pm_rows += hourly_rows(tok, 9000 + i, hours, ps, "2025-03")
        markets.append(gamma_market(9000 + i, tok, "Will the price of Bitcoin be above $100,000 on March 7?", iso(t_res), "bitcoin-above-on-march-7-2025", outcome=int(rng.random() < 0.5),
                                    fees=True, fee_type="crypto_fees_v2", group="100,000", desc='BTC/USDT 12:00 in the ET timezone (noon) on the date specified in the title'))
    ev = [row({"id": "ev", "slug": "bitcoin-above-on-march-7-2025", "endDate": iso(t_res), "markets": markets, "description": ""}, kind="event")]
    a = FakeArchive({m.EV_BTC_B: ev, m.EV_MACRO_B: [], m.PMH + "2025-03": pm_rows, m.DRB + "2025-03": drb})
    stat, n, verdict, reason = m.b6c_pmxv_pm_vs_deribit_digital(a)
    assert_json(stat, n, verdict, reason)
    assert n >= 40 and stat["fits"]["svi"]["n"] == stat["fits"]["cubic"]["n"] and stat["n_markets"] == 40
    assert verdict == "inconclusive" and "Binance klines are not archived" in reason
    assert stat["forward"]["sources"] == {"deribit_last_trade": stat["deribit"]["fits"]} and "latest Deribit trade index before H" in reason
    assert stat["fits"]["svi"]["mean"] is not None and stat["fits"]["svi"]["by_side"] == {"no": n}
    miss = m.b6c_pmxv_pm_vs_deribit_digital(FakeArchive({m.EV_BTC_B: ev}))
    assert miss[2] == "inconclusive" and any(x.startswith(m.DRB) for x in miss[0]["missing_bundles"])


def daily_rows(days, closes):
    return [row({"t": int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()), "close": float(c), "adjclose": float(c), "open": float(c), "volume": 1}, d + "T00:00:00+00:00", kind="bar")
            for d, c in zip(days, closes)]


def test_harness_t358_on_fake_archive():
    rng = np.random.default_rng(9)
    sess = sessions_from("2021-01-04", 1400)
    closes = 100 * np.cumprod(1 + rng.normal(0, 0.004, len(sess)))
    cpi_days = [sess[i] for i in range(130, len(sess) - 3, 21)]
    fomc_days = [sess[i] for i in range(140, len(sess) - 3, 31)]
    U_true = {}
    settled, cands = [], []
    for fam, days, series in (("cpi", cpi_days, "KXCPI"), ("fomc", fomc_days, "KXFEDDECISION")):
        for j, d in enumerate(days):
            i = sess.index(d)
            p = rng.uniform(0.1, 0.9)
            U_true[d] = p * (1 - p)
            closes[i:] *= 1 + 0.08 * U_true[d]                    # planted premium into the event
            tk = f"{series}-{j}-X"
            settled.append(row({"ticker": tk, "event_ticker": f"{series}-{j}", "result": "yes", "close_time": d + "T12:29:00Z", "open_time": sess[i - 20] + "T14:00:00Z"}, kind="market"))
            for back in (5, 4, 3):
                dd = date.fromisoformat(sess[i - back]) + timedelta(days=1)
                end = int(datetime(dd.year, dd.month, dd.day, 0, 0, tzinfo=ET).timestamp())
                cands.append(row({"ticker": tk, "period": 1440, "candle": {"end_period_ts": end, "volume": "1", "yes_bid": {"close": f"{p - 0.01:.4f}"}, "yes_ask": {"close": f"{p + 0.01:.4f}"}}}, kind="candle"))
    bundles = {m.SPY_B: daily_rows(sess, closes), m.FOMC_B: [row({"decision_day": d, "scheduled": True, "future": False}) for d in fomc_days],
               m.CPI_REL_B: [row({"day": d, "series": "CPIAUCSL", "release": "cpi"}) for d in cpi_days],
               m.EMP_REL_B: [row({"day": sess[i], "series": "PAYEMS", "release": "employment"}) for i in range(135, len(sess) - 3, 21)],
               m.KS + "KXCPI": [r for r in settled if "KXCPI" in r["value"]["ticker"]], m.KD + "KXCPI": [r for r in cands if "KXCPI" in r["value"]["ticker"]],
               m.KS + "KXFEDDECISION": [r for r in settled if "FEDDEC" in r["value"]["ticker"]], m.KD + "KXFEDDECISION": [r for r in cands if "FEDDEC" in r["value"]["ticker"]]}
    stat, n, verdict, reason = m.b6c_pmxv_event_uncertainty_premium(FakeArchive(bundles))
    assert_json(stat, n, verdict, reason)
    assert n == len(set(cpi_days) | set(fomc_days)) and stat["primary"]["slope"]["slope"] > 0.03 and stat["primary"]["slope"]["p_two"] < 0.05
    assert verdict == "supported" and stat["families"] == {"cpi": len(cpi_days), "fomc": len(fomc_days)}
    miss = m.b6c_pmxv_event_uncertainty_premium(FakeArchive({m.SPY_B: []}))
    assert miss[2] == "inconclusive" and m.FOMC_B in miss[0]["missing_bundles"]


def test_harness_t360_on_fake_archive():
    rng = np.random.default_rng(10)
    ms, cd, rd, nc, act = cpi_world(rng, 50, True)
    cle = []
    for tgt, labels in nc.items():
        for l, v in labels.items():
            cle.append(row({"file": "month", "target": tgt, "label_date": l, "series": "CPI Inflation", "measure": "mom", "value": v}, kind="nowcast"))
    for tgt, (l, v) in act.items():
        cle.append(row({"file": "month", "target": tgt, "label_date": l, "series": "Actual CPI Inflation", "measure": "mom", "value": v}, kind="actual"))
    settled = [row(dict(x, event_ticker=x["ticker"].rsplit("-", 1)[0]), kind="market") for x in ms]
    cands = [row({"ticker": tk, "period": 60, "candle": {"end_period_ts": e, "volume": "1", "yes_bid": {"close_dollars": f"{b:.4f}"}, "yes_ask": {"close_dollars": f"{a:.4f}"}}}, kind="candle")
             for tk, lst in cd.items() for e, b, a in lst]
    rel = [row({"day": d, "series": "CPIAUCSL", "release": "cpi", "days_since_previous": 30}) for d in rd]
    a = FakeArchive({m.CLE_B: cle, m.CPI_REL_B: rel, m.KS + "KXCPI": settled, m.KH + "KXCPI": cands})
    stat, n, verdict, reason = m.b6c_pmxv_kalshi_cpi_nowcast(a)
    assert_json(stat, n, verdict, reason)
    assert n >= 40 and stat["tests"]["headline_edge10"]["mean"] > 0 and stat["tests"]["headline_edge10"]["p_max"] < 0.05
    assert verdict == "inconclusive" and "vintage" in reason and stat["criteria"][-1][1] is None
    assert all(c[1] for c in stat["criteria"][:-1])
    # T-360 fix: the entry threshold is the claim's 10 pp with the fee in the P&L; the fee-inclusive threshold is a variant
    assert "as worded" in reason and stat["entry_rule"].startswith("q - ask > 0.10")
    assert stat["fee_in_threshold_variant"]["n_trades"] <= stat["n_trades"] and stat["fee_in_threshold_variant"]["mean"] is not None
    miss = m.b6c_pmxv_kalshi_cpi_nowcast(FakeArchive({m.CLE_B: cle}))
    assert miss[2] == "inconclusive" and m.KS + "KXCPI" in miss[0]["missing_bundles"]


def test_maps_and_helpers():
    assert set(m.THEORY_MAP) == {"T-336", "T-409", "T-337", "T-358", "T-360"}
    assert all(v in m.HARNESSES for v in m.THEORY_MAP.values()) and all(k.startswith("b6c_pmxv_") for k in m.HARNESSES)
    assert m.kalshi_quote({"yes_bid": {"close": "0.30"}, "yes_ask": {"close_dollars": "0.34"}, "volume_fp": "7"}) == (0.30, 0.34, 7.0)
    assert m.pm_fee_rate({"feesEnabled": True, "feeType": "crypto_fees_v2"}) == 0.07 and m.pm_fee_rate({"feesEnabled": False}) == 0.0
    assert m.pm_fee_rate({"feesEnabled": True, "feeType": "economics_fees"}) == 0.05
    books = [row({"books": {"yes": {"bids": [{"price": "0.40"}, {"price": "0.39"}], "asks": [{"price": "0.44"}]}}}) for _ in range(12)]
    hs, src = m.pm_half_spread(FakeArchive({m.BOOKS_B: books}))
    assert hs == pytest.approx(0.02) and "median" in src
    assert m.pm_half_spread(FakeArchive({}))[0] == m.PM_HALF_SPREAD_DEFAULT
    assert m._outcome_of_market({"outcomePrices": '["1", "0"]'}) == 1 and m._outcome_of_market({"outcomePrices": '["0", "1"]'}) == 0
