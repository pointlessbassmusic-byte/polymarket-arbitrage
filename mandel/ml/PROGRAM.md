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
