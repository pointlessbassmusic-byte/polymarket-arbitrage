"""
Walk-forward training and evaluation for the learning program (T-577).
======================================================================

    python -m mandel.ml.train [--classes crypto,stock,...] [--intervals 5m,15m,...] [--lockbox]

Per cell (asset class x interval x family x model): pooled walk-forward over weekly test blocks with an expanding
training window and a 1-day embargo, models fitted on targets divided by trailing volatility, predictions turned into
trades by the pre-registered rule, net of the pre-registered costs. Without --lockbox, data from 2026-10-01 on is
dropped before anything is built: the lockbox is opened once, after development, for the cells that passed.
Writes mandel/state/ml/results_<stage>.json (statistics only).
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mandel.ml import features as FE
from mandel.ml.fetch import ASSET_CLASS, COINBASE, YAHOO
from mandel.paths import MANDEL_ROOT

OUT = MANDEL_ROOT / "state" / "ml"
LOCKBOX = pd.Timestamp("2026-10-01", tz="UTC")
COST = {"crypto": 4e-4, "stock": 2e-4, "equity_etf": 1e-4, "bond_etf": 1e-4, "commodity_etf": 1e-4, "future": 1e-4,
        "fx": 1e-4, "index": None}
FAMILIES = {"F0": "f0", "F0F1": "f0f1", "F2": "f2", "ALL": "all"}
EMBARGO = pd.Timedelta(days=1)
MIN_TRAIN_DAYS = 14
H = 1
BARS_PER_YEAR = {"crypto": 365 * 24 * 60, "other": 252 * 6.5 * 60}       # minutes per year, divided by the interval


def family_cols(cols, fam: str) -> list:
    f1 = [c for c in cols if c.startswith("x_")]
    return {"f0": FE.F0, "f0f1": FE.F0 + f1, "f2": FE.F2, "all": FE.F0 + f1 + FE.F2}[fam]


def make_model(kind: str):
    if kind == "ridge":
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    import lightgbm as lgb
    return lgb.LGBMRegressor(n_estimators=200, num_leaves=31, learning_rate=0.05, min_child_samples=200,
                             subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=4)


def panel(syms, interval: str, lockbox: bool) -> pd.DataFrame:
    leaders = FE.leader_returns(interval)
    cal = FE.calendars()
    si = FE.short_interest()
    parts = []
    for s in syms:
        f = FE.build(s, interval, (H,), leaders, cal, si)
        if f is None:
            continue
        if not lockbox:
            f = f[f["decision_at"] < LOCKBOX]
        parts.append(f)
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts)
    df["yn"] = df[f"y{H}"] / df["vol_norm"]
    return df.replace([np.inf, -np.inf], np.nan)


def walk_forward(df: pd.DataFrame, cols: list, kind: str) -> pd.DataFrame:
    """Out-of-sample predictions for every weekly block after the minimum training span."""
    df = df.dropna(subset=["yn"]).copy()
    df = df[np.isfinite(df["vol_norm"])]
    X = df[cols].astype(float)
    t = df["decision_at"]
    start = t.min() + pd.Timedelta(days=MIN_TRAIN_DAYS)
    weeks = pd.date_range(start.floor("D"), t.max(), freq="7D")
    out = []
    for w0 in weeks:
        w1 = w0 + pd.Timedelta(days=7)
        tr = t < (w0 - EMBARGO)
        te = (t >= w0) & (t < w1)
        if tr.sum() < 2000 or te.sum() == 0:
            continue
        m = make_model(kind)
        Xtr = X[tr].fillna(X[tr].median())
        ytr = df.loc[tr, "yn"].clip(-10, 10)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(Xtr.values, ytr.values)
            p = m.predict(X[te].fillna(X[tr].median()).values)
        o = df.loc[te, ["sym", "cls", "decision_at", f"y{H}", "vol_norm"]].copy()
        o["pred_n"] = p
        out.append(o)
    return pd.concat(out) if out else pd.DataFrame()


def trade(pred: pd.DataFrame, cost_side: float) -> pd.DataFrame:
    """The pre-registered rule: trade the sign when the predicted absolute return beats the round trip."""
    p = pred.copy()
    p["pred"] = p["pred_n"] * p["vol_norm"]
    p["take"] = p["pred"].abs() > 2 * cost_side
    p["pos"] = np.where(p["take"], np.sign(p["pred"]), 0.0)
    p["net"] = p["pos"] * p[f"y{H}"] - p["take"] * 2 * cost_side
    return p


def deflated_sharpe(sr_per_period: float, n: int, n_trials: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Bailey & Lopez de Prado DSR of a per-period Sharpe over n periods against the expected max of n_trials."""
    from statistics import NormalDist
    nd = NormalDist()
    if n < 3 or n_trials < 1:
        return float("nan")
    emc = 0.5772156649
    sr0 = math.sqrt(1.0 / max(1, n - 1)) * ((1 - emc) * nd.inv_cdf(1 - 1 / n_trials) + emc * nd.inv_cdf(1 - 1 / (n_trials * math.e))) \
        if n_trials > 1 else 0.0
    den = math.sqrt(max(1e-12, 1 - skew * sr_per_period + (kurt - 1) / 4 * sr_per_period ** 2))
    z = (sr_per_period - sr0) * math.sqrt(n - 1) / den
    return nd.cdf(z)


def score(tr: pd.DataFrame, interval_min: int, cls: str) -> dict:
    taken = tr[tr["take"]]
    # one portfolio return per decision time: mean over symbols of the per-symbol net (equal weight)
    port = tr.groupby("decision_at")["net"].mean()
    ic = tr[["pred_n", f"y{H}"]].corr(method="spearman").iloc[0, 1] if len(tr) > 10 else float("nan")
    per_year = BARS_PER_YEAR["crypto" if cls == "crypto" else "other"] / interval_min
    sr = float(port.mean() / port.std()) if port.std() > 0 else 0.0
    return {"n_pred": int(len(tr)), "n_trades": int(len(taken)), "ic": float(ic),
            "hit": float((np.sign(taken["pred"]) == np.sign(taken[f"y{H}"])).mean()) if len(taken) else None,
            "mean_net_per_trade_bps": float(taken["net"].mean() * 1e4) if len(taken) else None,
            "mean_gross_per_trade_bps": float((taken["pos"] * taken[f"y{H}"]).mean() * 1e4) if len(taken) else None,
            "sr_period": sr, "sr_annual": sr * math.sqrt(per_year), "n_periods": int(len(port)),
            "skew": float(port.skew()) if len(port) > 3 else 0.0, "kurt": float(port.kurt() + 3) if len(port) > 3 else 3.0,
            "first": str(tr["decision_at"].min()), "last": str(tr["decision_at"].max())}


def run(classes, intervals, lockbox: bool, models=("ridge", "gbm")) -> dict:
    by_cls = {}
    for s in YAHOO + [f"{c}-USD" for c in COINBASE]:
        by_cls.setdefault(ASSET_CLASS.get(s, "other"), []).append(s)
    cells = []
    for cls in classes:
        cost = COST.get(cls)
        if cost is None:
            continue
        for iv in intervals:
            df = panel(by_cls.get(cls, []), iv, lockbox)
            if df.empty or df["sym"].nunique() == 0:
                cells.append({"cls": cls, "interval": iv, "status": "no data"}); continue
            for fam_name, fam in FAMILIES.items():
                cols = [c for c in family_cols(df.columns, fam) if c in df.columns]
                for kind in models:
                    pred = walk_forward(df, cols, kind)
                    if pred.empty:
                        cells.append({"cls": cls, "interval": iv, "family": fam_name, "model": kind, "status": "too little data"})
                        continue
                    tr = trade(pred, cost)
                    sc = score(tr, FE.INTERVAL_MIN[iv], cls)
                    cells.append({"cls": cls, "interval": iv, "family": fam_name, "model": kind, "n_symbols": int(df["sym"].nunique()),
                                  **sc})
                    print(json.dumps({k: cells[-1].get(k) for k in ("cls", "interval", "family", "model", "n_trades", "ic",
                                                                     "mean_net_per_trade_bps", "sr_annual")}), flush=True)
            # baselines on the same panel: sign of the last bar's return (momentum) and its inverse
            base = df.dropna(subset=[f"y{H}"]).copy()
            base = base[base["decision_at"] >= base["decision_at"].min() + pd.Timedelta(days=MIN_TRAIN_DAYS)]
            for nm, sgn in (("baseline_last_return", 1.0), ("baseline_reversal", -1.0)):
                b = base.assign(pred_n=sgn * np.sign(base["r1"].fillna(0)) * 10)
                sc = score(trade(b[["sym", "cls", "decision_at", f"y{H}", "vol_norm", "pred_n"]], cost), FE.INTERVAL_MIN[iv], cls)
                cells.append({"cls": cls, "interval": iv, "family": nm, "model": "rule", "n_symbols": int(df["sym"].nunique()), **sc})
    n_trials = sum(1 for c in cells if "sr_period" in c)
    for c in cells:
        if "sr_period" in c:
            c["dsr"] = deflated_sharpe(c["sr_period"], c["n_periods"], n_trials, c["skew"], c["kurt"])
            c["passes_dev"] = bool(c["dsr"] >= 0.95 and (c["mean_net_per_trade_bps"] or 0) > 0)
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lockbox_open": lockbox, "n_trials": n_trials,
            "cells": cells}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.ml.train")
    ap.add_argument("--classes", default="crypto,stock,equity_etf,bond_etf,commodity_etf,future,fx")
    ap.add_argument("--intervals", default="5m,15m,30m,45m,60m")
    ap.add_argument("--models", default="ridge,gbm")
    ap.add_argument("--lockbox", action="store_true")
    ap.add_argument("--stage", default="dev")
    a = ap.parse_args(argv)
    res = run(a.classes.split(","), a.intervals.split(","), a.lockbox, tuple(a.models.split(",")))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"results_{a.stage}.json").write_text(json.dumps(res, indent=1, default=str))
    passing = [c for c in res["cells"] if c.get("passes_dev")]
    print(f"{res['n_trials']} cells; {len(passing)} pass development")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
