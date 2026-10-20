"""
Options-implied daily variables for the swing models (T-580, feature family F3).
================================================================================

Every value enters at its archived ``available_at`` (Cboe index closes 21:30 UTC, Deribit DVOL candles a day after
their stamp, funding at its print), and the swing builder takes it only once known by the asset's own close.

Market-wide: log VIX; VIX/VIX3M and VIX9D/VIX term slopes; log VVIX; SKEW; COR1M implied correlation; DSPX
dispersion; the front VX future over VIX; the S&P variance premium log(VIX daily / SPY 20-day realised); BTC
perpetual funding averaged over the last day. Own: the asset's mapped implied-vol index (``OWN_IV``) as log level,
5-day change and implied over the asset's own 20-day realised volatility.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MARKET = ["iv_vix", "iv_term", "iv_term9", "iv_vvix", "iv_skew", "iv_cor", "iv_dspx", "vx_basis", "vrp_spx", "fund_btc"]
OWN = ["own_iv", "own_iv_chg5", "own_iv_rv"]
F3 = MARKET + OWN

_GOLD = ["GLD", "GC=F", "SLV", "SI=F", "GDX"]
_OIL = ["USO", "CL=F", "XLE", "XOM", "CVX"]
_RATES = ["TLT", "IEF", "SHY", "AGG", "LQD", "TIP", "ZN=F", "ZB=F", "ZF=F"]
_EM = ["EEM", "FXI", "EWZ"]
_NDX = ["QQQ", "NQ=F", "TQQQ", "SQQQ", "XLK", "SMH", "ARKK", "MSFT", "NVDA", "META", "TSLA", "AVGO", "AMD", "NFLX", "PLTR",
        "SMCI", "INTC", "MU", "ORCL", "CRM", "ADBE"]
_BTC = ["BTC-USD", "IBIT", "BTC=F", "COIN", "MSTR"]
OWN_IV = {**{s: "GVZ" for s in _GOLD}, **{s: "OVX" for s in _OIL}, **{s: "VXTLT" for s in _RATES},
          **{s: "VXEEM" for s in _EM}, **{s: "VXN" for s in _NDX}, **{s: "dvol:BTC" for s in _BTC},
          "IWM": "RVX", "RTY=F": "RVX", "DIA": "VXD", "YM=F": "VXD", "AAPL": "VXAPL", "GOOGL": "VXGOG", "AMZN": "VXAZN",
          "ETH-USD": "dvol:ETH", "ETHA": "dvol:ETH"}


def own_iv_key(sym: str, cls: str) -> str:
    if sym in OWN_IV:
        return OWN_IV[sym]
    return "dvol:BTC" if cls == "crypto" else "VIX"


def _frame(rows) -> pd.DataFrame:
    """(known_at, day, close) sorted by known time."""
    out = []
    for r in rows:
        v = r.get("value") or {}
        c = v.get("close")
        if c is None or not (c > 0):
            continue
        day = v.get("day") or r["observed_at"][:10]
        out.append((pd.Timestamp(r["available_at"]), day, float(c)))
    df = pd.DataFrame(out, columns=["known_at", "day", "close"])
    df["known_at"] = pd.to_datetime(df["known_at"], utc=True)
    return df.sort_values("known_at").drop_duplicates("day", keep="last").reset_index(drop=True)


def _pair(a: pd.DataFrame, b: pd.DataFrame, fn) -> pd.DataFrame:
    """A same-day combination of two series, known once both are."""
    m = a.merge(b, on="day", suffixes=("_a", "_b"))
    return pd.DataFrame({"known_at": m[["known_at_a", "known_at_b"]].max(axis=1),
                         "value": fn(m["close_a"], m["close_b"])}).sort_values("known_at").reset_index(drop=True)


def _one(a: pd.DataFrame, fn) -> pd.DataFrame:
    return pd.DataFrame({"known_at": a["known_at"], "value": fn(a["close"])})


def load(spy_daily: pd.DataFrame | None = None, spy_known: pd.DatetimeIndex | None = None) -> dict:
    """{"market": {feature: DataFrame(known_at, value)}, "own": {key: DataFrame(known_at, day, close)}}."""
    from mandel.archive import Archive
    a = Archive()
    names = {e.name for e in a.entries()}
    idx = {}
    for k in ("VIX", "VIX3M", "VIX9D", "VVIX", "SKEW", "COR1M", "DSPX", "GVZ", "OVX", "VXTLT", "VXEEM", "VXN", "RVX", "VXD",
              "VXAPL", "VXGOG", "VXAZN"):
        n = f"cboe-{k}-history"
        if n in names:
            idx[k] = _frame(a.load(n))
    for k in ("BTC", "ETH"):
        n = f"deribit-dvol-{k}-history"
        if n in names:
            d = _frame(a.load(n))
            d["day"] = d["known_at"].dt.strftime("%Y-%m-%d")
            idx[f"dvol:{k}"] = d
    mk = {}
    if "VIX" in idx:
        vix = idx["VIX"]
        mk["iv_vix"] = _one(vix, np.log)
        if "VIX3M" in idx:
            mk["iv_term"] = _pair(vix, idx["VIX3M"], lambda x, y: np.log(x / y))
        if "VIX9D" in idx:
            mk["iv_term9"] = _pair(idx["VIX9D"], vix, lambda x, y: np.log(x / y))
        if "VVIX" in idx:
            mk["iv_vvix"] = _one(idx["VVIX"], np.log)
        if "SKEW" in idx:
            mk["iv_skew"] = _one(idx["SKEW"], lambda x: x / 100)
        if "COR1M" in idx:
            mk["iv_cor"] = _one(idx["COR1M"], lambda x: x / 100)
        if "DSPX" in idx:
            mk["iv_dspx"] = _one(idx["DSPX"], lambda x: x / 100)
        if "cboe-vx-futures" in names:
            mk["vx_basis"] = _vx_basis(a.load("cboe-vx-futures"), vix)
        if spy_daily is not None and spy_known is not None:
            r = np.log(spy_daily["c"].astype(float)).diff()
            rv = pd.DataFrame({"known_at": spy_known, "day": spy_daily.index.tz_convert("America/New_York").strftime("%Y-%m-%d"),
                               "close": r.rolling(20).std().values}).dropna()
            mk["vrp_spx"] = _pair(vix, rv, lambda v, s: np.log(v / 100 / math.sqrt(252)) - np.log(s))
    if "deribit-funding-BTC-PERPETUAL" in names:
        rows = [(pd.Timestamp(r["available_at"]), (r.get("value") or {}).get("interest_8h"))
                for r in a.load("deribit-funding-BTC-PERPETUAL")]
        f = pd.DataFrame(rows, columns=["known_at", "value"]).dropna()
        f["known_at"] = pd.to_datetime(f["known_at"], utc=True)
        f = f.sort_values("known_at")
        f["value"] = f["value"].rolling(24, min_periods=6).mean()            # the last day of hourly prints
        mk["fund_btc"] = f.dropna().reset_index(drop=True)
    for k in list(mk):
        mk[k] = mk[k].replace([np.inf, -np.inf], np.nan).dropna().sort_values("known_at").reset_index(drop=True)
    return {"market": mk, "own": idx}


def _vx_basis(rows, vix: pd.DataFrame) -> pd.DataFrame:
    """log(front VX future / VIX): the front is the nearest expiry strictly after the day."""
    out = {}
    for r in rows:
        v = r.get("value") or {}
        px = v.get("close") or v.get("settle")
        if not px or px <= 0 or v.get("expiry", "") <= v.get("day", ""):
            continue
        d = v["day"]
        if d not in out or v["expiry"] < out[d][0]:
            out[d] = (v["expiry"], float(px), pd.Timestamp(r["available_at"]))
    fut = pd.DataFrame([(d, px, ka) for d, (_, px, ka) in out.items()], columns=["day", "close", "known_at"])
    fut["known_at"] = pd.to_datetime(fut["known_at"], utc=True)
    return _pair(fut, vix, lambda f, x: np.log(f / x))


def own_features(own: dict, key: str, known: pd.Series, rv20: pd.Series, crypto: bool) -> pd.DataFrame:
    """Own implied-vol features at each decision (``known``: the asset's close times; ``rv20``: its 20-day realised)."""
    out = pd.DataFrame(index=known.index, columns=OWN, dtype=float)
    s = own.get(key)
    if s is None or s.empty:
        return out
    s = s.copy()
    s["lv"] = np.log(s["close"])
    s["chg5"] = s["lv"] - s["lv"].shift(5)
    m = pd.merge_asof(pd.DataFrame({"known_at": known.reset_index(drop=True)}), s[["known_at", "lv", "chg5"]], on="known_at",
                      direction="backward")
    out["own_iv"] = m["lv"].values
    out["own_iv_chg5"] = m["chg5"].values
    per_day = math.sqrt(365 if (crypto or key.startswith("dvol")) else 252)
    out["own_iv_rv"] = (m["lv"].values - math.log(100 * per_day)) - np.log(rv20.values)
    return out
