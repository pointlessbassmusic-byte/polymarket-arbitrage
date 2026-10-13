"""Daily collectors for the data the queue needs and nobody sells for free.

1. IBIT option surface (`btc-vrp-listed-options`, step 1). Cboe publishes
   a delayed quote for every listed IBIT option, with the exchange's own
   implied volatility and delta per contract, and a 30-day IV for the
   underlying. One snapshot a day after the close gives, in a year, the
   history the variance-risk-premium test needs: 30-day at-the-money IV
   (variance-time interpolated between the two bracketing expiries),
   25-delta put and call IV, the bid-ask spread at those strikes, and
   20- and 30-day realised volatility from IBIT's closes (seeded from
   the Nasdaq data API on the first run). Appended to
   state/options/ibit.jsonl, one JSON object per trading day.

3. The out-of-sample tracker for `divergence-catchup-btc` (cryptobot.oos_track).
   (A monthly earnings-panel step ran here for `pead-per-price-smallcap`
   until that hypothesis was killed on 2026-10-13; cryptobot.pead_collect
   monthly is still callable by hand.)

2. Kalshi hourly candles for the BTC and US500 perps
   (`cross-asset-crypto-leadlag` follow-up: does the BTC perp lead the
   US500 perp hour to hour while the cash market is closed?). The
   public candlestick endpoint keeps little hourly history, so the last
   48 hours are appended daily to state/kalshi_hourly/<ticker>.jsonl,
   deduplicated on the bar's end time.

    python -m cryptobot.vrp_collect --state state            # one snapshot of both
    python -m cryptobot.vrp_collect --state state --report   # the series so far

The desk runs both once a day when `collectors.enabled` is true in the
config (see collector_loop).
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import math
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
NASDAQ_URL = ("https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=etf"
              "&fromdate={start}&todate={end}&limit=9999")
KALSHI_CANDLES = "https://external-api.kalshi.com/trade-api/v2/margin/markets/{ticker}/candlesticks"
KALSHI_TICKERS = ("KXBTCPERP", "KXUS500PERP", "KXETHPERP")
from .data.nasdaq import HEADERS as UA  # noqa: E402  (Nasdaq drops non-browser agents; Cboe and Kalshi do not care)


# ------------------------------------------------------------- option chain

def parse_symbol(sym: str, root: str = "IBIT") -> Optional[tuple[dt.date, str, float]]:
    """IBIT261218P00060000 -> (2026-12-18, 'P', 60.0)."""
    if not sym.startswith(root) or len(sym) < len(root) + 15:
        return None
    body = sym[len(root):]
    try:
        expiry = dt.datetime.strptime(body[:6], "%y%m%d").date()
        right = body[6]
        strike = int(body[7:15]) / 1000.0
    except ValueError:
        return None
    return (expiry, right, strike) if right in ("C", "P") else None


def _mid(o: dict) -> float:
    b, a = float(o.get("bid") or 0), float(o.get("ask") or 0)
    return (a + b) / 2 if a > 0 and b > 0 else 0.0


def surface(chain: dict, asof: dt.date, root: str = "IBIT") -> dict:
    """Per-expiry ATM and 25-delta implied vols from a Cboe chain."""
    spot = float(chain.get("current_price") or chain.get("close") or 0)
    by_exp: dict[dt.date, list] = {}
    for o in chain.get("options", []):
        p = parse_symbol(o.get("option", ""), root)
        if not p:
            continue
        expiry, right, strike = p
        iv = float(o.get("iv") or 0)
        if iv <= 0 or expiry <= asof:
            continue
        by_exp.setdefault(expiry, []).append({"right": right, "strike": strike, "iv": iv,
                                              "delta": float(o.get("delta") or 0), "mid": _mid(o),
                                              "bid": float(o.get("bid") or 0), "ask": float(o.get("ask") or 0),
                                              "oi": float(o.get("open_interest") or 0)})
    out = {"spot": spot, "expiries": []}
    for expiry in sorted(by_exp):
        rows = by_exp[expiry]
        days = (expiry - asof).days
        calls = [r for r in rows if r["right"] == "C"]
        puts = [r for r in rows if r["right"] == "P"]
        if not calls or not puts or spot <= 0:
            continue
        atm_c = min(calls, key=lambda r: abs(r["strike"] - spot))
        atm_p = min(puts, key=lambda r: abs(r["strike"] - spot))
        c25 = min(calls, key=lambda r: abs(r["delta"] - 0.25))
        p25 = min(puts, key=lambda r: abs(r["delta"] + 0.25))
        spread = statistics.fmean((r["ask"] - r["bid"]) / r["mid"] for r in (atm_c, atm_p) if r["mid"] > 0) \
            if any(r["mid"] > 0 for r in (atm_c, atm_p)) else None
        out["expiries"].append({
            "expiry": expiry.isoformat(), "days": days,
            "atm_iv": (atm_c["iv"] + atm_p["iv"]) / 2, "atm_strike": atm_c["strike"],
            "call25_iv": c25["iv"], "put25_iv": p25["iv"], "skew25": p25["iv"] - c25["iv"],
            "atm_spread": spread, "oi": sum(r["oi"] for r in rows), "n": len(rows)})
    return out


def interp_iv(expiries: list[dict], target_days: int = 30, key: str = "atm_iv") -> Optional[float]:
    """Variance-time interpolation of `key` to `target_days`; the nearest
    expiry when only one side exists."""
    pts = [(e["days"], e[key]) for e in expiries if e.get(key) and e["days"] > 0]
    if not pts:
        return None
    pts.sort()
    lo = [p for p in pts if p[0] <= target_days]
    hi = [p for p in pts if p[0] >= target_days]
    if lo and hi and lo[-1][0] != hi[0][0]:
        (d1, v1), (d2, v2) = lo[-1], hi[0]
        w = (target_days - d1) / (d2 - d1)
        var = (1 - w) * v1 * v1 * d1 + w * v2 * v2 * d2
        return math.sqrt(var / target_days)
    d, v = min(pts, key=lambda p: abs(p[0] - target_days))
    return v


# ------------------------------------------------------------- realised vol

def realised_vol(closes: list[float], window: int) -> Optional[float]:
    if len(closes) < window + 1:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - window, len(closes))]
    return statistics.pstdev(rets) * math.sqrt(252)


def parse_nasdaq_closes(payload: dict) -> list[tuple[dt.date, float]]:
    from .data.nasdaq import parse_closes
    return parse_closes(payload)


def quote_date(chain: dict) -> Optional[dt.date]:
    """The trading day the chain's quotes belong to: the wrapper's
    timestamp, else the latest option trade time."""
    for src in (chain.get("timestamp"), ):
        if src:
            try:
                return dt.datetime.fromisoformat(str(src).replace("Z", "+00:00")).date()
            except ValueError:
                pass
    times = [o.get("last_trade_time") for o in (chain.get("data") or chain).get("options", []) if o.get("last_trade_time")]
    if times:
        try:
            return dt.datetime.fromisoformat(max(times)).date()
        except ValueError:
            return None
    return None


# ------------------------------------------------------------- storage

from .data.nasdaq import append_jsonl, read_jsonl  # noqa: E402 (shared by every collector)


# ------------------------------------------------------------- collectors

from zoneinfo import ZoneInfo  # noqa: E402

ET = ZoneInfo("America/New_York")
CLOSE_MINUTES = 16 * 60 + 5                        # 16:05 New York: the closing prints are in


def market_closed_for_today(now: Optional[dt.datetime] = None) -> bool:
    """True once today's regular session is over (or it is a weekend), so
    a snapshot taken now stores the day's close, not an intraday print."""
    t = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ET)
    return t.weekday() >= 5 or (t.hour * 60 + t.minute) >= CLOSE_MINUTES


class Collector:
    def __init__(self, state_dir: Path, client: Optional[httpx.AsyncClient] = None, symbol: str = "IBIT",
                 gate_vol_points: float = 5.0, now: Optional[callable] = None):
        self.state = Path(state_dir)
        self.symbol = symbol
        self.gate = gate_vol_points
        self._now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._c = client or httpx.AsyncClient(timeout=60, headers=UA, follow_redirects=True)
        self._owns = client is None

    async def close(self) -> None:
        if self._owns:
            await self._c.aclose()

    @property
    def options_file(self) -> Path:
        return self.state / "options" / f"{self.symbol.lower()}.jsonl"

    @property
    def closes_file(self) -> Path:
        return self.state / "options" / f"{self.symbol.lower()}_closes.jsonl"

    async def _get_json(self, url: str, params: Optional[dict] = None) -> dict:
        r = await self._c.get(url, params=params)
        if r.status_code >= 400:
            raise RuntimeError(f"{url.split('?')[0]} -> {r.status_code}")
        return r.json()

    def seed_from_payload(self, payload: dict) -> int:
        """Store closes from a Nasdaq historical payload (API or a saved
        file); returns how many new days were added."""
        have = {r["date"] for r in read_jsonl(self.closes_file)}
        n = 0
        for d, c in parse_nasdaq_closes(payload):
            if d.isoformat() not in have:
                append_jsonl(self.closes_file, {"date": d.isoformat(), "close": c})
                n += 1
        return n

    async def seed_closes(self) -> list[tuple[dt.date, float]]:
        """Closes on file, topped up from the Nasdaq data API when fewer
        than 60 days are stored. A failed seed is logged, not fatal: the
        daily spot is appended anyway, so realised vol appears on its own
        after 21 snapshots."""
        have = [(dt.date.fromisoformat(r["date"]), float(r["close"])) for r in read_jsonl(self.closes_file)]
        if len(have) >= 60:
            return sorted(have)
        end = dt.date.today()
        try:
            payload = await self._get_json(NASDAQ_URL.format(symbol=self.symbol, start=(end - dt.timedelta(days=400)).isoformat(),
                                                             end=end.isoformat()))
            self.seed_from_payload(payload)
        except Exception as exc:                      # noqa: BLE001
            logger.warning("close-history seed for %s failed (%s); realised vol will build from daily spots",
                           self.symbol, type(exc).__name__)
        return sorted((dt.date.fromisoformat(r["date"]), float(r["close"])) for r in read_jsonl(self.closes_file))

    async def options_snapshot(self, asof: Optional[dt.date] = None, chain: Optional[dict] = None) -> Optional[dict]:
        """One row for `asof` (today), skipped if that day is already stored."""
        now = self._now()
        asof = asof or now.astimezone(ET).date()
        if any(r.get("date") == asof.isoformat() for r in read_jsonl(self.options_file)):
            return None
        if asof == now.astimezone(ET).date() and not market_closed_for_today(now):
            logger.info("%s: session still open at %s ET; the snapshot waits for the close",
                        self.symbol, now.astimezone(ET).strftime("%H:%M"))
            return None
        chain = chain or await self._get_json(CBOE_URL.format(symbol=self.symbol))
        qd = quote_date(chain) if isinstance(chain, dict) else None
        if isinstance(chain, dict) and "data" in chain and "options" not in chain:
            chain = chain["data"]                     # Cboe wraps the quote
        # A weekend or holiday run sees the last session's quotes under
        # today's date; storing them would duplicate that session in the
        # surface history and put flat prints into the realised vol.
        if asof.weekday() >= 5 or (qd is not None and qd != asof):
            logger.info("%s: quotes are from %s, not %s; nothing stored", self.symbol, qd, asof)
            return None
        surf = surface(chain, asof, self.symbol)
        if surf["spot"] <= 0 or not surf["expiries"]:
            raise RuntimeError(f"{self.symbol} chain had no usable quotes (spot {surf['spot']}, "
                               f"{len(chain.get('options', []))} options): nothing stored")
        closes = await self.seed_closes()
        spot = surf["spot"]
        if spot > 0 and (not closes or closes[-1][0] < asof):
            closes.append((asof, spot))
            append_jsonl(self.closes_file, {"date": asof.isoformat(), "close": spot})
        series = [c for _, c in closes]
        iv30 = interp_iv(surf["expiries"], 30)
        rv20, rv30 = realised_vol(series, 20), realised_vol(series, 30)
        row = {"date": asof.isoformat(), "spot": spot,
               "iv30_atm": iv30, "iv30_cboe": (float(chain.get("iv30")) / 100.0) if chain.get("iv30") else None,
               "put25_iv30": interp_iv(surf["expiries"], 30, "put25_iv"),
               "call25_iv30": interp_iv(surf["expiries"], 30, "call25_iv"),
               "rv20": rv20, "rv30": rv30,
               "iv_minus_rv20": (iv30 - rv20) if (iv30 is not None and rv20 is not None) else None,
               "gate_open": (iv30 - rv20) >= self.gate / 100.0 if (iv30 is not None and rv20 is not None) else None,
               "expiries": surf["expiries"][:8], "n_options": sum(e["n"] for e in surf["expiries"])}
        append_jsonl(self.options_file, row)
        return row

    async def kalshi_hourly(self, tickers=KALSHI_TICKERS, hours: int = 48) -> dict[str, int]:
        """Append the last `hours` of hourly candles per ticker; returns new rows per ticker."""
        now = int(time.time())
        added = {}
        for t in tickers:
            path = self.state / "kalshi_hourly" / f"{t}.jsonl"
            have = {int(r["end_ts"]) for r in read_jsonl(path)}
            try:
                d = await self._get_json(KALSHI_CANDLES.format(ticker=t),
                                         {"period_interval": 60, "start_ts": now - hours * 3600, "end_ts": now})
            except Exception as exc:                  # noqa: BLE001 - one ticker down must not stop the rest
                logger.warning("kalshi hourly %s: %s", t, exc)
                added[t] = 0
                continue
            n = 0
            for c in d.get("candlesticks", []):
                p = c.get("price") or {}
                end_ts = int(c.get("end_period_ts") or 0)
                if end_ts in have or not p.get("close"):
                    continue
                append_jsonl(path, {"end_ts": end_ts, "open": float(p.get("open") or p["close"]),
                                    "high": float(p.get("high") or p["close"]), "low": float(p.get("low") or p["close"]),
                                    "close": float(p["close"]), "volume": float(c.get("volume") or 0)})
                have.add(end_ts)
                n += 1
            added[t] = n
        return added

    async def run_once(self) -> dict:
        out: dict = {}
        try:
            row = await self.options_snapshot()
            out["options"] = "stored" if row else "already stored today"
            if row:
                out["options_row"] = {k: row[k] for k in ("date", "spot", "iv30_atm", "rv20", "iv_minus_rv20", "gate_open")}
        except Exception as exc:                      # noqa: BLE001
            logger.warning("options snapshot failed: %s", exc)
            out["options"] = f"ERROR {type(exc).__name__}"
        out["kalshi_hourly"] = await self.kalshi_hourly()
        try:
            from .oos_track import update as oos_update
            s = await oos_update(self.state, client=self._c)
            out["divergence_oos"] = {k: s[k] for k in ("days_tracked", "pending", "verdict")} | {"qualifying": s["qualifying"]["n"]}
        except Exception as exc:                      # noqa: BLE001
            logger.warning("divergence OOS tracker failed: %s", exc)
            out["divergence_oos"] = f"ERROR {type(exc).__name__}"
        return out


def status(state_dir: Path, symbol: str = "IBIT") -> dict:
    """What the collectors hold, for the desk's research card."""
    sd = Path(state_dir)
    opts = read_jsonl(sd / "options" / f"{symbol.lower()}.jsonl")
    last = opts[-1] if opts else {}
    hourly = {}
    for p in sorted((sd / "kalshi_hourly").glob("*.jsonl")) if (sd / "kalshi_hourly").exists() else []:
        rows = read_jsonl(p)
        hourly[p.stem] = {"rows": len(rows), "last": dt.datetime.fromtimestamp(rows[-1]["end_ts"], dt.timezone.utc).isoformat()
                          if rows else None}
    gated = [r for r in opts if r.get("gate_open") is not None]
    out = {"options": {"symbol": symbol, "days": len(opts), "first": opts[0]["date"] if opts else None,
                       "last": last.get("date"), "spot": last.get("spot"), "iv30": last.get("iv30_atm"),
                       "rv20": last.get("rv20"), "iv_minus_rv20": last.get("iv_minus_rv20"),
                       "gate_open": last.get("gate_open"),
                       "gate_open_days": sum(1 for r in gated if r["gate_open"]), "gated_days": len(gated)},
           "kalshi_hourly": hourly}
    try:
        from .oos_track import read_rows, summary
        out["divergence_oos"] = summary(read_rows(sd))
    except Exception:                                 # noqa: BLE001
        out["divergence_oos"] = None
    return out


def report(state_dir: Path, symbol: str = "IBIT") -> str:
    rows = read_jsonl(Path(state_dir) / "options" / f"{symbol.lower()}.jsonl")
    if not rows:
        return "no option snapshots yet"
    o = [f"{symbol} option snapshots: {len(rows)} days, {rows[0]['date']} .. {rows[-1]['date']}",
         f"{'date':10s} {'spot':>7s} {'iv30':>6s} {'rv20':>6s} {'iv-rv':>6s} {'skew25':>7s} gate"]
    for r in rows[-30:]:
        iv, rv = r.get("iv30_atm"), r.get("rv20")
        skew = (r.get("put25_iv30") or 0) - (r.get("call25_iv30") or 0) if r.get("put25_iv30") and r.get("call25_iv30") else None
        o.append(f"{r['date']:10s} {r['spot']:7.2f} {iv*100 if iv else float('nan'):6.1f} {rv*100 if rv else float('nan'):6.1f} "
                 f"{(iv-rv)*100 if iv and rv else float('nan'):+6.1f} {skew*100 if skew is not None else float('nan'):+7.1f} "
                 f"{'open' if r.get('gate_open') else 'shut' if r.get('gate_open') is not None else '—'}")
    gated = [r for r in rows if r.get("gate_open") is not None]
    if gated:
        o.append(f"gate open on {sum(1 for r in gated if r['gate_open'])} of {len(gated)} days")
    return "\n".join(o)


async def collector_loop(state_dir: Path, hour_utc: int = 21, minute_utc: int = 15) -> None:
    """Once a day after the US close; the first run happens at startup if
    today's snapshot is missing."""
    c = Collector(state_dir)
    try:
        while True:
            try:
                res = await c.run_once()
                logger.info("collectors: %s", res)
            except Exception as exc:                  # noqa: BLE001
                logger.warning("collector run failed: %s", exc)
            now = dt.datetime.now(dt.timezone.utc)
            nxt = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
            if nxt <= now:
                nxt += dt.timedelta(days=1)
            await asyncio.sleep((nxt - now).total_seconds())
    finally:
        await c.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--symbol", default="IBIT")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--seed-closes", type=Path, help="a saved Nasdaq historical JSON to seed the close history from")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.report:
        print(report(a.state, a.symbol))
        return 0

    async def go():
        c = Collector(a.state, symbol=a.symbol)
        try:
            if a.seed_closes:
                print(f"seeded {c.seed_from_payload(json.loads(a.seed_closes.read_text()))} closes")
            return await c.run_once()
        finally:
            await c.close()
    print(json.dumps(asyncio.run(go()), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
