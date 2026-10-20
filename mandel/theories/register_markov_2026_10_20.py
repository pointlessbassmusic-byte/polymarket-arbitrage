"""Pre-register the 2026-10-20 Markov-model tests: four places where a Markov state model may change a decision Mandel
or a child already makes (a regime filter for putwriting, regime-scaled sizing and state-conditioned entry for the
overnight sleeve, and a state-based exit for the crypto child's bounce-short). Every model is fitted on data strictly
before the decision it informs and read through its FORWARD-FILTERED state probability (a smoothed / Viterbi path uses
the future and is not used). Each parent's verdict is untouched."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

BASIS = "markov-models-2026-10-20 (user request: where a Markov state model can change a decision in Mandel's or the children's strategies)"

HMM = ("a two-state Gaussian hidden Markov model of daily log returns (means, variances and the 2x2 transition matrix fitted "
       "by EM, 200 iterations max, tolerance 1e-8, initialised from the 20th / 80th percentile of rolling 21-day variance), "
       "refitted every January 1 on all returns strictly before it; the high-volatility state is the one with the larger "
       "variance; on each day the forward-filtered probability of that state given returns through that day's close")

NEW = [
    dict(slug="putwrite-hmm-regime-filter", kind="options-strategy", parent="T-551", testable=True,
         claim="Over the Cboe PUT index's continuous daily history to 2026-09, PUT held only in months after a month-end at "
               "which the forward-filtered probability of the high-volatility state of a two-state Gaussian HMM on ^GSPC daily "
               "returns (refitted each January on all prior returns from 1990) is below 0.5, T-bills otherwise, reduces the "
               "maximum drawdown by at least 30% against always holding PUT, with the matched random-timing null p < 0.05 "
               "and the excess-return Sharpe difference's 95% lower bound above -0.05.",
         trial=dict(statistic="maximum-drawdown reduction vs always-PUT; matched random-timing null p; paired Sharpe difference of monthly excess returns",
                    null="reduction < 30%, or null p >= 0.05, or the Sharpe difference's 95% lower bound <= -0.05",
                    procedure="T-551's construction unchanged (month-end decision, fill at the next session's close, DTB3 when out, 2 bps per switch, the matched null re-placing the rule's own out-of-market spells, 10,000 paths; paired studentized CBB Sharpe difference, 12-month blocks) with the SMA signal replaced by: in = P(high-vol | ^GSPC returns through the month's last session) < 0.5, " + HMM + "; training from 1990-01-02; T-551's 10-month SMA filter on the same months is reported beside it",
                    data="cboe-PUT-history, daily-history--GSPC, fred-DTB3",
                    min_n=200,
                    pass_="reduction >= 30% with null p < 0.05 and the Sharpe difference's 95% lower bound > -0.05",
                    controls="min_n is 200 because the continuous PUT history holds ~230 months (T-551 was capped at 236 of 300); filtered, never smoothed, probabilities; the 0.5 cut is the only threshold (no grid); the SMA filter's numbers on the same months are reported, not a criterion"),
         why="T-551's trend filter is a crude regime detector; a volatility-state model targets the regime in which putwriting loses (persistent high volatility) directly"),
    dict(slug="overnight-hmm-vol-scaled", kind="underlying-strategy", parent="T-549", testable=True,
         claim="On QQQ and IWM from 2003-01 to 2026-09, scaling the overnight-only holding (buy the close, sell the next open, "
               "1 bp per side on the position) by w = min(1, s* / s_f), where s_f is the one-day-ahead volatility forecast of a "
               "two-state Gaussian HMM on the ETF's own daily close-to-close returns (refitted each January on all prior "
               "returns) and s* the median in-sample forecast at the last refit, raises the annualised Sharpe ratio of net "
               "overnight returns for both ETFs (paired 95% lower bound of the Sharpe difference > 0).",
         trial=dict(statistic="annualised Sharpe(scaled net overnight) - Sharpe(unscaled net overnight), per ETF, paired studentized circular block bootstrap (20-day blocks)",
                    null="Sharpe difference <= 0 for either ETF",
                    procedure="T-549's overnight return (Yahoo open, dividends on ex-date nights; batch7_cal.night_day); the weight for the night after close t uses returns through close t only: one-step-ahead state probabilities = filtered probabilities x transition matrix, s_f = sqrt(sum_k p_k sigma_k^2); " + HMM + "; training from each ETF's first bar (QQQ 1999-03, IWM 2000-05); costs 1 bp per side times the weight",
                    data="daily-history-QQQ, daily-history-IWM",
                    min_n=2500,
                    pass_="for both ETFs the paired 95% lower bound of the Sharpe difference > 0",
                    controls="no leverage (w <= 1), so the test is whether cutting exposure in the high-volatility state raises risk-adjusted return; the unscaled leg is T-549's own series; mean return per day of both legs is reported"),
         why="volatility-state sizing usually raises the Sharpe ratio of short-horizon equity returns without changing the signal; it is the Markov use that applies to every slot of the calendar sleeve (T-559)"),
    dict(slug="overnight-markov-state-conditioned", kind="underlying-strategy", parent="T-549", testable=True,
         claim="On QQQ and IWM from 2003-01 to 2026-09, holding overnight only when the expanding-window mean overnight return "
               "following the current four-state Markov state (sign of the day's intraday return x sign of the previous "
               "overnight return) exceeds the 2 bp round trip earns a higher mean net return per day than holding every night "
               "(both ETFs, Holm-adjusted p < 0.05).",
         trial=dict(statistic="mean over days of (conditioned net overnight return, 0 when out) - (unconditioned net overnight return), per ETF",
                    null="difference <= 0",
                    procedure="state at close t = (sign of open-to-close return of day t, sign of the overnight return into day t); the state's mean next-overnight return estimated on all (state, next-night) pairs strictly before t (at least 250 per state, else hold); studentized circular block bootstrap (20-day blocks); Holm over the two ETFs",
                    data="daily-history-QQQ, daily-history-IWM",
                    min_n=2500,
                    pass_="for both ETFs difference > 0 with Holm p < 0.05",
                    controls="the expected outcome is no gain (the overnight and IBS rules already use the day's state); registered because it is cheap and decides whether a return-state chain adds anything to the calendar sleeve; time in market reported"),
         why="the simplest Markov chain over daily return states; if it adds nothing, return-state chains are dropped from the calendar sleeve"),
    dict(slug="bounce-short-markov-exit", kind="underlying-strategy", parent="T-556", testable=True,
         claim="On T-556's DOGE-USD and SHIB-USD bounce-short trades (signal candles 2021-01..2026-09, next-open entry, the same "
               "stop, target and 14-day cap), additionally exiting at the next open once the coin's three-state Markov chain "
               "(daily return terciles) predicts a positive next-day return from the current state raises the mean net return "
               "per trade (paired, month-clustered 95% CI of the difference above 0, both coins positive).",
         trial=dict(statistic="mean paired difference per trade: net(Markov exit) - net(T-556 fixed exit), with T-556's costs and funding",
                    null="mean difference <= 0",
                    procedure="per coin, terciles of daily close-to-close returns and the state-conditional mean next-day return estimated on all bars strictly before the entry day (at least 120); on each close k from the entry day on, state = tercile of that day's return; when the conditional mean next-day return of that state > 0 the short is closed at the open of k+1 (if k+1 is within the 14-day window); stop and target checked first on every bar as in T-556; month-clustered studentized bootstrap",
                    data="coinbase-daily-DOGE-USD, coinbase-daily-SHIB-USD",
                    min_n=60,
                    pass_="month-clustered 95% CI of the mean paired difference excludes 0 on the positive side and both coins' mean difference > 0",
                    controls="same trades, entries, costs and funding as T-556 (paired); the exits were chosen by the child's search (4,512 trials), so a model-based exit is tested rather than another grid; the hold length of both rules reported"),
         why="the user asked whether hold / exit timing rather than the signal is what limits a rule; a Markov state model predicts the next day's drift from the current state without a parameter search"),
]


def _hash(claim: str, trial: dict) -> str:
    return hashlib.sha256(json.dumps({"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16]


def main() -> None:
    reg = json.load(open(REGISTRY))
    ids = {t["id"] for t in reg["theories"]}
    slugs = {t["slug"] for t in reg["theories"]}
    nxt = max(int(i[2:]) for i in ids) + 1
    led = Ledger()
    for e in NEW:
        assert e["slug"] not in slugs, e["slug"]
        tid = f"T-{nxt}"; nxt += 1
        tr = dict(e["trial"]); tr["pass"] = tr.pop("pass_")
        trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        t = {"id": tid, "slug": e["slug"], "kind": e["kind"], "claim": e["claim"], "origin": [e["parent"], BASIS],
             "trial": trial, "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "", "results": [],
             "notes": f"pre-registered Markov-model test (parent {e['parent']}) on 2026-10-20: {e['why']}."}
        reg["theories"].append(t)
        led.append("theory.preregistered", {"id": tid, "from": e["parent"], "hash": _hash(t["claim"], trial),
                                            "known_days": 0, "basis": "markov-models-2026-10-20"}, actor="mandel")
        print(tid, e["slug"])
    save_registry(reg)


if __name__ == "__main__":
    main()
