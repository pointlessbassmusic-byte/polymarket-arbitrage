"""`kalshi-weather-forecast`: price Kalshi's daily high-temperature buckets
from the day-ahead public forecast and compare with the market.

Forecast: Open-Meteo's previous-runs API, `temperature_2m_previous_day1`
(the value each hour had in the forecast made one day earlier), at the
settlement station, maximum over the NWS climate day (midnight to
midnight local STANDARD time). Error model per city: Normal(forecast +
bias, sd), bias and sd from the settled maxima of earlier days only
(expanding window, 15 days of training per city before any scoring).
Integer degrees with a half-degree continuity correction:

  greater f  ->  T >= f + 1      less c  ->  T <= c - 1      between a-b  ->  a <= T <= b

Decisions: 20:00 ET the evening before and 10:00 ET on the day.

    python -m cryptobot.weather_study --scratch <dir> --fetch
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from .binary_tails_study import cluster_t, fee, load as load_binaries, quote_at

ET = ZoneInfo("America/New_York")
# series -> (station, lat, lon, standard UTC offset hours)
CITIES = {
    "KXHIGHNY": ("CLINYC Central Park", 40.7790, -73.9692, -5),
    "KXHIGHCHI": ("CLIMDW Midway", 41.7861, -87.7522, -6),
    "KXHIGHMIA": ("CLIMIA Miami Intl", 25.7881, -80.3169, -5),
    "KXHIGHAUS": ("CLIAUS Bergstrom", 30.1831, -97.6799, -6),
    "KXHIGHDEN": ("CLIDEN Denver Intl", 39.8466, -104.6562, -7),
    "KXHIGHLAX": ("CLILAX LAX", 33.9382, -118.3866, -8),
    "KXHIGHPHIL": ("CLIPHL Philadelphia Intl", 39.8733, -75.2268, -5),
    "KXHIGHTDC": ("CLIDCA Reagan National", 38.8483, -77.0342, -5),
    "KXHIGHTBOS": ("CLIBOS Logan", 42.3606, -71.0097, -5),
}
TRAIN = 15
MARGIN = 0.02
SD_FLOOR = 1.0


def fetch(scratch: Path, days: int = 75) -> dict:
    from .kalshi_binaries import collect
    out = {}
    for s in CITIES:
        out[s] = asyncio.run(collect(scratch / "weather" / "kalshi" / s, days=days, series=s, interval=60, pace_s=0.6))
    c = httpx.Client(timeout=60, headers={"User-Agent": "cryptobot-research/0.1"})
    start = (dt.date.today() - dt.timedelta(days=days + 5)).isoformat()
    fd = scratch / "weather" / "forecast"
    fd.mkdir(parents=True, exist_ok=True)
    for s, (_, lat, lon, _) in CITIES.items():
        params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m_previous_day1", "temperature_unit": "fahrenheit",
                  "start_date": start, "end_date": dt.date.today().isoformat(), "timezone": "GMT"}
        for attempt in range(6):
            try:
                r = c.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=params)
                r.raise_for_status()
                break
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == 5:
                    raise
                import time as _t
                _t.sleep(3 * (attempt + 1))
        (fd / f"{s}.json").write_text(r.text)
    return out


def daily_max(path: Path, std_offset: int) -> dict[str, float]:
    j = json.loads(path.read_text())
    h = j["hourly"]
    by: dict[str, list[float]] = defaultdict(list)
    for t, v in zip(h["time"], h["temperature_2m_previous_day1"]):
        if v is None:
            continue
        lst = dt.datetime.fromisoformat(t) + dt.timedelta(hours=std_offset)
        by[lst.date().isoformat()].append(float(v))
    return {d: max(v) for d, v in by.items() if len(v) >= 20}


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bucket_prob(m: dict, mu: float, sd: float) -> float | None:
    st = m.get("strike_type")
    if st == "greater" and m.get("floor") is not None:
        return 1 - phi((m["floor"] + 0.5 - mu) / sd)
    if st == "less" and m.get("cap") is not None:
        return phi((m["cap"] - 0.5 - mu) / sd)
    if st == "between" and m.get("floor") is not None and m.get("cap") is not None:
        return phi((m["cap"] + 0.5 - mu) / sd) - phi((m["floor"] - 0.5 - mu) / sd)
    return None


def event_day(m: dict) -> str:
    """The temperature day of a market: the date in its ticker, e.g. KXHIGHNY-26OCT13-..."""
    code = m["event"].split("-")[1]
    return dt.datetime.strptime(code, "%y%b%d").date().isoformat()


def decision_ts(day: str, which: str) -> int:
    d = dt.date.fromisoformat(day)
    if which == "eve":
        t = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(20, 0), ET)
    else:
        t = dt.datetime.combine(d, dt.time(10, 0), ET)
    return int(t.timestamp())


def run(scratch: Path) -> dict:
    res = {"cities": {}, "decisions": {}}
    pooled = {w: {"rows": []} for w in ("eve", "morning")}
    for s, (station, _, _, off) in CITIES.items():
        kd = scratch / "weather" / "kalshi" / s
        fp = scratch / "weather" / "forecast" / f"{s}.json"
        if not (kd / "kalshi_binaries" / "markets.jsonl").exists() or not fp.exists():
            continue
        markets, bars = load_binaries(kd)
        fc = daily_max(fp, off)
        actual = {}
        for m in markets:
            if m.get("settle") is not None:
                actual[event_day(m)] = float(m["settle"])
        days = sorted(d for d in actual if d in fc)
        errs = []
        bias_sd = {}
        for d in days:
            if len(errs) >= TRAIN:
                bias_sd[d] = (statistics.fmean(errs), max(SD_FLOOR, statistics.pstdev(errs)))
            errs.append(actual[d] - fc[d])
        res["cities"][s] = {"station": station, "days": len(days),
                            "fc_mae": statistics.fmean(abs(actual[d] - fc[d]) for d in days) if days else None,
                            "bias": statistics.fmean(actual[d] - fc[d] for d in days) if days else None}
        for m in markets:
            d = event_day(m)
            if d not in bias_sd or m.get("result") not in ("yes", "no"):
                continue
            bias, sd = bias_sd[d]
            p = bucket_prob(m, fc[d] + bias, sd)
            if p is None:
                continue
            y = 1.0 if m["result"] == "yes" else 0.0
            for w in ("eve", "morning"):
                q = quote_at(bars.get(m["ticker"], []), decision_ts(d, w), tolerance_s=3600)
                if q is None:
                    continue
                bid, ask, _, _ = q
                row = {"city": s, "day": d, "p": p, "mid": (bid + ask) / 2, "y": y, "net": None}
                if p - ask - fee(ask) - MARGIN > 0 and ask < 1:
                    row["net"] = (y - ask - fee(ask)) / ask
                    row["side"] = "yes"
                elif (1 - p) - (1 - bid) - fee(1 - bid) - MARGIN > 0 and bid > 0:
                    price = 1 - bid
                    row["net"] = ((1 - y) - price - fee(price)) / price
                    row["side"] = "no"
                pooled[w]["rows"].append(row)
    for w, d in pooled.items():
        rows = d["rows"]
        if not rows:
            res["decisions"][w] = {"quoted": 0}
            continue
        tr = [r for r in rows if r["net"] is not None]
        out = {"quoted": len(rows), "brier_model": statistics.fmean((r["p"] - r["y"]) ** 2 for r in rows),
               "brier_mid": statistics.fmean((r["mid"] - r["y"]) ** 2 for r in rows), "trades": len(tr)}
        if tr:
            nets = [r["net"] for r in tr]
            ds = sorted(r["day"] for r in tr)
            mid = ds[len(ds) // 2]
            out.update({"net": statistics.fmean(nets), "t": cluster_t(nets, [(r["city"], r["day"]) for r in tr]),
                        "hit": statistics.fmean(1.0 if x > 0 else 0.0 for x in nets),
                        "h1": statistics.fmean([r["net"] for r in tr if r["day"] < mid] or [0.0]),
                        "h2": statistics.fmean([r["net"] for r in tr if r["day"] >= mid] or [0.0]),
                        "yes_share": statistics.fmean(1.0 if r["side"] == "yes" else 0.0 for r in tr),
                        "city_days": len({(r["city"], r["day"]) for r in tr})})
        cal = defaultdict(list)
        for r in rows:
            cal[min(int(r["p"] * 10), 9)].append(r["y"])
        out["calibration"] = {k: (round(statistics.fmean(v), 2), len(v)) for k, v in sorted(cal.items())}
        res["decisions"][w] = out
    e = res["decisions"].get("eve", {})
    mo = res["decisions"].get("morning", {})
    if (e.get("trades", 0) >= 150 and e["brier_model"] < e["brier_mid"] and e["net"] >= 0.03 and e["t"] >= 2.5
            and e["h1"] > 0 and e["h2"] > 0):
        res["verdict"] = "candidate"
    elif e.get("quoted") and mo.get("quoted") and e["brier_mid"] < e["brier_model"] and mo["brier_mid"] < mo["brier_model"]:
        res["verdict"] = "killed"
    else:
        res["verdict"] = "inconclusive"
    return res


def render(res: dict) -> str:
    o = ["Kalshi daily highs vs the day-ahead Open-Meteo forecast (Normal error model from earlier settled days), fee 0.07 p(1-p), margin 2c"]
    for s, c in res["cities"].items():
        o.append(f"  {s:11s} {c['station']:26s} {c['days']:3d} days; forecast mean abs error {c['fc_mae'] or 0:.1f}F, bias {c['bias'] or 0:+.1f}F")
    for w, label in (("eve", "20:00 ET the evening before"), ("morning", "10:00 ET on the day")):
        d = res["decisions"].get(w, {})
        if not d.get("quoted"):
            o.append(f"  {label}: no quotes")
            continue
        line = f"  {label}: {d['quoted']} quoted buckets; Brier model {d['brier_model']:.4f} vs mid {d['brier_mid']:.4f}; trades {d['trades']}"
        if d["trades"]:
            line += (f" over {d['city_days']} city-days: net {d['net']:+.1%} per $ (t {d['t']:+.1f}, hit {d['hit']:.0%}, halves {d['h1']:+.1%}/{d['h2']:+.1%}, "
                     f"YES {d['yes_share']:.0%})")
        o.append(line)
        o.append("    calibration, model p decile -> realised (n): " + ", ".join(f"{k / 10:.1f}:{v[0]:.2f}({v[1]})" for k, v in d["calibration"].items()))
    o.append(f"verdict: {res['verdict']}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", type=Path, default=Path("."))
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch:
        print(json.dumps(fetch(a.scratch), default=str)[:2000], flush=True)
    res = run(a.scratch)
    print(render(res))
    (a.scratch / "weather_study.json").write_text(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
