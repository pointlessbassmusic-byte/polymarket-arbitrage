"""Every broker the desk can reach: what it is for, which keys it needs,
and a probe that reads each account with the keys present.

    python -m cryptobot.brokers            # key status table
    python -m cryptobot.brokers --probe    # read every account that has keys

Which venue trades a rule is decided by the registry, not here; this is
the inventory and the health check. See RESEARCH-2026-10.md addendum 5
for why each broker is on the list and Fidelity is not.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any, Callable, Optional

BROKERS: dict[str, dict] = {
    "kalshi": {
        "for": "DOGE/SHIB/BTC/ETH, US500 and metals perps; the live small-account venue",
        "keys": ("CRYPTOBOT_KALSHI_KEY_ID", "CRYPTOBOT_KALSHI_KEY_PEM"),
        "fees": "4 bp taker / 2 bp maker, funding every 8h",
        "note": "CFTC-regulated; US residents; perps access enabled per member",
    },
    "coinbase": {
        "for": "DOGE, 1000PEPE, 1000SHIB perpetual-style futures in whole ~$60-480 contracts",
        "keys": ("CRYPTOBOT_COINBASE_KEY_NAME", "CRYPTOBOT_COINBASE_KEY_SECRET"),
        "fees": "0.05%/side with a $0.20/contract floor; 92-114% overnight short margin",
        "note": "CFTC-regulated; the only US PEPE listing",
    },
    "kraken": {
        "for": "carry spot leg; spot-margin shorts on DOGE/PEPE/SHIB (perp.venue: kraken, selectable, not default)",
        "keys": ("CRYPTOBOT_KRAKEN_KEY", "CRYPTOBOT_KRAKEN_SECRET"),
        "fees": "0.40% maker / 0.80% taker at tier 1 since 2026-07-09; margin 0.02-0.04% to open + per 4h",
        "note": "key with query + trade only, never withdrawal; US perps (Bitnomial, DOGE/SHIB, $0.15/contract) "
                "have no documented API yet",
    },
    "alpaca": {
        "for": "US stocks, ETFs and options; paper endpoint; free IEX bars (ORB pilot, PEAD, overnight study data)",
        "keys": ("CRYPTOBOT_ALPACA_KEY_ID", "CRYPTOBOT_ALPACA_SECRET_KEY"),
        "fees": "$0 commission on US equities; options $0.65/contract or less",
        "note": "paper and live keys are different pairs; no futures",
    },
    "tastytrade": {
        "for": "options, futures and futures options incl. CME micro BTC (btc-vrp-listed-options)",
        "keys": ("CRYPTOBOT_TASTY_CLIENT_SECRET", "CRYPTOBOT_TASTY_REFRESH_TOKEN"),
        "fees": "options $1/contract to open, $0 to close; futures per contract",
        "note": "OAuth2 personal app; futures approval is a flag on the account",
    },
    "hyperliquid": {
        "for": "150-perp universe; public data only from the US",
        "keys": ("CRYPTOBOT_PRIVATE_KEY",),
        "fees": "n/a from the US",
        "note": "geo-blocked for US residents; the desk reads its public candles and funding only",
    },
}


async def _kraken_cash(ex) -> float:
    """USD cash from the spot Balance call (the margin executor's own
    `balance()` is TradeBalance equity)."""
    from .execution.kraken_spot import KrakenSpotExecutor
    b = await KrakenSpotExecutor.balance(ex)
    return float(b.get("ZUSD", b.get("USD", 0.0)))


def key_status(env: dict) -> list[dict]:
    rows = []
    for name, spec in BROKERS.items():
        missing = [k for k in spec["keys"] if not env.get(k)]
        rows.append({"broker": name, "has_keys": not missing, "missing": missing, **spec})
    return rows


def render_status(rows: list[dict]) -> str:
    out = [f"{'broker':12s} {'keys':6s} {'for'}"]
    for r in rows:
        out.append(f"{r['broker']:12s} {'yes' if r['has_keys'] else 'no':6s} {r['for']}")
        if not r["has_keys"]:
            out.append(f"{'':19s} missing: {', '.join(r['missing'])}")
    return "\n".join(out)


async def probe(env: dict, cfg: Optional[dict] = None, *, factories: Optional[dict[str, Callable]] = None) -> list[str]:
    """One line per broker with keys: what the account says, or the
    exception class if it could not be read. `factories` overrides the
    client constructors (tests)."""
    cfg = cfg or {}
    brokers_cfg = cfg.get("brokers") or {}
    f = factories or {}
    lines: list[str] = []
    for name in BROKERS:
        if any(not env.get(k) for k in BROKERS[name]["keys"]):
            continue
        try:
            lines.append(await _probe_one(name, env, brokers_cfg.get(name) or {}, f))
        except Exception as exc:           # noqa: BLE001 - report, never raise, never print secrets
            lines.append(f"{name:12s} ERROR {type(exc).__name__}: {str(exc)[:160]}")
    return lines or ["no broker keys in the environment"]


async def _probe_one(name: str, env: dict, bcfg: dict, f: dict) -> str:
    if name == "alpaca":
        from .execution.alpaca import AlpacaConfig, AlpacaExecutor
        ex = (f.get("alpaca") or (lambda: AlpacaExecutor(AlpacaConfig(live=bool(bcfg.get("live"))))))()
        try:
            b = await ex.balance()
            clock = await ex.clock()
            return (f"{name:12s} {b['mode']:7s} equity ${b['total_usd_balance']:,.2f} buying power "
                    f"${b['available_margin']:,.2f} status {b['status']} shorting {'on' if b['shorting_enabled'] else 'off'} "
                    f"PDT {'yes' if b['pattern_day_trader'] else 'no'} daytrades {b['daytrade_count']} "
                    f"market {'open' if clock.get('is_open') else 'closed'}")
        finally:
            await ex.close_client()
    if name == "tastytrade":
        from .execution.tastytrade import TastytradeClient, TastytradeConfig
        cl = (f.get("tastytrade") or (lambda: TastytradeClient(TastytradeConfig(live=bool(bcfg.get("live"))))))()
        try:
            accts = await cl.accounts()
            parts = []
            for a in accts:
                b = await cl.balances(a)
                parts.append(f"{a}: NLV ${b['total_usd_balance']:,.2f} deriv BP ${b['available_margin']:,.2f}")
            mbt = await cl.micro_bitcoin()
            return (f"{name:12s} {len(accts)} account(s) " + "; ".join(parts)
                    + f" | CME micro BTC listed: {', '.join(mbt) if mbt else 'none'}")
        finally:
            await cl.close_client()
    if name == "kalshi":
        from .execution.kalshi_perps import KalshiExecConfig, KalshiPerpsExecutor
        ex = (f.get("kalshi") or (lambda: KalshiPerpsExecutor(KalshiExecConfig())))()
        try:
            en = await ex.enabled()
            b = await ex.balance()
            return (f"{name:12s} perps {'enabled' if en else 'NOT enabled'} equity ${b['total_usd_balance']:,.2f} "
                    f"available ${b['available_margin']:,.2f}")
        finally:
            await ex.close_client()
    if name == "kraken":
        from .execution.kraken_margin import KrakenMarginConfig, KrakenMarginExecutor
        ex = (f.get("kraken") or (lambda: KrakenMarginExecutor(KrakenMarginConfig())))()
        try:
            cash = await _kraken_cash(ex)
            tb = await ex.balance()
            return (f"{name:12s} USD ${cash:,.2f} equity ${tb['total_usd_balance']:,.2f} "
                    f"free margin ${tb['available_margin']:,.2f}")
        finally:
            await ex.close_client()
    if name == "coinbase":
        return f"{name:12s} keys present (balance via python -m cryptobot.desk --preflight)"
    return f"{name:12s} keys present"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true", help="read every account that has keys")
    ap.add_argument("--config", default="cryptobot_config.yaml")
    a = ap.parse_args(argv)
    env = dict(os.environ)
    print(render_status(key_status(env)))
    if a.probe:
        cfg: dict[str, Any] = {}
        try:
            import yaml
            from pathlib import Path
            p = Path(a.config)
            cfg = yaml.safe_load(p.read_text()) or {} if p.exists() else {}
        except Exception:               # noqa: BLE001
            cfg = {}
        print()
        for line in asyncio.run(probe(env, cfg)):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
