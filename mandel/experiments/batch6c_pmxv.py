"""
Batch 6c, group ``pmxv``: five cross-venue and event claims on the prediction-market histories of
``mandel.data.pm_history`` (Polymarket Gamma events, CLOB hourly / daily prices, data-api hourly taker volume, Kalshi
settled markets and hourly / daily candles, the frozen ``pm-kalshi-pairs`` table), the Deribit near-expiry BTC option
trades and Cleveland Fed nowcasts of ``mandel.data.public_history``, and the Yahoo daily bundles.
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-336  Polymarket-Kalshi convergence on templated pairs (FOMC, CPI, BTC thresholds), hourly. d_t = PM composite -
           (const + Kalshi composite mid), in points, on the same UTC hour (CLOB snapshot at :00:02 = state at the hour;
           a Kalshi candle ending at the hour = the quote at the hour). Episode: a fresh crossing of |d| above 5 points
           (the previous valid hour within 3 h had |d| <= 5); halved when |d| <= |d_0| / 2 within the next 24 hours
           (>= 12 valid hours in the window, and the window must end before either leg closes). Pass: the 95% lower
           bound of the halving rate > 70% under BOTH named constructions (Wilson on episodes; event-clustered bootstrap:
           rule 11) with >= 50 episodes (min_n), AND the rate exceeds the trial's null (Gaussian random walks started at
           |d_0| with each pair's realised hourly gap volatility; event-clustered one-sided p < 0.05), AND (secondary)
           the convergence trade's mean net return per episode > 0 under BOTH constructions the trial names (rule 11):
           (a) enter at the crossing, exit at |d| < 1 point (both venues' spreads and fees again) or at resolution on the
           stored outcomes; (b) the trial's pure-arb variant: the same entry held to settlement (payoff = entry edge -
           entry fees - s x d_res, mismatched pairs at +/-100) minus the T-bill carry on $1 of locked capital until the
           later leg's close at the DTB3 rate available at the entry hour (rule 7 conversion). Kalshi legs at bid/ask
           with the 0.07 x P(1-P) taker fee each way, Polymarket legs at the assumed half-spread (median of
           ``polymarket-books-snapshot`` when archived, else 1 cent) and the Gamma per-market fee flag. When the two
           constructions disagree the secondary is undecided. The hand audit the claim names does not exist: the table is ``audited: False``
           throughout, so the audit criterion is the automated rule check on the fields the builder carried (same
           resolution source or a documented same-underlying basis, |timing gap| <= 72 h and not timing_suspect, every
           PM leg's event / market end-date mismatch <= 24 h, the strike relation re-derived from the labels and tickers),
           and only pairs passing it are used; the differently-resolved count is reported (never used to select).
  * T-409  Kalshi / Polymarket lead-lag on the same pairs (rule-mismatched pairs KEPT, as the trial says). Leader at hour
           t = the venue with the larger trailing-24 h volume (Kalshi candle contracts; Polymarket data-api taker shares,
           available at the hour end; a pair without Polymarket hourly volume cannot name a leader and is excluded).
           Signal: the leader's last-hour composite mid change |Delta| >= c (claim: 3 cents) while the follower moved
           less than half as much; buy the follower in the leader's direction at the hour, exit after the hold (claim: 1
           hour; 3 h variant exits early when |PM - Kalshi| < 1 point), Kalshi at ask / bid with the taker fee each way,
           Polymarket at the assumed half-spread and the per-market fee. Pass: >= 40 pairs with >= 200 overlapping valid
           hours and >= 300 follow trades in all (a shortfall is a data limit: undecided), out-of-sample (the second half
           of pairs by listing time; the first half is the calibration half, whose best cell is reported) mean net return
           per follow trade > 0 with the pairs-bootstrap 95% CI excluding zero under both named constructions
           (studentized pair-cluster bootstrap; cluster-robust interval), and DSR >= 0.95 over the declared 32 cells
           (c in {3, 5} x hold {1, 3} x {one-legged follow, two-legged arbitrage held to settlement with the T-bill carry
           at the DTB3 rate available at each entry hour (rule 4; the rate range is reported)} x
           category {politics, macro, sports, crypto}; the table has no sports pairs, so those 8 cells are empty and
           counted as trials). PBO over the 32 cells (CSCV on the hourly cell P&L) is reported. The pairs table was frozen
           before any price bundle of its module was stored (recipe), which is the trial's freeze.
  * T-337  Polymarket 'Bitcoin above K' markets (daily / weekly noon-ET and 5 pm-ET variants; barrier and range markets
           excluded) against Deribit-implied digital probabilities. At each hourly CLOB point t: option trades with
           timestamps in (t - 2 h, t] (strictly before the decision) give the IV observations, expiries 0-8 days out,
           per-strike mean IV; the forward at t is point in time (rule 4): the ``hourly-BTC-USD`` close of the bar
           ending at t (available at t; archived from 2024-10-16), else the index price of the latest Deribit trade
           before t; the smile is fitted in log-moneyness k = ln(K / F_t) relative to that forward (sticky strike: each
           strike keeps its traded IV), and the staleness of the two-hour mean index against F_t is reported. Two smiles
           per expiry, SVI (quasi-explicit: linear (a, d, c) for each (m, sigma) on a grid, constraints c >= 0, |d| <= c)
           and a weighted cubic in k, on total variance; total variance interpolated linearly in time between the
           bracketing expiries (flat-vol scaling when only one side exists); p_RN = N(d2) - phi(d2) sqrt(tau) dsigma/dk
           (the Breeden-Litzenberger digital under the fitted smile). Sparse hours (< 6 strikes) and strikes outside the
           traded range are skipped and counted. Fade: |gap| = |p_poly - p_RN| > 5 points with p_RN in [0.05, 0.95] -> buy NO (gap > 0) or YES
           (gap < 0) at p_poly, exit at the first hour with |gap| < 1 point or at resolution (Gamma outcome); net =
           payoff - cost - 0.07 x p(1-p) at entry and at an early exit - 1 point haircut. Pass: one-sided 95% lower bound
           of the mean net return per trade > 0 (studentized market-cluster bootstrap) under BOTH fits AND the same
           sign in 2024-2025 and 2026 (both fits); min_n 300 trades. The resolution-source basis control (Binance BTCUSDT
           vs the Deribit index) reads ``binance-1m-BTCUSDT-btc-above`` (``mandel.data.binance_klines``: Binance 1-minute
           klines around every resolution time): the basis ln(Binance close / Deribit index) is measured at each
           resolution time from the latest Deribit trade before it against the Binance close of the minute holding that
           trade, every decision hour H shifts the strike by exp(-median of the bases known by H) (point in time), the
           fades are re-run under both fits, and the criterion passes when both one-sided 95% lower bounds stay > 0;
           the Gamma outcomes are audited against the Binance close under both readings of 'the 1 minute candle for
           12:00'. When the bundle is not archived that criterion is None (rule 9) and the sensitivity to a +/-0.2%
           strike shift is reported instead.
  * T-358  SPY's two-session return into scheduled binary events against ex-ante uncertainty U = p(1-p) three sessions
           before. Frozen tagging rule (built before SPY is read): Kalshi KXCPI / KXFED / KXFEDDECISION / KXPAYROLLS
           settled markets and the PRES-2024 race; Polymarket FOMC and CPI event families (``polymarket-events-macro``)
           and the 2024 presidential winner market. Event day = the family's calendar day (FOMC decision day, BLS
           release day, election day) nearest the market's close. p = the last quote by 23:59:59 ET on the session three
           sessions before the event day (Kalshi daily candle mid, spread <= 10 points; Polymarket daily snapshot;
           PRES-2024 hourly candles). U per event = max over its contracts (a ladder's uncertainty sits at the money;
           the all-contract mean is the reported variant); events sharing a date averaged. SPY return = close(D) /
           close(D - 2 sessions) - 1 (election: exit the next session's close). Pass: OLS slope > 0 with date-clustered
           two-sided p < 0.05 (studentized date bootstrap; percentile reported), the same sign in both halves
           (2020-2022 / 2023-2026: no venue has 2020 or 2021 H1 data, so the first half runs 2021-07..2022, stated),
           and a placebo slope indistinguishable from 0 (each date's U regressed on a random non-event two-session
           window, 200 draws pooled, date-clustered p > 0.05); min_n 60 distinct dates. The six variants (Fed only,
           excluding FOMC, TLT, GLD, BTC incl. calendar days, unconditional pre-event mean) are reported with the Holm
           adjustment of the primary p (the pass names no Holm).
  * T-360  Kalshi KXCPI thresholds against the Cleveland Fed nowcast. For each CPI release R: the nowcast N labelled the
           previous weekday D-1 (available 12:00 ET on D-1); sigma = RMSE of the day-before nowcast against the print
           over PRIOR releases only (expanding from 2013-07, >= 24 prior); q(k) = 1 - Phi((k + 0.05 - N) / sigma) for the
           'above k%' threshold; the 16:00 ET candle on D-1 (forward-filled from the last earlier candle within 7 days;
           spread <= 10 points, bid > 0, ask < 1); buy YES when q - yes_ask > 0.10, else NO when (1 - q) - no_ask > 0.10
           (the claim's wording: the edge threshold is gross, the fee 0.07 x P(1-P) is charged in the P&L; the
           fee-inclusive threshold is a reported variant); settle on the Kalshi result. Statistic: mean net P&L per
           contract (cents) averaged per release first. Pass: > 0 with cluster-bootstrap p < 0.05 under BOTH named nulls (parametric:
           outcomes Bernoulli(mid) per contract, release-clustered; release-level bootstrap of realised P&L), both
           halves (2021-2023 / 2024-2026) positive, Holm over 5 variants (headline edge 10 = primary; core CPI edge 10;
           headline edge 5; headline edge 15; market-only favourite side); min_n 40 releases with a qualifying trade.
           The archived nowcast history is the current vintage (``vintage_verified`` false; the dated real-time
           snapshots start 2026-10-15), so the trial's real-time criterion is None (rule 9).

Conventions
  * Data. Every bundle through ``archive.load``; bundles a harness only probes for (book snapshots, fee flags) are
    optional. Hours are UTC hour indices (unix // 3600). Kalshi candles use either field naming (close / close_dollars,
    volume / volume_fp); inactive hours are forward-filled (a quote older than 7 days is stale and invalid); an hour
    whose quote fails the spread filter (wider than 10 points, or bid 0 / ask 1) is invalid. Liquidity (T-336, T-409):
    the CLOB serves a placeholder price for a market nobody trades (0.50 for days), so an hour is valid only when every
    Polymarket leg had taker volume in the previous 24 hours (``polymarket-volume-hourly``, available at the hour end);
    pairs whose Polymarket legs have no hourly volume data (pre-2024 markets) are excluded and counted.
  * Fees (rule 9): Kalshi 0.07 x P(1-P) per contract per taker side (library formula); Polymarket by the Gamma fee flag
    (crypto 0.07, economics 0.05, sports 0.04 x p(1-p); 0 when fees are disabled), always 0.07 for T-337 as the claim
    states; the Polymarket half-spread is assumed (no historical book).
  * Intervals (rule 6): cluster-studentized bootstraps (events / pairs / markets / releases / dates) via
    ``batch6c_pub.cluster_stud``; '95% lower bound' is one-sided (the lower end of the two-sided 90% interval).
  * Rule 5: below min_n a failing criterion counts only when its bound at the pass's confidence lies wholly on the
    wrong side. Rule 11: criteria with two named constructions pass only when both pass (``all_constructions``).
  * Rule 10: every entry here is signal- or event-driven; no grid phase is free.
Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``.
"""

from __future__ import annotations

import bisect
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import product
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments.batch6b_bw import _clean, _decide, all_constructions
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
HOUR = 3600
N_BOOT = 2000
SEED = 0

PAIRS_B = "pm-kalshi-pairs"
EV_MACRO_B = "polymarket-events-macro"
EV_BTC_B = "polymarket-events-btc-above"
BOOKS_B = "polymarket-books-snapshot"
CLE_B = "clevelandfed-inflation-nowcast"
CPI_REL_B = "macro-release-cpi"
EMP_REL_B = "macro-release-employment-situation"
FOMC_B = "fomc-meetings"
SPY_B, TLT_B, GLD_B, BTC_B = "daily-history-SPY", "daily-history-TLT", "daily-history-GLD", "daily-history-BTC-USD"
HBTC_B = "hourly-BTC-USD"                # T-337's point-in-time forward (bar start t, close, available_at = t + 1 h)
BNC_B = "binance-1m-BTCUSDT-btc-above"   # T-337's resolution source: Binance 1-minute closes around every resolution time (optional)
DTB3_B = "fred-DTB3"
KS = "kalshi-settled-markets-"
KH = "kalshi-candles-hourly-"
KD = "kalshi-candles-daily-"
PMH = "polymarket-price-history-hourly-"
PMD = "polymarket-price-history-daily-"
PMV = "polymarket-volume-hourly-"
DRB = "deribit-option-trades-near-BTC-"

KALSHI_FEE = 0.07                       # taker fee rate x P(1-P) per contract
PM_FEE_RATE = {"crypto": 0.07, "economics": 0.05, "sports": 0.04}
PM_HALF_SPREAD_DEFAULT = 0.01           # assumed Polymarket half-spread when no book snapshot is archived
SPREAD_MAX = 0.10                       # a Kalshi quote wider than 10 points (or bid 0 / ask 1) is an illiquid hour
PAIR_TIMING_MAX_H = 72.0
PAIR_END_MISMATCH_MAX_H = 24.0

PAIR_SERIES = ("KXFEDDECISION", "KXCPI", "KXCPIYOY", "KXCPICORE", "KXCPICOREYOY", "PRES", "POPVOTE")
CATEGORY = {"fomc": "macro", "cpi_mom": "macro", "cpi_yoy": "macro", "core_cpi_mom": "macro", "core_cpi_yoy": "macro",
            "btc": "crypto", "election": "politics"}
CELL_CATS = ("politics", "macro", "sports", "crypto")

_CACHE: dict = {}


# ======================================================================================================= utilities ==

def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _names(archive, prefix: str) -> list:
    """Archived bundle names with ``prefix``, sorted."""
    try:
        return sorted(e.name for e in archive.entries() if e.name.startswith(prefix))
    except Exception:
        return []


def _rows(archive, name: str) -> list:
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        cap = str(cap) if cap else None
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and str(r["available_at"]) > cap)]
    return _cached(archive, ("rows", name), load)


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


def _ci_txt(ci, nd: int = 2, unit: str = "") -> str:
    lo, hi = (ci or [None, None])[:2]
    return "CI n/a" if lo is None or hi is None else f"CI {lo:+.{nd}f}{unit} to {hi:+.{nd}f}{unit}"


def _out(stat, n, verdict, reason):
    return _clean(stat), int(n), verdict, reason


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def wilson_lower(k: int, n: int, z: float = 1.959964) -> Optional[float]:
    """Lower end of the two-sided 95% Wilson interval for k successes in n."""
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / den


def wilson_upper(k: int, n: int, z: float = 1.959964) -> Optional[float]:
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + half) / den


def holm_adjusted(pvals: Sequence[Optional[float]], index: int) -> Optional[float]:
    """Holm step-down adjusted p-value of test ``index`` among ``pvals`` (None entries count as 1)."""
    ps = [1.0 if p is None else float(p) for p in pvals]
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj, running = {}, 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * ps[i])
        adj[i] = min(1.0, running)
    return adj.get(index)


def kalshi_quote(candle: dict) -> tuple:
    """(bid, ask, volume) of a Kalshi candle under either field naming (historical: close / volume; live: close_dollars /
    volume_fp)."""
    def close(side):
        d = candle.get(side) or {}
        return _num(d.get("close", d.get("close_dollars")))
    v = _num(candle.get("volume", candle.get("volume_fp"))) or 0.0
    return close("yes_bid"), close("yes_ask"), v


def _quote_ok(bid, ask) -> bool:
    return bid is not None and ask is not None and ask - bid <= SPREAD_MAX and not (bid <= 0.0 and ask >= 1.0)


def pm_fee_rate(market: Optional[dict]) -> float:
    """Polymarket taker-fee coefficient of a Gamma market row: rate x p(1-p); 0 when fees are disabled or unknown."""
    if not market or not market.get("feesEnabled"):
        return 0.0
    ft = str(market.get("feeType") or "")
    for k, r in PM_FEE_RATE.items():
        if k in ft:
            return r
    return PM_FEE_RATE["economics"]


def _bill_curve(archive) -> Optional[tuple]:
    """(available_at unix array, continuous T-bill rate array) from ``fred-DTB3`` sorted by available_at: the discount
    yield converted per rule 7 (-ln(1 - d x 91/360) / (91/365)). None when the bundle is not archived."""
    if not _has(archive, DTB3_B):
        return None

    def load():
        pts = []
        for r in _rows(archive, DTB3_B):
            v = _num((r.get("value") or {}).get("value"))
            ts = _ts(r.get("available_at"))
            if v is None or ts is None:
                continue
            d = v / 100.0
            pts.append((ts, -math.log(max(1 - d * 91 / 360, 1e-9)) / (91 / 365)))
        pts.sort()
        return np.array([p[0] for p in pts], dtype=np.int64), np.array([p[1] for p in pts], dtype=float)
    return _cached(archive, ("bill_curve",), load)


def bill_rate_at(curve: Optional[tuple], ts: int) -> Optional[float]:
    """The continuous T-bill rate known at unix ``ts``: the latest DTB3 observation with available_at <= ts (rule 4);
    None without a curve or before its first observation."""
    if curve is None or curve[0].size == 0:
        return None
    j = int(np.searchsorted(curve[0], int(ts), side="right")) - 1
    return float(curve[1][j]) if j >= 0 else None


def _rate_of(bill, ts: int) -> Optional[float]:
    """A carry rate given as a constant or as a callable of the entry time (point in time)."""
    if callable(bill):
        return bill(int(ts))
    return None if bill is None else float(bill)


def pm_half_spread(archive) -> tuple:
    """(assumed Polymarket half-spread, source): the median best-ask minus best-bid half-spread of the YES books in
    ``polymarket-books-snapshot`` when archived (books with both sides), else the default."""
    if not _has(archive, BOOKS_B):
        return PM_HALF_SPREAD_DEFAULT, "default (no book snapshot archived)"
    hs = []
    for r in _rows(archive, BOOKS_B):
        yes = ((r.get("value") or {}).get("books") or {}).get("yes") or {}
        bids = [_num(b.get("price")) for b in yes.get("bids") or []]
        asks = [_num(a.get("price")) for a in yes.get("asks") or []]
        bids = [b for b in bids if b is not None]
        asks = [a for a in asks if a is not None]
        if bids and asks and max(bids) < min(asks):
            hs.append((min(asks) - max(bids)) / 2)
    if len(hs) < 10:
        return PM_HALF_SPREAD_DEFAULT, f"default ({len(hs)} two-sided books)"
    return float(np.median(hs)), f"median of {len(hs)} two-sided YES books in {BOOKS_B}"


# ================================================================================================= pair loading ==

def _outcome_of_market(m: dict) -> Optional[int]:
    """1 / 0 for a resolved binary Gamma market (YES won / lost), None otherwise."""
    try:
        op = json.loads(m.get("outcomePrices") or "[]") if isinstance(m.get("outcomePrices"), str) else (m.get("outcomePrices") or [])
        op = [float(x) for x in op]
    except (TypeError, ValueError):
        return None
    if len(op) < 2:
        return None
    if op[0] > 0.99 and op[1] < 0.01:
        return 1
    if op[1] > 0.99 and op[0] < 0.01:
        return 0
    return None


def _pm_markets(archive) -> dict:
    """{market_id: Gamma market row} from the two event bundles (the pairs' and T-337's Polymarket legs)."""
    def load():
        out = {}
        for b in (EV_MACRO_B, EV_BTC_B):
            if not _has(archive, b):
                continue
            for r in _rows(archive, b):
                ev = r.get("value") or {}
                for m in ev.get("markets") or []:
                    mm = dict(m)
                    mm["_event_slug"] = ev.get("slug")
                    mm["_event_end"] = ev.get("endDate")
                    mm["_event_description"] = ev.get("description")
                    out[str(m.get("id"))] = mm
        return out
    return _cached(archive, ("pm_markets",), load)


def _kalshi_results(archive, series: Sequence[str]) -> dict:
    """{ticker: 1 / 0} from the settled-market bundles of ``series`` (KXBTCD months included when asked for 'KXBTCD')."""
    def load():
        out = {}
        names = []
        for s in series:
            if s == "KXBTCD":
                names += _names(archive, KS + "KXBTCD-")
            elif _has(archive, KS + s):
                names.append(KS + s)
        for n in names:
            for r in _rows(archive, n):
                v = r.get("value") or {}
                res = str(v.get("result") or "").lower()
                if res in ("yes", "no") and v.get("ticker"):
                    out[v["ticker"]] = 1 if res == "yes" else 0
        return out
    return _cached(archive, ("kalshi_results", tuple(series)), load)


def _pm_hourly(archive) -> dict:
    """{token: (hours int array, p float array)} from every polymarket-price-history-hourly-<M> bundle (hour = t // 3600:
    the CLOB snapshot at :00:02-:00:07 is the state at the hour; one point per token-hour, the latest kept)."""
    def load():
        acc_h, acc_p = defaultdict(list), defaultdict(list)
        for n in _names(archive, PMH):
            for r in archive.load(n):
                v = r["value"]
                p = _num(v.get("p"))
                t = _num(v.get("t"))
                if p is None or t is None:
                    continue
                acc_h[v["token"]].append(int(t) // HOUR)
                acc_p[v["token"]].append(p)
        out = {}
        for tok in acc_h:
            hs = np.array(acc_h[tok], dtype=np.int64)
            ps = np.array(acc_p[tok], dtype=float)
            order = np.argsort(hs, kind="stable")
            hs, ps = hs[order], ps[order]
            last = np.r_[hs[1:] != hs[:-1], True]                # the latest point of a token-hour
            out[tok] = (hs[last], ps[last])
        return out
    return _cached(archive, ("pm_hourly",), load)


def _kalshi_hourly(archive, tickers: set, series_names: Sequence[str]) -> dict:
    """{ticker: (hours, bid, ask, volume)} for ``tickers`` from the hourly-candle bundles ``series_names``."""
    key = ("kalshi_hourly", tuple(sorted(series_names)), hash(frozenset(tickers)))

    def load():
        acc = defaultdict(dict)
        for n in series_names:
            if not _has(archive, n):
                continue
            for r in archive.load(n):
                v = r["value"]
                tk = v.get("ticker")
                if tk not in tickers:
                    continue
                c = v.get("candle") or {}
                end = _num(c.get("end_period_ts"))
                if end is None:
                    continue
                bid, ask, vol = kalshi_quote(c)
                acc[tk][int(end) // HOUR] = (bid, ask, vol)
        out = {}
        for tk, d in acc.items():
            hs = np.array(sorted(d), dtype=np.int64)
            out[tk] = (hs, np.array([d[h][0] if d[h][0] is not None else np.nan for h in hs]),
                       np.array([d[h][1] if d[h][1] is not None else np.nan for h in hs]),
                       np.array([d[h][2] for h in hs], dtype=float))
        return out
    return _cached(archive, key, load)


def _pm_volume_hourly(archive, market_ids: set) -> dict:
    """{market_id: {hour: shares}} from polymarket-volume-hourly-<M> (hour = t // 3600, available at the hour end)."""
    key = ("pm_volume", hash(frozenset(market_ids)))

    def load():
        out = defaultdict(dict)
        for n in _names(archive, PMV):
            for r in archive.load(n):
                v = r["value"]
                mid = str(v.get("market_id"))
                if mid in market_ids:
                    t = _num(v.get("t"))
                    if t is not None:
                        out[mid][int(t) // HOUR] = float(v.get("shares") or 0.0)
        return dict(out)
    return _cached(archive, key, load)


# ============================================================================================ pair rule checks ==

_NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _label_number(label: str) -> Optional[float]:
    m = _NUM.search(str(label or "").replace("$", ""))
    return _num(m.group(0).replace(",", "")) if m else None


def _ticker_strike(ticker: str) -> Optional[float]:
    m = re.search(r"-T(-?\d+(?:\.\d+)?)$", str(ticker or ""))
    return _num(m.group(1)) if m else None


def pair_rule_checks(pair: dict, pm_outcomes: Optional[dict] = None, k_results: Optional[dict] = None) -> dict:
    """Automated audit of one frozen pair from its listing fields (never prices): timing, end-date mismatch, resolution
    source and strike relation; ``audited`` = every check passes (a documented same-underlying basis, e.g. Binance vs
    the CF BRTI at the same timestamp, passes with ``basis_flag``). ``mismatch_resolved`` compares the stored outcomes
    through the relation (a diagnostic: it uses outcomes, so it never selects)."""
    fam = pair.get("family")
    gap = _num(pair.get("timing_gap_hours"))
    timing_ok = (gap is not None) and abs(gap) <= PAIR_TIMING_MAX_H and not bool(pair.get("timing_suspect"))
    end_ok = all(_num(l.get("end_date_mismatch_hours")) is None or abs(_num(l.get("end_date_mismatch_hours"))) <= PAIR_END_MISMATCH_MAX_H
                 for l in pair.get("pm") or [])
    note = str(pair.get("basis_note") or "").lower()
    pm_rules = str(pair.get("pm_rules") or "").lower()
    k_rules = str(pair.get("kalshi_rules") or "").lower()
    basis_flag = False
    if fam == "fomc":
        source_ok = ("federal" in pm_rules or "fomc" in pm_rules or "fed" in pm_rules) and ("federal" in k_rules or "fed" in k_rules)
    elif fam in ("cpi_mom", "cpi_yoy", "core_cpi_mom", "core_cpi_yoy"):
        source_ok = ("bureau of labor" in pm_rules or "bls" in pm_rules or "consumer price" in pm_rules) and ("cpi" in k_rules or "consumer price" in k_rules)
    elif fam == "btc":
        source_ok = ("binance" in pm_rules) and ("brti" in k_rules or "cf benchmarks" in k_rules or "bitcoin" in k_rules)
        basis_flag = source_ok and "differs" in note
    else:
        source_ok = False                               # election: AP/Fox/NBC call vs the certified result, months apart
    strike_ok = True
    if fam == "btc":
        xs = [_label_number(l.get("label")) for l in pair.get("pm") or []]
        ks = [_ticker_strike(l.get("ticker")) for l in pair.get("kalshi") or []]
        strike_ok = (len(xs) == 1 and len(ks) == 1 and xs[0] is not None and ks[0] is not None and abs(xs[0] - (ks[0] + 0.01)) < 0.005)
    elif fam in ("cpi_mom", "cpi_yoy", "core_cpi_mom", "core_cpi_yoy"):
        m = re.match(r"CPI bucket (eq|ge|le) (-?\d+(?:\.\d+)?) = (-?\d+(?:\.\d+)?) \+ (.*)$", str(pair.get("template") or ""))
        if not m:
            strike_ok = False
        else:
            op, v = m.group(1), float(m.group(2))
            want = {"eq": [round(v - 0.1, 1), round(v, 1)], "ge": [round(v - 0.1, 1)], "le": [round(v, 1)]}[op]
            got = sorted(_ticker_strike(l.get("ticker")) for l in pair.get("kalshi") or [])
            strike_ok = all(g is not None for g in got) and [round(g, 1) for g in got] == sorted(want)
            const = float(m.group(3))
            if op == "le" and const != 1.0 or op != "le" and const != 0.0:
                strike_ok = False
    elif fam == "fomc":
        strike_ok = bool(pair.get("pm")) and bool(pair.get("kalshi")) and all(l.get("label") for l in pair["pm"] + pair["kalshi"])
    audited = bool(timing_ok and end_ok and source_ok and strike_ok)
    mismatch = None
    if pm_outcomes is not None and k_results is not None:
        pm_vals = [pm_outcomes.get(str(l.get("market_id"))) for l in pair.get("pm") or []]
        k_vals = [k_results.get(l.get("ticker")) for l in pair.get("kalshi") or []]
        if all(v is not None for v in pm_vals) and all(v is not None for v in k_vals) and pm_vals and k_vals:
            lhs = sum(int(l.get("sign") or 1) * v for l, v in zip(pair["pm"], pm_vals))
            rhs = float(pair.get("const") or 0.0) + sum(int(l.get("sign") or 1) * v for l, v in zip(pair["kalshi"], k_vals))
            mismatch = abs(lhs - rhs) > 1e-9
    return {"timing_ok": timing_ok, "end_date_ok": end_ok, "source_ok": bool(source_ok), "basis_flag": bool(basis_flag),
            "strike_ok": bool(strike_ok), "audited": audited, "mismatch_resolved": mismatch}


# ============================================================================================== pair alignment ==

def align_pair(pair: dict, pm_series: dict, k_series: dict, fee_rates: Optional[dict] = None, half_spread: float = PM_HALF_SPREAD_DEFAULT,
               pm_volume: Optional[dict] = None, pm_ffill_max: int = 2, require_volume: bool = False, k_stale_max: int = 7 * 24) -> Optional[dict]:
    """Hourly alignment of one pair on the UTC hour grid between the latest leg start and the earliest leg close
    (exclusive). Returns arrays over that grid: ``P`` (PM composite), ``K`` (Kalshi composite mid), ``Kask`` / ``Kbid``
    (cost of buying / proceeds of selling the Kalshi composite), ``Pask`` / ``Pbid`` (PM composite with the assumed
    half-spread per leg), ``fee_pm`` / ``fee_k`` (taker fee of one composite trade at the hour's prices), ``valid``
    (every leg quoted and within the spread filter; with ``pm_volume`` an hour is valid only when every PM leg had taker
    volume in the previous 24 hours, so a stale CLOB placeholder price never counts; a Kalshi quote forward-filled for more
    than ``k_stale_max`` hours is invalid), ``vol_pm`` / ``vol_k`` (hourly volume; vol_pm NaN when any PM leg has no hourly
    volume data), plus ``close_hour`` (the earliest leg close: the grid end), ``last_close_hour`` (the latest leg close:
    capital locked to settlement) and ``start_hour``. None when a leg has no hourly data (or, with ``require_volume``,
    no hourly volume data)."""
    pm_legs = pair.get("pm") or []
    k_legs = pair.get("kalshi") or []
    if not pm_legs or not k_legs:
        return None
    starts, closes = [], []
    for l in pm_legs:
        if l.get("yes_token") not in pm_series:
            return None
        s, e = _ts(l.get("start")), _ts(l.get("end") or l.get("end_date"))
        if s is not None:
            starts.append(s // HOUR)
        if e is not None:
            closes.append(e // HOUR)
    for l in k_legs:
        if l.get("ticker") not in k_series:
            return None
        s, e = _ts(l.get("open_time")), _ts(l.get("close_time"))
        if s is not None:
            starts.append(s // HOUR)
        if e is not None:
            closes.append(e // HOUR)
    if not closes:
        return None
    h0 = max(starts) if starts else min(int(pm_series[l["yes_token"]][0][0]) for l in pm_legs)
    h0 = max(h0, max(int(pm_series[l["yes_token"]][0][0]) for l in pm_legs))
    h1 = min(closes)
    if h1 - h0 < 2:
        return None
    hours = np.arange(h0, h1, dtype=np.int64)
    n = hours.size
    P = np.zeros(n)
    Pask = np.zeros(n)
    Pbid = np.zeros(n)
    fee_pm = np.zeros(n)
    valid = np.ones(n, dtype=bool)
    vol_pm = np.zeros(n)
    vol_known = True
    for l in pm_legs:
        hs, ps = pm_series[l["yes_token"]]
        idx = np.searchsorted(hs, hours, side="right") - 1
        ok = idx >= 0
        age = np.where(ok, hours - hs[np.maximum(idx, 0)], 10 ** 9)
        ok &= age <= pm_ffill_max
        p = np.where(ok, ps[np.maximum(idx, 0)], np.nan)
        valid &= ok
        sign = float(l.get("sign") or 1)
        rate = (fee_rates or {}).get(str(l.get("market_id")), 0.0)
        P += sign * p
        Pask += sign * p + half_spread
        Pbid += sign * p - half_spread
        fee_pm += rate * p * (1 - p)
        if pm_volume is not None:
            vm = pm_volume.get(str(l.get("market_id")))
            if vm is None:
                vol_known = False
                if require_volume:
                    return None
            else:
                ext = np.array([vm.get(int(h), 0.0) for h in range(h0 - 24, h1)])     # hours h0-24 .. h1-1
                vol_pm += ext[24:]
                # liquidity: taker volume in the 24 hours before the hour (an hour's volume is available at its end)
                cum = np.concatenate([[0.0], np.cumsum(ext)])
                valid &= (cum[24:24 + n] - cum[:n]) > 0
    const = float(pair.get("const") or 0.0)
    K = np.full(n, const)
    Kask = np.full(n, const)
    Kbid = np.full(n, const)
    fee_k = np.zeros(n)
    vol_k = np.zeros(n)
    for l in k_legs:
        hs, bid, ask, vol = k_series[l["ticker"]]
        idx = np.searchsorted(hs, hours, side="right") - 1
        ok = idx >= 0
        j = np.maximum(idx, 0)
        ok &= (hours - hs[j]) <= k_stale_max
        b, a = np.where(ok, bid[j], np.nan), np.where(ok, ask[j], np.nan)
        qok = ok & np.isfinite(b) & np.isfinite(a) & ((a - b) <= SPREAD_MAX) & ~((b <= 0.0) & (a >= 1.0))
        valid &= qok
        sign = float(l.get("sign") or 1)
        mid = (a + b) / 2
        K += sign * mid
        if sign > 0:
            Kask += a
            Kbid += b
        else:
            Kask -= b
            Kbid -= a
        fee_k += KALSHI_FEE * mid * (1 - mid)
        exact = (hs[j] == hours) & ok
        vol_k += np.where(exact, vol[j], 0.0)
    return {"pair_id": pair.get("pair_id"), "family": pair.get("family"), "category": CATEGORY.get(pair.get("family"), "other"),
            "event": f"{pair.get('family')}:{pair.get('key')}", "hours": hours, "P": P, "K": K, "Kask": Kask, "Kbid": Kbid,
            "Pask": Pask, "Pbid": Pbid, "fee_pm": fee_pm, "fee_k": fee_k, "valid": valid,
            "vol_pm": vol_pm if vol_known else np.full(n, np.nan), "vol_k": vol_k, "close_hour": int(h1), "last_close_hour": int(max(closes)),
            "start_hour": int(h0), "n_pm_legs": len(pm_legs), "n_k_legs": len(k_legs)}


# ====================================================================================================== T-336 ==

def episodes_halving(hours: np.ndarray, d: np.ndarray, valid: np.ndarray, thr: float = 5.0, horizon: int = 24,
                     min_valid: int = 12, fresh_within: int = 3) -> list:
    """Gap episodes on one pair's hourly grid (``d`` in points). An episode starts at a fresh crossing of |d| > thr (the
    last valid hour within ``fresh_within`` hours had |d| <= thr); it is halved when some valid hour in the next
    ``horizon`` hours has |d| <= |d_0| / 2. Windows with fewer than ``min_valid`` valid hours, or running past the grid
    (the earlier leg close), are truncated and not counted. Returns [{start, d0, halved, hours_to_half, exit_idx}]."""
    n = len(d)
    out = []
    i = 0
    last_ok = None                                   # index of the last valid hour with |d| <= thr
    while i < n:
        if not valid[i] or not np.isfinite(d[i]):
            i += 1
            continue
        if abs(d[i]) <= thr:
            last_ok = i
            i += 1
            continue
        fresh = last_ok is not None and (i - last_ok) <= fresh_within
        if not fresh:
            i += 1
            continue
        if i + horizon >= n:
            out.append({"start": int(hours[i]), "idx": i, "d0": float(d[i]), "halved": None, "truncated": True})
            break
        win = slice(i + 1, i + horizon + 1)
        w_ok = valid[win] & np.isfinite(d[win])
        if int(w_ok.sum()) < min_valid:
            out.append({"start": int(hours[i]), "idx": i, "d0": float(d[i]), "halved": None, "truncated": True, "sparse": True})
            i += horizon + 1
            last_ok = None
            continue
        absd = np.where(w_ok, np.abs(d[win]), np.inf)
        hit = np.flatnonzero(absd <= abs(d[i]) / 2)
        halved = hit.size > 0
        out.append({"start": int(hours[i]), "idx": i, "d0": float(d[i]), "halved": bool(halved),
                    "hours_to_half": int(hit[0] + 1) if halved else None, "truncated": False})
        i += horizon + 1
        last_ok = None
    return out


def rw_null_halving(d0: float, sigma: float, horizon: int = 24, n_sim: int = 400, rng: Optional[np.random.Generator] = None) -> float:
    """P(a Gaussian random walk from d0 with step sd sigma reaches |x| <= |d0| / 2 within ``horizon`` steps)."""
    rng = rng or np.random.default_rng(SEED)
    if sigma <= 0:
        return 0.0
    steps = rng.normal(0.0, sigma, (n_sim, horizon))
    paths = d0 + np.cumsum(steps, axis=1)
    return float(np.mean(np.min(np.abs(paths), axis=1) <= abs(d0) / 2))


def _convergence_entry(al: dict, idx: int, d: np.ndarray) -> tuple:
    """(s, entry edge in cents, entry fees in cents) of the convergence trade at grid index ``idx``: s = +1 when the PM
    composite is dear (sell PM at its bid, buy Kalshi at its ask), -1 the other way round; fees of both legs."""
    s = 1.0 if d[idx] > 0 else -1.0
    if s > 0:
        entry = 100.0 * (al["Pbid"][idx] - al["Kask"][idx])
    else:
        entry = 100.0 * (al["Kbid"][idx] - al["Pask"][idx])
    fees = 100.0 * (al["fee_pm"][idx] + al["fee_k"][idx])
    return s, float(entry), float(fees)


def convergence_pnl(al: dict, idx: int, d: np.ndarray, d_res: Optional[float], exit_thr: float = 1.0) -> Optional[dict]:
    """Construction (a), net return (cents per pair contract) of the convergence trade entered at grid index ``idx`` of
    an aligned pair: short the dear composite / long the cheap one at the hour's bid-ask and fees; exit at the first
    later valid hour with |d| < exit_thr (both venues' spreads and fees again) or hold to resolution, where the gap is
    ``d_res`` (0 for a consistently resolved pair, +/-100 for a mismatch; None = unknown: the trade is skipped). The exit
    leg pays two spreads on a position that converges with certainty at settlement; its cost is ``exit_cost``."""
    s, entry, fees = _convergence_entry(al, idx, d)
    n = len(d)
    j = idx + 1
    while j < n:
        if al["valid"][j] and np.isfinite(d[j]) and abs(d[j]) < exit_thr:
            if s > 0:
                close = 100.0 * (al["Pask"][j] - al["Kbid"][j])
            else:
                close = 100.0 * (al["Kask"][j] - al["Pbid"][j])
            exit_fees = 100.0 * (al["fee_pm"][j] + al["fee_k"][j])
            return {"net": entry - close - fees - exit_fees, "exit": "gap<1", "hours_held": j - idx, "entry_edge": entry,
                    "entry_fees": fees, "exit_cost": float(close + exit_fees)}
        j += 1
    if d_res is None:
        return None
    return {"net": entry - s * d_res - fees, "exit": "resolution", "hours_held": n - idx, "entry_edge": entry, "entry_fees": fees,
            "exit_cost": float(s * d_res)}


def convergence_pnl_hold(al: dict, idx: int, d: np.ndarray, d_res: Optional[float], bill_rate: Optional[float] = 0.0) -> Optional[dict]:
    """Construction (b), the trial's pure-arb variant: the convergence trade entered at grid index ``idx`` (same legs,
    bid/ask and entry fees as ``convergence_pnl``) held to settlement, where the gap is ``d_res`` (0 for a consistently
    resolved pair, +/-100 for a mismatch; None = unknown: the trade is skipped), minus the T-bill carry on $1 of capital
    locked until the later leg's close at ``bill_rate`` (continuous, the rate known at the entry; None = unknown: the
    trade is skipped). Nothing is paid to exit: the position converges with certainty at settlement."""
    if d_res is None or bill_rate is None:
        return None
    s, entry, fees = _convergence_entry(al, idx, d)
    lock_h = max(int(al.get("last_close_hour", al["close_hour"])) - int(al["hours"][idx]), 1)
    carry = 100.0 * float(bill_rate) * (lock_h / 24.0) / 365.0
    gross = entry - s * d_res - fees
    return {"net": float(gross - carry), "gross": float(gross), "carry": float(carry), "exit": "settlement", "hours_held": lock_h,
            "mismatch": abs(d_res) > 1e-9, "bill_rate": float(bill_rate), "entry_edge": entry, "entry_fees": fees}


def _event_boot(values: np.ndarray, labels: Sequence, fn, n_boot: int, seed: int = SEED) -> np.ndarray:
    """Cluster bootstrap of ``fn(values_resampled)`` resampling whole clusters (events)."""
    keys = sorted(set(labels))
    groups = {k: np.flatnonzero(np.array([lb == k for lb in labels])) for k in keys}
    rng = np.random.default_rng(seed)
    G = len(keys)
    out = np.empty(n_boot)
    arr = [groups[k] for k in keys]
    for b in range(n_boot):
        pick = rng.integers(0, G, G)
        idx = np.concatenate([arr[i] for i in pick]) if G else np.array([], dtype=int)
        out[b] = fn(values[idx]) if idx.size else np.nan
    return out


def halving_test(episodes: list, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Halving rate with the Wilson 95% interval, the event-clustered bootstrap interval, the matched random-walk null
    rate and the clustered one-sided p (H0: observed rate <= null rate)."""
    ep = [e for e in episodes if e.get("halved") is not None]
    n = len(ep)
    out = {"n": n, "n_truncated": sum(1 for e in episodes if e.get("halved") is None)}
    if n == 0:
        return out
    h = np.array([1.0 if e["halved"] else 0.0 for e in ep])
    q = np.array([e.get("null_p", np.nan) for e in ep], dtype=float)
    labels = [e["event"] for e in ep]
    k = int(h.sum())
    out.update(rate=k / n, k=k, wilson_lower=wilson_lower(k, n), wilson_upper=wilson_upper(k, n))
    if len(set(labels)) >= 4:
        boots = _event_boot(h, labels, lambda x: x.mean(), n_boot, seed)
        out["cluster_lower"], out["cluster_upper"] = float(np.nanquantile(boots, 0.025)), float(np.nanquantile(boots, 0.975))
        mask = np.isfinite(q)
        out["n_with_null"] = int(mask.sum())
        if mask.sum() >= 10 and len({l for l, m in zip(labels, mask) if m}) >= 4:
            diff = (h - q)[mask]
            lab_m = [l for l, m in zip(labels, mask) if m]
            out["null_rate"] = float(q[mask].mean())
            out["rate_with_null"] = float(h[mask].mean())
            db = _event_boot(diff, lab_m, lambda x: x.mean(), n_boot, seed + 1)
            out["diff"] = float(diff.mean())
            out["diff_ci"] = [float(np.nanquantile(db, 0.025)), float(np.nanquantile(db, 0.975))]
            out["diff_ci90"] = [float(np.nanquantile(db, 0.05)), float(np.nanquantile(db, 0.95))]
            out["p_vs_null"] = float((np.sum(db <= 0) + 1) / (n_boot + 1))
    out["clusters"] = len(set(labels))
    return out


def _pairs_universe(archive, half_spread: float) -> dict:
    """Pairs, their rule checks, outcomes and aligned hourly series (shared by T-336 and T-409). A pair is aligned only
    when every leg has hourly prices and every Polymarket leg has hourly taker volume (the liquidity filter)."""
    def load():
        pairs = [r["value"] for r in _rows(archive, PAIRS_B)]
        markets = _pm_markets(archive)
        pm_out = {mid: _outcome_of_market(m) for mid, m in markets.items()}
        fee_rates = {mid: pm_fee_rate(m) for mid, m in markets.items()}
        k_res = _kalshi_results(archive, PAIR_SERIES + ("KXBTCD",))
        checks = {p["pair_id"]: pair_rule_checks(p, pm_out, k_res) for p in pairs}
        pm_series = _pm_hourly(archive)
        tickers = {l["ticker"] for p in pairs for l in p.get("kalshi") or []}
        series_names = [KH + s for s in PAIR_SERIES] + _names(archive, KH + "KXBTCD-")
        k_series = _kalshi_hourly(archive, tickers, series_names)
        pm_vol = _pm_volume_hourly(archive, {str(l["market_id"]) for p in pairs for l in p.get("pm") or []})
        aligned = {}
        no_vol = 0
        for p in pairs:
            if any(str(l.get("market_id")) not in pm_vol for l in p.get("pm") or []):
                no_vol += 1
            al = align_pair(p, pm_series, k_series, fee_rates, half_spread, pm_vol, require_volume=True)
            if al is not None:
                lhs = [pm_out.get(str(l.get("market_id"))) for l in p["pm"]]
                rhs = [k_res.get(l.get("ticker")) for l in p["kalshi"]]
                if all(v is not None for v in lhs) and all(v is not None for v in rhs):
                    al["d_res"] = 100.0 * (sum(int(l["sign"]) * v for l, v in zip(p["pm"], lhs))
                                           - float(p.get("const") or 0.0) - sum(int(l["sign"]) * v for l, v in zip(p["kalshi"], rhs)))
                else:
                    al["d_res"] = None
                al["available_at"] = None
                aligned[p["pair_id"]] = al
        avail = {}
        for r in _rows(archive, PAIRS_B):
            avail[r["value"]["pair_id"]] = r.get("available_at")
        for pid, al in aligned.items():
            al["available_at"] = avail.get(pid)
        return {"pairs": pairs, "checks": checks, "aligned": aligned, "pm_out": pm_out, "k_res": k_res,
                "coverage": {"pairs": len(pairs), "aligned": len(aligned),
                             "pm_legs": len({l["yes_token"] for p in pairs for l in p.get("pm") or []}),
                             "pm_legs_hourly": len({l["yes_token"] for p in pairs for l in p.get("pm") or [] if l.get("yes_token") in pm_series}),
                             "k_legs": len(tickers), "k_legs_hourly": len([t for t in tickers if t in k_series]),
                             "pm_legs_volume": len({str(l["market_id"]) for p in pairs for l in p.get("pm") or [] if str(l["market_id"]) in pm_vol}),
                             "pairs_without_pm_volume": no_vol,
                             "by_family": dict(Counter(p["family"] for p in pairs)),
                             "aligned_by_family": dict(Counter(al["family"] for al in aligned.values())),
                             "valid_hours_by_family": {f: int(sum(int(al["valid"].sum()) for al in aligned.values() if al["family"] == f))
                                                       for f in Counter(p["family"] for p in pairs)}}}
    return _cached(archive, ("pairs_universe", round(half_spread, 5)), load)


def coverage_gaps(pairs: Sequence[dict], checks: dict) -> dict:
    """What the frozen table is missing against the claims' universe: families present, the audit failures by reason,
    and the known builder gaps (BTC 5 pm legs live 1-3 hours; FOMC day-suffixed events; CPI months)."""
    fams = Counter(p["family"] for p in pairs)
    fails = Counter()
    for p in pairs:
        c = checks.get(p["pair_id"], {})
        for k in ("timing_ok", "end_date_ok", "source_ok", "strike_ok"):
            if not c.get(k):
                fails[f"{p['family']}:{k}"] += 1
    keys = {f: sorted({p["key"] for p in pairs if p["family"] == f}) for f in fams}
    return {"families": dict(fams), "audit_failures": dict(fails),
            "fomc_months": keys.get("fomc", []), "cpi_mom_months": keys.get("cpi_mom", []),
            "btc_days": len(keys.get("btc", [])), "btc_first": (keys.get("btc") or [None])[0], "btc_last": (keys.get("btc") or [None])[-1],
            "election_keys": keys.get("election", [])}


def b6c_pmxv_cross_venue_convergence(archive):
    """T-336."""
    miss = _missing(archive, [PAIRS_B, EV_MACRO_B, EV_BTC_B])
    if miss:
        return miss
    hs, hs_src = pm_half_spread(archive)
    U = _pairs_universe(archive, hs)
    pairs, checks, aligned = U["pairs"], U["checks"], U["aligned"]
    cov = coverage_gaps(pairs, checks)
    audited_ids = [p["pair_id"] for p in pairs if checks[p["pair_id"]]["audited"]]
    basis_ids = [p["pair_id"] for p in pairs if checks[p["pair_id"]]["audited"] and checks[p["pair_id"]]["basis_flag"]]
    mism = Counter((p["family"], checks[p["pair_id"]]["mismatch_resolved"]) for p in pairs)
    curve = _bill_curve(archive)                                        # pure-arb carry: DTB3 known at the entry hour
    rng = np.random.default_rng(SEED)
    episodes, trades, holds, hours_total, untraded = [], [], [], 0, 0
    per_family = defaultdict(lambda: {"pairs": 0, "episodes": 0, "halved": 0, "valid_hours": 0})
    for pid in audited_ids:
        al = aligned.get(pid)
        if al is None:
            continue
        d = 100.0 * (al["P"] - al["K"])
        v = al["valid"]
        pf = per_family[al["family"]]
        pf["pairs"] += 1
        pf["valid_hours"] += int(v.sum())
        hours_total += int(v.sum())
        dd = np.diff(d)
        ok = v[1:] & v[:-1] & np.isfinite(dd)
        sigma = float(np.std(dd[ok])) if ok.sum() >= 24 else None
        cvk = np.concatenate([[0.0], np.cumsum(al["vol_k"])])
        for e in episodes_halving(al["hours"], d, v):
            e["event"] = al["event"]
            e["pair_id"] = pid
            e["family"] = al["family"]
            if e.get("halved") is not None:
                e["null_p"] = rw_null_halving(e["d0"], sigma, rng=rng) if sigma is not None else np.nan
                pf["episodes"] += 1
                pf["halved"] += int(bool(e["halved"]))
                i = e["idx"]
                if cvk[i + 1] - cvk[max(0, i - 23)] <= 0:       # the Kalshi leg must have traded in the last 24 h to be hit
                    untraded += 1
                else:
                    t = convergence_pnl(al, i, d, al.get("d_res"))
                    if t is not None:
                        t.update(event=al["event"], family=al["family"])
                        trades.append(t)
                        h = convergence_pnl_hold(al, i, d, al.get("d_res"), bill_rate_at(curve, int(al["hours"][i]) * HOUR))
                        if h is not None:
                            h.update(event=al["event"], family=al["family"])
                            holds.append(h)
            episodes.append(e)
    ht = halving_test(episodes)
    n = ht.get("n", 0)
    # criteria
    crit = []
    audit_ok = True if audited_ids and any("pm_rules" in p for p in pairs) else None
    crit.append((f"pair audit: automated rule checks in lieu of the hand audit (source, |timing gap| <= {PAIR_TIMING_MAX_H:g} h, end-date "
                 f"mismatch <= {PAIR_END_MISMATCH_MAX_H:g} h, strike relation) pass on {len(audited_ids)} of {len(pairs)} pairs "
                 f"({len(pairs) - len(audited_ids)} excluded; {len(basis_ids)} kept with a documented basis)", audit_ok, False))
    wl, cl = ht.get("wilson_lower"), ht.get("cluster_lower")
    rows = [(f"Wilson 95% lower bound {_f(wl)}", None if wl is None else wl > 0.70, wl is not None and (ht.get("wilson_upper") or 1) < 0.70),
            (f"event-clustered bootstrap lower bound {_f(cl)}", None if cl is None else cl > 0.70, cl is not None and (ht.get("cluster_upper") or 1) < 0.70)]
    crit.append(all_constructions(rows, f"24-hour halving rate {_f(ht.get('rate'))} ({ht.get('k')} of {n} episodes) > 70%"))
    pv = ht.get("p_vs_null")
    crit.append((f"halving rate above the matched random-walk null: observed {_f(ht.get('rate'))} vs null {_f(ht.get('null_rate'))} "
                 f"(difference {_s(ht.get('diff'), 3)}, {_ci_txt(ht.get('diff_ci'), 3)}; event-clustered one-sided p {_f(pv)}) < 0.05",
                 None if pv is None else pv < 0.05, pv is not None and (ht.get("diff_ci90") or [0, 1])[1] < 0))
    # secondary under both named constructions (rule 11): (a) exit at |d| < 1 or resolution; (b) pure arb held to settlement
    def _construction(tr: list) -> dict:
        if not tr:
            return {"n": 0, "mean": None, "ci": [None, None], "p": None}
        x = np.array([t["net"] for t in tr])
        cs_ = cluster_stud(x, [t["event"] for t in tr], N_BOOT)
        return {"n": len(tr), "mean": cs_["est"], "ci": cs_["ci"], "ci90": cs_["ci90"], "p": cs_.get("p"), "clusters": cs_.get("clusters"),
                "by_family": {f: float(np.mean([t["net"] for t in tr if t["family"] == f])) for f in sorted({t["family"] for t in tr})}}

    ca, cb = _construction(trades), _construction(holds)
    mean_net = ca["mean"]
    exit_costs = [t["exit_cost"] for t in trades if t["exit"] == "gap<1"]
    ca.update(by_exit=dict(Counter(t["exit"] for t in trades)), exit_leg_cost_mean=float(np.mean(exit_costs)) if exit_costs else None,
              entry_edge_mean=float(np.mean([t["entry_edge"] for t in trades])) if trades else None,
              entry_fees_mean=float(np.mean([t["entry_fees"] for t in trades])) if trades else None)
    if holds:
        gross = cluster_stud(np.array([h["gross"] for h in holds]), [h["event"] for h in holds], N_BOOT)
        clean = [h for h in holds if not h["mismatch"]]
        ex_mm = cluster_stud(np.array([h["net"] for h in clean]), [h["event"] for h in clean], N_BOOT) if clean else {"est": None, "ci": [None, None]}
        rates = [h["bill_rate"] for h in holds]
        cb.update(gross_mean=gross["est"], gross_ci=gross["ci"], excluding_mismatched={"n": len(clean), "mean": ex_mm["est"], "ci": ex_mm["ci"]},
                  mismatched_trades=sum(1 for h in holds if h["mismatch"]), carry_cents_mean=float(np.mean([h["carry"] for h in holds])),
                  bill_rate_range=[min(rates), max(rates)], days_locked_quantiles=[float(q) for q in np.quantile([h["hours_held"] / 24.0 for h in holds], [0.25, 0.5, 0.75])],
                  bill_source=f"{DTB3_B} by available_at at the entry hour (rule 7 conversion)")
    rows = []
    if trades:
        rows.append((f"(a) exit at |d| < 1 point or resolution: mean {_s(ca['mean'])} cents over {ca['n']} trades (event-clustered {_ci_txt(ca['ci'])}; "
                     f"entry edge {_s(ca['entry_edge_mean'])} - entry fees {_f(ca['entry_fees_mean'])} - exit leg {_s(ca['exit_leg_cost_mean'])} on "
                     f"{len(exit_costs)} gap<1 exits, which pays both venues' spreads and fees again on a position that converges with certainty at "
                     f"settlement; {ca['by_exit'].get('resolution', 0)} held to resolution)", ca["mean"] > 0, (ca["ci"][1] is not None) and ca["ci"][1] < 0))
    else:
        rows.append(("(a) exit at |d| < 1 point or resolution: no episode could be traded", None, False))
    if holds:
        rows.append((f"(b) pure-arb variant held to settlement, capital locked at the DTB3 rate known at entry ({cb['bill_rate_range'][0] * 100:.2f}-"
                     f"{cb['bill_rate_range'][1] * 100:.2f}% continuous, median lock {cb['days_locked_quantiles'][1]:.1f} days, carry {_f(cb['carry_cents_mean'])} cents): "
                     f"mean {_s(cb['mean'])} cents over {cb['n']} trades ({_ci_txt(cb['ci'])}; gross {_s(cb['gross_mean'])}, {_ci_txt(cb['gross_ci'])}; "
                     f"excluding the {cb['mismatched_trades']} differently-resolved trades {_s(cb['excluding_mismatched']['mean'])}, "
                     f"{_ci_txt(cb['excluding_mismatched']['ci'])})", cb["mean"] > 0, (cb["ci"][1] is not None) and cb["ci"][1] < 0))
    elif trades:
        rows.append((f"(b) pure-arb variant held to settlement: " + ("no resolved outcome for the traded episodes" if curve is not None
                                                                     else f"the T-bill carry needs {DTB3_B}, which is not archived"), None, False))
    else:
        rows.append(("(b) pure-arb variant held to settlement: no episode could be traded", None, False))
    crit.append(all_constructions(rows, f"secondary: convergence-trade mean net return per episode > 0 ({untraded} episodes untradeable: no Kalshi "
                                        f"trade in the previous 24 h)"))
    verdict, why = _decide(crit, n, 50, "episodes")
    fam_txt = "; ".join(f"{f}: {v['pairs']} pairs, {v['valid_hours']} valid hours, {v['halved']}/{v['episodes']} halved"
                        for f, v in sorted(per_family.items()))
    reason = (f"pm-kalshi-pairs: {len(pairs)} templated pairs ({cov['families']}), all audited=False; automated audit passes "
              f"{len(audited_ids)} (failures {cov['audit_failures']}); differently resolved (diagnostic) "
              f"{ {f'{k[0]}': v for k, v in mism.items() if k[1] is True} }; aligned hourly on both venues: {U['coverage']['aligned']} pairs "
              f"(PM legs with hourly {U['coverage']['pm_legs_hourly']}/{U['coverage']['pm_legs']}, Kalshi legs {U['coverage']['k_legs_hourly']}/"
              f"{U['coverage']['k_legs']}; {U['coverage']['pairs_without_pm_volume']} pairs lack Polymarket hourly volume and are excluded "
              f"by the liquidity filter: an hour counts only when every PM leg traded in the previous 24 h); BTC 5 pm legs live 1-3 "
              f"hourly points (table covers {cov['btc_first']}..{cov['btc_last']}, no pre-2026-05 BTC family), so no 24-hour BTC window "
              f"exists. Episodes (fresh |d| > 5 crossings, 24 h window before "
              f"either close, >= 12 valid hours): {n} counted, {ht.get('n_truncated', 0)} truncated or sparse; per family {fam_txt}; "
              f"{n / max(hours_total / 168.0, 1e-9):.2f} episodes per overlap-week. Halving rate {_f(ht.get('rate'))}: Wilson lower "
              f"{_f(wl)}, clustered lower {_f(cl)} ({ht.get('clusters', 0)} events); random-walk null {_f(ht.get('null_rate'))}, p {_f(pv)}. "
              f"Convergence trade (Kalshi bid/ask + 0.07 P(1-P) each way, PM half-spread {hs * 100:.2f} cents [{hs_src}] + Gamma fee flag): "
              f"(a) exit at |d| < 1 or resolution mean net {_s(mean_net)} cents per episode (the exit leg pays both venues' spreads and fees "
              f"again on a position that converges with certainty at settlement); (b) the trial's pure-arb variant held to settlement net of "
              f"the point-in-time DTB3 carry {_s(cb.get('mean'))} cents — {why}")
    stat = {"n_episodes": n, "halving": ht, "per_family": dict(per_family), "n_pairs": len(pairs), "n_audited": len(audited_ids),
            "n_basis_flagged": len(basis_ids), "coverage": U["coverage"], "table_gaps": cov,
            "mismatch_resolved": {f"{k[0]}:{k[1]}": v for k, v in mism.items()},
            "convergence_trade": {"n": len(trades), "untradeable_untraded_kalshi": untraded, "mean_net_cents": mean_net, "ci": ca.get("ci"), "p": ca.get("p"),
                                  "by_exit": ca.get("by_exit"), "by_family": ca.get("by_family"),
                                  "exit_rule": ca, "hold_to_settlement": cb,
                                  "constructions_agree": None if ca["mean"] is None or cb["mean"] is None else (ca["mean"] > 0) == (cb["mean"] > 0)},
            "costs": {"kalshi_fee": KALSHI_FEE, "pm_half_spread": hs, "pm_half_spread_source": hs_src, "pm_fee_rates": PM_FEE_RATE,
                      "bill_rate_range": cb.get("bill_rate_range")},
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "episodes are signal-driven (gap crossings): no grid phase"}
    return _out(stat, n, verdict, reason)


# ====================================================================================================== T-409 ==

def follow_trades(al: dict, c_cents: float = 3.0, hold: int = 1, close_thr: float = 1.0) -> list:
    """One-legged follow trades on an aligned pair: at hour t (t and t-1 valid) the leader is the venue with the larger
    trailing-24 h volume; when |Delta leader| >= c and |Delta follower| < |Delta leader| / 2, buy the follower in the
    leader's direction at t (ask / bid of the follower composite), exit at t + hold (or the first hour in between where
    |P - K| < close_thr points when hold > 1). One position per pair at a time. Returns [{hour, net, leader, dir}]."""
    hours, P, K, v = al["hours"], al["P"], al["K"], al["valid"]
    n = len(hours)
    vp, vk = al["vol_pm"], al["vol_k"]
    if not np.isfinite(vp).all():
        return []
    cvp, cvk = np.concatenate([[0.0], np.cumsum(vp)]), np.concatenate([[0.0], np.cumsum(vk)])
    out = []
    t = 1
    while t < n - hold:
        if not (v[t] and v[t - 1]):
            t += 1
            continue
        # Kalshi: the 24 candles ending at t-23..t are known at t; Polymarket: an hour's taker volume is available at its
        # end, so the 24 hours t-24..t-1 are known at t (rule 4)
        tv_pm, tv_k = cvp[t] - cvp[max(0, t - 24)], cvk[t + 1] - cvk[max(0, t - 23)]
        if tv_pm <= 0 and tv_k <= 0:
            t += 1
            continue
        leader = "pm" if tv_pm > tv_k else "kalshi"
        if (tv_k if leader == "pm" else tv_pm) <= 0:              # the follower must itself have traded in the last 24 h
            t += 1
            continue
        dL = (P[t] - P[t - 1]) if leader == "pm" else (K[t] - K[t - 1])
        dF = (K[t] - K[t - 1]) if leader == "pm" else (P[t] - P[t - 1])
        if abs(dL) * 100 < c_cents or not abs(dF) < abs(dL) / 2:
            t += 1
            continue
        s = 1.0 if dL > 0 else -1.0
        ask, bid, fee = (al["Kask"], al["Kbid"], al["fee_k"]) if leader == "pm" else (al["Pask"], al["Pbid"], al["fee_pm"])
        exit_i = None
        for j in range(t + 1, t + hold + 1):
            if not v[j]:
                continue
            if j == t + hold or abs(P[j] - K[j]) * 100 < close_thr:
                exit_i = j
                break
        if exit_i is None:
            t += 1
            continue
        if s > 0:
            net = 100.0 * (bid[exit_i] - ask[t])
        else:
            net = 100.0 * (bid[t] - ask[exit_i])
        net -= 100.0 * (fee[t] + fee[exit_i])
        out.append({"hour": int(hours[t]), "net": float(net), "leader": leader, "dir": s, "pair_id": al["pair_id"],
                    "category": al["category"], "exit_hours": exit_i - t})
        t = exit_i + 1
    return out


def arb_trades(al: dict, c_cents: float = 3.0, bill_rate=0.0) -> list:
    """Two-legged arbitrage held to settlement: at the first valid hour where buying the composite on one venue and
    selling it on the other clears both fees by more than c cents (both venues having traded in the previous 24 hours),
    enter; the payoff is the edge minus the resolution mismatch (``d_res``) and the T-bill carry on $1 of capital locked
    until the later leg's close. ``bill_rate`` is a constant continuous rate or a callable of the entry unix time (the
    DTB3 rate known at the entry hour: rule 4); the rate used is carried in the trade. One trade per pair."""
    hours, v = al["hours"], al["valid"]
    if al.get("d_res") is None or not np.isfinite(al["vol_pm"]).all():
        return []
    cvp, cvk = np.concatenate([[0.0], np.cumsum(al["vol_pm"])]), np.concatenate([[0.0], np.cumsum(al["vol_k"])])
    out = []
    for t in range(len(hours)):
        if not v[t]:
            continue
        if t < 1 or (cvp[t] - cvp[max(0, t - 24)]) <= 0 or (cvk[t + 1] - cvk[max(0, t - 23)]) <= 0:
            continue
        fees = 100.0 * (al["fee_pm"][t] + al["fee_k"][t])
        e1 = 100.0 * (al["Kbid"][t] - al["Pask"][t]) - fees          # buy PM, sell Kalshi
        e2 = 100.0 * (al["Pbid"][t] - al["Kask"][t]) - fees          # buy Kalshi, sell PM
        if max(e1, e2) <= c_cents:
            continue
        s = 1.0 if e1 >= e2 else -1.0                                 # s = +1 long PM / short Kalshi: payoff edge + d_res
        lock_h = max(int(al.get("last_close_hour", al["close_hour"])) - int(hours[t]), 1)
        rate = _rate_of(bill_rate, int(hours[t]) * HOUR)
        carry = 100.0 * (rate or 0.0) * (lock_h / 24.0) / 365.0
        net = max(e1, e2) + s * al["d_res"] - carry
        out.append({"hour": int(hours[t]), "net": float(net), "leader": "arb", "dir": s, "pair_id": al["pair_id"],
                    "category": al["category"], "exit_hours": lock_h, "bill_rate": rate, "carry": float(carry)})
        break
    return out


def _cell_name(c, h, variant, cat) -> str:
    return f"c{c:g}|h{h}|{variant}|{cat}"


def leadlag_cells(aligned: Sequence[dict], bill_rate=0.0) -> dict:
    """Trades of every declared cell: {cell: [trades]} over 2 x 2 x 2 x 4 = 32 cells (``bill_rate`` as in ``arb_trades``)."""
    cells = {_cell_name(c, h, var, cat): [] for c in (3, 5) for h in (1, 3) for var in ("follow", "arb") for cat in CELL_CATS}
    for al in aligned:
        cat = al["category"]
        if cat not in CELL_CATS:
            continue
        for c in (3, 5):
            arb = arb_trades(al, c, bill_rate)
            for h in (1, 3):
                cells[_cell_name(c, h, "follow", cat)] += follow_trades(al, c, h)
                cells[_cell_name(c, h, "arb", cat)] += list(arb)
    return cells


def _pair_test(trades: Sequence[dict]) -> dict:
    """Mean net return per trade (cents) with the studentized pairs-cluster bootstrap and the cluster-robust interval."""
    if not trades:
        return {"n": 0, "pairs": 0, "mean": None}
    x = np.array([t["net"] for t in trades])
    cs = cluster_stud(x, [t["pair_id"] for t in trades], N_BOOT)
    se = cs.get("se")
    robust = [cs["est"] - 1.959964 * se, cs["est"] + 1.959964 * se] if se else [None, None]
    return {"n": int(x.size), "pairs": cs.get("clusters"), "mean": cs["est"], "ci": cs["ci"], "ci90": cs["ci90"], "ci_pct": cs["ci_pct"],
            "robust_ci": robust, "p": cs.get("p"), "se": se}


def b6c_pmxv_leadlag(archive):
    """T-409."""
    miss = _missing(archive, [PAIRS_B, EV_MACRO_B, EV_BTC_B])
    if miss:
        return miss
    hs, hs_src = pm_half_spread(archive)
    U = _pairs_universe(archive, hs)
    pairs, checks, aligned = U["pairs"], U["checks"], U["aligned"]
    cov = coverage_gaps(pairs, checks)
    curve = _bill_curve(archive)                                      # arb carry: the DTB3 rate known at each entry hour (rule 4)
    bill = (lambda ts: bill_rate_at(curve, ts)) if curve is not None else 0.0
    # freeze check: the table's frozen_at precedes every price bundle of its module
    frozen = min((str(r.get("observed_at")) for r in _rows(archive, PAIRS_B)), default=None)
    price_b = [b for b in _names(archive, PMH) + _names(archive, KH) + _names(archive, PMV)]
    first_price = min((str(archive.get(b).created_at) for b in price_b), default=None) if price_b else None
    frozen_ok = (frozen is not None and first_price is not None and frozen < first_price and all("pm_rules" in p for p in pairs)) or None
    als = list(aligned.values())
    overlap = {al["pair_id"]: int(al["valid"].sum()) for al in als}
    with_vol = [al for al in als if np.isfinite(al["vol_pm"]).all()]
    qual = [al for al in with_vol if overlap[al["pair_id"]] >= 200]
    # claim's cell over the whole sample, then the OOS split by listing time
    claim_all = [t for al in with_vol for t in follow_trades(al, 3.0, 1)]
    order = sorted(with_vol, key=lambda al: (str(al.get("available_at") or ""), al["pair_id"]))
    half = len(order) // 2
    cal, test = order[:half], order[half:]
    test_ids = {al["pair_id"] for al in test}
    oos = [t for t in claim_all if t["pair_id"] in test_ids]
    ins = [t for t in claim_all if t["pair_id"] not in test_ids]
    t_oos, t_ins, t_all = _pair_test(oos), _pair_test(ins), _pair_test(claim_all)
    cells = leadlag_cells(with_vol, bill)
    arb_rates = sorted({t["bill_rate"] for tr in cells.values() for t in tr if t["leader"] == "arb" and t.get("bill_rate") is not None})
    arb_carry = [t["carry"] for tr in cells.values() for t in tr if t["leader"] == "arb"]
    bill_txt = (f"the point-in-time DTB3 rate at each entry ({arb_rates[0] * 100:.2f}-{arb_rates[-1] * 100:.2f}% continuous; mean carry "
                f"{np.mean(arb_carry):.2f} cents)" if arb_rates else ("the point-in-time DTB3 rate (no arb trade)" if curve is not None
                                                                      else f"0 ({DTB3_B} not archived)"))
    cell_stats = {}
    for name, tr in cells.items():
        x = np.array([t["net"] for t in tr]) if tr else np.array([])
        cell_stats[name] = {"n": int(x.size), "mean": float(x.mean()) if x.size else None,
                            "sr": float(sharpe_ratio(x)) if x.size >= 3 else None,
                            "n_oos": int(sum(1 for t in tr if t["pair_id"] in test_ids)),
                            "mean_oos": float(np.mean([t["net"] for t in tr if t["pair_id"] in test_ids])) if any(t["pair_id"] in test_ids for t in tr) else None,
                            "mean_is": float(np.mean([t["net"] for t in tr if t["pair_id"] not in test_ids])) if any(t["pair_id"] not in test_ids for t in tr) else None}
    # calibration: the best in-sample cell (>= 30 trades) and its OOS reading
    best = max(((k, v) for k, v in cell_stats.items() if v["n"] - v["n_oos"] >= 30 and v["mean_is"] is not None), key=lambda kv: kv[1]["mean_is"], default=None)
    # DSR over 32 cells on the claim-cell OOS trades
    srs = [v["sr"] for v in cell_stats.values() if v["sr"] is not None]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) > 1 else None
    dsr = None
    if len(oos) >= 10:
        try:
            dsr = float(deflated_sharpe_ratio(np.array([t["net"] for t in oos]), 32, var_trials_sr=var_sr if var_sr and var_sr > 0 else None))
        except Exception:
            dsr = None
    # PBO over the 32 cells on the hourly cell P&L
    pbo = None
    all_hours = sorted({t["hour"] for tr in cells.values() for t in tr})
    if len(all_hours) >= 64:
        hidx = {h: i for i, h in enumerate(all_hours)}
        R = np.zeros((len(all_hours), len(cells)))
        for j, (name, tr) in enumerate(cells.items()):
            for t in tr:
                R[hidx[t["hour"]], j] += t["net"]
        try:
            pbo = pbo_cscv(R, 8)
        except Exception:
            pbo = None
    n_pairs = len(qual)
    crit = [(f"pairs table frozen before any price bundle (frozen {frozen}, first price bundle {first_price}) with per-pair rule checks "
             f"(automated: {sum(1 for c in checks.values() if c['audited'])} pass, mismatched pairs kept as the trial says)", frozen_ok, False)]
    size_ok = True if (n_pairs >= 40 and len(claim_all) >= 300) else None
    crit.append((f">= 40 pairs with >= 200 overlapping valid hours ({n_pairs} of {len(with_vol)} pairs with a volume-named leader; "
                 f"{len(als)} aligned) and >= 300 follow trades in total ({len(claim_all)} at c = 3 cents, 1-hour hold)", size_ok, False))
    rows = [(f"studentized pairs bootstrap {_ci_txt(t_oos.get('ci'))}", None if t_oos.get("ci", [None])[0] is None else t_oos["ci"][0] > 0,
             t_oos.get("ci", [None, None])[1] is not None and t_oos["ci"][1] < 0),
            (f"cluster-robust {_ci_txt(t_oos.get('robust_ci'))}", None if t_oos.get("robust_ci", [None])[0] is None else t_oos["robust_ci"][0] > 0,
             t_oos.get("robust_ci", [None, None])[1] is not None and t_oos["robust_ci"][1] < 0)]
    crit.append(all_constructions(rows, f"out-of-sample (second half of {len(with_vol)} pairs by listing time: {len(test)} pairs, {t_oos.get('n', 0)} trades) "
                                        f"mean net return per follow trade {_s(t_oos.get('mean'))} cents > 0 with the 95% CI excluding zero"))
    crit.append((f"DSR {_f(dsr)} >= 0.95 over the 32 declared cells ({sum(1 for v in cell_stats.values() if v['n'] > 0)} non-empty; sports cells empty)",
                 None if dsr is None else dsr >= 0.95, False))
    verdict, why = _decide(crit, n_pairs, 40, "pairs")
    reason = (f"pm-kalshi-pairs: {len(pairs)} pairs ({cov['families']}; rule-mismatched kept: audit fails {cov['audit_failures']}); aligned "
              f"{len(als)} (every leg with hourly prices and Polymarket hourly taker volume: {U['coverage']['pm_legs_volume']}/"
              f"{U['coverage']['pm_legs']} PM legs have volume, {U['coverage']['pairs_without_pm_volume']} pairs excluded; an hour is valid "
              f"only when every PM leg traded in the previous 24 h); overlapping valid hours >= 200: {n_pairs} (categories "
              f"{dict(Counter(al['category'] for al in qual))}); BTC 5 pm legs live 1-3 points (crypto cells near-empty), no sports pairs. "
              f"Claim cell (c = 3 cents, 1 h, follow): {t_all.get('n', 0)} trades, mean net {_s(t_all.get('mean'))} cents "
              f"({_ci_txt(t_all.get('ci'))}); in-sample half {t_ins.get('n', 0)} trades {_s(t_ins.get('mean'))}; out-of-sample half "
              f"{t_oos.get('n', 0)} trades {_s(t_oos.get('mean'))} ({_ci_txt(t_oos.get('ci'))}; robust {_ci_txt(t_oos.get('robust_ci'))}; "
              f"percentile {_ci_txt(t_oos.get('ci_pct'))}). Calibration half's best cell {best[0] if best else 'n/a'} "
              f"(IS {_s(best[1]['mean_is']) if best else 'n/a'}, OOS {_s(best[1]['mean_oos']) if best else 'n/a'} over "
              f"{best[1]['n_oos'] if best else 0} trades). DSR over 32 cells {_f(dsr)}; PBO {_f((pbo or {}).get('pbo'))}. Costs: Kalshi "
              f"bid/ask + 0.07 P(1-P) each way, PM half-spread {hs * 100:.2f} cents [{hs_src}] + Gamma fee flag; arb carry at {bill_txt} — {why}")
    stat = {"n_pairs_qualifying": n_pairs, "n_pairs_aligned": len(als), "n_pairs_with_volume": len(with_vol), "coverage": U["coverage"],
            "table_gaps": cov, "frozen_at": frozen, "first_price_bundle": first_price, "claim_cell": {"all": t_all, "in_sample": t_ins, "out_of_sample": t_oos},
            "split": {"calibration_pairs": len(cal), "test_pairs": len(test), "split_at": (test[0].get("available_at") if test else None)},
            "cells": cell_stats, "best_in_sample_cell": best[0] if best else None, "dsr": dsr, "var_trial_sr": var_sr, "pbo": pbo,
            "overlap_hours": {k: v for k, v in sorted(overlap.items(), key=lambda kv: -kv[1])[:50]},
            "costs": {"kalshi_fee": KALSHI_FEE, "pm_half_spread": hs, "pm_half_spread_source": hs_src, "pm_fee_rates": PM_FEE_RATE,
                      "bill_rate_range": [arb_rates[0], arb_rates[-1]] if arb_rates else None, "bill_source": f"{DTB3_B} by available_at at the entry hour" if curve is not None else None,
                      "arb_carry_cents_mean": float(np.mean(arb_carry)) if arb_carry else None},
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "signal-driven entries (leader moves): no grid phase"}
    return _out(stat, n_pairs, verdict, reason)


# ====================================================================================================== T-337 ==

YEAR_S = 365.0 * 86400.0


def svi_fit(k: np.ndarray, w: np.ndarray, wt: Optional[np.ndarray] = None) -> Optional[dict]:
    """Quasi-explicit SVI on total variance: for each (m, sigma) on a grid the raw parameters (a, d, c) are weighted
    least squares (c >= 0, |d| <= c enforced by projection); the best SSE wins. Returns the raw parameters."""
    k, w = np.asarray(k, float), np.asarray(w, float)
    wt = np.ones_like(k) if wt is None else np.asarray(wt, float)
    if k.size < 5 or np.ptp(k) <= 0:
        return None
    ms = np.unique(np.concatenate([np.linspace(k.min(), k.max(), 9), [0.0]]))
    sigs = np.geomspace(0.01, 1.0, 10)
    M, S = np.meshgrid(ms, sigs, indexing="ij")
    M, S = M.ravel(), S.ravel()
    y = (k[None, :] - M[:, None]) / S[:, None]                       # (G, n)
    z = np.sqrt(y * y + 1.0)
    G = y.shape[0]

    def solve(cols):
        """Batched weighted least squares on the given (G, n, p) design."""
        Xw = cols * wt[None, :, None]
        A = np.einsum("gni,gnj->gij", Xw, cols) + 1e-12 * np.eye(cols.shape[2])[None]
        bv = np.einsum("gni,n->gi", Xw, w)
        try:
            return np.linalg.solve(A, bv[:, :, None])[:, :, 0]
        except np.linalg.LinAlgError:
            return None

    ones = np.ones_like(y)
    cands = []                                                       # (a, d, c, feasible) per candidate family
    full = solve(np.stack([ones, y, z], axis=2))                     # interior: a, d, c free
    if full is not None:
        cands.append((full[:, 0], full[:, 1], full[:, 2], (full[:, 2] >= 0) & (np.abs(full[:, 1]) <= full[:, 2] + 1e-15)))
    for rho in (1.0, -1.0):                                          # boundary rho = +/-1: c = |d|
        two = solve(np.stack([ones, rho * y + z], axis=2))
        if two is not None:
            cc = two[:, 1]
            cands.append((two[:, 0], rho * cc, cc, cc >= 0))
    flat_a = (wt[None, :] * w[None, :]).sum(axis=1) / wt.sum()       # c = d = 0
    cands.append((flat_a, np.zeros(G), np.zeros(G), np.ones(G, dtype=bool)))
    best = None
    for a, d, c, ok in cands:
        fit = a[:, None] + d[:, None] * y + c[:, None] * z
        sse = (wt[None, :] * (w[None, :] - fit) ** 2).sum(axis=1)
        sse = np.where(ok, sse, np.inf)
        g = int(np.argmin(sse))
        if np.isfinite(sse[g]) and (best is None or sse[g] < best[0]):
            best = (float(sse[g]), float(a[g]), float(d[g]), float(c[g]), float(M[g]), float(S[g]))
    if best is None:
        return None
    sse, a, d, c, m_, s_ = best
    return {"kind": "svi", "a": a, "d": d, "c": c, "m": m_, "sigma": s_, "sse": sse,
            "k_min": float(k.min()), "k_max": float(k.max()), "n": int(k.size)}


def cubic_fit(k: np.ndarray, w: np.ndarray, wt: Optional[np.ndarray] = None) -> Optional[dict]:
    """Weighted cubic in log-moneyness on total variance."""
    k, w = np.asarray(k, float), np.asarray(w, float)
    wt = np.ones_like(k) if wt is None else np.asarray(wt, float)
    if k.size < 5 or np.ptp(k) <= 0:
        return None
    sw = np.sqrt(wt)
    X = np.vander(k, 4)
    coef, *_ = np.linalg.lstsq(X * sw[:, None], w * sw, rcond=None)
    fit = X @ coef
    return {"kind": "cubic", "coef": [float(x) for x in coef], "sse": float((wt * (w - fit) ** 2).sum()),
            "k_min": float(k.min()), "k_max": float(k.max()), "n": int(k.size)}


def smile_w(fit: dict, k) -> np.ndarray:
    """Total variance of a fitted smile at log-moneyness k (floored at 1e-8)."""
    k = np.asarray(k, float)
    if fit["kind"] == "svi":
        y = (k - fit["m"]) / fit["sigma"]
        w = fit["a"] + fit["d"] * y + fit["c"] * np.sqrt(y * y + 1.0)
    else:
        w = np.polyval(fit["coef"], k)
    return np.maximum(w, 1e-8)


def digital_prob(k: float, w_fn, tau: float, dk: float = 1e-3) -> float:
    """P(S_T > K) under a smile: N(d2) - phi(d2) sqrt(tau) dsigma/dk, with w_fn(k) the total variance at k, tau in years
    and k = ln(K / F). (The Breeden-Litzenberger digital for the fitted smile.)"""
    w0 = float(w_fn(np.array([k]))[0])
    sig = math.sqrt(w0 / tau)
    wp, wm = float(w_fn(np.array([k + dk]))[0]), float(w_fn(np.array([k - dk]))[0])
    dsig = (math.sqrt(wp / tau) - math.sqrt(wm / tau)) / (2 * dk)
    st = sig * math.sqrt(tau)
    d2 = -k / st - st / 2
    p = norm_cdf(d2) - norm_pdf(d2) * math.sqrt(tau) * dsig
    return min(max(p, 0.0), 1.0)


class SmileBook:
    """Per-(decision hour, expiry) smile fits from Deribit trades grouped by hour; a decision at the start of hour H
    uses the IV observations of hours H-2 and H-1 (timestamps < H x 3600). ``groups``: {(hour, expiry): {strike: [iv sum,
    n], 'F': [index sum, n]}}. The forward at H is point in time (rule 4): ``forward[H]`` (the hourly spot close of the
    bar ending at H, available at H) when given, else the index price of the latest Deribit trade before H
    (``last_idx``: {hour: (ts, index)}), else the mean index of the two hours' trades (``mean_index``, the stale fallback,
    counted). Each strike keeps its traded IV (sticky strike) and is placed at k = ln(K / F_H); ``stale`` records
    ln(mean index / F_H) per fit."""

    def __init__(self, groups: dict, expiry_ts: dict, min_strikes: int = 6, forward: Optional[dict] = None, last_idx: Optional[dict] = None):
        self.groups = groups
        self.expiry_ts = expiry_ts
        self.min_strikes = min_strikes
        self.forward = forward or {}
        self.last_idx = last_idx or {}
        self.cache: dict = {}
        self.by_hour: dict = defaultdict(set)
        for (h, e) in groups:
            self.by_hour[h].add(e)
        self.n_fits = 0
        self.n_sparse = 0
        self.fwd_source: Counter = Counter()
        self.stale: list = []

    def expiries_at(self, H: int) -> set:
        return self.by_hour.get(H - 1, set()) | self.by_hour.get(H - 2, set())

    def forward_at(self, H: int) -> tuple:
        """(forward known at the start of hour H, source) or (None, None) when neither a spot close nor a Deribit trade
        before H exists."""
        F = self.forward.get(H)
        if F is not None and F > 0:
            return float(F), "spot"
        for h in (H - 1, H - 2):
            li = self.last_idx.get(h)
            if li is not None and li[1] and li[1] > 0:
                return float(li[1]), "deribit_last_trade"
        return None, None

    def fits(self, H: int, expiry: str):
        key = (H, expiry)
        if key in self.cache:
            return self.cache[key]
        strikes: dict = {}
        F_sum, F_n = 0.0, 0
        for h in (H - 2, H - 1):
            g = self.groups.get((h, expiry))
            if g:
                for K, s in g.items():
                    if K == "F":
                        F_sum += s[0]
                        F_n += s[1]
                    else:
                        cur = strikes.get(K)
                        if cur is None:
                            strikes[K] = [s[0], s[1]]
                        else:
                            cur[0] += s[0]
                            cur[1] += s[1]
        res = None
        ets = self.expiry_ts.get(expiry)
        if len(strikes) >= self.min_strikes and F_n and ets is not None:
            t = H * HOUR
            tau = (ets - t) / YEAR_S
            if tau * YEAR_S >= HOUR:
                F_avg = F_sum / F_n
                F, src = self.forward_at(H)
                if F is None:
                    F, src = F_avg, "mean_index"
                Ks = np.array(sorted(strikes), float)
                iv = np.array([strikes[K][0] / strikes[K][1] for K in Ks]) / 100.0
                wt = np.array([min(strikes[K][1], 10) for K in Ks], float)
                kk = np.log(Ks / F)
                w = iv * iv * tau
                svi, cub = svi_fit(kk, w, wt), cubic_fit(kk, w, wt)
                if svi and cub:
                    res = {"F": F, "F_avg": F_avg, "forward_source": src, "tau": tau, "svi": svi, "cubic": cub,
                           "k_min": float(kk.min()), "k_max": float(kk.max())}
                    self.n_fits += 1
                    self.fwd_source[src] += 1
                    self.stale.append(math.log(F_avg / F))
        if res is None:
            self.n_sparse += 1
        self.cache[key] = res
        return res

    def staleness(self) -> Optional[dict]:
        """Quantiles (in %) of |ln(mean index of hours H-2, H-1 / F_H)| over the fits: how far the two-hour mean index
        sits from the point-in-time forward."""
        if not self.stale:
            return None
        a = np.abs(np.array(self.stale)) * 100.0
        return {"n_fits": int(a.size), "abs_ln_pct_quantiles": {q: float(np.quantile(a, float(q))) for q in ("0.5", "0.75", "0.9", "0.95", "0.99")},
                "mean_signed_pct": float(np.mean(self.stale) * 100.0), "sources": dict(self.fwd_source)}

    def p_rn(self, H: int, K: float, t_res: int, margin: float = 0.02) -> Optional[dict]:
        """Risk-neutral digital probabilities {svi, cubic} for strike K resolving at unix ``t_res``, decided at the start
        of hour H: total variance interpolated linearly in time between the bracketing expiries (flat-vol scaling when
        only one side exists); None when no fit exists or K lies outside the traded strike range."""
        t = H * HOUR
        tau_res = (t_res - t) / YEAR_S
        if tau_res * YEAR_S < HOUR:
            return None
        cands = []
        for e in self.expiries_at(H):
            f = self.fits(H, e)
            if f is not None:
                cands.append((f["tau"], f))
        if not cands:
            return None
        cands.sort(key=lambda x: x[0])
        below = [c for c in cands if c[0] <= tau_res]
        above = [c for c in cands if c[0] >= tau_res]
        pick = []
        if below and above:
            pick = [below[-1], above[0]]
        elif below:
            pick = [below[-1]]
        else:
            pick = [above[0]]
        out = {}
        for kind in ("svi", "cubic"):
            def w_fn(kk, _pick=pick, _kind=kind):
                if len(_pick) == 2 and _pick[1][0] > _pick[0][0]:
                    (t1, f1), (t2, f2) = _pick
                    w1 = smile_w(f1[_kind], kk)
                    w2 = smile_w(f2[_kind], kk)
                    lam = (tau_res - t1) / (t2 - t1)
                    return np.maximum(w1 + lam * (w2 - w1), 1e-8)
                t1, f1 = _pick[0]
                return smile_w(f1[_kind], kk) * (tau_res / t1)
            F = pick[0][1]["F"]
            k = math.log(K / F)
            if any(not (f["k_min"] - margin <= k <= f["k_max"] + margin) for _, f in pick):
                return None
            out[kind] = digital_prob(k, w_fn, tau_res)
        out["F"] = pick[0][1]["F"]
        out["n_expiries"] = len(pick)
        return out


def fade_trades(hours: np.ndarray, p_poly: np.ndarray, p_rn: np.ndarray, t_res: int, outcome: Optional[int], market_id: str,
                gap_in: float = 5.0, gap_out: float = 1.0, lo: float = 0.05, hi: float = 0.95, fee: float = 0.07, haircut: float = 0.01) -> list:
    """T-337 fades on one market: at hour t with |gap| = |p_poly - p_RN| > gap_in points and p_RN in [lo, hi], buy NO
    (gap > 0) or YES (gap < 0) at p_poly; exit at the first later hour with |gap| < gap_out (taker fee again) or at
    resolution on ``outcome`` (None: unresolved, the trade is dropped). Net per share = payoff - cost - fees - haircut.
    One position per market at a time."""
    out = []
    n = len(hours)
    i = 0
    while i < n:
        q, r = p_poly[i], p_rn[i]
        if not (np.isfinite(q) and np.isfinite(r)) or not (lo <= r <= hi) or not (0 < q < 1):
            i += 1
            continue
        gap = 100.0 * (q - r)
        if abs(gap) <= gap_in:
            i += 1
            continue
        side = "no" if gap > 0 else "yes"
        cost = (1 - q) if side == "no" else q
        fees = fee * q * (1 - q)
        j = i + 1
        exit_val, exit_kind, exit_i = None, None, None
        while j < n:
            qj, rj = p_poly[j], p_rn[j]
            if np.isfinite(qj) and np.isfinite(rj) and abs(100.0 * (qj - rj)) < gap_out:
                exit_val = (1 - qj) if side == "no" else qj
                fees += fee * qj * (1 - qj)
                exit_kind, exit_i = "gap<1", j
                break
            j += 1
        if exit_val is None:
            if outcome is None:
                i = n
                break
            exit_val = float(outcome) if side == "yes" else 1.0 - float(outcome)
            exit_kind, exit_i = "resolution", n
        net = exit_val - cost - fees - haircut
        out.append({"hour": int(hours[i]), "market_id": market_id, "side": side, "gap": float(gap), "p_poly": float(q), "p_rn": float(r),
                    "net": float(net), "exit": exit_kind, "hours_held": int((exit_i if exit_i < n else n) - i)})
        i = (exit_i + 1) if exit_i is not None and exit_i < n else n
    return out


_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                        "october", "november", "december"], 1)}
_P_DESC = re.compile(r"(\d{1,2}) ([A-Za-z]+)\.? '(\d{2}),? (\d{1,2}):(\d{2})")
_P_TIME = re.compile(r"(\d{1,2}):(\d{2}) in the ET")
_P_SLUG = re.compile(r"on-([a-z]+)-(\d{1,2})(?:-(\d{4}))?(?:-(\d{1,2})(am|pm)-et)?$")


def btc_market_spec(m: dict) -> Optional[dict]:
    """Strike, resolution time (unix) and outcome of a 'Bitcoin above' Gamma market; None for barrier / range / unparsed
    markets. The resolution time comes from the description ("22 Mar '24 12:00 in the ET timezone"), else the slug's
    date with the described hour (noon ET for the daily / weekly events, 5 pm ET for the -5pm-et variant)."""
    slug = re.sub(r"-\d{3,}$", "", str(m.get("_event_slug") or m.get("slug") or ""))
    q = str(m.get("question") or "")
    if any(x in slug for x in ("till", "between", "reach", "dip", "hit", "range")) or "between" in q.lower():
        return None
    strike = _label_number(m.get("groupItemTitle")) if m.get("groupItemTitle") else None
    if strike is None:
        mm = re.search(r"\$\s?([\d,]+(?:\.\d+)?)\s*(k)?", q, re.I)
        if mm:
            strike = float(mm.group(1).replace(",", "")) * (1000 if mm.group(2) else 1)
    if strike is None or strike <= 0:
        return None
    if strike < 1000:
        strike *= 1000
    txt = " ".join(str(m.get(k) or "") for k in ("description", "_event_description"))
    t_res = None
    d = _P_DESC.search(txt)
    if d:
        day, mon, yy, hh, mi = d.groups()
        mon_i = _MONTHS.get(mon.lower()) or next((v for k_, v in _MONTHS.items() if k_.startswith(mon.lower()[:3])), None)
        if mon_i:
            t_res = int(datetime(2000 + int(yy), mon_i, int(day), int(hh), int(mi), tzinfo=ET).timestamp())
    if t_res is None:
        s = _P_SLUG.search(slug)
        end = _ts(m.get("endDate") or m.get("_event_end"))
        if s and end is not None:
            mon, day, yr, hr, ap = s.groups()
            mon_i = _MONTHS.get(mon)
            if mon_i:
                year = int(yr) if yr else datetime.fromtimestamp(end, UTC).year
                if hr:
                    hour = int(hr) % 12 + (12 if ap == "pm" else 0)
                else:
                    tm = _P_TIME.search(txt)
                    hour = int(tm.group(1)) if tm else None
                    if hour is None:
                        h_utc = datetime.fromtimestamp(end, UTC).hour
                        hour = 12 if h_utc in (16, 17) else (17 if h_utc == 21 else None)
                if hour is not None:
                    try:
                        t_res = int(datetime(year, mon_i, int(day), hour, 0, tzinfo=ET).timestamp())
                    except ValueError:
                        t_res = None
    if t_res is None:
        return None
    toks = m.get("clobTokenIds")
    try:
        toks = json.loads(toks) if isinstance(toks, str) else toks
    except (TypeError, ValueError):
        toks = None
    if not toks:
        return None
    return {"market_id": str(m.get("id")), "token": str(toks[0]), "strike": float(strike), "t_res": t_res,
            "outcome": _outcome_of_market(m), "variant": "5pm" if slug.endswith("pm-et") else "noon", "slug": slug}


def _deribit_groups(archive, months: Sequence[str]) -> tuple:
    """({(hour, expiry): {strike: [iv sum, count], 'F': [index sum, count]}}, {expiry: unix of 08:00 UTC}, trades,
    {hour: (timestamp ms, index price) of the hour's latest trade}) from the near-expiry bundles, reduced row by row
    (running sums: ~250k trades a month, 8.9 M in all)."""
    groups: dict = {}
    expiry_ts: dict = {}
    last_idx: dict = {}
    n_trades = 0
    for mo in months:
        name = DRB + mo
        if not _has(archive, name):
            continue
        for r in archive.load(name):
            if r.get("kind") != "option-trade":
                continue
            v = r["value"]
            iv, K, F, ts, ex = _num(v.get("iv")), _num(v.get("strike")), _num(v.get("index_price")), _num(v.get("timestamp")), v.get("expiry")
            if None in (iv, K, F, ts) or not ex or iv <= 0 or K <= 0 or F <= 0:
                continue
            h = int(ts // 1000) // HOUR
            g = groups.get((h, ex))
            if g is None:
                g = groups[(h, ex)] = {"F": [0.0, 0]}
            s = g.get(K)
            if s is None:
                g[K] = [iv, 1]
            else:
                s[0] += iv
                s[1] += 1
            g["F"][0] += F
            g["F"][1] += 1
            li = last_idx.get(h)
            if li is None or ts > li[0]:
                last_idx[h] = (ts, F)
            if ex not in expiry_ts:
                try:
                    expiry_ts[ex] = int(datetime.fromisoformat(ex).replace(hour=8, tzinfo=UTC).timestamp())
                except ValueError:
                    pass
            n_trades += 1
    return groups, expiry_ts, n_trades, last_idx


def _hourly_spot(archive, name: str = HBTC_B) -> dict:
    """{decision hour H: close of the hourly bar ending at H} from an ``hourly-<SYM>`` bundle (rows: t = bar start, close;
    available_at = t + 1 h). Point in time: a bar counts at H only when its available_at <= H x 3600 (a partial last bar
    stamped later is dropped). Empty when the bundle is not archived (it is optional: the Deribit trade index stands in)."""
    if not _has(archive, name):
        return {}

    def load():
        out = {}
        for r in _rows(archive, name):
            v = r.get("value") or {}
            t, c = _num(v.get("t")), _num(v.get("close"))
            if t is None or c is None or c <= 0:
                continue
            H = int(t) // HOUR + 1
            av = _ts(r.get("available_at"))
            if av is not None and av > H * HOUR:
                continue
            out[H] = c
        return out
    return _cached(archive, ("hourly_spot", name), load)


def _binance_minutes(archive, name: str = BNC_B) -> dict:
    """{minute start t: close} of the Binance BTCUSDT 1-minute klines archived around the 'Bitcoin above' resolution times
    (``mandel.data.binance_klines``; kind bar1m, available at the minute's end). Empty when the bundle is not archived
    (optional: the resolution-source basis criterion is then None)."""
    if not _has(archive, name):
        return {}

    def load():
        out = {}
        for r in _rows(archive, name):
            if r.get("kind") != "bar1m":
                continue
            v = r.get("value") or {}
            t, c = _num(v.get("t")), _num(v.get("close"))
            if t is not None and c is not None and c > 0:
                out[int(t) - int(t) % 60] = c
        return out
    return _cached(archive, ("binance_minutes", name), load)


def resolution_basis(t_res_set: Sequence[int], minutes: dict, last_idx: dict) -> dict:
    """{t_res: ln(Binance close / Deribit index)} at each resolution time: the index price of the latest Deribit trade in
    the hour before t_res (``_deribit_groups``'s last_idx) against the Binance close of the minute holding that trade
    (both known by t_res: the minute closes before the hour does). Only resolution times with both observations."""
    out = {}
    for t in t_res_set:
        li = last_idx.get((int(t) - 1) // HOUR)
        if li is None or li[0] // 1000 >= t or not li[1] or li[1] <= 0:
            continue
        c = minutes.get(int(li[0] // 1000) // 60 * 60)
        if c is not None:
            out[int(t)] = math.log(c / li[1])
    return out


def basis_by_hour(basis: dict):
    """H -> median of the resolution-time bases known by H (t_res <= H x 3600), None before the first; the point-in-time
    strike shift of the resolution-source control."""
    ts = sorted(basis)
    vals = np.array([basis[t] for t in ts])
    cache: dict = {}

    def at(H: int) -> Optional[float]:
        k = bisect.bisect_right(ts, H * HOUR)
        if k == 0:
            return None
        if k not in cache:
            cache[k] = float(np.median(vals[:k]))
        return cache[k]
    return at


def resolution_audit(specs: Sequence[dict], minutes: dict) -> dict:
    """Gamma outcomes against the Binance close under both readings of 'the 1 minute candle for 12:00' (the candle opening
    at t_res; the candle closing at t_res, which is also the hour candle's close for the 5 pm variant), per variant."""
    out: dict = {}
    for s in specs:
        if s["outcome"] is None:
            continue
        for lab, t in (("candle_opening_at_t_res", s["t_res"]), ("candle_closing_at_t_res", s["t_res"] - 60)):
            c = minutes.get(t)
            if c is None:
                continue
            d = out.setdefault(s["variant"], {}).setdefault(lab, {"n": 0, "agree": 0})
            d["n"] += 1
            d["agree"] += int((c > s["strike"]) == bool(s["outcome"]))
    for v in out.values():
        for d in v.values():
            d["rate"] = round(d["agree"] / d["n"], 4) if d["n"] else None
    return out


def b6c_pmxv_pm_vs_deribit_digital(archive):
    """T-337."""
    months = _names(archive, DRB)
    miss = _missing(archive, [EV_BTC_B] + ([] if months else [DRB + "<YYYY-MM>"]))
    if miss:
        return miss
    markets = _pm_markets(archive)
    specs = [s for s in (btc_market_spec(m) for m in markets.values() if m.get("_event_slug") and ("bitcoin" in str(m.get("_event_slug")) or "btc" in str(m.get("_event_slug")))) if s]
    pm_series = _pm_hourly(archive)
    specs = [s for s in specs if s["token"] in pm_series]
    groups, expiry_ts, n_trades, last_idx = _deribit_groups(archive, [n[len(DRB):] for n in months])
    spot = _hourly_spot(archive, HBTC_B)                               # optional: the point-in-time forward at H
    book = SmileBook(groups, expiry_ts, forward=spot, last_idx=last_idx)
    minutes = _binance_minutes(archive, BNC_B)                         # optional: the resolution-source basis control
    basis = resolution_basis(sorted({s["t_res"] for s in specs}), minutes, last_idx) if minutes else {}
    basis_at = basis_by_hour(basis)
    trades = {"svi": [], "cubic": []}
    adj = {"svi": [], "cubic": []}
    shifted = {"+0.2%": [], "-0.2%": []}
    gap_rows, brier = [], {"svi": [], "cubic": [], "poly": []}
    n_dec, n_skipped, n_markets_used, n_unshifted = 0, 0, 0, 0
    for s in specs:
        hs, ps = pm_series[s["token"]]
        keep = (hs * HOUR) < s["t_res"] - HOUR
        hs, ps = hs[keep], ps[keep]
        if hs.size == 0:
            continue
        prn = {"svi": np.full(hs.size, np.nan), "cubic": np.full(hs.size, np.nan)}
        prn_adj = {"svi": np.full(hs.size, np.nan), "cubic": np.full(hs.size, np.nan)}
        prn_shift = {"+0.2%": np.full(hs.size, np.nan), "-0.2%": np.full(hs.size, np.nan)}
        for i, H in enumerate(hs):
            r = book.p_rn(int(H), s["strike"], s["t_res"])
            n_dec += 1
            if r is None:
                n_skipped += 1
                continue
            prn["svi"][i], prn["cubic"][i] = r["svi"], r["cubic"]
            if minutes:                                                  # the basis control: K on the Deribit index = K x exp(-basis known at H)
                b = basis_at(int(H))
                n_unshifted += b is None
                ra = r if b is None else book.p_rn(int(H), s["strike"] * math.exp(-b), s["t_res"])
                if ra is not None:
                    prn_adj["svi"][i], prn_adj["cubic"][i] = ra["svi"], ra["cubic"]
            if 0 < ps[i] < 1:
                gap_rows.append((s["market_id"], int(H), 100.0 * (ps[i] - r["svi"])))
                if s["outcome"] is not None:
                    brier["svi"].append((r["svi"] - s["outcome"]) ** 2)
                    brier["cubic"].append((r["cubic"] - s["outcome"]) ** 2)
                    brier["poly"].append((ps[i] - s["outcome"]) ** 2)
            for lab, mult in (("+0.2%", 1.002), ("-0.2%", 0.998)):          # the strike-shift sensitivity (same hours, SVI)
                rs = book.p_rn(int(H), s["strike"] * mult, s["t_res"])
                if rs is not None:
                    prn_shift[lab][i] = rs["svi"]
        if np.isfinite(prn["svi"]).any():
            n_markets_used += 1
        for kind in ("svi", "cubic"):
            trades[kind] += fade_trades(hs, ps, prn[kind], s["t_res"], s["outcome"], s["market_id"])
            if minutes:
                adj[kind] += fade_trades(hs, ps, prn_adj[kind], s["t_res"], s["outcome"], s["market_id"])
        for lab in shifted:
            shifted[lab] += fade_trades(hs, ps, prn_shift[lab], s["t_res"], s["outcome"], s["market_id"])
    res = {}
    for kind, tr in trades.items():
        if tr:
            x = np.array([t["net"] for t in tr]) * 100.0
            cs = cluster_stud(x, [t["market_id"] for t in tr], N_BOOT)
            yrs = np.array([datetime.fromtimestamp(t["hour"] * HOUR, UTC).year for t in tr])
            m_early = float(x[yrs <= 2025].mean()) if (yrs <= 2025).any() else None
            m_late = float(x[yrs >= 2026].mean()) if (yrs >= 2026).any() else None
            res[kind] = {"n": int(x.size), "markets": cs.get("clusters"), "mean": cs["est"], "ci90": cs["ci90"], "ci": cs["ci"], "p": cs.get("p"),
                         "lower95_one_sided": cs["ci90"][0], "mean_2024_2025": m_early, "mean_2026": m_late,
                         "n_2024_2025": int((yrs <= 2025).sum()), "n_2026": int((yrs >= 2026).sum()),
                         "by_exit": dict(Counter(t["exit"] for t in tr)), "by_side": dict(Counter(t["side"] for t in tr))}
        else:
            res[kind] = {"n": 0, "mean": None, "ci90": [None, None], "lower95_one_sided": None, "mean_2024_2025": None, "mean_2026": None}
    sens = {lab: {"n": len(tr), "mean": float(np.mean([t["net"] for t in tr]) * 100.0) if tr else None} for lab, tr in shifted.items()}
    # diagnostics: AR(1) half-life of the gap, paired Brier difference
    half_life = None
    if len(gap_rows) > 50:
        by_m = defaultdict(list)
        for mid, H, g in gap_rows:
            by_m[mid].append((H, g))
        xs, ys = [], []
        for mid, rows_ in by_m.items():
            rows_.sort()
            for (h1, g1), (h2, g2) in zip(rows_[:-1], rows_[1:]):
                if h2 == h1 + 1:
                    xs.append(g1)
                    ys.append(g2 - g1)
        if len(xs) > 50:
            xs, ys = np.array(xs), np.array(ys)
            xs_c = xs - xs.mean()
            beta = float((xs_c @ (ys - ys.mean())) / (xs_c @ xs_c)) if (xs_c @ xs_c) > 0 else 0.0
            half_life = (-math.log(2) / math.log(1 + beta)) if -1 < beta < 0 else None
    brier_diff = {k: (float(np.mean(brier[k]) - np.mean(brier["poly"])) if brier[k] else None) for k in ("svi", "cubic")}
    n = res["svi"]["n"]
    dsr7 = None
    if n >= 10:
        try:
            dsr7 = float(deflated_sharpe_ratio(np.array([t["net"] for t in trades["svi"]]), 7))
        except Exception:
            dsr7 = None
    crit = []
    for kind in ("svi", "cubic"):
        r = res[kind]
        lb = r.get("lower95_one_sided")
        crit.append((f"{kind.upper()} fit: one-sided 95% lower bound of the mean net return per trade {_s(lb)} cents > 0 "
                     f"(mean {_s(r.get('mean'))} over {r.get('n', 0)} trades, {r.get('markets')} markets)",
                     None if lb is None else lb > 0, r.get("ci90", [None, None])[1] is not None and r["ci90"][1] < 0))
    signs = []
    for kind in ("svi", "cubic"):
        r = res[kind]
        a, b = r.get("mean_2024_2025"), r.get("mean_2026")
        signs.append(None if a is None or b is None else (a > 0) == (b > 0))
    same_sign = None if any(x is None for x in signs) else all(signs)
    crit.append(("same sign of the mean net return in 2024-2025 and 2026 under both fits: "
                 + "; ".join(f"{k} {_s(res[k].get('mean_2024_2025'))} ({res[k].get('n_2024_2025', 0)}) / {_s(res[k].get('mean_2026'))} "
                             f"({res[k].get('n_2026', 0)})" for k in ("svi", "cubic")), same_sign, False))
    res_adj = {}
    for kind, tr in adj.items():
        if tr:
            x = np.array([t["net"] for t in tr]) * 100.0
            cs = cluster_stud(x, [t["market_id"] for t in tr], N_BOOT)
            res_adj[kind] = {"n": int(x.size), "markets": cs.get("clusters"), "mean": cs["est"], "ci90": cs["ci90"], "lower95_one_sided": cs["ci90"][0]}
        else:
            res_adj[kind] = {"n": 0, "mean": None, "ci90": [None, None], "lower95_one_sided": None}
    bvals = np.array(list(basis.values())) * 100.0 if basis else np.array([])
    basis_stat = {"bundle": BNC_B if minutes else None, "minutes": len(minutes), "n_resolutions": len(basis), "of_resolution_times": len({s["t_res"] for s in specs}),
                  "median_pct": float(np.median(bvals)) if bvals.size else None, "mean_pct": float(bvals.mean()) if bvals.size else None,
                  "iqr_pct": [float(np.percentile(bvals, 25)), float(np.percentile(bvals, 75))] if bvals.size else None,
                  "decisions_unshifted_before_first_basis": n_unshifted, "fits": res_adj,
                  "resolution_audit": resolution_audit(specs, minutes) if minutes else None,
                  "rule": "basis = ln(Binance close of the minute holding the latest Deribit trade before t_res / that trade's index); at decision hour H "
                          "the strike is K x exp(-median of the bases of resolution times <= H); fades re-run under both fits"}
    if minutes:
        lbs = {k: res_adj[k]["lower95_one_sided"] for k in ("svi", "cubic")}
        ok = None if any(v is None for v in lbs.values()) else all(v > 0 for v in lbs.values())
        dec = any(res_adj[k]["ci90"][1] is not None and res_adj[k]["ci90"][1] < 0 for k in ("svi", "cubic"))
        crit.append((f"resolution-source basis control (Binance BTCUSDT vs the Deribit index) applied: {BNC_B} basis ln(Binance / Deribit) median "
                     f"{_s(basis_stat['median_pct'], 3)}% (IQR {_f((basis_stat['iqr_pct'] or [None])[0], 3)}..{_f((basis_stat['iqr_pct'] or [None, None])[1], 3)}%) over "
                     f"{len(basis)} of {basis_stat['of_resolution_times']} resolution times; strikes shifted by the point-in-time trailing median "
                     f"({n_unshifted} decisions before the first basis unshifted) -> one-sided 95% lower bound > 0 under both fits: SVI {_s(lbs['svi'])} "
                     f"({res_adj['svi']['n']} trades), cubic {_s(lbs['cubic'])} ({res_adj['cubic']['n']})", ok, dec))
    else:
        crit.append((f"resolution-source basis control (Binance BTCUSDT vs the Deribit index) applied: Binance klines are not archived ({BNC_B}; "
                     f"sensitivity: strikes +0.2% -> mean {_s(sens['+0.2%']['mean'])} cents over {sens['+0.2%']['n']} trades, -0.2% -> "
                     f"{_s(sens['-0.2%']['mean'])} over {sens['-0.2%']['n']})", None, False))
    verdict, why = _decide(crit, n, 300, "trades")
    stale = book.staleness() or {}
    sq = stale.get("abs_ln_pct_quantiles", {})
    src = dict(book.fwd_source)
    fwd_txt = (f"forward at H: {HBTC_B} close of the bar ending at H (available at H; {src.get('spot', 0)} fits" + (f", {len(spot)} bars from "
               f"{datetime.fromtimestamp(min(spot) * HOUR, UTC).strftime('%Y-%m-%d')}" if spot else ", bundle not archived") +
               f"), else the latest Deribit trade index before H ({src.get('deribit_last_trade', 0)} fits; {src.get('mean_index', 0)} fell back to the "
               f"two-hour mean index); the two-hour mean index is stale against F_H by |ln| median {_f(sq.get('0.5'))}%, 90% {_f(sq.get('0.9'))}%, "
               f"99% {_f(sq.get('0.99'))}%")
    reason = (f"{len(specs)} 'Bitcoin above' markets with hourly CLOB prices ({dict(Counter(s['variant'] for s in specs))}; barrier / range "
              f"markets excluded), {n_markets_used} with a Deribit smile at some hour; Deribit near-expiry trades {n_trades} in {len(months)} "
              f"monthly bundles ({months[0][len(DRB):] if months else 'n/a'}..{months[-1][len(DRB):] if months else 'n/a'}), {book.n_fits} "
              f"(hour, expiry) smiles fitted, {book.n_sparse} sparse (< 6 strikes); {n_dec} decision hours, {n_skipped} without a usable "
              f"p_RN (sparse or outside the strike range); {fwd_txt}. Fades |gap| > 5 points, p_RN in [0.05, 0.95], 0.07 p(1-p) taker fee each way, "
              f"1-point haircut: SVI {res['svi'].get('n', 0)} trades mean {_s(res['svi'].get('mean'))} cents (one-sided 95% lower "
              f"{_s(res['svi'].get('lower95_one_sided'))}; {res['svi'].get('by_exit')}); cubic {res['cubic'].get('n', 0)} trades mean "
              f"{_s(res['cubic'].get('mean'))} (lower {_s(res['cubic'].get('lower95_one_sided'))}). AR(1) half-life of the gap "
              f"{_f(half_life, 1)} h; paired Brier p_RN - p_poly: SVI {_s(brier_diff['svi'], 4)}, cubic {_s(brier_diff['cubic'], 4)}; "
              f"DSR at the trial's 7 variants {_f(dsr7)}. Resolution-source basis control: "
              + (f"{BNC_B} archived ({len(minutes)} minutes; basis median {_s(basis_stat['median_pct'], 3)}% over {len(basis)} resolution times; "
                 f"outcome audit {json.dumps(basis_stat['resolution_audit'], sort_keys=True)}); basis-shifted SVI {res_adj['svi']['n']} trades mean "
                 f"{_s(res_adj['svi']['mean'])} (lower {_s(res_adj['svi']['lower95_one_sided'])}), cubic mean {_s(res_adj['cubic']['mean'])} "
                 f"(lower {_s(res_adj['cubic']['lower95_one_sided'])})" if minutes else f"{BNC_B} not archived, criterion None")
              + f" — {why}")
    stat = {"n_trades": n, "fits": res, "sensitivity_strike_shift": sens, "basis": basis_stat, "n_markets": len(specs), "n_markets_with_smile": n_markets_used,
            "variants": dict(Counter(s["variant"] for s in specs)), "deribit": {"trades": n_trades, "months": len(months), "fits": book.n_fits, "sparse": book.n_sparse},
            "forward": {"rule": "point in time at H: hourly spot close of the bar ending at H, else the latest Deribit trade index before H; smile in k = ln(K / F_H)",
                        "spot_bundle": HBTC_B if spot else None, "spot_hours": len(spot),
                        "spot_from": datetime.fromtimestamp(min(spot) * HOUR, UTC).strftime("%Y-%m-%d") if spot else None,
                        "sources": src, "staleness_of_two_hour_mean_index": stale},
            "decisions": {"hours": n_dec, "skipped": n_skipped}, "ar1_half_life_hours": half_life, "brier_diff": brier_diff, "dsr_7": dsr7,
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "hourly signal-driven entries: no grid phase"}
    return _out(stat, n, verdict, reason)


# ====================================================================================================== T-358 ==

def _daily_close(archive, name: str) -> tuple:
    """(days, adjusted closes) of a Yahoo daily bundle."""
    by = {}
    for r in _rows(archive, name):
        v = r["value"]
        c = _num(v.get("adjclose")) if v.get("adjclose") is not None else _num(v.get("close"))
        t = _num(v.get("t"))
        if c is None or t is None or c <= 0:
            continue
        by[datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")] = c
    days = sorted(by)
    return days, np.array([by[d] for d in days])


def ols_slope(u: np.ndarray, r: np.ndarray) -> tuple:
    """(slope, intercept, HC1 s.e. of the slope)."""
    u, r = np.asarray(u, float), np.asarray(r, float)
    n = u.size
    if n < 3 or np.ptp(u) <= 0:
        return None, None, None
    uc = u - u.mean()
    sxx = float(uc @ uc)
    slope = float(uc @ (r - r.mean()) / sxx)
    icpt = float(r.mean() - slope * u.mean())
    e = r - icpt - slope * u
    se = math.sqrt(float(np.sum(uc * uc * e * e)) / sxx ** 2 * n / max(n - 2, 1))
    return slope, icpt, se


def slope_test(u: np.ndarray, r: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """OLS slope with a studentized pairs bootstrap over observations (dates = clusters: one observation per date):
    two-sided p (H0: slope = 0), one-sided p (H0: slope <= 0), 95% CI, percentile CI."""
    u, r = np.asarray(u, float), np.asarray(r, float)
    n = u.size
    out = {"n": int(n), "slope": None, "se": None, "p_two": None, "p_one": None, "ci": [None, None], "ci_pct": [None, None]}
    b, a, se = ols_slope(u, r)
    if b is None or not se or se <= 0:
        return out
    out.update(slope=b, se=se, t=b / se)
    rng = np.random.default_rng(seed)
    ts, bs = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        bb, _, sb = ols_slope(u[idx], r[idx])
        if bb is None or not sb or sb <= 0:
            continue
        ts.append((bb - b) / sb)
        bs.append(bb)
    if len(ts) < 100:
        return out
    ts, bs = np.array(ts), np.array(bs)
    t_obs = b / se
    out["ci"] = [b - float(np.quantile(ts, 0.975)) * se, b - float(np.quantile(ts, 0.025)) * se]
    out["ci_pct"] = [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]
    out["p_two"] = float(min(1.0, 2 * min((np.sum(ts >= t_obs) + 1) / (ts.size + 1), (np.sum(ts <= -t_obs) + 1) / (ts.size + 1))))
    out["p_one"] = float((np.sum(ts >= t_obs) + 1) / (ts.size + 1))
    return out


def placebo_slope(u: np.ndarray, sessions: Sequence[str], closes: np.ndarray, event_idx: np.ndarray, window: int = 2, draws: int = 200,
                  exclusion: int = 3, seed: int = SEED, n_boot: int = 500) -> dict:
    """Each date's U regressed on a random non-event ``window``-session return (end index at least ``exclusion`` sessions
    from every event index), ``draws`` times, pooled, with a date-clustered studentized bootstrap of the pooled slope."""
    rng = np.random.default_rng(seed)
    n = len(sessions)
    u = np.asarray(u, float)
    bad = np.zeros(n, dtype=bool)
    for i in event_idx:
        bad[max(0, int(i) - exclusion):min(n, int(i) + exclusion + 1)] = True
    cand = np.flatnonzero(~bad)
    cand = cand[cand >= window]
    G = u.size
    if cand.size < 10 or G < 4 or np.ptp(u) <= 0:
        return {"slope": None, "p_two": None, "draws": 0}
    ends = rng.choice(cand, (draws, G))
    R = closes[ends] / closes[ends - window] - 1                   # (draws, G): one placebo return per date and draw
    Um = np.broadcast_to(u, (draws, G))

    def pooled(Umat, Rmat):
        """Pooled slope, intercept and the date-clustered (column) s.e."""
        uc = Umat - Umat.mean()
        sxx = float((uc * uc).sum())
        b = float((uc * (Rmat - Rmat.mean())).sum() / sxx)
        a = float(Rmat.mean() - b * Umat.mean())
        e = Rmat - a - b * Umat
        g = (uc * e).sum(axis=0)                                     # cluster score sums (one cluster per date)
        return b, a, math.sqrt(float((g * g).sum())) / sxx

    b, a, se = pooled(Um, R)
    per_draw = (((Um - u.mean()) * (R - R.mean(axis=1, keepdims=True))).sum(axis=1) / float(((u - u.mean()) ** 2).sum()))
    ts = []
    for _ in range(n_boot):
        pick = rng.integers(0, G, G)
        bb, ab, seb = pooled(Um[:, pick], R[:, pick])
        if seb > 0:
            ts.append((bb - b) / seb)
    if len(ts) < 50 or se <= 0:
        return {"slope": b, "p_two": None, "draws": draws}
    ts = np.array(ts)
    t_obs = b / se
    p_two = float(min(1.0, 2 * min((np.sum(ts >= t_obs) + 1) / (ts.size + 1), (np.sum(ts <= -t_obs) + 1) / (ts.size + 1))))
    return {"slope": b, "se": se, "p_two": p_two, "ci": [b - float(np.quantile(ts, 0.975)) * se, b - float(np.quantile(ts, 0.025)) * se],
            "ci99": [b - float(np.quantile(ts, 0.995)) * se, b - float(np.quantile(ts, 0.005)) * se], "draws": draws,
            "per_draw_mean": float(per_draw.mean()), "per_draw_sd": float(per_draw.std(ddof=1)) if draws > 1 else None}


def event_regression(dates: Sequence[str], U: np.ndarray, sessions: Sequence[str], closes: np.ndarray, exit_offset: Sequence[int],
                     n_boot: int = N_BOOT, seed: int = SEED, split: str = "2023-01-01") -> dict:
    """The T-358 regression of the two-session pre-event return (close(D - 2) -> close(D + exit_offset)) on U over event
    dates; halves at ``split``; the pooled placebo."""
    pos = {d: i for i, d in enumerate(sessions)}
    rows = []
    for d, u, off in zip(dates, U, exit_offset):
        i = pos.get(d)
        if i is None:
            # the event day is not a session: use the next session
            j = bisect.bisect_left(sessions, d)
            if j >= len(sessions):
                continue
            i = j
        if i - 2 < 0 or i + off >= len(sessions):
            continue
        rows.append((d, float(u), float(closes[i + off] / closes[i - 2] - 1), i))
    if not rows:
        return {"n": 0}
    d_all = [r[0] for r in rows]
    u = np.array([r[1] for r in rows])
    r = np.array([r_[2] for r_ in rows])
    idx = np.array([r_[3] for r_ in rows])
    full = slope_test(u, r, n_boot, seed)
    first = np.array([d < split for d in d_all])
    halves = {"first": slope_test(u[first], r[first], n_boot // 2, seed + 1) if first.sum() >= 8 else {"n": int(first.sum()), "slope": None},
              "second": slope_test(u[~first], r[~first], n_boot // 2, seed + 2) if (~first).sum() >= 8 else {"n": int((~first).sum()), "slope": None}}
    plc = placebo_slope(u, sessions, closes, idx, seed=seed + 3)
    return {"n": len(rows), "slope": full, "halves": halves, "placebo": plc, "mean_return": float(r.mean()),
            "first_half_dates": [d_all[i] for i in range(len(d_all)) if first[i]][:1] + [d_all[i] for i in range(len(d_all)) if first[i]][-1:],
            "u_mean": float(u.mean()), "dates": d_all, "returns": r.tolist(), "u": u.tolist()}


def _event_day(close_day: str, cal: Sequence[str], back: int = 7, fwd: int = 3) -> Optional[str]:
    """The family's calendar day nearest a market's close: the latest calendar day <= close_day within ``back`` days, else
    the earliest within ``fwd`` days after."""
    j = bisect.bisect_right(cal, close_day) - 1
    if j >= 0 and (date.fromisoformat(close_day) - date.fromisoformat(cal[j])).days <= back:
        return cal[j]
    if j + 1 < len(cal) and (date.fromisoformat(cal[j + 1]) - date.fromisoformat(close_day)).days <= fwd:
        return cal[j + 1]
    return None


def _cutoff_ts(session_day: str) -> int:
    """Unix time of 23:59:59 ET on ``session_day``."""
    d = date.fromisoformat(session_day)
    return int(datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=ET).timestamp())


def b6c_pmxv_event_uncertainty_premium(archive):
    """T-358."""
    miss = _missing(archive, [SPY_B, FOMC_B, CPI_REL_B, EMP_REL_B])
    if miss:
        return miss
    have_k = [s for s in ("KXCPI", "KXFED", "KXFEDDECISION", "KXPAYROLLS") if _has(archive, KS + s) and _has(archive, KD + s)]
    have_pm = _has(archive, EV_MACRO_B)
    if not have_k and not have_pm:
        return _missing(archive, [KS + "KXCPI", KD + "KXCPI", EV_MACRO_B])
    fam_cal = {"fomc": sorted(r["value"]["decision_day"] for r in _rows(archive, FOMC_B) if r["value"].get("scheduled") and not r["value"].get("future")),
               "cpi": sorted(r["value"]["day"] for r in _rows(archive, CPI_REL_B)),
               "payrolls": sorted(r["value"]["day"] for r in _rows(archive, EMP_REL_B)),
               "election": ["2024-11-05"]}
    spy_days, spy = _daily_close(archive, SPY_B)
    sessions = spy_days
    spos = {d: i for i, d in enumerate(sessions)}

    def three_before(ev_day: str) -> Optional[str]:
        j = bisect.bisect_left(sessions, ev_day)
        return sessions[j - 3] if j - 3 >= 0 else None

    # ---- the event list (frozen tagging rule), built before any SPY return is used ----
    contracts = []          # (family, event_key, event_day, venue, p)
    # Kalshi settled markets + daily candles
    for s in have_k:
        fam = {"KXCPI": "cpi", "KXFED": "fomc", "KXFEDDECISION": "fomc", "KXPAYROLLS": "payrolls"}[s]
        cands = defaultdict(list)
        for r in _rows(archive, KD + s):
            v = r["value"]
            c = v.get("candle") or {}
            end = _num(c.get("end_period_ts"))
            if end is not None:
                bid, ask, _ = kalshi_quote(c)
                cands[v["ticker"]].append((int(end), bid, ask))
        for tk in cands:
            cands[tk].sort()
        for r in _rows(archive, KS + s):
            v = r["value"]
            if str(v.get("result") or "").lower() not in ("yes", "no"):
                continue
            close_day = str(v.get("close_time") or "")[:10]
            ev_day = _event_day(close_day, fam_cal[fam]) if close_day else None
            if ev_day is None:
                continue
            d3 = three_before(ev_day)
            if d3 is None:
                continue
            cut = _cutoff_ts(d3) + 60
            open_ts = _ts(v.get("open_time"))
            if open_ts is not None and open_ts > cut:
                continue
            q = [x for x in cands.get(v["ticker"], []) if x[0] <= cut and x[0] >= cut - 10 * 86400]
            if not q:
                continue
            _, bid, ask = q[-1]
            if not _quote_ok(bid, ask):
                continue
            p = (bid + ask) / 2
            contracts.append((fam, f"kalshi:{v.get('event_ticker')}", ev_day, "kalshi", p))
    # Kalshi PRES-2024 (hourly candles only)
    if _has(archive, KH + "PRES"):
        byt = defaultdict(list)
        for r in archive.load(KH + "PRES"):
            v = r["value"]
            c = v.get("candle") or {}
            end = _num(c.get("end_period_ts"))
            if end is not None and str(v.get("ticker", "")).startswith("PRES-2024"):
                bid, ask, _ = kalshi_quote(c)
                byt[v["ticker"]].append((int(end), bid, ask))
        d3 = three_before("2024-11-05")
        if d3:
            cut = _cutoff_ts(d3) + 60
            for tk, q in byt.items():
                q = sorted(x for x in q if x[0] <= cut and x[0] >= cut - 10 * 86400)
                if q and _quote_ok(q[-1][1], q[-1][2]):
                    contracts.append(("election", "kalshi:PRES-2024", "2024-11-05", "kalshi", (q[-1][1] + q[-1][2]) / 2))
    # Polymarket macro events + daily snapshots
    pm_daily = defaultdict(list)
    for n in _names(archive, PMD) + (["polymarket-price-history-daily"] if _has(archive, "polymarket-price-history-daily") else []):
        for r in archive.load(n):
            v = r["value"]
            p, t = _num(v.get("p")), _num(v.get("t"))
            if p is not None and t is not None:
                pm_daily[str(v.get("market_id"))].append((int(t), p))
    for k in pm_daily:
        pm_daily[k].sort()
    if have_pm:
        for r in _rows(archive, EV_MACRO_B):
            ev = r["value"]
            slug = str(ev.get("slug") or "")
            fam = "fomc" if slug.startswith("fed") else ("cpi" if ("inflation" in slug or "cpi" in slug) else None)
            if fam is None:
                continue
            for m in ev.get("markets") or []:
                if _outcome_of_market(m) is None:
                    continue
                end_day = str(m.get("endDate") or ev.get("endDate") or "")[:10]
                ev_day = _event_day(end_day, fam_cal[fam]) if end_day else None
                if ev_day is None:
                    continue
                d3 = three_before(ev_day)
                if d3 is None:
                    continue
                cut = _cutoff_ts(d3) + 60
                q = [x for x in pm_daily.get(str(m.get("id")), []) if x[0] <= cut and x[0] >= cut - 10 * 86400]
                if not q:
                    continue
                p = q[-1][1]
                if not (0 < p < 1):
                    continue
                contracts.append((fam, f"pm:{ev.get('id')}", ev_day, "pm", p))
    # Polymarket 2024 presidential winner (closed-markets month of the election)
    if _has(archive, "polymarket-closed-markets-2024-11"):
        d3 = three_before("2024-11-05")
        for r in _rows(archive, "polymarket-closed-markets-2024-11"):
            v = r["value"]
            evs = v.get("events") or []
            if not any(str(e.get("slug")) == "presidential-election-winner-2024" for e in evs if isinstance(e, dict)):
                continue
            if _outcome_of_market(v) is None or d3 is None:
                continue
            cut = _cutoff_ts(d3) + 60
            q = [x for x in pm_daily.get(str(v.get("id")), []) if x[0] <= cut and x[0] >= cut - 10 * 86400]
            if q and 0 < q[-1][1] < 1:
                contracts.append(("election", "pm:presidential-election-winner-2024", "2024-11-05", "pm", q[-1][1]))
    # per event: max U (primary) and mean U (variant); per date: mean over events
    by_event = defaultdict(list)
    for fam, ek, day, venue, p in contracts:
        by_event[(fam, ek, day)].append(p * (1 - p))
    by_date = defaultdict(lambda: {"max": [], "mean": [], "fams": set(), "venues": set()})
    for (fam, ek, day), us in by_event.items():
        by_date[day]["max"].append(max(us))
        by_date[day]["mean"].append(float(np.mean(us)))
        by_date[day]["fams"].add(fam)
        by_date[day]["venues"].add(ek.split(":")[0])
    dates = sorted(by_date)
    U_max = np.array([float(np.mean(by_date[d]["max"])) for d in dates])
    U_mean = np.array([float(np.mean(by_date[d]["mean"])) for d in dates])
    exit_off = [1 if by_date[d]["fams"] == {"election"} else 0 for d in dates]
    # ---- SPY and the other assets ----
    primary = event_regression(dates, U_max, sessions, spy, exit_off)
    variants = {"all_contract_mean_U": event_regression(dates, U_mean, sessions, spy, exit_off)}
    fed = [i for i, d in enumerate(dates) if "fomc" in by_date[d]["fams"]]
    nofed = [i for i, d in enumerate(dates) if "fomc" not in by_date[d]["fams"]]
    for lab, sel in (("fed_only", fed), ("exclude_fomc", nofed)):
        if len(sel) >= 8:
            variants[lab] = event_regression([dates[i] for i in sel], U_max[sel], sessions, spy, [exit_off[i] for i in sel], n_boot=N_BOOT // 2)
        else:
            variants[lab] = {"n": len(sel)}
    for lab, b in (("TLT", TLT_B), ("GLD", GLD_B)):
        if _has(archive, b):
            dd, cc = _daily_close(archive, b)
            variants[lab] = event_regression(dates, U_max, dd, cc, exit_off, n_boot=N_BOOT // 2)
    if _has(archive, BTC_B):
        dd, cc = _daily_close(archive, BTC_B)
        variants["BTC"] = event_regression(dates, U_max, dd, cc, exit_off, n_boot=N_BOOT // 2)
    uncond = None
    if primary.get("n"):
        rr = np.array(primary["returns"])
        cs = cluster_stud(rr, primary["dates"], N_BOOT // 2)
        uncond = {"mean": cs["est"], "ci": cs["ci"], "p": cs.get("p")}
    fam_p = [primary.get("slope", {}).get("p_two")] + [variants.get(k, {}).get("slope", {}).get("p_two") for k in ("fed_only", "exclude_fomc", "TLT", "GLD", "BTC")]
    holm = holm_adjusted(fam_p, 0)
    n = primary.get("n", 0)
    sl = primary.get("slope", {})
    h1, h2 = primary.get("halves", {}).get("first", {}), primary.get("halves", {}).get("second", {})
    plc = primary.get("placebo", {})
    crit = []
    p2 = sl.get("p_two")
    crit.append((f"slope of the 2-session SPY return on U > 0 with date-clustered two-sided p < 0.05: slope {_s(sl.get('slope'), 4)} "
                 f"(s.e. {_f(sl.get('se'), 4)}, studentized bootstrap {_ci_txt(sl.get('ci'), 4)}, percentile {_ci_txt(sl.get('ci_pct'), 4)}, "
                 f"p {_f(p2)}; one-sided {_f(sl.get('p_one'))}; Holm over 6 variants {_f(holm)})",
                 None if p2 is None or sl.get("slope") is None else (sl["slope"] > 0 and p2 < 0.05),
                 sl.get("ci", [None, None])[1] is not None and sl["ci"][1] < 0))
    s1, s2 = h1.get("slope"), h2.get("slope")
    c1, c2 = h1.get("ci") or [None, None], h2.get("ci") or [None, None]
    opposite = (None not in c1 and None not in c2) and ((c1[1] < 0 < c2[0]) or (c2[1] < 0 < c1[0]))
    crit.append((f"same sign in both halves (2021-07..2022 n={h1.get('n', 0)}: slope {_s(s1, 4)} {_ci_txt(c1, 4)}; 2023-2026 n={h2.get('n', 0)}: "
                 f"{_s(s2, 4)} {_ci_txt(c2, 4)}; no venue has 2020 or 2021 H1 data)",
                 None if s1 is None or s2 is None else (s1 > 0) == (s2 > 0), bool(opposite)))
    pp = plc.get("p_two")
    crit.append((f"placebo slope indistinguishable from 0 (U on random non-event 2-session windows, {plc.get('draws', 0)} draws pooled): "
                 f"slope {_s(plc.get('slope'), 4)}, {_ci_txt(plc.get('ci'), 4)}, date-clustered p {_f(pp)} > 0.05",
                 None if pp is None else pp > 0.05, plc.get("ci99") is not None and (plc["ci99"][0] > 0 or plc["ci99"][1] < 0)))
    verdict, why = _decide(crit, n, 60, "event dates")
    fam_counts = Counter(f for d in dates for f in by_date[d]["fams"])
    reason = (f"frozen tagging: Kalshi {have_k} + PRES-2024, Polymarket FOMC / CPI events + the 2024 winner market; {len(contracts)} contracts "
              f"({dict(Counter(c[3] for c in contracts))}), {len(by_event)} events, {n} distinct event dates {dates[0] if dates else 'n/a'}.."
              f"{dates[-1] if dates else 'n/a'} (families {dict(fam_counts)}); U = max p(1-p) per event three sessions before "
              f"(mean U {_f(primary.get('u_mean'))}), SPY close(D-2) -> close(D) (election: D+1), mean {_s((primary.get('mean_return') or 0) * 100, 3)}%. "
              f"Slope {_s(sl.get('slope'), 4)} per unit U (p {_f(p2)}); halves {_s(s1, 4)} / {_s(s2, 4)}; placebo {_s(plc.get('slope'), 4)} (p {_f(pp)}). "
              f"Variants: all-contract-mean U slope {_s(variants['all_contract_mean_U'].get('slope', {}).get('slope'), 4)}; Fed only "
              f"{_s(variants.get('fed_only', {}).get('slope', {}).get('slope'), 4)}; ex-FOMC {_s(variants.get('exclude_fomc', {}).get('slope', {}).get('slope'), 4)}; "
              f"TLT {_s(variants.get('TLT', {}).get('slope', {}).get('slope'), 4)}; GLD {_s(variants.get('GLD', {}).get('slope', {}).get('slope'), 4)}; "
              f"BTC {_s(variants.get('BTC', {}).get('slope', {}).get('slope'), 4)}; unconditional pre-event mean "
              f"{_s((uncond or {}).get('mean', 0) * 100 if uncond else None, 3)}%. Costs (1-2 bp a round trip) do not enter a slope — {why}")
    stat = {"n_dates": n, "n_events": len(by_event), "n_contracts": len(contracts), "families": dict(fam_counts), "venues": dict(Counter(c[3] for c in contracts)),
            "primary": {k: v for k, v in primary.items() if k not in ("dates", "returns", "u")}, "variants": {k: {kk: vv for kk, vv in v.items() if kk not in ("dates", "returns", "u")} for k, v in variants.items()},
            "unconditional": uncond, "holm_primary_p": holm, "window": [dates[0] if dates else None, dates[-1] if dates else None],
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "event-driven windows on the families' calendars: no grid phase"}
    return _out(stat, n, verdict, reason)


# ====================================================================================================== T-360 ==

def implied_q(k: float, N: float, sigma: float) -> float:
    """Nowcast-implied P(print > k) for a one-decimal print: 1 - Phi((k + 0.05 - N) / sigma)."""
    return 1.0 - norm_cdf((k + 0.05 - N) / sigma) if sigma > 0 else (1.0 if N > k + 0.05 else 0.0)


def _prev_weekday(day: str) -> str:
    d = date.fromisoformat(day) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def nowcast_table(rows: Sequence[dict], series: str) -> tuple:
    """({target: {label_date: value}} nowcasts, {target: (release_label, actual)}) for a Cleveland Fed monthly series."""
    nc, act = defaultdict(dict), {}
    for r in rows:
        v = r.get("value") or {}
        if v.get("file") != "month":
            continue
        x = _num(v.get("value"))
        if x is None:
            continue
        if v.get("series") == series:
            nc[v["target"]][v["label_date"]] = x
        elif v.get("series") == "Actual " + series:
            act[v["target"]] = (v["label_date"], x)
    return dict(nc), act


def nowcast_sigma(nc: dict, act: dict, before_release: str, min_n: int = 24) -> Optional[float]:
    """RMSE of the previous-weekday nowcast against the print over releases strictly before ``before_release``."""
    errs = []
    for tgt, (rel, a) in act.items():
        if rel >= before_release:
            continue
        labels = nc.get(tgt) or {}
        d1 = _prev_weekday(rel)
        cand = [l for l in labels if l <= d1]
        if not cand:
            continue
        errs.append(labels[max(cand)] - a)
    if len(errs) < min_n:
        return None
    return float(math.sqrt(np.mean(np.square(errs))))


def day_before_nowcast(nc: dict, target: str, release: str) -> Optional[tuple]:
    """(label_date, value) of the latest nowcast labelled on or before the previous weekday of ``release``."""
    labels = nc.get(target) or {}
    d1 = _prev_weekday(release)
    cand = [l for l in labels if l <= d1]
    if not cand:
        return None
    l = max(cand)
    return l, labels[l]


def cpi_market_target(ticker: str) -> Optional[str]:
    """Reference month 'YYYY-MM' of a KXCPI-style ticker (CPI-21JUN-T0.6, KXCPI-26SEP-T0.7, CPICORE-22JUN-T0.1)."""
    m = re.search(r"-(\d{2})([A-Z]{3})(?:\d{2})?-", str(ticker or ""))
    if not m:
        return None
    mon = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}.get(m.group(2))
    return f"20{m.group(1)}-{mon:02d}" if mon else None


def bar_quote(cands: Sequence[tuple], bar_ts: int, max_age: int = 7 * 86400) -> Optional[tuple]:
    """(bid, ask) of the candle ending at ``bar_ts``, else the latest earlier candle within ``max_age`` (forward fill)."""
    q = [c for c in cands if c[0] <= bar_ts and c[0] >= bar_ts - max_age]
    if not q:
        return None
    _, bid, ask = max(q)
    return (bid, ask) if _quote_ok(bid, ask) else None


def cpi_trades(markets: Sequence[dict], candles: dict, release_days: Sequence[str], nc: dict, act: dict, edge: float = 0.10,
               rule: str = "nowcast", fee_in_threshold: bool = False) -> dict:
    """T-360 trades. ``markets``: Kalshi settled rows ({ticker, close_time, result, floor_strike, open_time}); ``candles``:
    {ticker: [(end_ts, bid, ask)]}; ``rule``: 'nowcast' (the claim) or 'favourite' (market-only: buy the side above 0.5).
    Entry as the claim words it: q - ask > ``edge`` (or (1 - q) - no_ask > edge); the Kalshi fee 0.07 x P(1-P) is charged
    in the P&L only. ``fee_in_threshold`` adds the fee to the threshold (a reported variant, not the claim).
    Returns {trades: [{release, ticker, side, price, mid, win, net_cents}], releases: {release: [...]}, skipped: Counter}."""
    out, skipped = [], Counter()
    rel_sorted = sorted(release_days)
    by_rel = defaultdict(list)
    for m in markets:
        if str(m.get("result") or "").lower() not in ("yes", "no"):
            skipped["unresolved"] += 1
            continue
        close_day = str(m.get("close_time") or "")[:10]
        j = bisect.bisect_left(rel_sorted, close_day)
        if j >= len(rel_sorted) or (date.fromisoformat(rel_sorted[j]) - date.fromisoformat(close_day)).days > 3:
            skipped["no_release"] += 1
            continue
        by_rel[rel_sorted[j]].append(m)
    for rel, ms in sorted(by_rel.items()):
        sigma = nowcast_sigma(nc, act, rel) if rule == "nowcast" else None
        d1 = _prev_weekday(rel)
        dd = date.fromisoformat(d1)
        bar = int(datetime(dd.year, dd.month, dd.day, 16, tzinfo=ET).timestamp())
        for m in ms:
            k = _num(m.get("floor_strike"))
            if k is None:
                k = _ticker_strike(m.get("ticker"))
            if k is None:
                skipped["no_strike"] += 1
                continue
            open_ts = _ts(m.get("open_time"))
            if open_ts is not None and open_ts > bar:
                skipped["not_open"] += 1
                continue
            q = bar_quote(candles.get(m["ticker"], []), bar)
            if q is None:
                skipped["no_quote"] += 1
                continue
            bid, ask = q
            no_ask = 1.0 - bid
            mid = (bid + ask) / 2
            win_yes = str(m["result"]).lower() == "yes"
            if rule == "nowcast":
                tgt = cpi_market_target(m["ticker"])
                nv = day_before_nowcast(nc, tgt, rel) if tgt else None
                if nv is None or sigma is None:
                    skipped["no_nowcast"] += 1
                    continue
                qk = implied_q(k, nv[1], sigma)
                f_yes = KALSHI_FEE * ask * (1 - ask) if fee_in_threshold else 0.0
                f_no = KALSHI_FEE * no_ask * (1 - no_ask) if fee_in_threshold else 0.0
                if qk - ask > edge + f_yes:
                    side, price = "yes", ask
                elif (1 - qk) - no_ask > edge + f_no:
                    side, price = "no", no_ask
                else:
                    continue
                extra = {"q": qk, "nowcast": nv[1], "nowcast_label": nv[0], "sigma": sigma}
            else:
                if mid > 0.5:
                    side, price = "yes", ask
                elif mid < 0.5:
                    side, price = "no", no_ask
                else:
                    continue
                extra = {}
            fee = KALSHI_FEE * price * (1 - price)
            win = win_yes if side == "yes" else (not win_yes)
            net = 100.0 * ((1.0 if win else 0.0) - price - fee)
            out.append({"release": rel, "ticker": m["ticker"], "side": side, "price": price, "mid": mid if side == "yes" else 1 - mid,
                        "fee": fee, "win": bool(win), "net_cents": net, "strike": k, **extra})
    rel_map = defaultdict(list)
    for t in out:
        rel_map[t["release"]].append(t)
    return {"trades": out, "releases": dict(rel_map), "skipped": dict(skipped), "n_releases_total": len(by_rel)}


def release_stat(trades: Sequence[dict]) -> Optional[float]:
    """Mean over releases of the per-release mean net P&L (cents)."""
    rel = defaultdict(list)
    for t in trades:
        rel[t["release"]].append(t["net_cents"])
    if not rel:
        return None
    return float(np.mean([np.mean(v) for v in rel.values()]))


def parametric_null(trades: Sequence[dict], n_boot: int = N_BOOT, seed: int = SEED, comonotone: bool = False) -> dict:
    """The trial's parametric null: each contract's outcome ~ Bernoulli(mid of the bought side), release-clustered,
    statistic = mean of per-release mean net P&L; one-sided p = P(null stat >= observed). ``comonotone`` draws one latent
    uniform per release (thresholds of one print move together: a reported variant)."""
    obs = release_stat(trades)
    if obs is None or not trades:
        return {"p": None}
    rels = sorted({t["release"] for t in trades})
    rix = {r: i for i, r in enumerate(rels)}
    lab = np.array([rix[t["release"]] for t in trades])
    mid = np.array([min(max(t["mid"], 0.0), 1.0) for t in trades])
    price = np.array([t["price"] for t in trades])
    fee = np.array([t["fee"] for t in trades])
    cnt = np.bincount(lab, minlength=len(rels)).astype(float)
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        if comonotone:
            u = rng.random(len(rels))[lab]
            win = (u < mid).astype(float)
        else:
            win = (rng.random(len(trades)) < mid).astype(float)
        net = 100.0 * (win - price - fee)
        stats[b] = np.mean(np.bincount(lab, weights=net, minlength=len(rels)) / cnt)
    return {"p": float((np.sum(stats >= obs) + 1) / (n_boot + 1)), "null_mean": float(stats.mean()), "observed": obs,
            "null_q95": float(np.quantile(stats, 0.95))}


def release_bootstrap(trades: Sequence[dict], n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Release-level bootstrap of the realised per-release mean P&L (studentized; p for H0: mean <= 0)."""
    rel = defaultdict(list)
    for t in trades:
        rel[t["release"]].append(t["net_cents"])
    if len(rel) < 4:
        return {"p": None, "mean": release_stat(trades), "n_releases": len(rel)}
    x = np.array([np.mean(v) for v in rel.values()])
    cs = cluster_stud(x, list(rel.keys()), n_boot, seed)
    return {"p": cs.get("p"), "mean": cs["est"], "ci": cs["ci"], "ci90": cs["ci90"], "n_releases": len(rel)}


def b6c_pmxv_kalshi_cpi_nowcast(archive):
    """T-360."""
    miss = _missing(archive, [CLE_B, CPI_REL_B, KS + "KXCPI", KH + "KXCPI"])
    if miss:
        return miss
    cle = _rows(archive, CLE_B)
    nc_h, act_h = nowcast_table(cle, "CPI Inflation")
    nc_c, act_c = nowcast_table(cle, "Core CPI Inflation")
    rel_days = [r["value"]["day"] for r in _rows(archive, CPI_REL_B) if r["value"].get("day", "") >= "2021-06-01"]
    rel_gap = {r["value"]["day"]: r["value"].get("days_since_previous") for r in _rows(archive, CPI_REL_B)}

    def load_series(s: str) -> tuple:
        ms = [r["value"] for r in _rows(archive, KS + s)]
        cands = defaultdict(list)
        for r in archive.load(KH + s):
            v = r["value"]
            c = v.get("candle") or {}
            end = _num(c.get("end_period_ts"))
            if end is not None:
                bid, ask, _ = kalshi_quote(c)
                cands[v["ticker"]].append((int(end), bid, ask))
        return ms, dict(cands)

    ms_h, cd_h = load_series("KXCPI")
    primary = cpi_trades(ms_h, cd_h, rel_days, nc_h, act_h, 0.10)
    variants = {"headline_edge10": primary, "headline_edge5": cpi_trades(ms_h, cd_h, rel_days, nc_h, act_h, 0.05),
                "headline_edge15": cpi_trades(ms_h, cd_h, rel_days, nc_h, act_h, 0.15),
                "market_only_favourite": cpi_trades(ms_h, cd_h, rel_days, nc_h, act_h, 0.10, rule="favourite")}
    # reported only (not one of the trial's 5 variants): the fee-inclusive entry threshold q - ask > 0.10 + 0.07 P(1-P)
    fee_thr = cpi_trades(ms_h, cd_h, rel_days, nc_h, act_h, 0.10, fee_in_threshold=True)
    if _has(archive, KS + "KXCPICORE") and _has(archive, KH + "KXCPICORE"):
        ms_c, cd_c = load_series("KXCPICORE")
        variants["core_edge10"] = cpi_trades(ms_c, cd_c, rel_days, nc_c, act_c, 0.10)
    else:
        variants["core_edge10"] = {"trades": [], "releases": {}, "skipped": {"bundle_missing": 1}}
    payroll = None
    if _has(archive, KS + "KXPAYROLLS") and _has(archive, KH + "KXPAYROLLS") and _has(archive, EMP_REL_B):
        ms_p, cd_p = load_series("KXPAYROLLS")
        emp_days = [r["value"]["day"] for r in _rows(archive, EMP_REL_B) if r["value"].get("day", "") >= "2023-01-01"]
        pr = cpi_trades(ms_p, cd_p, emp_days, {}, {}, 0.10, rule="favourite")
        payroll = {"n_trades": len(pr["trades"]), "n_releases": len(pr["releases"]), "mean": release_stat(pr["trades"]),
                   "parametric": parametric_null(pr["trades"], N_BOOT // 2)}
    tests = {}
    for name, v in variants.items():
        tr = v["trades"]
        par = parametric_null(tr)
        rb = release_bootstrap(tr)
        tests[name] = {"n_trades": len(tr), "n_releases": len(v["releases"]), "mean": release_stat(tr), "parametric": par, "release_boot": rb,
                       "p_max": max([p for p in (par.get("p"), rb.get("p")) if p is not None], default=None),
                       "skipped": v.get("skipped"), "hit_rate": float(np.mean([t["win"] for t in tr])) if tr else None,
                       "mean_entry": float(np.mean([t["price"] for t in tr])) if tr else None}
    T = tests["headline_edge10"]
    tr = primary["trades"]
    n = len(primary["releases"])
    ft_rb = release_bootstrap(fee_thr["trades"])
    fee_thr_stat = {"n_trades": len(fee_thr["trades"]), "n_releases": len(fee_thr["releases"]), "mean": release_stat(fee_thr["trades"]),
                    "release_boot_p": ft_rb.get("p"), "release_boot_ci": ft_rb.get("ci"), "parametric_p": parametric_null(fee_thr["trades"]).get("p")}
    comon = parametric_null(tr, comonotone=True)
    first = [t for t in tr if t["release"] < "2024-01-01"]
    second = [t for t in tr if t["release"] >= "2024-01-01"]
    m1, m2 = release_stat(first), release_stat(second)
    order = ["headline_edge10", "core_edge10", "headline_edge5", "headline_edge15", "market_only_favourite"]
    holm = holm_adjusted([tests[k]["p_max"] for k in order], 0)
    delayed = sorted(r for r in primary["releases"] if (rel_gap.get(r) or 0) > 40)
    crit = []
    pp, pb = T["parametric"].get("p"), T["release_boot"].get("p")
    rows = [(f"parametric Bernoulli(mid) null p {_f(pp)}", None if pp is None else pp < 0.05, False),
            (f"release-level bootstrap p {_f(pb)} ({_ci_txt(T['release_boot'].get('ci'))})", None if pb is None else pb < 0.05,
             T["release_boot"].get("ci", [None, None])[1] is not None and T["release_boot"]["ci"][1] < 0)]
    crit.append(all_constructions(rows, f"mean net P&L per contract (release-averaged) {_s(T['mean'])} cents over {len(tr)} contracts in {n} releases > 0 with p < 0.05"))
    crit.append((f"both halves positive: 2021-2023 {_s(m1)} cents ({len({t['release'] for t in first})} releases), 2024-2026 {_s(m2)} "
                 f"({len({t['release'] for t in second})} releases)", None if m1 is None or m2 is None else (m1 > 0 and m2 > 0), False))
    crit.append((f"Holm over 5 variants: adjusted primary p {_f(holm)} < 0.05 (variant p: " +
                 ", ".join(f"{k} {_f(tests[k]['p_max'])}" for k in order) + ")", None if holm is None else holm < 0.05, False))
    crit.append(("nowcast vintages real-time (point in time): the archived history is the current vintage (vintage_verified false); dated "
                 "snapshots start 2026-10-15 and cover no release's day-before", None, False))
    verdict, why = _decide(crit, n, 40, "releases with a qualifying trade")
    reason = (f"Kalshi KXCPI: {len(ms_h)} settled thresholds over {primary.get('n_releases_total', 0)} CPI releases since 2021-07 (skipped "
              f"{primary.get('skipped')}); nowcast N = Cleveland Fed CPI MoM labelled the previous weekday (12:00 ET), sigma = expanding RMSE "
              f"of the day-before nowcast vs the print over prior releases from 2013-07 (last {_f(tr[-1]['sigma'] if tr else None)} pp); q(k) = "
              f"1 - Phi((k + 0.05 - N)/sigma) vs the 16:00 ET D-1 ask (forward-filled, spread <= 10 points); entry when the edge exceeds 10 pp as "
              f"worded, the 0.07 P(1-P) fee charged in the P&L (fee-inclusive threshold reported as a variant: {fee_thr_stat['n_trades']} contracts in "
              f"{fee_thr_stat['n_releases']} releases, mean {_s(fee_thr_stat['mean'])} cents, release bootstrap p {_f(fee_thr_stat['release_boot_p'])}). "
              f"{len(tr)} contracts in {n} releases (hit rate {_f(T.get('hit_rate'))}, mean entry {_f(T.get('mean_entry'))}): "
              f"release-averaged mean net {_s(T['mean'])} cents; parametric p {_f(pp)} (comonotone-print variant p {_f(comon.get('p'))}), "
              f"release bootstrap p {_f(pb)}; halves {_s(m1)} / {_s(m2)}; Holm-adjusted {_f(holm)}; variants: core {_s(tests['core_edge10']['mean'])} "
              f"({tests['core_edge10']['n_trades']}), edge 5 {_s(tests['headline_edge5']['mean'])} ({tests['headline_edge5']['n_trades']}), edge 15 "
              f"{_s(tests['headline_edge15']['mean'])} ({tests['headline_edge15']['n_trades']}), market-only favourite {_s(tests['market_only_favourite']['mean'])} "
              f"({tests['market_only_favourite']['n_trades']}); payrolls market-only {_s((payroll or {}).get('mean'))} ({(payroll or {}).get('n_trades', 0)}); "
              f"delayed releases (> 40 days) {delayed} — {why}")
    stat = {"n_releases": n, "n_trades": len(tr), "tests": tests, "comonotone_null": comon, "halves": {"2021_2023": m1, "2024_2026": m2},
            "holm_primary_p": holm, "payrolls": payroll, "delayed_releases": delayed, "sigma_last": tr[-1]["sigma"] if tr else None,
            "entry_rule": "q - ask > 0.10 (or (1 - q) - no_ask > 0.10) as worded; fee 0.07 P(1-P) in the P&L only",
            "fee_in_threshold_variant": fee_thr_stat,
            "per_release": {r: float(np.mean([t["net_cents"] for t in v])) for r, v in primary["releases"].items()},
            "vintage": {"history_vintage_verified": False, "snapshots_from": "2026-10-15"},
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "event-driven (the 16:00 ET bar before each release): no grid phase"}
    return _out(stat, n, verdict, reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_pmxv_cross_venue_convergence": b6c_pmxv_cross_venue_convergence,
    "b6c_pmxv_leadlag": b6c_pmxv_leadlag,
    "b6c_pmxv_pm_vs_deribit_digital": b6c_pmxv_pm_vs_deribit_digital,
    "b6c_pmxv_event_uncertainty_premium": b6c_pmxv_event_uncertainty_premium,
    "b6c_pmxv_kalshi_cpi_nowcast": b6c_pmxv_kalshi_cpi_nowcast,
}

THEORY_MAP = {
    "T-336": "b6c_pmxv_cross_venue_convergence",
    "T-409": "b6c_pmxv_leadlag",
    "T-337": "b6c_pmxv_pm_vs_deribit_digital",
    "T-358": "b6c_pmxv_event_uncertainty_premium",
    "T-360": "b6c_pmxv_kalshi_cpi_nowcast",
}
