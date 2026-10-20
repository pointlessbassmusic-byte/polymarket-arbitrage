"""Batch-6c kraken harnesses (T-331 cross-venue gap, T-425 inventory arbitrage, T-459 flow imbalance, T-465 VPIN
volatility) on synthetic data only: for every core function a planted effect passes and a null does not; the month
discovery, the partial-window cap (missing months named, never an error), the exact tick-based staleness shift and the
Coinbase candle-floor direction, the one-position-at-a-time rule, the maker fill rule (a print through the quote), the
pro-rata VPIN buckets and the walk-forward DM test are checked directly; every harness runs JSON-safe on a fake archive
and missing bundles give inconclusive. No archive, no network."""

import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_kraken as m

UTC = timezone.utc
M1, M2 = "2024-03", "2024-04"            # the synthetic months (both windows are patched onto them)


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    monkeypatch.setattr(m, "WIN", {k: (M1, M2) for k in m.WIN})
    monkeypatch.setattr(m, "MIN_N", {"T-331": 500, "T-425": 20_000, "T-459": 50, "T-465": 400})
    monkeypatch.setattr(m, "T459_OOS_FIRST", M2)
    monkeypatch.setattr(m, "BURN_IN_HOURS", 24 * 10)
    monkeypatch.setattr(m, "ADV_MIN_DAYS", 5)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2026-10-16T12:00:00+00:00"):
        self.bundles = bundles
        self.created = created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created, name=name, kind="data", tags=["complete"])

    def load(self, name):
        return iter(self.bundles[name])

    def entries(self, kind=None, tag=None):
        return [SimpleNamespace(name=n, kind="data", created_at=self.created) for n in sorted(self.bundles)]


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def month_s(month):
    return m._month_start_s(month)


def dtb3_rows(first="2023-12-01", n_days=200, rate=5.0):
    from datetime import date, timedelta
    d0 = date.fromisoformat(first)
    out = []
    for k in range(n_days):
        d = (d0 + timedelta(days=k)).isoformat()
        out.append({"source": "fred", "kind": "series", "key": "DTB3", "observed_at": d + "T00:00:00+00:00",
                    "available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": rate}})
    return out


# ------------------------------------------------------------------------------------------------ generators --

def world(months, seed=0, sigma=0.0002, gap=None, flow_drift=0.0, flow_spike=2.5, print_through=0.002,
          vpin_c=0.0, imb_block_hours=6, imb_level=0.9, n_ticks=5, no_ticks=False, tick_mode="flat"):
    """Synthetic Coinbase candles and Kraken signed-volume bars for whole months.

    ``gap``: callable(minute index within the run, rng) -> ln(P_cb / P_kr) per minute (None = 0).
    ``tick_mode``: 'flat' = every HH:59 trade prints at the minute's close (a gap at the mark is a true gap); 'jump' =
    the earlier trades print at the previous minute's close and only the last trade carries the close (a gap at the
    mark is a last-second move, which the staleness simulation must explain).
    ``flow_drift``: planted T-459 effect, per-minute log drift in minutes t+1..t+5 after a minute whose standardized
    5-minute imbalance sum exceeds ``flow_spike`` (the imbalance noise is iid N(0, 1) per minute; with ``imb_level`` 0
    the 5-minute z-score the harness computes is that sum).
    ``vpin_c``: planted T-465 effect, per-minute vol = sigma (1 + vpin_c x trailing-day mean |imbalance|) where the
    imbalance level alternates in iid blocks of ``imb_block_hours`` between 0 and ``imb_level``.
    ``print_through``: sells print this far below the close and buys this far above it in every minute."""
    rng = np.random.default_rng(seed)
    t0 = month_s(months[0])
    t1 = month_s(m._next_month(months[-1]))
    n = (t1 - t0) // 60
    # imbalance level per minute: blocks of imb_block_hours hours
    nb = n // (60 * imb_block_hours) + 1
    lev = rng.choice([0.0, imb_level], nb)
    level = np.repeat(lev, 60 * imb_block_hours)[:n]
    noise = rng.normal(0, 1, n)
    imb_signed = np.clip(level * np.where(rng.random(n) < 0.5, 1, -1) * 0.0 + 0.5 * noise, -0.95, 0.95)  # mean-zero noise
    # per-bucket imbalance magnitude is driven by |level|: deterministic one-sided flow within a block
    side_sign = np.repeat(rng.choice([-1.0, 1.0], nb), 60 * imb_block_hours)[:n]
    imb = np.clip(level * side_sign + 0.3 * noise, -0.98, 0.98)
    vol_m = np.full(n, 2.0) * rng.lognormal(0, 0.3, n)                 # BTC per minute
    buy = vol_m * (1 + imb) / 2
    sell = vol_m - buy
    # trailing-day mean |imbalance| (the VPIN-like quantity) drives vol when vpin_c > 0
    c1 = np.concatenate([[0.0], np.cumsum(np.abs(imb))])
    t = np.arange(n)
    lo = np.maximum(t - 1440, 0)
    tday = (c1[t] - c1[lo]) / np.maximum(t - lo, 1)
    sig = sigma * (1 + vpin_c * tday)
    r = rng.normal(0, 1, n) * sig
    if flow_drift:
        s5 = np.convolve(noise, np.ones(5), "full")[:n] / math.sqrt(5)      # the standardized 5-minute imbalance sum
        spike = s5 > flow_spike
        for k in range(1, 6):
            r[k:] += flow_drift * spike[:-k]
    logp = 10.5 + np.cumsum(r)
    p_cb = np.exp(logp)
    g = np.zeros(n) if gap is None else gap(n, rng)
    p_kr = p_cb * np.exp(-g)
    kr_rows, cb_rows = [], []
    for i in range(n):
        ts = t0 + 60 * i
        o = p_cb[i - 1] if i else p_cb[i]
        cb_rows.append({"source": "coinbase", "kind": "bar1m", "key": "BTC-USD", "observed_at": _iso(ts), "available_at": _iso(ts + 60),
                        "value": {"symbol": "BTC-USD", "t": ts, "open": float(o), "high": float(max(o, p_cb[i])), "low": float(min(o, p_cb[i])),
                                  "close": float(p_cb[i]), "volume": float(vol_m[i] * 3)}})
        c = float(p_kr[i])
        v = {"symbol": "XBTUSD", "t": ts, "open": float(p_kr[i - 1] if i else c), "high": c * (1 + print_through), "low": c * (1 - print_through),
             "close": c, "volume": float(vol_m[i]), "vwap": c, "n": 10, "buy_vol": float(buy[i]), "sell_vol": float(sell[i]), "n_buy": 5, "n_sell": 5,
             "buy_hi": c * (1 + print_through), "buy_lo": c, "sell_hi": c, "sell_lo": c * (1 - print_through), "mkt_vol": float(vol_m[i] / 2),
             "first_ts": ts + 1.0, "last_ts": ts + 59.0, "last_id": 1000 + i}
        if (i % 60) == 59 and not no_ticks:
            times = ts + np.linspace(5, 59, n_ticks)
            early = c if tick_mode == "flat" else float(p_kr[i - 1])
            v["ticks"] = [[float(tt), c if q == n_ticks - 1 else early, 0.01, "b" if q % 2 else "s", "l", 1000 * i + q]
                          for q, tt in enumerate(times)]
        kr_rows.append({"source": "kraken", "kind": "bar1m", "key": "XBTUSD", "observed_at": _iso(ts), "available_at": _iso(ts + 60), "value": v})
    bundles = {}
    for mo in months:
        a, b = (month_s(mo) - t0) // 60, (month_s(m._next_month(mo)) - t0) // 60
        bundles[m.KR_PREFIX + mo] = kr_rows[a:b]
        bundles[m.CB_PREFIX + mo] = cb_rows[a:b]
    bundles[m.DTB3_B] = dtb3_rows()
    return bundles


def hourly_gap(share=0.02, size=0.012):
    """A gap of ``size`` during the HH:59 minute of a random ``share`` of hours (the mark sees it), zero otherwise."""
    def fn(n, rng):
        g = np.zeros(n)
        hours = np.arange(59, n, 60)
        pick = hours[rng.random(hours.size) < share]
        g[pick] = size * rng.choice([-1.0, 1.0], pick.size)
        return g
    return fn


def arb_gap(share=0.01, size=0.04, persist=2):
    """A gap of ``size`` that opens at a random minute, persists ``persist`` more minutes and closes."""
    def fn(n, rng):
        g = np.zeros(n)
        starts = np.flatnonzero(rng.random(n) < share)
        for s in starts:
            g[s:s + persist + 1] = size
        return g
    return fn


# ------------------------------------------------------------------------------------------------- helpers --

def test_months_and_text_helpers():
    assert m._months("2022-11", "2023-02") == ["2022-11", "2022-12", "2023-01", "2023-02"]
    assert m._months_txt(["2024-06", "2024-07", "2024-08", "2025-01"]) == "2024-06..2024-08, 2025-01"
    assert m._months_txt([]) == "none"
    fake = FakeArchive({m.KR_PREFIX + "2024-03": [], m.KR_PREFIX + "2024-05": []})
    assert m.stored_months(fake, m.KR_PREFIX, m._months("2024-03", "2024-06")) == ["2024-03", "2024-05"]
    cov = m._coverage(fake, "T-459", need_cb=False)
    assert cov["missing"] == ["2024-04"]


def test_roll_prior_and_next_finite():
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    mu, sd = m._roll_prior(x, 3, 2)
    assert np.isnan(mu[0]) and np.isnan(mu[1]) and abs(mu[2] - 1.5) < 1e-12 and abs(mu[4] - 3.0) < 1e-12
    nf = m._next_finite(x, 5)
    assert list(nf) == [0, 1, 3, 3, 4, 5]
    pf = m._prev_finite(x, 5)
    assert list(pf) == [0, 1, 1, 3, 4, 5]
    assert m._next_finite(np.array([np.nan] * 3 + [1.0]), 1).tolist() == [-1, -1, 3, 3]


def test_judge_caps_partial_windows_and_keeps_decisive_failures():
    v, why = m._judge([("c", False, False)], 1000, 500, "u", ["2024-05"], "w")
    assert v == "inconclusive" and "partial window" in why and "2024-05" in why
    v, _ = m._judge([("c", False, True)], 1000, 500, "u", ["2024-05"], "w")
    assert v == "not_supported"
    v, why = m._judge([("c", False, False)], 100, 500, "u", [], "w")
    assert v == "inconclusive" and "below min_n" in why
    v, _ = m._judge([("c", True, False)], 1000, 500, "u", [], "w")
    assert v == "supported"
    v, _ = m._judge([("c", True, False)], 1000, 500, "u", ["2024-05"], "w")
    assert v == "inconclusive"


# -------------------------------------------------------------------------------------------- grid loading --

def test_grid_loads_both_venues_and_ticks_point_in_time():
    b = world([M1])
    fake = FakeArchive(b)
    g = m.grid(fake, [M1], [M1])
    n = (month_s(M2) - month_s(M1)) // 60
    assert g["N"] == n and g["rows"] == {"kraken": n, "coinbase": n}
    assert np.isfinite(g["kr_close"]).all() and np.isfinite(g["cb_close"]).all()
    assert g["marks_with_ticks"] == n // 60
    # the HH:59 ticks of hour 1 sit between the mark - 60 and the mark
    a, bb = g["tick_off"][1], g["tick_off"][2]
    assert bb - a == 5 and g["T0"] + 3540 <= g["tick_t"][a] < g["tick_t"][bb - 1] < g["T0"] + 3600
    # rows stamped after the capture are skipped
    late = dict(b[m.KR_PREFIX + M1][0]); late["available_at"] = "2030-01-01T00:00:00+00:00"
    fake2 = FakeArchive({**b, m.KR_PREFIX + M1: [late] + b[m.KR_PREFIX + M1][1:]})
    m._CACHE.clear()
    g2 = m.grid(fake2, [M1], [M1])
    assert np.isnan(g2["kr_close"][0]) and g2["rows"]["kraken"] == n - 1
    # the cache is keyed by the stored months and shared
    assert m.grid(fake2, [M1], [M1]) is g2


# --------------------------------------------------------------------------------------------------- T-331 --

def test_hourly_gaps_planted_vs_null_and_exact_staleness():
    fake = FakeArchive(world([M1], seed=1, gap=hourly_gap(0.05, 0.012)))
    g = m.grid(fake, [M1], [M1])
    r = m.hourly_gaps(g, 0, g["N"])
    share = r["exc"].sum() / r["valid"].sum()
    assert 0.03 < share < 0.08
    # within the HH:59 minute the price is flat: shifting Kraken by s <= 60 s never produces an excursion
    assert r["has_tick"].all()
    inside = r["ok_null"] & (r["s"] <= 55)                  # the first synthetic tick prints at second 5
    assert (r["stale_kr"][inside] > m.GAP_THR).sum() == 0
    beyond = r["ok_null"] & (r["s"] > 55) & r["exc"]        # before the first print the previous bar's close is exact
    assert (r["stale_kr"][beyond] > m.GAP_THR).all()
    # the exact tick lookup: with s = 60 the last trade at or before mark - 60 is the previous bar's close, so the
    # planted HH:59 gaps show up as 60 s staleness gaps
    assert abs((r["stale_kr60"][r["ok_null"]] > m.GAP_THR).mean() - share) < 0.01
    # a gap carried only by the last trade of the minute IS staleness: the simulation reproduces the excursions
    m._CACHE.clear()
    gj = m.grid(FakeArchive(world([M1], seed=1, gap=hourly_gap(0.05, 0.012), tick_mode="jump")), [M1], [M1])
    rj = m.hourly_gaps(gj, 0, gj["N"])
    assert abs(rj["exc"].mean() - (rj["ok_null"] & (rj["stale_kr"] > m.GAP_THR)).mean()) < 0.01
    m._CACHE.clear()
    fake0 = FakeArchive(world([M1], seed=1))
    g0 = m.grid(fake0, [M1], [M1])
    r0 = m.hourly_gaps(g0, 0, g0["N"])
    assert r0["exc"].sum() == 0


def test_coinbase_candle_floor_overstates_staleness():
    """A one-sided drift makes the candle-floor reading (up to 60 s staler) show larger staleness gaps than the exact one."""
    fake = FakeArchive(world([M1], seed=3, sigma=0.0008))
    g = m.grid(fake, [M1], [M1])
    r = m.hourly_gaps(g, 0, g["N"])
    ok = r["ok_null"] & np.isfinite(r["stale_cb"])
    # Kraken's exact shift within the flat HH:59 minute is 0 for s < 60 (the tick prices equal the close);
    # the Coinbase floor always spans at least one full minute of price change
    assert np.nanmean(r["stale_cb"][ok]) > np.nanmean(r["stale_kr"][ok])


def test_single_venue_rule_counts_signals():
    rng = np.random.default_rng(0)
    gap = rng.normal(0, 1e-4, 451)
    gap[400] = 0.02
    p = np.full(gap.size, 100.0)
    p[401:] = 101.0
    out = m.single_venue_rule(gap, p, p * np.exp(gap), rt_cost=0.0)
    # Gaussian noise fires |z| > 2 about 5% of the time with zero price moves; the planted spike is the only move
    assert 1 <= out["signals"] < 40 and out["kraken"]["n"] >= 1 and out["kraken"]["mean_gross"] > 0
    assert abs(out["kraken"]["mean_gross"] * out["kraken"]["n"] - math.log(1.01)) < 1e-9


def test_t331_planted_supported_and_null_not():
    fake = FakeArchive(world([M1, M2], seed=2, gap=hourly_gap(0.03, 0.012)))
    stat, n, verdict, reason = m.b6c_kraken_cross_venue_gap(fake)
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported", reason
    assert n >= 1000 and stat["wilson95"][0] >= 0.005 and stat["staleness"]["excess"]["ci"][0] > 0
    assert stat["missing_months"] == [] and "2024-03..2024-04" in reason
    m._CACHE.clear()
    stat0, n0, verdict0, reason0 = m.b6c_kraken_cross_venue_gap(FakeArchive(world([M1, M2], seed=2)))
    assert verdict0 == "not_supported" and stat0["excursions"] == 0, reason0
    assert "lower 95% Wilson bound" in reason0
    # the same excursion share produced by last-second jumps fails the staleness null (the Wilson criterion passes)
    m._CACHE.clear()
    statj, _, verdictj, reasonj = m.b6c_kraken_cross_venue_gap(FakeArchive(world([M1, M2], seed=2, gap=hourly_gap(0.03, 0.012), tick_mode="jump")))
    assert verdictj == "not_supported" and statj["wilson95"][0] >= 0.005, reasonj
    assert statj["criteria"][0][1] is True and statj["criteria"][1][1] is False


def test_t331_partial_window_is_capped_and_names_months(monkeypatch):
    monkeypatch.setitem(m.WIN, "T-331", (M1, "2024-05"))
    fake = FakeArchive(world([M1, M2], seed=2, gap=hourly_gap(0.03, 0.012)))
    stat, n, verdict, reason = m.b6c_kraken_cross_venue_gap(fake)
    assert verdict == "inconclusive" and stat["missing_months"] == ["2024-05"] and "2024-05" in reason
    assert stat["wilson95"][0] >= 0.005               # the covered part passes; the cap is the coverage criterion
    # a decisive failure on the covered part still counts (rule 5): 0 of 1464 marks has a Wilson upper bound below 0.5%
    m._CACHE.clear()
    stat0, _, verdict0, reason0 = m.b6c_kraken_cross_venue_gap(FakeArchive(world([M1, M2], seed=2)))
    assert verdict0 == "not_supported" and stat0["missing_months"] == ["2024-05"] and stat0["wilson95"][1] < 0.005
    # one month alone (720 marks, upper bound 0.53%) cannot rule out 0.5%: not decisive, so inconclusive
    m._CACHE.clear()
    stat1, _, verdict1, _ = m.b6c_kraken_cross_venue_gap(FakeArchive(world([M1], seed=2)))
    assert verdict1 == "inconclusive" and stat1["excursions"] == 0 and stat1["wilson95"][1] > 0.005


# --------------------------------------------------------------------------------------------------- T-425 --

def test_arb_sim_planted_gap_pays_and_one_position_at_a_time():
    rng = np.random.default_rng(0)
    n = 20000
    gap = rng.normal(0, 0.0001, n)
    starts = np.arange(100, n - 50, 200)
    for s in starts:
        gap[s:s + 3] = 0.03
    sigma = np.full(n, 0.0001)
    r = m.arb_sim(gap, sigma, fee_sum=0.0080)
    assert r["pnl"].size == starts.size
    assert np.all(r["entry"] == starts)                     # the trigger minute; fill at the next close
    assert np.all(r["fill_in"] == starts + 1)
    assert np.allclose(r["pnl"], 0.03 - 0.016, atol=0.001)  # gap captured minus the four legs
    assert np.all(r["exit"] > r["fill_in"]) and np.all(r["exit"][1:] > r["exit"][:-1])
    # overlapping triggers (the gap persists 3 minutes) do not open a second position
    assert r["candidates"] == 3 * starts.size
    r0 = m.arb_sim(rng.normal(0, 0.0001, n), sigma, fee_sum=0.0080)
    assert r0["pnl"].size == 0


def test_info_share_prefers_the_leading_venue():
    rng = np.random.default_rng(0)
    n = 20000
    eff = np.cumsum(rng.normal(0, 1e-3, n))
    p_cb = eff + rng.normal(0, 1e-5, n)                      # Coinbase tracks the efficient price
    p_kr = np.empty(n); p_kr[0] = eff[0]
    for i in range(1, n):
        p_kr[i] = p_kr[i - 1] + 0.3 * (p_cb[i - 1] - p_kr[i - 1]) + rng.normal(0, 1e-5)   # Kraken follows with a lag
    s = m.info_share(p_cb, p_kr)
    assert s is not None and s["coinbase_lower"] > 0.6 and s["coinbase_upper"] >= s["coinbase_lower"]


def test_t425_planted_passes_every_tier_but_the_unrecorded_tier_caps_it():
    """A planted gap pays every published tier pair; the implemented necessary condition passes, yet 'at the user's tier'
    is None (the tier is recorded nowhere), so the verdict is capped at inconclusive (rule 2 / rule 9)."""
    fake = FakeArchive(world([M1, M2], seed=4, gap=arb_gap(0.01, 0.045, 2)))
    stat, n, verdict, reason = m.b6c_kraken_inventory_arb(fake)
    json.dumps(stat, allow_nan=False)
    assert verdict == "inconclusive" and "not implemented" in reason and "not recorded" in reason, reason
    assert stat["criteria"][0][1] is None and stat["criteria"][1][1] is True
    assert n >= 20_000 and stat["missing_months"] == []
    retail = stat["cells"][f"cb:{m.RETAIL_PAIR[0]}|kr:{m.RETAIL_PAIR[1]}|taker"]
    assert retail["triggers"] > 100 and retail["total_net"] > 0 and stat["tiers"]["user_tier"] is None
    assert all(v["total_net"] > 0 for v in stat["cells"].values())
    assert all(v is not None for v in stat["family_sharpes_daily"].values()) and min(stat["family_triggers"].values()) >= m.FAMILY_MIN_N
    best = stat["bootstrap"][f"cb:{m.HIGHVOL_PAIR[0]}|kr:{m.HIGHVOL_PAIR[1]}|maker"]
    assert best["p"] < 0.05 and best["ci"][0] > 0
    assert stat["five_minute"]["retail"]["range"][0] <= stat["five_minute"]["retail"]["pooled_total_net"] <= stat["five_minute"]["retail"]["range"][1]
    # where the passing necessary condition's gross comes from: the legs sum to the gross; the synthetic gap sits on the
    # Kraken price (Coinbase is the random walk), so the Kraken leg carries it, and the reason says so by leg
    hv = stat["cells"][f"cb:{m.HIGHVOL_PAIR[0]}|kr:{m.HIGHVOL_PAIR[1]}|maker"]
    legs = hv["legs"]
    assert legs["n"] == hv["triggers"] and abs(legs["coinbase_leg"] + legs["kraken_leg"] - hv["mean_gross_per_trigger"]) < 1e-9
    assert abs(legs["coinbase_leg"]) < 0.003 and legs["kraken_leg"] > 0.03 and legs["kraken_leg_share_of_gross"] > 0.9
    assert legs["signed_gap_at_trigger"] > 0.04 and legs["signed_gap_at_exit"] < 0.005 and legs["fill_one_minute_later"]["n"] == legs["n"]
    assert "its gross by leg" in reason and "signed gap at trigger" in reason


def test_t425_null_fails_the_necessary_condition():
    """No gap: even the most favourable published pair loses (period costs, no triggers), which no tier can beat."""
    stat0, n0, verdict0, reason0 = m.b6c_kraken_inventory_arb(FakeArchive(world([M1, M2], seed=4)))
    assert verdict0 == "not_supported", reason0
    assert stat0["criteria"][0][1] is None and stat0["criteria"][1][1] is False
    best = stat0["cells"][f"cb:{m.HIGHVOL_PAIR[0]}|kr:{m.HIGHVOL_PAIR[1]}|maker"]
    assert best["total_net"] < 0 and best["total_period_costs"] < 0
    assert "not recorded" in reason0 and "necessary for any tier" in reason0
    # cells without triggers are only the financing drag: they do not enter the DSR family variance, and have no legs
    assert stat0["family_sharpes_daily"]["1m|retail"] is None and stat0["family_triggers"]["1m|retail"] < m.FAMILY_MIN_N
    assert stat0["cells"][f"cb:{m.RETAIL_PAIR[0]}|kr:{m.RETAIL_PAIR[1]}|maker"]["legs"] is None
    # on a partial window the same failure must be decisive to count: the best pair's upper bound is below 0 here
    m._CACHE.clear()
    stat1, _, verdict1, reason1 = m.b6c_kraken_inventory_arb(FakeArchive(world([M1], seed=4)))
    assert stat1["missing_months"] == [M2]
    assert verdict1 == ("not_supported" if stat1["criteria"][1][2] else "inconclusive"), reason1


def test_t425_unresolved_tiers_stay_inconclusive():
    """A gap that pays the best tier but not the worst leaves 'at the user's tier' undecided."""
    fake = FakeArchive(world([M1, M2], seed=5, gap=arb_gap(0.01, 0.012, 2)))
    stat, n, verdict, reason = m.b6c_kraken_inventory_arb(fake)
    best = stat["cells"][f"cb:{m.HIGHVOL_PAIR[0]}|kr:{m.HIGHVOL_PAIR[1]}|maker"]
    worst = stat["cells"][f"cb:{m.RETAIL_PAIR[0]}|kr:{m.RETAIL_PAIR[1]}|taker"]
    assert best["triggers"] > 50 and worst["triggers"] == 0
    assert verdict == "inconclusive" and stat["criteria"][0][1] is None and stat["criteria"][1][1] is True


def test_leg_decomposition_separates_venue_reversion_from_gap_capture():
    """Kraken-only reversion (Coinbase flat, Kraken's stale print reverts after the fill): the Kraken leg carries the whole
    gross and vanishes when its fill is one minute later; both venues converging half-way: the legs split the gross."""
    n = 20
    cb, kr = np.full(n, 100.0), np.full(n, 100.0)
    kr[10:12] = 100.0 * math.exp(-0.03)                     # gap 3% at the trigger (10) and the fill (11), gone from 12 on
    gap = np.log(cb / kr)
    tr = {"entry": np.array([10]), "fill_in": np.array([11]), "exit": np.array([13])}
    L = m.leg_decomposition(tr, gap, cb, kr)
    assert L["n"] == 1 and abs(L["mean_gross"] - 0.03) < 1e-12 and abs(L["coinbase_leg"]) < 1e-12 and abs(L["kraken_leg"] - 0.03) < 1e-12
    assert abs(L["kraken_leg_share_of_gross"] - 1.0) < 1e-12
    assert abs(L["signed_gap_at_trigger"] - 0.03) < 1e-12 and abs(L["signed_gap_at_fill"] - 0.03) < 1e-12 and abs(L["signed_gap_at_exit"]) < 1e-12
    assert abs(L["fill_one_minute_later"]["kraken_leg"]) < 1e-12 and abs(L["fill_one_minute_later"]["coinbase_leg"]) < 1e-12   # over by t+2
    cb2, kr2 = np.full(n, 100.0), np.full(n, 100.0)
    cb2[10:12] = 100.0 * math.exp(0.015); kr2[10:12] = 100.0 * math.exp(-0.015)
    L2 = m.leg_decomposition(tr, np.log(cb2 / kr2), cb2, kr2)
    assert abs(L2["coinbase_leg"] - 0.015) < 1e-12 and abs(L2["kraken_leg"] - 0.015) < 1e-12 and abs(L2["kraken_leg_share_of_gross"] - 0.5) < 1e-12
    # the sign convention: Coinbase cheap (gap < 0) buys Coinbase and sells Kraken for the same gross
    L3 = m.leg_decomposition(tr, -np.log(cb2 / kr2), kr2, cb2)
    assert abs(L3["mean_gross"] - 0.03) < 1e-12 and abs(L3["signed_gap_at_trigger"] - 0.03) < 1e-12 and abs(L3["coinbase_leg"] - 0.015) < 1e-12
    # no triggers -> None; arb_sim's empty result carries fill_in
    empty = m.arb_sim(np.zeros(100), np.ones(100), 0.001)
    assert empty["fill_in"].size == 0 and m.leg_decomposition(empty, np.zeros(100), np.ones(100), np.ones(100)) is None
    assert m._legs_txt(None) == "" and "Kraken" in m._legs_txt(L)


# --------------------------------------------------------------------------------------------------- T-459 --

def test_stationary_boot_mean_planted_vs_null():
    rng = np.random.default_rng(0)
    n = 2000
    e = rng.normal(0, 1, n)
    ar = np.empty(n); ar[0] = e[0]
    for i in range(1, n):
        ar[i] = 0.5 * ar[i - 1] + e[i]                        # autocorrelated noise: blocks matter
    planted = ar + 0.25
    r = m.stationary_boot_mean(planted, 40.0, n_boot=400, reps=2)
    assert r["p"] < 0.01 and r["ci"][0] > 0 and r["mean_block"] == 40.0 and r["reps"] == 2 and r["est"] > 0
    r0 = m.stationary_boot_mean(ar, 40.0, n_boot=400, reps=2)
    assert r0["p"] > 0.05 and r0["ci"][0] < 0 < r0["ci"][1]
    # the mean block is capped at n / 4; too few observations give no p
    assert m.stationary_boot_mean(planted[:40], 1000.0, n_boot=100, reps=1)["mean_block"] == 10.0
    assert m.stationary_boot_mean(planted[:5], 2.0)["p"] is None
    # blocks of mean 1 reduce to an iid bootstrap: an iid positive mean still passes
    assert m.stationary_boot_mean(e + 0.3, 1.0, n_boot=400, reps=1)["p"] < 0.01


def test_agree_rule11():
    assert m._agree(0.001, 0.005, 0.01) is True
    assert m._agree(0.2, 0.5, 0.01) is False
    assert m._agree(0.001, 0.5, 0.01) is None and m._agree(0.5, 0.001, 0.01) is None
    assert m._agree(None, 0.001, 0.01) is None


def test_imbalance_z_ratio_is_bounded_and_signed_is_not():
    fake = FakeArchive(world([M1], seed=6, imb_level=0.0))
    g = m.grid(fake, [M1], [M1])
    b, s_ = m._roll_sum(g["kr_buy"], 5), m._roll_sum(g["kr_sell"], 5)
    zr, zs = m.imbalance_z(g, 5), m.imbalance_z(g, 5, signed=True)
    ok = np.isfinite(zr) & np.isfinite(zs)
    assert ok.sum() > 10_000 and np.isnan(zr[:720]).all() and np.isfinite(zr[1440:]).all()   # >= 720 prior minutes are needed first
    # both are trailing-day z-scores: mean about 0, sd about 1 over the month
    assert abs(np.nanmean(zr)) < 0.1 and 0.8 < np.nanstd(zr) < 1.2 and abs(np.nanmean(zs)) < 0.1 and 0.8 < np.nanstd(zs) < 1.2
    # the ratio reading is bounded: |I| <= 1, so z can never exceed (1 - mean) / sd, while the signed reading is not
    I5 = (b - s_) / np.where(b + s_ > 0, b + s_, np.nan)
    assert np.nanmax(np.abs(I5)) <= 1.0 + 1e-12
    # a per-minute volume rescaling that keeps each minute's ratio leaves the 1-minute ratio z unchanged (a z-score is
    # scale invariant and the ratio is per minute) but changes the signed-volume z, which weighs busy minutes more
    rng = np.random.default_rng(0)
    f = rng.lognormal(0, 1, g["N"])
    g2 = dict(g); g2["kr_buy"] = g["kr_buy"] * f; g2["kr_sell"] = g["kr_sell"] * f
    z1, z1s = m.imbalance_z(g, 1), m.imbalance_z(g, 1, signed=True)
    ok1 = np.isfinite(z1) & np.isfinite(z1s)
    assert np.allclose(m.imbalance_z(g2, 1)[ok1], z1[ok1]) and not np.allclose(m.imbalance_z(g2, 1, signed=True)[ok1], z1s[ok1], atol=1e-3)


def test_imbalance_trades_fill_rule_and_planted_effect():
    fake = FakeArchive(world([M1], seed=6, flow_drift=0.0012, imb_level=0.0))
    g = m.grid(fake, [M1], [M1])
    z = m.imbalance_z(g, 5)
    tr = m.imbalance_trades(g, z, 0, g["N"], 5, 2.5, True)
    assert tr["net"].size > 30 and tr["net"].mean() > 0
    # entries are one at a time: consecutive entries at least h + 2 minutes apart
    assert np.all(np.diff(tr["entry"]) >= 7)
    # a strict reading (print strictly below the bid) fills too here, since sells print 0.2% through
    trs = m.imbalance_trades(g, z, 0, g["N"], 5, 2.5, True, strict=True)
    assert trs["net"].size == tr["net"].size
    # no print through the quote -> no fill (sells print 5% above every close: no seller ever reaches a bid at the prior close)
    g2 = dict(g); g2["kr_slo"] = g["kr_close"] * 1.05
    tr2 = m.imbalance_trades(g2, z, 0, g["N"], 5, 2.5, True)
    assert tr2["net"].size == 0 and tr2["unfilled"] == tr2["signals_taken"]
    # the taker reading pays two taker fees and fills at the next closes
    trt = m.imbalance_trades(g, z, 0, g["N"], 5, 2.5, False)
    assert trt["net"].size > 30 and abs((trt["gross"] - trt["net"]).mean() - 2 * m.T459_TAKER) < 1e-12
    # null: no drift -> the mean net is about minus the fees
    m._CACHE.clear()
    g0 = m.grid(FakeArchive(world([M1], seed=6, imb_level=0.0)), [M1], [M1])
    tr0 = m.imbalance_trades(g0, m.imbalance_z(g0, 5), 0, g0["N"], 5, 2.5, True)
    assert tr0["net"].size > 30 and tr0["net"].mean() < 0


def test_t459_planted_supported_and_null_not(monkeypatch):
    """The declared family is patched to the claim cell's maker / taker pair: the planted 5-minute drift then passes every
    criterion (both bootstraps agree, DSR against the family's spread); the null fails the mean-net criterion."""
    monkeypatch.setattr(m, "T459_GRID", [(5, 5, 2.0, True), (5, 5, 2.0, False)])
    fake = FakeArchive(world([M1, M2], seed=7, flow_drift=0.0015, flow_spike=2.0, imb_level=0.0))
    stat, n, verdict, reason = m.b6c_kraken_flow_imbalance(fake)
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported", reason
    assert n >= 50 and stat["oos"]["cluster_boot"]["p"] < 0.01 and stat["oos"]["stationary_boot"]["p"] < 0.01 and stat["dsr"]["dsr"] >= 0.95
    assert stat["oos"]["stationary_boot"]["mean_block"] > 1 and stat["oos"]["stationary_boot"]["ci"][0] > 0
    assert stat["oos_months_stored"] == [M2] and stat["forward_regression_oos"]["t"] > 2
    assert "stationary" in reason and "must agree" in stat["criteria"][0][0]
    m._CACHE.clear()
    stat0, n0, verdict0, reason0 = m.b6c_kraken_flow_imbalance(FakeArchive(world([M1, M2], seed=7, imb_level=0.0)))
    assert verdict0 == "not_supported", reason0
    assert stat0["oos"]["mean_net"] < 0 and stat0["criteria"][0][1] is False
    assert stat0["oos"]["stationary_boot"]["p"] > 0.5 and stat0["oos"]["cluster_boot"]["p"] > 0.5


def test_t459_full_grid_runs_and_the_family_spread_deflates_the_claim_cell():
    """With the full 24-cell family the planted world's structurally different cells (60-minute horizons, 3-sigma cells
    with a dozen trades) spread the trial Sharpes, so the DSR criterion, not the mean-net one, decides."""
    fake = FakeArchive(world([M1, M2], seed=7, flow_drift=0.0015, flow_spike=2.0, imb_level=0.0))
    stat, n, verdict, reason = m.b6c_kraken_flow_imbalance(fake)
    json.dumps(stat, allow_nan=False)
    assert len(stat["cells_out_of_sample"]) == 24 and stat["in_sample_best"] in stat["cells_out_of_sample"]
    assert stat["criteria"][0][1] is True and stat["criteria"][1][1] is False and verdict == "not_supported"
    assert stat["dsr"]["var_used"].startswith("observed")
    # cells with fewer than FAMILY_MIN_N trades (the 3-sigma cells here) do not enter the family variance
    small = sum(1 for v in stat["cells_out_of_sample"].values() if v["n"] < m.FAMILY_MIN_N)
    assert small > 0 and stat["dsr"]["n_family_computed"] == 24 - small
    assert set(stat["vol_terciles_oos"]) == {"low", "mid", "high"}
    # the alternative reading (raw signed volume z-scored) runs through the same pipeline and is reported, not decided
    alt = stat["alternative_reading_signed_volume"]
    assert alt["out_of_sample"]["n"] > 30 and alt["out_of_sample"]["mean_net"] > 0 and alt["out_of_sample"]["stationary_p"] < 0.05
    assert "alternative reading" in reason and "alternative" not in " ".join(c[0] for c in stat["criteria"])


def test_t459_decide_gates_both_criteria_on_the_same_minimum_evidence():
    """Rule 5: the DSR row (an asymptotic-normal PSR) is decided only from the evidence the mean-net row needs, at least
    MIN_TRADES_DECIDE trades on MIN_DAYS_DECIDE days, so a handful of losing trades on 2-3 days cannot decide the claim through
    the DSR row alone; the DSR and PSR values are still reported."""
    rng = np.random.default_rng(0)
    few = np.array([-0.456, -0.330, -0.320, -0.164, -0.851, -0.741]) / 100          # the reproduced 6 trades on 3 days
    days3 = ["2024-01-03", "2024-01-03", "2024-02-11", "2024-02-11", "2024-02-11", "2024-03-20"]
    d = m.t459_decide(few, days3, [None])
    assert d["enough"] is False and d["n_days"] == 3 and d["n"] == 6
    assert d["dsr"]["psr0"] is not None and d["dsr"]["psr0"] < 0.05           # the PSR alone WOULD have called it decisive
    assert d["dsr_crit"][1] is None and d["dsr_crit"][2] is False and "not decided" in d["dsr_crit"][0]
    assert d["cs"]["p"] is None and d["sb"]["p"] is None and d["p_ok"] is None and d["p_dec"] is False and d["cs"]["clusters"] == 3
    # 8 losing trades on 2 days: the day gate binds too (fewer than 4 clusters would give a degenerate cluster p of 0 / 1)
    x8 = -0.004 + 0.001 * rng.normal(size=8)
    d8 = m.t459_decide(x8, ["2024-01-03"] * 4 + ["2024-01-04"] * 4, [None])
    assert d8["enough"] is False and d8["dsr_crit"][1] is None and d8["p_dec"] is False and d8["dsr"]["psr0"] < 0.05
    # 40 losing trades on 20 days decide, decisively, through both rows
    x40 = -0.004 + 0.001 * rng.normal(size=40)
    d40 = m.t459_decide(x40, [f"2024-01-{1 + k // 2:02d}" for k in range(40)], [None])
    assert d40["enough"] is True and d40["dsr_crit"][1] is False and d40["dsr_crit"][2] is True and d40["p_ok"] is False and d40["p_dec"] is True
    # a planted positive mean on enough evidence passes both
    x60 = 0.005 + 0.002 * rng.normal(size=60)
    d60 = m.t459_decide(x60, [f"2024-02-{1 + k // 3:02d}" for k in range(60)], [None])
    assert d60["p_ok"] is True and d60["p_dec"] is False and d60["dsr_crit"][1] is True and d60["dsr"]["dsr"] >= 0.95
    # fewer than 4 trades: no DSR at all, still not an error
    d2 = m.t459_decide(few[:2], days3[:2], [None])
    assert d2["dsr"]["dsr"] is None and d2["dsr_crit"][1] is None and "n/a" in d2["dsr_crit"][0]


def test_t459_few_days_out_of_sample_are_reported_not_decided():
    """Harness level: losing out-of-sample trades on only two days (the null world with M2 cut to its first two days) are
    below the minimum evidence, so neither criterion is decided and the verdict is inconclusive; the PSR alone (and the
    degenerate 2-cluster bootstrap) would have called it a decisive failure."""
    b = world([M1, M2], seed=7, imb_level=0.0)
    b[m.KR_PREFIX + M2] = b[m.KR_PREFIX + M2][:2 * 1440]
    b[m.CB_PREFIX + M2] = b[m.CB_PREFIX + M2][:2 * 1440]
    stat, n, verdict, reason = m.b6c_kraken_flow_imbalance(FakeArchive(b))
    json.dumps(stat, allow_nan=False)
    assert n >= 8 and stat["oos"]["n_days"] <= 2 and stat["oos"]["minimum_evidence"]["met"] is False
    assert stat["oos"]["mean_net"] < 0 and stat["dsr"]["psr0"] is not None and stat["dsr"]["psr0"] < 0.05
    assert stat["oos"]["stationary_boot"]["p"] is None and stat["oos"]["cluster_boot"]["p"] is None
    assert stat["criteria"][0][1] is None and stat["criteria"][0][2] is False and stat["criteria"][1][1] is None and stat["criteria"][1][2] is False
    assert verdict == "inconclusive", reason
    assert f"below the {m.MIN_TRADES_DECIDE}-trade / {m.MIN_DAYS_DECIDE}-day minimum" in reason and "not decided" in reason


def test_t459_tercile_cutpoints_come_from_in_sample_signals(monkeypatch):
    """The volatility-tercile cutpoints are the terciles of the in-sample SIGNAL minutes (plentiful), not of the in-sample
    FILLED trades: with no seller printing through the bid in sample (zero in-sample fills) the control is still produced,
    and it follows the claim cell's window."""
    fake = FakeArchive(world([M1, M2], seed=7, flow_drift=0.0015, flow_spike=2.0, imb_level=0.0))
    g = m.grid(fake, [M1, M2], [M1, M2])
    a0, a1 = m._idx_range(g, M1, M1)
    g["kr_slo"][a0:a1] = g["kr_close"][a0:a1] * 1.05        # in-sample sells print 5% above every close: no maker fill in sample
    stat, n, verdict, reason = m.b6c_kraken_flow_imbalance(fake)
    assert stat["in_sample_claim_cell"]["n"] == 0 and stat["in_sample_claim_cell"]["signals"] >= m.TERCILE_MIN_SIGNALS
    cp = stat["vol_terciles_cutpoints"]
    assert cp["n_in_sample_signals"] >= m.TERCILE_MIN_SIGNALS and cp["rv60"][0] < cp["rv60"][1] and cp["source"].startswith("in-sample signal")
    assert set(stat["vol_terciles_oos"]) == {"low", "mid", "high"} and sum(v["n"] for v in stat["vol_terciles_oos"].values()) == n > 0
    assert "vol terciles (cutpoints from" in reason and "n/a (fewer" not in reason
    # the control follows the claim cell: a patched claim cell (w = 15) takes the cutpoints from ITS in-sample signals
    monkeypatch.setattr(m, "T459_CLAIM", (15, 5, 2.0, True))
    stat15, n15, _, reason15 = m.b6c_kraken_flow_imbalance(fake)
    assert stat15["claim_cell"] == "w15|h5|z2|maker" and "claim cell w15|h5|z2|maker" in reason15
    assert stat15["vol_terciles_cutpoints"]["n_in_sample_signals"] != cp["n_in_sample_signals"] and set(stat15["vol_terciles_oos"]) == {"low", "mid", "high"}


def test_t459_without_out_of_sample_months_is_inconclusive():
    fake = FakeArchive(world([M1], seed=7, flow_drift=0.0015, imb_level=0.0))
    stat, n, verdict, reason = m.b6c_kraken_flow_imbalance(fake)
    assert verdict == "inconclusive" and n == 0 and stat["missing_months"] == [M2]
    assert "out-of-sample months stored: none" in reason and "2024-04" in reason


# --------------------------------------------------------------------------------------------------- T-465 --

def test_vpin_buckets_pro_rata_and_hourly_alignment():
    fake = FakeArchive(world([M1], seed=8))
    g = m.grid(fake, [M1], [M1])
    bk = m.vpin_buckets(g, 50)
    # about 50 buckets a day after the ADV burn-in (5 days patched)
    days = (g["N"] // 1440) - 5
    assert 0.8 * 50 * days < bk["n_buckets"] < 1.2 * 50 * days
    assert np.all((bk["imb"] >= 0) & (bk["imb"] <= 1.0 + 1e-9))
    assert np.all(np.diff(bk["known_minute"]) >= 0)
    vp = m.vpin_hourly(bk, g["H"], 50)
    # the first hour mark with a VPIN is after 50 buckets have closed, and buckets closing after the mark do not count
    h = int(np.flatnonzero(np.isfinite(vp))[0])
    assert (bk["known_minute"] <= 60 * h - 1).sum() >= 50 and (bk["known_minute"] <= 60 * (h - 1) - 1).sum() < 50
    # a bucket straddling a boundary is split pro rata: total bucket imbalance is bounded by the minute imbalances
    assert np.nanmax(np.abs(bk["imb"])) <= 0.98 + 1e-9


def test_har_test_planted_vs_null():
    rng = np.random.default_rng(0)
    n = 3000
    X = rng.normal(0, 1, (n, 4))
    extra = rng.normal(0, 1, n)
    y = X @ np.array([0.5, 0.3, 0.2, 0.1]) + 0.8 * extra + rng.normal(0, 1, n)
    r = m.har_test(y, X, extra, burn_in=500)
    assert r["incr_r2"] > 0.02 and r["t"] > 3 and r["dm"]["p"] < 0.05 and r["n_oos"] == n - 500
    y0 = X @ np.array([0.5, 0.3, 0.2, 0.1]) + rng.normal(0, 1, n)
    r0 = m.har_test(y0, X, extra, burn_in=500)
    assert r0["incr_r2"] < 0.01 and not (r0["t"] > 3) and not (r0["dm"]["p"] < 0.05)


def test_hourly_rv_and_design():
    fake = FakeArchive(world([M1], seed=9))
    g = m.grid(fake, [M1], [M1])
    rv, vol = m.hourly_rv(g)
    assert rv.size == g["H"] and np.isnan(rv[0]) is np.False_ or np.isfinite(rv[1:]).all()
    X = m.har_design(rv, vol)
    assert X.shape == (g["H"], 4) and np.isfinite(X[200:]).all()
    assert abs(X[200, 0] - math.log(rv[199])) < 1e-12


def test_t465_planted_supported_and_null_not():
    fake = FakeArchive(world([M1, M2], seed=10, vpin_c=6.0, imb_block_hours=3))
    stat, n, verdict, reason = m.b6c_kraken_vpin_volatility(fake)
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported", reason
    assert n >= 400 and stat["headline"]["incr_r2"] >= 0.02 and stat["headline"]["t"] > 3 and stat["headline"]["dm"]["p"] < 0.05
    assert len(stat["cells"]) == 8
    m._CACHE.clear()
    stat0, n0, verdict0, reason0 = m.b6c_kraken_vpin_volatility(FakeArchive(world([M1, M2], seed=10)))
    assert verdict0 == "not_supported", reason0
    assert stat0["headline"]["incr_r2"] < 0.02


# ---------------------------------------------------------------------------------------------- contract --

@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason and " — " in reason


def test_contract_names_and_maps():
    assert set(m.THEORY_MAP) == {"T-331", "T-425", "T-459", "T-465"}
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(h.startswith("b6c_kraken_") and h == h.lower() for h in m.HARNESSES)


def test_every_harness_runs_json_safe_on_one_month():
    fake = FakeArchive(world([M1], seed=11))
    for name, fn in m.HARNESSES.items():
        stat, n, verdict, reason = fn(fake)
        json.dumps(stat, allow_nan=False)
        assert verdict in ("supported", "not_supported", "inconclusive")
        assert isinstance(n, int) and n >= 0 and " — " in reason
        assert "missing_bundles" not in stat and stat["missing_months"] == [M2]
