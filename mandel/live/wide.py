"""
Widened asset sleeves (forward tests T-567 and T-568): more assets, holds up to 30 days, its own account and journal.
=====================================================================================================================

    python -m mandel.live.wide close    [--dry-run]   # runs at 12:46 and 15:46 ET; acts only 4-16 min before that day's close
    python -m mandel.live.wide options  [--dry-run]   # 15:27 ET: open or manage the GLD / TLT / USO put spreads
    python -m mandel.live.wide reconcile
    python -m mandel.live.wide status

  T-567  pre-holiday IWM: buy IWM at the close of the session before the last session ahead of a scheduled NYSE holiday,
         sell it at that pre-holiday session's close (T-349: +12.3 bps vs other days, 2000-2026, p 0.048; one-day hold).
         Early-close sessions (the day before Independence Day, Christmas Eve) are handled by the 12:46 run.
  T-576  IEF over the month's last session: bought at the close of the second-to-last session, sold at the last
         session's close (T-574: Treasury month-end extension, +10 bp 1990-2026 in IEF, decayed to ~0 since 2024).
  T-568  one defined-risk put credit spread per underlying on GLD, TLT and USO: the standard monthly expiry 30-45 days out,
         short strike the highest listed at or below 95% of spot, long strike WIDTH lower, closed at 50% of the credit or
         at 21 days to expiry (holds 9-24 days). Basis: each asset's implied variance exceeds its realised variance
         (T-50/T-244/T-271 gold, T-64 Treasuries, T-63/T-512 crude); the spread form is NOT backtested (forward only).
         ETF options are American and physically settled: exiting at 21 DTE keeps the short strike far from expiry.

Separate from T-559/T-560 in everything: its own capital (MANDEL_WIDE_CAPITAL, default 5,000), state directory
(MANDEL_WIDE_STATE), client-order prefix 'w-', KILL file, and Alpaca keys (a second paper account is recommended so the
two forward records do not share cash). Paper only, under the same live switch as mandel.live.alpaca. Never borrows:
the IWM slot is capped by cash plus what it already holds; a spread is opened only when its max loss fits its budget.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from mandel.live import sleeves as S

ET = ZoneInfo("America/New_York")
STATE = Path(os.environ.get("MANDEL_WIDE_STATE") or (Path.home() / "mandel-wide-state"))
JOURNAL = STATE / "journal.jsonl"
KILL = STATE / "KILL"
CAPITAL = float(os.environ.get("MANDEL_WIDE_CAPITAL") or 5000)
PREHOL_SLOT = 0.40                                  # of CAPITAL
MONTHEND_SLOT = 0.30                                # T-576: IEF held over the month's last session
SPREADS = {"GLD": 5.0, "TLT": 2.0, "USO": 2.0}       # underlying -> width in points
SPREAD_BUDGET = 0.10                                # max loss per spread, of CAPITAL
CLOSE_WINDOW_MIN = (4, 16)                          # act only this many minutes before the session's close


# ------------------------------------------------------------------------------------------------ calendar --

def sessions_from(cal: list) -> dict:
    """{date: close time} from Alpaca /v2/calendar rows."""
    out = {}
    for c in cal:
        hh, mm = (c.get("close") or "16:00").split(":")[:2]
        out[date.fromisoformat(c["date"])] = dtime(int(hh), int(mm))
    return out


def is_pre_holiday(day: date, sess: dict) -> bool:
    """``day`` is a session and a weekday between it and the next session is not a session (a scheduled holiday)."""
    if day not in sess:
        return False
    later = sorted(d for d in sess if d > day)
    if not later:
        return False
    d = day + timedelta(days=1)
    while d < later[0]:
        if d.weekday() < 5:
            return True
        d += timedelta(days=1)
    return False


def prehol_target(day: date, sess: dict) -> bool:
    """Hold IWM from ``day``'s close when the next session is a pre-holiday session."""
    later = sorted(d for d in sess if d > day)
    return bool(later) and is_pre_holiday(later[0], sess)


def monthend_target(day: date, sess: dict) -> bool:
    """Hold IEF from ``day``'s close when the next session is the last session of its month (T-576)."""
    later = sorted(d for d in sess if d > day)
    if not later:
        return False
    nxt = later[0]
    return not any(d > nxt and (d.year, d.month) == (nxt.year, nxt.month) for d in sess)


def in_close_window(now: datetime, close_t: dtime) -> bool:
    close_dt = now.replace(hour=close_t.hour, minute=close_t.minute, second=0, microsecond=0)
    mins = (close_dt - now).total_seconds() / 60
    return CLOSE_WINDOW_MIN[0] <= mins <= CLOSE_WINDOW_MIN[1]


# ------------------------------------------------------------------------------------------------- spreads --

@dataclass
class Plan:
    underlying: str
    expiry: date
    short_strike: float
    long_strike: float
    credit_mid: float
    max_loss: float


def plan_spread(underlying: str, today: date, spot: float, book: dict, budget: float) -> tuple:
    """T-560's selection with this underlying's width; ``book``: {expiry: {strike: (bid, ask)}}."""
    width = SPREADS[underlying]
    exp = S.monthly_expiry(today, book)
    if exp is None:
        return None, f"no monthly expiry {S.SPREAD_DTE[0]}-{S.SPREAD_DTE[1]} days out"
    puts = book[exp]
    shorts = [k for k in puts if k <= S.SPREAD_OTM * spot]
    if not shorts:
        return None, "no strike at or below 95% of spot"
    ks = max(shorts)
    kl = round(ks - width, 2)
    if kl not in puts:
        return None, f"long strike {kl} not listed"
    (sb, sa), (lb, la) = puts[ks], puts[kl]
    if sb <= 0 or sa < sb or la < lb or lb < 0:
        return None, f"no two-sided quotes on {ks}/{kl}"
    credit = round((sb + sa) / 2 - (lb + la) / 2, 2)
    if credit <= 0:
        return None, f"non-positive mid credit {credit}"
    max_loss = round((width - credit) * 100, 2)
    if max_loss > budget:
        return None, f"max loss ${max_loss} above the budget ${budget:.0f}"
    return Plan(underlying, exp, ks, kl, credit, max_loss), "open"


# -------------------------------------------------------------------------------------------------- runner --

def _journal(kind: str, payload: dict, dry: bool) -> None:
    rec = {"ts": datetime.now(ET).isoformat(timespec="seconds"), "kind": kind, "dry_run": dry, **payload}
    if dry:
        print(json.dumps(rec, default=str, indent=1)); return
    STATE.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _guard(phase: str) -> None:
    if KILL.exists():
        sys.exit(f"{phase}: KILL file present at {KILL}: no orders")


def _send(api, order: dict, dry: bool) -> None:
    if dry:
        print("DRY RUN, not sent:", json.dumps(order)); return
    try:
        res = api.submit(order)
        _journal("order.sent", {"order": order, "id": res.get("id"), "status": res.get("status")}, False)
    except Exception as e:
        _journal("order.rejected", {"order": order, "error": str(e)[:500]}, False)


def _calendar(api, today: date) -> dict:
    return sessions_from(api.calendar((today - timedelta(days=10)).isoformat(), (today + timedelta(days=40)).isoformat()))


def phase_close(api, dry: bool, now: Optional[datetime] = None) -> None:
    _guard("close")
    from mandel.live.alpaca import auction_order
    now = now or datetime.now(ET)
    today = now.date()
    sess = _calendar(api, today)
    if today not in sess:
        print(f"{today} is not a session"); return
    if not dry and not in_close_window(now, sess[today]):
        print(f"outside the closing-auction window for a {sess[today]} close"); return
    acct = api.account()
    cash = float(acct.get("cash") or 0)
    held = {p["symbol"]: int(float(p["qty"])) for p in api.positions() if p["symbol"] in ("IWM", "IEF")}
    snap = api.stock_snapshots(["IWM", "IEF"])
    plan = {"IWM": (prehol_target(today, sess), PREHOL_SLOT), "IEF": (monthend_target(today, sess), MONTHEND_SLOT)}
    orders, budgets, prices = [], {}, {}
    free = cash + sum(held.get(s, 0) * snap[s]["latestTrade"]["p"] for s in held)   # never borrows across both slots
    for sym, (hold, slot) in plan.items():
        px = snap[sym]["latestTrade"]["p"]
        budget = min(CAPITAL * slot, free)
        want = S.shares_for(budget, px) if hold else 0
        free -= want * px
        delta = want - held.get(sym, 0)
        budgets[sym], prices[sym] = budget, px
        if delta:
            orders.append(auction_order(sym, abs(delta), "buy" if delta > 0 else "sell", "cls",
                                        f"w-cls-{sym}-{today}-{uuid.uuid4().hex[:6]}", not api.live))
    _journal("close.decision", {"day": today, "close_time": sess[today], "pre_holiday_next": plan["IWM"][0],
                                "month_end_next": plan["IEF"][0], "prices": prices, "budgets": budgets, "held": held,
                                "orders": orders}, dry)
    for o in orders:
        _send(api, o, dry)


def _book(api, underlying: str, today: date) -> tuple:
    lo, hi = S.SPREAD_DTE
    cons = api.option_contracts(underlying, "put", (today + timedelta(days=lo)).isoformat(),
                                (today + timedelta(days=hi)).isoformat())
    snaps = api.option_snapshots([c["symbol"] for c in cons])
    book, sym = {}, {}
    for c in cons:
        q = (snaps.get(c["symbol"]) or {}).get("latestQuote") or {}
        if "bp" in q and "ap" in q:
            e, k = date.fromisoformat(c["expiration_date"]), float(c["strike_price"])
            book.setdefault(e, {})[k] = (float(q["bp"]), float(q["ap"]))
            sym[(e, k)] = c["symbol"]
    return book, sym


def phase_options(api, dry: bool) -> None:
    _guard("options")
    from mandel.live.alpaca import spread_held, spread_order
    today = datetime.now(ET).date()
    if today not in _calendar(api, today):
        print(f"{today} is not a session"); return
    positions = api.positions()
    for u in SPREADS:
        path = STATE / f"spread-{u}.json"
        st = json.loads(path.read_text()) if path.exists() else None
        if st and not spread_held(positions, st["short"]):   # the opening order expired or was rejected: never held
            _journal("spread.unfilled", {"underlying": u, "day": today, "state": st}, dry)
            if not dry:
                path.rename(STATE / f"spread-{u}-unfilled-{today}.json")
            st = None                        # fall through and plan again today
        if st:
            exp = date.fromisoformat(st["expiry"])
            sn = api.option_snapshots([st["short"], st["long"]])
            try:
                qs, ql = sn[st["short"]]["latestQuote"], sn[st["long"]]["latestQuote"]
                mid = round((qs["bp"] + qs["ap"]) / 2 - (ql["bp"] + ql["ap"]) / 2, 2)
            except (KeyError, TypeError):
                mid = None
            why = S.spread_exit(today, exp, st["credit"], mid)
            _journal("spread.check", {"underlying": u, "day": today, "state": st, "buyback_mid": mid, "exit": why}, dry)
            if why:
                _send(api, spread_order(st["short"], st["long"], 1, mid if mid is not None else SPREADS[u], False,
                                        f"w-{u}-close-{today}"), dry)
                if not dry:
                    path.rename(STATE / f"spread-{u}-closed-{today}.json")
            continue
        spot = api.stock_snapshots([u])[u]["latestTrade"]["p"]
        book, sym = _book(api, u, today)
        plan, why = plan_spread(u, today, spot, book, CAPITAL * SPREAD_BUDGET)
        _journal("spread.plan", {"underlying": u, "day": today, "spot": spot, "plan": plan.__dict__ if plan else None,
                                 "reason": why}, dry)
        if plan:
            s_sym, l_sym = sym[(plan.expiry, plan.short_strike)], sym[(plan.expiry, plan.long_strike)]
            _send(api, spread_order(s_sym, l_sym, 1, plan.credit_mid, True, f"w-{u}-open-{today}"), dry)
            if not dry:
                STATE.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"expiry": plan.expiry.isoformat(), "short": s_sym, "long": l_sym,
                                            "credit": plan.credit_mid, "opened": today.isoformat()}))


def phase_reconcile(api) -> None:
    since = (datetime.now(ET) - timedelta(days=3)).isoformat()
    fills = [o for o in api.orders("closed", after=since) if str(o.get("client_order_id", "")).startswith("w-")]
    for o in fills:
        _journal("order.fill", {k: o.get(k) for k in ("client_order_id", "symbol", "side", "qty", "filled_qty",
                                                      "filled_avg_price", "time_in_force", "status", "filled_at",
                                                      "order_class")}, False)
    print(f"{len(fills)} widened-sleeve orders reconciled")


def phase_status(api) -> None:
    a = api.account()
    print(json.dumps({"paper": not api.live, "equity": a.get("equity"), "cash": a.get("cash"), "capital": CAPITAL,
                      "positions": [(p["symbol"], p["qty"]) for p in api.positions()],
                      "spreads": {u: (json.loads((STATE / f"spread-{u}.json").read_text())
                                      if (STATE / f"spread-{u}.json").exists() else None) for u in SPREADS},
                      "kill": KILL.exists()}, indent=1))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m mandel.live.wide")
    p.add_argument("phase", choices=["close", "options", "reconcile", "status"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--live", action="store_true", help="real money: also needs MANDEL_ALPACA_LIVE=I-UNDERSTAND")
    a = p.parse_args(argv)
    from mandel.live.alpaca import Alpaca
    api = Alpaca(live=a.live)
    {"close": lambda: phase_close(api, a.dry_run), "options": lambda: phase_options(api, a.dry_run),
     "reconcile": lambda: phase_reconcile(api), "status": lambda: phase_status(api)}[a.phase]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
