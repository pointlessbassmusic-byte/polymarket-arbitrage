"""Pre-register T-572 (user request 2026-10-20: daily per-model calibration, so no model runs on parameters that a
refit would have made more accurate): does refitting the two-state HMM every day beat the January refit?"""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

E = dict(slug="hmm-daily-vs-yearly-refit", kind="volatility", parent="T-562/T-569",
         claim="For SPY, QQQ and IWM daily log returns 2003-01 to 2026-09, refitting the two-state Gaussian HMM every day on all returns before that day (EM warm-started from the previous day's fit) gives a lower mean QLIKE loss of the one-day-ahead variance forecast than refitting it every January, for all three ETFs (Holm-adjusted p < 0.05).",
         trial=dict(statistic="mean of QLIKE(yearly refit) - QLIKE(daily refit) per day", null="mean difference <= 0",
                    procedure="mandel.experiments.batch10_calib; both forecasts one step ahead from returns through the previous close (no smoothing); studentized circular block bootstrap, 20-day blocks; Holm over 3 ETFs; reported: the T-562 scaled-overnight Sharpe under each refit, and how far the daily parameters drift within each year",
                    data="daily-history-SPY, daily-history-QQQ, daily-history-IWM", min_n=5000,
                    pass_="all three ETFs: difference > 0 with Holm p < 0.05",
                    controls="the January refit is what T-561/T-562 used; the daily refit can only use returns before the forecast day; the result decides whether the live shadows (T-565/T-566) should be refitted daily (a change made only at a pre-registered checkpoint)"),
         why="the user asked for daily per-model calibration so parameters cannot drift from what the data supports")


def main():
    reg = json.load(open(REGISTRY))
    assert E["slug"] not in {t["slug"] for t in reg["theories"]}
    tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
    tr = dict(E["trial"]); tr["pass"] = tr.pop("pass_")
    trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
    reg["theories"].append({"id": tid, "slug": E["slug"], "kind": E["kind"], "claim": E["claim"],
                            "origin": [E["parent"], "calibration request 2026-10-20"], "trial": trial, "experiments": [],
                            "testable_now": True, "status": "untested", "blocked_on": "", "results": [],
                            "notes": f"pre-registered on 2026-10-20: {E['why']}."})
    Ledger().append("theory.preregistered", {"id": tid, "from": E["parent"], "hash": hashlib.sha256(json.dumps(
        {"claim": E["claim"], "trial": trial}, sort_keys=True).encode()).hexdigest()[:16], "known_days": 0,
        "basis": "calibration-2026-10-20"}, actor="mandel")
    save_registry(reg)
    print(tid, E["slug"])


if __name__ == "__main__":
    main()
