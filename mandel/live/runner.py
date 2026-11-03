"""
Paper runner for the forward tests T-559 (calendar sleeve) and T-560 (XSP put spread).
=======================================================================================

    python -m mandel.live.runner close    [--dry-run]   # 15:40-15:48 ET: closing-auction orders for tonight's holdings
    python -m mandel.live.runner open     [--dry-run]   # 08:30-09:25 ET: opening-auction sale of the overnight QQQM
    python -m mandel.live.runner options  [--dry-run]   # 15:20-15:40 ET: open or manage the XSP put spread
    python -m mandel.live.runner reconcile              # after 16:15 ET: fills vs the modelled price
    python -m mandel.live.runner status

Paper account only unless the user sets the live switch (see mandel.live.alpaca). A file mandel/state/paper/KILL
stops every order-placing phase.

Live arm (T-744, the minimum-size execution test of the calendar sleeve), ``--live``:
  * its own state directory (MANDEL_LIVE_STATE, journal + KILL), never the paper one;
  * FIXED size: MANDEL_LIVE_SHARES whole shares (default 1) per symbol whose rule fires, never a capital fraction, and
    never more than the account's cash (no borrowing);
  * true auction orders ('cls' by 15:50 ET, 'opg' by 09:28 ET), the thing the paper venue could not measure;
  * a realised-loss halt: once the journal's closed round trips lose more than MANDEL_LIVE_MAX_LOSS_USD (default 40)
    no further order is placed until the user removes the HALT file; the options sleeve never runs live;
  * every order-placing phase journals a 'live.armed' row (the switch, the size, the halt) before it acts, which
    import_linode mirrors into the ledger with actor "human": the user created the switch, not Mandel. Every decision, order and fill is appended to mandel/state/paper/journal.jsonl and
summarised in the ledger ('paper.decision'), so the forward tests are scored from records written before outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from mandel._io import append_line
from mandel.ledger import Ledger, utcnow_iso
from mandel.live import sleeves as S
import os

from mandel.paths import MANDEL_ROOT

ET = ZoneInfo("America/New_York")
# On the Linode the journal lives outside the repository (MANDEL_PAPER_STATE) and the ledger is not touched
# (MANDEL_PAPER_LEDGER=0): one hash chain, one writer. The journal is imported into Mandel's ledger later.
STATE = Path(os.environ.get("MANDEL_PAPER_STATE") or (MANDEL_ROOT / "state" / "paper"))
USE_LEDGER = os.environ.get("MANDEL_PAPER_LEDGER", "1") != "0"
JOURNAL = STATE / "journal.jsonl"
KILL = STATE / "KILL"
SPREAD_STATE = STATE / "spread.json"
CAPITAL_SPLIT = {"calendar": 0.60, "spread_risk": 0.40}   # of the sleeve capital; the spread slot is its max-loss budget
# The sleeves trade a FIXED capital, not the account's equity: a paper account can be shared (the crypto child's QQQ and
# XLF pilots ran in the one this was installed on) and the forward test rehearses a small live account.
SLEEVE_CAPITAL = float(os.environ.get("MANDEL_PAPER_CAPITAL") or 5000)
LIVE_SHARES = max(1, int(os.environ.get("MANDEL_LIVE_SHARES") or 1))           # per symbol whose rule fires
LIVE_MAX_LOSS_USD = float(os.environ.get("MANDEL_LIVE_MAX_LOSS_USD") or 40)    # realised, cumulative; then HALT
HALT = STATE / "HALT"


def configure(live: bool) -> None:
    """Point the module at the live arm's own state (journal, KILL, HALT) when running --live. The paper state is never
    shared with real money: two journals, two kill files, two trackers rows (T-559 paper, T-744 live)."""
    global STATE, JOURNAL, KILL, SPREAD_STATE, HALT
    if live:
        STATE = Path(os.environ.get("MANDEL_LIVE_STATE") or (MANDEL_ROOT / "state" / "live"))
    JOURNAL, KILL, SPREAD_STATE, HALT = STATE / "journal.jsonl", STATE / "KILL", STATE / "spread.json", STATE / "HALT"


def sleeve_capital(equity: float) -> float:
    return min(SLEEVE_CAPITAL, equity)


def calendar_capital(equity: float, cash: float, own_value: float) -> float:
    """The calendar slot never borrows: capped by cash plus what it already holds (SPYM/QQQM at market)."""
    return max(0.0, min(sleeve_capital(equity) * CAPITAL_SPLIT["calendar"], cash + own_value))


def _journal(kind: str, payload: dict, dry: bool) -> None:
    rec = {"ts": utcnow_iso(), "kind": kind, "dry_run": dry, **payload}
    if dry:
        print(json.dumps(rec, default=str, indent=1))
        return
    STATE.mkdir(parents=True, exist_ok=True)
    append_line(JOURNAL, json.dumps(rec, default=str))
    if USE_LEDGER:
        summary = json.loads(json.dumps({k: payload[k] for k in list(payload)[:6]}, default=str))   # dates -> text
        Ledger().append("paper.decision", {"kind": kind, "summary": summary}, actor="mandel")


def _guard(phase: str) -> None:
    if KILL.exists():
        sys.exit(f"{phase}: KILL file present at {KILL}: no orders")


def realised_loss(journal_path: Path) -> float:
    """Cumulative realised P&L of the closed round trips in a journal (negative = loss), the tracker's accounting."""
    from mandel.live import tracker as T
    rows = T._journal(journal_path)
    return float(T.calendar_progress(rows).get("pnl_usd") or 0.0)


def _live_guard(api, phase: str, dry: bool) -> None:
    """Real money only: refuse while HALT stands, halt (and journal why) once realised losses pass the cap, and record
    the arming state before any order. The paper arm never reaches this."""
    if not getattr(api, "live", False):
        return
    if HALT.exists():
        sys.exit(f"{phase}: HALT file present at {HALT} (realised loss cap reached earlier): no orders until the user removes it")
    pnl = realised_loss(JOURNAL)
    if pnl < -LIVE_MAX_LOSS_USD:
        _journal("live.halted", {"phase": phase, "realised_pnl_usd": round(pnl, 2), "max_loss_usd": LIVE_MAX_LOSS_USD}, dry)
        if not dry:
            STATE.mkdir(parents=True, exist_ok=True)
            HALT.write_text(f"realised {pnl:.2f} < -{LIVE_MAX_LOSS_USD:.2f} at {utcnow_iso()}\n")
        sys.exit(f"{phase}: realised loss {pnl:.2f} passed the cap {LIVE_MAX_LOSS_USD:.2f}: HALT written, no orders")
    _journal("live.armed", {"phase": phase, "switch": os.environ.get("MANDEL_ALPACA_LIVE") == "I-UNDERSTAND",
                            "read_only": bool(getattr(api, "read_only", False)), "shares_per_symbol": LIVE_SHARES,
                            "max_loss_usd": LIVE_MAX_LOSS_USD, "realised_pnl_usd": round(pnl, 2), "endpoint": api.base}, dry)


def _sessions(api, around: date) -> list[date]:
    cal = api.calendar((around - timedelta(days=45)).isoformat(), (around + timedelta(days=75)).isoformat())
    return [date.fromisoformat(c["date"]) for c in cal]


def _mtd(bars: list[dict], before: date) -> Optional[float]:
    """Month-to-date return through the last close strictly before ``before`` (previous-close reading)."""
    rows = [(date.fromisoformat(b["t"][:10]), b["c"]) for b in bars]
    rows = [r for r in rows if r[0] < before]
    if not rows:
        return None
    last_day, last = rows[-1]
    prev_month = [c for d, c in rows if (d.year, d.month) < (last_day.year, last_day.month)]
    return last / prev_month[-1] - 1 if prev_month else None


def phase_close(api, dry: bool) -> None:
    _guard("close")
    _live_guard(api, "close", dry)
    today = datetime.now(ET).date()
    sessions = _sessions(api, today)
    if today not in sessions:
        print("not a session"); return
    acct = api.account()
    equity, cash = float(acct["equity"]), float(acct.get("cash") or 0)
    snap = api.stock_snapshots([S.SPX_ETF, "QQQM"])
    db = snap[S.SPX_ETF]["dailyBar"]
    bar = {"high": db["h"], "low": db["l"], "last": snap[S.SPX_ETF]["latestTrade"]["p"]}
    bars = api.daily_bars(["SPY", "TLT"], (today - timedelta(days=70)).isoformat())
    held = {p["symbol"]: int(float(p["qty"])) for p in api.positions() if p["symbol"] in (S.SPX_ETF, "QQQM")}
    own_value = sum(q * snap[s]["latestTrade"]["p"] for s, q in held.items())
    capital = calendar_capital(equity, cash, own_value)
    dec = S.close_decision(today, sessions, capital, bar, _mtd(bars.get("SPY", []), today), _mtd(bars.get("TLT", []), today))
    orders = []
    skipped = {}
    spend = 0.0
    for sym, usd in dec.targets.items():
        px = snap[sym]["latestTrade"]["p"]
        if api.live:                                       # T-744: fixed minimum size, never more than cash allows
            want = LIVE_SHARES if usd > 0 else 0
            if want and cash - spend < want * px * 1.01:
                skipped[sym] = f"cash {cash - spend:.2f} < {want} x {px:.2f}: no buy (never borrow)"
                want = held.get(sym, 0)
        else:
            want = S.shares_for(usd, px)
        delta = want - held.get(sym, 0)
        if delta > 0:
            spend += delta * px
        if delta:
            orders.append(api_order(sym, delta, "cls", today, not api.live))
    _journal("close.decision", {"day": today, "equity": equity, "cash": cash, "sleeve_capital": SLEEVE_CAPITAL,
                                "capital": capital, "snapshot_splg": bar, "live": bool(api.live),
                                "shares_per_symbol": LIVE_SHARES if api.live else None, "skipped": skipped or None,
                                "targets": dec.targets, "reasons": dec.reasons, "held": held, "orders": orders}, dry)
    for o in orders:
        _send(api, o, dry)


def _is_session(api, today: date) -> bool:
    if today not in _sessions(api, today):
        print(f"{today} is not a trading session: nothing to do")
        return False
    return True


def phase_open(api, dry: bool) -> None:
    _guard("open")
    _live_guard(api, "open", dry)
    today = datetime.now(ET).date()
    if not _is_session(api, today):
        return
    held = {p["symbol"]: int(float(p["qty"])) for p in api.positions()}
    q = held.get("QQQM", 0)
    orders = [api_order("QQQM", -q, "opg", today, not api.live)] if q > 0 else []
    _journal("open.decision", {"day": today, "held": held, "orders": orders}, dry)
    for o in orders:
        _send(api, o, dry)


def api_order(sym: str, delta: int, when: str, day: date, paper: bool = False) -> dict:
    from mandel.live.alpaca import auction_order
    return auction_order(sym, abs(delta), "buy" if delta > 0 else "sell", when, f"m-{when}-{sym}-{day}-{uuid.uuid4().hex[:6]}",
                         paper)


def _send(api, order: dict, dry: bool) -> None:
    if dry:
        print("DRY RUN, not sent:", json.dumps(order)); return
    try:
        res = api.submit(order)
        _journal("order.sent", {"order": order, "id": res.get("id"), "status": res.get("status")}, False)
    except Exception as e:  # journal the rejection; never retry blindly
        _journal("order.rejected", {"order": order, "error": str(e)[:500]}, False)


def _put_book(api, today: date) -> tuple[dict, dict]:
    lo, hi = S.SPREAD_DTE
    cons = api.option_contracts("XSP", "put", (today + timedelta(days=lo)).isoformat(), (today + timedelta(days=hi)).isoformat())
    syms = [c["symbol"] for c in cons]
    snaps = api.option_snapshots(syms)
    book: dict = {}
    sym_of: dict = {}
    for c in cons:
        q = (snaps.get(c["symbol"]) or {}).get("latestQuote") or {}
        if "bp" in q and "ap" in q:
            e = date.fromisoformat(c["expiration_date"]); k = float(c["strike_price"])
            book.setdefault(e, {})[k] = (float(q["bp"]), float(q["ap"]))
            sym_of[(e, k)] = c["symbol"]
    return book, sym_of


def phase_options(api, dry: bool) -> None:
    _guard("options")
    if getattr(api, "live", False):
        sys.exit("options: the XSP spread sleeve is paper-only (T-560); the live arm is the calendar sleeve alone (T-744)")
    from mandel.live.alpaca import spread_held, spread_order
    today = datetime.now(ET).date()
    if not _is_session(api, today):
        return
    st = json.loads(SPREAD_STATE.read_text()) if SPREAD_STATE.exists() else None
    if st and not spread_held(api.positions(), st["short"]):   # the opening order expired or was rejected: never held
        _journal("spread.unfilled", {"day": today, "state": st}, dry)
        if not dry:
            SPREAD_STATE.rename(STATE / f"spread-unfilled-{today}.json")
        st = None                            # fall through and plan again today
    if st:                                   # manage the open spread
        exp = date.fromisoformat(st["expiry"])
        snaps = api.option_snapshots([st["short"], st["long"]])
        try:
            qs, ql = snaps[st["short"]]["latestQuote"], snaps[st["long"]]["latestQuote"]
            mid = round((qs["bp"] + qs["ap"]) / 2 - (ql["bp"] + ql["ap"]) / 2, 2)
        except (KeyError, TypeError):
            mid = None
        why = S.spread_exit(today, exp, st["credit"], mid)
        _journal("spread.check", {"day": today, "state": st, "buyback_mid": mid, "exit": why}, dry)
        if why:
            limit = mid if mid is not None else S.SPREAD_WIDTH
            _send(api, spread_order(st["short"], st["long"], 1, limit, False, f"m-xsp-close-{today}"), dry)
            if not dry:
                SPREAD_STATE.rename(STATE / f"spread-closed-{today}.json")
        return
    bars = api.daily_bars(["SPY"], (today - timedelta(days=400)).isoformat()).get("SPY", [])
    month_end = {}
    for b in bars:
        d = date.fromisoformat(b["t"][:10])
        if (d.year, d.month) < (today.year, today.month):
            month_end[(d.year, d.month)] = b["c"]
    trend = S.trend_ok([month_end[k] for k in sorted(month_end)])
    spot = api.stock_snapshots(["SPY"])["SPY"]["latestTrade"]["p"]       # XSP = SPX/10 ~ SPY (index spot not served)
    equity = float(api.account()["equity"])
    book, sym_of = _put_book(api, today)
    plan, why = S.plan_put_spread(today, spot, book, sleeve_capital(equity) * CAPITAL_SPLIT["spread_risk"], trend)
    _journal("spread.plan", {"day": today, "spot_proxy_spy": spot, "trend_ok": trend, "plan": plan.__dict__ if plan else None,
                             "reason": why}, dry)
    if plan:
        s_sym, l_sym = sym_of[(plan.expiry, plan.short_strike)], sym_of[(plan.expiry, plan.long_strike)]
        _send(api, spread_order(s_sym, l_sym, 1, plan.credit_mid, True, f"m-xsp-open-{today}"), dry)
        if not dry:
            SPREAD_STATE.write_text(json.dumps({"expiry": plan.expiry.isoformat(), "short": s_sym, "long": l_sym,
                                                "credit": plan.credit_mid, "opened": today.isoformat()}))


def _journaled(kind: str, keys: tuple) -> set:
    """Rows of ``kind`` already in the journal, keyed by ``keys``: reconcile runs daily over a 3-day window and must not
    journal the same fill twice (the first three sessions did; the tracker also dedupes on read)."""
    seen = set()
    try:
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") == kind and not r.get("dry_run"):
                seen.add(tuple(str(r.get(k)) for k in keys))
    except OSError:
        pass
    return seen


def journal_official_prints(fills: list[dict], prefix: str, fetch=None) -> int:
    """One ``print.official`` row per (symbol, day) for every stock symbol with a filled order in ``fills``: Yahoo's official
    open and close, the prints the calendar rules are defined on (see mandel/live/prints.py). Returns rows written."""
    from mandel.live.prints import official_prints
    syms = sorted({o["symbol"] for o in fills if o.get("status") == "filled" and o.get("symbol") and o.get("order_class") != "mleg"
                   and str(o.get("client_order_id", "")).startswith(prefix)})
    if not syms:
        return 0
    seen = _journaled("print.official", ("symbol", "day"))
    n = 0
    for sym, by_day in (fetch or official_prints)(syms).items():
        for day in sorted(by_day)[-4:]:
            if (sym, day) in seen:
                continue
            _journal("print.official", {"day": day, "symbol": sym, "open": by_day[day]["open"], "close": by_day[day]["close"],
                                        "source": "yahoo"}, False)
            n += 1
    return n


def phase_reconcile(api) -> None:
    since = (datetime.now(ET) - timedelta(days=3)).isoformat()
    fills = [o for o in api.orders("closed", after=since) if o.get("client_order_id", "").startswith("m-")]
    seen = _journaled("order.fill", ("client_order_id", "status"))
    new = [o for o in fills if (str(o.get("client_order_id")), str(o.get("status"))) not in seen]
    for o in new:
        _journal("order.fill", {k: o.get(k) for k in ("client_order_id", "symbol", "side", "qty", "filled_qty",
                                                      "filled_avg_price", "time_in_force", "status", "filled_at",
                                                      "order_class")}, False)
    try:
        n_prints = journal_official_prints(fills, "m-")
    except Exception as e:  # noqa: BLE001 - a Yahoo outage or odd body must not fail the reconcile
        n_prints = 0
        _journal("print.official.error", {"error": str(e)[:300]}, False)
    print(f"{len(fills)} Mandel orders reconciled ({len(new)} new), {n_prints} official prints journaled")


def phase_status(api) -> None:
    a = api.account()
    out = {"paper": not api.live, "equity": a.get("equity"), "cash": a.get("cash"),
           "positions": [(p["symbol"], p["qty"], p.get("unrealized_pl")) for p in api.positions()],
           "spread": json.loads(SPREAD_STATE.read_text()) if SPREAD_STATE.exists() else None,
           "kill": KILL.exists(), "state": str(STATE)}
    if api.live:
        out.update(live=True, armed=not getattr(api, "read_only", False), halt=HALT.exists(), shares_per_symbol=LIVE_SHARES,
                   max_loss_usd=LIVE_MAX_LOSS_USD, realised_pnl_usd=round(realised_loss(JOURNAL), 2),
                   account_blocked=bool(a.get("trading_blocked") or a.get("account_blocked")),
                   pattern_day_trader=a.get("pattern_day_trader"))
    print(json.dumps(out, indent=1))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m mandel.live.runner")
    p.add_argument("phase", choices=["close", "open", "options", "reconcile", "status"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--live", action="store_true", help="real money: also needs MANDEL_ALPACA_LIVE=I-UNDERSTAND")
    a = p.parse_args(argv)
    configure(a.live)
    from mandel.live.alpaca import Alpaca
    # reads and dry runs may open the live endpoint before the switch is typed; an order never can
    api = Alpaca(live=a.live, read_only=a.live and (a.dry_run or a.phase in ("reconcile", "status")))
    {"close": lambda: phase_close(api, a.dry_run), "open": lambda: phase_open(api, a.dry_run),
     "options": lambda: phase_options(api, a.dry_run), "reconcile": lambda: phase_reconcile(api),
     "status": lambda: phase_status(api)}[a.phase]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
