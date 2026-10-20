"""
Shadow records for the forward tests T-565, T-566 and T-573: what the frozen HMMs say each session, written before outcomes.
====================================================================================================================

    python -m mandel.live.shadow record [--dry-run]     # after the close, weekdays

Nothing here trades or changes a running test. Each session it appends one line to <capture out>/shadow.jsonl:

  T-565  P(high-volatility state) of the frozen S&P model, filtered over SPY daily returns (Alpaca, adjusted; the
         stand-in for ^GSPC, on which the model was fitted), and the putwriting signal it implies (in when < 0.5).
         The last recorded session of each month is that month's decision; the PUT index months that follow are scored later.
  T-566  the frozen QQQ model's one-day-ahead volatility forecast and the weight w = min(1, s*/s_f) it would give
         tonight's QQQM overnight slot of the calendar sleeve (T-559). Scored later against T-559's own paper fills.

Parameters: mandel/live/shadow_params.json (fitted on returns through 2026-09-30, never refitted). The filter starts
from the model's stationary distribution on the first of ~400 sessions of history, so the start is forgotten long
before the recorded day.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mandel.experiments.hmm_states import HMM2, filter_probs, one_step_sigma
from mandel.live.capture import OUT
from mandel.paths import MANDEL_ROOT

ET = ZoneInfo("America/New_York")
PARAMS = MANDEL_ROOT / "live" / "shadow_params.json"
HISTORY_DAYS = 600                      # calendar days of bars to filter over (~400 sessions)
CUT = 0.5


def _stationary(P) -> tuple:
    p01, p10 = P[0][1], P[1][0]
    s = p01 + p10
    return (p10 / s, p01 / s) if s > 0 else (0.5, 0.5)


def load_models(path: Path = PARAMS) -> dict:
    raw = json.loads(path.read_text())
    out = {}
    for k in ("spx", "qqq"):
        m = raw[k]
        P = tuple(tuple(r) for r in m["P"])
        out[k] = (HMM2(tuple(m["mu"]), tuple(m["var"]), P, _stationary(P), 0.0, 0, m["n"]), m["sstar"])
    return out


def _log_returns(bars: list) -> tuple:
    days = [b["t"][:10] for b in bars]
    c = [float(b["c"]) for b in bars]
    return days[1:], [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]


def record_from_bars(spy: list, qqq: list, models: dict) -> dict:
    """The shadow line from daily bars (oldest first, Alpaca shape {t, c})."""
    h_spx, _ = models["spx"]
    h_q, sstar = models["qqq"]
    d1, r1 = _log_returns(spy)
    d2, r2 = _log_returns(qqq)
    p_spx = float(filter_probs(r1, h_spx)[-1])
    p_q = float(filter_probs(r2, h_q)[-1])
    sf = one_step_sigma(p_q, h_q)
    day = d1[-1]
    return {"day": day, "qqq_day": d2[-1],
            "T-565": {"p_high": p_spx, "in_put": p_spx < CUT, "n_returns": len(r1)},
            "T-566": {"p_high": p_q, "sigma_f": sf, "sstar": sstar, "w": min(1.0, sstar / sf) if sf > 0 else 1.0,
                      "n_returns": len(r2)},
            "T-573": _ewma_weight(r2)}


def _ewma_weight(r: list) -> dict:
    """T-573: the EWMA(0.94) version of T-566's weight (s* = the median EWMA sigma of QQQ through 2026-09-30)."""
    p = json.loads(PARAMS.read_text()).get("qqq_ewma") or {}
    lam, sstar = p.get("lambda", 0.94), p.get("sstar")
    h = sum(x * x for x in r[:250]) / max(1, min(250, len(r)))
    for x in r:
        h = lam * h + (1 - lam) * x * x
    sf = math.sqrt(h)
    return {"sigma_f": sf, "sstar": sstar, "w": (min(1.0, sstar / sf) if sstar and sf > 0 else None)}


def record(api, dry: bool) -> dict:
    today = datetime.now(ET).date()
    bars = api.daily_bars(["SPY", "QQQ"], (today - timedelta(days=HISTORY_DAYS)).isoformat())
    line = {"ts": datetime.now(ET).isoformat(timespec="seconds"), **record_from_bars(bars["SPY"], bars["QQQ"], load_models())}
    if line["day"] != today.isoformat():
        line["note"] = f"latest bar is {line['day']}, not today ({today}): no session or the bar is not final yet"
    if dry:
        print(json.dumps(line, indent=1))
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "shadow.jsonl", "a") as f:
            f.write(json.dumps(line) + "\n")
        print(json.dumps(line))
    return line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.live.shadow")
    ap.add_argument("what", choices=["record"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from mandel.live.alpaca import Alpaca
    record(Alpaca(), a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
