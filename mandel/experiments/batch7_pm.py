"""
Batch 7, group ``pm``: two prediction-market salvage successors pre-registered on 2026-10-20 (SALVAGE-2026-10-20.md).
=====================================================================================================================

Each claim is tested exactly as worded, on its own trial.pass and trial.min_n (MANDEL.md section 2, rules 1-12). The
parents' in-sample numbers that motivated the successors are not evidence and are not reused as the test sample.

  * T-544  (successor of T-337) Kalshi KXBTCD daily 5 pm ET 'Bitcoin above' markets settling 2025-01..2026-10 against
           the Deribit-implied risk-neutral digital. T-337's construction is reused unchanged by import from
           ``batch6c_pmxv``: ``_deribit_groups`` (near-expiry BTC option trades reduced row by row into per-(hour,
           expiry) per-strike IV sums), ``_hourly_spot`` (the point-in-time forward: ``hourly-BTC-USD`` close of the bar
           ending at H) and ``SmileBook`` (a decision at the start of hour H uses option trades of hours H-2 and H-1, SVI
           and cubic smiles on total variance in k = ln(K / F_H), total variance interpolated in time between the
           bracketing expiries, p_RN = the Breeden-Litzenberger digital under the fitted smile). The Kalshi side is
           T-337's liquidity-free venue: bid/ask candles (``kalshi-candles-hourly-KXBTCD-<M>``, read as
           ``batch6c_pmmicro`` reads them: value {ticker, candle {end_period_ts, yes_bid, yes_ask, ...}}, either field
           naming through ``kalshi_quote``). A candle is the quote at its end_period_ts; the decision hour is
           H = ceil(end_period_ts / 3600), so the quote and the option trades (timestamps < H x 3600) and the spot bar
           (available at H x 3600) are one information set (rule 12). Strikes from floor_strike (else the ticker suffix
           -T<strike>), settlement from ``kalshi-settled-markets-KXBTCD-<M>`` (result yes / no), t_res = close_time
           (17:00 ET). Rule (trial.procedure): at a candle hour with a valid two-sided book (bid > 0, ask < 1,
           ask >= bid, spread <= 10 cents) and at least one hour before the close, buy YES at yes_ask when
           p_RN - yes_ask > 5 points + 1-point haircut, buy NO at 1 - yes_bid when (1 - p_RN) - (1 - yes_bid) > 5 + 1;
           hold to settlement. Net per contract = payoff - price paid - Kalshi taker fee 0.07 x P x (1 - P) rounded up
           to 6 decimals (trial.controls) - the 1-point model haircut (the claim's "after ... a 1-point model haircut";
           the procedure also puts it in the entry threshold, so it is applied in both places and the mean without
           the P&L haircut, +1 cent, is reported). One entry per market at its first qualifying hour (primary), each
           fit choosing its own entries. Pass: one-sided 95% lower bound of the mean net P&L per contract (cents) > 0
           under SVI AND under cubic (market-clustered studentized bootstrap, ``batch6c_pub.cluster_stud``, the lower
           end of the two-sided 90% interval), the same sign in 2025 and 2026 (by settlement year) under both fits,
           and DSR >= 0.95 over the declared 8 cells (threshold 5 / 10 x SVI / cubic x first / any qualifying hour),
           each primary fit deflated with the 8 cells' per-contract Sharpe variance (floored at the iid null
           1 / (T - 1)). min_n 300 contracts (= markets entered: one contract per market in the primary cells).
           Reported: event-clustered intervals (the four strikes of one day settle on one print), splits by hours to
           close and by year, the candle selection (Kalshi archives candles for the 4 most-traded strikes per event
           only), the BRTI-vs-Deribit-index basis at settlement (ln(expiration_value / the latest Deribit trade index
           in the hour before the close), reported, never applied), the per-order cent fee rounding sensitivity.
  * T-557  (successor of T-02) Polymarket cheap-YES calibration on markets T-02 never saw. T-02's construction is
           reused unchanged: ``markets.resolved_outcomes`` (binary markets resolved 0 / 1; close = min(closedTime,
           endDate)) and the price at 7 days = the last daily point at or before close - 7 d, at most 3 days stale,
           skipped when the cutoff falls after endDate (``markets.price_at_horizons``' rule, applied through
           ``batch6c_pmcal._price_before`` on ``batch6c_pmcal``'s month-bundle loaders ``_closed_meta`` / ``_outcomes``
           / ``_daily_series``). Universe: resolved markets of ``polymarket-closed-markets-<YYYY-MM>`` with daily
           history in ``polymarket-price-history-daily-<YYYY-MM>``, close in 2023-2026, MINUS every market id that
           T-02's harness reads (``polymarket-closed-markets``, the cycle-2 2,100-market bundle, and
           ``polymarket-price-history-daily``, its 400-market price bundle). Bucket: price < 0.10. Statistic:
           mean(outcome - price), event-clustered percentile bootstrap (``batch6c_pmcal.cluster_mean``: events[0].id,
           else negRiskMarketID, else the market; 2,000 draws, two-sided 95%). Pass: the 95% CI excludes 0 on the
           positive side AND at least 20 YES resolutions in the bucket; min_n 300 markets. Secondary (reported, not a
           criterion): net P&L per contract buying YES at price + 1 cent spread + the market's own fee
           (``batch6c_pmcal.pm_fee``). Reported: categories (question keywords, the fetcher's selection reason, the
           fee type), years, the scheduled-endDate-anchored sensitivity (price 7 d before endDate on markets not yet
           closed then), and the exclusion counts.

Conventions
  * Data: every bundle through ``archive.load``; month families are probed through ``archive.entries``; a missing
    required bundle or family is inconclusive and named (rule 9).
  * Rule 5: below min_n the verdict is never supported and a failing criterion counts only when its bound at the pass's
    own confidence lies wholly on the wrong side.
  * Rule 10: both claims are signal- or event-driven (first qualifying hour; a fixed horizon before each market's end):
    no grid phase is free.
  Verdicts via ``underlying2._verdict`` (through ``batch6b_bw._decide`` for T-544, ``batch6c_pmcal._finish`` for
  T-557); stat dicts are JSON-safe (NaN / inf -> None); n is in the claim's units (contracts; markets).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import _clean, _decide
from mandel.experiments.batch6c_pmcal import (LEGACY_DAILY, LEGACY_MARKETS, MONTH_DAILY_RE, MONTH_MARKETS_RE, _bundle_names,
                                              _closed_meta, _daily_series, _fetch_log, _outcomes, _price_before, cluster_key,
                                              cluster_mean, pm_fee)
from mandel.experiments.batch6c_pmxv import DRB, HBTC_B, SmileBook, _deribit_groups, _hourly_spot, kalshi_quote
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio

UTC = timezone.utc
HOUR = 3600
DAY = 86_400.0
N_BOOT = 2000
SEED = 0

KS_BTCD = "kalshi-settled-markets-KXBTCD-"
KH_BTCD = "kalshi-candles-hourly-KXBTCD-"
KALSHI_FEE = 0.07
SPREAD_MAX = 0.10
EPS = 1e-6
WINDOW_544 = (int(datetime(2025, 1, 1, tzinfo=UTC).timestamp()), int(datetime(2026, 11, 1, tzinfo=UTC).timestamp()))
DERIBIT_FROM = "2024-12"           # option trades needed from the first listing of a 2025-01 market (open up to ~7 days early)
HTC_BUCKETS = (("1-3 h", 1, 3), ("4-6 h", 4, 6), ("7-12 h", 7, 12), ("13-24 h", 13, 24), ("25+ h", 25, 10 ** 9))
CELLS_544 = [(thr, kind, mode) for thr in (5.0, 10.0) for kind in ("svi", "cubic") for mode in ("first", "any")]


# ======================================================================================================= utilities ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
    try:
        return sorted(e.name for e in archive.entries() if e.name.startswith(prefix))
    except Exception:
        return []


def _missing(archive, names: Sequence[str], families: Sequence[str] = ()):
    """Inconclusive (rule 9) naming every missing bundle and every family (prefix) with no archived month."""
    miss = [n for n in names if not _has(archive, n)] + [p + "<YYYY-MM>" for p in families if not _names(archive, p)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v, f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ts(s) -> Optional[int]:
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return int(s)
    try:
        d = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    return int((d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp())


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


# ====================================================================================================== T-544 ==

def kalshi_fee_6dp(price: float, rate: float = KALSHI_FEE) -> float:
    """Kalshi taker fee per contract, rate x P x (1 - P), rounded UP to 6 decimals (trial.controls)."""
    raw = round(rate * price * (1.0 - price) * 1e6, 6)          # strip float noise before the ceiling
    return math.ceil(raw) / 1e6


def kalshi_fee_cent(price: float, rate: float = KALSHI_FEE) -> float:
    """Sensitivity: a one-contract order's fee rounded up to the next cent (Kalshi's per-order rounding)."""
    raw = round(rate * price * (1.0 - price) * 100, 6)
    return math.ceil(raw) / 100


_TK_STRIKE = re.compile(r"-T(\d+(?:\.\d+)?)$")


def kxbtcd_markets(rows) -> dict:
    """{ticker: {close_s, result (1 / 0), strike, event, expiration_value}} of settled 'above' KXBTCD markets (result yes
    / no only; strike from floor_strike, else the ticker suffix -T<strike>). Rows with another strike_type are dropped."""
    out = {}
    for r in rows:
        v = r.get("value") or {}
        tk = v.get("ticker")
        if not tk:
            continue
        st = v.get("strike_type")
        if st not in (None, "", "greater"):
            continue
        res = str(v.get("result") or "").lower()
        if res not in ("yes", "no"):
            continue
        close_s = _ts(v.get("close_time"))
        K = _num(v.get("floor_strike"))
        if K is None:
            m = _TK_STRIKE.search(str(tk))
            K = float(m.group(1)) if m else None
        if close_s is None or K is None or K <= 0:
            continue
        out[str(tk)] = {"close_s": int(close_s), "result": 1 if res == "yes" else 0, "strike": float(K),
                        "event": str(v.get("event_ticker") or tk.rsplit("-", 1)[0]), "expiration_value": _num(v.get("expiration_value"))}
    return out


def kxbtcd_candles(rows) -> dict:
    """{ticker: [(H, bid, ask)] sorted by H} from hourly candle rows: H = ceil(end_period_ts / 3600) is the decision hour at
    whose start the candle's closing quote is known; the latest row of a ticker-hour wins."""
    by: dict = defaultdict(dict)
    for r in rows:
        v = r.get("value") or {}
        tk = v.get("ticker")
        c = v.get("candle") or {}
        end = _num(c.get("end_period_ts"))
        if not tk or end is None:
            continue
        bid, ask, _vol = kalshi_quote(c)
        if bid is None or ask is None:
            continue
        H = -(-int(end) // HOUR)
        by[str(tk)][H] = (float(bid), float(ask))
    return {tk: [(H, b, a) for H, (b, a) in sorted(d.items())] for tk, d in by.items()}


def valid_book(bid: float, ask: float) -> bool:
    """A two-sided book: bid > 0, ask < 1, ask >= bid, spread <= 10 cents."""
    return bid > 0.0 and ask < 1.0 and ask >= bid and ask - bid <= SPREAD_MAX + EPS


def prn_table(markets: dict, candles: dict, p_rn: Callable, window: tuple = WINDOW_544) -> tuple:
    """Per market settling inside ``window``: the decision rows [(H, bid, ask, p_svi, p_cubic)] at candle hours with a valid
    book, at least one hour before the close and with a p_RN (``p_rn(H, K, t_res)`` -> {'svi', 'cubic'} or None). Also the
    counts of candle hours dropped for each reason."""
    table, cnt = {}, Counter()
    for tk, m in markets.items():
        if not (window[0] <= m["close_s"] < window[1]):
            continue
        cnt["markets_in_window"] += 1
        cs = candles.get(tk)
        if not cs:
            continue
        cnt["markets_with_candles"] += 1
        rows = []
        for H, b, a in cs:
            if H * HOUR > m["close_s"] - HOUR:
                cnt["hours_within_1h_of_close_or_after"] += 1
                continue
            cnt["candle_hours"] += 1
            if not valid_book(b, a):
                cnt["invalid_book"] += 1
                continue
            r = p_rn(int(H), m["strike"], m["close_s"])
            if r is None:
                cnt["no_p_rn"] += 1
                continue
            rows.append((int(H), b, a, float(r["svi"]), float(r["cubic"])))
        cnt["decision_hours"] += len(rows)
        if rows:
            table[tk] = rows
    return table, cnt


def kxbtcd_trades(markets: dict, table: dict, thr: float = 5.0, kind: str = "svi", mode: str = "first", haircut: float = 0.01,
                  fee_fn: Callable = kalshi_fee_6dp) -> list:
    """Entries under one cell: at a decision row, buy YES at the ask when p_RN - ask > (thr + 1) points, buy NO at 1 - bid when
    bid - p_RN > (thr + 1) points; held to settlement. net = payoff - price - fee - haircut (dollars per contract). mode
    'first': the first qualifying hour per market; 'any': every qualifying hour (one contract each)."""
    col = 3 if kind == "svi" else 4
    edge_min = (thr + 1.0) / 100.0
    out = []
    for tk, rows in table.items():
        m = markets[tk]
        for row in rows:
            H, b, a, p = row[0], row[1], row[2], row[col]
            if p - a > edge_min + 1e-12:
                side, price, payoff, edge = "yes", a, float(m["result"]), p - a
            elif b - p > edge_min + 1e-12:
                side, price, payoff, edge = "no", 1.0 - b, 1.0 - float(m["result"]), b - p
            else:
                continue
            fee = fee_fn(price)
            out.append({"ticker": tk, "event": m["event"], "hour": int(H), "side": side, "price": float(price), "p_rn": float(p),
                        "edge": float(edge), "fee": float(fee), "payoff": float(payoff), "net": float(payoff - price - fee - haircut),
                        "htc": int((m["close_s"] - H * HOUR) // HOUR), "year": datetime.fromtimestamp(m["close_s"], UTC).year})
            if mode == "first":
                break
    return out


def _sharpe(x: np.ndarray) -> Optional[float]:
    return float(x.mean() / x.std(ddof=1)) if x.size > 2 and x.std(ddof=1) > 0 else None


def trade_stats(tr: Sequence[dict], n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Mean net P&L per contract in cents with the market-clustered studentized bootstrap (one-sided 95% lower bound =
    the lower end of the two-sided 90% interval) and the event-clustered one (reported); by settlement year, hours to close
    and side."""
    if not tr:
        return {"n": 0, "markets": 0, "events": 0, "mean": None, "lower95_one_sided": None, "ci90": [None, None], "p": None,
                "event_clustered": None, "by_year": {}, "by_htc": {}, "by_side": {}, "sharpe_per_contract": None}
    x = np.array([t["net"] for t in tr]) * 100.0
    cs = cluster_stud(x, [t["ticker"] for t in tr], n_boot, seed)
    ce = cluster_stud(x, [t["event"] for t in tr], n_boot, seed)
    yrs = np.array([t["year"] for t in tr]); htc = np.array([t["htc"] for t in tr]); side = np.array([t["side"] for t in tr])
    by_year = {str(y): {"n": int((yrs == y).sum()), "mean": float(x[yrs == y].mean())} for y in sorted(set(yrs.tolist()))}
    by_htc = {lab: {"n": int(((htc >= lo) & (htc <= hi)).sum()), "mean": float(x[(htc >= lo) & (htc <= hi)].mean())}
              for lab, lo, hi in HTC_BUCKETS if ((htc >= lo) & (htc <= hi)).any()}
    by_side = {s: {"n": int((side == s).sum()), "mean": float(x[side == s].mean())} for s in ("yes", "no") if (side == s).any()}
    return {"n": int(x.size), "markets": len({t["ticker"] for t in tr}), "events": len({t["event"] for t in tr}), "mean": cs["est"],
            "lower95_one_sided": cs["ci90"][0], "ci90": cs["ci90"], "ci95": cs["ci"], "p": cs.get("p"),
            "event_clustered": {"lower95_one_sided": ce["ci90"][0], "ci90": ce["ci90"], "clusters": ce.get("clusters")},
            "by_year": by_year, "by_htc": by_htc, "by_side": by_side, "sharpe_per_contract": _sharpe(x),
            "mean_price": float(np.mean([t["price"] for t in tr])), "mean_edge_points": float(np.mean([t["edge"] for t in tr]) * 100),
            "mean_fee_cents": float(np.mean([t["fee"] for t in tr]) * 100), "win_rate": float(np.mean([t["payoff"] for t in tr]))}


def dsr_over_cells(x_primary: Sequence[float], cell_sharpes: Sequence[Optional[float]], n_trials: int = 8) -> Optional[float]:
    """DSR of the primary cell's per-contract P&L against the best of ``n_trials`` cells: the variance of the cells'
    per-contract Sharpes, floored at the iid-null variance 1 / (T - 1) (empty cells still count as trials)."""
    x = np.asarray(x_primary, float)
    if x.size < 10 or x.std(ddof=1) == 0:
        return None
    srs = [s for s in cell_sharpes if s is not None and math.isfinite(s)]
    var = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    var = max(var, 1.0 / max(1, x.size - 1))
    try:
        return float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=var))
    except Exception:
        return None


def t544_cells(markets: dict, table: dict, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """The declared 8 cells (threshold 5 / 10 x SVI / cubic x first / any qualifying hour): trades and statistics."""
    cells = {}
    for thr, kind, mode in CELLS_544:
        tr = kxbtcd_trades(markets, table, thr, kind, mode)
        cells[f"thr{int(thr)}_{kind}_{mode}"] = {"trades": tr, "stats": trade_stats(tr, n_boot if mode == "first" else min(n_boot, 500), seed)}
    return cells


def t544_criteria(cells: dict, min_n: int = 300) -> tuple:
    """Criteria rows (name, ok, decisive) of T-544's pass on the primary cells (threshold 5, first qualifying hour) and n."""
    prim = {k: cells[f"thr5_{k}_first"]["stats"] for k in ("svi", "cubic")}
    crit = []
    for k in ("svi", "cubic"):
        r = prim[k]
        lb = r["lower95_one_sided"]
        crit.append((f"{k.upper()} fit: one-sided 95% lower bound of the mean net P&L per contract {_s(lb)} cents > 0 (mean {_s(r['mean'])} over "
                     f"{r['n']} contracts, market-clustered studentized bootstrap)", None if lb is None else bool(lb > 0),
                     bool(r["ci90"][1] is not None and r["ci90"][1] < 0)))
    signs = []
    for k in ("svi", "cubic"):
        a, b = (prim[k]["by_year"].get("2025") or {}).get("mean"), (prim[k]["by_year"].get("2026") or {}).get("mean")
        signs.append(None if a is None or b is None else bool((a > 0) == (b > 0)))
    yr_txt = "; ".join(f"{k} 2025 {_s((prim[k]['by_year'].get('2025') or {}).get('mean'))} ({(prim[k]['by_year'].get('2025') or {}).get('n', 0)}) / 2026 "
                       f"{_s((prim[k]['by_year'].get('2026') or {}).get('mean'))} ({(prim[k]['by_year'].get('2026') or {}).get('n', 0)})" for k in ("svi", "cubic"))
    crit.append(("same sign of the mean net P&L in 2025 and 2026 under both fits: " + yr_txt,
                 None if any(s is None for s in signs) else all(signs), False))
    sharpes = [c["stats"]["sharpe_per_contract"] for c in cells.values()]
    dsr = {k: dsr_over_cells([t["net"] for t in cells[f"thr5_{k}_first"]["trades"]], sharpes, 8) for k in ("svi", "cubic")}
    crit.append((f"DSR >= 0.95 over the declared 8 cells: SVI {_f(dsr['svi'])}, cubic {_f(dsr['cubic'])}",
                 None if any(v is None for v in dsr.values()) else all(v >= 0.95 for v in dsr.values()), False))
    n = min(prim["svi"]["n"], prim["cubic"]["n"])
    return crit, n, dsr


def settlement_basis(markets: dict, last_idx: dict, window: tuple = WINDOW_544) -> dict:
    """BRTI-vs-Deribit-index basis at settlement, per close time: ln(expiration_value / index of the latest Deribit trade in
    the hour before the close), in %. Reported, never applied (trial.controls)."""
    by_close = {}
    for m in markets.values():
        if window[0] <= m["close_s"] < window[1] and m.get("expiration_value"):
            by_close.setdefault(m["close_s"], m["expiration_value"])
    vals = []
    for c, ev in by_close.items():
        li = last_idx.get(c // HOUR - 1)
        if li is not None and li[1] and li[1] > 0 and ev > 0:
            vals.append(100.0 * math.log(ev / li[1]))
    if not vals:
        return {"n_closes": len(by_close), "n_measured": 0, "median_pct": None}
    a = np.array(vals)
    return {"n_closes": len(by_close), "n_measured": int(a.size), "median_pct": float(np.median(a)), "mean_pct": float(a.mean()),
            "iqr_pct": [float(np.percentile(a, 25)), float(np.percentile(a, 75))], "p95_abs_pct": float(np.percentile(np.abs(a), 95))}


def _t544_from_tables(markets: dict, table: dict, cnt: Counter, min_n: int = 300, n_boot: int = N_BOOT, seed: int = SEED, extra: Optional[dict] = None):
    cells = t544_cells(markets, table, n_boot, seed)
    crit, n, dsr = t544_criteria(cells, min_n)
    verdict, why = _decide(crit, n, min_n, "contracts")
    prim = {k: cells[f"thr5_{k}_first"]["stats"] for k in ("svi", "cubic")}
    no_hc = {k: (prim[k]["mean"] + 1.0 if prim[k]["mean"] is not None else None) for k in ("svi", "cubic")}
    cent = {}
    for k in ("svi", "cubic"):
        tr = kxbtcd_trades(markets, table, 5.0, k, "first", fee_fn=kalshi_fee_cent)
        cent[k] = float(np.mean([t["net"] for t in tr]) * 100) if tr else None
    cell_sum = {name: {kk: c["stats"].get(kk) for kk in ("n", "markets", "mean", "lower95_one_sided", "sharpe_per_contract")} for name, c in cells.items()}
    extra = extra or {}
    sel_txt = (f"{cnt.get('markets_in_window', 0)} settled KXBTCD 'above' markets closing 2025-01..2026-10, {cnt.get('markets_with_candles', 0)} with hourly "
               f"candles (Kalshi archives candles for the 4 most-traded strikes per event only), {len(table)} with a decision hour; "
               f"{cnt.get('candle_hours', 0)} candle hours at least 1 h before the close, {cnt.get('invalid_book', 0)} without a valid two-sided book "
               f"(spread <= 10 cents), {cnt.get('no_p_rn', 0)} without a Deribit p_RN (sparse smile or strike outside the traded range), "
               f"{cnt.get('decision_hours', 0)} decision hours")
    def _cell_txt(k):
        r = prim[k]
        return (f"{k.upper()} {r['n']} contracts on {r['events']} events, mean {_s(r['mean'])} cents (one-sided 95% lower {_s(r['lower95_one_sided'])}; "
                f"event-clustered lower {_s((r['event_clustered'] or {}).get('lower95_one_sided'))}), mean price {_f(r.get('mean_price'))}, mean edge "
                f"{_f(r.get('mean_edge_points'), 1)} points, mean fee {_f(r.get('mean_fee_cents'), 2)} cents, sides {json_safe_counts(r['by_side'])}, by hours to "
                f"close {json_safe_counts(r['by_htc'])}")
    other = "; ".join(f"{nm} n {c['n']} mean {_s(c['mean'])}" for nm, c in cell_sum.items() if not nm.startswith("thr5_") or nm.endswith("_any"))
    reason = (f"{sel_txt}. {extra.get('deribit_txt', '')}Rule: buy YES at the ask when p_RN - ask > 5 + 1 points, NO at 1 - bid when bid - p_RN > 5 + 1, "
              f"first qualifying hour per market, held to settlement; net = payoff - price - 0.07 P(1-P) (ceil 6 dp) - 1-point haircut. "
              f"PRIMARY: {_cell_txt('svi')}; {_cell_txt('cubic')}. Without the P&L haircut: SVI {_s(no_hc['svi'])}, cubic {_s(no_hc['cubic'])}; "
              f"per-order cent fee rounding: SVI {_s(cent['svi'])}, cubic {_s(cent['cubic'])}. Other cells: {other}. "
              f"{extra.get('basis_txt', '')}— {why}")
    stat = {"n_contracts": n, "primary": prim, "cells": cell_sum, "dsr_8": dsr, "selection": dict(cnt), "no_pnl_haircut_mean_cents": no_hc,
            "cent_fee_rounding_mean_cents": cent, "criteria": [(c[0], c[1]) for c in crit], "rule10": "signal-driven first qualifying hour: no grid phase"}
    stat.update({k: v for k, v in extra.items() if not k.endswith("_txt")})
    return _clean(stat), int(n), verdict, reason


def json_safe_counts(d: dict) -> str:
    return "{" + ", ".join(f"{k}: {v.get('n')} @ {_s(v.get('mean'))}" for k, v in d.items()) + "}"


def b7_pm_kalshi_vs_deribit_digital(archive, min_n: int = 300, n_boot: int = N_BOOT, seed: int = SEED):
    """T-544: Kalshi KXBTCD against T-337's Deribit risk-neutral digital, first qualifying hour, held to settlement."""
    miss = _missing(archive, [HBTC_B], [KS_BTCD, KH_BTCD, DRB])
    if miss:
        return miss
    markets: dict = {}
    for name in _names(archive, KS_BTCD):
        markets.update(kxbtcd_markets(archive.load(name)))
    candle_rows = (r for name in _names(archive, KH_BTCD) for r in archive.load(name))
    candles = kxbtcd_candles(candle_rows)
    months = [n[len(DRB):] for n in _names(archive, DRB) if n[len(DRB):] >= DERIBIT_FROM]
    groups, expiry_ts, n_trades, last_idx = _deribit_groups(archive, months)
    spot = _hourly_spot(archive, HBTC_B)
    book = SmileBook(groups, expiry_ts, forward=spot, last_idx=last_idx)
    table, cnt = prn_table(markets, candles, book.p_rn)
    basis = settlement_basis(markets, last_idx)
    src = dict(book.fwd_source)
    extra = {"deribit": {"months": len(months), "first": months[0] if months else None, "last": months[-1] if months else None, "trades": n_trades,
                         "fits": book.n_fits, "sparse": book.n_sparse, "forward_sources": src, "staleness": book.staleness()},
             "settlement_basis": basis,
             "deribit_txt": (f"Deribit near-expiry trades {n_trades} in {len(months)} months ({months[0] if months else 'n/a'}..{months[-1] if months else 'n/a'}), "
                             f"{book.n_fits} (hour, expiry) smiles fitted, {book.n_sparse} sparse; forward = {HBTC_B} close of the bar ending at H "
                             f"({src.get('spot', 0)} fits), else the latest Deribit trade index ({src.get('deribit_last_trade', 0)}). "),
             "basis_txt": (f"Settlement basis ln(Kalshi expiration_value / latest Deribit index in the hour before the close): median {_s(basis.get('median_pct'), 3)}% "
                           f"over {basis.get('n_measured', 0)} of {basis.get('n_closes', 0)} closes (reported, no shift) ")}
    if not table:
        crit = [("one-sided 95% lower bound > 0 under SVI and cubic", None, False)]
        v, why = _decide(crit, 0, min_n, "contracts")
        return _clean({"selection": dict(cnt), **{k: v_ for k, v_ in extra.items() if not k.endswith('_txt')}}), 0, v, \
            f"no KXBTCD decision hour with a valid book and a Deribit p_RN ({dict(cnt)}) — {why}"
    return _t544_from_tables(markets, table, cnt, min_n, n_boot, seed, extra)


# ====================================================================================================== T-557 ==

_CAT_RULES = (("crypto", r"bitcoin|btc|ethereum|eth\b|solana|crypto|xrp|doge|token|coin\b|airdrop|fdv"),
              ("sports", r"\bvs\.?\b|win the|nba|nfl|mlb|nhl|ufc|premier league|champions league|super bowl|world cup|grand slam|open\b|f1|formula|match|game\b"),
              ("politics", r"election|president|trump|biden|harris|senate|house|governor|parliament|prime minister|nominee|primary|vote|poll|cabinet|congress"),
              ("economics", r"fed\b|fomc|interest rate|cpi|inflation|gdp|payroll|unemployment|recession|rates"),
              ("geopolitics", r"war|ceasefire|israel|ukraine|russia|china|iran|gaza|nato|invade|strike"))


def question_category(q: str) -> str:
    """Coarse category from question keywords (reported only; the Gamma rows carry no category field)."""
    s = str(q or "").lower()
    for name, pat in _CAT_RULES:
        if re.search(pat, s):
            return name
    return "other"


def t02_excluded_ids(archive) -> set:
    """Every market id T-02's harness reads: its closed-markets bundle (the cycle-2 2,100 markets) and its daily price bundle."""
    ids = set()
    for r in archive.load(LEGACY_MARKETS):
        ids.add(str((r.get("value") or {}).get("id")))
    for r in archive.load(LEGACY_DAILY):
        ids.add(str((r.get("value") or {}).get("market_id")))
    ids.discard("None")
    return ids


def cheap_yes_rows(outcomes: dict, series: dict, meta: dict, exclude: set, horizon_days: float = 7.0, hi_p: float = 0.10,
                   max_stale: float = 3 * DAY, years: tuple = (2023, 2026), anchor: str = "t02") -> tuple:
    """Bucket rows {mid, p, o, cluster, ...} for resolved markets not in ``exclude``, closing in ``years``. anchor 't02' is
    T-02's construction (cutoff = min(closedTime, endDate) - h, skipped when after endDate, price at most 3 days stale);
    anchor 'end' is the scheduled-endDate sensitivity (cutoff = endDate - h, skipped when the market had closed by then)."""
    rows, cnt = [], Counter()
    for mid, o in outcomes.items():
        if mid in exclude:
            cnt["excluded_t02"] += 1
            continue
        y = datetime.fromtimestamp(o["close_ts"], UTC).year
        if not (years[0] <= y <= years[1]):
            cnt["outside_years"] += 1
            continue
        sv = series.get(mid)
        if sv is None:
            cnt["no_daily_history"] += 1
            continue
        if anchor == "t02":
            cutoff = o["close_ts"] - horizon_days * DAY
            if o.get("end_ts") is not None and cutoff > o["end_ts"]:
                cnt["post_end_cutoff"] += 1
                continue
        else:
            if o.get("end_ts") is None:
                cnt["no_end_date"] += 1
                continue
            cutoff = o["end_ts"] - horizon_days * DAY
            if o.get("closed_ts") is not None and o["closed_ts"] <= cutoff:
                cnt["closed_before_cutoff"] += 1
                continue
        p, _t = _price_before(sv[0], sv[1], cutoff, max_stale)
        if p is None:
            cnt["no_price_at_horizon"] += 1
            continue
        cnt["priced"] += 1
        if not (p < hi_p):
            continue
        s = meta.get(mid, {})
        rows.append({"mid": mid, "p": float(min(max(p, 0.0), 1.0)), "o": int(o["outcome"]), "cluster": cluster_key(s) if s else f"market:{mid}",
                     "year": y, "category": question_category(s.get("question", o.get("question", ""))), "fee_type": str(s.get("feeType") or "none"),
                     "fees_enabled": bool(s.get("feesEnabled")), "close_ts": o["close_ts"]})
    return rows, cnt


def cheap_yes_stats(rows: Sequence[dict], spread: float = 0.01, n_boot: int = N_BOOT, seed: int = SEED, reasons: Optional[dict] = None) -> dict:
    """mean(outcome - price) with the event-clustered percentile bootstrap; YES count; the secondary net P&L per contract
    (buy YES at p + spread + the market's fee); splits by category, year, fee type and the fetcher's selection reason."""
    if not rows:
        return {"n": 0, "yes": 0, "mean": None, "ci": [None, None], "n_events": 0, "net": None}
    e = np.array([r["o"] - r["p"] for r in rows]); keys = [r["cluster"] for r in rows]
    cm = cluster_mean(e, keys, n_boot, seed)
    net = np.array([r["o"] - (r["p"] + spread) - pm_fee(min(r["p"] + spread, 1.0), r["fee_type"] if r["fee_type"] != "none" else None, r["fees_enabled"]) for r in rows])
    cn = cluster_mean(net, keys, n_boot, seed)

    def split(field):
        out = {}
        for val in sorted({str(r[field]) for r in rows}):
            idx = [i for i, r in enumerate(rows) if str(r[field]) == val]
            out[val] = {"n": len(idx), "yes": int(sum(rows[i]["o"] for i in idx)), "mean": float(e[idx].mean()), "mean_price": float(np.mean([rows[i]["p"] for i in idx]))}
        return out
    res = {"n": int(e.size), "yes": int(sum(r["o"] for r in rows)), "mean": cm["mean"], "ci": cm["ci"], "p_le0": cm["p_le0"], "n_events": cm["n_clusters"],
           "mean_price": float(np.mean([r["p"] for r in rows])), "yes_rate": float(np.mean([r["o"] for r in rows])),
           "n_price_zero": int(sum(1 for r in rows if r["p"] <= 0.0)),
           "net": {"spread": spread, "mean": cn["mean"], "ci": cn["ci"]},
           "by_category": split("category"), "by_year": split("year"), "by_fee_type": split("fee_type")}
    if reasons is not None:
        for r in rows:
            r["reason"] = reasons.get(r["mid"], "unlogged")
        res["by_selection_reason"] = split("reason")
    return res


def cheap_yes_criteria(res: dict, min_n: int = 300, min_yes: int = 20) -> list:
    lo, hi = res["ci"]
    c1 = None if lo is None else bool(lo > 0)
    return [(f"event-clustered 95% CI of mean(outcome - price) [{_s(lo, 4)}, {_s(hi, 4)}] excludes 0 on the positive side (mean {_s(res['mean'], 4)})",
             c1, bool(hi is not None and hi < 0)),
            (f"at least {min_yes} YES resolutions in the bucket ({res['yes']})", bool(res["yes"] >= min_yes), False)]


def _finish557(crit: list, n: int, min_n: int, stat: dict, text: str):
    """Rule 5 + _verdict: below min_n only decisive failures count and supported is impossible."""
    if n < min_n:
        judged = [(nm + (" [fails, not decisively, below min_n]" if ok is False and not dec else ""), None if (ok is False and not dec) else ok) for nm, ok, dec in crit]
        judged.append((f"n >= trial min_n ({n} of {min_n} markets)", None))
    else:
        judged = [(nm, ok) for nm, ok, _ in crit]
    v, why = _verdict(judged)
    stat["criteria"] = [(nm, ok) for nm, ok in judged]
    return _clean(stat), int(n), v, text + " — " + why


def b7_pm_cheap_yes_archived_panel(archive, min_n: int = 300, n_boot: int = N_BOOT, seed: int = SEED):
    """T-557: Polymarket YES < 0.10 at 7 days before the end, on archived month-panel markets absent from T-02's sample."""
    miss = _missing(archive, [LEGACY_MARKETS, LEGACY_DAILY], ["polymarket-closed-markets-", "polymarket-price-history-daily-"])
    if miss:
        return miss
    if not _bundle_names(archive, MONTH_MARKETS_RE) or not _bundle_names(archive, MONTH_DAILY_RE):
        return _missing(archive, ["polymarket-closed-markets-<YYYY-MM>", "polymarket-price-history-daily-<YYYY-MM>"])
    exclude = t02_excluded_ids(archive)
    meta, outs, series = _closed_meta(archive), _outcomes(archive), _daily_series(archive)
    reasons = (_fetch_log(archive) or {}).get("daily", {})
    rows, cnt = cheap_yes_rows(outs, series, meta, exclude)
    res = cheap_yes_stats(rows, n_boot=n_boot, seed=seed, reasons=reasons)
    rows_end, cnt_end = cheap_yes_rows(outs, series, meta, exclude, anchor="end")
    res_end = cheap_yes_stats(rows_end, n_boot=min(n_boot, 1000), seed=seed)
    n = res["n"]
    stat = {"primary": res, "counts": dict(cnt), "n_excluded_ids_t02": len(exclude), "n_resolved_with_history": len(outs),
            "sensitivity_scheduled_end_anchor": {k: res_end.get(k) for k in ("n", "yes", "mean", "ci", "n_events")}, "counts_end_anchor": dict(cnt_end),
            "construction": "T-02: close = min(closedTime, endDate); price = last daily point <= close - 7 d, <= 3 d stale, cutoff after endDate skipped"}
    if n == 0:
        crit = [("event-clustered 95% CI excludes 0 on the positive side", None, False), ("at least 20 YES resolutions", None, False)]
        return _finish557(crit, 0, min_n, stat, f"no market outside T-02's sample priced < 0.10 at 7 days ({dict(cnt)})")
    crit = cheap_yes_criteria(res, min_n)
    cats = ", ".join(f"{k} {v['n']} ({v['yes']} YES, {_s(v['mean'], 4)})" for k, v in res["by_category"].items())
    yrs = ", ".join(f"{k} {v['n']} ({v['yes']} YES, {_s(v['mean'], 4)})" for k, v in res["by_year"].items())
    sel = ", ".join(f"{k} {v['n']} ({v['yes']} YES)" for k, v in (res.get("by_selection_reason") or {}).items())
    text = (f"{len(outs)} resolved binary markets with daily history; {len(exclude)} market ids read by T-02 excluded ({cnt.get('excluded_t02', 0)} of the resolved), "
            f"{cnt.get('priced', 0)} priced at 7 d (T-02's construction; {cnt.get('post_end_cutoff', 0)} post-end cutoffs and {cnt.get('no_price_at_horizon', 0)} "
            f"without a price <= 3 d stale skipped). Bucket < 0.10: {n} markets in {res['n_events']} events, mean price {_f(res['mean_price'], 4)}, "
            f"YES rate {_f(res['yes_rate'], 4)} ({res['yes']} YES), mean(outcome - price) {_s(res['mean'], 4)} [{_s(res['ci'][0], 4)}, {_s(res['ci'][1], 4)}] "
            f"(event-clustered 95%); {res['n_price_zero']} priced at 0. Secondary net per contract after a 1-cent spread and the market's fee "
            f"{_s(res['net']['mean'], 4)} [{_s(res['net']['ci'][0], 4)}, {_s(res['net']['ci'][1], 4)}]. Categories (question keywords): {cats}; years: {yrs}; "
            f"selection reasons: {sel}. Sensitivity anchored at the scheduled endDate: {res_end['n']} markets, {res_end['yes']} YES, mean "
            f"{_s(res_end['mean'], 4)} [{_s((res_end['ci'] or [None, None])[0], 4)}, {_s((res_end['ci'] or [None, None])[1], 4)}]")
    return _finish557(crit, n, min_n, stat, text)


# ======================================================================================================= map ==

HARNESSES = {
    "b7_pm_kalshi_vs_deribit_digital": b7_pm_kalshi_vs_deribit_digital,
    "b7_pm_cheap_yes_archived_panel": b7_pm_cheap_yes_archived_panel,
}

THEORY_MAP = {
    "T-544": "b7_pm_kalshi_vs_deribit_digital",
    "T-557": "b7_pm_cheap_yes_archived_panel",
}
