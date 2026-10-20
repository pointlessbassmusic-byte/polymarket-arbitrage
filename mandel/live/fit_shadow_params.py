"""Freeze the HMM parameters for the shadow forward tests T-565 / T-566 (run once, 2026-10-20, in Mandel's archive).

Fitted on returns through 2026-09-30 (before registration) and never refitted during the forward test, so the forward
record is out of sample by construction. Writes mandel/live/shadow_params.json."""

import json
import math
import sys

import numpy as np

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.archive import Archive  # noqa: E402
from mandel.experiments import batch4_ohlc as OHLC  # noqa: E402
from mandel.experiments import batch6c_mom as MOM  # noqa: E402
from mandel.experiments import hmm_states as MK  # noqa: E402
from mandel.paths import MANDEL_ROOT  # noqa: E402

END = "2026-09-30"


def _fit(days, px, start):
    px = np.asarray(px, float)
    d = list(days)
    keep = [i for i in range(1, len(d)) if start <= d[i] <= END]
    r = np.log(px[keep] / px[[i - 1 for i in keep]])
    h = MK.fit(r)
    p = MK.filter_probs(r, h)
    sstar = float(np.median([MK.one_step_sigma(float(v), h) for v in p]))
    return h, sstar, len(r), d[keep[0]], d[keep[-1]]


def main():
    a = Archive()
    g = MOM._daily(a, "daily-history--GSPC")
    q = OHLC._bars(a, "QQQ")
    out = {"fitted_on": END, "note": "frozen for the forward tests; state 1 = high variance; filter with "
                                     "mandel.experiments.hmm_states.filter_probs"}
    for key, (days, px, start) in {"spx": (g["days"], g["close"], "1990-01-02"),
                                   "qqq": (q.days, q.adj, "1999-03-10")}.items():
        h, sstar, n, first, last = _fit(days, px, start)
        out[key] = {"mu": h.mu, "var": h.var, "P": h.P, "pi": h.pi, "n": n, "first": first, "last": last,
                    "daily_vol": [math.sqrt(v) for v in h.var], "sstar": sstar, "iters": h.iters}
    (MANDEL_ROOT / "live" / "shadow_params.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
