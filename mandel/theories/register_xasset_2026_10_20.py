"""Pre-register batch 11 (user request 2026-10-20: futures for bonds and other assets, FX, leverage venues): two
month-end flow effects that a futures or FX venue can trade, neither tested by Mandel before. Registered before running."""

import hashlib
import json
import sys

sys.path.insert(0, "/home/user/polymarket-arbitrage")
from mandel.experiments.run import REGISTRY, save_registry  # noqa: E402
from mandel.ledger import Ledger  # noqa: E402

BASIS = "cross-asset futures/FX sweep 2026-10-20 (month-end index-extension and hedge-rebalancing flows)"
NEW = [
    dict(slug="treasury-month-end-extension", kind="underlying-strategy", parent="T-59 (equity turn-of-month) / T-484 (synthetic 10Y)",
         claim="From 1990-01 to 2026-09, the synthetic 10-year Treasury total return (from FRED DGS10: carry y/252 minus modified duration x daily yield change) on the last trading day of each month exceeds its mean on all other days by at least 1 bp, with both halves positive.",
         trial=dict(statistic="mean synthetic 10Y daily return on month-end days minus the mean on other days, bps",
                    null="difference <= 1 bp",
                    procedure="mandel.experiments.batch11_xasset: daily return = y_{t-1}/100/252 - D(y_{t-1}) (y_t - y_{t-1})/100, D = modified duration of a 10-year par bond at y_{t-1}; month-end = the last FRED observation of each calendar month; studentized circular block bootstrap of the paired day-flag series (blocks of 21 days); halves 1990-2007 / 2008-2026; reported: the 2-year note (DGS2), the last 2 and first 2 days of the month",
                    data="fred-DGS10, fred-DGS2", min_n=400,
                    pass_="difference >= 1 bp with one-sided p < 0.05 and both halves positive",
                    controls="index-extension buying is documented in the literature for month-end; the synthetic return ignores convexity and the bid-ask of the futures/ETF that would carry it (a micro Treasury future or TLT, 1-2 bp a round trip, reported)"),
         why="Treasury month-end index extension is the bond analogue of the supported equity turn-of-month (T-59) and is tradeable with Treasury futures"),
    dict(slug="usd-month-end-weakness-g10", kind="underlying-strategy", parent="T-368/T-478 (FX carry, momentum: not supported)",
         claim="From 2000-01 to 2026-09, an equal-weight basket of the nine G10 currencies against the US dollar rises more on the last two trading days of each month than on other days, by at least 2 bp a day, with both halves positive.",
         trial=dict(statistic="mean daily log change of the equal-weight G10-vs-USD basket on the last two trading days of the month minus other days, bps",
                    null="difference <= 2 bp",
                    procedure="mandel.experiments.batch11_xasset: basket = mean over EUR, JPY, GBP, CHF, CAD, AUD, NZD, SEK, NOK of the daily log change of USD per unit (FRED noon rates); days on which every currency has a print; studentized circular block bootstrap (21-day blocks); halves 2000-2012 / 2013-2026; per-currency signs reported",
                    data="fx-spot-g10", min_n=600,
                    pass_="difference >= 2 bp with one-sided p < 0.05 and both halves positive",
                    controls="month-end USD selling from foreign investors' hedge rebalancing is a documented flow; FRED noon fixes are not tradeable prints (the trade would use CME FX futures or a US FX broker at ~1-2 pips); carry over two days is negligible and ignored"),
         why="FX carry and momentum failed in Mandel; a calendar flow effect is the FX analogue of the equity calendar edges that did survive"),
]


def _h(c, t):
    return hashlib.sha256(json.dumps({"claim": c, "trial": t}, sort_keys=True).encode()).hexdigest()[:16]


def main():
    reg = json.load(open(REGISTRY))
    slugs = {t["slug"] for t in reg["theories"]}
    nxt = max(int(t["id"][2:]) for t in reg["theories"]) + 1
    led = Ledger()
    for e in NEW:
        assert e["slug"] not in slugs
        tid = f"T-{nxt}"; nxt += 1
        tr = dict(e["trial"]); tr["pass"] = tr.pop("pass_")
        trial = {k: tr[k] for k in ("statistic", "null", "procedure", "data", "min_n", "pass", "controls")}
        reg["theories"].append({"id": tid, "slug": e["slug"], "kind": e["kind"], "claim": e["claim"], "origin": [e["parent"], BASIS],
                                "trial": trial, "experiments": [], "testable_now": True, "status": "untested", "blocked_on": "",
                                "results": [], "notes": f"pre-registered 2026-10-20: {e['why']}."})
        led.append("theory.preregistered", {"id": tid, "from": e["parent"], "hash": _h(e["claim"], trial), "known_days": 0,
                                            "basis": "xasset-2026-10-20"}, actor="mandel")
        print(tid, e["slug"])
    save_registry(reg)


if __name__ == "__main__":
    main()
