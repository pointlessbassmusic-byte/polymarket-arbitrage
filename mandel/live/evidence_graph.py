"""
Live evidence graph: what every running strategy depends on, with measured state, and the alerts that follow.
=============================================================================================================

    python -m mandel.live.evidence_graph [--today YYYY-MM-DD]

The signal map (mandel.graph) links research files to concepts to Mandel's decision centres by text statistics. This
graph has the same shape, from evidence to decisions, but its nodes are the things that trade and its edges carry
measured state:

  strategy  every row of the paper strategy tracker (state/tracker/strategies.json)
  signal    what a strategy reads to decide (IBS, turn of month, funding, queue depth, ...)
  stream    the data a signal is computed from: an archived bundle family (health = age of its newest bundle) or a
            child's recorder (health = age of the child's last report)
  venue     where it trades, with its cost
  account   the broker account it trades in (two strategies in one account share cash and P&L)
  factor    the risk it carries (US equity beta, short volatility, crypto beta, ...), signed

Edges: strategy -reads-> signal -from-> stream; strategy -trades_on-> venue; strategy -in-> account;
strategy -exposed_to-> factor (sign +1 long, -1 short); claim -contradicts-> claim (the signal map's 'tension' edges,
here between measured results that point opposite ways).

Monitors, all read-only (they recommend; nothing here places, sizes or cancels an order):
  1. propagate   a stale or broken stream flags every strategy downstream of it
  2. exposure    strategies sharing a factor or an account are grouped with their combined capital, against a cap
  3. contradict  measured results that conflict are surfaced so a venue / category split can be tested
  4. checkpoint  a test at its pre-registered decision point gets the sizing rule's output (and only then)
  5. next tests  blocked / inconclusive / untested theories ranked by how ready their data is and what deciding
                 them would be worth (value of information), including theories the archive has since unblocked

Rule (MANDEL.md): a live parameter changes only through a ledgered, pre-registered run. These monitors may justify
pausing (the runner's KILL file, which the user or the operator touches); adding risk waits for a checkpoint.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from mandel.paths import MANDEL_ROOT

TRACKER = MANDEL_ROOT / "state" / "tracker"
REGISTRY = MANDEL_ROOT / "theories" / "registry.json"
ARCHIVE_INDEX = MANDEL_ROOT / "archive" / "INDEX.json"
CHILD_TESTS = MANDEL_ROOT / "state" / "children" / "forward_tests.json"

# ------------------------------------------------------------------------------------------------- the wiring --
# What each tracked strategy reads, from where, where it trades and what risk it carries. Mandel's rows come from its
# own code (mandel.live.sleeves, the T-541..T-543 harness data fields); the children's from their first-contact reports.
# capital_usd here is the capital at work in the factor (live money or the paper sleeve's budget), not account equity.
WIRING: dict[str, dict] = {
    "T-559": {"signals": ["overnight-gap", "ibs", "turn-of-month", "spy-tlt-monthend"], "streams": ["alpaca-iex-bars"],
              "venue": "alpaca", "account": "alpaca-paper-1", "factors": {"us-equity-beta": 1}, "capital_usd": 3000},
    "T-560": {"signals": ["trend-10m-sma", "put-premium"], "streams": ["alpaca-option-quotes", "alpaca-iex-bars"],
              "venue": "alpaca", "account": "alpaca-paper-1", "factors": {"us-equity-beta": 1, "short-volatility": 1},
              "capital_usd": 2000},
    "T-565": {"signals": ["hmm-vol-regime", "put-premium"], "streams": ["alpaca-iex-bars", "cboe-PUT-history"],
              "venue": "record-only", "factors": {}},
    "T-566": {"signals": ["hmm-vol-regime", "overnight-gap"], "streams": ["alpaca-iex-bars"], "venue": "record-only",
              "factors": {}},
    "T-573": {"signals": ["ewma-vol", "overnight-gap"], "streams": ["alpaca-iex-bars"], "venue": "record-only", "factors": {}},
    "T-567": {"signals": ["pre-holiday"], "streams": ["alpaca-iex-bars"], "venue": "alpaca", "account": "alpaca-paper-wide",
              "factors": {"us-equity-beta": 1}, "capital_usd": 2000},
    "T-568": {"signals": ["put-premium"], "streams": ["alpaca-option-quotes"], "venue": "alpaca",
              "account": "alpaca-paper-wide", "factors": {"gold-beta": 1, "rates-beta": 1, "oil-beta": 1, "short-volatility": 1},
              "capital_usd": 500},                       # max loss per spread (one spread per underlying)
    "T-542": {"signals": ["put-call-parity"], "streams": ["options-chain-SPX"], "venue": "cboe-delayed", "factors": {}},
    "T-541": {"signals": ["vix-call-premium"], "streams": ["options-chain-VIX", "cboe-VVIX-history"], "venue": "cboe-delayed",
              "factors": {}},
    "T-543": {"signals": ["event-day-vol"], "streams": ["deribit-dvol-BTC-history", "fomc-meetings", "macro-release-cpi"],
              "venue": "deribit-model", "factors": {}},
    "H-bounce-short": {"signals": ["bounce-in-decline"], "streams": ["child:Hurst:kalshi-perp-books"], "venue": "kalshi-perps",
                       "account": "kalshi-hurst", "factors": {"crypto-beta": -1}, "capital_usd": 1000},
    "H-orb-qqq": {"signals": ["opening-range"], "streams": ["child:Hurst:alpaca-bars"], "venue": "alpaca",
                  "account": "alpaca-paper-1", "factors": {"us-equity-beta": 1}, "capital_usd": 0},
    "H-2s10s-xlf": {"signals": ["curve-2s10s"], "streams": ["child:Hurst:alpaca-bars"], "venue": "alpaca",
                    "account": "alpaca-paper-1", "factors": {"us-equity-beta": 1}, "capital_usd": 0},
    "H-btc-us500-lead": {"signals": ["cross-perp-lead"], "streams": ["child:Hurst:kalshi-perp-books"], "venue": "kalshi-perps"},
    "H-book-imbalance": {"signals": ["book-imbalance"], "streams": ["child:Hurst:kalshi-perp-books"], "venue": "kalshi-perps"},
    "H-btc-favourite": {"signals": ["favourite-longshot"], "streams": ["child:Hurst:kalshi-settled-binaries"], "venue": "kalshi"},
    "H-hype-fade": {"signals": ["attention-spike"], "streams": ["child:Hurst:hype-signals"], "venue": "kalshi-perps"},
    "H-ibit-carry": {"signals": ["funding-carry"], "streams": ["child:Hurst:perp-funding", "child:Hurst:ibit-surface"],
                     "venue": "kalshi-perps"},
    "H-ibit-ladder": {"signals": ["btc-vol-premium"], "streams": ["child:Hurst:ibit-surface"], "venue": "ibit-options"},
    "H-btc-tom": {"signals": ["turn-of-month"], "streams": ["child:Hurst:kalshi-perp-books"], "venue": "kalshi-perps"},
    "H-us500-overnight": {"signals": ["overnight-gap", "funding-carry"], "streams": ["child:Hurst:kalshi-perp-books"],
                          "venue": "kalshi-perps"},
    "H-gold-perp-carry": {"signals": ["funding-carry"], "streams": ["child:Hurst:perp-funding", "fred-DTB3"], "venue": "kalshi-perps"},
    "K-maker-kalshi": {"signals": ["touch-maker-clv"], "streams": ["child:Kelly:kalshi-books"], "venue": "kalshi",
                       "account": "kalshi-kelly", "factors": {}, "capital_usd": 0},
    "K-tennis-longshot-no": {"signals": ["favourite-longshot"], "streams": ["child:Kelly:kalshi-books"], "venue": "kalshi"},
    "K-thin-queue-maker": {"signals": ["touch-maker-clv", "queue-depth"], "streams": ["child:Kelly:kalshi-books"], "venue": "kalshi"},
    "K-queue-markov-fill": {"signals": ["queue-depth", "touch-maker-clv"], "streams": ["child:Kelly:kalshi-books"], "venue": "kalshi"},
    "B-maker-pmus": {"signals": ["touch-maker-clv"], "streams": ["child:Brier:pmus-books"], "venue": "polymarket-us",
                     "account": "pmus-brier", "factors": {}, "capital_usd": 0},
    "B-paper-book": {"signals": ["model-vs-market"], "streams": ["child:Brier:polymarket-tape"], "venue": "polymarket"},
    "B-longshot-calibration": {"signals": ["favourite-longshot"], "streams": ["child:Brier:pmus-books"], "venue": "polymarket-us"},
    "S-fed-g10": {"signals": ["central-bank-bucket"], "streams": ["child:Shannon:cb-watch"], "venue": "kalshi"},
    "S-kalshi-crypto-short": {"signals": ["favourite-longshot"], "streams": ["child:Shannon:kalshi-crypto-recorder"], "venue": "kalshi"},
    "S-macro-buckets": {"signals": ["central-bank-bucket"], "streams": ["child:Shannon:cb-watch"], "venue": "kalshi"},
}

# Cost per round trip, for the venue nodes (bp of notional unless marked).
VENUES = {
    "alpaca": "0 commission; auction fills; IEX data", "cboe-delayed": "data only (15-minute delayed chains)",
    "deribit-model": "model-priced, not US-accessible", "kalshi-perps": "4 bp taker / 2 bp maker a side; funding 3x a day",
    "kalshi": "quadratic fee, ~1-2 c a contract at mid prices", "polymarket-us": "maker rebate tiered (0 below $10M/month)",
    "polymarket": "paper only (not US-accessible for trading)", "record-only": "no orders (shadow record)", "ibit-options": "~$0.65 a contract; ~$25k margin for the ladder",
}

# Measured results that point opposite ways (the signal map's 'tension' edges, between numbers instead of texts).
CONTRADICTIONS = [
    {"a": "T-557", "b": "H-btc-favourite", "topic": "favourite-longshot",
     "detail": "Polymarket YES < 0.10 at 7 days resolved +2.08 pp ABOVE price (longshots underpriced); Hurst finds Kalshi "
               "crypto longshots lose 27-72% per dollar (overpriced), and Kelly's forward record bets NO on tennis longshots.",
     "test": "split the calibration by venue x category in B-longshot-calibration before acting on either"},
    {"a": "T-41", "b": "T-554", "topic": "greed-sentiment",
     "detail": "Mandel's T-41 expected greed (F&G >= 75) to be contrarian; the data showed BTC's 7-day return HIGHER after greed.",
     "test": "T-554 replicates on ETH; until it reads, neither direction is traded"},
]

FACTOR_CAP_USD = {"us-equity-beta": 8000, "short-volatility": 3500, "crypto-beta": 1500, "gold-beta": 1000,
                  "rates-beta": 1000, "oil-beta": 1000}   # combined, per factor

STREAM_STALE_DAYS = 3        # an archived daily stream older than this (in days) is stale
STREAM_STALE_OVERRIDE = {"fomc-meetings": 120, "macro-release-cpi": 40,   # calendars: refreshed monthly at most
                         "cboe-PUT-history": 10}                           # refreshed weekly by the capture box
CHILD_STALE_DAYS = 10        # a child's figures older than this are stale (weekly protocol + slack)

STATUS_WEIGHT = {"inconclusive": 1.0, "untested": 0.8, "blocked": 0.5}


# ----------------------------------------------------------------------------------------------- data access --

def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _bundles() -> dict:
    return _load(ARCHIVE_INDEX, {}).get("bundles", {})


def apply_capture_status(bundles: dict, status: dict) -> dict:
    """Merge the Linode capture box's status (branch capture/status, fetched to state/tracker/capture_status.json): its
    newest day per dated family becomes a bundle name, and newer created_at stamps of undated bundles win. Names and
    dates only; no data."""
    out = dict(bundles)
    for fam, f in (status.get("families") or {}).items():
        if f.get("latest"):
            out.setdefault(f"{fam}-{f['latest']}", {"created_at": f["latest"], "source": "capture box"})
    for name, ts in (status.get("undated") or {}).items():
        cur = str((out.get(name) or {}).get("created_at", ""))
        if ts and ts > cur:
            out[name] = {**(out.get(name) or {}), "created_at": ts, "source": "capture box"}
    return out


_DATED = re.compile(r"^(?P<family>.+?)-(?P<day>\d{4}-\d{2}-\d{2})$")


def stream_health(stream: str, bundles: dict, today: date, child_as_of: Optional[str]) -> dict:
    """{state: ok|stale|missing|child, age_days, latest}. Dated families (options-chain-SPX-2026-10-15) are aged by
    their newest date; other bundles by created_at; child recorders by the child's last report."""
    if stream.startswith("child:"):
        age = (today - date.fromisoformat(child_as_of)).days if child_as_of else None
        return {"state": "stale" if age is None or age > CHILD_STALE_DAYS else "child", "age_days": age, "latest": child_as_of}
    if stream.startswith("alpaca-"):
        return {"state": "broker", "age_days": None, "latest": None}       # read live by the runner each session
    days = sorted(m.group("day") for k in bundles if (m := _DATED.match(k)) and m.group("family") == stream)
    if days:
        latest = days[-1]
    elif stream in bundles:
        latest = str(bundles[stream].get("created_at", ""))[:10] or None
    else:
        return {"state": "missing", "age_days": None, "latest": None}
    age = (today - date.fromisoformat(latest)).days if latest else None
    limit = STREAM_STALE_OVERRIDE.get(stream, STREAM_STALE_DAYS)
    return {"state": "stale" if age is None or age > limit else "ok", "age_days": age, "latest": latest,
            "captures": len(days) or None}


# --------------------------------------------------------------------------------------------------- the graph --

def build_graph(rows: list[dict], bundles: dict, today: date, child_as_of: Optional[str]) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid: str, kind: str, **attrs) -> None:
        nodes.setdefault(nid, {"id": nid, "kind": kind, **attrs})

    for r in rows:
        w = WIRING.get(r["id"], {})
        node(r["id"], "strategy", owner=r.get("owner"), label=r.get("strategy"), mode=r.get("mode"), state=r.get("state"))
        for s in w.get("signals", []):
            node(f"signal:{s}", "signal", label=s)
            edges.append({"from": r["id"], "to": f"signal:{s}", "kind": "reads"})
            for st in w.get("streams", []):
                edges.append({"from": f"signal:{s}", "to": f"stream:{st}", "kind": "from", "strategy": r["id"]})
        for st in w.get("streams", []):
            node(f"stream:{st}", "stream", label=st, **stream_health(st, bundles, today, child_as_of))
        if w.get("venue"):
            node(f"venue:{w['venue']}", "venue", label=w["venue"], cost=VENUES.get(w["venue"]))
            edges.append({"from": r["id"], "to": f"venue:{w['venue']}", "kind": "trades_on"})
        if w.get("account"):
            node(f"account:{w['account']}", "account", label=w["account"])
            edges.append({"from": r["id"], "to": f"account:{w['account']}", "kind": "in"})
        for f, sign in (w.get("factors") or {}).items():
            node(f"factor:{f}", "factor", label=f, cap_usd=FACTOR_CAP_USD.get(f))
            edges.append({"from": r["id"], "to": f"factor:{f}", "kind": "exposed_to", "sign": sign,
                          "capital_usd": w.get("capital_usd", 0)})
    for c in CONTRADICTIONS:
        for x in (c["a"], c["b"]):
            node(x, "strategy" if x in WIRING else "claim", label=x)
        edges.append({"from": c["a"], "to": c["b"], "kind": "contradicts", "sign": -1, "topic": c["topic"]})
    return {"as_of": today.isoformat(), "nodes": list(nodes.values()), "edges": edges}


def downstream(graph: dict, stream_id: str) -> list[str]:
    """Strategies that read any signal computed from ``stream_id``."""
    return sorted({e["strategy"] for e in graph["edges"] if e["kind"] == "from" and e["to"] == stream_id})


# ---------------------------------------------------------------------------------------------------- sizing --

def checkpoint_size(mean: float, var: float, dsr: float, cap_usd: float, kelly_fraction: float = 0.25) -> float:
    """Capital for a strategy at a decision checkpoint: fractional Kelly (mean / variance of the per-period return)
    shrunk linearly by the deflated Sharpe ratio above 0.5 (0 at DSR <= 0.5, full fraction at DSR = 1), capped.
    Returns dollars; 0 when the edge is not positive."""
    if mean <= 0 or var <= 0:
        return 0.0
    shrink = max(0.0, min(1.0, (dsr - 0.5) / 0.5))
    return round(min(cap_usd, cap_usd * kelly_fraction * (mean / var) * shrink), 2)


# --------------------------------------------------------------------------------------------------- monitors --

def _alert(severity: str, kind: str, node: str, message: str, affected: list[str], action: str) -> dict:
    return {"id": f"{kind}:{node}", "severity": severity, "kind": kind, "node": node, "message": message,
            "affected": ", ".join(affected), "n_affected": len(affected), "action": action}


def monitors(graph: dict, rows: list[dict], today: date) -> list[dict]:
    alerts: list[dict] = []
    by_id = {r["id"]: r for r in rows}
    # 1. propagate stream health
    for n in graph["nodes"]:
        if n["kind"] != "stream" or n["state"] not in ("stale", "missing"):
            continue
        hit = downstream(graph, n["id"])
        live = [s for s in hit if by_id.get(s, {}).get("mode") == "live"]
        sev = "critical" if live else "warning"
        what = (f"{n['label']}: no data since {n['latest']} ({n['age_days']} days)" if n["state"] == "stale" and n["latest"]
                else f"{n['label']}: {'no report from the child yet' if n['label'].startswith('child:') else 'not in the archive'}")
        act = ("pause the live strategies that read it until it is fresh (touch KILL / tell the child)" if live else
               "restart the capture" if not n["label"].startswith("child:") else "ask the child for its weekly status")
        alerts.append(_alert(sev, "stream", n["id"], what, hit, act))
    # 2. shared factor / account exposure
    for kind in ("factor", "account"):
        for n in (x for x in graph["nodes"] if x["kind"] == kind):
            es = [e for e in graph["edges"] if e["to"] == n["id"]]
            members = sorted({e["from"] for e in es})
            if len(members) < 2:
                continue
            if kind == "factor":
                cap = n.get("cap_usd")
                gross = sum(abs(e.get("capital_usd") or 0) for e in es)
                net = sum((e.get("sign") or 1) * (e.get("capital_usd") or 0) for e in es)
                over = cap is not None and gross > cap
                alerts.append(_alert("warning" if over else "info", "exposure", n["id"],
                                     f"{len(members)} strategies carry {n['label']}: ${gross:,.0f} gross, ${net:,.0f} net"
                                     + (f" against a ${cap:,.0f} cap" if cap else ""), members,
                                     "trim at the next checkpoint" if over else "within the cap; they move together"))
            else:
                owners = sorted({by_id.get(m, {}).get("owner") for m in members} - {None})
                if len(owners) > 1:
                    alerts.append(_alert("warning", "account", n["id"],
                                         f"one broker account shared by {', '.join(owners)}: cash, equity and P&L mix",
                                         members, "give each owner its own paper account"))
    # 3. contradictions
    for c in CONTRADICTIONS:
        alerts.append(_alert("info", "contradiction", c["topic"], c["detail"], [c["a"], c["b"]], c["test"]))
    # 4. checkpoints
    for r in rows:
        due = (r.get("progress") is not None and r["progress"] >= 1) or (r.get("read_date") and r["read_date"] <= today.isoformat())
        if due:
            alerts.append(_alert("action", "checkpoint", r["id"], f"{r['strategy']} has reached its decision point "
                                 f"({r.get('n_now')}/{r.get('n_target')} {r.get('unit')}; read {r.get('read_date') or 'n/a'})",
                                 [r["id"]], "run the pre-registered read; size only through checkpoint_size on its result"))
    order = {"critical": 0, "action": 1, "warning": 2, "info": 3}
    return sorted(alerts, key=lambda a: (order[a["severity"]], -a["n_affected"], a["id"]))


# ------------------------------------------------------------------------------------------------- next tests --

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*(?:-<[^>]+>|\*)?(?:[A-Za-z0-9_.\-]*)$")


def _need_count(blocked_on: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*(?:\w+\s+)?(?:capture\s+)?days?", blocked_on or "")
    return int(m.group(1)) if m else None


def data_readiness(data_field: str, bundles: dict, blocked_on: str = "") -> tuple[Optional[float], list[str]]:
    """Share of the bundle names in a theory's data field that the archive holds, and the missing ones. A name with
    '<...>' or '*' matches any bundle with that prefix; when the theory is blocked on a count of capture days
    ('30 days'), a dated family counts as count/required. None when the field names no bundles."""
    toks = [t.strip().strip(".;") for t in re.split(r",|\+|;| and ", data_field or "")]
    names = [t.split(" ")[0] for t in toks if t and _TOKEN.match(t.split(" ")[0]) and "-" in t.split(" ")[0]]
    if not names:
        return None, []
    missing, have = [], 0.0
    need = _need_count(blocked_on)
    for nm in names:
        prefix = re.split(r"<|\*", nm)[0]
        if prefix == nm:
            ok = 1.0 if nm in bundles else 0.0
        else:
            n = sum(1 for k in bundles if k.startswith(prefix))
            ok = (min(1.0, n / need) if need else 1.0) if n else 0.0
            if 0 < ok < 1:
                missing.append(f"{nm} ({n}/{need})")
        if ok == 0:
            missing.append(nm)
        have += ok
    return have / len(names), missing


def _newest_bundle(data_field: str, bundles: dict) -> Optional[str]:
    """Newest created_at among the bundles a data field names (prefix match for dated families)."""
    best = None
    for t in re.split(r",|\+|;| and ", data_field or ""):
        nm = t.strip().split(" ")[0]
        if not nm:
            continue
        prefix = re.split(r"<|\*", nm)[0]
        for k, b in bundles.items():
            if (k == nm) if prefix == nm else k.startswith(prefix):
                c = str(b.get("created_at", ""))
                best = c if best is None or c > best else best
    return best


def _result_times() -> dict[str, str]:
    out = {}
    p = MANDEL_ROOT / "state" / "experiments.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            out[d.get("id")] = str(d.get("created_at", ""))
    return out


def next_tests(registry: list[dict], bundles: dict, top: int = 20, result_times: Optional[dict] = None) -> list[dict]:
    """Value-of-information ranking: status weight x data readiness x new-data factor x a small-sample bonus
    (decisions that need few observations are cheap to reach) x US accessibility.

    An inconclusive theory re-run on the data it was already tested on cannot be decided, so it scores x0.2 unless a
    bundle it names is newer than its last result. Forward tests (blocked on future observations by design) are left
    out: they are tracked, not ranked. Blocked theories whose data the archive now fully holds are flagged 'unblocked'."""
    result_times = result_times if result_times is not None else _result_times()
    out = []
    for t in registry:
        st = t.get("status")
        if st not in STATUS_WEIGHT:
            continue
        trial = t.get("trial") or {}
        if "forward" in (str(trial.get("procedure", "")) + str(trial.get("statistic", "")) + str(t.get("claim", ""))).lower() \
                or t["id"] in WIRING:
            continue
        ready, missing = data_readiness(str(trial.get("data", "")), bundles, str(t.get("blocked_on") or ""))
        if ready is None:
            continue
        fresh = 1.0
        if st == "inconclusive":
            last = max((result_times.get(x, "") for x in (t.get("results") or [])), default="")
            newest = _newest_bundle(str(trial.get("data", "")), bundles) or ""
            fresh = 1.0 if (newest and last and newest > last) else 0.2
        min_n = trial.get("min_n") or 100
        try:
            min_n = float(min_n)
        except (TypeError, ValueError):
            min_n = 100.0
        text = (str(trial) + " " + str(t.get("notes", ""))).lower()
        us = 0.5 if ("not accessible to us" in text or "not us-accessible" in text) else 1.0
        cheap = 1.0 / (1.0 + math.log10(max(min_n, 10)) / 4)
        score = STATUS_WEIGHT[st] * ready * fresh * cheap * us
        out.append({"id": t["id"], "status": st, "claim": str(t.get("claim", ""))[:180], "data_ready": round(ready, 2),
                    "new_data": fresh == 1.0 if st == "inconclusive" else None,
                    "missing": ", ".join(missing[:4]), "min_n": int(min_n), "score": round(score, 3),
                    "unblocked": st == "blocked" and ready == 1.0,
                    "note": "data present: check its coverage before running" if st == "blocked" and ready == 1.0 else ""})
    return sorted(out, key=lambda x: (-x["score"], x["id"]))[:top]


# ------------------------------------------------------------------------------------------------------- main --

def run(today: date, out: Path = TRACKER) -> dict:
    rows = _load(out / "strategies.json", [])
    if not rows:
        raise SystemExit("no tracker rows: run python -m mandel.live.tracker first")
    bundles = _bundles()
    cap = _load(out / "capture_status.json", None)
    if cap:
        bundles = apply_capture_status(bundles, cap)
    child_as_of = _load(CHILD_TESTS, {}).get("as_of")
    graph = build_graph(rows, bundles, today, child_as_of)
    alerts = monitors(graph, rows, today)
    reg = _load(REGISTRY, {}).get("theories", [])
    reg = reg if isinstance(reg, list) else list(reg.values())
    nxt = next_tests(reg, bundles)
    cal = _load(out / "calibration.json", None)               # the Linode's daily per-model calibration
    for model, rec in ((cal or {}).get("models") or {}).items():
        for flag in rec.get("flags") or []:
            alerts.append(_alert("action", "calibration", f"model:{model}", f"{model}: {flag} ({rec.get('scored_days')} scored days)",
                                 ["T-565"] if model.startswith("spx") else ["T-566"],
                                 "pre-register the parameter switch; it takes effect only at the test's checkpoint"))
    alerted = {a["node"] for a in alerts}
    fams: dict[str, str] = {}
    for k in bundles:                                           # daily capture families no tracked strategy reads
        m = _DATED.match(k)
        if m and m.group("day") > fams.get(m.group("family"), ""):
            fams[m.group("family")] = m.group("day")
    for fam, last in sorted(fams.items()):
        age = (today - date.fromisoformat(last)).days
        if f"stream:{fam}" not in alerted and age > STREAM_STALE_DAYS and \
                any(t.get("status") == "blocked" and fam in str((t.get("trial") or {}).get("data", "")) for t in reg):
            alerts.append(_alert("warning", "stream", f"stream:{fam}", f"{fam}: no data since {last} ({age} days)", [],
                                 "restart the capture"))
    for a in alerts:                                            # a stale stream also holds back the theories it feeds
        if a["kind"] == "stream":
            fam = a["node"].split(":", 1)[1]
            held = [t["id"] for t in reg if t.get("status") == "blocked" and fam in str((t.get("trial") or {}).get("data", ""))]
            if held:
                a["message"] += (f"; it also holds back {len(held)} blocked theor{'y' if len(held) == 1 else 'ies'} "
                                 f"({', '.join(held[:6])}{'...' if len(held) > 6 else ''})")
                a["theories_held"] = len(held)
    order = {"critical": 0, "action": 1, "warning": 2, "info": 3}
    alerts.sort(key=lambda a: (order[a["severity"]], -(a["n_affected"] + a.get("theories_held", 0)), a["id"]))
    dependencies = [{"strategy": e["from"], "owner": next((r["owner"] for r in rows if r["id"] == e["from"]), None),
                     "kind": e["kind"], "target": e["to"].split(":", 1)[1], "target_kind": e["to"].split(":", 1)[0],
                     "health": next((n.get("state") for n in graph["nodes"] if n["id"] == e["to"]), None)}
                    for e in graph["edges"] if e["kind"] in ("trades_on", "in", "exposed_to")
                    or (e["kind"] == "from")]
    seen, deps = set(), []
    for d in dependencies:                                      # one row per (strategy, target)
        k = (d["strategy"] if d["kind"] != "from" else None, d["target"])
        if d["kind"] == "from":
            continue
        if k not in seen:
            seen.add(k); deps.append(d)
    for n in graph["nodes"]:
        if n["kind"] == "stream":
            for s in downstream(graph, n["id"]):
                deps.append({"strategy": s, "owner": next((r["owner"] for r in rows if r["id"] == s), None), "kind": "reads",
                             "target": n["label"], "target_kind": "stream", "health": n["state"]})
    for d in deps:
        d["key"] = f"{d['strategy']}|{d['target_kind']}:{d['target']}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence_graph.json").write_text(json.dumps(graph, indent=1))
    (out / "alerts.json").write_text(json.dumps(alerts, indent=1))
    (out / "next_tests.json").write_text(json.dumps(nxt, indent=1))
    (out / "dependencies.json").write_text(json.dumps(deps, indent=1))
    return {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "alerts": len(alerts), "next_tests": len(nxt),
            "dependencies": len(deps)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m mandel.live.evidence_graph")
    p.add_argument("--today", type=date.fromisoformat, default=date.today())
    a = p.parse_args(argv)
    print(json.dumps(run(a.today)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
