"""Round-2 regression tests for mandel/experiments/underlying2.py (group u2b), on synthetic data and in-memory archives.

Items (checker follow-ups to round-1 findings):
- U2A-14: low_vol_tilt reports a top-level n equal to the clipped 2011-11..2026-09 count, so run.py's setdefault keeps it.
- U2-1: svxy_v2 takes the Sharpe difference on excess returns over the T-bill (s - rf vs b - rf), matching the excess-index path.
- U2-5: golden_cross_v2 holds the day-t SMA signal from close t+1 (T-485: "SMA through close t, return from close t+1").
"""

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

import mandel.experiments.run as run
import mandel.experiments.underlying2 as u2
from mandel.archive import BundleEntry


# ----------------------------------------------------------------------------- helpers --

class MemArchive:
    """Dict-backed stand-in for Archive (every bundle captured long after its rows)."""

    def __init__(self, bundles: dict):
        self._rows = dict(bundles)

    def entries(self, kind=None, tag=None):
        return [self.get(n) for n in sorted(self._rows)]

    def get(self, name):
        return BundleEntry(name=name, kind="data", path=name, created_at="2099-01-01T00:00:00+00:00", rows=0, bytes=0, sha256="")

    def load(self, name):
        return iter(self._rows[name])


def _daily_rows(sym, closes, start):
    return [{"value": {"t": (start + timedelta(days=i)).timestamp(), "close": float(c), "day": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "symbol": sym}}
            for i, c in enumerate(closes)]


def _days(start, end, weekdays_only=True):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if not weekdays_only or d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _closes(ret):
    """Closes whose return ending on day i is ret[i] (ret[0] ignored)."""
    r = np.asarray(ret, float).copy(); r[0] = 0.0
    return 100 * np.cumprod(1 + r)


# ------------------------------------------------------------------- U2A-14: low_vol_tilt n --

def test_u2a14_low_vol_tilt_reports_the_clipped_n_and_the_runner_records_it():
    # USMV/SPY/SPLV/SPHB from 2011-10-03 (calendar days): 299 overlapping returns, of which only those dated on or after 2011-11-01 are
    # inside T-384's window. The runner's fallback n (the unclipped overlap) must not replace the count the verdict rests on.
    rng, n, start = np.random.default_rng(7), 400, datetime(2011, 10, 3, tzinfo=timezone.utc)
    bundles = {run._dh(s)[0]: _daily_rows(s, 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), start) for s in ("USMV", "SPY", "SPLV", "SPHB")}
    bundles["fred-DTB3"] = _daily_rows("DTB3", 5.0 * np.ones(n), start)
    a = MemArchive(bundles)
    clipped = sum(1 for i in range(1, n) if (start + timedelta(days=i)).strftime("%Y-%m-%d") >= "2011-11-01")
    assert clipped == n - 1 - 28                                        # 28 returns dated 2011-10-04..10-31 are outside the window
    b = run._bill(a)
    rep = u2.low_vol_tilt(u2.load_series(a, "USMV"), u2.load_series(a, "SPY"), bill_days=b[0], bill_vals=b[1])
    assert rep["n"] == rep["n_days"] == clipped and rep["first_day"] == "2011-11-01"
    stat, n_rec, _, _ = run.HARNESSES["low_vol_tilt"](a)
    assert n_rec == stat["n"] == stat["n_days"] == clipped              # was: the unclipped overlap, n - 1 = 399
    _, n_v2, _, _ = run.HARNESSES["low_vol_v2"](a)
    assert n_v2 == clipped                                              # low_vol_v2 inherits the same n


# ---------------------------------------------------------- U2-1: svxy_v2 excess-return basis --

def _svxy_case(seed=11, start="2016-01-04", end="2021-12-31"):
    rng = np.random.default_rng(seed)
    days = _days(start, end); n = len(days)
    vix = {d: 20.0 for d in days}
    vix3m = {d: 20.0 * x for d, x in zip(days, np.where(rng.random(n) < 0.6, 1.2, 0.95))}
    excess = rng.normal(0.0003, 0.03, n)
    return days, vix, vix3m, excess


def test_u2_1_svxy_v2_sharpe_difference_is_on_excess_returns():
    # SVXY's raw return = excess return + a constant bill. Crediting the bill on cash days and subtracting it from both legs must give
    # exactly the statistic of the excess-only series with cash at 0 (the run.py excess-index path): pos*(r - rf) - cost vs r - rf.
    days, vix, vix3m, e = _svxy_case()
    pct = 5.04; rf = pct / 100 / 252
    raw = (days, _closes(np.concatenate([[0.0], e[1:] + rf])))
    rep = u2.svxy_v2(raw, vix, vix3m, test_from="2017-01-01", bill_days=days, bill_vals=[pct] * len(days))
    ex = u2.svxy_v2((days, _closes(e)), vix, vix3m, test_from="2017-01-01")
    assert rep["cash_leg"] == "T-bill" and rep["excess_over_bills"]
    assert rep["sharpe_diff"] == pytest.approx(ex["sharpe_diff"], abs=1e-9)
    assert rep["lower90"] == pytest.approx(ex["lower90"], abs=1e-9)
    assert rep["sharpe"] == pytest.approx(ex["sharpe"], abs=1e-9) and rep["always_sharpe"] == pytest.approx(ex["always_sharpe"], abs=1e-9)
    assert rep["dsr"] == pytest.approx(ex["dsr"], abs=1e-9)             # the DSR is on s - b, where the bill cancels
    # the old total-return basis: the same strategy legs without subtracting the bill
    r = raw[1][1:] / raw[1][:-1] - 1; m = np.array([d >= "2017-01-01" for d in days[1:]])
    sig = np.array([float(vix3m[d] / vix[d] > 1.05) for d in days[:-1]]); pos = np.concatenate([[0.0], sig[:-1]])
    s = (pos * r + (1 - pos) * rf - np.abs(np.diff(np.concatenate([[0.0], pos]))) * 0.001)[m]
    assert s.mean() * 1e4 == pytest.approx(rep["strategy_mean_bps_day"], abs=1e-9)          # the replica is the harness's strategy leg
    old = u2._sr(s, 252) - u2._sr(r[m], 252)
    assert abs(old - rep["sharpe_diff"]) > 0.02                         # the raw basis was a different (biased) number
    assert "excess Sharpe" in rep["reason"]


def test_u2_1_svxy_v2_runner_path_matches_the_excess_index_path():
    rng, n, start = np.random.default_rng(5), 2500, datetime(2016, 1, 4, tzinfo=timezone.utc)
    vix = 15 + 5 * np.abs(np.sin(np.arange(n) / 40))
    a = MemArchive({"daily-history-SVXY": _daily_rows("SVXY", 50 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, n))), start),
                    "cboe-VIX-history": _daily_rows("VIX", vix, start), "cboe-VIX3M-history": _daily_rows("VIX3M", vix * (1 + 0.1 * np.sin(np.arange(n) / 17)), start),
                    "fred-DTB3": _daily_rows("DTB3", 4.0 + np.arange(n) / n, start)})          # time-varying bill, prior-day print
    stat, _, _, _ = run.HARNESSES["svxy_v2"](a)
    vx, v3 = run.index_closes(a.load("cboe-VIX-history")), run.index_closes(a.load("cboe-VIX3M-history"))
    ex = u2.svxy_v2(run._excess_index(run._ls(a, "SVXY"), run._bill(a)), vx, v3)
    assert stat["cash_leg"] == "T-bill" and stat["sharpe_diff"] == pytest.approx(ex["sharpe_diff"], abs=1e-9)
    assert stat["lower90"] == pytest.approx(ex["lower90"], abs=1e-9)


# ------------------------------------------------------- U2-5: golden_cross_v2 next-close fill --

def _same_day_signal_series(start, n, seed, jump=0.25, sd=0.02):
    """Crypto closes (calendar days) built sequentially: the return close t -> t+1 jumps +jump when the 50/200 signal through close t
    has just turned on and -jump when it has just turned off. A fill at close t (same close as the signal) catches every up-jump and
    dodges every down-jump; a position held from close t+1 does the opposite."""
    rng = np.random.default_rng(seed)
    days = [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range(n)]
    c = np.empty(n); c[0] = 100.0; prev = 0.0
    for t in range(n - 1):
        pos = float(c[t - 49:t + 1].mean() > c[t - 199:t + 1].mean()) if t >= 199 else 0.0
        r = rng.normal(0.0005, sd) + jump * (pos - prev)
        c[t + 1] = c[t] * (1 + r); prev = pos
    return days, c


def test_u2_5_golden_cross_v2_holds_the_signal_from_the_next_close():
    btc = _same_day_signal_series("2014-09-17", 4300, 31)
    eth = _same_day_signal_series("2017-11-09", 3200, 32)
    rep = u2.golden_cross_v2(btc, eth)
    for name, (days, c) in (("BTC", btc), ("ETH", eth)):
        pos = u2._ma_pos(c, 50, 200)
        assert int(np.abs(np.diff(pos)).sum()) >= 10                   # the signal really switches
        ds = days[1:]; m = np.array([name == "ETH" or d >= "2015-04-01" for d in ds]); m[:200] = False
        bh = c[1:] / c[:-1] - 1
        same_close = u2._sr(u2._apply(pos, c, 0.0035)[m], 365) - u2._sr(bh[m], 365)
        assert same_close > 0.4                                         # what the old same-close fill reported: a spurious gap
        assert rep[name]["diff"] < 0                                    # held from close t+1: no gap
        assert rep[name]["diff"] == pytest.approx(u2._sr(u2._apply(pos, c, 0.0035, lag=1)[m], 365) - u2._sr(bh[m], 365), abs=1e-12)
    assert rep["verdict"] == "not_supported" and "ETH diff > 0" in rep["reason"]
    assert "return from close t+1" in rep["reason"]


def test_u2_5_lagged_apply_holds_pos_t_minus_1_and_charges_its_switches():
    c = 100 * np.cumprod(1 + np.array([0.0, 0.01, -0.02, 0.03, 0.01, -0.01, 0.02]))
    pos = np.array([0, 1, 1, 0, 1, 1, 0], float)
    r = c[1:] / c[:-1] - 1
    held = np.array([0, 0, 1, 1, 0, 1], float)                          # pos[i-1] over r[i]: signal at close i-1, held from close i
    cost = np.abs(np.diff(np.concatenate([[0.0], held]))) * 0.01
    assert u2._apply(pos, c, 0.01, lag=1) == pytest.approx(held * r - cost, abs=1e-15)
    assert u2._apply(pos, c, 0.01) == pytest.approx(pos[:-1] * r - np.abs(np.diff(np.concatenate([[0.0], pos[:-1]]))) * 0.01, abs=1e-15)   # lag 0 unchanged (T-302)


def test_u2_5_golden_cross_v2_window_starts_at_the_first_held_position():
    rng = np.random.default_rng(18)
    bd = [(date(2014, 9, 17) + timedelta(days=i)).isoformat() for i in range(1932)]
    ed = [(date(2017, 11, 9) + timedelta(days=i)).isoformat() for i in range(1514)]
    btc, eth = (bd, _closes(rng.normal(0.001, 0.03, len(bd)))), (ed, _closes(rng.normal(0.001, 0.03, len(ed))))
    rep = u2.golden_cross_v2(btc, eth)
    assert rep["BTC"]["start"] == "2015-04-06" == bd[201]               # signal through close index 199, held from close 200
    assert rep["ETH"]["start"] == ed[201]
    assert rep["ETH"]["n_days"] == len(ed) - 1 - 200 and rep["n"] == rep["BTC"]["n_days"]
