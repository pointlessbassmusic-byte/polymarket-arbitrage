"""
Batch 4, VIX futures term structure: the gated VX M1-M2 calendar (T-160) and VXX decay in steep contango (T-242).
================================================================================================================

Two options-library claims, each tested against its claim and trial.pass as worded.

VX futures (T-160). ``cboe-vx-futures`` holds the CBOE per-contract daily files (monthly contracts, expiries
2013-01-16 onward). The bundle's ``day`` field is ISO (a MM/DD/YYYY form is accepted too). The 2013 files carry
Settle = 0 until 2013-05-17. The trial says these rows must be filtered, so the first usable settlement is 2013-05-20.
On its final settlement day a contract's row carries the final settlement value (the special opening quotation) as
``settle``. CFE's VX daily settlement is taken at 15:00 Chicago time, 15 minutes before the 16:15 ET VIX and VIX3M
closes.

* M1 and M2 on day D are the first two listed expiries strictly after D, ordered by expiry. A spread held from the
  close of D is therefore marked on the next trading day against the same two contracts. On an expiry day the
  expiring M1 is marked at its final settlement, and the position rolls at that day's close into the next pair. These
  are the trial's Wednesday rolls: expiries fall on Wednesdays, or on a Tuesday when a holiday moves them.
* Position: short 1 M1 and long 1 M2, so P&L = (change in M2 - change in M1) x $1,000.
* Gate, point in time: VIX/VIX3M is observed at the close of D-1. If it is below 1, the spread is held from the
  settlement of D to the settlement of D+1. Otherwise the book is flat. The 16:15 ET index close comes after the
  15:00 CT VX settlement, so the same day's ratio cannot be traded at that day's settlement. A lag-0 run, which uses
  that 15-minute look-ahead, is reported as a sensitivity only.
* Costs: $2 per contract per leg on every leg traded. A roll closes both old legs and opens both new ones, $8; the
  expiring leg is counted even though it cash-settles. A gate entry or exit costs $4.
* Missing settles are bridged. Legs are marked at their last valid settle, so a held position's move across a hole in
  one leg is booked on the first day the settle returns. A trade that needs a missing settle is deferred to the next
  settle, with no extra cost. No interval is dropped. The reason reports the number of gap intervals and the absolute
  P&L and spread move booked across them. The archive has none.
* Statistics: daily net P&L over every trading day, with flat days counted as 0. The 95% CI is two-sided (2.5% and
  97.5%) from a studentized circular block bootstrap with block 21, Bartlett long-run variance with bandwidth 21.
  Annualisation uses 252 days.

VXX (T-242). ``daily-history-VXX`` is the current VXX (series B) from its first traded bar in 2018-01.
Zero-volume bars are stale quotes and are dropped: the two launch bars and 2018-05-08. Closes are Yahoo's
split-adjusted closes, and VXX pays no dividends. The matured 2009-2019 series is not archived and is not spliced.

* Entry rule: VIX3M/VIX at the close of trading day t-1 is above 1.10. VXX is bought at the close of day t and sold at
  the close of t+21, so the cycles do not overlap. Scanning resumes at t+21.
* The pass bound is "upper 95% bound", read as the one-sided 95% upper bound (the repo's convention), from a
  studentized circular block bootstrap with block 3 cycles.
* Reported controls: unconditional drift, a random-entry placebo, the worst cycles, a walk-forward threshold chosen
  on the first half over {1.00, 1.05, 1.10, 1.15, 1.20}, a deflated Sharpe ratio of the short-VXX cycle over that grid,
  fixed-grid phases, and an SVXY proxy (sign-flipped and leverage-adjusted: -1x through 2018-02-27, -0.5x from
  2018-02-28).
* The secondary put spread is MODEL-PRICED: Black-Scholes on VXX with a VVIX-scaled IV proxy. It is reported
  separately and is not a pass criterion.

Verdicts use ``underlying2._verdict``. Any implemented criterion failing gives not_supported. Any criterion not
implemented (missing data, too few events) gives at best inconclusive. A claim is supported only when every criterion
is implemented and passes. Below the trial's min_n (T-160: daily observations; T-242: non-overlapping conditional
cycles) house rule 5 applies (``_rule5_criteria``): the min_n criterion is unmet, so the verdict is never supported, and
a failing criterion counts only when it fails decisively, its studentized bound at the pass's own confidence lying
wholly on the wrong side of the claimed bound. T-160's pass is a two-sided 95% CI, so its failure is decisive when the
two-sided 95% CI lies at or below 0. T-242's pass is the one-sided 95% upper bound, so its failure is decisive when the
one-sided 95% lower bound from the same bootstrap-t draws lies at or above -3% (the two-sided 95% CI's lower end would
be a one-sided 97.5% bound and under-call). Any other failure there is undecided, so the verdict is inconclusive. Under
8 observations no bootstrap runs and the verdict is inconclusive.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _sr, _verdict
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import deflated_sharpe_ratio

EQUITY_PPY = 252
VX_MULT = 1000.0
VX_BUNDLE = "cboe-vx-futures"
VIX_BUNDLE = "cboe-VIX-history"
VIX3M_BUNDLE = "cboe-VIX3M-history"
VXX_BUNDLE = "daily-history-VXX"
SVXY_BUNDLE = "daily-history-SVXY"
VVIX_BUNDLE = "cboe-VVIX-history"
DTB3_BUNDLE = "fred-DTB3"
SVXY_HALF_FROM = "2018-02-28"          # ProShares cut SVXY to -0.5x after the 2018-02-27 close
CRISIS_MONTHS = ("2018-02", "2020-03")
THRESHOLD_GRID = (1.00, 1.05, 1.10, 1.15, 1.20)


# =================================================================================================== statistics ==

def _lrv(x: np.ndarray, bw: int) -> np.ndarray:
    """Row-wise Bartlett long-run variance of a 2-D array (rows are samples), bandwidth ``bw``."""
    x = x - x.mean(axis=1, keepdims=True)
    n = x.shape[1]
    v = np.einsum("ij,ij->i", x, x) / n
    for k in range(1, max(1, bw)):
        if k >= n:
            break
        v = v + 2.0 * (1.0 - k / bw) * np.einsum("ij,ij->i", x[:, k:], x[:, :-k]) / n
    return v


def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def stud_mean(x, block: int, n_boot: int = 5000, seed: int = 0, chunk: int = 500) -> dict:
    """Studentized (bootstrap-t) circular block bootstrap of the mean of ``x``.

    t* = (mean* - mean) / se*, with se from a Bartlett long-run variance whose bandwidth is the block length. Returns
    mean, se, a two-sided 95% CI (2.5% and 97.5%), and one-sided 95% lower and upper bounds."""
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    out = {"mean": float(x.mean()) if n else None, "se": None, "ci95": [None, None], "lb95": None, "ub95": None, "n": n,
           "block": int(block)}
    if n < 8:
        return out
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    v0 = float(_lrv(x[None, :], block)[0])
    if not v0 > 0:
        out.update(se=0.0, ci95=[m, m], lb95=m, ub95=m)
        return out
    se = math.sqrt(v0 / n)
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        s = x[_boot_idx(rng, n, block, k)]
        v = _lrv(s, block)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (s.mean(axis=1) - m) / np.sqrt(v / n)
        ts.append(t[np.isfinite(t) & (v > 0)])
        done += k
    t = np.concatenate(ts)
    q025, q05, q95, q975 = np.quantile(t, [0.025, 0.05, 0.95, 0.975])
    out.update(se=se, ci95=[m - float(q975) * se, m - float(q025) * se], lb95=m - float(q95) * se, ub95=m - float(q05) * se)
    return out


def _cvar(x: np.ndarray, q: float = 0.01) -> Optional[float]:
    """Mean of the worst ceil(q * n) observations (the lower-tail expected shortfall, sign kept)."""
    if len(x) == 0:
        return None
    k = max(1, int(math.ceil(q * len(x))))
    return float(np.sort(x)[:k].mean())


def _rule5_criteria(min_row: str, rows, n: int, min_n: int) -> list:
    """House rule 5. ``rows``: [(name, ok, decisive)] with ok True / False / None and decisive True when a failure stands
    below min_n: the criterion's bound at the pass's own confidence lies wholly on the wrong side of the claimed bound
    (T-160: the two-sided 95% CI; T-242: the one-sided 95% lower bound). At or above min_n the criteria
    are judged at face value after a passing ``min_row`` (n >= min_n). Below min_n ``min_row`` is unmet (None), so the
    verdict cannot be supported; a passing or decisively failing criterion keeps its bool and any other failure becomes
    None (undecided)."""
    if n >= min_n:
        return [(min_row, True)] + [(name, ok) for name, ok, _ in rows]
    return [(min_row, None)] + [(name, ok) if (ok is None or ok) else (name + " (fails decisively below min_n)", False) if decisive
                                else (name + " (fails, not decisively, below min_n: undecided)", None) for name, ok, decisive in rows]


def _rule5_note(rows, n: int, min_n: int, unit: str,
                decisive: str = "its 95% CI wholly on the wrong side of the claimed bound") -> str:
    """Reason fragment below min_n ('' at or above): rule 5 and the face-value criteria verdict. ``decisive`` says when
    a failure counts (the default fits a pass judged on a two-sided 95% CI)."""
    if n >= min_n:
        return ""
    v0, why0 = _verdict([(name, ok) for name, ok, _ in rows])
    dec = [name for name, ok, d in rows if ok is not None and not ok and d]
    return (f". Only {n} of the trial's min_n {min_n} {unit}, so the verdict cannot be supported and a failing criterion counts "
            f"only when it fails decisively, {decisive} (house rule 5); "
            f"decisive failures: {'; '.join(dec) if dec else 'none'}; criteria at face value: {v0}, {why0}")


def _mdd_abs(pnl: np.ndarray) -> float:
    """Maximum drawdown of cumulative dollar P&L (dollars, <= 0)."""
    if len(pnl) == 0:
        return 0.0
    c = np.concatenate([[0.0], np.cumsum(pnl)])
    return float((c - np.maximum.accumulate(c)).min())


# ================================================================================================= date helpers ==

def _iso(s) -> str:
    """ISO day from 'YYYY-MM-DD', 'YYYY-MM-DDTHH..' or 'MM/DD/YYYY'."""
    s = str(s).strip()
    if "/" in s:
        m, d, y = s.split("/")[:3]
        return date(int(y[:4]), int(m), int(d)).isoformat()
    return s[:10]


class AsOf:
    """Point-in-time lookup of a {day: value} series: the last value dated on or before a day, optionally within
    ``max_stale_days`` calendar days."""

    def __init__(self, series: dict, max_stale_days: Optional[int] = None):
        self.days = sorted(series)
        self.vals = [series[d] for d in self.days]
        self.max_stale = max_stale_days

    def at(self, day: str) -> Optional[float]:
        i = bisect_right(self.days, day) - 1
        if i < 0:
            return None
        if self.max_stale is not None and (date.fromisoformat(day) - date.fromisoformat(self.days[i])).days > self.max_stale:
            return None
        return self.vals[i]


def ratio_series(num: dict, den: dict) -> dict:
    """{day: num/den} on days where both closes exist and are positive."""
    return {d: num[d] / den[d] for d in num if d in den and den[d] and num[d] and den[d] > 0}


# ======================================================================================== T-160: VX M1-M2 calendar ==

def vx_curve(values: Sequence[dict]) -> dict:
    """{day: {expiry: settle}} from cboe-vx-futures values. Rows with a missing or non-positive settle are dropped (the
    2013 CBOE files carry Settle = 0), as are rows dated after their expiry."""
    curve: dict = defaultdict(dict)
    for v in values:
        s = v.get("settle")
        if s is None:
            continue
        try:
            s = float(s)
        except (TypeError, ValueError):
            continue
        if not (s > 0 and math.isfinite(s)):
            continue
        d, e = _iso(v["day"]), _iso(v["expiry"])
        if d > e:
            continue
        curve[d][e] = s
    return dict(curve)


def calendar_pnl(curve: dict, gate_ratio: dict, lag: int = 1, threshold: float = 1.0, cost_per_contract: float = 2.0,
                 mult: float = VX_MULT, expiries: Optional[Sequence[str]] = None, gate: bool = True) -> dict:
    """Daily P&L of short 1 M1 / long 1 M2, held while VIX/VIX3M < ``threshold``.

    ``curve``: {day: {expiry: settle}} with only valid settles. ``gate_ratio``: {day: VIX/VIX3M}, read as of the
    decision day. The spread held from the close of days[k] to days[k+1] is decided at the close of days[k - lag].
    lag=1 is point in time; lag=0 uses a 15-minute look-ahead and is reported only as a sensitivity. M1 and M2 are the
    first two ``expiries`` strictly after days[k]. Costs are ``cost_per_contract`` times the number of contracts
    whose position changes at days[k], an expiring leg included. They are charged to the interval that starts at
    days[k]. With ``gate=False`` the spread is always held.

    Missing settles are bridged, never skipped. Every leg is marked at its last valid settle, so a held leg with no
    settle on a day books nothing that day, and its move across the gap is booked on the first day its settle
    returns. A trade whose legs lack a settle at days[k] is deferred: the held legs are kept, no extra cost is charged,
    and the trade is retried at the next settle. An expired leg that never got a final settle is closed at its last
    valid settle (a stale close). Every interval is kept in the series.

    Returns per-interval arrays (the day an interval ends, the position held, the ungated spread change in dollars,
    gross, cost, net, a gap flag) plus counts of trades, the intervals that bridged a missing settle (``gaps``),
    deferred trades, stale closes, and the absolute held P&L and spread move booked across gaps."""
    days = sorted(curve)
    if expiries is None:
        expiries = sorted({e for d in curve for e in curve[d]})
    expiries = sorted(expiries)
    asof = AsOf(gate_ratio, max_stale_days=7)
    rec = {k: [] for k in ("day", "start", "w", "spread_chg", "gross", "cost", "net", "spread", "ratio", "m1", "m2", "gap")}
    gaps, held, last = [], {}, {}
    n_rolls = n_switch = n_deferred = n_stale = 0
    for d in days[:lag + 1]:
        last.update(curve[d])                            # last valid settle per contract, as of the close of d0
    for k in range(lag, len(days) - 1):
        d0, d1 = days[k], days[k + 1]
        c0, c1 = curve[d0], curve[d1]
        j = bisect_right(expiries, d0)
        pair = (expiries[j], expiries[j + 1]) if j + 1 < len(expiries) else None
        r = asof.at(days[k - lag])
        w = (1 if (r is not None and r < threshold) else 0) if gate else 1
        pos = {pair[0]: -w, pair[1]: w} if (w and pair) else {}
        legs = [c for c in set(pos) | set(held) if pos.get(c, 0) != held.get(c, 0)]
        deferred = not all(c in c0 or c <= d0 for c in legs)
        stale = 0
        if deferred:
            n_deferred += 1; cost = 0.0                  # a leg to trade has no settle at d0: keep the held legs
        else:
            if held and pos and set(held) != set(pos):
                n_rolls += 1
            elif bool(held) != bool(pos):
                n_switch += 1
            stale = sum(1 for c in legs if c not in c0)  # expired, no final settle: closed at its last valid settle
            n_stale += stale
            cost = cost_per_contract * sum(abs(pos.get(c, 0) - held.get(c, 0)) for c in legs)
            held = pos
        watch = set(held) | set(pair or ())
        m0 = {c: last.get(c) for c in watch}
        last.update(c1)
        gross = mult * sum(q * (last[c] - m0[c]) for c, q in held.items())
        if pair and m0[pair[0]] is not None and m0[pair[1]] is not None:
            chg = mult * ((last[pair[1]] - m0[pair[1]]) - (last[pair[0]] - m0[pair[0]]))
            spread = m0[pair[1]] - m0[pair[0]]
        else:
            chg, spread = 0.0, float("nan")
        gap = pair is None or deferred or stale > 0 or any(c not in c0 or c not in c1 for c in watch)
        if gap:
            gaps.append((d1, "no M2 listed" if pair is None else "missing settle"))
        rec["day"].append(d1); rec["start"].append(d0); rec["w"].append(1 if held else 0); rec["spread_chg"].append(chg)
        rec["gross"].append(gross); rec["cost"].append(cost); rec["net"].append(gross - cost); rec["gap"].append(gap)
        rec["spread"].append(spread); rec["ratio"].append(r)
        rec["m1"].append(pair[0] if pair else None); rec["m2"].append(pair[1] if pair else None)
    out = {k: (np.array(v, dtype=float) if k in ("w", "spread_chg", "gross", "cost", "net", "spread") else v) for k, v in rec.items()}
    g = np.array(rec["gap"], dtype=bool)
    out.update(gaps=gaps, n_rolls=n_rolls, n_switches=n_switch, n_deferred=n_deferred, n_stale_closes=n_stale,
               gap_abs_gross=float(np.abs(out["gross"][g]).sum()) if g.any() else 0.0,
               gap_abs_spread_chg=float(np.abs(out["spread_chg"][g]).sum()) if g.any() else 0.0)
    return out


def _block_shift_placebo(w: np.ndarray, chg: np.ndarray, block: int = 21, min_shift: int = 63) -> np.ndarray:
    """Gross mean P&L with the regime label circularly shifted by every multiple of ``block`` in
    [min_shift, n - min_shift]."""
    n = len(w)
    shifts = [s for s in range(block, n, block) if min_shift <= s <= n - min_shift]
    return np.array([float((np.roll(w, s) * chg).mean()) for s in shifts])


def vx_calendar(curve: dict, vix: dict, vix3m: dict, cost_per_contract: float = 2.0, mult: float = VX_MULT,
                block: int = 21, n_boot: int = 5000, seed: int = 0, min_n: int = 2500, lag: int = 1,
                crisis_months: Sequence[str] = CRISIS_MONTHS) -> dict:
    """T-160. Pass (as worded): after costs, mean daily P&L > 0, with the 95% CI excluding 0 in both chronological
    halves. Criteria: n >= min_n daily observations; full-sample mean > 0; the first half's studentized block-21 95%
    CI lies above 0; the second half's does too. Below min_n (house rule 5) a failure counts only when the CI in question
    lies wholly at or below 0. Sharpe, 1% CVaR, the ex-crisis run, the ungated and lag-0 runs, the block-shifted placebo
    and the VIX3M - VIX basis cross-check are reported."""
    ratio = ratio_series(vix, vix3m)                       # VIX / VIX3M
    res = calendar_pnl(curve, ratio, lag=lag, cost_per_contract=cost_per_contract, mult=mult)
    net = res["net"]; n = int(len(net))
    if n < 8:
        crit = [(f"n >= {min_n} daily observations (min_n)", None),
                ("full-sample mean daily net P&L > 0", None),
                ("first half: mean > 0 and 95% CI excludes 0", None),
                ("second half: mean > 0 and 95% CI excludes 0", None)]
        v, why = _verdict(crit)
        return {"n": n, "criteria": crit, "verdict": v,
                "reason": f"only {n} usable VX M1/M2 intervals with settlements and a VIX/VIX3M gate — {why}"}
    days = res["day"]
    full = stud_mean(net, block, n_boot, seed)
    h = n // 2
    first = stud_mean(net[:h], block, n_boot, seed + 1)
    second = stud_mean(net[h:], block, n_boot, seed + 2)
    keep = np.array([d[:7] not in crisis_months for d in days])
    ex = stud_mean(net[keep], block, n_boot, seed + 3)
    ungated = calendar_pnl(curve, ratio, lag=lag, cost_per_contract=cost_per_contract, mult=mult, gate=False)
    lag0 = calendar_pnl(curve, ratio, lag=0, cost_per_contract=cost_per_contract, mult=mult) if lag != 0 else res
    l0 = lag0["net"]; h0 = len(l0) // 2
    lag0_halves = [stud_mean(l0[:h0], block, n_boot, seed + 4), stud_mean(l0[h0:], block, n_boot, seed + 5)] if len(l0) >= 16 else None
    plc = _block_shift_placebo(res["w"], res["spread_chg"], 21, 63)
    gross_mean = float(res["gross"].mean())
    plc_pct = float((plc >= gross_mean).mean()) if len(plc) else None
    spread_days = res["start"]
    sl = [(s, vix3m[d] - vix[d]) for s, d in zip(res["spread"], spread_days) if d in vix and d in vix3m and math.isfinite(s)]
    sa, sb = np.array([a for a, _ in sl]), np.array([b for _, b in sl])
    basis_corr = float(np.corrcoef(sa, sb)[0, 1]) if len(sl) > 10 and sa.std() > 0 and sb.std() > 0 else None
    held = res["w"] > 0
    sharpe = _sr(net, EQUITY_PPY) if n > 2 else None
    cvar = _cvar(net, 0.01)
    cvar_held = _cvar(net[held], 0.01) if held.any() else None
    worst = sorted(zip(days, net.tolist()), key=lambda t: t[1])[:5]
    def down(s):        # rule 5: the 95% CI lies wholly at or below 0 (a zero-width CI, e.g. never held, decides nothing)
        return s["ci95"][1] is not None and bool(s["se"]) and s["ci95"][1] <= 0
    rows = [("full-sample mean daily net P&L > 0", full["mean"] > 0, down(full)),
            (f"first half {days[0]}..{days[h - 1]}: mean > 0 and studentized block-{block} 95% CI excludes 0",
             None if first["ci95"][0] is None else bool(first["mean"] > 0 and first["ci95"][0] > 0), down(first)),
            (f"second half {days[h]}..{days[-1]}: mean > 0 and studentized block-{block} 95% CI excludes 0",
             None if second["ci95"][0] is None else bool(second["mean"] > 0 and second["ci95"][0] > 0), down(second))]
    crit = _rule5_criteria(f"n >= {min_n} daily observations (min_n)", rows, n, min_n)
    v, why = _verdict(crit)

    def ci(s):
        return f"[{_usd(s['ci95'][0])}, {_usd(s['ci95'][1])}]"

    reason = (f"VX M1-M2 calendar (short M1 / long M2, $1,000/pt) on CBOE daily settlements {days[0]}..{days[-1]}, "
              f"n={n} daily intervals (2013 rows with Settle = 0 dropped, so the first settlement is {min(curve)}; "
              f"{len(res['gaps'])} intervals bridged a missing settle, booking {_usd(res['gap_abs_gross'], 0)} absolute held "
              f"P&L and {_usd(res['gap_abs_spread_chg'], 0)} absolute spread move across gaps, {res['n_deferred']} trades "
              f"deferred, {res['n_stale_closes']} stale closes); held on {held.mean():.0%} of days under the "
              f"point-in-time gate (VIX/VIX3M < 1 at the previous close); costs $2/contract/leg on every leg traded "
              f"({res['n_rolls']} rolls at $8, {res['n_switches']} gate entries/exits at $4, total {_usd(float(res['cost'].sum()), 0)}). "
              f"Mean net {_usd(full['mean'])}/day, 95% CI {ci(full)} (n >= {min_n}: {n >= min_n}); "
              f"first half mean {_usd(first['mean'])}, CI {ci(first)}; second half mean {_usd(second['mean'])}, CI {ci(second)} "
              f"(each needs mean > 0 and lower > 0). Sharpe {_f(sharpe)} (x sqrt 252), 1% CVaR {_usd(cvar, 0)}/day "
              f"({_usd(cvar_held, 0)} on held days), max drawdown {_usd(_mdd_abs(net), 0)}; without {'/'.join(crisis_months)}: "
              f"mean {_usd(ex['mean'])}, CI {ci(ex)}; ungated always-on mean {_usd(float(ungated['net'].mean()) if len(ungated['net']) else None)}; "
              f"lag-0 gate (15-min look-ahead) mean {_usd(float(l0.mean()) if len(l0) else None)}"
              f"{f', halves CI {ci(lag0_halves[0])} and {ci(lag0_halves[1])}' if lag0_halves else ''}; block-shifted "
              f"gate placebo: {plc_pct if plc_pct is None else f'{plc_pct:.0%}'} of {len(plc)} shifts reach the actual gross mean "
              f"{_usd(gross_mean)}; basis cross-check corr(M2 - M1, VIX3M - VIX) = {_f(basis_corr)}. Margin outlay is not "
              f"archived (the statistic is dollars per spread){_rule5_note(rows, n, min_n, 'daily observations')} — {why}")
    rep = {"n": n, "start": days[0], "end": days[-1], "mean_net": full["mean"], "ci95": full["ci95"], "se": full["se"],
           "halves": {"first": {"days": f"{days[0]}..{days[h - 1]}", **first},
                      "second": {"days": f"{days[h]}..{days[-1]}", **second}},
           "mean_gross": gross_mean, "total_cost": float(res["cost"].sum()), "n_rolls": res["n_rolls"],
           "n_gate_switches": res["n_switches"], "frac_held": float(held.mean()), "mean_held_day": float(net[held].mean()) if held.any() else None,
           "sharpe": sharpe, "cvar_1pct": cvar, "cvar_1pct_held": cvar_held, "max_drawdown_usd": _mdd_abs(net),
           "ex_crisis": {"months_dropped": list(crisis_months), **ex},
           "ungated_mean": float(ungated["net"].mean()) if len(ungated["net"]) else None,
           "lag0_mean": float(l0.mean()) if len(l0) else None, "lag0_halves": lag0_halves,
           "placebo": {"n_shifts": int(len(plc)), "share_ge_actual": plc_pct,
                       "mean": float(plc.mean()) if len(plc) else None, "actual_gross": gross_mean},
           "basis_corr_spread_vs_vix3m_minus_vix": basis_corr, "worst_days": worst,
           "gap_intervals": len(res["gaps"]), "gap_abs_gross_usd": res["gap_abs_gross"],
           "gap_abs_spread_chg_usd": res["gap_abs_spread_chg"], "n_deferred_trades": res["n_deferred"],
           "n_stale_closes": res["n_stale_closes"],
           "conventions": "M1/M2 = first two expiries after the day; Wednesday (expiry-day) rolls; gate at previous close; "
                          "$2 x contracts traded",
           "criteria": crit, "verdict": v, "reason": reason}
    if n < min_n:
        rep["rule5"] = {"min_n": min_n, "n": n, "decisive_failures": [c for c, ok, d in rows if ok is not None and not ok and d]}
    return rep


# ============================================================================== T-242: VXX 21-day decay in contango ==

def conditional_cycles(days: Sequence[str], closes: np.ndarray, ratio: dict, threshold: float = 1.10,
                       horizon: int = 21, lag: int = 1, start: Optional[str] = None, end: Optional[str] = None,
                       max_stale_days: int = 5) -> dict:
    """Non-overlapping event cycles: VIX3M/VIX (``ratio``, as of the close of days[i - lag]) above ``threshold`` means
    buy at the close of days[i] and sell at the close of days[i + horizon]. Scanning resumes at i + horizon. Returns
    entry indices, entry days and log returns. With ``threshold=None`` every scanned day is an entry (the
    unconditional drift)."""
    asof = AsOf(ratio, max_stale_days=max_stale_days)
    c = np.asarray(closes, dtype=float)
    idx, lr = [], []
    i = max(lag, 0)
    n = len(days)
    while i + horizon < n:
        if (start and days[i] < start) or (end and days[i + horizon] > end):
            i += 1; continue
        r = asof.at(days[i - lag]) if threshold is not None else None
        if threshold is None or (r is not None and r > threshold):
            idx.append(i); lr.append(math.log(c[i + horizon] / c[i])); i += horizon
        else:
            i += 1
    return {"idx": idx, "days": [days[i] for i in idx], "logret": np.array(lr, dtype=float)}


def grid_cycles(days, closes, ratio: dict, threshold: float, phase: int, horizon: int = 21, lag: int = 1) -> np.ndarray:
    """Fixed calendar grid (entries at lag + phase + k*horizon), kept when the as-of ratio at days[i - lag] > threshold."""
    asof = AsOf(ratio, max_stale_days=5)
    c = np.asarray(closes, dtype=float)
    out = []
    for i in range(lag + phase, len(days) - horizon, horizon):
        r = asof.at(days[i - lag])
        if r is not None and r > threshold:
            out.append(math.log(c[i + horizon] / c[i]))
    return np.array(out)


def svxy_proxy(days: Sequence[str], svxy: np.ndarray, half_from: str = SVXY_HALF_FROM) -> np.ndarray:
    """VXX-like proxy closes from SVXY: daily return = -r_SVXY / L, with L = 1 before ``half_from`` and 0.5 from it.
    The level starts at 100. A proxy return at or below -100% is floored at -99%."""
    s = np.asarray(svxy, dtype=float)
    out = np.empty(len(s)); out[0] = 100.0
    for i in range(1, len(s)):
        lev = 0.5 if days[i] >= half_from else 1.0
        r = -(s[i] / s[i - 1] - 1.0) / lev
        out[i] = out[i - 1] * max(1.0 + r, 0.01)
    return out


def put_spread_model(days, closes, entries: Sequence[int], iv_index: dict, rates: dict, horizon: int = 21,
                     dte_cal: int = 75, otm: float = 0.175, hist: int = 252) -> dict:
    """MODEL-PRICED secondary for T-242: buy an ATM VXX put and sell a put ``otm`` below spot, both ``dte_cal`` calendar
    days out (the middle of the library's 15-20% OTM and 60-90 DTE). Marked by Black-Scholes after ``horizon`` trading
    days with the remaining calendar time. IV proxy: scale x VVIX/100, as of the previous close. The scale is the
    ratio of VXX's realised 21-day volatility to VVIX/100 over the ``hist`` days before entry, so it is point in time.
    Rate: DTB3 as of the previous day. No skew and no bid/ask."""
    c = np.asarray(closes, dtype=float)
    lr = np.diff(np.log(c))
    vv = AsOf(iv_index, max_stale_days=7)
    rr = AsOf(rates, max_stale_days=10) if rates else None
    rows = []
    for i in entries:
        if i - hist - 21 < 0 or i + horizon >= len(c):
            continue
        rv, vvs = [], []
        for j in range(i - hist, i):
            w = lr[j - 21:j]                       # log returns over (close j-21, close j], all known at entry
            v_ = vv.at(days[j - 21])               # VVIX at the start of that window
            if len(w) == 21 and v_:
                rv.append(float(w.std(ddof=1)) * math.sqrt(EQUITY_PPY)); vvs.append(v_ / 100.0)
        if len(rv) < hist // 2:
            continue
        scale = float(np.mean(rv) / np.mean(vvs))
        v0 = vv.at(days[i - 1]); v1 = vv.at(days[i + horizon - 1])
        if not v0 or not v1:
            continue
        r = (rr.at(days[i - 1]) if rr else 0.0) or 0.0
        r = math.log(1.0 + r / 100.0)
        S0, S1 = float(c[i]), float(c[i + horizon])
        K2, K1 = S0, S0 * (1.0 - otm)
        T0 = dte_cal / 365.0
        el = (date.fromisoformat(days[i + horizon]) - date.fromisoformat(days[i])).days
        T1 = max(dte_cal - el, 0) / 365.0
        s0, s1 = scale * v0 / 100.0, scale * v1 / 100.0
        debit = float(bs.price(S0, K2, T0, r, s0, "put")) - float(bs.price(S0, K1, T0, r, s0, "put"))
        exitv = float(bs.price(S1, K2, T1, r, s1, "put")) - float(bs.price(S1, K1, T1, r, s1, "put"))
        rows.append({"day": days[i], "debit_over_spot": debit / S0, "pnl_over_debit": (exitv - debit) / debit if debit > 0 else None,
                     "pnl_over_spot": (exitv - debit) / S0, "iv_entry": s0, "scale": scale})
    if not rows:
        return {"pricing": "MODEL-PRICED", "n": 0}
    pod = np.array([r["pnl_over_debit"] for r in rows if r["pnl_over_debit"] is not None])
    pos = np.array([r["pnl_over_spot"] for r in rows])
    return {"pricing": f"MODEL-PRICED: Black-Scholes, long ATM / short {otm:.1%} OTM VXX puts, {dte_cal} DTE, marked after "
                       f"{horizon} trading days; IV = point-in-time scale x VVIX/100; DTB3 rate; no skew, no spread",
            "n": len(rows), "mean_pnl_over_debit": float(pod.mean()) if len(pod) else None,
            "median_pnl_over_debit": float(np.median(pod)) if len(pod) else None,
            "mean_pnl_over_spot": float(pos.mean()), "win_rate": float((pos > 0).mean()),
            "mean_debit_over_spot": float(np.mean([r["debit_over_spot"] for r in rows])),
            "mean_iv_entry": float(np.mean([r["iv_entry"] for r in rows])),
            "mean_scale": float(np.mean([r["scale"] for r in rows]))}


def vxx_decay(days: Sequence[str], closes: np.ndarray, vix: dict, vix3m: dict, threshold: float = 1.10,
              horizon: int = 21, lag: int = 1, bound: float = -0.03, block: int = 3, n_boot: int = 5000, seed: int = 0,
              min_n: int = 80, n_place: int = 2000, proxy: Optional[tuple] = None, vvix: Optional[dict] = None,
              rates: Optional[dict] = None, grid: Sequence[float] = THRESHOLD_GRID) -> dict:
    """T-242. Pass (as worded): the upper 95% bound of the mean 21-day VXX log return, conditional on VIX3M/VIX >
    ``threshold`` at entry, is below ``bound``. Criteria: n >= min_n non-overlapping conditional cycles, and the
    one-sided 95% studentized block-bootstrap upper bound < bound. Below min_n (house rule 5) the bound criterion's
    failure counts only when the one-sided 95% lower bound (the same bootstrap-t draws, the pass's own confidence) lies
    at or above ``bound``. ``proxy`` = (days, closes) of the
    SVXY-based proxy, reported as a cross-check. The model-priced put spread is reported separately."""
    days = list(days); c = np.asarray(closes, dtype=float)
    ratio = ratio_series(vix3m, vix)                       # VIX3M / VIX
    ev = conditional_cycles(days, c, ratio, threshold, horizon, lag)
    x = ev["logret"]; n = int(len(x))
    if n < 8:
        crit = [(f"n >= {min_n} non-overlapping conditional cycles (min_n)", None),
                (f"upper 95% bound of the conditional mean < {bound}", None)]
        v, why = _verdict(crit)
        return {"n": n, "criteria": crit, "verdict": v,
                "reason": f"only {n} VXX cycles with VIX3M/VIX > {threshold} at entry — {why}"}
    st = stud_mean(x, block, n_boot, seed)
    unc = conditional_cycles(days, c, ratio, None, horizon, lag)["logret"]
    lag0 = conditional_cycles(days, c, ratio, threshold, horizon, 0)["logret"]
    phases = [grid_cycles(days, c, ratio, threshold, p, horizon, lag) for p in range(horizon)]
    ph_means = [float(p.mean()) for p in phases if len(p)]
    # random-entry placebo: the same number of entries drawn uniformly from all valid entry days
    rng = np.random.default_rng(seed + 7)
    all_lr = np.log(c[lag + horizon:] / c[lag:len(c) - horizon]) if len(c) > lag + horizon else np.array([])
    plc = np.array([all_lr[rng.integers(0, len(all_lr), n)].mean() for _ in range(n_place)]) if len(all_lr) else np.array([])
    plc_p = float((plc <= st["mean"]).mean()) if len(plc) else None
    worst = sorted(zip(ev["days"], x.tolist()), key=lambda t: -t[1])[:5]
    # walk-forward threshold: chosen on the first half of the calendar, applied to the second
    mid = days[len(days) // 2]
    first = {t: conditional_cycles(days, c, ratio, t, horizon, lag, end=mid)["logret"] for t in grid}
    pick = min((t for t in grid if len(first[t]) >= 5), key=lambda t: float(first[t].mean()), default=None)
    wf = conditional_cycles(days, c, ratio, pick, horizon, lag, start=mid)["logret"] if pick is not None else np.array([])
    # deflated Sharpe of the short-VXX cycle (-log return) at the stated threshold, over the threshold grid
    trial = {t: conditional_cycles(days, c, ratio, t, horizon, lag)["logret"] for t in grid}
    tsr = [float((-trial[t]).mean() / (-trial[t]).std(ddof=1)) if len(trial[t]) > 2 and trial[t].std(ddof=1) > 0 else 0.0 for t in grid]
    dsr = float(deflated_sharpe_ratio(-x, n_trials=len(grid), trial_sharpes=tsr)) if n > 2 else None
    prox = None
    if proxy is not None:
        pd_, pc_ = proxy
        pe = conditional_cycles(list(pd_), np.asarray(pc_, dtype=float), ratio, threshold, horizon, lag)["logret"]
        ps = stud_mean(pe, block, n_boot, seed + 3) if len(pe) >= 8 else {"mean": float(pe.mean()) if len(pe) else None, "ub95": None}
        pre = conditional_cycles(list(pd_), np.asarray(pc_, dtype=float), ratio, threshold, horizon, lag, end=days[0])["logret"]
        prox = {"start": pd_[0], "end": pd_[-1], "n": int(len(pe)), "mean": ps["mean"], "ub95": ps.get("ub95"),
                "n_before_vxx": int(len(pre)), "mean_before_vxx": float(pre.mean()) if len(pre) else None}
    mp = put_spread_model(days, c, ev["idx"], vvix, rates or {}, horizon) if vvix else {"pricing": "MODEL-PRICED", "n": 0}
    # rule 5: the pass is the one-sided 95% upper bound, so the failure is decisive when the one-sided 95% lower bound
    # from the same bootstrap-t draws lies at or above the bound (the two-sided CI's lower end is a one-sided 97.5% bound;
    # a zero-width interval decides nothing)
    rows = [(f"one-sided 95% studentized block-{block} bootstrap upper bound of the conditional mean < {bound}",
             None if st["ub95"] is None else bool(st["ub95"] < bound),
             st["lb95"] is not None and bool(st["se"]) and st["lb95"] >= bound)]
    crit = _rule5_criteria(f"n >= {min_n} non-overlapping conditional cycles (min_n)", rows, n, min_n)
    v, why = _verdict(crit)
    r5_dec = (f"its one-sided 95% lower bound ({_pc(st['lb95'])}, the mirror of the one-sided 95% upper-bound pass from the "
              f"same bootstrap-t draws) at or above {_pc(bound)}")
    pr = (f"SVXY proxy (sign-flipped, -1x to 2018-02-27 then -0.5x) {prox['start']}..{prox['end']}: n={prox['n']}, mean "
          f"{_pc(prox['mean'])}, upper bound {_pc(prox['ub95'])}, pre-2018 cycles {prox['n_before_vxx']} mean {_pc(prox['mean_before_vxx'])}"
          if prox else "SVXY proxy not run")
    mps = (f"{mp['pricing']}: n={mp['n']}, mean P&L {_pc(mp.get('mean_pnl_over_debit'))} of the debit "
           f"(debit {mp['mean_debit_over_spot']:.1%} of spot, IV proxy {mp['mean_iv_entry']:.0%}), win rate "
           f"{mp['win_rate']:.0%}" if mp.get("n") else "MODEL-PRICED put spread: no cycle with a full VVIX/VXX history")
    reason = (f"VXX (current series B, zero-volume bars dropped) {days[0]}..{days[-1]}: n={n} non-overlapping 21-day cycles "
              f"entered at the close after a VIX3M/VIX > {threshold} close (need >= {min_n}); mean log return {_pc(st['mean'])} "
              f"(median {_pc(float(np.median(x)))}), one-sided 95% studentized block-{block} upper bound {_pc(st['ub95'])} "
              f"(need < {_pc(bound)}), 95% CI [{_pc(st['ci95'][0])}, {_pc(st['ci95'][1])}]. Controls: unconditional mean "
              f"{_pc(float(unc.mean()) if len(unc) else None)} over {len(unc)} cycles; random-entry placebo: {'n/a' if plc_p is None else f'{plc_p:.0%}'} of "
              f"{len(plc)} draws at or below the conditional mean; lag-0 entry mean {_pc(float(lag0.mean()) if len(lag0) else None)} "
              f"(n={len(lag0)}); fixed-grid phases {_pc(min(ph_means) if ph_means else None)} to {_pc(max(ph_means) if ph_means else None)}; "
              f"walk-forward threshold {pick} (first half to {mid}) gives second-half mean {_pc(float(wf.mean()) if len(wf) else None)} "
              f"(n={len(wf)}); DSR of the short-VXX cycle over {len(grid)} thresholds {_f(dsr, 3)}; worst cycles (largest VXX gains) "
              f"{', '.join(f'{d} {_pc(r, 0)}' for d, r in worst[:3])}; {pr}. Secondary, reported separately: {mps}"
              f"{_rule5_note(rows, n, min_n, 'non-overlapping conditional cycles', r5_dec)} — {why}")
    rep = {"n": n, "start": days[0], "end": days[-1], "threshold": threshold, "mean_logret": st["mean"],
           "median_logret": float(np.median(x)), "ub95": st["ub95"], "ci95": st["ci95"], "se": st["se"],
           "entries": ev["days"], "unconditional_mean": float(unc.mean()) if len(unc) else None, "unconditional_n": int(len(unc)),
           "lag0": {"n": int(len(lag0)), "mean": float(lag0.mean()) if len(lag0) else None},
           "grid_phase_means": ph_means, "placebo_share_le": plc_p, "worst_cycles": worst,
           "walk_forward": {"split": mid, "threshold": pick, "n": int(len(wf)), "mean": float(wf.mean()) if len(wf) else None,
                            "first_half_means": {str(t): (float(first[t].mean()) if len(first[t]) else None) for t in grid}},
           "dsr": dsr, "grid_sharpes_per_cycle": dict(zip([str(t) for t in grid], tsr)), "svxy_proxy": prox,
           "model_priced_put_spread": mp, "criteria": crit, "verdict": v, "reason": reason}
    if n < min_n:
        rep["rule5"] = {"min_n": min_n, "n": n, "lb95": st["lb95"],
                        "decisive_failures": [c for c, ok, d in rows if ok is not None and not ok and d]}
    return rep


# ========================================================================================== formatting helpers ==

def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _usd(x, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return f"-${abs(x):,.{nd}f}" if x < 0 else f"${x:,.{nd}f}"


def _pc(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except KeyError:
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were already available when it was captured (drops bars still open at capture)."""
    cap = getattr(archive.get(name), "created_at", None)
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _index(archive, name: str) -> dict:
    return index_closes(_rows(archive, name))


def _prices(archive, name: str, drop_zero_volume: bool = True) -> tuple[list, np.ndarray]:
    """(days, closes) from a daily-history bundle: adjclose when present, bars not yet available at capture and
    (optionally) zero-volume stale bars dropped."""
    by = {}
    for r in _rows(archive, name):
        v = r["value"]
        if drop_zero_volume and not v.get("volume"):
            continue
        c = v.get("adjclose") if v.get("adjclose") is not None else v.get("close")
        if c is None or not c > 0:
            continue
        by[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = float(c)
    ds = sorted(by)
    return ds, np.array([by[d] for d in ds], dtype=float)


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, date):
        return x.isoformat()
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


# ==================================================================================================== harnesses ==

def vx_calendar_gated(archive):
    """T-160: short VX M1 / long M2, held while VIX/VIX3M < 1 (previous close), after $2/contract/leg costs, 2013+."""
    miss = _missing(archive, [VX_BUNDLE, VIX_BUNDLE, VIX3M_BUNDLE])
    if miss:
        return miss
    curve = vx_curve([r["value"] for r in _rows(archive, VX_BUNDLE)])
    return _wrap(vx_calendar(curve, _index(archive, VIX_BUNDLE), _index(archive, VIX3M_BUNDLE)))


def vx_vxx_contango_decay(archive):
    """T-242: mean 21-trading-day VXX log return after VIX3M/VIX > 1.10, upper 95% bound < -3%."""
    miss = _missing(archive, [VXX_BUNDLE, VIX_BUNDLE, VIX3M_BUNDLE])
    if miss:
        return miss
    days, closes = _prices(archive, VXX_BUNDLE)
    proxy = None
    if _has(archive, SVXY_BUNDLE):
        sd, sc = _prices(archive, SVXY_BUNDLE)
        if len(sd) > 50:
            proxy = (sd, svxy_proxy(sd, sc))
    vvix = _index(archive, VVIX_BUNDLE) if _has(archive, VVIX_BUNDLE) else None
    rates = _index(archive, DTB3_BUNDLE) if _has(archive, DTB3_BUNDLE) else None
    return _wrap(vxx_decay(days, closes, _index(archive, VIX_BUNDLE), _index(archive, VIX3M_BUNDLE), proxy=proxy,
                           vvix=vvix, rates=rates))


HARNESSES = {
    "vx_calendar_gated": vx_calendar_gated,
    "vx_vxx_contango_decay": vx_vxx_contango_decay,
}

THEORY_MAP = {
    "T-160": "vx_calendar_gated",
    "T-242": "vx_vxx_contango_decay",
}
