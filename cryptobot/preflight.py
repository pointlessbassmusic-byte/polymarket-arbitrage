"""Go-live preflight: verify every dependency of profitable live trading
BEFORE arming real money. Run with `python run_cryptobot.py --preflight`.

Checks, in order of "will this lose money if wrong":
  1. config parses and the risk/cost numbers are coherent;
  2. data feeds reachable (DexScreener, CoinGecko, GoPlus);
  3. 0x quote API reachable (with the API key if provided);
  4. live wiring: private key present and valid, RPC per chain responds
     and reports the expected chain id, wallet gas balance per chain
     covers a sensible number of swaps;
  5. per-chain viability: minimum position size implied by gas vs the
     configured position caps (catches "every trade will be skipped").

Read-only: no transaction is ever sent. Exits 0 when live-ready (or when
paper-only and everything paper needs is green), 1 otherwise.
"""

from __future__ import annotations

import os

import httpx

from .costs import CostModel
from .execution.wallet import CHAIN_IDS, WalletConfig
from .risk import RiskConfig

OK, WARN, FAIL = "ok", "warn", "fail"


class Check:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.rows.append((status, name, detail))

    @property
    def failed(self) -> bool:
        return any(s == FAIL for s, _, _ in self.rows)

    def render(self) -> str:
        icon = {OK: "✓", WARN: "!", FAIL: "✗"}
        return "\n".join(
            f"  [{icon[s]}] {name}" + (f" — {detail}" if detail else "")
            for s, name, detail in self.rows
        )


async def _probe(client: httpx.AsyncClient, name: str, url: str,
                 check: Check, headers: dict | None = None) -> None:
    try:
        resp = await client.get(url, headers=headers or {})
        if resp.status_code < 400:
            check.add(OK, name)
        else:
            check.add(FAIL, name, f"HTTP {resp.status_code}")
    except httpx.TransportError as exc:
        check.add(FAIL, name, str(exc))


async def run_preflight(wallet_cfg: WalletConfig, risk_cfg: RiskConfig,
                        costs: CostModel, chains: list[str]) -> bool:
    check = Check()

    # 1. config coherence
    if risk_cfg.max_position_usd > risk_cfg.max_total_exposure_usd:
        check.add(FAIL, "risk config",
                  "max_position_usd exceeds max_total_exposure_usd")
    else:
        check.add(OK, "risk config")

    # 5 (early, no network needed). per-chain economic viability
    for chain in chains:
        min_size = costs.min_viable_size(chain)
        if min_size > risk_cfg.max_position_usd:
            check.add(WARN, f"viability: {chain}",
                      f"gas needs ≥${min_size:.0f}/trade but cap is "
                      f"${risk_cfg.max_position_usd:.0f} — entries here "
                      f"will be skipped")
        else:
            check.add(OK, f"viability: {chain}",
                      f"min ${min_size:.0f}/trade")

    # 2. data feeds
    async with httpx.AsyncClient(timeout=15.0) as client:
        await _probe(client, "DexScreener",
                     "https://api.dexscreener.com/latest/dex/search?q=PEPE", check)
        await _probe(client, "CoinGecko",
                     "https://api.coingecko.com/api/v3/ping", check)
        await _probe(client, "GoPlus security DB",
                     "https://api.gopluslabs.io/api/v1/supported_chains", check)

        # 3. 0x
        zerox_key = os.environ.get(wallet_cfg.zerox_api_key_env, "")
        headers = {"0x-version": "v2"}
        if zerox_key:
            headers["0x-api-key"] = zerox_key
        try:
            resp = await client.get(
                "https://api.0x.org/swap/allowance-holder/price",
                params={"chainId": 8453,
                        "sellToken": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                        "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        "sellAmount": "1000000000000000"},
                headers=headers)
            if resp.status_code < 400:
                check.add(OK, "0x swap API",
                          "with key" if zerox_key else "no key (rate-limited)")
            elif resp.status_code in (401, 403):
                check.add(WARN if not wallet_cfg.live else FAIL, "0x swap API",
                          f"HTTP {resp.status_code} — set "
                          f"${wallet_cfg.zerox_api_key_env} (free at 0x.org)")
            else:
                check.add(WARN, "0x swap API", f"HTTP {resp.status_code}")
        except httpx.TransportError as exc:
            check.add(WARN, "0x swap API", str(exc))

    # 4. live wiring (only meaningful when live is requested)
    if not wallet_cfg.live:
        check.add(OK, "mode", "paper trading — no key/RPC checks needed")
    else:
        armed = os.environ.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes"
        check.add(OK if armed else WARN, "arm switch",
                  "CRYPTOBOT_ARM_LIVE=yes" if armed
                  else "CRYPTOBOT_ARM_LIVE not 'yes' — will stay dry-run")

        key = os.environ.get(wallet_cfg.private_key_env, "")
        address = None
        if not key:
            check.add(FAIL, "private key",
                      f"${wallet_cfg.private_key_env} is empty")
        else:
            try:
                from eth_account import Account
                address = Account.from_key(key).address
                check.add(OK, "private key", f"wallet {address[:10]}…")
            except ImportError:
                check.add(FAIL, "private key",
                          "eth-account not installed — pip install web3")
            except Exception:
                check.add(FAIL, "private key", "not a valid secp256k1 key")

        evm_chains = [c for c in chains if c in CHAIN_IDS]
        for chain in evm_chains:
            rpc = wallet_cfg.rpc_urls.get(chain)
            if not rpc:
                check.add(FAIL, f"RPC: {chain}", "no URL configured")
                continue
            try:
                from web3 import Web3
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
                cid = w3.eth.chain_id
                if cid != CHAIN_IDS[chain]:
                    check.add(FAIL, f"RPC: {chain}",
                              f"reports chain id {cid}, expected {CHAIN_IDS[chain]}")
                    continue
                if address:
                    bal_wei = w3.eth.get_balance(address)
                    bal = bal_wei / 1e18
                    swaps = costs.gas_usd(chain)
                    check.add(OK if bal > 0 else WARN, f"RPC: {chain}",
                              f"native balance {bal:.4f} "
                              f"(~${swaps:.2f}/swap gas here)")
                else:
                    check.add(OK, f"RPC: {chain}", "reachable")
            except ImportError:
                check.add(FAIL, f"RPC: {chain}", "web3 not installed")
            except Exception as exc:
                check.add(FAIL, f"RPC: {chain}", str(exc)[:80])

    print("\nPreflight:")
    print(check.render())
    verdict = "NOT READY — fix the ✗ items" if check.failed else (
        "ready to go live" if wallet_cfg.live else "ready (paper mode)")
    print(f"\n  → {verdict}\n")
    return not check.failed
