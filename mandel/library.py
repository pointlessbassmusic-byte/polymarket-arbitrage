"""
Library renderers: structured sweep results (venues, options strategies, underlying strategies) -> JSON + Markdown.
=================================================================================================================

The agents return structured records; nothing is merged by another agent. These functions dedupe, sort and
render deterministically, and derive theory-registry entries from the strategies' claims so every strategy
in the library is also a falsifiable statement with a status. Strategy JSON files live in ``mandel/options/``
and ``mandel/strategies/``; Markdown lives in ``mandel/knowledge/``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from mandel._io import atomic_write_text
from mandel.paths import KNOWLEDGE_ROOT, MANDEL_ROOT


def _esc(x) -> str:
    if isinstance(x, list):
        x = ", ".join(str(i) for i in x)
    return str("" if x is None else x).replace("|", "\\|").replace("\n", " ").strip()


# ----------------------------------------------------------------------- venues --

VENUE_ORDER = {"yes": 0, "yes-with-conditions": 1, "institutional-only": 2, "unclear": 3, "no": 4}


def render_venues(result: dict, day: str) -> tuple[str, dict]:
    venues = []
    for lane in result.get("lanes", []):
        for v in lane.get("venues", []):
            venues.append({**v, "lane": lane["lane"]})
    venues.sort(key=lambda v: (VENUE_ORDER.get(v.get("us_retail_api"), 5), v.get("category", ""), v["name"].lower()))
    counts = Counter(v.get("us_retail_api") for v in venues)
    by_cat = Counter(v.get("category") for v in venues)
    lines = [f"# Venues where a US person can trade through an API (swept {day})", "",
             f"**{len(venues)} venues** across {len(result.get('lanes', []))} lanes, each checked by a sweep agent and re-checked by a skeptic agent that re-fetched the documentation. "
             f"US retail API access: " + ", ".join(f"{k} {counts[k]}" for k in VENUE_ORDER if counts.get(k)) + ". "
             "Facts come from the fetched pages (listed per venue); 'not stated' means the page did not say. This is a map for choosing execution and data venues, not an endorsement; "
             "Mandel trades nothing until a theory passes the gate and the user says so.", "",
             "By category: " + ", ".join(f"{k} {n}" for k, n in by_cat.most_common()) + ".", ""]
    for status in VENUE_ORDER:
        rows = [v for v in venues if v.get("us_retail_api") == status]
        if not rows:
            continue
        lines += [f"## US retail API access: {status} ({len(rows)})", "",
                  "| Venue | Category | Regulators | Asset classes | Options via API | API | Auth | Paper | Rate limits | Market data | Fees | Python SDK | Rules | Verified | Mandel use |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v in rows:
            name = f"[{_esc(v['name'])}]({v['docs_url']})" if v.get("docs_url", "").startswith("http") else _esc(v["name"])
            lines.append("| " + " | ".join([name, _esc(v.get("category")), _esc(v.get("regulators")), _esc(v.get("asset_classes")), _esc(v.get("options_support")),
                                            _esc(v.get("api_types")), _esc(v.get("auth")), _esc(v.get("paper_trading")), _esc(v.get("rate_limits")), _esc(v.get("market_data")),
                                            _esc(v.get("fees")), _esc(v.get("python_sdk")), _esc(v.get("account_minimums_and_rules")), "yes" if v.get("verified") else "no", _esc(v.get("mandel_relevance"))]) + " |")
        lines.append("")
        for v in rows:
            if v.get("us_notes"):
                lines.append(f"- **{_esc(v['name'])}**: {_esc(v['us_notes'])}" + (f" Sources: {', '.join(u for u in v.get('fetched_urls', [])[:3])}" if v.get("fetched_urls") else ""))
        lines.append("")
    corr = [c for lane in result.get("lanes", []) for c in lane.get("corrections", [])]
    if corr:
        lines += [f"## Skeptic corrections ({len(corr)})", ""] + [f"- {_esc(c)}" for c in corr] + [""]
    return "\n".join(lines), {"swept": day, "count": len(venues), "venues": venues}


# ------------------------------------------------------------ options strategies --

def _legs_str(legs: list[dict]) -> str:
    return "; ".join(f"{l.get('side')} {l.get('qty')}x {l.get('instrument')} @ {l.get('strike_rule')} ({l.get('expiry_rule')})" for l in legs)


def render_options_strategies(result: dict, day: str, engine_checks: dict | None = None) -> tuple[str, dict]:
    strategies = []
    for fam in result.get("families", []):
        for s in fam.get("strategies", []):
            strategies.append({**s, "family": s.get("family") or fam["family"]})
    strategies.sort(key=lambda s: (s["family"], s["name"].lower()))
    fams = Counter(s["family"] for s in strategies)
    now = sum(1 for s in strategies if s.get("testable_now"))
    ec = engine_checks or {}
    lines = [f"# Options strategies (library swept {day})", "",
             f"**{len(strategies)} strategies** in {len(fams)} families, each extracted by one agent and corrected by an adversarial verifier that recomputed payoffs from the legs and fetched a source. "
             f"{now} have a claim testable with data Mandel holds today; the rest are blocked, mostly on the daily option-chain capture that started {day}. "
             "Every strategy is also a falsifiable claim in the theory registry (T-100 upward). Legs are templates the payoff engine (`mandel/options`) can price and draw; "
             "the engine check column says whether the template parsed and what risk shape it produced.", "",
             "Families: " + ", ".join(f"{k} {n}" for k, n in fams.most_common()) + ".", ""]
    for fam, _ in fams.most_common():
        rows = [s for s in strategies if s["family"] == fam]
        lines += [f"## {fam} ({len(rows)})", ""]
        for s in rows:
            chk = ec.get(s["slug"], {})
            g = s.get("greeks_at_inception", {})
            lines += [f"### {_esc(s['name'])} (`{s['slug']}`)", "",
                      f"- legs: {_esc(_legs_str(s.get('legs', [])))}",
                      f"- payoff at expiry: {_esc(s.get('payoff_at_expiry'))}",
                      f"- max profit: {_esc(s.get('max_profit'))} · max loss: {_esc(s.get('max_loss'))} · breakevens: {_esc(s.get('breakevens'))}",
                      f"- Greeks at inception: delta {_esc(g.get('delta'))}, gamma {_esc(g.get('gamma'))}, theta {_esc(g.get('theta'))}, vega {_esc(g.get('vega'))}",
                      f"- when: {_esc(s.get('when_to_use'))}", f"- risks: {_esc(s.get('risks'))} · margin: {_esc(s.get('margin_note'))}",
                      f"- assets: {_esc(s.get('assets'))}", f"- crypto: {_esc(s.get('crypto_notes'))}", f"- metals: {_esc(s.get('metals_notes'))}"]
            if s.get("variants"):
                lines.append(f"- variants: {_esc(s['variants'])}")
            lines.append(f"- **claim:** {_esc(s.get('claim'))}")
            t = s.get("trial", {})
            lines.append(f"- trial: statistic {_esc(t.get('statistic'))}; null {_esc(t.get('null'))}; procedure {_esc(t.get('procedure'))}; data {_esc(t.get('data'))}; min n {_esc(t.get('min_n'))}; pass {_esc(t.get('pass'))}; controls {_esc(t.get('controls'))}")
            lines.append(f"- testable now: {'yes' if s.get('testable_now') else 'no'}" + (f" · blocked on: {_esc(s.get('blocked_on'))}" if s.get("blocked_on") else "") + f" · harness: {_esc(s.get('harness_suggestion'))}")
            if chk:
                lines.append(f"- engine check: parsed {chk.get('parsed')}, {chk.get('n_legs')} legs, risk {'defined' if chk.get('defined_risk') else ('full-downside' if chk.get('full_downside') else ('UNBOUNDED loss' if chk.get('downside_unbounded') else 'bounded'))}, "
                             f"upside {'unbounded' if chk.get('upside_unbounded') else 'capped'}, breakevens {chk.get('n_breakevens')}, net {'credit' if (chk.get('net_debit') or 0) < 0 else 'debit'}")
            if s.get("sources"):
                lines.append(f"- sources: {', '.join(s['sources'][:4])}")
            lines.append("")
        for fam_rec in result.get("families", []):
            if fam_rec["family"] == fam and (fam_rec.get("corrections") or fam_rec.get("missing_added")):
                lines.append(f"Verifier for {fam}: {len(fam_rec.get('corrections', []))} corrections; added {_esc(fam_rec.get('missing_added'))}.")
                lines.append("")
    return "\n".join(lines), {"swept": day, "count": len(strategies), "strategies": strategies}


# --------------------------------------------------------- underlying strategies --

def render_underlying_strategies(result: dict, day: str) -> tuple[str, dict]:
    strategies = []
    for fam in result.get("families", []):
        for s in fam.get("strategies", []):
            strategies.append({**s, "family": s.get("family") or fam["family"]})
    strategies.sort(key=lambda s: (s["family"], s["name"].lower()))
    fams = Counter(s["family"] for s in strategies)
    now = sum(1 for s in strategies if s.get("testable_now"))
    lines = [f"# Strategies on the underlying: stocks, funds, crypto, metals, event contracts (swept {day})", "",
             f"**{len(strategies)} strategies** in {len(fams)} families, extracted and adversarially verified. {now} are testable with data Mandel holds today. "
             "Each is a falsifiable claim in the theory registry (T-200 upward). Literature notes say what happened out of sample after publication; most anomalies decayed, "
             "which is why nothing here is believed until a harness says so.", "",
             "Families: " + ", ".join(f"{k} {n}" for k, n in fams.most_common()) + ".", ""]
    for fam, _ in fams.most_common():
        rows = [s for s in strategies if s["family"] == fam]
        lines += [f"## {fam} ({len(rows)})", ""]
        for s in rows:
            t = s.get("trial", {})
            lines += [f"### {_esc(s['name'])} (`{s['slug']}`)", "", f"- rule: {_esc(s.get('rule'))}", f"- assets: {_esc(s.get('assets'))}",
                      f"- crypto: {_esc(s.get('crypto_notes'))} · metals: {_esc(s.get('metals_notes'))} · event contracts: {_esc(s.get('event_contract_notes'))}"]
            if s.get("variants"):
                lines.append(f"- variants: {_esc(s['variants'])}")
            lines += [f"- literature, out of sample: {_esc(s.get('literature_out_of_sample'))}", f"- **claim:** {_esc(s.get('claim'))}",
                      f"- trial: statistic {_esc(t.get('statistic'))}; null {_esc(t.get('null'))}; procedure {_esc(t.get('procedure'))}; data {_esc(t.get('data'))}; min n {_esc(t.get('min_n'))}; pass {_esc(t.get('pass'))}; controls {_esc(t.get('controls'))}",
                      f"- costs and capacity: {_esc(s.get('costs_and_capacity'))}",
                      f"- testable now: {'yes' if s.get('testable_now') else 'no'}" + (f" · blocked on: {_esc(s.get('blocked_on'))}" if s.get("blocked_on") else "") + f" · harness: {_esc(s.get('harness_suggestion'))}"]
            if s.get("sources"):
                lines.append(f"- sources: {', '.join(s['sources'][:4])}")
            lines.append("")
        for fam_rec in result.get("families", []):
            if fam_rec["family"] == fam and (fam_rec.get("corrections") or fam_rec.get("missing_added")):
                lines.append(f"Verifier for {fam}: {len(fam_rec.get('corrections', []))} corrections; added {_esc(fam_rec.get('missing_added'))}.")
                lines.append("")
    return "\n".join(lines), {"swept": day, "count": len(strategies), "strategies": strategies}


# ------------------------------------------------------------- theories from them --

def theories_from_strategies(strategies: Iterable[dict], id_start: int, kind: str, origin_prefix: str, existing_ids: set[str]) -> list[dict]:
    """One registry entry per strategy claim. Status: untested when testable_now, else blocked with the stated blocker."""
    out = []
    i = id_start
    for s in strategies:
        tid = f"T-{i}"
        while tid in existing_ids:
            i += 1; tid = f"T-{i}"
        t = s.get("trial", {})
        claim = (s.get("claim") or "").strip()
        if claim and not claim.endswith("."):
            claim += "."
        out.append({"id": tid, "slug": s["slug"][:60], "kind": kind, "claim": claim or f"{s['name']} has positive expectancy under its stated conditions.",
                    "origin": [f"{origin_prefix}:{s['family']}"] + [u for u in s.get("sources", [])[:2]],
                    "trial": {"statistic": t.get("statistic", ""), "null": t.get("null", ""), "procedure": t.get("procedure", ""), "data": t.get("data", ""),
                              "min_n": t.get("min_n", 0), "pass": t.get("pass", ""), "controls": t.get("controls", "")},
                    "experiments": [], "testable_now": bool(s.get("testable_now")), "status": "untested" if s.get("testable_now") else "blocked",
                    "blocked_on": "" if s.get("testable_now") else (s.get("blocked_on") or "a harness and the data it names"), "results": [],
                    "notes": f"from the {origin_prefix} library: {s['name']}; harness suggestion: {s.get('harness_suggestion', '')}"})
        existing_ids.add(tid); i += 1
    return out


# ------------------------------------------------------------ engine checks --

def engine_check_strategies(strategies: Iterable[dict], S: float = 100.0) -> dict:
    """Run every template's legs through the payoff engine and compare with the stated max loss / max profit.
    Flags: 'loss_text_vs_engine' when the text says unlimited/unbounded loss but the engine finds it bounded (or the
    reverse), 'profit_text_vs_engine' likewise; 'unparsed' when a strike rule fell back to ATM."""
    from mandel.options.strategies import build_position, classify_risk
    out = {}
    for s in strategies:
        try:
            pos, info = build_position(s, S)
            risk = classify_risk(pos, S)
        except Exception as e:  # a template the engine cannot draw is itself a finding
            out[s["slug"]] = {"error": repr(e)[:160], "parsed": False}
            continue
        loss_text = (s.get("max_loss") or "").lower(); profit_text = (s.get("max_profit") or "").lower()
        says_unbounded_loss = any(w in loss_text for w in ("unlimited", "unbounded", "theoretically unlimited", "infinite"))
        says_unbounded_profit = any(w in profit_text for w in ("unlimited", "unbounded", "infinite"))
        flags = []
        if not info["parsed"]:
            flags.append("unparsed")
        if says_unbounded_loss != bool(risk["downside_unbounded"]) and info["parsed"]:
            flags.append("loss_text_vs_engine")
        if says_unbounded_profit != bool(risk["upside_unbounded"]) and info["parsed"]:
            flags.append("profit_text_vs_engine")
        out[s["slug"]] = {"parsed": info["parsed"], "n_legs": info["n_legs"], "defined_risk": risk["defined_risk"], "full_downside": risk["full_downside"],
                          "downside_unbounded": risk["downside_unbounded"], "upside_unbounded": risk["upside_unbounded"], "n_breakevens": len(risk["breakevens"]),
                          "net_debit": round(pos.net_debit(), 4), "max_loss_fraction_of_spot": round(risk["max_loss_fraction_of_spot"], 3), "flags": flags}
    return out
