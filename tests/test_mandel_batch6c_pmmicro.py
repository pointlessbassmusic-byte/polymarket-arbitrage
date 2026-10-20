"""Synthetic tests for mandel.experiments.batch6c_pmmicro: a planted effect that passes and a null that does not, per core
function (hourly reversal, flow imbalance, market-making replay, print coverage, the trial nulls), plus the harness
contract (missing bundles, JSON-safe stat, verdict set) on a fake archive, and the regression tests of the skeptic fixes
(exits on the close hour settle, exits into an invalid book hold to the next valid quote, the H - h signal book must be
valid, the retrace is read from valid books, the T-411 markout uses the next valid mid, the h = 1 cells collapse to 84
distinct rules, the trial null runs 2,000 draws on valid-book mid changes with path-consistent settlement). No network, no
real archive."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_pmmicro as M

HOUR = 3600
T0 = int(datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp())      # a Saturday 00:00 UTC
H0 = T0 // HOUR


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------------------------- synthetic data ---

def _meta(tk: str, cat: str, open_s: int, close_s: int, result: float = 1.0, series: str = "KXCPI") -> dict:
    return {"series": series, "cat": cat, "open_s": open_s, "close_s": close_s, "result": result, "vol": 5000.0}


def _candles(hours: np.ndarray, mid: np.ndarray, half: float = 0.005, vol: float = 10.0) -> tuple:
    bid = np.clip(mid - half, 0.0, 1.0).astype(np.float32)
    ask = np.clip(mid + half, 0.0, 1.0).astype(np.float32)
    return hours.astype(np.int64), bid, ask, np.full(hours.size, vol, dtype=np.float32)


def _reversal_universe(planted: bool, n_markets: int = 40, L: int = 300, seed: int = 0):
    """Planted: mid = 0.5 + e_t with e_t iid uniform(-0.3, 0.3) (a 3-hour move reverts fully). Null: a random walk."""
    rng = np.random.default_rng(seed)
    meta, cand = {}, {}
    for k in range(n_markets):
        tk = f"KXTEST-{k:03d}"
        h0 = H0 + k * 240                                        # markets open ten days apart (the 7-day embargo test half)
        hours = np.arange(h0, h0 + L)
        if planted:
            mid = 0.5 + rng.uniform(-0.3, 0.3, L)
        else:
            mid = np.clip(0.5 + np.cumsum(rng.normal(0, 0.03, L)), 0.05, 0.95)
        cand[tk] = _candles(hours, mid)
        meta[tk] = _meta(tk, "macro", h0 * HOUR - 3600, (h0 + L - 1) * HOUR, result=float(mid[-1] > 0.5))
    return meta, cand


def _stack(meta, cand, oos=None):
    return M.build_stack(meta, cand, sorted(cand), oos if oos is not None else set(cand))


# ------------------------------------------------------------------------------------------------- T-408 engine ---

def test_reversal_planted_mean_reversion_is_positive_after_costs():
    meta, cand = _reversal_universe(True)
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h")
    assert tr["idx"].size > 500
    assert tr["net_c"].mean() > 2.0                        # cents per contract after fee and spread
    cs = M.cluster_stud(tr["net_c"], [st["seg_ticker"][s] for s in st["seg"][tr["idx"]]], 300)
    assert cs["p"] < 0.01


def test_reversal_null_random_walk_loses_the_costs():
    meta, cand = _reversal_universe(False)
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h")
    assert tr["idx"].size > 100
    assert tr["net_c"].mean() < 0.0
    cs = M.cluster_stud(tr["net_c"], [st["seg_ticker"][s] for s in st["seg"][tr["idx"]]], 300)
    assert cs["p"] > 0.5


def test_reversal_fills_at_ask_and_exit_rules():
    """One market, a hand-built path: the signal fires at the hour the mid fell 6 cents over 3 hours; YES is bought at the
    ask of that candle and sold at the bid 3 hours later; the retrace exit leaves at the first hour the move half-reverted."""
    mid = np.array([0.50, 0.50, 0.50, 0.50, 0.44, 0.44, 0.47, 0.48, 0.48, 0.48])
    hours = np.arange(H0, H0 + mid.size)
    meta = {"K": _meta("K", "macro", H0 * HOUR, (H0 + mid.size - 1) * HOUR, result=1.0)}
    cand = {"K": _candles(hours, mid, half=0.005)}
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    # signal hours: index 4 (0.44 - 0.50 = -0.06), index 5 (0.44 - 0.50), index 6 (-0.03: no), 7 (0.48 - 0.44 = +0.04: no)
    assert tr["idx"].tolist() == [4, 5]
    assert tr["buy_yes"].all()
    # entry at ask 0.445, exit at bid of hour 7 (0.475) -> +3.0 cents; hour 8 bid 0.475 -> +3.0
    assert np.allclose(tr["net_c"], [3.0, 3.0])
    trr = M.reversal_trades(st, 3, 0.05, "retrace", fee=0.0)
    # half retrace target 0.47: first hit at hour 6 for the entry at 4 (k = 2), at hour 6 for the entry at 5 (k = 1): exit bid 0.465 -> +2.0
    assert np.allclose(trr["net_c"], [2.0, 2.0])
    # fee: 0.07 x P(1-P) each way
    trf = M.reversal_trades(st, 3, 0.05, "h")
    fee = 0.07 * 0.445 * 0.555 + 0.07 * 0.475 * 0.525
    assert np.allclose(trf["net_c"], [3.0 - 100 * fee] * 2)


def test_reversal_settles_when_the_market_closes_first():
    mid = np.array([0.50, 0.50, 0.50, 0.50, 0.42])
    hours = np.arange(H0, H0 + mid.size)
    # the market closes at 05:30 after the last candle: the grid runs to the close hour H0 + 6 (forward-filled), exits after it settle
    meta = {"K": _meta("K", "macro", H0 * HOUR, (H0 + 5) * HOUR + 1800, result=1.0)}
    st = _stack(meta, {"K": _candles(hours, mid)})
    assert st["n"] == 7 and not st["fresh"][5:].any()
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    assert tr["idx"].tolist() == [4, 5]                              # the forward-filled hour 5 signals too (fresh = False); hour 6 is the close hour (no entry)
    assert np.allclose(tr["net_c"], [100 * (1.0 - 0.425)] * 2)      # YES settles at 1, bought at the ask 0.425, no exit fee
    assert tr["fresh"].tolist() == [True, False]
    # a NO buy settles at 1 - result
    meta["K"]["result"] = 0.0
    st = _stack(meta, {"K": _candles(hours, 1.0 - mid)})
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    assert (~tr["buy_yes"]).all() and np.allclose(tr["net_c"], [100 * (1.0 - 0.425)] * 2)


def test_stationary_resample_stays_within_segments_and_blocks_are_contiguous():
    meta, cand = _reversal_universe(False, n_markets=5, L=50)
    st = _stack(meta, cand)
    idx = M.stationary_resample_idx(st, 6.0, np.random.default_rng(1))
    assert idx.shape == (st["n"],)
    assert np.all(st["seg"][idx] == st["seg"])
    # a position whose predecessor is in the same run points one past its predecessor (circularly within the segment)
    lo = st["seg_start"][st["seg"]]
    L = st["seglen"]
    nxt = lo + (idx - lo + 1) % L
    same = (idx[1:] == nxt[:-1]) | (st["pos"][1:] == 0)
    assert same.mean() > 0.6                                         # mean block 6: most steps continue the block


def test_reversal_null_planted_small_p_and_random_walk_large_p():
    meta, cand = _reversal_universe(True, n_markets=20, L=200, seed=3)
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h")
    r = M.reversal_null(st, M.T408_HEADLINE, float(tr["net_c"].mean()), 40, seed=1)
    assert r["n_draws"] == 40 and r["p"] < 0.05 and r["boot_mean"] > 0
    meta, cand = _reversal_universe(False, n_markets=20, L=200, seed=4)
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h")
    r = M.reversal_null(st, M.T408_HEADLINE, float(tr["net_c"].mean()), 40, seed=1)
    assert r["p"] > 0.5 and r["boot_mean"] < 0


def test_walk_forward_split_embargo():
    meta = {f"M{i}": _meta(f"M{i}", "macro", T0 + i * 86_400, T0 + (i + 30) * 86_400) for i in range(20)}
    sp = M.walk_forward_split(meta, list(meta), 7 * 86_400)
    assert len(sp["calib"]) == 10 and sp["split_s"] == T0 + 10 * 86_400
    assert sp["embargoed"] == {f"M{i}" for i in range(10, 17)}
    assert sp["test"] == {f"M{i}" for i in range(17, 20)}


def test_pm_reversal_replication_planted_and_null():
    rng = np.random.default_rng(0)
    planted, null = {}, {}
    for k in range(30):
        hours = np.arange(H0 + k, H0 + k + 300)
        planted[str(k)] = (hours.astype(np.int64), (0.5 + rng.uniform(-0.3, 0.3, 300)).astype(np.float32))
        null[str(k)] = (hours.astype(np.int64), np.clip(0.5 + np.cumsum(rng.normal(0, 0.03, 300)), 0.05, 0.95).astype(np.float32))
    meta = {str(k): {"fee_rate": 0.0, "outcome": 1} for k in range(30)}
    r = M.pm_reversal_trades(planted, meta, 0.01)
    assert r["n"] > 300 and r["mean_c"] > 2.0
    r0 = M.pm_reversal_trades(null, meta, 0.01)
    assert r0["mean_c"] < 0.0


# ------------------------------------------------------------------------------------------------- T-463 engine ---

def _prints(tk_hours: np.ndarray, F_sign: np.ndarray, n: int = 25, qty: float = 10.0, px: float = 0.5):
    """n prints per hour; F_sign +1 -> 80% YES takers, -1 -> 80% NO takers, 0 -> balanced."""
    t, p, s, q = [], [], [], []
    for h, sg in zip(tk_hours, F_sign):
        k_yes = {1: 20, -1: 5, 0: 12}[int(sg)]
        for i in range(n):
            t.append(h * HOUR + 60 + i * 120)
            p.append(px)
            s.append(1 if i < k_yes else -1)
            q.append(qty)
    return (np.array(t, dtype=np.int64), np.array(p, dtype=np.float32), np.array(s, dtype=np.int8), np.array(q, dtype=np.float32))


def _flow_universe(planted: bool, n_markets: int = 40, L: int = 240, seed: int = 0):
    rng = np.random.default_rng(seed)
    meta, cand, trades = {}, {}, {}
    for k in range(n_markets):
        tk = f"KXFLOW-{k:03d}"
        h0 = H0 + 5 * k
        hours = np.arange(h0, h0 + L)
        sig = np.zeros(L, dtype=int)
        sig[rng.choice(np.arange(10, L - 10), 20, replace=False)] = rng.choice([-1, 1], 20)
        mid = np.full(L, 0.5)
        if planted:
            jump = np.zeros(L)
            for i in np.flatnonzero(sig):
                jump[i + 1:i + 7] += 0.08 * sig[i]                   # the taken side keeps moving for six hours
            mid = np.clip(0.5 + jump + rng.normal(0, 0.003, L), 0.05, 0.95)
        else:
            mid = np.clip(0.5 + np.cumsum(rng.normal(0, 0.01, L)), 0.05, 0.95)
        cand[tk] = _candles(hours, mid, half=0.01)
        # prints of hour [H-1, H) are keyed by their start hour H-1: the flow is known at H = the signal hour
        trades[tk] = _prints(hours - 1, sig)
        meta[tk] = _meta(tk, "sports", h0 * HOUR - 3600, (h0 + L - 1) * HOUR, result=float(mid[-1] > 0.5), series="KXNBAGAME")
    return meta, cand, trades


def test_hourly_flow_counts_and_coverage_bound():
    t = np.array([T0 + 10, T0 + 20, T0 + HOUR + 5, T0 + HOUR + 6, T0 + HOUR + 7], dtype=np.int64)
    tr = (t, np.full(5, 0.5, np.float32), np.array([1, -1, 1, 1, -1], np.int8), np.array([10, 30, 5, 5, 10], np.float32))
    he, n, F, q = M.hourly_flow(tr)
    assert he.tolist() == [H0 + 1, H0 + 2] and n.tolist() == [2, 3]
    assert np.allclose(F, [(10 - 30) / 40, (10 - 10) / 20])
    he2, n2, _, _ = M.hourly_flow(tr, from_s=T0 + HOUR)
    assert he2.tolist() == [H0 + 2] and n2.tolist() == [3]


def test_flow_planted_continuation_positive_and_permutation_p_small():
    meta, cand, trades = _flow_universe(True)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    c = M.flow_candidates(st, flows)
    assert c["idx"].size > 500
    ry, rn = M.side_returns(st, c["idx"], 6)
    tr = M.flow_trades(c, ry, rn, 0.5, True)
    assert tr["sel"].size > 300 and tr["net_c"].mean() > 2.0
    p = M.flow_permutation_null(c, st, ry, rn, 0.5, True, float(tr["net_c"].mean()), 60)
    assert p["n_perm"] == 60 and p["p"] < 0.05
    fade = M.flow_trades(c, ry, rn, 0.5, False)
    assert fade["net_c"].mean() < 0.0


def test_flow_null_no_relation_loses_the_costs_and_permutation_p_large():
    meta, cand, trades = _flow_universe(False)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    c = M.flow_candidates(st, flows)
    ry, rn = M.side_returns(st, c["idx"], 6)
    tr = M.flow_trades(c, ry, rn, 0.5, True)
    assert tr["sel"].size > 300 and tr["net_c"].mean() < 0.0
    p = M.flow_permutation_null(c, st, ry, rn, 0.5, True, float(tr["net_c"].mean()), 60)
    assert p["p"] > 0.2


def test_flow_candidates_filters_and_delay():
    meta, cand, trades = _flow_universe(True, n_markets=3, L=60)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    c = M.flow_candidates(st, flows)
    assert np.all(c["n_trades"] >= 20)
    assert np.all((st["mid"][c["idx"]] >= 0.05) & (st["mid"][c["idx"]] <= 0.95))
    c1 = M.flow_candidates(st, flows, delay=1)
    assert np.all(np.isin(c1["idx"] - 1, c["idx"]))


def test_pm_flow_trades_planted_and_null():
    rng = np.random.default_rng(2)
    flows, series_p, series_n = {}, {}, {}
    for k in range(20):
        hours = np.arange(H0 + k, H0 + k + 200)
        F = np.zeros(200, np.float32)
        sig = rng.choice(np.arange(5, 190), 15, replace=False)
        F[sig] = rng.choice([-0.8, 0.8], 15)
        flows[str(k)] = (hours + 1, np.full(200, 30, np.int32), F)   # flow of hour [H, H+1) known at H + 1
        jump = np.zeros(200)
        for i in sig:
            jump[i + 2:i + 9] += 0.1 * np.sign(F[i])
        series_p[str(k)] = (hours, np.clip(0.5 + jump, 0.05, 0.95).astype(np.float32))
        series_n[str(k)] = (hours, np.clip(0.5 + np.cumsum(rng.normal(0, 0.01, 200)), 0.05, 0.95).astype(np.float32))
    meta = {str(k): {"fee_rate": 0.0, "outcome": 1} for k in range(20)}
    r = M.pm_flow_trades(flows, series_p, meta, 0.01, 0.5, 6, True)
    assert r["n"] >= 200 and r["mean_c"] > 2.0
    r0 = M.pm_flow_trades(flows, series_n, meta, 0.01, 0.5, 6, True)
    assert r0["n"] >= 200 and r0["mean_c"] < 0.0


# ------------------------------------------------------------------------------------------------- T-411 engine ---

def _mm_universe(adverse: bool, n_markets: int = 12, L: int = 240, seed: int = 0):
    """Markets quoted bid 0.49 / ask 0.51 (planted: the mid never moves, prints through both quotes every hour) or with a
    mid falling 2 cents an hour and takers selling through the bid every hour (adverse)."""
    meta, cand, trades = {}, {}, {}
    for k in range(n_markets):
        tk = f"KXMM-{k:03d}"
        h0 = H0 + 3 * k
        hours = np.arange(h0, h0 + L)
        if adverse:
            mid = np.clip(0.9 - 0.02 * np.arange(L), 0.1, 0.9)
        else:
            mid = np.full(L, 0.5)
        cand[tk] = _candles(hours, mid, half=0.01)
        t, p, s, q = [], [], [], []
        for i, h in enumerate(hours):
            bid, ask = mid[i] - 0.01, mid[i] + 0.01
            t.append(h * HOUR + 600)
            p.append(round(bid - 0.01, 4))
            s.append(-1)                                           # taker sold YES below our bid
            q.append(10.0)
            if not adverse:
                t.append(h * HOUR + 1200)
                p.append(round(ask + 0.01, 4))
                s.append(1)                                        # taker bought YES above our ask
                q.append(10.0)
        trades[tk] = (np.array(t, np.int64), np.array(p, np.float32), np.array(s, np.int8), np.array(q, np.float32))
        meta[tk] = _meta(tk, "macro", h0 * HOUR - 3600, (h0 + L - 1) * HOUR, result=float(mid[-1] > 0.5))
    return meta, cand, trades


def test_mm_replay_planted_spread_capture_positive_every_cell():
    meta, cand, trades = _mm_universe(False)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    tb = M.mm_tables(st, trades, flows, np.zeros(0, np.int64))
    assert tb["n_market_days"] > 50
    rep = M.mm_replay(st, tb, M.t411_cells())
    assert np.all(rep["fills_n"] > 0)
    assert np.all(rep["daily_net"].mean(axis=0) > 0)
    # each filled contract: 1 cent capture minus the maker fee 0.0175 x 0.49 x 0.51, on both sides -> realised spread 2 cents gross
    rsp = rep["realised_spread_sum"] / rep["filled"]
    assert np.allclose(rsp, 0.02, atol=1e-6)
    # pull rule (d): no quoting inside the last 48 hours
    assert not np.any(tb["active"] & (st["htc"] < 48))


def test_mm_replay_adverse_selection_negative():
    meta, cand, trades = _mm_universe(True)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    tb = M.mm_tables(st, trades, flows, np.zeros(0, np.int64))
    rep = M.mm_replay(st, tb, M.t411_cells())
    assert np.all(rep["fills_n"] > 0)
    assert np.all(rep["daily_net"].mean(axis=0) < 0)
    # the inventory cap binds: a 50-contract cap fills at most 50 contracts per market before the markout pull or room stops it
    cap50 = [i for i, c in enumerate(M.t411_cells()) if c[2] == 50.0]
    assert np.all(rep["filled"][cap50] <= rep["filled"][[i for i, c in enumerate(M.t411_cells()) if c[2] == 500.0]])


def test_mm_tables_event_pull_and_flow_pull():
    meta, cand, trades = _mm_universe(False, n_markets=2, L=120)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk]) for tk in st["seg_ticker"]}
    ev = np.array([(H0 + 30) * HOUR + 1800], dtype=np.int64)       # an event at 30:30 after H0
    tb = M.mm_tables(st, trades, flows, ev)
    seg0 = st["seg"] == 0
    hours0 = st["hour"][seg0]
    act0 = tb["active"][seg0]
    assert not act0[np.isin(hours0, [H0 + 29, H0 + 30, H0 + 31])].any()   # the periods within an hour of the event are pulled
    assert act0[hours0 == H0 + 33].all()
    # balanced prints -> F = 0 -> no flow pull
    assert np.all(np.abs(tb["F_prev"]) < 1e-6)


def test_trade_coverage_from_fetch_log():
    rows = [{"value": {"product": "trades", "id": "A", "complete": True, "complete_from": None}},
            {"value": {"product": "trades", "id": "B", "complete": False, "complete_from": "2026-08-18T21:53:39+00:00", "routes": ["/markets/trades"], "routes_skipped": ["/historical/trades"]}},
            {"value": {"product": "trades", "id": "C", "complete": False, "complete_from": "2026-07-26T02:50:06+00:00"}},
            {"value": {"product": "trades", "id": "D", "complete": False, "complete_from": None}},
            {"value": {"product": "candles-60", "id": "A"}}]
    cov = M.trade_coverage(rows)
    assert cov["A"] == {"complete": True, "from_s": 0, "cutoff_gap": False}
    assert cov["B"]["from_s"] == M._ts("2026-08-18T21:53:39+00:00") and cov["B"]["cutoff_gap"] is True and not cov["B"]["complete"]
    assert cov["C"]["cutoff_gap"] is False and cov["C"]["from_s"] > 0
    assert cov["D"]["from_s"] is None


def test_build_stack_usable_hours_follow_the_coverage_bound():
    meta, cand = _reversal_universe(False, n_markets=2, L=50)
    tks = sorted(cand)
    from_s = {tks[0]: (H0 + 20) * HOUR, tks[1]: 0}
    st = M.build_stack(meta, cand, tks, set(), from_s)
    seg0 = st["seg"] == 0
    assert st["usable"][seg0].sum() == 30 and st["usable"][~seg0].all()


# ------------------------------------------------------------------------- regression tests (skeptic fixes, batch 6c) ---

def _book_path(mid: np.ndarray, close_s: int, result: float = 1.0, half: float = 0.005, invalid: tuple = (), wide: dict = None):
    """One market 'K' on hours H0.., spread 2 x half, the positions in ``invalid`` quoted bid 0 / ask 1 (the empty book) and
    those in ``wide`` {pos: half_spread} quoted wider. Returns (meta, cand)."""
    hours = np.arange(H0, H0 + mid.size)
    bid = np.clip(mid - half, 0.0, 1.0)
    ask = np.clip(mid + half, 0.0, 1.0)
    for p in invalid:
        bid[p], ask[p] = 0.0, 1.0
    for p, hs in (wide or {}).items():
        bid[p], ask[p] = mid[p] - hs, mid[p] + hs
    cand = {"K": (hours.astype(np.int64), bid.astype(np.float32), ask.astype(np.float32), np.full(mid.size, 10.0, np.float32))}
    return {"K": _meta("K", "macro", H0 * HOUR, close_s, result=result)}, cand


def test_fix_reversal_exit_landing_on_the_close_hour_settles_at_the_result():
    """Defect: the grid's last hour contains the market close and its candle closes on the post-close empty book (bid 0 / ask 1);
    an exit marked there sold YES at 0. Fix: an exit on or after the close hour settles at the result with no exit fee."""
    mid = np.array([0.50, 0.50, 0.50, 0.50, 0.44, 0.44, 0.44, 0.44, 0.50])
    # the market closes at 07:30 -> close hour H0 + 8 = position 8, whose candle is the empty post-close book
    meta, cand = _book_path(mid, (H0 + 7) * HOUR + 1800, result=1.0, invalid=(8,))
    st = _stack(meta, cand)
    assert st["n"] == 9 and st["htc"][8] == 0
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    assert tr["idx"].tolist() == [4, 5, 6]
    # entry 4 exits at hour 7 (bid 0.435): -1.0 cents; entry 5 lands on the close hour, entry 6 after it: both settle at 1.0
    assert np.allclose(tr["net_c"], [-1.0, 55.5, 55.5])
    assert tr["kind"].tolist() == [M.EXIT_AT_K, M.EXIT_SETTLED_CLOSE, M.EXIT_SETTLED_CLOSE]
    assert tr["exit_pos"].tolist() == [7, -1, -1]
    # with the fee, the settled exits pay the entry fee only
    trf = M.reversal_trades(st, 3, 0.05, "h")
    assert np.allclose(trf["net_c"][1:], [55.5 - 100 * 0.07 * 0.445 * 0.555] * 2)
    # the NO side: a close-hour exit settles at 1 - result
    meta0, cand0 = _book_path(1.0 - mid, (H0 + 7) * HOUR + 1800, result=0.0, invalid=(8,))
    tr0 = M.reversal_trades(_stack(meta0, cand0), 3, 0.05, "h", fee=0.0)
    assert (~tr0["buy_yes"]).all() and np.allclose(tr0["net_c"], [-1.0, 55.5, 55.5])


def test_fix_reversal_midlife_exit_into_an_invalid_book_holds_to_the_next_valid_quote_or_settles():
    """Defect: a mid-life exit was marked at whatever book sat k hours out, including bid 0 / ask 1 (a -100% exit). Fix: hold to
    the next valid quote within EXIT_WAIT_H hours, else settle; the kinds are counted."""
    L = 80
    mid = np.r_[0.50, 0.50, 0.50, 0.50, 0.44, np.full(L - 5, 0.47)]              # one signal at position 4 (k = 3 -> position 7)
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=1.0, invalid=(7,))
    tr = M.reversal_trades(_stack(meta, cand), 3, 0.05, "h", fee=0.0)
    assert tr["idx"].tolist() == [4] and tr["kind"].tolist() == [M.EXIT_HELD] and tr["exit_pos"].tolist() == [8]
    assert np.allclose(tr["net_c"], [100 * (0.465 - 0.445)])                     # the bid of hour 8, not 0
    # exactly EXIT_WAIT_H hours of invalid books: the quote at 7 + 48 is taken
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=1.0, invalid=tuple(range(7, 7 + M.EXIT_WAIT_H)))
    tr = M.reversal_trades(_stack(meta, cand), 3, 0.05, "h", fee=0.0)
    assert tr["kind"].tolist() == [M.EXIT_HELD] and tr["exit_pos"].tolist() == [7 + M.EXIT_WAIT_H]
    # one hour more and the trade settles at the result (no exit fee)
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=1.0, invalid=tuple(range(7, 8 + M.EXIT_WAIT_H)))
    tr = M.reversal_trades(_stack(meta, cand), 3, 0.05, "h")
    assert tr["kind"].tolist() == [M.EXIT_SETTLED_NO_QUOTE] and tr["exit_pos"].tolist() == [-1]
    assert np.allclose(tr["net_c"], [100 * (1.0 - 0.445 - 0.07 * 0.445 * 0.555)])
    # a wide (> 10 cents) book is invalid too
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=1.0, wide={7: 0.08})
    tr = M.reversal_trades(_stack(meta, cand), 3, 0.05, "h", fee=0.0)
    assert tr["kind"].tolist() == [M.EXIT_HELD] and tr["exit_pos"].tolist() == [8]
    assert M.exit_kind_counts(tr["kind"]) == {"quote_at_k": 0, "held_to_next_valid_quote": 1, "settled_close_hour_or_later": 0, "settled_no_valid_quote_within_wait": 0}


def test_fix_exit_marks_never_cross_into_another_market():
    """The next valid quote must belong to the same market: a market whose remaining books are all invalid settles even when
    the following segment quotes a valid book right after."""
    L = 12
    mid = np.r_[0.50, 0.50, 0.50, 0.50, 0.44, np.full(L - 5, 0.47)]
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=0.0, invalid=tuple(range(7, L)))
    hours2 = np.arange(H0 + L, H0 + 2 * L)
    cand["Z"] = _candles(hours2, np.full(L, 0.5))
    meta["Z"] = _meta("Z", "macro", (H0 + L) * HOUR, (H0 + 2 * L - 1) * HOUR, result=1.0)
    st = M.build_stack(meta, cand, ["K", "Z"], set())
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    assert tr["idx"].tolist() == [4] and tr["kind"].tolist() == [M.EXIT_SETTLED_NO_QUOTE]
    assert np.allclose(tr["net_c"], [-44.5])                                    # YES bought at 0.445 settles at 0


def test_fix_reversal_signal_requires_a_valid_book_at_h_minus_h():
    """Defect: the mid at H - h came from any book, so an empty (mid 0.495) or wide book at H - 3 produced a 'move' that was a
    book appearing. Fix: the book at H - h must be a valid touch with spread <= theta / 2 like the book at H; the dropped
    signals are returned (and the any-valid-touch reading is a sensitivity)."""
    mid = np.r_[0.50, 0.50, 0.50, 0.50, np.full(9, 0.44)]
    # position 1: empty book; position 2: 6-cent spread (a valid touch, wider than theta / 2 = 2.5 cents); position 3: tight
    meta, cand = _book_path(mid, (H0 + mid.size - 1) * HOUR, result=1.0, invalid=(1,), wide={2: 0.03})
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h", fee=0.0)
    assert tr["idx"].tolist() == [6]                                            # 4 (vs the empty book) and 5 (vs the 6-cent book) are dropped
    assert tr["dropped_prev_book_idx"].tolist() == [4, 5]
    tr10 = M.reversal_trades(st, 3, 0.05, "h", fee=0.0, prev_spread=M.SPREAD_MAX)
    assert tr10["idx"].tolist() == [5, 6] and tr10["dropped_prev_book_idx"].tolist() == [4]
    # a book at H - h that is valid and tight keeps every signal (the earlier hand-built path is unchanged)
    meta2, cand2 = _book_path(np.array([0.50, 0.50, 0.50, 0.50, 0.44, 0.44, 0.47, 0.48, 0.48, 0.48]), (H0 + 9) * HOUR)
    tr2 = M.reversal_trades(_stack(meta2, cand2), 3, 0.05, "h", fee=0.0)
    assert tr2["idx"].tolist() == [4, 5] and tr2["dropped_prev_book_idx"].size == 0


def test_fix_retrace_exit_is_not_read_from_an_invalid_book():
    """The 50% retrace is read from the mid of a valid book only: an empty book's 0.495 is not a retrace."""
    mid = np.array([0.50, 0.50, 0.50, 0.50, 0.44, 0.44, 0.44, 0.44, 0.44, 0.44, 0.44, 0.44])
    meta, cand = _book_path(mid, (H0 + mid.size - 1) * HOUR, result=1.0, invalid=(5,))
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "retrace", fee=0.0)
    assert tr["idx"].tolist() == [4, 6]                                         # position 5 (the empty book) cannot signal
    # entry 4: the empty book at 5 is not a hit, 6 and 7 are below the target -> exit at k = 3 (hour 7, bid 0.435): -1.0 cents, not -44.5 at bid 0
    assert tr["exit_pos"].tolist() == [7, 9] and tr["kind"].tolist() == [M.EXIT_AT_K, M.EXIT_AT_K]
    assert np.allclose(tr["net_c"], [-1.0, -1.0])


def test_fix_side_returns_close_hour_settles_and_invalid_book_holds():
    """T-463 shares the exit defect: side_returns exited at the candle 6 hours out whatever its book. Same fix through exit_marks."""
    L = 30
    mid = np.full(L, 0.50)
    mid[10:] = 0.56
    meta, cand = _book_path(mid, (H0 + L - 1) * HOUR, result=1.0, invalid=(16,))
    st = _stack(meta, cand)
    idx = np.array([4, 10, L - 7, L - 5])                                        # 4 -> 10 valid; 10 -> 16 invalid (17 valid); L-7 -> close hour; L-5 -> beyond
    ry, rn = M.side_returns(st, idx, 6, fee=0.0)
    assert np.allclose(ry, [100 * (0.555 - 0.505), 100 * (0.555 - 0.565), 100 * (1.0 - 0.565), 100 * (1.0 - 0.565)])
    assert np.allclose(rn, [100 * ((1 - 0.565) - (1 - 0.495)), 100 * ((1 - 0.565) - (1 - 0.555)), 100 * (0.0 - (1 - 0.555)), 100 * (0.0 - (1 - 0.555))])
    ep, kind = M.exit_marks(st, idx, 6)
    assert ep.tolist() == [10, 17, -1, -1]
    assert kind.tolist() == [M.EXIT_AT_K, M.EXIT_HELD, M.EXIT_SETTLED_CLOSE, M.EXIT_SETTLED_CLOSE]
    # with the fee: no exit fee on the settled trades
    ryf, _ = M.side_returns(st, idx, 6)
    assert np.allclose(ryf[2:], [100 * (1.0 - 0.565 - 0.07 * 0.565 * 0.435)] * 2)
    assert np.isclose(ryf[0], 100 * (0.555 - 0.505 - 0.07 * 0.505 * 0.495 - 0.07 * 0.555 * 0.445))


def test_fix_mm_markout_uses_the_next_valid_mid_and_counts_remarked_fills():
    """Defect: the 60-minute markout was the grid mid at P + 2 whatever the book (0.495 for bid 0 / ask 1). Fix: the first valid
    mid at or after P + 2 within EXIT_WAIT_H hours, else settlement; the re-marked fills are counted."""
    meta, cand, trades = _mm_universe(False, n_markets=1, L=240)
    tk = "KXMM-000"
    hours, bid, ask, vol = cand[tk]
    bid, ask = bid.copy(), ask.copy()
    bid[50], ask[50] = 0.0, 1.0                                                  # P = 48: the P + 2 book is empty
    bid[51], ask[51] = 0.59, 0.61                                                # the next valid mid is 0.60 (P = 49's own P + 2 book: valid, not re-marked)
    bid[60], ask[60] = 0.40, 0.70                                                # 30-cent book: P = 58 is re-marked at the mid of 61 (0.50)
    cand[tk] = (hours, bid, ask, vol)
    st = _stack(meta, cand)
    flows = {tk: M.hourly_flow(trades[tk])}
    tb = M.mm_tables(st, trades, flows, np.zeros(0, np.int64))
    assert np.isclose(tb["mark"][48], 0.60) and np.isclose(tb["mark"][49], 0.60) and np.isclose(tb["mark"][47], 0.50)
    assert np.isclose(tb["mark"][58], 0.50) and tb["remarked"][58] and tb["remarked"][48] and not tb["remarked"][47] and not tb["remarked"][49]
    # the close hour and beyond settle at the result; the close-hour position itself (P + 2 = close hour) counts as re-marked
    L = 240
    assert np.allclose(tb["mark"][L - 3:], meta[tk]["result"]) and tb["remarked"][L - 3] and not tb["remarked"][L - 2]
    rep = M.mm_replay(st, tb, [(0.1, 0.01, 50.0)])
    # the planted universe fills 10 contracts through each quote every hour: periods 48 and 58 are the re-marked fills (20 contracts each)
    assert rep["remarked_fills_n"].tolist() == [2] and np.isclose(rep["remarked_contracts"][0], 40.0)
    assert rep["fills_n"][0] > 100
    # the old mark (0.495 from the empty book) would have marked the 48 fills differently from the 0.60 mid that follows
    assert not np.isclose(tb["mark"][48], 0.495)
    # a long invalid stretch past EXIT_WAIT_H hours falls back to settlement
    bid2, ask2 = bid.copy(), ask.copy()
    bid2[100:100 + M.EXIT_WAIT_H + 1], ask2[100:100 + M.EXIT_WAIT_H + 1] = 0.0, 1.0
    cand[tk] = (hours, bid2, ask2, vol)
    tb2 = M.mm_tables(_stack(meta, cand), trades, flows, np.zeros(0, np.int64))
    assert np.isclose(tb2["mark"][98], meta[tk]["result"]) and np.isclose(tb2["mark"][99], 0.50)


def test_fix_t408_h1_cells_collapse_to_84_distinct_rules():
    """Defect: at hourly granularity the h = 1 cells' three exit rules coincide, so 24 of the 108 declared cells duplicate others
    and DSR / PBO counted duplicated columns. Fix: 84 distinct rules, DSR over 84 + 21 = 105 trials (129 the declared bound)."""
    cells, distinct = M.t408_cells(), M.t408_distinct_cells()
    assert len(cells) == 108 and len(distinct) == 84 and len(set(distinct)) == 84
    assert M.t408_cell_key((1, 0.03, "half", True, False)) == (1, 0.03, "h", True, False)
    assert M.t408_cell_key((1, 0.03, "retrace", False, True)) == (1, 0.03, "h", False, True)
    assert M.t408_cell_key((3, 0.03, "half", False, False)) == (3, 0.03, "half", False, False)
    assert sum(1 for c in cells if M.t408_cell_key(c) != c) == 24
    meta, cand = _reversal_universe(False, n_markets=6, L=80, seed=9)
    st = _stack(meta, cand)
    a, b, c = (M.reversal_trades(st, 1, 0.03, ex) for ex in ("h", "half", "retrace"))
    assert a["idx"].size > 20 and np.array_equal(a["idx"], b["idx"]) and np.array_equal(a["idx"], c["idx"])
    assert np.allclose(a["net_c"], b["net_c"]) and np.allclose(a["net_c"], c["net_c"])
    h3 = [M.reversal_trades(st, 3, 0.03, ex)["net_c"].mean() for ex in ("h", "half", "retrace")]
    assert len({round(x, 6) for x in h3}) == 3                                  # at h = 3 the exit rules differ


def test_fix_trial_null_runs_the_named_2000_draws():
    assert M.N_NULL_T408 == 2000
    meta, cand = _reversal_universe(False, n_markets=4, L=60, seed=2)
    st = _stack(meta, cand)
    r = M.reversal_null(st, M.T408_HEADLINE, 0.0, 12, seed=1)
    assert r["n_draws"] == 12 and "mean_settled_trades_per_draw" in r


def test_fix_valid_mid_path_carries_the_last_quoted_mid_over_invalid_books():
    """The null resamples mid CHANGES: a jump into an empty book (mid 0.495) and back is not a change. valid_mid_path carries the
    last valid mid over invalid hours within the market, takes the first valid mid before it, and never crosses markets."""
    mid = np.array([0.30, 0.30, 0.32, 0.32, 0.32, 0.36, 0.36, 0.36])
    meta, cand = _book_path(mid, (H0 + 7) * HOUR, invalid=(0, 3, 4), wide={6: 0.2})
    hours2 = np.arange(H0 + 8, H0 + 12)
    cand["Z"] = _candles(hours2, np.array([0.80, 0.80, 0.80, 0.80]))
    cand["Z"] = (cand["Z"][0], np.array([0.0, 0.79, 0.79, 0.79], np.float32), np.array([1.0, 0.81, 0.81, 0.81], np.float32), cand["Z"][3])
    meta["Z"] = _meta("Z", "macro", (H0 + 8) * HOUR, (H0 + 11) * HOUR)
    st = M.build_stack(meta, cand, ["K", "Z"], set())
    mv = M.valid_mid_path(st)
    # K: hour 0 (empty) takes the first valid mid 0.30; hours 3, 4 (empty) and 6 (40-cent book) carry the last valid mid
    assert np.allclose(mv[:8], [0.30, 0.30, 0.32, 0.32, 0.32, 0.36, 0.36, 0.36])
    # Z: its empty first hour takes Z's own first valid mid, not K's last
    assert np.allclose(mv[8:], [0.80, 0.80, 0.80, 0.80])
    d = mv - M._shift_back(mv, st["pos"], 1)
    assert np.allclose(np.nan_to_num(d)[[3, 4, 6, 8]], 0.0) and np.isclose(d[5], 0.04) and np.isclose(d[2], 0.02)
    # a market without any valid book has no mid path
    meta3, cand3 = _book_path(np.full(5, 0.5), (H0 + 4) * HOUR, invalid=tuple(range(5)))
    assert np.all(np.isnan(M.valid_mid_path(_stack(meta3, cand3))))


def test_fix_trial_null_is_not_biased_by_empty_book_hours():
    """Regression: on a random walk whose hours are 40% empty books the old null resampled the +/- 0.3 jumps into and out of
    the empty book as mid changes and marked settled trades at the real result; the refined null's bootstrap mean must sit
    near the observed cost-driven loss and its p must not flag an edge."""
    rng = np.random.default_rng(11)
    meta, cand = {}, {}
    for k in range(24):
        tk = f"KXTEST-{k:03d}"
        h0 = H0 + k * 50
        L = 160
        hours = np.arange(h0, h0 + L)
        mid = np.clip(0.3 + np.cumsum(rng.normal(0, 0.03, L)), 0.05, 0.95)
        bid, ask = (mid - 0.005).astype(np.float32), (mid + 0.005).astype(np.float32)
        empty = rng.random(L) < 0.4
        bid[empty], ask[empty] = 0.0, 1.0
        cand[tk] = (hours.astype(np.int64), bid, ask, np.full(L, 10.0, np.float32))
        meta[tk] = _meta(tk, "sports", h0 * HOUR - 3600, (h0 + L - 1) * HOUR, result=float(mid[-1] > rng.random()))
    st = _stack(meta, cand)
    tr = M.reversal_trades(st, 3, 0.05, "h")
    obs = float(tr["net_c"].mean())
    assert tr["idx"].size > 200 and obs < 0.0 and (tr["kind"] == M.EXIT_HELD).sum() > 20
    r = M.reversal_null(st, M.T408_HEADLINE, obs, 40, seed=3)
    assert r["n_draws"] == 40 and r["p"] > 0.2
    assert abs(r["boot_mean"] - obs) < 2.0                                      # cents: no fake-jump or settlement bias
    assert r["mean_settled_trades_per_draw"] > 0


def test_ts_fast_path_matches_fromisoformat():
    for s in ("2021-08-11T16:08:05.654945Z", "2026-08-18T21:53:39+00:00", "2025-04-01 06:50:20+00", "2024-02-29T23:59:59Z"):
        ref = int(datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T", 1).replace("+00", "+00:00") if s.endswith("+00") else s.replace("Z", "+00:00")).timestamp())
        assert M._ts(s) == ref


# ------------------------------------------------------------------------------------------------ fake archive ---

class FakeArchive:
    def __init__(self, bundles: dict):
        self._b = bundles

    def get(self, name):
        if name not in self._b:
            raise KeyError(name)
        return SimpleNamespace(name=name, rows=len(self._b[name]), created_at="2026-10-16T00:00:00+00:00")

    def entries(self, kind=None, tag=None):
        return [SimpleNamespace(name=n) for n in self._b]

    def load(self, name):
        return iter(self._b[name])


def _market_row(tk, series, m):
    return {"source": "kalshi", "kind": "market", "key": tk, "observed_at": _iso(m["close_s"]), "available_at": _iso(m["close_s"] + 60),
            "value": {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "open_time": _iso(m["open_s"]), "close_time": _iso(m["close_s"]),
                      "settlement_ts": _iso(m["close_s"] + 600), "result": "yes" if m["result"] == 1.0 else "no", "volume_fp": "5000.00", "status": "finalized"}}


def _candle_rows(tk, c):
    hours, bid, ask, vol = c
    out = []
    for h, b, a, v in zip(hours, bid, ask, vol):
        out.append({"source": "kalshi", "kind": "candle", "key": tk, "observed_at": _iso(h * HOUR), "available_at": _iso(h * HOUR),
                    "value": {"ticker": tk, "period": 60, "candle": {"end_period_ts": int(h) * HOUR, "yes_bid": {"close": f"{float(b):.4f}"},
                                                                     "yes_ask": {"close": f"{float(a):.4f}"}, "price": {"close": None}, "volume": f"{float(v):.2f}", "open_interest": "1.00"}}})
    return out


def _trade_rows(tk, tr):
    t, p, s, q = tr
    out = []
    for i in range(t.size):
        side = "yes" if s[i] > 0 else "no"
        out.append({"source": "kalshi", "kind": "trade", "key": f"{tk}-{i}", "observed_at": _iso(int(t[i])), "available_at": _iso(int(t[i])),
                    "value": {"trade_id": f"{tk}-{i}", "ticker": tk, "created_time": _iso(int(t[i])), "yes_price_dollars": f"{float(p[i]):.4f}",
                              "no_price_dollars": f"{1 - float(p[i]):.4f}", "count_fp": f"{float(q[i]):.2f}", "taker_side": side, "taker_outcome_side": side,
                              "taker_book_side": "bid" if side == "yes" else "ask", "is_block_trade": False}})
    return out


def _fake_archive(planted: bool, n_markets: int = 16, L: int = 160) -> FakeArchive:
    meta, cand, trades = _flow_universe(planted, n_markets=n_markets, L=L, seed=7)
    bundles = {"kalshi-settled-markets-KXNBAGAME": [_market_row(tk, "KXNBAGAME", m) for tk, m in meta.items()],
               "kalshi-candles-hourly-KXNBAGAME": sum((_candle_rows(tk, cand[tk]) for tk in cand), []),
               "kalshi-trades-KXNBAGAME": sum((_trade_rows(tk, trades[tk]) for tk in trades), []),
               "kalshi-fetch-log": [{"source": "kalshi", "kind": "fetch", "key": f"trades:{tk}", "value": {"product": "trades", "id": tk, "complete": True, "complete_from": None}}
                                    for tk in trades]}
    return FakeArchive(bundles)


def _check_contract(out):
    stat, n, verdict, reason = out
    json.dumps(stat)
    assert isinstance(n, int) and n >= 0
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert " — " in reason
    return stat, n, verdict, reason


def test_registry_contract():
    assert set(M.THEORY_MAP) == {"T-408", "T-411", "T-463"}
    assert set(M.THEORY_MAP.values()) <= set(M.HARNESSES)
    assert all(name.startswith("b6c_pmmicro_") and name == name.lower() for name in M.HARNESSES)
    assert len(M.t408_cells()) == 108 and len(M.t411_cells()) == 27


def test_harnesses_missing_bundles_are_inconclusive():
    a = FakeArchive({})
    for fn in M.HARNESSES.values():
        stat, n, verdict, reason = _check_contract(fn(a))
        assert verdict == "inconclusive" and n == 0 and "missing" in reason


def test_flow_harness_on_a_fake_archive(monkeypatch):
    monkeypatch.setattr(M, "N_BOOT", 200)
    monkeypatch.setattr(M, "N_NULL", 40)
    a = _fake_archive(True)
    stat, n, verdict, reason = _check_contract(M.b6c_pmmicro_flow_imbalance(a))
    assert stat["n_markets"] == 16 and n > 0
    assert stat["headline"]["mean_c_oos"] > 0 and stat["headline"]["permutation"]["p"] < 0.05
    assert verdict in ("inconclusive", "not_supported")          # below min_n, Polymarket cells empty
    kinds = stat["headline"]["exit_kinds_oos"]
    assert sum(kinds.values()) == n and "Exit marks" in reason and "Cost decomposition" in reason and "mostly reverses" not in reason
    assert stat["headline"]["decomposition_oos"]["quote_exits"]["n"] == kinds["quote_at_k"] + kinds["held_to_next_valid_quote"]
    a0 = _fake_archive(False)
    stat0, n0, verdict0, reason0 = _check_contract(M.b6c_pmmicro_flow_imbalance(a0))
    assert stat0["headline"]["mean_c_oos"] < 0 and verdict0 != "supported"


def test_reversal_harness_on_a_fake_archive(monkeypatch):
    monkeypatch.setattr(M, "N_BOOT", 200)
    monkeypatch.setattr(M, "N_NULL_T408", 20)
    meta, cand = _reversal_universe(True, n_markets=12, L=120, seed=5)
    bundles = {"kalshi-settled-markets-KXCPI": [_market_row(tk, "KXCPI", m) for tk, m in meta.items()],
               "kalshi-candles-hourly-KXCPI": sum((_candle_rows(tk, cand[tk]) for tk in cand), [])}
    stat, n, verdict, reason = _check_contract(M.b6c_pmmicro_hourly_reversal(FakeArchive(bundles)))
    assert stat["n_markets"] == 12 and n > 0 and stat["headline"]["mean_c_oos"] > 0
    assert stat["headline"]["trial_null"]["p"] < 0.1
    assert verdict != "supported"                                  # below min_n and no Polymarket replication
    assert "Polymarket replication" in reason
    # the distinct-cell accounting: 108 declared cells reported, 24 flagged as duplicates of their h = 1 rule, 105 trials for DSR
    assert stat["n_cells_declared"] == 108 and stat["n_cells_distinct"] == 84 and len(stat["cells"]) == 108
    assert stat["n_trials"] == 105 and stat["n_trials_declared"] == 129 and "dsr_declared_trials" in stat
    assert stat["cells"]["h1_t3_half_all_any"]["duplicate_of"] == "h1_t3_h_all_any" and "duplicate_of" not in stat["cells"]["h1_t3_h_all_any"]
    assert stat["cells"]["h1_t3_half_all_any"]["n"] == stat["cells"]["h1_t3_h_all_any"]["n"]
    assert sum(1 for v in stat["cells"].values() if "duplicate_of" in v) == 24
    assert stat["best_calibration_cell"] is None or "duplicate_of" not in stat["cells"][stat["best_calibration_cell"]]
    assert sum(stat["headline"]["exit_kinds_oos"].values()) == n and "Exit marks" in reason and "Signal books" in reason
    assert stat["headline"]["signals_dropped_prev_book"]["oos"] == 0           # every synthetic book is tight


def test_mm_harness_on_a_fake_archive(monkeypatch):
    monkeypatch.setattr(M, "N_BOOT", 200)
    meta, cand, trades = _mm_universe(False, n_markets=24, L=200)
    bundles = {"kalshi-settled-markets-KXCPI": [_market_row(tk, "KXCPI", m) for tk, m in meta.items()],
               "kalshi-candles-hourly-KXCPI": sum((_candle_rows(tk, cand[tk]) for tk in cand), []),
               "kalshi-trades-KXCPI": sum((_trade_rows(tk, trades[tk]) for tk in trades), []),
               "kalshi-fetch-log": []}
    stat, n, verdict, reason = _check_contract(M.b6c_pmmicro_market_making(FakeArchive(bundles)))
    assert stat["n_markets"] == 24 and n > 0
    assert stat["headline"]["mean_daily_oos"] > 0 and stat["headline"]["p_cluster"] < 0.05
    assert verdict == "inconclusive"                               # paper-trading criterion is None; one category only
    assert "paper-trading" in reason
