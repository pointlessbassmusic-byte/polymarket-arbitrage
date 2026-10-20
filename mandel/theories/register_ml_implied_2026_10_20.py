"""Pre-register T-580: options-implied variables as a fourth feature family for the swing models (T-578), before any
model with them is fitted or any of their correlations computed."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

CLAIM = ("Adding options-implied variables (family F3) to the T-578 swing models yields at least one cell (asset class x "
         "hold {1, 5, 20 days} x family {F0+F1+F3, all+F3} x model {ridge, gradient boosting} x rule {sign, cross-sectional}) "
         "with a development deflated Sharpe >= 0.95 counting every T-578 and T-580 cell as a trial AND a positive lockbox mean "
         "net return.")
TRIAL = {
    "statistic": "as T-578, per cell; plus the paired ablation: each F3 cell's IC and net Sharpe minus the same cell without F3",
    "null": "no F3 cell passes both the development DSR and the lockbox",
    "procedure": ("mandel.ml.implied + mandel.ml.swing --families F0F1F3,ALLF3: market-wide F3 = log VIX, VIX/VIX3M and VIX9D/VIX "
                  "term slopes, log VVIX, SKEW, COR1M implied correlation, DSPX dispersion, front VX future over VIX, the S&P "
                  "variance premium log(VIX daily / SPY 20-day realised), BTC perpetual funding over the last day; own F3 per "
                  "asset from its mapped implied-vol index (GVZ gold, OVX oil, VXTLT Treasuries, VXEEM emerging markets, VXN "
                  "Nasdaq and tech, RVX small caps, VXD Dow, VXAPL/VXGOG/VXAZN for AAPL/GOOGL/AMZN, Deribit DVOL for BTC and ETH "
                  "and BTC's for other coins, VIX otherwise): log level, 5-day change, implied over own 20-day realised; every "
                  "value enters at its archived available_at (Cboe 21:30 UTC, DVOL the next day) and only if known by the "
                  "asset's own close; everything else exactly as T-578"),
    "data": "cboe-*-history, cboe-vx-futures, deribit-dvol-*-history, deribit-funding-BTC-PERPETUAL, plus the T-578 data",
    "min_n": 200,
    "pass": ("some F3 cell with development DSR >= 0.95 (N = T-578 + T-580 cells) and a positive lockbox mean net return with "
             ">= 200 lockbox trades (the implied histories are refreshed before the lockbox is read); a survivor becomes a "
             "separately pre-registered forward paper test"),
    "controls": ("paired ablation against the identical T-578 cell without F3; the F3 correlation rows are scanned with the "
                 "T-579 method as their own Benjamini-Hochberg family (discovery 2016-2025, confirmation 2026-01..09); "
                 "single-stock implied vol exists only for AAPL, GOOGL and AMZN, so the rest of the stock class maps to VXN or VIX"),
}


def main():
    reg = json.load(open(REGISTRY))
    assert "ml-implied-family-v0" not in {t["slug"] for t in reg["theories"]}
    tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
    reg["theories"].append({"id": tid, "slug": "ml-implied-family-v0", "kind": "ml-program", "claim": CLAIM,
                            "origin": ["user request 2026-10-20: Greeks / options pricing / derivative variables in the trainer"],
                            "trial": TRIAL, "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "",
                            "results": [], "notes": "pre-registered before any F3 model was fitted; lockbox 2026-10-01 onward sealed."})
    Ledger().append("theory.preregistered", {"id": tid, "from": "user request", "hash": hashlib.sha256(json.dumps(
        {"claim": CLAIM, "trial": TRIAL}, sort_keys=True).encode()).hexdigest()[:16], "known_days": 0,
        "basis": "ml-program-2026-10-20"}, actor="mandel")
    save_registry(reg)
    print(tid)


if __name__ == "__main__":
    main()
