"""Batch-6c stocktwits harnesses (T-414 pre-open bullish ratio, T-415 intensity -> next-day realised variance) on
synthetic data only: for every core function a planted effect passes and a null does not; the pre-open window filter
and count cross-check, the crypto 09:30 ET marks (minute bars, then hourly), the permutation null under the StockTwits
bullish skew, the strictly-trailing z-score, the session bar filter, the HAR row alignment, the Driscoll-Kraay
estimator, the walk-forward embargo and Diebold-Mariano, the two-reading criteria and the rule-5 / data-limit paths are
checked directly; every harness runs JSON-safe on a fake archive, missing bundles give inconclusive, optional bundles
are optional. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_stocktwits as m

UTC = timezone.utc
CAP = "2026-10-19T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _clear():
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, n):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cdays(start, end):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def et_iso(day, hh, mm):
    return datetime.fromtimestamp(m._et_ts(day, hh, mm), tz=UTC).isoformat()


def utc_ts(day, hh=0):
    y, mo, d = map(int, day.split("-"))
    return datetime(y, mo, d, hh, tzinfo=UTC).timestamp()


class FakeArchive:
    def __init__(self):
        self.b = {}

    def add(self, name, rows, created_at=CAP):
        self.b[name] = SimpleNamespace(name=name, rows=list(rows), recipe="", created_at=created_at)

    def get(self, name):
        return self.b[name]

    def load(self, name):
        yield from self.b[name].rows

    def entries(self, kind=None, tag=None):
        return list(self.b.values())


def yahoo_daily(days, opens, closes, highs=None, lows=None):
    rows = []
    for i, d in enumerate(days):
        t = m._et_ts(d, 9, 30)
        c = float(closes[i])
        rows.append({"available_at": et_iso((date.fromisoformat(d) + timedelta(days=1)).isoformat(), 9, 30),
                     "value": {"symbol": "X", "t": t, "open": float(opens[i]), "high": float(highs[i]) if highs is not None else c * 1.01,
                               "low": float(lows[i]) if lows is not None else c * 0.99, "close": c, "adjclose": c, "volume": 1000}})
    return rows


def bar_row(t, o, h, l, c, vol=100):
    return {"available_at": datetime.fromtimestamp(t + 3600, tz=UTC).isoformat(),
            "value": {"symbol": "X", "t": float(t), "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": vol}}


# ================================================================================================ T-414 world ==

def t414_world(p_follow, n_days=110, seed=0, start="2025-10-01", with_1m=True):
    """Fake archive for T-414: 14 streams x n_days sessions; the forward sign follows the pre-declared rule with
    probability ``p_follow``."""
    rng = np.random.default_rng(seed)
    sessions = bdays(start, n_days + 1)
    days = sessions[:n_days]
    arch = FakeArchive()
    arch.add(m.SPY_B, yahoo_daily(sessions, 100 + np.arange(len(sessions)) * 0.1, 100 + np.arange(len(sessions)) * 0.1))
    arch.add(m.VIX_B, [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": 15 + 5 * math.sin(i / 7.0)}} for i, d in enumerate(sessions)])
    weeks = {}
    truth = []
    for si, sym in enumerate(m.ST_PREOPEN_SYMBOLS):
        B = rng.uniform(0.2, 0.9, n_days)
        pred = np.sign(B - m.FOLLOW_CUT)
        follow = rng.random(n_days) < p_follow
        mag = np.abs(rng.normal(0, 0.012, n_days)) + 1e-4
        ret = np.where(follow, pred, -pred) * mag
        price = 100.0 * np.cumprod(np.concatenate([[1.0], 1 + ret]))
        for i, d in enumerate(days):
            prev = sessions[sessions.index(d) - 1] if sessions.index(d) > 0 else (date.fromisoformat(d) - timedelta(days=1)).isoformat()
            ws, we = et_iso(prev, 16, 0), et_iso(d, 9, 0)
            t0, t1 = m._ts(ws), m._ts(we)
            tagged = int(25 + rng.integers(0, 30))
            bull = int(round(B[i] * tagged))
            bear = tagged - bull
            sents = ["Bullish"] * bull + ["Bearish"] * bear + [None] * 5
            rows = []
            for k, s in enumerate(sents):
                tt = t0 + rng.uniform(0, t1 - t0 - 1)
                rows.append({"kind": "message", "available_at": datetime.fromtimestamp(tt, tz=UTC).isoformat(),
                             "value": {"stream": sym, "day": d, "created_at": datetime.fromtimestamp(tt, tz=UTC).isoformat(), "sentiment": s}})
            # one bullish message outside the window (before 16:00 ET) must be ignored
            rows.append({"kind": "message", "available_at": datetime.fromtimestamp(t0 - 600, tz=UTC).isoformat(),
                         "value": {"stream": sym, "day": d, "created_at": datetime.fromtimestamp(t0 - 600, tz=UTC).isoformat(), "sentiment": "Bullish"}})
            wb, wbe = bull, bear
            if si == 1 and i == 0:
                wb += 3                                  # a fetcher count that disagrees with the stored messages
            rows.append({"kind": "window", "available_at": we,
                         "value": {"stream": sym, "day": d, "window_start": ws, "window_end": we, "anchor_id": 1, "pages": 2,
                                   "messages": len(sents), "tagged": wb + wbe, "bullish": wb, "bearish": wbe,
                                   "complete": not (si == 0 and i == 0)}})
            weeks.setdefault(iso_week(d), []).extend(rows)
            truth.append((sym, d, float(B[i]), float(ret[i]), tagged))
        if sym in m.CRYPTO_PID:
            pid = m.CRYPTO_PID[sym]
            hourly, by_month = [], {}
            for d in cdays(sessions[0], sessions[-1]):
                j = sum(1 for s in sessions if s <= d) - 1
                p = price[min(max(j, 0), n_days)]
                for h in range(24):
                    t = utc_ts(d, h)
                    hourly.append(bar_row(t, p, p, p, p))
                if d in sessions and with_1m and pid == "BTC-USD":          # only BTC has minute bars archived
                    for mm in (30, 31):
                        t = m._et_ts(d, 9, mm)
                        by_month.setdefault(d[:7], []).append(bar_row(t, p, p, p, p))
            arch.add(f"coinbase-hourly-{pid}", hourly)
            for mo, rows in by_month.items():
                arch.add(f"coinbase-1m-{pid}-{mo}", rows)
        else:
            cl = price[:len(sessions)] * (1 + rng.normal(0, 0.003, len(sessions)))
            arch.add(m.dh(sym), yahoo_daily(sessions, price[:len(sessions)], cl))
    for w, rows in weeks.items():
        arch.add(f"{m.PREOPEN_PREFIX}{w}", rows)
    return arch, truth


def obs_from_truth(truth):
    return [{"sym": s, "day": d, "B": B, "ret": r, "tagged": tg, "cost": m.COST_RT.get(s, m.COST_RT_DEFAULT)} for s, d, B, r, tg in truth]


# ================================================================================================ T-415 world ==

def t415_world(gamma, n_days=130, seed=0, start="2025-10-01", hourly_for_all=True):
    """Fake archive for T-415: 21 streams; the day's message intensity is x_t = base exp(0.3 u_t) with u_t ~ N(0, 1) on
    90% of sampled days and a spike u_t = 4 + |N(0, 0.5)| (z > 2) on 10%; ln RV_{t+1} = mu + 0.5 (ln RV_t - mu) +
    gamma u_t + noise, so both readings of the regressor (z and 1{z > 2}) carry the planted effect."""
    rng = np.random.default_rng(seed)
    warm = 35
    sessions = bdays(start, n_days + warm)
    sampled = sessions[warm - 30:]                     # 30 warm-up sampled days for z, then n_days
    arch = FakeArchive()
    arch.add(m.SPY_B, yahoo_daily(sessions, 100 + np.arange(len(sessions)) * 0.1, 100 + np.arange(len(sessions)) * 0.1))
    arch.add(m.FOMC_B, [{"available_at": d + "T00:00:00+00:00", "value": {"decision_day": d, "future": False}} for d in sessions[::17]])
    weeks, dolt, truth = {}, [], {}
    for sym in m.ST_INTENSITY_SYMBOLS:
        crypto = sym in m.CRYPTO_PID
        cal = cdays(sessions[0], sessions[-1]) if crypto else list(sessions)
        mu = math.log(4e-4 if crypto else 1e-4 * (0.5 + rng.random()))
        u = {}
        for d in sampled:
            u[d] = (4.0 + abs(rng.normal(0, 0.5))) if rng.random() < 0.10 else rng.normal()
        lv = np.empty(len(cal))
        lv[0] = mu
        for i in range(1, len(cal)):
            lv[i] = mu + 0.5 * (lv[i - 1] - mu) + gamma * u.get(cal[i - 1], 0.0) + rng.normal(0, 0.25)
        v = np.exp(lv)
        truth[sym] = dict(zip(cal, v))
        # bars
        bars, px = [], 100.0
        nb = 24 if crypto else 7
        for i, d in enumerate(cal):
            for k in range(nb):
                t = utc_ts(d, k) if crypto else m._et_ts(d, 9, 30) + k * 3600
                o = px
                px = px * math.exp(rng.normal(0, math.sqrt(v[i] / nb)))
                bars.append(bar_row(t, o, max(o, px), min(o, px), px))
            if not crypto:
                bars.append(bar_row(m._et_ts(d, 16, 0), px, px, px, px, vol=0))      # Yahoo's spurious 16:00 bar
        if crypto:
            arch.add(f"coinbase-hourly-{m.CRYPTO_PID[sym]}", bars)
        elif hourly_for_all or sym != "XLK":
            arch.add(m.hourly_b(sym), bars)
        # daily bars (Parkinson / squared-return family; the fallback estimator)
        closes, highs, lows = [], [], []
        c = 100.0
        for i, d in enumerate(sessions):
            vv = truth[sym].get(d, v[0])
            c = c * math.exp(rng.normal(0, math.sqrt(vv)))
            closes.append(c)
            highs.append(c * math.exp(math.sqrt(vv) * 0.9))
            lows.append(c * math.exp(-math.sqrt(vv) * 0.9))
        if not crypto:
            arch.add(m.dh(sym), yahoo_daily(sessions, closes, closes, highs, lows))
        # implied variance at the same close
        if sym in m.CBOE_IV:
            arch.add(m.cboe_b(m.CBOE_IV[sym]), [{"available_at": d + "T21:30:00+00:00",
                                                 "value": {"day": d, "close": 100 * math.sqrt(252 * truth[sym][d]) * math.exp(rng.normal(0, 0.1))}} for d in sessions])
        elif sym in m.DVOL_IV:
            arch.add(m.dvol_b(m.DVOL_IV[sym]), [{"available_at": (date.fromisoformat(d) + timedelta(days=1)).isoformat() + "T00:00:00+00:00",
                                                 "value": {"ts_ms": utc_ts(d) * 1000, "close": 100 * math.sqrt(365 * truth[sym][d]) * math.exp(rng.normal(0, 0.1))}} for d in cal])
        else:
            for d in sessions:
                dolt.append({"available_at": d + "T22:00:00+00:00",
                             "value": {"symbol": sym, "snapshot_date": d, "quote_date": d, "iv_current": math.sqrt(252 * truth[sym][d]) * math.exp(rng.normal(0, 0.1))}})
                if d == sessions[40]:                                                   # a weekend snapshot repeating the quote
                    dolt.append({"available_at": d + "T22:00:00+00:00",
                                 "value": {"symbol": sym, "snapshot_date": (date.fromisoformat(d) + timedelta(days=2)).isoformat(), "quote_date": d, "iv_current": 9.9}})
        # intensity samples
        base = 20.0 * (0.5 + rng.random())
        for i, d in enumerate(sampled):
            x = base * math.exp(0.3 * u[d])
            for k, hm in enumerate(("10:00", "13:00", "15:30")):
                if sym == "XLU" and d == sampled[50] and k > 0:
                    continue                                                           # a day with one sample only: dropped
                ph = None if (sym == "SPY" and d == sampled[51] and k == 0) else x * (1 + rng.normal(0, 0.05))
                hh, mm = map(int, hm.split(":"))
                st = et_iso(d, hh, mm)
                weeks.setdefault(iso_week(d), []).append({"kind": "intensity-sample", "available_at": st,
                                                          "value": {"stream": sym, "day": d, "sample_time": st, "n": 30, "per_hour": ph}})
    arch.add(m.DOLT_B, dolt)
    for w, rows in weeks.items():
        arch.add(f"{m.INTENSITY_PREFIX}{w}", rows)
    return arch, truth


# ======================================================================================== small pieces ==

def test_sidak_nw_lag_and_ranks():
    assert abs(m.sidak(0.0005, 16) - (1 - (1 - 0.0005) ** 16)) < 1e-12
    assert m.sidak(None, 16) is None
    assert m.nw_lag(200) == 4 and m.nw_lag(50) == 3
    assert list(m._rank(np.array([3.0, 1.0, 2.0, 2.0]))) == [4.0, 1.0, 2.5, 2.5]
    assert abs(m.spearman([1, 2, 3, 4], [2, 4, 6, 8]) - 1.0) < 1e-12
    assert m.spearman([1, 2], [1, 2]) is None


def test_dk_ols_matches_ols_under_iid_and_widens_under_common_shocks():
    rng = np.random.default_rng(1)
    T, Nc = 150, 20
    X = rng.normal(size=(T * Nc, 2))
    tidx = np.repeat(np.arange(T), Nc)
    y = 1 + X @ np.array([0.5, -0.3]) + rng.normal(size=T * Nc)
    r = m.dk_ols(y, X, tidx, 3)
    Z = np.column_stack([np.ones(T * Nc), X])
    b = np.linalg.lstsq(Z, y, rcond=None)[0]
    e = y - Z @ b
    se_ols = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * (e @ e) / (T * Nc - 3))
    assert np.allclose(r["beta"], b)
    assert np.all(np.abs(r["se"] / se_ols - 1) < 0.3)
    # a common shock per period inflates the slope's s.e. when the regressor is shared across the cross-section
    xc = np.repeat(rng.normal(size=T), Nc)
    yc = 1 + 0.5 * xc + np.repeat(rng.normal(size=T), Nc) + rng.normal(size=T * Nc) * 0.1
    r2 = m.dk_ols(yc, xc[:, None], tidx, 3)
    Z2 = np.column_stack([np.ones(T * Nc), xc])
    e2 = yc - Z2 @ np.linalg.lstsq(Z2, yc, rcond=None)[0]
    se_naive = math.sqrt(np.linalg.inv(Z2.T @ Z2)[1, 1] * (e2 @ e2) / (T * Nc - 2))
    assert r2["se"][1] > 2.5 * se_naive


def test_preopen_panel_recomputes_counts_inside_the_window_and_flags_mismatch():
    ws, we = "2025-10-23T20:00:00+00:00", "2025-10-24T13:00:00+00:00"
    win = [{"kind": "window", "value": {"stream": "AAPL", "day": "2025-10-24", "window_start": ws, "window_end": we, "bullish": 2, "bearish": 1, "complete": True}},
           {"kind": "window", "value": {"stream": "QQQ", "day": "2025-10-24", "window_start": ws, "window_end": we, "bullish": 5, "bearish": 0, "complete": False}}]
    msgs = [{"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-23T21:00:00Z", "sentiment": "Bullish"}},
            {"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-24T08:00:00Z", "sentiment": "Bullish"}},
            {"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-24T12:59:59Z", "sentiment": "Bearish"}},
            {"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-24T13:00:00Z", "sentiment": "Bearish"}},     # at 09:00 ET: out
            {"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-23T19:59:00Z", "sentiment": "Bullish"}},     # before 16:00 ET: out
            {"value": {"stream": "AAPL", "day": "2025-10-24", "created_at": "2025-10-24T01:00:00Z", "sentiment": None}},
            {"value": {"stream": "QQQ", "day": "2025-10-24", "created_at": "2025-10-24T01:00:00Z", "sentiment": "Bullish"}}]
    p = m.preopen_panel(msgs, win)
    a = p[("AAPL", "2025-10-24")]
    assert a["bullish"] == 2 and a["bearish"] == 1 and a["tagged"] == 3 and abs(a["B"] - 2 / 3) < 1e-12
    assert a["messages"] == 4 and a["outside"] == 2 and a["mismatch"] is False and a["complete"] is True
    q = p[("QQQ", "2025-10-24")]
    assert q["B"] == 1.0 and q["mismatch"] is True and q["complete"] is False


def test_crypto_open_marks_prefer_minute_bars_then_hourly():
    arch = FakeArchive()
    days = ["2025-11-03", "2025-11-04"]                                     # EST: 09:30 ET = 14:30 UTC
    arch.add("coinbase-1m-BTC-USD-2025-11", [bar_row(m._et_ts("2025-11-03", 9, 30), 101, 101, 101, 101),
                                             bar_row(m._et_ts("2025-11-03", 9, 31), 102, 102, 102, 102)])
    arch.add("coinbase-hourly-BTC-USD", [bar_row(utc_ts(d, h), 200 + h, 200 + h, 200 + h, 200 + h) for d in days for h in range(24)])
    marks, desc, src = m.crypto_open_marks(arch, "BTC-USD", days)
    assert marks["2025-11-03"] == 101 and src["2025-11-03"] == "1m"
    assert marks["2025-11-04"] == 215 and src["2025-11-04"] == "1h"        # the 15:00 UTC (10:00 EST) bar
    assert "1m" in desc and "hourly" in desc
    marks2, desc2, _ = m.crypto_open_marks(arch, "ETH-USD", days)
    assert marks2 == {} and desc2 == "no archived bars"


# ============================================================================================= T-414 core ==

def test_bullish_ratio_test_planted_passes_and_null_fails():
    _, truth = t414_world(0.65, n_days=100, seed=3)
    res = m.bullish_ratio_test(obs_from_truth(truth), n_perm=2000, seed=0)
    assert res["accuracy"] > 0.6 and res["p_perm_deflated"] < 0.01
    assert res["ic"]["pooled_t_symbol_clustered"] > 3 and res["ic"]["cross_sectional_t_nw"] > 3
    crit = m.t414_criteria(res)
    v, why = m._decide(crit, res["n"], m.T414_MIN_N, "symbol-days")
    assert v == "supported", why
    _, truth0 = t414_world(0.5, n_days=100, seed=4)
    res0 = m.bullish_ratio_test(obs_from_truth(truth0), n_perm=300, seed=0)
    crit0 = m.t414_criteria(res0)
    v0, why0 = m._decide(crit0, res0["n"], m.T414_MIN_N, "symbol-days")
    assert v0 == "not_supported" and res0["p_perm_deflated"] > 0.01
    assert res0["net"]["mean_net_bps"] < res0["net"]["mean_gross_bps"]


def test_permutation_p_is_one_under_a_pure_bullish_skew():
    """B above 0.5 on every day predicts 'up' always: the accuracy equals the up-day share and shuffling B cannot change
    it, so the permutation p is 1 whatever the accuracy."""
    rng = np.random.default_rng(0)
    obs = [{"sym": s, "day": f"2026-01-{d + 1:02d}", "B": 0.6 + 0.3 * rng.random(), "ret": 0.01 if rng.random() < 0.7 else -0.01, "tagged": 30, "cost": 0}
           for s in ("A", "B", "C", "D", "E", "F") for d in range(25)]
    res = m.bullish_ratio_test(obs, n_perm=100, seed=0)
    assert res["accuracy"] > 0.6 and res["p_perm"] == 1.0
    crit = m.t414_criteria(res)
    assert crit[1][1] is False and crit[1][2] is False                   # fails, never decisively


def test_t414_accuracy_decisive_failure_below_min_n():
    res = {"accuracy": 0.40, "n_predicted": 400, "acc_se": math.sqrt(0.4 * 0.6 / 400), "p_perm_deflated": 0.9,
           "ic": {"cross_sectional_t_nw": -1.0, "pooled_t_symbol_clustered": -3.5},
           "halves": {"first": {"accuracy": 0.4, "ic_pooled": -0.1}, "second": {"accuracy": 0.41, "ic_pooled": -0.05}}}
    crit = m.t414_criteria(res)
    assert crit[0][1] is False and crit[0][2] is True                    # 99% upper bound of 40% on 400 days is below 52%
    assert crit[2][2] is True                                            # pooled t < -3: decisively the wrong sign
    v, why = m._decide(crit, 400, m.T414_MIN_N, "symbol-days")
    assert v == "not_supported"
    res["accuracy"], res["acc_se"] = 0.515, math.sqrt(0.515 * 0.485 / 400)
    res["ic"]["pooled_t_symbol_clustered"] = 1.0
    crit = m.t414_criteria(res)
    assert crit[0][1] is False and crit[0][2] is False
    v, why = m._decide(crit, 400, m.T414_MIN_N, "symbol-days")
    assert v == "inconclusive"


# ============================================================================================= T-415 core ==

def test_zscore_trailing_uses_only_the_past():
    days = [f"d{i:03d}" for i in range(40)]
    x = np.ones(40)
    x[35] = 10.0
    z = m.zscore_trailing(days, x, window=30, min_obs=20)
    assert np.isnan(z[:20]).all()                                        # fewer than 20 past observations
    assert np.isnan(z[20:35]).all()                                      # constant history: sd 0 -> not computable
    assert np.isnan(z[35]) and np.isfinite(z[36])                        # the spike enters only later windows
    x2 = np.arange(40, dtype=float)
    z2 = m.zscore_trailing(days, x2, window=30, min_obs=20)
    assert np.isfinite(z2[25]) and z2[25] > 0
    expected = (25 - np.mean(x2[0:25])) / np.std(x2[0:25], ddof=1)
    assert abs(z2[25] - expected) < 1e-12


def test_rv_from_hourly_session_filter_and_crypto_day():
    d = "2026-03-10"
    bars = []
    px = 100.0
    for k in range(7):
        t = m._et_ts(d, 9, 30) + k * 3600
        o, c = px, px * (1.01 if k % 2 == 0 else 0.99)
        bars.append((t, o, max(o, c), min(o, c), c))
        px = c
    bars.append((m._et_ts(d, 16, 0), px, px, px, px))                  # spurious 16:00 bar
    bars.append((m._et_ts(d, 8, 30), 50.0, 50.0, 50.0, 50.0))          # pre-market bar
    rv = m.rv_from_hourly(bars, "session")
    lr = np.log([1.01, 0.99] * 3 + [1.01])
    assert abs(rv[d] - float(lr @ lr)) < 1e-12
    # an early close (4 bars) drops out
    short = [b for b in bars[:4]]
    assert m.rv_from_hourly(short, "session") == {}
    cb = [(utc_ts("2026-03-10", h), 100.0, 100.0, 100.0, 100.0 * (1 + 0.001 * h)) for h in range(24)]
    rvc = m.rv_from_hourly(cb, "utc")
    assert "2026-03-10" in rvc and rvc["2026-03-10"] > 0
    assert m.rv_from_hourly(cb[:10], "utc") == {}


def test_parkinson_sq_ret_and_har_rows_alignment():
    daily = {"2026-01-05": {"open": 1, "close": 100.0, "raw_close": 100, "high": 102.0, "low": 98.0},
             "2026-01-06": {"open": 1, "close": 110.0, "raw_close": 110, "high": 111.0, "low": 109.0}}
    pk = m.parkinson(daily)
    assert abs(pk["2026-01-05"] - math.log(102 / 98) ** 2 / (4 * math.log(2))) < 1e-15
    sq = m.sq_ret(daily)
    assert list(sq) == ["2026-01-06"] and abs(sq["2026-01-06"] - math.log(1.1) ** 2) < 1e-15
    cal = [f"2026-02-{i:02d}" for i in range(1, 29)]
    rv = {d: float(i + 1) for i, d in enumerate(cal)}
    z = {cal[24]: 1.5, cal[27]: 2.5, cal[10]: 0.3}
    iv = {d: 2.0 for d in cal if d != cal[10]}
    rows = m.har_rows("S", rv, z, iv, 5, 22, 1)
    assert [r["day"] for r in rows] == [cal[24]]                       # cal[27] has no next day; cal[10] has no IV and no 22-day window
    r = rows[0]
    assert r["y"] == 26.0 and r["rv"] == 25.0 and r["rvw"] == 23.0 and r["rvm"] == 14.5 and r["target_day"] == cal[25]
    assert r["abn"] == 0.0
    assert m.har_rows("S", rv, {cal[20]: 3.0}, iv, 5, 22, 1) == []      # only 21 RV days up to cal[20]: no 22-day window
    rows5 = m.har_rows("S", rv, {cal[21]: 3.0}, iv, 5, 22, 5)
    assert rows5[0]["y"] == np.mean([23, 24, 25, 26, 27]) and rows5[0]["abn"] == 1.0


def _panel(gamma, seed=0, n_days=130):
    arch, _ = t415_world(gamma, n_days=n_days, seed=seed)
    rows = []
    for w in m._entry_names(arch, m.INTENSITY_PREFIX):
        rows.extend(r for r in m._rows(arch, w) if r.get("kind") == "intensity-sample")
    intensity, few = m.intensity_panel(rows)
    P = m.build_t415_panel(arch, intensity)
    return arch, P, few


def test_intensity_panel_and_har_test_planted_vs_null():
    arch, P, few = _panel(0.5, seed=2)
    assert few["XLU"] == 1 and P["drops"] == {}
    rows = P["rows"]
    assert len(rows) >= m.T415_MIN_N
    assert all(v["rv"].startswith("intraday hourly RV") for s, v in P["info"].items() if s not in m.CRYPTO_PID)
    assert all(v["rv"].startswith("hourly RV over the UTC day") for s, v in P["info"].items() if s in m.CRYPTO_PID)
    assert P["info"]["XLB"]["iv"] == m.DOLT_B and P["info"]["SPY"]["iv"] == m.cboe_b("VIX")
    z_in, a_in = m.har_test(rows, "z", 1), m.har_test(rows, "abn", 1)
    assert z_in["t"] > 3 and z_in["dr2"] >= 0.02 and a_in["t"] > 3 and a_in["dr2"] >= 0.02
    assert z_in["p_sidak"] < 0.05
    _, P0, _ = _panel(0.0, seed=5)
    z0 = m.har_test(P0["rows"], "z", 1)
    assert z0["dr2"] < 0.02 and abs(z0["t"]) < 3


def test_walk_forward_qlike_planted_improves_and_null_does_not():
    _, P, _ = _panel(0.5, seed=2)
    wf = m.walk_forward_qlike(P["rows"], "z")
    assert wf["n_origins"] >= 30 and wf["qlike_full"] < wf["qlike_base"] and wf["dm_p_sidak"] < 0.05
    wf_a = m.walk_forward_qlike(P["rows"], "abn")
    assert wf_a["dm_p_sidak"] < 0.05
    lev = m.walk_forward_qlike(P["rows"], "z", log=False)
    assert lev["floored_share"] is not None and lev["form"].startswith("levels")
    _, P0, _ = _panel(0.0, seed=5)
    wf0 = m.walk_forward_qlike(P0["rows"], "z")
    assert wf0["dm_p_sidak"] > 0.05


def test_walk_forward_embargo_excludes_recent_targets():
    """A target that leaks into training raises the fit: with the embargo the rows whose target is within 5 days of the
    origin are not used, so a forecast at origin k never sees y of days k-4..k."""
    rows = []
    for i in range(80):
        d = f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}" if i < 59 else f"2026-03-{i - 58:02d}"
        rows.append({"sym": "S", "day": d, "target_day": d, "y": 1.0 + (i >= 70) * 100.0, "rv": 1.0, "rvw": 1.0, "rvm": 1.0, "iv": 1.0, "z": 0.0, "abn": 0.0})
    wf = m.walk_forward_qlike(rows, "z", min_train=60, embargo=5)
    assert wf["n_origins"] == 20 and wf["origins"][0] == "2026-03-02"


def test_t415_criteria_need_both_readings():
    ok = {"t": 3.5, "dr2": 0.03, "p_sidak": 0.001}
    bad = {"t": 2.0, "dr2": 0.03, "p_sidak": 0.1}
    wf_ok = {"dm_t": 3.0, "dm_p": 0.001, "dm_p_sidak": 0.01, "qlike_full": 0.4, "qlike_base": 0.5}
    wf_bad = {"dm_t": 1.0, "dm_p": 0.16, "dm_p_sidak": 0.9, "qlike_full": 0.49, "qlike_base": 0.5}
    c = m.t415_criteria(ok, ok, wf_ok, wf_ok)
    assert c[0][1] is True and c[1][1] is True
    c = m.t415_criteria(ok, bad, wf_ok, wf_bad)
    assert c[0][1] is False and c[1][1] is False and c[0][2] is False
    c = m.t415_criteria({"t": -3.5, "dr2": 0.03}, ok, wf_ok, wf_ok)
    assert c[0][2] is True                                               # decisively the wrong sign
    c = m.t415_criteria({"t": None, "dr2": None}, ok, {"dm_p_sidak": None}, wf_ok)
    assert c[0][1] is None and c[1][1] is None


# ============================================================================================ harnesses ==

@pytest.fixture(scope="module")
def planted():
    a414, _ = t414_world(0.65, n_days=110, seed=3)
    a415, _ = t415_world(0.5, n_days=130, seed=2)
    arch = FakeArchive()
    arch.b.update(a414.b)
    arch.b.update(a415.b)
    return arch


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_every_harness_runs_json_safe_and_planted_is_supported(planted, name):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES[name](planted)
    json.dumps(stat, allow_nan=False)
    assert verdict == "supported", reason
    assert isinstance(n, int) and n >= (m.T414_MIN_N if name.endswith("ratio") else m.T415_MIN_N)
    assert " — " in reason and "earnings flags not available" in reason


def test_t414_harness_bookkeeping(planted):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_bullish_ratio"](planted)
    assert stat["drops"] == {"window incomplete": 1} and stat["window_count_mismatches"] == 1
    assert stat["symbol_days_raw"] == 14 * 110 and n == 14 * 110 - 1
    assert stat["marks"]["BTC.X"].startswith("coinbase-1m") and stat["marks"]["ETH.X"].startswith("coinbase-hourly")
    assert stat["marks"]["AAPL"].startswith("Yahoo")
    assert stat["result"]["vix_split"]["high_vix"]["n"] > 0 and stat["earnings_flag"] is None
    assert set(stat["result"]["family"]) >= {"follow_level_0.5", "contrarian_level_0.5", "follow_threshold_0.7_0.4"}
    assert stat["result"]["family"]["contrarian_level_0.5"]["accuracy"] < 0.5


def test_t415_harness_bookkeeping(planted):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_intensity_rv"](planted)
    assert stat["symbols_dropped"] == {} and len(stat["per_symbol"]) == 21
    assert stat["in_sample"]["levels_z"]["t"] is not None and stat["walk_forward"]["levels_z"]["floored_share"] is not None
    assert set(stat["family"]) == {"hourly_h1", "hourly_h5", "parkinson_h1", "parkinson_h5", "sq_ret_h1", "sq_ret_h5"}
    assert stat["ex_fomc_target_days"]["n"] < n and stat["n_fomc_days"] > 0
    assert stat["days_with_too_few_samples"]["XLU"] == 1


def test_null_worlds_are_not_supported(monkeypatch):
    monkeypatch.setattr(m, "T414_N_PERM", 300)
    a414, _ = t414_world(0.5, n_days=110, seed=4)
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_bullish_ratio"](a414)
    assert n >= m.T414_MIN_N and verdict == "not_supported", reason
    m._CACHE.clear()
    a415, _ = t415_world(0.0, n_days=130, seed=5)
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_intensity_rv"](a415)
    assert n >= m.T415_MIN_N and verdict == "not_supported", reason


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive())
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "no week archived yet" in reason and " — " in reason


def test_t414_two_days_is_a_data_limit_inconclusive(monkeypatch):
    monkeypatch.setattr(m, "T414_N_PERM", 100)
    arch, _ = t414_world(0.65, n_days=2, seed=1)
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_bullish_ratio"](arch)
    assert verdict == "inconclusive" and 0 < n < m.T414_MIN_N
    assert "below min_n" in reason or "not implemented" in reason
    assert f"n >= trial min_n ({n} of {m.T414_MIN_N} symbol-days)" in reason


def test_optional_bundles_are_optional(monkeypatch):
    monkeypatch.setattr(m, "T414_N_PERM", 100)
    a414, _ = t414_world(0.65, n_days=40, seed=3, with_1m=False)
    for k in [m.VIX_B, m.dh("GME"), "coinbase-hourly-SOL-USD"]:
        a414.b.pop(k, None)
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_bullish_ratio"](a414)
    assert "missing_bundles" not in stat and n > 0
    assert set(stat["price_missing"]) == {"GME", "SOL.X"} and stat["drops"]["no archived prices"] == 80
    assert stat["marks"]["BTC.X"].startswith("coinbase-hourly") and stat["result"]["vix_split"] is None
    m._CACHE.clear()
    a415, _ = t415_world(0.5, n_days=60, seed=2, hourly_for_all=False)
    for k in [m.FOMC_B, m.cboe_b("VXTLT"), "coinbase-hourly-ETH-USD"]:
        a415.b.pop(k, None)
    stat, n, verdict, reason = m.HARNESSES["b6c_stocktwits_intensity_rv"](a415)
    assert "missing_bundles" not in stat and n > 0
    assert stat["per_symbol"]["XLK"]["rv"].startswith("Parkinson")
    assert stat["per_symbol"]["TLT"]["used"] == 0 and "no implied" in stat["per_symbol"]["TLT"]["reason"]
    assert stat["per_symbol"]["ETH.X"]["used"] == 0 and "no realised" in stat["per_symbol"]["ETH.X"]["reason"]
    assert stat["symbols_dropped"] == {"no IV source": 1, "no RV source": 1} and stat["ex_fomc_target_days"] is None


def test_maps_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-414", "T-415"}
    assert all(k.startswith("b6c_stocktwits_") and k == k.lower() for k in m.HARNESSES)
