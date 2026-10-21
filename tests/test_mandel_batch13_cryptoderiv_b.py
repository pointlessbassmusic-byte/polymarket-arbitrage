"""Synthetic tests for mandel.experiments.batch13_cryptoderiv_b (T-616, T-607, T-615, T-610): every signal is unchanged
when data after its decision time is shocked, each harness is inconclusive when its bundles are missing, and a few
construction details (1-day fill, snapshot age, delisting haircut, carried minutes). No network, no real archive."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch6b_drb as B6B
from mandel.experiments import batch6c_cryptovenue as CV
from mandel.experiments import batch13_cryptoderiv_a as CDA
from mandel.experiments import batch13_cryptoderiv_b as M

UTC = timezone.utc
H = 3600
DAY = 86400


class _StubArchive:
    """Every bundle is missing: get() and load() raise KeyError, entries() is empty."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, kind=None, tag=None):
        return []


def _ts(d: str, hh: int = 0, mm: int = 0) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()) + hh * H + mm * 60


def _days(first: str, n: int) -> list:
    o = date.fromisoformat(first).toordinal()
    return [date.fromordinal(o + k).isoformat() for k in range(n)]


# ========================================================================================= missing bundles (rule 9) ==

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    out = M.HARNESSES[name](_StubArchive())
    assert out[2] == "inconclusive"
    assert out[1] == 0
    assert "missing" in out[3]


def test_maps_cover_the_four_theories():
    assert set(M.THEORY_MAP) == {"T-616", "T-607", "T-615", "T-610"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for fn in M.HARNESSES.values():
        assert fn.__doc__ and fn.__doc__.startswith("T-6")


# ======================================================================================================= T-616 ==

def _smile_trades(day: str, hour: int, a: float = 0.6, b: float = -0.08, c: float = 0.03, S: float = 40000.0) -> list:
    """Synthetic Deribit prints on ``day`` at ``hour`` UTC for two expiries bracketing 30 DTE, IV from a known smile."""
    out = []
    tms = _ts(day, hour, 15) * 1000
    for dte in (20, 40):
        e = (date.fromisoformat(day) + timedelta(days=dte)).isoformat()
        T = dte / 365.0
        for x in np.linspace(-2.0, 2.0, 11):
            K = round(S * math.exp(x * math.sqrt(T)))
            xx = math.log(K / S) / math.sqrt(T)
            iv = a + b * xx + c * xx * xx
            for kind in ("C", "P"):
                out.append({"timestamp": tms, "instrument_name": f"BTC-{e}-{K}-{kind}", "expiry": e, "strike": float(K),
                            "iv": iv * 100.0, "index_price": S, "amount": 1.0, "type": "call" if kind == "C" else "put"})
    return out


def test_t616_rr_uses_the_0700_0900_sample_only():
    day = "2024-03-04"
    base = _smile_trades(day, 7)
    sm0 = B6B.daily_smiles(base)
    rr0, bf0 = B6B.rr30(sm0[day], day), M.bf30(sm0[day], day)
    assert rr0 is not None and bf0 is not None
    assert rr0 < 0                                    # b < 0: put wing richer
    shocked = base + _smile_trades(day, 9, a=1.5, b=0.9, c=0.4, S=55000.0)      # prints after 09:00 UTC
    sm1 = B6B.daily_smiles(shocked)
    assert B6B.rr30(sm1[day], day) == pytest.approx(rr0)
    assert M.bf30(sm1[day], day) == pytest.approx(bf0)


def test_t616_trailing_z_uses_prior_days_only():
    days = _days("2023-01-01", 200)
    rng = np.random.default_rng(1)
    s = {d: float(v) for d, v in zip(days, rng.normal(0, 3, len(days)))}
    z0 = M.trailing_z(s)
    t = days[150]
    assert t in z0
    s2 = dict(s)
    for d in days[151:]:
        s2[d] = 1e6                                  # shock every later value
    assert M.trailing_z(s2)[t] == pytest.approx(z0[t])
    s3 = dict(s)
    s3[t] = s[t] + 5.0                               # the day's own value moves its own z only
    w = np.array([s[d] for d in days[60:150]])
    assert M.trailing_z(s3)[t] == pytest.approx((s[t] + 5.0 - w.mean()) / w.std(ddof=1))
    assert t not in M.trailing_z({d: s[d] for d in days[100:]})        # fewer than 60 days of history


def test_t616_signal_fill_is_one_day_only():
    zd = {"2024-01-01": 1.5}
    fit = {"2024-01-01"}
    assert M.signal_at(zd, fit, "2024-01-01") == (1.5, False)
    assert M.signal_at(zd, fit, "2024-01-02") == (1.5, True)
    assert M.signal_at(zd, fit, "2024-01-03") == (None, False)


def _hourly(first: str, n_days: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    ts = _ts(first) + H * np.arange(24 * n_days, dtype=np.int64)
    cl = 30000 * np.exp(np.cumsum(rng.normal(0, 0.004, ts.size)))
    return ts, cl


def test_t616_controls_do_not_see_after_0900():
    days = _days("2023-09-01", 170)
    ts, cl = _hourly(days[0], len(days) + 1)
    rng = np.random.default_rng(2)
    zd = {d: float(v) for d, v in zip(days, rng.normal(0, 1, len(days)))}
    dvol = {d: 50.0 + k * 0.1 for k, d in enumerate(days)}
    fts = (_ts(days[0]) + H * np.arange(24 * len(days), dtype=np.int64)) * 1000
    fv = rng.normal(0, 1e-4, fts.size)
    d = days[100]
    tab = M.t616_table(zd, {}, set(zd), ts, cl, dvol, fts, fv, first=days[40], last=days[130])
    k = tab["days"].index(d)
    t_dec = _ts(d, 9)
    cl2 = np.where(ts >= t_dec - H + 1, cl * 3.0, cl)          # every bar starting at or after 08:00:01 (ends after 09:00)
    dvol2 = {x: (v * 9 if x >= d else v) for x, v in dvol.items()}   # the candle stamped d closes at d+1 00:00
    fv2 = np.where(fts >= t_dec * 1000, fv + 1.0, fv)                # funding rows stamped at or after 09:00
    tab2 = M.t616_table(zd, {}, set(zd), ts, cl2, dvol2, fts, fv2, first=days[40], last=days[130])
    for key in ("z", "ret7", "ret30", "dvol", "fund"):
        assert tab2[key][k] == pytest.approx(tab[key][k]), key
    assert tab2["y7"][k] != pytest.approx(tab["y7"][k])               # the target does move
    assert tab["dvol"][k] == dvol[days[99]]                           # DVOL of the candle stamped t-1


def test_t616_oos_forecast_uses_completed_targets_only():
    rng = np.random.default_rng(3)
    n = 120
    ords = np.arange(n) + 738000
    x = rng.normal(0, 1, n)
    y = 0.3 * x + rng.normal(0, 1, n)
    oos = np.zeros(n, bool)
    oos[-1] = True
    r0 = M.oos_r2(ords, y, x, oos, hold=7, min_train=20)
    y2 = y.copy()
    y2[n - 7:n - 1] += 50.0                           # targets that complete after the last decision
    r1 = M.oos_r2(ords, y2, x, oos, hold=7, min_train=20)
    assert r1["r2"] == pytest.approx(r0["r2"])
    y3 = y.copy()
    y3[n - 8] += 50.0                                 # a completed target does enter
    assert M.oos_r2(ords, y3, x, oos, hold=7, min_train=20)["r2"] != pytest.approx(r0["r2"])


def test_t616_bonferroni_deflation():
    assert M.bonferroni_t(2.0, 1) == pytest.approx(2.0)
    t6 = M.bonferroni_t(2.0, 6)
    assert t6 < 1.2
    assert M.bonferroni_t(2.67, 6) == pytest.approx(2.0, abs=0.02)


# ======================================================================================================= T-607 ==

def _cb_panel(n_coins: int = 20, first: str = "2024-01-01", n_days: int = 120, seed: int = 4):
    rng = np.random.default_rng(seed)
    days = _days(first, n_days)
    daily = {}
    for i in range(n_coins):
        px = 10.0 * (i + 1) * np.exp(np.cumsum(rng.normal(0, 0.03, n_days)))
        vol = np.full(n_days, 2e6 / px.mean()) * (1 + i)
        daily[f"C{i:02d}-USD"] = {d: (float(p), float(p), float(v)) for d, p, v in zip(days, px, vol)}
    return daily, days


def test_t607_membership_and_weights_ignore_later_data():
    daily, days = _cb_panel()
    sun = next(d for d in days[40:] if date.fromisoformat(d).weekday() == 6)
    pan = CDA.build_panel(daily, days[0], days[-1])
    k_snap = date.fromisoformat(sun).toordinal() - pan["o0"]
    smap = {pan["base"][i].upper(): [(i, float(pan["C"][i, k_snap]), 1e6 * (i + 1))] for i in range(len(pan["pids"]))}
    el = M.eligible_week(pan, smap, k_snap, k_snap + 1)
    assert el["rows"].size == 20
    q = M.quintiles(el["mc"], [pan["pids"][i] for i in el["rows"]])
    mon = (date.fromisoformat(sun) + timedelta(days=1)).isoformat()
    # prices from the Monday bar on (its close is the entry fill; later bars are after the decision) and volumes from the
    # snapshot day on (the floor uses the 30 bars ending by the snapshot day's 00:00)
    shocked = {p: {d: (o * (5 if d >= mon else 1), c * (5 if d >= mon else 1), v * (1e-6 if d >= sun else 1))
                   for d, (o, c, v) in s.items()} for p, s in daily.items()}
    pan2 = CDA.build_panel(shocked, days[0], days[-1])
    smap2 = {pan2["base"][i].upper(): [(i, float(pan["C"][i, k_snap]), 1e6 * (i + 1))] for i in range(len(pan2["pids"]))}
    el2 = M.eligible_week(pan2, smap2, k_snap, k_snap + 1)
    assert el2["rows"].tolist() == el["rows"].tolist()
    assert np.allclose(el2["mc"], el["mc"])
    assert M.quintiles(el2["mc"], [pan2["pids"][i] for i in el2["rows"]]).tolist() == q.tolist()
    assert (q == 0).sum() == 4                       # floor(5 r / n): the smallest 4 of 20


def test_t607_volume_floor_and_price_match():
    daily, days = _cb_panel(n_coins=3)
    daily["THIN-USD"] = {d: (1.0, 1.0, 10.0) for d in days}          # $10 a day: below the floor
    pan = CDA.build_panel(daily, days[0], days[-1])
    sun = next(d for d in days[40:] if date.fromisoformat(d).weekday() == 6)
    k = date.fromisoformat(sun).toordinal() - pan["o0"]
    smap = {pan["base"][i].upper(): [(i, float(pan["C"][i, k]), 1e6)] for i in range(len(pan["pids"]))}
    smap["C00"] = [(99, float(pan["C"][0, k]) * 3.0, 5e5)]                # a same-symbol CMC coin at 3x the price
    el = M.eligible_week(pan, smap, k, k + 1)
    bases = {pan["base"][i] for i in el["rows"]}
    assert "THIN" not in bases and "C00" not in bases and el["unmatched"] == ["C00"]


def test_t607_snapshot_age_rule():
    sundays = {"2024-03-03", "2024-03-10"}
    assert M.snapshot_for(sundays, "2024-03-05") == "2024-03-03"     # Tuesday: 2 days old
    assert M.snapshot_for(sundays, "2024-03-11") == "2024-03-03"     # Monday 00:00: the 03-10 snapshot is 1 day old
    assert M.snapshot_for({"2024-03-03"}, "2024-03-12") is None       # 9 days old: never used
    assert M.snapshot_for(sundays, "2024-03-12") == "2024-03-10"


def test_t607_delisted_haircut_and_turnover():
    days = _days("2024-01-01", 30)
    daily = {"A-USD": {d: (1.0, 1.0, 1e9) for d in days},
             "B-USD": {d: (2.0, 2.0, 1e9) for d in days[:10]}}          # B stops trading for good after day 9
    pan = CDA.build_panel(daily, days[0], days[-1])
    rows = np.array([pan["pids"].index("A-USD"), pan["pids"].index("B-USD")])
    r, gone = M.hold_returns(pan, rows, 5, 12)
    assert r.tolist() == pytest.approx([0.0, -0.5]) and gone.tolist() == [False, True]
    w = {"vw_q1": np.array([0.5, 0.5])}
    weeks = [{"k": 5, "rows": rows, "w": w, "r": np.array([0.0, 0.0])},
             {"k": 12, "rows": rows, "w": w, "r": np.array([0.0, 0.0])},
             {"k": 26, "rows": rows, "w": w, "r": np.array([0.0, 0.0])}]
    M.book_costs(weeks, "vw_q1")
    assert weeks[0]["vw_q1_to"] == pytest.approx(1.0)                # first entry
    assert weeks[1]["vw_q1_to"] == pytest.approx(0.0 + 1.0)          # unchanged weights, then a gap: full liquidation
    assert weeks[2]["vw_q1_net"] == pytest.approx(-M.T607_COST)      # re-entry after the gap


# ======================================================================================================= T-615 ==

def test_t615_spike_and_drawdown_use_prior_days_only():
    rng = np.random.default_rng(5)
    n = 900
    supply = 1e9 + np.cumsum(np.abs(rng.normal(1e6, 5e5, n)))
    supply[700] += 2e7                                # a spike on day 700
    sp0, z0 = M.spike_flags(supply)
    assert sp0[700]
    s2 = supply.copy()
    s2[701:] += np.cumsum(rng.normal(0, 1e8, n - 701))  # shock everything after day 700
    sp1, z1 = M.spike_flags(s2)
    assert sp1[700] and z1[700] == pytest.approx(z0[700])
    cl = 30000 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
    cl[600:603] *= np.array([0.95, 0.90, 0.85])
    dd0, r0 = M.drawdown_flags(cl)
    c2 = cl.copy()
    c2[603:] *= 0.3
    dd1, r1 = M.drawdown_flags(c2)
    assert dd0[:603].tolist() == dd1[:603].tolist() and np.allclose(r0[:603], r1[:603], equal_nan=True)


def test_t615_entries_after_both_conditions_are_known():
    n = 40
    spike = np.zeros(n, bool)
    dd = np.zeros(n, bool)
    dd[10] = True
    spike[12] = True                                   # 2 days after the drawdown day
    spike[30] = True                                   # no drawdown before it
    dd[20] = True                                      # a drawdown day without a spike
    ev = M.stable_events(spike, dd)
    assert ev == [14]                                  # spike day 12 is usable from 14 00:00; the drawdown from 11
    assert M.stable_events(spike, dd, strict=True) == [14]
    assert M.control_days(spike, dd) == [24]           # no spike on 20..22, known at 24 00:00
    assert M.refractory([14, 16, 19, 25]) == [14, 19, 25]
    op = np.arange(1.0, n + 1)
    cl = op + 0.5
    y = M.fwd_returns(op, cl, [14], 3)
    assert y[0] == pytest.approx(math.log(cl[16] / op[14]))


def test_t615_cluster_bootstrap_bar():
    rng = np.random.default_rng(6)
    xe = rng.normal(0.03, 0.01, 40)
    xc = rng.normal(0.0, 0.01, 200)
    ge = np.arange(40)
    gc = np.arange(200) % 100
    t = M.cluster_diff_test(xe, ge, xc, gc, bar=0.005, n_boot=1000)
    assert t["diff"] == pytest.approx(xe.mean() - xc.mean())
    assert t["lb"] > 0.005 and t["p_greater"] < 0.05


# ======================================================================================================= T-610 ==

def _minute_grid(day: str, seed: int = 7, drop=()):
    rng = np.random.default_rng(seed)
    t0 = _ts(day)
    t = t0 + 60 * np.arange(24 * 60, dtype=np.int64)
    c = 30000 * np.exp(np.cumsum(rng.normal(0, 0.0005, t.size)))
    o = np.concatenate([[c[0]], c[:-1]])
    v = rng.uniform(1, 5, t.size)
    keep = ~np.isin(t, np.asarray(list(drop), np.int64))
    return t[keep], o[keep], c[keep], v[keep]


def test_t610_signal_ignores_bars_after_1000():
    day = "2025-03-12"                                  # a Wednesday, EDT (09:30 ET = 13:30 UTC)
    t, o, c, v = _minute_grid(day)
    g = M.grid_from(t, o, c, v)
    tr = M.session_trades(g, [day])
    t_sig = int(CV.et_epoch(day, "10:00"))
    c2 = np.where(t >= t_sig, c * 1.5, c)                # every bar starting at or after 10:00 ET
    v2 = np.where(t >= t_sig, v * 100, v)
    tr2 = M.session_trades(M.grid_from(t, np.where(t >= t_sig, o * 1.5, o), c2, v2), [day])
    assert tr2["r1"][0] == pytest.approx(tr["r1"][0])
    assert tr2["side"][0] == tr["side"][0]
    assert tr2["vol"][0] == pytest.approx(tr["vol"][0])
    k0 = (int(CV.et_epoch(day, "09:30")) - 60 - g["g0"]) // 60
    assert tr["r1"][0] == pytest.approx(math.log(c[k0 + 30] / c[k0]))    # bar closes ending 09:30 and 10:00
    ke = (int(CV.et_epoch(day, "15:30")) - g["g0"]) // 60
    kx = (int(CV.et_epoch(day, "16:00")) - 60 - g["g0"]) // 60
    assert tr["move"][0] == pytest.approx(c[kx] / o[ke] - 1.0)


def test_t610_missing_minutes_carry_forward():
    day = "2025-01-15"                                  # EST: 15:30 ET = 20:30 UTC
    te = int(CV.et_epoch(day, "15:30"))
    t, o, c, v = _minute_grid(day, drop=(te,))
    g = M.grid_from(t, o, c, v)
    p, carried = M.open_at(g, [te])
    k_prev = (te - 60 - g["g0"]) // 60
    assert carried[0] and p[0] == pytest.approx(g["C"][k_prev])
    tr = M.session_trades(g, [day])
    assert tr["carried_marks"]["entry"] == 1


def test_t610_volume_tercile_uses_prior_sessions():
    rng = np.random.default_rng(8)
    vol = rng.uniform(1, 2, 200)
    f0, v0 = M.volume_flags(vol)
    vol2 = vol.copy()
    vol2[121:] *= 1000.0
    f1, v1 = M.volume_flags(vol2)
    assert f0[:121].tolist() == f1[:121].tolist() and v0[:121].tolist() == v1[:121].tolist()
    assert not v0[:60].any()


def test_t610_full_sessions_drop_early_closes_and_holidays():
    s = M.full_sessions("2024-11-25", "2024-12-31")
    assert "2024-11-28" not in s                        # Thanksgiving
    assert "2024-11-29" not in s                        # early close
    assert "2024-12-24" not in s and "2024-12-25" not in s
    assert "2024-12-26" in s
