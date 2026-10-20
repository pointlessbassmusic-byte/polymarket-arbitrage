"""
Point-in-time features and isolated targets for the learning program (T-577).
=============================================================================

Timing contract (the one rule everything else follows):
  * a bar stamped t (its OPEN) with length L is known at t + L, its close; a decision is taken at a bar's close;
  * every feature at decision time T uses only bars whose close is <= T, and slow data only once published
    (FINRA short interest by its ``available_at``; calendars by their scheduled dates, which are known in advance);
  * the target is the forward log return from the NEXT bar's open over h bars, log(open[i+1+h] / open[i+1]):
    nothing from bar i+1 onward is ever an input, and the target is never used to build a feature;
  * normalisations that need statistics are trailing (rolling windows that end at bar i) or fitted on the training
    fold only (in train.py), never on the full sample.

Feature families, kept apart so the program can measure what carries information besides the asset's own price:
  F0  price-free: volume and dollar volume (levels relative to their own trailing averages, time-of-day volume
      profile), calendar (time of day, day of week, minutes to the session close, days to month end, FOMC / CPI
      proximity), short interest (days to cover, change) for stocks and ETFs
  F1  other assets: trailing returns of market leaders (SPY, QQQ, BTC, ^VIX, DX, ^TNX) up to bar i — never the asset's own
  F2  own past price: lagged returns, realised volatility, range, close location in the bar, distance from the
      session VWAP, return since the session open
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from mandel.ml.fetch import ASSET_CLASS, STORE, _safe

INTERVAL_MIN = {"5m": 5, "15m": 15, "30m": 30, "45m": 45, "60m": 60}
LEADERS = ["SPY", "QQQ", "BTC-USD", "^VIX", "DX-Y.NYB", "^TNX"]
F0 = ["lv_rel12", "lv_rel_tod", "dv_log", "tod_sin", "tod_cos", "dow", "min_to_close", "days_to_me", "fomc_days",
      "cpi_days", "si_dtc", "si_chg"]
F2 = ["r1", "r2", "r3", "r6", "r12", "rv12", "rv48", "rng", "clv", "vwap_dist", "r_sess"]


def load_bars(interval: str, sym: str) -> Optional[pd.DataFrame]:
    p = STORE / interval / f"{_safe(sym)}.csv.gz"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if df.empty:
        return None
    df = df.dropna(subset=["o", "h", "l", "c"]).sort_values("t").drop_duplicates("t")
    df["t"] = pd.to_datetime(df["t"], unit="s", utc=True)
    return df.set_index("t")


def resample(df5: pd.DataFrame, minutes: int, crypto: bool) -> pd.DataFrame:
    """Aggregate 5-minute bars into ``minutes`` bars. Equities: blocks counted from each session's first bar (so a
    45-minute bar never straddles the close); crypto: blocks on the UTC clock."""
    if minutes == 5:
        return df5.copy()
    k = minutes // 5
    if crypto:
        key = df5.index.floor(f"{minutes}min")
    else:
        day = df5.index.tz_convert("America/New_York").date
        idx = df5.groupby(day).cumcount() // k
        key = pd.Series(list(zip(day, idx)), index=df5.index)
    g = df5.groupby(key.values if not crypto else key)
    out = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(), "v": g["v"].sum(),
                        "t": g.apply(lambda x: x.index[0]), "n": g["o"].size()})
    out = out[out["n"] == k] if crypto else out          # crypto: drop incomplete blocks (gaps)
    return out.set_index("t").drop(columns="n").sort_index()


def _calendar_days(index: pd.DatetimeIndex, dates: list) -> np.ndarray:
    """Days to the next scheduled event (known in advance), capped at 30."""
    ev = np.array(sorted(pd.to_datetime(dates, utc=True).values.astype("datetime64[ns]")))
    t = index.values.astype("datetime64[ns]")
    j = np.searchsorted(ev, t)
    nxt = np.where(j < len(ev), ev[np.minimum(j, len(ev) - 1)], np.datetime64("NaT"))
    d = (nxt - t) / np.timedelta64(1, "D")
    return np.clip(np.nan_to_num(d, nan=30.0), 0, 30)


def calendars() -> dict:
    from mandel.archive import Archive
    a = Archive()
    out = {"fomc": [], "cpi": []}
    try:
        out["fomc"] = [r["value"]["decision_day"] + "T18:00:00Z" for r in a.load("fomc-meetings")]
        out["cpi"] = [r["value"]["day"] + "T12:30:00Z" for r in a.load("macro-release-cpi")]
    except Exception:
        pass
    return out


def short_interest() -> dict:
    """{symbol: DataFrame(available_at, dtc, chg)} from the FINRA bundles, keyed by publication time."""
    from mandel.archive import Archive
    a = Archive()
    rows = []
    for e in a.entries():
        if e.name.startswith("finra-short-interest-2025") or e.name.startswith("finra-short-interest-2026"):
            for r in a.load(e.name):
                v = r.get("value") or {}
                rows.append((v.get("symbolCode"), r.get("available_at"), v.get("daysToCoverQuantity"), v.get("changePercent")))
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=["sym", "avail", "dtc", "chg"]).dropna(subset=["sym", "avail"])
    df["avail"] = pd.to_datetime(df["avail"], utc=True)
    return {s: g.sort_values("avail") for s, g in df.groupby("sym")}


def build(sym: str, interval: str, horizons=(1,), leaders: Optional[dict] = None, cal: Optional[dict] = None,
          si: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """One row per decision bar: features (F0, F1, F2), targets y_h (next-open to open h bars later, log), and the
    trailing volatility used to normalise them."""
    crypto = ASSET_CLASS.get(sym) == "crypto"
    base = load_bars("5m", sym)
    if base is None or len(base) < 500:
        return None
    df = resample(base, INTERVAL_MIN[interval], crypto)
    o, h, l, c, v = (df[k].astype(float) for k in ("o", "h", "l", "c", "v"))
    lc = np.log(c)
    r = lc.diff()
    f = pd.DataFrame(index=df.index)
    bar_close = df.index + pd.Timedelta(minutes=INTERVAL_MIN[interval])
    # --- F2 own past price (all through bar i)
    for k in (1, 2, 3, 6, 12):
        f[f"r{k}"] = lc - lc.shift(k)
    f["rv12"] = r.rolling(12).std()
    f["rv48"] = r.rolling(48).std()
    f["rng"] = np.log(h / l)
    f["clv"] = ((c - l) / (h - l)).where(h > l, 0.5)
    ny = df.index.tz_convert("America/New_York")
    sess = pd.Series(ny.date, index=df.index) if not crypto else pd.Series(df.index.floor("1D").date, index=df.index)
    pv = (c * v).groupby(sess.values).cumsum()
    vv = v.groupby(sess.values).cumsum()
    vwap = pv / vv.replace(0, np.nan)
    f["vwap_dist"] = np.log(c / vwap)
    first_open = o.groupby(sess.values).transform("first")
    f["r_sess"] = np.log(c / first_open)
    # --- F0 price-free
    lv = np.log1p(v)
    f["lv_rel12"] = lv - lv.rolling(12).mean()
    tod = (ny.hour * 60 + ny.minute) if not crypto else (df.index.hour * 60 + df.index.minute)
    tod_s = pd.Series(np.asarray(tod), index=df.index)
    prof = lv.groupby(tod_s.values).transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    f["lv_rel_tod"] = lv - prof
    f["dv_log"] = np.log1p(c * v) - np.log1p(c * v).rolling(48).mean()
    f["tod_sin"] = np.sin(2 * np.pi * tod_s / 1440)
    f["tod_cos"] = np.cos(2 * np.pi * tod_s / 1440)
    f["dow"] = df.index.dayofweek
    if crypto:
        f["min_to_close"] = 0.0
    else:
        close_ny = pd.Series(ny.normalize() + pd.Timedelta(hours=16), index=df.index)
        f["min_to_close"] = (close_ny - pd.Series(bar_close.tz_convert("America/New_York"), index=df.index)).dt.total_seconds() / 60
    me = (df.index + pd.offsets.MonthEnd(0)).normalize()
    f["days_to_me"] = (me - df.index.normalize()).days
    cal = cal or {}
    f["fomc_days"] = _calendar_days(bar_close, cal.get("fomc", [])) if cal.get("fomc") else 30.0
    f["cpi_days"] = _calendar_days(bar_close, cal.get("cpi", [])) if cal.get("cpi") else 30.0
    f["si_dtc"], f["si_chg"] = np.nan, np.nan
    if si and sym in si:
        s = si[sym]
        pos = np.searchsorted(s["avail"].values.astype("datetime64[ns]"), bar_close.values.astype("datetime64[ns]"), side="right") - 1
        ok = pos >= 0
        f.loc[ok, "si_dtc"] = s["dtc"].values[pos[ok]]
        f.loc[ok, "si_chg"] = s["chg"].values[pos[ok]]
    # --- F1 other assets (their returns through bar i, aligned by bar close time; never the asset itself)
    for name, lr in (leaders or {}).items():
        if name == sym:
            continue
        al = lr.reindex(df.index, method="ffill", tolerance=pd.Timedelta(minutes=INTERVAL_MIN[interval]))
        f[f"x_{_safe(name)}"] = al
    # --- targets: next bar's open to the open h bars later
    lo = np.log(o)
    for hz in horizons:
        f[f"y{hz}"] = lo.shift(-(1 + hz)) - lo.shift(-1)
        if not crypto:                                    # intraday horizons never cross the session close
            same = sess.shift(-(1 + hz)) == sess.shift(-1)
            f.loc[~same.fillna(False), f"y{hz}"] = np.nan
    f["vol_norm"] = f["rv48"].replace(0, np.nan)
    f["sym"] = sym
    f["cls"] = ASSET_CLASS.get(sym, "other")
    f["decision_at"] = bar_close
    return f


def leader_returns(interval: str) -> dict:
    """Trailing one-bar log returns of the leaders, indexed by bar OPEN time (each value known at that bar's close)."""
    out = {}
    for s in LEADERS:
        b = load_bars("5m", s)
        if b is None:
            continue
        rb = resample(b, INTERVAL_MIN[interval], ASSET_CLASS.get(s) == "crypto")
        out[s] = np.log(rb["c"]).diff()
    return out
