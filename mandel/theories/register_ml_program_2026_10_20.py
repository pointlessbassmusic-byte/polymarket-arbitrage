"""Pre-register T-577, the intraday-to-monthly learning program (user request 2026-10-20), before any model is fitted."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

CLAIM = ("Across the learning program's cells (asset class x bar interval {5, 15, 30, 45, 60 min} x feature family {F0 "
         "price-free, F0+F1 with other assets, F2 own past price, F0+F1+F2} x model {ridge, gradient boosting}), at least "
         "one cell's walk-forward predictions, traded by the pre-declared rule net of the pre-declared costs, earn a "
         "positive mean net return on the sealed lockbox (2026-10-01 onward) AND a deflated Sharpe ratio >= 0.95 over the "
         "development period counting every cell as a trial.")
TRIAL = {
    "statistic": "per cell: development-period net Sharpe (annualised) of the trading rule and its DSR over N = number of cells; lockbox mean net return per trade for the cells that pass development",
    "null": "no cell passes both the development DSR and the lockbox",
    "procedure": ("mandel.ml (fetch, features, train): bars from Coinbase (crypto 5-min, 2026-01-01 on) and Yahoo (5-min, last 60 days) "
                  "for ~115 symbols in 8 asset classes; features only from bars closed at or before the decision bar's close and slow "
                  "data only once published (FINRA short interest by available_at); target = log(open[i+1+h]/open[i+1]) with h = 1 bar, "
                  "never an input; targets divided by trailing 48-bar volatility for fitting; pooled per asset class; walk-forward with "
                  "weekly test blocks, an expanding training window and a 1-day embargo; model hyperparameters fixed in advance (ridge "
                  "alpha 10; LightGBM 200 trees, 31 leaves, learning rate 0.05, min 200 rows per leaf); trading rule: at each decision bar take "
                  "the sign of the prediction when the predicted absolute return exceeds the round-trip cost, hold h bars, one position "
                  "per symbol; costs per side: crypto 4 bp (perp taker), stocks 2 bp, ETFs 1 bp, futures 1 bp, FX 1 bp, index none (not traded)"),
    "data": "mandel/ml_data/bars (local, Coinbase and Yahoo), finra-short-interest-*, fomc-meetings, macro-release-cpi",
    "min_n": 1000,
    "pass": "some cell with development DSR >= 0.95 (N = all cells) and a positive lockbox mean net return with at least 200 lockbox trades; such a cell becomes a separately pre-registered forward paper test, never a live trade directly",
    "controls": ("lockbox evaluated once, only for cells that pass development; family ablation reported (does anything beyond own price carry information); "
                 "zero-prediction and sign-of-last-return baselines reported; Yahoo's 60-day window limits equities/futures/FX to ~40 sessions here, "
                 "the same code runs on the Linode on Alpaca's 2026 history (stage B, a separate record); options Greeks/IV and earnings dates are "
                 "not in v0 (no free 2026 intraday history): added forward from the capture box"),
}


def main():
    reg = json.load(open(REGISTRY))
    assert "ml-learning-program-v0" not in {t["slug"] for t in reg["theories"]}
    tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
    reg["theories"].append({"id": tid, "slug": "ml-learning-program-v0", "kind": "ml-program", "claim": CLAIM,
                            "origin": ["user request 2026-10-20: day-to-month trader training program"], "trial": TRIAL,
                            "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "", "results": [],
                            "notes": "pre-registered before any model was fitted; lockbox 2026-10-01 onward sealed."})
    Ledger().append("theory.preregistered", {"id": tid, "from": "user request", "hash": hashlib.sha256(json.dumps(
        {"claim": CLAIM, "trial": TRIAL}, sort_keys=True).encode()).hexdigest()[:16], "known_days": 0,
        "basis": "ml-program-2026-10-20"}, actor="mandel")
    save_registry(reg)
    print(tid)


if __name__ == "__main__":
    main()
