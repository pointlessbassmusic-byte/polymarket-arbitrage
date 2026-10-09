"""Execution log: what real money actually paid.

Coinbase Derivatives exposes no fill history beyond individual orders
and no funding history at all, so the only record of execution quality
is the one the bot keeps. Every real fill (with the signal price it was
meant to get, the modelled fee and the fee the venue charged), every
funding accrual on a real position, every margin snapshot (flagged when
it falls near the 16:00 ET intraday-to-overnight switch) and every
real-book skip goes to an append-only JSONL under the state directory.

`python -m cryptobot.execlog --state-dir state` summarises it: slippage
per coin in basis points, fee charged vs modelled, funding paid or
received, peak margin usage. That report is the evidence the
small-real-money gates in RESEARCH-2026-10.md ask for.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import statistics
import time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

FILE = "execution.jsonl"
ET = ZoneInfo("America/New_York")
SWITCH_WINDOW_S = 1800       # +-30 min around 16:00 ET


def near_margin_switch(ts: float) -> bool:
    """True within half an hour of 16:00 ET, when Coinbase moves from
    intraday to overnight margin rates."""
    local = dt.datetime.fromtimestamp(ts, ET)
    switch = local.replace(hour=16, minute=0, second=0, microsecond=0)
    return abs((local - switch).total_seconds()) <= SWITCH_WINDOW_S


def slippage_bps(side: str, intended: float, filled: float) -> float:
    """Adverse slippage in basis points, positive = cost. A short that
    sells below the intended price paid; a cover that buys above it paid."""
    if intended <= 0:
        return 0.0
    if side == "short":
        return (intended - filled) / intended * 1e4
    return (filled - intended) / intended * 1e4


class ExecutionLog:
    def __init__(self, path: Optional[Path]):
        self.path = path
        self.written = 0

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def record(self, kind: str, **fields) -> Optional[dict]:
        if self.path is None:
            return None
        row = {"ts": fields.pop("ts", time.time()), "kind": kind, **fields}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(row, default=float) + "\n")
            self.written += 1
        except OSError:
            logger.exception("execution log write failed")
        return row

    # -- typed helpers -------------------------------------------------------

    def fill(self, *, book: str, coin: str, side: str, contracts: float, qty: float,
             intended: float, filled: float, notional: float, fee_modelled: float,
             fee_actual: Optional[float], order_id=None, reason: str = "") -> dict:
        return self.record("fill", book=book, coin=coin, side=side, contracts=contracts, qty=qty,
                           intended=intended, filled=filled, notional=notional,
                           slippage_bps=slippage_bps(side, intended, filled),
                           fee_modelled=fee_modelled, fee_actual=fee_actual,
                           order_id=order_id, reason=reason)

    def funding(self, *, book: str, coin: str, rate_hourly: float, hours: float,
                notional: float, usd: float) -> dict:
        return self.record("funding", book=book, coin=coin, rate_hourly=rate_hourly,
                           hours=hours, notional=notional, usd=usd)

    def margin(self, *, balance: dict) -> dict:
        total = float(balance.get("total_usd_balance") or 0.0)
        avail = float(balance.get("available_margin") or 0.0)
        usage = (1.0 - avail / total) if total > 0 else 0.0
        return self.record("margin", usage=usage, near_switch=near_margin_switch(time.time()),
                           **{k: float(v) for k, v in balance.items()})

    def skip(self, *, book: str, coin: str, stage: str, reason: str, size: float = 0.0) -> dict:
        return self.record("skip", book=book, coin=coin, stage=stage, reason=reason, size=size)


# -- reading ---------------------------------------------------------------

def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _fmt_bps(xs: list[float]) -> str:
    if not xs:
        return "n/a"
    med = statistics.median(xs)
    worst = max(xs)
    return f"mean {statistics.mean(xs):+.1f} bp, median {med:+.1f}, worst {worst:+.1f} (n={len(xs)})"


def summary(rows: list[dict], since: float = 0.0) -> dict:
    rows = [r for r in rows if r.get("ts", 0) >= since]
    fills = [r for r in rows if r.get("kind") == "fill" and r.get("book") == "real"]
    by_coin: dict[str, list[float]] = {}
    for f in fills:
        by_coin.setdefault(f["coin"], []).append(float(f.get("slippage_bps", 0.0)))
    fee_modelled = sum(float(f.get("fee_modelled") or 0.0) for f in fills)
    fee_rows = [f for f in fills if f.get("fee_actual") is not None]
    fee_actual = sum(float(f["fee_actual"]) for f in fee_rows)
    fee_modelled_matched = sum(float(f.get("fee_modelled") or 0.0) for f in fee_rows)
    funding = [r for r in rows if r.get("kind") == "funding" and r.get("book") == "real"]
    fund_by_coin: dict[str, float] = {}
    for r in funding:
        fund_by_coin[r["coin"]] = fund_by_coin.get(r["coin"], 0.0) + float(r.get("usd") or 0.0)
    margins = [r for r in rows if r.get("kind") == "margin"]
    usages = [float(r.get("usage") or 0.0) for r in margins]
    switch = [float(r.get("usage") or 0.0) for r in margins if r.get("near_switch")]
    skips = [r for r in rows if r.get("kind") == "skip" and r.get("book") == "real"]
    unfilled = sum(1 for r in skips if r.get("stage") == "unfilled")
    return {
        "unfilled": unfilled,
        "fills": len(fills),
        "slippage_bps_by_coin": by_coin,
        "slippage_bps_all": [x for xs in by_coin.values() for x in xs],
        "fee_modelled": fee_modelled,
        "fee_actual": fee_actual if fee_rows else None,
        "fee_modelled_matched": fee_modelled_matched,
        "fee_rows": len(fee_rows),
        "funding_usd_by_coin": fund_by_coin,
        "margin_snapshots": len(margins),
        "margin_peak": max(usages) if usages else None,
        "margin_peak_near_switch": max(switch) if switch else None,
        "margin_over_90": sum(1 for u in usages if u > 0.9),
        "skips": len(skips),
    }


def render(s: dict) -> str:
    out = [f"real fills: {s['fills']}"]
    for coin, xs in sorted(s["slippage_bps_by_coin"].items()):
        out.append(f"  {coin}: slippage {_fmt_bps(xs)}")
    if s["slippage_bps_all"]:
        out.append(f"  all: slippage {_fmt_bps(s['slippage_bps_all'])}")
    if s["fee_actual"] is not None:
        gap = s["fee_actual"] - s["fee_modelled_matched"]
        out.append(f"fees: charged ${s['fee_actual']:.2f} vs modelled ${s['fee_modelled_matched']:.2f} "
                   f"({gap:+.2f}) on {s['fee_rows']} fills with a venue fee")
    else:
        out.append(f"fees: modelled ${s['fee_modelled']:.2f}; no venue fee recorded yet")
    if s["funding_usd_by_coin"]:
        tot = sum(s["funding_usd_by_coin"].values())
        parts = ", ".join(f"{c} {v:+.2f}" for c, v in sorted(s["funding_usd_by_coin"].items()))
        out.append(f"funding (real): {tot:+.2f} USD ({parts})")
    if s["margin_snapshots"]:
        out.append(f"margin: {s['margin_snapshots']} snapshots, peak usage {100 * s['margin_peak']:.0f}%"
                   + (f", peak near 16:00 ET switch {100 * s['margin_peak_near_switch']:.0f}%"
                      if s["margin_peak_near_switch"] is not None else "")
                   + (f", {s['margin_over_90']} above 90%" if s["margin_over_90"] else ""))
    if s["skips"]:
        out.append(f"real-book skips: {s['skips']}" + (f" ({s['unfilled']} unfilled IOC orders)" if s.get("unfilled") else ""))
    return "\n".join(out)


def digest_line(path: Optional[Path], since: float) -> str:
    """One line for the daily digest."""
    if path is None:
        return ""
    s = summary(load(path), since)
    if not s["fills"] and not s["margin_snapshots"]:
        return ""
    bits = [f"execution: {s['fills']} real fills"]
    if s["slippage_bps_all"]:
        bits.append(f"slippage mean {statistics.mean(s['slippage_bps_all']):+.1f} bp")
    if s["fee_actual"] is not None:
        bits.append(f"fees {s['fee_actual']:.2f} vs model {s['fee_modelled_matched']:.2f}")
    if s["margin_peak"] is not None:
        bits.append(f"margin peak {100 * s['margin_peak']:.0f}%")
    return ", ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser(description="summarise the real-money execution log")
    ap.add_argument("--state-dir", type=Path, default=Path("state"))
    ap.add_argument("--days", type=float, default=0.0, help="only the last N days (0 = all)")
    args = ap.parse_args()
    rows = load(args.state_dir / FILE)
    since = time.time() - args.days * 86400 if args.days else 0.0
    print(render(summary(rows, since)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
