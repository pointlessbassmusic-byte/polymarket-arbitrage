"""Pre-register the 2026-10-20 salvage successors: variants that keep the part of a failed or half-passing model that
measured something (gross signal killed by costs, a robust risk-control component, a one-sided effect, a wrong-way
result, a better exit or instrument), each tested on data or a period its parent did not use, or forward only.
The parents' verdicts are untouched; nothing here is evidence for the successors, only the reason to register them."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

SALVAGE = "salvage audit 2026-10-20 (every not_supported / inconclusive / parked record re-read for the part that measured something)"

NEW = [
    dict(slug="kalshi-kxbtcd-vs-deribit-digital", kind="underlying-strategy", parent="T-337", testable=True,
         claim="On Kalshi KXBTCD daily 5 pm ET 'Bitcoin above' markets from 2025-01 to 2026-10, buying the side whose executable price is at least 5 points below the Deribit-implied risk-neutral digital (point-in-time smile fitted on near-expiry Deribit trades, T-337's SmileBook) and holding to settlement earns a positive mean net return per contract after Kalshi's taker fee 0.07 x P x (1-P) and a 1-point model haircut.",
         trial=dict(statistic="mean net P&L per contract in cents (first qualifying hour per market), with the market-clustered one-sided 95% lower bound",
                    null="mean net P&L per contract <= 0",
                    procedure="p_RN at each hourly mark H from T-337's SmileBook (SVI and cubic, forward = hourly-BTC-USD close at H); Kalshi side priced at the candle ending at H: buy YES at yes_ask when p_RN - yes_ask > 5 points + 1-point haircut, buy NO at 1 - yes_bid when (1 - p_RN) - (1 - yes_bid) > 5 + 1; valid two-sided book with spread <= 10 cents; settlement from kalshi-settled-markets result; one entry per market (the first qualifying hour); split by hours to close and by year; DSR over the declared 8 cells (threshold 5/10 x SVI/cubic x first/any qualifying hour)",
                    data="kalshi-candles-hourly-KXBTCD-<YYYY-MM>, kalshi-settled-markets-KXBTCD-<YYYY-MM>, deribit-option-trades-near-BTC-<YYYY-MM>, hourly-BTC-USD",
                    min_n=300,
                    pass_="one-sided 95% lower bound of the mean net P&L per contract > 0 under both SVI and cubic fits, same sign in 2025 and 2026, DSR >= 0.95 over the 8 cells",
                    controls="Kalshi candles exist only for the 4 most-traded strikes per event (selection reported); Kalshi settles on a 60-second BRTI average, Deribit on its own index (basis reported, no shift); fees per docs.kalshi.com fee rounding (ceil to 6 dp); motivation: T-337 on Polymarket failed because Polymarket's hourly mids at listing were placeholder values, which Kalshi's bid/ask candles do not have; the 2026-10-20 Kalshi quant pass found the Kalshi mid better calibrated than a spot + 30-day-RV model (following that model lost 5.8 cents), so this tests the option-implied model, not that one"),
         why="T-337's model (the Deribit digital) was never tested on a venue a US trader can use; Kalshi KXBTCD has the same payoff and bid/ask candles"),
    dict(slug="rvx-vix-narrow-spread-replication", kind="options-strategy", parent="T-237", testable=True,
         claim="From 2009-09 to 2026-09, after the 60-day z-score of RVX minus VIX falls below -2, the IWM-minus-SPY realised volatility spread over the next 21 trading days exceeds the entry RVX-minus-VIX spread on average (non-overlapping events).",
         trial=dict(statistic="mean of (RV_IWM - RV_SPY over the next 21 sessions) - (RVX - VIX at entry), vol points, over non-overlapping events",
                    null="mean <= 0",
                    procedure="z on the trailing 60 sessions of RVX - VIX (Cboe closes); an event at the first close with z < -2 after the previous event's 21-session hold ends; RV as annualised close-to-close log-return volatility of adjclose; studentized block bootstrap over events; halves; z-windows 40 and 120 reported",
                    data="cboe-RVX-history, cboe-VIX-history, daily-history-IWM, daily-history-SPY",
                    min_n=30,
                    pass_="mean > 0 with the 95% CI excluding 0, win rate > 0.6, both halves positive",
                    controls="random-entry placebo with the matched count; the unconditional implied-minus-realised spread; only the narrow side is claimed (pre-declared from T-237, where the wide side failed: -0.35 vol pts, CI -1.14 to +0.43); the VXN/QQQ events of T-237 are not used"),
         why="T-237 failed as a two-sided rule, but its narrow side alone was +1.75 vol pts (95% CI +1.13 to +2.46, win 0.79) and stable across z-windows; RVX/IWM is an independent pair"),
    dict(slug="crypto-alt-high-volume-premium", kind="underlying-strategy", parent="T-419", testable=True,
         claim="On the point-in-time top 50 Coinbase USD products by trailing 30-day dollar volume (stablecoins, wrapped and staked tokens excluded; BTC and ETH excluded because T-419 used them), 2019-2026, a top-decile idiosyncratic volume day without a 2-sigma price move is followed by a positive 10-day market-adjusted return after a 50 bp round trip.",
         trial=dict(statistic="mean 10-day return minus the equal-weight universe return, net of 50 bp, per event",
                    null="mean net <= 0",
                    procedure="volume surprise = log dollar volume minus its trailing 50-day mean, residualised on the universe's mean surprise; top decile among names that day, |return| < 2 trailing sigma; entry at the next UTC daily close, 10-day hold; date-clustered bootstrap; halves; placebo of random days per name",
                    data="coinbase-daily-<PID> (493 products), coinbase-products-<day>",
                    min_n=300,
                    pass_="date-clustered 95% CI of the mean net return excludes 0 on the positive side, placebo p < 0.05, both halves positive",
                    controls="point-in-time membership from the daily bundles (dead products included); the universe excludes the two names T-419 used; costs at 50 bp round trip as in T-419's crypto cell"),
         why="T-419 failed on its pooled ETF+crypto claim and deflation, but its crypto events alone were +378 bp over 460 events and its placebo p was 0.02; the altcoin universe is untouched data"),
    dict(slug="turn-of-month-country-etfs", kind="underlying-strategy", parent="T-344", testable=True,
         claim="Pooled over the 21 iShares country ETFs, 2000-01 to 2026-09, the mean daily return in the turn-of-month window (trading days -4 to +3, T-59's window) exceeds the mean on other days by at least 3 bps net of 2 bps per round trip, with both halves positive.",
         trial=dict(statistic="pooled mean daily return in the window minus outside it, net of 2 bps per monthly round trip",
                    null="difference <= 3 bps",
                    procedure="T-59's window and cost convention unchanged; equal-weight panel, date-clustered (month) block bootstrap; per-ETF signs reported",
                    data="daily-history-<country ETF> for the 21 iShares country ETFs of T-319/T-471",
                    min_n=200,
                    pass_="pooled difference >= 3 bps with one-sided p < 0.05, both halves positive, at least 60% of ETFs with a positive difference",
                    controls="none of these ETFs was used by T-59, T-344 or T-443; US-listed ETFs trade on the US calendar (the window is in NYSE sessions)"),
         why="T-344 replicated turn-of-month on IWM and BTC but not on 3 of 5 assets; an independent international panel tests whether the effect is a global month-end flow"),
    dict(slug="halloween-country-etfs", kind="underlying-strategy", parent="T-441", testable=True,
         claim="Pooled over the 21 iShares country ETFs, 2000-01 to 2026-09, the mean monthly return in November-April exceeds the mean in May-October, with both halves positive.",
         trial=dict(statistic="pooled mean monthly return Nov-Apr minus May-Oct",
                    null="difference <= 0",
                    procedure="month-end adjclose returns; equal-weight panel; block bootstrap by year; per-ETF differences reported",
                    data="daily-history-<country ETF> for the 21 iShares country ETFs",
                    min_n=200,
                    pass_="difference > 0 with one-sided p < 0.05, both halves positive, at least 60% of ETFs positive",
                    controls="Bouman and Jacobsen (2002) report the effect internationally; none of these ETFs was used by T-352/T-441 (^GSPC +40 bps/month, p 0.051)"),
         why="T-352/T-441 missed their 50 bp bar on ^GSPC (+40 bps, p 0.051) but the sign held post-publication; the international panel is independent data"),
    dict(slug="overnight-intraday-gap-qqq-iwm", kind="underlying-strategy", parent="T-348", testable=True,
         claim="On QQQ (1999-03 on) and IWM (2000-05 on) to 2026-09, the mean close-to-next-open return (dividends added back on ex-dates) exceeds the mean open-to-close return, the gap is positive in both halves, and holding only overnight (buy the close, sell the open) earns a positive mean return net of 1 bp per side.",
         trial=dict(statistic="mean overnight minus mean intraday return per day; mean net overnight-only return per day",
                    null="gap <= 0 or net overnight-only mean <= 0",
                    procedure="T-348's construction unchanged (Yahoo open, dividends on ex-date nights); studentized block-10 bootstrap; Holm over the two ETFs; Yahoo-open quality check against the first hourly bar on the 730-day overlap",
                    data="daily-history-QQQ, daily-history-IWM (dividends recovered from close / adjclose as in T-348), hourly-QQQ, hourly-IWM",
                    min_n=2500,
                    pass_="for both ETFs after Holm: gap > 0 with p < 0.05, both halves positive, and net overnight-only mean > 0 with p < 0.05",
                    controls="SPY (T-348) is not used; costs are the MOC/MOO half-spreads (1 bp per side) the claim states; 2 bp per side reported"),
         why="T-348's SPY gap was +3.29 bps (lower bound +1.44) and failed only its 3 bp bar; the overnight-only holding is an exposure efficiency (similar return, half the time in market) worth replicating"),
    dict(slug="spy-short-strangle-quoted-exit-rules", kind="options-strategy", parent="T-156", testable=True,
         claim="On DoltHub end-of-day SPY chains 2019-02 to 2026-10, a 45-DTE 0.16-delta short strangle sold at mid minus half the quoted spread on each standard monthly expiry and bought back at 50% of the credit or at 21 DTE (whichever first) at mid plus half the spread earns a positive mean P&L per unit of Reg-T margin, and its P&L per day in the trade exceeds holding to expiry.",
         trial=dict(statistic="mean P&L per unit margin per cycle; paired difference of P&L per day (target-50-or-21-DTE minus hold to expiry)",
                    null="mean P&L <= 0, or the paired P&L-per-day difference <= 0",
                    procedure="batch6b_dolt's chain parser and strike-by-delta selector (vendor delta within 0.075); entries on the standard monthly expiry calendar at 45 +/- 7 DTE; marks on each later quote day; settlement at intrinsic on SPY's raw close; circular block bootstrap over cycles",
                    data="dolt-chain-SPY, daily-history-SPY",
                    min_n=60,
                    pass_="mean P&L per unit margin > 0 with the 95% CI excluding 0 AND the paired P&L-per-day difference > 0 with the 95% CI excluding 0",
                    controls="QUOTE-PRICED (the parent was model-priced at VIX: hold +1.45 vs target50 +3.69 bp of spot per day); half-spread from the same quote rows; early assignment ignored as the parents do; 2020-03 and 2022 reported separately"),
         why="the model-priced theta family (T-156, T-103, T-109, T-57) flips sign with the pricing scale; the archived DoltHub quotes turn it into a quote-priced test, and the parent's best component was the exit rule, not the entry"),
    dict(slug="putwrite-with-trend-filter", kind="options-strategy", parent="T-301", testable=True,
         claim="Over the Cboe PUT index history to 2026-09, holding PUT only in months after SPY (^GSPC before 1993) closed above its 10-month simple moving average at the prior month-end, and T-bills otherwise, reduces the maximum drawdown by at least 30% relative to always holding PUT without lowering the excess-return Sharpe ratio.",
         trial=dict(statistic="maximum drawdown reduction (always minus filtered, as a share of always) and the Sharpe difference",
                    null="reduction < 30% or Sharpe(filtered) < Sharpe(always)",
                    procedure="month-end decision on the index close, applied from the next month; DTB3 (rule 7) when out; 2 bps per switch; matched random-timing null that re-places the rule's own out-of-market spells (T-301's construction); paired block bootstrap for the Sharpe difference",
                    data="cboe-PUT-history, daily-history--GSPC, daily-history-SPY, fred-DTB3",
                    min_n=300,
                    pass_="drawdown reduction >= 30% with the matched-null p < 0.05 AND the Sharpe difference's 95% lower bound > -0.05",
                    controls="PUT before its 2007 launch is Cboe's back-test (reported, and the live months judged separately); the filter is the single pre-declared 10-month SMA, no grid"),
         why="T-301's drawdown control was the robust part (MDD 24.3% vs 52.9%, 95 of 96 variants raw p < 0.05) while its Sharpe gain was not; putwriting is Mandel's best-supported premium; combining a robust risk control with a supported premium is the natural salvage"),
    dict(slug="cme-btc-carry-brr-exit", kind="underlying-strategy", parent="T-362", testable=False,
         claim="From 2022-01 to 2026-09, a hold-to-expiry CME BTC cash-and-carry entered when the synchronous annualised basis exceeds DTB3 + 3% earns a positive mean annualised excess return over DTB3 when the exit is priced at a replication of the CME CF BRR (median of twelve 5-minute volume-weighted partitions of Coinbase and Kraken 1-minute trades, 15:00-16:00 London).",
         trial=dict(statistic="mean annualised excess return over DTB3 on capital per contract-month",
                    null="mean <= 0",
                    procedure="T-362's entry rule and contract set unchanged; the exit leg's spot sold at the BRR replication instead of the 16:00 London index; studentized block bootstrap; DSR counted over T-362's 10 trials plus this one",
                    data="daily-history-BTC-F, coinbase-1m-BTC-USD-<YYYY-MM>, kraken-trades-1m-XBTUSD-<YYYY-MM>, fred-DTB3",
                    min_n=40,
                    pass_="one-sided 95% studentized lower bound of the mean > 0 and DSR > 0.95 over 11 trials",
                    controls="NOT independent of T-362: its control (exit at the mean of the 15:00 and 16:00 London index: +1.01%, lower +0.35%) was seen; this successor tests whether a faithful settlement replication, rather than a seen alternative, changes the verdict; Bitstamp, Gemini, itBit and LMAX are missing from the replication (reported)"),
         blocked="kraken-trades-1m-XBTUSD through 2026-09 (the fetch chain is at 2025-01)",
         why="T-362's test-window loss came from settlement slippage (+0.103% of spot) at a 16:00-London proxy exit; the real CME settlement is the BRR over 15:00-16:00, which the archived 1-minute venue data can replicate"),
    dict(slug="eth-perp-funding-carry-hysteresis", kind="underlying-strategy", parent="T-363", testable=False,
         claim="On Deribit ETH-PERPETUAL from 2023-01 to 2026-09, long spot / short perpetual entered when trailing 7-day annualised funding exceeds DTB3 + 4% and exited only when it falls below DTB3, earns an annualised Sharpe of daily excess returns above 0.5 after 10 bp per side per leg.",
         trial=dict(statistic="annualised Sharpe of the daily excess return of the position",
                    null="Sharpe <= 0.5",
                    procedure="T-363's construction with the pre-declared hysteresis exit; perp-spot spread bounded as in T-363; stationary bootstrap",
                    data="deribit-funding-ETH-PERPETUAL (to fetch), daily-history-ETH-USD, fred-DTB3",
                    min_n=1000,
                    pass_="Sharpe > 0.5 with the one-sided 95% lower bound > 0",
                    controls="ETH was not used by T-363; on BTC the hysteresis control gave central Sharpe 1.13 against -0.64 for the switching rule (seen, so BTC is not the test); Deribit is not accessible to US retail: the US analogue is a Coinbase Derivatives or Kalshi perp, whose funding history is not archived (venue access recorded)"),
         blocked="deribit-funding-ETH-PERPETUAL history (fetchable from the Deribit history API)",
         why="T-363 lost on 118 switches, not on funding: the hysteresis exit cut turnover and is the part worth keeping"),
    dict(slug="eth-greed-momentum", kind="underlying-strategy", parent="T-41", testable=True,
         claim="From 2018-02 to 2026-09, ETH-USD's forward 7-day log return after a Crypto Fear & Greed reading of 75 or more exceeds its unconditional 7-day mean, with both halves positive.",
         trial=dict(statistic="mean forward 7-day log return after F >= 75 minus the unconditional mean",
                    null="difference <= 0",
                    procedure="F for day t known at 00:00 UTC on t+1; entry at the close of t+1; block-shift permutation p as in T-41; halves",
                    data="crypto-fear-greed-history, daily-history-ETH-USD",
                    min_n=150,
                    pass_="difference > 0 with block-shift p < 0.05 and both halves positive",
                    controls="WRONG-WAY SALVAGE of T-41: on BTC the greed side was the opposite of the claim (+2.29% vs the unconditional mean, one-sided p for the claim 0.955, halves +3.36% / +0.40%); ETH is a weakly independent replication (correlation with BTC ~0.8); BTC after 2026-10-20 is counted forward in the notes"),
         why="a contrarian claim that failed in the momentum direction; the momentum reading is the salvage"),
    dict(slug="gold-futures-plus-bills-vs-gld", kind="underlying-strategy", parent="T-370", testable=True,
         claim="From 2005-01 to 2026-09, a fully collateralised long front-month COMEX gold futures position (rolled before first notice, collateral earning DTB3) has a higher total return than holding GLD by at least 0.5% a year.",
         trial=dict(statistic="annualised mean daily return difference (futures + DTB3 accrual minus GLD total return) on sessions outside the roll windows",
                    null="difference <= 0.5% a year",
                    procedure="Yahoo GC=F is a continuous front series, so the +-2 sessions around each scheduled roll are masked from both legs (T-370's mask) and the excluded-session drift is reported; HAC lag 21; halves",
                    data="daily-history-GC-F, daily-history-GLD, fred-DTB3",
                    min_n=3000,
                    pass_="difference >= 0.5%/yr with the HAC 95% lower bound > 0 and both halves positive",
                    controls="INVERSION SALVAGE of T-370: its implied financing came out 159 bp BELOW bills (CI -185 to -133), which if real means futures + bills beat spot gold by about that much plus GLD's 0.40% fee; a realised-return test is the check, and a measurement artefact (Yahoo front-contract identification, 13:30 vs 16:00 closes) is the leading alternative; micro gold (MGC) is the US retail instrument"),
         why="the parent claimed no excess carry and found a large one; if it survives a realised-return test it is an instrument efficiency (hold gold as futures + T-bills), if not it is a data artefact worth knowing"),
    dict(slug="memecoin-bounce-short-coinbase-check", kind="underlying-strategy", parent="child:cryptobot (unregistered sibling session; its armed live rule)", testable=True,
         claim="On Coinbase DOGE-USD and SHIB-USD daily candles from 2021 to 2026-09, shorting at the next UTC daily open after a closed day whose 1-day return is in the top tercile and whose 3-day return is in the bottom tercile of the expanding history (at least 120 days), with a -20% target, +10% stop (both on later daily highs and lows, stop first when one day touches both) and a 14-day time exit, earns a positive mean net return per trade after 18 bp per round trip and 0.01% per 8 hours of funding.",
         trial=dict(statistic="mean net return per trade with a trade-clustered (by month) 95% CI",
                    null="mean net <= 0",
                    procedure="the rule as written in the child's cryptobot/perp_bot.py (expanding terciles refitted daily on history before the signal candle, min_history_days 120, re-entry after 14 days) but entered at the NEXT open and exited on later bars only (no fill at the signal candle's own close or at the barrier unless the bar trades through it); studentized block bootstrap; per coin and pooled; halves",
                    data="coinbase-daily-DOGE-USD, coinbase-daily-SHIB-USD",
                    min_n=60,
                    pass_="pooled 95% CI of the mean net return excludes 0 on the positive side and both coins positive",
                    controls="an independent check of a live rule run by a sibling session (Mandel does not touch the child); the child's own diagnostics give the rule DSR 0.00 at nominal N and 0.18-0.35 at N_eff after a 4,512-trial search, and its benchmark fills sit exactly at the barriers; the trial count of the child's search is carried as the deflation context, not re-run"),
         why="real money is armed on this rule; Mandel's job under section 5 is to measure it independently and report, not to change it"),
    dict(slug="cheap-yes-7d-archived-panel", kind="market-structure", parent="T-02", testable=True,
         claim="Across resolved Polymarket binary markets in the archived closed-markets panel (2023-2026) that were not in T-02's 2,100-market sample, YES contracts priced below 0.10 seven days before the scheduled end resolve YES more often than their price implies (mean outcome minus price > 0).",
         trial=dict(statistic="mean (outcome - price) in the < 0.10 bucket at 7 days before the scheduled end; net P&L per contract after a 1-cent spread and the market's fee as secondary",
                    null="mean (outcome - price) <= 0",
                    procedure="T-02's construction (price = the daily history point nearest end - 7 d, no later than it) on markets absent from T-02's bundle; event-clustered bootstrap; categories reported",
                    data="polymarket-closed-markets-<YYYY-MM>, polymarket-price-history-daily-<YYYY-MM>",
                    min_n=300,
                    pass_="event-clustered 95% CI of the mean excludes 0 on the positive side, with at least 20 YES resolutions",
                    controls="WRONG-WAY SALVAGE: T-02 claimed longshots are overpriced and found the reverse (+0.0208, CI +0.0022 to +0.0510, only 9 YES events), which T-47 restated as a forward test; this uses the archive's markets T-02 never saw; the crypto child reports the opposite sign on Kalshi crypto longshots, so the venue is part of the claim"),
         why="the only wrong-way-significant prediction-market calibration result; the archive now holds far more resolved markets than T-02 saw"),
    dict(slug="ibs-reversal-replication-qqq-iwm-dia", kind="underlying-strategy", parent="T-332", testable=True,
         claim="On QQQ, IWM and DIA from inception to 2026-09, the mean next-day close-to-close return after an internal bar strength below 0.2 exceeds the unconditional mean next-day return by more than 2 bps, after Holm over the three ETFs.",
         trial=dict(statistic="mean next-day return after IBS < 0.2 minus the unconditional mean, per ETF",
                    null="difference <= 2 bps",
                    procedure="T-332's construction unchanged (IBS = (close - low) / (high - low) of day t, entry at the close of t, exit at the close of t+1); studentized block bootstrap; Holm over three",
                    data="daily-history-QQQ, daily-history-IWM, daily-history-DIA",
                    min_n=1000,
                    pass_="at least two of three ETFs with Holm-adjusted p < 0.05 and every ETF positive in both halves",
                    controls="T-332 (SPY) is one of Mandel's three executable class-A rules; SPY is not used here"),
         why="not a failure salvage: the decision-centre review asks that the few executable supported rules get a replication family before anything is built on them"),
]


def _hash(claim: str, trial: dict) -> str:
    return hashlib.sha256(json.dumps({"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16]


def main() -> None:
    reg = json.load(open(REGISTRY))
    ids = {t["id"] for t in reg["theories"]}
    slugs = {t["slug"] for t in reg["theories"]}
    nxt = max(int(i[2:]) for i in ids) + 1
    led = Ledger()
    added = []
    for e in NEW:
        assert e["slug"] not in slugs, e["slug"]
        tid = f"T-{nxt}"; nxt += 1
        tr = dict(e["trial"]); tr["pass"] = tr.pop("pass_")
        trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        t = {"id": tid, "slug": e["slug"], "kind": e["kind"], "claim": e["claim"], "origin": [e["parent"], SALVAGE],
             "trial": trial, "experiments": [], "testable_now": e["testable"],
             "status": "untested" if e["testable"] else "blocked", "blocked_on": "" if e["testable"] else e["blocked"],
             "results": [],
             "notes": (f"pre-registered salvage successor of {e['parent']} on 2026-10-20: {e['why']}. The observation that "
                       "motivated it is evidence for registering it, not for supporting it; the parent's verdict stands.")}
        reg["theories"].append(t)
        led.append("theory.preregistered", {"id": tid, "from": e["parent"], "hash": _hash(t["claim"], trial),
                                            "known_days": 0, "basis": "salvage-audit-2026-10-20"}, actor="mandel")
        added.append((tid, e["slug"], t["status"]))
    save_registry(reg)
    for a in added:
        print(*a)


if __name__ == "__main__":
    main()
