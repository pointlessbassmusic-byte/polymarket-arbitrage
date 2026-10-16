"""Library renderers and the engine check on hand-made entries."""

from mandel.library import engine_check_strategies, render_options_strategies, render_underlying_strategies, render_venues, theories_from_strategies


def _strat(slug, legs, max_loss, max_profit, testable=True):
    return {"name": slug, "slug": slug, "family": "test", "legs": [{"instrument": i, "side": s, "qty": 1, "strike_rule": k, "expiry_rule": "same"} for i, s, k in legs],
            "payoff_at_expiry": "", "max_profit": max_profit, "max_loss": max_loss, "breakevens": "", "greeks_at_inception": {"delta": "+", "gamma": "+", "theta": "-", "vega": "+"},
            "when_to_use": "", "risks": "", "margin_note": "", "assets": ["etfs"], "crypto_notes": "", "metals_notes": "", "variants": [],
            "claim": "it works", "trial": {"statistic": "s", "null": "n", "procedure": "p", "data": "d", "min_n": 10, "pass": "x", "controls": "c"},
            "testable_now": testable, "blocked_on": "" if testable else "chains", "harness_suggestion": "h", "sources": ["https://example.org"]}


def test_engine_check_flags_mismatches():
    good = _strat("bull-call-spread", [("call", "long", "K1"), ("call", "short", "K2")], "net debit", "K2 - K1 - debit")
    bad = _strat("naked-call-wrong", [("call", "short", "ATM")], "limited to the premium", "premium received")
    odd = _strat("odd", [("call", "long", "whatever")], "debit", "unlimited")
    chk = engine_check_strategies([good, bad, odd])
    assert chk["bull-call-spread"]["flags"] == [] and chk["bull-call-spread"]["defined_risk"]
    assert "loss_text_vs_engine" in chk["naked-call-wrong"]["flags"] and chk["naked-call-wrong"]["downside_unbounded"]
    assert chk["odd"]["flags"] == ["unparsed"]


def test_renderers_and_theory_derivation():
    res = {"families": [{"family": "test", "strategies": [_strat("a", [("call", "long", "ATM")], "debit", "unlimited"), _strat("b", [("put", "short", "ATM")], "strike - premium", "premium", testable=False)], "corrections": ["fixed x"], "missing_added": ["c"]}]}
    md, data = render_options_strategies(res, "2026-10-14", engine_check_strategies([s for f in res["families"] for s in f["strategies"]]))
    assert "# Options strategies" in md and "engine check" in md and data["count"] == 2
    ths = theories_from_strategies(data["strategies"], 100, "options-strategy", "options-library", {"T-100"})
    assert [t["id"] for t in ths] == ["T-101", "T-102"] and ths[1]["status"] == "blocked" and ths[0]["status"] == "untested" and ths[0]["claim"].endswith(".")
    umd, udata = render_underlying_strategies({"families": [{"family": "trend", "strategies": [{**_strat("tsmom", [], "", ""), "rule": "buy if up", "literature_out_of_sample": "decayed", "costs_and_capacity": "low", "event_contract_notes": ""}], "corrections": [], "missing_added": []}]}, "2026-10-14")
    assert "tsmom" in umd and udata["count"] == 1
    vmd, vdata = render_venues({"lanes": [{"lane": "x", "venues": [{"name": "Alpaca", "slug": "alpaca", "category": "broker", "us_retail_api": "yes", "us_notes": "ok", "regulators": ["FINRA"], "asset_classes": ["stocks"], "options_support": "equity", "api_types": ["REST"], "docs_url": "https://docs.alpaca.markets", "auth": "key", "paper_trading": "yes", "rate_limits": "200/min", "market_data": "IEX", "fees": "0", "python_sdk": "alpaca-py", "account_minimums_and_rules": "PDT", "verified": True, "fetched_urls": ["https://docs.alpaca.markets"], "mandel_relevance": "execution"}], "corrections": []}]}, "2026-10-14")
    assert "Alpaca" in vmd and vdata["count"] == 1
