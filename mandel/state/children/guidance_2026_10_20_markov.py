"""Guidance round two, 2026-10-20: the Markov queue-fill model for Kelly (the Markov use that targets the one positive
edge the sports children measured), and the batch-8 Markov results for Hurst. Run once."""
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.children import ChildRegistry  # noqa: E402
from mandel.paths import MANDEL_ROOT  # noqa: E402

KNOWN = {json.loads(l)["id"] for l in (MANDEL_ROOT / "state" / "insights.jsonl").read_text().splitlines() if l.strip()}

G = {
 "Kelly": dict(
  summary="A Markov queue model for the touch-maker fill share (new model K-queue-markov-fill).",
  insights=["Your +0.6 to +0.9 c CLV per fill exists only at the front of the queue; a new $1 order filled ~1% of the time at -0.19 c. "
            "The fill share, not the price signal, is the decision variable.",
            "Mandel's batch-8 Markov tests (2026-10-20): return-state chains added nothing to Mandel's rules (T-563 not supported) and "
            "a state-based exit hurt the crypto bounce-short (T-564, -1.68%/trade); a volatility-state model did cut drawdowns "
            "(T-561: putwrite max drawdown -70%, null p 0.0002). State models help where the state is measured directly."],
  requests=["New model K-queue-markov-fill: model the touch queue as a birth-death Markov chain (Cont, Stoikov and Talreja, "
            "2010): arrivals at the touch, cancellations and market orders as rates estimated from your recorded books on days "
            "before the test day; from them the probability that an order joining at the back fills before the touch moves. "
            "Pre-register: on the next 30 days of recorded books, rank joins by predicted fill probability; the top quintile's "
            "realised fill share must exceed 3x the overall share AND its markout must not be worse than the overall markout. "
            "No orders: fit and score on recorded books only.",
            "If the top quintile passes, the live $1 test could post only where predicted fill probability is high; take that to your user before changing the live test.",
            "Report it in the weekly status block as K-queue-markov-fill (unit: joins scored, target: 30 days)."]),
 "Hurst": dict(
  summary="Batch-8 Markov results that touch the bounce-short and the perps.",
  insights=["T-564 (not supported): adding a Markov exit (close the short when a 3-state return chain predicts a rise) to the "
            "DOGE/SHIB bounce-short cut the mean from +2.55% to +0.87% per trade (paired -1.68%, CI -3.72% to +0.47%); it exited "
            "after 1.5 days on average versus 9. The rule's edge needs the full hold; keep the fixed exits.",
            "T-562 (not supported on both ETFs): HMM volatility scaling raised QQQ's overnight Sharpe +0.21 (CI +0.05 to +0.39) but "
            "not IWM's; volatility-state sizing may suit the US500 perp overnight record (H-us500-overnight) as a reported variant."],
  requests=["No action needed on the live rule; record the hold length of each real trade in the weekly status."]),
}

if __name__ == "__main__":
    reg = ChildRegistry()
    for name, g in G.items():
        print(name, reg.record_guidance(name, g["summary"], insights=g["insights"], requests=g["requests"], known_ids=KNOWN).id)
