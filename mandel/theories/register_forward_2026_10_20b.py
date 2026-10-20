"""Pre-register the 2026-10-20 forward tests: two shadow records of the batch-8 HMMs (T-565, T-566; nothing traded)
and the widened asset sleeves (T-567 pre-holiday IWM, T-568 GLD/TLT/USO put spreads; paper, holds up to 30 days).
Forward only: every outcome is recorded after its registration."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

NEW = [
    dict(slug="putwrite-hmm-regime-forward-shadow", kind="options-strategy", parent="T-561",
         claim="From the 2026-10 month-end to the 2029-09 month-end, Cboe PUT held only in months after a month-end at which the frozen S&P HMM (shadow_params.json, fitted through 2026-09-30, filtered over SPY daily returns) gives P(high-volatility) below 0.5, T-bills otherwise, has a maximum drawdown at least 30% smaller than always holding PUT, and its annualised excess-return Sharpe ratio is no more than 0.05 below always-PUT's.",
         trial=dict(statistic="maximum drawdown reduction vs always-PUT; Sharpe difference of monthly excess returns (point estimates)",
                    null="reduction < 30% or Sharpe difference < -0.05",
                    procedure="mandel.live.shadow records P(high) after every close on the Linode; the last recorded session of each month is that month's decision (a month without a recorded last session counts as 'in'); PUT monthly returns from the captured cboe-PUT-history, filled at the next session's close, DTB3 when out, 2 bps per switch (T-551's construction)",
                    data="state/capture/shadow.jsonl (Linode), cboe-PUT-history, fred-DTB3",
                    min_n=36,
                    pass_="reduction >= 30% and Sharpe difference >= -0.05 over the 36 months; inconclusive when always-PUT's drawdown in the window is under 5% (nothing to reduce)",
                    controls="parameters frozen before the window (no refit); point estimates because 36 months cannot bound a Sharpe difference; SPY stands in for ^GSPC in the filter (the model was fitted on ^GSPC); the 10-month SMA filter on the same months is reported"),
         blocked="36 month-end decisions recorded forward (first: 2026-10)",
         why="T-561 cut putwriting's drawdown by 70% (null p 0.0002) but could not bound its Sharpe cost; a forward record decides it without reusing the fitted history"),
    dict(slug="qqqm-overnight-hmm-scaling-forward-shadow", kind="underlying-strategy", parent="T-562",
         claim="Over T-559's first 250 paper sessions, weighting each night's QQQM overnight-slot return by the frozen QQQ HMM's weight w = min(1, s*/s_f) recorded at that close raises the annualised Sharpe ratio of the slot's net returns (paired 95% lower bound of the difference > 0).",
         trial=dict(statistic="Sharpe(w x r) - Sharpe(r) over nights the slot held QQQM; r = the slot's net return from T-559's paper fills (buy at the close auction, sell at the next open auction)",
                    null="difference <= 0",
                    procedure="w from the shadow line of the same close (mandel.live.shadow, frozen params); r from T-559's journal fills; paired studentized circular block bootstrap, 10-night blocks",
                    data="state/capture/shadow.jsonl (Linode), the paper journal (paper/journal branch)",
                    min_n=200,
                    pass_="paired 95% lower bound of the Sharpe difference > 0",
                    controls="the scaling is not traded (T-559 is not changed mid-test); QQQ was the ETF on which T-562 passed in sample, so only a forward record is evidence; nights with no shadow line are dropped and counted"),
         blocked="200 shadow-weighted overnight nights of T-559 fills",
         why="T-562's in-sample QQQ improvement (+0.21 Sharpe, CI +0.05 to +0.39) applies to the sleeve's QQQM slot; the shadow decides it without touching the running test"),
    dict(slug="pre-holiday-iwm-paper", kind="underlying-strategy", parent="T-349",
         claim="On Alpaca paper, buying IWM at the closing auction of the session before each pre-holiday session and selling at the pre-holiday session's closing auction earns a positive mean net return per event, with closing-auction fills within 1.5 bps a side of the official close.",
         trial=dict(statistic="(a) mean |fill - official close| per side, bps; (b) mean net return per event",
                    null="(a) > 1.5 bps a side; (b) mean <= 0",
                    procedure="mandel.live.wide (pinned commit), capital MANDEL_WIDE_CAPITAL x 0.40, whole shares, never borrowing; official closes from daily-history-IWM; every decision journalled before the auction",
                    data="the widened-sleeve journal (Linode), daily-history-IWM",
                    min_n=27,
                    pass_="(a) decided at 10 events; (b) decided at 27 events (about three years): mean net > 0",
                    controls="T-349 passed at p 0.048 with a 95% CI including 0 and a weak first half (+2.6 bps); the forward record is the replication; early-close pre-holiday sessions are traded at their own close"),
         blocked="27 pre-holiday events traded on paper",
         why="the one supported calendar rule Alpaca can trade that the calendar sleeve does not already hold; a one-day hold"),
    dict(slug="multi-asset-put-spreads-paper", kind="options-strategy", parent="T-560",
         claim="On Alpaca paper, one defined-risk put credit spread per underlying on GLD (5-point), TLT (2-point) and USO (2-point), short strike the highest at or below 95% of spot on the 30-45 DTE standard monthly expiry, closed at 50% of the credit or at 21 DTE, earns a positive mean P&L per spread after fills, with no spread losing more than its declared max loss.",
         trial=dict(statistic="mean P&L per spread (dollars, after fills and fees); fill vs quoted mid at entry and exit",
                    null="mean P&L per spread <= 0",
                    procedure="mandel.live.wide (pinned commit); every plan, order, rejection and fill journalled before outcomes; bootstrap over spreads clustered by expiry month",
                    data="the widened-sleeve journal and spread-*.json (Linode)",
                    min_n=36,
                    pass_="after 36 closed spreads: mean P&L > 0 with the expiry-clustered 95% lower bound > 0 and no spread beyond its max loss; execution: mean fill within the quoted half-spread",
                    controls="basis: each asset's implied variance exceeds realised (T-50/T-244/T-271, T-64, T-63/T-512); the spread form is not backtested; ETF options are American (exit at 21 DTE limits assignment); no trend filter (T-551 inconclusive); the HMM shadow (T-565) is reported beside it"),
         blocked="36 closed spreads on paper",
         why="the variance premium is supported on gold, Treasuries and crude; defined-risk spreads put it within a small account's reach and hold 9-24 days"),
]


def _hash(claim, trial):
    return hashlib.sha256(json.dumps({"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16]


def main():
    reg = json.load(open(REGISTRY))
    slugs = {t["slug"] for t in reg["theories"]}
    nxt = max(int(t["id"][2:]) for t in reg["theories"]) + 1
    led = Ledger()
    for e in NEW:
        assert e["slug"] not in slugs, e["slug"]
        tid = f"T-{nxt}"; nxt += 1
        tr = dict(e["trial"]); tr["pass"] = tr.pop("pass_")
        trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        reg["theories"].append({"id": tid, "slug": e["slug"], "kind": e["kind"], "claim": e["claim"],
                                "origin": [e["parent"], "forward tests 2026-10-20 (shadow HMMs, widened asset sleeves)"],
                                "trial": trial, "experiments": [], "testable_now": False, "status": "blocked",
                                "blocked_on": e["blocked"], "results": [],
                                "notes": f"pre-registered forward test (parent {e['parent']}) on 2026-10-20: {e['why']}."})
        led.append("theory.preregistered", {"id": tid, "from": e["parent"], "hash": _hash(e["claim"], trial),
                                            "known_days": 0, "basis": "forward-2026-10-20b"}, actor="mandel")
        print(tid, e["slug"])
    save_registry(reg)


if __name__ == "__main__":
    main()
