"""Synthetic tests for mandel.experiments.batch7_crypto (T-546, T-554, T-556): a planted effect that passes and a null that
does not, per core function, the child-rule replication details, and the harness contract (missing bundles named and
inconclusive, JSON-safe stat, verdict set) on fake archives. No network, no real archive."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch7_crypto as M

UTC = timezone.utc
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


def _days(first: str, n: int) -> list:
    d0 = date.fromisoformat(first)
    return [(d0 + timedelta(days=k)).isoformat() for k in range(n)]


def _ts(d: str) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp())


# ============================================================================================================ T-546 ==

def _alt_panel(planted: bool, seed: int = 1, P: int = 30, T: int = 700):
    rng = np.random.default_rng(seed)
    days = _days("2018-06-01", T)
    r = rng.normal(0.0, 0.02, (P, T))
    lv = rng.normal(12.0, 0.25, (P, T))
    spike = np.zeros((P, T), bool)
    for t in range(80, T - 15):
        i = rng.integers(0, P)
        spike[i, t] = True
        lv[i, t] += 2.5
        r[i, t] = rng.normal(0.0, 0.004)
        if planted:
            r[i, t + 2: t + 12] += 0.008
    C = 10.0 * np.exp(np.cumsum(r, axis=1))
    V = np.exp(lv) / C
    pids = [f"A{i:02d}-USD" for i in range(P)]
    daily = {p: {d: (float(C[i, t]), float(V[i, t])) for t, d in enumerate(days)} for i, p in enumerate(pids)}
    members = {d: list(pids) for d in days}
    return M.alt_panel(daily, members, days[0], days[-1])


@pytest.mark.parametrize("planted", [True, False])
def test_alt_hvp_planted_and_null(planted):
    pan = _alt_panel(planted)
    sig = M.alt_hvp_signals(pan, start="2018-09-01", end="2026-12-31")
    j = M.alt_hvp_test(sig, min_n=300, n_boot=400, reps=2, n_draw=500)
    assert j["n"] >= 300
    if planted:
        assert j["mean_net"] > 0.01
        assert j["placebo"]["p"] < 0.05
        assert j["verdict"] == "supported", j["why"]
    else:
        assert j["verdict"] == "not_supported", j["why"]


def test_alt_signals_point_in_time():
    """Changing prices after day t never changes whether day t is an event."""
    pan = _alt_panel(True, seed=3)
    s1 = M.alt_hvp_signals(pan, start="2018-09-01", end="2026-12-31")
    pan2 = dict(pan)
    C = pan["C"].copy()
    V = pan["V"].copy()
    C[:, 400:] *= 1.7
    V[:, 400:] *= 3.0
    pan2.update(C=C, V=V)
    s2 = M.alt_hvp_signals(pan2, start="2018-09-01", end="2026-12-31")
    assert s1["ev"][:, :385].any()
    assert np.array_equal(s1["ev"][:, :385], s2["ev"][:, :385])     # forward windows of these days end before day 400


def test_alt_harness_missing_bundles():
    stat, n, v, reason = M.b7_crypto_alt_high_volume_premium(FakeArchive({}))
    assert v == "inconclusive" and n == 0 and "coinbase-products-<day>" in reason
    json.dumps(stat)


# ============================================================================================================ T-554 ==

def _greed_data(planted: bool, seed: int = 0, n: int = 3000):
    rng = np.random.default_rng(seed)
    days = _days("2018-01-01", n + 20)
    f = np.empty(n)
    z = 0.0
    for t in range(n):
        z = 0.97 * z + rng.normal(0, 4.0)
        f[t] = min(100.0, max(0.0, 50 + 2.0 * z))
    r = rng.normal(0.0, 0.03, n + 20)
    if planted:
        for t in range(n):
            if f[t] >= 75:
                r[t + 2: t + 9] += 0.004          # entry close t+1 -> exit close t+8: returns of days t+2..t+8
    c = 100.0 * np.exp(np.cumsum(r))
    closes = dict(zip(days, c.tolist()))
    fng = dict(zip(days[:n], f.tolist()))
    return fng, closes


@pytest.mark.parametrize("planted", [True, False])
def test_greed_planted_and_null(planted):
    fng, closes = _greed_data(planted)
    f, fwd, dd = M.greed_align(fng, closes, start="2018-01-01", end="2030-01-01")
    j = M.greed_test(f, fwd, dd, min_n=150)
    assert j["n_greed"] >= 150
    if planted:
        assert j["d"] > 0 and j["p"] < 0.05
        assert j["verdict"] == "supported", j["why"]
    else:
        assert j["verdict"] != "supported"


def test_greed_alignment_is_t41():
    days = _days("2020-01-01", 20)
    closes = {d: float(k + 1) for k, d in enumerate(days)}
    fng = {days[0]: 80.0}
    f, fwd, dd = M.greed_align(fng, closes, start="2020-01-01", end="2020-12-31")
    assert dd == [days[0]]
    assert fwd[0] == pytest.approx(math.log(9.0 / 2.0))   # close(t+8) / close(t+1)


def test_greed_shift_null_matches_roll():
    rng = np.random.default_rng(5)
    f = rng.uniform(0, 100, 400)
    fwd = rng.normal(0, 0.05, 400)
    j = M.greed_test(f, fwd, [f"d{k:04d}" for k in range(400)], min_n=10)
    g = f >= 75
    d = fwd[g].mean() - fwd.mean()
    ks = np.arange(8, 400 - 8)
    null = np.array([fwd[np.roll(g, k)].mean() - fwd.mean() for k in ks])
    assert j["p"] == pytest.approx((1 + np.sum(null >= d - 1e-15)) / (1 + ks.size))


def _yahoo_rows(sym, days, closes):
    return [{"observed_at": d + "T00:00:00+00:00", "available_at": d + "T00:00:00+00:00",
             "value": {"symbol": sym, "t": _ts(d), "open": c, "high": c, "low": c, "close": c, "adjclose": c}}
            for d, c in zip(days, closes)]


def test_greed_harness_contract():
    stat, n, v, reason = M.b7_crypto_eth_greed_momentum(FakeArchive({}))
    assert v == "inconclusive" and "crypto-fear-greed-history" in reason
    fng, closes = _greed_data(True, n=2000)
    fdays = sorted(fng)
    rows_f = [{"observed_at": d + "T00:00:00+00:00", "available_at": d + "T00:00:00+00:00", "value": {"value": fng[d]}} for d in fdays]
    cd = sorted(closes)
    arch = FakeArchive({M.FNG_B: rows_f, M.ETH_Y: _yahoo_rows("ETH-USD", cd, [closes[d] for d in cd])})
    stat, n, v, reason = M.b7_crypto_eth_greed_momentum(arch)
    json.dumps(stat)
    assert v in VERDICTS and n == stat["n_greed"] and " — " in reason


# ============================================================================================================ T-556 ==

def test_child_quantiles_and_buckets():
    vals = sorted([5.0, 1.0, 3.0, 2.0, 4.0, 6.0])
    assert M.child_quantiles(vals) == [3.0, 5.0]           # vals[int(6/3)], vals[int(12/3)]
    assert M.child_bucket(2.9, [3.0, 5.0]) == 0
    assert M.child_bucket(3.0, [3.0, 5.0]) == 1
    assert M.child_bucket(5.0, [3.0, 5.0]) == 2


def _bars(days, o, h, l, c):
    return {"days": days, "open": np.array(o, float), "high": np.array(h, float), "low": np.array(l, float), "close": np.array(c, float)}


def test_short_trade_fills():
    days = _days("2022-01-01", 40)
    n = len(days)
    o = [100.0] * n; h = [101.0] * n; l = [99.0] * n; c = [100.0] * n
    # signal on day 5 -> entry open day 6 = 100; day 8 gaps up through the stop: fill at the open 115
    o[8], h[8], l[8], c[8] = 115.0, 116.0, 114.0, 115.0
    b = _bars(days, o, h, l, c)
    tr = M.short_trades({"X": b}, [("X", days[5], 5)], first="2000-01-01", last="2100-01-01")
    assert len(tr) == 1 and tr[0]["why"] == "stop" and tr[0]["exit"] == pytest.approx(115.0)
    assert tr[0]["net"] == pytest.approx(1 - 115 / 100 - M.T556_COST - M.T556_FUND_DAY * 3)
    # target: the low must trade through 80; touching exactly 80 is not a fill
    o = [100.0] * n; h = [101.0] * n; l = [99.0] * n; c = [100.0] * n
    l[7] = 80.0
    l[9] = 79.0
    tr = M.short_trades({"X": _bars(days, o, h, l, c)}, [("X", days[5], 5)], first="2000-01-01", last="2100-01-01")
    assert tr[0]["why"] == "target" and tr[0]["exit_day"] == days[9] and tr[0]["exit"] == pytest.approx(80.0)
    # one bar touching both: the stop first
    o = [100.0] * n; h = [101.0] * n; l = [99.0] * n; c = [100.0] * n
    h[10], l[10] = 111.0, 70.0
    tr = M.short_trades({"X": _bars(days, o, h, l, c)}, [("X", days[5], 5)], first="2000-01-01", last="2100-01-01")
    assert tr[0]["why"] == "stop" and tr[0]["exit"] == pytest.approx(110.0)
    assert tr[0]["bench_net"] == pytest.approx(-0.1018)
    # time exit at the close of entry + 13, 14 days of funding; re-entry blocked for 14 days from entry
    c = [100.0] * n
    c[6 + 13] = 95.0
    tr = M.short_trades({"X": _bars(days, [100.0] * n, [101.0] * n, [99.0] * n, c)},
                        [("X", days[5], 5), ("X", days[10], 10), ("X", days[19], 19)], first="2000-01-01", last="2100-01-01")
    assert [t["signal"] for t in tr] == [days[5], days[19]]
    assert tr[0]["why"] == "time" and tr[0]["exit_day"] == days[19] and tr[0]["held_days"] == 14
    assert tr[0]["net"] == pytest.approx(0.05 - M.T556_COST - 14 * M.T556_FUND_DAY)


def test_child_signals_fire_on_bounce_in_decline():
    rng = np.random.default_rng(2)
    n = 400
    days = _days("2021-01-01", n)
    r = rng.normal(0, 0.03, n)
    for t in (250, 320):                                     # a sharp 3-day decline then a one-day bounce
        r[t - 2: t] = -0.12
        r[t] = 0.10
    c = 100 * np.exp(np.cumsum(r))
    b = _bars(days, c, c * 1.01, c * 0.99, c)
    sig = M.child_signals({"X": b, "Y": _bars(days, c[::-1], c[::-1] * 1.01, c[::-1] * 0.99, c[::-1])})
    fired = {(k, d) for k, d, _ in sig}
    assert ("X", days[250]) in fired and ("X", days[320]) in fired
    assert all(d >= days[30 + 60] for _, d, _ in sig)       # at least 120 days of pooled history (2 coins from day 30)


def _trades(mean_a, mean_b, n_each=60, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    d0 = date(2021, 11, 1)
    for k in range(n_each):
        for coin, m in (("DOGE-USD", mean_a), ("SHIB-USD", mean_b)):
            ed = (d0 + timedelta(days=14 * k + (0 if coin == "DOGE-USD" else 3))).isoformat()
            x = float(rng.normal(m, 0.08))
            out.append({"coin": coin, "entry_day": ed, "net": x, "gross": x + 0.005, "net_funding_received": x + 0.008,
                        "bench_net": 0.1982 if x > 0.1 else (-0.1018 if x < -0.08 else x), "why": "time"})
    return out


@pytest.mark.parametrize("planted", [True, False])
def test_bounce_planted_and_null(planted):
    tr = _trades(0.06, 0.05) if planted else _trades(0.0, -0.01)
    j = M.bounce_test(tr, n_boot=400, reps=2)
    assert j["n"] == 120
    if planted:
        assert j["verdict"] == "supported", j["why"]
    else:
        assert j["verdict"] == "not_supported", j["why"]


def test_bounce_one_coin_negative_fails():
    j = M.bounce_test(_trades(0.12, -0.03), n_boot=400, reps=2)
    assert j["verdict"] == "not_supported"


def _cb_rows(pid, days, o, h, l, c, v=1e6):
    return [{"observed_at": d + "T00:00:00+00:00", "available_at": d + "T00:00:00+00:00",
             "value": {"symbol": pid, "t": _ts(d), "open": float(o[k]), "high": float(h[k]), "low": float(l[k]),
                       "close": float(c[k]), "volume": v}} for k, d in enumerate(days)]


def test_bounce_harness_contract():
    stat, n, v, reason = M.b7_crypto_memecoin_bounce_short(FakeArchive({}))
    assert v == "inconclusive" and "coinbase-daily-DOGE-USD" in reason and "coinbase-daily-SHIB-USD" in reason
    rng = np.random.default_rng(4)
    days = _days("2021-06-01", 700)
    b = {}
    for pid in M.T556_COINS:
        c = 0.2 * np.exp(np.cumsum(rng.normal(0, 0.05, len(days))))
        o = np.concatenate([[c[0]], c[:-1]])
        b[M.cbd(pid)] = _cb_rows(pid, days, o, np.maximum(o, c) * 1.03, np.minimum(o, c) * 0.97, c)
    stat, n, v, reason = M.b7_crypto_memecoin_bounce_short(FakeArchive(b))
    json.dumps(stat)
    assert v in VERDICTS and n == stat["n_trades"] and "+0.1982" in reason and " — " in reason


def test_maps():
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    assert all(k.startswith("b7_crypto_") for k in M.HARNESSES)
    assert set(M.THEORY_MAP) == {"T-546", "T-554", "T-556"}
