"""Macro and commodity daily series for the research queue: FRED's public
CSVs (no key) and the ETFs that carry sectors, metals, miners and energy
(Nasdaq data API, ten years, no key). Stored as state/macro/<ID>.json,
[[date, value], ...], refreshed from the last date on file.

    python -m cryptobot.data.macro --state state            # fetch or extend everything
    python -m cryptobot.data.macro --state state --report

FRED ids: DFF (fed funds), DGS2, DGS10, DFII10 (10y real), T10YIE
(breakeven), DTWEXBGS (broad dollar), VIXCLS, DCOILWTICO, DCOILBRENTEU,
DHHNGSP (Henry Hub gas), BAMLH0A0HYM2 (HY spread), DEXUSEU, DEXJPUS.
ETFs: GLD SLV PPLT PALL CPER (metals), GDX SIL (miners), USO UNG XLE XOP
(energy), XLF XLK XLV XLI XLU XLP XLY (sectors), SPY QQQ IWM (indices),
TLT HYG (bonds), EEM EFA (foreign), IBIT.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from .nasdaq import HEADERS, parse_closes

logger = logging.getLogger(__name__)

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
NASDAQ_URL = "https://api.nasdaq.com/api/quote/{sym}/historical"
FRED_IDS = ("DFF", "DGS2", "DGS10", "DFII10", "T10YIE", "DTWEXBGS", "VIXCLS", "DCOILWTICO", "DCOILBRENTEU",
            "DHHNGSP", "BAMLH0A0HYM2", "DEXUSEU", "DEXJPUS")
ETFS = ("GLD", "SLV", "PPLT", "PALL", "CPER", "GDX", "SIL", "USO", "UNG", "XLE", "XOP",
        "XLF", "XLK", "XLV", "XLI", "XLU", "XLP", "XLY", "SPY", "QQQ", "IWM", "TLT", "HYG", "EEM", "EFA", "IBIT")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cryptobot-research"}


def macro_dir(state_dir: Path) -> Path:
    return Path(state_dir) / "macro"


def read_series(state_dir: Path, sid: str) -> list[tuple[str, float]]:
    p = macro_dir(state_dir) / f"{sid}.json"
    return [(d, float(v)) for d, v in json.loads(p.read_text())] if p.exists() else []


def write_series(state_dir: Path, sid: str, rows: list[tuple[str, float]]) -> None:
    p = macro_dir(state_dir) / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([[d, v] for d, v in sorted(dict(rows).items())]))


def parse_fred(text: str) -> list[tuple[str, float]]:
    out = []
    for line in text.splitlines()[1:]:
        parts = line.strip().split(",")
        if len(parts) == 2 and parts[1] not in (".", ""):
            try:
                out.append((parts[0], float(parts[1])))
            except ValueError:
                continue
    return out


async def fetch_fred(client, sid: str) -> list[tuple[str, float]]:
    r = await client.get(FRED_URL.format(id=sid))
    if r.status_code != 200:
        raise RuntimeError(f"FRED {sid} -> {r.status_code}")
    return parse_fred(r.text)


async def fetch_etf(client, sym: str, years: int = 10) -> list[tuple[str, float]]:
    end = dt.date.today()
    start = end.replace(year=end.year - years)
    r = await client.get(NASDAQ_URL.format(sym=sym), params={"assetclass": "etf", "fromdate": start.isoformat(),
                                                             "todate": end.isoformat(), "limit": 9999}, headers=HEADERS)
    if r.status_code != 200:
        raise RuntimeError(f"nasdaq {sym} -> {r.status_code}")
    return [(d.isoformat() if hasattr(d, "isoformat") else str(d), c) for d, c in parse_closes(r.json())]


async def update(state_dir: Path, client=None, fred_ids=FRED_IDS, etfs=ETFS, pause_s: float = 0.6) -> dict[str, int]:
    own = client is None
    client = client or httpx.AsyncClient(timeout=60, headers=UA, follow_redirects=True)
    added = {}
    try:
        for sid in fred_ids:
            try:
                rows = await fetch_fred(client, sid)
            except Exception as exc:                  # noqa: BLE001
                logger.warning("macro %s: %s", sid, exc)
                added[sid] = -1
                continue
            have = dict(read_series(state_dir, sid))
            new = [(d, v) for d, v in rows if d not in have]
            write_series(state_dir, sid, list(have.items()) + new)
            added[sid] = len(new)
            await asyncio.sleep(pause_s)
        for sym in etfs:
            try:
                rows = await fetch_etf(client, sym)
            except Exception as exc:                  # noqa: BLE001
                logger.warning("macro %s: %s", sym, exc)
                added[sym] = -1
                continue
            have = dict(read_series(state_dir, sym))
            new = [(d, v) for d, v in rows if d not in have]
            write_series(state_dir, sym, list(have.items()) + new)
            added[sym] = len(new)
            await asyncio.sleep(pause_s)
    finally:
        if own:
            await client.aclose()
    return added


def status(state_dir: Path) -> dict[str, dict]:
    out = {}
    d = macro_dir(state_dir)
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        rows = read_series(state_dir, p.stem)
        out[p.stem] = {"n": len(rows), "first": rows[0][0] if rows else None, "last": rows[-1][0] if rows else None,
                       "value": rows[-1][1] if rows else None}
    return out


def render(st: dict) -> str:
    if not st:
        return "no macro series yet"
    return "\n".join(f"{k:14s} {v['n']:6d} rows  {v['first']} .. {v['last']}  last {v['value']:,.4g}" for k, v in st.items())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if not a.report:
        added = asyncio.run(update(a.state))
        print("fetched: " + ", ".join(f"{k} {'ERR' if n < 0 else f'+{n}'}" for k, n in added.items()))
    print(render(status(a.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
