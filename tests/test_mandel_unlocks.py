"""Unlock parsers: FOMC headings and calendar blocks, Ken French daily blocks, VIX futures expiry rule."""

from datetime import date

from mandel.data.unlocks import parse_calendar_page, parse_french_daily, parse_meeting_heading, vx_expiries


def test_fomc_headings():
    assert parse_meeting_heading("June 30-July 1 Meeting", 1998)["decision_day"] == "1998-07-01"
    assert parse_meeting_heading("Jan/Feb 31-1 Meeting", 2017)["decision_day"] == "2017-02-01"
    assert parse_meeting_heading("April/May 30-1 Meeting", 2013)["start"] == "2013-04-30"
    u = parse_meeting_heading("October 16 (unscheduled)", 2013)
    assert u["decision_day"] == "2013-10-16" and u["scheduled"] is False
    assert parse_meeting_heading("March 17-18 (cancelled) Meeting", 2020) is None
    assert parse_meeting_heading("January 9 Conference Call", 2008) is None


def test_fomc_calendar_blocks():
    html = ('<h4><a id="1">2026 FOMC Meetings</a></h4>'
            '<div class="fomc-meeting__month x"><strong>January</strong></div><div class="fomc-meeting__date y">27-28</div><div>Statement</div>'
            '<div class="fomc-meeting__month x"><strong>Aug</strong></div><div class="fomc-meeting__date y">22</div><div>(notation vote)</div>'
            '<div class="fomc-meeting__month x"><strong>Apr/May</strong></div><div class="fomc-meeting__date y">30-1*</div><div>Statement</div>'
            '<div class="fomc-meeting__month x"><strong>December</strong></div><div class="fomc-meeting__date y">8-9*</div><div>Statement</div>')
    ms = parse_calendar_page(html)
    assert [m["decision_day"] for m in ms] == ["2026-01-28", "2026-05-01", "2026-12-09"] and ms[1]["sep"] and ms[2]["sep"]


def test_french_and_vx():
    cols, rows = parse_french_daily("note\n\n,Mkt-RF,SMB,HML,RF\n20260828,   -0.33,   -0.02,   -0.39,    0.01\n20260831,  0.10,  0.20,  -99.99,  0.01\n\nAnnual\n,Mkt-RF\n2025, 10.0\n")
    assert cols == ["Mkt-RF", "SMB", "HML", "RF"] and len(rows) == 2 and "HML" not in rows[1]          # -99.99 is French's missing code
    assert [d.isoformat() for d in vx_expiries(date(2025, 10, 1), date(2025, 12, 31))] == ["2025-10-22", "2025-11-19", "2025-12-17"]
