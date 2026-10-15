"""Batch-6b Deribit harnesses (T-197 quarterly basis, T-223 Friday settlement straddle, T-269 CME vs IBIT after tax, T-222
catalyst strangle, T-257 RR skew harvest, T-262 calendar on inversion, T-263 FOMC implied move, T-268 DVOL futures basis,
T-195 parity, T-196 quarterly box, T-260 capture-day box) on synthetic data only: for every core judge a planted effect
passes and a null does not; calendars, rates, pricing, fees, the point-in-time handling of catalyst windows and the
smile machinery are checked directly; every harness runs on a fake archive (JSON-safe, labelled, missing bundles ->
inconclusive naming the bundle and its request). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6b_drb as m

NB = 200                                # bootstrap resamples in tests
UTC = timezone.utc
DAY = 86_400_000
HOUR = 3_600_000


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", NB)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00", listing=True):
        self.bundles, self.created, self.listing = bundles, created, listing

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])

    def entries(self):
        if not self.listing:
            raise RuntimeError("no listing")
        return [SimpleNamespace(name=n) for n in self.bundles]


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _ms(day, hh=0, mm=0):
    return int(datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}:00+00:00").timestamp() * 1000)


def _days(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _check(res, verdicts=("supported", "not_supported", "inconclusive")):
    stat, n, v, reason = res
    json.dumps(stat)
    assert isinstance(n, int) and v in verdicts and " — " in reason
    return stat, n, v, reason


def _dtb3_rows(days, pct=2.0):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": pct}} for d in days]


def _dvol_rows(days, level=50.0):
    return [{"available_at": _iso(_ms(d) + DAY), "value": {"ts_ms": _ms(d), "open": level, "high": level, "low": level,
                                                           "close": float(level if not callable(level) else level(d))}}
            for d in days]


def _fund_rows(days, S, hours=(0, 8)):
    out = []
    for d in days:
        for h in hours:
            t = _ms(d, h)
            out.append({"available_at": _iso(t), "value": {"timestamp": t, "index_price": float(S(d, h))}})
    return out


def _deliv_rows(prices):
    return [{"available_at": d + "T08:30:00+00:00", "value": {"date": d, "delivery_price": float(p)}} for d, p in prices.items()]


def _gbm(n, sig_annual, seed, s0=40000.0):
    rng = np.random.default_rng(seed)
    lr = rng.normal(-0.5 * sig_annual ** 2 / 365, sig_annual / math.sqrt(365), n)
    lr[0] = 0.0
    return s0 * np.exp(np.cumsum(lr))


# ------------------------------------------------------------------------------------- rates, calendars, BS --

def test_dtb3_conversion_decision_vs_same_day():
    assert m.dtb3_cont(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    b = m.Bills({"2020-01-02": 4.0, "2020-01-03": 8.0})
    assert b.rate("2020-01-03") == pytest.approx(m.dtb3_cont(4.0))         # a decision on 01-03 cannot see the 01-03 print
    assert b.same_day("2020-01-03") == pytest.approx(m.dtb3_cont(8.0))     # a same-day comparison can
    assert b.same_day("2020-01-05") == pytest.approx(m.dtb3_cont(8.0))     # weekend carries Friday's print


def test_deribit_calendar_helpers():
    assert m.code_date("25DEC26") == "2026-12-25" and m.code_date("5JAN24") == "2024-01-05" and m.code_date("XX") is None
    assert m.last_friday(2024, 3) == date(2024, 3, 29) and m.last_friday(2026, 10) == date(2026, 10, 30)
    assert m.is_quarterly("2026-12-25") and not m.is_quarterly("2026-11-27") and m.is_last_friday("2026-11-27")
    assert m.fridays("2026-10-01", "2026-10-31") == ["2026-10-02", "2026-10-09", "2026-10-16", "2026-10-23", "2026-10-30"]
    assert m.deribit_monthly_expiries("2021-03-25", "2021-06-30") == ["2021-03-26", "2021-04-30", "2021-05-28", "2021-06-25"]
    assert m.expiry_ms("2026-12-25") == _ms("2026-12-25", 8)


def test_black_scholes_parity_delta_and_fee_cap():
    S, K, T, s = 100.0, 110.0, 0.25, 0.6
    c, p = m.bs_price(S, K, T, s, "call"), m.bs_price(S, K, T, s, "put")
    assert c - p == pytest.approx(S - K, abs=1e-9)
    assert m.bs_delta(S, K, T, s, "call") - m.bs_delta(S, K, T, s, "put") == pytest.approx(1.0)
    assert m.option_fee(0.1) == pytest.approx(0.0003) and m.option_fee(0.001) == pytest.approx(0.000125)


def test_sign_test_and_exact_binomial_interval():
    assert m.sign_test(15, 20)[0] == pytest.approx(sum(math.comb(20, i) for i in range(15, 21)) / 2 ** 20)
    lo, hi = m.clopper_pearson(0, 39)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** (1 / 39), rel=1e-4)
    lo, hi = m.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.187, abs=2e-3) and hi == pytest.approx(0.813, abs=2e-3)


def test_greedy_and_per_start():
    days = _days("2022-01-01", 10)
    exits = [m._add(d, 3) for d in days]
    assert m._greedy(days, exits) == [0, 4, 8]
    ps = m._per_start(days, exits, np.arange(10.0), 4)
    assert ps["offsets"] == 4 and ps["n_min"] <= ps["n_max"] <= 3


def test_dated_bundles_from_listing_or_probe(monkeypatch):
    b = {"deribit-book-BTC-2026-10-14": [], "deribit-book-BTC-2026-10-15": [], "deribit-book-ETH-2026-10-14": []}
    assert m._dated(FakeArchive(b), m.BOOK_PREFIX) == ["deribit-book-BTC-2026-10-14", "deribit-book-BTC-2026-10-15"]
    assert m._dated(FakeArchive(b, listing=False), m.BOOK_PREFIX) == ["deribit-book-BTC-2026-10-14", "deribit-book-BTC-2026-10-15"]


# ===================================================================================== T-197 quarterly basis ==

def _quarterlies(first, last):
    out, y = [], int(first[:4]) - 1
    while y <= int(last[:4]) + 1:
        for mo in (3, 6, 9, 12):
            out.append(m.last_friday(y, mo).isoformat())
        y += 1
    return out


def _qf_bundle(days, S, basis, noise=0.0, seed=0):
    """Daily quarterly bars (open 08:00, close next 08:00) for every quarterly listed 270 days before its expiry; the
    close is S x exp(basis x DTE/365) at the close tick."""
    rng = np.random.default_rng(seed)
    rows = []
    qs = _quarterlies(days[0], days[-1])
    for d in days:
        t_close = _ms(d, 8) + DAY
        for e in qs:
            exp = _ms(e, 8)
            dte = (exp - t_close) / DAY
            if 0 < dte <= 270:
                b = basis + noise * rng.normal()
                F = S(m._dday(t_close), 8) * math.exp(b * dte / 365)
                code = m.MONTHS3[int(e[5:7]) - 1]
                rows.append({"available_at": _iso(t_close), "value": {"instrument": f"BTC-{int(e[8:])}{code}{e[2:4]}",
                                                                      "expiry": e, "ts_ms": _ms(d, 8), "close": F}})
    return rows


def test_basis_days_aligns_close_and_picks_second_quarterly():
    days = _days("2021-01-01", 30)
    S = lambda d, h: 30000.0
    fut = [r["value"] for r in _qf_bundle(days, S, 0.10)]
    idx = {r["value"]["timestamp"]: r["value"]["index_price"] for r in _fund_rows(_days("2021-01-01", 32), S)}
    rows = m.basis_days(fut, idx)
    assert rows and all(r["dte1"] < r["dte2"] for r in rows)
    r0 = rows[0]
    assert r0["day"] == "2021-01-02" and r0["q1"] == "BTC-26MAR21" and r0["q2"] == "BTC-25JUN21"
    assert r0["basis2"] == pytest.approx(0.10, abs=1e-9)


def test_basis_judge_planted_passes_null_fails():
    rng = np.random.default_rng(1)
    days = _days("2019-05-01", 900)
    v, why, det = m.judge_basis(0.05 + 0.002 * rng.normal(size=900), days, overlap=180)
    assert v == "supported", why
    v, why, _ = m.judge_basis(0.002 * rng.normal(size=900), days, overlap=180)
    assert v == "not_supported", why


def _ar1(seed, n=1800, phi=0.995, sd=0.001):
    rng = np.random.default_rng(seed)
    u = np.zeros(n)
    for i in range(1, n):
        u[i] = phi * u[i - 1] + sd * rng.normal()
    return u


def test_basis_judge_decides_on_rule6_blocks_only():
    # regression (T-197 review): a persistent AR(1) excess (phi 0.995). The trial's 20-day blocks pass; on blocks as long
    # as the forward window (rule 6) the studentized and the percentile lower bounds both fall below 100 bp. The 20-day
    # CI breaks rule 6 and cannot cancel the compliant one: not_supported, not MARGINAL.
    days = _days("2019-05-01", 1800)
    x = 0.019 + _ar1(1)
    v, why, det = m.judge_basis(x, days, overlap=180)
    t20, t180 = det["tests"][20], det["tests"][180]
    assert t20["ci"][0] > 0.01 and t180["ci"][0] < 0.01 and t180["ci_pct"][0] < 0.01
    assert det["decision_block"] == 180 and v == "not_supported" and "MARGINAL" not in why, why
    assert "20-day blocks, shorter than the rule-6 minimum" in why and "not deciding" in why
    v, why, det = m.judge_basis(x, days, overlap=None)                 # no overlap given: the trial's 20-day blocks decide
    assert det["decision_block"] == 20 and v == "supported", why
    v, why, det = m.judge_basis(x, days, overlap=10)                   # an overlap shorter than the trial's block
    assert det["decision_block"] == 20 and det["blocks"] == [20] and v == "supported", why


def test_basis_judge_marginal_only_between_rule6_constructions(monkeypatch):
    days = _days("2019-05-01", 900)
    x = np.full(900, 0.03)

    def fake(ci, ci_pct):
        return lambda x, b, n_boot=None: {"median": 0.03, "ci": ci[b], "ci_pct": ci_pct[b], "se": 0.001, "n": 900, "block": b}
    # studentized passes, percentile fails on the 180-day blocks: undecided between two rule-compliant constructions
    monkeypatch.setattr(m, "median_ci_t", fake({20: [0.02, 0.04], 180: [0.011, 0.05]}, {20: [0.02, 0.04], 180: [0.009, 0.05]}))
    v, why, _ = m.judge_basis(x, days, overlap=180)
    assert v == "inconclusive" and "MARGINAL: studentized and percentile disagree" in why
    # the trial's 20-day CI failing does not matter once both 180-day constructions pass
    monkeypatch.setattr(m, "median_ci_t", fake({20: [0.009, 0.04], 180: [0.011, 0.05]}, {20: [0.009, 0.04], 180: [0.012, 0.05]}))
    v, why, _ = m.judge_basis(x, days, overlap=180)
    assert v == "supported", why


def test_quarterly_basis_harness_planted_and_missing():
    days = _days("2019-05-01", 700)
    S = lambda d, h: 8000.0 * (1 + 0.0005 * (date.fromisoformat(d) - date(2019, 5, 1)).days)
    b = {m.QF_B: _qf_bundle(days, S, 0.09, noise=0.004, seed=3), m.FUND_B: _fund_rows(_days("2019-05-01", 702), S),
         m.DTB3_B: _dtb3_rows(days, 2.0)}
    stat, n, v, reason = _check(m.b6b_drb_quarterly_basis(FakeArchive(b)))
    assert n >= 600 and v == "supported", reason
    assert stat["median_excess"] == pytest.approx(0.09 - m.dtb3_cont(2.0), abs=0.003)
    b[m.QF_B] = _qf_bundle(days, S, m.dtb3_cont(2.0), noise=0.004, seed=3)
    m._CACHE.clear()
    assert _check(m.b6b_drb_quarterly_basis(FakeArchive(b)))[2] == "not_supported"
    stat, n, v, reason = _check(m.b6b_drb_quarterly_basis(FakeArchive({m.QF_B: []})))
    assert v == "inconclusive" and n == 0 and m.FUND_B in reason


# ================================================================================ T-223 Friday settlement straddle ==

def test_friday_straddle_prices_with_thursday_dvol():
    d = "2024-03-29"                          # a last Friday
    s00, s08 = {d: 100.0}, {d: 101.0}
    dvol = {"2024-03-28": 50.0, "2024-03-29": 999.0}
    rows, skipped = m.friday_straddles(s00, s08, dvol, None, [d, "2024-04-05"])
    assert skipped == ["2024-04-05"] and rows[0]["monthly"] and rows[0]["quarterly"]
    T = 8 / (24 * 365)
    prem = m.bs_price(100, 100, T, 0.5, "call") + m.bs_price(100, 100, T, 0.5, "put")
    assert rows[0]["prem"] == pytest.approx(prem) and rows[0]["pnl_usd"] == pytest.approx(prem - 1.0)


def _friday_world(planted, n_years=6, seed=4):
    rng = np.random.default_rng(seed)
    days = m.fridays("2020-01-03", f"{2020 + n_years}-01-01")
    s00, s08, dvol = {}, {}, {}
    for d in days:
        dvol[m._add(d, -1)] = 60.0
        s00[d] = 30000.0
        sd = 0.6 * math.sqrt(8 / (24 * 365))
        f = 0.25 if (planted and m.is_last_friday(d)) else 1.0
        s08[d] = 30000.0 * math.exp(rng.normal(0, sd * f))
    return s00, s08, dvol, days


def test_friday_judge_planted_passes_null_fails():
    s00, s08, dvol, days = _friday_world(True)
    rows, _ = m.friday_straddles(s00, s08, dvol, None, days)
    v, why, det = m.judge_friday(rows, n_boot=NB)
    assert sum(r["monthly"] for r in rows) >= 60 and v == "supported", why
    s00, s08, dvol, days = _friday_world(False)
    rows, _ = m.friday_straddles(s00, s08, dvol, None, days)
    v, why, _ = m.judge_friday(rows, n_boot=NB)
    assert v != "supported", why


def test_friday_harness_runs_on_fake_archive():
    days = _days("2024-01-01", 200)
    S = lambda d, h: 40000.0 + (50.0 if h == 8 else 0.0)
    b = {m.FUND_B: _fund_rows(days, S), m.DELIV_B: _deliv_rows({d: 40100.0 for d in days}),
         m.DVOL_B["BTC"]: _dvol_rows(days, 55.0), m.DTB3_B: _dtb3_rows(days)}
    stat, n, v, reason = _check(m.b6b_drb_expiry_friday_straddle(FakeArchive(b)))
    assert m.MP in reason and v == "inconclusive" and 0 < n < 60 and stat["label"] == m.MP
    assert _check(m.b6b_drb_expiry_friday_straddle(FakeArchive({})))[2] == "inconclusive"


# ======================================================================================== T-269 CME vs IBIT tax ==

def _cyc(year, opt, share, basis_cost, S=100.0, k=12):
    return [{"entry": f"{year}-01-01", "expiry": f"{year}-12-31", "year": year, "S0": S, "ST": S, "opt": opt / k * S,
             "share": share / k * S, "basis_cost": basis_cost / k * S, "basis": 0.0, "T": 1 / 12,
             "bill_income": 0.0} for _ in range(k)]


def test_annual_tax_identity():
    y = m.annual_tax(_cyc(2022, 0.10, 0.30, 0.05))[2022]
    assert y["ibit_after"] == pytest.approx(0.40 - 0.37 * 0.10 - 0.20 * 0.30)
    assert y["cme_after"] == pytest.approx(0.35 * (1 - 0.268))
    assert y["diff"] == pytest.approx(0.102 * 0.10 - 0.068 * 0.30 - 0.732 * 0.05)


def test_tax_judge_planted_passes_null_fails():
    planted = [c for yr in range(2021, 2026) for c in _cyc(yr, 0.20 + 0.01 * (yr % 3), -0.05, 0.0)]
    r = m.tax_claim(planted)
    assert r["n"] == 5 and r["verdict"] == "supported", r["reason"]
    null = [c for yr in range(2021, 2026) for c in _cyc(yr, 0.05, 0.80, 0.08)]
    r = m.tax_claim(null)
    assert r["verdict"] == "not_supported" and m.MP in r["reason"]


def test_loss_carryback_control():
    yrs = {2021: {"cme_pre": 0.5, "opt": 0.1, "share": 0.4, "pre_tax": 0.5},
           2022: {"cme_pre": -0.3, "opt": 0.1, "share": -0.4, "pre_tax": -0.3}}
    out = m.carry_losses(yrs)
    assert out[2022]["cme_after"] == pytest.approx(-0.3 + 0.268 * 0.3)      # full carryback refund
    assert out[2022]["ibit_after"] == pytest.approx(-0.3)                     # net loss carried forward, no refund


def test_cme_ibit_harness_runs_on_fake_archive():
    days = _days("2021-03-20", 1700)
    px = {d: 30000.0 * (1 + 0.0003 * i) for i, d in enumerate(days)}
    S = lambda d, h: px.get(d, 30000.0)
    b = {m.DELIV_B: _deliv_rows(px), m.DVOL_B["BTC"]: _dvol_rows(days[4:], 60.0), m.DTB3_B: _dtb3_rows(days),
         m.QF_B: _qf_bundle(days, S, 0.06), m.FUND_B: _fund_rows(days, S)}
    stat, n, v, reason = _check(m.b6b_drb_cme_ibit_tax(FakeArchive(b)))
    assert n == 5 and sorted(stat["years"]) == ["2021", "2022", "2023", "2024", "2025"] and m.MP in reason
    assert set(stat["basis_sensitivity_mean_diff"]) == {"0.0%", "2.5%", "5.0%", "7.5%", "10.0%", "15.0%"}


# ===================================================================================== T-222 catalyst strangle ==

def _coin(S, K, T, iv, kind):
    return m.bs_price(S, K, T, iv, kind) / S


def _cat_rows(i, move, iv0=0.6, iv1=0.6, known=True, cur="BTC", S0=10000.0):
    ev = date(2019, 1, 1) + timedelta(days=45 * i)
    entry, exit_ = ev - timedelta(days=21), ev - timedelta(days=1)
    expiry = (ev + timedelta(days=2)).isoformat()
    exp_ms = m.expiry_ms(expiry)
    code = f"{int(expiry[8:])}{m.MONTHS3[int(expiry[5:7]) - 1]}{expiry[2:4]}"
    cat = f"cat{i:02d}"
    listed = _iso(_ms((entry - timedelta(days=30)).isoformat()))
    win = {"kind": "catalyst-window", "available_at": listed if known else _iso(_ms(ev.isoformat(), 15)),
           "value": {"catalyst": cat, "currency": cur, "category": "protocol" if i % 2 else "etf", "event": cat,
                     "event_date": ev.isoformat(), "event_time": _iso(_ms(ev.isoformat(), 15)),
                     "event_time_basis": "scheduled", "entry_day": entry.isoformat(), "exit_day": exit_.isoformat(),
                     "target_expiry": expiry, "target_expiry_code": code, "target_listed_at": listed,
                     "known_since": (entry - timedelta(days=60)).isoformat() if known else None}}
    rows = [win]
    tid = 0
    for day, S, iv in ((entry.isoformat(), S0, iv0), (exit_.isoformat(), S0 * move, iv1)):
        for hh, mm, dirn in ((11, 0, "buy"), (12, 30, "buy"), (12, 31, "sell")):
            t = _ms(day, hh, mm)
            T = (exp_ms - t) / DAY / 365
            for K in np.arange(6000.0, 14001.0, 500.0):
                for kind in ("call", "put"):
                    tid += 1
                    px = _coin(S, K, T, iv, kind)
                    rows.append({"kind": "option-trade", "available_at": _iso(t), "value": {
                        "catalyst": cat, "currency": cur, "expiry": expiry, "expiry_code": code, "strike": float(K),
                        "type": kind, "trade_id": f"{i}-{tid}", "timestamp": t,
                        "instrument_name": f"{cur}-{code}-{int(K)}-{'C' if kind == 'call' else 'P'}",
                        "price": px * (1.02 if dirn == "buy" else 0.98), "mark_price": px, "iv": iv * 100,
                        "index_price": S, "amount": 1.0, "direction": dirn}})
    return rows


def test_strangle_window_picks_25_delta_and_nets_fees():
    rows = _cat_rows(0, 1.0)
    wins, trades = m.catalyst_inputs(rows)
    w = wins["cat00:BTC"]
    r = m.strangle_window(w, trades["cat00:BTC"])
    assert r["ok"] and 0.15 < r["delta_call"] < 0.35 and -0.35 < r["delta_put"] < -0.15
    assert all(L["entry_how"] == "mark at next print" and L["exit_how"] == "mark at next print" for L in r["legs"])
    g = m.strangle_window(w, trades["cat00:BTC"], fees=False)
    assert g["ret"] > r["ret"] and r["ret"] < -0.5                 # 20 days of decay with no move or vol change


def test_catalyst_point_in_time_filter():
    rows = _cat_rows(0, 1.0, known=True) + _cat_rows(1, 1.0, known=False)
    wins, _ = m.catalyst_inputs(rows)
    assert m.pit_window(wins["cat00:BTC"]) and not m.pit_window(wins["cat01:BTC"])


def test_leg_value_falls_back_to_re_mark():
    rows = _cat_rows(0, 1.0)
    wins, trades = m.catalyst_inputs(rows)
    w = wins["cat00:BTC"]
    tr = [t for t in trades["cat00:BTC"] if not (t["instrument_name"].endswith("-11500-C") and t["_ts"] >= _ms(w["exit_day"], 12))]
    v = m.leg_value(tr, "BTC-" + w["target_expiry_code"] + "-11500-C", _ms(w["exit_day"], 12), _ms(w["exit_day"], 23),
                    m.expiry_ms(w["target_expiry"]))
    assert v["how"] == "re-marked own IV" and v["coin"] > 0


def test_catalyst_planted_passes_null_fails():
    planted = [r for i in range(22) for r in _cat_rows(i, 1.25 if i % 2 else 0.75)] + _cat_rows(30, 1.0, known=False)
    wins, trades = m.catalyst_inputs(planted)
    r = m.catalyst_claim(wins, trades, {}, n_boot=NB)
    assert r["n"] == 22 and r["stat"]["windows_pit"] == 22 and r["verdict"] == "supported", r["reason"]
    null = [r for i in range(22) for r in _cat_rows(i, 1.0)]
    wins, trades = m.catalyst_inputs(null)
    r = m.catalyst_claim(wins, trades, {}, n_boot=NB)
    assert r["verdict"] == "not_supported", r["reason"]


def test_catalyst_realised_block_height_windows_not_in_primary():
    # regression (T-222 review): a window timed from a realised block height (entry, exit and target expiry from a time
    # that was only an estimate at the entry) is reported apart and never enters the primary statistic (rule 4)
    rows = [r for i in range(22) for r in _cat_rows(i, 1.25 if i % 2 else 0.75)]
    bad = [r for i in range(22, 25) for r in _cat_rows(i, 0.75)]       # losing windows, all timed ex post
    for r in bad:
        if r["kind"] == "catalyst-window":
            r["value"]["event_time_basis"] = "realised (ex post)"
    wins, trades = m.catalyst_inputs(rows + bad)
    assert not m.ex_ante_timed(wins["cat22:BTC"]) and m.ex_ante_timed(wins["cat00:BTC"])
    r = m.catalyst_claim(wins, trades, {}, n_boot=NB)
    st = r["stat"]
    assert r["n"] == 22 and st["windows_pit"] == 25 and st["windows_primary"] == 22 and r["verdict"] == "supported", r["reason"]
    assert set(st["realised_event_time_windows"]) == {"cat22:BTC", "cat23:BTC", "cat24:BTC"}
    assert not {"cat22", "cat23", "cat24"} & set(st["per_catalyst"]) and len(st["pit_including_realised_event_time"]) == 25
    assert "realised block-height windows (reported, not in the primary statistic)" in r["reason"]


def test_catalyst_judge_below_min_n_is_never_supported():
    v, why, _ = m.judge_catalyst([0.5] * 7, n_boot=NB)
    assert v == "inconclusive"
    v, why, _ = m.judge_catalyst([-0.5] * 7, n_boot=NB)                # 0 of 7: even 13 more wins give p > 0.05
    assert v == "not_supported"


def test_catalyst_harness_on_fake_archive():
    rows = [r for i in range(3) for r in _cat_rows(i, 1.0)]
    stat, n, v, reason = _check(m.b6b_drb_catalyst_strangle(FakeArchive({m.CAT_B: rows})))
    assert n == 3 and v in ("inconclusive", "not_supported") and "Point in time" in reason
    assert _check(m.b6b_drb_catalyst_strangle(FakeArchive({})))[2] == "inconclusive"


# =========================================================================================== smile machinery ==

def test_smile_fit_recovers_skew_and_25_delta_strikes():
    S, T = 40000.0, 30 / 365
    iv = lambda x: 0.5 + 0.12 * x
    pts = [(S * math.exp(z * math.sqrt(T)), iv(z), 1.0) for z in np.linspace(-1, 1, 9)]
    f = m.smile_fit(pts, S, T)
    assert f["a"] == pytest.approx(0.5, abs=1e-9) and f["b"] == pytest.approx(0.12, abs=1e-9)
    K, ivc = m.delta_strike(f, 0.25, "call")
    assert m.bs_delta(S, K, T, ivc, "call") == pytest.approx(0.25, abs=1e-6) and K > S
    rr = m.rr_at(f)
    assert rr[0] > 0.05                                                 # call wing richer
    assert m.smile_fit(pts[:3], S, T) is None                           # one side of S only


def test_daily_smiles_from_trade_prints():
    S, d = 40000.0, "2023-03-01"
    e = "2023-03-31"
    T = m._dte(d, e) / 365
    trades = []
    for k, K in enumerate(np.linspace(30000, 50000, 11)):
        x = math.log(K / S) / math.sqrt(T)
        for hh in (7, 8, 12):                                           # the 12:00 print is outside the sample
            trades.append({"timestamp": _ms(d, hh), "instrument_name": f"BTC-31MAR23-{int(K)}-C", "expiry": e,
                           "strike": float(K), "iv": (0.6 + 0.1 * x + (0.5 if hh == 12 else 0.0)) * 100,
                           "index_price": S, "amount": 1.0})
    sm = m.daily_smiles(trades)
    f = sm[d]["fits"][e]
    assert sm[d]["S"] == S and f["a"] == pytest.approx(0.6, abs=1e-6) and f["n"] == 22


# ======================================================================================= T-257 RR skew harvest ==

def _smile_world(ndays, S, ivf, start="2022-01-01", step=7, horizon=60):
    d0 = date.fromisoformat(start)
    days = [(d0 + timedelta(days=i)).isoformat() for i in range(ndays)]
    exps = [(d0 + timedelta(days=i)).isoformat() for i in range(3, ndays + horizon, step)]
    sm = {}
    for i, d in enumerate(days):
        s, fits = S[i], {}
        for e in exps:
            dte = m._dte(d, e)
            if 1 <= dte <= horizon:
                T = dte / 365
                f = m.smile_fit([(s * math.exp(z * 0.5 * math.sqrt(T)), ivf(z * 0.5, T), 1.0) for z in np.linspace(-2, 2, 9)], s, T)
                if f:
                    fits[e] = f
        sm[d] = {"S": s, "fits": fits}
    settle = {e: S[(date.fromisoformat(e) - d0).days] for e in exps if (date.fromisoformat(e) - d0).days < len(S)}
    return sm, settle


def _local_vol_path(n, seed):
    rng = np.random.default_rng(seed)
    s = [40000.0]
    for _ in range(n - 1):
        sg = 0.9 if s[-1] > s[max(0, len(s) - 10)] else 0.25            # upside vol above the call wing's IV
        s.append(s[-1] * math.exp(rng.normal(-0.5 * sg * sg / 365, sg / math.sqrt(365))))
    return np.array(s)


def test_rr_claim_planted_passes_null_fails(monkeypatch):
    monkeypatch.setattr(m, "T257_MIN_N", 15)
    skew = lambda x, T: 0.45 + 0.25 * x                                  # RR30 ~ +17 vol points
    sm, st = _smile_world(500, _gbm(700, 0.40, 1), skew)                 # realised 40% = the put wing: the short call earns
    r = m.rr_claim(sm, st, n_boot=NB)
    assert r["n"] >= 15 and r["verdict"] == "supported", r["reason"]
    sm, st = _smile_world(500, _local_vol_path(700, 3), skew)            # upside realised vol far above the call IV
    r = m.rr_claim(sm, st, n_boot=NB)
    assert r["verdict"] == "not_supported", r["reason"]


def test_rr_no_signal_when_smile_flat():
    sm, st = _smile_world(60, _gbm(200, 0.4, 2), lambda x, T: 0.45)
    r = m.rr_claim(sm, st, n_boot=NB)
    assert r["n"] == 0 and r["verdict"] == "inconclusive"


def _monthly_world(days, S, ivf, expiries):
    """Smiles on a Deribit-like listing: only the given (last-Friday monthly) expiries."""
    sm = {}
    for i, d in enumerate(days):
        s, fits = S[i], {}
        for e in expiries:
            dte = m._dte(d, e)
            if 1 <= dte <= 120:
                T = dte / 365
                f = m.smile_fit([(s * math.exp(z * 0.5 * math.sqrt(T)), ivf(z * 0.5, T), 1.0) for z in np.linspace(-2, 2, 9)], s, T)
                if f:
                    fits[e] = f
        sm[d] = {"S": s, "fits": fits}
    return sm


MONTHLIES = ["2022-01-28", "2022-02-25", "2022-03-25", "2022-04-29", "2022-05-27", "2022-06-24", "2022-07-29"]


def test_rr_trade_holds_30_days_and_re_marks():
    # regression (T-257 review): the claim's statistic is a 30-day P&L. An expiry beyond the hold (25FEB22 at 44 DTE) is
    # re-marked on day 30 at that day's fitted smile, not held to expiry; with a flat smile and a constant index the P&L
    # is exactly the Black-Scholes value change of the two legs over 30 days (the hedge earns nothing).
    days = _days("2022-01-01", 120)
    S = np.full(len(days), 40000.0)
    sm = _monthly_world(days, S, lambda x, T: 0.45, MONTHLIES)
    settle = {e: 40000.0 for e in MONTHLIES[:4]}
    t = m.rr_trade("2022-01-12", sm, settle, 0.10)
    assert t["expiry"] == "2022-02-25" and t["exit"] == "2022-02-11"
    (_, (Kc, ivc), (Kp, ivp)) = m.rr_at(sm["2022-01-12"]["fits"]["2022-02-25"])
    T0, T1 = m._dte("2022-01-12", "2022-02-25") / 365, m._dte("2022-02-11", "2022-02-25") / 365
    want = (-(m.bs_price(40000.0, Kc, T1, 0.45, "call") - m.bs_price(40000.0, Kc, T0, 0.45, "call"))
            + (m.bs_price(40000.0, Kp, T1, 0.45, "put") - m.bs_price(40000.0, Kp, T0, 0.45, "put"))) / 40000.0
    assert t["pnl"] == pytest.approx(want, rel=1e-6, abs=1e-12)
    t = m.rr_trade("2022-01-01", sm, settle, 0.10)                      # 28JAN22 at 27 DTE: settles inside the hold
    assert t["exit"] == t["expiry"] == "2022-01-28"
    assert m.rr_trade("2022-01-01", sm, {}, 0.10) is None               # an expiry inside the hold needs its delivery price


def test_rr_holds_never_exceed_30_days_and_pooled_blocks_follow_the_longest_hold():
    days = _days("2022-01-01", 200)
    sm = _monthly_world(days, _gbm(200, 0.4, 7), lambda x, T: 0.45 + 0.25 * x, MONTHLIES)
    settle = {e: 40000.0 for e in MONTHLIES}
    tr = m.signal_trades(sm, settle)
    holds = [(date.fromisoformat(t["exit"]) - date.fromisoformat(t["day"])).days for t in tr]
    exp_dte = [m._dte(t["day"], t["expiry"]) for t in tr]
    assert tr and max(holds) == 30 and max(exp_dte) > 40               # 44-DTE monthlies held 30 days, not to expiry
    v, why, det = m.judge_pooled(tr, m.T257_HOLD, m.T257_MIN_N, 0.55, NB)
    assert det["block"] == 60 and det["longest_hold"] == 30 and det["per_start"]["offsets"] == 30
    # rule 10 guard: entries held longer than the nominal hold widen the blocks and the per-start offsets
    long = [{"day": d, "exit": m._add(d, 45), "pnl": 0.01} for d in _days("2022-01-01", 400)]
    v, why, det = m.judge_pooled(long, 30, 5, None, NB)
    assert det["hold"] == 45 and det["block"] == 90 and det["per_start"]["offsets"] == 45


def test_judge_pooled_real_min_n():
    days = _days("2022-01-01", 1500)
    rng = np.random.default_rng(5)
    tr = [{"day": d, "exit": m._add(d, 30), "pnl": 0.01 + 0.005 * rng.normal()} for d in days]
    v, why, det = m.judge_pooled(tr, 30, m.T257_MIN_N, 0.55, NB)
    assert det["n"] >= 40 and v == "supported", why
    tr = [{"day": d, "exit": m._add(d, 30), "pnl": 0.005 * rng.normal()} for d in days]
    v, why, _ = m.judge_pooled(tr, 30, m.T257_MIN_N, 0.55, NB)
    assert v == "not_supported", why


# ================================================================================ T-262 calendar on inversion ==

def _with_fwd(sm, carry=0.05):
    """Attach each expiry's forward F = S exp(carry T) to a synthetic smile world (daily_smiles' ``fwd``)."""
    for d, s in sm.items():
        s["fwd"] = {e: s["S"] * math.exp(carry * f["T"]) for e, f in s["fits"].items()}
    return sm


def test_calendar_claim_planted_passes_null_fails():
    inv = lambda x, T: 0.80 if T * 365 <= 35 else 0.50
    sm, st = _smile_world(500, _gbm(700, 0.35, 5), inv, horizon=125)     # low realised vol: the rich front decays
    r = m.calendar_claim(_with_fwd(sm), st, n_boot=NB)
    assert r["n"] >= 30 and r["verdict"] == "supported", r["reason"]
    sm, st = _smile_world(500, _gbm(700, 2.5, 5), inv, horizon=125)      # extreme realised vol: short front gamma loses
    r = m.calendar_claim(_with_fwd(sm), st, n_boot=NB)
    assert r["verdict"] == "not_supported", r["reason"]


def _episodes(n_ep=40, run=14, gap=30, hold=14, walk_pnl=0.02, rest_pnl=0.05):
    """Signal days in runs of ``run`` consecutive days, ``gap`` quiet days apart: a non-overlapping walk can take only
    the first day of each run (P&L alternating +/- walk_pnl, mean 0); the other days (rest_pnl) only an overlapping
    pool can take."""
    tr, d0 = [], date(2022, 1, 3)
    for k in range(n_ep):
        for j in range(run):
            d = (d0 + timedelta(days=k * (run + gap) + j)).isoformat()
            tr.append({"day": d, "exit": m._add(d, hold), "pnl": (walk_pnl if k % 2 else -walk_pnl) if j == 0 else rest_pnl})
    return tr


def test_calendar_judge_is_the_all_start_pool_of_the_trials_non_overlapping_walks():
    # regression (T-262 refutation, defect 1): the trial names 'non-overlapping entries; block bootstrap'. The old
    # primary statistic pooled every overlapping signal day, so entries no non-overlapping walk can take decided a
    # 'supported'. The criterion now reads the all-start pool of the walks (each start's walk weighted equally); the
    # every-signal-day pool is secondary and a disagreement is undecided (rule 11), never a pass.
    tr = _episodes()
    v_old, _, old = m.judge_pooled(tr, m.T262_HOLD, m.T262_MIN_N, None, NB)
    assert v_old == "supported" and old["ci"][0] > 0                     # the overlapping reading alone would pass
    v, why, det = m.judge_walks(tr, m.T262_HOLD, m.T262_MIN_N, NB)
    assert v == "inconclusive" and det["ok"] is None and "disagree" in why, why
    assert det["ci"][0] < 0 < det["ci"][1] and det["pooled"]["ci"][0] > 0 and det["n"] >= m.T262_MIN_N
    assert det["walks"] == det["hold"] == 14 and det["block"] == 28 and len(det["starts"]) == 14
    assert det["entries_in_walks"] < len(tr) / 5 and det["starts_pass"] == 0
    walk_means = [s["mean"] for s in det["starts"]]
    assert det["mean"] == pytest.approx(np.mean(walk_means), abs=1e-12)  # equal weight on every start's walk
    assert all(s["ci"][0] is not None and not s["pass"] for s in det["starts"])
    # both readings fail -> not_supported at n >= min_n; both pass -> supported
    tr0 = _episodes(rest_pnl=0.0)
    assert m.judge_walks(tr0, m.T262_HOLD, m.T262_MIN_N, NB)[0] == "not_supported"
    tr1 = [dict(t, pnl=0.01 + 0.001 * (i % 3)) for i, t in enumerate(_episodes())]
    v, why, det = m.judge_walks(tr1, m.T262_HOLD, m.T262_MIN_N, NB)
    assert v == "supported" and det["starts_pass"] == det["walks"], why


def test_daily_smiles_recovers_each_expiry_forward_from_prints():
    # regression (T-262 refutation, defect 3): Deribit IVs are Black-76 on each expiry's own forward (coin price =
    # Black-76 / F, r = 0); the forward each print's IV is quoted on is recovered from its coin price
    S, d = 40000.0, "2023-03-01"
    trades = []
    for e, F in (("2023-03-17", 40100.0), ("2023-05-26", 40800.0)):
        for K in np.linspace(30000, 50000, 11):
            for hh in (7, 8):
                ts = _ms(d, hh)
                Tp = (m.expiry_ms(e) - ts) / DAY / 365
                for kind in ("call", "put"):
                    iv = 0.6 + 0.05 * math.log(K / F)
                    trades.append({"timestamp": ts, "instrument_name": f"BTC-X-{int(K)}-{kind[0].upper()}", "expiry": e,
                                   "strike": float(K), "iv": iv * 100, "index_price": S, "amount": 1.0,
                                   "price": m.bs_price(F, K, Tp, iv, kind) / F})
    assert m.print_forward(trades[0]["price"], 30000.0, (m.expiry_ms("2023-03-17") - _ms(d, 7)) / DAY / 365,
                           trades[0]["iv"] / 100, "call", S) == pytest.approx(40100.0, rel=1e-9)
    sm = m.daily_smiles(trades)
    assert sm[d]["fwd"]["2023-03-17"] == pytest.approx(40100.0, rel=1e-8)
    assert sm[d]["fwd"]["2023-05-26"] == pytest.approx(40800.0, rel=1e-8)
    for t in trades:
        t.pop("price")
    assert m.daily_smiles(trades)[d]["fwd"] == {}                       # no coin price: no forward, never spot


def _cal_day(S=40000.0, front_iv=0.80, back=lambda x: 0.50, carry=0.10, day="2022-01-03"):
    """One smile day plus its re-mark 14 days later: a 25-DTE front, an 88-DTE back, forwards S exp(carry T)."""
    sm = {}
    for d in (day, m._add(day, 14)):
        fits, fwd = {}, {}
        for e, ivf in (("2022-01-28", lambda x: front_iv), ("2022-04-01", back)):
            T = m._dte(d, e) / 365
            F = S * math.exp(carry * T)
            pts = [(F * math.exp(z * math.sqrt(T)), ivf(z), 1.0) for z in np.linspace(-1, 1, 9)]
            fits[e], fwd[e] = m.smile_fit(pts, S, T), F
        sm[d] = {"S": S, "fits": fits, "fwd": fwd}
    return sm


def test_calendar_legs_priced_black76_on_each_expiry_forward_and_atm_at_the_forward():
    # regression (T-262 refutation, defect 3): every leg is priced Black-76 on its own expiry's forward (entry and
    # re-mark), not Black-Scholes on spot; ATM IV is read at K = F of each expiry; a leg without a forward is not priced
    sm, day = _cal_day(), "2022-01-03"
    x = m._add(day, 14)
    t = m.calendar_trade(day, sm, {})
    assert t is not None and t["front"] == "2022-01-28" and t["back"] == "2022-04-01" and t["exit"] == x
    K = min(sm[day]["fits"]["2022-01-28"]["strikes"], key=lambda k: abs(k - 40000.0))
    b76 = lambda d, e, iv: m.bs_price(sm[d]["fwd"][e], K, m._dte(d, e) / 365, iv, "call")
    iv_f = lambda d: m.smile_iv(sm[d]["fits"]["2022-01-28"], K)
    iv_b = lambda d: m.smile_iv(sm[d]["fits"]["2022-04-01"], K)
    want = ((b76(x, "2022-04-01", iv_b(x)) - b76(x, "2022-01-28", iv_f(x)))
            - (b76(day, "2022-04-01", iv_b(day)) - b76(day, "2022-01-28", iv_f(day)))) / 40000.0
    assert t["pnl"] == pytest.approx(want, rel=1e-9, abs=1e-12)
    spot = ((m.bs_price(40000.0, K, m._dte(x, "2022-04-01") / 365, iv_b(x), "call")
             - m.bs_price(40000.0, K, m._dte(x, "2022-01-28") / 365, iv_f(x), "call"))
            - (m.bs_price(40000.0, K, m._dte(day, "2022-04-01") / 365, iv_b(day), "call")
               - m.bs_price(40000.0, K, m._dte(day, "2022-01-28") / 365, iv_f(day), "call"))) / 40000.0
    assert abs(t["pnl"] - spot) > 1e-4                                   # Black-Scholes on spot is a different price
    # ATM at the forward: a back smile rising with moneyness is 0.545 at spot (inversion 5.5 points) but 0.56 at its
    # forward (2.4% above spot at 88 DTE: inversion 4 points) -> no entry
    slope = lambda z: 0.56 + 0.30 * z
    sm2 = _cal_day(front_iv=0.60, back=slope)
    fb, Fb = sm2[day]["fits"]["2022-04-01"], sm2[day]["fwd"]["2022-04-01"]
    assert m.smile_iv(fb, Fb) == pytest.approx(0.56, abs=1e-9) and 0.60 - m.smile_iv(fb, 40000.0) > 0.054
    assert m.calendar_trade(day, sm2, {}) is None
    del sm[x]["fwd"]["2022-04-01"]
    assert m.calendar_trade(day, sm, {}) is None                        # no forward at the re-mark: not priced
    del sm[day]["fwd"]["2022-01-28"]
    assert m.calendar_trade(day, sm, {}) is None


def test_calendar_fees_and_front_rules():
    # regressions (T-262 refutation, defects 2, 4, 5): the module's fee schedule is a control; the front rule is a
    # named choice with alternatives inside the claim's 7-30 DTE
    sm, day = _cal_day(), "2022-01-03"
    g, f = m.calendar_trade(day, sm, {}), m.calendar_trade(day, sm, {}, fees=True)
    assert 0 < (g["pnl"] - f["pnl"]) * 40000.0 <= 4 * m.OPT_TAKER * 40000.0 + 1e-9
    fits = {e: {"n": n} for e, n in (("2022-01-14", 50), ("2022-01-21", 30), ("2022-01-28", 20), ("2022-02-01", 10),
                                     ("2022-04-01", 5), ("2022-01-07", 99))}
    s = {"fits": fits}
    want = {"most": "2022-01-14", "outlives": "2022-01-21", "nearest30": "2022-02-01", "nearest7": "2022-01-14",
            "monthly": "2022-01-28"}
    assert set(m.T262_FRONTS) == set(want)
    for rule, e in want.items():
        assert m.calendar_legs("2022-01-03", s, rule) == (e, "2022-04-01"), rule


def test_calendar_claim_reports_cost_control_cis_front_rules_and_borderline(monkeypatch):
    # regressions (T-262 refutation, defects 2 and 4): every cost control carries its CI and criterion, not only its
    # mean; P&L basis is stated (rule 9); every front rule is reported; a pass that flips under a control is BORDERLINE
    inv = lambda x, T: 0.80 if T * 365 <= 35 else 0.50
    sm, st = _smile_world(500, _gbm(700, 0.35, 5), inv, horizon=125)
    sm = _with_fwd(sm)
    orig = m.calendar_trade

    def slipped_loses(day, smiles, settle, slip=0.0, **kw):
        t = orig(day, smiles, settle, slip=slip, **kw)
        return dict(t, pnl=t["pnl"] - 1.0) if t is not None and slip else t
    monkeypatch.setattr(m, "calendar_trade", slipped_loses)
    r = m.calendar_claim(sm, st, n_boot=NB)
    stat = r["stat"]
    assert r["verdict"] == "supported" and stat["borderline"] and "BORDERLINE" in r["reason"], r["reason"]
    assert "1 vol point slippage per leg" in stat["flips_under"]
    for k in ("1 vol point slippage per leg", "Deribit fees", "fees + 1 vol point slippage", "IV x0.9", "IV x1.1"):
        c = stat["controls"][k]
        assert c["ci"][0] is not None and c["ok"] in (True, False, None), k
    assert stat["controls"]["1 vol point slippage per leg"]["ok"] is False
    assert set(stat["front_rules"]) == set(m.T262_FRONTS) - {"most"} and stat["front_rule"] == "most"
    assert "gross" in stat["pnl_basis"] and "P&L gross" in r["reason"] and "fees + 1 vol point slippage" in r["reason"]
    fe = stat["front_expired_in_hold"]
    assert fe["entries"] + fe["alive_entries"] == stat["judge"]["entries"]
    monkeypatch.setattr(m, "calendar_trade", orig)
    r = m.calendar_claim(sm, st, n_boot=NB)
    assert not r["stat"]["flips_under"] or r["stat"]["borderline"]


def test_daily_trade_harnesses_missing_and_on_fake_archive():
    for h in (m.b6b_drb_rr_skew_harvest, m.b6b_drb_calendar_inversion):
        stat, n, v, reason = _check(h(FakeArchive({m.DELIV_B: []})))
        assert v == "inconclusive" and m.DAILY_TRADES_B in reason and "history.deribit.com" in reason
    S = 40000.0
    rows = []
    for d in _days("2022-01-01", 20):
        for e in ("2022-01-28", "2022-02-25", "2022-03-25", "2022-04-29"):
            T = m._dte(d, e) / 365
            for K in np.linspace(30000, 50000, 9):
                x = math.log(K / S) / math.sqrt(T)
                for kind in ("call", "put"):
                    rows.append({"kind": "option-trade", "available_at": _iso(_ms(d, 8)), "value": {
                        "timestamp": _ms(d, 8), "instrument_name": "x", "expiry": e, "strike": float(K), "type": kind,
                        "iv": (0.5 + 0.15 * x) * 100, "index_price": S, "amount": 1.0,
                        "price": m.bs_price(S, K, T, 0.5 + 0.15 * x, kind) / S}})
    b = {m.DAILY_TRADES_B: rows, m.DELIV_B: _deliv_rows({"2022-01-28": S, "2022-02-25": S})}
    for h in (m.b6b_drb_rr_skew_harvest, m.b6b_drb_calendar_inversion):
        stat, n, v, reason = _check(h(FakeArchive(b)))
        assert v == "inconclusive" and m.MP in reason


# ======================================================================================= T-263 FOMC implied move ==

def _fomc_rows(i, realised_mult, S=30000.0, iv=0.5):
    d = (date(2022, 1, 26) + timedelta(days=45 * i)).isoformat()
    dec = _ms(d, 19)
    exp = m._add(d, 1)
    code = f"{int(exp[8:])}{m.MONTHS3[int(exp[5:7]) - 1]}{exp[2:4]}"
    rows = [{"kind": "fomc-window", "available_at": _iso(dec - DAY),
             "value": {"decision_day": d, "decision_time": _iso(dec), "currency": "BTC", "target_expiry": exp,
                       "target_expiry_code": code}}]
    t = dec - HOUR
    T = (m.expiry_ms(exp) - t) / DAY / 365
    for K in (S - 1000, S, S + 1000):
        for kind in ("call", "put"):
            px = m.bs_price(S, K, T, iv, kind) / S
            rows.append({"kind": "option-trade", "available_at": _iso(t), "value": {
                "decision_day": d, "currency": "BTC", "timestamp": t, "strike": float(K), "type": kind,
                "instrument_name": f"BTC-{code}-{int(K)}-{'C' if kind == 'call' else 'P'}", "mark_price": px, "price": px,
                "index_price": S, "iv": iv * 100}})
    implied = (m.bs_price(S, S, T, iv, "call") + m.bs_price(S, S, T, iv, "put")) / S
    settle = {exp: S * (1 + realised_mult * implied * (1 if i % 2 else -1))}
    return rows, settle


def _fomc_world(mults):
    rows, settle = [], {}
    for i, k in enumerate(mults):
        r, s = _fomc_rows(i, k)
        rows += r
        settle.update(s)
    return rows, settle


def test_fomc_planted_passes_null_fails():
    rows, settle = _fomc_world([0.2] * 20)
    wins, trades = m.fomc_inputs(rows)
    r = m.fomc_claim(wins, trades, settle, {}, n_boot=NB)
    assert r["n"] == 20 and r["verdict"] == "supported", r["reason"]
    rows, settle = _fomc_world([0.5, 1.5] * 10)                          # realised = implied on average
    wins, trades = m.fomc_inputs(rows)
    r = m.fomc_claim(wins, trades, settle, {}, n_boot=NB)
    assert r["verdict"] == "not_supported" and abs(r["stat"]["judge"]["mean"]) < 1e-9, r["reason"]


def test_fomc_harness_missing_reports_dvol_control_then_runs():
    days = _days("2022-01-01", 400)
    fomc = [{"available_at": "2022-01-25T00:00:00+00:00", "value": {"decision_day": d, "scheduled": True, "future": False}}
            for d in ("2022-01-26", "2022-03-16", "2022-05-04")]
    lvl = lambda d: 60.0 if d not in ("2022-01-26", "2022-03-16", "2022-05-04") else 57.0
    b = {m.DVOL_B["BTC"]: _dvol_rows(days, lvl), m.FOMC_B: fomc, m.DELIV_B: []}
    stat, n, v, reason = _check(m.b6b_drb_fomc_event_straddle(FakeArchive(b)))
    assert v == "inconclusive" and m.FOMC_TRADES_B in reason and stat["dvol_control"]["mean"] == pytest.approx(-3.0)
    rows, settle = _fomc_world([0.2] * 18)
    b.update({m.FOMC_TRADES_B: rows, m.DELIV_B: _deliv_rows(settle)})
    m._CACHE.clear()
    stat, n, v, reason = _check(m.b6b_drb_fomc_event_straddle(FakeArchive(b)))
    assert n == 18 and v == "supported", reason


# ====================================================================================== T-268 DVOL futures basis ==

def _dvolf_world(diffs, noise_lag_h=2):
    rows = []
    for i, dd in enumerate(diffs):
        e = (date(2023, 1, 4) + timedelta(days=7 * i)).isoformat()
        exp = m.expiry_ms(e)
        inst = f"BTCDVOL_USDC-{i}"
        settle = 50.0 + i % 5
        for lag, mark in ((-noise_lag_h, settle + dd), (30, settle + dd + 9)):   # the far trade must not be picked
            t = exp - 7 * DAY + lag * HOUR
            rows.append({"kind": "future-trade", "available_at": _iso(t), "value": {
                "instrument_name": inst, "expiry": m._iso(exp), "timestamp": t, "price": mark + 0.1, "mark_price": mark,
                "index_price": 49.0, "amount": 1.0, "direction": "buy"}})
        rows.append({"kind": "future-settlement", "available_at": _iso(exp),
                     "value": {"instrument_name": inst, "expiry": m._iso(exp), "delivery_price": settle}})
    return rows


def test_dvol_futures_planted_passes_null_fails():
    rng = np.random.default_rng(6)
    tr, st = m.dvolf_inputs(_dvolf_world(3.0 + 0.5 * rng.normal(size=14)))
    pts, drop = m.dvolf_points(tr, st)
    assert len(pts) == 14 and not drop and all(abs(p["lag_h"]) <= 2 for p in pts)
    r = m.dvolf_claim(pts, drop, n_boot=NB)
    assert r["verdict"] == "supported" and r["stat"]["target_2_vol_points_met"], r["reason"]
    tr, st = m.dvolf_inputs(_dvolf_world([2.0, -2.0] * 7))
    r = m.dvolf_claim(*m.dvolf_points(tr, st), n_boot=NB)
    assert r["verdict"] == "not_supported", r["reason"]


def test_dvol_futures_harness_missing_and_present():
    stat, n, v, reason = _check(m.b6b_drb_dvol_futures_basis(FakeArchive({})))
    assert v == "inconclusive" and "get_last_trades_by_instrument_and_time" in reason
    rows = _dvolf_world([3.0] * 13)
    stat, n, v, reason = _check(m.b6b_drb_dvol_futures_basis(FakeArchive({m.DVOLF_B: rows})))
    assert n == 13 and v == "supported", reason


# ================================================================================== book snapshots: T-195 / 196 ==

def _book_rows(start, hours, codes, r_box=None, bill=0.0, bad=(), spread=0.0001, S=80000.0, oi=None):
    """Hourly declared-bundle rows: futures at F = S exp(0.05 T); option mids from Black-76 on F/coin, with the box
    forward F' = S exp(r_box T) when r_box is given (mid box rate = r_box); ``bad`` strikes carry +0.01 coin on the call."""
    rows = []
    t0 = _ms(start)
    for h in range(hours):
        ts = t0 + h * HOUR
        cap = _iso(ts)
        for code in codes:
            e = m.code_date(code)
            T = (m.expiry_ms(e) - ts) / DAY / 365
            F = S * math.exp(0.05 * T)
            Fp = S * math.exp(r_box * T) if r_box is not None else F
            rows.append({"kind": "future", "available_at": cap, "value": {"capture_ts": cap, "instrument": f"BTC-{code}",
                                                                          "expiry": code, "bid": F - 1, "ask": F + 1,
                                                                          "mark": F, "index_price": S}})
            for K in np.arange(round(0.8 * F, -3), 1.2 * F, 4000.0):
                for kind in ("call", "put"):
                    mid = m.bs_price(Fp, K, T, 0.5, kind) / Fp
                    if kind == "call" and K in bad:
                        mid += 0.01
                    rows.append({"kind": "option", "available_at": cap, "value": {
                        "capture_ts": cap, "instrument": f"BTC-{code}-{int(K)}-{kind[0].upper()}", "expiry": code,
                        "strike": float(K), "type": kind, "bid": mid - spread, "ask": mid + spread, "mark": mid,
                        "underlying": F, "underlying_index": f"BTC-{code}", "index_price": S,
                        "oi": (oi or {}).get(code, 1.0)}})
    return rows


def test_parity_obs_and_persistence():
    rows = _book_rows("2026-11-01", 3, ["25DEC26"])
    a = FakeArchive({m.HOURLY_BOOK_B: rows})
    snaps, names = m.book_snapshots(a)
    assert len(snaps) == 3 and names == [m.HOURLY_BOOK_B]
    obs = [o for s in snaps for o in m.parity_obs(s, m.listed_future_codes(s))]
    assert obs and max(o["dev"] for o in obs) < 1e-9 and not any(o["exceed"] for o in obs)
    assert m.persistence_hours(obs) == 0.0
    assert all(abs(o["K"] / o["F"] - 1) <= 0.10 for o in obs)


def test_listed_future_codes_from_underlying_index():
    # regression (T-195 review): a snapshot without futures rows keeps every expiry whose option underlying_index names a
    # listed future (weeklies and monthlies too), not only the archived quarterlies; SYN. underlyings never count
    rows = _book_rows("2026-10-15", 1, ["23OCT26", "30OCT26", "27NOV26", "25DEC26"])
    opts = [r["value"] for r in rows if r["kind"] == "option"]
    for o in opts:
        if o["expiry"] == "23OCT26":
            o["underlying_index"] = "SYN.BTC-23OCT26"
    s = {"ts": _ms("2026-10-15", 9), "options": [{**o, "code": o["expiry"]} for o in opts], "futures": {}, "S": 80000.0}
    assert m.listed_future_codes(s, {"BTC-25DEC26"}) == {"30OCT26", "27NOV26", "25DEC26"}
    assert m.listed_future_codes(s) == {"30OCT26", "27NOV26", "25DEC26"}
    obs = m.parity_obs(s, m.listed_future_codes(s))
    assert {o["code"] for o in obs} == {"30OCT26", "27NOV26", "25DEC26"}         # 23OCT26 (SYN., 8 DTE) excluded
    for o in s["options"]:
        o["underlying_index"] = "index_price"                         # no listed future referenced: only the quarterly
    assert m.listed_future_codes(s, {"BTC-25DEC26"}) == {"25DEC26"}


def test_parity_planted_passes_null_fails():
    rows = _book_rows("2026-11-01", 168, ["25DEC26", "26MAR27"])
    snaps, names = m.book_snapshots(FakeArchive({m.HOURLY_BOOK_B: rows}))
    r = m.parity_claim(snaps, set(), names, True, n_boot=NB)
    assert r["n"] >= 500 and r["verdict"] == "supported", r["reason"]
    rows = _book_rows("2026-11-01", 168, ["25DEC26", "26MAR27"], bad=(80000.0, 84000.0))
    snaps, names = m.book_snapshots(FakeArchive({m.HOURLY_BOOK_B: rows}))
    r = m.parity_claim(snaps, set(), names, True, n_boot=NB)
    assert r["verdict"] == "not_supported" and r["stat"]["judge"]["persistence_h"] > 1.0, r["reason"]


def test_box_rates_recover_planted_rate():
    rows = _book_rows("2026-11-01", 1, ["26MAR27"], r_box=0.09, spread=0.0)
    snaps, _ = m.book_snapshots(FakeArchive({m.HOURLY_BOOK_B: rows}))
    rs = m.box_rates(snaps[0], "26MAR27")
    mids = [b["r_mid"] for b in rs if b["r_mid"] is not None]
    assert rs and np.median(mids) == pytest.approx(0.09, abs=1e-6)
    assert all(b["r_exec"] < b["r_mid"] for b in rs if b["r_exec"] is not None)


def test_quarterly_box_planted_passes_null_fails():
    bills = m.Bills({"2026-10-30": 2.0})
    oi = {"26MAR27": 100.0, "25JUN27": 90.0, "25DEC26": 1.0}
    rows = _book_rows("2026-11-01", 216, ["25DEC26", "26MAR27", "25JUN27"], r_box=m.dtb3_cont(2.0) + 0.08, oi=oi)
    snaps, names = m.book_snapshots(FakeArchive({m.HOURLY_BOOK_B: rows}))
    assert m.quarterly_codes(snaps[0])[:2] == ["26MAR27", "25JUN27"]
    r = m.box_claim(snaps, bills, names, True, n_boot=NB)
    assert r["n"] >= 200 and r["verdict"] == "supported", r["reason"]
    rows = _book_rows("2026-11-01", 216, ["26MAR27", "25JUN27"], r_box=m.dtb3_cont(2.0), oi=oi)
    snaps, names = m.book_snapshots(FakeArchive({m.HOURLY_BOOK_B: rows}))
    r = m.box_claim(snaps, bills, names, True, n_boot=NB)
    assert r["verdict"] == "not_supported", r["reason"]


def test_book_harnesses_daily_captures_partial_and_missing():
    assert _check(m.b6b_drb_parity_violations(FakeArchive({})))[2] == "inconclusive"
    rows = _book_rows("2026-10-14", 1, ["25DEC26", "26MAR27"])
    daily = [{"observed_at": r["available_at"], "available_at": r["available_at"], "value": {k: v for k, v in r["value"].items()
                                                                                          if k != "capture_ts"}}
             for r in rows if r["kind"] == "option"]
    b = {"deribit-book-BTC-2026-10-14": daily, m.DTB3_B: _dtb3_rows(_days("2026-10-01", 20)),
         m.QF_B: [{"available_at": "2026-10-14T08:00:00+00:00", "value": {"instrument": "BTC-25DEC26"}},
                  {"available_at": "2026-10-14T08:00:00+00:00", "value": {"instrument": "BTC-26MAR27"}}]}
    for h in (m.b6b_drb_parity_violations, m.b6b_drb_quarterly_box_rate):
        stat, n, v, reason = _check(h(FakeArchive(b)))
        assert v == "inconclusive" and m.HOURLY_BOOK_B in reason and n > 0
    stat, n, v, reason = _check(m.b6b_drb_box_rate_capture_days(FakeArchive(b)))
    assert v == "inconclusive" and n == 1 and m.BOX_MONTHLY_B in reason


# =========================================================================================== T-260 capture days ==

def _tardis_rows(days, r_box, S=50000.0, dte=60):
    rows = []
    for d in days:
        e = m._add(d, dte)
        code = f"{int(e[8:])}{m.MONTHS3[int(e[5:7]) - 1]}{e[2:4]}"
        T = (m.expiry_ms(e) - _ms(d)) / DAY / 365
        Fp = S * math.exp(r_box * T)
        rows.append({"kind": "capture", "available_at": d + "T00:01:00+00:00", "value": {"capture_day": d}})
        for K in (S - 2000, S - 1000, S + 1000, S + 2000):
            for kind in ("call", "put"):
                mid = m.bs_price(Fp, K, T, 0.6, kind) / Fp
                rows.append({"kind": "option-ticker", "available_at": d + "T00:00:01+00:00", "value": {
                    "capture_day": d, "instrument": f"BTC-{code}-{K}-{kind[0].upper()}", "expiry": e, "expiry_code": code,
                    "dte": T * 365, "strike": float(K), "type": kind, "snap": "first",
                    "ticker": {"best_bid_price": mid - 0.0002, "best_ask_price": mid + 0.0002, "mark_price": mid,
                               "index_price": S, "underlying_price": S * math.exp(0.05 * T)}}})
    return rows


def test_capture_days_planted_passes_null_fails():
    days = [f"{y}-{mo:02d}-01" for y in range(2020, 2026) for mo in range(1, 13)][:64]
    bills = m.Bills({"2019-12-31": 2.0})
    for r_add, want in ((0.04, "supported"), (0.0, "not_supported")):
        snaps = m.tardis_snapshots(_tardis_rows(days, m.dtb3_cont(2.0) + r_add))
        rates = [m.capture_day_rate(s) for s in snaps]
        assert all(r is not None for r in rates)
        assert np.median([r["r_mid"] for r in rates]) == pytest.approx(m.dtb3_cont(2.0) + r_add, abs=1e-6)
        r = m.capture_claim(snaps, bills, [m.BOX_MONTHLY_B], True, [])
        assert r["n"] == 64 and r["verdict"] == want, r["reason"]


def test_capture_days_harness_with_tardis_bundle():
    days = [f"2020-{mo:02d}-01" for mo in range(1, 13)]
    b = {m.BOX_MONTHLY_B: _tardis_rows(days, 0.08), m.DTB3_B: _dtb3_rows(_days("2019-12-01", 400))}
    stat, n, v, reason = _check(m.b6b_drb_box_rate_capture_days(FakeArchive(b)))
    assert n == 12 and v == "inconclusive" and stat["judge"]["fraction"] == 1.0


# ===================================================================================================== registry ==

def test_registry_names_and_map():
    assert set(m.THEORY_MAP) == {"T-222", "T-197", "T-223", "T-263", "T-268", "T-269", "T-195", "T-196", "T-260", "T-257", "T-262"}
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(k.startswith("b6b_drb_") and k == k.lower() for k in m.HARNESSES)


def test_every_harness_inconclusive_on_empty_archive():
    for name, h in m.HARNESSES.items():
        stat, n, v, reason = _check(h(FakeArchive({})))
        assert v == "inconclusive" and n == 0 and "missing data bundles" in reason, name
