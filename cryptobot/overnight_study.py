"""Overnight-only index exposure: hold from the US close to the next
open, flat during the session. Pre-registered as `overnight-index-perp`
(hypotheses.yaml), with the success bar written before this ran.

Inputs (free, fetched 2026-10-12; --dir):
  eodhd_VTI.US.json   VTI daily OHLC + adjusted close since 2001-05 (EODHD demo)
  nasdaq_SPY.json     SPY daily OHLC 2016-10 .. (Nasdaq data API, 10-year cap)
  nasdaq_NDX.json     Nasdaq-100 index daily OHLC since 1996-06 (opens from 1996)
  kalshi_us500_funding.json   the US500 perp's funding history (daily, from 2026-10-06)

Returns are log returns. Overnight = ln(open_t / close_{t-1}); intraday =
ln(close_t / open_t). Where an adjusted close exists, dividends are
recovered from the adjustment factor and added to the overnight return
of the ex-date (the overnight holder receives them; the price drop at
the open is not a loss). The buy-and-hold benchmark gets the same
dividends on the same days. An index series has no dividends; the perp
that would trade it carries the basis in its funding instead, which is
why funding is a separate sensitivity here.

Costs per night: two executions at `fee` plus `half_spread` each, and
`funding` per night (the perp's daily rate when the long pays). Sharpe
is per-observation x sqrt(observations per year), so a weekday subset is
not deflated by the nights it skips.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

from . import stats as S

ERAS = (
    ("1996-00", dt.date(1996, 1, 1), dt.date(2000, 12, 31)),
    ("2001-07", dt.date(2001, 1, 1), dt.date(2007, 12, 31)),
    ("2008-14", dt.date(2008, 1, 1), dt.date(2014, 12, 31)),
    ("2015-19", dt.date(2015, 1, 1), dt.date(2019, 12, 31)),
    ("2020-26", dt.date(2020, 1, 1), dt.date(2026, 12, 31)),
)
SCORED_ERAS = ("2001-07", "2008-14", "2015-19", "2020-26")   # the pre-registered four
VARIANTS = ("all nights", "skip Fri->Mon", "Mon->Tue only")


# ------------------------------------------------------------------ loading

def load_nasdaq(path: Path) -> list[dict]:
    from .data.nasdaq import parse_history
    return [{"day": dt.date.fromisoformat(r["date"]), "open": r["open"], "close": r["close"], "adj": None}
            for r in parse_history(json.loads(Path(path).read_text()))]


def load_eodhd(path: Path) -> list[dict]:
    rows = []
    for r in json.loads(Path(path).read_text()):
        try:
            day = dt.date.fromisoformat(r["date"])
            o, c = float(r["open"]), float(r["close"])
            adj = float(r.get("adjusted_close") or 0) or None
        except (KeyError, ValueError, TypeError):
            continue
        if o > 0 and c > 0:
            rows.append({"day": day, "open": o, "close": c, "adj": adj})
    rows.sort(key=lambda r: r["day"])
    return rows


def dividends(rows: list[dict], split_threshold: float = 0.10) -> dict[dt.date, float]:
    """Dividend yield on each ex-date (relative to the previous close),
    recovered from the adjusted-close factor; ratio changes above
    `split_threshold` are splits and ignored."""
    out = {}
    prev = None
    for r in rows:
        if r["adj"] and prev and prev["adj"]:
            f_prev, f = prev["adj"] / prev["close"], r["adj"] / r["close"]
            y = 1.0 - f_prev / f if f > 0 else 0.0
            if 1e-6 < y < split_threshold:
                out[r["day"]] = y
        prev = r
    return out


def series(rows: list[dict], with_dividends: bool = True) -> list[dict]:
    """Per trading day: overnight, intraday and close-to-close log
    returns, the ex-date dividend, and the weekday of the night's start."""
    divs = dividends(rows) if with_dividends else {}
    out = []
    for i in range(1, len(rows)):
        p, r = rows[i - 1], rows[i]
        d = divs.get(r["day"], 0.0)
        on = math.log(r["open"] / p["close"]) + d
        cc = math.log(r["close"] / p["close"]) + d
        out.append({"day": r["day"], "prev_day": p["day"], "overnight": on,
                    "intraday": math.log(r["close"] / r["open"]), "close_close": cc,
                    "gap_days": (r["day"] - p["day"]).days, "start_weekday": p["day"].weekday()})
    return out


def kalshi_funding(path: Path) -> dict:
    """Mean and median daily funding the long pays on the US500 perp."""
    try:
        d = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {"n": 0, "mean": 0.0, "median": 0.0}
    rates = [float(r["funding_rate"]) for r in d.get("funding_rates", []) if r.get("funding_rate") not in (None, "")]
    if not rates:
        return {"n": 0, "mean": 0.0, "median": 0.0}
    return {"n": len(rates), "mean": statistics.fmean(rates), "median": statistics.median(rates)}


# ------------------------------------------------------------------ rules

def held(row: dict, variant: str) -> bool:
    if variant == "all nights":
        return True
    if variant == "skip Fri->Mon":
        return row["gap_days"] == 1          # no weekend or holiday gaps
    if variant == "Mon->Tue only":
        return row["start_weekday"] == 0 and row["gap_days"] == 1
    raise ValueError(variant)


def era_of(day: dt.date):
    for name, a, b in ERAS:
        if a <= day <= b:
            return name
    return None


def net_overnight(rows: list[dict], variant: str, fee: float, half_spread: float, funding: float) -> list[dict]:
    cost = 2 * (fee + half_spread) + funding
    return [{"day": r["day"], "ret": r["overnight"] - cost, "gross": r["overnight"]}
            for r in rows if held(r, variant)]


def sharpe_ann(rets: list[float], years: float) -> float:
    if len(rets) < 3 or years <= 0:
        return 0.0
    sd = statistics.pstdev(rets)
    if sd <= 0:
        return 0.0
    per_year = len(rets) / years
    return statistics.fmean(rets) / sd * math.sqrt(per_year)


def _years(days: list[dt.date]) -> float:
    return max((days[-1] - days[0]).days, 1) / 365.25 if days else 0.0


def summarize(points: list[dict]) -> dict:
    rets = [p["ret"] for p in points]
    days = [p["day"] for p in points]
    yrs = _years(days)
    return {"n": len(rets), "mean_bp": statistics.fmean(rets) * 1e4 if rets else 0.0,
            "ann_return": sum(rets) / yrs if yrs else 0.0, "sharpe": sharpe_ann(rets, yrs),
            "psr": S.psr(rets) if len(rets) > 2 else 0.0}


def by_era(points: list[dict]) -> dict:
    out = {}
    for name, _a, _b in ERAS:
        sub = [p for p in points if era_of(p["day"]) == name]
        if len(sub) >= 40:
            out[name] = summarize(sub)
    return out


def by_year(points: list[dict]) -> dict[int, float]:
    out: dict[int, float] = {}
    for p in points:
        out[p["day"].year] = out.get(p["day"].year, 0.0) + p["ret"]
    return out


def benchmark(rows: list[dict]) -> list[dict]:
    return [{"day": r["day"], "ret": r["close_close"]} for r in rows]


def passes(over: dict, hold: dict, psr_recent: float, eras: tuple = SCORED_ERAS) -> dict:
    """The pre-registered bar: Sharpe above buy-and-hold in >= 3 of the 4
    eras including 2020-26, and PSR >= 0.95 on the 2015-2026 net series."""
    wins = [e for e in eras if e in over and e in hold and over[e]["sharpe"] > hold[e]["sharpe"]]
    scored = [e for e in eras if e in over and e in hold]
    ok = len(wins) >= 3 and "2020-26" in wins and psr_recent >= 0.95
    return {"wins": wins, "scored": scored, "psr_2015_2026": psr_recent, "pass": ok}


def recent_psr(points: list[dict]) -> float:
    rets = [p["ret"] for p in points if p["day"] >= dt.date(2015, 1, 1)]
    return S.psr(rets) if len(rets) > 2 else 0.0


def run(rows: list[dict], label: str, funding_levels: dict, fees: tuple = ((0.0004, "4 bp taker"), (0.0002, "2 bp maker")),
        half_spread: float = 0.00003) -> dict:
    ser = series(rows)
    hold = benchmark(ser)
    out = {"label": label, "first": ser[0]["day"], "last": ser[-1]["day"], "n_days": len(ser),
           "hold": {"all": summarize(hold), "eras": by_era(hold), "years": by_year(hold)},
           "decomp": {}, "runs": [], "trials": 0}
    # gross decomposition by era: overnight vs intraday share of the return
    for name, _a, _b in ERAS:
        sub = [r for r in ser if era_of(r["day"]) == name]
        if len(sub) >= 40:
            yrs = _years([r["day"] for r in sub])
            out["decomp"][name] = {"overnight_ann": sum(r["overnight"] for r in sub) / yrs,
                                   "intraday_ann": sum(r["intraday"] for r in sub) / yrs,
                                   "overnight_sharpe": sharpe_ann([r["overnight"] for r in sub], yrs),
                                   "intraday_sharpe": sharpe_ann([r["intraday"] for r in sub], yrs),
                                   "n": len(sub)}
    srs = []
    for fee, fee_label in fees:
        for variant in VARIANTS:
            for fund_label, funding in funding_levels.items():
                pts = net_overnight(ser, variant, fee, half_spread, funding)
                res = {"fee": fee_label, "variant": variant, "funding": fund_label,
                       "all": summarize(pts), "eras": by_era(pts), "years": by_year(pts),
                       "check": passes(by_era(pts), out["hold"]["eras"], recent_psr(pts))}
                out["runs"].append(res)
                out["trials"] += 1
                if fund_label == "none":
                    srs.append(S.sharpe([p["ret"] for p in pts]))
    best = max(out["runs"], key=lambda r: r["all"]["sharpe"])
    if len(srs) >= 2:
        var_sr = statistics.pvariance(srs)
        best_fee = next(f for f, l in fees if l == best["fee"])
        pts = net_overnight(ser, best["variant"], best_fee, half_spread, funding_levels[best["funding"]])
        out["dsr_best"] = S.dsr([p["ret"] for p in pts], out["trials"], var_sr)
        out["best"] = (best["fee"], best["variant"], best["funding"])
    return out


# ------------------------------------------------------------------ report

def render(res: dict) -> str:
    o = [f"{res['label']}: {res['first']} .. {res['last']}, {res['n_days']} sessions"]
    o.append("  gross decomposition (annualised log return; Sharpe):")
    for era, d in res["decomp"].items():
        o.append(f"    {era}: overnight {d['overnight_ann']*100:+6.1f}% (SR {d['overnight_sharpe']:+.2f})   "
                 f"intraday {d['intraday_ann']*100:+6.1f}% (SR {d['intraday_sharpe']:+.2f})   n={d['n']}")
    h = res["hold"]
    o.append(f"  buy-and-hold: {h['all']['ann_return']*100:+.1f}%/yr, Sharpe {h['all']['sharpe']:+.2f}; by era "
             + ", ".join(f"{e} SR {v['sharpe']:+.2f}" for e, v in h["eras"].items()))
    o.append("  overnight-only, net:")
    o.append(f"    {'fee':12s} {'variant':14s} {'funding':10s} {'nights':>6s} {'bp/night':>9s} {'ann':>7s} {'SR':>6s} "
             f"{'PSR15+':>7s}  eras beaten (SR vs hold)")
    for r in res["runs"]:
        a, c = r["all"], r["check"]
        eras = " ".join(f"{e}:{r['eras'][e]['sharpe']:+.2f}/{res['hold']['eras'][e]['sharpe']:+.2f}" for e in c["scored"])
        flag = " PASS" if c["pass"] else ""
        o.append(f"    {r['fee']:12s} {r['variant']:14s} {r['funding']:10s} {a['n']:6d} {a['mean_bp']:+9.2f} "
                 f"{a['ann_return']*100:+6.1f}% {a['sharpe']:+6.2f} {c['psr_2015_2026']:7.2f}  "
                 f"{len(c['wins'])}/{len(c['scored'])} [{eras}]{flag}")
    if "dsr_best" in res:
        o.append(f"  trials {res['trials']}; best {res['best']} DSR {res['dsr_best']:.2f}")
    ys = sorted(res["hold"]["years"])
    base = next((r for r in res["runs"] if r["fee"].startswith("4") and r["variant"] == "all nights" and r["funding"] == "none"), None)
    if base:
        o.append("  by year, all nights at 4 bp (net) vs buy-and-hold:")
        o.append("    " + " ".join(f"{y}:{base['years'].get(y, 0)*100:+.0f}/{res['hold']['years'][y]*100:+.0f}" for y in ys))
    return "\n".join(o)


SOURCES = {
    "eodhd_VTI.US.json": "https://eodhd.com/api/eod/VTI.US?api_token=demo&fmt=json&from=1990-01-01",
    "nasdaq_SPY.json": "https://api.nasdaq.com/api/quote/SPY/historical?assetclass=etf&fromdate=1993-01-29&todate={today}&limit=9999",
    "nasdaq_NDX.json": "https://api.nasdaq.com/api/quote/NDX/historical?assetclass=index&fromdate=1993-01-01&todate={today}&limit=9999",
    "kalshi_us500_funding.json": "https://external-api.kalshi.com/trade-api/v2/margin/funding_rates/historical?ticker=KXUS500PERP&limit=1000",
}


def fetch(d: Path) -> None:
    """Download the four inputs into `d` (all free, no keys)."""
    import urllib.request
    d.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    for name, url in SOURCES.items():
        req = urllib.request.Request(url.format(today=today),
                                     headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) overnight-study/1.0",
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            (d / name).write_bytes(r.read())
        print(f"fetched {name}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="overnight")
    ap.add_argument("--fetch", action="store_true", help="download the inputs into --dir first")
    ap.add_argument("--json", help="write results here")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    if a.fetch:
        fetch(d)
    fund = kalshi_funding(d / "kalshi_us500_funding.json")
    levels = {"none": 0.0, "fair basis": 0.00008}
    if fund["n"]:
        levels[f"kalshi med ({fund['n']}d)"] = fund["median"]
        levels[f"kalshi mean ({fund['n']}d)"] = fund["mean"]
    print(f"Kalshi US500 perp funding, {fund['n']} daily prints: mean {fund['mean']*100:.3f}%/day, "
          f"median {fund['median']*100:.3f}%/day (fair basis for rates minus dividends ~0.008%/day)\n")
    results = []
    for fname, label, loader in (("eodhd_VTI.US.json", "VTI (US total market ETF, dividends added back)", load_eodhd),
                                 ("nasdaq_SPY.json", "SPY (price only, 10-year cap at the source)", load_nasdaq),
                                 ("nasdaq_NDX.json", "Nasdaq-100 index (price only)", load_nasdaq)):
        p = d / fname
        if not p.exists():
            print(f"{label}: {p} missing")
            continue
        res = run(loader(p), label, levels)
        results.append(res)
        print(render(res))
        print()
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
