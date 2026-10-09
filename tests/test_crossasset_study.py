import datetime as dt
import math
import pickle
import random

from cryptobot import crossasset_study as X


def _hourly(start: dt.datetime, hours: int, price: float = 100.0):
    out = {}
    ts = int(start.timestamp())
    for i in range(hours):
        out[ts + i * 3600] = (price + i, price + i + 0.5)
    return out


def test_ols_recovers_known_slope_and_nw_t_is_finite():
    rng = random.Random(3)
    xs = [rng.gauss(0, 1) for _ in range(600)]
    ys = [0.5 + 2.0 * x + rng.gauss(0, 0.5) for x in xs]
    fit = X.ols(ys, [[x] for x in xs])
    assert abs(fit["beta"][0] - 0.5) < 0.1 and abs(fit["beta"][1] - 2.0) < 0.1
    assert fit["t"][1] > 20 and 0.9 < fit["r2"] < 1.0
    # pure noise: |t| small
    zs = [rng.gauss(0, 1) for _ in xs]
    assert abs(X.ols(zs, [[x] for x in xs])["t"][1]) < 3


def test_solve_rejects_exact_collinearity():
    xs = [[i, 2.0 * i] for i in range(1, 50)]
    ys = [float(i) for i in range(1, 50)]
    try:
        X.ols(ys, xs)
    except ValueError as e:
        assert "singular" in str(e)
    else:
        raise AssertionError("collinear design accepted")


def test_price_at_et_uses_the_bar_starting_at_that_hour_and_falls_back():
    start = dt.datetime(2024, 3, 8, 0, tzinfo=dt.timezone.utc)
    h = _hourly(start, 72)
    day = dt.date(2024, 3, 8)
    ts16 = int(dt.datetime(2024, 3, 8, 16, tzinfo=X.ET).timestamp())
    assert X.price_at_et(h, day, 16) == h[ts16][0]
    del h[ts16]
    assert X.price_at_et(h, day, 16) == h[ts16 - 3600][1]   # previous bar's close
    assert X.price_at_et({}, day, 16) is None


def test_basket_returns_equal_weight_and_min_coins(tmp_path):
    from cryptobot.backtest import PoolMeta
    from cryptobot.data.geckoterminal import Candle
    meta = PoolMeta(chain="hyperliquid", pair_address="X", symbol="X", token_address="",
                    liquidity_usd=0.0, fdv_usd=None)
    t0 = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    def coin(mult):
        return (meta, [Candle(ts=t0 + i * 86400, open=1, high=1, low=1, close=mult ** i, volume_usd=0)
                       for i in range(4)])
    cache = tmp_path / "c.pkl"
    pickle.dump({"A": coin(1.1), "B": coin(0.9)}, cache.open("wb"))
    r = X.basket_returns(cache, min_coins=2)
    d1 = dt.date(2025, 1, 2)
    assert abs(r[d1] - (math.log(1.1) + math.log(0.9)) / 2) < 1e-12
    assert X.basket_returns(cache, min_coins=3) == {}
    assert X.basket_returns(tmp_path / "missing.pkl", 1) == {}


def test_candidate_bar_needs_full_sample_and_both_latest_eras():
    ok = {"all": {"t": 3.0}, "2022-23": {"t": 1.6}, "2024-26": {"t": 2.0}}
    assert X.candidate(ok)
    assert not X.candidate({**ok, "all": {"t": 2.0}})
    assert not X.candidate({**ok, "2024-26": {"t": 1.0}})
    assert not X.candidate({**ok, "2022-23": {"t": -2.0}})      # sign flip
    assert not X.candidate({"all": None})


def _rows(n_years: int = 4, seed: int = 1):
    rng = random.Random(seed)
    rows = []
    day = dt.date(2016, 1, 1)
    while day.year < 2016 + n_years:
        if day.weekday() < 5:
            x = rng.gauss(0, 0.01)
            rows.append({"day": day, "spx": x, "btc1": 0.5 * x + rng.gauss(0, 0.02),
                         "btc_lag": rng.gauss(0, 0.03)})
        day += dt.timedelta(days=1)
    return rows


def test_walk_forward_only_fits_on_prior_years_and_charges_costs():
    rows = _rows()
    X._FITS.clear()
    wf = X.walk_forward(rows, ("spx",), cost_rt=0.0008, start_year=2018)
    assert set(wf["by_year"]) == {2018, 2019}
    assert all(k[2] in (2018, 2019) for k in X._FITS)      # fits keyed by the traded year
    assert wf["n"] == sum(1 for r in rows if r["day"].year >= 2018)
    # a large cost removes the edge
    X._FITS.clear()
    dear = X.walk_forward(rows, ("spx",), cost_rt=0.20, start_year=2018)
    assert dear["sharpe"] <= wf["sharpe"]
    sign = X.walk_forward(rows, ("spx",), cost_rt=0.0008, start_year=2018, mode="sign")
    assert sign["sharpe"] > 1.0                             # the planted relation


def test_divergence_buckets_are_disjoint_and_counted():
    rows = _rows()
    d = X.divergence(rows, threshold=0.005)
    total = sum(v["all"]["n"] for v in d.values())
    both = sum(1 for r in rows if abs(r["spx"]) > 0.005 and abs(r["btc_lag"]) > 0.005)
    assert total == both
