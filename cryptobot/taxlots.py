"""Lot-level export of real trades for tax reporting.

One row per closed real trade: venue, coin, side, quantity, open and
close times (UTC), proceeds, cost basis, modelled fees, the fees the
venue reported for that trade's fills when the execution log has them,
and net P&L. Coinbase and Kalshi perpetual-style contracts are not
Section 1256 instruments and 1099-DA reports gross proceeds without
basis, so this file is the basis record.

    python -m cryptobot.taxlots --state-dir state [--year 2026] [--out lots.csv]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Optional

from .execlog import FILE as EXECLOG_FILE, load as load_log

BOOK_FILES = {"bounce": "cryptobot_real_portfolio.json", "carry": "cryptobot_carry_real.json"}


def _utc(ts: float) -> str:
    return dt.datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")


def closed_trades(state_dir: Path) -> list[dict]:
    out = []
    for strategy, fname in BOOK_FILES.items():
        p = state_dir / fname
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        for t in d.get("closed") or []:
            out.append(dict(t, strategy=strategy))
    return out


def venue_fees(rows: list[dict]) -> dict[tuple, float]:
    """(coin, side, order_id) -> fee the venue reported; summed per coin and
    day for matching to trades when no order id is available."""
    fees: dict[tuple, float] = {}
    for r in rows:
        if r.get("kind") != "fill" or r.get("book") != "real" or r.get("fee_actual") is None:
            continue
        day = dt.datetime.utcfromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        key = (r["coin"], day)
        fees[key] = fees.get(key, 0.0) + float(r["fee_actual"])
    return fees


def lots(state_dir: Path, year: Optional[int] = None, venue: str = "") -> list[dict]:
    fees = venue_fees(load_log(state_dir / EXECLOG_FILE))
    out = []
    for t in closed_trades(state_dir):
        closed_at = float(t.get("closed_at") or 0)
        if year and dt.datetime.utcfromtimestamp(closed_at).year != year:
            continue
        side = str(t.get("side", "")).lower()
        qty = float(t.get("size_usd", 0)) / float(t.get("entry_price") or 1) if t.get("entry_price") else 0.0
        entry, exit_ = float(t.get("entry_price") or 0), float(t.get("exit_price") or 0)
        if side == "short":
            proceeds, basis = qty * entry, qty * exit_
        else:
            proceeds, basis = qty * exit_, qty * entry
        opened_day = dt.datetime.utcfromtimestamp(float(t.get("opened_at") or 0)).strftime("%Y-%m-%d")
        closed_day = dt.datetime.utcfromtimestamp(closed_at).strftime("%Y-%m-%d")
        venue_fee = fees.get((t.get("symbol"), opened_day), 0.0) + fees.get((t.get("symbol"), closed_day), 0.0)
        out.append({
            "strategy": t["strategy"], "venue": venue, "coin": t.get("symbol"), "side": side,
            "quantity": round(qty, 6), "opened_utc": _utc(t.get("opened_at") or 0), "closed_utc": _utc(closed_at),
            "proceeds_usd": round(proceeds, 4), "cost_basis_usd": round(basis, 4),
            "fees_modelled_usd": round(float(t.get("costs_usd") or 0), 4),
            "fees_venue_usd": round(venue_fee, 4) if venue_fee else "",
            "funding_usd": round(float(t.get("funding_usd") or 0), 4),
            "net_pnl_usd": round(float(t.get("pnl_usd") or 0), 4),
            "exit_reason": t.get("exit_reason", ""),
        })
    out.sort(key=lambda r: r["closed_utc"])
    return out


FIELDS = ["strategy", "venue", "coin", "side", "quantity", "opened_utc", "closed_utc", "proceeds_usd",
          "cost_basis_usd", "fees_modelled_usd", "fees_venue_usd", "funding_usd", "net_pnl_usd", "exit_reason"]


def write_csv(rows: list[dict], out) -> None:
    w = csv.DictWriter(out, fieldnames=FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state-dir", type=Path, default=Path("state"))
    ap.add_argument("--year", type=int)
    ap.add_argument("--venue", default="")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = lots(args.state_dir, args.year, args.venue)
    if args.out:
        with args.out.open("w", newline="") as f:
            write_csv(rows, f)
        print(f"{len(rows)} lots -> {args.out}; net P&L {sum(r['net_pnl_usd'] for r in rows):+.2f} USD")
    else:
        write_csv(rows, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
