"""T-577 timing contract: no feature at decision bar i may depend on any bar after i, and the target starts at bar i+1."""

import numpy as np
import pandas as pd
import pytest

from mandel.ml import features as FE


def _bars(n=3000, seed=0, sym="BTC-USD"):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-03-02 00:00", periods=n, freq="5min", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.001, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.001, n))
    v = rng.uniform(1, 10, n)
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": v}, index=t)


@pytest.mark.parametrize("interval", ["5m", "15m", "45m"])
def test_features_do_not_see_the_future(monkeypatch, interval):
    base = _bars()
    monkeypatch.setattr(FE, "load_bars", lambda iv, s: base.copy())
    f1 = FE.build("BTC-USD", interval, (1,))
    cut = len(f1) // 2
    t_cut = f1.index[cut]
    shocked = base.copy()
    later = shocked.index > t_cut + pd.Timedelta(minutes=FE.INTERVAL_MIN[interval])   # bars after the decision bar
    shocked.loc[later, ["o", "h", "l", "c"]] *= 3.0
    shocked.loc[later, "v"] *= 50
    monkeypatch.setattr(FE, "load_bars", lambda iv, s: shocked.copy())
    f2 = FE.build("BTC-USD", interval, (1,))
    feat = [c for c in FE.F0 + FE.F2 if c in f1.columns]
    a, b = f1.loc[:t_cut, feat], f2.loc[:t_cut, feat]
    assert np.allclose(a.fillna(-999).values, b.fillna(-999).values), "a feature moved when only future bars changed"


def test_target_is_next_open_to_open():
    base = _bars(800)
    import mandel.ml.features as M
    f = None
    orig = M.load_bars
    M.load_bars = lambda iv, s: base.copy()
    try:
        f = M.build("BTC-USD", "5m", (1, 3))
    finally:
        M.load_bars = orig
    lo = np.log(base["o"].values)
    i = 100
    assert f["y1"].iloc[i] == pytest.approx(lo[i + 2] - lo[i + 1])
    assert f["y3"].iloc[i] == pytest.approx(lo[i + 4] - lo[i + 1])


# --- T-578 daily swing horizons: the same contract on daily bars, including the cross-asset (F1) inputs

def _daily(n=900, seed=1, start="2023-01-02 14:30"):
    rng = np.random.default_rng(seed)
    t = pd.bdate_range(start, periods=n, tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = c * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.01, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.01, n))
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": rng.uniform(1e6, 2e6, n)}, index=t)


def _leader_frame(bars, cls):
    from mandel.ml import swing as SW
    lc = np.log(bars["c"])
    return pd.DataFrame({"known_at": SW.known_at(bars.index, cls), "r1": lc.diff().values,
                         "r5": (lc - lc.shift(5)).values, "r20": (lc - lc.shift(20)).values})


def test_swing_features_do_not_see_the_future(monkeypatch):
    from mandel.ml import swing as SW
    own, lead = _daily(seed=1), _daily(seed=2)
    cal = {"fomc": [], "cpi": []}

    def feats(own_bars, lead_bars):
        monkeypatch.setattr(SW, "load_daily", lambda s: own_bars.copy())
        return SW.build("AAPL", (1, 5, 20), {"SPY": _leader_frame(lead_bars, "equity_etf")}, cal, {})

    f1 = feats(own, lead)
    cut = len(f1) // 2
    t_cut, k_cut = f1.index[cut], f1["decision_at"].iloc[cut]
    own2, lead2 = own.copy(), lead.copy()
    own2.loc[own2.index > t_cut, ["o", "h", "l", "c"]] *= 3.0
    own2.loc[own2.index > t_cut, "v"] *= 50
    lead_later = SW.known_at(lead2.index, "equity_etf") > k_cut          # leader bars not yet known at the decision
    lead2.loc[lead_later, ["o", "h", "l", "c"]] *= 3.0
    f2 = feats(own2, lead2)
    cols = SW.F0 + SW.F2 + [c for c in f1.columns if c.startswith("x_")]
    a, b = f1.loc[:t_cut, cols], f2.loc[:t_cut, cols]
    assert np.allclose(a.fillna(-999).values, b.fillna(-999).values), "a daily feature moved when only future bars changed"
    lo = np.log(own["o"].values)
    assert f1["y5"].iloc[cut] == pytest.approx(lo[cut + 6] - lo[cut + 1])
    assert f1["yend5"].iloc[cut] == own.index[cut + 6]


def test_swing_walk_forward_purges_and_holds_do_not_overlap():
    from mandel.ml import swing as SW
    n = 3000
    t = pd.bdate_range("2015-01-02 21:00", periods=n, tz="UTC")       # runs into the 2026 development blocks
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"sym": "X", "cls": "stock", "decision_at": t, "row": np.arange(n), "a": rng.normal(size=n),
                       "y20": rng.normal(0, 0.05, n), "vn20": 0.05})
    df["yend20"] = df["decision_at"].shift(-21)
    seen = []
    orig = SW.TR.make_model

    class Spy:
        def __init__(self): self.m = orig("ridge")
        def fit(self, X, y): seen.append(len(X)); self.m.fit(X, y); return self
        def predict(self, X): return self.m.predict(X)

    SW.TR.make_model = lambda kind: Spy()
    try:
        pred = SW.walk_forward(df, ["a"], "ridge", 20, lockbox=False)
    finally:
        SW.TR.make_model = orig
    first_block = pred["decision_at"].min()
    m0 = first_block.to_period("M").to_timestamp().tz_localize("UTC")
    assert seen[0] == int((df["yend20"] < m0).sum())           # trained only on targets realised before the block
    grid = SW.non_overlapping(pred, 20)
    d = np.sort(grid["date"].unique())
    assert (np.diff(d) >= np.timedelta64(20, "D")).all()        # 20 trading days apart: no two holds overlap
