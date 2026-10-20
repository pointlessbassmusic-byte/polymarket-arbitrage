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
