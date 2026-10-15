"""House rule 10 (no arbitrary grid phase) for batch4_carry (key 'carry'), on synthetic data. No archive, no network.

Two harnesses rest on a grid whose phase the claim does not fix. T-198's "non-overlapping 90-day windows since 2020"
name no window calendar: a window now starts on every day from 2020-01-01, both criteria are judged on that pooled
all-start set (circular-block bootstrap in blocks of 180 daily starts) and the 90 per-offset grids are reported. T-364's
weekly observations name no weekday: the five weekday phases are pooled (each labelled from its own trailing 52
observations, blocks of 8 weeks of pooled entries) and each phase is reported. n stays in the claims' units (windows,
weeks). The other six are calendar-month (T-258), CME contract-calendar (T-362), daily (T-303, T-363), signal-driven
(T-329) or daily event-study (T-423) tests; the last tests pin the calendar anchoring of T-258 and T-362."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch4_carry as cy
from mandel.experiments.underlying2 import _mean_ci, _verdict

from tests.test_mandel_batch4_carry import _days, _hedged_setup, _hours, _quarterly_setup

NB = 300


# -------------------------------------------------------------------------------------------- the CBB helper --

def test_cbb_mean_ci_reproduces_underlying2_mean_ci():
    rng = np.random.default_rng(4)
    for n, block in ((4, 2), (27, 2), (700, 180)):
        x = rng.standard_normal(n)
        assert cy.cbb_mean_ci(x, block, 777, 3) == _mean_ci(x, block, 777, 3)


# ------------------------------------------------------------------------------------- T-198: every daily start --

def _phase_setup(low_on_offset0: bool):
    """Constant funding (~1% per 90 days) against an annualised basis of -5% on the days whose offset from 2020-01-01 is 0
    (mod 90) and +20% on every other day (or the reverse with ``low_on_offset0`` False): the grid from 2020-01-01 sees
    one regime only, the other 89 offsets the other."""
    fts = _hours("2019-12-01", "2026-12-31")
    i1 = np.full(len(fts), 0.04 / 8760)
    idx = 10000.0 * np.exp(np.linspace(0.0, 0.5, len(fts)))
    d0 = date(2020, 1, 1)
    futures, e = [], date(2020, 3, 27)
    while e <= date(2027, 6, 30):
        ets = cy._utc_ts(e, 8)
        ct = np.array([ets - k * 86400 for k in range(270, 0, -1)], dtype=np.int64)
        on0 = np.array([(date.fromisoformat(cy._day_of(t)) - d0).days % 90 == 0 for t in ct])          # UTC days
        ann = np.where(on0 == low_on_offset0, -0.05, 0.20)
        S = cy.value_at(fts, idx, ct)
        futures.append({"expiry_ts": ets, "close_ts": ct, "close": S * (1 + ann * (ets - ct) / 86400 / 365)})
        e += timedelta(days=91)
    return fts, i1, idx, futures


def test_t198_windows_start_on_every_day_and_the_grids_are_their_phases():
    fts, i1, idx, fut = _quarterly_setup(3e-5, 0.01)
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    r10 = rep["rule10"]
    last = (fts[-1] - 90 * 86400 - cy._utc_ts("2020-01-01", 8)) // 86400          # the last start whose window fits
    assert rep["pooled_starts"] == r10["pooled_starts"] == last + 1
    assert r10["offsets"] == 90 and r10["offsets_with_windows"] == 90
    w0 = rep["windows_offset0"]
    assert [w["start"] for w in w0] == [(date(2020, 1, 1) + timedelta(days=90 * k)).isoformat() for k in range(len(w0))]
    counts = [r10["per_offset"][str(o)]["n"] for o in range(90)]
    assert sum(counts) == rep["pooled_starts"] and set(counts) == {27, 28}
    assert rep["n"] == max(counts) == 28 == len(w0)                                # n in windows: what the sample holds
    assert r10["per_offset"]["37"]["first_start"] == "2020-02-07"
    assert r10["pooled_block_starts"] == 180 >= 2 * 90 and r10["per_offset_block_windows"] == 2


def test_t198_pooled_statistics_and_per_offset_report():
    fts, i1, idx, fut = _quarterly_setup(0.04 * 90 / 365 / 2160, 0.04, seed=3)      # funding prices the basis
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    r10 = rep["rule10"]
    # rebuild the pooled differences from the per-offset grids: offset o holds the starts o, o + 90, ...
    w0 = rep["windows_offset0"]
    assert all(w["offset"] == 0 for w in w0)
    d0 = np.array([w["diff"] for w in w0])
    assert r10["per_offset"]["0"]["share"] == pytest.approx(np.mean(d0 > 0))
    assert r10["per_offset"]["0"]["ci95"] == pytest.approx(list(_mean_ci(d0, 2, NB, 0)))
    shares = [r10["per_offset"][str(o)]["share"] for o in range(90)]
    counts = [r10["per_offset"][str(o)]["n"] for o in range(90)]
    assert rep["share"] == pytest.approx(np.dot(shares, counts) / sum(counts))    # the share of all pooled windows
    assert r10["share_range"] == pytest.approx([min(shares), max(shares)])
    assert r10["n_offsets_share_pass"] == sum(s >= 0.5 for s in shares)
    assert r10["n_offsets_ci_pass"] == sum(r10["per_offset"][str(o)]["ci95"][0] > 0 for o in range(90))
    head = rep["reason"].split(" — ")[0]
    assert "house rule 10" in head and f"all {rep['pooled_starts']} overlapping 90-day windows" in head
    assert f"{r10['n_offsets_share_pass']} of 90 offsets >= 50%" in head and "offsets pass both" in head
    assert "blocks of 180 daily starts" in head and "the grid from 2020-01-01 (offset 0)" in head


def test_t198_pooled_estimate_decides_against_a_lucky_grid():
    # the grid from 2020-01-01 sees only the cheap-basis days and passes both criteria; the pooled set does not
    fts, i1, idx, fut = _phase_setup(low_on_offset0=True)
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    o0 = rep["rule10"]["per_offset"]["0"]
    assert o0["share"] == 1.0 and o0["ci95"][0] > 0 and o0["share_pass"] and o0["ci_pass"]
    assert rep["share"] < 0.05 and rep["ci95"][1] < 0
    assert rep["rule10"]["n_offsets_both_pass"] == 1 and rep["n"] >= 24
    assert rep["verdict"] == "not_supported"
    assert (rep["verdict"], rep["reason"].rsplit(" — ", 1)[1]) == _verdict(rep["criteria"])
    assert "1 of 90 offsets pass both" in rep["reason"]
    # below min_n the share's decisiveness uses the pooled share: 28 windows x ~1% + 12 missing wins < 50% of 40
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB, min_n=40)
    assert "share of windows with funding_90d > basis_90d >= 50%" in rep["rule5"]["decisive_failures"]
    assert rep["verdict"] == "not_supported"


def test_t198_pooled_estimate_passes_when_one_grid_fails():
    fts, i1, idx, fut = _phase_setup(low_on_offset0=False)
    rep = cy.perp_vs_quarterly_basis(fts, i1, idx, fut, n_boot=NB)
    o0 = rep["rule10"]["per_offset"]["0"]
    assert o0["share"] == 0.0 and not o0["share_pass"] and not o0["ci_pass"]     # the old grid alone would fail
    assert rep["share"] > 0.95 and rep["ci95"][0] > 0
    assert rep["rule10"]["n_offsets_both_pass"] == 89
    assert rep["verdict"] == "supported", rep["reason"]


# -------------------------------------------------------------------------------- T-364: every weekday phase --

def test_weekly_phase_first_ok_day_on_or_after_the_weekday_else_the_last_before():
    days = _days("2024-03-04", "2024-03-31", weekdays_only=True)                   # Mon 4 Mar .. Fri 29 Mar
    ok = np.ones(len(days), dtype=bool)
    ok[days.index("2024-03-13")] = False                                           # a Wednesday drops out
    for d in ("2024-03-26", "2024-03-27", "2024-03-28", "2024-03-29"):              # an expiry week's roll window
        ok[days.index(d)] = False
    assert cy.weekly_phase(days, ok, 0) == cy.weekly_first(days, ok)
    pick = {p: [days[i] for i in cy.weekly_phase(days, ok, p)] for p in range(5)}
    assert pick[2] == ["2024-03-06", "2024-03-14", "2024-03-20", "2024-03-25"]    # Wed, else Thu; roll week: Monday
    assert pick[4] == ["2024-03-08", "2024-03-15", "2024-03-22", "2024-03-25"]
    assert all(len(v) == 4 for v in pick.values())                                 # one observation per week per phase
    assert cy.WEEKDAY_PHASES == ("Mon", "Tue", "Wed", "Thu", "Fri")


def _phased_crash(planted_phases, seed=0):
    """Weekly basis on each weekday phase of the same weeks; a ~30% fall starts on the Saturday of every 13th week (after
    every weekday phase's observation). A planted phase's basis spikes on those weeks; the others are noise."""
    rng = np.random.default_rng(seed)
    mondays = [d for d in _days("2017-12-04", "2026-09-28") if date.fromisoformat(d).weekday() == 0]
    pdays = _days("2017-11-01", "2026-12-31")
    pos = {d: i for i, d in enumerate(pdays)}
    r = 0.01 * rng.standard_normal(len(pdays))
    spikes = list(range(5, len(mondays), 13))
    for k in spikes:
        i = pos[mondays[k]]
        r[i + 5:i + 15] = -0.035
    px = 100 * np.cumprod(1 + r)
    phases = []
    for p in range(5):
        wd = [(date.fromisoformat(m) + timedelta(days=p)).isoformat() for m in mondays]
        b = 0.05 + 0.01 * rng.standard_normal(len(wd))
        if p in planted_phases:
            b[spikes] = 0.20
        phases.append((wd, b))
    return phases, pdays, px


def test_t364_single_phase_is_unchanged_and_has_no_rule10_record():
    phases, pdays, px = _phased_crash({0})
    rep = cy.basis_crash_predictor(*phases[0], pdays, px, n_perm=NB)
    assert "rule10" not in rep and "house rule 10" not in rep["reason"]
    assert rep["n"] >= 350 and rep["verdict"] == "supported", rep["reason"]


def test_t364_pooled_over_weekday_phases_matches_the_union_and_reports_each_phase():
    phases, pdays, px = _phased_crash({0, 1, 2, 3, 4})
    rep = cy.basis_crash_predictor(*phases[0], pdays, px, n_perm=NB, more_phases=phases[1:],
                                   phase_labels=cy.WEEKDAY_PHASES)
    singles = [cy.basis_crash_predictor(*ph, pdays, px, n_perm=NB) for ph in phases]
    r10 = rep["rule10"]
    assert r10["phases"] == list(cy.WEEKDAY_PHASES) and r10["pooled_block_entries"] == 8 * 5
    assert rep["n"] == singles[0]["n"]                                             # n in ISO weeks, not observations
    assert r10["pooled_entries"] == sum(s["n"] for s in singles)
    tops = sum(s["mean_depth_top"] * cnt for s, cnt in zip(singles, [r10["per_phase"][k]["top"] for k in cy.WEEKDAY_PHASES]))
    bots = sum(s["mean_depth_bottom"] * cnt for s, cnt in zip(singles, [r10["per_phase"][k]["bottom"] for k in cy.WEEKDAY_PHASES]))
    ntop = sum(r10["per_phase"][k]["top"] for k in cy.WEEKDAY_PHASES)
    nbot = sum(r10["per_phase"][k]["bottom"] for k in cy.WEEKDAY_PHASES)
    assert rep["gap_pp"] == pytest.approx(tops / ntop - bots / nbot)               # the pooled gap of the union
    for k, s in zip(cy.WEEKDAY_PHASES, singles):                                   # each phase as if tested alone
        x = r10["per_phase"][k]
        assert x["gap_pp"] == pytest.approx(s["gap_pp"]) and x["p_perm"] == pytest.approx(s["p_perm"])
        assert x["episodes"] == s["episodes"] and x["weeks"] == s["n"]
    assert r10["gap_range_pp"] == pytest.approx([min(s["gap_pp"] for s in singles), max(s["gap_pp"] for s in singles)])
    assert r10["n_phases_all_pass"] == 5 and rep["verdict"] == "supported", rep["reason"]
    head = rep["reason"].split(" — ")[0]
    assert "house rule 10" in head and "pooled over the 5 weekday phases" in head and "5 of 5 phases pass all four" in head
    assert rep["timing_rule"]["phases"] == 5


def test_t364_pooled_estimate_decides_against_a_lucky_weekday():
    # only Monday's basis carries the signal: Monday alone passes, the five weekdays pooled do not
    phases, pdays, px = _phased_crash({0})
    rep = cy.basis_crash_predictor(*phases[0], pdays, px, n_perm=NB, more_phases=phases[1:],
                                   phase_labels=cy.WEEKDAY_PHASES)
    mon = rep["rule10"]["per_phase"]["Mon"]
    assert mon["all_pass"] and mon["gap_pp"] >= 10
    assert rep["rule10"]["n_phases_all_pass"] == 1 and rep["n"] >= 350
    assert rep["gap_pp"] < 10 and rep["verdict"] == "not_supported", rep["reason"]
    assert "depth gap (top decile - bottom half) >= 10 pp" in rep["reason"].rsplit(" — ", 1)[1]
    assert "1 of 5 phases pass all four" in rep["reason"]


def test_t364_rule5_below_min_n_uses_the_pooled_blocks(monkeypatch):
    phases, pdays, px = _phased_crash(set())
    seen = []
    real = cy.block_gap_ci

    def spy(lab, dep, block, n_boot=5000, seed=0):
        seen.append((len(lab), block))
        return real(lab, dep, block, n_boot, seed)

    monkeypatch.setattr(cy, "block_gap_ci", spy)
    rep = cy.basis_crash_predictor(*phases[0], pdays, px, n_perm=NB, more_phases=phases[1:], end="2023-12-31",
                                   phase_labels=cy.WEEKDAY_PHASES)
    assert rep["n"] < 350 and "rule5" in rep
    assert seen and all(b == 40 for _, b in seen) and seen[0][0] == rep["rule10"]["pooled_entries"]
    assert rep["verdict"] == "not_supported" and rep["rule5"]["decisive_failures"]


def test_t364_harness_passes_every_weekday_phase(monkeypatch):
    days = _days("2019-01-07", "2026-09-30", weekdays_only=True)
    n = len(days)
    F = np.full(n, 101.0); S = np.full(n, 100.0); std = np.ones(n, dtype=bool)
    got = {}
    monkeypatch.setattr(cy, "_missing", lambda a, names: None)
    monkeypatch.setattr(cy, "_cme_sync", lambda a: (days, F, S, std))
    monkeypatch.setattr(cy, "_cached", lambda a, key, fn: (days, np.ones(n)))
    monkeypatch.setattr(cy, "_index", lambda a, name: {})

    def fake(obs_days, obs_basis, px_days, px_close, dtb3=None, **kw):
        got.update(obs_days=obs_days, **kw)
        return {"n": 0, "verdict": "inconclusive", "reason": "fake"}

    monkeypatch.setattr(cy, "basis_crash_predictor", fake)
    cy.carry_basis_crash_predictor(object())
    tab = cy.cme_daily_basis(days, F, S, std, cy.cme_expiries(), roll_calendar_days=3)
    assert got["phase_labels"] == cy.WEEKDAY_PHASES and len(got["more_phases"]) == 4
    assert got["obs_days"] == [days[i] for i in cy.weekly_first(days, tab["ok"])]
    for p, (wd, b) in enumerate(got["more_phases"], start=1):
        assert wd == [days[i] for i in cy.weekly_phase(days, tab["ok"], p)] and len(b) == len(wd)
    tue = [date.fromisoformat(d).weekday() for d in got["more_phases"][0][0]]
    assert tue.count(1) > 0.6 * len(tue) and 0 in tue                             # Tuesdays, Monday in roll weeks


# ------------------------------------------------------------------------------- the calendar-anchored others --

def test_t258_months_are_calendar_months():
    fts, _, deliv, dvol, rf = _hedged_setup(0.0, 0.3)
    c = 1e-5
    rep = cy.funding_call_hedged(fts, np.full(len(fts), c), deliv, dvol, rf, start="2021-04", end="2022-03", n_boot=NB)
    for row in rep["months"]:
        y, m = int(row["month"][:4]), int(row["month"][5:])
        hours = (cy._next_month(y, m) - date(y, m, 1)).days * 24                   # day 1 08:00 to next day 1 08:00
        assert row["funding"] == pytest.approx(c * hours)


def test_t362_decides_on_the_cme_contract_calendar():
    # one decision per contract month: the first standard session after the previous month's CME expiry
    days = _days("2021-12-01", "2023-01-31", weekdays_only=True)
    std = np.ones(len(days), dtype=bool)
    std[days.index("2022-01-31")] = False                                          # a half-day session is skipped
    tab = cy.cme_contract_table(days, np.full(len(days), 101.0), std, lambda t: 100.0, cy.cme_expiries(),
                                first="2022-01", last="2022-12")
    assert [c["contract"] for c in tab] == [f"2022-{m:02d}" for m in range(1, 13)]
    for c in tab:
        y, m = int(c["contract"][:4]), int(c["contract"][5:])
        prev = cy.cme_btc_expiry(y - 1, 12) if m == 1 else cy.cme_btc_expiry(y, m - 1)
        first = next(d for d, s in zip(days, std) if d > prev.isoformat() and s)
        assert c["expiry"] == cy.cme_btc_expiry(y, m).isoformat() and c["decision"] == first
    assert tab[1]["decision"] == "2022-02-01"                                      # Jan expiry 28th; the 31st is a half day


def test_module_docstring_states_rule10_for_every_harness():
    doc = " ".join(cy.__doc__.split())
    assert "House rule 10" in doc
    for t in cy.THEORY_MAP:
        assert t in doc.split("House rule 10", 1)[1], t
