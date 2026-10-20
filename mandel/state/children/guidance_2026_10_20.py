"""
First guidance round, 2026-10-20: Mandel's results that bear on each child's work, new models assigned to each (as
forward records or paper tests the child pre-registers itself; nothing here places an order or changes a live
setting), and one shared weekly measurement protocol that feeds the Paper Strategy Tracker. Run once.
"""
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")

from mandel.children import ChildRegistry
from mandel.paths import MANDEL_ROOT

KNOWN = {json.loads(l)["id"] for l in (MANDEL_ROOT / "state" / "insights.jsonl").read_text().splitlines() if l.strip()}

PROTOCOL = ("Weekly status, one line per paper/live/forward test, fields: id, strategy, venue, mode (live|paper|forward), "
            "started, unit, n_now, n_target, read_date, pnl_usd, fills, mean fill gap vs your replay/model price in bp or "
            "cents, status, next_step. Count every rule variant you have tried (for Mandel's deflation).")

GUIDANCE = {
 "Hurst": dict(
  summary="Mandel's independent check of the bounce-short, and three new forward records on the Kalshi perps you already collect.",
  insights=[
   "T-556 (supported after refutation): the DOGE/SHIB bounce-short re-run on Coinbase daily candles, entered at the NEXT open, exits on later bars only: +2.55%/trade, month-clustered 95% CI +0.24% to +4.78%. DOGE carries most of it and the CI is sensitive to the cluster width, so it supports running small, not sizing up.",
   "T-549 (supported): close-to-open (overnight) returns on QQQ/IWM net +3.4 to +3.6 bp a night at 1 bp a side, 1999-2026.",
   "T-547: turn-of-month (return days -4..+3) replicated on BTC (+13.5 bp/day, p 0.041) and IWM, not on 3 of 5 country ETFs.",
   "T-555 (supported): gold futures plus T-bills beat GLD by about +1.07%/yr; GLD's implied financing sits 159 bp below bills.",
   "Leverage review: no killed Mandel model becomes profitable at 2-10x on Kalshi perps or Kraken margin; funding (US500 0.019-0.030%/day so far) and Kraken rollover (~33%/yr BTC) exceed the edges. Mandel recommends 1x.",
  ],
  warnings=["The bounce-short's universe was picked with hindsight (DOGE/SHIB because Kalshi lists them); treat T-556 as a check of the rule, not of the universe."],
  requests=[
   "New model H-btc-tom: pre-register a forward record of Kalshi BTC perp returns over turn-of-month days -4..+3 versus other days, net of 4 bp taker / 2 bp maker and funding paid; record only, no orders; read after 12 months.",
   "New model H-us500-overnight: from the perp books you already record, measure US500 perp close-to-open vs open-to-close drift and the funding paid over each leg; record whether overnight drift exceeds funding plus 2 bp maker each side. Record only.",
   "New model H-gold-perp-carry: record Kalshi gold perp funding against the 3-month T-bill rate, to test whether the perp prices gold financing below bills as GLD does (T-555).",
   "For the live bounce-short: journal each real fill with the replay's price for the same bar, so fill gap in bp can be read after 10 fills.",
   PROTOCOL,
  ]),
 "Brier": dict(
  summary="A longshot calibration record that points the other way to Kalshi crypto, and the shared weekly protocol.",
  insights=[
   "T-557 registered: on Polymarket, YES below 0.10 seven days out resolved +2.08 pp above its price (CI +0.22 to +5.10) over a small panel (9 YES events). That runs against Hurst's Kalshi crypto longshots (they lose 27-72% per dollar); both may be true by venue and category.",
   "T-411 (not supported): Mandel's Kalshi market-making replay lost $0.076 per market-day with a realised spread of -1.13 c, consistent with your queue-adjusted result.",
  ],
  requests=[
   "New model B-longshot-calibration: a forward record (no orders) of every Polymarket US and Kalshi non-sports market priced below 0.10 YES at 7 days, with category and venue, scored at resolution; read at 200 markets.",
   "When the Polymarket US key arrives, journal each $1 maker order with queue ahead at entry, so fill share can be modelled against queue depth.",
   PROTOCOL,
  ]),
 "Kelly": dict(
  summary="Queue-depth-conditioned maker fills as a new model, and the shared weekly protocol.",
  insights=[
   "T-411 (not supported): Kalshi market making in Mandel's replay loses to adverse selection (realised spread -1.13 c), the same shape as your 34,454-fill markout.",
   "T-408 / T-463: Kalshi hourly reversal and taker-flow follow both fail after ~4 c round-trip costs, and their inverses fail too; costs, not direction, are the problem.",
  ],
  requests=[
   "New model K-thin-queue-maker: re-cut your existing queue data by touch size at entry (e.g. under 50, 50-500, over 500 contracts) and report fill share and markout per bucket; if a thin-queue bucket shows positive markout, pre-register it as its own arm before the live $1 test starts.",
   "Report the NO-on-tennis-longshots-at-T-30 forward record's n weekly against its 150.",
   PROTOCOL,
  ]),
 "Shannon": dict(
  summary="Recorders for data Mandel cannot archive itself, and the shared weekly protocol.",
  insights=[
   "T-544 (not supported): Kalshi KXBTCD priced from the Deribit digital loses -5.2 c a contract; the Kalshi daily BTC market is better calibrated than a spot-plus-realised-vol model.",
   "Kalshi 15-minute and hourly crypto series (KXBTC15M and others, settled on CF BRTI 60-second averages) are not archived anywhere Mandel can reach.",
  ],
  requests=[
   "New recorder S-kalshi-crypto-short: archive settled KXBTC15M / hourly crypto markets (strike, final bid/ask, volume, settlement) daily from your Linode, so a calibration test can be pre-registered on data neither of us has seen.",
   "New recorder S-macro-buckets: record Kalshi CPI and Fed decision bucket prices at T-7, T-1 and settlement, extending the fed_watch / cb_watch forward record to CPI.",
   "Report G10 fires weekly against the forward record.",
   PROTOCOL,
  ]),
}

if __name__ == "__main__":
    reg = ChildRegistry()
    for name, g in GUIDANCE.items():
        rec = reg.record_guidance(name, g["summary"], insights=g["insights"], warnings=g.get("warnings"),
                                  requests=g["requests"], known_ids=KNOWN)
        print(name, rec.id)
