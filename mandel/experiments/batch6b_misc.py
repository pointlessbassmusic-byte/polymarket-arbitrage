"""
Batch 6b, group ``misc``: four options-library claims on newly archived data (box rates, OPEC dates) and on long daily
histories (SPY at VIX around US elections, SLV at trailing realised vol).
====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-188  daily changes in the SPX box-minus-bill spread vs daily changes in VIX: Pearson correlation > 0.2 with the
           95% CI excluding 0 (studentized block bootstrap, 5-day blocks), on the van Binsbergen-Diamond-Grotteria box
           rates (``box-rates-bdg``, 2004-01-02..2018-03-19) with FRED DTB3 and Cboe VIX.
  * T-518  MODEL-PRICED 1-day ATM USO straddle at OVX bought at the T-1 close: OPEC+ meeting days vs non-event days
           since 2009-09 (difference in mean P&L > 0 with the 95% CI excluding 0).
  * T-522  US federal election days since 1994: |SPY 2-day return| / (VIX/sqrt(126)) vs matched windows 4 weeks before
           and after (exact sign test p < 0.05, i.e. >= 13 of 16, and mean difference > 0); MODEL-PRICED straddle reported.
  * T-275  MODEL-PRICED 1x2 SLV call backspread (short 0.50 delta, long 2 x 0.25 delta, 90 DTE) at trailing 60-day
           realised vol, entered monthly 2006-2026 (mean P&L CI > 0 at RV and at RV + 5 vol points; the final verdict on
           captured IV cannot be given from two capture days).

Conventions
  * Data are loaded through ``archive.load``; a row is used only if its ``available_at`` is not after the bundle's capture
    time (``created_at``). Yahoo daily bars: ``close`` is split-adjusted, not dividend-adjusted (the raw close for option
    settlement up to splits, which scale strike and spot alike); SPY dividends are read from the adjclose/close steps.
  * Rates (rule 7): FRED DTB3 is a 91-day discount yield, converted to a continuous rate r = -ln(1 - d/100 * 91/360) /
    (91/365). A trading decision on day d uses the print dated strictly before d (FRED publishes a day late). T-188 is a
    contemporaneous correlation, not a decision, so it pairs each day's DTB3 with the same day's box rate and VIX.
  * Options (rule 8): Black-Scholes, settlement on the raw (split-adjusted) close of the expiry session, the escrowed
    dividend forward S - PV(D) when an ex-date falls inside the option's life (SPY only; USO, SLV and GLD pay none).
    Every model-priced result says MODEL-PRICED and reports IV-scale sensitivities.
  * Intervals (rule 6): two-sided 95% unless a pass says otherwise. T-188: studentized circular block bootstrap of the
    correlation (bootstrap-t with an influence-function Bartlett long-run s.e., 5-day blocks as the trial says; 20-day
    blocks reported). T-518: event-minus-non-event difference resampled PAIRED on the shared daily timeline (circular
    blocks of 21 sessions, percentile). T-522: exact binomial sign test (elections are two years apart) and an iid
    percentile bootstrap of the mean difference for the rule-5 check. T-275: circular block bootstrap of the per-cycle
    P&L (blocks of 6 and 12 monthly cycles, both >= the 3-cycle overlap of a 90-DTE position entered monthly); a CI
    criterion passes only when both block lengths pass, fails when both fail and is MARGINAL (None) when they disagree.
  * Calendars (rule 10): T-275 names monthly entries of 90-DTE options, so rule 10(a): the standard monthly expiry (third
    Friday, the prior session on a holiday) and an entry at the last session on or before 90 calendar days ahead of it
    (lives of 90-93 calendar days: a weekend or holiday steps the entry back, never forward). The pooled
    every-session entry (rule 10(b) estimator, blocks of 2 x the 63-session hold) is reported as robustness only. T-518
    and T-522 are event studies on named calendars (OPEC dates, election days with matched windows); T-188 is a daily series.
  * Below trial.min_n (rule 5) the verdict is never supported and a failing criterion counts only when it fails
    decisively (its bound at the pass's own confidence wholly on the wrong side, or the failure would persist at min_n).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
(None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.data.cboe_strategy import is_trading_day
from mandel.experiments.underlying2 import _verdict
from mandel.options import bs
from mandel.validation.backtest_eval import skewness

N_BOOT = 2000
SEED = 0
MP = "MODEL-PRICED"
NY = ZoneInfo("America/New_York")

BOX_B = "box-rates-bdg"
DTB3_B = "fred-DTB3"
VIX_B = "cboe-VIX-history"
FOMC_B = "fomc-meetings"
OPEC_B = "opec-announcements"
USO_B = "daily-history-USO"
OVX_B = "cboe-OVX-history"
SPY_B = "daily-history-SPY"
SLV_B = "daily-history-SLV"
GLD_B = "daily-history-GLD"
PM_MARKETS_B = "polymarket-closed-markets"
PM_PRICES_B = "polymarket-price-history-daily"
KALSHI_B = "kalshi-settled-markets"

# T-188
T188_MIN_N = 120
T188_THR = 0.2
T188_BLOCK = 5                 # the trial's 5-day blocks
# T-518
T518_MIN_N = 40
T518_START = "2009-09-01"      # "since 2009-09"
T518_BLOCK = 21
# T-522
T522_MIN_N = 16
T522_NEED = 13                 # ">= 13 of 16"
T522_FIRST = 1994
# T-275
T275_MIN_N = 100
T275_DTE = 90
T275_RV = 60
T275_VRP = 0.05                # "+ 5 vol points"
T275_BLOCKS = (6, 12)
T275_START = "2006-01-01"


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


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _daily(archive, name: str) -> tuple:
    """(days, close, adjclose) of a Yahoo daily-history bundle; a bar without adjclose carries the previous ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            try:
                c = float(v.get("close"))
            except (TypeError, ValueError):
                continue
            if not (c > 0 and math.isfinite(c)):
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            by[d] = (c, float(a) if a is not None and float(a) > 0 else float("nan"))
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, close, adj
    return _cached(archive, ("daily", name), load)


def _series(archive, name: str) -> dict:
    """{day: value} of a Cboe index (close) or FRED series (value) bundle; non-numeric prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = v.get("close", v.get("value"))
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("series", name), load)


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _f(x, nd=3, pct=False, sign=False) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    x = float(x) * (100 if pct else 1)
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s + ("%" if pct else "")


def _ci(c, nd=3, pct=False) -> str:
    if c is None:
        return "[n/a]"
    return f"[{_f(c[0], nd, pct, True)}, {_f(c[1], nd, pct, True)}]"


# ========================================================================================================= bills ==

def dtb3_cont(d_pct: float) -> float:
    """Continuous rate from a 91-day bill discount yield in percent (FRED DTB3), house rule 7."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


class Bills:
    """FRED DTB3 as a continuous rate known on a day: the print dated strictly before it (FRED publishes a day late)."""

    def __init__(self, dtb3: dict):
        self.k = sorted(dtb3)
        if not self.k:
            raise ValueError("no DTB3 prints")
        self.r = [dtb3_cont(float(dtb3[d])) for d in self.k]

    def rate(self, day: str) -> float:
        j = bisect.bisect_left(self.k, day) - 1
        return float(self.r[max(j, 0)])


# ==================================================================================================== bootstrap ==

def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    """k circular block-bootstrap index rows of length n."""
    block = max(1, min(int(block), n))
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def mean_ci(x, block: int, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> tuple:
    """Two-sided percentile circular block-bootstrap CI of the mean."""
    n_boot = _nb(n_boot)
    x = np.asarray(x, float)
    if x.size < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    m = np.empty(n_boot)
    for s in range(0, n_boot, 500):
        k = min(500, n_boot - s)
        m[s:s + k] = x[_boot_idx(rng, x.size, block, k)].mean(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def _nb(n_boot: Optional[int]) -> int:
    return N_BOOT if n_boot is None else int(n_boot)


def _agree(oks: list) -> Optional[bool]:
    """True when every variant passes, False when none does, None (MARGINAL) when they disagree."""
    oks = [bool(o) for o in oks]
    if not oks:
        return None
    return True if all(oks) else False if not any(oks) else None


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n (rule 5) a pass is not enough for supported and a failing criterion
    counts only when it fails decisively; otherwise it is reported as undecided (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


# ============================================================================================ T-188 box vs VIX ==

def _corr_parts(x: np.ndarray, y: np.ndarray, bw: int) -> tuple:
    """Pearson r along the last axis and its influence-function Bartlett long-run s.e. (bandwidth bw)."""
    n = x.shape[-1]
    xc = x - x.mean(axis=-1, keepdims=True)
    yc = y - y.mean(axis=-1, keepdims=True)
    sx = np.sqrt((xc * xc).mean(axis=-1, keepdims=True))
    sy = np.sqrt((yc * yc).mean(axis=-1, keepdims=True))
    with np.errstate(invalid="ignore", divide="ignore"):
        u, v = xc / sx, yc / sy
        r = (u * v).mean(axis=-1)
        inf = u * v - r[..., None] * (u * u + v * v) / 2.0
    z = inf - inf.mean(axis=-1, keepdims=True)
    lrv = (z * z).mean(axis=-1)
    for k in range(1, min(max(1, bw), n)):
        lrv = lrv + 2.0 * (1.0 - k / bw) * (z[..., k:] * z[..., :-k]).sum(axis=-1) / n
    se = np.sqrt(np.maximum(lrv, 0.0) / n)
    return r, se


def corr_test(x, y, block: int = T188_BLOCK, n_boot: Optional[int] = None, seed: int = SEED, level: float = 0.95) -> dict:
    """Pearson correlation of paired daily changes with a studentized (bootstrap-t) circular block-bootstrap CI and the
    percentile CI for reference."""
    n_boot = _nb(n_boot)
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = int(x.size)
    if n < 4 or np.std(x) == 0 or np.std(y) == 0:
        return {"r": None, "ci": None, "ci_pct": None, "se": None, "n": n, "block": block}
    r, se = _corr_parts(x, y, block)
    r, se = float(r), float(se)
    rng = np.random.default_rng(seed)
    tb, rb = [], []
    for s in range(0, n_boot, 250):
        k = min(250, n_boot - s)
        idx = _boot_idx(rng, n, block, k)
        rr, ss = _corr_parts(x[idx], y[idx], block)
        rb.append(rr)
        tb.append((rr - r) / ss)
    tb, rb = np.concatenate(tb), np.concatenate(rb)
    tb, rb = tb[np.isfinite(tb)], rb[np.isfinite(rb)]
    a = (1 - level) / 2
    lo = max(-1.0, r - float(np.quantile(tb, 1 - a)) * se)
    hi = min(1.0, r - float(np.quantile(tb, a)) * se)
    return {"r": r, "ci": [lo, hi], "ci_pct": [float(np.quantile(rb, a)), float(np.quantile(rb, 1 - a))], "se": se,
            "n": n, "block": block}


def box_panel(box: dict, dtb3: dict, vix: dict) -> dict:
    """Days on which the box rates (6m and 12m), the DTB3 print and the VIX close all exist, with the spreads in percent
    (continuously compounded, annualised): box 6m - bill, box 3m (linear extrapolation of 6m and 12m to 0.25 y) - bill,
    box 6m - the authors' 6m Treasury fit, box 12m - their 12m fit. Bill = DTB3 converted to a continuous rate."""
    days = sorted(d for d in box if d in dtb3 and d in vix
                  and box[d].get("box_6m") is not None and box[d].get("box_12m") is not None)
    g = lambda k: np.array([float(box[d][k]) if box[d].get(k) is not None else np.nan for d in days], float)
    b6, b12, g6, g12 = g("box_6m"), g("box_12m"), g("gov_6m"), g("gov_12m")
    bill = np.array([dtb3_cont(float(dtb3[d])) * 100.0 for d in days], float)
    spread = {"box6m-bill": b6 - bill, "box3m-bill": 1.5 * b6 - 0.5 * b12 - bill, "box6m-gov6m": b6 - g6,
              "box12m-gov12m": b12 - g12}
    return {"days": days, "vix": np.array([float(vix[d]) for d in days], float), "spread": spread, "bill": bill}


def judge_box_vix(tests: dict, n: int, min_n: int = T188_MIN_N, thr: float = T188_THR,
                  maturity_observed: bool = False) -> tuple:
    """T-188 criteria on the decision variants ``tests`` (name -> corr_test): point correlation > thr and the 95% CI
    excluding 0 (lower bound > 0, the claimed direction), each decided only when every variant agrees; plus the claim's
    60-120 DTE mid-price box series, which is None unless ``maturity_observed``."""
    ts = [t for t in tests.values() if t.get("r") is not None]
    if not ts:
        crit = [("correlation computable", None, False)]
    else:
        names = "/".join(tests)
        c1 = _agree([t["r"] > thr for t in ts])
        d1 = all(t["ci"][1] < thr for t in ts)
        c2 = _agree([t["ci"][0] > 0 for t in ts])
        d2 = all(t["ci"][1] < 0 for t in ts)
        crit = [(f"correlation > {thr} ({names}: " + ", ".join(_f(t["r"]) for t in ts) + ")", c1, d1),
                (f"95% CI excludes 0 on the positive side ({names}: lower " + ", ".join(_f(t["ci"][0]) for t in ts) + ")",
                 c2, d2)]
    crit.append(("box rate at the claim's 60-120 DTE from mid prices"
                 + ("" if maturity_observed else " (box-rates-bdg has 6/12/18-month constant maturities only)"),
                 True if maturity_observed else None, False))
    return _decide(crit, n, min_n, "daily changes")


def box_vix_claim(P: dict, fomc_days: Optional[set] = None, n_boot: Optional[int] = None) -> dict:
    """T-188 on a box_panel: correlation of daily spread changes with daily VIX changes."""
    n_boot = _nb(n_boot)
    days = P["days"]
    if len(days) < 3:
        v, why = _verdict([("box, DTB3 and VIX overlap", None)])
        return {"stat": {"n": 0}, "n": 0, "verdict": v,
                "reason": f"T-188: fewer than 3 common days of box rates, DTB3 and VIX — {why}"}
    end = days[1:]
    dv = np.diff(P["vix"])
    ds = {k: np.diff(v) for k, v in P["spread"].items()}
    dec = ("box6m-bill", "box3m-bill")
    tests = {k: corr_test(ds[k], dv, T188_BLOCK, n_boot) for k in dec}
    n = int(tests["box6m-bill"]["n"])
    verdict, why = judge_box_vix(tests, n)
    rep = {k: corr_test(ds[k], dv, T188_BLOCK, n_boot) for k in ("box6m-gov6m", "box12m-gov12m")}
    b20 = {k: corr_test(ds[k], dv, 20, n_boot) for k in dec}
    nofomc = None
    if fomc_days:
        keep = np.array([d not in fomc_days for d in end])
        nofomc = {k: corr_test(ds[k][keep], dv[keep], T188_BLOCK, n_boot) for k in dec}
        nofomc["dropped"] = int((~keep).sum())
    sub = {}
    for lab, a, b in (("2004-2007", "2004", "2008"), ("2008-2009", "2008", "2010"), ("2010-2018", "2010", "2019")):
        m = np.array([a <= d < b for d in end])
        if m.sum() >= 10:
            sub[lab] = {k: corr_test(ds[k][m], dv[m], T188_BLOCK, min(n_boot, 500)) for k in dec}
    lvl = {k: {"mean_bp": float(np.nanmean(v) * 100), "sd_bp": float(np.nanstd(v) * 100)} for k, v in P["spread"].items()}
    stat = {"tests": tests, "reported": rep, "blocks20": b20, "no_fomc": nofomc, "subperiods": sub, "spread_level": lvl,
            "first": days[0], "last": days[-1], "n_days": len(days), "n": n, "min_n": T188_MIN_N}

    def rr(t):
        return f"r {_f(t['r'])} {_ci(t['ci'])}" if t and t.get("r") is not None else "n/a"
    reason = (
        f"T-188 daily changes {end[0]}..{end[-1]}, n = {n} changes on the days box rates, DTB3 and VIX all print. Box "
        f"rates: van Binsbergen-Diamond-Grotteria SPX box-implied rates (box-rates-bdg; a research series published "
        f"2021-11-23, available_at that date for every row, so no trader saw it in real time; the claim is a "
        f"contemporaneous correlation with no trading decision, so rule 4 does not restrict it) at 6/12/18-month constant "
        f"maturities: the claim's 60-120 DTE box is not in the data, so the correlation is decided on two stand-ins that "
        f"must agree: box 6m (the shortest observed) and box 3m linearly extrapolated from 6m and 12m (= 1.5 box6m - 0.5 "
        f"box12m), each minus the 3-month bill (FRED DTB3, a discount yield, as the continuous rate of rule 7; DGS3MO, "
        f"which the trial names, is not archived), same-day prints. Correlation of d(spread) with d(VIX), studentized "
        f"circular block bootstrap with the trial's 5-day blocks, two-sided 95%: box6m-bill {rr(tests['box6m-bill'])}; "
        f"box3m-bill {rr(tests['box3m-bill'])} (criterion: point > {T188_THR} and lower > 0 on both). Reported: "
        f"maturity-matched box6m - gov6m {rr(rep['box6m-gov6m'])}, box12m - gov12m {rr(rep['box12m-gov12m'])}; 20-day "
        f"blocks: {rr(b20['box6m-bill'])} / {rr(b20['box3m-bill'])}")
    if nofomc:
        reason += (f"; dropping the {nofomc['dropped']} changes ending on FOMC decision days: {rr(nofomc['box6m-bill'])} / "
                   f"{rr(nofomc['box3m-bill'])}")
    if sub:
        reason += "; sub-periods (box6m-bill / box3m-bill): " + ", ".join(
            f"{lab} {_f(v['box6m-bill']['r'], 2)} / {_f(v['box3m-bill']['r'], 2)}" for lab, v in sub.items())
    reason += ("; mean spread level (reported separately, bp): " + ", ".join(
        f"{k} {_f(v['mean_bp'], 1)} (sd {_f(v['sd_bp'], 1)})" for k, v in lvl.items()))
    reason += f" — {why}"
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason}


def b6b_misc_box_bill_vix_corr(archive):
    """T-188: SPX box-minus-bill spread daily changes vs VIX daily changes, correlation > 0.2 with the 95% CI > 0."""
    miss = _missing(archive, [BOX_B, DTB3_B, VIX_B])
    if miss:
        return miss
    box = {}
    for r in _rows(archive, BOX_B):
        v = r["value"]
        if v.get("day"):
            box[v["day"]] = v
    P = box_panel(box, _series(archive, DTB3_B), _series(archive, VIX_B))
    fomc = None
    if _has(archive, FOMC_B):
        fomc = {r["value"].get("decision_day") for r in _rows(archive, FOMC_B) if r["value"].get("decision_day")}
    return _out(box_vix_claim(P, fomc))


def _out(rep: dict):
    return _clean(rep["stat"]), int(rep["n"]), rep["verdict"], rep["reason"]


# ===================================================================================== T-518 OPEC USO straddle ==

def straddle_atm(S0, S1, sig, T: float, r, fwd=None) -> tuple:
    """MODEL-PRICED long ATM straddle (K = S0) bought at Black-Scholes(sig, T, r) on the spot (or on the escrowed forward
    spot ``fwd``) and settled at S1. Returns (P&L / S0, premium / S0) with the premium carried at r to expiry."""
    S0, S1 = np.asarray(S0, float), np.asarray(S1, float)
    sig, r = np.asarray(sig, float), np.asarray(r, float)
    Sp = S0 if fwd is None else np.asarray(fwd, float)
    prem = bs.price(Sp, S0, T, r, sig, "call") + bs.price(Sp, S0, T, r, sig, "put")
    pnl = np.abs(S1 - S0) - prem * np.exp(r * T)
    return pnl / S0, prem / S0


def event_diff_test(pnl, ev, other, block: int = T518_BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Mean P&L on event days minus mean on ``other`` days, with a two-sided 95% percentile CI from a circular block
    bootstrap of the shared daily timeline (both groups resampled together, so the difference is paired in time)."""
    n_boot = _nb(n_boot)
    pnl, ev, other = np.asarray(pnl, float), np.asarray(ev, bool), np.asarray(other, bool)
    keep = ev | other
    x, e = pnl[keep], ev[keep]
    ne, no = int(e.sum()), int((~e).sum())
    if ne == 0 or no == 0:
        return {"diff": None, "ci": None, "n_event": ne, "n_other": no, "mean_event": None, "mean_other": None}
    me, mo = float(x[e].mean()), float(x[~e].mean())
    rng = np.random.default_rng(seed)
    out = []
    for s in range(0, n_boot, 250):
        k = min(250, n_boot - s)
        idx = _boot_idx(rng, x.size, block, k)
        X, E = x[idx], e[idx]
        se, so = E.sum(axis=1), (~E).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append((X * E).sum(axis=1) / se - (X * ~E).sum(axis=1) / so)
    d = np.concatenate(out)
    d = d[np.isfinite(d)]
    ci = [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))] if d.size else None
    return {"diff": me - mo, "ci": ci, "n_event": ne, "n_other": no, "mean_event": me, "mean_other": mo,
            "block": block}


def judge_event_diff(test: Optional[dict], n_events: int, pit_known: Optional[bool], min_n: int = T518_MIN_N) -> tuple:
    """T-518 criteria: event flags known at the T-1 close (None when no event date is verifiably known in advance);
    event-minus-non-event mean P&L > 0 with the 95% CI excluding 0, on the point-in-time events."""
    crit = [("OPEC event dates known at the T-1 close (verified advance notice)", pit_known, False)]
    if not test or test.get("diff") is None or test.get("ci") is None:
        crit.append(("event-minus-non-event mean P&L > 0 with the 95% CI excluding 0 (no point-in-time events)", None,
                     False))
    else:
        lo, hi = test["ci"]
        crit.append((f"event-minus-non-event mean P&L > 0 with the 95% CI excluding 0 ({_f(test['diff'], 3, True, True)} "
                     f"{_ci(test['ci'], 3, True)} of S)", bool(test["diff"] > 0 and lo > 0), bool(hi < 0)))
    return _decide(crit, n_events, min_n, "point-in-time events")


def _month_end(vintage: str) -> Optional[str]:
    """'2025M12' -> '2025-12-31' (the last day a research vintage covers)."""
    try:
        y, m = int(vintage[:4]), int(vintage[5:7])
    except (TypeError, ValueError):
        return None
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).isoformat()


def close_time_utc(day: str) -> datetime:
    """16:00 New York on ``day`` in UTC (the equity / ETF-option close)."""
    d = date.fromisoformat(day)
    return datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY).astimezone(timezone.utc)


def _parse_ts(s: str) -> datetime:
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def opec_events(rows: list, days: list) -> list:
    """Event rows mapped to the trading session they fall on: the announcement day, a weekend's next Monday
    (``effective_weekday``), and an exchange holiday's next session in ``days``. Several announcements mapping to one
    session give one event (known in advance only when one of them is)."""
    by = {}
    for r in rows:
        if r.get("kind") != "opec-announcement":
            continue
        v = r["value"]
        eff = v.get("effective_weekday") or v.get("day")
        j = bisect.bisect_left(days, eff)
        if j >= len(days) or j == 0:
            continue
        T = days[j]
        e = by.setdefault(T, {"session": T, "prev": days[j - 1], "days": [], "available_at": None, "known_since": None})
        e["days"].append(v.get("day"))
        av = _parse_ts(r["available_at"])
        if e["available_at"] is None or av < e["available_at"]:
            e["available_at"] = av
            e["known_since"] = v.get("known_since")
    out = []
    for T in sorted(by):
        e = by[T]
        e["pit"] = bool(e["available_at"] <= close_time_utc(e["prev"]))
        out.append(e)
    return out


def cl_last_trade(y: int, m: int) -> date:
    """NYMEX WTI (CL) contract month (y, m): trading ends 3 business days before the 25th calendar day of the prior month
    (counting from the business day before the 25th when the 25th is not a business day). Exchange holidays are the US
    equity calendar's (an approximation)."""
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    d = date(py, pm, 25)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    k = 0
    while k < 3:
        d -= timedelta(days=1)
        if is_trading_day(d):
            k += 1
    return d


def uso_roll_days(first: str, last: str) -> set:
    """APPROXIMATE USO roll sessions: the four sessions starting about two weeks (the first session on or after 14
    calendar days) before each front CL contract's last trade (the prospectus rule before 2020-04; USO has held a mix of
    months since, so the set is a guide, not its actual roll calendar)."""
    out = set()
    y, m = int(first[:4]), int(first[5:7])
    end = date.fromisoformat(last)
    while date(y, m, 1) <= end + timedelta(days=62):
        lt = cl_last_trade(y, m)
        d, k = lt - timedelta(days=14), 0
        while k < 4:
            if is_trading_day(d):
                out.add(d.isoformat())
                k += 1
            d += timedelta(days=1)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def uso_panel(days: list, close: np.ndarray, ovx: dict, bills: Bills, start: str, end: str, scale: float = 1.0,
              divs: Optional[dict] = None) -> dict:
    """One MODEL-PRICED 1-day ATM USO straddle per session T in [start, end]: bought at the T-1 close at sigma = OVX/100 x
    scale (the T-1 OVX close, or the last print within 5 days), T = 1/252, r = DTB3 known at T-1; settled at T's close."""
    ovd = sorted(ovx)
    out = {"day": [], "prev": [], "S0": [], "S1": [], "sig": [], "r": [], "fwd": []}
    for i in range(1, len(days)):
        T, P = days[i], days[i - 1]
        if T < start or T > end:
            continue
        j = bisect.bisect_right(ovd, P) - 1
        if j < 0 or (date.fromisoformat(P) - date.fromisoformat(ovd[j])).days > 5:
            continue
        out["day"].append(T); out["prev"].append(P)
        out["S0"].append(close[i - 1]); out["S1"].append(close[i])
        r = bills.rate(P)
        D = (divs or {}).get(T, 0.0)                    # an ex-date inside the 1-day life: escrowed-dividend spot
        out["sig"].append(ovx[ovd[j]] / 100.0 * scale); out["r"].append(r)
        out["fwd"].append(close[i - 1] - D * math.exp(-r / 252))
    for k in ("S0", "S1", "sig", "r", "fwd"):
        out[k] = np.array(out[k], float)
    if out["day"]:
        out["pnl"], out["prem"] = straddle_atm(out["S0"], out["S1"], out["sig"], 1 / 252, out["r"], out["fwd"])
    else:
        out["pnl"], out["prem"] = np.array([]), np.array([])
    return out


def opec_claim(U: dict, events: list, roll: set, variants: dict, n_boot: Optional[int] = None, n_div: int = 0) -> dict:
    """T-518 on a uso_panel and its mapped OPEC events. ``variants``: IV-scale panels (same days) for the sensitivity."""
    n_boot = _nb(n_boot)
    day = U["day"]
    if not day:
        v, why = _verdict([("USO / OVX / DTB3 overlap since 2009-09", None)])
        return {"stat": {"n": 0}, "n": 0, "verdict": v, "reason": f"T-518: no USO session with an OVX print since "
                                                                   f"{T518_START} — {why}"}
    pos = {d: i for i, d in enumerate(day)}
    ev_all = np.zeros(len(day), bool)
    ev_pit = np.zeros(len(day), bool)
    used = [e for e in events if e["session"] in pos]
    for e in used:
        ev_all[pos[e["session"]]] = True
        ev_pit[pos[e["session"]]] = e["pit"]
    n_exp, n_pit = int(ev_all.sum()), int(ev_pit.sum())
    other = ~ev_all
    pnl = U["pnl"]
    pit_test = event_diff_test(pnl, ev_pit, other, T518_BLOCK, n_boot) if n_pit else None
    verdict, why = judge_event_diff(pit_test, n_pit, True if n_pit else None)
    # ex-post diagnostics (look-ahead: event dates known only after the fact), never criteria
    xp = event_diff_test(pnl, ev_all, other, T518_BLOCK, n_boot)
    m2020 = np.array([not d.startswith(("2020-03", "2020-04")) for d in day])
    xp_ex2020 = event_diff_test(pnl, ev_all & m2020, other & m2020, T518_BLOCK, n_boot)
    mroll = np.array([d not in roll for d in day])
    xp_roll = event_diff_test(pnl, ev_all & mroll, other & mroll, T518_BLOCK, n_boot)
    xp63 = event_diff_test(pnl, ev_all, other, 63, n_boot)
    scales = {k: event_diff_test(V["pnl"], ev_all, other, T518_BLOCK, n_boot) for k, V in variants.items()
              if len(V["day"]) == len(day)}
    wed = np.array([date.fromisoformat(d).weekday() == 2 for d in day])
    eia = event_diff_test(pnl, wed & other, ~wed & other, T518_BLOCK, n_boot)
    move = np.abs(U["S1"] / U["S0"] - 1)
    ratio_ev = float(np.mean(move[ev_all] / U["prem"][ev_all])) if n_exp else None
    ratio_ot = float(np.mean(move[other] / U["prem"][other])) if other.any() else None
    stat = {"label": MP, "n_events_pit": n_pit, "n_events_expost": n_exp, "n_sessions": len(day), "first": day[0],
            "last": day[-1], "pit_test": pit_test, "expost": xp, "expost_ex_2020_03_04": xp_ex2020,
            "expost_ex_roll_approx": xp_roll, "expost_block63": xp63, "expost_iv_scale": scales, "eia_wednesdays": eia,
            "move_over_premium": {"event": ratio_ev, "other": ratio_ot},
            "event_sessions": [e["session"] for e in used], "n": n_pit, "min_n": T518_MIN_N}

    def dd(t):
        if not t or t.get("diff") is None:
            return "n/a"
        return (f"{_f(t['diff'], 3, True, True)} {_ci(t['ci'], 3, True)} (event {_f(t['mean_event'], 3, True, True)}, n "
                f"{t['n_event']}; other {_f(t['mean_other'], 3, True, True)}, n {t['n_other']})")
    reason = (
        f"T-518 {MP}: 1-day ATM USO straddle bought at the T-1 close at Black-Scholes with sigma = OVX(T-1)/100, T = "
        f"1/252, r = DTB3 (rule 7, print before T-1), K = S(T-1), settled at T's raw (split-adjusted) close, P&L in % of "
        f"S(T-1); USO ex-dividend dates in the data: {n_div} (escrowed forward when one falls on T); sessions "
        f"{day[0]}..{day[-1]} (OVX starts 2009-09-18; the Kanzig vintage covers OPEC dates to its month-end). OPEC dates: "
        f"opec-announcements (Kanzig 2021), {len(used)} event sessions in the window (weekend dates on the next Monday). "
        f"POINT IN TIME: an event row is available at the END of its announcement day unless a verified known_since "
        f"says the date was announced earlier; {n_pit} of {n_exp} event sessions have a flag available by the T-1 close "
        f"(16:00 New York)")
    if n_pit == 0:
        reason += (", so the event flag is not known in advance and the claim's T-1-close entry is not implementable "
                   "point in time (the claim fixes the entry at the T-1 close, so there is no day-after reading to "
                   "fall back on); both criteria are undecided")
    else:
        reason += f"; point-in-time difference {dd(pit_test)}"
    reason += (
        f". Ex-post diagnostics (LOOK-AHEAD: event dates known only after the fact; reported, never criteria): "
        f"event - non-event {dd(xp)} (21-session blocks; 63-session blocks CI {_ci(xp63.get('ci'), 3, True)}); excluding "
        f"2020-03/04 {_f(xp_ex2020.get('diff'), 3, True, True)} {_ci(xp_ex2020.get('ci'), 3, True)}; excluding the "
        f"APPROXIMATE USO roll sessions {_f(xp_roll.get('diff'), 3, True, True)} {_ci(xp_roll.get('ci'), 3, True)}; "
        f"IV-scale sensitivity " + ", ".join(f"{k} {_f(t.get('diff'), 3, True, True)} {_ci(t.get('ci'), 3, True)}"
                                             for k, t in scales.items())
        + f"; mean |move| / premium: events {_f(ratio_ev, 2)}, other days {_f(ratio_ot, 2)}; EIA Wednesdays (second "
        f"event set; Tuesday-close entry, holiday-week shifts not modelled) minus other non-OPEC days "
        f"{_f(eia.get('diff'), 3, True, True)} {_ci(eia.get('ci'), 3, True)}. n = {n_pit} point-in-time events "
        f"(min_n {T518_MIN_N})")
    reason += f" — {why}"
    return {"stat": stat, "n": n_pit, "verdict": verdict, "reason": reason}


def b6b_misc_opec_uso_straddle(archive):
    """T-518: MODEL-PRICED 1-day USO straddle at OVX on OPEC+ meeting days vs non-event days, since 2009-09."""
    miss = _missing(archive, [OPEC_B, USO_B, OVX_B, DTB3_B])
    if miss:
        return miss
    days, close, adj = _daily(archive, USO_B)
    divs = _divs(days, close, adj)
    ovx = _series(archive, OVX_B)
    bills = Bills(_series(archive, DTB3_B))
    orows = _rows(archive, OPEC_B)
    vint = sorted({r["value"].get("vintage") for r in orows if r.get("kind") == "opec-announcement"
                   and r["value"].get("vintage")})
    cover = _month_end(vint[-1]) if vint else None
    end = min(cover, days[-1]) if (cover and days) else (days[-1] if days else "0000-01-01")
    start = T518_START                       # a session counts once its T-1 close has an OVX print (OVX from 2009-09-18)
    U = uso_panel(days, close, ovx, bills, start, end, divs=divs)
    events = opec_events(orows, days)
    variants = {f"IV x{s}": uso_panel(days, close, ovx, bills, start, end, s, divs=divs) for s in (0.9, 1.1)}
    roll = uso_roll_days(start, end) if U["day"] else set()
    rep = opec_claim(U, events, roll, variants, n_div=len(divs))
    if cover:
        rep["stat"]["coverage_end"] = cover
    return _out(rep)


# ============================================================================== T-522 election-day SPY move ==

def election_day(year: int) -> date:
    """US federal election day: the Tuesday after the first Monday of November (2 U.S.C. 7)."""
    d = date(year, 11, 1)
    first_monday = d + timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + timedelta(days=1)


def election_days(first: int, last_day: str) -> list:
    out, y = [], first + (first % 2)
    while election_day(y).isoformat() <= last_day:
        out.append(election_day(y))
        y += 2
    return out


def _divs(days: list, close: np.ndarray, adj: np.ndarray) -> dict:
    """{ex-day: cash dividend} from the adjclose/close steps (D = C(t-1) (1 - f(t-1)/f(t)))."""
    f = adj / close
    out = {}
    for i in range(1, len(days)):
        if f[i] > 0 and f[i - 1] / f[i] < 1 - 1e-6:
            out[days[i]] = float(close[i - 1] * (1 - f[i - 1] / f[i]))
    return out


def two_day_window(pos: dict, days: list, close: np.ndarray, vix: dict, tuesday: date, bills: Optional[Bills] = None,
                   divs: Optional[dict] = None, scales: Sequence[float] = (1.0,)) -> Optional[dict]:
    """|S(after)/S(before) - 1| / (VIX(before)/100/sqrt(126)) for the 2-session window around ``tuesday`` (the close
    before it to the close after it); None when the Tuesday is not a session or a close/VIX print is missing. With
    ``bills`` also the MODEL-PRICED 2-day ATM straddle bought at the before-close (sigma = VIX x scale, T = 2/252)."""
    t = tuesday.isoformat()
    i = pos.get(t)
    if i is None or i < 1 or i + 1 >= len(days):
        return None
    a, b = i - 1, i + 1
    v = vix.get(days[a])
    if v is None or not v > 0:
        return None
    S0, S1 = float(close[a]), float(close[b])
    R = S1 / S0 - 1
    imp = v / 100.0 / math.sqrt(126.0)
    out = {"tuesday": t, "before": days[a], "after": days[b], "ret": R, "vix": v, "implied": imp, "ratio": abs(R) / imp}
    if bills is not None:
        r = bills.rate(days[a])
        T = 2 / 252
        D = sum(x for d, x in (divs or {}).items() if days[a] < d <= days[b])
        fwd = S0 - D * math.exp(-r * T) if D else None
        out["div_in_window"] = D
        for s in scales:
            p, _ = straddle_atm(np.array([S0]), np.array([S1]), np.array([v / 100.0 * s]), T, np.array([r]),
                                None if fwd is None else np.array([fwd]))
            out[f"straddle_x{s}"] = float(p[0])
    return out


def sign_test(k: int, n: int) -> tuple:
    """Exact binomial sign test: (one-sided P(X >= k), two-sided p) under p = 1/2."""
    if n <= 0:
        return 1.0, 1.0
    tail = lambda j: sum(math.comb(n, i) for i in range(j, n + 1)) / 2 ** n
    one = tail(k)
    two = min(1.0, 2 * tail(max(k, n - k)))
    return float(one), float(two)


def judge_election(diffs, min_n: int = T522_MIN_N, need: int = T522_NEED, n_boot: Optional[int] = None, seed: int = SEED) -> tuple:
    """T-522 criteria on the per-election differences (election ratio minus matched-window ratio): exact sign test p <
    0.05 with >= ``need`` of ``min_n`` positive, and mean difference > 0. Returns (verdict, why, details)."""
    n_boot = _nb(n_boot)
    d = np.asarray(diffs, float)
    d = d[np.isfinite(d)]
    n, k = int(d.size), int((d > 0).sum())
    p1, p2 = sign_test(k, n)
    mean = float(d.mean()) if n else float("nan")
    ci = None
    if n >= 2:
        rng = np.random.default_rng(seed)
        bm = d[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
        ci = [float(np.quantile(bm, 0.025)), float(np.quantile(bm, 0.975))]
    c1 = bool(k >= need and p2 < 0.05)
    dec1 = k + max(0, min_n - n) < need
    c2 = bool(n > 0 and mean > 0)
    dec2 = bool(ci is not None and ci[1] < 0)
    crit = [(f"exact sign test p < 0.05 with >= {need} of {min_n} elections positive ({k} of {n}, two-sided p "
             f"{_f(p2, 4)})", c1, dec1),
            (f"mean ratio difference > 0 ({_f(mean, 3, False, True)})", c2, dec2)]
    v, why = _decide(crit, n, min_n, "elections")
    return v, why, {"n": n, "positive": k, "p_one_sided": p1, "p_two_sided": p2, "mean_diff": mean, "mean_ci": ci}


def election_table(days: list, close: np.ndarray, adj: np.ndarray, vix: dict, bills: Bills, elections: list) -> list:
    pos = {d: i for i, d in enumerate(days)}
    divs = _divs(days, close, adj)
    out = []
    for E in elections:
        kw = dict(bills=bills, divs=divs, scales=(1.0, 0.9, 1.1))
        e = two_day_window(pos, days, close, vix, E, **kw)
        bef = two_day_window(pos, days, close, vix, E - timedelta(days=28), **kw)
        aft = two_day_window(pos, days, close, vix, E + timedelta(days=28), **kw)
        row = {"year": E.year, "kind": "presidential" if E.year % 4 == 0 else "midterm", "election": E.isoformat(),
               "event": e, "before": bef, "after": aft}
        m = [w for w in (bef, aft) if w]
        if e and m:
            row["matched_ratio"] = float(np.mean([w["ratio"] for w in m]))
            row["diff"] = e["ratio"] - row["matched_ratio"]
            row["n_matched"] = len(m)
            for s in (1.0, 0.9, 1.1):
                row[f"straddle_diff_x{s}"] = e[f"straddle_x{s}"] - float(np.mean([w[f"straddle_x{s}"] for w in m]))
        out.append(row)
    return out


def _odds_2024(archive) -> Optional[dict]:
    """Polymarket prices of the 2024 US presidential winner markets at the last daily print before the 2024-11-04 close
    (reported context only: odds exist for one election)."""
    if not (_has(archive, PM_MARKETS_B) and _has(archive, PM_PRICES_B)):
        return None
    ids = {}
    for r in _rows(archive, PM_MARKETS_B):
        q = str(r["value"].get("question") or "")
        if "win the 2024 US Presidential Election" in q:
            ids[str(r["value"].get("id"))] = q
    if not ids:
        return {"markets": 0}
    cut = close_time_utc("2024-11-04").timestamp()
    last = {}
    for r in _rows(archive, PM_PRICES_B):
        v = r["value"]
        mid = str(v.get("market_id"))
        if mid in ids and v.get("t") is not None and float(v["t"]) <= cut:
            if mid not in last or float(v["t"]) > last[mid][0]:
                last[mid] = (float(v["t"]), float(v.get("p")))
    prices = {ids[m]: p for m, (t, p) in last.items() if p >= 0.02}
    return {"markets": len(ids), "prices": prices}


def election_claim(rows: list, odds: Optional[dict] = None, kalshi_rows: Optional[int] = None, n_boot: Optional[int] = None) -> dict:
    use = [r for r in rows if r.get("diff") is not None]
    diffs = np.array([r["diff"] for r in use], float)
    verdict, why, det = judge_election(diffs, n_boot=n_boot)
    n = det["n"]

    def sub(sel):
        dd = np.array([r["diff"] for r in use if sel(r)], float)
        k = int((dd > 0).sum())
        return {"n": int(dd.size), "positive": k, "p_two_sided": sign_test(k, int(dd.size))[1],
                "mean_diff": float(dd.mean()) if dd.size else None}
    med = float(np.median([r["event"]["vix"] for r in use])) if use else float("nan")
    controls = {"presidential": sub(lambda r: r["kind"] == "presidential"), "midterm": sub(lambda r: r["kind"] == "midterm"),
                f"VIX above {med:.1f}": sub(lambda r: r["event"]["vix"] > med),
                f"VIX at or below {med:.1f}": sub(lambda r: r["event"]["vix"] <= med),
                "excluding 2008": sub(lambda r: r["year"] != 2008)}
    strad = {}
    for s in (1.0, 0.9, 1.1):
        ev = [r["event"][f"straddle_x{s}"] for r in use]
        df = [r[f"straddle_diff_x{s}"] for r in use]
        strad[f"x{s}"] = {"election_mean": float(np.mean(ev)) if ev else None, "diff_mean": float(np.mean(df)) if df else None}
    stat = {"label": MP, "elections": rows, "n": n, "min_n": T522_MIN_N, **det, "controls": controls, "straddle": strad,
            "odds_2024": odds, "kalshi_election_rows": kalshi_rows}
    tested = [r["election"] for r in use]
    skipped = [r["election"] for r in rows if r.get("diff") is None]
    reason = (
        f"T-522 elections {tested[0] if tested else 'n/a'}..{tested[-1] if tested else 'n/a'} (federal election day = the "
        f"Tuesday after the first Monday of November, fixed by law, so known in advance), n = {n} of {T522_MIN_N}"
        + (f" (no data: {skipped})" if skipped else "")
        + f". Ratio = |SPY close-after / close-before - 1| / (VIX at the close before / 100 / sqrt(126)), SPY raw closes; "
        f"matched windows = the same Monday-to-Wednesday windows 4 weeks before and after (their mean). Election ratio "
        f"minus matched ratio positive in {det['positive']} of {n} (exact sign test two-sided p {_f(det['p_two_sided'], 4)}, "
        f"one-sided {_f(det['p_one_sided'], 4)}; pass needs >= {T522_NEED} of {T522_MIN_N}); mean difference "
        f"{_f(det['mean_diff'], 3, False, True)} (iid bootstrap 95% CI {_ci(det['mean_ci'])}); underpowered by design: "
        f"indicative only. {MP} 2-day ATM SPY straddle at VIX (T = 2/252, DTB3 known at entry, raw-close settlement, "
        f"dividend forward if an ex-date falls in the window): mean P&L on election windows "
        f"{_f(strad['x1.0']['election_mean'], 3, True, True)} of S, election minus matched "
        f"{_f(strad['x1.0']['diff_mean'], 3, True, True)}; IV x0.9 {_f(strad['x0.9']['diff_mean'], 3, True, True)}, IV x1.1 "
        f"{_f(strad['x1.1']['diff_mean'], 3, True, True)}. Controls (reported): " + "; ".join(
            f"{k} {v['positive']}/{v['n']} positive, mean {_f(v['mean_diff'], 3, False, True)}" for k, v in controls.items()))
    if odds and odds.get("prices"):
        reason += ("; Polymarket (2024 only, one election, so no odds covariate can be estimated): last daily price before "
                   "the 2024-11-04 close " + ", ".join(f"'{q}' {p:.2f}" for q, p in odds["prices"].items()))
    elif odds is not None:
        reason += "; Polymarket: no 2024 presidential winner prices before the 2024-11-04 close in the archive"
    else:
        reason += "; Polymarket odds bundles not archived (the odds part is 2024+ only and not a criterion)"
    if kalshi_rows is not None:
        reason += f"; Kalshi: {kalshi_rows} election markets in the archived settled-markets sample"
    reason += f" — {why}"
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason}


def b6b_misc_election_spy_move(archive):
    """T-522: SPY 2-day |return| / VIX-implied move on US federal election days since 1994 vs matched windows."""
    miss = _missing(archive, [SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    days, close, adj = _daily(archive, SPY_B)
    vix = _series(archive, VIX_B)
    bills = Bills(_series(archive, DTB3_B))
    if not days:
        v, why = _verdict([("SPY closes", None)])
        return {"n": 0}, 0, v, f"T-522: no SPY closes — {why}"
    # an election is in the sample once the close after it AND the matched window 4 weeks later have printed
    last = (date.fromisoformat(days[-1]) - timedelta(days=30)).isoformat()
    els = election_days(T522_FIRST, last)
    rows = election_table(days, close, adj, vix, bills, els)
    odds = _odds_2024(archive)
    kal = None
    if _has(archive, KALSHI_B):
        kal = sum(1 for r in _rows(archive, KALSHI_B)
                  if any(s in str(r["value"].get("event_ticker", "")).upper() for s in ("PRES", "ELECT", "HOUSE", "SENATE")))
    return _out(election_claim(rows, odds, kal))


# ============================================================================== T-275 SLV call backspread ==

def monthly_expiries(days: list) -> list:
    """Session index of each standard monthly expiry: the third Friday, or the prior session when it is a holiday."""
    if not days:
        return []
    out, y, m = [], int(days[0][:4]), int(days[0][5:7])
    last = date.fromisoformat(days[-1])
    while date(y, m, 1) <= last:
        d = date(y, m, 1)
        tf = d + timedelta(days=(4 - d.weekday()) % 7 + 14)
        if tf <= last:
            j = bisect.bisect_right(days, tf.isoformat()) - 1
            if j >= 0 and (tf - date.fromisoformat(days[j])).days <= 3:
                out.append(j)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def trailing_rv(close: np.ndarray, window: int = T275_RV, ppy: int = 252) -> np.ndarray:
    """Annualised realised vol of the ``window`` daily log returns ending at each close (sum of squares, no mean removed),
    known at that close; nan before the window fills."""
    c = np.asarray(close, float)
    lr = np.full(c.size, np.nan)
    lr[1:] = np.log(c[1:] / c[:-1])
    out = np.full(c.size, np.nan)
    if c.size > window:
        sq = np.concatenate([[0.0], np.cumsum(np.nan_to_num(lr[1:]) ** 2)])     # sq[k] = sum of lr[1..k]^2
        for i in range(window, c.size):
            out[i] = math.sqrt(ppy / window * (sq[i] - sq[i - window]))
    return out


def dte_cycles(days: list, rv: np.ndarray, expiries: list, dte: int = T275_DTE, start: str = T275_START) -> tuple:
    """(entries, expiries): for each monthly expiry the last session on or before ``dte`` calendar days ahead of it with a
    realised vol (stepping back at most 3 sessions)."""
    cal = np.array([date.fromisoformat(d).toordinal() for d in days])
    ents, exps = [], []
    for x in expiries:
        j = int(np.searchsorted(cal, cal[x] - dte, side="right")) - 1
        for _ in range(4):
            if j < 0 or np.isfinite(rv[j]):
                break
            j -= 1
        if j >= 0 and np.isfinite(rv[j]) and days[j] >= start and j < x:
            ents.append(j); exps.append(int(x))
    return ents, exps


def backspread(S0, ST, T, r, sig, d_short: float = 0.50, d_long: float = 0.25, ratio: int = 2, fwd=None) -> dict:
    """MODEL-PRICED 1xratio call backspread: short one call at delta ``d_short``, long ``ratio`` calls at delta ``d_long``
    (strikes from the Black-Scholes delta at the pricing vol, on the escrowed-dividend spot ``fwd`` = S0 - PV(D) when a
    dividend goes ex inside the life, else on S0), held to expiry and settled at ST. P&L (net credit carried at r to
    expiry plus the payoff) as a fraction of S0."""
    S0, ST, T, r, sig = (np.asarray(a, float) for a in (S0, ST, T, r, sig))
    Sp = S0 if fwd is None else np.asarray(fwd, float)
    K1 = np.array([bs.strike_for_delta(s, t, rr, v, d_short, "call") for s, t, rr, v in zip(Sp, T, r, sig)])
    K2 = np.array([bs.strike_for_delta(s, t, rr, v, d_long, "call") for s, t, rr, v in zip(Sp, T, r, sig)])
    c1 = bs.price(Sp, K1, T, r, sig, "call")
    c2 = bs.price(Sp, K2, T, r, sig, "call")
    credit = c1 - ratio * c2
    payoff = -np.maximum(ST - K1, 0.0) + ratio * np.maximum(ST - K2, 0.0)
    pnl = credit * np.exp(r * T) + payoff
    return {"pnl": pnl / S0, "credit": credit / S0, "k1": K1 / S0, "k2": K2 / S0}


def backspread_cycles(days: list, close: np.ndarray, rv: np.ndarray, bills: Bills, entries: list, expiries: list,
                      vol_add: float = 0.0, vol_mult: float = 1.0, divs: Optional[dict] = None) -> dict:
    a, b = np.asarray(entries, int), np.asarray(expiries, int)
    if a.size == 0:
        return {"pnl": np.array([]), "credit": np.array([]), "k1": np.array([]), "k2": np.array([]), "day": [],
                "expiry": [], "T": np.array([])}
    cal = np.array([date.fromisoformat(d).toordinal() for d in days])
    T = (cal[b] - cal[a]) / 365.0
    r = np.array([bills.rate(days[i]) for i in a])
    sig = rv[a] * vol_mult + vol_add
    fwd = None
    if divs:
        pv = np.zeros(a.size)
        for k, (i, j) in enumerate(zip(a, b)):
            for d, x in divs.items():
                if days[i] < d <= days[j]:
                    pv[k] += x * math.exp(-r[k] * (date.fromisoformat(d).toordinal() - cal[i]) / 365.0)
        fwd = close[a] - pv if pv.any() else None
    out = backspread(close[a], close[b], T, r, sig, fwd=fwd)
    out.update(day=[days[i] for i in a], expiry=[days[i] for i in b], T=T, sig=sig)
    return out


def pooled_cycles(days: list, rv: np.ndarray, dte: int = T275_DTE, start: str = T275_START) -> tuple:
    """Rule 10(b) estimator (robustness only here): an entry at every session with a realised vol, settled at the last
    session on or before ``dte`` calendar days later (and no more than 3 days short of it)."""
    cal = np.array([date.fromisoformat(d).toordinal() for d in days])
    ents, exps = [], []
    for i in range(len(days)):
        if days[i] < start or not np.isfinite(rv[i]):
            continue
        j = int(np.searchsorted(cal, cal[i] + dte, side="right")) - 1
        if j > i and cal[i] + dte - cal[j] <= 3 and cal[i] + dte <= cal[-1]:
            ents.append(i); exps.append(j)
    return ents, exps


def judge_backspread(pnl_rv, pnl_rv5, min_n: int = T275_MIN_N, blocks: Sequence[int] = T275_BLOCKS,
                     captured_iv: Optional[bool] = None, n_boot: Optional[int] = None, seed: int = SEED) -> tuple:
    """T-275 criteria: mean P&L 95% CI > 0 at RV pricing and at RV + 5 vol points (each decided only when every block
    length agrees), and the final verdict on captured IV (None unless given). Returns (verdict, why, details)."""
    x, y = np.asarray(pnl_rv, float), np.asarray(pnl_rv5, float)
    n = int(x.size)
    det = {"n": n}
    crit = []
    for lab, z in (("RV", x), ("RV + 5 vol points", y)):
        cis = {b: mean_ci(z, b, n_boot, seed) for b in blocks} if z.size >= 2 else {}
        det[lab] = {"mean": float(z.mean()) if z.size else None, "ci": {str(b): list(c) for b, c in cis.items()}}
        if not cis:
            crit.append((f"mean P&L 95% CI > 0 at {lab} (no cycles)", None, False))
            continue
        ok = _agree([c[0] > 0 for c in cis.values()])
        dec = all(c[1] < 0 for c in cis.values())
        crit.append((f"mean P&L 95% CI > 0 at {lab} (mean {_f(float(z.mean()), 3, True, True)} of S, lower "
                     + ", ".join(f"{_f(c[0], 3, True, True)} [{b}-cycle blocks]" for b, c in cis.items()) + ")", ok, dec))
    crit.append(("final verdict on captured SLV IV/skew" + ("" if captured_iv is not None else
                 " (not implementable: no captured SLV IV history)"), captured_iv, False))
    v, why = _decide(crit, n, min_n, "backspreads")
    return v, why, det


def _cycle_summary(c: dict, blocks=T275_BLOCKS, n_boot: Optional[int] = None) -> dict:
    n_boot = _nb(n_boot)
    p = c["pnl"]
    if p.size < 2:
        return {"n": int(p.size)}
    return {"n": int(p.size), "mean": float(p.mean()), "ci": {str(b): list(mean_ci(p, b, n_boot)) for b in blocks},
            "skew": float(skewness(p)), "hit": float((p > 0).mean()), "median": float(np.median(p)),
            "mean_credit": float(c["credit"].mean()), "p05": float(np.quantile(p, 0.05)), "p95": float(np.quantile(p, 0.95))}


def backspread_claim(days, close, bills, gld: Optional[tuple] = None, captured_days: Optional[list] = None,
                     n_boot: Optional[int] = None, seed: int = SEED, divs: Optional[dict] = None) -> dict:
    n_boot = _nb(n_boot)
    rv = trailing_rv(close)
    ex = monthly_expiries(days)
    ents, exps = dte_cycles(days, rv, ex)
    base = backspread_cycles(days, close, rv, bills, ents, exps, divs=divs)
    vrp = backspread_cycles(days, close, rv, bills, ents, exps, vol_add=T275_VRP, divs=divs)
    verdict, why, det = judge_backspread(base["pnl"], vrp["pnl"], n_boot=n_boot, seed=seed)
    n = det["n"]
    if n == 0:
        stat = {"label": MP, "n": 0, "min_n": T275_MIN_N}
        return {"stat": stat, "n": 0, "verdict": verdict,
                "reason": f"T-275 {MP}: no monthly 90-DTE cycle with 60 days of SLV history — {why}"}
    sens = {f"IV x{s}": _cycle_summary(backspread_cycles(days, close, rv, bills, ents, exps, vol_mult=s, divs=divs),
                                       n_boot=n_boot) for s in (0.9, 1.2)}
    sens["RV + 10 vol points"] = _cycle_summary(backspread_cycles(days, close, rv, bills, ents, exps, vol_add=0.10,
                                                                  divs=divs), n_boot=n_boot)
    pe, px = pooled_cycles(days, rv)
    pooled = None
    if pe:
        pc = backspread_cycles(days, close, rv, bills, pe, px, divs=divs)
        hold = int(np.median(np.asarray(px) - np.asarray(pe)))
        pooled = {"n_entries": len(pe), "hold_sessions": hold, "block": 2 * hold, "mean": float(pc["pnl"].mean()),
                  "ci": list(mean_ci(pc["pnl"], 2 * hold, min(n_boot, 1000), seed))}
    # shuffled-returns control: same dates, SLV log returns permuted (kills tail clustering)
    rng = np.random.default_rng(seed)
    lr = np.diff(np.log(close))
    sh = close[0] * np.exp(np.concatenate([[0.0], np.cumsum(rng.permutation(lr))]))
    rv_sh = trailing_rv(sh)
    e2, x2 = dte_cycles(days, rv_sh, ex)
    shuf = _cycle_summary(backspread_cycles(days, sh, rv_sh, bills, e2, x2), n_boot=n_boot)
    gctl = None
    if gld is not None and len(gld[0]) > T275_RV + 2:
        gd, gc = gld[0], gld[1]
        grv = trailing_rv(gc)
        ge, gx = dte_cycles(gd, grv, monthly_expiries(gd), start=days[ents[0]] if ents else T275_START)
        gctl = _cycle_summary(backspread_cycles(gd, gc, grv, bills, ge, gx), n_boot=n_boot)
    main = _cycle_summary(base, n_boot=n_boot)
    main5 = _cycle_summary(vrp, n_boot=n_boot)
    lives = np.round(base["T"] * 365).astype(int)
    stat = {"label": MP, "n": n, "min_n": T275_MIN_N, "first_entry": base["day"][0], "last_expiry": base["expiry"][-1],
            "rv": main, "rv_plus_5": main5, "judge": det, "iv_sensitivity": sens, "pooled_daily_entries": pooled,
            "shuffled_returns": shuf, "gld_control": gctl, "life_days": [int(lives.min()), int(lives.max())],
            "mean_k1_over_s": float(base["k1"].mean()), "mean_k2_over_s": float(base["k2"].mean()),
            "captured_iv_days": captured_days or []}

    def ms(s):
        if not s or s.get("mean") is None:
            return "n/a"
        return (f"mean {_f(s['mean'], 3, True, True)} " + " ".join(f"{_ci(c, 3, True)}[{b}]" for b, c in s["ci"].items())
                + (f", skew {_f(s['skew'], 2)}, hit {_f(s['hit'], 2)}" if "skew" in s else ""))
    reason = (
        f"T-275 {MP} (Black-Scholes at a flat IV = SLV's trailing 60-day realised vol: no VRP, no skew, so optimistic): "
        f"short 1 call at 0.50 delta, long 2 at 0.25 delta (strikes from the delta at the pricing vol; mean K1/S "
        f"{_f(stat['mean_k1_over_s'], 3)}, K2/S {_f(stat['mean_k2_over_s'], 3)}), SLV raw (split-adjusted) closes "
        f"(ex-dividend dates in the data: {len(divs or {})}; an escrowed forward would be used inside a life), r = DTB3 "
        f"known at entry (rule 7), net credit carried to expiry, P&L in % of S at entry. Rule 10(a): "
        f"one cycle per standard monthly expiry (third Friday), entered at the last session on or before 90 calendar days "
        f"ahead and settled at the expiry close ({lives.min()}-{lives.max()}-day lives); {n} backspreads "
        f"{base['day'][0]}..{base['expiry'][-1]}. Mean P&L, two-sided 95% circular block bootstrap CI (blocks of 6 and 12 "
        f"cycles >= the 3-cycle overlap): at RV {ms(main)}; at RV + 5 vol points {ms(main5)}. IV sensitivity (reported): "
        + "; ".join(f"{k} {ms(v)}" for k, v in sens.items())
        + f". Robustness (not the claim's calendar): pooled entry every session, "
        + (f"{pooled['n_entries']} entries, mean {_f(pooled['mean'], 3, True, True)} {_ci(pooled['ci'], 3, True)} "
           f"({pooled['block']}-session blocks = 2 x hold)" if pooled else "n/a")
        + f". Controls: shuffled SLV returns {ms(shuf)}; GLD same rule {ms(gctl) if gctl else 'not run (GLD not archived)'}. "
        f"Final verdict on captured IV: SLV chains are captured on "
        f"{', '.join(captured_days) if captured_days else 'no day'} only, so no historical backspread can be priced on "
        f"captured IV/skew")
    reason += f" — {why}"
    return {"stat": stat, "n": n, "verdict": verdict, "reason": reason}


def b6b_misc_slv_call_backspread(archive):
    """T-275: MODEL-PRICED 1x2 SLV call backspread (0.50/0.25 delta, 90 DTE) at trailing 60-day RV, entered monthly."""
    miss = _missing(archive, [SLV_B, DTB3_B])
    if miss:
        return miss
    days, close, adj = _daily(archive, SLV_B)
    divs = _divs(days, close, adj)
    bills = Bills(_series(archive, DTB3_B))
    gld = None
    if _has(archive, GLD_B):
        gd, gc, _ = _daily(archive, GLD_B)
        gld = (gd, gc)
    cap = [d for d in ("2026-10-14", "2026-10-15") if _has(archive, f"options-chain-SLV-{d}")]
    return _out(backspread_claim(days, close, bills, gld, cap, divs=divs))


# ================================================================================================== registry ==

HARNESSES: dict[str, Callable] = {
    "b6b_misc_box_bill_vix_corr": b6b_misc_box_bill_vix_corr,
    "b6b_misc_opec_uso_straddle": b6b_misc_opec_uso_straddle,
    "b6b_misc_election_spy_move": b6b_misc_election_spy_move,
    "b6b_misc_slv_call_backspread": b6b_misc_slv_call_backspread,
}

THEORY_MAP = {
    "T-188": "b6b_misc_box_bill_vix_corr",
    "T-518": "b6b_misc_opec_uso_straddle",
    "T-522": "b6b_misc_election_spy_move",
    "T-275": "b6b_misc_slv_call_backspread",
}
