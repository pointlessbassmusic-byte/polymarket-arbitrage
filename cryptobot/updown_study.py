"""Do the Polymarket "Up or Down" strategies from two X posts hold up?

Post 1 (@RetroValix on account "mo-money"): price each side with a
fair-value model (BTC vs its opening price, time left, volatility), buy
the side the market underprices, and buy the other side later if the
pair can be completed for under $1.
Post 2 (@Dan1ro0): pick the side with the larger directional index
(+DI vs -DI) when ADX > 25.

Neither post shows how its results came about, so each idea is tested
against what Polymarket actually quoted, net of its taker fee
(0.07 * p * (1 - p) per share; makers pay none). Every setting is chosen
on the first half of the markets and scored on the second half.

  calibration  is the market's own price a good probability?
  information  does the model or DMI add anything beyond the price?
               (logistic blend fitted on half 1, log loss on half 2)
  taker        buy the side the model says is cheap, at the quoted price
               plus half a cent of spread plus the fee
  hedge        the same entries, plus completing the pair when the other
               side gets cheap enough that both cost under $1
  maker        rest a bid below fair value; filled only if the price
               later trades through it (fills arrive when it moves
               against you, which is what makes maker P&L honest)
  dmi          the post-2 rule, bought at the quoted price

Run:  python -m cryptobot.updown_study --data updown_15m.pkl
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import statistics
from pathlib import Path
from typing import Optional

FEE_RATE = 0.07
HALF_SPREAD = 0.005
DECISION_MIN = (10, 5, 2)          # minutes before the end


def fee(p: float) -> float:
    return FEE_RATE * p * (1 - p)


def taker_cost(p: float) -> float:
    """All-in cost of one share quoted at p, bought as a taker."""
    q = min(0.999, p + HALF_SPREAD)
    return q + fee(q)


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


# ------------------------------------------------------------------ inputs

def quote_at(history: list, t: int, max_age: int = 150) -> Optional[tuple]:
    """(ts, price): the last history point at or before t."""
    best = None
    for ts, p in history:
        if ts <= t:
            best = (ts, p)
        else:
            break
    if best is None or t - best[0] > max_age or not 0 < best[1] < 1:
        return None
    return best


def price_at(history: list, t: int, max_age: int = 150) -> Optional[float]:
    q = quote_at(history, t, max_age)
    return q[1] if q else None


def quote_after(history: list, t: int, within: int = 120) -> Optional[tuple]:
    """(ts, price): the first history point strictly after t. This is the
    price to trade at: a signal formed at t cannot fill at an older quote."""
    for ts, p in history:
        if ts > t:
            return (ts, p) if ts - t <= within and 0 < p < 1 else None
    return None


def spot(candles: dict, t: int) -> Optional[float]:
    """BTC price at t: close of the 1-minute candle that ended at t."""
    c = candles.get(t - t % 60 - 60)
    return c[3] if c else None


def realized_vol(candles: dict, t: int, minutes: int = 60) -> Optional[float]:
    """Per-minute standard deviation of 1m log returns over the window."""
    base = t - t % 60
    closes = [candles.get(base - k * 60) for k in range(minutes + 1, 0, -1)]
    closes = [c[3] for c in closes if c]
    if len(closes) < minutes * 0.8:
        return None
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    return statistics.pstdev(rets) if len(rets) > 10 else None


def fair_value(s0: float, st: float, sigma: float, minutes_left: float) -> float:
    """P(end >= start) for a driftless random walk: Phi(ln(St/S0) / (sigma sqrt(tau)))."""
    if minutes_left <= 0:
        return 1.0 if st >= s0 else 0.0
    return phi(math.log(st / s0) / (max(sigma, 1e-6) * math.sqrt(minutes_left)))


def dmi(candles: dict, t: int, n: int = 14, warm: int = 60) -> Optional[tuple]:
    """(+DI, -DI, ADX) on 1-minute candles closed by time t, Wilder smoothing."""
    base = t - t % 60
    rows = [candles.get(base - k * 60) for k in range(warm + 2 * n, 0, -1)]
    rows = [r for r in rows if r]
    if len(rows) < 3 * n:
        return None
    tr_s = pdm_s = ndm_s = None
    dxs = []
    adx = None
    for prev, cur in zip(rows, rows[1:]):
        _, ph, pl, pc, _ = prev
        _, h, l, _, _ = cur
        up, dn = h - ph, pl - l
        pdm = up if up > dn and up > 0 else 0.0
        ndm = dn if dn > up and dn > 0 else 0.0
        tr = max(h - l, abs(h - pc), abs(l - pc))
        if tr_s is None:
            tr_s, pdm_s, ndm_s = tr, pdm, ndm
        else:
            tr_s = tr_s - tr_s / n + tr
            pdm_s = pdm_s - pdm_s / n + pdm
            ndm_s = ndm_s - ndm_s / n + ndm
        if tr_s <= 0:
            continue
        pdi, ndi = 100 * pdm_s / tr_s, 100 * ndm_s / tr_s
        dx = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi > 0 else 0.0
        dxs.append(dx)
        if len(dxs) == n:
            adx = statistics.mean(dxs)
        elif adx is not None:
            adx = (adx * (n - 1) + dx) / n
    if adx is None:
        return None
    return pdi, ndi, adx


# --------------------------------------------------------------- snapshots

def snapshots(data: dict, minutes_before: int) -> list[dict]:
    """One row per resolved market, built so the model never knows more
    than the market it is compared with:

      price / model_info   the last quote at or before the decision time,
                           and the model computed from BTC candles closed
                           by that QUOTE's timestamp (information test);
      model / entry        the model from BTC up to the decision time t,
                           traded at the first quote printed AFTER t
                           (trading tests).
    """
    candles = data["candles"].get("BTC-USD", {})
    out = []
    for m in sorted(data["markets"].values(), key=lambda m: m.start):
        if m.up_won is None or not m.history or m.history[0][0] < 0:
            continue
        t = m.end - minutes_before * 60
        q = quote_at(m.history, t)
        e = quote_after(m.history, t)
        s0 = candles.get(m.start)
        sig = realized_vol(candles, m.start)
        if q is None or e is None or s0 is None or sig is None:
            continue
        q_ts = q[0] - q[0] % 60
        s_q, s_t = spot(candles, q_ts), spot(candles, t)
        if s_q is None or s_t is None:
            continue
        out.append({
            "slug": m.slug, "start": m.start, "end": m.end, "t": t,
            "day": dt.datetime.utcfromtimestamp(m.start).strftime("%Y-%m-%d"),
            "price": q[1],
            "model_info": fair_value(s0[0], s_q, sig, (m.end - q_ts) / 60),
            "model": fair_value(s0[0], s_t, sig, minutes_before),
            "entry": e[1], "entry_ts": e[0],
            "dmi": dmi(candles, q_ts), "up": 1 if m.up_won else 0, "history": m.history,
        })
    return out


def halves(rows: list) -> tuple[list, list]:
    k = len(rows) // 2
    return rows[:k], rows[k:]


# ---------------------------------------------------------------- analyses

def calibration(rows: list, bins=(0, .1, .3, .5, .7, .9, 1.0001)) -> list[tuple]:
    out = []
    for lo, hi in zip(bins, bins[1:]):
        g = [r for r in rows if lo <= r["price"] < hi]
        if g:
            out.append((lo, hi, len(g), statistics.mean(r["price"] for r in g),
                        statistics.mean(r["up"] for r in g)))
    return out


def logloss(ps, ys) -> float:
    return -statistics.mean(y * math.log(min(max(p, 1e-6), 1 - 1e-6))
                            + (1 - y) * math.log(min(max(1 - p, 1e-6), 1 - 1e-6))
                            for p, y in zip(ps, ys))


def fit_logistic(X: list[list[float]], y: list[int], steps: int = 3000, lr: float = 0.05):
    """Plain gradient-descent logistic regression with intercept."""
    w = [0.0] * (len(X[0]) + 1)
    n = len(y)
    for _ in range(steps):
        g = [0.0] * len(w)
        for xi, yi in zip(X, y):
            z = w[0] + sum(a * b for a, b in zip(w[1:], xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            g[0] += e
            for j, v in enumerate(xi):
                g[j + 1] += e * v
        w = [wi - lr * gi / n for wi, gi in zip(w, g)]
    return w


def predict(w, X):
    return [1 / (1 + math.exp(-max(-30, min(30, w[0] + sum(a * b for a, b in zip(w[1:], x))))))
            for x in X]


def information(rows: list) -> dict:
    """Out-of-sample log loss: market alone vs market + model vs market + DMI."""
    tr, te = halves([r for r in rows if r["dmi"]])
    y_tr, y_te = [r["up"] for r in tr], [r["up"] for r in te]

    def feats(r, kind):
        f = [logit(r["price"])]
        if kind in ("model", "both"):
            f.append(logit(r["model_info"]))
        if kind in ("dmi", "both"):
            pdi, ndi, adx = r["dmi"]
            f.append((pdi - ndi) / 100 * (adx / 25))
        return f
    out = {"n_test": len(te), "market_raw": logloss([r["price"] for r in te], y_te)}
    for kind in ("market", "model", "dmi", "both"):
        w = fit_logistic([feats(r, kind) for r in tr], y_tr)
        out[kind] = logloss(predict(w, [feats(r, kind) for r in te]), y_te)
        out[kind + "_w"] = w
    return out


def taker_trades(rows: list, edge: float) -> list[dict]:
    """Buy the side whose model value exceeds its all-in cost by `edge`."""
    out = []
    for r in rows:
        cu, cd = taker_cost(r["entry"]), taker_cost(1 - r["entry"])
        vu, vd = r["model"] - cu, (1 - r["model"]) - cd
        if max(vu, vd) < edge:
            continue
        side_up = vu >= vd
        cost = cu if side_up else cd
        payoff = r["up"] if side_up else 1 - r["up"]
        out.append({**r, "side_up": side_up, "cost": cost, "pnl": payoff - cost})
    return out


def with_hedge(trades: list[dict]) -> list[dict]:
    """Post-1 overlay: after entry, buy the other side the first time the
    pair's all-in cost drops below $1, locking 1 - total for that pair."""
    out = []
    for tr in trades:
        locked = None
        for ts, p_up in tr["history"]:
            if ts <= tr["entry_ts"] or ts >= tr["end"]:
                continue
            other = (1 - p_up) if tr["side_up"] else p_up
            c2 = taker_cost(other)
            if tr["cost"] + c2 < 1.0:
                locked = 1.0 - tr["cost"] - c2
                break
        if locked is None:
            out.append({**tr, "locked": False})
        else:
            # two shares bought, one pays $1 for sure; return per $ of the first leg
            out.append({**tr, "locked": True, "pnl": locked})
    return out


def maker_trades(rows: list, margin: float, wait_min: int = 3) -> list[dict]:
    """Rest a bid at (model - margin) on the cheaper-than-model side.
    Filled only if that side's quoted price later trades at or below the
    bid within `wait_min` minutes, before the end. No fee for makers."""
    out = []
    for r in rows:
        for side_up in (True, False):
            fair = r["model"] if side_up else 1 - r["model"]
            quoted = r["entry"] if side_up else 1 - r["entry"]
            bid = fair - margin
            if bid <= 0.02 or bid >= quoted:      # only bid below the market
                continue
            filled = False
            for ts, p_up in r["history"]:
                if ts <= r["entry_ts"] or ts > min(r["t"] + wait_min * 60, r["end"] - 30):
                    continue
                if (p_up if side_up else 1 - p_up) <= bid:
                    filled = True
                    break
            if filled:
                payoff = r["up"] if side_up else 1 - r["up"]
                out.append({**r, "side_up": side_up, "cost": bid, "pnl": payoff - bid})
    return out


def dmi_trades(rows: list, adx_min: float = 25.0) -> list[dict]:
    out = []
    for r in rows:
        if not r["dmi"]:
            continue
        pdi, ndi, adx = r["dmi"]
        if adx < adx_min or pdi == ndi:
            continue
        side_up = pdi > ndi
        cost = taker_cost(r["entry"] if side_up else 1 - r["entry"])
        payoff = r["up"] if side_up else 1 - r["up"]
        out.append({**r, "side_up": side_up, "cost": cost, "pnl": payoff - cost,
                    "hit": payoff})
    return out


def summary(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0}
    pnl = [t["pnl"] for t in trades]
    cost = [t["cost"] for t in trades]
    by_day: dict[str, float] = {}
    for t in trades:
        by_day[t["day"]] = by_day.get(t["day"], 0.0) + t["pnl"]
    days = list(by_day.values())
    sd = statistics.pstdev(pnl) if len(pnl) > 1 else 0.0
    return {"n": len(pnl), "per_share": statistics.mean(pnl),
            "per_dollar": sum(pnl) / sum(cost), "t": statistics.mean(pnl) / (sd / math.sqrt(len(pnl))) if sd else 0.0,
            "win": statistics.mean(1 if p > 0 else 0 for p in pnl),
            "days": len(days), "days_up": sum(d > 0 for d in days),
            "daily_sd": statistics.pstdev(days) if len(days) > 1 else 0.0}


def fmt(s: dict) -> str:
    if not s.get("n"):
        return "no trades"
    return (f"n={s['n']:4d}  {100 * s['per_dollar']:+6.2f}% per $  t={s['t']:+5.2f}  "
            f"win {100 * s['win']:3.0f}%  days up {s['days_up']}/{s['days']}")


def choose(rows_tr, rows_te, make, grid):
    """Pick the grid value with the best per-$ return on half 1 (min 30
    trades), score it on half 2."""
    best = None
    for g in grid:
        s = summary(make(rows_tr, g))
        if s.get("n", 0) >= 30 and (best is None or s["per_dollar"] > best[1]["per_dollar"]):
            best = (g, s)
    if best is None:
        return None, None, None
    return best[0], best[1], summary(make(rows_te, best[0]))


def report(data: dict) -> str:
    ms = [m for m in data["markets"].values() if m.up_won is not None]
    out = [f"{len(ms)} resolved markets, "
           f"{dt.datetime.utcfromtimestamp(min(m.start for m in ms)):%Y-%m-%d} .. "
           f"{dt.datetime.utcfromtimestamp(max(m.end for m in ms)):%Y-%m-%d}; "
           f"Up won {100 * statistics.mean(m.up_won for m in ms):.1f}%; "
           f"taker fee 0.07*p*(1-p) + {HALF_SPREAD * 100:.1f}c spread"]
    for mins in DECISION_MIN:
        rows = snapshots(data, mins)
        if len(rows) < 100:
            out.append(f"\n{mins} min before end: only {len(rows)} usable markets")
            continue
        tr, te = halves(rows)
        out.append(f"\n===== decision {mins} min before the end: {len(rows)} markets "
                   f"(choose on {tr[0]['day']}..{tr[-1]['day']}, test on {te[0]['day']}..{te[-1]['day']})")
        out.append("calibration of the market price (all markets):")
        for lo, hi, n, mp, freq in calibration(rows):
            out.append(f"  price {lo:.1f}-{min(hi, 1):.1f}: n={n:4d}  avg price {mp:.3f}  Up won {freq:.3f}")
        inf = information(rows)
        out.append(f"out-of-sample log loss on {inf['n_test']} markets (lower is better):")
        out.append(f"  raw market {inf['market_raw']:.4f} | market refit {inf['market']:.4f} | "
                   f"+model {inf['model']:.4f} | +DMI {inf['dmi']:.4f} | +both {inf['both']:.4f}")
        out.append(f"  weights (+model): {[round(x, 2) for x in inf['model_w']]}  "
                   f"(+DMI): {[round(x, 2) for x in inf['dmi_w']]}")
        g, s_tr, s_te = choose(tr, te, taker_trades, (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15))
        out.append(f"taker on model edge (edge >= {g}):")
        out.append(f"  chosen half: {fmt(s_tr) if s_tr else '-'}")
        out.append(f"  test half:   {fmt(s_te) if s_te else '-'}")
        if g is not None:
            h_tr, h_te = summary(with_hedge(taker_trades(tr, g))), summary(with_hedge(taker_trades(te, g)))
            locked = with_hedge(taker_trades(te, g))
            out.append(f"  + hedge-to-lock, test half: {fmt(h_te)}  "
                       f"(pairs locked {sum(t['locked'] for t in locked)}/{len(locked)})")
        g, s_tr, s_te = choose(tr, te, maker_trades, (0.0, 0.02, 0.04, 0.06, 0.08, 0.10))
        out.append(f"maker bid at model - {g}:")
        out.append(f"  chosen half: {fmt(s_tr) if s_tr else '-'}")
        out.append(f"  test half:   {fmt(s_te) if s_te else '-'}")
        d_tr, d_te = summary(dmi_trades(tr)), summary(dmi_trades(te))
        hit = [t["hit"] for t in dmi_trades(rows)]
        out.append(f"DMI/ADX>25 rule (fixed, as posted): hit rate {100 * statistics.mean(hit):.1f}% "
                   f"on {len(hit)} signals" if hit else "DMI: no signals")
        out.append(f"  half 1: {fmt(d_tr)}")
        out.append(f"  half 2: {fmt(d_te)}")
    return "\n".join(out)


def near_resolution(data: dict, minutes_before: int, min_price: float = 0.85) -> dict:
    """Pre-registered `near-resolution-capture`: in the last minutes buy
    the favourite as a taker (UP at its quote, or DOWN at 1 - quote) when
    it trades at `min_price` or above, hold to settlement. Net per dollar
    after the taker fee and half-spread, hit rate, and the price bucket."""
    rows = snapshots(data, minutes_before)
    trades = []
    for r in rows:
        p_up = r["entry"]
        if p_up >= min_price:
            cost, win = taker_cost(p_up), r["up"]
        elif p_up <= 1 - min_price:
            cost, win = taker_cost(1 - p_up), 1 - r["up"]
        else:
            continue
        trades.append({"day": r["day"], "price": max(p_up, 1 - p_up), "cost": cost, "win": win,
                       "net": (win - cost) / cost})
    out = {"minutes_before": minutes_before, "n": len(trades), "markets": len(rows)}
    if trades:
        nets = [t["net"] for t in trades]
        m = statistics.mean(nets)
        sd = statistics.stdev(nets) if len(nets) > 1 else 0.0
        days = len({t["day"] for t in trades})
        out.update({"hit": sum(t["win"] for t in trades) / len(trades), "mean_net": m,
                    "t": (m / sd * math.sqrt(days)) if sd else 0.0,
                    "implied": statistics.mean(t["price"] for t in trades)})
        buckets = {}
        for t in trades:
            b = round(min(0.99, t["price"]) * 20) / 20
            buckets.setdefault(b, []).append(t)
        out["buckets"] = {b: {"n": len(g), "hit": sum(x["win"] for x in g) / len(g),
                              "mean_net": statistics.mean(x["net"] for x in g)} for b, g in sorted(buckets.items())}
    return out


def render_near_resolution(res: dict) -> str:
    if not res.get("n"):
        return f"{res['minutes_before']} min before: no favourite at or above the threshold in {res['markets']} markets"
    out = [f"{res['minutes_before']} min before resolution: {res['n']} favourites bought of {res['markets']} markets; "
           f"implied {100 * res['implied']:.1f}% vs hit {100 * res['hit']:.1f}%; net {100 * res['mean_net']:+.2f}% per $ "
           f"(t={res['t']:+.2f}, days clustered)"]
    for b, g in res["buckets"].items():
        out.append(f"   price ~{b:.2f}: n={g['n']:4d} hit {100 * g['hit']:5.1f}% net {100 * g['mean_net']:+.2f}%")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--near-resolution", action="store_true",
                    help="pre-registered test: buy the favourite in the last 2 and 1 minutes")
    args = ap.parse_args()
    from cryptobot.updown_data import load
    data = load(args.data)
    if args.near_resolution:
        for mb in (2, 1):
            print(render_near_resolution(near_resolution(data, mb)))
        return 0
    print(report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
