"""
Feature correlation scan for the learning program (T-579): every feature against the forward return, positive or inverse.
=======================================================================================================================

    python -m mandel.ml.ic                 # discovery (intraday: before 2026-10-01; daily: 2016-2025) + daily confirmation
    python -m mandel.ml.ic --confirm       # also the intraday confirmation on the lockbox (once, after T-577's development)
    python -m mandel.ml.ic --f3            # T-580's options-implied rows, their own Benjamini-Hochberg family

For each (feature, asset class, interval or hold) the rank correlation (Spearman) with the forward return is computed
inside each period (a trading day for intraday bars, a calendar month for daily bars), pooled over the class's symbols;
the statistic is the mean over periods and its t, so overlapping targets inside a period do not inflate it.
Benjamini-Hochberg over every triple picks the discoveries; each is then checked, in its own sign, on a period the scan
never saw. Writes mandel/state/ml/ic_scan.json. A correlation is not a trade: a confirmed triple only becomes a
strategy through its own pre-registered, costed test.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from statistics import NormalDist

import numpy as np
import pandas as pd

from mandel.ml import features as FE
from mandel.ml import swing as SW
from mandel.ml import train as TR
from mandel.ml.fetch import ASSET_CLASS, COINBASE, YAHOO

ND = NormalDist()
MIN_ROWS_PER_PERIOD = 30
DAILY_DISCOVERY_END = pd.Timestamp("2026-01-01", tz="UTC")


def period_ics(df: pd.DataFrame, feat: str, y: str, period: pd.Series) -> pd.Series:
    """Spearman of feat vs y inside each period (ranks within the period, then Pearson of the ranks)."""
    d = pd.DataFrame({"x": df[feat].values, "y": df[y].values, "p": period.values}).dropna()
    if d.empty:
        return pd.Series(dtype=float)
    g = d.groupby("p")
    n = g["x"].transform("size")
    d = d[n >= MIN_ROWS_PER_PERIOD]
    if d.empty:
        return pd.Series(dtype=float)
    g = d.groupby("p")
    rx = g["x"].rank() - g["x"].transform("size").add(1) / 2
    ry = g["y"].rank() - g["y"].transform("size").add(1) / 2
    num = (rx * ry).groupby(d["p"]).sum()
    den = np.sqrt((rx ** 2).groupby(d["p"]).sum() * (ry ** 2).groupby(d["p"]).sum())
    return (num / den.replace(0, np.nan)).dropna()


def summarise(ics: pd.Series) -> dict:
    """Mean period IC, its t over periods and the two-sided p from Student's t with n - 1 degrees of freedom (a
    confirmation period of nine months is too short for the normal approximation)."""
    from scipy.stats import t as student
    n = len(ics)
    if n < 3 or ics.std() == 0:
        return {"n_periods": n, "mean_ic": float(ics.mean()) if n else None, "t": None, "p": None}
    t = float(ics.mean() / ics.std() * math.sqrt(n))
    return {"n_periods": n, "mean_ic": float(ics.mean()), "t": t, "p": float(2 * student.sf(abs(t), n - 1))}


def bh(pvals: list) -> list:
    """Benjamini-Hochberg q-values."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [1.0] * m
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, pvals[i] * m / rank)
        q[i] = prev
    return q


def family_of(feat: str) -> str:
    if feat.startswith("x_"):
        return "F1"
    return "F0" if feat in FE.F0 or feat in SW.F0 else "F2"


def judge(rows: list) -> dict:
    """Benjamini-Hochberg over ``rows``, then each discovery's one-sided check in its own sign."""
    tested = [r for r in rows if r["disc_p"] is not None]
    for r, q in zip(tested, bh([r["disc_p"] for r in tested])):
        r["disc_q"] = q
        r["discovered"] = q < 0.05
        r["sign"] = "positive" if (r["disc_mean_ic"] or 0) > 0 else "inverse"
        c = r["conf"]
        if r["discovered"] and c and c.get("t") is not None:
            from scipy.stats import t as student
            t_signed = c["t"] if r["sign"] == "positive" else -c["t"]
            c["p_one_sided"] = float(student.sf(t_signed, c["n_periods"] - 1))
            r["confirmed"] = c["p_one_sided"] < 0.05
        else:
            r["confirmed"] = None if r["discovered"] else False
    disc = [r for r in tested if r["discovered"]]
    judged = [r for r in disc if r["confirmed"] is not None]
    conf = [r for r in judged if r["confirmed"]]
    return {"n_triples": len(tested), "n_discovered": len(disc), "n_judged": len(judged), "n_confirmed": len(conf),
            "confirmed_fraction": (len(conf) / len(judged)) if judged else None}


def daily_rows(cls: str, df: pd.DataFrame, feats: list) -> list:
    month = df["decision_at"].dt.strftime("%Y-%m")
    disc = (df["decision_at"] >= pd.Timestamp("2016-01-01", tz="UTC")) & (df["decision_at"] < DAILY_DISCOVERY_END)
    conf = (df["decision_at"] >= DAILY_DISCOVERY_END) & (df["decision_at"] < TR.LOCKBOX)
    rows = []
    for hz in (1, 5, 20):
        for ft in feats:
            d = summarise(period_ics(df[disc], ft, f"y{hz}", month[disc]))
            c = summarise(period_ics(df[conf], ft, f"y{hz}", month[conf]))
            rows.append({"scope": "daily", "cls": cls, "horizon": f"{hz}d", "feature": ft, "family": family_of(ft),
                         **{f"disc_{k}": v for k, v in d.items()}, "conf": c})
    return rows


def scan_f3() -> dict:
    """T-580's options-implied features, scanned with the T-579 method as their own family."""
    from mandel.ml import implied as IM
    leaders, cal, si, implied = SW.leader_frames(), FE.calendars(), FE.short_interest(), SW.load_implied()
    rows = []
    for cls, syms in _by_cls().items():
        if TR.COST.get(cls) is None:
            continue
        df = SW.panel(syms, (1, 5, 20), False, leaders, cal, si, implied)
        if not df.empty:
            rows += daily_rows(cls, df, [c for c in IM.F3 if c in df.columns])
    for r in rows:
        r["family"] = "F3"
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), **judge(rows), "rows": rows}


def _by_cls() -> dict:
    by_cls = {}
    for s in YAHOO + [f"{c}-USD" for c in COINBASE]:
        by_cls.setdefault(ASSET_CLASS.get(s, "other"), []).append(s)
    return by_cls


def scan(confirm_intraday: bool) -> dict:
    by_cls = _by_cls()
    rows = []
    # intraday: T-577 panels, h = 1 bar, period = trading day (New York date; crypto: UTC date)
    for cls, syms in by_cls.items():
        if TR.COST.get(cls) is None:
            continue
        for iv in FE.INTERVAL_MIN:
            df = TR.panel(syms, iv, lockbox=confirm_intraday)       # sealed unless the confirmation is being read
            if df.empty:
                continue
            day = df["decision_at"].dt.tz_convert("UTC" if cls == "crypto" else "America/New_York").dt.date
            disc = (df["decision_at"] < TR.LOCKBOX) & (df["y_end"] < TR.LOCKBOX)
            conf = df["decision_at"] >= TR.LOCKBOX
            feats = [c for c in FE.F0 + FE.F2 + [c for c in df.columns if c.startswith("x_")] if c in df.columns]
            for ft in feats:
                d = summarise(period_ics(df[disc], ft, "y1", day[disc]))
                c = summarise(period_ics(df[conf], ft, "y1", day[conf])) if confirm_intraday else None
                rows.append({"scope": "intraday", "cls": cls, "horizon": f"{iv} x1", "feature": ft, "family": family_of(ft),
                             **{f"disc_{k}": v for k, v in d.items()}, "conf": c})
    # daily: T-578 panels, h = 1, 5, 20 days, period = calendar month; discovery 2016-2025, confirmation 2026-01..09
    leaders, cal, si = SW.leader_frames(), FE.calendars(), FE.short_interest()
    for cls, syms in by_cls.items():
        if TR.COST.get(cls) is None:
            continue
        df = SW.panel(syms, (1, 5, 20), False, leaders, cal, si)
        if not df.empty:
            rows += daily_rows(cls, df, [c for c in SW.F0 + SW.F2 + [c for c in df.columns if c.startswith("x_")]
                                         if c in df.columns])
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "intraday_confirmation_read": confirm_intraday,
            **judge(rows), "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mandel.ml.ic")
    ap.add_argument("--confirm", action="store_true", help="read the intraday lockbox (once, after T-577 development)")
    ap.add_argument("--f3", action="store_true", help="T-580's options-implied rows only")
    a = ap.parse_args(argv)
    res = scan_f3() if a.f3 else scan(a.confirm)
    TR.OUT.mkdir(parents=True, exist_ok=True)
    (TR.OUT / ("ic_scan_f3.json" if a.f3 else "ic_scan.json")).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
