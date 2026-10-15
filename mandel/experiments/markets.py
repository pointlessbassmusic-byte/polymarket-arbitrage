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


def resolved_outcomes(market_rows: Iterable[dict], flag_lag_days: float = 7.0) -> dict[str, dict]:
    """market_id -> {outcome (1 if YES won), close_ts, volume, question, group} for binary resolved markets.

    close_ts is when the outcome became known: min(closedTime, endDate). closedTime alone often lags the event by days or
    weeks of UMA resolution, so 'h days before closedTime' can be a post-event price. A market whose closedTime is more
    than ``flag_lag_days`` after its endDate is flagged (``postponed_flag``: postponed, annulled or slow to resolve)."""
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
        closed, end = _parse_ts(m.get("closedTime")), _parse_ts(m.get("endDate"))
        known = [t for t in (closed, end) if t is not None]
        if not known:
            continue
        close = min(known)
        lag = (closed - end) / 86400 if closed is not None and end is not None else None
        out[str(m.get("id"))] = {"outcome": int(p_yes == 1.0), "close_ts": close, "volume": float(m.get("volumeNum") or 0),
                                 "question": m.get("question", ""), "neg_risk": bool(m.get("negRisk")),
                                 "start_ts": _parse_ts(m.get("startDate")), "closed_ts": closed, "end_ts": end,
                                 "anchor": "endDate" if (end is not None and (closed is None or end < closed)) else "closedTime",
                                 "closed_after_end_days": lag, "postponed_flag": bool(lag is not None and lag > flag_lag_days)}
    return out


def _anchor_summary(outcomes: dict) -> dict:
    return {"anchored_at_endDate": sum(1 for o in outcomes.values() if o.get("anchor") == "endDate"),
            "anchored_at_closedTime": sum(1 for o in outcomes.values() if o.get("anchor") == "closedTime"),
            "postponed_flagged": sum(1 for o in outcomes.values() if o.get("postponed_flag")),
            "rule": "close = min(closedTime, endDate); flagged when closedTime > endDate + 7d"}


def price_at_horizons(price_rows: Iterable[dict], outcomes: dict, horizons_days=(1, 3, 7, 30, 90),
                      dropped: Optional[dict] = None) -> dict[int, list[tuple[float, int, str]]]:
    """For each horizon h, the last daily price at or before close - h days: list of (p, outcome, market_id).
    A cutoff after the market's endDate (a post-event price) is skipped; ``dropped`` (if given) receives the count per horizon."""
    by_market: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in price_rows:
        v = r["value"]
        by_market[v["market_id"]].append((float(v["t"]), float(v["p"])))
    res: dict[int, list] = {h: [] for h in horizons_days}
    drop = {h: 0 for h in horizons_days}
    for mid, pts in by_market.items():
        o = outcomes.get(mid)
        if not o:
            continue
        pts.sort()
        ts = np.array([t for t, _ in pts]); ps = np.array([p for _, p in pts])
        for h in horizons_days:
            cutoff = o["close_ts"] - h * 86400
            if o.get("end_ts") is not None and cutoff > o["end_ts"]:
                drop[h] += 1                                        # post-event price: the outcome was already known
                continue
            idx = np.searchsorted(ts, cutoff, side="right") - 1
            if idx >= 0 and cutoff - ts[idx] <= 3 * 86400:        # price must be at most 3 days stale
                p = float(min(max(ps[idx], 0.0), 1.0))
                res[h].append((p, o["outcome"], mid))
    if dropped is not None:
        dropped.update(drop)
    return res


def market_calibration(price_rows: Iterable[dict], market_rows: Iterable[dict], horizons_days=(1, 3, 7, 30, 90)) -> dict:
    outcomes = resolved_outcomes(market_rows)
    dropped: dict = {}
    byh = price_at_horizons(price_rows, outcomes, horizons_days, dropped=dropped)
    report = {"n_resolved_markets": len(outcomes), "horizons": {}, "close_anchor": _anchor_summary(outcomes),
              "dropped_post_end_by_horizon": {str(h): k for h, k in dropped.items()}}
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
    out = {"horizons": {}, "buckets": {}, "close_anchor": _anchor_summary(outcomes)}
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
    # T-03 pass: signs agree across ALL horizons, judged on the raw sign of every horizon's mean error (a non-significant
    # horizon still counts); a horizon with too few markets is unscored, so agreement across all horizons is not shown.
    raw = [int(np.sign(v["mean_error"])) for v in out["horizons"].values()]
    out["raw_signs"] = {str(h): int(np.sign(v["mean_error"])) for h, v in out["horizons"].items()}
    out["signs_agree"] = bool(len(raw) == len(tuple(horizons_days)) and 0 not in raw and len(set(raw)) == 1)
    return out


def bundle_arb_scan(book_rows: Iterable[dict], taker_fee_bps: float = 150.0, gas_per_order: float = 0.02, min_depth_usd: float = 5.0) -> dict:
    """Scan one snapshot for bundle mispricings after fees. Uses the top of book and the depth at it.

    Units: the fee is a share of notional, gas is USD per order. The bundle is sized at the executable top-of-book quantity
    q = min(YES shares, NO shares) at the best prices, and net_usd = q * (1 - (ask_yes + ask_no) * (1 + fee)) - 2 * gas.
    A long mispricing is net_usd > 0 with >= min_depth_usd on each side. ``net_edge`` is net_usd / q (USD per $1 bundle)."""
    n = 0; long_ops = []; short_ops = []; spreads = []; gross = 0
    for r in book_rows:
        v = r["value"]; b = v["books"]
        try:
            ask_y = min(float(x["price"]) for x in b["yes"]["asks"]); ask_n = min(float(x["price"]) for x in b["no"]["asks"])
            bid_y = max(float(x["price"]) for x in b["yes"]["bids"]); bid_n = max(float(x["price"]) for x in b["no"]["bids"])
            sy = sum(float(x["size"]) for x in b["yes"]["asks"] if float(x["price"]) == ask_y)
            sn = sum(float(x["size"]) for x in b["no"]["asks"] if float(x["price"]) == ask_n)
            by = sum(float(x["size"]) for x in b["yes"]["bids"] if float(x["price"]) == bid_y)
            bn = sum(float(x["size"]) for x in b["no"]["bids"] if float(x["price"]) == bid_n)
        except (ValueError, KeyError):
            continue
        dep_ay, dep_an = sy * ask_y, sn * ask_n
        n += 1
        fee = taker_fee_bps / 10000
        spreads.append((ask_y - bid_y) + (ask_n - bid_n))
        total_ask = ask_y + ask_n
        gross += total_ask < 1.0
        q_long = min(sy, sn)
        net_long_usd = q_long * (1.0 - total_ask * (1 + fee)) - 2 * gas_per_order
        total_bid = bid_y + bid_n
        q_short = min(by, bn)
        net_short_usd = q_short * (total_bid - 1.0 - fee * total_bid) - 2 * gas_per_order
        if net_long_usd > 0 and min(dep_ay, dep_an) >= min_depth_usd:
            long_ops.append({"market": v.get("question", "")[:60], "net_edge": round(net_long_usd / q_long, 4), "net_usd": round(net_long_usd, 2),
                             "size_shares": q_long, "depth_usd": round(min(dep_ay, dep_an), 2)})
        if net_short_usd > 0:
            short_ops.append({"market": v.get("question", "")[:60], "net_edge": round(net_short_usd / q_short, 4), "net_usd": round(net_short_usd, 2), "size_shares": q_short})
    return {"markets_scanned": n, "long_after_fees": len(long_ops), "short_after_fees": len(short_ops),
            "gross_long_candidates": int(gross), "median_round_trip_spread": float(np.median(spreads)) if spreads else None,
            "examples_long": sorted(long_ops, key=lambda d: -d["net_edge"])[:5], "examples_short": sorted(short_ops, key=lambda d: -d["net_edge"])[:5],
            "params": {"taker_fee_bps": taker_fee_bps, "gas_per_order": gas_per_order, "min_depth_usd": min_depth_usd}}
