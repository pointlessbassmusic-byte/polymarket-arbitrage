"""Nasdaq's public data API, shared by the studies and collectors.

No key; the edge drops non-browser user agents, so every caller sends
the same headers. Values arrive as display strings ('$1.72', '($0.13)',
'1,000', 'N/A'); the parsers here are the one place that decodes them.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}
HIST_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
CAL_URL = "https://api.nasdaq.com/api/calendar/earnings"


def money(s) -> Optional[float]:
    """'$1.72' -> 1.72, '($0.13)' -> -0.13, '1,000' -> 1000.0, '' / 'N/A' -> None."""
    if s in (None, "", "N/A", "--"):
        return None
    t = str(s).replace("$", "").replace(",", "").replace("%", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def parse_history(payload: dict) -> list[dict]:
    """Rows of {date, open, close, high, low, volume}, oldest first; rows
    without a positive open and close are dropped."""
    out = []
    for r in (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []:
        try:
            day = dt.datetime.strptime(r["date"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        o, c = money(r.get("open")), money(r.get("close"))
        if o and c and o > 0 and c > 0:
            out.append({"date": day.isoformat(), "open": o, "close": c,
                        "high": money(r.get("high")), "low": money(r.get("low")), "volume": money(r.get("volume"))})
    out.sort(key=lambda x: x["date"])
    return out


def parse_closes(payload: dict) -> list[tuple[dt.date, float]]:
    """(date, close) oldest first, keeping days that have a close even
    when the open is missing."""
    out = []
    for r in (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []:
        try:
            day = dt.datetime.strptime(r["date"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        c = money(r.get("close"))
        if c and c > 0:
            out.append((day, c))
    return sorted(out)


def payload_ok(payload: dict) -> bool:
    """Nasdaq answers HTTP 200 with data=null in two cases that must be
    told apart by the body's own rCode: 200 means a genuinely empty
    answer (a market holiday's calendar, a symbol with no rows), anything
    else is a throttle or an unknown symbol and must not be stored."""
    if not isinstance(payload, dict):
        return False
    if payload.get("data") is not None:
        return True
    return ((payload.get("status") or {}).get("rCode")) == 200


# -- JSON lines, used by every collector --------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def append_jsonl(path: Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")
