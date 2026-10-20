"""
Swing horizons for the learning program (T-578): daily bars, holds of 1, 5 and 20 trading days.
==============================================================================================

    python -m mandel.ml.swing [--classes ...] [--horizons 1,5,20] [--lockbox] [--stage dev]

Timing contract (the daily version of mandel.ml.features):
  * a daily bar is known at its class's close: US stocks and ETFs 16:00 ET, CME futures 17:00 ET and indices 16:15 ET on
    the bar's New York date; FX and crypto at stamp + 24 h (their bars are stamped at the open of a 24-hour day);
  * features of an asset use its own bars up to i and other assets' bars only once known by the asset's own close;
  * the target is log(open[i+1+h] / open[i+1]): entry at the next open, never an input, and rows whose target is
    realised in the lockbox (2026-10-01 on) are dropped unless --lockbox;
  * walk-forward: monthly test blocks through 2026, each model fitted on every earlier row whose target window ended
    before the block began (purged), so no 2026 prediction comes from a model that saw its outcome.
Writes mandel/state/ml/swing_<stage>.json (statistics only).
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from mandel.ml import features as FE
from mandel.ml import implied as IM
from mandel.ml import train as TR
from mandel.ml.fetch import ASSET_CLASS, COINBASE, YAHOO, _safe

DEV_START = pd.Timestamp("2026-01-01", tz="UTC")
LOCKBOX = TR.LOCKBOX
LEADERS = ["SPY", "QQQ", "^VIX", "DX-Y.NYB", "^TNX", "BTC-USD", "TLT", "GLD"]
F0 = ["lv_rel20", "dv_rel20", "dow", "dom", "days_to_me", "days_to_opex", "fomc_days", "cpi_days", "si_dtc", "si_chg"]
F2 = ["r1", "r5", "r20", "r60", "r120", "rv20", "rv60", "rng", "ibs", "gap", "ma50_dist", "ma200_dist"]
XS_MIN_SYMBOLS = 10
PER_YEAR = {"crypto": 365, "other": 252}


def known_at(index: pd.DatetimeIndex, cls: str) -> pd.DatetimeIndex:
    """When a daily bar stamped ``index`` is complete (see the timing contract)."""
    if cls in ("crypto", "fx"):
        return index + pd.Timedelta(hours=24)
    ny = index.tz_convert("America/New_York").normalize()
    hours = {"future": 17.0, "index": 16.25}.get(cls, 16.0)
    return (ny + pd.Timedelta(hours=hours)).tz_convert("UTC")


def _third_friday_days(index: pd.DatetimeIndex) -> np.ndarray:
    """Calendar days to the next monthly options expiry (third Friday), known in advance."""
    out = []
    for t in index.tz_convert("America/New_York"):
        for k in (0, 1):
            m = (t.replace(day=1) + pd.DateOffset(months=k))
            first = m.replace(day=1)
            fri = first + pd.Timedelta(days=(4 - first.dayofweek) % 7 + 14)
            if fri.normalize() >= t.normalize():
                out.append((fri.normalize() - t.normalize()).days)
                break
    return np.array(out, dtype=float)


def load_daily(sym: str) -> pd.DataFrame | None:
    """Daily bars, without any bar that was not complete when its file was written (the day still trading at fetch)."""
    df = FE.load_bars("1d", sym)
    if df is None:
        return None
    written = pd.Timestamp((FE.STORE / "1d" / f"{_safe(sym)}.csv.gz").stat().st_mtime, unit="s", tz="UTC")
    df = df[(df["o"] > 0) & (df["c"] > 0)]
    ka = known_at(df.index, ASSET_CLASS.get(sym, "other"))
    if (ka <= df.index).any():                            # a stamp convention this module does not know: stop, never guess
        raise ValueError(f"{sym}: daily bar stamped at or after its assumed close, e.g. {df.index[ka <= df.index][0]}")
    return df[ka <= written]


def build(sym: str, horizons, leaders: dict, cal: dict, si: dict, implied: dict | None = None) -> pd.DataFrame | None:
    cls = ASSET_CLASS.get(sym, "other")
    df = load_daily(sym)
    if df is None or len(df) < 300:
        return None
    o, h, l, c, v = (df[k].astype(float) for k in ("o", "h", "l", "c", "v"))
    lc, r = np.log(c), np.log(c).diff()
    f = pd.DataFrame(index=df.index)
    ka = known_at(df.index, cls)
    # F2 own past price
    for k in (1, 5, 20, 60, 120):
        f[f"r{k}"] = lc - lc.shift(k)
    f["rv20"], f["rv60"] = r.rolling(20).std(), r.rolling(60).std()
    f["rng"] = np.log(h / l)
    f["ibs"] = ((c - l) / (h - l)).where(h > l, 0.5)
    f["gap"] = np.log(o / c.shift(1))
    f["ma50_dist"] = lc - lc.rolling(50).mean()
    f["ma200_dist"] = lc - lc.rolling(200).mean()
    # F0 price-free
    lv = np.log1p(v)
    f["lv_rel20"] = lv - lv.rolling(20).mean()
    dv = np.log1p(c * v)
    f["dv_rel20"] = dv - dv.rolling(20).mean()
    ny = df.index.tz_convert("America/New_York")
    f["dow"], f["dom"] = ny.dayofweek, ny.day
    f["days_to_me"] = ((ny + pd.offsets.MonthEnd(0)).normalize() - ny.normalize()).days
    f["days_to_opex"] = _third_friday_days(df.index)
    f["fomc_days"] = FE._calendar_days(ka, cal["fomc"]) if cal.get("fomc") else 30.0
    f["cpi_days"] = FE._calendar_days(ka, cal["cpi"]) if cal.get("cpi") else 30.0
    f["si_dtc"], f["si_chg"] = np.nan, np.nan
    if si and sym in si:
        s = si[sym]
        pos = np.searchsorted(s["avail"].values.astype("datetime64[ns]"), ka.values.astype("datetime64[ns]"), side="right") - 1
        ok = pos >= 0
        f.loc[ok, "si_dtc"] = s["dtc"].values[pos[ok]]
        f.loc[ok, "si_chg"] = s["chg"].values[pos[ok]]
    # F1 other assets: each leader's latest bar known by this asset's close (merge on known time, backward)
    f["known_at"] = ka
    for name, lf in leaders.items():
        if name == sym:
            continue
        m = pd.merge_asof(f[["known_at"]].reset_index(), lf, on="known_at", direction="backward")
        for col in ("r1", "r5", "r20"):
            f[f"x_{_safe(name)}_{col}"] = m[col].values
    # F3 options-implied (T-580): market-wide series and the asset's own implied vol, each once known by this close
    if implied:
        for name, fr in implied["market"].items():
            m = pd.merge_asof(f[["known_at"]].reset_index(), fr[["known_at", "value"]], on="known_at", direction="backward")
            f[name] = m["value"].values
        own = IM.own_features(implied["own"], IM.own_iv_key(sym, cls), f["known_at"], f["rv20"], cls == "crypto")
        for col in IM.OWN:
            f[col] = own[col].values
    # targets: next open to the open h bars later; realised at the stamp of bar i+1+h
    lo = np.log(o)
    stamps = pd.Series(df.index, index=df.index)
    for hz in horizons:
        f[f"y{hz}"] = lo.shift(-(1 + hz)) - lo.shift(-1)
        f[f"yend{hz}"] = stamps.shift(-(1 + hz))
        f[f"vn{hz}"] = (f["rv20"] * math.sqrt(hz)).replace(0, np.nan)
    f["row"] = np.arange(len(f))
    f["sym"], f["cls"], f["decision_at"] = sym, cls, ka
    return f


def leader_frames() -> dict:
    out = {}
    for s in LEADERS:
        b = load_daily(s)
        if b is None:
            continue
        lc = np.log(b["c"].astype(float))
        fr = pd.DataFrame({"known_at": known_at(b.index, ASSET_CLASS.get(s, "other")),
                           "r1": lc.diff().values, "r5": (lc - lc.shift(5)).values, "r20": (lc - lc.shift(20)).values})
        out[s] = fr.sort_values("known_at")
    return out


FAMILIES = {"F0": "f0", "F0F1": "f0f1", "F2": "f2", "ALL": "all", "F0F1F3": "f0f1f3", "ALLF3": "allf3"}
T578_FAMILIES = ("F0", "F0F1", "F2", "ALL")


def family_cols(cols, fam: str) -> list:
    f1 = [c for c in cols if c.startswith("x_")]
    return {"f0": F0, "f0f1": F0 + f1, "f2": F2, "all": F0 + f1 + F2, "f0f1f3": F0 + f1 + IM.F3,
            "allf3": F0 + f1 + F2 + IM.F3}[fam]


def walk_forward(df: pd.DataFrame, cols: list, kind: str, hz: int, lockbox: bool) -> pd.DataFrame:
    y, yend, vn = f"y{hz}", f"yend{hz}", f"vn{hz}"
    df = df.dropna(subset=[y, vn]).copy()
    df["yn"] = (df[y] / df[vn]).clip(-10, 10)
    X = df[cols].astype(float)
    t = df["decision_at"]
    last = t.max()
    out = []
    for m0 in pd.date_range(DEV_START, last, freq="MS"):
        m1 = m0 + pd.offsets.MonthBegin(1)
        if not lockbox and m0 >= LOCKBOX:
            break
        tr = df[yend] < m0                                 # purged: the training target was realised before the block
        te = (t >= m0) & (t < m1)
        if tr.sum() < 2000 or te.sum() == 0:
            continue
        med = X[tr].median().fillna(0.0)
        model = TR.make_model(kind)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(X[tr].fillna(med).values, df.loc[tr, "yn"].values)
            p = model.predict(X[te].fillna(med).values)
        o = df.loc[te, ["sym", "cls", "decision_at", "row", y, vn]].copy()
        o["pred"] = p * o[vn]
        out.append(o)
    return pd.concat(out) if out else pd.DataFrame()


def non_overlapping(pred: pd.DataFrame, hz: int) -> pd.DataFrame:
    """Every h-th decision date of the class, the same dates for every symbol: the portfolio's holds never overlap in
    time, so its periods are as independent as the market allows and the Sharpe and DSR count them honestly."""
    p = pred.copy()
    p["date"] = p["decision_at"].dt.floor("D")
    keep = np.sort(p["date"].unique())[::hz]
    return p[p["date"].isin(keep)].copy()


def rule_sign(pred: pd.DataFrame, hz: int, cost: float) -> pd.DataFrame:
    p = non_overlapping(pred, hz)
    p["take"] = p["pred"].abs() > 2 * cost
    p["pos"] = np.where(p["take"], np.sign(p["pred"]), 0.0)
    p["net"] = p["pos"] * p[f"y{hz}"] - p["take"] * 2 * cost
    return p


def rule_xs(pred: pd.DataFrame, hz: int, cost: float) -> pd.DataFrame:
    """Cross-sectional: on every h-th decision date of the class, long the top fifth, short the bottom fifth."""
    p = non_overlapping(pred, hz)
    rk = p.groupby("date")["pred"].rank(pct=True)
    n = p.groupby("date")["pred"].transform("size")
    p["pos"] = np.where((rk > 0.8) & (n >= XS_MIN_SYMBOLS), 1.0, np.where((rk <= 0.2) & (n >= XS_MIN_SYMBOLS), -1.0, 0.0))
    p["take"] = p["pos"] != 0
    p["net"] = p["pos"] * p[f"y{hz}"] - p["take"] * 2 * cost
    return p


def score(tr: pd.DataFrame, hz: int, cls: str) -> dict:
    taken = tr[tr["take"]]
    port = taken.groupby("date")["net"].mean().reindex(sorted(tr["date"].unique()), fill_value=0.0)
    ic = tr[["pred", f"y{hz}"]].corr(method="spearman").iloc[0, 1] if len(tr) > 10 else float("nan")
    sr = float(port.mean() / port.std()) if len(port) > 2 and port.std() > 0 else 0.0
    per_year = PER_YEAR["crypto" if cls == "crypto" else "other"] / hz
    y = f"y{hz}"
    return {"n_pred": int(len(tr)), "n_trades": int(len(taken)), "ic": float(ic),
            "hit": float((np.sign(taken["pos"]) == np.sign(taken[y])).mean()) if len(taken) else None,
            "mean_net_per_trade_bps": float(taken["net"].mean() * 1e4) if len(taken) else None,
            "mean_gross_per_trade_bps": float((taken["pos"] * taken[y]).mean() * 1e4) if len(taken) else None,
            "sr_period": sr, "sr_annual": sr * math.sqrt(per_year), "n_periods": int(len(port)),
            "skew": float(port.skew()) if len(port) > 3 else 0.0, "kurt": float(port.kurt() + 3) if len(port) > 3 else 3.0,
            "first": str(tr["decision_at"].min()), "last": str(tr["decision_at"].max())}


def panel(syms, horizons, lockbox: bool, leaders, cal, si, implied: dict | None = None) -> pd.DataFrame:
    parts = []
    for s in syms:
        f = build(s, horizons, leaders, cal, si, implied)
        if f is None:
            continue
        if not lockbox:
            f = f[f["decision_at"] < LOCKBOX]
            for hz in horizons:                            # an outcome realised in the lockbox is not development data
                f.loc[~(f[f"yend{hz}"] < LOCKBOX), f"y{hz}"] = np.nan
        parts.append(f)
    return pd.concat(parts).replace([np.inf, -np.inf], np.nan) if parts else pd.DataFrame()


def load_implied() -> dict:
    spy = load_daily("SPY")
    return IM.load(spy, known_at(spy.index, "equity_etf") if spy is not None else None)


def run(classes, horizons, lockbox: bool, models=("ridge", "gbm"), families=T578_FAMILIES, baselines: bool = True,
        extra_trials: int = 0) -> dict:
    """``families`` beyond T-578's (the F3 ones, T-580) load the implied series; ``extra_trials`` adds the cells of an
    earlier run of the same programme to the deflated Sharpe's trial count."""
    leaders, cal, si = leader_frames(), FE.calendars(), FE.short_interest()
    implied = load_implied() if any("F3" in f for f in families) else None
    by_cls = {}
    for s in YAHOO + [f"{c}-USD" for c in COINBASE]:
        by_cls.setdefault(ASSET_CLASS.get(s, "other"), []).append(s)
    cells = []
    for cls in classes:
        cost = TR.COST.get(cls)
        if cost is None:
            continue
        df = panel(by_cls.get(cls, []), horizons, lockbox, leaders, cal, si, implied)
        if df.empty:
            cells.append({"cls": cls, "status": "no data"}); continue
        nsym = int(df["sym"].nunique())
        rules = [("sign", rule_sign)] + ([("xs", rule_xs)] if nsym >= XS_MIN_SYMBOLS else [])
        for hz in horizons:
            for fam_name in families:
                fam = FAMILIES[fam_name]
                cols = [c for c in family_cols(df.columns, fam) if c in df.columns]
                for kind in models:
                    pred = walk_forward(df, cols, kind, hz, lockbox)
                    if pred.empty:
                        cells.append({"cls": cls, "h": hz, "family": fam_name, "model": kind, "status": "too little data"})
                        continue
                    for rname, rule in rules:
                        sc = score(rule(pred, hz, cost), hz, cls)
                        cells.append({"cls": cls, "h": hz, "family": fam_name, "model": kind, "rule": rname, "n_symbols": nsym, **sc})
                        print(json.dumps({k: cells[-1].get(k) for k in ("cls", "h", "family", "model", "rule", "n_trades", "ic",
                                                                         "mean_net_per_trade_bps", "sr_annual")}), flush=True)
            if not baselines:
                continue
            # baselines: sign of the trailing h-day return (time-series momentum) and its inverse, same evaluation
            rcol = {1: "r1", 5: "r5", 20: "r20"}.get(hz, "r20")
            base = df[(df["decision_at"] >= DEV_START)].dropna(subset=[f"y{hz}", f"vn{hz}"])
            for nm, sgn in (("baseline_momentum", 1.0), ("baseline_reversal", -1.0)):
                b = base[["sym", "cls", "decision_at", "row", f"y{hz}", f"vn{hz}"]].copy()
                b["pred"] = sgn * np.sign(base[rcol].fillna(0)) * 1.0
                sc = score(rule_sign(b, hz, cost), hz, cls)
                cells.append({"cls": cls, "h": hz, "family": nm, "model": "rule", "rule": "sign", "n_symbols": nsym, **sc})
    n_trials = sum(1 for c in cells if "sr_period" in c) + extra_trials
    for c in cells:
        if "sr_period" in c:
            c["dsr"] = TR.deflated_sharpe(c["sr_period"], c["n_periods"], n_trials, c["skew"], c["kurt"])
            c["passes_dev"] = bool(c["dsr"] >= 0.95 and (c["mean_net_per_trade_bps"] or 0) > 0)
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lockbox_open": lockbox, "n_trials": n_trials,
            "cells": cells}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.ml.swing")
    ap.add_argument("--classes", default="crypto,stock,equity_etf,bond_etf,commodity_etf,future,fx")
    ap.add_argument("--horizons", default="1,5,20")
    ap.add_argument("--models", default="ridge,gbm")
    ap.add_argument("--lockbox", action="store_true")
    ap.add_argument("--stage", default="dev")
    ap.add_argument("--families", default=",".join(T578_FAMILIES), help="T-580: F0F1F3,ALLF3")
    ap.add_argument("--no-baselines", action="store_true")
    ap.add_argument("--extra-trials", type=int, default=0, help="cells of an earlier run counted in the DSR")
    a = ap.parse_args(argv)
    res = run(a.classes.split(","), tuple(int(x) for x in a.horizons.split(",")), a.lockbox, tuple(a.models.split(",")),
              tuple(a.families.split(",")), not a.no_baselines, a.extra_trials)
    TR.OUT.mkdir(parents=True, exist_ok=True)
    (TR.OUT / f"swing_{a.stage}.json").write_text(json.dumps(res, indent=1, default=str))
    passing = [c for c in res["cells"] if c.get("passes_dev")]
    print(f"{res['n_trials']} cells; {len(passing)} pass development")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
