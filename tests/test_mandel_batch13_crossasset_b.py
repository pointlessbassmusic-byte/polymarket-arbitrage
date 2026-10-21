"""Batch 13 ``crossasset_b`` (T-597, T-601, T-602, T-604): point-in-time signal tests and missing-bundle verdicts."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pytest

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch13_crossasset_b as M


class _NoBundles:
    """A stub archive with no bundles: every lookup raises KeyError."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)


def _sessions(start: str, n: int) -> list:
    d = date.fromisoformat(start)
    if not CAL.is_nyse_session(d):
        d = CAL.next_session(d)
    out = [d.isoformat()]
    while len(out) < n:
        d = CAL.next_session(d)
        out.append(d.isoformat())
    return out


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_NoBundles())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason


def test_theory_map_matches_harnesses():
    assert set(M.THEORY_MAP) == {"T-597", "T-601", "T-602", "T-604"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


# ------------------------------------------------------------------------------------- monthly predictor engine --

def test_expanding_forecast_ignores_targets_and_predictors_after_origin():
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=200), rng.normal(size=200)
    k = 150
    for gap in (1, 2):
        base = M.expanding_oos(x, y, k, k, 0, gap, 24)
        x2, y2 = x.copy(), y.copy()
        x2[k + 1:] += 50.0
        y2[k - gap + 1:] += 50.0                 # targets not realised at the origin (y[k-1] is still unknown at gap 2)
        alt = M.expanding_oos(x2, y2, k, k, 0, gap, 24)
        assert alt["fm"][0] == pytest.approx(base["fm"][0]) and alt["fb"][0] == pytest.approx(base["fb"][0])
        y3 = y.copy()
        y3[k - gap] += 50.0                      # the last realised pair does enter
        assert M.expanding_oos(x, y3, k, k, 0, gap, 24)["fm"][0] != pytest.approx(base["fm"][0])


def test_pc1_forecast_ignores_months_after_origin():
    rng = np.random.default_rng(1)
    f = rng.normal(size=(300, 1))
    G = f @ np.ones((1, 6)) + 0.3 * rng.normal(size=(300, 6))
    y = 0.2 * f[:, 0] + rng.normal(size=300)
    k = 250
    base = M.pc1_oos(G, y, k, k, 1, 24)
    G2, y2 = G.copy(), y.copy()
    G2[k + 1:] *= -7.0
    y2[k:] += 30.0
    alt = M.pc1_oos(G2, y2, k, k, 1, 24)
    assert alt["fm"][0] == pytest.approx(base["fm"][0])
    assert np.allclose(alt["loadings"][0], base["loadings"][0])
    assert base["loadings"][0].sum() > 0


def test_ff_and_industry_months_compound_only_their_own_days():
    days = _sessions("2020-01-02", 60)
    rows = [{"value": {"day": d, "Mkt-RF": 0.1 * (i % 3), "RF": 0.01, "Banks": 0.2, "Oil": -0.1}} for i, d in enumerate(days)]
    mkt, _rf = M.ff_monthly(rows)
    ind = M.ind_monthly(rows, ["Banks", "Oil"])
    jan = [r for r in rows if r["value"]["day"] < "2020-02-01"]
    shocked = [dict(r, value=dict(r["value"], **{"Mkt-RF": 9.0, "Banks": 9.0})) if r["value"]["day"] >= "2020-02-01" else r
               for r in rows]
    mkt2, _ = M.ff_monthly(shocked)
    ind2 = M.ind_monthly(shocked, ["Banks", "Oil"])
    assert mkt2["2020-01"] == pytest.approx(mkt["2020-01"]) and ind2["Banks"]["2020-01"] == pytest.approx(ind["Banks"]["2020-01"])
    expect = np.prod([1 + (r["value"]["Mkt-RF"] + 0.01) / 100 for r in jan]) - np.prod([1.0001 for _ in jan])
    assert mkt["2020-01"] == pytest.approx(expect)
    missing = [dict(r, value={k: v for k, v in r["value"].items() if k != "Oil"}) if r["value"]["day"] == days[3] else r
               for r in rows]
    assert np.isnan(M.ind_monthly(missing, ["Oil"])["Oil"]["2020-01"])


def test_dtb3_threshold_is_the_print_before_the_fill_day():
    keys, vals = ["2024-01-02", "2024-01-03", "2024-01-04"], [5.0, 6.0, 7.0]
    assert M.dtb3_before(keys, vals, "2024-01-04") == 6.0
    assert M.switching([0.01, 0.02, -0.01], [0.004, 0.006, 0.001], 0.005).tolist() == \
        pytest.approx([0.0, 0.02 - 2e-4, -2e-4])


# ------------------------------------------------------------------------------------------------------ T-602 --

def _month_series():
    rng = np.random.default_rng(2)
    ms = M.mrange("2010-01", "2016-12")
    return ms, {m: float(v) for m, v in zip(ms, rng.normal(0.004, 0.02, len(ms)))}, \
        {m: float(v) for m, v in zip(ms, rng.normal(0.003, 0.015, len(ms)))}


def test_hedged_excess_uses_only_the_trailing_36_months():
    _ms, re, ri = _month_series()
    t = "2014-06"
    base, betas = M.hedged_excess(re, ri)
    re2 = {m: (v + 1.0 if m > t else v) for m, v in re.items()}
    ri2 = {m: (v * -3.0 if m > t else v) for m, v in ri.items()}
    alt, betas2 = M.hedged_excess(re2, ri2)
    assert alt[t] == pytest.approx(base[t]) and betas2[t] == pytest.approx(betas[t])
    assert min(base) == "2012-12"                # the 36th monthly return


def test_baa_month_end_change_ignores_later_prints():
    days = _sessions("2015-01-02", 80)
    ser = {d: 2.0 + 0.01 * i for i, d in enumerate(days)}
    ch = M.month_changes(M.month_end_values(ser))
    ser2 = {d: (v + 5.0 if d >= "2015-03-01" else v) for d, v in ser.items()}
    ch2 = M.month_changes(M.month_end_values(ser2))
    assert ch2["2015-02"] == pytest.approx(ch["2015-02"])
    last_jan = max(d for d in days if d < "2015-02-01")
    last_feb = max(d for d in days if d < "2015-03-01")
    assert ch["2015-02"] == pytest.approx(ser[last_feb] - ser[last_jan])
    assert days[-1][:7] not in M.month_end_values(ser) or M.month_complete(days[-1])


def test_spy_target_runs_from_the_first_close_of_t_plus_1():
    days = _sessions("2020-01-02", 90)
    adj = np.linspace(100, 130, len(days))
    bills = CAL.Bills({"2019-12-31": 0.0})
    tg = M.spy_targets(days, adj, bills, ["2020-01"])
    y, d0, d1 = tg["2020-01"]
    i0, i1 = days.index(d0), days.index(d1)
    assert d0 == min(d for d in days if d >= "2020-02-01") and d1 == min(d for d in days if d >= "2020-03-01")
    assert y == pytest.approx(adj[i1] / adj[i0] - 1.0)
    adj2 = adj.copy()
    adj2[i1 + 1:] *= 3.0
    assert M.spy_targets(days, adj2, bills, ["2020-01"])["2020-01"][0] == pytest.approx(y)


# ------------------------------------------------------------------------------------------------------ T-601 --

def _bar_world(n_days: int = 40, seed: int = 3):
    """Synthetic 60-minute bars: 7 bars a session at 09:30..15:30 ET plus a 16:00 stub."""
    rng = np.random.default_rng(seed)
    days = _sessions("2025-08-01", n_days)
    t, o, c = [], [], []
    px = 100.0
    for d in days:
        for hh in (9, 10, 11, 12, 13, 14, 15, 16):
            dt = datetime.fromisoformat(f"{d}T{hh:02d}:{30 if hh < 16 else 0:02d}:00").replace(tzinfo=M.NY)
            op = px * (1 + rng.normal(0, 2e-4))
            px = op * (1 + rng.normal(0, 3e-3))
            t.append(int(dt.timestamp())); o.append(op); c.append(px)
    return M.bars_from_arrays(t, o, c)


def test_bar_filter_drops_stubs_and_lockbox():
    b = _bar_world()
    hm = {datetime.fromtimestamp(int(x), M.NY).strftime("%H:%M") for x in b["t"]}
    assert "16:00" not in hm and hm == {"09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"}
    t = [int(datetime.fromisoformat("2026-10-01T09:30:00").replace(tzinfo=M.NY).timestamp())]
    assert M.bars_from_arrays(t, [1.0], [1.0])["t"].size == 0


@pytest.mark.parametrize("unit", ["s", "ns"])
def test_bars_from_df_epoch_seconds_any_unit(unit):
    import pandas as pd
    t0 = int(datetime.fromisoformat("2026-03-02T10:30:00").replace(tzinfo=M.NY).timestamp())
    idx = pd.to_datetime([t0, t0 + 3600], unit="s", utc=True).as_unit(unit)
    b = M.bars_from_df(pd.DataFrame({"o": [1.0, 2.0], "c": [1.5, 2.5]}, index=idx))
    assert b["t"].tolist() == [t0, t0 + 3600] and b["day"].tolist() == ["2026-03-02", "2026-03-02"]


@pytest.mark.parametrize("reading", ["bar", "c2c"])
def test_t601_signal_ignores_bars_after_its_close(reading):
    b = _bar_world()
    G = M.grid_of(b)
    r = M.bar_ret(b["o"], b["c"], reading)
    sd = M.session_sd(r, G["starts"], G["n_sess"])
    sig = M.signals(r, sd, G["sess"], G["next_ok"])
    i = int(np.flatnonzero(G["sess"] == 30)[2])               # the 11:30 bar of session 30
    o2, c2 = b["o"].copy(), b["c"].copy()
    o2[i + 1:] *= 1.5
    c2[i + 1:] *= 0.5
    r2 = M.bar_ret(o2, c2, reading)
    sd2 = M.session_sd(r2, G["starts"], G["n_sess"])
    sig2 = M.signals(r2, sd2, G["sess"], G["next_ok"])
    assert sig2[i] == sig[i] and r2[i] == pytest.approx(r[i])
    assert sd2[30] == pytest.approx(sd[30])
    assert np.isnan(sd[19]) and np.isfinite(sd[20])          # 20 complete prior sessions needed
    last = np.flatnonzero(G["sess"] == 30)[-1]
    assert not G["next_ok"][last] and sig[last] == 0          # the 15:30 bar never signals


def test_t601_threshold_uses_only_prior_sessions():
    b = _bar_world()
    G = M.grid_of(b)
    r = M.bar_ret(b["o"], b["c"], "bar")
    sd = M.session_sd(r, G["starts"], G["n_sess"])
    s = 25
    prior = r[(G["sess"] >= s - 20) & (G["sess"] < s)]
    assert sd[s] == pytest.approx(np.std(prior[np.isfinite(prior)], ddof=1))
    r2 = r.copy()
    r2[G["sess"] >= s] *= 10.0
    assert M.session_sd(r2, G["starts"], G["n_sess"])[s] == pytest.approx(sd[s])


def test_t601_trade_return_is_the_next_bar_and_costs_two_sides():
    b = _bar_world()
    G = M.grid_of(b)
    r = M.bar_ret(b["o"], b["c"], "bar")
    y = M.next_bar_ret(b["o"], b["c"], G["next_ok"])
    bk = M.t601_book(r, y, G, G["sdays"][0], G["sdays"][-1])
    assert bk["idx"].size > 0
    i = bk["idx"][0]
    assert bk["net"][0] == pytest.approx(np.sign(r[i]) * (b["c"][i + 1] / b["o"][i + 1] - 1.0) - 4e-4)
    assert bk["sess_series"].sum() == pytest.approx(bk["net"].sum())


def test_placebo_counts_and_basket_signal():
    a = M.draw_counts(38, 50, 30, replace=False)
    bb = M.draw_counts(28, 50, 30, replace=True)
    assert (a.sum(0) == 30).all() and a.max() == 1 and (bb.sum(0) == 30).all()
    b = _bar_world()
    G = M.grid_of(b)
    r = M.bar_ret(b["o"], b["c"], "bar")
    y = M.next_bar_ret(b["o"], b["c"], G["next_ok"])
    one = np.ones((1, 1), int)
    pm = M.placebo_means(r[:, None], one, y, G, G["sdays"][0], G["sdays"][-1])
    bk = M.t601_book(r, y, G, G["sdays"][0], G["sdays"][-1])
    assert pm[0] == pytest.approx(bk["net"].mean())


# ------------------------------------------------------------------------------------------------------ T-604 --

def _panel(D: int = 60, N: int = 12, seed: int = 4):
    rng = np.random.default_rng(seed)
    A = 50 * np.cumprod(1 + rng.normal(0, 0.02, (D, N)), axis=0)
    O = A * (1 + rng.normal(0, 0.003, (D, N)))
    member = np.ones((D, N), bool)
    member[:, -1] = False
    raw = A.copy()
    raw[:, 0] = 3.0                                            # below $5: never eligible
    return A, O, member, raw


@pytest.mark.parametrize("L", [1, 5])
def test_t604_weights_ignore_day_t_and_later(L):
    A, _O, member, raw = _panel()
    OK = M.eligible(member, raw, A)
    W = M.reversal_weights(A, OK, L)
    t = 40
    A2, raw2, mem2 = A.copy(), raw.copy(), member.copy()
    A2[t:] *= np.random.default_rng(9).uniform(0.5, 1.5, A2[t:].shape)
    raw2[t:] = 1.0
    mem2[t:] = False
    W2 = M.reversal_weights(A2, M.eligible(mem2, raw2, A2), L)
    assert np.allclose(W2[t], W[t])
    assert W[t, 0] == 0 and W[t, -1] == 0                      # price filter and membership at close t-1
    assert W[t][W[t] > 0].sum() == pytest.approx(1.0) and W[t][W[t] < 0].sum() == pytest.approx(-1.0)
    r = A[t - 1] / A[t - 1 - L] - 1.0
    ok = OK[t - 1]
    assert np.corrcoef(W[t][ok], r[ok])[0, 1] < -0.99            # weights are minus the demeaned formation return


def test_t604_day_return_is_open_to_close_with_costs():
    A, O, member, raw = _panel()
    W = M.reversal_weights(A, M.eligible(member, raw, A), 1)
    C = A
    g, net, turn = M.day_returns(W, O, C)
    t = 30
    assert g[t] == pytest.approx(float((W[t] * (C[t] / O[t] - 1)).sum()))
    assert turn[t] == pytest.approx(2.0) and net[t] == pytest.approx(g[t] - 12e-4)
    O2 = O.copy()
    O2[t, 3] = np.nan                                          # unfilled name: no return, no cost
    _g2, _net2, turn2 = M.day_returns(W, O2, C)
    assert turn2[t] == pytest.approx(2.0 - abs(W[t, 3]))


def test_t604_vix_tercile_uses_only_closes_before_the_day():
    days = _sessions("2018-01-02", 400)
    rng = np.random.default_rng(5)
    vix = {d: float(15 + rng.normal(0, 3)) for d in days}
    vg = M.vix_grid(vix, days)
    vp, q1, q2 = M.vix_terciles(vg)
    t = 300
    vg2 = vg.copy()
    vg2[t:] += 40.0
    vp2, q12, q22 = M.vix_terciles(vg2)
    assert vp2[t] == vp[t] == vg[t - 1] and q22[t] == pytest.approx(q2[t]) and q12[t] == pytest.approx(q1[t])
    assert q2[t] == pytest.approx(np.quantile(vg[t - 252:t], 2 / 3))
    assert np.isnan(q2[251]) and np.isfinite(q2[252])


def test_split_factors_and_vix_grid_forward_fill():
    days = ["2020-01-02", "2020-06-01", "2021-01-04"]
    f = M.split_factors(days, [("2020-06-01", 4.0), ("2021-01-04", 2.0)])
    assert f.tolist() == [8.0, 2.0, 1.0]
    vg = M.vix_grid({"2020-01-02": 20.0}, ["2020-01-02", "2020-01-03"])
    assert vg.tolist() == [20.0, 20.0]


@pytest.mark.parametrize("L", [1, 5])
def test_t604_ff49_weights_ignore_day_t_and_later(L):
    days = _sessions("2012-06-01", 320)
    rng = np.random.default_rng(6)
    FM = rng.normal(0, 0.01, (len(days), 8))
    FM[:40, 2] = np.nan                                         # an industry that starts later
    vp, _q1, q2 = M.vix_terciles(M.vix_grid({d: float(15 + rng.normal(0, 3)) for d in days}, days))
    fd = np.array(days)
    base = M.ff49_reversal(fd, FM, L, fd, vp, q2)
    t = 300
    FM2 = FM.copy()
    FM2[t:] += 0.05
    alt = M.ff49_reversal(fd, FM2, L, fd, vp, q2)
    assert np.allclose(alt["weights"][t], base["weights"][t])
    w = base["weights"][t]
    assert w[w > 0].sum() == pytest.approx(1.0) and base["gross"][t] == pytest.approx(float((w * FM[t]).sum()))
    assert base["weights"][L + 10, 2] == 0                     # missing formation data: no weight
