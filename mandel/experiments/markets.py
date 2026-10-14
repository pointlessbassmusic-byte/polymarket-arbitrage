"""
Market harnesses: calibration of market prices, bundle-arbitrage scan, multi-scale edge sign.
=============================================================================================

- market_calibration: is the market price h days before close a calibrated probability of the
  outcome? Brier, log loss, Murphy decomposition and a reliability table by price bucket, per
  horizon. This is both a diagnostic of the benchmark Mandel scores everyone against and the
  "controls" sanity check (a coin must score 0.25 Brier; the oracle 0).
- bundle_arb_scan: in a snapshot of both books, how often does ask_yes + ask_no < 1 (long) or
  bid_yes + bid_no > 1 (short) after fees, and how deep?
- multiscale_edge: does the sign of the market's mean error (outcome minus price) agree across
  horizons and categories? A structural bias should survive coarse-graining; noise does not.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

import numpy as np

from mandel.validation.scoring import brier_score, calibration_table, log_loss, murphy_decomposition


def _parse_ts(s) -> Optional[float]:
    if s is None:
        return None
    try:
        if isinstance(s, (int, float)):
            return float(s)
        s = str(s).replace("Z", "+00:00").replace(" ", "T")
        if s.endswith("+00"):
            s = s + ":00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def resolved_outcomes(market_rows: Iterable[dict]) -> dict[str, dict]:
    """market_id -> {outcome (1 if YES won), close_ts, volume, question, group} for binary resolved markets."""
    out = {}
    for r in market_rows:
        m = r["value"]
        if str(m.get("umaResolutionStatus", "")).lower() != "resolved":
            continue
        try:
            prices = json.loads(m["outcomePrices"]) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
            outcomes = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
        except (TypeError, json.JSONDecodeError):
            continue
        if not prices or not outcomes or len(prices) != 2:
            continue
        p_yes = float(prices[0])
        if p_yes not in (0.0, 1.0):
            continue
        close = _parse_ts(m.get("closedTime")) or _parse_ts(m.get("endDate"))
        if close is None:
            continue
        out[str(m.get("id"))] = {"outcome": int(p_yes == 1.0), "close_ts": close, "volume": float(m.get("volumeNum") or 0),
                                 "question": m.get("question", ""), "neg_risk": bool(m.get("negRisk")),
                                 "start_ts": _parse_ts(m.get("startDate"))}
    return out


def price_at_horizons(price_rows: Iterable[dict], outcomes: dict, horizons_days=(1, 3, 7, 30, 90)) -> dict[int, list[tuple[float, int, str]]]:
    """For each horizon h, the last daily price at or before close - h days: list of (p, outcome, market_id)."""
    by_market: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in price_rows:
        v = r["value"]
        by_market[v["market_id"]].append((float(v["t"]), float(v["p"])))
    res: dict[int, list] = {h: [] for h in horizons_days}
    for mid, pts in by_market.items():
        o = outcomes.get(mid)
        if not o:
            continue
        pts.sort()
        ts = np.array([t for t, _ in pts]); ps = np.array([p for _, p in pts])
        for h in horizons_days:
            cutoff = o["close_ts"] - h * 86400
            idx = np.searchsorted(ts, cutoff, side="right") - 1
            if idx >= 0 and cutoff - ts[idx] <= 3 * 86400:        # price must be at most 3 days stale
                p = float(min(max(ps[idx], 0.0), 1.0))
                res[h].append((p, o["outcome"], mid))
    return res


def market_calibration(price_rows: Iterable[dict], market_rows: Iterable[dict], horizons_days=(1, 3, 7, 30, 90)) -> dict:
    outcomes = resolved_outcomes(market_rows)
    byh = price_at_horizons(price_rows, outcomes, horizons_days)
    report = {"n_resolved_markets": len(outcomes), "horizons": {}}
    for h, rows in byh.items():
        if len(rows) < 20:
            report["horizons"][h] = {"n": len(rows), "note": "too few"}
            continue
        p = np.array([r[0] for r in rows]); o = np.array([r[1] for r in rows])
        md = murphy_decomposition(p, o, n_bins=10)
        table = calibration_table(p, o, n_bins=10)
        coin = brier_score(np.full(p.size, 0.5), o)
        report["horizons"][h] = {
            "n": int(p.size), "brier": brier_score(p, o), "log_loss": log_loss(p, o), "coin_brier": coin,
            "skill_vs_coin": 1 - brier_score(p, o) / coin if coin else None,
            "reliability": md.reliability, "resolution": md.resolution, "uncertainty": md.uncertainty,
            "mean_error": float(np.mean(o - p)), "base_rate": float(o.mean()),
            "table": [{"lo": b.lo, "hi": b.hi, "n": b.n, "mean_p": round(b.mean_prob, 4), "freq": round(b.freq, 4)} for b in table],
        }
    return report


def multiscale_edge(price_rows: Iterable[dict], market_rows: Iterable[dict], horizons_days=(1, 3, 7, 30, 90), n_boot: int = 1000, seed: int = 0) -> dict:
    """Sign and bootstrap interval of mean(outcome - price) at each horizon, split by the favourite/longshot
    buckets. The theory under test (ORIGINAL-IDEAS 3): a structural bias agrees in sign across scales."""
    outcomes = resolved_outcomes(market_rows)
    byh = price_at_horizons(price_rows, outcomes, horizons_days)
    rng = np.random.default_rng(seed)
    out = {"horizons": {}, "buckets": {}}
    signs = []
    for h, rows in byh.items():
        if len(rows) < 30:
            continue
        e = np.array([r[1] - r[0] for r in rows])
        boots = rng.choice(e, size=(n_boot, e.size), replace=True).mean(axis=1)
        lo, hi = np.quantile(boots, [0.025, 0.975])
        out["horizons"][h] = {"n": int(e.size), "mean_error": float(e.mean()), "ci": [float(lo), float(hi)]}
        signs.append(int(np.sign(e.mean())) if not (lo <= 0 <= hi) else 0)
    for name, (lo_p, hi_p) in {"longshot_0_0.2": (0.0, 0.2), "mid_0.2_0.8": (0.2, 0.8), "favourite_0.8_1": (0.8, 1.0001)}.items():
        per_h = {}
        for h, rows in byh.items():
            sel = [r for r in rows if lo_p <= r[0] < hi_p]
            if len(sel) < 30:
                continue
            e = np.array([r[1] - r[0] for r in sel])
            boots = rng.choice(e, size=(n_boot, e.size), replace=True).mean(axis=1)
            lo, hi = np.quantile(boots, [0.025, 0.975])
            per_h[h] = {"n": int(e.size), "mean_error": float(e.mean()), "ci": [float(lo), float(hi)]}
        out["buckets"][name] = per_h
    nonzero = [s for s in signs if s != 0]
    out["n_scales_significant"] = len(nonzero)
    out["n_scales_total"] = len(signs)
    out["signs_agree"] = bool(nonzero) and len(set(nonzero)) == 1
    return out


def bundle_arb_scan(book_rows: Iterable[dict], taker_fee_bps: float = 150.0, gas_per_order: float = 0.02, min_depth_usd: float = 5.0) -> dict:
    """Scan one snapshot for bundle mispricings after fees. Uses the top of book and the depth at it."""
    n = 0; long_ops = []; short_ops = []; spreads = []
    for r in book_rows:
        v = r["value"]; b = v["books"]
        try:
            ask_y = min(float(x["price"]) for x in b["yes"]["asks"]); ask_n = min(float(x["price"]) for x in b["no"]["asks"])
            bid_y = max(float(x["price"]) for x in b["yes"]["bids"]); bid_n = max(float(x["price"]) for x in b["no"]["bids"])
            dep_ay = sum(float(x["size"]) for x in b["yes"]["asks"] if float(x["price"]) == ask_y) * ask_y
            dep_an = sum(float(x["size"]) for x in b["no"]["asks"] if float(x["price"]) == ask_n) * ask_n
        except (ValueError, KeyError):
            continue
        n += 1
        fee = taker_fee_bps / 10000
        spreads.append((ask_y - bid_y) + (ask_n - bid_n))
        total_ask = ask_y + ask_n
        net_long = 1.0 - total_ask - fee * total_ask - 2 * gas_per_order
        total_bid = bid_y + bid_n
        net_short = total_bid - 1.0 - fee * total_bid - 2 * gas_per_order
        if net_long > 0 and min(dep_ay, dep_an) >= min_depth_usd:
            long_ops.append({"market": v.get("question", "")[:60], "net_edge": round(net_long, 4), "depth_usd": round(min(dep_ay, dep_an), 2)})
        if net_short > 0:
            short_ops.append({"market": v.get("question", "")[:60], "net_edge": round(net_short, 4)})
    return {"markets_scanned": n, "long_after_fees": len(long_ops), "short_after_fees": len(short_ops),
            "gross_long_candidates": sum(1 for r in [] ), "median_round_trip_spread": float(np.median(spreads)) if spreads else None,
            "examples_long": sorted(long_ops, key=lambda d: -d["net_edge"])[:5], "examples_short": sorted(short_ops, key=lambda d: -d["net_edge"])[:5],
            "params": {"taker_fee_bps": taker_fee_bps, "gas_per_order": gas_per_order, "min_depth_usd": min_depth_usd}}
