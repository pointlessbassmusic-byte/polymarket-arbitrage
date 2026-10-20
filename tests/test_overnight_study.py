import datetime as dt
import json
import math
import random

import pytest

from cryptobot import overnight_study as O


def _rows(n: int = 1500, seed: int = 7, overnight_drift: float = 0.0004, dividend_every: int = 0):
    """Synthetic daily open/close with a planted overnight drift and no
    intraday drift; optional quarterly 0.3% dividends via the adjusted
    close."""
    rng = random.Random(seed)
    rows = []
    day = dt.date(2001, 1, 2)
    close, adj_factor = 100.0, 1.0
    divs = set()
    i = 0
    while len(rows) < n:
        if day.weekday() < 5:
            d = 0.0
            if dividend_every and i and i % dividend_every == 0:
                d = 0.003
                divs.add(day)
            opn = close * math.exp(overnight_drift + rng.gauss(0, 0.004) - d)
            adj_factor *= (1 - d)      # everything before the ex-date is scaled down
            new_close = opn * math.exp(rng.gauss(0, 0.006))
            rows.append({"day": day, "open": opn, "close": new_close, "adj": None})
            close = new_close
            i += 1
        day += dt.timedelta(days=1)
    if dividend_every:
        # adjusted close = close x product of (1 - d) for ex-dates AFTER that day
        factor_after = 1.0
        for r in reversed(rows):
            r["adj"] = r["close"] * factor_after
            if r["day"] in divs:
                factor_after *= (1 - 0.003)
    return rows, divs


def test_series_decomposes_close_to_close_and_tags_weekdays():
    rows, _ = _rows(300)
    ser = O.series(rows)
    assert len(ser) == len(rows) - 1
    for r in ser:
        assert r["overnight"] + r["intraday"] == pytest.approx(r["close_close"], abs=1e-12)
    mon = [r for r in ser if r["start_weekday"] == 0]
    assert all(r["gap_days"] == 1 for r in mon)                       # Mon -> Tue
    fri = [r for r in ser if r["start_weekday"] == 4]
    assert all(r["gap_days"] == 3 for r in fri)                       # Fri -> Mon


def test_dividends_recovered_from_adjusted_close_and_added_overnight():
    rows, divs = _rows(600, dividend_every=63)
    found = O.dividends(rows)
    assert set(found) == divs
    assert all(abs(y - 0.003) < 1e-9 for y in found.values())
    with_d = {r["day"]: r["overnight"] for r in O.series(rows, with_dividends=True)}
    without = {r["day"]: r["overnight"] for r in O.series(rows, with_dividends=False)}
    for d in divs:
        assert with_d[d] - without[d] == pytest.approx(0.003)
    # a 2:1 split is not a dividend
    rows[300]["adj"], rows[299]["adj"] = rows[300]["close"] * 0.5, rows[299]["close"] * 0.5 * 2
    split_rows = [dict(r) for r in rows]
    for r in split_rows[:300]:
        r["adj"] = (r["adj"] or r["close"]) * 0.5 if r["adj"] else None
    assert all(y < 0.10 for y in O.dividends(split_rows).values())


def test_variants_select_the_intended_nights():
    rows, _ = _rows(400)
    ser = O.series(rows)
    allv = O.net_overnight(ser, "all nights", 0, 0, 0)
    no_wknd = O.net_overnight(ser, "skip Fri->Mon", 0, 0, 0)
    mon = O.net_overnight(ser, "Mon->Tue only", 0, 0, 0)
    assert len(allv) == len(ser) and len(no_wknd) < len(allv) and len(mon) < len(no_wknd)
    assert all(p["day"].weekday() == 1 for p in mon)
    with pytest.raises(ValueError):
        O.held(ser[0], "Tue->Wed")


def test_costs_come_off_each_night_and_sharpe_scales_by_observations_per_year():
    rows, _ = _rows(1500)
    ser = O.series(rows)
    free = O.net_overnight(ser, "all nights", 0, 0, 0)
    dear = O.net_overnight(ser, "all nights", 0.0004, 0.00003, 0.0001)
    assert all(d["ret"] == pytest.approx(f["ret"] - (2 * 0.00043 + 0.0001)) for f, d in zip(free, dear))
    s_all = O.summarize(free)
    assert s_all["mean_bp"] == pytest.approx(4.0, abs=1.5)            # planted 4 bp/night
    assert s_all["sharpe"] > 1.0
    mon = O.summarize(O.net_overnight(ser, "Mon->Tue only", 0, 0, 0))
    assert mon["n"] < s_all["n"] and mon["sharpe"] > 0.5             # not deflated by skipped nights


def test_passes_applies_the_pre_registered_bar():
    over = {"2001-07": {"sharpe": 1.0}, "2008-14": {"sharpe": 0.5}, "2015-19": {"sharpe": 0.2}, "2020-26": {"sharpe": 0.9}}
    hold = {"2001-07": {"sharpe": 0.3}, "2008-14": {"sharpe": 0.0}, "2015-19": {"sharpe": 0.8}, "2020-26": {"sharpe": 0.7}}
    assert O.passes(over, hold, 0.97)["pass"]
    assert not O.passes(over, hold, 0.90)["pass"]                      # PSR
    over2 = dict(over, **{"2020-26": {"sharpe": 0.5}})
    r = O.passes(over2, hold, 0.97)
    assert not r["pass"] and "2020-26" not in r["wins"]              # must include the latest era
    assert not O.passes({"2020-26": {"sharpe": 2.0}}, hold, 0.99)["pass"]   # too few eras scored


def test_loaders_parse_nasdaq_and_eodhd_shapes(tmp_path):
    nd = tmp_path / "nasdaq_SPY.json"
    nd.write_text(json.dumps({"data": {"tradesTable": {"rows": [
        {"date": "10/09/2026", "close": "778.57", "open": "776.24"},
        {"date": "10/08/2026", "close": "1,001.5", "open": "1,000.0"},
        {"date": "10/07/2026", "close": "0", "open": "0"}]}}}))
    rows = O.load_nasdaq(nd)
    assert [r["day"].day for r in rows] == [8, 9] and rows[0]["close"] == 1001.5
    eo = tmp_path / "eodhd.json"
    eo.write_text(json.dumps([{"date": "2001-05-31", "open": 114.5, "close": 114.8, "adjusted_close": 36.8},
                              {"date": "2001-06-01", "open": 115.0, "close": 115.5, "adjusted_close": 37.0}]))
    rows = O.load_eodhd(eo)
    assert len(rows) == 2 and rows[1]["adj"] == 37.0


def test_run_counts_trials_and_reports_dsr():
    rows, _ = _rows(1500)
    res = O.run(rows, "synthetic", {"none": 0.0, "fair basis": 0.00008})
    assert res["trials"] == 2 * 3 * 2 and len(res["runs"]) == 12
    assert "dsr_best" in res and 0.0 <= res["dsr_best"] <= 1.0
    text = O.render(res)
    assert "overnight-only, net" in text and "trials 12" in text
