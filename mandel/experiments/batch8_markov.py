"""
Batch 8, group ``markov``: four Markov-model tests pre-registered on 2026-10-20 (mandel/theories/register_markov_2026_10_20.py).
=============================================================================================================================

Each tests whether a Markov state model changes a decision an existing rule makes, on the parent's own construction:

  * T-561  (parent T-551) Cboe PUT held only after month-ends at which a two-state Gaussian HMM on ^GSPC daily log returns
           puts the forward-filtered probability of its high-variance state below 0.5. T-551's machinery unchanged
           (batch7_vol.putwrite_trend_filter: fills, bills, switch cost, matched null, Sharpe test); only the signal and
           min_n (200) differ. T-551's 10-month SMA on the same months is reported.
  * T-562  (parent T-549) QQQ / IWM overnight-only holding scaled by w = min(1, s*/s_f): s_f the HMM's one-day-ahead
           volatility forecast (filtered probability x transition matrix, mixing the two variances) from returns through
           the close the position is taken at; s* the median one-step forecast over the refit's own training sample.
           Paired Sharpe difference (scaled - unscaled), 20-day blocks; both ETFs' 95% lower bounds > 0.
  * T-563  (parent T-549) Hold the night after close t only when the expanding mean of next-night returns after the
           state of close t (sign of day t's intraday return x sign of the night into day t; pairs fully observed before
           close t; at least 250 per state, else hold) exceeds 2 bps. Paired mean difference vs holding every night,
           studentized circular block bootstrap (20 days), Holm over the two ETFs.
  * T-564  (parent T-556) T-556's DOGE / SHIB trades re-run with one added exit: on every close k from the entry day, the
           tercile state of day k's close-to-close return (cuts and state-conditional mean next-day returns estimated per
           coin on bars strictly before the entry day, at least 120 returns) predicts a positive next-day return -> close
           the short at the open of k+1 when k+1 is inside the 14-day window. Stop and target are checked first on every
           bar, exactly as T-556. Paired per-trade difference, month-clustered studentized bootstrap.

HMM conventions (mandel.experiments.hmm_states): EM fit refitted every January 1 on all returns strictly before it (from the
training start), variances initialised at the 20th / 80th percentile of rolling 21-day variance, state 1 = the
high-variance state; a day's probability is the FORWARD-FILTERED P(high | returns through that day's close) under its
year's fit. No smoothed or Viterbi path is used anywhere.

Rule 5: below min_n the verdict is never supported and a failing criterion counts only when it fails decisively. Rule 9:
a missing bundle is inconclusive and names what is missing.
"""

from __future__ import annotations

import bisect
import math
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch7_crypto as B7X
from mandel.experiments import batch7_vol as B7V
from mandel.experiments import hmm_states as MK
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_bw import _ci_crit, _decide, mc_escalate, sharpe_diff_test
from mandel.experiments.batch6c_cryptovenue import cbd

N_BOOT = 2000
SEED = 0

GSPC_B = "daily-history--GSPC"
PUT_B = "cboe-PUT-history"
DTB3_B = "fred-DTB3"
SPY_B = "daily-history-SPY"

T561_TRAIN_FROM = "1990-01-02"
T561_CUT = 0.5
T561_MIN_N = 200

T562_START, T562_END = "2003-01-01", "2026-09-30"
T562_COST_SIDE = 1e-4
T562_BLOCK = 20
T562_MIN_N = 2500
ETFS = ("QQQ", "IWM")

T563_MIN_STATE = 250
T563_BAR = 2e-4

T564_MIN_HIST = 120
T564_MIN_N = 60


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not B7C._has(archive, n)]
    if miss:
        return _out({"missing": miss}, 0, "inconclusive", f"missing bundles: {', '.join(miss)} (rule 9)")
    return None


def _bp(x) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 1e4:+.2f} bps"


def _log_returns(days: Sequence[str], px) -> tuple:
    px = np.asarray(px, float)
    r = np.log(px[1:] / px[:-1])
    return list(days[1:]), r


# ------------------------------------------------------------------------------------------------- T-561 --

def hmm_month_signal(days: Sequence[str], close, train_from: str = T561_TRAIN_FROM, cut: float = T561_CUT,
                     first_year: Optional[int] = None) -> tuple:
    """{month: (in_market, 'HMM')} from the filtered P(high) at each month's last session; and the fits."""
    rd, r = _log_returns(days, close)
    fy = first_year or (int(train_from[:4]) + 3)
    fits = MK.yearly_refits(rd, r, fy, train_from=train_from)
    ph = MK.filtered_high(rd, r, fits, train_from=train_from)
    last = {}
    for d in sorted(ph):
        last[d[:7]] = d
    sig = {m: (bool(ph[d] < cut), "HMM") for m, d in last.items()}
    return sig, fits, ph


def b8_markov_putwrite_hmm_filter(archive):
    """T-561."""
    miss = _missing(archive, [PUT_B, GSPC_B, DTB3_B, SPY_B])
    if miss:
        return miss
    P = B7V.cboe_index(archive, "PUT")
    pdays_all = sorted(P["close"])
    i0 = B7V.continuous_start(pdays_all)
    pdays = pdays_all[i0:]
    lvl = [P["close"][d] for d in pdays]
    bt = [P["backtest"].get(d, False) for d in pdays]
    g = MOM._daily(archive, GSPC_B)
    sig, fits, ph = hmm_month_signal(g["days"], g["close"])
    bills = MOM._bills(archive)
    j = B7V.putwrite_trend_filter(pdays, lvl, bt, sig, bills, min_n=T561_MIN_N)
    spy = MOM._daily(archive, SPY_B)
    sma = B7V.sma_signal([("SPY", spy["days"], spy["adj"]), ("^GSPC", g["days"], g["close"])])
    js = B7V.putwrite_trend_filter(pdays, lvl, bt, sma, bills, min_n=T561_MIN_N, n_null=2000, reps=1)
    if "dd" not in j:
        return _out({"n_months": j["n"]}, j["n"], j["verdict"], f"PUT HMM filter: {j['reason']} — {j['why']}")
    months = [m for m in sig if j["first_month"] <= m <= j["last_month"]]
    agree = float(np.mean([sig[m][0] == sma[m][0] for m in months if m in sma])) if months else None
    high_share = float(np.mean([not sig[m][0] for m in months])) if months else None
    last_fit = fits[max(fits)]
    head = (f"Cboe PUT index {pdays[0]}..{pdays[-1]} held after month-ends with filtered P(high-vol) < {T561_CUT} under a "
            f"two-state Gaussian HMM on ^GSPC daily log returns (training from {T561_TRAIN_FROM}, refitted every January, "
            f"{len(fits)} fits; latest: daily vol {math.sqrt(last_fit.var[0]) * 100:.2f}% / {math.sqrt(last_fit.var[1]) * 100:.2f}%, "
            f"stay probabilities {last_fit.P[0][0]:.3f} / {last_fit.P[1][1]:.3f}), T-551's fills, bills, switch cost and null: "
            f"{j['n']} hold months, {j['time_in_market'] * 100:.0f}% in PUT, {j['n_switches']} switches; the HMM is out on "
            f"{_pc(high_share)} of decision months and agrees with the 10-month SMA on {_pc(agree)}")
    parts = [f"HMM filter: {B7V._dd_txt(j['dd'], j['sharpe'])}"]
    if "dd" in js:
        parts.append(f"T-551's SMA filter on the same history (reported): {B7V._dd_txt(js['dd'], js['sharpe'])}")
    if j.get("live"):
        parts.append(f"live months ({j['live']['n']}): {B7V._dd_txt(j['live']['dd'], j['live']['sharpe'])}")
    stat = {"n_months": j["n"], "first_decision": j["first_month"], "last_decision": j["last_month"],
            "time_in_market": j["time_in_market"], "n_switches": j["n_switches"], "mdd_filtered": j["dd"]["mdd_rule"],
            "mdd_always": j["dd"]["mdd_always"], "reduction": j["dd"]["reduction"], "null_p": j["dd"]["p"],
            "sharpe_filtered": j["sharpe"].get("sharpe_a"), "sharpe_always": j["sharpe"].get("sharpe_b"),
            "sharpe_diff": j["sharpe"].get("diff"), "sharpe_ci": j["sharpe"].get("ci"),
            "sma_reduction": (js.get("dd") or {}).get("reduction"), "sma_sharpe_diff": (js.get("sharpe") or {}).get("diff"),
            "agreement_with_sma": agree, "share_out": high_share, "n_fits": len(fits),
            "latest_fit": {"vol": [math.sqrt(v) for v in last_fit.var], "P": last_fit.P, "iters": last_fit.iters},
            "filter": "forward-filtered (no smoothing)", "rule10": "calendar: month-end decisions (T-551's construction)"}
    return _out(stat, j["n"], j["verdict"], head + ". " + "; ".join(parts) + " — " + j["why"])


def _pc(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


# ------------------------------------------------------------------------------------------ T-562 / T-563 --

def _etf_series(b) -> dict:
    """Daily close-to-close log returns on adjclose and T-549's nights, aligned by day."""
    days = list(b.days)
    adj = np.asarray(b.adj, float)
    rd, r = _log_returns(days, adj)
    nd = B7C.night_day(b, days[1], "9999-12-31")
    return {"days": days, "rdays": rd, "r": r, "nd": nd}


def vol_scaled_nights(b, start: str = T562_START, end: str = T562_END, cost_side: float = T562_COST_SIDE) -> dict:
    """Unscaled and HMM-scaled net overnight returns for nights into days in [start, end]."""
    s = _etf_series(b)
    rd, r = s["rdays"], s["r"]
    fits = MK.yearly_refits(rd, r, int(start[:4]), train_from=None)
    ph = MK.filtered_high(rd, r, fits)
    sstar = {}
    for y, h in fits.items():                                  # median one-step forecast over the fit's training sample
        m = [i for i, d in enumerate(rd) if d < f"{y}-01-01"]
        p = MK.filter_probs(r[m], h)
        sstar[y] = float(np.median([MK.one_step_sigma(float(v), h) for v in p]))
    nd = s["nd"]
    days = s["days"]
    pos = {d: i for i, d in enumerate(days)}
    out_d, un, sc, w_all = [], [], [], []
    for d, night in zip(nd["ds"], nd["night"]):
        d = str(d)
        if not (start <= d <= end):
            continue
        prev = days[pos[d] - 1]
        y = int(prev[:4])
        if prev not in ph or y not in fits:
            continue
        sf = MK.one_step_sigma(ph[prev], fits[y])
        w = min(1.0, sstar[y] / sf) if sf > 0 else 1.0
        out_d.append(d); w_all.append(w)
        un.append(night - 2 * cost_side)
        sc.append(w * night - w * 2 * cost_side)
    return {"days": out_d, "unscaled": np.array(un), "scaled": np.array(sc), "w": np.array(w_all), "n_fits": len(fits)}


def scaled_claim(per: dict, min_n: int = T562_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    nb = N_BOOT if n_boot is None else n_boot
    crit, rep = [], {}
    for s, x in per.items():
        a, b = x["scaled"], x["unscaled"]
        t = mc_escalate(lambda seed: sharpe_diff_test(a, b, 252, T562_BLOCK, nb, seed),
                        lambda t: _ci_crit(t, "gt", 0.0, "")[1], reps, SEED)
        c = _ci_crit(t, "gt", 0.0, f"{s}: Sharpe(scaled) - Sharpe(unscaled) {B7X._s(t.get('diff'))} > 0, paired 95% lower bound")
        crit.append(c)
        rep[s] = {"n": int(a.size), "first": x["days"][0] if x["days"] else None, "last": x["days"][-1] if x["days"] else None,
                  "sharpe_scaled": t.get("sharpe_a"), "sharpe_unscaled": t.get("sharpe_b"), "diff": t.get("diff"),
                  "ci": t.get("ci"), "mean_scaled_bps": float(a.mean() * 1e4), "mean_unscaled_bps": float(b.mean() * 1e4),
                  "mean_weight": float(x["w"].mean()), "share_weight_below_1": float(np.mean(x["w"] < 1)), "n_fits": x["n_fits"]}
    n = min((r["n"] for r in rep.values()), default=0)
    v, why = _decide(crit, n, min_n, "nights (the smaller ETF)")
    return {"n": n, "per_etf": rep, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b8_markov_overnight_vol_scaled(archive):
    """T-562."""
    miss = _missing(archive, [B7C.dh(s) for s in ETFS])
    if miss:
        return miss
    per = {s: vol_scaled_nights(OHLC._bars(archive, s)) for s in ETFS}
    j = scaled_claim(per)
    parts = []
    for s, r in j["per_etf"].items():
        ci = r["ci"] or [None, None]
        parts.append(f"{s} {r['first']}..{r['last']} ({r['n']} nights, {r['n_fits']} yearly fits): Sharpe scaled "
                     f"{B7X._s(r['sharpe_scaled'])} vs unscaled {B7X._s(r['sharpe_unscaled'])}, difference {B7X._s(r['diff'])} "
                     f"(95% CI {B7X._s(ci[0])}..{B7X._s(ci[1])}); mean net {r['mean_scaled_bps']:+.2f} vs "
                     f"{r['mean_unscaled_bps']:+.2f} bps/night; mean weight {r['mean_weight']:.2f}, below 1 on "
                     f"{r['share_weight_below_1'] * 100:.0f}% of nights")
    stat = {k: j[k] for k in ("per_etf", "criteria")} | {"filter": "forward-filtered one-step forecast (no smoothing)",
                                                          "rule10": "every trading night (no grid phase)"}
    return _out(stat, j["n"], j["verdict"], "; ".join(parts) + " — " + j["why"])


def state_conditioned(b, start: str = T562_START, end: str = T562_END, cost_side: float = T562_COST_SIDE,
                      min_state: int = T563_MIN_STATE, bar: float = T563_BAR) -> dict:
    """Paired daily series: conditioned net (0 when out) minus every-night net, for nights into days in [start, end]."""
    nd = B7C.night_day(b, b.days[1], "9999-12-31")
    ds, night, dayr = [str(d) for d in nd["ds"]], nd["night"], nd["day"]
    st = [(1 if dayr[i] > 0 else 0) * 2 + (1 if night[i] > 0 else 0) for i in range(len(ds))]
    sums, cnts = [0.0] * 4, [0] * 4
    diff, cond, every, held, days = [], [], [], [], []
    for i in range(len(ds) - 1):
        # pairs (st[j], night[j+1]) with j + 1 <= i are known at close i
        if i >= 1:
            sums[st[i - 1]] += night[i]; cnts[st[i - 1]] += 1
        d_next = ds[i + 1]
        s = st[i]
        hold = cnts[s] < min_state or (sums[s] / cnts[s]) > bar
        if not (start <= d_next <= end):
            continue
        net = night[i + 1] - 2 * cost_side
        c = net if hold else 0.0
        diff.append(c - net); cond.append(c); every.append(net); held.append(hold); days.append(d_next)
    return {"days": days, "diff": np.array(diff), "cond": np.array(cond), "every": np.array(every),
            "held": np.array(held, bool), "state_counts": cnts}


def conditioned_claim(per: dict, min_n: int = T562_MIN_N, n_boot: Optional[int] = None) -> dict:
    ps, rep = [], {}
    for s, x in per.items():
        d = x["diff"]
        pg, pl, dr = CAL.studentized_p_escalated(d, T562_BLOCK, n_boot, SEED, B7C.N_SEEDS)
        ps.append(pg)
        rep[s] = {"n": int(d.size), "first": x["days"][0] if x["days"] else None, "last": x["days"][-1] if x["days"] else None,
                  "diff_bps": float(d.mean() * 1e4), "p": pg, "p_less": pl, "draws": dr,
                  "cond_bps": float(x["cond"].mean() * 1e4), "every_bps": float(x["every"].mean() * 1e4),
                  "time_in_market": float(x["held"].mean()), "state_counts": x["state_counts"]}
    hp = B7C.holm(ps)
    crit = []
    for (s, r), h in zip(rep.items(), hp):
        r["holm_p"] = h
        crit.append((f"{s}: conditioned - every night {r['diff_bps']:+.3f} bps/day > 0 with Holm p < 0.05 "
                     f"(Holm p {B7C._mc(h, r['draws'])})", B7C._sig_crit(r["diff_bps"], h, r["draws"]),
                     CAL.decide_p(r["p_less"], r["draws"]) is True))
    n = min((r["n"] for r in rep.values()), default=0)
    v, why = _decide(crit, n, min_n, "nights (the smaller ETF)")
    return {"n": n, "per_etf": rep, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b8_markov_overnight_state_conditioned(archive):
    """T-563."""
    miss = _missing(archive, [B7C.dh(s) for s in ETFS])
    if miss:
        return miss
    per = {s: state_conditioned(OHLC._bars(archive, s)) for s in ETFS}
    j = conditioned_claim(per)
    parts = [f"{s} {r['first']}..{r['last']} ({r['n']} nights): held {r['time_in_market'] * 100:.0f}% of nights, conditioned "
             f"{r['cond_bps']:+.2f} vs every night {r['every_bps']:+.2f} bps/day net, difference {r['diff_bps']:+.3f} "
             f"(p {B7C._mc(r['p'], r['draws'])}, Holm {B7C._mc(r['holm_p'], r['draws'])}); state counts {r['state_counts']}"
             for s, r in j["per_etf"].items()]
    stat = {k: j[k] for k in ("per_etf", "criteria")} | {"rule10": "every trading night (no grid phase)"}
    return _out(stat, j["n"], j["verdict"], "; ".join(parts) + " — " + j["why"])


# ------------------------------------------------------------------------------------------------- T-564 --

def markov_exit_trade(bars: dict, trade: dict, hold: int = B7X.T556_HOLD, cost: float = B7X.T556_COST,
                      fund_day: float = B7X.T556_FUND_DAY, min_hist: int = T564_MIN_HIST) -> dict:
    """T-556's trade with the Markov exit added. Returns the trade's Markov-exit net and how it exited."""
    days, O, Hh, L, C = bars["days"], bars["open"], bars["high"], bars["low"], bars["close"]
    j = bisect.bisect_left(days, trade["entry_day"])
    e_ord = B7X._ord(trade["entry_day"])
    last_ord = e_ord + hold - 1
    entry = O[j]
    # chain estimated on bars strictly before the entry day: returns r_q = C[q]/C[q-1]-1 for q < j
    r_hist = C[1:j] / C[:j - 1] - 1.0
    usable = r_hist.size >= min_hist
    means = None
    if usable:
        cuts = MK.tercile_cuts(r_hist)
        states = [MK.tercile_state(v, cuts) for v in r_hist[:-1]]
        means = MK.state_next_means(states, r_hist[1:], 3)
    stop, tgt = entry * (1 + B7X.T556_STOP), entry * (1 - B7X.T556_TARGET)
    exit_px, why, k, held = None, "time", j, None
    while k < len(days) and B7X._ord(days[k]) <= last_ord:
        if Hh[k] >= stop:
            exit_px, why = max(stop, O[k]), "stop"; break
        if L[k] < tgt:
            exit_px, why = tgt, "target"; break
        if usable and k >= 1 and k + 1 < len(days) and B7X._ord(days[k + 1]) <= last_ord:
            s = MK.tercile_state(C[k] / C[k - 1] - 1.0, cuts)
            m = means[s]
            if m is not None and m > 0:
                exit_px, why = O[k + 1], "markov"
                held = B7X._ord(days[k + 1]) - e_ord
                break
        k += 1
    if exit_px is None:
        k = bisect.bisect_right(days, B7X._iso(last_ord)) - 1
        exit_px = C[k]
    if held is None:
        held = B7X._ord(days[k]) - e_ord + 1
    gross = 1.0 - exit_px / entry
    return {"net": float(gross - cost - fund_day * held), "why": why, "held_days": int(held), "chain": usable}


def markov_exit_test(pairs: Sequence[dict], coins: Sequence[str] = B7X.T556_COINS, min_n: int = T564_MIN_N,
                     n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    n = len(pairs)
    d = np.array([p["diff"] for p in pairs], float)
    months = [p["entry_day"][:7] for p in pairs]
    bt = B7X._boot(d, months, n_boot, reps)
    crit = [_ci_crit(bt, "gt", 0.0, f"month-clustered 95% CI of the mean paired difference {B7X._pfmt(B7X._mean(d))} "
                                     f"excludes 0 on the positive side", B7X._pfmt)]
    per = {}
    for cn in coins:
        xs = [p["diff"] for p in pairs if p["coin"] == cn]
        per[cn] = {"n": len(xs), "mean_diff": B7X._mean(xs)}
        crit.append((f"{cn} mean difference {B7X._pfmt(per[cn]['mean_diff'])} > 0 ({len(xs)} trades)",
                     None if per[cn]["mean_diff"] is None else bool(per[cn]["mean_diff"] > 0), False))
    v, why = _decide(crit, n, min_n, "trades")
    return {"n": n, "mean_diff": B7X._mean(d), "boot": {k: bt.get(k) for k in ("est", "ci", "clusters")}, "per_coin": per,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b8_markov_bounce_short_exit(archive):
    """T-564."""
    need = [cbd(c) for c in B7X.T556_COINS]
    miss = _missing(archive, need)
    if miss:
        return miss
    coins = {c: B7X._ohlc(archive, cbd(c)) for c in B7X.T556_COINS}
    trades = B7X.short_trades(coins, B7X.child_signals(coins))
    pairs = []
    for t in trades:
        m = markov_exit_trade(coins[t["coin"]], t)
        pairs.append({"coin": t["coin"], "entry_day": t["entry_day"], "fixed": t["net"], "markov": m["net"],
                      "diff": m["net"] - t["net"], "why_markov": m["why"], "why_fixed": t["why"],
                      "held_markov": m["held_days"], "held_fixed": t["held_days"], "chain": m["chain"]})
    j = markov_exit_test(pairs)
    from collections import Counter
    ex = Counter(p["why_markov"] for p in pairs)
    reason = (f"T-556's {len(trades)} DOGE/SHIB trades (same entries, costs, funding): mean net fixed exit "
              f"{B7X._pfmt(B7X._mean([p['fixed'] for p in pairs]))} vs with the Markov exit "
              f"{B7X._pfmt(B7X._mean([p['markov'] for p in pairs]))}; paired difference {B7X._pfmt(j['mean_diff'])} "
              f"(month-clustered 95% {B7X._ci_txt(j['boot'].get('ci'))}, {j['boot'].get('clusters')} months); "
              + "; ".join(f"{c} {r['n']} trades, difference {B7X._pfmt(r['mean_diff'])}" for c, r in j["per_coin"].items())
              + f"; Markov-rule exits {dict(ex)}; mean hold {np.mean([p['held_markov'] for p in pairs]):.1f} vs "
              f"{np.mean([p['held_fixed'] for p in pairs]):.1f} days; chain usable on "
              f"{sum(p['chain'] for p in pairs)} trades")
    stat = {k: j[k] for k in ("mean_diff", "boot", "per_coin", "criteria")} | {"exits_markov": dict(ex),
            "n_trades": len(pairs), "rule10": "data-determined entries (T-556's signals)"}
    return _out(stat, j["n"], j["verdict"], reason + " — " + j["why"])


HARNESSES = {
    "b8_markov_putwrite_hmm_filter": b8_markov_putwrite_hmm_filter,
    "b8_markov_overnight_vol_scaled": b8_markov_overnight_vol_scaled,
    "b8_markov_overnight_state_conditioned": b8_markov_overnight_state_conditioned,
    "b8_markov_bounce_short_exit": b8_markov_bounce_short_exit,
}

THEORY_MAP = {
    "T-561": "b8_markov_putwrite_hmm_filter",
    "T-562": "b8_markov_overnight_vol_scaled",
    "T-563": "b8_markov_overnight_state_conditioned",
    "T-564": "b8_markov_bounce_short_exit",
}
