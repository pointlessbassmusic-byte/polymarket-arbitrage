"""
Batch 6c, group ``events``: three single-stock event claims on S&P 500 names (the dividend-month premium, the post-
effective reversal of index additions, the FINRA daily off-exchange short-volume ratio), on the Yahoo single-stock
histories of ``mandel.data.market_history`` (``daily-history-<T>`` bars, ``daily-events-<T>`` dividends) and the S&P 500
tables and FINRA files of ``mandel.data.public_history`` (``wikipedia-sp500-constituents`` / ``-changes``,
``fja-sp500-components``, ``finra-regsho-cnms-<YYYY-MM>``).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-374  current S&P 500 dividend payers, firm-months 2010-01..2026-09 (min_n 5,000 dividend firm-months). A month is a
           predicted dividend month when the firm went ex in the same calendar month a year earlier (Hartzmark-Solomon,
           point in time); its span runs from the month start (the previous month's last close) to the close of the last
           session before the predicted ex-date (that ex-date's day of month, a year on). A non-dividend month of a
           point-in-time payer (an ex-date in the 12 months before the month) has the same span: month start to the
           session before the day of month of the firm's latest ex-date. Market-adjusted = total return minus SPY's
           over the span. Pass: the difference (dividend minus non-dividend firm-months, pooled over the same firms) >=
           20 bp with clustered p < 0.01 in 2010-2017 and in 2018-2026 (and over the whole span, as the claim states)
           AND the same on the ETF-only robustness (VYM, SCHD, SDY, DVY) AND DSR > 0.95 at the trial's 4 trials (the
           pass names the DSR without a level; 0.95 is the house threshold).
  * T-334  S&P 500 additions with effective dates 2010-2026 (min_n 150 events): short the added stock and buy SPY at the
           effective-date close (the first date in the fja05680 membership), cover 20 sessions later. Pass: mean 20-day
           excess return net of 10 bps per leg per trade < -0.2% AND its one-sided 95% upper bound < 0 (bootstrap
           clustered by effective date) AND a size-matched placebo of non-changing members on the same dates centred on
           zero. The 5-year buckets (the Greenwood-Sammon trend) are reported.
  * T-394  point-in-time S&P 500 members, signal days 2019-2026 (min_n 5,000 events): FINRA CNMS off-exchange
           short-volume ratio (short / total volume) z-scored on the symbol's trailing 60 file days (t included) > 2;
           enter at the next session's open, exit at the open five sessions later; abnormal = minus SPY over the same
           opens. Pass: the one-sided 95% upper bound of the mean abnormal return net of costs < 0 (date-clustered
           bootstrap) over >= 5,000 events AND negative in both halves (2019-2022, 2023-2026); otherwise the trial parks
           the claim as 'daily SVR not informative' (``park_condition``). Gross and net, the yearly walk-forward means and
           the Fama-MacBeth slope of the 5-day return on z (secondary) are reported.

Conventions
  * Data. Every bundle through ``archive.load``; a row is used only when its ``available_at`` is not after the bundle's
    capture time. Prices are Yahoo ``adjclose`` (total return; opens on the same basis, open x adjclose / close) on the
    SPY session calendar from 2008; a bar with zero volume is a stale print and is not used (the Smurfit Westrock series
    before its 2024 listing is such a run). Dividends are ``daily-events-<T>`` ex-dates (Yahoo's date is the ex-date;
    ex-dates are not revised, so a prior-year schedule is point in time).
  * Membership (T-334, T-394). Point-in-time S&P 500 members are the fja05680 change-date snapshots (available at the
    change day's 09:30 ET); changes after the file's last date (2026-08-18) come from the Wikipedia changes table.
    Additions are fja first appearances (the trial's 'additions = first appearance') confirmed by a Wikipedia change
    row adding the same ticker within 10 calendar days (the claim's cross-check against S&P press releases), or adding
    it under another spelling (fja uses later tickers: DLPH = APTV, UA = UAA, Q = IQV, JOYG = JOY, ANR = ANRZQ; matched
    on the company name, or as the replacement of the same leaver); before 2010-06, where the Wikipedia table is
    incomplete, fja joins are accepted unconfirmed (NRG, URBN, BRK.B, DISCA, OKE). A ticker change of one company is
    not an addition: it is judged on the tickers, never on the free-text reason, which often describes the company
    that LEFT (Allergan's row adds American Airlines; Fossil's adds Willis Towers Watson; Navient's adds Evergy). A
    row is a ticker change when its removed and added names match (DuPont / DuPont, WLTW / WTW), or when its removed
    ticker is the fja change's only unexplained leaver and its added ticker joins (Questar / QEP, Dow Chemical /
    DowDuPont, Ceridian / Dayforce), unless the leaver's own Yahoo history trades on across the change (Fossil,
    Navient); a row whose reason says the company 'remained in the index' is not an addition (Howmet: Arconic Inc.
    renamed). Unconfirmed first appearances (renames, the GOOG class split) are listed in the stat.
  * Renames. Yahoo keeps a renamed company's history under its new ticker (FB is META; FB itself is now an ETF), so a
    ticker of the past is priced from its own bundle when that has traded bars on the dates, else from its successor's.
    Rename edges, from 2010-06 (the Wikipedia table is incomplete before): Wikipedia rows that are ticker changes of one
    company by the rule above; same-change-date fja leave/join pairs that the Wikipedia table does not explain, when
    the index's names for the two tickers match or Yahoo's history for the new ticker covers the old one's join and the
    old ticker does not trade on as itself (QLogic / Noble is neither: Noble replaced QLogic); ambiguous groups matched
    through the current member's Wikipedia date-added; a join nothing explains on a change where Wikipedia adds a new
    company under a ticker already in the index (IR -> TT: Gardner Denver renamed Ingersoll Rand Inc. took IR in
    2020; Ingersoll-Rand plc continues as TT); and a leave nothing explains paired with an earlier unexplained join
    whose Yahoo history covers the leaver's join (KORS -> CPRI). A ticker's own bars before a rename out of it are not
    used when its own Yahoo history starts after its join (a later listing re-using the ticker: Yahoo's IR is Gardner
    Denver from 2017). A successor's bars are used only for dates before the rename, only when its volume is continuous
    across it, and (T-334) only when Yahoo's longName for it matches the index's name for it. Yahoo's longName is not
    always right: VMRK's reads 'AvalonBay Communities', but its bars are Equity Residential's (first trade 1993-08-12,
    EQR's IPO; EQR's price level, not AvalonBay's), so T-394 lets FINRA's volume decide identity (per spell) and T-334,
    which has no volume reference, refuses VMRK (EQR is no addition, only a placebo-pool name). T-394 judges each spell
    piece of a resolved history (between the root ticker's rename and join dates) and refuses only a failing piece,
    whose dates the successor chain then fills.
  * Survivorship (rule 9). Yahoo answers 404 for delisted and acquired names, so they are ABSENT. T-374's universe is
    the current members, as the claim states; the current members without an archived history are named, and every
    criterion that involves them (the three stock criteria and the DSR, which is computed on the stock panel; not the
    ETF-only one) is kept only when no plausible data for them could change it, under every reading the criterion
    conjoins (gross and net): otherwise it is undecided (None). T-334's additions and T-394's point-in-time members include names that have since left and been
    delisted: every event is counted from the membership tables (and, for T-394, from the FINRA files, which list
    delisted symbols), the priced share is measured and reported, and a criterion that needs the absent names' returns
    is not implemented (None) unless every event in the claim's universe is priced. The survivor-subset statistics
    are reported in full.
  * Point in time (rules 4, 12). T-374: the prediction uses ex-dates of the month a year earlier, the payer state and
    the non-dividend span use ex-dates before the month start; the universe itself is the 2026 list (the claim's).
    T-334: the change is public by the effective day's 09:30 ET (the announcement is earlier), the entry is that day's
    close. T-394: the day-t FINRA file is available at the end of day t; z uses file days up to t; the membership is
    the one in force on t; the entry is the next session's open. Files before 2021-10-27 were re-posted that day
    (backfilled); their values are the sums of the per-facility files FINRA published each evening, so the fetcher's
    end-of-day availability holds; the events on them are counted in the stat.
  * Intervals (rule 6). T-374: the trial's firm- and month-clustered bootstrap (2,000 draws a seed; centred-bootstrap
    p, H0: difference <= 0), each clustering on its own, and their joint two-way reading, the Cameron-Gelbach-Miller
    firm-and-month cluster-robust variance (the pigeonhole bootstrap counts the observation-level variance twice); every
    one must pass (``all_constructions``). The ETF robustness has 4 funds, too few firm clusters, so it is
    month-clustered (CGM reported). T-334: studentized cluster bootstrap by effective date (the
    trial's) and by 40-session effective-date buckets (blocks at least twice the 20-session hold); T-394: by signal date
    (the trial's) and by 10-session date blocks (twice the 5-session hold). Both constructions must pass. '95% upper
    bound' is one-sided (the upper end of the two-sided 90% interval); the two-sided 95% interval is reported. Interval
    ends and p-values are the means over 5 bootstrap seeds with their Monte Carlo s.e. (15 seeds when 5 cannot resolve
    them).
  * Costs (rule 9) and readings (rule 11). T-374: 5 bp a round trip on the dividend-month trade; the claim's
    statistic is gross, so the gross and the net difference are both judged and must agree. T-334: '10 bps per leg per
    trade' is read per round trip (2 legs x 10 bps = 20 bps a trade) and per side (40 bps); both must pass. T-394:
    '5 bp per side' on the stock leg (the library's 2 x 5 bp round trip = 10 bps) and on the SPY hedge too (20 bps);
    both must pass. The short's net abnormal return is the abnormal return plus the cost.
  * Calendars (rule 10). T-374 rebalances at month starts (the claim's calendar); T-334 and T-394 are event-driven
    (effective dates; next-day opens after each file). No grid phase is free.
  * Families. T-374: the trial's 4 trials are the run-up span (primary), the span through the predicted ex-day, the
    ETF-only panel and the ex-day capture (close two sessions before an ex-date to the ex-date close); the DSR uses
    their per-period Sharpes (the house 1/(T-1) floor when larger). T-334 (5 variants) and T-394 (4 trials) name no
    deflation in their passes.
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively (its bound at
    the pass's own confidence wholly on the wrong side).

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import _clean, _decide, all_constructions, resolve
from mandel.experiments.batch6c_mom import DSR_PASS, dsr_row, family_dsr
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.batch6c_rates import hac_mean
from mandel.experiments.underlying2 import _verdict

N_BOOT = 2000                  # bootstrap draws per seed (T-374's trial names 2,000)
REPS = 5                       # bootstrap seeds behind every decisive interval end or p-value
REPS_MAX = 15                  # seeds when 5 cannot resolve a bound against its threshold
SEED = 0

SPY_B = "daily-history-SPY"
CONS_B = "wikipedia-sp500-constituents"
CHG_B = "wikipedia-sp500-changes"
FJA_B = "fja-sp500-components"
CNMS_FMT = "finra-regsho-cnms-{}"
CAL_START = "2008-01-01"       # first session kept (T-374 needs 2009 ex-dates, T-334 the 2009 trailing volume)
EDGE_START = "2010-06-01"      # rename edges from here (the Wikipedia changes table is incomplete before)
CONFIRM_DAYS = 10              # fja first appearance vs Wikipedia effective date, calendar days
RENAME_RE = re.compile(r"ticker symbol|ticker changed|changed to [A-Z]|renamed|changed (its )?name", re.I)
REMAIN_RE = re.compile(r"remained in the index", re.I)     # 'Howmet remained in the index': Arconic Inc. renamed

_EPOCH0 = date(1970, 1, 1).toordinal()


# ================================================================================================= data access ==

_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
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


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _epoch(s) -> float:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _avail_filter(archive, name: str):
    """A predicate on rows: available_at not after the bundle's capture time (string compare for UTC ISO stamps)."""
    cap = getattr(archive.get(name), "created_at", None)
    if not cap:
        return lambda r: True
    cap = str(cap)
    capx = _epoch(cap)
    utc = cap.endswith("+00:00")
    c19 = cap[:19]

    def ok(r):
        av = r.get("available_at")
        if not av:
            return True
        av = str(av)
        if utc and av.endswith("+00:00") and len(av) >= 19:
            return av[:19] <= c19
        return _epoch(av) <= capx
    return ok


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        keep = _avail_filter(archive, name)
        return [r for r in archive.load(name) if keep(r)]
    return _cached(archive, ("rows", name), load)


def _ed(iso: str) -> int:
    """Epoch day (days since 1970-01-01) of an ISO date."""
    return date.fromisoformat(str(iso)[:10]).toordinal() - _EPOCH0


def _iso(ed) -> str:
    return date.fromordinal(int(ed) + _EPOCH0).isoformat()


def _dom(ed: int) -> int:
    return date.fromordinal(int(ed) + _EPOCH0).day


def _mk(ed: int) -> int:
    d = date.fromordinal(int(ed) + _EPOCH0)
    return d.year * 12 + d.month - 1


def _mk_first_ed(mk: int) -> int:
    return date(mk // 12, mk % 12 + 1, 1).toordinal() - _EPOCH0


def _mk_days(mk: int) -> int:
    nxt = _mk_first_ed(mk + 1)
    return nxt - _mk_first_ed(mk)


def _mk_str(mk: int) -> str:
    return f"{mk // 12:04d}-{mk % 12 + 1:02d}"


def _mk_of(s: str) -> int:
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def ysym(t: str) -> str:
    """Yahoo spelling of an index / FINRA ticker (BRK.B, BRK/B -> BRK-B)."""
    return str(t).replace("/", "-").replace(".", "-").strip()


def ntick(t) -> str:
    """Index spelling (BRK.B) of a Wikipedia / FINRA ticker; '' for none."""
    return str(t or "").replace("|", "").replace("/", ".").strip()


def _long_name(archive, name: str) -> str:
    rec = str(getattr(archive.get(name), "recipe", "") or "")
    m = re.search(r"meta (\{.*?\})", rec)
    if not m:
        return ""
    try:
        return str(json.loads(m.group(1)).get("longName") or "")
    except ValueError:
        return ""


def _yahoo_bars(archive, name: str, start_ed: int) -> dict:
    """Bars of a Yahoo daily bundle from ``start_ed``: arrays ed, close (split-adjusted), adj (total return; a bar
    without adjclose carries the previous adjclose/close ratio), open (adj basis), vol (NaN when absent), plus the first
    bar's epoch day over the whole bundle."""
    keep = _avail_filter(archive, name)
    by = {}
    first = None
    for r in archive.load(name):
        if not keep(r):
            continue
        v = r.get("value") or {}
        c = _num(v.get("close"))
        t = _num(v.get("t"))
        if c is None or c <= 0 or t is None:
            continue
        e = int(t // 86400)
        first = e if first is None or e < first else first
        if e < start_ed:
            continue
        a, o, vol = _num(v.get("adjclose")), _num(v.get("open")), v.get("volume")
        vv = _num(vol) if vol is not None else float("nan")
        by[e] = (c, a if a and a > 0 else float("nan"), o if o and o > 0 else float("nan"),
                 float("nan") if vv is None else vv)
    eds = sorted(by)
    arr = np.array([by[e] for e in eds], float).reshape(-1, 4)
    close, adj, opn, vol = arr[:, 0], arr[:, 1].copy(), arr[:, 2], arr[:, 3]
    ratio = 1.0
    for i in range(len(eds)):
        if np.isfinite(adj[i]):
            ratio = adj[i] / close[i]
        else:
            adj[i] = close[i] * ratio
    return {"ed": np.array(eds, np.int64), "close": close, "adj": adj, "open": opn * adj / close, "vol": vol, "first": first}


def _spy(archive) -> dict:
    """The SPY session calendar from CAL_START and SPY's total-return close and open on it."""
    def load():
        b = _yahoo_bars(archive, SPY_B, _ed(CAL_START))
        return {"cal": b["ed"], "adj": b["adj"], "open": b["open"]}
    return _cached(archive, ("spy",), load)


def _stock(archive, sym: str) -> Optional[dict]:
    """A Yahoo single-stock (or fund) bundle aligned to the SPY calendar: adj, open (NaN where there is no traded bar:
    missing, or zero volume), dv (close x volume), first (epoch day of the first bar), name (Yahoo longName)."""
    name = f"daily-history-{ysym(sym)}"

    def load():
        if not _has(archive, name):
            return None
        cal = _spy(archive)["cal"]
        b = _yahoo_bars(archive, name, int(cal[0]) if cal.size else 0)
        n = cal.size
        A, O = np.full(n, np.nan), np.full(n, np.nan)
        DV, VOL = np.full(n, np.nan, np.float32), np.full(n, np.nan, np.float32)
        if b["ed"].size and n:
            ix = np.searchsorted(cal, b["ed"])
            ok = ix < n
            ok[ok] &= cal[ix[ok]] == b["ed"][ok]
            traded = ~(b["vol"] <= 0)                     # NaN volume (not reported) keeps the bar
            ok &= traded
            A[ix[ok]] = b["adj"][ok]
            O[ix[ok]] = b["open"][ok]
            DV[ix[ok]] = (b["close"] * b["vol"])[ok]
            VOL[ix[ok]] = b["vol"][ok]
        return {"adj": A, "open": O, "dv": DV, "vol": VOL, "first": b["first"], "name": _long_name(archive, name)}
    return _cached(archive, ("stock", ysym(sym)), load)


def _dividends(archive, sym: str) -> Optional[np.ndarray]:
    """Sorted ex-date epoch days of a ``daily-events-<T>`` bundle (None when the bundle is absent)."""
    name = f"daily-events-{ysym(sym)}"

    def load():
        if not _has(archive, name):
            return None
        out = set()
        for r in _rows(archive, name):
            v = r.get("value") or {}
            if (r.get("kind") or v.get("type")) != "dividend":
                continue
            amt = _num(v.get("amount"))
            if amt is not None and amt <= 0:
                continue
            if v.get("ex_date"):
                out.add(_ed(v["ex_date"]))
            elif _num(v.get("t")) is not None:
                out.add(int(float(v["t"]) // 86400))
        return np.array(sorted(out), np.int64)
    return _cached(archive, ("divs", ysym(sym)), load)


# ======================================================================================== statistics helpers ==

def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(x.mean()) if x.size else None


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bp"


def _ci(ci, nd: int = 2, scale: float = 100.0, unit: str = "%") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "n/a"
    return f"[{lo * scale:+.{nd}f}{unit}, {hi * scale:+.{nd}f}{unit}]"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _avg_reps(rs: list, keys=("ci", "ci90", "ci_pct")) -> dict:
    """Replicate means of interval ends and p-values over bootstrap seeds, with '<key>_mc_se'."""
    out = dict(rs[0])
    r_ = len(rs)
    for key in keys:
        if key not in out:
            continue
        arr = np.array([[np.nan if v is None else v for v in r[key]] for r in rs], float)
        if np.isfinite(arr).all():
            out[key] = [float(v) for v in arr.mean(axis=0)]
            out[key + "_mc_se"] = [float(v) for v in (arr.std(axis=0, ddof=1) / math.sqrt(r_) if r_ > 1 else np.zeros(arr.shape[1]))]
    for key in ("p", "p_lt"):
        vals = [r.get(key) for r in rs]
        if all(v is not None for v in vals):
            out[key] = float(np.mean(vals))
            out[key + "_mc_se"] = float(np.std(vals, ddof=1) / math.sqrt(r_)) if r_ > 1 else 0.0
    out["reps"] = r_
    return out


def cluster_mc(x, labels, check=None, reps: Optional[int] = None) -> dict:
    """``batch6c_pub.cluster_stud`` (studentized cluster bootstrap) over ``reps`` seeds; again with REPS_MAX seeds when
    ``check`` (the resolved criterion, None = unresolved) cannot decide."""
    reps = REPS if reps is None else reps
    x = np.asarray(x, float)
    if x.size < 4:
        return {"est": _mean(x), "ci": [None, None], "ci90": [None, None], "n": int(x.size), "clusters": len(set(labels))}
    t = _avg_reps([cluster_stud(x, labels, N_BOOT, SEED + k) for k in range(reps)])
    if check is not None and check(t) is None and REPS_MAX > reps:
        t = _avg_reps([cluster_stud(x, labels, N_BOOT, SEED + k) for k in range(REPS_MAX)])
    return t


def _upper_lt0(t: dict) -> tuple:
    """(ok, decisive, note) for 'one-sided 95% upper bound < 0' on a cluster_mc result (ci90 upper end)."""
    lo, hi = (t.get("ci90") or [None, None])[:2]
    se_lo, se_hi = (t.get("ci90_mc_se") or [0.0, 0.0])[:2]
    ok, note = resolve(hi, se_hi, 0.0, "lt")
    dec = lo is not None and resolve(lo, se_lo, 0.0, "gt")[0] is True
    return ok, dec, note


# =========================================================================== membership, renames and prices ==

def membership_snapshots(fja_rows: Sequence[dict], changes: Sequence[dict]) -> list:
    """[(epoch day, frozenset of index tickers)]: the fja05680 change-date snapshots, then the Wikipedia changes after
    the file's last date applied in order (adds and removes on their effective dates)."""
    snaps = []
    for r in sorted(fja_rows, key=lambda r: (r.get("value") or {}).get("date", "")):
        v = r.get("value") or {}
        if v.get("date") and v.get("tickers"):
            snaps.append((_ed(v["date"]), frozenset(ntick(t) for t in v["tickers"])))
    if not snaps:
        return snaps
    last = snaps[-1][0]
    later = defaultdict(list)
    for w in changes:
        e = w.get("effective_date")
        if e and _ed(e) > last:
            later[_ed(e)].append(w)
    cur = set(snaps[-1][1])
    for e in sorted(later):
        for w in later[e]:
            if ntick(w.get("removed_ticker")):
                cur.discard(ntick(w.get("removed_ticker")))
            if ntick(w.get("added_ticker")):
                cur.add(ntick(w.get("added_ticker")))
        snaps.append((e, frozenset(cur)))
    return snaps


def members_at(snaps: Sequence[tuple], ed: int) -> frozenset:
    """The membership in force on epoch day ``ed`` (the latest snapshot on or before it)."""
    eds = [s[0] for s in snaps]
    j = bisect.bisect_right(eds, ed) - 1
    return snaps[j][1] if j >= 0 else frozenset()


def _rename_candidate(w: dict) -> bool:
    """A Wikipedia row whose reason reads like a ticker change. The reason often describes the company that LEFT
    ('Allergan was acquired by Actavis (and changed its name ...)', 'Westar Energy ... changed name to Evergy' on the row
    where Evergy replaced Navient), so it only nominates the row: ``same_company`` judges it on the tickers."""
    r = str(w.get("reason") or "")
    return bool(RENAME_RE.search(r) or REMAIN_RE.search(r))


_STOP = {"inc", "corp", "corporation", "company", "co", "the", "plc", "ltd", "limited", "group", "holdings", "holding",
         "class", "common", "stock", "sa", "nv", "n", "v", "and", "of", "international", "incorporated", "technologies",
         "technology", "financial", "properties", "health", "energy", "services", "systems", "communications",
         "industries", "resources", "brands", "solutions", "trust", "new", "a", "b", "s"}


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", str(s or "").lower()) if w not in _STOP and len(w) >= 2}


_STOP_INI = {"inc", "corp", "corporation", "company", "co", "the", "plc", "ltd", "limited", "and", "of", "n", "v", "sa", "nv"}


def _initials(s: str) -> str:
    return "".join(w[0] for w in re.findall(r"[a-z0-9]+", str(s or "").lower()) if w not in _STOP_INI)


def name_match(a: str, b: str, ticker: str = "") -> bool:
    """Do two company names denote the same company? A shared distinctive token (Meta Platforms / Meta Platforms,
    Inc.), one name's token inside the other's run of tokens (Supermicro / Super Micro Computer), an acronym (IBM /
    International Business Machines), both abbreviating the ticker (Wabtec / Westinghouse Air Brake, WAB), or the
    first name carrying the ticker as a word (SLB N.V. for SLB)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if ta & tb:
        return True
    ca, cb = "".join(re.findall(r"[a-z0-9]+", str(a).lower())), "".join(re.findall(r"[a-z0-9]+", str(b).lower()))
    if any(len(t) >= 4 and t in cb for t in ta) or any(len(t) >= 4 and t in ca for t in tb):
        return True
    ia, ib = _initials(a), _initials(b)
    if (len(ia) >= 3 and ia in tb) or (len(ib) >= 3 and ib in ta):
        return True
    tk = re.sub(r"[^a-z0-9]", "", str(ticker).lower())
    if len(tk) >= 2:
        abbr = lambda toks, ini: tk in toks or ini.startswith(tk) or any(t.startswith(tk) for t in toks)
        if abbr(ta, ia) and abbr(tb, ib):
            return True
        if tk in ta:
            return True
    return False


class YahooFacts:
    """What the archived Yahoo histories say about an index ticker, for the rename rules: its first bar over the whole
    bundle (None: no bundle), whether Yahoo's longName matches the index's names for it (True / False / None), and
    whether its own name-matched bars trade on both sides of a date (a leaver that keeps trading as itself, like Fossil
    Group or Navient, is a different company from the joiner that replaced it)."""

    def __init__(self, archive, refs: dict):
        self.archive, self.refs = archive, refs

    def first(self, t: str) -> Optional[int]:
        st = _stock(self.archive, t)
        return None if st is None else st.get("first")

    def valid(self, t: str) -> Optional[bool]:
        st = _stock(self.archive, t)
        refs = [r for r in (self.refs.get(t) or []) if r]
        if st is None or not st.get("name") or not refs:
            return None
        return any(name_match(st["name"], r, t) for r in refs)

    def trades_across(self, t: str, e: int, win: Optional[int] = None) -> bool:
        win = CONT_WIN if win is None else win
        st = _stock(self.archive, t)
        if st is None or self.valid(t) is not True:
            return False
        cal = _spy(self.archive)["cal"]
        i = int(np.searchsorted(cal, e))
        a, b = st["adj"][max(0, i - win):i], st["adj"][i:i + win]
        return int(np.isfinite(a).sum()) >= win // 3 and int(np.isfinite(b).sum()) >= win // 3

    def covers(self, t: str, ed: int, tol: int = CONFIRM_DAYS) -> bool:
        """Yahoo's history for ``t`` starts by ``ed`` (whose company it is, the price book checks)."""
        f = self.first(t)
        return f is not None and f <= ed + tol


def same_company(x, y, name_x, name_y, L, J, others_removed, facts=None, e1: Optional[int] = None) -> tuple:
    """Rename rule: are a rename-candidate row's removed ticker ``x`` and added ticker ``y`` one company? (ok, why). Yes
    when the row's two names match (Willis Towers Watson / Willis Towers Watson, DuPont / DuPont), or when x leaves and
    y joins on the fja change and x is the change's only leaver that no other Wikipedia row removes (Questar / QEP,
    Dow Chemical / DowDuPont, Ceridian / Dayforce, Arconic / Howmet), unless x's own name-matched Yahoo history trades on
    across the change (Fossil Group, Navient: a different company left and the joiner replaced it). A row whose removed
    ticker does not leave on that change (Allergan for American Airlines; Bemis for Amcor) is not a rename."""
    x, y = ntick(x), ntick(y)
    if not x or not y:
        return False, "the row names no removed or no added ticker"
    if name_x and name_y and name_match(name_x, name_y):
        return True, f"names match ({name_x} / {name_y})"
    if x in L and y in J and (set(L) - set(others_removed)) == {x}:
        if facts is not None and e1 is not None and facts.trades_across(x, e1):
            return False, f"{x} is the only leaver, but its own Yahoo history trades on across the change: a different company"
        return True, f"{x} -> {y} is the change's only unexplained leave/join"
    return False, f"{x} is not the only unexplained leaver on this fja change"


def _pair_evidence(x: str, y: str, sx: Optional[int], e1: int, refs: dict, facts=None) -> Optional[str]:
    """Evidence that an unexplained fja leave/join pair is one company: a name match between the index's names for the
    two tickers, or Yahoo-history continuity (Yahoo's ``y`` history starts by x's join and x does not trade on as
    itself across the change). None: no evidence (QLogic / Noble: Yahoo's NE starts in 2021)."""
    for a in refs.get(x) or []:
        for b in refs.get(y) or []:
            if a and b and name_match(a, b):
                return f"names match: {a} / {b}"
    if facts is not None and sx is not None and facts.covers(y, sx) and not facts.trades_across(x, e1):
        return f"Yahoo's {y} history covers {x}'s {_iso(sx)} join"
    return None


def _in_fja(snaps: Sequence[tuple], eds: Sequence[int], t: str, lo: int, hi: int) -> bool:
    """Is ``t`` a member in any snapshot in force between epoch days ``lo`` and ``hi``?"""
    j0 = max(0, bisect.bisect_right(eds, lo) - 1)
    j1 = max(j0 + 1, bisect.bisect_right(eds, hi))
    return any(t in snaps[j][1] for j in range(j0, min(j1, len(snaps))))


def spelling_pairs(snaps: Sequence[tuple], changes: Sequence[dict], refs: dict, start: str = EDGE_START,
                   tol: int = CONFIRM_DAYS) -> dict:
    """fja joins that no Wikipedia row adds under the same ticker, confirmed by a Wikipedia add under another spelling
    (fja uses later tickers): {(fja ticker, join epoch day): (Wikipedia row, how)}. The confirming row is an 'orphan'
    add within ``tol`` days (its ticker is not an fja member around either date) whose added_security name-matches the
    fja ticker's index names (UA = UAA, JOYG = JOY), or, the only such orphan for the change's only unexplained join,
    one whose removed ticker leaves fja on this same change (DLPH = APTV, ANR = ANRZQ) or, when this change has no
    leaver, on a change within ``tol`` days that has no joiner (fja splits Whole Foods' leave and IQVIA's join over
    2017-08-28 / 2017-08-29: Q = IQV). Bemis's row, which replaces Mattel on the 2019-06-07 change where Amcor joins,
    does not confirm L3Harris's 2019-06-01 join, a rename of Harris."""
    s_ed = _ed(start)
    eds = [s[0] for s in snaps]
    rows = [(w, _ed(w["effective_date"])) for w in changes if w.get("effective_date") and ntick(w.get("added_ticker"))]
    adds = defaultdict(list)
    for w, e in rows:
        adds[ntick(w["added_ticker"])].append(e)
    out = {}
    for k in range(1, len(snaps)):
        e1, s1 = snaps[k]
        if e1 < s_ed:
            continue
        J = s1 - snaps[k - 1][1]
        L = snaps[k - 1][1] - s1
        un = sorted(t for t in J if not any(abs(e - e1) <= tol for e in adds.get(t, [])))
        if not un:
            continue
        orph = [(w, e) for w, e in rows if abs(e - e1) <= tol and ntick(w["added_ticker"]) not in J
                and not _in_fja(snaps, eds, ntick(w["added_ticker"]), min(e, e1) - tol, max(e, e1) + tol)]
        used = set()
        for t in list(un):
            hit = [i for i, (w, _) in enumerate(orph) if i not in used and w.get("added_security")
                   and any(r and name_match(w["added_security"], r) for r in refs.get(t) or [])]
            if len(hit) == 1:
                out[(t, e1)] = (orph[hit[0]][0], "names match")
                used.add(hit[0])
                un.remove(t)
        def same_leaver(r):
            if r in L:
                return True
            if L:
                return False
            return any(abs(snaps[q][0] - e1) <= tol and r in snaps[q - 1][1] - snaps[q][1] and not (snaps[q][1] - snaps[q - 1][1])
                       for q in range(max(1, k - 20), min(len(snaps), k + 21)))
        left = [i for i, (w, _) in enumerate(orph) if i not in used and ntick(w.get("removed_ticker"))
                and same_leaver(ntick(w["removed_ticker"]))]
        if len(un) == 1 and len(left) == 1:
            out[(un[0], e1)] = (orph[left[0]][0], "replaces the same leaver")
    return out


def spell_joins(snaps: Sequence[tuple]) -> dict:
    """{ticker: sorted join epoch days} (the first snapshot counts as a join)."""
    out = defaultdict(list)
    prev = frozenset()
    for e, s in snaps:
        for t in s - prev:
            out[t].append(int(e))
        prev = s
    return dict(out)


def rename_edges(snaps: Sequence[tuple], changes: Sequence[dict], current: dict, start: str = EDGE_START,
                 facts: Optional[YahooFacts] = None, refs: Optional[dict] = None, spelled: Optional[dict] = None) -> list:
    """Ticker renames [(epoch day, old, new, how)] from consecutive membership snapshots on or after ``start``:
    rename-candidate Wikipedia rows whose removed / added tickers leave / join on that change and are one company
    (``same_company``: judged on the tickers, never on the free-text reason); then leaves and joins that no Wikipedia
    row within 10 days explains, paired one-to-one when the names match or the Yahoo history is continuous
    (``_pair_evidence``); an ambiguous group is paired through the current member's Wikipedia date-added (the
    successor chain's current member was added on the old ticker's join date). With ``facts`` (Yahoo histories), two
    more rules for a ticker whose own Yahoo history starts after its join (or is absent) while a successor's covers it:
    a join that nothing explains on a change where Wikipedia adds a new company under a ticker already in the index
    (Gardner Denver renamed Ingersoll Rand Inc. took IR; Ingersoll-Rand plc continues as TT: IR -> TT); and a leave that
    nothing explains, paired with the one earlier unexplained join, still a member, whose Yahoo history covers the
    leaver's join (fja lists Michael Kors as KORS until 2018-09-19 and as CPRI from 2016-01-04: KORS -> CPRI). Joins
    that a Wikipedia add confirms under another spelling, or that the constituents table dates as the member's own
    addition, are additions, not successors."""
    s_ed = _ed(start)
    rows = [(w, _ed(w["effective_date"])) for w in changes if w.get("effective_date")]
    refs = _ref_names(list(current.values()), changes) if refs is None else refs
    spelled = spelling_pairs(snaps, changes, refs, start) if spelled is None else spelled
    edges, amb = [], []
    run_start: dict = {}                                       # ticker -> join epoch day of its current spell
    open_joins: dict = {}                                      # unexplained joins without a leaver -> join epoch day
    prev = None
    for e1, s1 in snaps:
        if prev is None:
            for t in s1:
                run_start[t] = e1
            prev = (e1, s1)
            continue
        e0, s0 = prev
        L, J = set(s0 - s1), set(s1 - s0)
        starts = {t: run_start.get(t) for t in L}
        for t in J:
            run_start[t] = e1
        for t in L:
            run_start.pop(t, None)
            open_joins.pop(t, None)
        prev = (e1, s1)
        if e1 < s_ed or not (L or J):
            continue
        near = [w for w, e in rows if abs(e - e1) <= CONFIRM_DAYS or e0 < e <= e1]
        for w in near:
            x, y = ntick(w.get("removed_ticker")), ntick(w.get("added_ticker"))
            if _rename_candidate(w) and x in L and y in J:
                others = {ntick(v.get("removed_ticker")) for v in near if v is not w}
                ok, _why = same_company(x, y, w.get("removed_security"), w.get("added_security"), L, J, others,
                                        facts=facts, e1=e1)
                if ok:
                    edges.append((e1, x, y, "wikipedia ticker change"))
                    L.discard(x)
                    J.discard(y)
        exL = {ntick(w.get("removed_ticker")) for w in near}
        exJ = {ntick(w.get("added_ticker")) for w in near}
        Lu, Ju = sorted(L - exL), sorted(J - exJ)
        if len(Lu) == 1 and len(Ju) == 1:
            how = _pair_evidence(Lu[0], Ju[0], starts.get(Lu[0]), e1, refs, facts)
            if how:
                edges.append((e1, Lu[0], Ju[0], f"unexplained leave/join pair ({how})"))
        elif Lu and Ju:
            amb.append((e1, Lu, Ju, {t: starts.get(t) for t in Lu}))
        elif Ju and facts is not None:
            reuse = sorted({ntick(w.get("added_ticker")) for w in near if ntick(w.get("added_ticker")) in s0
                            and ntick(w.get("added_ticker")) in s1
                            and run_start.get(ntick(w.get("added_ticker")), e1) < e1 - CONFIRM_DAYS})
            if len(Ju) == 1 and len(reuse) == 1:
                u, y = reuse[0], Ju[0]
                fu = facts.first(u)
                if (fu is None or fu > run_start[u] + CONFIRM_DAYS) and facts.covers(y, run_start[u]):
                    edges.append((e1, u, y, f"ticker reused: Wikipedia adds a new company as {u}; Yahoo's {y} covers "
                                            f"{u}'s {_iso(run_start[u])} join"))
                    Ju = []
            for y in Ju:
                da = (current.get(y) or {}).get("date_added")
                if (y, e1) in spelled or (da and abs(_ed(da) - e1) <= CONFIRM_DAYS):
                    continue
                open_joins[y] = e1
        elif Lu and facts is not None:
            for x in Lu:
                sx = starts.get(x)
                fx = facts.first(x)
                if sx is None or (fx is not None and fx <= sx + CONFIRM_DAYS and facts.valid(x) is not False):
                    continue                                   # x's own Yahoo history is there from its join
                cand = [y for y, ej in open_joins.items() if y in s1 and sx <= ej < e1 and facts.covers(y, sx)]
                if len(cand) == 1:
                    edges.append((e1, x, cand[0], f"unexplained leave paired with the unexplained {_iso(open_joins[cand[0]])} "
                                                  f"join of {cand[0]}, whose Yahoo history covers {x}'s join"))
                    open_joins.pop(cand[0])
    succ = defaultdict(list)
    for e, x, y, _ in edges:
        succ[x].append((e, y))

    def last_of(y, after, seen):
        for e, z in sorted(succ.get(y, [])):
            if e > after and z not in seen:
                return last_of(z, e, seen | {z})
        return y
    for e1, Lu, Ju, starts in amb:
        used = set()
        for y in Ju:
            c = last_of(y, e1, {y})
            da = (current.get(c) or {}).get("date_added")
            if not da:
                continue
            hit = [x for x in Lu if x not in used and starts.get(x) is not None and abs(starts[x] - _ed(da)) <= 3]
            if len(hit) == 1:
                edges.append((e1, hit[0], y, "ambiguous change paired through the current member's date added"))
                used.add(hit[0])
    return sorted(edges)


CONT_WIN = 60                  # sessions either side of a rename for the volume-continuity check
CONT_MIN = 0.2                 # median volume before / after the rename at least this


class PriceBook:
    """Aligned total-return closes and opens of index tickers, resolved through renames. A ticker's own Yahoo bars
    are used where they trade (``check_own``: only when Yahoo's name for the ticker matches the index's, since Yahoo
    re-issues old tickers with another company's stitched history: BBT is now Beacon Financial, PARA Banzai); for the
    dates before each rename out of a ticker, its successor's resolved bars fill the gaps, when Yahoo's name for every
    successor used matches the index's (``names_veto``; off where another identity check decides, as T-394's FINRA
    volume check) and the successor's volume is continuous across the rename (median volume in the 60 sessions before
    at least 0.2 of the 60 after: Smurfit Westrock's pre-listing prints trade a few hundred shares). A ticker's own bars
    before a rename out of it are not used when its own Yahoo history starts after its join (a later listing that
    re-uses the ticker: Yahoo's IR is Gardner Denver from 2017, the index's IR to 2020-03-02 is Ingersoll-Rand plc, now
    TT; Yahoo's BBT is Beacon Financial from 2000): the successor's bars are used for those dates. ``refuse`` spans
    (ticker, from, to) drop a ticker's own bars so the successor chain can fill them. ``rejected`` records every
    refusal."""

    def __init__(self, archive, edges: Sequence[tuple], ref_names: dict, check_own: bool = True, unknown_ok: bool = False,
                 joins: Optional[dict] = None, names_veto: bool = True):
        self.archive = archive
        self.cal = _spy(archive)["cal"]
        self.succ = defaultdict(list)
        for e, x, y, _ in edges:
            self.succ[x].append((int(e), y))
        self.ref_names = ref_names
        self.check_own = check_own
        self.unknown_ok = unknown_ok              # a successor the index names nowhere is kept (validated elsewhere)
        self.joins = joins or {}
        self.names_veto = names_veto
        self.memo: dict = {}
        self.rejected: dict = {}
        self.name_overruled: dict = {}

    def identity(self, t: str, st: Optional[dict]) -> Optional[bool]:
        """Yahoo's name vs the index's names for ``t``: True / False, None when either side has no name (or, without
        ``names_veto``, when they disagree: recorded in ``name_overruled``)."""
        refs = [r for r in (self.ref_names.get(t) or []) if r]
        if not st or not st.get("name") or not refs:
            return None
        ok = any(name_match(st["name"], r, t) for r in refs)
        if not ok and not self.names_veto:
            self.name_overruled[t] = f"Yahoo '{st['name']}' vs index '{'; '.join(refs[:2])}': not used, the volume check decides"
            return None
        return ok

    def _continuous(self, r: dict, e: int) -> bool:
        i = int(np.searchsorted(self.cal, e))
        v = r["vol"]
        a, b = v[max(0, i - CONT_WIN):i], v[i:i + CONT_WIN]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if a.size < CONT_WIN // 3 or b.size < CONT_WIN // 3:
            return a.size >= CONT_WIN // 3          # nothing after the rename to compare with: keep what traded before
        mb = float(np.median(b))
        return mb > 0 and float(np.median(a)) >= CONT_MIN * mb

    def resolved(self, t: str, seen: frozenset = frozenset(), root: bool = True, refuse: tuple = ()) -> Optional[dict]:
        key = (t, seen, root, refuse)
        if key in self.memo:
            return self.memo[key]
        st = _stock(self.archive, t)
        n = self.cal.size
        own = st is not None
        if own and (not root or self.check_own):
            idn = self.identity(t, st)
            if idn is False or (idn is None and not root and not self.unknown_ok):
                self.rejected[t] = f"Yahoo '{st.get('name') or '?'}' vs index '{'; '.join((self.ref_names.get(t) or ['?'])[:2])}'"
                own = False
        A = st["adj"].copy() if own else np.full(n, np.nan)
        O = st["open"].copy() if own else np.full(n, np.nan)
        DV = st["dv"].astype(float) if own else np.full(n, np.nan)
        VOL = st["vol"].astype(float) if own else np.full(n, np.nan)
        drop = np.zeros(n, bool)
        if own and st.get("first") is not None:
            for e, _y in self.succ.get(t, []):
                js = [j for j in self.joins.get(t, []) if j < e]
                if js and st["first"] > js[-1] + CONFIRM_DAYS:
                    cut = (self.cal < e) & np.isfinite(A)
                    if cut.any():
                        drop |= cut
                        self.rejected[f"{t}<{_iso(e)}"] = (f"Yahoo's {t} starts {_iso(st['first'])}, after the {_iso(js[-1])} "
                                                           f"join: a later listing, not used before the {_iso(e)} rename")
        for tk, a, b in refuse:
            if tk == t:
                drop |= (self.cal >= a) & (self.cal < b)
        if drop.any():
            A[drop], O[drop], DV[drop], VOL[drop] = np.nan, np.nan, np.nan, np.nan
        src = np.where(np.isfinite(A), 0, -1).astype(np.int8)
        lo = -10 ** 9
        names = [t]
        for e, y in sorted(self.succ.get(t, [])):
            if y in seen or y == t:
                lo = e
                continue
            r = self.resolved(y, seen | {t}, root=False, refuse=refuse)
            if r is not None:
                if not self._continuous(r, e):
                    self.rejected[f"{t}->{y}"] = f"volume not continuous across the {_iso(e)} rename"
                else:
                    span = (self.cal >= lo) & (self.cal < e)
                    fill = span & ~np.isfinite(A) & np.isfinite(r["adj"])
                    if fill.any():
                        A[fill], O[fill], DV[fill], VOL[fill] = r["adj"][fill], r["open"][fill], r["dv"][fill], r["vol"][fill]
                        for q in sorted(set(r["src"][fill].tolist())):    # keep the ticker each bar really comes from
                            nm = r["names"][q]
                            if nm not in names:
                                names.append(nm)
                            src[fill & (r["src"] == q)] = names.index(nm)
            lo = e
        out = None if not np.isfinite(A).any() else {"adj": A, "open": O, "dv": DV, "vol": VOL, "src": src, "names": names}
        self.memo[key] = out
        return out


def _ref_names(cons: Sequence[dict], changes: Sequence[dict]) -> dict:
    out = defaultdict(list)
    for c in cons:
        if c.get("symbol") and c.get("security"):
            out[ntick(c["symbol"])].append(c["security"])
    for w in changes:
        if ntick(w.get("added_ticker")) and w.get("added_security"):
            out[ntick(w["added_ticker"])].append(w["added_security"])
        if ntick(w.get("removed_ticker")) and w.get("removed_security"):   # the company's name as it left
            out[ntick(w["removed_ticker"])].append(w["removed_security"])
    return out


def _tables(archive) -> dict:
    """Membership snapshots, rename edges, Wikipedia rows and current members (cached)."""
    def load():
        cons = [r.get("value") or {} for r in _rows(archive, CONS_B)] if _has(archive, CONS_B) else []
        chg = [r.get("value") or {} for r in _rows(archive, CHG_B)] if _has(archive, CHG_B) else []
        fja = _rows(archive, FJA_B) if _has(archive, FJA_B) else []
        snaps = membership_snapshots(fja, chg)
        current = {ntick(c.get("symbol")): c for c in cons if c.get("symbol")}
        if cons and snaps:
            rev = cons[0].get("revision_time") or cons[0].get("date") or ""
            if rev and _ed(rev) > snaps[-1][0]:
                snaps = snaps + [(_ed(rev), frozenset(current))]
        refs = _ref_names(cons, chg)
        facts = YahooFacts(archive, refs) if _has(archive, SPY_B) else None
        spelled = spelling_pairs(snaps, chg, refs)
        edges = rename_edges(snaps, chg, current, facts=facts, refs=refs, spelled=spelled)
        fja_last = max((_ed((r.get("value") or {}).get("date")) for r in fja if (r.get("value") or {}).get("date")), default=None)
        return {"cons": cons, "chg": chg, "snaps": snaps, "current": current, "edges": edges, "fja_last": fja_last,
                "refs": refs, "facts": facts, "spelled": spelled, "joins": spell_joins(snaps)}
    return _cached(archive, ("tables",), load)


def _book(archive, check_own: bool = True, unknown_ok: bool = False, names_veto: bool = True) -> PriceBook:
    tb = _tables(archive)
    return _cached(archive, ("book", check_own, unknown_ok, names_veto),
                   lambda: PriceBook(archive, tb["edges"], tb["refs"], check_own, unknown_ok, tb["joins"], names_veto))


def _split_factor(archive, sym: str) -> np.ndarray:
    """Per calendar session, the product of the split ratios with ex-dates after it: Yahoo volume / this = as-traded
    volume (ones when the events bundle is absent)."""
    def load():
        cal = _spy(archive)["cal"]
        F = np.ones(cal.size)
        name = f"daily-events-{ysym(sym)}"
        if not _has(archive, name):
            return F
        for r in _rows(archive, name):
            v = r.get("value") or {}
            if (r.get("kind") or v.get("type")) != "split" or not v.get("ex_date"):
                continue
            nu, de = _num(v.get("numerator")), _num(v.get("denominator"))
            if nu and de and nu > 0 and de > 0:
                F[cal < _ed(v["ex_date"])] *= nu / de
        return F
    return _cached(archive, ("splits", ysym(sym)), load)


# ================================================================================ T-374 dividend-month premium ==

T374_START, T374_END = "2010-01", "2026-09"
T374_SPLIT = "2018-01"
T374_THR = 0.0020              # 20 bp
T374_ALPHA = 0.01
T374_COST = 0.0005             # 5 bp a round trip on the dividend-month trade
T374_MIN_N = 5000              # dividend firm-months
T374_TRIALS = 4
T374_ETFS = ("VYM", "SCHD", "SDY", "DVY")
T374_PAYER_DAYS = 365          # 'current payer': an ex-date in the year to the constituents snapshot
T374_HOWS = ("firm", "month")   # the trial's clustered bootstraps; the two-way construction is Cameron-Gelbach-Miller
TWO = "two-way CGM"
_NORM = __import__("statistics").NormalDist()


def _month_index(cal: np.ndarray) -> dict:
    mks = np.array([_mk(e) for e in cal], np.int64) if cal.size else np.zeros(0, np.int64)
    first, last = {}, {}
    for i, k in enumerate(mks):
        k = int(k)
        if k not in first:
            first[k] = i
        last[k] = i
    return {"first": first, "last": last}


def divmonth_obs(cal: np.ndarray, mi: dict, spy: np.ndarray, adj: np.ndarray, exd: np.ndarray, first_ed: Optional[int],
                 m_lo: int, m_hi: int, mode: str = "runup") -> dict:
    """One firm's firm-months (month key -> (kind 'D'/'N', market-adjusted span return)). Dividend month (D): an ex-date
    in the calendar month a year earlier; the predicted ex-date is that ex-date's day of month in this month. Non-
    dividend month (N): no such ex-date, an ex-date in the 12 months before the month start; its span ends at the day of
    month of the latest ex-date before the month start. The span starts at the previous month's last close and ends at
    the close of the last session before the predicted day (``mode`` 'runup') or on it ('through'). A month needs the
    firm listed by the start of the month a year earlier (so the prediction is informative)."""
    out = {}
    empty = 0
    exd = np.asarray(exd, np.int64)
    for mk in range(m_lo, m_hi + 1):
        fi = mi["first"].get(mk)
        if fi is None or fi == 0:
            continue
        s0 = fi - 1
        m12 = _mk_first_ed(mk - 12)
        if first_ed is None or first_ed > m12:
            continue
        m11, m0 = _mk_first_ed(mk - 11), _mk_first_ed(mk)
        a, b, c = np.searchsorted(exd, [m12, m11, m0])
        if b > a:
            day, kind = _dom(exd[a]), "D"
        elif c > a:
            day, kind = _dom(exd[c - 1]), "N"
        else:
            continue
        p = m0 + min(day, _mk_days(mk)) - 1
        e = int(np.searchsorted(cal, p, "left" if mode == "runup" else "right")) - 1
        if e < fi or e > mi["last"][mk]:
            empty += 1
            continue
        if not (np.isfinite(adj[e]) and np.isfinite(adj[s0])):
            continue
        out[mk] = (kind, float(adj[e] / adj[s0] - spy[e] / spy[s0]))
    return {"obs": out, "empty": empty}


def divmonth_panel(cal: np.ndarray, spy: np.ndarray, firms: dict, m_lo: str = T374_START, m_hi: str = T374_END,
                   mode: str = "runup", same_firms: bool = True) -> dict:
    """firms: {sym: {"adj": aligned total-return closes, "exd": sorted ex-date epoch days, "first": first bar epoch
    day}} -> firm x month matrices of dividend-month (XD, CD) and non-dividend-month (XN, CN) market-adjusted span
    returns (gross) and counts. ``same_firms`` keeps firms with both kinds (the claim's 'same firms')."""
    mi = _month_index(cal)
    lo, hi = _mk_of(m_lo), _mk_of(m_hi)
    months = list(range(lo, hi + 1))
    col = {m: j for j, m in enumerate(months)}
    per, empty, dropped = {}, 0, []
    for s, f in firms.items():
        r = divmonth_obs(cal, mi, spy, f["adj"], f["exd"], f.get("first"), lo, hi, mode)
        empty += r["empty"]
        kinds = {k for k, _ in r["obs"].values()}
        if not r["obs"] or (same_firms and kinds != {"D", "N"}):
            if r["obs"]:
                dropped.append(s)
            continue
        per[s] = r["obs"]
    syms = sorted(per)
    F, M = len(syms), len(months)
    XD, CD, XN, CN = (np.zeros((F, M)) for _ in range(4))
    for i, s in enumerate(syms):
        for mk, (kind, v) in per[s].items():
            j = col[mk]
            if kind == "D":
                XD[i, j], CD[i, j] = v, 1.0
            else:
                XN[i, j], CN[i, j] = v, 1.0
    return {"syms": syms, "months": [_mk_str(m) for m in months], "XD": XD, "CD": CD, "XN": XN, "CN": CN,
            "empty_spans": empty, "one_kind_firms": dropped}


def _scope_masks(months: Sequence[str], split: str = T374_SPLIT) -> dict:
    mo = np.array(months)
    return {"full": np.ones(len(months), bool), "first": mo < split, "second": mo >= split}


def _diff(XD, CD, XN, CN, cost: float) -> Optional[float]:
    nd, nn = CD.sum(), CN.sum()
    if nd < 1 or nn < 1:
        return None
    return float((XD.sum() - cost * nd) / nd - XN.sum() / nn)


def twoway_boot(P: dict, scopes: dict, costs: dict, how: str, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Cluster bootstrap of the pooled dividend-minus-non-dividend difference: 'two-way' resamples firms and months
    together (pigeonhole: weight = firm count x month count), 'firm' firms only, 'month' months only (within each
    scope's months). {scope: {cost: {est, p (H0 diff <= 0, centred bootstrap), p_lt, ci (95%), ci98, n_d}}}."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    XD, CD, XN, CN = P["XD"], P["CD"], P["XN"], P["CN"]
    F, M = XD.shape
    out = {}
    if F < 2 or M < 2:
        return {s: {c: {"est": None, "p": None, "p_lt": None, "ci": [None, None], "ci98": [None, None]} for c in costs} for s in scopes}
    rng = np.random.default_rng(seed)
    draws = {(s, c): [] for s in scopes for c in costs}
    k = max(1, min(n_boot, 250))
    done = 0
    while done < n_boot:
        kk = min(k, n_boot - done)
        Wf = rng.multinomial(F, np.full(F, 1.0 / F), size=kk).astype(float) if how in ("two-way", "firm") else np.ones((kk, F))
        A, B, C, D = Wf @ XD, Wf @ CD, Wf @ XN, Wf @ CN
        for s, mask in scopes.items():
            ms = np.flatnonzero(mask)
            if how in ("two-way", "month"):
                Wm = np.zeros((kk, M))
                Wm[:, ms] = rng.multinomial(ms.size, np.full(ms.size, 1.0 / ms.size), size=kk)
            else:
                Wm = np.zeros((kk, M))
                Wm[:, ms] = 1.0
            sa, sb, sc, sd = (A * Wm).sum(1), (B * Wm).sum(1), (C * Wm).sum(1), (D * Wm).sum(1)
            ok = (sb > 0) & (sd > 0)
            for c, cv in costs.items():
                d = np.full(kk, np.nan)
                d[ok] = (sa[ok] - cv * sb[ok]) / sb[ok] - sc[ok] / sd[ok]
                draws[(s, c)].append(d)
        done += kk
    for s, mask in scopes.items():
        out[s] = {}
        for c, cv in costs.items():
            d0 = _diff(XD[:, mask], CD[:, mask], XN[:, mask], CN[:, mask], cv)
            d = np.concatenate(draws[(s, c)])
            d = d[np.isfinite(d)]
            if d0 is None or d.size < 10:
                out[s][c] = {"est": d0, "p": None, "p_lt": None, "ci": [None, None], "ci98": [None, None]}
                continue
            dc = d - d0
            q = lambda a: float(np.quantile(dc, a))
            out[s][c] = {"est": d0, "p": float((1 + np.sum(dc >= d0)) / (1 + dc.size)),
                         "p_lt": float((1 + np.sum(dc <= d0)) / (1 + dc.size)),
                         "ci": [d0 - q(0.975), d0 - q(0.025)], "ci98": [d0 - q(0.99), d0 - q(0.01)],
                         "n_d": int(CD[:, mask].sum()), "n_n": int(CN[:, mask].sum())}
    return out


def cgm_twoway(P: dict, scopes: dict, costs: dict) -> dict:
    """Two-way (firm and month) cluster-robust inference on the pooled difference (Cameron, Gelbach and Miller 2011):
    V = V_firm + V_month - V_cell from the difference's influence values (max(V_firm, V_month) if that is not
    positive); normal p (H0: difference <= 0) and intervals. The pigeonhole bootstrap counts the observation-level
    variance twice and is not used."""
    out = {}
    for s_, mask in scopes.items():
        XD, CD, XN, CN = (P[k][:, mask] for k in ("XD", "CD", "XN", "CN"))
        nd, nn = float(CD.sum()), float(CN.sum())
        out[s_] = {}
        for c, cv in costs.items():
            if nd < 2 or nn < 2:
                out[s_][c] = {"est": None, "p": None, "p_lt": None, "ci": [None, None], "ci98": [None, None]}
                continue
            mD, mN = (XD.sum() - cv * nd) / nd, XN.sum() / nn
            d0 = float(mD - mN)
            U = np.where(CD > 0, (XD - cv - mD) / nd, 0.0) - np.where(CN > 0, (XN - mN) / nn, 0.0)
            vf, vm, vi = float((U.sum(1) ** 2).sum()), float((U.sum(0) ** 2).sum()), float((U * U).sum())
            v = vf + vm - vi
            if not v > 0:
                v = max(vf, vm)
            se = math.sqrt(v) if v > 0 else 0.0
            z = d0 / se if se > 0 else (math.inf if d0 > 0 else -math.inf)
            out[s_][c] = {"est": d0, "se": se, "p": 1.0 - _NORM.cdf(z) if math.isfinite(z) else (0.0 if z > 0 else 1.0),
                          "p_lt": _NORM.cdf(z) if math.isfinite(z) else (1.0 if z > 0 else 0.0),
                          "ci": [d0 - 1.959964 * se, d0 + 1.959964 * se], "ci98": [d0 - 2.326348 * se, d0 + 2.326348 * se],
                          "n_d": int(nd), "n_n": int(nn), "v_firm": vf, "v_month": vm, "v_cell": vi, "p_mc_se": 0.0, "reps": 0}
    return out


def twoway_mc(P: dict, scopes: dict, costs: dict, how: str, reps: Optional[int] = None) -> dict:
    """``twoway_boot`` over ``reps`` seeds: replicate means of p and interval ends with their Monte Carlo s.e.; again
    with REPS_MAX seeds when any p lies within 2 Monte Carlo s.e. of the trial's 0.01."""
    reps = REPS if reps is None else reps

    def run(r):
        rs = [twoway_boot(P, scopes, costs, how, N_BOOT, SEED + 100 * k) for k in range(r)]
        return {s: {c: _avg_reps([x[s][c] for x in rs], ("ci", "ci98")) for c in costs} for s in scopes}
    t = run(reps)
    unresolved = any(v.get("p") is not None and resolve(v["p"], v.get("p_mc_se"), T374_ALPHA, "lt")[0] is None
                     for sc in t.values() for v in sc.values())
    if unresolved and REPS_MAX > reps:
        t = run(REPS_MAX)
    return t


def _div_row(b: dict, label: str, thr: float = T374_THR, alpha: float = T374_ALPHA) -> tuple:
    """(name, ok, decisive) for 'difference >= thr with p < alpha' on one bootstrap result; decisive: the one-sided 99%
    upper bound (two-sided 98% upper end) lies below thr."""
    est, p = b.get("est"), b.get("p")
    if est is None or p is None:
        return f"{label}: n/a", None, False
    ok_p, note = resolve(p, b.get("p_mc_se"), alpha, "lt")
    ok = (est >= thr) and ok_p if ok_p is not None else (False if est < thr else None)
    hi = (b.get("ci98") or [None, None])[1]
    dec = hi is not None and hi < thr
    return f"{label} {_bp(est)}, p {p:.4f}{note}", ok, dec


def _and_rows(rows: Sequence[tuple], label: str) -> tuple:
    """A conjunction of criteria rows (name, ok, decisive): False when any part fails (decisive when a failing part is),
    True when every part passes, else None."""
    oks = [r[1] for r in rows]
    ok = False if any(o is False for o in oks) else (True if all(o is True for o in oks) else None)
    dec = ok is False and any(r[1] is False and r[2] for r in rows)
    return f"{label} (" + "; ".join(r[0] for r in rows) + ")", ok, dec


def judge_divmonth(P: dict, E: Optional[dict], family: dict, dsr_x: Sequence[float], min_n: int = T374_MIN_N,
                   reps: Optional[int] = None, split: str = T374_SPLIT, n_absent: int = 0) -> dict:
    """T-374 criteria. P: the stock panel, E: the ETF panel (None = not available), family: {trial: per-period Sharpe},
    dsr_x: the primary's monthly net difference series, n_absent: current members with no archived history (rule 9: a
    stock criterion is kept only when no plausible data for them could change it, see ``absent_sensitivity``)."""
    costs = {"gross": 0.0, "net": T374_COST}
    scopes = _scope_masks(P["months"], split)
    boots = {TWO: cgm_twoway(P, scopes, costs)}
    boots.update({h: twoway_mc(P, scopes, costs, h, reps) for h in T374_HOWS})
    n = int(P["CD"].sum())
    labels = {"full": f"{P['months'][0]}..{P['months'][-1]}" if P["months"] else "full",
              "first": f"..{int(split[:4]) - 1}", "second": f"{split[:4]}.."}
    crit, sens = [], {}
    for s, title in (("full", "whole span"), ("first", "first half"), ("second", "second half")):
        rows = [_div_row(boots[h][s][c], f"{h} {c}") for h in (TWO,) + T374_HOWS for c in costs]
        nd = boots[TWO][s]["gross"].get("n_d")
        c = all_constructions(rows, f"difference >= 20 bp with clustered p < 0.01 over the {title} ({labels[s]}, "
                                    f"{nd} dividend firm-months; firm- and month-clustered, gross and net)")
        if n_absent:
            # rule 9 for every reading of the conjunction: a False stands only when no reading could flip (each absent
            # firm would need a difference beyond every included firm's), likewise a True
            rd = {cn: absent_sensitivity(P, scopes[s], n_absent, boots[TWO][s][cn].get("est"), boots[TWO][s][cn].get("ci"),
                                         cost=cv) for cn, cv in costs.items()}
            sens[s] = rd
            if c[1] is False:
                st_ = {cn: r["need_up"] is not None and r["need_up"] > r["firm_max"] for cn, r in rd.items()}
                robust = all(st_.values())
                txt = "; ".join(f"{cn} {_bp(r['need_up'])} each vs the largest included firm's {_bp(r['firm_max'])} to reach "
                                f"the pass bound {_bp(r.get('bound'))}" + ("" if st_[cn] else " (could flip)") for cn, r in rd.items())
                c = (c[0] + f" [{n_absent} absent current members would need a dividend-minus-non-dividend difference of: "
                            + txt + ("; the failure stands under every reading]" if robust else
                                     "; undecided by the absent data: a reading's failure does not stand]"),
                     False if robust else None, c[2] and robust)
            elif c[1] is True:
                st_ = {cn: r["need_down"] is not None and r["need_down"] < r["firm_min"] for cn, r in rd.items()}
                robust = all(st_.values())
                txt = "; ".join(f"{cn} {_bp(r['need_down'])} each vs the smallest included firm's {_bp(r['firm_min'])}"
                                + ("" if st_[cn] else " (could flip)") for cn, r in rd.items())
                c = (c[0] + f" [{n_absent} absent current members would need, to undo it: " + txt
                            + ("; the pass stands under every reading]" if robust else "; undecided by the absent data]"),
                     True if robust else None, False)
        crit.append(c)
    etf = None
    if E is not None and E["XD"].size and E["CD"].sum() > 0:
        eb = twoway_mc(E, _scope_masks(E["months"], split), costs, "month", reps)
        e2 = cgm_twoway(E, _scope_masks(E["months"], split), costs)
        readings = []
        for c in costs:
            readings.append(_and_rows([_div_row(eb[s][c], f"{s} half") for s in ("first", "second")], f"[{c}] both halves"))
            readings.append(_div_row(eb["full"][c], f"[{c}] whole span"))
        crit.append(all_constructions(readings, f"ETF-only robustness ({', '.join(E['syms'])}; month-clustered; "
                                                f"{int(E['CD'].sum())} dividend fund-months) holds (the pass in both halves, "
                                                f"or over the whole span; gross and net)"))
        etf = {"month": eb, TWO: e2, "funds": E["syms"]}
    else:
        crit.append(("ETF-only robustness (VYM, SCHD, SDY, DVY not archived)", None, False))
    fs = [family.get(k) for k in sorted(family)]
    d = family_dsr(np.asarray(dsr_x, float), fs, T374_TRIALS) if len(dsr_x) > 3 else {"dsr": None}
    row = dsr_row(d, f"DSR > 0.95 of the monthly net difference ({len(dsr_x)} months)")
    d_abs = None
    if n_absent and row[1] is not None and sens.get("full", {}).get("net", {}).get("w"):
        row, d_abs = dsr_absent(row, np.asarray(dsr_x, float), family, sens["full"]["net"], n_absent)
    crit.append(row)
    v, why = _decide(crit, n, min_n, "dividend firm-months")
    return {"n": n, "boot": boots, "etf": etf, "dsr": d, "dsr_absent": d_abs, "absent_sensitivity": sens,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def dsr_absent(row: tuple, x: np.ndarray, family: dict, se_: dict, n_absent: int) -> tuple:
    """Rule 9 for the DSR, which is computed on the stock panel's monthly net difference and so involves the absent
    current members too: give them weight w (``absent_sensitivity``) and the largest (for a failure) or smallest (for a
    pass) included firm-level net difference in every month, x' = (1 - w) x + w d, and recompute the DSR with the
    primary trial's Sharpe (the first trial in sorted order) replaced. The criterion stands only when x' keeps its side
    of 0.95; otherwise it is undecided (None)."""
    w = float(se_["w"])
    fail = row[1] is False
    dv = se_["firm_max"] if fail else se_["firm_min"]
    xs = (1.0 - w) * x + w * dv
    keys = sorted(family)
    fs = [(_sr(xs) if k == keys[0] else family.get(k)) for k in keys]
    d2 = family_dsr(xs, fs, T374_TRIALS)
    v2 = d2.get("dsr")
    stands = v2 is not None and ((v2 <= DSR_PASS) if fail else (v2 > DSR_PASS))
    note = (f" [{n_absent} absent current members at weight {w:.4f}, each with the {'largest' if fail else 'smallest'} "
            f"included firm's net difference {_bp(dv)} in every month: DSR {_f(v2)}"
            + ("; the " + ("failure" if fail else "pass") + " stands]" if stands else "; undecided by the absent data]"))
    return (row[0] + note, row[1] if stands else None, row[2] and stands), d2


def monthly_diff(P: dict, cost: float = T374_COST, per: int = 1) -> np.ndarray:
    """Per-period (dividend net minus non-dividend) mean market-adjusted span return, periods with both kinds; ``per``
    months a period (3 = calendar quarters, for funds that all go ex in the same months)."""
    if per == 1:
        nd, nn = P["CD"].sum(0), P["CN"].sum(0)
        ok = (nd > 0) & (nn > 0)
        return ((P["XD"].sum(0)[ok] - cost * nd[ok]) / nd[ok]) - P["XN"].sum(0)[ok] / nn[ok]
    keys = [(int(m[:4]) * 12 + int(m[5:7]) - 1) // per for m in P["months"]]
    out = []
    for k in sorted(set(keys)):
        c = np.array([kk == k for kk in keys])
        nd, nn = P["CD"][:, c].sum(), P["CN"][:, c].sum()
        if nd > 0 and nn > 0:
            out.append((P["XD"][:, c].sum() - cost * nd) / nd - P["XN"][:, c].sum() / nn)
    return np.array(out, float)


def absent_sensitivity(P: dict, mask: np.ndarray, n_absent: int, est: Optional[float], ci: Sequence, thr: float = T374_THR,
                       z: float = 2.326, cost: float = T374_COST) -> dict:
    """Could ``n_absent`` firms without data change a criterion 'difference >= thr with one-sided p < 0.01'? Each absent
    firm is given the included firms' mean number of dividend firm-months in the scope (weight w of the pooled mean);
    the pass bound is max(thr, z x the two-way s.e.). ``need_up``: the D-minus-N difference the absent firms would need
    to lift the estimate to the bound; ``need_down``: to pull it below. Compared with the largest and smallest firm-level
    differences of the included firms (noisy, so a generous range)."""
    out = {"n_absent": int(n_absent), "need_up": None, "need_down": None, "firm_max": None, "firm_min": None, "w": None}
    if est is None or not ci or ci[0] is None or ci[1] is None:
        return out
    CD, CN, XD, XN = (P[k][:, mask] for k in ("CD", "CN", "XD", "XN"))
    nd, nn = CD.sum(1), CN.sum(1)
    ok = (nd > 0) & (nn > 0)
    if not ok.any():
        return out
    fd = (XD.sum(1)[ok] - cost * nd[ok]) / nd[ok] - XN.sum(1)[ok] / nn[ok]
    add = n_absent * float(nd[ok].mean())
    w = add / (float(CD.sum()) + add) if add > 0 else 0.0
    se = (ci[1] - ci[0]) / 3.92
    bound = max(thr, z * se)
    out.update(firm_max=float(fd.max()), firm_min=float(fd.min()), w=w, bound=bound)
    if w > 0:
        out["need_up"] = (bound - (1 - w) * est) / w
        out["need_down"] = (bound - (1 - w) * est) / w
    return out


def exday_capture(cal: np.ndarray, spy: np.ndarray, firms: dict, m_lo: str = T374_START, m_hi: str = T374_END,
                  cost: float = T374_COST) -> np.ndarray:
    """The ex-day capture trial: close two sessions before each ex-date to the ex-date close, market-adjusted, net;
    the per-month mean over all ex-dates of the month."""
    lo, hi = _mk_of(m_lo), _mk_of(m_hi)
    by = defaultdict(list)
    for f in firms.values():
        adj = f["adj"]
        for e in f["exd"]:
            mk = _mk(int(e))
            if mk < lo or mk > hi:
                continue
            i = int(np.searchsorted(cal, e))
            if i < 2 or i >= cal.size or cal[i] != e or not (np.isfinite(adj[i]) and np.isfinite(adj[i - 2])):
                continue
            by[mk].append(adj[i] / adj[i - 2] - spy[i] / spy[i - 2] - cost)
    return np.array([np.mean(by[k]) for k in sorted(by)], float)


def _sr(x) -> Optional[float]:
    x = np.asarray(x, float)
    if x.size < 3 or not x.std(ddof=1) > 0:
        return None
    return float(x.mean() / x.std(ddof=1))


def b6c_events_dividend_month(archive):
    """T-374: dividend-month premium of current S&P 500 payers 2010-01..2026-09."""
    etf_b = [f"daily-history-{s}" for s in T374_ETFS] + [f"daily-events-{s}" for s in T374_ETFS]
    miss = _missing(archive, [SPY_B, CONS_B] + etf_b)
    if miss:
        return miss
    sp = _spy(archive)
    cal, spy = sp["cal"], sp["adj"]
    cons = [r.get("value") or {} for r in _rows(archive, CONS_B)]
    snap = cons[0].get("revision_time", "")[:10] if cons else ""
    snap_ed = _ed(snap) if snap else int(cal[-1])
    syms = sorted({ntick(c.get("symbol")) for c in cons if c.get("symbol")})
    absent, payers, nonpayers = [], {}, []
    for s in syms:
        st, dv = _stock(archive, s), _dividends(archive, s)
        if st is None or dv is None:
            absent.append(s)
            continue
        if not ((dv > snap_ed - T374_PAYER_DAYS) & (dv <= snap_ed)).any():
            nonpayers.append(s)
            continue
        payers[s] = {"adj": st["adj"], "exd": dv, "first": st["first"]}
    ssga = None
    for k in range(0, 40):
        nm = f"ssga-spy-holdings-{_iso(snap_ed - k)}"
        if _has(archive, nm):
            tick = {ntick(str((r.get("value") or {}).get("ticker", "")).replace(" ", ".")) for r in _rows(archive, nm)}
            ssga = {"bundle": nm, "holdings": len(tick), "in_wikipedia": len(tick & set(syms))}
            break
    P = divmonth_panel(cal, spy, payers, mode="runup")
    Pt = divmonth_panel(cal, spy, payers, mode="through")
    etfs = {}
    for s in T374_ETFS:
        st, dv = _stock(archive, s), _dividends(archive, s)
        if st is not None and dv is not None and dv.size:
            etfs[s] = {"adj": st["adj"], "exd": dv, "first": st["first"]}
    E = divmonth_panel(cal, spy, etfs, mode="runup", same_firms=False) if etfs else None
    x = monthly_diff(P)
    sq = _sr(monthly_diff(E, per=3)) if E is not None else None
    fam = {"1 run-up (primary)": _sr(x), "2 through the ex-day": _sr(monthly_diff(Pt)),
           "3 ETF-only (quarterly, per month)": None if sq is None else sq / math.sqrt(3.0),
           "4 ex-day capture": _sr(exday_capture(cal, spy, payers))}
    j = judge_divmonth(P, E, fam, x, n_absent=len(absent))
    b = j["boot"]
    tw = b[TWO]
    stat = {"universe": {"constituents": len(syms), "snapshot": snap, "absent": absent, "current_payers": len(payers),
                         "non_payers": len(nonpayers), "ssga": ssga, "one_kind_firms": P["one_kind_firms"],
                         "firms": len(P["syms"])},
            "n_dividend_firm_months": j["n"], "n_nondividend_firm_months": int(P["CN"].sum()),
            "empty_spans": P["empty_spans"],
            "difference": {s: {c: tw[s][c].get("est") for c in ("gross", "net")} for s in tw},
            "mean_dividend_month_gross": float(P["XD"].sum() / max(P["CD"].sum(), 1)),
            "mean_nondividend_month": float(P["XN"].sum() / max(P["CN"].sum(), 1)),
            "p": {h: {s: {c: b[h][s][c].get("p") for c in ("gross", "net")} for s in b[h]} for h in b},
            "ci95": {h: {s: b[h][s]["net"].get("ci") for s in b[h]} for h in b},
            "through_ex_day": {"difference_net": _diff(Pt["XD"], Pt["CD"], Pt["XN"], Pt["CN"], T374_COST)},
            "etf": None if j["etf"] is None else {
                "funds": j["etf"]["funds"], "n_dividend_fund_months": int(E["CD"].sum()),
                "difference": {s: {c: j["etf"]["month"][s][c].get("est") for c in ("gross", "net")} for s in j["etf"]["month"]},
                "p_month": {s: {c: j["etf"]["month"][s][c].get("p") for c in ("gross", "net")} for s in j["etf"]["month"]},
                "p_two_way_cgm": {s: j["etf"][TWO][s]["net"].get("p") for s in j["etf"][TWO]}},
            "family_sharpe_monthly": fam, "dsr": j["dsr"], "absent_sensitivity": j["absent_sensitivity"],
            "criteria": j["criteria"], "cost_round_trip": T374_COST}
    dn = stat["difference"]
    et = stat["etf"]
    reason = (f"T-374 current S&P 500 dividend payers ({len(payers)} of {len(syms)} constituents of the {snap} Wikipedia "
              f"list have an ex-date in the year to it; {len(absent)} constituents have no archived Yahoo history: "
              f"{', '.join(absent) or 'none'}; the universe is current members, as the claim states, and each criterion that "
              f"involves the absent members (the stock criteria under gross and net, the DSR) is kept only when no plausible "
              f"data for them could change it; {len(P['syms'])} firms with both kinds of month, {len(P['one_kind_firms'])} monthly or "
              f"one-kind payers out), 2010-01..2026-09: {j['n']} predicted dividend firm-months vs "
              f"{stat['n_nondividend_firm_months']} non-dividend firm-months (run-up span: previous month-end close to the "
              f"close before the predicted ex-date; market-adjusted vs SPY). Difference gross {_bp(dn['full']['gross'])}, "
              f"net of 5 bp {_bp(dn['full']['net'])} (2010-2017 {_bp(dn['first']['net'])}, 2018-2026 "
              f"{_bp(dn['second']['net'])} net); two-way (CGM) p {_f(b[TWO]['full']['net'].get('p'), 4)}, firm-clustered "
              f"bootstrap p {_f(b['firm']['full']['net'].get('p'), 4)}, month-clustered p {_f(b['month']['full']['net'].get('p'), 4)} "
              f"(net, whole span; {N_BOOT} draws x {b['firm']['full']['net'].get('reps')} seeds). ETF-only: "
              + ("n/a" if et is None else f"{', '.join(et['funds'])}, {et['n_dividend_fund_months']} dividend fund-months, "
                 f"net {_bp(et['difference']['full']['net'])} (halves {_bp(et['difference']['first']['net'])} / "
                 f"{_bp(et['difference']['second']['net'])}), month-clustered p {_f(et['p_month']['full']['net'], 4)}")
              + f". Through the ex-day: net {_bp(stat['through_ex_day']['difference_net'])}. DSR {_f(j['dsr'].get('dsr'))} "
              f"at 4 trials. Criteria: " + "; ".join(f"{c[0]} -> {c[1]}" for c in j["criteria"]) + " — " + j["why"])
    return _out(stat, j["n"], j["verdict"], reason)


# =========================================================================== T-334 index-addition reversal ==

T334_START, T334_END = "2010-01-01", "2026-12-31"
T334_HOLD = 20                 # sessions after the effective-date close
T334_THR = -0.0020             # mean net 20-day excess < -0.2%
T334_COSTS = {"20 bps a trade (10 bps per leg per round trip)": 0.0020, "40 bps a trade (10 bps per leg per side)": 0.0040}
T334_MIN_N = 150               # addition events
T334_BUCKET = 40               # sessions per time-bucket cluster (2 x the hold)
T334_DRAWS = 1000              # placebo draws (the trial's)
T334_K = 10                    # nearest-size candidates per event in the placebo
T334_DV_WIN = 60               # trailing sessions of the dollar-volume size proxy (known before the entry)
T334_BUCKETS = (("2010-2014", 2010, 2014), ("2015-2019", 2015, 2019), ("2020-2024", 2020, 2024), ("2025-2026", 2025, 2026))


def absent_needed(n_ok: int, n_abs: int, mean_s: Optional[float], target: float, gap: float = 0.0) -> Optional[float]:
    """The mean the ``n_abs`` absent events would need for the full-universe mean (or, with ``gap`` = bound - mean on the
    survivors, the bound) to reach ``target``: information on how far the survivor result is from changing."""
    if not n_abs or mean_s is None:
        return None
    return ((target - gap) * (n_ok + n_abs) - n_ok * mean_s) / n_abs


def _share(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def addition_events(snaps: Sequence[tuple], changes: Sequence[dict], fja_last: Optional[int], start: str = T334_START,
                    end: str = T334_END, tol: int = CONFIRM_DAYS, spelled: Optional[dict] = None, facts=None,
                    edge_start: str = EDGE_START, refs: Optional[dict] = None) -> dict:
    """First appearances (joins) in the membership snapshots with effective dates in [start, end]. An event when a
    Wikipedia change row adds the same ticker within ``tol`` calendar days, or adds it under another spelling
    (``spelling_pairs``: DLPH = APTV, UA = UAA, Q = IQV, JOYG = JOY, ANR = ANRZQ); before ``edge_start`` (the Wikipedia
    table is incomplete there) an fja join is accepted unconfirmed; after the fja file's last date the snapshots are
    built from those rows, so they confirm themselves. Not an event: a join whose confirming row is a ticker change of
    one company (a rename-candidate row that ``same_company`` confirms on the tickers) or says the company 'remained in
    the index' (Howmet: Arconic Inc. renamed). Returns events (with how each is confirmed), unconfirmed joins, rename
    rows and the rename-candidate rows kept as additions (with the ticker evidence)."""
    lo, hi = _ed(start), _ed(end)
    e_edge = _ed(edge_start)
    if spelled is None:
        spelled = spelling_pairs(snaps, changes, refs if refs is not None else _ref_names([], changes), edge_start, tol)
    adds = defaultdict(list)
    rows = [(w, _ed(w["effective_date"])) for w in changes if w.get("effective_date")]
    for w, e in rows:
        t = ntick(w.get("added_ticker"))
        if t:
            adds[t].append((e, w))
    events, unconf, renamed, kept = [], [], [], []
    prev, e0 = None, None
    for e1, s1 in snaps:
        if prev is not None and lo <= e1 <= hi:
            L, J = set(prev - s1), set(s1 - prev)
            near = [w for w, e in rows if abs(e - e1) <= tol or e0 < e <= e1]
            for t in sorted(J):
                c = [(abs(e - e1), w) for e, w in adds.get(t, []) if abs(e - e1) <= tol]
                if c:
                    w, how = min(c, key=lambda z: z[0])[1], "same ticker"
                elif (t, e1) in spelled:
                    w, why = spelled[(t, e1)]
                    how = f"Wikipedia adds it as {ntick(w.get('added_ticker'))} ({why})"
                elif e1 < e_edge:
                    w, how = None, f"accepted unconfirmed (before {edge_start} the Wikipedia table is incomplete)"
                else:
                    unconf.append({"ticker": t, "date": _iso(e1)})
                    continue
                if w is not None:
                    reason = str(w.get("reason") or "")
                    if REMAIN_RE.search(reason):
                        renamed.append({"ticker": t, "date": _iso(e1), "reason": reason[:120], "why": "remained in the index"})
                        continue
                    if _rename_candidate(w):
                        others = {ntick(v.get("removed_ticker")) for v in near if v is not w}
                        same, why = same_company(w.get("removed_ticker"), t, w.get("removed_security"), w.get("added_security"),
                                                 L, J, others, facts=facts, e1=e1)
                        if same:
                            renamed.append({"ticker": t, "date": _iso(e1), "reason": reason[:120], "why": why})
                            continue
                        kept.append({"ticker": t, "date": _iso(e1), "reason": reason[:120], "why": why})
                events.append({"ticker": t, "ed": int(e1), "date": _iso(e1), "announced": (w or {}).get("announced"),
                               "after_fja": fja_last is not None and e1 > fja_last, "security": (w or {}).get("added_security"),
                               "confirmed": how})
        prev, e0 = s1, e1
    return {"events": events, "unconfirmed": unconf, "rename_rows": renamed, "rename_candidates_kept": kept}


def _dv_med(dv: np.ndarray, i: int, win: int = T334_DV_WIN) -> Optional[float]:
    seg = dv[max(0, i - win):i]
    seg = seg[np.isfinite(seg) & (seg > 0)]
    return float(np.median(seg)) if seg.size >= win // 2 else None


def event_excess(events: Sequence[dict], cal: np.ndarray, spy: np.ndarray, series, hold: int = T334_HOLD) -> list:
    """Each event's entry (first session on or after the effective date), the close ``hold`` sessions later and the
    excess return vs SPY; status ok / window_open / no_history / no_bar. ``series(ticker)`` -> resolved arrays or None."""
    out = []
    for ev in events:
        i0 = int(np.searchsorted(cal, ev["ed"]))
        r = dict(ev, i0=i0)
        if i0 + hold >= cal.size:
            r["status"] = "window_open"
            out.append(r)
            continue
        s = series(ev["ticker"])
        i1 = i0 + hold
        if s is None:
            r["status"] = "no_history"
        elif not (np.isfinite(s["adj"][i0]) and np.isfinite(s["adj"][i1])):
            r["status"] = "no_bar"
        else:
            r.update(status="ok", ex=float(s["adj"][i1] / s["adj"][i0] - spy[i1] / spy[i0]), dv=_dv_med(s["dv"], i0),
                     via=s["names"][int(s["src"][i0])] if s["src"][i0] >= 0 else ev["ticker"])
        out.append(r)
    return out


def placebo_draws(ok: Sequence[dict], pool, cal: np.ndarray, spy: np.ndarray, hold: int = T334_HOLD, k: int = T334_K,
                  draws: int = T334_DRAWS, seed: int = SEED) -> dict:
    """Size-matched placebo: for each event, the ``k`` non-changing members nearest in trailing dollar volume on the
    same date (``pool(event)`` -> [(ticker, arrays)]), one drawn at random per draw; the per-draw mean excess and each
    event's placebo excess averaged over the draws."""
    rng = np.random.default_rng(seed)
    cand = []
    for ev in ok:
        i0, i1 = ev["i0"], ev["i0"] + hold
        xs = []
        for t, s in pool(ev):
            if not (np.isfinite(s["adj"][i0]) and np.isfinite(s["adj"][i1])):
                continue
            d = _dv_med(s["dv"], i0)
            if d is None:
                continue
            xs.append((abs(math.log(d) - math.log(ev["dv"])) if ev.get("dv") else 0.0,
                       float(s["adj"][i1] / s["adj"][i0] - spy[i1] / spy[i0])))
        xs.sort()
        cand.append(np.array([x for _, x in xs[:k]], float))
    keep = [i for i, c in enumerate(cand) if c.size]
    if not keep:
        return {"n_events": 0, "draw_means": [], "per_event": [], "keep": []}
    M = np.zeros((draws, len(keep)))
    for j, i in enumerate(keep):
        c = cand[i]
        M[:, j] = c[rng.integers(0, c.size, draws)]
    return {"n_events": len(keep), "draw_means": M.mean(axis=1), "per_event": M.mean(axis=0), "keep": keep,
            "k_mean": float(np.mean([cand[i].size for i in keep]))}


def judge_additions(ok: Sequence[dict], complete: bool, placebo: Optional[dict], size_ok: bool, min_n: int = T334_MIN_N,
                    reps: Optional[int] = None, survivor_note: str = "") -> dict:
    """T-334 criteria on the priced events (``ok``: dicts with ex, date, i0). ``complete``: every event of the claim's
    universe is priced (else the criteria that need the absent names are not implemented). ``size_ok``: the placebo is
    matched on point-in-time size from a survivorship-free pool."""
    x = np.array([e["ex"] for e in ok], float)
    n = int(x.size)
    dates = [e["date"] for e in ok]
    bucket = [str(e["i0"] // T334_BUCKET) for e in ok]
    boots, rows1, rows2 = {}, [], []
    for name, c in T334_COSTS.items():
        xn = x + c
        chk = lambda t: _upper_lt0(t)[0]
        bd = cluster_mc(xn, dates, chk, reps)
        bb = cluster_mc(xn, bucket, chk, reps)
        boots[name] = {"date": bd, "bucket": bb}
        m = _mean(xn)
        lo = (bd.get("ci90") or [None])[0]
        rows1.append((f"[{name}] mean net {_pc(m, 3)} < -0.2%", None if m is None else m < T334_THR,
                      lo is not None and lo > T334_THR))
        for lab, b in (("effective-date clusters", bd), (f"{T334_BUCKET}-session buckets", bb)):
            okb, dec, note = _upper_lt0(b)
            rows2.append((f"[{name}, {lab}] one-sided 95% upper bound {_pc((b.get('ci90') or [None, None])[1], 3)}{note}", okb, dec))
    c1 = all_constructions(rows1, f"mean 20-day excess net of costs < -0.2% ({n} priced events)")
    c2 = all_constructions(rows2, "one-sided 95% upper bound < 0 (both cost readings, both cluster constructions)")
    pl = None
    if placebo is not None and len(placebo.get("per_event", [])):
        pe = np.asarray(placebo["per_event"], float)
        pdates = [dates[i] for i in placebo["keep"]]
        pl = cluster_mc(pe, pdates, None, reps)
        lo, hi = (pl.get("ci") or [None, None])[:2]
        okp = None if lo is None else bool(lo <= 0.0 <= hi)
        dm = np.asarray(placebo["draw_means"], float)
        c3 = (f"placebo centred on zero: mean {_pc(pl.get('est'), 3)}, 95% CI {_ci(pl.get('ci'), 3)} over "
              f"{placebo['n_events']} events, {len(dm)} draws (draw means 2.5-97.5% {_pc(float(np.quantile(dm, 0.025)), 3)} "
              f"to {_pc(float(np.quantile(dm, 0.975)), 3)})", okp, okp is False)
    else:
        c3 = ("placebo centred on zero (no placebo computed)", None, False)
    crit = []
    if complete:
        crit += [c1, c2]
    else:
        crit += [(c1[0] + f" [NOT IMPLEMENTED: survivor subset only{survivor_note}]", None, False),
                 (c2[0] + f" [NOT IMPLEMENTED: survivor subset only{survivor_note}]", None, False)]
    if complete and size_ok:
        crit.append(c3)
    else:
        why = []
        if not size_ok:
            why.append("matched on trailing dollar volume, not point-in-time market capitalisation")
        if not complete:
            why.append("the non-changing pool holds survivors only")
        crit.append((c3[0] + " [NOT IMPLEMENTED: " + "; ".join(why) + "]", None, False))
    v, why = _decide(crit, n, min_n, "addition events")
    return {"n": n, "boot": boots, "placebo": pl, "criteria": [(c[0], c[1]) for c in crit], "raw": [c1, c2, c3],
            "verdict": v, "why": why}


def b6c_events_index_addition_reversal(archive):
    """T-334: 20-session excess return after the effective-date close of S&P 500 additions 2010-2026."""
    miss = _missing(archive, [SPY_B, FJA_B, CHG_B, CONS_B])
    if miss:
        return miss
    sp = _spy(archive)
    cal, spy = sp["cal"], sp["adj"]
    tb = _tables(archive)
    book = _book(archive)
    A = addition_events(tb["snaps"], tb["chg"], tb["fja_last"], spelled=tb["spelled"], facts=tb["facts"])
    evs = event_excess(A["events"], cal, spy, book.resolved)
    ok = [e for e in evs if e["status"] == "ok"]
    status = defaultdict(int)
    for e in evs:
        status[e["status"]] += 1
    measurable = [e for e in evs if e["status"] != "window_open"]
    unpriced = [e for e in measurable if e["status"] != "ok"]
    cur = set(tb["current"])
    gone = [e for e in unpriced if e["ticker"] not in cur]
    complete = not unpriced
    via_rename = [e for e in ok if e.get("via") and e["via"] != e["ticker"]]
    # placebo on the priced pool
    snaps = tb["snaps"]
    snap_eds = [s[0] for s in snaps]

    def pool(ev):
        i0, i1 = ev["i0"], ev["i0"] + T334_HOLD
        lo_ed, hi_ed = int(cal[max(0, i0 - T334_HOLD)]), int(cal[i1])
        m0 = members_at(snaps, lo_ed - 1)
        stable = set(m0)
        for e, s in snaps[bisect.bisect_left(snap_eds, lo_ed):bisect.bisect_right(snap_eds, hi_ed)]:
            stable &= s
        out = []
        for t in sorted(stable):
            if t == ev["ticker"]:
                continue
            s = book.resolved(t)
            if s is not None:
                out.append((t, s))
        return out
    i_dv = [i for i, e in enumerate(ok) if e.get("dv")]
    pl = placebo_draws([ok[i] for i in i_dv], pool, cal, spy) if i_dv else None
    if pl is not None:
        pl = dict(pl, keep=[i_dv[i] for i in pl["keep"]])
    note = f": {len(unpriced)} of {len(measurable)} measurable additions have no Yahoo prices, {len(gone)} of them names no longer in the index"
    j = judge_additions(ok, complete, pl, size_ok=False, survivor_note=note)
    x = np.array([e["ex"] for e in ok], float)
    yrs = np.array([int(e["date"][:4]) for e in ok], int)
    buckets = {lab: {"n": int(((yrs >= a) & (yrs <= b)).sum()),
                     "mean_gross": _mean(x[(yrs >= a) & (yrs <= b)])} for lab, a, b in T334_BUCKETS}
    ann = []
    for e in ok:
        if not e.get("announced"):
            continue
        ia = int(np.searchsorted(cal, _ed(e["announced"]), "right"))
        s = book.resolved(e["ticker"])
        if ia < e["i0"] and s is not None and np.isfinite(s["adj"][ia]) and np.isfinite(s["adj"][e["i0"]]):
            ann.append(float(s["adj"][e["i0"]] / s["adj"][ia] - spy[e["i0"]] / spy[ia]))
    n_ann = sum(1 for e in A["events"] if e.get("announced"))
    bd = j["boot"][list(T334_COSTS)[0]]["date"]
    conf = defaultdict(int)
    for e in A["events"]:
        conf["same ticker" if e["confirmed"] == "same ticker" else ("spelling" if e["confirmed"].startswith("Wikipedia adds")
                                                                    else "unconfirmed before 2010-06")] += 1
    no_hist = [e for e in unpriced if e["status"] == "no_history"]
    no_bar = [e for e in unpriced if e["status"] == "no_bar"]
    own_refused = {(e["ticker"], e["date"]) for e in unpriced if _has(archive, f"daily-history-{ysym(e['ticker'])}")}
    no_404 = [e for e in no_hist if (e["ticker"], e["date"]) not in own_refused]       # Yahoo has nothing under the ticker
    no_ident = [e for e in no_hist if (e["ticker"], e["date"]) in own_refused]         # the ticker now names another company
    lst = lambda es: ", ".join(f"{e['ticker']} {e['date']}" for e in es) or "none"
    stat = {"events_confirmed": len(A["events"]), "confirmation": dict(conf),
            "confirmed_by_spelling": [{"ticker": e["ticker"], "date": e["date"], "how": e["confirmed"]} for e in A["events"]
                                      if e["confirmed"].startswith("Wikipedia adds")],
            "accepted_before_edge_start": [{"ticker": e["ticker"], "date": e["date"]} for e in A["events"]
                                           if e["confirmed"].startswith("accepted")],
            "status": dict(status), "n_priced": len(ok), "n_measurable": len(measurable),
            "priced_share": len(ok) / len(measurable) if measurable else None,
            "unpriced": [{"ticker": e["ticker"], "date": e["date"], "status": e["status"], "current_member": e["ticker"] in cur,
                          "own_bundle_archived": (e["ticker"], e["date"]) in own_refused} for e in unpriced],
            "unpriced_no_longer_members": len(gone), "unpriced_no_history": len(no_hist), "unpriced_no_bar": len(no_bar),
            "unpriced_yahoo_404": len(no_404), "unpriced_own_ticker_reissued": [f"{e['ticker']} {e['date']}" for e in no_ident],
            "complete_universe": complete,
            "priced_via_rename": [{"ticker": e["ticker"], "date": e["date"], "via": e["via"]} for e in via_rename],
            "unconfirmed_first_appearances": A["unconfirmed"], "rename_row_additions": A["rename_rows"],
            "rename_candidates_kept_as_additions": A["rename_candidates_kept"],
            "mean_excess_gross": _mean(x), "mean_excess_net": {k: (None if not x.size else float(x.mean() + c)) for k, c in T334_COSTS.items()},
            "ci90_net_date": {k: v["date"].get("ci90") for k, v in j["boot"].items()},
            "ci90_net_bucket": {k: v["bucket"].get("ci90") for k, v in j["boot"].items()},
            "effective_dates": len({e["date"] for e in ok}), "buckets_5y": buckets,
            "placebo": None if j["placebo"] is None else {"mean": j["placebo"].get("est"), "ci": j["placebo"].get("ci"),
                                                         "n_events": pl["n_events"], "k_mean": pl.get("k_mean"),
                                                         "draw_mean_q": [float(np.quantile(pl["draw_means"], q)) for q in (0.025, 0.5, 0.975)]},
            "announcement_runup": {"events_with_cited_announcement": n_ann, "priced": len(ann), "mean_excess": _mean(ann),
                                   "window": "close of the first session after the announcement day -> effective-date close (variant; not in the pass)"},
            "rename_edges_used": len(tb["edges"]), "identity_rejected": dict(book.rejected), "criteria": j["criteria"]}
    first = list(T334_COSTS)[0]
    mn = stat["mean_excess_net"][first]
    up = (bd.get("ci90") or [None, None])[1]
    stat["absent_needed_20bps"] = {
        "upper_bound_below_0": absent_needed(len(ok), len(unpriced), mn, 0.0, (up - mn) if (up is not None and mn is not None) else 0.0),
        "mean_above_minus_0.2pct": absent_needed(len(ok), len(unpriced), mn, T334_THR)}
    an = stat["absent_needed_20bps"]
    rn = ", ".join(f"{r['ticker']} {r['date']}" for r in A["rename_rows"]) or "none"
    reason = (f"T-334 S&P 500 additions 2010-2026: {len(A['events'])} additions (fja first appearances: {conf.get('same ticker', 0)} "
              f"matched to a Wikipedia add of the same ticker within {CONFIRM_DAYS} days, {conf.get('spelling', 0)} to a "
              f"Wikipedia add under another spelling ("
              + (", ".join(f"{e['ticker']} {e['date']}" for e in stat["confirmed_by_spelling"]) or "none")
              + f"), {conf.get('unconfirmed before 2010-06', 0)} accepted before {EDGE_START} where the Wikipedia table is "
              f"incomplete; {len(A['unconfirmed'])} unconfirmed first appearances and {len(A['rename_rows'])} ticker changes "
              f"of one company judged on the tickers ({rn}) not counted; {len(A['rename_candidates_kept'])} rows whose reason "
              f"reads like a rename kept as additions because the tickers are different companies), "
              f"{status.get('window_open', 0)} with the 20-session window still open; SURVIVORSHIP: {len(ok)} of "
              f"{len(measurable)} measurable additions priced ({_share(stat['priced_share'])}; {len(via_rename)} through a "
              f"rename or a later listing's successor: " + lst(via_rename) + f"), {len(unpriced)} unpriced: {len(no_404)} "
              f"with no Yahoo history under the ticker or any successor (Yahoo answers 404: delisted or acquired; "
              f"{sum(1 for e in no_404 if e['ticker'] not in cur)} of them no longer in the index), {len(no_ident)} whose "
              f"ticker Yahoo now gives to another company, with no successor history to fall back on (refused on identity: "
              + lst(no_ident) + f") and {len(no_bar)} with a Yahoo history but no traded bar on the entry or exit date ("
              + lst(no_bar) + f"; Yahoo series or spans refused on identity or as later listings in all: {len(book.rejected)}), "
              f"so every criterion on the mean needs absent names' returns (the absent additions would need a mean net excess of "
              f"{_pc(an['upper_bound_below_0'], 2)} for the "
              f"20-bps upper bound to fall below 0, or {_pc(an['mean_above_minus_0.2pct'], 2)} for the mean to miss -0.2%). "
              f"Survivor subset: mean 20-day excess gross {_pc(_mean(x), 3)}, net {_pc(stat['mean_excess_net'][first], 3)} "
              f"(20 bps) / {_pc(stat['mean_excess_net'][list(T334_COSTS)[1]], 3)} (40 bps), one-sided 95% upper bound "
              f"(date clusters, 20 bps) {_pc((bd.get('ci90') or [None, None])[1], 3)}; 5-year buckets "
              + ", ".join(f"{k} {_pc(v['mean_gross'], 2)} (n {v['n']})" for k, v in buckets.items())
              + f"; dollar-volume placebo (survivors) {_pc(stat['placebo']['mean'] if stat['placebo'] else None, 3)}; "
              f"announcement-to-effective run-up on {len(ann)} of {n_ann} events with a cited announcement date "
              f"{_pc(_mean(ann), 2)} (variant, not in the pass). Criteria: "
              + "; ".join(f"{c[0]} -> {c[1]}" for c in j["criteria"]) + " — " + j["why"])
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================== T-394 FINRA short-volume ratio ==

T394_START, T394_END = "2019-01-01", "2026-12-31"
T394_FIRST_MONTH = "2018-08"   # the CNMS bundles' first month (z warm-up)
T394_LAST_MONTH = "2030-12"    # probe bound for monthly bundles
T394_WIN = 60                  # trailing file days in the z window (t included)
T394_MIN_OBS = 55              # valid ratios needed in the window
T394_THR = 2.0
T394_HOLD = 5                  # sessions: next open -> the open 5 sessions later
T394_BLOCK = 10                # sessions per date block (2 x the hold)
T394_COSTS = {"10 bps a trade (5 bp per side, stock leg)": 0.0010, "20 bps a trade (5 bp per side, stock and SPY legs)": 0.0020}
T394_SPLIT = "2023-01-01"
T394_MIN_N = 5000              # events
T394_FM_MIN = 30               # names per Fama-MacBeth cross-section


def _months(a: str, b: str) -> list:
    out, k = [], _mk_of(a)
    while k <= _mk_of(b):
        out.append(_mk_str(k))
        k += 1
    return out


def cnms_panel(archive, first: str = T394_FIRST_MONTH, last: str = T394_LAST_MONTH) -> dict:
    """File days (status ok) x symbols matrix of the short-volume ratio from the monthly CNMS bundles present."""
    def load():
        months = [m for m in _months(first, last) if _has(archive, CNMS_FMT.format(m))]
        days, recs = set(), []
        for m in months:
            nm = CNMS_FMT.format(m)
            keep = _avail_filter(archive, nm)
            for r in archive.load(nm):                     # streamed: about 1.3 M rows, not cached as dicts
                if not keep(r):
                    continue
                v = r.get("value") or {}
                k = r.get("kind")
                if k == "file-day" or (k is None and "status" in v):
                    if v.get("status", "ok") == "ok" and v.get("day"):
                        days.add(_ed(v["day"]))
                    continue
                sv, tv = _num(v.get("short_volume")), _num(v.get("total_volume"))
                if v.get("day") and v.get("symbol") and sv is not None and tv and tv > 0:
                    recs.append((_ed(v["day"]), ntick(v["symbol"]), sv / tv, tv))
        if not days:
            days = {d for d, _, _, _ in recs}
        dl = np.array(sorted(days), np.int64)
        syms = sorted({s for _, s, _, _ in recs})
        si = {s: i for i, s in enumerate(syms)}
        X = np.full((dl.size, len(syms)), np.nan)
        TV = np.full((dl.size, len(syms)), np.nan, np.float32)
        di = {int(d): i for i, d in enumerate(dl)}
        for d, s, x, tv in recs:
            i = di.get(d)
            if i is not None:
                X[i, si[s]] = x
                TV[i, si[s]] = tv
        present = set(months)
        span = _months(months[0], months[-1]) if months else []
        return {"days": dl, "syms": syms, "svr": X, "tv": TV, "months": months,
                "missing_months": [m for m in span if m not in present]}
    return _cached(archive, ("cnms",), load)


def svr_z(X: np.ndarray, win: int = T394_WIN, min_obs: int = T394_MIN_OBS) -> np.ndarray:
    """z of each day's ratio against the symbol's trailing ``win`` file days including that day (NaN with fewer than
    ``min_obs`` valid ratios in the window, or no dispersion)."""
    V = np.isfinite(X)
    X0 = np.where(V, X, 0.0)
    pad = lambda A: np.vstack([np.zeros((1, A.shape[1])), np.cumsum(A, axis=0)])
    c1, c2, cn = pad(X0), pad(X0 * X0), pad(V.astype(float))
    n = X.shape[0]
    lo = np.maximum(np.arange(n) + 1 - win, 0)
    hi = np.arange(n) + 1
    s1, s2, cnt = c1[hi] - c1[lo], c2[hi] - c2[lo], cn[hi] - cn[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = s1 / cnt
        var = (s2 - cnt * mu * mu) / (cnt - 1)
        sd = np.sqrt(np.where(var > 1e-14, var, np.nan))
        z = (X - mu) / sd
    z[(cnt < min_obs) | ~V] = np.nan
    return z


def svr_returns(days: np.ndarray, cal: np.ndarray, spy_open: np.ndarray, opens: np.ndarray, hold: int = T394_HOLD) -> np.ndarray:
    """Abnormal open-to-open returns (D x S): next session's open after each file day -> the open ``hold`` sessions
    later, minus SPY's over the same opens. ``opens``: calendar x symbols total-return opens."""
    i = np.searchsorted(cal, days)
    on = (i < cal.size) & (cal[np.minimum(i, cal.size - 1)] == days)
    e0, e1 = i + 1, i + 1 + hold
    ok = on & (e1 < cal.size)
    R = np.full((days.size, opens.shape[1]), np.nan)
    rows = np.flatnonzero(ok)
    a, b = e0[rows], e1[rows]
    with np.errstate(invalid="ignore", divide="ignore"):
        R[rows] = opens[b] / opens[a] - 1.0 - (spy_open[b] / spy_open[a] - 1.0)[:, None]
    return R


def fama_macbeth(Z: np.ndarray, R: np.ndarray, mask: np.ndarray, lag: int = 2 * T394_HOLD, min_names: int = T394_FM_MIN) -> dict:
    """Daily cross-sectional OLS slope of the 5-day abnormal return on z (members with both), then the time-series mean
    with a Newey-West s.e. (lag >= the overlap)."""
    sl = []
    for t in range(Z.shape[0]):
        m = mask[t] & np.isfinite(Z[t]) & np.isfinite(R[t])
        if m.sum() < min_names:
            continue
        z, r = Z[t, m], R[t, m]
        zc = z - z.mean()
        if not (zc @ zc) > 0:
            continue
        sl.append(float(zc @ (r - r.mean()) / (zc @ zc)))
    h = hac_mean(np.array(sl, float), lag) if len(sl) > 3 else {"mean": None, "t": None}
    return {"n_days": len(sl), "slope": h.get("mean"), "t": h.get("t"), "lag": lag}


def spell_pieces(src: np.ndarray, cal: np.ndarray, bounds: Sequence[int]) -> list:
    """[(source index, first calendar index, end index)] of a resolved series: each source's sessions between
    consecutive rename / join dates of the root ticker, so a stitched history is judged per spell (Yahoo's IR is
    Gardner Denver until the 2020-03-02 rename and Ingersoll Rand Inc. after it)."""
    cuts = sorted({0, int(src.size)} | {int(np.searchsorted(cal, b)) for b in bounds})
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        seg = src[a:b]
        for k in sorted(set(seg[seg >= 0].tolist())):
            idx = np.flatnonzero(seg == k)
            out.append((int(k), a + int(idx[0]), a + int(idx[-1]) + 1))
    return out


VOL_RATIO = (0.08, 1.0)         # FINRA off-exchange / Yahoo as-traded volume, median over member days (measured 0.15-0.47)
VOL_CORR = 0.4                  # correlation of the two log volumes (measured >= 0.5 for every verified identity)
VOL_MIN_DAYS = 20


def finra_identity(tv: np.ndarray, yv: np.ndarray, member: np.ndarray, min_days: int = VOL_MIN_DAYS) -> dict:
    """Does a Yahoo series belong to the FINRA symbol? On the member file days with both volumes: the median ratio of
    FINRA's off-exchange volume to Yahoo's as-traded volume and the correlation of their logs. ok None when fewer than
    ``min_days`` days overlap (not checkable)."""
    sel = member & np.isfinite(tv) & np.isfinite(yv) & (tv > 0) & (yv > 0)
    n = int(sel.sum())
    if n < min_days:
        return {"ok": None, "days": n, "ratio": None, "corr": None}
    lt, ly = np.log(tv[sel]), np.log(yv[sel])
    ratio = float(np.exp(np.median(lt - ly)))
    corr = float(np.corrcoef(lt, ly)[0, 1]) if lt.std() > 0 and ly.std() > 0 else 0.0
    return {"ok": bool(VOL_RATIO[0] <= ratio <= VOL_RATIO[1] and corr >= VOL_CORR), "days": n, "ratio": ratio, "corr": corr}


def judge_svr(ar: np.ndarray, sig_days: Sequence[str], sess: np.ndarray, complete: bool, min_n: int = T394_MIN_N,
              split: str = T394_SPLIT, reps: Optional[int] = None, survivor_note: str = "") -> dict:
    """T-394 criteria on the priced events (abnormal returns ``ar``, signal days, session indices). ``complete``: every
    event of the point-in-time universe is priced (else the return criteria are not implemented)."""
    ar = np.asarray(ar, float)
    n = int(ar.size)
    blocks = [str(int(s) // T394_BLOCK) for s in sess]
    h1 = np.array([d < split for d in sig_days], bool)
    rows1, rows2, boots = [], [], {}
    for name, c in T394_COSTS.items():
        x = ar + c
        chk = lambda t: _upper_lt0(t)[0]
        bd = cluster_mc(x, list(sig_days), chk, reps)
        bb = cluster_mc(x, blocks, chk, reps)
        boots[name] = {"date": bd, "block": bb}
        for lab, b in (("date clusters", bd), (f"{T394_BLOCK}-session date blocks", bb)):
            okb, dec, note = _upper_lt0(b)
            rows1.append((f"[{name}, {lab}] mean net {_bp(b.get('est'))}, one-sided 95% upper bound "
                          f"{_bp((b.get('ci90') or [None, None])[1])}{note}", okb, dec))
        m1, m2 = _mean(x[h1]), _mean(x[~h1])
        ok3 = None if (m1 is None or m2 is None) else bool(m1 < 0 and m2 < 0)
        dec3 = False
        if ok3 is False:
            for hm, mm in ((h1, m1), (~h1, m2)):
                if mm is not None and mm >= 0:
                    bh = cluster_mc(x[hm], [d for d, k in zip(sig_days, hm) if k], None, 1)
                    dec3 = dec3 or (bh["ci"][0] is not None and bh["ci"][0] > 0)
        rows2.append((f"[{name}] 2019-2022 {_bp(m1)} ({int(h1.sum())} events), 2023-2026 {_bp(m2)} ({int((~h1).sum())} events)",
                      ok3, dec3))
    c1 = all_constructions(rows1, f"one-sided 95% upper bound of the mean net abnormal return < 0 over {n} events")
    c2 = all_constructions(rows2, "negative net mean in both halves")
    if complete:
        crit = [c1, c2]
    else:
        crit = [(c[0] + f" [NOT IMPLEMENTED: survivor subset only{survivor_note}]", None, False) for c in (c1, c2)]
    v, why = _decide(crit, n, min_n, "events")
    return {"n": n, "boot": boots, "criteria": [(c[0], c[1]) for c in crit], "raw": [c1, c2], "verdict": v, "why": why}


def b6c_events_short_volume_ratio(archive):
    """T-394: FINRA CNMS off-exchange short-volume-ratio z > 2 and the next 5-session abnormal return, 2019-2026."""
    miss = _missing(archive, [SPY_B, FJA_B, CHG_B, CONS_B, CNMS_FMT.format("2019-01")])
    if miss:
        return miss
    sp = _spy(archive)
    cal = sp["cal"]
    tb = _tables(archive)
    book = _book(archive, check_own=False, unknown_ok=True, names_veto=False)
    C = cnms_panel(archive)
    days, syms, X = C["days"], C["syms"], C["svr"]
    Z = svr_z(X)
    snaps = tb["snaps"]
    mask = np.zeros(X.shape, bool)
    col = {s: j for j, s in enumerate(syms)}
    last = None
    for i, d in enumerate(days):
        mem = members_at(snaps, int(d))
        if mem is not last:
            idx = [col[s] for s in mem if s in col]
            last = mem
        mask[i, idx] = True
    win = (days >= _ed(T394_START)) & (days <= _ed(T394_END))
    opens = np.full((cal.size, len(syms)), np.nan)
    no_hist, id_fail, id_unchecked, refilled = [], [], 0, []
    ic = np.minimum(np.searchsorted(cal, days), cal.size - 1)
    on_cal = cal[ic] == days
    for j, s in enumerate(syms):
        tv = C["tv"][:, j].astype(float)
        r, refuse = book.resolved(s), ()
        for _round in range(4):                    # refuse failing spell pieces; the successor chain fills those dates
            if r is None:
                break
            new = []
            for k, a, b in spell_pieces(r["src"], cal, sorted({e for e, _ in book.succ.get(s, [])} | set(book.joins.get(s, [])))):
                nm = r["names"][k]
                seg = np.zeros(cal.size, bool)
                seg[a:b] = r["src"][a:b] == k
                yv = np.where(seg, r["vol"] / _split_factor(archive, nm), np.nan)[ic]
                chk = finra_identity(tv, np.where(on_cal, yv, np.nan), mask[:, j])
                if chk["ok"] is False:
                    new.append((nm, int(cal[a]), int(cal[b - 1]) + 1))
                    id_fail.append({"symbol": s, "yahoo": nm, "from": _iso(cal[a]), "to": _iso(cal[b - 1]), "days": chk["days"],
                                    "ratio": chk["ratio"], "corr": chk["corr"]})
                elif chk["ok"] is None and _round == 0:
                    id_unchecked += 1
            if not new:
                break
            refuse = refuse + tuple(new)
            r = book.resolved(s, refuse=refuse)
            fills = {}                                     # member sessions of each refused span now priced by another source
            for nm, a_, b_ in new:
                span = (cal >= a_) & (cal < b_)
                got = span & np.isfinite(r["adj"]) if r is not None else np.zeros(cal.size, bool)
                if r is not None:
                    got &= np.array([r["names"][q] != nm if q >= 0 else False for q in r["src"]], bool)
                fills[f"{nm} {_iso(a_)}..{_iso(b_ - 1)}"] = sorted({r["names"][q] for q in r["src"][got].tolist()}) if got.any() else []
            refilled.append({"symbol": s, "refused": [[x[0], _iso(x[1]), _iso(x[2] - 1)] for x in new], "refilled_from": fills})
        if r is None or not np.isfinite(r["open"]).any():
            no_hist.append(s)
            continue
        opens[:, j] = r["open"]
    R = svr_returns(days, cal, sp["open"], opens)
    ev = (Z > T394_THR) & mask & win[:, None]
    n_all = int(ev.sum())
    priced = ev & np.isfinite(R)
    # events whose exit open lies past the data are not yet measurable
    i_cal = np.searchsorted(cal, days)
    open_win = (i_cal + 1 + T394_HOLD >= cal.size)[:, None] & ev
    measurable = ev & ~open_win
    unpriced = measurable & ~priced
    n_meas, n_ok = int(measurable.sum()), int(priced.sum())
    hist_set = set(no_hist)
    up_cols = np.flatnonzero(unpriced.any(axis=0))
    up_syms = sorted({syms[j] for j in up_cols})
    up_no_hist = int(unpriced[:, [col[s] for s in up_syms if s in hist_set]].sum()) if up_syms else 0
    cur = set(tb["current"])
    up_gone = int(unpriced[:, [col[s] for s in up_syms if s not in cur]].sum()) if up_syms else 0
    complete = n_meas > 0 and not unpriced.any()
    ti, tj = np.nonzero(priced)
    ar = R[ti, tj]
    sig = [_iso(days[t]) for t in ti]
    sess = np.searchsorted(cal, days[ti])
    note = (f": {n_meas - n_ok} of {n_meas} point-in-time events lack Yahoo returns ({up_no_hist} on symbols with no "
            f"history, {up_gone} on names no longer in the index)")
    j = judge_svr(ar, sig, sess, complete, survivor_note=note)
    fm = fama_macbeth(Z[win], R[win], mask[win])
    yrs = np.array([int(s[:4]) for s in sig], int)
    c0 = list(T394_COSTS.values())[0]
    by_year = {str(y): {"n": int((yrs == y).sum()), "mean_gross": _mean(ar[yrs == y]), "mean_net_10bp": _mean(ar[yrs == y] + c0)}
               for y in sorted(set(yrs.tolist()))}
    member_days = int((mask & win[:, None] & np.isfinite(Z)).sum())
    bd = j["boot"][list(T394_COSTS)[0]]["date"]
    park = None if j["verdict"] == "inconclusive" else (j["verdict"] == "not_supported")
    mn0 = _mean(ar + c0) if ar.size else None
    up0 = (bd.get("ci90") or [None, None])[1]
    need = absent_needed(n_ok, n_meas - n_ok, mn0, 0.0, (up0 - mn0) if (up0 is not None and mn0 is not None) else 0.0)
    stat = {"file_days": int(win.sum()), "symbols": len(syms), "symbols_no_history": no_hist, "member_days_with_z": member_days,
            "events_point_in_time": n_all, "events_measurable": n_meas, "events_priced": n_ok,
            "priced_share": n_ok / n_meas if n_meas else None, "unpriced_on_no_history_symbols": up_no_hist,
            "unpriced_on_former_members": up_gone, "complete_universe": complete, "cnms_missing_months": C["missing_months"],
            "identity_rejected": id_fail, "identity_unchecked_segments": id_unchecked, "identity_refilled": refilled,
            "names_overruled_by_volume_check": dict(book.name_overruled),
            "rename_rejected": {k: v for k, v in book.rejected.items()},
            "mean_ar_gross": _mean(ar), "mean_ar_net": {k: (None if not ar.size else float(ar.mean() + c)) for k, c in T394_COSTS.items()},
            "ci90_net_date": {k: v["date"].get("ci90") for k, v in j["boot"].items()},
            "ci90_net_block": {k: v["block"].get("ci90") for k, v in j["boot"].items()},
            "halves_net_10bp": {"2019-2022": _mean(ar[yrs < 2023] + c0), "2023-2026": _mean(ar[yrs >= 2023] + c0)},
            "by_year": by_year, "fama_macbeth": fm, "park_condition": park, "rename_edges": len(tb["edges"]),
            "absent_needed_10bps_upper_below_0": need,
            "events_priced_on_backfilled_files": int(sum(1 for d in sig if d < "2021-10-27")),
            "criteria": j["criteria"]}
    reason = (f"T-394 FINRA CNMS off-exchange short-volume ratio, point-in-time S&P 500 members (fja05680 + Wikipedia), "
              f"{int(win.sum())} file days {_iso(days[win][0]) if win.any() else 'n/a'}..{_iso(days[win][-1]) if win.any() else 'n/a'}: "
              f"z (trailing {T394_WIN} file days, t included) > 2 gives {n_all} events ({n_meas} with a closed 5-session "
              f"window); SURVIVORSHIP: {n_ok} priced ({_share(stat['priced_share'])}), "
              f"{n_meas - n_ok} lack Yahoo returns ({up_no_hist} on {len([s for s in up_syms if s in hist_set])} symbols with no "
              f"Yahoo history even through renames, {n_meas - n_ok - up_no_hist} on symbols whose Yahoo history misses those "
              f"dates or was refused there, {up_gone} on names no longer in the index; own Yahoo tickers that are later "
              f"listings, replaced by the successor's history before the rename: "
              + (", ".join(k for k in sorted(book.rejected) if "<" in k) or "none") + f"; {len(id_fail)} Yahoo spell pieces "
              f"refused because their volume does not match FINRA's on the symbol's member days, their dates handed to the "
              f"successor chain ({sum(1 for x in refilled if any(x['refilled_from'].values()))} of {len(refilled)} symbols "
              f"re-priced that way; refused: " + (", ".join(f"{x['symbol']} via {x['yahoo']} {x['from']}..{x['to']}" for x in id_fail) or "none")
              + f"); "
              f"{len(book.name_overruled)} successors whose Yahoo longName disagrees with the index's kept for the volume "
              f"check to decide), so the return criteria need absent names (the absent "
              f"events would need a mean cost-adjusted abnormal return of {_bp(need)} for the 10-bps upper bound to fall below "
              f"0). Survivor subset (next open -> open 5 sessions later, minus SPY; cost-adjusted = abnormal + cost, which the "
              f"short must beat): mean gross {_bp(_mean(ar))}, cost-adjusted {_bp(stat['mean_ar_net'][list(T394_COSTS)[0]])} "
              f"(10 bps) / {_bp(stat['mean_ar_net'][list(T394_COSTS)[1]])} (20 bps), one-sided 95% upper bound (date clusters, "
              f"10 bps) {_bp((bd.get('ci90') or [None, None])[1])}; "
              f"halves net (10 bps) {_bp(stat['halves_net_10bp']['2019-2022'])} / {_bp(stat['halves_net_10bp']['2023-2026'])}; "
              f"Fama-MacBeth slope {_bp(fm.get('slope'), 2)} per unit z (NW t {_f(fm.get('t'), 2)}, {fm['n_days']} days; "
              f"secondary). PARK CONDITION ('daily SVR not informative'): "
              f"{'undecided' if park is None else park}. Criteria: " + "; ".join(f"{c[0]} -> {c[1]}" for c in j["criteria"])
              + " — " + j["why"])
    return _out(stat, j["n"], j["verdict"], reason)


# ===================================================================================================== maps ==

HARNESSES = {
    "b6c_events_dividend_month": b6c_events_dividend_month,
    "b6c_events_index_addition_reversal": b6c_events_index_addition_reversal,
    "b6c_events_short_volume_ratio": b6c_events_short_volume_ratio,
}

THEORY_MAP = {
    "T-374": "b6c_events_dividend_month",
    "T-334": "b6c_events_index_addition_reversal",
    "T-394": "b6c_events_short_volume_ratio",
}
