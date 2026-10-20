"""Batch-6b dolt harnesses (T-119 call backspread, T-121 put front-ratio, T-539 put ladder, T-173 1x2 overlay by call
skew) on synthetic data only. For every core judge a planted effect passes and a null does not; the selectors (expiry,
delta, moneyness), denominators (max loss, Reg-T naked put margin), settlement, early-exercise rule, snapshot dedupe,
rule-10 chains, rule-5 handling and the stress criterion are checked directly; every harness runs on a fake archive
(JSON-safe stat, reason ending with the verdict explanation, missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.data.dolt_options import is_trading_day
from mandel.experiments import batch6b_dolt as d
from mandel.options import bs

NB = 200                                # bootstrap resamples in tests


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(d, "N_BOOT", NB)
    d._CACHE.clear()
    yield
    d._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

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


def _gbm(n, vol, seed, mu_day=0.0, s0=100.0):
    rng = np.random.default_rng(seed)
    sd = vol / math.sqrt(252)
    lr = rng.normal(mu_day - 0.5 * sd ** 2, sd, n)
    lr[0] = 0.0
    return s0 * np.exp(np.cumsum(lr))


def _spy_rows(days, close, adj=None):
    adj = close if adj is None else adj
    return [{"available_at": dd + "T21:00:00+00:00",
             "value": {"symbol": "SPY", "t": datetime.fromisoformat(dd + "T13:30:00+00:00").timestamp(),
                       "close": float(c), "adjclose": float(a)}} for dd, c, a in zip(days, close, adj)]


def _vix_rows(days, level):
    return [{"available_at": dd + "T21:30:00+00:00", "value": {"day": dd, "close": float(x)}} for dd, x in zip(days, level)]


def _fridays(q: str, lo: int, hi: int) -> list:
    """Trading Fridays (or the prior session when the Friday is a holiday) at lo..hi calendar days after q."""
    out = []
    for k in range(lo, hi + 1):
        x = date.fromisoformat(q) + timedelta(days=k)
        if x.weekday() == 4:
            while not is_trading_day(x):
                x -= timedelta(days=1)
            out.append(x.isoformat())
    return out


def _chain(days, close, snaps, exp_fn, kinds, price_fn, iv_fn=None, delta_vol=0.20, hs=0.01, lo=0.85, hi=1.15, step=1.0):
    """Synthetic dolt-chain rows. ``price_fn(kind, K, S, T, q) -> mid``; vendor delta from BS at ``delta_vol``; iv field
    from ``iv_fn(kind, K/S, q)`` (default ``delta_vol``)."""
    cb = dict(zip(days, close))
    rows = []
    for q in snaps:
        S = cb[q]
        K = np.arange(step * math.ceil(lo * S / step), hi * S + 1e-9, step)
        for e in exp_fn(q):
            T = (date.fromisoformat(e) - date.fromisoformat(q)).days / 365.0
            for kind in kinds:
                m = price_fn(kind, K, S, T, q)
                dl = bs.greeks(S, K, T, 0.0, delta_vol, kind)["delta"]
                iv = iv_fn(kind, K / S, q) if iv_fn else np.full(K.size, delta_vol)
                for k, mm, dd, vv in zip(K, m, dl, iv):
                    rows.append({"available_at": q + "T22:00:00+00:00",
                                 "value": {"symbol": "SPY", "snapshot_date": q, "quote_date": q, "expiry": e,
                                           "strike": float(k), "type": kind, "bid": round(float(mm) - hs, 4),
                                           "ask": round(float(mm) + hs, 4), "iv": float(vv), "delta": float(dd),
                                           "stale": False}})
    return rows


def _fair(vol):
    def f(kind, K, S, T, q):
        return np.asarray(bs.price(S, K, T, 0.0, vol, kind), dtype=float)
    return f


def _marked(vol, kind_m, cond, amount):
    """Fair BS mids plus ``amount`` x S on ``kind_m`` legs where cond(K/S) holds."""
    def f(kind, K, S, T, q):
        p = np.asarray(bs.price(S, K, T, 0.0, vol, kind), dtype=float)
        if kind == kind_m:
            p = p + amount * S * cond(K / S)
        return p
    return f


def _mwf(days):
    return [x for x in days if date.fromisoformat(x).weekday() in (0, 2, 4)]


def _world(n=660, vol=0.20, seed=0, mu_day=0.0, kinds=("call",), price_fn=None, exp=(53, 67), snaps="mwf",
           vix_spike=True, iv_fn=None):
    days = _sessions("2020-01-02", n)
    close = _gbm(n, vol, seed, mu_day)
    sn = _mwf(days) if snaps == "mwf" else days
    rows = _chain(days, close, sn, lambda q: _fridays(q, *exp), kinds, price_fn or _fair(vol), iv_fn=iv_fn)
    vix = np.full(n, 20.0)
    if vix_spike:
        vix[n // 3] = 45.0
    return {d.CHAIN_B: rows, d.SPY_B: _spy_rows(days, close), d.VIX_B: _vix_rows(days, vix)}


def _check_out(out, claim_name):
    stat, n, v, reason = out
    json.dumps(stat)
    assert v in ("supported", "not_supported", "inconclusive")
    assert " — " in reason
    assert reason.rsplit(" — ", 1)[1].startswith(("all criteria pass", "failed:", "implemented criteria pass",
                                                  "not implemented"))
    assert claim_name in reason
    return stat, n, v, reason


# ------------------------------------------------------------------------------------------------ statistics --

def test_cluster_mean_ci_planted_passes_null_does_not():
    rng = np.random.default_rng(1)
    days = _sessions("2020-01-02", 500)
    planted = rng.normal(0.4, 1.0, 500)
    S, N = d.week_clusters(days, planted)
    lo, hi = d.cluster_mean_ci(S, N, 4, n_boot=NB)
    assert lo > 0 and hi > lo
    null = rng.normal(0.0, 1.0, 500)
    S, N = d.week_clusters(days, null)
    lo, hi = d.cluster_mean_ci(S, N, 4, n_boot=NB)
    assert lo < 0 < hi
    assert d.cluster_mean_ci(S[:5], N[:5], 2) == (None, None)        # too few clusters


def test_week_clusters_keep_empty_weeks():
    S, N = d.week_clusters(["2020-01-06", "2020-01-08", "2020-01-27"], [1.0, 2.0, 5.0])
    assert list(N) == [2, 0, 0, 1]
    assert list(S) == [3.0, 0.0, 0.0, 5.0]


def test_cluster_diff_ci_planted_passes_null_does_not():
    rng = np.random.default_rng(2)
    C = 60
    Nt, Nb = rng.integers(1, 4, C).astype(float), rng.integers(1, 4, C).astype(float)
    St = Nt * 0.8 + rng.normal(0, 0.5, C) * np.sqrt(Nt)
    Sb = Nb * 0.0 + rng.normal(0, 0.5, C) * np.sqrt(Nb)
    r = d.cluster_diff_ci(St, Nt, Sb, Nb, 2, n_boot=NB)
    assert r["diff"] > 0 and r["ci"][0] > 0
    Sb2 = Nb * 0.8 + rng.normal(0, 0.5, C) * np.sqrt(Nb)
    r = d.cluster_diff_ci(St, Nt, Sb2, Nb, 2, n_boot=NB)
    assert r["ci"][0] < 0 < r["ci"][1]


def test_pooled_mean_test_sides_robustness_and_decisive():
    rng = np.random.default_rng(3)
    days = _sessions("2019-01-02", 900)
    neg = rng.normal(-0.5, 1.0, 900)
    p = d.pooled_mean_test(days, neg, 30, -1, n_boot=NB)
    assert p["ok"] is True and p["decisive_fail"] is False
    assert [r["block_weeks"] for r in p["by_block"]] == [9, 18]      # ceil(2 x 30 / 7), ceil(4 x 30 / 7)
    q = d.pooled_mean_test(days, -neg, 30, -1, n_boot=NB)             # wrong side: fails decisively
    assert q["ok"] is False and q["decisive_fail"] is True
    z = d.pooled_mean_test(days, rng.normal(0, 1.0, 900), 30, 1, n_boot=NB)
    assert z["ok"] is not True and z["decisive_fail"] is False
    assert d._robust([True, False]) is None and d._robust([True, True]) is True and d._robust([False, None]) is None


def test_week_weighted_equalises_cadence():
    days = ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10", "2020-01-13"]
    w = d.week_weighted(days, [1, 1, 1, 1, 1, -1], 7, n_boot=NB)
    assert w["mean"] == pytest.approx(0.0)                            # two weeks: mean 1 and mean -1
    assert w["n_weeks"] == 2


def test_decide_rule5_below_min_n():
    v, why = d._decide([("crit", False, False)], 10, 250, "entry days")
    assert v == "inconclusive" and "not decisively" in why
    v, why = d._decide([("crit", False, True)], 10, 250, "entry days")
    assert v == "not_supported"
    v, _ = d._decide([("crit", True, False)], 10, 250, "entry days")
    assert v == "inconclusive"                                       # never supported below min_n
    v, _ = d._decide([("crit", True, False)], 300, 250, "entry days")
    assert v == "supported"
    v, _ = d._decide([("crit", False, False)], 300, 250, "entry days")
    assert v == "not_supported"


# ------------------------------------------------------------------------------------- data access, selectors --

def test_closes_from_rows_drops_possibly_open_bar_and_reads_dividends():
    days = ["2024-03-13", "2024-03-14", "2024-03-15", "2024-03-18"]
    close = np.array([500.0, 501.0, 499.0, 502.0])
    adj = close * np.array([0.99, 0.99, 1.0, 1.0])                    # ex-date 2024-03-15
    rows = _spy_rows(days, close, adj)
    dd, c, a = d.closes_from_rows(rows, created="2024-03-18T08:00:00+00:00")
    assert dd == days[:3]                                            # the capture-day bar is dropped
    dd, c, a = d.closes_from_rows(rows, created="2024-03-18T22:00:00+00:00")
    assert dd == days
    ev = d.dividend_events(dd, c, a)
    assert len(ev) == 1 and ev[0][0] == "2024-03-15"
    assert ev[0][1] == pytest.approx(501.0 * (1 - 0.99))


def _day(q, spot, exp):
    return {"quote_date": q, "snapshot_date": q, "stale": False, "spot": spot, "exp": exp}


def _leg(k, bid, ask, delta, iv=0.2):
    return {"strike": float(k), "bid": bid, "ask": ask, "delta": delta, "iv": iv}


def test_pick_expiry_tolerance_ties_and_allowed():
    day = _day("2024-01-02", 100.0, {"2024-02-09": {}, "2024-02-16": {}, "2024-03-01": {}})
    assert d.pick_expiry(day, 45, 7) == "2024-02-16"                 # 45 DTE exactly
    assert d.pick_expiry(day, 60, 7) == "2024-03-01"                 # 59 DTE
    day2 = _day("2024-01-02", 100.0, {"2024-02-09": {}, "2024-02-23": {}})
    assert d.pick_expiry(day2, 45, 7) == "2024-02-23"                # 38 vs 52 DTE: tie goes to the longer-dated
    assert d.pick_expiry(day2, 60, 7) is None                        # 52 DTE is 8 off 60
    assert d.pick_expiry(day2, 45, 7, allowed={"2024-02-09"}) == "2024-02-09"


def test_pick_delta_moneyness_and_usable():
    legs = [_leg(90, 0.5, 0.6, -0.12), _leg(95, 1.0, 1.1, -0.21), _leg(98, 0.0, 1.5, -0.41), _leg(99, 2.0, 2.1, -0.46)]
    assert d.pick_delta(legs, 0.20)["strike"] == 95
    assert d.pick_delta(legs, 0.40)["strike"] == 99                  # 98 has no bid: unusable
    assert d.pick_delta(legs, 0.70) is None                          # beyond the tolerance
    assert d.pick_moneyness(legs, 100.0, 0.95, 0.02)["strike"] == 95
    assert d.pick_moneyness(legs, 100.0, 0.80, 0.02) is None
    assert d.iv_at([_leg(104, 1, 1, 0.3, 0.20), _leg(106, 1, 1, 0.2, 0.22)], 100.0, 1.05) == pytest.approx(0.21)


def test_monthly_expiries_follow_holidays():
    m = d.monthly_expiries(2022, 2022)
    assert "2022-04-14" in m and "2022-04-15" not in m               # Good Friday: the prior session
    assert "2022-03-18" in m and len(m) == 12


def test_chain_days_dedupes_quote_days():
    def row(snap, quote, k, stale=False):
        return {"available_at": snap + "T22:00:00+00:00",
                "value": {"snapshot_date": snap, "quote_date": quote, "expiry": "2024-02-16", "strike": k, "type": "put",
                          "bid": 1.0, "ask": 1.1, "iv": 0.2, "delta": -0.3, "stale": stale}}
    rows = [row("2024-01-06", "2024-01-05", 90.0), row("2024-01-05", "2024-01-05", 91.0),
            row("2024-01-09", "2024-01-08", 92.0, stale=True), row("2024-01-10", "2024-01-10", 93.0)]
    ch, info = d.chain_days(rows, {"2024-01-05": 100.0, "2024-01-08": 101.0, "2024-01-10": 102.0})
    assert sorted(ch) == ["2024-01-05", "2024-01-08", "2024-01-10"]
    assert ch["2024-01-05"]["snapshot_date"] == "2024-01-05"         # the quote day's own snapshot wins
    assert ch["2024-01-08"]["stale"] and ch["2024-01-08"]["spot"] == 101.0
    assert info["duplicate_snapshots_dropped"] == 1 and info["moved_stale_kept"] == 1


# ----------------------------------------------------------------------------------- structures, settlement --

def _trade(legs, spot=100.0, entry="2024-01-02", expiry="2024-03-01", **kw):
    return {"entry": entry, "expiry": expiry, "dte": 59, "spot": spot, "legs": legs, **kw}


def _tl(kind, k, qty, bid, ask, iv=0.2):
    return {"kind": kind, "strike": float(k), "qty": qty, "bid": bid, "ask": ask, "mid": 0.5 * (bid + ask), "iv": iv,
            "delta": None}


def test_backspread_credit_payoff_and_max_loss():
    t = _trade([_tl("call", 100, -1, 4.0, 4.2), _tl("call", 108, 2, 1.0, 1.1)])
    assert d.net_credit(t, "mid") == pytest.approx(4.1 - 2 * 1.05)
    assert d.net_credit(t, "exec") == pytest.approx(4.0 - 2 * 1.1)
    assert d.backspread_max_loss(t, "mid") == pytest.approx(8 - 2.0)
    for s, pay in ((95, 0.0), (104, -4.0), (108, -8.0), (120, -20 + 24)):
        assert d.payoff(t, s) == pytest.approx(pay)
    m = d.backspread_metrics(dict(t, s_t=108.0))
    assert m["mid"]["ratio"] == pytest.approx(-1.0)                  # the max loss is realised at S_T = K2
    assert m["upper_be"] == pytest.approx(108 + 8 - 2.0)


def test_naked_put_margin_reg_t():
    leg = _tl("put", 90, -2, 1.0, 1.2)
    assert d.naked_put_margin(leg, 100.0, "mid") == pytest.approx(1.1 + max(20 - 10, 9.0))
    assert d.naked_put_margin(leg, 100.0, "exec") == pytest.approx(1.0 + 10.0)
    far = _tl("put", 70, -1, 0.1, 0.2)
    assert d.naked_put_margin(far, 100.0, "mid") == pytest.approx(0.15 + 7.0)   # 10% of the strike floor


def test_front_ratio_and_ladder_builders_pick_by_delta():
    puts = [_leg(k, 1.0, 1.1, dl) for k, dl in ((85, -0.10), (88, -0.15), (91, -0.20), (94, -0.25), (97, -0.40),
                                                  (100, -0.50))]
    day = _day("2024-01-02", 100.0, {"2024-02-16": {"put": puts, "call": []}})
    t, why = d.front_ratio_trade(day)
    assert why is None and [(l["strike"], l["qty"]) for l in t["legs"]] == [(97, 1), (91, -2)]
    t, why = d.ladder_trade(day)
    assert [(l["strike"], l["qty"]) for l in t["legs"]] == [(97, 1), (94, -1), (88, -1)] and t["naked"] == 2
    t, why = d.front_ratio_trade(_day("2024-01-02", 100.0, {"2024-03-29": {"put": puts, "call": []}}))
    assert t is None and "DTE" in why


def test_early_exercise_rule_and_payoff():
    assert d.exercise_early(110.0, 100.0, 2.0, 1 / 365, 0.2)         # deep ITM the day before: exercise
    assert not d.exercise_early(101.0, 100.0, 2.0, 30 / 365, 0.2)    # time value exceeds the dividend
    assert not d.exercise_early(99.0, 100.0, 2.0, 1 / 365, 0.2)      # OTM
    t = _trade([_tl("call", 100, -1, 4.0, 4.2)], entry="2024-02-01", expiry="2024-03-15")
    days = ["2024-03-13", "2024-03-14", "2024-03-15"]
    cb = {"2024-03-13": 109.0, "2024-03-14": 110.0, "2024-03-15": 108.5}
    pe = d.early_exercise_payoff(t, 108.5, [("2024-03-15", 1.5)], days, cb)
    assert pe == pytest.approx(-10.0)                                # assigned at the cum close (110 - 100)
    assert d.payoff(t, 108.5) == pytest.approx(-8.5)


def test_resolve_and_start_chains():
    tr = [{"entry": e, "expiry": x} for e, x in (("2024-01-02", "2024-02-02"), ("2024-01-10", "2024-02-09"),
                                                 ("2024-02-02", "2024-03-01"), ("2024-02-12", "2024-03-15"),
                                                 ("2024-03-04", "2024-04-05"))]
    ch = d.start_chains(tr, 30)
    assert ch[0] == [0, 2, 4] and ch[1] == [1, 3]                     # next entry on or after the previous expiry
    res, cnt = d.resolve([dict(t) for t in tr], {"2024-02-02": 1.0, "2024-03-01": 2.0}, "2024-03-05")
    assert [t["expiry"] for t in res] == ["2024-02-02", "2024-03-01"]
    assert sum(cnt.values()) == 3


def test_stress_hits_and_drawdown_months():
    tr = [{"entry": "2020-02-03", "expiry": "2020-03-20"}, {"entry": "2020-05-01", "expiry": "2020-06-19"}]
    assert d.stress_hits(tr, ["2020-03-16", "2020-04-10", "2020-07-01"]) == ["2020-03"]
    assert d.stress_hits(tr, []) == []
    days = _sessions("2020-01-02", 40)
    c = np.r_[np.full(20, 100.0), np.full(20, 85.0)]
    assert d.drawdown_months(days, c) == sorted({x[:7] for x in days[20:]})


# -------------------------------------------------------------------------------------------- T-173 core --

def _quartile_trades(n_coh=40, per=6, effect=0.01, seed=0):
    rng = np.random.default_rng(seed)
    trades, x, sig = [], [], []
    for c in range(n_coh):
        coh = (date(2020, 1, 17) + timedelta(days=28 * c)).isoformat()
        for j in range(per):
            u = rng.normal()
            trades.append({"cohort": coh, "entry": (date.fromisoformat(coh) - timedelta(days=30 - j)).isoformat(),
                           "dte": 30 - j})
            sig.append(u)
            x.append(effect * u + rng.normal(0, 0.01))
    return trades, np.array(x), np.array(sig)


def test_quartile_claim_planted_passes_null_does_not():
    tr, x, s = _quartile_trades(effect=0.01)
    q = d.quartile_claim(tr, x, s, min_n=24, n_boot=NB)
    assert q["n"] == 40 and q["ok"] is True and q["diff"] > 0
    tr, x, s = _quartile_trades(effect=0.0, seed=5)
    q = d.quartile_claim(tr, x, s, min_n=24, n_boot=NB)
    assert q["ok"] is not True
    tr, x, s = _quartile_trades(effect=-0.01, seed=6)
    q = d.quartile_claim(tr, x, s, min_n=24, n_boot=NB)
    assert q["ok"] is False and q["decisive_fail"] is True


def test_expanding_labels_are_point_in_time():
    tr, x, s = _quartile_trades(n_coh=20, per=3)
    top, bot = d.expanding_labels(tr, s, min_cohorts=12)
    s2 = s.copy()
    s2[-3:] = [100.0, -100.0, 0.0]                                    # change only the last cohort's signals
    top2, bot2 = d.expanding_labels(tr, s2, min_cohorts=12)
    assert (top[:-3] == top2[:-3]).all() and (bot[:-3] == bot2[:-3]).all()
    assert not top[:11 * 3 + 1].any() and not bot[:11 * 3 + 1].any()  # no label before 12 cohorts of history
    assert (top | bot)[11 * 3 + 1:].any()


def test_drop_influential_removes_the_favourable_cohort():
    tr, x, s = _quartile_trades(effect=0.0, seed=8)
    q1, q3 = np.quantile(s, [0.25, 0.75])
    top, bot = s >= q3, s <= q1
    first_bot = int(np.nonzero(bot)[0][0])
    x[first_bot] = -1.0                                                # one huge loss in the bottom group
    r = d.drop_influential(tr, x, top, bot, k=1)
    assert r["dropped"] == [tr[first_bot]["cohort"]]


# --------------------------------------------------------------------------------------------- harnesses --

def test_missing_bundles_inconclusive():
    for name, fn in d.HARNESSES.items():
        stat, n, v, reason = fn(FakeArchive({}))
        assert v == "inconclusive" and n == 0 and "missing data bundles" in reason
        json.dumps(stat)
    assert set(d.THEORY_MAP.values()) == set(d.HARNESSES)
    assert all(h.startswith("b6b_dolt_") for h in d.HARNESSES)


def test_t119_planted_overpriced_wing_supported():
    # fair BS world, but the long OTM calls (K/S > 1.04) are quoted 1% of S rich: the backspread loses
    b = _world(price_fn=_marked(0.20, "call", lambda m: m > 1.04, 0.01))
    stat, n, v, reason = _check_out(d.b6b_dolt_backspread(FakeArchive(b)), "T-119")
    assert n >= 250 and v == "supported", reason
    assert stat["pooled_mid"]["by_block"][0]["ci"][1] < 0
    assert stat["credit_share_mid"] is not None and "per start" in reason


def test_t119_null_fair_prices_not_supported():
    b = _world(seed=11)
    stat, n, v, reason = _check_out(d.b6b_dolt_backspread(FakeArchive(b)), "T-119")
    assert n >= 250 and v == "not_supported", reason
    assert stat["pooled_mid"]["by_block"][0]["ci"][0] < 0 < stat["pooled_mid"]["by_block"][0]["ci"][1]


def test_t119_reversed_effect_and_below_min_n():
    b = _world(price_fn=_marked(0.20, "call", lambda m: m > 1.04, -0.004))   # cheap wings: the backspread wins
    stat, n, v, reason = d.b6b_dolt_backspread(FakeArchive(b))
    assert v == "not_supported"
    short = _world(n=300, price_fn=_marked(0.20, "call", lambda m: m > 1.04, 0.01))
    stat, n, v, reason = d.b6b_dolt_backspread(FakeArchive(short))
    assert n < 250 and v == "inconclusive"                            # rule 5: never supported below min_n


def _put_world(amount, seed=0, vix_spike=True, n=660):
    # fair BS world; puts with K/S < 0.955 (the short legs) quoted ``amount`` x S rich (planted) or not (null)
    pf = _marked(0.20, "put", lambda m: m < 0.955, amount) if amount else _fair(0.20)
    return _world(n=n, seed=seed, kinds=("put",), price_fn=pf, exp=(38, 52), vix_spike=vix_spike)


def test_t121_planted_rich_short_puts_supported():
    stat, n, v, reason = _check_out(d.b6b_dolt_put_front_ratio(FakeArchive(_put_world(0.012))), "T-121")
    assert n >= 250 and v == "supported", reason
    assert stat["pooled_exec"]["by_block"][0]["ci"][0] > 0
    assert stat["stress_months_in_sample"] and "Reg-T" in reason


def test_t121_null_fair_prices_not_supported():
    stat, n, v, reason = _check_out(d.b6b_dolt_put_front_ratio(FakeArchive(_put_world(0.0, seed=3))), "T-121")
    assert v == "not_supported", reason


def test_t121_without_stress_capped_at_inconclusive():
    stat, n, v, reason = d.b6b_dolt_put_front_ratio(FakeArchive(_put_world(0.012, vix_spike=False)))
    assert v == "inconclusive" and stat["stress_months_in_sample"] == []
    assert "stress month in the sample" in reason


def test_t539_planted_supported_and_null_not():
    stat, n, v, reason = _check_out(d.b6b_dolt_put_ladder(FakeArchive(_put_world(0.012))), "T-539")
    assert n >= 250 and v == "supported", reason
    assert "15-delta put" in reason
    stat, n, v, reason = _check_out(d.b6b_dolt_put_ladder(FakeArchive(_put_world(0.0, seed=4))), "T-539")
    assert v == "not_supported", reason


def _overlay_world(planted: bool, seed=0, n=660, persist=0.95, step=1.0):
    """Daily snapshots, the monthly expiry at 20-40 DTE, calls at K/S 0.95-1.15 every ``step`` dollars. Vendor call IV
    slope per day u_q, an AR(1) with coefficient ``persist`` (a persistent skew, so the prior slope carries the signal;
    0 = an independent draw each day); calls at K/S in [1.02, 1.08) quoted 1% x S x Phi(z) rich, z = u_q (planted) or
    an independent draw (null). Realised vol 8% vs pricing vol 20%, so the spread's payoff noise is small."""
    rng = np.random.default_rng(100 + seed)
    days = _sessions("2020-01-02", n)
    close = _gbm(n, 0.08, seed)
    u, prev = {}, rng.normal()
    for q in days:
        prev = persist * prev + math.sqrt(1.0 - persist ** 2) * rng.normal()
        u[q] = prev
    z = u if planted else {q: rng.normal() for q in days}
    monthly = d.monthly_expiries(2020, 2023)

    def exp_fn(q):
        return [e for e in monthly if 20 <= (date.fromisoformat(e) - date.fromisoformat(q)).days <= 40]

    def price_fn(kind, K, S, T, q):
        p = np.asarray(bs.price(S, K, T, 0.0, 0.20, kind), dtype=float)
        phi = 0.5 * (1 + math.erf(z[q] / math.sqrt(2)))
        return p + 0.01 * S * phi * ((K / S >= 1.02) & (K / S < 1.08))

    def iv_fn(kind, m, q):
        return 0.20 + 0.3 * u[q] * (m - 1.0)

    rows = _chain(days, close, days, exp_fn, ("call",), price_fn, iv_fn=iv_fn, lo=0.95, hi=1.15, step=step)
    return {d.CHAIN_B: rows, d.SPY_B: _spy_rows(days, close)}


def test_t173_planted_supported_null_not():
    stat, n, v, reason = _check_out(d.b6b_dolt_ratio_overlay_skew(FakeArchive(_overlay_world(True))), "T-173")
    assert n >= 24 and v == "supported", reason
    assert stat["diff_mid"] > 0 and "fragility" in reason and "point-in-time" in reason
    assert len(stat["readings"]) == 4 and all(stat["decision"]["cells"].values())
    d._CACHE.clear()
    stat, n, v, reason = _check_out(d.b6b_dolt_ratio_overlay_skew(FakeArchive(_overlay_world(False, seed=1))), "T-173")
    assert v != "supported", reason


def test_t173_rule12_previous_close_reading_must_agree():
    # regression (reviewer, T-173 rule 12): the archive stamps the entry-day chain after the fill, so the prior-slope
    # claim is also read from the last capture known before the entry close. Here the skew does not persist (a fresh
    # slope every day) and the rich quotes follow the SAME day's slope: the entry-close live proxy passes, the
    # previous-capture reading does not, so the criterion is undecided and the claim is not supported.
    stat, n, v, reason = _check_out(d.b6b_dolt_ratio_overlay_skew(FakeArchive(_overlay_world(True, persist=0.0))),
                                    "T-173")
    cells = stat["decision"]["cells"]
    assert cells["entry close (live proxy), exact 5%/10% OTM"] is True
    assert cells["entry close (live proxy), nearest listed strike"] is True
    assert cells["previous capture, exact 5%/10% OTM"] is not True
    assert cells["previous capture, nearest listed strike"] is not True
    assert v != "supported" and stat["decision"]["ok"] is not True, reason
    assert "previous capture" in reason and "calendar days before the entry" in reason


def test_prev_capture_uses_only_rows_known_before_the_fill():
    ch = {"2024-01-03": {"quote_date": "2024-01-03", "available_at": "2024-01-03T22:00:00+00:00"},
          "2024-01-05": {"quote_date": "2024-01-05", "available_at": "2024-01-08T22:00:00+00:00"},   # moved, stamped late
          "2024-01-08": {"quote_date": "2024-01-08", "available_at": "2024-01-08T22:00:00+00:00"}}
    qd = sorted(ch)
    assert d.prev_capture(ch, qd, "2024-01-08")["quote_date"] == "2024-01-03"   # 01-05 was stamped after the 01-08 fill
    assert d.prev_capture(ch, qd, "2024-01-09")["quote_date"] == "2024-01-08"
    assert d.prev_capture(ch, qd, "2024-01-03") is None                          # its own capture is stamped after the fill


def test_mix_legs_prices_the_exact_moneyness():
    # regression (reviewer, T-173 rule 1): the nearest listed strike on a ~2%-of-S grid can sit 3.7-6.2% OTM; the exact
    # construction mixes the two bracketing usable strikes so the average strike is exactly the claim's target
    legs = [_leg(k, 1.0, 1.1, 0.3) for k in (100, 103.5, 107, 109.5, 111)] + [_leg(113, 0.0, 0.1, 0.1)]
    m = d.mix_legs(legs, 105.0, 6.0)
    assert [l["strike"] for l, _ in m] == [103.5, 107.0]
    assert sum(w for _, w in m) == pytest.approx(1.0)
    assert sum(w * l["strike"] for l, w in m) == pytest.approx(105.0)
    assert d.pick_moneyness(legs, 100.0, 1.05, 0.02)["strike"] == 103.5         # nearest: 3.5% OTM
    assert d.mix_legs(legs, 107.0, 6.0) == [(legs[2], 1.0)]                      # on a strike: weight 1
    assert d.mix_legs(legs, 112.0, 6.0) is None                                   # 113 has no bid: no upper bracket
    assert d.mix_legs(legs, 105.0, 3.0) is None                                   # bracket wider than the gap
    calls = [_leg(k, 1.0, 1.1, 0.3, 0.2) for k in (100, 103.5, 107, 109.5, 111)]
    day = _day("2024-01-02", 100.0, {"2024-02-01": {"call": calls, "put": []}})
    t, why = d.overlay_trade(day, {"2024-02-01"}, moneyness="exact")
    assert why is None and t["k5"] == pytest.approx(105.0) and t["k10"] == pytest.approx(110.0)
    assert sum(l["qty"] for l in t["legs"]) == pytest.approx(0.0)                 # short 1 unit, long 1 unit
    t2, _ = d.overlay_trade(day, {"2024-02-01"})
    assert t2["k5"] == 103.5 and t2["k10"] == 109.5


def _offgrid_world(seed=0, n=660, step=2.5, amount=0.01, vol=0.30, persist=0.95):
    """A 2.5%-of-S strike grid where the listed strike NEAREST 1.05 S is quoted rich by 2 x m x w_far and the other
    bracketing strike cheap by 2 x m x w_near (m = amount x S x Phi(u_q), u_q the persistent vendor-slope factor), so the
    strike-weighted mixture at exactly 1.05 S carries no markup: a planted effect at the nearest strike only."""
    rng = np.random.default_rng(300 + seed)
    days = _sessions("2020-01-02", n)
    close = _gbm(n, 0.08, seed)
    u, prev = {}, rng.normal()
    for q in days:
        prev = persist * prev + math.sqrt(1.0 - persist ** 2) * rng.normal()
        u[q] = prev
    monthly = d.monthly_expiries(2020, 2023)

    def exp_fn(q):
        return [e for e in monthly if 20 <= (date.fromisoformat(e) - date.fromisoformat(q)).days <= 40]

    def price_fn(kind, K, S, T, q):
        p = np.asarray(bs.price(S, K, T, 0.0, vol, kind), dtype=float)
        tgt = 1.05 * S
        lo, hi = K[K <= tgt].max(), K[K >= tgt].min()
        if hi == lo:
            return p
        wlo = (hi - tgt) / (hi - lo)
        near_lo = tgt - lo <= hi - tgt
        wn, wf = (wlo, 1 - wlo) if near_lo else (1 - wlo, wlo)
        if wn > 0.8:
            return p
        m = amount * S * 0.5 * (1 + math.erf(u[q] / math.sqrt(2)))
        kn, kf = (lo, hi) if near_lo else (hi, lo)
        out = p.copy()
        out[K == kn] += 2 * m * wf
        out[K == kf] -= 2 * m * wn
        return p if out[K == kf][0] < 0.05 else out

    def iv_fn(kind, mm, q):
        return 0.20 + 0.3 * u[q] * (mm - 1.0)

    rows = _chain(days, close, days, exp_fn, ("call",), price_fn, iv_fn=iv_fn, lo=0.95, hi=1.15, step=step)
    return {d.CHAIN_B: rows, d.SPY_B: _spy_rows(days, close)}


def test_t173_rule1_exact_moneyness_must_agree_with_nearest_strike():
    # regression (reviewer, T-173 rule 1): on a coarse grid the nearest listed strike is not 5% OTM; an effect that lives
    # only at the nearest strike passes that reading but not the claim's exact 5%-OTM moneyness, so it is not supported
    stat, n, v, reason = _check_out(d.b6b_dolt_ratio_overlay_skew(FakeArchive(_offgrid_world())), "T-173")
    cells = stat["decision"]["cells"]
    assert cells["entry close (live proxy), nearest listed strike"] is True
    assert cells["entry close (live proxy), exact 5%/10% OTM"] is not True
    assert v != "supported", reason
    assert stat["n_off_band_short"] > 0 and stat["k5_over_s"]["min"] < 1.045 < 1.055 < stat["k5_over_s"]["max"]
    assert "K5/S" in reason and "more than 1% of S off target" in reason


def test_judge_cells_needs_every_reading_to_pass():
    tr, x, s = _quartile_trades(effect=0.01)
    good = d.quartile_claim(tr, x, s, min_n=24, n_boot=NB)
    tr0, x0, s0 = _quartile_trades(effect=0.0, seed=5)
    null = d.quartile_claim(tr0, x0, s0, min_n=24, n_boot=NB)
    trn, xn, sn = _quartile_trades(effect=-0.01, seed=6)
    bad = d.quartile_claim(trn, xn, sn, min_n=24, n_boot=NB)
    assert good["ok"] is True and null["ok"] is not True and bad["ok"] is False
    assert d.judge_cells({"a": good, "b": good})[0] is True
    assert d.judge_cells({"exact": null, "nearest": good})[0] is None             # disagreement: undecided
    assert d.judge_cells({"a": good, "b": bad})[0] is None
    ok, dec, n = d.judge_cells({"a": bad, "b": bad})
    assert ok is False and dec is True and n == 40


def test_t173_below_min_n_never_supported():
    stat, n, v, reason = d.b6b_dolt_ratio_overlay_skew(FakeArchive(_overlay_world(True, n=330)))
    assert n < 24 and v == "inconclusive"


def test_late_stamped_snapshots_flagged_and_reported():
    legs = [_leg(k, 1.0, 1.1, dl) for k, dl in ((91, -0.20), (97, -0.40))]
    sat = {"quote_date": "2019-03-01", "snapshot_date": "2019-03-02", "stale": False, "spot": 100.0,
           "available_at": "2019-03-02T22:00:00+00:00", "exp": {"2019-04-12": {"put": legs, "call": []}}}
    t, _ = d.front_ratio_trade(sat)
    assert t["late_stamp"] is True                                   # a Saturday snapshot of Friday's close
    own = dict(sat, snapshot_date="2019-03-01", available_at="2019-03-01T22:00:00+00:00")
    t, _ = d.front_ratio_trade(own)
    assert t["late_stamp"] is False
    stat, n, v, reason = d.b6b_dolt_put_front_ratio(FakeArchive(_put_world(0.012)))
    assert stat["snapshot_date_sensitivity"]["n_dropped"] == 0 and "snapshot-date sensitivity" in reason


def test_snapshot_date_sensitivity_is_not_labelled_point_in_time():
    # regression (reviewer, T-119/T-121/T-173/T-539): every chain row is stamped 22:00Z on its snapshot date, after the
    # 16:15 ET fill, so dropping weekend/holiday/moved snapshots does not leave point-in-time entries; the reason must say
    # every entry is an entry-close live proxy and must not call the variant a strict available_at sensitivity
    for fn, b in ((d.b6b_dolt_put_ladder, _put_world(0.012)), (d.b6b_dolt_backspread, _world(seed=11)),
                  (d.b6b_dolt_ratio_overlay_skew, _overlay_world(True))):
        d._CACHE.clear()
        stat, n, v, reason = fn(FakeArchive(b))
        assert "strict available_at" not in reason and "strict_available_at" not in stat
        assert "snapshot-date sensitivity" in reason and "live proxy" in reason and "22:00Z" in reason
        assert "snapshot_date_sensitivity" in stat
