"""Batch-6c pub harnesses (T-405 COMEX gold COT extremes, T-442 Treasury auction cycle, T-472 PHYS discount reversion,
T-404 GLD holdings flows) on synthetic data only: for every core function a planted effect passes and a null does not;
the COT point-in-time statuses (backcasts, windows needing them, superseded catch-ups), the release-to-open alignment,
the auction filter and weekly clusters, the flags-fixed null and placements, the Sprott next-close timing and costs,
the block-shift null, the SPDR t+1 holdings, the Granger and chi-square helpers and the rule-5 paths are checked
directly; every harness runs JSON-safe on a fake archive, and missing bundles give inconclusive. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_pub as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "T442_BOOT", 300)
    monkeypatch.setattr(m, "T442_N_PLACE", 200)
    monkeypatch.setattr(m, "REPS_MAX_442", 3)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def px_of(days, closes, opens=None):
    c = np.asarray(closes, float)
    o = c.copy() if opens is None else np.asarray(opens, float)
    return {"days": list(days), "close": c.copy(), "adj": c.copy(), "open": o}


def walk(n, mu=0.0002, sd=0.008, seed=0, start=100.0):
    r = np.random.default_rng(seed).normal(mu, sd, n)
    return start * np.cumprod(1 + r)


def et_iso(day, hhmm):
    return datetime.fromtimestamp(m.et_epoch(day, hhmm), tz=timezone.utc).isoformat()


def tuesdays(start, end):
    d = date.fromisoformat(start)
    while d.weekday() != 1:
        d += timedelta(days=1)
    out = []
    while d.isoformat() <= end:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def cot_row(rd, x, av, pit="schedule", oi=100000.0):
    return {"available_at": av, "value": {"report_date": rd, "m_money_positions_long_all": str(oi * (0.5 + x / 2)),
                                          "m_money_positions_short_all": str(oi * (0.5 - x / 2)), "open_interest_all": str(oi),
                                          "pit": pit, "release_rule": av}}


def friday_release(rd):
    return et_iso((date.fromisoformat(rd) + timedelta(days=3)).isoformat(), "15:30")


# ======================================================================================== small pieces ==

def test_chi2_sf_closed_forms():
    for x in (0.5, 2.0, 7.3, 20.0):
        assert m.chi2_sf(x, 2) == pytest.approx(math.exp(-x / 2), rel=1e-9)
        assert m.chi2_sf(x, 4) == pytest.approx(math.exp(-x / 2) * (1 + x / 2), rel=1e-9)
    assert m.chi2_sf(0.0, 4) == 1.0


def test_granger_detects_lead_only_one_way():
    rng = np.random.default_rng(1)
    b = rng.normal(0, 1, 1200)
    a = np.r_[0.0, 0.6 * b[:-1]] + rng.normal(0, 1, 1200)
    assert m.granger(a, b, 4)["p"] < 1e-6                     # b leads a
    assert m.granger(b, a, 4)["p"] > 0.01                     # a does not lead b


def test_et_epoch_handles_dst():
    assert m.et_epoch("2020-07-01", "09:30") - datetime(2020, 7, 1, 13, 30, tzinfo=timezone.utc).timestamp() == 0
    assert m.et_epoch("2020-01-02", "09:30") - datetime(2020, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp() == 0


# ============================================================================================ T-405 COT ==

def test_cot_weeks_point_in_time_statuses():
    rds = tuesdays("2009-06-02", "2009-12-31")
    late = (date.fromisoformat(rds[8]) + timedelta(days=4)).isoformat() + "T23:59:59+00:00"     # after row 8's release
    rows = []
    for i, rd in enumerate(rds):
        av, pit = friday_release(rd), "schedule"
        if i < 6:
            av, pit = late, "backcast"
        if i == 12:
            av = et_iso((date.fromisoformat(rds[13]) + timedelta(days=6)).isoformat(), "12:00")  # released with row 13
        if i == 13:
            av = et_iso((date.fromisoformat(rds[13]) + timedelta(days=6)).isoformat(), "12:00")
        rows.append(cot_row(rd, 0.01 * i * ((-1) ** i), av, pit))
    rows.append(cot_row("1988-01-15", 0.1, "1988-02-12T23:59:59+00:00", "not_realtime"))
    wk = m.cot_weeks(rows, win=4)
    st = {q["report_date"]: q["status"] for q in wk}
    assert "1988-01-15" not in st                                  # not_realtime rows dropped
    assert [st[rds[i]] for i in range(6)] == ["backcast"] * 6
    assert [st[rds[i]] for i in (6, 7, 8)] == ["window_not_public"] * 3
    assert st[rds[9]] == "ok" and st[rds[12]] == "superseded" and st[rds[13]] == "ok"
    q = wk[10]
    xs = np.array([w["x"] for w in wk[7:11]])
    assert q["z"] == pytest.approx((xs[-1] - xs.mean()) / xs.std(ddof=1))


def test_fwd_returns_enter_monday_open_after_friday_release():
    days = bdays("2020-01-01", "2020-03-31")
    c = np.arange(len(days), dtype=float) + 100
    px = px_of(days, c, opens=c - 0.5)
    t = m.et_epoch("2020-01-10", "15:30")                          # Friday release
    fw = m.fwd_returns(px, [t], 28, "open")
    e, x = fw["e"][0], fw["x"][0]
    assert days[e] == "2020-01-13" and days[x] == "2020-02-10"
    assert fw["ret"][0] == pytest.approx((c[x] - 0.5) / (c[e] - 0.5) - 1)
    fc = m.fwd_returns(px, [t], 28, "close")
    assert days[fc["e"][0]] == "2020-01-10"                         # the 16:00 close after a 15:30 release
    late = m.fwd_returns(px, [m.et_epoch("2020-03-20", "15:30")], 28, "open")
    assert not np.isfinite(late["ret"][0])                          # exit beyond the data


def test_t405_planted_passes():
    rng = np.random.default_rng(3)
    z = rng.normal(0, 1.4, 900)
    fwd = -0.01 * z + rng.normal(0, 0.01, 900)
    j = m.judge_cot(fwd, z, 0)
    assert j["n_short_tail"] >= 50 and j["n_long_tail"] >= 50
    assert j["boot"]["ci"][0] > 0
    assert j["verdict"] == "supported", j["why"]
    assert j["park_condition"] is False


def test_t405_null_fails():
    rng = np.random.default_rng(4)
    z = rng.normal(0, 1.4, 900)
    fwd = rng.normal(0.003, 0.03, 900)
    j = m.judge_cot(fwd, z, 0)
    assert j["verdict"] != "supported"
    assert j["verdict"] == "not_supported"                          # n >= min_n: a failing criterion counts


def test_t405_insufficient_extremes_decisive_and_park():
    rng = np.random.default_rng(5)
    z = rng.normal(0, 1.0, 900)
    z[z > 2] = 1.5
    z[:20] = 2.5                                                    # 20 weeks z > 2
    fwd = -0.01 * z + rng.normal(0, 0.01, 900)
    j = m.judge_cot(fwd, z, remaining_weeks=0)
    assert j["n_long_tail"] == 20 and j["park_condition"] is True
    assert j["verdict"] == "not_supported"                          # the count cannot reach 50: decisive below min_n
    j2 = m.judge_cot(fwd, z, remaining_weeks=200)
    assert j2["verdict"] == "inconclusive"                          # the count could still grow: never supported


def test_t405_count_decisive_uses_combined_shortfall():
    # regression: both tails short (45 / 45). Each tail alone could reach 50 in 8 weeks (45 + 8 >= 50), but a week is in
    # at most one tail, so together they need 5 + 5 = 10 > 8 more weeks: the count fails decisively below min_n.
    rng = np.random.default_rng(1)
    z = rng.normal(0, 0.5, 400)
    z[:45] = 2.5
    z[100:145] = -2.5
    fwd = rng.normal(0, 0.03, 400)
    j = m.judge_cot(fwd, z, remaining_weeks=8, reps=1)
    assert j["n_long_tail"] == 45 and j["n_short_tail"] == 45
    cnt = [c for c in j["criteria"] if c[0].startswith(">= 50 extreme weeks")][0]
    assert "need 10 more extreme weeks" in cnt[0] and "at most 8 more" in cnt[0] and "cannot reach 50" in cnt[0]
    assert cnt[1] is False and j["verdict"] == "not_supported", j["why"]
    j10 = m.judge_cot(fwd, z, remaining_weeks=10, reps=1)   # the shortfall exactly fits: not decisive
    c10 = [c for c in j10["criteria"] if c[0].startswith(">= 50 extreme weeks")][0]
    assert "need 10 more" in c10[0] and "cannot reach" not in c10[0]
    assert j10["verdict"] == "inconclusive", j10["why"]


def test_tail_diff_stat_matches_point_estimate():
    rng = np.random.default_rng(6)
    x = rng.normal(0, 1, 300)
    S = (rng.random(300) < 0.1).astype(float)
    L = ((rng.random(300) < 0.1) & (S == 0)).astype(float)
    d, se = m._tail_diff_stat(x[None, :], S[None, :], L[None, :], 8)
    assert d[0] == pytest.approx(x[S > 0].mean() - x[L > 0].mean())
    assert se[0] > 0
    d2, _ = m._tail_diff_stat(x[None, :], S[None, :], np.zeros((1, 300)), 8)
    assert np.isnan(d2[0])


# ======================================================================================== T-442 auctions ==

def auction_rows(specs):
    """specs: (date, term, nominal, reopening, held)."""
    rows = []
    for i, (d, term, nominal, reopen, held) in enumerate(specs):
        key = f"C{i}:{d}"
        ann = (date.fromisoformat(d) - timedelta(days=6)).isoformat()
        rows.append({"kind": "auction-announcement", "key": key, "available_at": ann + "T23:59:59+00:00",
                     "value": {"auction_date": d, "security_term": term, "nominal_coupon": nominal,
                               "reopening": "Yes" if reopen else "No", "cusip": f"C{i}"}})
        if held:
            rows.append({"kind": "auction-result", "key": key, "available_at": et_iso(d, "13:30"),
                         "value": {"auction_date": d, "high_yield": "4.1"}})
    return rows


def test_nominal_auctions_filter_and_clusters():
    rows = auction_rows([("2024-01-10", "10-Year", True, False, True), ("2024-01-11", "29-Year 11-Month", True, True, True),
                         ("2024-01-18", "10-Year", False, False, True),                  # TIPS: not nominal
                         ("2024-01-24", "5-Year", True, False, True),                   # 5-year
                         ("2024-02-07", "9-Year 10-Month", True, True, True),
                         ("2024-02-21", "19-Year 11-Month", True, True, True),          # 20-year reopening: not 9/10/29/30
                         ("2024-03-06", "10-Year", True, False, False)])                # not held
    au = m.nominal_auctions(rows)
    assert [(a["date"], a["fam"], a["reopening"]) for a in au] == [("2024-01-10", "10", False), ("2024-01-11", "30", True),
                                                                   ("2024-02-07", "10", True)]
    sess = [d for d in bdays("2024-01-01", "2024-03-31") if d != "2024-02-07"]
    cl = m.auction_clusters(au, sess)
    assert [c["date"] for c in cl["clusters"]] == ["2024-01-11"]   # merged, dated at the week's last auction
    assert cl["clusters"][0]["n"] == 2 and not cl["clusters"][0]["reopen_only"] and cl["clusters"][0]["ann_ok"]
    assert cl["dropped_weeks"] == [m._iso_week("2024-02-07")]       # no auction on a session that week


def _t442_world(effect, seed=7):
    days = bdays("2002-07-30")
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0002, 0.008, len(days))
    au = []
    k = 0
    months = sorted({d[:7] for d in days})
    pos = {d: i for i, d in enumerate(days)}
    for mo in months:
        wed = [d for d in days if d.startswith(mo) and date.fromisoformat(d).weekday() == 2]
        if len(wed) >= 2:
            d = wed[1]
            au.append({"date": d, "term": "10-Year", "fam": "10", "reopening": k % 3 != 0, "av": m.et_epoch(d, "00:00") - 86400 * 5,
                       "cusip": f"X{k}"})
            k += 1
            i = pos[d]
            r[i + 1:i + 4] += effect
    lv = 100 * np.cumprod(1 + r)
    return px_of(days, lv), au


def test_t442_planted_passes():
    tlt, au = _t442_world(0.0015)
    res = m.t442_study(tlt, au)
    p = res["prim"]
    assert res["n"] >= 200 and p["obs"] > 0.0015
    assert p["p_boot"] < 0.01 and p["p_place"] < 0.01
    assert res["verdict"] == "supported", res["why"]


def test_t442_null_fails():
    tlt, au = _t442_world(0.0)
    res = m.t442_study(tlt, au)
    assert res["verdict"] == "not_supported"
    assert res["prim"]["obs"] < 0.0010


def test_event_test_weights_and_placement_avoid_auction_weeks():
    tlt, au = _t442_world(0.0)
    cl = m.auction_clusters(au, tlt["days"])
    r = m.event_test({"days": tlt["days"], "lv": tlt["adj"]}, cl["clusters"], 0, 3, auction_weeks=frozenset(cl["weeks"]),
                     split=m.T442_SPLIT, n_boot=50, n_place=50, seed=1)
    a = tlt["adj"]
    pos = {d: i for i, d in enumerate(tlt["days"])}
    full = [c for c in cl["clusters"] if pos[c["date"]] + 3 < a.size]
    ev = np.array([a[pos[c["date"]] + 3] / a[pos[c["date"]]] - 1 for c in full])
    allr = a[3:] / a[:-3] - 1
    assert r["obs"] == pytest.approx(ev.mean() - allr.mean(), rel=1e-9)
    assert r["n_events"] == len(full) and r["pool_weeks"] > 500
    assert "h1" in r and "h2" in r and 0 < r["placebo"]["p_two"] <= 1
    z = m._null_draws(np.diff(np.log(a)), np.zeros((a.size - 3, 1)), 3, "price", 10, 20, 0)
    assert z.shape == (20, 1) and np.all(z == 0)


def test_t442_contrast_and_yield_variant():
    tlt, au = _t442_world(0.0)
    cl = m.auction_clusters(au, tlt["days"])["clusters"]
    r = m.event_test({"days": tlt["days"], "lv": tlt["adj"]}, cl, 0, 3, side="two", contrast=[c["reopen_only"] for c in cl],
                     n_boot=50, n_place=50)
    assert r["n_true"] + r["n_false"] == r["n_events"] >= len(cl) - 1 and 0 < r["p_boot"] <= 1 and 0 < r["p_place"] <= 1
    y = 4.0 + np.cumsum(np.random.default_rng(2).normal(0, 0.05, len(tlt["days"])))
    pos = {d: i for i, d in enumerate(tlt["days"])}
    for c in cl:
        y[pos[c["date"]] + 1:] -= 0.03                             # yields fall 3 bps the day after: sign-flipped positive
    ry = m.event_test({"days": tlt["days"], "lv": y}, cl, 0, 3, kind="yield", n_boot=100, n_place=50)
    assert ry["obs"] > 2.5 and ry["p_boot"] < 0.05


# ================================================================================ T-472 PHYS / GLD discount ==

def _t472_world(planted=True, seed=8, n_tsx=3):
    days = bdays("2010-02-25")
    rng = np.random.default_rng(seed)
    n = len(days)
    nav = 10 * np.cumprod(1 + rng.normal(0.0002, 0.01, n))
    d = -0.5 + rng.normal(0, 0.05, n)
    i = 300
    while i < n - 20:
        dip = np.linspace(-2.6, -0.3, 12)
        d[i:i + 12] = dip
        i += int(rng.integers(55, 110))
    phys = nav * (1 + d / 100) if planted else nav * (1 + rng.normal(-0.005, 0.004, n))
    sp_days = list(days)
    extra = [x for x in bdays("2012-01-01", "2026-01-01") if date.fromisoformat(x).weekday() == 0][:n_tsx]
    sp_days = sorted(set(sp_days) | set(extra))
    dv = np.array([d[days.index(x)] if x in days else -0.5 for x in sp_days])
    px_p = px_of([x for x in days if x not in extra], [p for x, p in zip(days, phys) if x not in extra])
    px_g = px_of([x for x in days if x not in extra], [g for x, g in zip(days, nav) if x not in extra])
    return sp_days, dv, px_p, px_g


def test_t472_next_close_timing():
    days = bdays("2015-01-01", "2016-12-31")
    n = len(days)
    d = np.full(n, -0.5)
    sp = list(days)
    k = days.index("2016-01-15")                                   # Friday; Monday 2016-01-18 is a TSX-only Sprott day
    px = px_of([x for x in days if x != "2016-01-18"], np.full(n - 1, 10.0))
    d[k] = -3.0                                                     # a dip on Friday only: 01-18 (back at the mean) is the
    sim = m.discount_trades(sp, d, px, px, start="2015-01-01", end="2016-12-31")   # latest value known at the 01-19 close
    assert sim["trades"] == []
    d[k + 1] = -3.0                                                 # still dipped on the TSX-only Monday
    sim = m.discount_trades(sp, d, px, px, start="2015-01-01", end="2016-12-31")
    assert sim["signal_days"][0] == "2016-01-18" and sim["entry"][0] == "2016-01-19"
    assert sim["exit"][0] == "2016-01-20"                           # 01-19 back at the mean, known by 01-20: exit at its close


def test_t472_costs_and_borrow():
    sp, dv, pp, pg = _t472_world(True)
    sim = m.discount_trades(sp, dv, pp, pg)
    k20, k40 = list(m.T472_COSTS)
    assert np.allclose(sim["net"][k20], sim["gross"] - 0.002 - 0.005 * sim["days"] / 365)
    assert np.allclose(sim["net"][k40], sim["gross"] - 0.004 - 0.005 * sim["days"] / 365)
    assert all(a >= m.T472_START and a <= m.T472_END for a in sim["entry"])
    assert all(h <= m.T472_MAX_HOLD for h in sim["sessions_held"])


def test_t472_planted_passes():
    sp, dv, pp, pg = _t472_world(True)
    sim = m.discount_trades(sp, dv, pp, pg)
    j = m.judge_discount(sim, window_closed=True)
    assert j["n"] >= 30 and j["shift"]["p"] < 0.05
    assert j["verdict"] == "supported", j["why"]


def test_t472_null_fails():
    sp, dv, pp, pg = _t472_world(False)
    sim = m.discount_trades(sp, dv, pp, pg)
    j = m.judge_discount(sim, window_closed=True)
    assert j["n"] >= 30 and j["verdict"] == "not_supported"


def test_t472_below_min_n_count_decisive():
    sp, dv, pp, pg = _t472_world(True)
    sim = m.discount_trades(sp, dv, pp, pg, start="2012-01-01", end="2014-12-31")
    assert 3 < len(sim["trades"]) < 30
    assert m.judge_discount(sim, window_closed=True)["verdict"] == "not_supported"
    assert m.judge_discount(sim, window_closed=False)["verdict"] == "inconclusive"


def test_cluster_stud_mean_and_null():
    rng = np.random.default_rng(9)
    x = rng.normal(0.01, 0.01, 60)
    labs = [f"2020-{1 + i // 5:02d}" for i in range(60)]
    b = m.cluster_stud(x, labs, 500, 0)
    assert b["ci90"][0] > 0 and b["clusters"] == 12
    y = rng.normal(0.0, 0.01, 60)
    assert m.cluster_stud(y, labs, 500, 0)["ci"][0] < 0 < m.cluster_stud(y, labs, 500, 0)["ci"][1]


# ======================================================================================== T-404 GLD flows ==

def _t404_world(beta, seed=10):
    days = bdays("2004-11-18")
    rng = np.random.default_rng(seed)
    wk = [m._iso_week(d) for d in days]
    weeks = sorted(set(wk))
    flows = {w: rng.normal(0, 5) for w in weeks}
    t, H = 100.0, []
    for d, w in zip(days, wk):
        if date.fromisoformat(d).weekday() == 2:
            t += flows[w]
        H.append(t)
    rows = [{"available_at": et_iso((date.fromisoformat(d) + timedelta(days=1)).isoformat(), "09:30"),
             "value": {"day": d, "tonnes": h}} for d, h in zip(days, H)]
    h = m.spdr_holdings(rows)
    flat = px_of(days, np.full(len(days), 100.0))
    pan = m.flow_panel(h, flat, start="1990-01-01", end="2100-01-01")
    zmap = dict(zip(pan["dates"], pan["z"]))
    wb = m.week_bounds(days)
    L = np.ones(len(wb)) * 100
    for i in range(len(wb) - 2):
        zi = zmap.get(days[wb[i][2]], 0.0)
        L[i + 2] = L[i + 1] * (1 + beta * zi + rng.normal(0, 0.02))
    lv = np.empty(len(days))
    for i, (_, f, l) in enumerate(wb):
        lv[f:l + 1] = L[i]
    return h, px_of(days, lv), rows


def test_flow_panel_uses_thursday_holdings_at_friday_close():
    days = bdays("2020-01-01", "2021-12-31")
    rows = [{"available_at": et_iso((date.fromisoformat(d) + timedelta(days=1)).isoformat(), "09:30"),
             "value": {"day": d, "tonnes": float(i)}} for i, d in enumerate(days)]
    h = m.spdr_holdings(rows)
    px = px_of(days, np.full(len(days), 100.0))
    wb = m.week_bounds(days)
    pan = m.flow_panel(h, px, start="2020-01-01", end="2021-12-31", z_weeks=3)
    # F = H(known at Friday close) - H(4 weeks earlier) = Thursday index differences: 20 sessions apart in a plain calendar
    assert np.allclose(pan["F"], 20.0)
    opn = m.flow_panel(h, px, info="open", start="2020-01-01", end="2021-12-31", z_weeks=3)
    assert np.allclose(opn["F"], 20.0)
    i = 10
    T = m.et_epoch(days[wb[i][2]], "16:00")
    k = int(np.searchsorted(h["av"], T, side="right")) - 1
    assert h["days"][k] == days[wb[i][2] - 1]                       # Friday close knows Thursday's holdings


def test_t404_planted_passes():
    h, px, _ = _t404_world(0.004)
    pan = m.flow_panel(h, px)
    j = m.judge_flows(pan)
    assert j["n"] >= 1000 and j["full"]["t"] >= 2
    assert j["verdict"] == "supported", j["why"]
    assert j["park_condition"] is False


def test_t404_null_fails():
    h, px, _ = _t404_world(0.0)
    j = m.judge_flows(m.flow_panel(h, px))
    assert j["verdict"] == "not_supported" and j["park_condition"] is True


# ============================================================================================ fake archive ==

class FakeArchive:
    def __init__(self, bundles, created="2026-10-15T23:30:00+00:00"):
        self.bundles = bundles
        self.created = created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


_EPOCH = date(1970, 1, 1).toordinal()


def _yahoo(p):
    rows = []
    for d, c, a, o in zip(p["days"], p["close"], p["adj"], p["open"]):
        od = date.fromisoformat(d).toordinal()
        rows.append({"available_at": date.fromordinal(od + 1).isoformat() + "T14:30:00+00:00",
                     "value": {"t": (od - _EPOCH) * 86400 + 14.5 * 3600, "open": float(o), "high": float(c), "low": float(c),
                               "close": float(c), "adjclose": float(a)}})
    return rows


def _fred(series):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(v)}} for d, v in sorted(series.items())]


def _cot_bundle(seed):
    rng = np.random.default_rng(seed)
    rows, x = [], 0.0
    for rd in tuesdays("2006-06-13", "2026-10-06"):
        x = 0.97 * x + rng.normal(0, 0.03)
        if rd < "2009-09-01":
            av, pit = "2009-10-20T23:59:59+00:00", "backcast"
        else:
            av, pit = friday_release(rd), "schedule"
        rows.append(cot_row(rd, x, av, pit))
    return rows


def _full_archive():
    rng = np.random.default_rng(12)
    b = {}
    days = bdays("2002-07-30")
    for sym, start in (("GLD", "2004-11-18"), ("SLV", "2006-04-28"), ("GDX", "2006-05-22"), ("TLT", "2002-07-30"),
                       ("IEF", "2002-07-30"), ("PSLV", "2010-10-28")):
        dd = [d for d in days if d >= start]
        b[f"daily-history-{sym}"] = _yahoo(px_of(dd, walk(len(dd), seed=len(b) + 1)))
    sp, dv, pp, pg = _t472_world(True)
    b["daily-history-PHYS"] = _yahoo(pp)
    b[m.SPROTT_PHYS] = [{"available_at": et_iso((date.fromisoformat(d) + timedelta(days=1)).isoformat(), "09:30"),
                         "value": {"fund": "PHYS", "day": d, "premium_discount_pct": float(v)}} for d, v in zip(sp, dv)]
    b[m.SPROTT_PSLV] = [{"available_at": r["available_at"], "value": {**r["value"], "fund": "PSLV"}} for r in b[m.SPROTT_PHYS]
                        if r["value"]["day"] >= "2010-10-28"]
    b[m.COT_GOLD] = _cot_bundle(1)
    b[m.COT_GOLD_F] = _cot_bundle(2)
    b[m.COT_SILVER] = _cot_bundle(3)
    fd = bdays("1990-01-02")
    b[m.DGS10_B] = _fred({d: 4.0 + 0.5 * math.sin(k / 300.0) + rng.normal(0, 0.03) for k, d in enumerate(fd)})
    b[m.DFII10_B] = _fred({d: 1.0 + 0.5 * math.sin(k / 250.0) for k, d in enumerate(fd) if d >= "2003-01-02"})
    specs = []
    for mo in sorted({d[:7] for d in fd}):
        wed = [d for d in fd if d.startswith(mo) and date.fromisoformat(d).weekday() == 2]
        thu = [d for d in fd if d.startswith(mo) and date.fromisoformat(d).weekday() == 3]
        if len(wed) >= 2 and len(thu) >= 2:
            specs.append((wed[1], "10-Year" if mo[5:7] in ("02", "05", "08", "11") else "9-Year 11-Month", True,
                          mo[5:7] not in ("02", "05", "08", "11"), True))
            specs.append((thu[1], "30-Year" if mo[5:7] in ("02", "05", "08", "11") else "29-Year 11-Month", True,
                          mo[5:7] not in ("02", "05", "08", "11"), True))
            specs.append((wed[0], "10-Year", False, False, True))                            # TIPS
    b[m.AUCT_B] = auction_rows(specs)
    b[m.CPI_B] = [{"available_at": d + "T12:30:00+00:00", "value": {"day": d}} for d in fd if d[8:10] == "13"]
    b[m.FOMC_B] = [{"available_at": d + "T00:00:00+00:00", "value": {"decision_day": d, "future": False}}
                   for d in fd if d[5:7] in ("01", "03", "06", "09") and d[8:10] == "17"]
    h, px, rows = _t404_world(0.0)
    b[m.SPDR_GLD] = rows
    return FakeArchive(b)


@pytest.fixture(scope="module")
def fake():
    return _full_archive()


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_every_harness_runs_json_safe(fake, name):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES[name](fake)
    json.dumps(stat, allow_nan=False)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert isinstance(n, int) and n > 0
    assert " — " in reason


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason and " — " in reason


def test_optional_bundles_are_optional(fake):
    b = dict(fake.bundles)
    for k in (m.COT_GOLD_F, m.COT_SILVER, m.SLV_B, m.GDX_B, m.DFII10_B, m.IEF_B, m.DGS10_B, m.CPI_B, m.FOMC_B, m.SPROTT_PSLV,
              m.PSLV_B):
        b.pop(k, None)
    arch = FakeArchive(b)
    for name in m.HARNESSES:
        m._CACHE.clear()
        stat, n, verdict, reason = m.HARNESSES[name](arch)
        assert "missing_bundles" not in stat and n > 0


def test_t405_harness_drops_backcasts_and_reports_park(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_pub_gold_cot_extremes"](fake)
    assert stat["first_week"] > "2009-10-13" and stat["dropped"]["backcast"] > 150
    assert stat["dropped"]["window_not_public"] == 7
    assert "PARK CONDITION" in reason and isinstance(stat["park_condition"], bool)
    assert n == min(stat["n_long_tail"], stat["n_short_tail"])


def test_t442_harness_counts_tips_out(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_pub_treasury_auction_cycle"](fake)
    assert stat["variants"]["V3_ief_10y"] is not None and stat["variants"]["V4_dgs10_10y"] is not None
    assert stat["variants"]["V6_ex_cpi_fomc"] is not None
    assert all(v is not None for v in stat["family_p_boot"].values())
    nominal = sum(1 for r in fake.bundles[m.AUCT_B] if r["kind"] == "auction-announcement" and r["value"]["nominal_coupon"])
    assert stat["n_auctions"] == nominal                             # the TIPS rows sharing the '10-Year' label are out
    assert n == stat["n_clusters"] and 280 <= n <= 2 * 292           # 1-2 ISO-week clusters a month since 2002-07


def test_maps_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-405", "T-442", "T-472", "T-404"}
    assert all(k.startswith("b6c_pub_") and k == k.lower() for k in m.HARNESSES)
