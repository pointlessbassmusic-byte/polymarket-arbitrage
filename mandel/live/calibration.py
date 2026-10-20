"""
Daily per-model calibration: is every model a live test uses still the most accurate version of itself?
======================================================================================================

    python -m mandel.live.calibration run [--dry-run]     # after the close, weekdays (after mandel.live.shadow record)

The live shadows (T-565, T-566) run on parameters frozen at registration. Each session this records, per model:

  * the FROZEN model's one-day-ahead variance forecast for the next session;
  * a CHALLENGER: the same model refitted through today (HMM: EM warm-started from yesterday's challenger, on the
    full archived history plus the newest bars; MSM: not refitted daily, its grid fit is too slow, so only its
    calibration is tracked);
  * once the next session's return is known, both forecasts' QLIKE losses, whether |r| exceeded 2 forecast sigmas,
    and r^2 / h (1 on average when calibrated).

calibration.json summarises each model: scored days, mean r^2/h and the 2-sigma exceedance rate of the frozen forecast,
the frozen-minus-challenger loss difference with a t statistic, and how far the challenger's parameters have moved.
Flags (never actions): 'recalibration candidate' when, over at least 60 scored days, the challenger's loss is lower with
t > 2; 'miscalibrated' when the 60-day mean r^2/h leaves [0.6, 1.6]. A flag goes to the evidence graph as an alert; a
parameter changes only by a new pre-registered record at a checkpoint, never by this job, so no model's parameters can
be tuned day by day toward recent profits.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments import hmm_states as MK
from mandel.experiments import msm as MSM
from mandel.live.capture import OUT
from mandel.live.shadow import PARAMS, load_models

ET = ZoneInfo("America/New_York")
STATE = OUT / "calibration_state.json"
LOG = OUT / "calibration.jsonl"
SUMMARY = OUT / "calibration.json"
MODELS = {"spx_hmm": ("SPY", "hmm"), "qqq_hmm": ("QQQ", "hmm"), "qqq_msm": ("QQQ", "msm"),
          "spx_ewma": ("SPY", "ewma"), "qqq_ewma": ("QQQ", "ewma")}   # EWMA(0.94): the benchmark that beat both in review
EWMA_LAMBDA = 0.94
FLAG_MIN_DAYS = 60
FLAG_T = 2.0
CAL_BAND = (0.6, 1.6)


def qlike(r2: float, h: float) -> float:
    h = max(h, 1e-12)
    return r2 / h + math.log(h)


def msm_next_var(r: np.ndarray, p: dict) -> float:
    """MSM one-step-ahead variance after filtering through all of ``r``."""
    k = int(p.get("k", 4))
    _, prod = MSM._states(k, p["m0"])
    var = p["sigma"] ** 2 * prod
    P = MSM._transition(k, p["gamma1"], p["b"])
    pi = np.full(var.size, 1.0 / var.size)
    for x in r:
        pred = pi @ P
        w = pred * np.exp(-0.5 * x * x / var) / np.sqrt(2 * math.pi * var)
        s = w.sum()
        if s > 0 and np.isfinite(s):
            pi = w / s
    return float((pi @ P) @ var)


def ewma_next_var(r: np.ndarray, lam: float = EWMA_LAMBDA) -> float:
    """RiskMetrics EWMA: h_{t+1} = lam h_t + (1 - lam) r_t^2, seeded with the variance of the first 250 returns."""
    h = float(np.var(r[:250])) if r.size >= 250 else float(np.var(r))
    for x in r:
        h = lam * h + (1 - lam) * float(x) * float(x)
    return h


def hmm_from(d: dict) -> MK.HMM2:
    return MK.HMM2(tuple(d["mu"]), tuple(d["var"]), tuple(tuple(x) for x in d["P"]), tuple(d["pi"]), 0.0, 0, d.get("n", 0))


def hmm_to(h: MK.HMM2) -> dict:
    return {"mu": list(h.mu), "var": list(h.var), "P": [list(x) for x in h.P], "pi": list(h.pi), "n": h.n, "iters": h.iters}


def returns_series(archive_returns: dict, bar_returns: dict) -> tuple:
    """Archived (Yahoo adjclose) daily log returns, extended by broker bars for days after the archive's last day."""
    days = sorted(archive_returns)
    last = days[-1] if days else ""
    extra = sorted(d for d in bar_returns if d > last)
    ds = days + extra
    return ds, np.array([archive_returns[d] for d in days] + [bar_returns[d] for d in extra])


def step(model: str, days: list, r: np.ndarray, state: dict, frozen: dict) -> tuple:
    """Score yesterday's pending forecasts against today's return, then forecast the next session. Returns
    (scored line or None, new pending forecast, updated challenger state)."""
    today = days[-1]
    scored = None
    pend = state.get("pending", {}).get(model)
    if pend and pend["for_after"] < today:
        r_t = float(r[-1]); r2 = r_t * r_t
        scored = {"model": model, "day": today, "r": r_t, "h_frozen": pend["h_frozen"], "h_challenger": pend.get("h_challenger"),
                  "loss_frozen": qlike(r2, pend["h_frozen"]),
                  "loss_challenger": None if pend.get("h_challenger") is None else qlike(r2, pend["h_challenger"]),
                  "ratio_frozen": r2 / max(pend["h_frozen"], 1e-12), "exceed_2sd": abs(r_t) > 2 * math.sqrt(pend["h_frozen"])}
    kind = MODELS[model][1]
    chal_state = state.get("challenger", {}).get(model)
    if kind == "hmm":
        h_frozen_model = frozen[model]
        p = MK.filter_probs(r, h_frozen_model)[-1]
        h_f = MK.one_step_sigma(float(p), h_frozen_model) ** 2
        init = hmm_from(chal_state) if chal_state else h_frozen_model
        ch = MK.fit(r, max_iter=50, init=init)
        pc = MK.filter_probs(r, ch)[-1]
        h_c = MK.one_step_sigma(float(pc), ch) ** 2
        new_chal = hmm_to(ch)
    elif kind == "msm":
        h_f = msm_next_var(r[-2500:], frozen[model])
        h_c, new_chal = None, None
    else:
        h_f = ewma_next_var(r[-1000:])
        h_c, new_chal = None, None
    pending = {"for_after": today, "h_frozen": h_f, "h_challenger": h_c}
    return scored, pending, new_chal


def summarise(lines: list, state: dict, frozen_raw: dict) -> dict:
    out = {}
    for model in MODELS:
        L = [x for x in lines if x["model"] == model]
        rec = {"scored_days": len(L)}
        if L:
            last = L[-FLAG_MIN_DAYS:]
            rec["ratio_mean_all"] = float(np.mean([x["ratio_frozen"] for x in L]))
            rec["ratio_mean_60"] = float(np.mean([x["ratio_frozen"] for x in last]))
            rec["exceed_2sd_rate"] = float(np.mean([x["exceed_2sd"] for x in L]))
            d = np.array([x["loss_frozen"] - x["loss_challenger"] for x in L if x.get("loss_challenger") is not None])
            if d.size:
                rec["loss_diff_mean"] = float(d.mean())
                rec["loss_diff_t"] = float(d.mean() / (d.std(ddof=1) / math.sqrt(d.size))) if d.size > 2 and d.std() > 0 else None
            flags = []
            if len(L) >= FLAG_MIN_DAYS and rec.get("loss_diff_t") is not None and rec["loss_diff_t"] > FLAG_T:
                flags.append("recalibration candidate: the daily refit has forecast better; pre-register a parameter switch")
            if len(last) >= FLAG_MIN_DAYS and not (CAL_BAND[0] <= rec["ratio_mean_60"] <= CAL_BAND[1]):
                flags.append(f"miscalibrated: 60-day mean r^2/h {rec['ratio_mean_60']:.2f} outside {CAL_BAND}")
            rec["flags"] = flags
        ch = (state.get("challenger") or {}).get(model)
        fz = frozen_raw.get(model.replace("_hmm", "")) if model.endswith("_hmm") else None
        if ch and fz:
            rec["challenger_drift"] = {"daily_vol": [math.sqrt(a) - b for a, b in zip(ch["var"], fz["daily_vol"])],
                                       "stay_high": ch["P"][1][1] - fz["P"][1][1]}
        out[model] = rec
    return out


def run(api, dry: bool, archive=None) -> dict:
    from mandel.archive import Archive
    from mandel.experiments import batch4_ohlc as OHLC
    archive = archive or Archive()
    today = datetime.now(ET).date()
    bars = api.daily_bars(["SPY", "QQQ"], (today - timedelta(days=60)).isoformat())
    frozen_models = load_models()
    frozen = {"spx_hmm": frozen_models["spx"][0], "qqq_hmm": frozen_models["qqq"][0],
              "qqq_msm": json.loads(PARAMS.read_text())["qqq_msm"]}
    frozen_raw = json.loads(PARAMS.read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {"pending": {}, "challenger": {}}
    from mandel.experiments import batch6c_mom as MOM

    def bar_returns(sym):
        br = bars.get(sym, [])
        return {br[i]["t"][:10]: float(math.log(br[i]["c"] / br[i - 1]["c"])) for i in range(1, len(br))}

    # each model's series is the history its frozen fit used, extended by the broker's newest bars
    g = MOM._daily(archive, "daily-history--GSPC")
    gc = np.asarray(g["close"], float)
    spx = {g["days"][i]: float(math.log(gc[i] / gc[i - 1])) for i in range(1, len(g["days"])) if g["days"][i] >= "1990-01-02"}
    q = OHLC._bars(archive, "QQQ")
    qa = np.asarray(q.adj, float)
    qqq = {q.days[i]: float(math.log(qa[i] / qa[i - 1])) for i in range(1, len(q.days)) if q.days[i] >= "1999-03-10"}
    series = {"SPY": returns_series(spx, bar_returns("SPY")), "QQQ": returns_series(qqq, bar_returns("QQQ"))}
    new_lines = []
    for model, (sym, _) in MODELS.items():
        days, r = series[sym]
        scored, pending, chal = step(model, days, r, state, frozen)
        if scored:
            new_lines.append(scored)
        state.setdefault("pending", {})[model] = pending
        if chal:
            state.setdefault("challenger", {})[model] = chal
    old = [json.loads(x) for x in LOG.read_text().splitlines()] if LOG.exists() else []
    summary = {"as_of": datetime.now(ET).isoformat(timespec="seconds"), "models": summarise(old + new_lines, state, frozen_raw)}
    if dry:
        print(json.dumps({"scored": new_lines, "pending": state["pending"], "summary": summary}, indent=1, default=str))
        return summary
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        for x in new_lines:
            f.write(json.dumps(x) + "\n")
    STATE.write_text(json.dumps(state, indent=1))
    SUMMARY.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.live.calibration")
    ap.add_argument("what", choices=["run"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from mandel.live.alpaca import Alpaca
    run(Alpaca(), a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
