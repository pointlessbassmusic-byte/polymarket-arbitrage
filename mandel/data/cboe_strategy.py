"""
Cboe options strategy benchmark indices: traded-price histories of buy-write, put-write, collar, condor, butterfly,
protective-put, risk-reversal, VIX-strategy and target-outcome overlays, plus VRO (the VIX settlement value).
================================================================================================================

Source (no key, verified 2026-10-15): ``https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv``.
It answers with a 307 to ``cdn-api.cboe.com`` (same path), so redirects are followed. A symbol with no file answers
403 (S3 AccessDenied), not 404. Each file is the whole history, ``DATE,<SYM>`` (one level per day) or
``DATE,OPEN,HIGH,LOW,CLOSE`` (SPRO, SPEN, SPAI, SPATI, LOVOL), dates as MM/DD/YYYY. Index list and dashboards:
https://www.cboe.com/us/indices/benchmark_indices/ (each index: https://www.cboe.com/us/indices/dashboard/<SYM>/,
which links the methodology PDF recorded in ``INDEX_META``).

Coverage on 2026-10-15 (every file ends 2026-10-14):
  1986-06: BXMD, CLLZ, CNDR, BFLY, RXM (06-20); PUTY, CMBO, PPUT, SMILE (06-30).   1988-06: BXY.
  1990-01: BXMC, BXMH.   1994-12: BXNT.   1997-10: BXD, BXDE.   2000-12: BXR.   2001-01: BXRD, PUTR, CLLR.
  2002-03: BXM (the free file starts 2002-03-22 although Cboe's own history starts 1986).   2004: BXRC, PPUT3M.
  2005: BXNH, BXLB, BXTB, PTLT, SPEN, SPRO, SPENME, SPROME, SVRPO.   2006: PUTD, WPUT, CALD, VXTH, LOVOL, SPAI, SPATI, BXRH.
  2006-12: RPEN, RPRO.   2007: VPD (11-16), BXHB.   2008: VRO (07-16), VPN, CLL (08-26), GLDBUF, GLDTI.   2009: BXN (09-18),
  GLDPRO.   2011: WPTR.   2012: BXMW.   2013: BXDEH.   2018: SPDVDCC.   2021: BXGBTCA, BXGBTCT.   2024: RTYDCC, RTYDBI.
  PUT has only seven rows before 2007-01-03 (1991, 1991, 1994, 1997, 1997, 2001, 2004): daily from 2007 only.
  No file (403): PUTW (a WisdomTree ETF, not a Cboe index), BXMT, BXND, BXK, PUTN, VXO, VIXTLT, TAIL and the *RUT variants.

Point in time. Every index here is disseminated every 15 seconds and closes at 4:00-4:31 pm ET (methodology section 4),
so a close is public that evening: ``available_at`` = 19:00 America/New_York on the index date. The CDN file itself was
rewritten between 22:31 UTC the same day and 07:30 UTC the next morning (Last-Modified on 2026-10-15), which is the
fallback channel and is later than the feed. Values before an index's launch date are back-tested (each methodology
says so); they were not knowable until launch, so those rows carry ``backtest: true`` and ``available_at`` = 19:00 ET on
the launch date. ``available_at`` is never later than ``observed_at`` (the fetch time). VRO is an actual settlement value
(the VIX special opening quotation), never back-tested. VRO rows are monthly to 2014, weekly from 2015, and in
2017-2020 the file repeats each settlement on every business day until the next one; those rows get ``carried: true``.

Data defects found on 2026-10-15 and kept as published (rows carry ``flag``): BXY 2013-03-11 is a one-day bad print
(937.94 between 1260.26 and 1262.11); CLL steps down 19.8% on 2009-10-16 while SPX fell 0.8%; WPTR steps down 15.8% on
2024-09-06 and 16.9% on 2025-01-31 while PUTR moved -0.9% and -0.4%. SPAI 2021-11-05 has blank open/high/low.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, time as dtime, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import httpx

from mandel.data.fetch import Throttle, now_iso

UA = {"User-Agent": "mandel-substrate research bot (contact: https://github.com/pointlessbassmusic-byte/polymarket-arbitrage/issues)"}
CDN = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
DASHBOARD = "https://www.cboe.com/us/indices/dashboard/{sym}/"
BENCHMARKS = "https://www.cboe.com/us/indices/benchmark_indices/"
GOV = "https://cdn-api.cboe.com/api/global/us_indices/governance/"
NY = ZoneInfo("America/New_York")
PUBLISH_ET = dtime(19, 0)          # evening of the index date: dissemination ends 4:15-4:31 pm ET
RETRY_STATUS = (429, 500, 502, 503, 504)

_BW = GOV + "Cboe_BuyWrite_Indices_Methodology.pdf"
_CBW = GOV + "Cboe_Conditional_BuyWrite_Indices_Methodology.pdf"
_HBW = GOV + "Cboe_Half_Buywrite_Indices_Methodology.pdf"
_NBW = GOV + "Cboe_NASDAQ_BuyWrite_Indices_Methodology.pdf"
_PW = GOV + "Cboe_PutWrite_Indices_Methodology.pdf"
_SPW = GOV + "Cboe_SP_500_PutWrite_Indices_Methodology.pdf"
_PP = GOV + "Cboe_SP_500_Put_Protection_Indices_Methodology.pdf"
_ZC = GOV + "Cboe_Zero-Cost_Put_Spread_Collar_Indices_Methodology.pdf"
_EG = GOV + "Cboe_Enhanced_Growth_Indices_Methodology.pdf"
_BP = GOV + "Cboe_Buffer_Protect_Indices_Methodology.pdf"
_GBTC = GOV + "Cboe_GBTC_BuyWrite_Indices_Methodology.pdf"

# sym: (name, family, underlying, launch date (None = not stated in any source we read), methodology URL, theories)
# Launch dates are from each methodology's "Index Information" table, except BXM ("April, 2002": month end used),
# CLLR ("2016": year end used) and SPATI (dashboard: "launched on March 2, 2018").
_META = {
    "BXM": ("Cboe S&P 500 BuyWrite Index", "buywrite", "SPX", "2002-04-30", _BW,
            ["T-54", "T-161", "T-162", "T-163", "T-164", "T-170", "T-171", "T-180", "T-202", "T-527"]),
    "BXMD": ("Cboe S&P 500 30-Delta BuyWrite Index", "buywrite", "SPX", "2015-08-03", _BW, ["T-54", "T-161", "T-162", "T-180"]),
    "BXY": ("Cboe S&P 500 2% OTM BuyWrite Index", "buywrite", "SPX", "2006-03-20", _BW, ["T-54", "T-161", "T-162", "T-172", "T-180"]),
    "BXMC": ("Cboe S&P 500 Conditional BuyWrite Index", "buywrite", "SPX", "2015-08-03", _CBW, ["T-161", "T-164"]),
    "BXMW": ("Cboe S&P 500 Multi-Week BuyWrite Index", "buywrite", "SPX", "2015-08-03", GOV + "BXMW_Methodology.pdf", ["T-161", "T-163", "T-180"]),
    "BXMH": ("Cboe S&P 500 Half BuyWrite Index", "buywrite", "SPX", "2020-09-08", _HBW, ["T-161", "T-164", "T-180"]),
    "CALD": ("Cboe Validus S&P 500 Dynamic Call BuyWrite Index", "buywrite", "SPX", "2022-07-25",
             GOV + "Cboe_Validus_Dynamic_Call_BuyWrite_Indices_Methodology.pdf", []),
    "SPDVDCC": ("Cboe S&P 500 Volatility Contingent Daily Covered Call Index", "buywrite", "SPX", "2024-10-25",
                GOV + "Cboe_Volatility_Contingent_Daily_Covered_Call_Indices_Methodology.pdf", []),
    "BXR": ("Cboe Russell 2000 BuyWrite Index", "buywrite", "RUT", "2004-06-18", _BW, ["T-161", "T-180"]),
    "BXRC": ("Cboe Russell 2000 Conditional BuyWrite Index", "buywrite", "RUT", "2015-11-23", _CBW, []),
    "BXRD": ("Cboe Russell 2000 30-Delta BuyWrite Index", "buywrite", "RUT", "2015-11-23", _BW, []),
    "BXRH": ("Cboe Russell 2000 Half BuyWrite Index", "buywrite", "RUT", "2022-09-28", _HBW, []),
    "RTYDCC": ("Cboe Russell 2000 Daily Covered Call Index", "buywrite", "RUT", "2024-08-27", GOV + "Cboe_Daily_BuyWrite_Indices_Methodology.pdf", []),
    "BXD": ("Cboe DJIA BuyWrite Index", "buywrite", "DJX", "2005-01-31", _BW, []),
    "BXDE": ("DJIA Cboe BuyWrite V2 Index", "buywrite", "DJX", "2022-04-02", _BW, []),
    "BXDEH": ("Cboe DJIA Half BuyWrite Index", "buywrite", "DJX", "2023-07-21", GOV + "Cboe_DJIA_Half_BuyWrite_Index_Methodology.pdf", []),
    "BXN": ("Cboe NASDAQ-100 BuyWrite Index", "buywrite", "NDX", "2005-09-09", _NBW, ["T-161", "T-180"]),
    "BXNT": ("Cboe NASDAQ-100 BuyWrite V2 Index", "buywrite", "NDX", "2015-06-22", _NBW, []),
    "BXNH": ("Cboe NASDAQ-100 Half BuyWrite V2 Index", "buywrite", "NDX", "2015-06-22", _NBW, []),
    "BXHB": ("Cboe HYG BuyWrite Index", "buywrite", "HYG", "2022-05-31", GOV + "BXHB_Methodology.pdf", []),
    "BXLB": ("Cboe LQD BuyWrite Index", "buywrite", "LQD", "2022-05-31", GOV + "BXLB_Methodology.pdf", []),
    "BXTB": ("Cboe TLT 2% OTM BuyWrite Index", "buywrite", "TLT", "2022-05-31", GOV + "BXTB_Methodology.pdf", []),
    "BXGBTCA": ("Cboe GBTC ATM BuyWrite Index", "buywrite", "GBTC", "2025-02-25", _GBTC, ["T-253"]),
    "BXGBTCT": ("Cboe GBTC 20% OTM BuyWrite Index", "buywrite", "GBTC", "2025-02-25", _GBTC, ["T-253"]),
    "PUT": ("Cboe S&P 500 PutWrite Index", "putwrite", "SPX", "2007-06-20", _SPW, ["T-55", "T-128", "T-170", "T-171", "T-180", "T-202"]),
    "PUTY": ("Cboe S&P 500 2% OTM PutWrite Index", "putwrite", "SPX", "2019-02-15", _PW, ["T-55", "T-170"]),
    "WPUT": ("Cboe S&P 500 One-Week PutWrite Index", "putwrite", "SPX", "2015-08-03", _PW, ["T-170"]),
    "PUTD": ("Cboe Validus S&P 500 Dynamic PutWrite Index", "putwrite", "SPX", "2022-07-25",
             GOV + "Cboe_Validus_Dynamic_PutWrite_Indices_Methodology.pdf", ["T-170"]),
    "PUTR": ("Cboe Russell 2000 PutWrite Index", "putwrite", "RUT", "2015-11-23", _PW, []),
    "WPTR": ("Cboe Russell 2000 One-Week PutWrite Index", "putwrite", "RUT", "2015-11-23", _PW, []),
    "PTLT": ("Cboe 20+ Year Treasury Bond PutWrite Index", "putwrite", "TLT", "2021-03-31", _PW, []),
    "CMBO": ("Cboe S&P 500 Covered Combo Index", "combo", "SPX", "2015-08-03", GOV + "CMBO_Methodology.pdf", ["T-172", "T-180"]),
    "BFLY": ("Cboe S&P 500 Iron Butterfly Index", "butterfly", "SPX", "2015-08-03", GOV + "BFLY_Methodology.pdf",
             ["T-57", "T-104", "T-105", "T-106", "T-107", "T-178", "T-180"]),
    "CNDR": ("Cboe S&P 500 Iron Condor Index", "condor", "SPX", "2015-08-03", GOV + "CNDR_Methodology.pdf",
             ["T-103", "T-109", "T-110", "T-178", "T-179", "T-180"]),
    "CLL": ("Cboe S&P 500 95-110 Collar Index", "collar", "SPX", None, GOV + "CLL_Methodology.pdf", ["T-56", "T-166", "T-180"]),
    "CLLZ": ("Cboe S&P 500 Zero-Cost Put Spread Collar Index", "collar", "SPX", "2015-08-03", _ZC, ["T-56", "T-166", "T-168", "T-180"]),
    "CLLR": ("Cboe Russell 2000 Zero-Cost Put Spread Collar Index", "collar", "RUT", "2016-12-31", _ZC, []),
    "PPUT": ("Cboe S&P 500 5% Put Protection Index", "put-protection", "SPX", "2015-08-03", _PP, ["T-169", "T-180"]),
    "PPUT3M": ("Cboe S&P 500 Tail Risk Index", "put-protection", "SPX", "2021-08-02", _PP, ["T-169", "T-528"]),
    "RXM": ("Cboe S&P 500 Risk Reversal Index", "risk-reversal", "SPX", "2015-12-30", GOV + "RXM_Methodology.pdf", ["T-138"]),
    "VXTH": ("Cboe VIX Tail Hedge Index", "vix-strategy", "SPX+VIX", "2011-07-29", GOV + "Cboe_VIX_Tail_Hedge_Index_Methodology.pdf", ["T-239", "T-528"]),
    "VPD": ("Cboe VIX Premium Strategy Index", "vix-strategy", "VX", "2007-11-16", GOV + "VPD_Methodology.pdf", ["T-242"]),
    "VPN": ("Cboe Capped VIX Premium Strategy Index", "vix-strategy", "VX", "2008-06-04", GOV + "VPN_Methodology.pdf", ["T-242"]),
    "LOVOL": ("Cboe Low Volatility Index (40% BXM / 60% VXTH)", "vix-strategy", "SPX+VIX", "2012-11-30",
              GOV + "Cboe_Low_Volatility_Index_Methodology.pdf", []),
    "SMILE": ("Cboe S&P 500 SMILE Index", "vol-premium", "SPX", "2016-10-25", GOV + "SMILE_Methodology.pdf", ["T-103"]),
    "SVRPO": ("Cboe S&P 500 Market-Neutral Volatility Risk Premia Index", "vol-premium", "SPX", None, None, []),
    "SPEN": ("Cboe S&P 500 Enhanced Growth Index Series", "target-outcome", "SPX", "2016-06-24", _EG, []),
    "SPENME": ("Cboe S&P 500 Enhanced Growth Month-End Balanced Series", "target-outcome", "SPX", "2020-07-31", _EG, []),
    "SPRO": ("Cboe S&P 500 Buffer Protect Index Series", "target-outcome", "SPX", "2016-03-30", _BP, []),
    "SPROME": ("Cboe S&P 500 Buffer Protect Index Balanced Series (month end)", "target-outcome", "SPX", "2020-07-31", _BP, []),
    "RPEN": ("Cboe Russell 2000 Enhanced Growth Balanced Series", "target-outcome", "RUT", "2020-07-31", _EG, []),
    "RPRO": ("Cboe Russell 2000 Buffer Protect Index Balanced Series", "target-outcome", "RUT", "2020-07-31", _BP, []),
    "RTYDBI": ("Cboe Russell 2000 Daily Buffer Index", "target-outcome", "RUT", "2025-05-27", GOV + "Cboe-Russell-Daily-Buffer-Indices-Methodology.pdf", []),
    "GLDBUF": ("Cboe Gold 10% (-5% to -15%) Buffer Protect Index", "target-outcome", "GLD", "2021-04-26", GOV + "GLDBUF_Methodology.pdf", []),
    "GLDPRO": ("Cboe Gold 10% Buffer Protect Index Balanced Series", "target-outcome", "GLD", "2021-03-31", _BP, []),
    "GLDTI": ("Cboe Gold Target Income Index Monthly Series", "target-outcome", "GLD", "2021-04-16", GOV + "GLDTI_Methodology.pdf", ["T-270"]),
    "SPAI": ("Cboe S&P 500 Dividend Aristocrats Target Income Index", "target-outcome", "SPDAUDT", None, None, []),
    "SPATI": ("Cboe S&P 500 Dividend Aristocrats Target Income Index Monthly Series", "target-outcome", "SPDAUDT", "2018-03-02", None, []),
    "VRO": ("VIX settlement value (special opening quotation)", "settlement", "VIX", None, None, ["T-220"]),
}
INDEX_META: dict[str, dict] = {s: {"name": n, "family": f, "underlying": u, "launch": l, "methodology": m, "theories": t,
                                   "dashboard": DASHBOARD.format(sym=s), "history": CDN.format(sym=s)}
                               for s, (n, f, u, l, m, t) in _META.items()}
STRATEGY_INDICES = list(INDEX_META)

# How each index stands in for the traded-price version of a theory's structure (model-priced in the registry).
THEORY_NOTES = {
    "T-54": "BXMD is the traded 30-delta SPX buy-write (monthly 3rd-Friday roll); BXM (ATM) and BXY (2% OTM) are the other strike arms",
    "T-55": "PUT is the traded ATM monthly SPX put-write on T-bill collateral; PUTY (2% OTM) and WPUT (weekly) are arms",
    "T-56": "CLL (long 5% OTM put, short 10% OTM call) is the traded collar; CLLZ (zero-cost put-spread collar) is a variant",
    "T-57": "BFLY = short ATM SPX straddle with 5% wings over T-bills: the straddle VRP with capped tails",
    "T-103": "CNDR = short ~20-delta strangle with ~5-delta wings; SMILE = short 25-delta put with a put/call-ratio-sized call",
    "T-104": "BFLY has the long-butterfly payoff shape (short body, long wings) up to financing",
    "T-105": "short butterfly = minus BFLY",
    "T-106": "BFLY is the sold SPX iron butterfly (ATM body, 5% wings)",
    "T-107": "reverse iron butterfly = minus BFLY",
    "T-109": "CNDR is the sold SPX iron condor (strikes by delta, not +/-5%/8%)",
    "T-110": "reverse iron condor = minus CNDR",
    "T-128": "PUT is the claim's own benchmark check",
    "T-138": "RXM = long 25-delta call, short 25-delta put, monthly (claim uses 5% OTM legs)",
    "T-161": "BXM excess returns vs SPY TR; BXMD/BXY/BXMW/BXMH/BXMC/BXN/BXR named as further arms",
    "T-162": "BXMD vs BXM (BXY as the third arm)", "T-163": "BXMW vs BXM", "T-164": "BXMH vs BXM (BXMC as reference)",
    "T-166": "CLL vs beta-matched SPY TR / T-bill blend", "T-168": "CLLZ Sharpe vs SPY TR", "T-169": "PPUT (PPUT3M secondary)",
    "T-170": "PUT vs BXM; PUTY, WPUT, PUTD secondary arms", "T-171": "BXM and PUT are the calibration gate", "T-172": "CMBO vs BXY",
    "T-178": "BFLY vs CNDR", "T-179": "CNDR roll-date returns vs VIX - realised vol", "T-180": "the replication targets themselves",
    "T-202": "PUT vs BXM over the common history", "T-220": "VRO is the settlement print (SOQ) the trade settles at",
    "T-239": "VXTH is a traded VIX-call overlay on SPX TR (budget rule differs)",
    "T-242": "VPD/VPN are short front VIX futures over T-bills: the traded side of the VIX futures premium",
    "T-253": "BXGBTCA/BXGBTCT are traded GBTC covered calls (ATM / 20% OTM) from 2021-11",
    "T-270": "GLDTI is a traded GLD buy-write (target-income strike rule, not 30-delta)",
    "T-527": "BXM is the calibration gate", "T-528": "VXTH vs PPUT3M and SPY TR drawdowns",
}

# Defects verified on 2026-10-15 against neighbouring indices; values are kept as published, rows are flagged.
KNOWN_ISSUES = {
    "BXY": {"2013-03-11": "one-day bad print (937.94 between 1260.26 and 1262.11)"},
    "CLL": {"2009-10-16": "level step -19.8% while SPX fell 0.8%: splice in the free file; do not compound returns across it"},
    "WPTR": {"2024-09-06": "level step -15.8% while PUTR fell 0.9%", "2025-01-31": "level step -16.9% while PUTR fell 0.4%"},
}


def _client() -> httpx.Client:
    return httpx.Client(headers=UA, timeout=90, follow_redirects=True)


def history_url(sym: str) -> str:
    return CDN.format(sym=sym)


def theories_for(sym: str) -> list[str]:
    return list(INDEX_META.get(sym, {}).get("theories", []))


def indices_for(theory: str) -> list[str]:
    return [s for s, m in INDEX_META.items() if theory in m["theories"]]


# ------------------------------------------------------------------ parsing --

def _day(s: str) -> str:
    return datetime.strptime(s.strip(), "%m/%d/%Y").date().isoformat()


def _num(s) -> Optional[float]:
    try:
        return float(s) if s is not None and str(s).strip() != "" else None
    except ValueError:
        return None


def parse_history(text: str, sym: str) -> list[dict]:
    """Rows {day, close} or {day, open?, high?, low?, close}, sorted by day, one per day (the last wins). A row without a
    parseable date or close is dropped; blank open/high/low are left out."""
    text = text.lstrip("﻿")
    rd = csv.DictReader(io.StringIO(text))
    cols = [c.strip() for c in (rd.fieldnames or [])]
    rd.fieldnames = cols
    ohlc = "CLOSE" in cols
    vcol = "CLOSE" if ohlc else (sym if sym in cols else next((c for c in cols if c != "DATE"), None))
    out: dict[str, dict] = {}
    for row in rd:
        try:
            day = _day(row.get("DATE") or "")
        except ValueError:
            continue
        close = _num(row.get(vcol))
        if close is None:
            continue
        r = {"day": day}
        if ohlc:
            for k in ("OPEN", "HIGH", "LOW"):
                v = _num(row.get(k))
                if v is not None:
                    r[k.lower()] = v
        r["close"] = close
        out[day] = r
    return [out[d] for d in sorted(out)]


def spikes(rows: list[dict], jump: float = 0.20, back: float = 0.03) -> set[str]:
    """Days whose close jumps more than ``jump`` and fully reverts the next day (within ``back`` of the day before):
    one-day bad prints. Crash days (1987-10-19) do not revert; March 2020 swings in volatility-selling indices
    (SVRPO -16.4% then +18.3% on 2020-03-12/13, with SPX -9.5% / +9.3%) are real and stay under 20%."""
    out = set()
    for i in range(1, len(rows) - 1):
        a, b, c = rows[i - 1]["close"], rows[i]["close"], rows[i + 1]["close"]
        if a > 0 and b > 0 and abs(b / a - 1) > jump and abs(c / b - 1) > jump and abs(c / a - 1) < back:
            out.add(rows[i]["day"])
    return out


def annotate(sym: str, rows: list[dict]) -> list[dict]:
    """Adds ``backtest`` (day before launch; None when the launch date is unknown; False for VRO) and ``flag``.
    For VRO also ``carried``: the file repeats the last settlement on non-settlement days (mostly 2017-2020), so a row
    equal to the row at most 4 calendar days earlier is a carried value, not a new settlement print."""
    meta = INDEX_META.get(sym, {})
    launch, settle = meta.get("launch"), meta.get("family") == "settlement"
    flags = dict(KNOWN_ISSUES.get(sym, {}))
    if not settle:
        for d in spikes(rows):
            flags.setdefault(d, "one-day spike that reverts next day (suspect print)")
    out, prev = [], None
    for r in rows:
        v = dict(r)
        v["backtest"] = False if settle else ((r["day"] < launch) if launch else None)
        if settle:
            v["carried"] = bool(prev and prev["close"] == r["close"]
                                and (date.fromisoformat(r["day"]) - date.fromisoformat(prev["day"])).days <= 4)
        if r["day"] in flags:
            v["flag"] = flags[r["day"]]
        out.append(v)
        prev = r
    return out


# --------------------------------------------------------------- point in time --

def publish_time(day: str) -> datetime:
    """19:00 America/New_York on ``day`` as a UTC datetime (23:00 UTC in summer, 00:00 UTC next day in winter)."""
    return datetime.combine(date.fromisoformat(day), PUBLISH_ET, tzinfo=NY).astimezone(timezone.utc)


def available_at(day: str, launch: Optional[str] = None, observed_at: Optional[str] = None) -> str:
    """Evening of the index date, or of the launch date for back-tested values, capped at the fetch time."""
    t = publish_time(max(day, launch) if launch else day)
    if observed_at:
        obs = datetime.fromisoformat(observed_at)
        obs = obs if obs.tzinfo else obs.replace(tzinfo=timezone.utc)
        t = min(t, obs.astimezone(timezone.utc))
    return t.isoformat(timespec="seconds")


def to_archive_rows(sym: str, rows: list[dict], observed_at: str) -> list[dict]:
    launch = INDEX_META.get(sym, {}).get("launch")
    return [{"source": "cboe", "kind": "strategy-index", "key": sym, "observed_at": observed_at,
             "available_at": available_at(v["day"], launch if v.get("backtest") else None, observed_at), "value": v}
            for v in annotate(sym, rows)]


def coverage(rows: list[dict]) -> dict:
    """first, last, rows, columns, largest calendar gap, back-tested and flagged row counts (archive rows or values)."""
    vals = [r.get("value", r) for r in rows]
    if not vals:
        return {"rows": 0}
    days = [date.fromisoformat(v["day"]) for v in vals]
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    cols = sorted({k for v in vals for k in v if k in ("open", "high", "low", "close")})
    return {"first": vals[0]["day"], "last": vals[-1]["day"], "rows": len(vals), "columns": cols,
            "max_gap_days": max(gaps) if gaps else 0, "backtest_rows": sum(1 for v in vals if v.get("backtest")),
            "flagged": {v["day"]: v["flag"] for v in vals if v.get("flag")}}


# -------------------------------------------------------------------- fetching --

def fetch_csv(sym: str, client: httpx.Client, throttle: Throttle, retries: int = 4, backoff: float = 1.0) -> tuple[Optional[str], dict]:
    """GET one history file. Retries 429/5xx and transport errors with exponential backoff; 403/404 mean no file."""
    url = history_url(sym)
    info: dict = {"url": url, "attempts": 0}
    for attempt in range(retries):
        throttle.wait()
        info["attempts"] = attempt + 1
        try:
            r = client.get(url, follow_redirects=True)
        except httpx.HTTPError as e:
            info["error"] = repr(e)
            time.sleep(backoff * 2 ** attempt)
            continue
        info.update(status=r.status_code, final_url=str(r.url), last_modified=r.headers.get("last-modified"), bytes=len(r.content))
        if r.status_code == 200 and r.text.lstrip("﻿").startswith("DATE"):
            return r.text, info
        if r.status_code in RETRY_STATUS:
            time.sleep(backoff * 2 ** attempt)
            continue
        return None, info
    return None, info


def _recipe(sym: str, min_interval: float, retries: int) -> str:
    m = INDEX_META.get(sym, {})
    launch = m.get("launch")
    pit = (f"available_at = 19:00 America/New_York on the index date; rows before launch {launch} are back-tested and "
           f"dated 19:00 ET on {launch}" if launch else "available_at = 19:00 America/New_York on the index date "
           + ("(settlement values, never back-tested)" if m.get("family") == "settlement" else "(launch date not stated by Cboe: backtest = null)"))
    return (f"GET {history_url(sym)} (307 -> cdn-api.cboe.com, redirects followed) via mandel.data.cboe_strategy.fetch_cboe_strategy"
            f"(symbols=['{sym}']); httpx, {min_interval}s pacing, {retries} tries with exponential backoff on 429/5xx/transport errors, "
            f"403 = no file. {pit}; never after observed_at (fetch time). Methodology: {m.get('methodology') or m.get('dashboard', DASHBOARD.format(sym=sym))}")


SCHEMA = ("value = {day, close} (open/high/low too for SPRO, SPEN, SPAI, SPATI, LOVOL when published), index level; "
          "backtest = day before the index launch (null when Cboe states no launch date; false for VRO); "
          "flag = suspect print or known splice (present only when set); VRO rows also carry carried = repeat of the previous "
          "settlement on a non-settlement day")


def fetch_cboe_strategy(store=None, symbols: Optional[Iterable[str]] = None, limit: Optional[int] = None, dry_run: bool = False,
                        client: Optional[httpx.Client] = None, min_interval: float = 0.7, retries: int = 4, backoff: float = 1.0,
                        report: Optional[dict] = None) -> dict[str, list[dict]]:
    """One bundle per index, ``cboe-<SYM>-history`` (small, in git). Returns {bundle name: archive rows}.

    ``store``: an Archive (or an ObservationStore, whose ``.archive`` is used) or None to only return rows; a failed or
    empty fetch never overwrites a stored bundle. ``limit`` caps the number of indices fetched (one call each);
    ``dry_run`` makes no request and returns empty lists, with the plan in ``report``. ``report`` (a dict) is filled
    per symbol with status, Last-Modified and coverage."""
    syms = list(symbols) if symbols is not None else list(STRATEGY_INDICES)
    if limit is not None:
        syms = syms[:limit]
    rep = report if report is not None else {}
    out: dict[str, list[dict]] = {}
    if dry_run:
        for s in syms:
            out[f"cboe-{s}-history"] = []
            rep[s] = {"url": history_url(s), "dry_run": True}
        rep["_plan"] = {"calls": len(syms), "est_seconds": round(len(syms) * (min_interval + 0.6)), "est_raw_mb": round(len(syms) * 0.17, 1)}
        return out
    archive = getattr(store, "archive", store)
    own = client is None
    c = client or _client()
    th = Throttle(min_interval)
    try:
        for s in syms:
            name = f"cboe-{s}-history"
            text, info = fetch_csv(s, c, th, retries=retries, backoff=backoff)
            observed = now_iso()
            rows = to_archive_rows(s, parse_history(text, s), observed) if text else []
            out[name] = rows
            info["coverage"] = coverage(rows)
            if archive is not None and rows:
                m = INDEX_META.get(s, {})
                tags = ["options", "cboe", "strategy-index", "history", m.get("family", "unlisted")] + (["backtested"] if info["coverage"].get("backtest_rows") else [])
                e = archive.store(name, kind="data", rows=rows, recipe=_recipe(s, min_interval, retries), tags=tags, schema=SCHEMA, in_git=True)
                info["stored"] = {"rows": e.rows, "bytes": e.bytes}
            rep[s] = info
    finally:
        if own:
            c.close()
    return out
