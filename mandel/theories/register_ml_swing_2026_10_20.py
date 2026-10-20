"""Pre-register T-578 (swing horizons on daily bars) and T-579 (feature correlation scan), before any model is fitted or
any correlation is computed (user request 2026-10-20: day-to-month buy and sell points, all correlations and inverse
relationships)."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

SWING_CLAIM = ("On daily bars, at least one cell (asset class x hold {1, 5, 20 trading days} x feature family {F0 price-free, "
               "F0+F1 other assets, F2 own past price, all} x model {ridge, gradient boosting} x rule {sign, cross-sectional "
               "long-short}) earns a positive mean net return on the sealed lockbox (2026-10-01 onward) AND a deflated Sharpe "
               ">= 0.95 over the 2026-01-01 to 2026-09-30 development walk-forward, counting every cell as a trial.")
SWING_TRIAL = {
    "statistic": "per cell: development net Sharpe on non-overlapping holds and its DSR over N = all cells; lockbox mean net per trade",
    "null": "no cell passes both the development DSR and the lockbox",
    "procedure": ("mandel.ml.swing: Yahoo 10-year daily bars for the Yahoo universe and Coinbase daily candles from 2017 for 30 coins; "
                  "a daily bar is known at its class's close (US equities and ETFs 16:00 ET, CME futures 17:00 ET, indices 16:15 ET, "
                  "FX and crypto stamp + 24 h) and features use only bars known at or before the asset's own close; target "
                  "log(open[i+1+h]/open[i+1]), entry at the next open, never an input; fit on target / (20-day vol x sqrt h); pooled "
                  "per class; monthly test blocks 2026-01..2026-09 (lockbox: 2026-10), training on all earlier history with rows "
                  "purged unless their target window ends before the block starts; hyperparameters as T-577; rule 'sign': trade the "
                  "sign when the predicted absolute return beats the round trip; rule 'xs' (classes with >= 10 symbols): at each "
                  "decision date long the top fifth and short the bottom fifth of predictions, equal weight, both legs costed; "
                  "evaluation on non-overlapping decisions (every h-th trading day); costs per side as T-577"),
    "data": "mandel/ml_data/bars/1d (local), finra-short-interest-*, fomc-meetings, macro-release-cpi",
    "min_n": 200,
    "pass": ("some cell with development DSR >= 0.95 (N = all cells) and a positive lockbox mean net return with >= 200 lockbox "
             "trades; 20-day cells cannot reach 200 lockbox trades before late 2026, so a 20-day survivor goes to a separately "
             "pre-registered forward paper record instead; any survivor becomes a forward paper test, never a live trade directly"),
    "controls": ("baselines on the same panels: sign of the trailing h-day return (time-series momentum) and its inverse "
                 "(reversal); family ablation; development is 2026 only, so every 2026 prediction comes from a model fitted on "
                 "earlier data; the T-577 lockbox date is shared and stays sealed"),
}

IC_CLAIM = ("Some (feature x asset class x interval-or-hold) triple whose mean rank correlation with the forward return is "
            "significant in a discovery period (Benjamini-Hochberg q < 0.05 over every triple scanned, positive or inverse) keeps "
            "its sign with one-sided p < 0.05 in a confirmation period the scan never saw.")
IC_TRIAL = {
    "statistic": "per triple: mean of period ICs (Spearman of feature vs forward return within each period), t over periods; BH q over all triples; confirmation-period mean IC and one-sided p in the discovered sign",
    "null": "no discovered triple is confirmed (under the null about 5% of discovered triples confirm by chance)",
    "procedure": ("mandel.ml.ic: intraday panels of T-577 (5-60 minute bars, h = 1 bar, period = trading day): discovery = "
                  "development (before 2026-10-01), confirmation = the lockbox (2026-10-01 onward), read once after T-577's "
                  "development is final; daily panels of T-578 (h = 1, 5, 20 days, period = calendar month): discovery = "
                  "2016-2025, confirmation = 2026-01..2026-09; features as defined in mandel.ml.features / mandel.ml.swing, "
                  "including the cross-asset (F1) lead-lag inputs; the sign is reported, so inverse relationships are scanned "
                  "on the same footing as positive ones"),
    "data": "the T-577 and T-578 panels",
    "min_n": 10,
    "pass": "at least one discovered triple confirmed; the confirmed fraction is reported against the 5% expected by chance",
    "controls": ("a correlation is not a trade: a confirmed triple only becomes a strategy through its own pre-registered "
                 "trading test with costs; periods are days or months so overlapping targets inside a period do not inflate t"),
}


def main():
    reg = json.load(open(REGISTRY))
    slugs = {t["slug"] for t in reg["theories"]}
    assert "ml-swing-horizons-v0" not in slugs and "ml-feature-ic-scan-v0" not in slugs
    out = []
    for slug, kind, claim, trial in (("ml-swing-horizons-v0", "ml-program", SWING_CLAIM, SWING_TRIAL),
                                     ("ml-feature-ic-scan-v0", "ml-program", IC_CLAIM, IC_TRIAL)):
        tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
        reg["theories"].append({"id": tid, "slug": slug, "kind": kind, "claim": claim,
                                "origin": ["user request 2026-10-20: day-to-month trader training program"], "trial": trial,
                                "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "", "results": [],
                                "notes": "pre-registered before any model was fitted or correlation computed; lockbox 2026-10-01 onward sealed."})
        Ledger().append("theory.preregistered", {"id": tid, "from": "user request", "hash": hashlib.sha256(json.dumps(
            {"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16], "known_days": 0,
            "basis": "ml-program-2026-10-20"}, actor="mandel")
        out.append(tid)
    save_registry(reg)
    print(" ".join(out))


if __name__ == "__main__":
    main()
