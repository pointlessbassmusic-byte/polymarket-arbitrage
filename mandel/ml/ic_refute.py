"""
Independent refutation of T-579 (the feature correlation scan), run after its verdict and kept separate from it.
================================================================================================================

    python -m mandel.ml.ic_refute          # writes mandel/state/ml/ic_refute.json

Three attacks on "225 of 604 discovered relationships confirmed out of sample":
  1. dependence: the triples are not independent (the same effect appears as many features, intervals and classes).
     A joint sign-flip null flips every confirmation period's IC for ALL triples together (one coin per period label),
     which keeps the dependence between triples, and counts confirmations under the null;
  2. microstructure: an effect carried by stale prints or bid-ask bounce dies when the target starts one bar later.
     Every confirmed triple is re-scored with the target shifted by one bar (intraday) or one day (daily);
  3. how many effects: confirmed triples are grouped into effect families, and the count of distinct families is
     reported next to the triple count.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import t as student

from mandel.ml import features as FE
from mandel.ml import ic as IC
from mandel.ml import swing as SW
from mandel.ml import train as TR

N_DRAWS = 2000
SEED = 0


def family_of_effect(r: dict) -> str:
    f = r["feature"]
    if f.startswith("x_"):
        lead = f[2:].rsplit("_r", 1)[0] if r["scope"] == "daily" else f[2:]
        return f"{r['scope']}: other asset {lead} ({r['sign']})"
    if f in ("r_sess", "vwap_dist"):
        return f"{r['scope']}: return since the session open / VWAP ({r['sign']})"
    if f in ("r1", "r2", "r3", "r5", "r6", "r12", "r20", "r60", "r120", "ma50_dist", "ma200_dist", "gap", "clv", "ibs"):
        return f"{r['scope']}: own past price ({r['sign']})"
    return f"{r['scope']}: {f} ({r['sign']})"


def _conf_p(ics: np.ndarray, sign: float) -> float:
    n = len(ics)
    sd = ics.std(ddof=1)
    if n < 3 or sd == 0:
        return 1.0
    t = sign * ics.mean() / sd * np.sqrt(n)
    return float(student.sf(t, n - 1))


def run() -> dict:
    scan = json.loads((TR.OUT / "ic_scan.json").read_text())
    if not scan.get("intraday_confirmation_read"):
        raise SystemExit("the scan's intraday confirmation has not been read; nothing to refute")
    disc = [r for r in scan["rows"] if r.get("discovered")]
    by_panel = defaultdict(list)
    for r in disc:
        by_panel[(r["scope"], r["cls"], r["horizon"])].append(r)
    by_cls = IC._by_cls()
    conf_ics = {}                         # triple key -> pd.Series of confirmation-period ICs (original target)
    gap = {}                              # triple key -> gapped discovery / confirmation summaries
    leaders, cal, si = SW.leader_frames(), FE.calendars(), FE.short_interest()
    daily_cache = {}
    for (scope, cls, hor), rows in sorted(by_panel.items()):
        if scope == "intraday":
            iv = hor.split()[0]
            df = TR.panel(by_cls[cls], iv, lockbox=True).sort_values(["sym", "decision_at"]).reset_index(drop=True)
            per = df["decision_at"].dt.tz_convert("UTC" if cls == "crypto" else "America/New_York").dt.date.astype(str)
            y = "y1"
            d_mask = (df["decision_at"] < TR.LOCKBOX) & (df["y_end"] < TR.LOCKBOX)
            c_mask = df["decision_at"] >= TR.LOCKBOX
        else:
            if cls not in daily_cache:
                daily_cache[cls] = SW.panel(by_cls[cls], (1, 5, 20), False, leaders, cal, si).sort_values(
                    ["sym", "decision_at"]).reset_index(drop=True)
            df = daily_cache[cls]
            per = df["decision_at"].dt.strftime("%Y-%m")
            y = f"y{int(hor[:-1])}"
            d_mask = (df["decision_at"] >= pd.Timestamp("2016-01-01", tz="UTC")) & (df["decision_at"] < IC.DAILY_DISCOVERY_END)
            c_mask = (df["decision_at"] >= IC.DAILY_DISCOVERY_END) & (df["decision_at"] < TR.LOCKBOX)
        # the one-bar gap: the same symbol's target one row later (its next bar or next day)
        df = df.assign(_per=per.values, _yg=df.groupby("sym")[y].shift(-1))
        for r in rows:
            key = (scope, cls, hor, r["feature"])
            conf_ics[key] = IC.period_ics(df[c_mask], r["feature"], y, df.loc[c_mask, "_per"])
            if r.get("confirmed"):
                gd = IC.summarise(IC.period_ics(df[d_mask], r["feature"], "_yg", df.loc[d_mask, "_per"]))
                gc = IC.period_ics(df[c_mask], r["feature"], "_yg", df.loc[c_mask, "_per"])
                sgn = 1.0 if r["sign"] == "positive" else -1.0
                gap[key] = {"disc": gd, "conf": IC.summarise(gc), "conf_p_one_sided": _conf_p(gc.values, sgn) if len(gc) else None,
                            "same_sign_disc": bool(gd["mean_ic"] is not None and np.sign(gd["mean_ic"]) == sgn),
                            "confirmed": bool(len(gc) >= 3 and _conf_p(gc.values, sgn) < 0.05)}
    # 1. joint sign-flip null over period labels (one coin per label, shared by every triple)
    keys = [k for k in conf_ics if len(conf_ics[k]) >= 3]
    signs = {k: (1.0 if next(r for r in disc if (r["scope"], r["cls"], r["horizon"], r["feature"]) == k)["sign"] == "positive" else -1.0)
             for k in keys}
    labels = sorted({lab for k in keys for lab in conf_ics[k].index.astype(str)})
    pos = {lab: i for i, lab in enumerate(labels)}
    rng = np.random.default_rng(SEED)
    observed = sum(_conf_p(conf_ics[k].values, signs[k]) < 0.05 for k in keys)
    idx = {k: np.array([pos[str(x)] for x in conf_ics[k].index]) for k in keys}
    null = np.empty(N_DRAWS, int)
    for b in range(N_DRAWS):
        coin = rng.choice([-1.0, 1.0], size=len(labels))
        null[b] = sum(_conf_p(conf_ics[k].values * coin[idx[k]], signs[k]) < 0.05 for k in keys)
    # 3. effect families among confirmed triples
    conf_rows = [r for r in disc if r.get("confirmed")]
    fams = Counter(family_of_effect(r) for r in conf_rows)
    fam_gap = defaultdict(lambda: [0, 0])
    for r in conf_rows:
        g = gap.get((r["scope"], r["cls"], r["horizon"], r["feature"]))
        if g:
            fam_gap[family_of_effect(r)][0] += 1
            fam_gap[family_of_effect(r)][1] += int(g["confirmed"])
    n_gap = sum(1 for g in gap.values() if g["confirmed"])
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "joint_sign_flip": {"n_triples": len(keys), "observed_confirmed": int(observed), "n_draws": N_DRAWS,
                                "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
                                "null_max": int(null.max()), "p": float((1 + (null >= observed).sum()) / (N_DRAWS + 1))},
            "gap_one_bar": {"n_confirmed_triples": len(gap), "still_confirmed": n_gap,
                            "same_sign_in_discovery": sum(1 for g in gap.values() if g["same_sign_disc"])},
            "effect_families": [{"family": f, "triples": n, "gap_rescored": fam_gap[f][0], "gap_confirmed": fam_gap[f][1]}
                                for f, n in fams.most_common()],
            "gap_rows": [{"scope": k[0], "cls": k[1], "horizon": k[2], "feature": k[3], **v} for k, v in gap.items()]}


def main() -> int:
    res = run()
    (TR.OUT / "ic_refute.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "gap_rows"}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
