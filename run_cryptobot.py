#!/usr/bin/env python3
"""Entry point for the crypto volatility / memecoin swing bot.

Usage:
    python run_cryptobot.py                 # continuous paper-trading loop
    python run_cryptobot.py --once          # single scan cycle, print signals
    python run_cryptobot.py --dashboard     # loop + web dashboard on :8081
    python run_cryptobot.py --config my.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import yaml

from cryptobot.costs import CostConfig
from cryptobot.data.goplus import ScreenConfig
from cryptobot.execution.wallet import WalletConfig, WalletExecutor
from cryptobot.protections import ProtectionConfig
from cryptobot.risk import RiskConfig
from cryptobot.scanner import Scanner, ScannerConfig
from cryptobot.signals import SignalConfig


def _build(cls, section: dict):
    """Instantiate a dataclass from a config section, ignoring unknown keys."""
    fields = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
    return cls(**{k: v for k, v in (section or {}).items() if k in fields})


def load(config_path: Path) -> Scanner:
    raw = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    scan_cfg = _build(ScannerConfig, raw.get("scanner"))
    sig_cfg = _build(SignalConfig, raw.get("signals"))
    risk_cfg = _build(RiskConfig, raw.get("risk"))

    executor = None
    exec_raw = raw.get("execution") or {}
    if exec_raw.get("live"):
        executor = WalletExecutor(_build(WalletConfig, exec_raw))

    return Scanner(scan_cfg, sig_cfg, risk_cfg,
                   state_dir=config_path.parent, executor=executor,
                   screen_cfg=_build(ScreenConfig, raw.get("security")),
                   protection_cfg=_build(ProtectionConfig, raw.get("protections")),
                   cost_cfg=_build(CostConfig, raw.get("costs")),
                   sim_bankroll_usd=float(
                       (raw.get("sim") or {}).get("bankroll_usd", 200.0)))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Crypto volatility swing bot")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).parent / "cryptobot_config.yaml")
    parser.add_argument("--once", action="store_true",
                        help="run one scan cycle and print signals as JSON")
    parser.add_argument("--preflight", action="store_true",
                        help="check keys, RPCs, balances, and per-chain "
                             "viability, then exit")
    parser.add_argument("--dashboard", action="store_true",
                        help="serve the live web dashboard alongside the loop")
    parser.add_argument("--port", type=int, default=8081,
                        help="dashboard port (default 8081)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="dashboard bind address. Defaults to loopback: "
                             "the dashboard has no authentication, exposes "
                             "the full position book on /api/state and can "
                             "switch trading mode on /api/mode. Only widen "
                             "this behind a trusted proxy or VPN.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.preflight:
        from cryptobot.costs import CostModel
        from cryptobot.preflight import run_preflight

        raw = yaml.safe_load(args.config.read_text()) if args.config.exists() else {}
        ok = await run_preflight(
            _build(WalletConfig, raw.get("execution")),
            _build(RiskConfig, raw.get("risk")),
            CostModel(_build(CostConfig, raw.get("costs"))),
            (raw.get("scanner") or {}).get("chains")
            or ["ethereum", "base", "solana", "bsc", "arbitrum"],
        )
        return 0 if ok else 1

    scanner = load(args.config)
    try:
        if args.once:
            signals = await scanner.run_cycle()
            print(json.dumps([s.as_dict() for s in signals], indent=2))
        elif args.dashboard:
            import uvicorn

            from cryptobot.dashboard import create_app

            import secrets

            log = logging.getLogger(__name__)
            # Guards every /api/* route. Not a login — it is what stops
            # anything else that can reach the port (or a rebinding page)
            # from reading the book or switching trading mode.
            token = os.environ.get("CRYPTOBOT_DASHBOARD_TOKEN") \
                or secrets.token_urlsafe(16)
            extra_hosts = ({args.host.lower()}
                           if args.host not in ("0.0.0.0", "::") else set())
            if args.host not in ("127.0.0.1", "localhost", "::1"):
                log.warning(
                    "dashboard binding to %s — it has NO authentication: "
                    "anyone who can reach port %d can read your positions "
                    "and switch trading mode. Put it behind a proxy or VPN.",
                    args.host, args.port)
            server = uvicorn.Server(uvicorn.Config(
                create_app(scanner, token=token, extra_hosts=extra_hosts),
                host=args.host, port=args.port, log_level="warning",
            ))
            log.info("dashboard at http://%s:%d/?t=%s   (the token is "
                     "required — open this exact URL)",
                     "localhost" if args.host == "127.0.0.1" else args.host,
                     args.port, token)
            await asyncio.gather(scanner.run_forever(), server.serve())
        else:
            await scanner.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        await scanner.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
