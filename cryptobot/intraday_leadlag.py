"""Does the Kalshi BTC perp lead the US500 perp hour to hour while the
cash equity market is closed?

The cross-asset study found BTC's move between the US close and the
next open "predicts" the S&P's close-to-close return (t 3.9), which is
the overnight futures gap the cash close already contains, not a lead.
The perps settle that: both trade around the clock, so if BTC's hourly
return predicts the US500 perp's NEXT hourly return after the cash
close, that is a trade on the existing executor; if it only moves with
it in the same hour, it is comovement.

Data: the collector's hourly caches (state/kalshi_hourly/<ticker>.jsonl).
Pre-registered as `btc-leads-us500-intraday`; the bar is in the
registry. Costs for the follow rule: 4 bp a side plus 0.3 bp half-spread
on the US500 perp (8.6 bp a round trip, one trade an hour at most).

    python -m cryptobot.intraday_leadlag --state state
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from . import stats as S
from .crossasset_study import ols

ET = ZoneInfo("America/New_York")
MIN_HOURS = 500
COST_RT = 2 * (0.0004 + 0.00003)


def read_closes(path: Path) -> dict[int, float]:
    out = {}
    if not Path(path).exists():
        return out
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            out[int(r["end_ts"])] = float(r["close"])
        except (ValueError, KeyError, TypeError):
            continue
    return out


def cash_open(ts: int) -> bool:
    """True when the hour ENDING at ts fell inside 09:30-16:00 New York on a weekday."""
    t = dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(ET)
    if t.weekday() >= 5:
        return False
    start = t - dt.timedelta(hours=1)
    m0, m1 = start.hour * 60 + start.minute, t.hour * 60 + t.minute
    return m1 > 9 * 60 + 30 and m0 < 16 * 60


def align(a: dict[int, float], b: dict[int, float]) -> list[dict]:
    """Hourly log returns of both series on consecutive shared hours, with
    each hour's cash-session flag and the next hour's returns."""
    ts = sorted(set(a) & set(b))
    rows = []
    for i in range(1, len(ts)):
        if ts[i] - ts[i - 1] != 3600:
            continue
        rows.append({"ts": ts[i], "ra": math.log(a[ts[i]] / a[ts[i - 1]]), "rb": math.log(b[ts[i]] / b[ts[i - 1]]),
                     "open": cash_open(ts[i])})
    for i in range(len(rows) - 1):
        if rows[i + 1]["ts"] - rows[i]["ts"] == 3600:
            rows[i]["ra_next"], rows[i]["rb_next"] = rows[i + 1]["ra"], rows[i + 1]["rb"]
    return [r for r in rows if "rb_next" in r]


def regress(rows: list[dict], x: str, y: str, session: str | None = None) -> dict | None:
    sub = [r for r in rows if session is None or (r["open"] if session == "open" else not r["open"])]
    if len(sub) < 30:
        return None
    fit = ols([r[y] for r in sub], [[r[x]] for r in sub], nw_lags=3)
    xs, ys = [r[x] for r in sub], [r[y] for r in sub]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((v - mx) ** 2 for v in xs)
    syy = sum((v - my) ** 2 for v in ys)
    corr = sum((p - mx) * (q - my) for p, q in zip(xs, ys)) / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0
    return {"n": len(sub), "beta": fit["beta"][1], "t": fit["t"][1], "corr": corr}


def follow_rule(rows: list[dict], session: str = "closed", cost_rt: float = COST_RT,
                threshold: float = 0.001) -> dict:
    """Long (short) the US500 perp for the next hour when BTC's hourly
    return exceeds +threshold (-threshold), cash market closed only."""
    in_session = (lambda r: r["open"]) if session == "open" else (lambda r: not r["open"])
    pnl = []
    pos_prev = 0.0
    trades = 0
    for r in rows:
        # flat whenever the hour is outside the traded session (and after
        # any gap in the data), so every evening starts from zero
        if not in_session(r):
            if pos_prev:
                pnl.append(-abs(pos_prev) * cost_rt / 2)
            pos_prev = 0.0
            continue
        pos = 1.0 if r["ra"] > threshold else -1.0 if r["ra"] < -threshold else 0.0
        trades += pos != 0.0
        pnl.append(pos * r["rb_next"] - abs(pos - pos_prev) * cost_rt / 2)
        pos_prev = pos
    sub = [r for r in rows if in_session(r)]
    hrs = len(sub)
    sd = statistics.pstdev(pnl) if len(pnl) > 2 else 0.0
    return {"hours": hrs, "trades": trades, "mean_bp": statistics.fmean(pnl) * 1e4 if pnl else 0.0,
            "sharpe": statistics.fmean(pnl) / sd * math.sqrt(24 * 365) if sd > 0 else 0.0,
            "psr": S.psr(pnl) if hrs > 2 else 0.0, "total": sum(pnl)}


def run(btc: dict[int, float], us500: dict[int, float]) -> dict:
    rows = align(btc, us500)
    out = {"hours": len(rows), "enough": len(rows) >= MIN_HOURS,
           "first": dt.datetime.fromtimestamp(rows[0]["ts"], dt.timezone.utc).isoformat() if rows else None,
           "last": dt.datetime.fromtimestamp(rows[-1]["ts"], dt.timezone.utc).isoformat() if rows else None,
           "same_hour": {s: regress(rows, "ra", "rb", s) for s in ("open", "closed")},
           "btc_leads": {s: regress(rows, "ra", "rb_next", s) for s in ("open", "closed")},
           "us500_leads": {s: regress(rows, "rb", "ra_next", s) for s in ("open", "closed")},
           "follow_closed": follow_rule(rows, "closed"), "trials": 7}
    lead = out["btc_leads"]["closed"]
    f = out["follow_closed"]
    if not out["enough"]:
        out["verdict"] = ("collecting", f"{len(rows)} shared hours, {MIN_HOURS} needed")
    elif lead and abs(lead["t"]) >= 2.5 and lead["beta"] > 0 and f["mean_bp"] > 0 and f["psr"] >= 0.95:
        out["verdict"] = ("candidate", "BTC leads the US500 perp off-session and the follow rule is net positive")
    elif lead and abs(lead["t"]) >= 2.5:
        out["verdict"] = ("inconclusive", "a lead in the regression (sign %s) that the pre-registered follow rule does not keep after costs"
                          % ("+" if lead["beta"] > 0 else "-"))
    else:
        out["verdict"] = ("killed", "no off-session lead at |t| >= 2.5")
    return out


def render(res: dict) -> str:
    o = [f"shared consecutive hours: {res['hours']} ({res['first']} .. {res['last']}); need {MIN_HOURS}"]

    def fmt(r):
        return f"n {r['n']:4d}  beta {r['beta']:+.3f}  t {r['t']:+.2f}  corr {r['corr']:+.2f}" if r else "n/a"
    for key, label in (("same_hour", "same hour: US500 on BTC"), ("btc_leads", "BTC this hour -> US500 next hour"),
                       ("us500_leads", "US500 this hour -> BTC next hour")):
        o.append(f"  {label}")
        for s in ("open", "closed"):
            o.append(f"    cash {s:6s} {fmt(res[key][s])}")
    f = res["follow_closed"]
    o.append(f"  follow rule off-session (|BTC hourly| > 0.1%): {f['trades']} trades over {f['hours']} hours, "
             f"{f['mean_bp']:+.2f} bp/hour, Sharpe {f['sharpe']:+.2f}, PSR {f['psr']:.2f}, total {f['total']*100:+.2f}%")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    a = ap.parse_args(argv)
    d = a.state / "kalshi_hourly"
    res = run(read_closes(d / "KXBTCPERP.jsonl"), read_closes(d / "KXUS500PERP.jsonl"))
    print(render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
