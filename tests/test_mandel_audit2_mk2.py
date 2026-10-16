"""Audit round 2, group 'mk2' (markets.py, library_reconcile.py), synthetic data only.

1. OM-6 follow-up (T-03): multiscale_edge.signs_agree is three-valued: False when scored raw signs disagree (or one is 0),
   None when they agree but a registered horizon is unscored, True only when every registered horizon is scored with one sign.
2. OM-15, T-03 part: multiscale_edge intervals resample whole events (events[0].id, else negRiskMarketID, else market) and
   report n_events beside n.
3. OM-6 (rw), reconcile part: a superseded theory's harnesses move to experiments_frozen, so run_all no longer re-scores it.
"""

import copy
import json
from datetime import datetime, timedelta, timezone

import numpy as np

from mandel.experiments import markets
from mandel.experiments.markets import event_clusters, multiscale_edge
from mandel.library_reconcile import reconcile

UTC = timezone.utc


# ------------------------------------------------------------------------------- 1. signs_agree is True / False / None --

def _byh(means: dict, n: int = 300):
    """Rows (p=0.5, outcome, id) whose mean(outcome - price) is exactly the given value per horizon."""
    out = {}
    for h, m in means.items():
        k = int(round((m + 0.5) * n))
        out[h] = [(0.5, int(i < k), f"{h}-{i}") for i in range(n)]
    return out


def _edge(monkeypatch, byh):
    monkeypatch.setattr(markets, "price_at_horizons", lambda *a, **k: byh)
    return multiscale_edge([], [])


def test_signs_agree_none_when_scored_horizons_agree_but_one_is_unscored(monkeypatch):
    same = _byh({1: 0.02, 3: 0.02, 7: 0.02, 30: 0.12, 90: 0.02})
    rep = _edge(monkeypatch, same)
    assert rep["signs_agree"] is True and rep["unscored_horizons"] == [] and rep["n_scales_significant"] == 1
    short = copy.deepcopy(same); short[90] = short[90][:10]              # the checker's case: 90d cut to 10 rows
    rep = _edge(monkeypatch, short)
    assert rep["raw_signs"] == {"1": 1, "3": 1, "7": 1, "30": 1} and rep["n_scales_total"] == 4
    assert rep["signs_agree"] is None and rep["unscored_horizons"] == ["90"]   # was False -> 'significant horizons disagree'


def test_signs_agree_false_is_decisive_even_with_an_unscored_horizon(monkeypatch):
    mixed = _byh({1: -0.02, 3: -0.02, 7: -0.02, 30: 0.12, 90: 0.02})
    assert _edge(monkeypatch, mixed)["signs_agree"] is False
    mixed[90] = mixed[90][:10]                                          # scored horizons already disagree: unscored 90d cannot rescue it
    rep = _edge(monkeypatch, mixed)
    assert rep["signs_agree"] is False and rep["unscored_horizons"] == ["90"]
    zero = _byh({1: 0.0, 3: 0.02, 7: 0.02, 30: 0.12, 90: 0.02})        # a zero raw sign is not agreement
    assert _edge(monkeypatch, zero)["raw_signs"]["1"] == 0 and _edge(monkeypatch, zero)["signs_agree"] is False


def test_signs_agree_none_when_nothing_is_scored(monkeypatch):
    rep = _edge(monkeypatch, {h: [] for h in (1, 3, 7, 30, 90)})
    assert rep["n_scales_total"] == 0 and rep["signs_agree"] is None


# ------------------------------------------------------------------------------- 2. event-clustered intervals --

CLOSE = datetime(2026, 6, 1, tzinfo=UTC)


def _market(mid: str, yes: bool, events=None, neg_risk_id=None) -> dict:
    m = {"id": mid, "umaResolutionStatus": "resolved", "outcomes": json.dumps(["Yes", "No"]),
         "outcomePrices": json.dumps(["1", "0"] if yes else ["0", "1"]),
         "closedTime": CLOSE.isoformat(), "endDate": CLOSE.isoformat(), "question": mid}
    if events is not None:
        m["events"] = events
    if neg_risk_id is not None:
        m["negRiskMarketID"] = neg_risk_id
    return {"value": m}


def _prices(mids, p=0.5, days=120):
    return [{"value": {"market_id": mid, "t": (CLOSE - timedelta(days=d)).timestamp(), "p": p}} for mid in mids for d in range(days)]


def _clustered_panel(n_events=40, per_event=10, n_yes_events=24):
    """Every market of an event shares its outcome (perfectly dependent); price 0.5, so mean error = 24/40 - 0.5 = +0.10.
    iid over 400 markets: se ~0.025, interval excludes zero. Over 40 events: se ~0.078, interval straddles zero."""
    rows, mids = [], []
    for k in range(n_events):
        ev = [{"id": f"E{k}", "title": f"event {k}"}]
        for j in range(per_event):
            mid = f"m{k}-{j}"
            rows.append(_market(mid, k < n_yes_events, events=json.dumps(ev) if j % 2 else ev))   # events as JSON text or list
            mids.append(mid)
    return rows, mids


def test_intervals_resample_events_not_markets():
    rows, mids = _clustered_panel()
    rep = multiscale_edge(_prices(mids), iter(rows), horizons_days=(1, 7))   # a one-shot iterator must feed both readers
    for h in (1, 7):
        s = rep["horizons"][h]
        assert s["n"] == 400 and s["n_events"] == 40 and abs(s["mean_error"] - 0.10) < 1e-12
        lo, hi = s["ci"]
        assert lo < 0 < hi and hi - lo > 0.2                            # iid would give ~[0.05, 0.15], 'significant'
    assert rep["n_scales_significant"] == 0 and "event-clustered" in rep["ci_method"]
    assert rep["buckets"]["mid_0.2_0.8"][7]["n_events"] == 40
    # the old iid bootstrap over the same 400 markets excludes zero
    e = np.array([1 - 0.5] * 240 + [0 - 0.5] * 160)
    iid = np.quantile(np.random.default_rng(0).choice(e, size=(1000, e.size)).mean(axis=1), [0.025, 0.975])
    assert iid[0] > 0


def test_independent_markets_are_their_own_clusters():
    rows = [_market(f"x{i}", i % 5 < 3) for i in range(200)]           # no event, no negRisk id: one cluster per market
    rep = multiscale_edge(_prices([f"x{i}" for i in range(200)]), rows, horizons_days=(7,))
    s = rep["horizons"][7]
    assert s["n"] == s["n_events"] == 200 and abs(s["mean_error"] - 0.10) < 1e-12
    assert s["ci"][0] > 0                                               # se ~0.035: an independent panel still shows the bias


def test_event_cluster_key_fallbacks():
    keys = event_clusters([_market("a", True, events=[{"id": 7}]), _market("b", True, events=json.dumps([{"id": 7}])),
                           _market("c", True, events=[], neg_risk_id="0xabc"), _market("d", True, neg_risk_id="0xabc"),
                           _market("e", True, events="not json"), _market("f", True)])
    assert keys == {"a": "event:7", "b": "event:7", "c": "negrisk:0xabc", "d": "negrisk:0xabc", "e": "market:e", "f": "market:f"}


# ------------------------------------------------------------------------------- 3. reconcile freezes superseded harnesses --

def _theory(tid, slug, claim, experiments, results, status):
    return {"id": tid, "slug": slug, "kind": "underlying", "claim": claim, "origin": ["underlying:fam"],
            "trial": {"statistic": "s", "null": "n", "procedure": "p", "data": "d", "min_n": 10, "pass": "x > 0", "controls": "c"},
            "experiments": list(experiments), "testable_now": True, "status": status, "blocked_on": "", "results": list(results), "notes": ""}


def _strategy(slug, claim):
    return {"slug": slug, "name": slug, "family": "fam", "claim": claim, "testable_now": True, "sources": [],
            "trial": {"statistic": "s", "null": "n", "procedure": "p", "data": "d", "min_n": 10, "pass": "x > 0", "controls": "c"}}


def test_reconcile_moves_superseded_experiments_to_frozen():
    from mandel.experiments.run import _scored_theories
    reg = {"theories": [_theory("T-10", "old-claim", "Old wording.", ["h_old"], ["X-1"], "supported"),
                        _theory("T-11", "same-claim", "Same wording.", ["h_same"], ["X-2"], "not_supported"),
                        _theory("T-12", "untested-claim", "Draft wording.", ["h_draft"], [], "untested")]}
    rep = reconcile(reg, [_strategy("old-claim", "Restated wording"), _strategy("same-claim", "Same wording"),
                          _strategy("untested-claim", "Corrected draft")], "underlying", "underlying", 600, {"fam": True})
    by = {t["id"]: t for t in reg["theories"]}
    assert rep["superseded"] == ["T-10"] and rep["unchanged"] == ["T-11"] and rep["updated"] == ["T-12"]
    new = [t for t in reg["theories"] if t.get("supersedes") == "T-10"]
    assert len(new) == 1 and new[0]["experiments"] == []
    old = by["T-10"]
    assert old["experiments"] == [] and old["experiments_frozen"] == ["h_old"]
    assert old["status"] == "supported" and old["results"] == ["X-1"]  # the standing verdict is kept, not rewritten
    assert by["T-11"]["experiments"] == ["h_same"] and "experiments_frozen" not in by["T-11"]
    assert by["T-12"]["experiments"] == ["h_draft"] and "experiments_frozen" not in by["T-12"]   # rewritten in place: still scored
    scored = _scored_theories(reg)
    assert "h_old" not in scored and scored["h_same"] == ["T-11"]       # run_all no longer re-scores the superseded wording
    # an existing experiments_frozen list is merged into, without duplicates
    t = _theory("T-20", "again", "First wording.", ["h_old", "h_more"], ["X-3"], "not_supported"); t["experiments_frozen"] = ["h_old"]
    reg2 = {"theories": [t]}
    assert reconcile(reg2, [_strategy("again", "Second wording")], "underlying", "underlying", 600, {"fam": True})["superseded"] == ["T-20"]
    assert t["experiments"] == [] and t["experiments_frozen"] == ["h_old", "h_more"]
