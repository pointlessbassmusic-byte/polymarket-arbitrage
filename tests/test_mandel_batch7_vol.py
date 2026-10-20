"""Batch-7 vol harnesses (T-545 RVX-VIX narrow side, T-550 quote-priced SPY strangle exits, T-551 PUT with a 10-month
SMA filter) on synthetic data only. Per core judge a planted effect passes and a null does not; the event rule, the
quote interpolation, the exit readings, the strangle margin, settlement and the trend-filter null are checked directly;
every harness runs on a fake archive (JSON-safe stat, reason ending with the verdict explanation, missing bundles ->
inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.data.dolt_options import is_trading_day
from mandel.experiments import batch6_surf as SURF
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6b_dolt as DOLT
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch7_vol as m
from mandel.options import bs

NB = 200


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", NB)
    monkeypatch.setattr(m, "T545_PLACEBO", 200)
    monkeypatch.setattr(m, "T551_N_NULL", 400)
    monkeypatch.setattr(MOM, "N_BOOT", NB)
    monkeypatch.setattr(MOM, "REPS", 1)
    for mod in (DOLT, MOM, BW):
        mod._CACHE.clear()
    yield
    for mod in (DOLT, MOM, BW):
        mod._CACHE.clear()


class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _sessions(start: str, n: int) -> list:
    out, x = [], date.fromisoformat(start)
    while len(out) < n:
        if is_trading_day(x):
            out.append(x.isoformat())
        x += timedelta(days=1)
    return out


def _gbm(n, vol, seed, s0=100.0):
    rng = np.random.default_rng(seed)
    sd = vol / math.sqrt(252)
    lr = rng.normal(-0.5 * sd ** 2, sd, n)
    lr[0] = 0.0
    return s0 * np.exp(np.cumsum(lr))


def _daily_rows(days, close, adj=None):
    adj = close if adj is None else adj
    return [{"available_at": d + "T21:00:00+00:00",
             "value": {"t": datetime.fromisoformat(d + "T13:30:00+00:00").timestamp(), "close": float(c),
                       "adjclose": float(a)}} for d, c, a in zip(days, close, adj)]


def _index_rows(days, level, **extra):
    return [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": float(x), **extra}}
            for d, x in zip(days, level)]


def _check(out):
    stat, n, verdict, reason = out
    json.dumps(stat)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert " — " in reason
    assert isinstance(n, int)
    return stat, n, verdict, reason


# ============================================================================================== T-545 ==

def _t545_world(dip_to: float, n: int = 3300, seed: int = 1):
    days = _sessions("2009-10-01", n)
    spy = _gbm(n, 0.10, seed)
    iwm = _gbm(n, 0.15, seed + 1)
    rng = np.random.default_rng(seed + 2)
    x = 10.0 + rng.normal(0, 0.5, n)
    x[100::63] = dip_to                        # isolated narrow dips (z far below -2)
    vix = np.full(n, 20.0)
    return days, vix + x, vix, iwm, spy


def test_t545_planted_narrow_side_passes():
    days, rvx, vix, iwm, spy = _t545_world(dip_to=0.0)      # realised IWM-SPY spread ~ +5 vs implied 0 at the dips
    r = m.rvx_narrow_test(days, rvx, vix, iwm, spy, n_boot=NB, n_placebo=200)
    assert r["n"] >= 30
    assert r["mean"] > 3 and r["ci95"][0] > 0 and r["win_rate"] > 0.6
    assert r["verdict"] == "supported", r["why"]


def test_t545_null_does_not_pass():
    days, rvx, vix, iwm, spy = _t545_world(dip_to=8.0)      # implied 8 at the dips vs realised ~5: wrong side
    r = m.rvx_narrow_test(days, rvx, vix, iwm, spy, n_boot=NB, n_placebo=200)
    assert r["n"] >= 30
    assert r["mean"] < 0
    assert r["verdict"] == "not_supported"


def test_t545_events_non_overlapping_first_close_rule():
    n = 400
    days = _sessions("2010-01-04", n)
    x = 10.0 + 0.3 * np.sin(np.arange(n) / 3.0)         # |z| of a sinusoid stays below sqrt(2)
    x[100:110] = 0.0                           # a 10-day narrow spell: one event (first close), no second inside the hold
    x[125] = 0.0                               # after the hold ends: a new event
    px = _gbm(n, 0.2, 3)
    ev = m.narrow_events(days, x, np.zeros(n), px, px)
    assert list(ev["t"][:2]) == [100, 125]
    assert np.all(np.diff(ev["t"]) >= m.T545_HOLD)
    evc = m.narrow_events(days, x, np.zeros(n), px, px, crossing=True)
    assert 100 in evc["t"]
    # entries outside the claim window are dropped
    ev2 = m.narrow_events(days, x, np.zeros(n), px, px, start="2011-01-01")
    assert all(days[t] >= "2011-01-01" for t in ev2["t"])
    # identical prices: realised spread 0, so the statistic is minus the implied spread at entry
    assert ev["stat"][0] == pytest.approx(-x[100])


def test_t545_harness_fake_archive():
    days, rvx, vix, iwm, spy = _t545_world(dip_to=0.0, n=1200)
    arch = FakeArchive({m.RVX_B: _index_rows(days, rvx), m.VIX_B: _index_rows(days, vix),
                        m.IWM_B: _daily_rows(days, iwm), m.SPY_B: _daily_rows(days, spy)})
    stat, n, verdict, reason = _check(m.b7_vol_rvx_narrow_spread(arch))
    assert n == stat["n"] and n > 0
    assert verdict != "supported" or n >= 30
    assert reason.split(" — ")[-1]
    out = m.b7_vol_rvx_narrow_spread(FakeArchive({}))
    assert out[2] == "inconclusive" and "missing" in out[3]


# ============================================================================================== T-550 ==

def _cycles(n, ratio_mu, diff_mu, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        y, mo = 2019 + (i + 2) // 12, (i + 2) % 12 + 1
        ppd_h = float(rng.normal(1e-4, 1e-4))
        rd = {}
        for r in m.READINGS:
            rd[m._rk(r)] = {"ratio": float(rng.normal(ratio_mu, 0.02)), "ppd": ppd_h + float(rng.normal(diff_mu, 5e-5))}
        out.append({"expiry": f"{y:04d}-{mo:02d}-15", "entry": f"{y:04d}-{mo:02d}-01", "ppd_h": ppd_h, "readings": rd})
    return out


def test_t550_planted_passes():
    r = m.strangle_claim(_cycles(80, 0.02, 1e-4), n_boot=NB)
    assert r["verdict"] == "supported", r["why"]


def test_t550_null_does_not_pass():
    r = m.strangle_claim(_cycles(80, -0.02, -1e-4, seed=1), n_boot=NB)
    assert r["verdict"] == "not_supported"
    r0 = m.strangle_claim(_cycles(80, 0.0, 0.0, seed=2), n_boot=NB)
    assert r0["verdict"] != "supported"


def test_t550_readings_must_agree_and_below_min_n():
    cs = _cycles(80, 0.02, 1e-4, seed=3)
    for c in cs:                                 # one reading loses: the ratio criterion becomes undecided, not a pass
        c["readings"]["loglinear/last>=21"]["ratio"] -= 0.05
    r = m.strangle_claim(cs, n_boot=NB)
    assert r["verdict"] == "inconclusive"
    r2 = m.strangle_claim(_cycles(30, 0.02, 1e-4, seed=4), n_boot=NB)   # below min_n 60: never supported
    assert r2["verdict"] != "supported"


def test_t550_ask_interpolation_and_exit_rules():
    legs = [{"strike": 90.0, "bid": 0.9, "ask": 1.0}, {"strike": 100.0, "bid": 3.8, "ask": 4.0},
            {"strike": 110.0, "bid": 9.5, "ask": 10.0}]
    assert m.ask_at(legs, 100.0, 200.0, "linear") == (4.0, True)
    lin, ex = m.ask_at(legs, 95.0, 200.0, "linear")
    lg, _ = m.ask_at(legs, 95.0, 200.0, "loglinear")
    assert not ex and lin == pytest.approx(2.5) and lg == pytest.approx(2.0) and lg < lin
    assert m.ask_at(legs, 120.0, 200.0, "linear") == (None, False)
    assert m.ask_at(legs, 95.0, 100.0, "linear") == (None, False)         # bracket wider than 6% of S
    mk = lambda rows: [(d, t, {"linear": c, "loglinear": c}, False) for d, t, c in rows]
    marks = mk([("a", 30, 1.5), ("b", 25, 1.4), ("c", 14, 1.2)])
    assert m.exit_rule(marks, 2.0, "linear", "first<=21") == ("21dte", "c", 1.2)
    assert m.exit_rule(marks, 2.0, "linear", "last>=21") == ("21dte", "b", 1.4)
    tgt = mk([("a", 30, 1.5), ("b", 28, 0.9), ("c", 14, 1.2)])
    assert m.exit_rule(tgt, 2.0, "linear", "first<=21") == ("target", "b", 0.9)
    assert m.exit_rule(tgt, 2.0, "linear", "last>=21") == ("target", "b", 0.9)
    assert m.exit_rule(mk([("a", 30, 1.5)]), 2.0, "linear", "first<=21") == (None, None, None)
    assert m.exit_rule(mk([("a", 30, 1.5)]), 2.0, "linear", "last>=21") == ("21dte", "a", 1.5)


def test_t550_margin_and_settlement():
    day = {"quote_date": "2021-01-04", "snapshot_date": "2021-01-04", "spot": 100.0, "available_at": "",
           "exp": {"2021-02-19": {"call": [{"strike": 110.0, "bid": 1.0, "ask": 1.1, "iv": 0.2, "delta": 0.16}],
                                  "put": [{"strike": 90.0, "bid": 1.5, "ask": 1.6, "iv": 0.25, "delta": -0.16}]}}}
    t, why = m.strangle_trade(day, "2021-02-19")
    assert why is None
    # call: 1.0 + max(20 - 10, 10) = 11; put: 1.5 + max(20 - 10, 9) = 11.5 -> 11.5 + call premium 1.0
    assert m.strangle_margin(t) == pytest.approx(12.5)
    mark = {"quote_date": "2021-02-01", "spot": 101.0,
            "exp": {"2021-02-19": {"call": [{"strike": 110.0, "bid": 0.3, "ask": 0.35}],
                                   "put": [{"strike": 90.0, "bid": 0.6, "ask": 0.65}]}}}
    chain = {"2021-01-04": day, "2021-02-01": mark}
    out = m.manage(chain, sorted(chain), t, 85.0)
    assert out["credit"] == pytest.approx(2.5)
    assert out["pnl_h"] == pytest.approx(2.5 - 5.0)          # put settles 5 in the money on the raw close
    r = out["readings"]["linear/first<=21"]
    assert r["exit"] == "target" and r["pnl"] == pytest.approx(2.5 - 1.0)   # 1.0 <= 50% of 2.5 at 18 DTE


def _t550_chain(n=170, vol=0.18, seed=0):
    days = _sessions("2019-02-01", n)
    close = _gbm(n, vol, seed, s0=280.0)
    monthly = sorted(DOLT.monthly_expiries(2019, 2020))
    rows = []
    for q, S in zip(days, close):
        K = np.arange(math.ceil(0.85 * S), 1.15 * S, 2.0)
        for e in monthly:
            dt = DOLT.dte(e, q)
            if not 11 <= dt <= 66:
                continue
            T = dt / 365.0
            for kind in ("call", "put"):
                px = np.asarray(bs.price(S, K, T, 0.0, vol, kind), float)
                dl = bs.greeks(S, K, T, 0.0, vol, kind)["delta"]
                for k, p, d in zip(K, px, dl):
                    rows.append({"available_at": q + "T22:00:00+00:00",
                                 "value": {"snapshot_date": q, "quote_date": q, "expiry": e, "strike": float(k),
                                           "type": kind, "bid": max(round(float(p) - 0.02, 4), 0.01),
                                           "ask": round(float(p) + 0.02, 4), "iv": vol, "delta": float(d),
                                           "stale": False}})
    return {m.CHAIN_B: rows, m.SPY_B: _daily_rows(days, close)}


def test_t550_harness_fake_archive():
    stat, n, verdict, reason = _check(m.b7_vol_spy_strangle_quoted_exits(FakeArchive(_t550_chain())))
    assert verdict != "supported"                              # far below min_n 60 cycles
    assert n == stat["n_cycles"] and n >= 1
    out = m.b7_vol_spy_strangle_quoted_exits(FakeArchive({}))
    assert out[2] == "inconclusive" and "missing" in out[3]


# ============================================================================================== T-551 ==

def _monthly_path(n_months=372, seed=0, bears=(60, 150, 240, 320), start="1990-01-02"):
    """Daily sessions with a monthly return path: drift +0.8%/month, steady -4%/month 12-month bear trends."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.008, 0.02, n_months)
    for b in (b for b in bears if b + 12 <= n_months):
        r[b:b + 12] = -0.04 + rng.normal(0, 0.01, 12)
    days = _sessions(start, n_months * 23)
    months = sorted({d[:7] for d in days})[:n_months]
    by = {}
    for d in days:
        by.setdefault(d[:7], []).append(d)
    out_d, out_l, lvl = [], [], 100.0
    for k, mo in enumerate(months):
        ds = by[mo]
        step = (1 + r[k]) ** (1 / len(ds))
        for d in ds:
            lvl *= step
            out_d.append(d)
            out_l.append(lvl)
    return out_d, np.array(out_l)


def _bills():
    return BW.Bills({"1989-12-01": 3.0, "2005-01-03": 2.0})


def test_t551_planted_filter_passes():
    days, lvl = _monthly_path()
    sig = m.sma_signal([("SPY", days, lvl)])
    r = m.putwrite_trend_filter(days, lvl, [False] * len(days), sig, _bills(), launch="2005-01-01", n_null=400,
                                n_boot=NB, reps=1)
    assert r["n"] >= 300
    assert r["dd"]["reduction"] >= 0.3 and r["dd"]["p"] < 0.05
    assert r["verdict"] == "supported", r["why"]


def test_t551_null_signal_does_not_pass():
    days, lvl = _monthly_path(seed=1)
    noise = _gbm(len(days), 0.15, 7)                              # a signal unrelated to the PUT path
    sig = m.sma_signal([("SPY", days, noise)])
    r = m.putwrite_trend_filter(days, lvl, [False] * len(days), sig, _bills(), launch="2005-01-01", n_null=400,
                                n_boot=NB, reps=1)
    assert r["verdict"] != "supported"


def test_t551_signal_splice_and_continuity():
    gd = _sessions("1990-01-02", 1200)
    sd = [d for d in gd if d >= "1993-01-29"]
    sig = m.sma_signal([("SPY", sd, np.linspace(1, 2, len(sd))), ("^GSPC", gd, np.linspace(2, 1, len(gd)))])
    assert sig["1992-06"] == (False, "^GSPC")                     # falling ^GSPC below its SMA
    assert sig["1993-05"][1] == "^GSPC"                           # SPY's own 10-month SMA not yet defined
    assert sig["1994-01"] == (True, "SPY")
    assert m.continuous_start(["1991-03-04", "1994-09-27", "2007-01-03", "2007-01-04"]) == 2


def test_t551_harness_fake_archive():
    days, lvl = _monthly_path(n_months=300, start="2004-01-02")
    g = _gbm(len(days), 0.15, 3, s0=1000.0)
    bt = [d < m.T551_LAUNCH for d in days]
    put = [{"available_at": d + "T23:00:00+00:00", "value": {"day": d, "close": float(x), "backtest": b}}
           for d, x, b in zip(days, lvl, bt)]
    put.insert(0, {"available_at": "2007-06-20T23:00:00+00:00", "value": {"day": "1995-03-01", "close": 50.0,
                                                                          "backtest": True}})
    arch = FakeArchive({m.PUT_B: put, m.GSPC_B: _daily_rows(days, g), m.SPY_B: _daily_rows(days, lvl),
                        m.DTB3_B: [{"available_at": "2003-12-02T00:00:00+00:00", "value": {"day": "2003-12-01", "value": 2.0}}]})
    stat, n, verdict, reason = _check(m.b7_vol_putwrite_trend_filter(arch))
    assert stat["pre_continuous_prints"] == ["1995-03-01"]
    assert n == stat["n_months"] and n >= 250
    assert stat["last_decision"] < m.T551_END                   # holds end with 2026-09 (the claim's "to 2026-09")
    assert stat["n_backtest_months"] > 0 and stat["live"]["n"] < n
    out = m.b7_vol_putwrite_trend_filter(FakeArchive({}))
    assert out[2] == "inconclusive" and "missing" in out[3]


def test_registry_maps():
    assert set(m.THEORY_MAP) == {"T-545", "T-550", "T-551"}
    assert all(h in m.HARNESSES and h.startswith("b7_vol_") for h in m.THEORY_MAP.values())
