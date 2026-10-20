"""
Batch 6c, group ``pmmicro``: three Kalshi microstructure claims on the trade prints and hourly bid/ask candles of
``mandel.data.pm_history`` (kalshi-trades-<S>, kalshi-candles-hourly-<S>, kalshi-settled-markets-<S>, kalshi-fetch-log),
with the Polymarket replications on polymarket-price-history-hourly-<M> and polymarket-volume-hourly-<M>.
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-408  hourly reversal. Signal at the close of hour H: d = mid_H - mid_{H-3} from the forward-filled hourly yes_bid /
           yes_ask closes (mid = (bid + ask) / 2); |d| >= 5 cents and the quoted spread <= theta / 2 (the library rule);
           the book at H - 3 must be a mid too (a valid touch with spread <= theta / 2: an empty, one-sided or wide book
           appearing is not a move; the dropped signals are counted and the any-valid-touch (<= 10 cents) reading is
           reported); fade: d < 0 buys YES at the ask at H, d > 0 buys NO at 1 - bid at H (the fill uses the ask of the
           same candle close as the signal, never the mid: rule 12, one information set); exit after 3 hours at the bid
           (YES: bid, NO: 1 - ask) or at settlement when the market closes first; taker fee 0.07 x P(1-P) per contract
           each way (none at settlement). Exit marks (``exit_marks``): the grid's last hour is the hour containing the
           close and its candle closes on the post-close empty book (bid 0 / ask 1 in 3,264 of 4,010 pool markets with
           a close-hour candle), so an exit landing on the close hour or later settles at the result; a mid-life exit
           into an invalid book (bid 0, ask 1 or spread > 10 cents: nothing to trade against) holds to the next valid
           quote within 48 h, else settles; the counts are reported. Net return per trade in cents per contract; the
           fractional return (net / entry cost, fixed dollars per trade) feeds Sharpe, DSR and PBO. Declared grid, 108
           cells: h in {1, 3, 6} x theta in {3, 5, 8} cents x exit in {h, h/2 (max(1, h // 2) at hourly granularity), 50%
           retrace within h} x final-24h exclusion {off, on} x volume > 0 at the signal hour {off, on}; headline = h 3,
           theta 5, exit h, both off. At h = 1 the three exit rules coincide, so the 108 declared cells are 84 distinct
           rules: PBO runs on the 84 distinct columns and DSR counts 84 + 21 = 105 trials (the declared 108 + 21 = 129
           is reported as the upper bound).
           Walk forward: markets sorted by open_time, the first half calibrates (reported: its best cell and that cell's
           out-of-sample reading), markets opening within 7 days after the split are embargoed, the rest are out of
           sample; n = out-of-sample headline trades (min_n 3,000). Pass: bootstrap p < 0.01 for mean net > 0 on the
           out-of-sample headline trades under BOTH constructions (the trial's: a stationary block bootstrap of the
           hourly mid changes within market, mean block 24 h, with the hour's spread and volume attached, the rule re-run
           on each resampled path, p = the share of bootstrap means <= 0, the named 2,000 draws; the mid changes are those
           of the valid-book mid carried over invalid hours (a jump into an empty book's 0.495 is not a mid change: 43%
           of out-of-sample market-hours quote an invalid book and such jumps were 68% of the raw |dmid|), and a trade
           settling in a resampled path settles at Bernoulli(the path's final mid), the fair value under the martingale
           null, not at the real market's outcome, which is unrelated to the resampled entry; and a market-clustered
           studentized bootstrap of the trade returns), PBO < 0.2 over the cells (CSCV on the hourly cell P&L matrix,
           all markets), DSR >= 0.95 of the out-of-sample headline Sharpe over the trials (the trial's '21 daily rules'
           counted), and the Polymarket replication (the same rule on the hourly CLOB price of the archived resolved
           markets, entry at p + the assumed half-spread, exit at p - it, the Gamma fee flag) with the same sign. Crypto
           (KXBTCD) is a separate bucket (library rule), reported next to the headline pool; KXMVE combos were never
           fetched. Zero-volume / forward-filled signal hours are counted (flagged, kept).
  * T-411  market making replay. Each hour P the quotes for the period [P, P + 1 h) are the touch of the candle closed
           at P (forward-filled): bid = yes_bid, ask = yes_ask, widened one tick each when the spread is under 2 cents,
           skewed by the Avellaneda-Stoikov reservation shift -gamma x sigma_day^2 x tau x q (q = inventory / cap in
           [-1, 1], sigma_day^2 = 24 x the variance of the last 24 hourly mid changes, tau = min(hours to close, 24) / 24
           days) rounded to whole ticks and clipped to one tick. Four pull rules: (a) the trailing 60-minute markout of
           own fills (the fills of period P - 2, whose marks are known at P) worse than m cents a contract pulls both
           sides; (b) last-hour taker-flow imbalance |F| > 0.4 pulls the side being hit; (c) a scheduled event within
           one hour of the period pulls both sides (FOMC decisions 14:00 ET from fomc-meetings, CPI / employment / GDP
           releases 08:30 ET from the macro-release bundles; game starts are NOT in the archived Kalshi metadata, so
           that part of rule (c) is not applied: fewer pulls = more toxic fills kept = conservative for the claim);
           (d) under 48 hours to close no quotes. Fills only on trade-through prints: a public print whose taker sold
           YES (taker_outcome_side 'no') strictly below our bid fills our bid, one whose taker bought YES strictly above
           our ask fills our ask, at our price, for the print's size up to the inventory room at the period start
           (proportional when the period's through-size exceeds the room). Per fill the P&L is s x (fill - mid_{+60m})
           x size = half the realised spread 2 s (fill - mid_{+60m}), mid_{+60m} being the close of the first candle that
           closes at least 60 minutes after the print (the candle ending at P + 2) when that book is valid (bid > 0,
           ask < 1, spread <= 10 cents), else the first valid mid after it within 48 h, else the settlement value (also
           when the market has closed; the re-marked fills are counted), minus the maker fee. Daily net P&L per
           market-day = the day's fills' P&L (0 on a quoted day without
           fills); market-day = a UTC day with at least one quoting period. Declared grid, 27 cells: gamma {0.1, 0.5,
           1} x m {1, 2, 3} cents x cap {50, 200, 500} contracts. Walk forward: the first half of markets by open_time
           picks the cell (best mean daily net P&L), the second half is out of sample; n = out-of-sample market-days
           (min_n 1,500). Pass: mean daily net > 0 with the market-clustered studentized bootstrap p < 0.01, positive in
           each of the 3 largest categories (by out-of-sample market-days), DSR >= 0.95 over 27 cells, and the
           paper-trading criterion (live quoting with real fills, a forward test) which no archive can supply: None,
           with the replay half (the mean realised spread per fill) reported. Rewards and rebates excluded.
  * T-463  signed trade-flow imbalance. F over the prints of the hour ending at H = (contracts taken on YES - taken on
           NO) / all contracts, at least 20 prints; |F| > 0.5 buys the taken side at the hour close H (the ask of the
           candle closed at H, which is what the next candle opens at: flow up to the hour close, fill after it; the
           next candle's closing ask is the reported 1-hour-delay sensitivity), exits after 6 hours at the bid or at
           settlement (``exit_marks``: an exit on or after the close hour settles at the result, an exit into an invalid
           book holds to the next valid quote within 48 h, else settles; counted, with the cost decomposition of the
           quote-exit trades); mid at H within [0.05, 0.95] and a valid touch (bid > 0, ask < 1, spread <= 10 cents); taker fee
           0.07 x P(1-P) each way, the spread paid by crossing. Declared grid, 16 cells: f {0.3, 0.5} x h {1, 6} x
           {follow, fade} x {Kalshi, Polymarket}; the Polymarket cells use data-api taker flow (polymarket-volume-hourly:
           YES-direction = YES buys + NO sells) and the hourly CLOB price with the assumed half-spread and the Gamma fee
           flag, where both exist. Walk forward by open_time with a 24-hour embargo; n = out-of-sample headline trades
           (min_n 3,000). Pass: mean net > 0 with p < 0.01 under BOTH named constructions (the trial's null: F permuted
           across the qualifying hours within market; the market-clustered studentized bootstrap), DSR >= 0.95 over 16
           cells, PBO < 0.3 (CSCV over the non-empty cells' hourly P&L). Crypto (KXBTCD) is a separate bucket; the
           final 48 hours are reported separately.

Conventions
  * Data. Every bundle through ``archive.load``; the event-calendar, book-snapshot, legacy Polymarket and event bundles
    are optional (probed). Candles use either field naming (close / close_dollars, volume / volume_fp); hours without a
    candle are forward-filled (the book did not change); the grid runs from a market's first candle to its close hour,
    whose candle closes on the post-close book: no entry there, and an exit or markout landing on it settles at the
    result (``exit_marks``). An invalid book (bid 0, ask 1 or spread > 10 cents) is never traded against or used as a mid.
  * Print coverage (kalshi-fetch-log). A market whose trade paging hit the page cap holds every print from
    ``complete_from`` on only, and a market spanning the 2026-08-16 live / historical cutoff whose live route was capped
    never read the historical route (an undeclared hole between the cutoff and complete_from): for both, only the hours
    starting at or after complete_from are used, and the counts are flagged in ``stat['coverage']``.
  * Fees (rule 9). The CURRENT published Kalshi schedule, stated as such because point-in-time schedules are not
    archived: taker 0.07 x C x P(1-P) (the claims' own formula), maker 0.0175 x C x P(1-P) applied to every maker fill
    (Kalshi charges it on some series only and the per-series list is not archived either: applying it everywhere is
    conservative for T-411; the zero-maker-fee variant is reported). The published rounding (up to the next cent per
    order) is not applied: it is at most one cent per order of many contracts. Polymarket: the Gamma per-market fee
    flag (crypto 0.07, economics 0.05, sports 0.04 x p(1-p), 0 when disabled or unknown) plus the assumed half-spread
    (median two-sided YES book of polymarket-books-snapshot, else 1 cent): no historical Polymarket book exists.
  * Intervals (rule 6). Market-clustered studentized bootstraps (``batch6c_pub.cluster_stud``); the trial-named nulls
    (stationary block bootstrap of mid changes, permutation of F) are run as written and a criterion with two named
    constructions passes only when both pass (rule 11, ``all_constructions``). Rule 5: below min_n a failing criterion
    counts only when decisive (the market-clustered one-sided p for mean < 0 is itself below the pass's 0.01, and
    every named construction fails decisively); PBO, DSR and sign criteria are never decisive.
  * Rule 10: every entry is signal-driven (a mid move, a flow imbalance, a print through a quote): no grid phase.
Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``.
"""

from __future__ import annotations

import math
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
DAY = 86_400
N_BOOT = 2000                 # cluster bootstrap draws
N_NULL = 2000                 # T-463 permutations (the trial's count)
N_NULL_T408 = 2000            # T-408 stationary-bootstrap draws: the trial's named count (each draw rebuilds ~3M market-hours and re-runs
                              # the rule, ~0.3 s: about ten minutes on the out-of-sample stack)
SEED = 0
EXIT_WAIT_H = 48              # hours an exit into an invalid book waits for the next valid quote before settling at the result
EXIT_AT_K, EXIT_HELD, EXIT_SETTLED_CLOSE, EXIT_SETTLED_NO_QUOTE = 0, 1, 2, 3
EXIT_KIND_NAMES = {EXIT_AT_K: "quote_at_k", EXIT_HELD: "held_to_next_valid_quote", EXIT_SETTLED_CLOSE: "settled_close_hour_or_later",
                   EXIT_SETTLED_NO_QUOTE: "settled_no_valid_quote_within_wait"}

KS = "kalshi-settled-markets-"
KH = "kalshi-candles-hourly-"
KT = "kalshi-trades-"
K_LOG = "kalshi-fetch-log"
PMH = "polymarket-price-history-hourly-"
PMV = "polymarket-volume-hourly-"
PM_LEGACY_B = "polymarket-closed-markets"
BOOKS_B = "polymarket-books-snapshot"
EV_MACRO_B = "polymarket-events-macro"
EV_BTC_B = "polymarket-events-btc-above"
FOMC_B = "fomc-meetings"
CPI_REL_B = "macro-release-cpi"
EMP_REL_B = "macro-release-employment-situation"
GDP_REL_B = "macro-release-gdp"

TAKER_FEE = 0.07              # current published Kalshi taker fee x C x P(1-P)
MAKER_FEE = 0.0175            # current published Kalshi maker fee x C x P(1-P), where charged
FEE_NOTE = ("Kalshi fees: the CURRENT published schedule (taker 0.07 x C x P(1-P); maker 0.0175 x C x P(1-P) where charged, applied to "
            "every fill); point-in-time schedules and the per-series maker-fee list are not archived")
PM_FEE_RATE = {"crypto": 0.07, "economics": 0.05, "sports": 0.04}
PM_HALF_SPREAD_DEFAULT = 0.01
TICK = 0.01
EPS = 1e-6                    # tolerance for strict price comparisons (prices are 4-decimal strings held in float32: ~3e-8 noise)
SPREAD_MAX = 0.10
CRYPTO_SERIES = ("KXBTCD",)
SERIES_CATEGORY = {"KXFEDDECISION": "macro", "KXFED": "macro", "KXCPI": "macro", "KXCPIYOY": "macro", "KXCPICORE": "macro",
                   "KXCPICOREYOY": "macro", "KXPAYROLLS": "macro", "KXU3": "macro", "KXGDP": "macro",
                   "PRES": "election", "POPVOTE": "election",
                   "KXHIGHNY": "weather", "KXHIGHCHI": "weather", "KXHIGHMIA": "weather", "KXHIGHAUS": "weather",
                   "KXNFLGAME": "sports", "KXNBAGAME": "sports", "KXMLBGAME": "sports", "KXNHLGAME": "sports", "KXATPMATCH": "sports",
                   "KXWTAMATCH": "sports", "KXNCAAFGAME": "sports", "KXEPLGAME": "sports", "KXBTCD": "crypto"}

# T-408 grid
T408_H = (1, 3, 6)
T408_THETA = (0.03, 0.05, 0.08)
T408_EXIT = ("h", "half", "retrace")
T408_HEADLINE = (3, 0.05, "h", False, False)
T408_DAILY_RULES = 21
T408_EMBARGO_S = 7 * DAY
# T-411 grid
T411_GAMMA = (0.1, 0.5, 1.0)
T411_M = (0.01, 0.02, 0.03)
T411_CAP = (50.0, 200.0, 500.0)
T411_FLOW_PULL = 0.4
T411_PULL_HOURS = 48
# T-463 grid
T463_F = (0.3, 0.5)
T463_H = (1, 6)
T463_MIN_TRADES = 20
T463_HEADLINE = (0.5, 6, "follow", "kalshi")
T463_EMBARGO_S = DAY

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


def _names(archive, prefix: str) -> list:
    try:
        return sorted(e.name for e in archive.entries() if e.name.startswith(prefix))
    except Exception:
        return []


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _missing_families(archive, prefixes: Sequence[str]):
    """Like ``_missing`` for bundle families (``prefix<S>``): every family needs at least one archived bundle."""
    miss = [p + "<S>" for p in prefixes if not _names(archive, p)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


_DAY_EPOCH: dict = {}


def _ts(s) -> Optional[int]:
    """Unix seconds of an ISO UTC string ('2025-04-01T06:50:20.123Z', '2025-04-01T06:50:20+00:00', '2025-04-01 06:50:20+00')
    or a number. Fast path for the UTC forms the Kalshi bundles use; fromisoformat otherwise."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s)
    if len(s) >= 19 and s[4] == "-" and s[7] == "-" and s[13] == ":" and s[16] == ":" and (s.endswith("Z") or s.endswith("+00:00") or s.endswith("+00")):
        try:
            d = _DAY_EPOCH.get(s[:10])
            if d is None:
                d = int(datetime(int(s[:4]), int(s[5:7]), int(s[8:10]), tzinfo=UTC).timestamp())
                _DAY_EPOCH[s[:10]] = d
            return d + int(s[11:13]) * 3600 + int(s[14:16]) * 60 + int(s[17:19])
        except ValueError:
            pass
    try:
        d = datetime.fromisoformat(s.strip().replace("Z", "+00:00").replace(" ", "T", 1))
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


def _day_str(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).date().isoformat()


def kalshi_quote(candle: dict) -> tuple:
    """(bid, ask, volume) of a raw Kalshi candle under either field naming."""
    def close(side):
        d = candle.get(side) or {}
        return _num(d.get("close", d.get("close_dollars")))
    v = _num(candle.get("volume", candle.get("volume_fp"))) or 0.0
    return close("yes_bid"), close("yes_ask"), v


def kalshi_fee(price, rate: float = TAKER_FEE):
    """Kalshi fee per contract at ``price`` (dollars): rate x P(1-P)."""
    p = np.asarray(price, dtype=float)
    return rate * p * (1.0 - p)


def pm_fee_rate(market: Optional[dict]) -> float:
    if not market or not market.get("feesEnabled"):
        return 0.0
    ft = str(market.get("feeType") or "")
    for k, r in PM_FEE_RATE.items():
        if k in ft:
            return r
    return PM_FEE_RATE["economics"]


def _pm_outcome(m: dict) -> Optional[int]:
    import json
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


# ===================================================================================================== loaders ==

def _series_of_bundle(name: str, prefix: str) -> str:
    """'kalshi-candles-hourly-KXBTCD-2025-01' -> 'KXBTCD'; '...-KXCPI' -> 'KXCPI'."""
    return name[len(prefix):].split("-")[0]


def _kalshi_meta(archive) -> dict:
    """{ticker: {series, cat, open_s, close_s, result (1.0 / 0.0 / nan), vol}} from every kalshi-settled-markets-<S> bundle
    (KXMVE combos excluded; they were never fetched)."""
    def load():
        out = {}
        for n in _names(archive, KS):
            s = _series_of_bundle(n, KS)
            cat = SERIES_CATEGORY.get(s, "other")
            for r in archive.load(n):
                v = r.get("value") or {}
                tk = v.get("ticker")
                if not tk or str(tk).startswith("KXMVE"):
                    continue
                open_s, close_s = _ts(v.get("open_time")), _ts(v.get("close_time"))
                if open_s is None or close_s is None:
                    continue
                res = str(v.get("result") or "").lower()
                out[tk] = {"series": s, "cat": cat, "open_s": open_s, "close_s": close_s,
                           "result": 1.0 if res == "yes" else 0.0 if res == "no" else float("nan"), "vol": _num(v.get("volume_fp")) or 0.0}
        return out
    return _cached(archive, ("meta",), load)


def _kalshi_candles(archive) -> dict:
    """{ticker: (hours int64 sorted unique, bid f32, ask f32, vol f32)} from every kalshi-candles-hourly-<S> bundle; the
    latest row of a ticker-hour wins. hour = end_period_ts // 3600 (a candle is known once its period closed)."""
    def load():
        hs, bs, as_, vs = defaultdict(lambda: array("q")), defaultdict(lambda: array("f")), defaultdict(lambda: array("f")), defaultdict(lambda: array("f"))
        for n in _names(archive, KH):
            for r in archive.load(n):
                v = r.get("value") or {}
                tk = v.get("ticker")
                c = v.get("candle") or {}
                end = _num(c.get("end_period_ts"))
                if not tk or end is None:
                    continue
                bid, ask, vol = kalshi_quote(c)
                if bid is None or ask is None:
                    continue
                hs[tk].append(int(end) // HOUR)
                bs[tk].append(bid)
                as_[tk].append(ask)
                vs[tk].append(vol)
        out = {}
        for tk in hs:
            h = np.frombuffer(hs[tk], dtype=np.int64)
            b = np.frombuffer(bs[tk], dtype=np.float32)
            a = np.frombuffer(as_[tk], dtype=np.float32)
            vv = np.frombuffer(vs[tk], dtype=np.float32)
            order = np.argsort(h, kind="stable")
            h, b, a, vv = h[order], b[order], a[order], vv[order]
            last = np.r_[h[1:] != h[:-1], True]
            out[tk] = (h[last], b[last], a[last], vv[last])
        return out
    return _cached(archive, ("candles",), load)


def _kalshi_trades(archive) -> dict:
    """{ticker: (t int64 seconds sorted, price f32 (YES price), side int8 (+1 taker bought YES, -1 taker bought NO),
    qty f32)} from every kalshi-trades-<S> bundle (streamed into flat buffers: 5.5M prints)."""
    def load():
        codes: dict = {}
        tk_code, ts, px, sd, qt = array("i"), array("q"), array("f"), array("b"), array("f")
        for n in _names(archive, KT):
            for r in archive.load(n):
                v = r.get("value") or {}
                tk = v.get("ticker")
                t = _ts(v.get("created_time")) or _ts(r.get("observed_at"))
                p = _num(v.get("yes_price_dollars"))
                q = _num(v.get("count_fp"))
                if not tk or t is None or p is None or q is None or q <= 0:
                    continue
                side = str(v.get("taker_outcome_side") or v.get("taker_side") or "").lower()
                if side not in ("yes", "no"):
                    continue
                code = codes.get(tk)
                if code is None:
                    code = codes[tk] = len(codes)
                tk_code.append(code)
                ts.append(t)
                px.append(p)
                sd.append(1 if side == "yes" else -1)
                qt.append(q)
        code_a = np.frombuffer(tk_code, dtype=np.int32)
        t_a = np.frombuffer(ts, dtype=np.int64)
        p_a = np.frombuffer(px, dtype=np.float32)
        s_a = np.frombuffer(sd, dtype=np.int8)
        q_a = np.frombuffer(qt, dtype=np.float32)
        order = np.lexsort((t_a, code_a))
        code_a, t_a, p_a, s_a, q_a = code_a[order], t_a[order], p_a[order], s_a[order], q_a[order]
        bounds = np.r_[0, np.flatnonzero(code_a[1:] != code_a[:-1]) + 1, code_a.size]
        inv = {c: tk for tk, c in codes.items()}
        out = {}
        for i in range(bounds.size - 1):
            lo, hi = bounds[i], bounds[i + 1]
            out[inv[int(code_a[lo])]] = (t_a[lo:hi], p_a[lo:hi], s_a[lo:hi], q_a[lo:hi])
        return out
    return _cached(archive, ("trades",), load)


def trade_coverage(log_rows: Sequence[dict]) -> dict:
    """{ticker: {complete, from_s (first second every print is held from; 0 when complete), cutoff_gap}} from the
    kalshi-fetch-log 'trades' rows. A capped route is complete from complete_from on; a market spanning the cutoff whose
    live route was capped (routes_skipped) has the same bound and is flagged ``cutoff_gap``. A capped market without a
    complete_from is unusable (from_s = None)."""
    out = {}
    for r in log_rows:
        v = r.get("value") or {}
        if v.get("product") != "trades" or not v.get("id"):
            continue
        complete = bool(v.get("complete"))
        cf = _ts(v.get("complete_from")) if not complete else 0
        out[str(v["id"])] = {"complete": complete, "from_s": 0 if complete else cf, "cutoff_gap": bool(v.get("routes_skipped"))}
    return out


def _trade_coverage(archive) -> dict:
    def load():
        if not _has(archive, K_LOG):
            return {}
        return trade_coverage(list(archive.load(K_LOG)))
    return _cached(archive, ("coverage",), load)


def _pm_meta(archive) -> dict:
    """{market_id: {fee_rate, outcome}} from the legacy polymarket-closed-markets bundle and the two event bundles."""
    def load():
        out = {}
        if _has(archive, PM_LEGACY_B):
            for r in archive.load(PM_LEGACY_B):
                m = r.get("value") or {}
                if m.get("id") is not None:
                    out[str(m["id"])] = {"fee_rate": pm_fee_rate(m), "outcome": _pm_outcome(m), "legacy": True}
        for b in (EV_MACRO_B, EV_BTC_B):
            if not _has(archive, b):
                continue
            for r in archive.load(b):
                for m in (r.get("value") or {}).get("markets") or []:
                    if m.get("id") is not None and str(m["id"]) not in out:
                        out[str(m["id"])] = {"fee_rate": pm_fee_rate(m), "outcome": _pm_outcome(m), "legacy": False}
        return out
    return _cached(archive, ("pm_meta",), load)


def pm_half_spread(archive) -> tuple:
    if not _has(archive, BOOKS_B):
        return PM_HALF_SPREAD_DEFAULT, "default (no book snapshot archived)"
    hs = []
    for r in archive.load(BOOKS_B):
        yes = ((r.get("value") or {}).get("books") or {}).get("yes") or {}
        bids = [b for b in (_num(x.get("price")) for x in yes.get("bids") or []) if b is not None]
        asks = [a for a in (_num(x.get("price")) for x in yes.get("asks") or []) if a is not None]
        if bids and asks and max(bids) < min(asks):
            hs.append((min(asks) - max(bids)) / 2)
    if len(hs) < 10:
        return PM_HALF_SPREAD_DEFAULT, f"default ({len(hs)} two-sided books)"
    return float(np.median(hs)), f"median of {len(hs)} two-sided YES books in {BOOKS_B}"


def _pm_hourly(archive) -> dict:
    """{market_id: (hours int64 sorted unique, p f32)} from every polymarket-price-history-hourly-<M> bundle (hour = t //
    3600; the latest point of a market-hour kept)."""
    def load():
        hs, ps = defaultdict(lambda: array("q")), defaultdict(lambda: array("f"))
        for n in _names(archive, PMH):
            for r in archive.load(n):
                v = r.get("value") or {}
                p, t, mid = _num(v.get("p")), _num(v.get("t")), v.get("market_id")
                if p is None or t is None or mid is None:
                    continue
                hs[str(mid)].append(int(t) // HOUR)
                ps[str(mid)].append(p)
        out = {}
        for k in hs:
            h = np.frombuffer(hs[k], dtype=np.int64)
            p = np.frombuffer(ps[k], dtype=np.float32)
            order = np.argsort(h, kind="stable")
            h, p = h[order], p[order]
            last = np.r_[h[1:] != h[:-1], True]
            out[k] = (h[last], p[last])
        return out
    return _cached(archive, ("pm_hourly",), load)


def _pm_flow(archive) -> dict:
    """{market_id: (hour_end int64, n int32, F f32)} from polymarket-volume-hourly-<M>: taker flow of the hour starting at
    t, known at its end; YES-direction = YES buys + NO sells, NO-direction = YES sells + NO buys."""
    def load():
        acc = defaultdict(list)
        for n in _names(archive, PMV):
            for r in archive.load(n):
                v = r.get("value") or {}
                t, mid = _num(v.get("t")), v.get("market_id")
                if t is None or mid is None:
                    continue
                o0, o1 = v.get("o0") or {}, v.get("o1") or {}
                yes_q = (_num(o0.get("buy")) or 0.0) + (_num(o1.get("sell")) or 0.0)
                no_q = (_num(o0.get("sell")) or 0.0) + (_num(o1.get("buy")) or 0.0)
                tot = yes_q + no_q
                if tot <= 0:
                    continue
                acc[str(mid)].append((int(t) // HOUR + 1, int(_num(v.get("n")) or 0), (yes_q - no_q) / tot))
        out = {}
        for k, rows in acc.items():
            rows.sort()
            out[k] = (np.array([x[0] for x in rows], dtype=np.int64), np.array([x[1] for x in rows], dtype=np.int32),
                      np.array([x[2] for x in rows], dtype=np.float32))
        return out
    return _cached(archive, ("pm_flow",), load)


def _event_times(archive) -> tuple:
    """Sorted unix times of scheduled events for T-411's pull rule (c): FOMC decision days 14:00 ET, CPI / employment /
    GDP releases 08:30 ET. (times array, note)."""
    def load():
        times, parts = [], []
        if _has(archive, FOMC_B):
            k = 0
            for r in archive.load(FOMC_B):
                v = r.get("value") or {}
                d = v.get("decision_day")
                if d and v.get("scheduled", True):
                    y, m, dd = (int(x) for x in str(d)[:10].split("-"))
                    times.append(int(datetime(y, m, dd, 14, 0, tzinfo=ET).timestamp()))
                    k += 1
            parts.append(f"FOMC {k}")
        for b, lab in ((CPI_REL_B, "CPI"), (EMP_REL_B, "employment"), (GDP_REL_B, "GDP")):
            if not _has(archive, b):
                continue
            k = 0
            for r in archive.load(b):
                d = (r.get("value") or {}).get("day")
                if d:
                    y, m, dd = (int(x) for x in str(d)[:10].split("-"))
                    times.append(int(datetime(y, m, dd, 8, 30, tzinfo=ET).timestamp()))
                    k += 1
            parts.append(f"{lab} {k}")
        return np.array(sorted(set(times)), dtype=np.int64), ", ".join(parts) if parts else "no event calendar archived"
    return _cached(archive, ("events",), load)


# ============================================================================================== hourly stack ==

def build_stack(meta: dict, candles: dict, tickers: Sequence[str], oos: set, from_s: Optional[dict] = None) -> Optional[dict]:
    """Forward-filled hourly grids of ``tickers`` concatenated into one array set (positions = hours from a market's first
    candle to its close hour). Per position: mid, bid, ask, vol (f32), fresh (the hour had a candle), pos (within the
    segment), seglen, htc (hours to close), result (settlement 1 / 0 / nan), seg (segment id), hour (absolute UTC hour),
    oos (market out of sample), usable (hour start >= the market's print-coverage bound when ``from_s`` is given).
    Segment tables: seg_ticker, seg_cat, seg_open_s, seg_start (offsets)."""
    parts = defaultdict(list)
    seg_ticker, seg_cat, seg_open, seg_start = [], [], [], [0]
    n = 0
    for tk in tickers:
        m, c = meta.get(tk), candles.get(tk)
        if m is None or c is None or c[0].size == 0:
            continue
        hours, bid, ask, vol = c
        h0 = int(hours[0])
        close_h = -(-m["close_s"] // HOUR)
        if close_h < h0:
            continue
        L = close_h - h0 + 1
        grid = np.arange(h0, close_h + 1, dtype=np.int64)
        j = np.searchsorted(hours, grid, side="right") - 1
        fresh = np.zeros(L, dtype=bool)
        fresh[hours[hours <= close_h] - h0] = True           # candles after the close hour exist (one period past close)
        parts["mid"].append(((bid[j] + ask[j]) / 2).astype(np.float32))
        parts["bid"].append(bid[j])
        parts["ask"].append(ask[j])
        parts["vol"].append(np.where(fresh, vol[j], 0.0).astype(np.float32))
        parts["fresh"].append(fresh)
        parts["pos"].append(np.arange(L, dtype=np.int32))
        parts["seglen"].append(np.full(L, L, dtype=np.int32))
        parts["htc"].append((close_h - grid).astype(np.int32))
        parts["result"].append(np.full(L, m["result"], dtype=np.float32))
        parts["seg"].append(np.full(L, len(seg_ticker), dtype=np.int32))
        parts["hour"].append(grid)
        parts["oos"].append(np.full(L, tk in oos, dtype=bool))
        if from_s is not None:
            fs = from_s.get(tk, 0)
            parts["usable"].append(np.ones(L, dtype=bool) if fs is None else (grid * HOUR >= fs))
        seg_ticker.append(tk)
        seg_cat.append(m["cat"])
        seg_open.append(m["open_s"])
        n += L
        seg_start.append(n)
    if not seg_ticker:
        return None
    st = {k: np.concatenate(v) for k, v in parts.items()}
    st.update(seg_ticker=seg_ticker, seg_cat=seg_cat, seg_open_s=np.array(seg_open, dtype=np.int64), seg_start=np.array(seg_start, dtype=np.int64), n=n)
    return st


def _shift_back(x: np.ndarray, pos: np.ndarray, k: int) -> np.ndarray:
    y = np.full(x.shape, np.nan, dtype=np.float32)
    if 0 < k < x.size:
        y[k:] = x[:-k]
    y[pos < k] = np.nan
    return y


def _shift_back_bool(x: np.ndarray, pos: np.ndarray, k: int) -> np.ndarray:
    """x shifted k positions later within segments (False where no predecessor k hours back exists)."""
    y = np.zeros(x.shape, dtype=bool)
    if 0 < k < x.size:
        y[k:] = x[:-k]
    y[pos < k] = False
    return y


def valid_book(bid, ask) -> np.ndarray:
    """A two-sided book: bid > 0, ask < 1, bid <= ask, spread <= 10 cents (illiquid hours and the post-close book quote 0 / 1)."""
    return (bid > 0.0) & (ask < 1.0) & (ask >= bid) & (ask - bid <= SPREAD_MAX + EPS)


def next_valid_quote(st: dict) -> np.ndarray:
    """nv[p] = the first position q >= p (anywhere in the stack) whose book is valid and which is not the market's close hour
    (the close-hour candle closes on the post-close empty book), N when none. Callers check that q is in p's segment."""
    N = st["n"]
    ok = valid_book(st["bid"], st["ask"]) & (st["htc"] >= 1)
    cand = np.where(ok, np.arange(N, dtype=np.int64), N)
    return np.minimum.accumulate(cand[::-1])[::-1]


def exit_marks(st: dict, idx: np.ndarray, k, nv: Optional[np.ndarray] = None, max_wait: int = EXIT_WAIT_H) -> tuple:
    """Where a position opened at ``idx`` and held ``k`` hours (int or array) is marked out. The hour idx + k is used when
    it lies before the market's close hour and its book is valid (EXIT_AT_K); an invalid book there (bid 0, ask 1 or a
    spread over 10 cents: no quote to trade against) holds the position to the first later valid quote of the same market
    within ``max_wait`` hours (EXIT_HELD); an exit landing on the close hour or later settles at the result
    (EXIT_SETTLED_CLOSE), and so does one that finds no valid quote in time (EXIT_SETTLED_NO_QUOTE). Returns (exit_pos,
    kind) with exit_pos -1 for a settlement."""
    N = st["n"]
    if nv is None:
        nv = next_valid_quote(st)
    idx = np.asarray(idx, dtype=np.int64)
    k = np.broadcast_to(np.asarray(k, dtype=np.int64), idx.shape)
    pos, seglen, seg = st["pos"][idx], st["seglen"][idx], st["seg"][idx]
    before_close = pos + k < seglen - 1                    # the exit hour has htc >= 1
    j0 = idx + k
    q = nv[np.minimum(j0, N - 1)]
    qc = np.minimum(q, N - 1)
    found = before_close & (q < N) & (st["seg"][qc] == seg) & (q - j0 <= max_wait)
    exit_pos = np.where(found, q, -1).astype(np.int64)
    kind = np.where(~before_close, EXIT_SETTLED_CLOSE, np.where(found, np.where(q == j0, EXIT_AT_K, EXIT_HELD), EXIT_SETTLED_NO_QUOTE))
    return exit_pos, kind.astype(np.int8)


def exit_kind_counts(kind: np.ndarray) -> dict:
    return {name: int(np.count_nonzero(kind == code)) for code, name in EXIT_KIND_NAMES.items()}


def exit_decomposition(st: dict, idx: np.ndarray, buy_yes: np.ndarray, exit_pos: np.ndarray, net_c: np.ndarray, fee: float = TAKER_FEE) -> dict:
    """Mean components (cents per contract) of the trades marked at a quote: mid-to-mid gross in the trade's direction,
    the entry and exit half-spreads, the two fees, the net; and for the settled trades the mean entry price, the mean
    settlement value and the hit rate."""
    q = exit_pos >= 0
    out = {"quote_exits": {"n": int(q.sum())}, "settled": {"n": int((~q).sum())}}
    if q.any():
        i, j = idx[q], exit_pos[q]
        by = buy_yes[q]
        mid_e, mid_x = st["mid"][i].astype(float), st["mid"][j].astype(float)
        entry = np.where(by, st["ask"][i], 1.0 - st["bid"][i]).astype(float)
        exit_q = np.where(by, st["bid"][j], 1.0 - st["ask"][j]).astype(float)
        out["quote_exits"].update(gross_mid_to_mid_c=float((np.where(by, mid_x - mid_e, mid_e - mid_x) * 100).mean()),
                                  entry_half_spread_c=float(((st["ask"][i] - st["bid"][i]) / 2 * 100).mean()),
                                  exit_half_spread_c=float(((st["ask"][j] - st["bid"][j]) / 2 * 100).mean()),
                                  fee_in_c=float((kalshi_fee(entry, fee) * 100).mean()), fee_out_c=float((kalshi_fee(exit_q, fee) * 100).mean()),
                                  net_c=float(net_c[q].mean()))
    if (~q).any():
        i = idx[~q]
        by = buy_yes[~q]
        entry = np.where(by, st["ask"][i], 1.0 - st["bid"][i]).astype(float)
        res = st["result"][i].astype(float)
        settle = np.where(by, res, 1.0 - res)
        fin = np.isfinite(settle)
        out["settled"].update(mean_entry=float(entry.mean()), mean_settlement=float(settle[fin].mean()) if fin.any() else None,
                              hit_rate=float((settle[fin] > 0.5).mean()) if fin.any() else None, net_c=float(net_c[~q].mean()))
    return out


def _stack_subset(st: dict, mask: np.ndarray) -> dict:
    """The positions of whole segments selected by ``mask`` (a per-position mask constant within segments), re-indexed."""
    keep = np.flatnonzero(mask)
    out = {k: (v[keep] if isinstance(v, np.ndarray) and v.shape[:1] == (st["n"],) else v) for k, v in st.items()}
    segs = np.unique(st["seg"][keep])
    remap = np.full(len(st["seg_ticker"]), -1, dtype=np.int64)
    remap[segs] = np.arange(segs.size)
    out["seg"] = remap[st["seg"][keep]].astype(np.int32)
    out["seg_ticker"] = [st["seg_ticker"][i] for i in segs]
    out["seg_cat"] = [st["seg_cat"][i] for i in segs]
    out["seg_open_s"] = st["seg_open_s"][segs]
    out["n"] = int(keep.size)
    starts = np.r_[0, np.flatnonzero(out["seg"][1:] != out["seg"][:-1]) + 1, out["n"]] if out["n"] else np.array([0])
    out["seg_start"] = starts.astype(np.int64)
    return out


def walk_forward_split(meta: dict, tickers: Sequence[str], embargo_s: int) -> dict:
    """Markets sorted by open_time: the first half (by count) calibrates, markets opening within ``embargo_s`` after the
    split open time are embargoed, the rest are out of sample. {calib: set, test: set, embargoed: set, split_s}."""
    tk = sorted((t for t in tickers if t in meta), key=lambda t: (meta[t]["open_s"], t))
    if len(tk) < 2:
        return {"calib": set(tk), "test": set(), "embargoed": set(), "split_s": None}
    h = len(tk) // 2
    split_s = meta[tk[h]]["open_s"]
    calib = {t for t in tk if meta[t]["open_s"] < split_s}
    test = {t for t in tk if meta[t]["open_s"] >= split_s + embargo_s}
    emb = set(tk) - calib - test
    return {"calib": calib, "test": test, "embargoed": emb, "split_s": split_s}


# ================================================================================================ T-408 engine ==

def reversal_trades(st: dict, h: int, theta: float, exit_rule: str = "h", excl24: bool = False, need_vol: bool = False,
                    fee: float = TAKER_FEE, nv: Optional[np.ndarray] = None, prev_spread: Optional[float] = None) -> dict:
    """Trades of one T-408 cell on a stack: signal d = mid_H - mid_{H-h} with |d| >= theta, the book at H a valid touch
    with spread <= theta / 2 (the library rule) and the book at H - h the same (``prev_spread`` overrides the spread bound
    there; a mid is only a mid when a two-sided book quotes it: a book appearing is not a move); d < 0 buys YES at the
    ask, d > 0 buys NO at 1 - bid (same candle close as the signal); exit after k hours at the bid (YES) / 1 - ask (NO),
    k = h, max(1, h // 2) or the first hour within h at which the mid (of a valid book) retraced half the move (else h).
    The exit is marked by ``exit_marks``: an exit landing on the close hour or later settles at the result (no exit fee),
    an exit into an invalid book holds to the next valid quote within EXIT_WAIT_H hours, else settles. Returns arrays
    idx (positions), net_c (cents per contract), ret (net / entry), buy_yes, fresh (the signal hour had a candle),
    exit_pos (-1 = settlement), kind (EXIT_*), and dropped_prev_book_idx (signals removed by the H - h book condition)."""
    mid, bid, ask, pos, seglen, htc = st["mid"], st["bid"], st["ask"], st["pos"], st["seglen"], st["htc"]
    N = st["n"]
    if nv is None:
        nv = next_valid_quote(st)
    vb = valid_book(bid, ask)
    d = mid - _shift_back(mid, pos, h)
    ok = np.isfinite(d) & (np.abs(d) >= theta - EPS) & vb & (ask - bid <= theta / 2 + EPS) & (htc >= 1)
    if "usable" in st:
        ok &= st["usable"]
    if excl24:
        ok &= htc > 24
    if need_vol:
        ok &= st["vol"] > 0
    prev_ok = _shift_back_bool(vb & (ask - bid <= (theta / 2 if prev_spread is None else prev_spread) + EPS), pos, h)
    dropped = np.flatnonzero(ok & ~prev_ok)
    ok &= prev_ok
    i = np.flatnonzero(ok)
    empty = {"idx": np.zeros(0, np.int64), "net_c": np.zeros(0), "ret": np.zeros(0), "buy_yes": np.zeros(0, bool), "fresh": np.zeros(0, bool),
             "exit_pos": np.zeros(0, np.int64), "kind": np.zeros(0, np.int8), "dropped_prev_book_idx": dropped}
    if i.size == 0:
        return empty
    d_i = d[i].astype(float)
    buy_yes = d_i < 0
    entry = np.where(buy_yes, ask[i], 1.0 - bid[i]).astype(float)
    if exit_rule == "h":
        k = np.full(i.size, h, dtype=np.int64)
    elif exit_rule == "half":
        k = np.full(i.size, max(1, h // 2), dtype=np.int64)
    else:
        k = np.full(i.size, h, dtype=np.int64)
        target = mid[i].astype(float) - d_i / 2.0
        for kk in range(h, 0, -1):
            j = np.minimum(i + kk, N - 1)
            inside = (pos[i] + kk < seglen[i] - 1) & vb[j]        # a retrace is read from a valid book before the close hour
            mj = mid[j].astype(float)
            hit = inside & np.where(buy_yes, mj >= target - EPS, mj <= target + EPS)
            k = np.where(hit, kk, k)
    exit_pos, kind = exit_marks(st, i, k, nv)
    settled = exit_pos < 0
    jj = np.where(settled, i, exit_pos)
    exit_q = np.where(buy_yes, bid[jj], 1.0 - ask[jj]).astype(float)
    res = st["result"][i].astype(float)
    settle = np.where(buy_yes, res, 1.0 - res)
    exit_px = np.where(settled, settle, exit_q)
    fee_in = kalshi_fee(entry, fee)
    fee_out = np.where(settled, 0.0, kalshi_fee(exit_q, fee))
    net = exit_px - entry - fee_in - fee_out
    keep = np.isfinite(net) & (entry > 0)
    return {"idx": i[keep], "net_c": 100.0 * net[keep], "ret": net[keep] / entry[keep], "buy_yes": buy_yes[keep], "fresh": st["fresh"][i[keep]],
            "exit_pos": exit_pos[keep], "kind": kind[keep], "dropped_prev_book_idx": dropped}


def t408_cells() -> list:
    cells = []
    for h in T408_H:
        for th in T408_THETA:
            for ex in T408_EXIT:
                for e24 in (False, True):
                    for nv in (False, True):
                        cells.append((h, th, ex, e24, nv))
    return cells


def t408_cell_key(c: tuple) -> tuple:
    """The distinct rule a declared cell runs: at h = 1 the three exit rules coincide (exit after h = 1 hour; h // 2 -> max(1, 0)
    = 1; a 50% retrace within 1 hour exits at 1 hour), so the h = 1 cells collapse onto their 'h' cell."""
    h, th, ex, e24, nv = c
    return (h, th, "h" if h == 1 else ex, e24, nv)


def t408_distinct_cells() -> list:
    """The 84 distinct cells of the declared 108 (the h = 1 triplets are one rule each), in declared order."""
    seen: list = []
    for c in t408_cells():
        key = t408_cell_key(c)
        if key not in seen:
            seen.append(key)
    return seen


def cell_name(c: tuple) -> str:
    h, th, ex, e24, nv = c
    return f"h{h}_t{int(round(th * 100))}_{ex}_{'x24' if e24 else 'all'}_{'vol' if nv else 'any'}"


def stationary_resample_idx(st: dict, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Stationary block bootstrap indices within every segment: each position starts a new block with probability
    1 / mean_block (always at a segment's first position), a block starts at a uniform position of its own segment and
    runs circularly within it."""
    N, pos, seglen = st["n"], st["pos"], st["seglen"]
    seg_start_of = np.arange(N, dtype=np.int64) - pos
    new = rng.random(N) < 1.0 / mean_block
    new[pos == 0] = True
    start_rel = np.floor(rng.random(N) * seglen).astype(np.int64)
    run_first = np.flatnonzero(new)
    run_id = np.cumsum(new) - 1
    offset = np.arange(N, dtype=np.int64) - run_first[run_id]
    return seg_start_of + (start_rel[run_first[run_id]] + offset) % seglen


def _segment_cumsum(x: np.ndarray, seg_start: np.ndarray, seg: np.ndarray) -> np.ndarray:
    cs = np.cumsum(x, dtype=np.float64)
    base = cs[seg_start[:-1]] - x[seg_start[:-1]]
    return cs - base[seg]


def valid_mid_path(st: dict) -> np.ndarray:
    """The mid of a valid book, carried forward within the market over the hours whose book is invalid (an empty, one-sided or
    > 10-cent book quotes no mid: the last quoted mid stands until the next valid book, and the change across the invalid
    stretch is booked at the first valid hour after it); the hours before a market's first valid book take that first mid;
    nan for a market with no valid book at all."""
    N = st["n"]
    ar = np.arange(N, dtype=np.int64)
    vb = valid_book(st["bid"], st["ask"])
    seg_start_of = ar - st["pos"]
    last = np.maximum.accumulate(np.where(vb, ar, -1))
    nxt = np.minimum.accumulate(np.where(vb, ar, N)[::-1])[::-1]
    nxt_c = np.minimum(nxt, N - 1)
    has_last = last >= seg_start_of
    has_next = (nxt < N) & (st["seg"][nxt_c] == st["seg"])
    src = np.where(has_last, np.maximum(last, 0), nxt_c)
    out = st["mid"].astype(np.float32)[src]
    out[~(has_last | has_next)] = np.nan
    return out


def reversal_null(st: dict, cell: tuple, observed_mean_c: float, n_draws: int, mean_block: float = 24.0, seed: int = SEED) -> dict:
    """The trial's bootstrap for T-408 (H0: hourly mid changes are a martingale after costs): the hourly changes of every
    market's valid-book mid (``valid_mid_path``: a jump into or out of an empty book is not a mid change) resampled by a
    stationary block bootstrap within the market (mean block ``mean_block`` hours; the hour's spread and volume travel
    with the change, so the resampled path has invalid books where the source hours had them), the path rebuilt from the
    market's first valid mid (clipped to [0.005, 0.995]), the cell re-run with its book-validity and exit rules on the
    resampled book, and its mean net return (cents) recorded. A trade that settles in the resampled path settles at a
    result drawn per market and draw as Bernoulli(the resampled path's final mid): under the martingale null the final
    mid is the fair settlement expectation, whereas the real market's outcome is unrelated to the resampled path's entry
    level (markets whose real result is unknown stay unknown). ``n_draws`` = the trial's 2,000 in the harness. p = share
    of bootstrap means <= 0 (the percentile bootstrap p-value for H0: mean net <= 0; the block bootstrap keeps
    within-block dependence, so the draws scatter around the observed mean and their spread is the estimator's sampling
    variation under hourly dependence); p_lt = share >= 0 (p_lt < 0.01 is a decisive failure: the whole bootstrap
    distribution lies below zero). Also reported: boot_mean (against the observed, a bias check), p_centred = share of
    (draw - boot_mean) >= observed, and the mean count of settled trades per draw."""
    rng = np.random.default_rng(seed)
    h, th, ex, e24, nv = cell
    S = len(st["seg_ticker"])
    mid_v = valid_mid_path(st)
    dmid = mid_v - _shift_back(mid_v, st["pos"], 1)
    dmid[st["pos"] == 0] = 0.0
    dmid = np.nan_to_num(dmid).astype(np.float32)
    spread = (st["ask"] - st["bid"]).astype(np.float32)
    first_seg = np.where(np.isfinite(mid_v[st["seg_start"][:-1]]), mid_v[st["seg_start"][:-1]], st["mid"][st["seg_start"][:-1]]).astype(np.float32)
    first_mid = first_seg[st["seg"]]
    last_pos = st["seg_start"][1:] - 1                       # each market's last position (the close hour)
    real_known = np.isfinite(st["result"][st["seg_start"][:-1]])
    means = np.empty(n_draws)
    settled_n = np.empty(n_draws)
    for b in range(n_draws):
        idx = stationary_resample_idx(st, mean_block, rng)
        dm = dmid[idx]
        dm[st["pos"] == 0] = 0.0
        m_res = np.clip(first_mid + _segment_cumsum(dm, st["seg_start"], st["seg"]), 0.005, 0.995).astype(np.float32)
        sp = spread[idx]
        sub = dict(st)
        sub["mid"] = m_res
        sub["bid"] = np.clip(m_res - sp / 2, 0.0, 1.0).astype(np.float32)
        sub["ask"] = np.clip(m_res + sp / 2, 0.0, 1.0).astype(np.float32)
        sub["vol"] = st["vol"][idx]
        res_seg = (rng.random(S) < m_res[last_pos]).astype(np.float32)
        res_seg[~real_known] = np.nan
        sub["result"] = res_seg[st["seg"]]
        tr = reversal_trades(sub, h, th, ex, e24, nv)
        means[b] = float(tr["net_c"].mean()) if tr["net_c"].size else np.nan
        settled_n[b] = float((tr["exit_pos"] < 0).sum())
    ok = np.isfinite(means)
    means, settled_n = means[ok], settled_n[ok]
    if means.size < 10:
        return {"n_draws": int(means.size), "p": None, "p_lt": None, "p_centred": None, "boot_mean": None, "boot_sd": None, "observed": observed_mean_c}
    centred = means - means.mean()
    return {"n_draws": int(means.size), "p": float((np.sum(means <= 0.0) + 1) / (means.size + 1)),
            "p_lt": float((np.sum(means >= 0.0) + 1) / (means.size + 1)),
            "p_centred": float((np.sum(centred >= observed_mean_c) + 1) / (means.size + 1)),
            "boot_mean": float(means.mean()), "boot_sd": float(means.std(ddof=1)), "observed": observed_mean_c,
            "mean_settled_trades_per_draw": float(settled_n.mean()),
            "construction": "valid-book mid changes, stationary block bootstrap within market; settlement drawn as Bernoulli(final resampled mid)"}


def pm_reversal_trades(series: dict, meta: dict, hs: float, h: int = 3, theta: float = 0.05, max_gap: int = 3) -> dict:
    """The Polymarket replication of a T-408 cell on hourly CLOB prices: forward-filled over gaps <= ``max_gap`` hours;
    d = p_H - p_{H-h}, |d| >= theta; d < 0 buys YES at p + hs, d > 0 buys NO at (1 - p) + hs; exit after h hours at
    p' - hs / (1 - p') - hs (settlement at the Gamma outcome when the series ends first and the outcome is known, else
    the trade is dropped); fee = the market's Gamma rate x P(1-P) each way. Returns net_c, ret, market labels."""
    nets, rets, labels = [], [], []
    for mid_id, (hours, p) in series.items():
        if hours.size < h + 2:
            continue
        h0, h1 = int(hours[0]), int(hours[-1])
        grid = np.arange(h0, h1 + 1, dtype=np.int64)
        j = np.searchsorted(hours, grid, side="right") - 1
        gap = grid - hours[j]
        pg = p[j].astype(float)
        pg[gap > max_gap] = np.nan
        L = grid.size
        info = meta.get(str(mid_id)) or {}
        rate, outcome = float(info.get("fee_rate") or 0.0), info.get("outcome")
        d = np.full(L, np.nan)
        d[h:] = pg[h:] - pg[:-h]
        ok = np.isfinite(d) & (np.abs(d) >= theta - EPS) & (pg > 0.0) & (pg < 1.0)
        i = np.flatnonzero(ok)
        if i.size == 0:
            continue
        buy_yes = d[i] < 0
        entry = np.where(buy_yes, pg[i] + hs, (1.0 - pg[i]) + hs)
        inside = i + h < L
        jj = np.minimum(i + h, L - 1)
        pe = pg[jj]
        exit_q = np.where(buy_yes, pe - hs, (1.0 - pe) - hs)
        settle = np.full(i.size, np.nan) if outcome is None else np.where(buy_yes, float(outcome), 1.0 - float(outcome))
        exit_px = np.where(inside, exit_q, settle)
        fee_in = rate * entry * (1 - entry)
        fee_out = np.where(inside, rate * np.clip(exit_q, 0, 1) * (1 - np.clip(exit_q, 0, 1)), 0.0)
        net = exit_px - entry - fee_in - fee_out
        keep = np.isfinite(net) & (entry > 0)
        nets.append(100.0 * net[keep])
        rets.append(net[keep] / entry[keep])
        labels += [str(mid_id)] * int(keep.sum())
    if not nets:
        return {"n": 0, "mean_c": None, "markets": 0}
    net_c = np.concatenate(nets)
    cs = cluster_stud(net_c, labels, N_BOOT)
    return {"n": int(net_c.size), "mean_c": float(net_c.mean()), "markets": len(set(labels)), "ci": cs["ci"], "p": cs["p"], "p_lt": cs["p_lt"]}


def b6c_pmmicro_hourly_reversal(archive):
    """T-408."""
    miss = _missing_families(archive, [KH, KS])
    if miss:
        return miss
    meta, candles = _kalshi_meta(archive), _kalshi_candles(archive)
    pool_all = [tk for tk in candles if tk in meta]
    pool = [tk for tk in pool_all if meta[tk]["series"] not in CRYPTO_SERIES]
    crypto = [tk for tk in pool_all if meta[tk]["series"] in CRYPTO_SERIES]
    if len(pool) < 2:
        v, why = _verdict([("Kalshi markets with hourly candles (>= 2 non-crypto)", None)])
        return _out({"n_markets": len(pool)}, 0, v, f"only {len(pool)} non-crypto Kalshi markets with hourly candles — {why}")
    split = walk_forward_split(meta, pool, T408_EMBARGO_S)
    st = build_stack(meta, candles, pool, split["test"])
    nv = next_valid_quote(st)
    cells = t408_cells()
    distinct = t408_distinct_cells()
    head = T408_HEADLINE
    hour_min, hour_max = int(st["hour"].min()), int(st["hour"].max())
    H = hour_max - hour_min + 1
    R = np.zeros((H, len(distinct)), dtype=np.float64)
    is_mask = np.isin(st["seg"], np.flatnonzero(np.array([tk in split["calib"] for tk in st["seg_ticker"]])))
    cell_stats = {}
    head_tr = None
    for ci, c in enumerate(distinct):
        tr = reversal_trades(st, *c, nv=nv)
        idx = tr["idx"]
        if idx.size:
            R[:, ci] = np.bincount(st["hour"][idx] - hour_min, weights=tr["ret"], minlength=H)
        oos_m = st["oos"][idx] if idx.size else np.zeros(0, bool)
        is_m = is_mask[idx] if idx.size else np.zeros(0, bool)
        r_oos = tr["ret"][oos_m]
        cell_stats[cell_name(c)] = {"n": int(idx.size), "mean_c": float(tr["net_c"].mean()) if idx.size else None,
                                    "n_is": int(is_m.sum()), "mean_c_is": float(tr["net_c"][is_m].mean()) if is_m.any() else None,
                                    "n_oos": int(oos_m.sum()), "mean_c_oos": float(tr["net_c"][oos_m].mean()) if oos_m.any() else None,
                                    "sr_oos": float(sharpe_ratio(r_oos)) if r_oos.size >= 2 else None}
        if c == head:
            head_tr = tr
    for c in cells:                                             # the declared duplicates (h = 1 'half' / 'retrace') point at their rule
        key = t408_cell_key(c)
        if key != c:
            cell_stats[cell_name(c)] = {**cell_stats[cell_name(key)], "duplicate_of": cell_name(key)}
    n_trials_distinct = len(distinct) + T408_DAILY_RULES
    n_trials_declared = len(cells) + T408_DAILY_RULES
    # headline cell, out of sample
    idx = head_tr["idx"]
    oos_m = st["oos"][idx]
    oos_idx, oos_net, oos_ret = idx[oos_m], head_tr["net_c"][oos_m], head_tr["ret"][oos_m]
    n_oos = int(oos_idx.size)
    labels = [st["seg_ticker"][s] for s in st["seg"][oos_idx]]
    cs = cluster_stud(oos_net, labels, N_BOOT) if n_oos >= 4 else {"est": float(oos_net.mean()) if n_oos else None, "ci": [None, None], "p": None, "p_lt": None, "clusters": len(set(labels))}
    all_cs = cluster_stud(head_tr["net_c"], [st["seg_ticker"][s] for s in st["seg"][idx]], N_BOOT) if idx.size >= 4 else {"est": None, "ci": [None, None], "p": None}
    # exit marks and the H - h book condition on the headline cell (out of sample)
    exit_kinds = exit_kind_counts(head_tr["kind"][oos_m])
    decomp = exit_decomposition(st, oos_idx, head_tr["buy_yes"][oos_m], head_tr["exit_pos"][oos_m], oos_net) if n_oos else {}
    dropped_all = int(head_tr["dropped_prev_book_idx"].size)
    dropped_oos = int(st["oos"][head_tr["dropped_prev_book_idx"]].sum()) if dropped_all else 0
    tr_touch = reversal_trades(st, *head, nv=nv, prev_spread=SPREAD_MAX)        # sensitivity: any valid touch (<= 10 cents) at H - h
    oos_t = st["oos"][tr_touch["idx"]] if tr_touch["idx"].size else np.zeros(0, bool)
    prev_touch_sens = {"n_oos": int(oos_t.sum()), "mean_c_oos": float(tr_touch["net_c"][oos_t].mean()) if oos_t.any() else None,
                       "n_dropped_oos": int(st["oos"][tr_touch["dropped_prev_book_idx"]].sum()) if tr_touch["dropped_prev_book_idx"].size else 0}
    # trial null on the out-of-sample stack
    null = {"n_draws": 0, "p": None, "p_lt": None, "p_raw": None}
    if n_oos >= 4:
        st_oos = _stack_subset(st, st["oos"])
        null = reversal_null(st_oos, head, float(oos_net.mean()), N_NULL_T408)
    # PBO over the 84 distinct cells (all markets), DSR of the headline out-of-sample Sharpe over 84 + 21 = 105 distinct trials
    # (the declared 108 + 21 = 129 is the upper bound: reported next to it)
    pbo = None
    if H >= 64 and np.any(R != 0):
        try:
            pbo = pbo_cscv(R, 8)
        except Exception:
            pbo = None
    srs = [cell_stats[cell_name(c)]["sr_oos"] for c in distinct if cell_stats[cell_name(c)]["sr_oos"] is not None]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) > 1 else None
    dsr = dsr_declared = None
    if n_oos >= 10:
        try:
            dsr = float(deflated_sharpe_ratio(oos_ret, n_trials_distinct, var_trials_sr=var_sr if var_sr and var_sr > 0 else None))
            dsr_declared = float(deflated_sharpe_ratio(oos_ret, n_trials_declared, var_trials_sr=var_sr if var_sr and var_sr > 0 else None))
        except Exception:
            dsr = dsr_declared = None
    # calibration half's best cell and its out-of-sample reading
    best = max(((k, v) for k, v in cell_stats.items() if "duplicate_of" not in v and v["n_is"] >= 30 and v["mean_c_is"] is not None),
               key=lambda kv: kv[1]["mean_c_is"], default=None)
    # regimes
    cats = [st["seg_cat"][s] for s in st["seg"][oos_idx]]
    by_cat = {c: {"n": int(k), "mean_c": float(oos_net[np.array(cats) == c].mean())} for c, k in Counter(cats).items()} if n_oos else {}
    htc = st["htc"][oos_idx] if n_oos else np.zeros(0)
    by_htc = {}
    for lab, lo, hi in (("<=24h", 0, 24), ("24-96h", 24, 96), (">96h", 96, 10 ** 9)):
        m = (htc > lo) & (htc <= hi) if n_oos else np.zeros(0, bool)
        by_htc[lab] = {"n": int(m.sum()), "mean_c": float(oos_net[m].mean()) if m.any() else None}
    def _period_split(hours_a, net_a):
        yrs = (hours_a * HOUR).astype("datetime64[s]").astype("datetime64[Y]").astype(np.int64) + 1970
        return {"2024_and_before": {"n": int((yrs <= 2024).sum()), "mean_c": float(net_a[yrs <= 2024].mean()) if (yrs <= 2024).any() else None},
                "2025_26": {"n": int((yrs >= 2025).sum()), "mean_c": float(net_a[yrs >= 2025].mean()) if (yrs >= 2025).any() else None}}
    by_period = _period_split(st["hour"][oos_idx], oos_net) if n_oos else {}
    by_period_all = _period_split(st["hour"][idx], head_tr["net_c"]) if idx.size else {}
    zero_vol = int((~head_tr["fresh"][oos_m]).sum()) + int(((st["vol"][oos_idx] <= 0) & head_tr["fresh"][oos_m]).sum()) if n_oos else 0
    # crypto bucket (reported, not in the headline pool)
    crypto_stat = {"n_markets": len(crypto)}
    if len(crypto) >= 2:
        st_c = build_stack(meta, candles, crypto, set())
        if st_c is not None:
            trc = reversal_trades(st_c, *head)
            crypto_stat.update(n=int(trc["idx"].size), mean_c=float(trc["net_c"].mean()) if trc["idx"].size else None)
    # Polymarket replication
    hs, hs_src = pm_half_spread(archive)
    pm_meta = _pm_meta(archive)
    pm_series = _pm_hourly(archive)
    legacy_ids = {k for k, v in pm_meta.items() if v.get("legacy")}
    pm_sel = {k: v for k, v in pm_series.items() if k in legacy_ids} or pm_series
    pm_scope = "the archived largest resolved markets (legacy polymarket-closed-markets ids)" if any(k in legacy_ids for k in pm_series) else "every archived hourly history"
    pm = pm_reversal_trades(pm_sel, pm_meta, hs, head[0], head[1]) if pm_sel else {"n": 0, "mean_c": None, "markets": 0}
    # criteria
    obs = cs.get("est")
    rows = [(f"trial bootstrap (stationary block bootstrap of hourly valid-book mid changes within market, mean block 24 h, {null['n_draws']} draws, the rule re-run on "
             f"each path, settlement drawn from the resampled final mid) p {_f(null.get('p'))} (bootstrap mean {_s(null.get('boot_mean'))} vs observed {_s(obs)})",
             None if null.get("p") is None else null["p"] < 0.01, null.get("p_lt") is not None and null["p_lt"] < 0.01),
            (f"market-clustered studentized bootstrap p {_f(cs.get('p'))} ({cs.get('clusters', 0)} markets)",
             None if cs.get("p") is None else cs["p"] < 0.01, cs.get("p_lt") is not None and cs["p_lt"] < 0.01)]
    crit = [all_constructions(rows, f"out-of-sample headline cell (h 3, theta 5 cents, exit 3 h): {n_oos} trades, mean net {_s(obs)} cents/contract > 0 with bootstrap p < 0.01")]
    pbo_v = (pbo or {}).get("pbo")
    crit.append((f"PBO {_f(pbo_v)} < 0.2 over the 108 declared cells = {len(distinct)} distinct rules (the h = 1 exit rules coincide; CSCV, hourly cell P&L, {H} hours, all markets)",
                 None if pbo_v is None else pbo_v < 0.2, False))
    crit.append((f"DSR {_f(dsr)} >= 0.95 over {len(distinct)} distinct cells + 21 = {n_trials_distinct} trials (declared 108 + 21 = {n_trials_declared} is the upper bound: "
                 f"DSR {_f(dsr_declared)}; out-of-sample headline Sharpe)", None if dsr is None else dsr >= 0.95, False))
    same_sign = None if (pm.get("mean_c") is None or obs is None) else (np.sign(pm["mean_c"]) == np.sign(obs) and obs != 0)
    sign_note = " (both negative: the replication agrees with the Kalshi loss, not with the claim)" if (same_sign and obs is not None and obs < 0) else ""
    crit.append((f"Polymarket replication same sign: {pm.get('n', 0)} trades on {pm.get('markets', 0)} markets, mean net {_s(pm.get('mean_c'))} cents "
                 f"(half-spread {hs * 100:.2f} cents [{hs_src}], Gamma fee flag) vs Kalshi {_s(obs)}{sign_note}", same_sign, False))
    verdict, why = _decide(crit, n_oos, 3000, "out-of-sample trades")
    qx = decomp.get("quote_exits", {})
    reason = (f"Kalshi hourly reversal on {len(pool)} non-crypto markets with hourly candles ({dict(Counter(meta[t]['cat'] for t in pool))}; "
              f"{st['n']} forward-filled market-hours; crypto KXBTCD bucket separate: {crypto_stat.get('n', 0)} trades mean {_s(crypto_stat.get('mean_c'))}). "
              f"Walk-forward split at open {_day_str(split['split_s']) if split['split_s'] else 'n/a'}: {len(split['calib'])} calibration, {len(split['embargoed'])} embargoed (7 d), "
              f"{len(split['test'])} test markets. Headline cell: {idx.size} trades in all (mean {_s(all_cs.get('est'))} cents, {_ci_txt(all_cs.get('ci'))}); "
              f"out of sample {n_oos} trades, mean net {_s(obs)} cents/contract ({_ci_txt(cs.get('ci'))}, cluster p {_f(cs.get('p'))}; trial bootstrap p {_f(null.get('p'))} over "
              f"{null.get('n_draws', 0)} draws, bootstrap mean {_s(null.get('boot_mean'))} +/- {_f(null.get('boot_sd'))}, centred p {_f(null.get('p_centred'))}); {zero_vol} signal hours without a fresh candle or volume "
              f"(flagged, kept). Signal books: the book at H - 3 must be a valid touch with spread <= theta / 2 like the book at H ({dropped_oos} out-of-sample signals dropped whose "
              f"H - 3 book was empty, one-sided or wider; with any valid touch <= 10 cents at H - 3 instead: {prev_touch_sens['n_oos']} trades, mean {_s(prev_touch_sens['mean_c_oos'])}). "
              f"Exit marks (out of sample): {exit_kinds['quote_at_k']} at the 3-hour quote, {exit_kinds['held_to_next_valid_quote']} held to the next valid quote (invalid book at 3 h, "
              f"<= {EXIT_WAIT_H} h), {exit_kinds['settled_close_hour_or_later']} settled at the result (exit on or after the close hour: the close-hour candle's close is the post-close "
              f"empty book), {exit_kinds['settled_no_valid_quote_within_wait']} settled for want of a valid quote; quote-exit decomposition (cents): mid-to-mid {_s(qx.get('gross_mid_to_mid_c'))}, "
              f"entry half-spread {_f(qx.get('entry_half_spread_c'), 2)}, exit half-spread {_f(qx.get('exit_half_spread_c'), 2)}, fees {_f(qx.get('fee_in_c'), 2)} + {_f(qx.get('fee_out_c'), 2)}. "
              f"Calibration-best cell {best[0] if best else 'n/a'}: IS {_s(best[1]['mean_c_is']) if best else 'n/a'}, OOS "
              f"{_s(best[1]['mean_c_oos']) if best else 'n/a'} over {best[1]['n_oos'] if best else 0}. PBO {_f(pbo_v)}; DSR {_f(dsr)} over {n_trials_distinct} trials "
              f"({len(distinct)} distinct of the 108 declared cells: the h = 1 exit rules coincide; var of their Sharpes {_f(var_sr, 5)}; DSR at the declared {n_trials_declared}: {_f(dsr_declared)}). "
              f"By category {by_cat}; by hours to close {by_htc}; out-of-sample period split {by_period}, all headline trades {by_period_all}. Polymarket replication on {pm_scope}: {pm.get('n', 0)} trades, mean {_s(pm.get('mean_c'))} cents. "
              f"{FEE_NOTE}; fills at the ask / 1 - bid of the signal candle close (rule 12), exits at the bid, no exit fee at settlement — {why}")
    stat = {"n_markets": len(pool), "n_markets_crypto": len(crypto), "market_hours": int(st["n"]), "split": {"split_s": split["split_s"], "calib": len(split["calib"]),
            "embargoed": len(split["embargoed"]), "test": len(split["test"]), "embargo_days": 7},
            "headline": {"cell": cell_name(head), "n_all": int(idx.size), "mean_c_all": all_cs.get("est"), "ci_all": all_cs.get("ci"), "n_oos": n_oos, "mean_c_oos": obs,
                         "ci_oos": cs.get("ci"), "p_cluster": cs.get("p"), "p_lt_cluster": cs.get("p_lt"), "clusters": cs.get("clusters"), "trial_null": null,
                         "zero_volume_signal_hours_oos": zero_vol, "sr_hourly_annualised_oos": (float(sharpe_ratio(R[:, distinct.index(head)], 24 * 365)) if H > 2 else None),
                         "exit_kinds_oos": exit_kinds, "exit_wait_hours": EXIT_WAIT_H, "decomposition_oos": decomp,
                         "signals_dropped_prev_book": {"all": dropped_all, "oos": dropped_oos, "rule": "book at H - h a valid touch with spread <= theta / 2"},
                         "prev_book_any_valid_touch_sensitivity_oos": prev_touch_sens},
            "cells": cell_stats, "n_cells_declared": len(cells), "n_cells_distinct": len(distinct), "best_calibration_cell": best[0] if best else None, "pbo": pbo,
            "dsr": dsr, "dsr_declared_trials": dsr_declared, "var_trial_sr": var_sr, "n_trials": n_trials_distinct, "n_trials_declared": n_trials_declared,
            "by_category_oos": by_cat, "by_hours_to_close_oos": by_htc, "by_period_oos": by_period, "by_period_all": by_period_all, "crypto_bucket": crypto_stat,
            "polymarket": {**pm, "half_spread": hs, "half_spread_source": hs_src, "scope": pm_scope},
            "costs": {"taker_fee": TAKER_FEE, "fee_note": FEE_NOTE}, "criteria": [(c[0], c[1]) for c in crit], "rule10": "signal-driven entries: no grid phase"}
    return _out(stat, n_oos, verdict, reason)


# ================================================================================================ T-463 engine ==

def hourly_flow(trades: tuple, from_s: int = 0) -> tuple:
    """(hour_end int64, n int32, F f32, qty f32) per hour from one market's prints (t, price, side, qty): F = (YES-taken -
    NO-taken) / all contracts over the prints of [H - 1 h, H). Hours starting before ``from_s`` (print coverage) are
    dropped."""
    t, _, side, qty = trades
    keep = (t // HOUR) * HOUR >= from_s                       # whole hours only: a partial boundary hour would understate n and F
    t, side, qty = t[keep], side[keep].astype(np.int64), qty[keep].astype(np.float64)
    if t.size == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int32), np.zeros(0, np.float32), np.zeros(0, np.float32)
    P = t // HOUR
    uniq, inv = np.unique(P, return_inverse=True)
    n = np.bincount(inv, minlength=uniq.size)
    yes_q = np.bincount(inv, weights=np.where(side > 0, qty, 0.0), minlength=uniq.size)
    no_q = np.bincount(inv, weights=np.where(side < 0, qty, 0.0), minlength=uniq.size)
    tot = yes_q + no_q
    F = np.where(tot > 0, (yes_q - no_q) / np.maximum(tot, 1e-12), 0.0)
    return uniq + 1, n.astype(np.int32), F.astype(np.float32), tot.astype(np.float32)


def flow_candidates(st: dict, flows: dict, min_trades: int = T463_MIN_TRADES, delay: int = 0) -> dict:
    """Qualifying hours of a stack: for every market with a flow table, the hours H with >= ``min_trades`` prints in
    [H - 1 h, H), a valid touch at H (+ ``delay`` hours for the 1-hour-delay sensitivity) and mid within [0.05, 0.95].
    Returns position idx (the entry hour), F, n_trades per candidate."""
    seg_of = {tk: i for i, tk in enumerate(st["seg_ticker"])}
    idxs, Fs, ns = [], [], []
    for tk, (hour_end, n, F, _) in flows.items():
        s = seg_of.get(tk)
        if s is None:
            continue
        lo, hi = st["seg_start"][s], st["seg_start"][s + 1]
        h0 = int(st["hour"][lo])
        L = hi - lo
        q = n >= min_trades
        pos = hour_end[q] - h0 + delay
        ok = (pos >= 0) & (pos < L)
        p = pos[ok] + lo
        idxs.append(p)
        Fs.append(F[q][ok])
        ns.append(n[q][ok])
    if not idxs:
        return {"idx": np.zeros(0, np.int64), "F": np.zeros(0, np.float32), "n_trades": np.zeros(0, np.int32)}
    idx, F, n = np.concatenate(idxs), np.concatenate(Fs), np.concatenate(ns)
    bid, ask, mid, htc = st["bid"][idx], st["ask"][idx], st["mid"][idx], st["htc"][idx]
    ok = (bid > 0.0) & (ask < 1.0) & (ask >= bid) & (ask - bid <= SPREAD_MAX + EPS) & (mid >= 0.05) & (mid <= 0.95) & (htc >= 1)
    if "usable" in st:
        ok &= st["usable"][idx]
    return {"idx": idx[ok], "F": F[ok], "n_trades": n[ok]}


def side_returns(st: dict, idx: np.ndarray, h: int, fee: float = TAKER_FEE, nv: Optional[np.ndarray] = None) -> tuple:
    """(r_yes, r_no) in cents per contract of buying YES at the ask / NO at 1 - bid at positions ``idx`` and exiting at the
    bid / 1 - ask after ``h`` hours, marked by ``exit_marks``: an exit on or after the close hour settles at the result (no
    exit fee), an exit into an invalid book holds to the next valid quote within EXIT_WAIT_H hours, else settles; taker fee
    each way."""
    exit_pos, _ = exit_marks(st, idx, h, nv)
    settled = exit_pos < 0
    jj = np.where(settled, idx, exit_pos)
    res = st["result"][idx].astype(float)
    out = []
    for yes in (True, False):
        entry = (st["ask"][idx] if yes else 1.0 - st["bid"][idx]).astype(float)
        exit_q = (st["bid"][jj] if yes else 1.0 - st["ask"][jj]).astype(float)
        settle = res if yes else 1.0 - res
        exit_px = np.where(settled, settle, exit_q)
        net = exit_px - entry - kalshi_fee(entry, fee) - np.where(settled, 0.0, kalshi_fee(exit_q, fee))
        out.append(100.0 * net)
    return out[0], out[1]


def flow_trades(cand: dict, r_yes: np.ndarray, r_no: np.ndarray, f: float, follow: bool = True) -> dict:
    """Trades of one Kalshi T-463 cell: |F| > f; follow buys the taken side, fade the other. Returns sel (candidate
    indices), net_c."""
    F = cand["F"].astype(float)
    sel = np.flatnonzero((np.abs(F) > f) & np.isfinite(r_yes) & np.isfinite(r_no))
    buy_yes = (F[sel] > 0) if follow else (F[sel] < 0)
    net = np.where(buy_yes, r_yes[sel], r_no[sel])
    return {"sel": sel, "net_c": net, "buy_yes": buy_yes}


def flow_permutation_null(cand: dict, st: dict, r_yes: np.ndarray, r_no: np.ndarray, f: float, follow: bool, observed_mean_c: float,
                          n_perm: int, seed: int = SEED) -> dict:
    """The trial's null for T-463: F permuted across the qualifying hours within each market; the cell re-run on every
    permutation (which hours trigger, and in which direction, change) and its mean net return recorded. p = share of
    permuted means >= observed; p_lt the mirror."""
    rng = np.random.default_rng(seed)
    F = cand["F"].astype(float)
    ok = np.isfinite(r_yes) & np.isfinite(r_no)
    F, ry, rn, seg = F[ok], r_yes[ok], r_no[ok], st["seg"][cand["idx"][ok]].astype(np.int64)
    n = F.size
    if n < 8:
        return {"n_perm": 0, "p": None, "p_lt": None}
    order = np.argsort(seg, kind="stable")
    F, ry, rn, seg = F[order], ry[order], rn[order], seg[order]
    means = np.empty(n_perm)
    for b in range(n_perm):
        perm = np.lexsort((rng.random(n), seg))               # a random order within each market, markets kept
        Fp = F[perm]
        sel = np.abs(Fp) > f
        if not sel.any():
            means[b] = np.nan
            continue
        buy_yes = (Fp[sel] > 0) if follow else (Fp[sel] < 0)
        means[b] = np.where(buy_yes, ry[sel], rn[sel]).mean()
    means = means[np.isfinite(means)]
    if means.size < 10:
        return {"n_perm": int(means.size), "p": None, "p_lt": None}
    return {"n_perm": int(means.size), "p": float((np.sum(means >= observed_mean_c) + 1) / (means.size + 1)),
            "p_lt": float((np.sum(means <= observed_mean_c) + 1) / (means.size + 1)), "null_mean": float(means.mean()), "null_sd": float(means.std(ddof=1))}


def pm_flow_trades(flows: dict, series: dict, meta: dict, hs: float, f: float, h: int, follow: bool, min_trades: int = T463_MIN_TRADES,
                   max_gap: int = 3) -> dict:
    """The Polymarket cells of T-463: data-api taker flow per hour (>= min_trades taker orders, |F| > f), entry at the
    hour end at p + hs (YES) / (1 - p) + hs (NO), exit after h hours at p' - hs / (1 - p') - hs, the Gamma fee rate each
    way; settlement at the outcome when the series ends first (dropped when unknown)."""
    nets, labels, hours = [], [], []
    for mid_id, (hour_end, n, F) in flows.items():
        ser = series.get(mid_id)
        if ser is None:
            continue
        hrs, p = ser
        if hrs.size < 2:
            continue
        h0, h1 = int(hrs[0]), int(hrs[-1])
        grid = np.arange(h0, h1 + 1, dtype=np.int64)
        j = np.searchsorted(hrs, grid, side="right") - 1
        pg = p[j].astype(float)
        pg[(grid - hrs[j]) > max_gap] = np.nan
        L = grid.size
        q = (n >= min_trades) & (np.abs(F) > f)
        pos = hour_end[q] - h0
        ok = (pos >= 0) & (pos < L)
        pos, Fq = pos[ok], F[q][ok].astype(float)
        if pos.size == 0:
            continue
        pe0 = pg[pos]
        ok2 = np.isfinite(pe0) & (pe0 >= 0.05) & (pe0 <= 0.95)
        pos, Fq, pe0 = pos[ok2], Fq[ok2], pe0[ok2]
        if pos.size == 0:
            continue
        info = meta.get(str(mid_id)) or {}
        rate, outcome = float(info.get("fee_rate") or 0.0), info.get("outcome")
        buy_yes = (Fq > 0) if follow else (Fq < 0)
        entry = np.where(buy_yes, pe0 + hs, (1.0 - pe0) + hs)
        inside = pos + h < L
        jj = np.minimum(pos + h, L - 1)
        pe = pg[jj]
        exit_q = np.where(buy_yes, pe - hs, (1.0 - pe) - hs)
        settle = np.full(pos.size, np.nan) if outcome is None else np.where(buy_yes, float(outcome), 1.0 - float(outcome))
        exit_px = np.where(inside, exit_q, settle)
        net = exit_px - entry - rate * entry * (1 - entry) - np.where(inside, rate * np.clip(exit_q, 0, 1) * (1 - np.clip(exit_q, 0, 1)), 0.0)
        keep = np.isfinite(net)
        nets.append(100.0 * net[keep])
        labels += [str(mid_id)] * int(keep.sum())
        hours.append(grid[pos[keep]])
    if not nets:
        return {"n": 0, "mean_c": None, "markets": 0, "net_c": np.zeros(0), "hours": np.zeros(0, np.int64), "labels": []}
    net_c = np.concatenate(nets)
    return {"n": int(net_c.size), "mean_c": float(net_c.mean()), "markets": len(set(labels)), "net_c": net_c, "hours": np.concatenate(hours), "labels": labels}


def b6c_pmmicro_flow_imbalance(archive):
    """T-463."""
    miss = _missing_families(archive, [KT, KH, KS])
    if miss:
        return miss
    meta, candles, trades, cov = _kalshi_meta(archive), _kalshi_candles(archive), _kalshi_trades(archive), _trade_coverage(archive)
    pool_all = [tk for tk in trades if tk in meta and tk in candles]
    from_s = {}
    unusable, capped, gap = [], [], []
    for tk in pool_all:
        c = cov.get(tk)
        if c is None:
            from_s[tk] = 0
            continue
        if c["from_s"] is None:
            unusable.append(tk)
            continue
        from_s[tk] = c["from_s"]
        if not c["complete"]:
            capped.append(tk)
        if c["cutoff_gap"]:
            gap.append(tk)
    pool_all = [tk for tk in pool_all if tk not in set(unusable)]
    pool = [tk for tk in pool_all if meta[tk]["series"] not in CRYPTO_SERIES]
    crypto = [tk for tk in pool_all if meta[tk]["series"] in CRYPTO_SERIES]
    if len(pool) < 2:
        v, why = _verdict([("Kalshi markets with trades and hourly candles (>= 2 non-crypto)", None)])
        return _out({"n_markets": len(pool)}, 0, v, f"only {len(pool)} non-crypto Kalshi markets with trades and hourly candles — {why}")
    split = walk_forward_split(meta, pool, T463_EMBARGO_S)
    st = build_stack(meta, candles, pool, split["test"], from_s)
    flows = {tk: hourly_flow(trades[tk], from_s.get(tk, 0)) for tk in st["seg_ticker"]}
    cand = flow_candidates(st, flows)
    n_cand = int(cand["idx"].size)
    is_segs = np.flatnonzero(np.array([tk in split["calib"] for tk in st["seg_ticker"]]))
    cand_oos = st["oos"][cand["idx"]] if n_cand else np.zeros(0, bool)
    cand_is = np.isin(st["seg"][cand["idx"]], is_segs) if n_cand else np.zeros(0, bool)
    R_cells: dict = {}
    cell_stats = {}
    hour_min, hour_max = int(st["hour"].min()), int(st["hour"].max())
    H = hour_max - hour_min + 1
    nv = next_valid_quote(st)
    side_r = {h: side_returns(st, cand["idx"], h, nv=nv) for h in T463_H}
    head_tr = None
    head_key = T463_HEADLINE
    for f in T463_F:
        for h in T463_H:
            for var in ("follow", "fade"):
                tr = flow_trades(cand, side_r[h][0], side_r[h][1], f, var == "follow")
                key = f"kalshi_f{int(f * 10)}_h{h}_{var}"
                sel, net = tr["sel"], tr["net_c"]
                oos_m, is_m = cand_oos[sel], cand_is[sel]
                entry = np.where(tr["buy_yes"], st["ask"][cand["idx"][sel]], 1.0 - st["bid"][cand["idx"][sel]]).astype(float) if sel.size else np.zeros(0)
                ret = net / 100.0 / np.maximum(entry, 1e-6) if sel.size else np.zeros(0)
                cell_stats[key] = {"n": int(sel.size), "mean_c": float(net.mean()) if sel.size else None, "n_is": int(is_m.sum()),
                                   "mean_c_is": float(net[is_m].mean()) if is_m.any() else None, "n_oos": int(oos_m.sum()),
                                   "mean_c_oos": float(net[oos_m].mean()) if oos_m.any() else None,
                                   "sr_oos": float(sharpe_ratio(ret[oos_m])) if oos_m.sum() >= 2 else None, "venue": "kalshi"}
                if sel.size:
                    R_cells[key] = np.bincount(st["hour"][cand["idx"][sel]] - hour_min, weights=ret, minlength=H)
                if (f, h, var, "kalshi") == head_key:
                    head_tr = {**tr, "ret": ret, "oos": oos_m, "is": is_m}
    # Polymarket cells
    hs, hs_src = pm_half_spread(archive)
    pm_meta, pm_series, pm_flows = _pm_meta(archive), _pm_hourly(archive), _pm_flow(archive)
    pm_cells = {}
    for f in T463_F:
        for h in T463_H:
            for var in ("follow", "fade"):
                key = f"polymarket_f{int(f * 10)}_h{h}_{var}"
                r = pm_flow_trades(pm_flows, pm_series, pm_meta, hs, f, h, var == "follow") if pm_flows and pm_series else {"n": 0, "mean_c": None, "markets": 0}
                cell_stats[key] = {"n": r["n"], "mean_c": r["mean_c"], "markets": r["markets"], "venue": "polymarket",
                                   "sr": float(sharpe_ratio(r["net_c"])) if r["n"] >= 2 else None}
                if r["n"]:
                    pm_cells[key] = (r["hours"], r["net_c"] / 100.0)
                if (f, h, var) == (head_key[0], head_key[1], head_key[2]):
                    pm_head = r
    # headline out of sample
    sel = head_tr["sel"]
    oos_m = head_tr["oos"]
    oos_net = head_tr["net_c"][oos_m]
    oos_ret = head_tr["ret"][oos_m]
    n_oos = int(oos_net.size)
    oos_idx = cand["idx"][sel[oos_m]]
    labels = [st["seg_ticker"][s] for s in st["seg"][oos_idx]]
    cs = cluster_stud(oos_net, labels, N_BOOT) if n_oos >= 4 else {"est": float(oos_net.mean()) if n_oos else None, "ci": [None, None], "p": None, "p_lt": None, "clusters": len(set(labels))}
    all_cs = cluster_stud(head_tr["net_c"], [st["seg_ticker"][s] for s in st["seg"][cand["idx"][sel]]], N_BOOT) if sel.size >= 4 else {"est": None, "ci": [None, None], "p": None}
    perm = {"n_perm": 0, "p": None, "p_lt": None}
    if n_oos >= 8:
        c_oos = {"idx": cand["idx"][cand_oos], "F": cand["F"][cand_oos], "n_trades": cand["n_trades"][cand_oos]}
        ry, rn = side_r[head_key[1]][0][cand_oos], side_r[head_key[1]][1][cand_oos]
        perm = flow_permutation_null(c_oos, st, ry, rn, head_key[0], True, float(oos_net.mean()), N_NULL)
    # DSR over 16 cells, PBO over the non-empty cells
    srs = [v["sr_oos"] for v in cell_stats.values() if v.get("sr_oos") is not None] + [v["sr"] for v in cell_stats.values() if v.get("sr") is not None]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) > 1 else None
    dsr = None
    if n_oos >= 10:
        try:
            dsr = float(deflated_sharpe_ratio(oos_ret, 16, var_trials_sr=var_sr if var_sr and var_sr > 0 else None))
        except Exception:
            dsr = None
    pbo = None
    all_hours_lo = min([hour_min] + [int(v[0].min()) for v in pm_cells.values()])
    all_hours_hi = max([hour_max] + [int(v[0].max()) for v in pm_cells.values()])
    HH = all_hours_hi - all_hours_lo + 1
    cols = []
    for key, vec in R_cells.items():
        col = np.zeros(HH)
        col[hour_min - all_hours_lo: hour_min - all_hours_lo + H] = vec
        cols.append(col)
    for key, (hrs, ret) in pm_cells.items():
        cols.append(np.bincount(hrs - all_hours_lo, weights=ret, minlength=HH))
    if len(cols) >= 2 and HH >= 64:
        try:
            pbo = pbo_cscv(np.column_stack(cols), 8)
        except Exception:
            pbo = None
    # regimes and diagnostics
    hit = float((oos_net > 0).mean()) if n_oos else None
    head_exit_pos, head_kind = exit_marks(st, oos_idx, head_key[1], nv) if n_oos else (np.zeros(0, np.int64), np.zeros(0, np.int8))
    exit_kinds = exit_kind_counts(head_kind)
    decomp = exit_decomposition(st, oos_idx, head_tr["buy_yes"][oos_m], head_exit_pos, oos_net) if n_oos else {}
    cats = np.array([st["seg_cat"][s] for s in st["seg"][oos_idx]]) if n_oos else np.zeros(0)
    by_cat = {c: {"n": int((cats == c).sum()), "mean_c": float(oos_net[cats == c].mean())} for c in set(cats.tolist())} if n_oos else {}
    htc = st["htc"][oos_idx] if n_oos else np.zeros(0)
    final48 = {"n": int((htc <= 48).sum()), "mean_c": float(oos_net[htc <= 48].mean()) if (htc <= 48).any() else None}
    beyond48 = {"n": int((htc > 48).sum()), "mean_c": float(oos_net[htc > 48].mean()) if (htc > 48).any() else None}
    # 1-hour-delay sensitivity (next candle's closing ask)
    cand_d = flow_candidates(st, flows, delay=1)
    delay_stat = None
    if cand_d["idx"].size:
        ry_d, rn_d = side_returns(st, cand_d["idx"], head_key[1], nv=nv)
        tr_d = flow_trades(cand_d, ry_d, rn_d, head_key[0], True)
        oos_d = st["oos"][cand_d["idx"][tr_d["sel"]]]
        delay_stat = {"n_oos": int(oos_d.sum()), "mean_c_oos": float(tr_d["net_c"][oos_d].mean()) if oos_d.any() else None}
    crypto_stat = {"n_markets": len(crypto)}
    if len(crypto) >= 2:
        st_c = build_stack(meta, candles, crypto, set(), from_s)
        if st_c is not None:
            fl_c = {tk: hourly_flow(trades[tk], from_s.get(tk, 0)) for tk in st_c["seg_ticker"]}
            cc = flow_candidates(st_c, fl_c)
            if cc["idx"].size:
                ry_c, rn_c = side_returns(st_c, cc["idx"], head_key[1])
                tr_c = flow_trades(cc, ry_c, rn_c, head_key[0], True)
                crypto_stat.update(n=int(tr_c["sel"].size), mean_c=float(tr_c["net_c"].mean()) if tr_c["sel"].size else None)
    obs = cs.get("est")
    rows = [(f"trial null (F permuted across qualifying hours within market, {perm.get('n_perm', 0)} permutations) p {_f(perm.get('p'))}",
             None if perm.get("p") is None else perm["p"] < 0.01, perm.get("p_lt") is not None and perm["p_lt"] < 0.01),
            (f"market-clustered studentized bootstrap p {_f(cs.get('p'))} ({cs.get('clusters', 0)} markets)",
             None if cs.get("p") is None else cs["p"] < 0.01, cs.get("p_lt") is not None and cs["p_lt"] < 0.01)]
    crit = [all_constructions(rows, f"out-of-sample headline cell (|F| > 0.5, >= 20 prints, hold 6 h, follow): {n_oos} trades, mean net {_s(obs)} cents/contract > 0 with p < 0.01")]
    crit.append((f"DSR {_f(dsr)} >= 0.95 over the 16 declared cells ({sum(1 for v in cell_stats.values() if v['n'] > 0)} non-empty)", None if dsr is None else dsr >= 0.95, False))
    pbo_v = (pbo or {}).get("pbo")
    crit.append((f"PBO {_f(pbo_v)} < 0.3 (CSCV over {len(cols)} non-empty cells' hourly P&L)", None if pbo_v is None else pbo_v < 0.3, False))
    verdict, why = _decide(crit, n_oos, 3000, "out-of-sample trades")
    pm_n = sum(v["n"] for v in cell_stats.values() if v.get("venue") == "polymarket")
    qx, sx = decomp.get("quote_exits", {}), decomp.get("settled", {})
    reason = (f"Kalshi taker-flow imbalance on {len(pool)} non-crypto markets with trade prints and hourly candles ({dict(Counter(meta[t]['cat'] for t in pool))}); "
              f"print coverage: {len(capped)} markets capped at the page cap (hours before complete_from dropped), {len(gap)} of them spanning the 2026-08-16 cutoff "
              f"with the historical route unread, {len(unusable)} unusable; {n_cand} qualifying market-hours (>= 20 prints, valid touch, mid in [0.05, 0.95]). "
              f"Walk-forward split at open {_day_str(split['split_s']) if split['split_s'] else 'n/a'} (24 h embargo): {len(split['calib'])} calibration, "
              f"{len(split['embargoed'])} embargoed, {len(split['test'])} test markets. Headline cell: {sel.size} trades in all (mean {_s(all_cs.get('est'))} cents, "
              f"{_ci_txt(all_cs.get('ci'))}); out of sample {n_oos} trades, mean net {_s(obs)} cents/contract ({_ci_txt(cs.get('ci'))}; cluster p {_f(cs.get('p'))}; "
              f"permutation p {_f(perm.get('p'))}, null mean {_s(perm.get('null_mean'))}), hit rate {_f(hit)}; 1-hour-delay fill sensitivity {delay_stat}. "
              f"Exit marks (out of sample): {exit_kinds['quote_at_k']} at the 6-hour quote, {exit_kinds['held_to_next_valid_quote']} held to the next valid quote (invalid book at 6 h, "
              f"<= {EXIT_WAIT_H} h), {exit_kinds['settled_close_hour_or_later']} settled at the result (exit on or after the close hour: the close-hour candle's close is the post-close "
              f"empty book), {exit_kinds['settled_no_valid_quote_within_wait']} settled for want of a valid quote. Cost decomposition of the {qx.get('n', 0)} quote-exit trades (cents): "
              f"mid-to-mid gross {_s(qx.get('gross_mid_to_mid_c'))}, entry half-spread {_f(qx.get('entry_half_spread_c'), 2)}, exit half-spread {_f(qx.get('exit_half_spread_c'), 2)}, "
              f"fees {_f(qx.get('fee_in_c'), 2)} + {_f(qx.get('fee_out_c'), 2)}, net {_s(qx.get('net_c'))}: the mid does not move against the taken side, the loss is the spread crossed "
              f"twice plus two fees; the {sx.get('n', 0)} settled trades enter at {_f(sx.get('mean_entry'))} and settle at {_f(sx.get('mean_settlement'))} on average (hit {_f(sx.get('hit_rate'))}). "
              f"Final 48 h {final48} vs earlier {beyond48}; by category {by_cat}; crypto bucket {crypto_stat}. DSR {_f(dsr)} (var of cell Sharpes {_f(var_sr, 5)}); PBO {_f(pbo_v)}. "
              f"Polymarket cells: {pm_n} trades in all (half-spread {hs * 100:.2f} cents [{hs_src}], Gamma fee flag), headline-equivalent "
              f"{pm_head.get('n', 0)} trades mean {_s(pm_head.get('mean_c'))}. Entry at the ask / 1 - bid of the hour-close candle (what the next candle opens at), "
              f"exit at the bid / 1 - ask after 6 h (next valid quote when that book is invalid) or settlement; {FEE_NOTE} — {why}")
    stat = {"n_markets": len(pool), "n_markets_crypto": len(crypto), "coverage": {"capped_markets": len(capped), "cutoff_gap_markets": len(gap), "unusable": len(unusable),
            "note": "hours starting before a capped market's complete_from are dropped"}, "n_candidates": n_cand,
            "split": {"split_s": split["split_s"], "calib": len(split["calib"]), "embargoed": len(split["embargoed"]), "test": len(split["test"]), "embargo_hours": 24},
            "headline": {"cell": "kalshi_f5_h6_follow", "n_all": int(sel.size), "mean_c_all": all_cs.get("est"), "ci_all": all_cs.get("ci"), "n_oos": n_oos, "mean_c_oos": obs,
                         "ci_oos": cs.get("ci"), "p_cluster": cs.get("p"), "p_lt_cluster": cs.get("p_lt"), "clusters": cs.get("clusters"), "permutation": perm, "hit_rate_oos": hit,
                         "delay_sensitivity": delay_stat, "exit_kinds_oos": exit_kinds, "exit_wait_hours": EXIT_WAIT_H, "decomposition_oos": decomp},
            "cells": cell_stats, "dsr": dsr, "var_trial_sr": var_sr, "pbo": pbo, "by_category_oos": by_cat, "final_48h_oos": final48, "beyond_48h_oos": beyond48,
            "crypto_bucket": crypto_stat, "polymarket": {"half_spread": hs, "half_spread_source": hs_src, "n_trades": pm_n, "markets_with_flow": len(pm_flows),
                                                          "markets_with_hourly_price": len(pm_series)},
            "costs": {"taker_fee": TAKER_FEE, "fee_note": FEE_NOTE}, "criteria": [(c[0], c[1]) for c in crit], "rule10": "signal-driven entries: no grid phase"}
    return _out(stat, n_oos, verdict, reason)


# ================================================================================================ T-411 engine ==

def t411_cells() -> list:
    return [(g, m, c) for g in T411_GAMMA for m in T411_M for c in T411_CAP]


def _rolling_var(x: np.ndarray, seg_start: np.ndarray, pos: np.ndarray, window: int = 24) -> np.ndarray:
    """Variance of the last ``window`` values of x (per position, within segment, including the current one; nan until
    2 values)."""
    N = x.size
    cs = np.cumsum(np.nan_to_num(x).astype(np.float64))
    cs2 = np.cumsum(np.nan_to_num(x).astype(np.float64) ** 2)
    k = np.minimum(pos + 1, window)
    lo = np.arange(N) - k                                    # index before the window
    s = cs - np.where(lo >= 0, cs[np.maximum(lo, 0)], 0.0)
    s2 = cs2 - np.where(lo >= 0, cs2[np.maximum(lo, 0)], 0.0)
    var = np.maximum(s2 / k - (s / k) ** 2, 0.0)
    var[k < 2] = np.nan
    return var


def mm_tables(st: dict, trades: dict, flows: dict, events: np.ndarray, pull_hours: int = T411_PULL_HOURS) -> dict:
    """Pre-computation for the T-411 replay on a stack. Quoting periods: positions P with a valid touch (bid >= 0.01,
    ask <= 0.99, spread <= 10 cents), >= ``pull_hours`` to close, no scheduled event within one hour of the period and
    a usable print coverage. Per quoting period: the touch, the one-tick widening flag, sigma_day^2, tau, the previous
    hour's flow F, the UTC day. For periods with prints: through-size and size-weighted markout sums for the bid levels
    touch + {-2, -1, 0, +1} ticks (prints whose taker sold YES strictly below the level) and the ask levels touch +
    {-1, 0, +1, +2} ticks (taker bought YES strictly above); the markout mid is the grid mid at P + 2 (the first candle
    closing at least 60 minutes after any print of the period) when that book is valid, else the first valid mid after it
    within EXIT_WAIT_H hours, else the settlement value (also past the market's end); ``remarked`` flags the positions
    whose P + 2 book existed but was not a valid mid."""
    N = st["n"]
    bid, ask, mid, pos, seglen, htc, seg, hour = st["bid"], st["ask"], st["mid"], st["pos"], st["seglen"], st["htc"], st["seg"], st["hour"]
    dmid = mid.astype(np.float64) - np.nan_to_num(_shift_back(mid, pos, 1)).astype(np.float64)
    dmid[pos == 0] = 0.0
    var_h = _rolling_var(dmid, st["seg_start"], pos, 24)
    sigma_day2 = 24.0 * np.nan_to_num(var_h)
    tau = np.minimum(htc, 24) / 24.0
    quote_ok = (bid >= TICK - EPS) & (ask <= 1.0 - TICK + EPS) & (ask - bid <= SPREAD_MAX + EPS) & (ask > bid)
    active = quote_ok & (htc >= pull_hours)
    if "usable" in st:
        active &= st["usable"]
    if events.size:
        start_s = hour * HOUR
        k = np.searchsorted(events, start_s - HOUR, side="left")
        nxt = events[np.minimum(k, events.size - 1)]
        near = (k < events.size) & (nxt < start_s + 2 * HOUR)
        active &= ~near
    else:
        near = np.zeros(N, bool)
    # markout mid: the first valid mid at or after P + 2 within EXIT_WAIT_H hours (an empty, one-sided or > 10-cent book has no
    # mid; the close-hour candle closes on the post-close book), the settlement value past the market's end
    ep2, kind2 = exit_marks(st, np.arange(N, dtype=np.int64), 2, next_valid_quote(st))
    settled2 = ep2 < 0
    mark = np.where(settled2, st["result"].astype(np.float64), mid[np.where(settled2, 0, ep2)].astype(np.float64))
    remarked = (kind2 != EXIT_AT_K) & (pos + 2 < seglen)       # the P + 2 book existed but was not a valid mid: the fill is re-marked
    # previous hour's flow
    F_prev = np.zeros(N, dtype=np.float32)
    seg_of = {tk: i for i, tk in enumerate(st["seg_ticker"])}
    for tk, (hour_end, n, F, _) in flows.items():
        s = seg_of.get(tk)
        if s is None:
            continue
        lo, hi = st["seg_start"][s], st["seg_start"][s + 1]
        h0 = int(hour[lo])
        p = hour_end - h0                                    # flow of [H-1, H) is known at H = period index P
        ok = (p >= 0) & (p < hi - lo)
        F_prev[lo + p[ok]] = F[ok]
    # prints -> (position, level) aggregates
    rows_pos, Qb, Sb, Qa, Sa = [], [], [], [], []
    for tk, (t, price, side, qty) in trades.items():
        s = seg_of.get(tk)
        if s is None or t.size == 0:
            continue
        lo, hi = st["seg_start"][s], st["seg_start"][s + 1]
        h0 = int(hour[lo])
        P = t // HOUR - h0
        ok = (P >= 0) & (P < hi - lo)
        P, pr, sd, q = P[ok] + lo, price[ok].astype(np.float64), side[ok], qty[ok].astype(np.float64)
        ok = active[P] & np.isfinite(mark[P])
        P, pr, sd, q = P[ok], pr[ok], sd[ok], q[ok]
        if P.size == 0:
            continue
        uniq, inv = np.unique(P, return_inverse=True)
        qb = np.zeros((uniq.size, 4))
        sb = np.zeros((uniq.size, 4))
        qa = np.zeros((uniq.size, 4))
        sa = np.zeros((uniq.size, 4))
        mk = mark[P]
        for li, L in enumerate((-2, -1, 0, 1)):
            lvl = bid[P].astype(np.float64) + L * TICK
            thr = (sd < 0) & (pr < lvl - EPS)
            qb[:, li] = np.bincount(inv, weights=np.where(thr, q, 0.0), minlength=uniq.size)
            sb[:, li] = np.bincount(inv, weights=np.where(thr, q * mk, 0.0), minlength=uniq.size)
        for li, L in enumerate((-1, 0, 1, 2)):
            lvl = ask[P].astype(np.float64) + L * TICK
            thr = (sd > 0) & (pr > lvl + EPS)
            qa[:, li] = np.bincount(inv, weights=np.where(thr, q, 0.0), minlength=uniq.size)
            sa[:, li] = np.bincount(inv, weights=np.where(thr, q * mk, 0.0), minlength=uniq.size)
        rows_pos.append(uniq)
        Qb.append(qb)
        Sb.append(sb)
        Qa.append(qa)
        Sa.append(sa)
    if rows_pos:
        rp = np.concatenate(rows_pos)
        order = np.argsort(rp, kind="stable")
        rp = rp[order]
        Qb, Sb, Qa, Sa = (np.concatenate(x)[order] for x in (Qb, Sb, Qa, Sa))
    else:
        rp = np.zeros(0, np.int64)
        Qb = Sb = Qa = Sa = np.zeros((0, 4))
    # market-days of quoting
    act_idx = np.flatnonzero(active)
    day = (hour[act_idx] * HOUR) // DAY
    md_key = seg[act_idx].astype(np.int64) * 100_000 + day
    md_uniq, md_inv = np.unique(md_key, return_inverse=True)
    md_seg = (md_uniq // 100_000).astype(np.int64)
    md_day = (md_uniq % 100_000).astype(np.int64)
    md_of_pos = np.full(N, -1, dtype=np.int64)
    md_of_pos[act_idx] = md_inv
    return {"active": active, "near_event": near, "sigma_day2": sigma_day2, "tau": tau, "F_prev": F_prev, "mark": mark, "remarked": remarked, "rows_pos": rp,
            "Qb": Qb, "Sb": Sb, "Qa": Qa, "Sa": Sa, "md_seg": md_seg, "md_day": md_day, "md_of_pos": md_of_pos, "n_market_days": int(md_uniq.size)}


def mm_replay(st: dict, tb: dict, cells: Sequence[tuple], maker_fee: float = MAKER_FEE, flow_pull: float = T411_FLOW_PULL) -> dict:
    """The T-411 replay over every cell at once (cells on axis 1). Returns daily P&L matrices (market-days x cells) net
    and gross of maker fees, filled size per cell, the sum of realised spreads, and per-cell fill counts."""
    bid, ask, mid, seg = st["bid"], st["ask"], st["mid"], st["seg"]
    cells = list(cells)
    C = len(cells)
    gamma = np.array([c[0] for c in cells])
    mthr = np.array([c[1] for c in cells])
    cap = np.array([c[2] for c in cells])
    S = len(st["seg_ticker"])
    inv = np.zeros((S, C))
    lastP = np.full((S, C), -10, dtype=np.int64)
    last_pnl = np.zeros((S, C))
    last_qty = np.zeros((S, C))
    MD = tb["n_market_days"]
    daily_net = np.zeros((MD, C))
    daily_gross = np.zeros((MD, C))
    filled = np.zeros(C)
    fills_n = np.zeros(C)
    rsp_sum = np.zeros(C)
    remarked_n = np.zeros(C)
    remarked_qty = np.zeros(C)
    rp = tb["rows_pos"]
    out = {"daily_net": daily_net, "daily_gross": daily_gross, "filled": filled, "fills_n": fills_n, "realised_spread_sum": rsp_sum,
           "remarked_fills_n": remarked_n, "remarked_contracts": remarked_qty}
    if rp.size == 0:
        return out
    Ppos = st["pos"][rp]
    hours = st["hour"][rp]
    # process in order of absolute hour so that state (inventory, last fills) is causal across the markets' own timelines
    order = np.argsort(hours, kind="stable")
    rp, Ppos, hours = rp[order], Ppos[order], hours[order]
    Qb, Sb, Qa, Sa = tb["Qb"][order], tb["Sb"][order], tb["Qa"][order], tb["Sa"][order]
    rem = tb["remarked"][rp] if "remarked" in tb else np.zeros(rp.size, bool)
    bounds = np.r_[0, np.flatnonzero(hours[1:] != hours[:-1]) + 1, hours.size]
    rng_c = np.arange(C)
    for bi in range(bounds.size - 1):
        lo, hi = bounds[bi], bounds[bi + 1]
        p = rp[lo:hi]
        m = seg[p].astype(np.int64)
        n = p.size
        b0, a0 = bid[p].astype(np.float64), ask[p].astype(np.float64)
        widen = (a0 - b0 < 0.02 - EPS).astype(np.int64)
        q = inv[m] / cap[None, :]                                                       # (n, C)
        skew = -gamma[None, :] * tb["sigma_day2"][p][:, None] * tb["tau"][p][:, None] * q
        s_ticks = np.clip(np.rint(skew / TICK), -1, 1).astype(np.int64)
        bid_off = s_ticks - widen[:, None]                                              # in {-2, -1, 0, 1}
        ask_off = s_ticks + widen[:, None]                                              # in {-1, 0, 1, 2}
        bid_L = b0[:, None] + bid_off * TICK
        ask_L = a0[:, None] + ask_off * TICK
        Fp = tb["F_prev"][p].astype(np.float64)
        pull_bid = (Fp < -flow_pull)[:, None]
        pull_ask = (Fp > flow_pull)[:, None]
        Pidx = Ppos[lo:hi]
        la = (lastP[m] == (Pidx[:, None] - 2)) & (last_qty[m] > 0)
        mo = np.where(la, -last_pnl[m] / np.maximum(last_qty[m], 1e-12), 0.0)           # markout loss per contract (dollars)
        pull_a = la & (mo > mthr[None, :] - 1e-12)
        rows = np.arange(n)[:, None]
        qb = Qb[lo:hi][rows, bid_off + 2]
        sb = Sb[lo:hi][rows, bid_off + 2]
        qa = Qa[lo:hi][rows, ask_off + 1]
        sa = Sa[lo:hi][rows, ask_off + 1]
        room_b = np.maximum(cap[None, :] - inv[m], 0.0)
        room_a = np.maximum(cap[None, :] + inv[m], 0.0)
        fb = np.where(qb > 0, np.minimum(1.0, room_b / np.maximum(qb, 1e-12)), 0.0)
        fa = np.where(qa > 0, np.minimum(1.0, room_a / np.maximum(qa, 1e-12)), 0.0)
        fb = np.where(pull_bid | pull_a | (bid_L < TICK - EPS), 0.0, fb)
        fa = np.where(pull_ask | pull_a | (ask_L > 1.0 - TICK + EPS), 0.0, fa)
        gross = fb * (sb - bid_L * qb) + fa * (ask_L * qa - sa)
        fee = maker_fee * (bid_L * (1 - bid_L) * fb * qb + ask_L * (1 - ask_L) * fa * qa)
        net = gross - fee
        qty = fb * qb + fa * qa
        inv[m] += fb * qb - fa * qa
        any_fill = qty > 0
        lastP[m] = np.where(any_fill, Pidx[:, None], lastP[m])
        last_pnl[m] = np.where(any_fill, gross, last_pnl[m])
        last_qty[m] = np.where(any_fill, qty, last_qty[m])
        md = tb["md_of_pos"][p]
        ok = md >= 0
        if ok.any():
            np.add.at(daily_net, (md[ok][:, None], rng_c[None, :]), net[ok])
            np.add.at(daily_gross, (md[ok][:, None], rng_c[None, :]), gross[ok])
        filled += qty.sum(axis=0)
        fills_n += any_fill.sum(axis=0)
        rsp_sum += 2.0 * gross.sum(axis=0)
        r = rem[lo:hi][:, None]
        remarked_n += (any_fill & r).sum(axis=0)
        remarked_qty += (qty * r).sum(axis=0)
    return out


def b6c_pmmicro_market_making(archive):
    """T-411."""
    miss = _missing_families(archive, [KT, KH, KS])
    if miss:
        return miss
    meta, candles, trades, cov = _kalshi_meta(archive), _kalshi_candles(archive), _kalshi_trades(archive), _trade_coverage(archive)
    events, ev_note = _event_times(archive)
    pool_all = [tk for tk in trades if tk in meta and tk in candles]
    from_s, unusable, capped, gap = {}, [], [], []
    for tk in pool_all:
        c = cov.get(tk)
        if c is None:
            from_s[tk] = 0
            continue
        if c["from_s"] is None:
            unusable.append(tk)
            continue
        from_s[tk] = c["from_s"]
        if not c["complete"]:
            capped.append(tk)
        if c["cutoff_gap"]:
            gap.append(tk)
    pool_all = [tk for tk in pool_all if tk not in set(unusable)]
    pool = [tk for tk in pool_all if meta[tk]["series"] not in CRYPTO_SERIES]
    crypto = [tk for tk in pool_all if meta[tk]["series"] in CRYPTO_SERIES]
    if len(pool) < 2:
        v, why = _verdict([("Kalshi markets with trades and hourly candles (>= 2 non-crypto)", None)])
        return _out({"n_markets": len(pool)}, 0, v, f"only {len(pool)} non-crypto Kalshi markets with trades and hourly candles — {why}")
    split = walk_forward_split(meta, pool, 0)
    st = build_stack(meta, candles, pool, split["test"], from_s)
    flows = {tk: hourly_flow(trades[tk], from_s.get(tk, 0)) for tk in st["seg_ticker"]}
    tb = mm_tables(st, {tk: trades[tk] for tk in st["seg_ticker"]}, flows, events)
    cells = t411_cells()
    rep = mm_replay(st, tb, cells)
    rep0 = mm_replay(st, tb, cells, maker_fee=0.0)
    MD = tb["n_market_days"]
    md_oos = np.array([st["seg_ticker"][s] in split["test"] for s in tb["md_seg"]]) if MD else np.zeros(0, bool)
    md_is = ~md_oos
    md_cat = np.array([st["seg_cat"][s] for s in tb["md_seg"]]) if MD else np.zeros(0)
    D = rep["daily_net"]
    names = [f"g{g}_m{int(round(m * 100))}_cap{int(c)}" for g, m, c in cells]
    cell_stats = {}
    for ci, nm in enumerate(names):
        col = D[:, ci]
        cell_stats[nm] = {"mean_is": float(col[md_is].mean()) if md_is.any() else None, "mean_oos": float(col[md_oos].mean()) if md_oos.any() else None,
                          "sr_oos": float(sharpe_ratio(col[md_oos])) if md_oos.sum() >= 2 else None, "fills": int(rep["fills_n"][ci]), "filled_contracts": float(rep["filled"][ci]),
                          "mean_oos_no_maker_fee": float(rep0["daily_net"][md_oos, ci].mean()) if md_oos.any() else None}
    best_ci = int(np.argmax([cell_stats[nm]["mean_is"] if cell_stats[nm]["mean_is"] is not None else -np.inf for nm in names])) if md_is.any() else 0
    head = names[best_ci]
    x = D[md_oos, best_ci]
    n_oos = int(x.size)
    labels = [st["seg_ticker"][s] for s in tb["md_seg"][md_oos]]
    cs = cluster_stud(x, labels, N_BOOT) if n_oos >= 4 else {"est": float(x.mean()) if n_oos else None, "ci": [None, None], "p": None, "p_lt": None, "clusters": len(set(labels))}
    all_cs = cluster_stud(D[:, best_ci], [st["seg_ticker"][s] for s in tb["md_seg"]], N_BOOT) if MD >= 4 else {"est": None, "ci": [None, None], "p": None}
    cats_oos = Counter(md_cat[md_oos].tolist()) if n_oos else Counter()
    top3 = [c for c, _ in cats_oos.most_common(3)]
    by_cat = {c: {"market_days": int(k), "mean_daily": float(x[md_cat[md_oos] == c].mean())} for c, k in cats_oos.items()}
    cat_ok = None if len(top3) < 3 else all(by_cat[c]["mean_daily"] > 0 for c in top3)
    srs = [v["sr_oos"] for v in cell_stats.values() if v["sr_oos"] is not None]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) > 1 else None
    dsr = None
    if n_oos >= 10:
        try:
            dsr = float(deflated_sharpe_ratio(x, len(cells), var_trials_sr=var_sr if var_sr and var_sr > 0 else None))
        except Exception:
            dsr = None
    filled = float(rep["filled"][best_ci])
    rsp = float(rep["realised_spread_sum"][best_ci] / filled * 100) if filled > 0 else None
    remarked = {"fills": int(rep["remarked_fills_n"][best_ci]), "contracts": float(rep["remarked_contracts"][best_ci]),
                "print_periods": int(tb["remarked"][tb["rows_pos"]].sum()) if tb["rows_pos"].size else 0, "print_periods_all": int(tb["rows_pos"].size),
                "rule": f"P + 2 book empty, one-sided, wider than 10 cents or the close hour: marked at the next valid mid within {EXIT_WAIT_H} h, else settlement"}
    sr_daily = float(sharpe_ratio(x, 365)) if n_oos >= 2 else None
    # near-resolution (48-96 h) vs earlier, by the market-day's minimum hours to close
    htc_md = np.full(MD, 10 ** 6)
    act = np.flatnonzero(tb["active"])
    np.minimum.at(htc_md, tb["md_of_pos"][act], st["htc"][act])
    near = (htc_md[md_oos] < 96)
    regime = {"48_96h_to_close": {"market_days": int(near.sum()), "mean_daily": float(x[near].mean()) if near.any() else None},
              "beyond_96h": {"market_days": int((~near).sum()), "mean_daily": float(x[~near].mean()) if (~near).any() else None}}
    obs = cs.get("est")
    crit = [(f"out-of-sample mean daily net P&L {_s(obs, 4)} $/market-day > 0 with market-clustered studentized bootstrap p {_f(cs.get('p'))} < 0.01 "
             f"({cs.get('clusters', 0)} markets, {n_oos} market-days; cell {head} chosen on the calibration half)", None if cs.get("p") is None else cs["p"] < 0.01,
             cs.get("p_lt") is not None and cs["p_lt"] < 0.01)]
    cat_note = ("" if len(top3) >= 3 else f" [only {len(top3)} categories have quoting market-days: the other series' markets live under 48 h "
                                            f"(pull rule d) or have no prints, so the criterion cannot be evaluated as worded]")
    crit.append((f"positive in each of the 3 largest categories by out-of-sample market-days {[(c, by_cat[c]) for c in top3]}{cat_note}", cat_ok, False))
    crit.append((f"DSR {_f(dsr)} >= 0.95 over the 27 declared cells", None if dsr is None else dsr >= 0.95, False))
    crit.append((f"paper-trading realised spread within 50% of the replay before any capital (a forward live-quoting test; replay half: mean realised spread "
                 f"{_s(rsp)} cents per filled contract over {filled:.0f} contracts) — needs live fills, not in any archive", None, False))
    verdict, why = _decide(crit, n_oos, 1500, "out-of-sample market-days")
    reason = (f"Kalshi trade-through market-making replay on {len(pool)} non-crypto markets with prints and hourly candles ({dict(Counter(meta[t]['cat'] for t in pool))}; "
              f"print coverage: {len(capped)} capped markets (hours before complete_from dropped), {len(gap)} spanning the 2026-08-16 cutoff with the historical route unread, "
              f"{len(unusable)} unusable); quoting periods need a valid touch, >= 48 h to close (pull rule d) and no scheduled event within an hour (rule c: {ev_note}; "
              f"game starts not in the archived metadata, so not applied: conservative); {MD} market-days in all. Walk forward: calibration {len(split['calib'])} markets picks "
              f"{head} (IS mean {_s(cell_stats[head]['mean_is'], 4)} $/day); test {len(split['test'])} markets: {n_oos} market-days, mean daily net {_s(obs, 4)} $ "
              f"({_ci_txt(cs.get('ci'), 4)}; cluster p {_f(cs.get('p'))}; daily Sharpe annualised {_f(sr_daily)}); without maker fees {_s(cell_stats[head]['mean_oos_no_maker_fee'], 4)}; "
              f"{int(rep['fills_n'][best_ci])} filled periods, {filled:.0f} contracts, mean realised spread {_s(rsp)} cents; {remarked['fills']} filled periods ({remarked['contracts']:.0f} "
              f"contracts) re-marked because the P + 2 book was empty, one-sided, wider than 10 cents or the close hour ({remarked['print_periods']} of {remarked['print_periods_all']} "
              f"print periods): marked at the next valid mid within {EXIT_WAIT_H} h, else settlement. By category {by_cat}; regime {regime}. "
              f"DSR {_f(dsr)} (var of 27 cell Sharpes {_f(var_sr, 5)}). Crypto bucket excluded ({len(crypto)} markets). Rewards and rebates excluded; {FEE_NOTE}; markout mid = the "
              f"first valid candle close >= 60 min after the print (P + 2 or the next valid book), settlement when closed — {why}")
    stat = {"n_markets": len(pool), "n_markets_crypto": len(crypto), "coverage": {"capped_markets": len(capped), "cutoff_gap_markets": len(gap), "unusable": len(unusable)},
            "market_days_all": MD, "split": {"split_s": split["split_s"], "calib": len(split["calib"]), "test": len(split["test"])},
            "headline": {"cell": head, "n_oos_market_days": n_oos, "mean_daily_oos": obs, "ci_oos": cs.get("ci"), "p_cluster": cs.get("p"), "p_lt_cluster": cs.get("p_lt"),
                         "clusters": cs.get("clusters"), "mean_daily_all": all_cs.get("est"), "ci_all": all_cs.get("ci"), "sr_daily_annualised_oos": sr_daily,
                         "fills": int(rep["fills_n"][best_ci]), "filled_contracts": filled, "mean_realised_spread_cents": rsp,
                         "mean_daily_oos_no_maker_fee": cell_stats[head]["mean_oos_no_maker_fee"], "remarked": remarked},
            "cells": cell_stats, "by_category_oos": by_cat, "top3_categories": top3, "regime_oos": regime, "dsr": dsr, "var_trial_sr": var_sr,
            "events": ev_note, "costs": {"maker_fee": MAKER_FEE, "fee_note": FEE_NOTE, "rewards_rebates": "excluded"},
            "not_implemented": ["paper-trading realised spread within 50% of the replay (forward live quoting)", "pull rule (c) for game starts (no start time in the archived metadata)"],
            "criteria": [(c[0], c[1]) for c in crit], "rule10": "print-driven fills: no grid phase"}
    return _out(stat, n_oos, verdict, reason)


# ==================================================================================================== registry ==

HARNESSES = {
    "b6c_pmmicro_hourly_reversal": b6c_pmmicro_hourly_reversal,
    "b6c_pmmicro_market_making": b6c_pmmicro_market_making,
    "b6c_pmmicro_flow_imbalance": b6c_pmmicro_flow_imbalance,
}

THEORY_MAP = {
    "T-408": "b6c_pmmicro_hourly_reversal",
    "T-411": "b6c_pmmicro_market_making",
    "T-463": "b6c_pmmicro_flow_imbalance",
}
