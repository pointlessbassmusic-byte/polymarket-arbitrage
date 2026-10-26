"""Day trading bot: the time-block scalper's rule engine, shared by the
backtest (cryptobot.daytrade_study) and the paper bot
(cryptobot.daytrade_bot), so both trade exactly the same logic.

Windows (UTC; the template's MST hours):
  bullish 13:30-16:00 Mon-Fri          momentum LONGS only
  bearish 22:00-03:00, starting Mon-Fri  fades: SHORTS only
  everything else: flat

Variants (registered as `daytrade-timeblock`):
  V0  the template: EMA 9/21 cross; long +1.5% / -0.75%, short +2% / -1%
  V1  ATR(14) exits: stop 1.5 ATR, target 3 ATR (1:2), both sides
  V2  V1 + filters: longs only above the 13:30-14:00 opening-range high;
      shorts only when RSI(14) was > 65 in the last 4 bars and volume is
      below its 20-bar mean (overextended on fading volume)

Instruments (amendment of 2026-10-20): every trade is also scored as
  spot     the coin itself, longs only (US retail cannot short spot), at
           Alpaca crypto taker 25 bp a side plus the half-spread
  bin15    a Kalshi 15-minute UP/DOWN binary in the signal direction for
           the 15 minutes from the entry bar's open, bought at 0.51 plus
           the 0.07 p(1-p) fee; ties settle UP; stops/targets ignored
  bin60    the same over the 60 minutes from the entry bar's open
Binary results are per dollar staked, in bp.

Fills: the signal is read on a closed bar; entry at the next bar's open,
only if that bar is inside a window and follows the signal bar directly;
stops and targets on later bars (a bar touching both is the stop; a gap
through a level fills at the open); at the first bar outside the windows
the position is closed at that bar's open.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Optional

Bar = tuple  # (ts_start, open, high, low, close, volume)

VARIANTS = ("V0", "V1", "V2")
TAKER_BP = 4.0
HALF_SPREAD_BP = {"BTC": 0.2, "ETH": 0.4, "SOL": 1.4, "DOGE": 2.9, "XRP": 1.6, "SHIB": 3.8}


def cost_bp(asset: str) -> float:
    """Round trip on Kalshi perps at the taker fee plus the measured half-spread, both sides."""
    return 2 * (TAKER_BP + HALF_SPREAD_BP.get(asset, 3.0))


SPOT_TAKER_BP = 25.0
BIN_PRICE = 0.51
INSTRUMENTS = ("perp", "spot", "bin15", "bin60")


def spot_cost_bp(asset: str) -> float:
    return 2 * (SPOT_TAKER_BP + HALF_SPREAD_BP.get(asset, 3.0))


def binary_fee(p: float) -> float:
    """Kalshi's fee per contract, 0.07 p (1-p) rounded up to the cent."""
    return math.ceil(round(0.07 * p * (1 - p) * 100, 9)) / 100


def binary_bp(win: bool, price: float = BIN_PRICE) -> float:
    """Return per dollar staked on one binary bought at `price` plus the fee."""
    c = price + binary_fee(price)
    return ((1.0 if win else 0.0) / c - 1) * 1e4


def binary_win(side: int, bars15: dict, entry_ts: float, minutes: int) -> Optional[bool]:
    """Did an UP (side +1) or DOWN (side -1) binary over `minutes` from the
    entry bar's open win? bars15 maps 15-minute bar start -> bar. None when
    the bars are not there (yet)."""
    first, last = bars15.get(int(entry_ts)), bars15.get(int(entry_ts + minutes * 60 - 900))
    if first is None or last is None:
        return None
    up = last[4] >= first[1]
    return up if side > 0 else not up


def score(trade: dict, bars15: dict) -> dict:
    """The trade's result in bp on every instrument (None = not tradeable
    that way, or not known yet)."""
    out = {"perp": trade["net_bp"],
           "spot": trade["gross_bp"] - spot_cost_bp(trade["asset"]) if trade["side"] > 0 else None}
    for k, m in (("bin15", 15), ("bin60", 60)):
        w = binary_win(trade["side"], bars15, trade["entry_ts"], m)
        out[k] = None if w is None else binary_bp(w)
    return out


def window(ts: float) -> Optional[str]:
    t = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    m = t.hour * 60 + t.minute
    wd = t.weekday()                       # Mon 0 .. Sun 6
    if wd < 5 and 13 * 60 + 30 <= m < 16 * 60:
        return "bull"
    if (wd < 5 and m >= 22 * 60) or (1 <= wd <= 5 and m < 3 * 60):
        return "bear"
    return None


def stock_window(ts: float) -> Optional[str]:
    """US session windows (New York time): 'am' 09:30-12:00, 'pm' 13:00-15:55,
    weekdays; both directions are traded inside them (daytrade-stocks)."""
    from zoneinfo import ZoneInfo
    t = dt.datetime.fromtimestamp(ts, ZoneInfo("America/New_York"))
    if t.weekday() >= 5:
        return None
    m = t.hour * 60 + t.minute
    if 9 * 60 + 30 <= m < 12 * 60:
        return "am"
    if 13 * 60 <= m < 15 * 60 + 55:
        return "pm"
    return None


def ema(xs: list[float], n: int) -> list[float]:
    k = 2 / (n + 1)
    out, e = [], None
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def atr(bars: list[Bar], n: int = 14) -> list[Optional[float]]:
    out, a, prev = [], None, None
    for i, b in enumerate(bars):
        tr = b[2] - b[3] if prev is None else max(b[2] - b[3], abs(b[2] - prev), abs(b[3] - prev))
        a = tr if a is None else a + (tr - a) / n           # Wilder
        out.append(a if i >= n else None)
        prev = b[4]
    return out


def rsi(closes: list[float], n: int = 14) -> list[Optional[float]]:
    out, up, dn = [None], None, None
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        u, w = max(d, 0.0), max(-d, 0.0)
        up = u if up is None else up + (u - up) / n
        dn = w if dn is None else dn + (w - dn) / n
        out.append(None if i < n else (100.0 if dn == 0 else 100 - 100 / (1 + up / dn)))
    return out


@dataclass
class Position:
    side: int            # +1 long, -1 short
    entry: float
    stop: float
    target: float
    entry_ts: float
    window: str


def exits_for(variant: str, side: int, entry: float, atr_v: Optional[float]) -> Optional[tuple[float, float]]:
    if variant == "V0":
        tp, sl = (0.015, 0.0075) if side > 0 else (0.02, 0.01)
        return (entry * (1 - side * sl), entry * (1 + side * tp))
    if atr_v is None or atr_v <= 0:
        return None
    return (entry - side * 1.5 * atr_v, entry + side * 3.0 * atr_v)


class Engine:
    """Bar-by-bar state machine. Feed closed bars in order with `on_bar`;
    it returns any trade that closed on that bar."""

    def __init__(self, variant: str = "V0", asset: str = "BTC", window_fn=None, cost: Optional[float] = None):
        """window_fn: ts -> window label (default: the crypto windows);
        stock_window switches V2 to the opening-range filter on both sides.
        cost: round trip in bp (default: Kalshi perps for `asset`)."""
        assert variant in VARIANTS
        self.variant, self.asset = variant, asset
        self._win = window_fn or window
        self.stock = window_fn is stock_window
        self._cost = cost_bp(asset) if cost is None else cost
        self.bars: list[Bar] = []
        self.pos: Optional[Position] = None
        self.pending: Optional[tuple[int, str, Optional[float]]] = None   # side, window, atr at the signal bar

    def _signal(self) -> Optional[tuple[int, str, Optional[float]]]:
        b = self.bars
        i = len(b) - 1
        if i < 30:
            return None
        w = self._win(b[i][0])
        if w is None:
            return None
        closes = [x[4] for x in b[-200:]]
        f, s = ema(closes, 9), ema(closes, 21)
        up = f[-2] <= s[-2] and f[-1] > s[-1]
        down = f[-2] >= s[-2] and f[-1] < s[-1]
        a = atr(b[-200:])[-1]
        if self.stock:
            side = 1 if up else (-1 if down else 0)
            if not side:
                return None
            if self.variant == "V2":
                from zoneinfo import ZoneInfo
                et = ZoneInfo("America/New_York")
                now = dt.datetime.fromtimestamp(b[i][0], et)
                day = now.date()
                orng = [x for x in b[-60:] if dt.datetime.fromtimestamp(x[0], et).date() == day
                        and dt.time(9, 30) <= dt.datetime.fromtimestamp(x[0], et).time() < dt.time(10, 0)]
                if not orng or now.time() < dt.time(10, 0):
                    return None
                if side > 0 and b[i][4] <= max(x[2] for x in orng):
                    return None
                if side < 0 and b[i][4] >= min(x[3] for x in orng):
                    return None
            return (side, w, a)
        if w == "bull" and up:
            if self.variant == "V2":
                day = dt.datetime.fromtimestamp(b[i][0], dt.timezone.utc).date()
                orng = [x for x in b[-40:] if dt.datetime.fromtimestamp(x[0], dt.timezone.utc).date() == day
                        and window(x[0]) == "bull" and x[0] < self._or_end(x[0])]
                if not orng or b[i][0] < self._or_end(b[i][0]) or b[i][4] <= max(x[2] for x in orng):
                    return None
            return (1, w, a)
        if w == "bear" and down:
            if self.variant == "V2":
                r = rsi(closes)
                vols = [x[5] for x in b[-21:-1]]
                if max(x for x in r[-4:] if x is not None) <= 65 or not vols or b[i][5] >= sum(vols) / len(vols):
                    return None
            return (-1, w, a)
        return None

    @staticmethod
    def _or_end(ts: float) -> float:
        d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
        return d.timestamp()

    def on_bar(self, bar: Bar) -> Optional[dict]:
        """Process one CLOSED bar. Order of events within the bar: a pending
        entry fills at its open; then (if flat-out-of-hours) close at open;
        then stop/target on the bar's range; then a new signal on its close."""
        self.bars.append(bar)
        if len(self.bars) > 400:
            self.bars = self.bars[-300:]
        ts, o, h, l, c, v = bar
        closed = None
        if self.pending and self.pos is None:
            side, w, a = self.pending
            self.pending = None
            prev = self.bars[-2][0] if len(self.bars) > 1 else ts
            # enter only inside a window and on the bar right after the signal (never across a session gap)
            ex = exits_for(self.variant, side, o, a) if self._win(ts) is not None and ts - prev <= 7200 else None
            if ex is not None:
                self.pos = Position(side, o, ex[0], ex[1], ts, w)
        if self.pos is not None:
            p = self.pos
            if self._win(ts) is None and ts > p.entry_ts:
                closed = self._close(o, ts, "flat_out_of_hours")
            else:
                hit_stop = (l <= p.stop) if p.side > 0 else (h >= p.stop)
                hit_tgt = (h >= p.target) if p.side > 0 else (l <= p.target)
                if hit_stop:
                    px = min(o, p.stop) if p.side > 0 else max(o, p.stop)        # a gap through the stop fills at the open
                    closed = self._close(px, ts, "stop")
                elif hit_tgt:
                    px = max(o, p.target) if p.side > 0 else min(o, p.target)
                    closed = self._close(px, ts, "target")
        if self.pos is None and closed is None:
            sig = self._signal()
            if sig is not None:
                self.pending = sig
        return closed

    def _close(self, px: float, ts: float, reason: str) -> dict:
        p = self.pos
        self.pos = None
        gross = p.side * (px / p.entry - 1) * 1e4
        return {"asset": self.asset, "variant": self.variant, "side": p.side, "window": p.window,
                "entry_ts": p.entry_ts, "exit_ts": ts, "entry": p.entry, "exit": px, "reason": reason,
                "gross_bp": gross, "net_bp": gross - self._cost}


def resample(bars: list[Bar], seconds: int) -> list[Bar]:
    out: dict[int, list] = {}
    for b in bars:
        k = int(b[0] // seconds * seconds)
        if k not in out:
            out[k] = [k, b[1], b[2], b[3], b[4], b[5]]
        else:
            r = out[k]
            r[2], r[3], r[4], r[5] = max(r[2], b[2]), min(r[3], b[3]), b[4], r[5] + b[5]
    return [tuple(out[k]) for k in sorted(out)]


def backtest(bars: list[Bar], variant: str, asset: str, window_fn=None, cost: Optional[float] = None) -> list[dict]:
    e = Engine(variant, asset, window_fn, cost)
    trades = []
    for b in bars:
        t = e.on_bar(b)
        if t:
            trades.append(t)
    return trades
