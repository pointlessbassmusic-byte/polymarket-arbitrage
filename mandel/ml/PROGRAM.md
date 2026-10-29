# The day-to-month learning program (T-577)

Goal: learn, from data a bot would have had in real time, when to buy and sell each asset over 5-minute to 30-day
windows, and turn whatever survives into new pre-registered strategies for the widened sleeve.

## The rules that keep it honest

1. **Point in time.** A bar is known only at its close. Every feature at decision bar i uses bars closed at or before
   i; slow data (short interest, filings) only from its publication time; calendars only for events scheduled in
   advance. `tests/test_mandel_ml_leakage.py` shocks every bar after i and fails if any feature at i moves.
2. **Isolated target.** The thing being predicted, log(open[i+1+h] / open[i+1]), is never an input and is never used to
   build an input. Entry is at the next bar's open, so the decision bar's own close is not a free fill.
3. **Price kept apart.** Features come in families scored separately: F0 price-free (volume, dollar volume, time-of-day
   volume profile, calendar, short interest), F1 other assets (leaders' past returns), F2 own past price. The ablation
   says whether anything besides an asset's own price history carries information.
4. **Walk-forward only.** Expanding training window, weekly test blocks, 1-day embargo; hyperparameters fixed before
   any run; normalisations fitted on the training fold.
5. **Every cell is a trial.** Asset class x interval x family x model; the deflated Sharpe counts them all.
6. **Sealed lockbox.** 2026-10-01 onward is dropped before anything is built and opened once, for development
   survivors only. A survivor becomes a separately pre-registered forward paper test, never a live trade.
7. **Costs per asset class**, charged on every trade (crypto perps 4 bp a side, stocks 2, ETFs / futures / FX 1).

## Stage A (this repository, v0)

- Crypto: 30 Coinbase products, 5-minute bars from 2026-01-01 (aggregated to 15/30/45/60).
- Stocks, ETFs (equity, sector, bond, commodity), futures, FX, VIX, 10-year yield: Yahoo 5-minute bars, last 60
  days (Yahoo's limit); 60-minute bars for two years as context.
- Daily context: FINRA short interest (by publication time), FOMC and CPI dates.

### T-578: swing holds (`python -m mandel.ml.swing`)

Day-to-month: 10 years of daily bars (Yahoo; Coinbase from 2017), holds of 1, 5 and 20 trading days, monthly test
blocks through 2026 with every model fitted only on rows whose outcome was realised before the block (purged), and
two trading rules: the sign rule of T-577 and a cross-sectional rule (long the top fifth of predictions, short the
bottom fifth) for classes with at least 10 symbols. Holds are scored on a non-overlapping date grid. A daily bar is
known at its class's close (stocks 16:00 ET, CME futures 17:00 ET, indices 16:15 ET, FX and crypto stamp + 24 h) and
other assets enter only once known by the asset's own close.

### T-579: correlation and inverse-relationship scan (`python -m mandel.ml.ic`)

Every feature against the forward return, per asset class and interval or hold: the rank correlation inside each
period (a trading day intraday, a month on daily bars), its mean and t over periods, Benjamini-Hochberg over every
triple. Discoveries are checked in their own sign on periods the scan never saw (intraday: the lockbox, read once;
daily: 2026 after discovery on 2016-2025). Inverse relationships are scanned on the same footing as positive ones. A
correlation is not a trade.

## Stage B (the Linode, after stage A)

The same code on Alpaca's 2026 history (stocks and ETFs, 5-minute, Jan-Oct 2026, the full market feed for data older
than 15 minutes) and the capture box's forward data (option chains, Greeks, implied volatility, put/call volume).
Results only are pushed; the bars stay on the box.

## What else the program should add (in order of expected value)

1. **Triple-barrier labels and meta-labelling.** Predict whether a take-profit or a stop is hit first within N bars,
   and train a second model that decides whether to act on a primary signal (de Prado). Matches "optimal buy and sell
   points" better than a fixed-horizon return and lets the existing rules (IBS, overnight, turn of month) be the primary
   signals, with the model only filtering them.
2. **Options-implied features (forward, from the capture box):** implied volatility level and term slope, 25-delta
   skew, put/call volume and open interest, dealer gamma exposure, and the implied-minus-realised variance spread. The
   variance premium is Mandel's best-supported effect; using it as a conditioning variable is the natural next step.
3. **Event calendars:** earnings dates (from SEC filing history), options expiry and index rebalance days, Treasury
   auctions (archived), month-end (T-574/T-576), pre-holiday (T-567).
4. **Order flow and microstructure:** signed volume from trade prints (Kraken and Coinbase trades are public),
   spreads, trade counts, the queue model Kelly is testing.
5. **Crypto derivatives state:** perpetual funding, basis, open interest (Kalshi / Coinbase / Deribit), with the
   funding-carry findings as priors.
6. **Regime conditioning:** the daily-calibrated volatility models (EWMA first, per the T-569/T-572 reviews) as inputs
   and as position sizers, not as signals.
7. **Probability calibration and conformal intervals** on every prediction, so position size follows the calibrated
   edge (fractional Kelly at a checkpoint, never daily retuning).
8. **Drift monitoring:** the daily calibration job extended to every deployed model (feature drift, prediction
   drift, realised hit rate against the backtest's band).
9. **Cross-sectional ranking** within an asset class (long the top decile of predicted return, short the bottom),
   which removes the market's own direction and is usually where intraday models earn whatever they earn.

## Re-weighting check, 2026-10-29

The IC scan's 2,254 feature x class x horizon triples (2,135 with a confirmation read) were re-aggregated under five
weightings: discovery share, confirmation share among discovered, sign stability (|t| > 1 both sides, same sign),
confirmation-n-weighted |IC|, and the share with disc_t x conf_t > 1. What is stable across all five:

- **Horizon:** 5d and 20d, then 1d; every intraday horizon ranks below every daily one on every weighting.
- **Family:** F2 (technical/price-path) and F3 (options-implied) tie, F1 (cross-asset) close, F0 (volume) last by a wide
  margin under every weighting (F0 confirmation share 0.08).
- **Class:** `future` and `bond_etf` are top-3 under four of five weightings; bond ETFs carry the largest confirmation
  ICs in the scan (TLT trailing 20-day return, inverse, IC -0.40 to -0.44, t -3.9 to -7.3; 10-year-yield trailing
  20-day change, positive, IC +0.31 to +0.46, t 3.6 to 7.0; 8-9 confirmation periods). The bond-ETF cross-section
  is roughly one factor (duration), so these ICs are a time-series duration call with high |IC| and little breadth; the
  swing program's bond_etf trading cells at h = 20 (9 periods, 52-63 trades) reached SR 0.8-1.9 but DSR <= 0.03
  against 306 trials and could not decide anything. Registered as a single pre-discovery replication, T-743
  (2002-07..2023-12, TLT and IEF, both readings under rule 11).
- **Relationship type:** inverse relationships keep their sign on the confirmation periods 73% of the time (n 1,262),
  positive ones 59% (n 873): the reversal structure T-579 found is the stable part of the scan.

Nothing here reverses T-577/T-578/T-580: the re-weighting ranks where signal concentrates, not whether it pays a taker.
