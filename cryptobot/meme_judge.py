"""`meme-judge-forward`: a memecoin launch judge, paper only.

The design of an X post ("the seventh seat"), with fixed rules instead of
a chat model: finders write a facts-only dossier, a judge answers closed
questions, and fixed code decides. Nothing is bought. Every verdict and
what the pool did afterwards are logged, so the gate is judged on its
record, not on a story.

  every 2 min   GeckoTerminal's newest pools on solana and base -> first sight
  +30 min       re-read the pool + GoPlus -> dossier -> RISK -> JUDGE
                BUY / WATCH (asked once more 30 min later) / PASS
  +1h +4h +24h  price after each decision, net of a $250 round trip

State: state/meme/{pools.json, verdicts.jsonl}. The registered rule and
thresholds live in cryptobot/hypotheses.yaml (`meme-judge-forward`); a
change to them is a new registration, not an edit.

    python -m cryptobot.meme_judge --state state --report
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import random
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GT = "https://api.geckoterminal.com/api/v2"
GOPLUS = "https://api.gopluslabs.io/api/v1"
CHAINS = {"solana": "solana", "base": "8453"}          # GeckoTerminal network -> GoPlus chain
POLL_S = 120
JUDGE_AFTER_S = 1800
WATCH_AGAIN_S = 1800
HORIZONS = (("1h", 3600), ("4h", 14400), ("24h", 86400))
SIZE_USD = 250.0
SWAP_FEE = 0.003
NETWORK_USD = 1.0
MIN_LIQ, DEAD_LIQ = 10_000.0, 1_000.0
READ_BUYS, READ_DAYS = 200, 45


def _f(v, default=None):
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ parsing

def parse_pool(raw: dict, chain: str, now: float) -> Optional[dict]:
    """GeckoTerminal pool -> snapshot (facts only; None for absent fields)."""
    a = raw.get("attributes") or {}
    tok = (((raw.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
    addr = a.get("address")
    if not addr:
        return None
    tx = a.get("transactions") or {}

    def t(w, k):
        return (tx.get(w) or {}).get(k)
    created = a.get("pool_created_at")
    return {"chain": chain, "pool": addr, "token": tok.split("_", 1)[1] if "_" in tok else tok, "name": a.get("name"),
            "ts": now, "created": dt.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp() if created else None,
            "price": _f(a.get("base_token_price_usd")), "liq": _f(a.get("reserve_in_usd")), "fdv": _f(a.get("fdv_usd")),
            "buys_m5": t("m5", "buys"), "sells_m5": t("m5", "sells"), "buys_m15": t("m15", "buys"), "sells_m15": t("m15", "sells"),
            "buyers_h1": t("h1", "buyers"), "sellers_h1": t("h1", "sellers")}


def parse_goplus(chain: str, r: Optional[dict]) -> dict:
    """GoPlus token security -> the flags RISK uses; missing stays None."""
    if not r:
        return {"checked": False}
    out = {"checked": True}
    if chain == "solana":
        def status(k):
            v = r.get(k)
            return None if not isinstance(v, dict) else v.get("status") == "1"
        out.update(mintable=status("mintable"), freezable=status("freezable"))
        out["analysed"] = out["mintable"] is not None and out["freezable"] is not None
    else:
        flag = lambda k: None if r.get(k) in (None, "") else r.get(k) == "1"
        out.update(honeypot=flag("is_honeypot"), cannot_sell_all=flag("cannot_sell_all"), sell_tax=_f(r.get("sell_tax")))
        out["analysed"] = out["honeypot"] is not None
    holders = r.get("holders") or []
    out["top10"] = sum(_f(h.get("percent"), 0.0) for h in holders[:10]) if holders else None
    return out


# ------------------------------------------------------------------ the seats

def dossier(first: dict, now: dict, sec: dict) -> dict:
    """Facts only, for one pool at its decision; a missing field stays None."""
    m15b, m15s, m5b, m5s = (now.get(k) for k in ("buys_m15", "sells_m15", "buys_m5", "sells_m5"))
    move = (now["price"] / first["price"] - 1) if first.get("price") and now.get("price") else None
    return {"chain": now["chain"], "pool": now["pool"], "token": now["token"], "name": now.get("name"),
            "age_min": (now["ts"] - now["created"]) / 60 if now.get("created") else None,
            "liq": now.get("liq"), "fdv": now.get("fdv"), "price": now.get("price"), "move_since_first": move,
            "buyers_h1": now.get("buyers_h1"), "sellers_h1": now.get("sellers_h1"),
            "buys_m5": m5b, "sells_m5": m5s,
            "buys_prev5": (m15b - m5b) if m15b is not None and m5b is not None else None,
            "sells_prev5": (m15s - m5s) if m15s is not None and m5s is not None else None,
            "security": sec}


def risk(d: dict) -> Optional[str]:
    """One hard fail kills; returns the reason, or None for RISK-clean."""
    s = d["security"]
    if d["liq"] is None or d["liq"] < MIN_LIQ:
        return "liquidity < $10k"
    if d["fdv"] is None:
        return "fdv missing"
    if d["price"] is None:
        return "price missing"
    if not s.get("analysed"):
        return "security unchecked"
    if s.get("honeypot"):
        return "honeypot"
    if (s.get("sell_tax") or 0) > 0.10:
        return "sell tax > 10%"
    if s.get("cannot_sell_all"):
        return "cannot sell all"
    if s.get("mintable"):
        return "mint authority live"
    if s.get("freezable"):
        return "freeze authority live"
    return None


def exit_risk(liq: float, size: float = SIZE_USD) -> int:
    share = size / liq
    for score, cut in ((1, 0.0025), (2, 0.005), (3, 0.01), (4, 0.02)):
        if share < cut:
            return score
    return 5


def judge(d: dict) -> dict:
    """The four closed questions, answered by rule from the dossier."""
    b, s, top = d["buyers_h1"], d["sellers_h1"], d["security"].get("top10")
    organic = (b is not None and s is not None and b >= 25 and b >= 1.2 * s and (top is None or top <= 0.5))
    late = d["move_since_first"] is not None and d["move_since_first"] > 3.0
    er = exit_risk(d["liq"])
    flowing = d["buys_m5"] is not None and d["sells_m5"] is not None and d["buys_m5"] > d["sells_m5"]
    if organic and not late and er <= 3 and flowing:
        action, why = "buy", ""
    elif organic and not late:
        action, why = "watch", "exit_risk > 3" if er > 3 else "last 5 minutes not net buying"
    else:
        action, why = "pass", ("not organic" if not organic else "late")
    return {"organic": organic, "late": late, "exit_risk": er, "action": action, "why": why}


SCORING_VERSION = 2       # v1 (2026-11-03..06) priced exits linearly and let a sale pay more than the pool held


def net_return(entry: float, px: Optional[float], liq_now: Optional[float], liq_entry: float,
               dead: bool = False, size: float = SIZE_USD) -> float:
    """Net return of a $size round trip through constant-product pools.
    Each side of a pool holds about half its reported liquidity, so a buy
    of S into quote reserve Q gets tokens worth S*Q/(Q+S) at the mid, and
    selling tokens worth V into reserve Q pays Q*V/(Q+V): never more than
    the pool holds. A dead pool is -100%."""
    if dead or px is None or liq_now is None or liq_now < DEAD_LIQ or not entry or not liq_entry:
        return -1.0
    q0, q1 = liq_entry / 2, liq_now / 2
    held = size * (1 - SWAP_FEE) * q0 / (q0 + size * (1 - SWAP_FEE))          # value at the entry mid
    v = held * px / entry
    proceeds = q1 * v / (q1 + v) * (1 - SWAP_FEE)
    return (proceeds - 2 * NETWORK_USD) / size - 1


# ------------------------------------------------------------------ collector

class MemeJudge:
    def __init__(self, state: Path, client: Optional[httpx.AsyncClient] = None, now=None, sleep=None):
        self.dir = Path(state) / "meme"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._c = client or httpx.AsyncClient(timeout=20, headers={"Accept": "application/json",
                                                                    "User-Agent": "cryptobot-research/0.1"})
        self._now = now or time.time
        self._sleep = sleep or asyncio.sleep
        p = self.dir / "pools.json"
        self.pools: dict = json.loads(p.read_text()) if p.exists() else {}

    def _save(self) -> None:
        cut = self._now() - 26 * 3600
        self.pools = {k: v for k, v in self.pools.items() if v["first"]["ts"] >= cut or v.get("pending")}
        (self.dir / "pools.json").write_text(json.dumps(self.pools))

    def _log(self, row: dict) -> None:
        with (self.dir / "verdicts.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")

    async def _get(self, url: str, params=None):
        for attempt in range(3):
            r = await self._c.get(url, params=params)
            if r.status_code == 429:
                await self._sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    async def discover(self) -> int:
        n = 0
        for chain in CHAINS:
            d = await self._get(f"{GT}/networks/{chain}/new_pools", {"page": 1})
            for raw in d.get("data") or []:
                snap = parse_pool(raw, chain, self._now())
                key = f"{chain}:{snap['pool']}" if snap else None
                if snap and key not in self.pools:
                    self.pools[key] = {"first": snap, "next": "judge", "due": snap["ts"] + JUDGE_AFTER_S}
                    n += 1
        return n

    async def _read(self, chain: str, addrs: list[str]) -> dict:
        out = {}
        for i in range(0, len(addrs), 30):
            d = await self._get(f"{GT}/networks/{chain}/pools/multi/{','.join(addrs[i:i + 30])}")
            for raw in d.get("data") or []:
                s = parse_pool(raw, chain, self._now())
                if s:
                    out[s["pool"]] = s
        return out

    async def _security(self, chain: str, tokens: list[str]) -> dict:
        if not tokens:
            return {}
        path = "/solana/token_security" if chain == "solana" else f"/token_security/{CHAINS[chain]}"
        out = {}
        for tok in tokens:                                # the free tier answers one address per call
            try:
                d = await self._get(GOPLUS + path, {"contract_addresses": tok})
            except Exception as exc:                      # security missing is recorded as missing
                logger.info("goplus %s: %s", chain, exc)
                continue
            for k, v in (d.get("result") or {}).items():
                out[k.lower()] = v
            await self._sleep(1.0)
        return out

    async def process(self) -> int:
        """Judge pools that are due and score outcomes that are due."""
        now = self._now()
        due = {k: v for k, v in self.pools.items() if v.get("due") and v["due"] <= now}
        n = 0
        for chain in CHAINS:
            keys = [k for k in due if k.startswith(chain + ":")]
            if not keys:
                continue
            snaps = await self._read(chain, [self.pools[k]["first"]["pool"] for k in keys])
            judging = [k for k in keys if self.pools[k]["next"] in ("judge", "rejudge")]
            # GoPlus only for pools that clear the market checks: the rest die on those anyway
            liquid = [k for k in judging if ((snaps.get(self.pools[k]["first"]["pool"]) or {}).get("liq") or 0) >= MIN_LIQ]
            sec = await self._security(chain, [self.pools[k]["first"]["token"] for k in liquid])
            for k in keys:
                p = self.pools[k]
                snap = snaps.get(p["first"]["pool"])
                if p["next"] in ("judge", "rejudge"):
                    n += self._decide(k, p, snap, sec, chain)
                else:
                    self._score(p, snap, chain, sec)
        self._save()
        return n

    def _decide(self, k: str, p: dict, snap: Optional[dict], sec: dict, chain: str) -> int:
        if snap is None:
            row = {"pool": p["first"]["pool"], "chain": chain, "ts": self._now(), "stage": "risk", "action": "pass",
                   "why": "pool gone before the decision"}
            self._log(row)
            p.update(next=None, due=None)
            return 1
        d = dossier(p["first"], snap, parse_goplus(chain, sec.get(p["first"]["token"].lower())))
        why = risk(d)
        verdict = {"organic": None, "late": None, "exit_risk": None, "action": "pass", "why": why} if why else judge(d)
        if verdict["action"] == "watch" and p["next"] == "rejudge":
            verdict = dict(verdict, action="pass", why="second watch")
        row = {"id": k, "ts": self._now(), "stage": "risk" if why else "judge", "risk_clean": not why,
               "round": 2 if p["next"] == "rejudge" else 1, "dossier": d, **verdict}
        self._log(row)
        if verdict["action"] == "watch":
            p.update(next="rejudge", due=self._now() + WATCH_AGAIN_S)
        elif not why:                                     # RISK-clean: follow it, BUY or not (the baseline)
            p.update(next="1h", due=self._now() + 3600, entry={"ts": self._now(), "price": d["price"], "liq": d["liq"],
                                                               "action": verdict["action"]}, out={}, pending=True)
        else:
            p.update(next=None, due=None)
        return 1

    def _score(self, p: dict, snap: Optional[dict], chain: str, sec: dict) -> None:
        e = p["entry"]
        h = p["next"]
        r = net_return(e["price"], snap["price"] if snap else None, snap["liq"] if snap else None, e["liq"])
        p["out"][h] = r
        p.setdefault("raw", {})[h] = {"price": snap["price"] if snap else None, "liq": snap["liq"] if snap else None}
        i = [x[0] for x in HORIZONS].index(h)
        if i + 1 < len(HORIZONS):
            nh, sec_ = HORIZONS[i + 1]
            p.update(next=nh, due=e["ts"] + sec_)
        else:
            self._log({"id": f"{chain}:{p['first']['pool']}", "ts": self._now(), "stage": "outcome",
                       "action": e["action"], "entry_ts": e["ts"], "out": p["out"], "v": SCORING_VERSION,
                       "entry": {"price": e["price"], "liq": e["liq"]}, "raw": p.get("raw", {})})
            p.update(next=None, due=None, pending=False)

    async def run_forever(self) -> None:
        logger.info("meme judge (paper): new pools on %s, decision 30 min after first sight", ", ".join(CHAINS))
        while True:
            try:
                await self.discover()
                await self.process()
            except Exception as exc:                      # never let research kill the desk
                logger.warning("meme judge step failed: %s", exc)
            await self._sleep(POLL_S)


# ------------------------------------------------------------------ the record

def _boot_lower(rets: list[float], days: list[str], draws: int = 2000, seed: int = 7) -> Optional[float]:
    by: dict = {}
    for r, d in zip(rets, days):
        by.setdefault(d, []).append(r)
    groups = list(by.values())
    if len(groups) < 5:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.fmean([x for g in rng.choices(groups, k=len(groups)) for x in g]) for _ in range(draws))
    return means[int(0.025 * draws)]


def report(state: Path) -> dict:
    p = Path(state) / "meme" / "verdicts.jsonl"
    rows = [json.loads(l) for l in p.open() if l.strip()] if p.exists() else []
    dec = [r for r in rows if r.get("stage") in ("risk", "judge")]
    all_outs = [r for r in rows if r.get("stage") == "outcome"]
    outs = [r for r in all_outs if r.get("v", 1) >= SCORING_VERSION]
    final = [r for r in dec if r["action"] != "watch"]
    kills: dict = {}
    for r in final:
        if r["action"] == "pass" and r.get("why"):
            kills[r["why"]] = kills.get(r["why"], 0) + 1
    out = {"judged": len(final), "risk_clean": sum(1 for r in final if r.get("risk_clean")),
           "buy": sum(1 for r in final if r["action"] == "buy"), "pass": sum(1 for r in final if r["action"] == "pass"),
           "watch_asked": sum(1 for r in dec if r["action"] == "watch"), "kills": kills,
           "old_scoring": len(all_outs) - len(outs),
           "first": dt.datetime.fromtimestamp(min(r["ts"] for r in rows), dt.timezone.utc).date().isoformat() if rows else None}
    for grp, sel in (("buys", lambda r: r["action"] == "buy"), ("clean", lambda r: True)):
        x = [r for r in outs if sel(r) and r["out"].get("4h") is not None]
        if x:
            rets = [r["out"]["4h"] for r in x]
            days = [dt.datetime.fromtimestamp(r["entry_ts"], dt.timezone.utc).date().isoformat() for r in x]
            out[grp] = {"n": len(x), "mean4h": statistics.fmean(rets), "median4h": statistics.median(rets),
                        "top": sorted(((r["out"]["4h"], r["id"]) for r in x), reverse=True)[:3], "win": statistics.fmean(1.0 if v > 0 else 0.0 for v in rets),
                        "dead": statistics.fmean(1.0 if v <= -0.999 else 0.0 for v in rets), "lo95": _boot_lower(rets, days),
                        "mean1h": statistics.fmean([r["out"]["1h"] for r in x if r["out"].get("1h") is not None] or [0.0]),
                        "mean24h": statistics.fmean([r["out"]["24h"] for r in x if r["out"].get("24h") is not None] or [0.0]),
                        "days": len(set(days))}
    b = out.get("buys")
    if not b or b["n"] < READ_BUYS or b["days"] < READ_DAYS:
        n, d = (b["n"], b["days"]) if b else (0, 0)
        out["verdict"] = ("collecting", f"{min(n, READ_BUYS)} of {READ_BUYS} BUYs with a 4h outcome"
                                        + (f" ({n} so far)" if n > READ_BUYS else "") + f", {d} of {READ_DAYS} days")
    elif b["mean4h"] <= 0:
        out["verdict"] = ("killed", f"BUY mean {b['mean4h']:+.1%} over {b['n']}")
    elif (b["lo95"] or -1) > 0 and b["mean4h"] > out["clean"]["mean4h"]:
        out["verdict"] = ("adopt candidate (check halves)", f"BUY mean {b['mean4h']:+.1%}, 95% low {b['lo95']:+.1%}")
    else:
        out["verdict"] = ("inconclusive", f"BUY mean {b['mean4h']:+.1%}, 95% low {b['lo95']}")
    return out


def render(r: dict) -> str:
    o = [f"meme judge (paper, since {r['first']}): {r['judged']} pools judged, {r['risk_clean']} RISK-clean, "
         f"{r['buy']} BUY, {r['pass']} PASS ({r['watch_asked']} watch re-asks)"]
    if r["kills"]:
        o.append("  killed by: " + ", ".join(f"{k} {v}" for k, v in sorted(r["kills"].items(), key=lambda x: -x[1])[:6]))
    for g, label in (("buys", "BUYs"), ("clean", "all RISK-clean (baseline)")):
        s = r.get(g)
        if s:
            o.append(f"  {label}: {s['n']} with 4h outcome, mean net 1h {s['mean1h']:+.1%} / 4h {s['mean4h']:+.1%} / 24h {s['mean24h']:+.1%}, "
                     f"median 4h {s['median4h']:+.1%}, win {s['win']:.0%}, dead {s['dead']:.0%}"
                     + (f", 4h 95% low {s['lo95']:+.1%}" if s["lo95"] is not None else ""))
            o.append("    best 4h: " + ", ".join(f"{v:+.0%} {k}" for v, k in s["top"]))
    if r.get("old_scoring"):
        o.append(f"  ({r['old_scoring']} outcomes scored before the 2026-11-06 exit-model fix are excluded)")
    v, why = r["verdict"]
    o.append(f"  verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--once", action="store_true", help="one discovery + processing step against the live APIs")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.once:
        async def one():
            j = MemeJudge(a.state)
            try:
                n = await j.discover()
                await j.process()
                return n
            finally:
                await j._c.aclose()
        print(f"first sight of {asyncio.run(one())} new pools")
    print(render(report(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
