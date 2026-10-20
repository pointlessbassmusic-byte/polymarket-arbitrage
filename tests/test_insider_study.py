"""insider-purchases: screener parsing, events, the placebo bar."""
import datetime as dt

from cryptobot import insider_study as ins

PAGE = """<table class="tinytable"><tr><th>X</th></tr>
<tr><td></td><td>2020-01-31 17:53:42</td><td>2020-01-30</td><td><b><a href="/CATC" onmouseover="Tip('x', DELAY, 1)">CATC</a></b></td>
<td>Cambridge Bancorp</td><td>Fuchs Christine</td><td>Dir</td><td>P - Purchase</td><td>$71.51</td><td>+500</td>
<td>808</td><td>+162%</td><td>+$35,755</td><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td>2020-01-31 10:00:00</td><td>2020-01-29</td><td><a href="/XYZ">XYZ</a></td><td>X Co</td>
<td>Doe Jane</td><td>CEO</td><td>S - Sale</td><td>$10</td><td>-5</td><td>1</td><td>-1%</td><td>-$50</td>
<td></td><td></td><td></td><td></td></tr></table>"""


def test_screener_keeps_purchases_and_reads_the_link_ticker():
    rows = ins.parse_screener(PAGE)
    assert len(rows) == 1
    r = rows[0]
    assert (r["ticker"], r["filed"], r["traded"], r["title"]) == ("CATC", "2020-01-31", "2020-01-30", "Dir")
    assert r["value"] == 35755.0 and r["price"] == 71.51


def test_params_cover_the_whole_month_and_every_officer_flag():
    p = ins.screener_params(dt.date(2024, 2, 1), 2)
    assert p["fdr"] == "02/01/2024 - 02/29/2024" and p["page"] == "2" and p["xp"] == "1"
    assert p["isdirector"] == p["isceo"] == "1" and p["vl"] == "25"


def test_events_group_by_ticker_and_filing_and_flag_clusters():
    f = [{"ticker": "A", "filed": "2020-01-10", "insider": "x", "value": 30000},
         {"ticker": "A", "filed": "2020-01-10", "insider": "x", "value": 20000},
         {"ticker": "A", "filed": "2020-02-01", "insider": "y", "value": 40000},
         {"ticker": "B", "filed": "2020-01-10", "insider": "z", "value": 50000}]
    ev = {(e["ticker"], e["filed"]): e for e in ins.events(f)}
    assert ev[("A", "2020-01-10")]["value"] == 50000 and ev[("A", "2020-01-10")]["cluster"] is False
    assert ev[("A", "2020-02-01")]["cluster"] is True     # y, plus x 22 days earlier
    assert ev[("B", "2020-01-10")]["cluster"] is False


def _px(n=400, start=dt.date(2020, 1, 1), drift=0.0):
    rows, p, d = [], 10.0, start
    for i in range(n):
        rows.append({"date": d.isoformat(), "open": p, "close": p * (1 + drift), "high": p, "low": p, "volume": 1e6})
        p *= 1 + drift
        d += dt.timedelta(days=1)
    return rows


def test_a_name_that_rises_everywhere_earns_nothing_over_its_placebo():
    # survivorship in miniature: a steady riser beats SPY in any window, so
    # event minus placebo is ~0 and the bar is not met
    evs = [{"ticker": "UP", "filed": f"2020-{m:02d}-05", "value": 1, "insiders": 1, "cluster": False}
           for m in range(1, 10)]
    prices = {"UP": _px(drift=0.002), "SPY": _px()}
    r = ins.evaluate(evs, prices, "every", 20)
    assert r["events"] == 9 and abs(r["mean"]) < 1e-9
    assert r["event_minus_spy"] > 0.03
    assert ins.verdict(r) == "killed"
