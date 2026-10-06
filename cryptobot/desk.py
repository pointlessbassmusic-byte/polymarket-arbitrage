"""The trading desk: both surviving strategies in one process.

Runs the bounce-short bot (`perp_bot`) and the funding-carry bot
(`carry_bot`) side by side, each sizing from its share of the bankroll
(`allocation:` in the config), behind one web server:

    /          combined view: each strategy's sim and real equity, and the total
    /bounce/   the bounce-short dashboard
    /carry/    the carry dashboard

One token guards every API route, including the mounted ones.

    python -m cryptobot.desk                     # paper trade both, dashboard on :8080
    python -m cryptobot.desk --preflight         # what real money needs, and what is missing

Both bots persist their books in --state-dir and restore them on start, so
a restart (or a container being replaced) loses nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import Request     # module level: annotations here are resolved by name

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ summary

def summary(bots: dict) -> dict:
    """Equity per strategy and in total, for both books."""
    out = {"strategies": {}, "total": {}}
    for name, bot in bots.items():
        st = bot.state()
        row = {"mode": st["mode"], "real_unlocked": st["real_unlocked"]}
        for book in ("sim", "real"):
            b = st["books"][book]
            row[book] = {"start": b["starting_equity"], "equity": b["equity"],
                         "open": b["summary"]["open_positions"],
                         "trades": b["summary"]["trades"]}
            tot = out["total"].setdefault(book, {"start": 0.0, "equity": 0.0})
            tot["start"] += b["starting_equity"]
            tot["equity"] += b["equity"]
        out["strategies"][name] = row
    for book, tot in out["total"].items():
        tot["return_pct"] = (tot["equity"] / tot["start"] - 1.0) if tot["start"] else 0.0
    return out


def digest(bots: dict, since: float, at: Optional[float] = None) -> str:
    """One day in a few lines: equity and return per book, what closed
    since `since`, what is open, and the sim-vs-real gap (the execution
    cost the paper book does not pay). Safe to post anywhere."""
    import datetime as dt
    at = at if at is not None else time.time()
    day = dt.datetime.utcfromtimestamp(at).strftime("%Y-%m-%d")
    lines = [f"desk digest {day} UTC"]
    for name, bot in bots.items():
        st = bot.state()
        books = st["books"]
        for book in ("sim", "real"):
            b = books[book]
            if book == "real" and not st["real_unlocked"]:
                continue
            closed = [t for t in b["closed_trades"] if t["closed_at"] >= since]
            pnl = sum(t["pnl_usd"] for t in closed)
            flags = []
            if b.get("halted"):
                flags.append("HALTED")
            if b.get("drawdown", 0) >= 0.10:
                flags.append(f"drawdown {100 * b['drawdown']:.0f}%")
            lines.append(
                f"{name}/{book}: ${b['equity']:,.2f} ({100 * b['return_pct']:+.2f}% since start), "
                f"{len(closed)} closed today {pnl:+,.2f}, {b['summary']['open_positions']} open"
                + (f" [{'; '.join(flags)}]" if flags else ""))
            for t in closed:
                lines.append(f"    {t['symbol']} {t['exit_reason']} {t['pnl_usd']:+,.2f}")
        if st["real_unlocked"]:
            s_ret, r_ret = books["sim"]["return_pct"], books["real"]["return_pct"]
            lines.append(f"{name} sim-vs-real gap: {100 * (r_ret - s_ret):+.2f} pp")
        rc = st.get("reconcile")
        if rc and not rc.get("ok"):
            lines.append(f"{name} VENUE MISMATCH: venue-only {rc['venue_only']} "
                         f"book-only {rc['book_only']} size {rc['qty_mismatch']}")
    return "\n".join(lines)


async def digest_loop(bots: dict, alerter, hour_utc: int = 0, minute_utc: int = 30) -> None:
    """Post the digest once a day, after the bounce-short's daily run."""
    import datetime as dt
    last = time.time()
    while True:
        now_dt = dt.datetime.now(dt.timezone.utc)
        nxt = now_dt.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
        if nxt <= now_dt:
            nxt += dt.timedelta(days=1)
        await asyncio.sleep((nxt - now_dt).total_seconds())
        try:
            await alerter.send(digest(bots, since=last))
        except Exception as exc:                        # never let the digest kill the desk
            logger.warning("digest failed: %s", exc)
        last = time.time()


SUMMARY_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Desk</title><style>
:root{--bg:#fff;--fg:#1d1d1f;--mut:#6e6e73;--line:#e5e5ea;--up:#1a7f37;--dn:#c62828}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#f2f2f2;--mut:#9a9aa0;--line:#2a2a2e;--up:#4cc26b;--dn:#ff6b6b}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0;padding:24px 16px;max-width:860px;margin:auto}
h1{font-size:20px;margin:0 0 4px}p{color:var(--mut);margin:0 0 20px}
table{width:100%;border-collapse:collapse}th,td{text-align:right;padding:8px 6px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}th{color:var(--mut);font-weight:500;font-size:13px}
.up{color:var(--up)}.dn{color:var(--dn)}a{color:inherit}</style></head><body>
<h1>Trading desk</h1><p>Each strategy on its share of the bankroll.
Open <span id="links"></span></p>
<table><thead><tr><th>strategy</th><th>mode</th><th>sim equity</th><th>sim open</th>
<th>real equity</th><th>real open</th></tr></thead><tbody id="rows"></tbody></table>
<script>
const T=new URLSearchParams(location.search).get("t")||"";
const LINKS={bounce:"bounce-short",carry:"carry"};let linked=false;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct=(e,s)=>{if(!s)return"";const r=e/s-1;return ` <span class="${r>=0?"up":"dn"}">${r>=0?"+":""}${(100*r).toFixed(2)}%</span>`};
async function tick(){try{
 const r=await fetch("api/summary",{headers:{"x-dashboard-token":T}});const d=await r.json();
 if(!linked){linked=true;document.getElementById("links").innerHTML=Object.keys(d.strategies).map(n=>`<a href="${esc(n)}/${T?"?t="+encodeURIComponent(T):""}">${esc(LINKS[n]||n)}</a>`).join(" · ")}
 let h="";for(const [n,s] of Object.entries(d.strategies)){
  h+=`<tr><td>${esc(n)}</td><td>${esc(s.mode)}</td><td>$${s.sim.equity.toFixed(2)}${pct(s.sim.equity,s.sim.start)}</td><td>${s.sim.open}</td>`+
     `<td>$${s.real.equity.toFixed(2)}${pct(s.real.equity,s.real.start)}</td><td>${s.real.open}</td></tr>`}
 const t=d.total;h+=`<tr><th>total</th><th></th><th>$${t.sim.equity.toFixed(2)}${pct(t.sim.equity,t.sim.start)}</th><th></th>`+
     `<th>$${t.real.equity.toFixed(2)}${pct(t.real.equity,t.real.start)}</th><th></th></tr>`;
 document.getElementById("rows").innerHTML=h}catch(e){}}
tick();setInterval(tick,5000);
</script></body></html>"""


def create_desk_app(bots: dict, token: Optional[str], extra_hosts: Optional[set] = None):
    import secrets as _s
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from .dashboard import LOOPBACK_HOSTS, create_app

    app = FastAPI(title="Trading Desk", docs_url=None, redoc_url=None)
    allowed = LOOPBACK_HOSTS | (extra_hosts or set())

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").split(":")[0].lower()
        if host and host not in allowed:
            return JSONResponse({"error": "host not allowed"}, status_code=421)
        if token and request.url.path == "/api/summary":
            sent = request.headers.get("x-dashboard-token") or request.query_params.get("t") or ""
            if not _s.compare_digest(sent, token):
                return JSONResponse({"error": "bad or missing token"}, status_code=401)
        return await call_next(request)

    @app.get("/api/summary")
    async def api_summary() -> dict:
        return summary(bots)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return SUMMARY_PAGE

    def slash_redirect(prefix: str):
        async def _slash(request: Request):
            q = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(f"/{prefix}/{q}")
        return _slash

    for name, bot in bots.items():
        app.add_api_route(f"/{name}", slash_redirect(name), include_in_schema=False)
        app.mount(f"/{name}", create_app(bot, token=token, extra_hosts=extra_hosts))
    return app


# ---------------------------------------------------------------- preflight

def venue(cfg: dict) -> str:
    return cfg.get("perp", {}).get("venue", "hyperliquid")


def capital_plan(cfg: dict) -> dict:
    """Where the real bankroll has to sit, per venue, for both strategies
    at their configured sizes."""
    from .carry_bot import allocation
    carry = cfg.get("carry", {})
    perp = cfg.get("perp", {})
    bank = float(cfg.get("risk", {}).get("bankroll_usd", 1000))
    c_share, b_share = allocation(cfg, "carry"), allocation(cfg, "bounce_short")
    lev = float(carry.get("perp_leverage", 1.0))
    deployed = int(carry.get("top_n", 3)) * float(carry.get("slot_fraction", 0.30))
    carry_notional = c_share * bank * deployed / (1 + 1 / lev)
    if venue(cfg) == "coinbase":
        from .execution.coinbase_futures import US_COINS
        n_coins = len(perp.get("coins") or US_COINS)
        default_cap = 500.0
    else:
        n_coins = len(perp.get("coins") or range(18))
        default_cap = 50.0
    slot = b_share * bank / n_coins
    return {
        "bankroll": bank, "venue": venue(cfg),
        "carry_capital": c_share * bank,
        "bounce_capital": b_share * bank,
        "bounce_slot": slot,
        "kraken_usd": carry_notional,                        # spot leg
        "hyperliquid_usdc": carry_notional / lev + (b_share * bank if venue(cfg) != "coinbase" else 0.0),
        "coinbase_usd": b_share * bank if venue(cfg) == "coinbase" else 0.0,
        "max_trade_usd": float(perp.get("max_trade_usd", default_cap)),
        "largest_order": max(carry_notional / max(1, int(carry.get("top_n", 3))), slot),
    }


async def order_previews(env: dict, max_trade_usd: float) -> list[dict]:
    """With a Coinbase key present, ask the venue to price one contract of
    each coin without placing anything: proves the key, the futures
    account and each product's tradability end to end."""
    from .execution.coinbase_futures import CONTRACTS, CoinbaseExecConfig, CoinbaseFuturesExecutor
    ex = CoinbaseFuturesExecutor(CoinbaseExecConfig(max_trade_usd=max_trade_usd),
                                 key_name=env["CRYPTOBOT_COINBASE_KEY_NAME"],
                                 key_secret=env["CRYPTOBOT_COINBASE_KEY_SECRET"])
    out = []
    for coin in CONTRACTS:
        try:
            out.append(await ex.preview(coin))
        except Exception as exc:
            out.append({"coin": coin, "errs": [str(exc)], "tradable": False})
    return out


def preview_checks(previews: list[dict]) -> list[tuple[str, bool, str]]:
    checks = []
    for p in previews:
        ok = bool(p.get("tradable")) and not p.get("errs")
        why = "; ".join(str(e) for e in p.get("errs") or []) or f"status {p.get('status')}"
        detail = (f"1 contract = ${p.get('order_total', 0):,.2f}, fee ${p.get('commission', 0):.2f}, "
                  f"margin ${p.get('margin', 0):,.2f}") if ok else why
        checks.append((f"Coinbase will accept a {p['coin']} order", ok, detail))
    return checks


async def contract_prices() -> dict:
    """Live dollar size of one Coinbase contract per coin."""
    from .data.coinbase_futures import CoinbaseMarketData
    from .execution.coinbase_futures import CONTRACTS
    md = CoinbaseMarketData()
    try:
        mids = await md.all_mids()
    finally:
        await md.close()
    return {c: mids[c] * CONTRACTS[c].units_per_contract for c in CONTRACTS if c in mids}


def preflight(cfg: dict, env: dict, balances: Optional[dict] = None,
              contract_usd: Optional[dict] = None) -> list[tuple[str, bool, str]]:
    """Checklist for real money. `balances` = {"kraken_usd": x,
    "hyperliquid_usdc": y, "coinbase_usd": z} when they could be read;
    `contract_usd` = live dollar size per Coinbase contract."""
    plan = capital_plan(cfg)
    perp, carry = cfg.get("perp", {}), cfg.get("carry", {})
    carry_on = plan["carry_capital"] > 0
    checks = [
        ("perp.live is true", bool(perp.get("live")), "set perp.live: true in the config"),
        ("CRYPTOBOT_ARM_LIVE=yes", env.get("CRYPTOBOT_ARM_LIVE", "").lower() == "yes",
         "export CRYPTOBOT_ARM_LIVE=yes"),
    ]
    if plan["venue"] == "coinbase":
        checks.append(("Coinbase CDP API key (ES256) name + secret",
                       bool(env.get("CRYPTOBOT_COINBASE_KEY_NAME") and env.get("CRYPTOBOT_COINBASE_KEY_SECRET")),
                       "export CRYPTOBOT_COINBASE_KEY_NAME / _SECRET: a CDP key with trade permission "
                       "only, ECDSA (not Ed25519), futures enabled on the account"))
    else:
        checks.append(("Hyperliquid wallet key",
                       bool(env.get(perp.get("private_key_env", "CRYPTOBOT_PRIVATE_KEY"))),
                       "export CRYPTOBOT_PRIVATE_KEY (a dedicated wallet, not your main one)"))
    if carry_on:
        checks += [
            ("carry.live is true", bool(carry.get("live")), "set carry.live: true (Kraken spot leg)"),
            ("Kraken API key + secret", bool(env.get("CRYPTOBOT_KRAKEN_KEY") and env.get("CRYPTOBOT_KRAKEN_SECRET")),
             "export CRYPTOBOT_KRAKEN_KEY / _SECRET (trade + query permissions, NO withdrawal)"),
        ]
    checks.append(("orders fit under max_trade_usd", plan["largest_order"] <= plan["max_trade_usd"],
                   f"largest planned order ${plan['largest_order']:.2f} > perp.max_trade_usd "
                   f"${plan['max_trade_usd']:.2f}: orders would be capped and positions undersized"))
    if plan["venue"] == "coinbase" and contract_usd:
        worst = max(contract_usd.values())
        checks.append((f"each slot (${plan['bounce_slot']:.0f}) buys at least one contract",
                       plan["bounce_slot"] >= worst,
                       f"the largest contract is ${worst:,.0f}; with {len(contract_usd)} coins the "
                       f"bounce-short needs a bankroll of at least ${worst * len(contract_usd) / max(1e-9, plan['bounce_capital'] / plan['bankroll']):,.0f}"))
    if balances is not None:
        needs = [("kraken_usd", plan["kraken_usd"]), ("hyperliquid_usdc", plan["hyperliquid_usdc"]),
                 ("coinbase_usd", plan["coinbase_usd"])]
        for venue_key, need in needs:
            if need <= 0:
                continue
            have = balances.get(venue_key)
            checks.append((f"{venue_key} >= ${need:.2f}", have is not None and have >= need,
                           f"have ${have if have is not None else 0:.2f}, need ${need:.2f}"))
    return checks


async def read_balances(cfg: dict, env: dict) -> dict:
    """Best-effort live balances; a venue that cannot be read is omitted."""
    out = {}
    key = env.get(cfg.get("perp", {}).get("private_key_env", "CRYPTOBOT_PRIVATE_KEY"))
    if key:
        try:
            import httpx
            from eth_account import Account
            addr = Account.from_key(key).address
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post("https://api.hyperliquid.xyz/info",
                                 json={"type": "clearinghouseState", "user": addr})
                out["hyperliquid_usdc"] = float(r.json()["marginSummary"]["accountValue"])
        except Exception as exc:
            logger.warning("hyperliquid balance unavailable: %s", exc)
    if env.get("CRYPTOBOT_COINBASE_KEY_NAME") and env.get("CRYPTOBOT_COINBASE_KEY_SECRET"):
        try:
            from .execution.coinbase_futures import CoinbaseExecConfig, CoinbaseFuturesExecutor
            ex = CoinbaseFuturesExecutor(CoinbaseExecConfig(),
                                         key_name=env["CRYPTOBOT_COINBASE_KEY_NAME"],
                                         key_secret=env["CRYPTOBOT_COINBASE_KEY_SECRET"])
            out["coinbase_usd"] = (await ex.balance())["total_usd_balance"]
        except Exception as exc:
            logger.warning("coinbase balance unavailable: %s", exc)
    if env.get("CRYPTOBOT_KRAKEN_KEY") and env.get("CRYPTOBOT_KRAKEN_SECRET"):
        try:
            from .execution.kraken_spot import KrakenSpotExecutor, SpotExecConfig
            ex = KrakenSpotExecutor(SpotExecConfig())
            ex._key, ex._secret = env["CRYPTOBOT_KRAKEN_KEY"], env["CRYPTOBOT_KRAKEN_SECRET"]
            bal = await ex.balance()
            await ex.close()
            out["kraken_usd"] = float(bal.get("ZUSD", 0.0)) + float(bal.get("USD", 0.0))
        except Exception as exc:
            logger.warning("kraken balance unavailable: %s", exc)
    return out


def render_preflight(cfg: dict, checks: list) -> str:
    plan = capital_plan(cfg)
    out = [f"real bankroll ${plan['bankroll']:.2f}: carry ${plan['carry_capital']:.2f}, "
           f"bounce-short ${plan['bounce_capital']:.2f} on {plan['venue']}"]
    if plan["kraken_usd"] > 0:
        out.append(f"  fund Kraken with >= ${plan['kraken_usd']:.2f} USD (carry spot leg)")
    if plan["hyperliquid_usdc"] > 0:
        out.append(f"  fund Hyperliquid with >= ${plan['hyperliquid_usdc']:.2f} USDC")
    if plan["coinbase_usd"] > 0:
        out.append(f"  fund Coinbase with >= ${plan['coinbase_usd']:.2f} USD (swept to the futures account automatically)")
    out.append("")
    for name, ok, fix in checks:
        out.append(f"  [{'ok' if ok else '  '}] {name}" + ("" if ok else f"  -> {fix}"))
    ready = all(ok for _, ok, _ in checks)
    out.append("\nREADY for real money" if ready else "\nNOT ready: paper trading only until every box is ticked")
    return "\n".join(out)


# --------------------------------------------------------------------- main

def build(cfg: dict, state_dir: Path) -> dict:
    """Carry is only built when it has capital; on Coinbase-only US setups
    allocation.carry is 0 and the desk is the bounce-short alone."""
    from . import carry_bot, perp_bot
    from .carry_bot import allocation
    from .alerts import Alerter
    bots = {"bounce": perp_bot.build(cfg, state_dir)}
    if allocation(cfg, "carry") > 0:
        bots["carry"] = carry_bot.build(cfg, state_dir)
    alerter = Alerter()
    if alerter.enabled:
        for name, bot in bots.items():
            bot.journal.on_record.append(alerter.hook(name))
        logger.info("alerts on: real fills, exits, reconcile mismatches, halts")
    bots["_alerter"] = alerter
    return bots


async def _main(args) -> int:
    import yaml
    cfg = yaml.safe_load(args.config.read_text()) or {}
    if args.preflight:
        env = dict(os.environ)
        balances = await read_balances(cfg, env)
        sizes = None
        extra: list = []
        if venue(cfg) == "coinbase":
            try:
                sizes = await contract_prices()
            except Exception as exc:
                logger.warning("contract prices unavailable: %s", exc)
            if env.get("CRYPTOBOT_COINBASE_KEY_NAME") and env.get("CRYPTOBOT_COINBASE_KEY_SECRET"):
                extra = preview_checks(await order_previews(
                    env, float(cfg.get("perp", {}).get("max_trade_usd", 500))))
        print(render_preflight(cfg, preflight(cfg, env, balances or None, sizes) + extra))
        return 0
    args.state_dir.mkdir(parents=True, exist_ok=True)
    bots = build(cfg, args.state_dir)
    alerter = bots.pop("_alerter")
    if args.digest:
        print(digest(bots, since=time.time() - 86400))
        for b in bots.values():
            await b.close()
        return 0
    token = args.token or os.environ.get("CRYPTOBOT_DASH_TOKEN") or secrets.token_urlsafe(16)
    import uvicorn
    app = create_desk_app(bots, token, set(args.allow_host or []))
    shown = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    logger.info("desk dashboard: http://%s:%d/?t=%s", shown, args.port, token)
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="warning"))
    alerter.fire(f"desk up: {', '.join(bots)}; venue {venue(cfg)}; "
                 f"real {'ARMED' if any(getattr(b, 'real_armed', False) for b in bots.values()) else 'locked'}")
    tasks = [b.run_forever() for b in bots.values()] + [server.serve()]
    if alerter.enabled:
        d = cfg.get("desk", {}).get("digest_utc", "00:30")
        hh, mm = (int(x) for x in str(d).split(":"))
        tasks.append(digest_loop(bots, alerter, hh, mm))
    try:
        await asyncio.gather(*tasks)
    finally:
        for b in bots.values():
            await b.close()
        await alerter.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="carry + bounce-short trading desk")
    ap.add_argument("--config", type=Path, default=Path("cryptobot_config.yaml"))
    ap.add_argument("--state-dir", type=Path, default=Path("state"))
    ap.add_argument("--digest", action="store_true",
                    help="print today's digest from the saved books and exit")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default=None, help="dashboard token (default: random, or $CRYPTOBOT_DASH_TOKEN)")
    ap.add_argument("--allow-host", action="append",
                    help="extra Host header to accept, e.g. your server's name (repeatable)")
    ap.add_argument("--preflight", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
