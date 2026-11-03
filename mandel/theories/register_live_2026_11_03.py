"""Pre-register T-744, the minimum-size LIVE execution test of the calendar sleeve, before any real order exists.
The user decided it on 2026-11-03 after the summary of what deserves money; the paper test (T-559) cannot pass its
execution criterion because Alpaca paper runs no auctions. Forward only: every outcome is recorded after this row."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

E = dict(
    slug="calendar-sleeve-live-execution-minimum-size", kind="underlying-strategy", parent="T-559",
    claim="On a live Alpaca account from the day the user arms the switch, the calendar sleeve's rules (overnight QQQM close-to-open every session; SPYM close-to-close after IBS < 0.2 read at 15:40 ET; SPYM over turn-of-month return days -4..+3 with T-345's month-end skip) placed as market-on-close and market-on-open orders for MANDEL_LIVE_SHARES (= 1) whole share per symbol fill at the official auction prints: over the first 60 sessions with a fill, mean |fill - official print| <= 1.5 bp per side with the 95% upper bound <= 2.5 bp, and at least 95% of auction orders fill.",
    trial=dict(statistic="(a) mean |fill - official auction print| per side in bp over every filled order, with its 95% upper bound; (b) share of auction orders filled; (c, reported only) realised P&L of the closed round trips beside the same trips at the official prints",
               null="(a) mean gap > 1.5 bp or upper bound > 2.5 bp; (b) fill share < 95%",
               procedure="mandel.live.runner --live (pinned commit) on the Linode: close phase 15:40 ET ('cls' orders, cutoff 15:50), open phase 08:30 ET ('opg', cutoff 09:28), reconcile 16:20 ET books fills and Yahoo's official open/close as print.official rows; journal at MANDEL_LIVE_STATE pushed nightly to branch live/journal; tracker.calendar_progress scores it (fill_gap_bp_mean, fill_gap_bp_upper95, fill_gap_n)",
               data="the live journal (live/journal branch), print.official rows (Yahoo chart, keyless)",
               min_n=60,
               pass_="(a) and (b) at 60 sessions with a fill: mean gap <= 1.5 bp, upper <= 2.5 bp, fill share >= 95%. (c) is NOT a pass criterion at this size: T-559's return criterion needs 250 sessions and this arm's P&L at 1 share is noise by construction",
               controls="size is fixed at 1 share per symbol whatever the account holds (about $290 QQQM every night, $90 SPYM when a rule fires; at most ~$400 at risk); never borrows (a buy is skipped and journalled when cash is short); realised-loss halt at $40 cumulative (HALT file, user-removed); KILL file stops every order phase; the switch MANDEL_ALPACA_LIVE=I-UNDERSTAND exists only in /etc/mandel-live.env written by the user, and the client is read-only without it; IBS is read at 15:40 instead of the paper's 15:45 (the MOC cutoff), a registered deviation from T-332's close-defined IBS; the options sleeve (T-560) never runs live; the paper arm (T-559) continues unchanged beside it for the return criterion"),
    blocked="the user arming the switch on the Linode (deploy/live/install.sh, then the MANDEL_ALPACA_LIVE line), then 60 live sessions with a fill",
    why="T-559 criterion (a) is unpassable on the paper venue (no auctions; fills at 15:44 and 09:33 prints); only live auction orders measure the fill gap the rules are defined on. Sized so a total loss changes nothing: the test buys execution evidence, not return.")


def _hash(claim, trial):
    return hashlib.sha256(json.dumps({"claim": claim, "trial": trial}, sort_keys=True).encode()).hexdigest()[:16]


def main():
    reg = json.load(open(REGISTRY))
    assert E["slug"] not in {t["slug"] for t in reg["theories"]}, E["slug"]
    tid = f"T-{max(int(t['id'][2:]) for t in reg['theories']) + 1}"
    tr = dict(E["trial"]); tr["pass"] = tr.pop("pass_")
    trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
    reg["theories"].append({"id": tid, "slug": E["slug"], "kind": E["kind"], "claim": E["claim"],
                            "origin": [E["parent"], "user decision 2026-11-03: minimum-size live execution test"],
                            "trial": trial, "experiments": [], "testable_now": False, "status": "blocked",
                            "blocked_on": E["blocked"], "results": [],
                            "notes": f"pre-registered live execution test (parent {E['parent']}) on 2026-11-03 before any real order: {E['why']}"})
    Ledger().append("theory.preregistered", {"id": tid, "from": E["parent"], "hash": _hash(E["claim"], trial), "known_days": 0,
                                             "basis": "live-execution-2026-11-03",
                                             "decision": "the user's, 2026-11-03, after the funding summary; Mandel sets no switch"},
                    actor="mandel")
    save_registry(reg)
    print(tid, E["slug"])


if __name__ == "__main__":
    main()
