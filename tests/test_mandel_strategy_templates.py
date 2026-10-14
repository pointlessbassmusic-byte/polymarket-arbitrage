"""Template parser: rules -> strikes -> Position, on the classic shapes."""

from mandel.options.payoff import Position
from mandel.options.strategies import build_position, classify_risk, parse_strike_rule

S = 100.0


def _t(name, legs):
    return {"name": name, "legs": [{"instrument": i, "side": s, "qty": q, "strike_rule": k, "expiry_rule": "same"} for i, s, q, k in legs]}


def test_rules_parse():
    for r in ("ATM", "OTM 5%", "ITM 10%", "delta 0.30", "K1", "K2", "95", "+5%", "at the money"):
        assert parse_strike_rule(r), r
    assert not parse_strike_rule("whatever the trader likes")


def test_ordered_strikes_and_shapes():
    ic = _t("iron condor", [("put", "long", 1, "K1"), ("put", "short", 1, "K2"), ("call", "short", 1, "K3"), ("call", "long", 1, "K4")])
    pos, info = build_position(ic, S)
    ks = [l.strike for l in pos.legs]
    assert info["parsed"] and ks == sorted(ks) and ks[1] < S < ks[2]
    risk = classify_risk(pos, S)
    assert risk["defined_risk"] and not risk["upside_unbounded"] and len(risk["breakevens"]) == 2 and pos.net_debit() < 0
    cc = _t("covered call", [("underlying", "long", 1, ""), ("call", "short", 1, "delta 0.30")])
    pos, info = build_position(cc, S)
    assert info["parsed"] and pos.legs[1].strike > S and not classify_risk(pos, S)["upside_unbounded"]
    ls = _t("long strangle", [("put", "long", 1, "OTM 5%"), ("call", "long", 1, "OTM 5%")])
    pos, info = build_position(ls, S)
    assert abs(pos.legs[0].strike - 95) < 1e-9 and abs(pos.legs[1].strike - 105) < 1e-9 and classify_risk(pos, S)["upside_unbounded"]
    naked = _t("short put", [("put", "short", 1, "ATM")])
    pos, _ = build_position(naked, S)
    r = classify_risk(pos, S)
    assert not r["defined_risk"] and r["full_downside"] and r["max_loss_bounded"] and r["pnl_at_grid_low"] < -90
    nc = _t("short call", [("call", "short", 1, "ATM")])
    assert classify_risk(build_position(nc, S)[0], S)["downside_unbounded"]


def test_unparseable_rule_is_flagged_not_fatal():
    odd = _t("odd", [("call", "long", 1, "wherever")])
    pos, info = build_position(odd, S)
    assert not info["parsed"] and isinstance(pos, Position) and pos.legs[0].strike == S
