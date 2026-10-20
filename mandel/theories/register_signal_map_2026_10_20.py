"""Pre-register batch 9: three tests drawn from the signal map (mandel/viz/graph.json) — its most-supported concepts
with no market test, each tied to a decision a live sleeve makes. Registered before any of them is run."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

BASIS = "signal map 2026-10-20 (concepts with source support and no market test; the map's Markov-vs-multifractal tension)"
NEW = [
    dict(slug="msm-vs-hmm-variance-forecast", kind="volatility", parent="k:markov/k:multifractal tension",
         claim="For SPY, QQQ and IWM daily log returns 2003-01 to 2026-09, the one-day-ahead variance forecast of a k=4 binomial Markov-switching multifractal model has a lower mean QLIKE loss than a two-state Gaussian HMM's, both refitted every January on all prior returns, for all three ETFs (Holm-adjusted p < 0.05).",
         trial=dict(statistic="mean of QLIKE(HMM) - QLIKE(MSM) per day, QLIKE = r^2/h + log h", null="mean difference <= 0",
                    procedure="mandel.experiments.batch9_signal: one-step predicted variances (no smoothing); studentized circular block bootstrap, 20-day blocks; Holm over 3 ETFs",
                    data="daily-history-SPY, daily-history-QQQ, daily-history-IWM", min_n=5000,
                    pass_="all three ETFs: difference > 0 with Holm p < 0.05",
                    controls="the map's tension between discrete Markov regimes and continuous multifractal roughness, decided on forecast loss; the winner sizes T-562 / T-566-style scaling"),
         why="the signal map's tension between discrete regimes (11, 13) and multifractal roughness (A4) had no test; the better variance model is the one to size the sleeves with"),
    dict(slug="ibs-reversal-by-hurst-regime", kind="underlying-strategy", parent="k:fractal_dimension/T-332",
         claim="On SPY, QQQ and IWM 2003-01 to 2026-09, IBS < 0.2 closes followed to the next close earn more when the DFA Hurst exponent of the trailing 250 daily log returns is below 0.5 than when it is 0.5 or above (pooled difference > 0, p < 0.05, both halves positive).",
         trial=dict(statistic="pooled mean next-day return of IBS trades with H < 0.5 minus those with H >= 0.5", null="difference <= 0",
                    procedure="mandel.experiments.batch9_signal; H from scaling.hurst_dfa on log adjclose through the signal close; studentized circular block bootstrap (20 trades) of the signed contributions; halves by trade order",
                    data="daily-history-SPY, daily-history-QQQ, daily-history-IWM", min_n=1000,
                    pass_="difference > 0 with p < 0.05 and both halves positive",
                    controls="a reversal should pay more when the series is anti-persistent; the IBS rule itself is T-332/T-558; one threshold (0.5), no grid"),
         why="the map's 'fractal dimension / roughness' concept (28.6 support, one parked theory) applied to the calendar sleeve's IBS slot"),
    dict(slug="calendar-sleeve-half-kelly-weights", kind="underlying-strategy", parent="k:kelly/T-559",
         claim="From 2006-01 to 2026-09, weighting the calendar sleeve's three slots (overnight QQQ, IBS SPY, turn-of-month SPY, 1 bp a side) by half-Kelly weights re-estimated each month on all prior daily returns (long-only, no leverage) gives a higher mean daily log growth than the fixed 0.40 / 0.30 / 0.30 weights (paired p < 0.05, both halves positive).",
         trial=dict(statistic="mean daily log growth, Kelly-weighted minus fixed-weight sleeve", null="difference <= 0",
                    procedure="mandel.experiments.batch9_signal; w = 0.5 inv(Sigma) mu clipped at 0 and scaled to sum 1 when above 1; studentized circular block bootstrap, 20-day blocks",
                    data="daily-history-SPY, daily-history-QQQ", min_n=4000,
                    pass_="difference > 0 with p < 0.05 and both halves positive",
                    controls="the map's tension 'edge in bits as the Kelly growth rate versus never full Kelly on an estimated edge' (half Kelly, estimated only from the past); T-345's month-end skip is left out of both legs"),
         why="the map's Kelly / bet-sizing concept had one blocked theory; the sleeve's 40/30/30 split was a judgement call"),
]


def _hash(c, t):
    return hashlib.sha256(json.dumps({"claim": c, "trial": t}, sort_keys=True).encode()).hexdigest()[:16]


def main():
    reg = json.load(open(REGISTRY))
    slugs = {t["slug"] for t in reg["theories"]}
    nxt = max(int(t["id"][2:]) for t in reg["theories"]) + 1
    led = Ledger()
    for e in NEW:
        assert e["slug"] not in slugs
        tid = f"T-{nxt}"; nxt += 1
        tr = dict(e["trial"]); tr["pass"] = tr.pop("pass_")
        trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        reg["theories"].append({"id": tid, "slug": e["slug"], "kind": e["kind"], "claim": e["claim"], "origin": [e["parent"], BASIS],
                                "trial": trial, "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "",
                                "results": [], "notes": f"pre-registered from the signal map on 2026-10-20: {e['why']}."})
        led.append("theory.preregistered", {"id": tid, "from": e["parent"], "hash": _hash(e["claim"], trial), "known_days": 0,
                                            "basis": "signal-map-2026-10-20"}, actor="mandel")
        print(tid, e["slug"])
    save_registry(reg)


if __name__ == "__main__":
    main()
