"""Live web dashboard for the crypto volatility bot.

FastAPI app that reads the running Scanner's state: equity curve, open
positions, recent signals, wildest movers, closed trades, and the learned
edge report. Single embedded page, polls /api/state every 5 seconds.

Run with:  python run_cryptobot.py --dashboard [--port 8081]
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


def create_app(scanner) -> FastAPI:
    app = FastAPI(title="Crypto Volatility Bot", docs_url=None, redoc_url=None)

    @app.get("/api/state")
    async def state() -> dict:
        return scanner.state()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return PAGE

    return app


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Vol Bot</title>
<style>
:root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --surface-2: #f2f1ee;
  --border: #e0dfda;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #8a8983;
  --series-1: #2a78d6;
  --status-good: #0ca30c;
  --status-critical: #d03b3b;
  --status-warning: #fab219;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --surface-2: #232322;
    --border: #3a3a38;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #8a8983;
    --series-1: #3987e5;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1: #1a1a19;
  --surface-2: #232322;
  --border: #3a3a38;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted: #8a8983;
  --series-1: #3987e5;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 16px;
  background: var(--surface-1); color: var(--text-primary);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
}
h1 { font-size: 18px; margin: 0 0 4px; }
.sub { color: var(--text-secondary); font-size: 12px; margin-bottom: 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.tile { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }
.tile .label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); }
.tile .value { font-size: 22px; font-weight: 600; margin-top: 2px; font-variant-numeric: tabular-nums; }
.tile .delta { font-size: 12px; color: var(--text-secondary); }
.grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
@media (min-width: 1000px) { .grid { grid-template-columns: 1fr 1fr; } }
.card { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h2 { font-size: 13px; margin: 0 0 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .05em; }
table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
th { text-align: left; color: var(--text-muted); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; padding: 4px 8px 6px 0; border-bottom: 1px solid var(--border); }
td { padding: 5px 8px 5px 0; border-bottom: 1px solid var(--border); color: var(--text-primary); }
td.num, th.num { text-align: right; }
td.dim { color: var(--text-secondary); }
.empty { color: var(--text-muted); font-size: 13px; padding: 8px 0; }
.pnl-pos::before { content: "▲ "; color: var(--status-good); }
.pnl-neg::before { content: "▼ "; color: var(--status-critical); }
.badge { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-secondary); }
.badge.live { border-color: var(--status-critical); color: var(--status-critical); }
#chart-wrap { position: relative; }
#tooltip {
  position: absolute; pointer-events: none; display: none;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 9px; font-size: 12px; color: var(--text-primary);
  font-variant-numeric: tabular-nums; white-space: nowrap; z-index: 5;
}
svg text { fill: var(--text-muted); font-size: 10px; font-family: inherit; }
svg .gridline { stroke: var(--border); stroke-width: 1; }
svg .eq-line { stroke: var(--series-1); stroke-width: 2; fill: none; }
svg .crosshair { stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
svg .hoverdot { fill: var(--series-1); stroke: var(--surface-2); stroke-width: 2; }
</style>
</head>
<body>
<h1>Crypto Volatility Bot</h1>
<div class="sub" id="status">connecting…</div>

<div class="tiles" id="tiles"></div>

<div class="grid">
  <div class="card" style="grid-column: 1 / -1;">
    <h2>Equity (USD)</h2>
    <div id="chart-wrap">
      <svg id="chart" width="100%" height="180" role="img" aria-label="Equity curve"></svg>
      <div id="tooltip"></div>
    </div>
  </div>
  <div class="card"><h2>Open positions</h2><div id="positions"></div></div>
  <div class="card"><h2>Recent signals</h2><div id="signals"></div></div>
  <div class="card"><h2>Wildest movers</h2><div id="movers"></div></div>
  <div class="card"><h2>Closed trades</h2><div id="closed"></div></div>
  <div class="card" style="grid-column: 1 / -1;"><h2>Learned edge by pattern</h2><div id="edges"></div></div>
</div>

<script>
"use strict";
const $ = id => document.getElementById(id);
const fmt = (v, d=2) => v == null ? "–" : Number(v).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = v => v == null ? "–" : (v >= 0 ? "+" : "") + (100 * v).toFixed(1) + "%";
const price = v => v >= 1 ? fmt(v, 4) : Number(v).toPrecision(4);
const ago = ts => { const s = Date.now()/1000 - ts; if (s < 90) return Math.round(s) + "s"; if (s < 5400) return Math.round(s/60) + "m"; return (s/3600).toFixed(1) + "h"; };
const pnlCls = v => v > 0 ? "pnl-pos" : v < 0 ? "pnl-neg" : "";

function tile(label, value, delta) {
  return `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div>` +
         (delta ? `<div class="delta">${delta}</div>` : "") + `</div>`;
}

function table(headers, rows, numCols) {
  if (!rows.length) return `<div class="empty">nothing yet</div>`;
  const th = headers.map((h, i) => `<th${numCols.includes(i) ? ' class="num"' : ''}>${h}</th>`).join("");
  const body = rows.map(r =>
    "<tr>" + r.map((c, i) => `<td class="${numCols.includes(i) ? 'num ' : ''}${c.cls || ''}">${c.v !== undefined ? c.v : c}</td>`).join("") + "</tr>"
  ).join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
}

let curve = [];

function drawChart() {
  const svg = $("chart");
  const W = svg.clientWidth, H = 180, padL = 56, padR = 12, padT = 10, padB = 22;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  if (curve.length < 2) { svg.innerHTML = `<text x="${W/2}" y="${H/2}" text-anchor="middle">collecting data…</text>`; return; }
  const xs = curve.map(p => p[0]), ys = curve.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (y1 - y0 < 1) { y0 -= 1; y1 += 1; }
  const pad = (y1 - y0) * 0.1; y0 -= pad; y1 += pad;
  const X = t => padL + (t - x0) / (x1 - x0) * (W - padL - padR);
  const Y = v => padT + (1 - (v - y0) / (y1 - y0)) * (H - padT - padB);
  let g = "";
  const yd = (y1 - y0) < 4 ? 2 : (y1 - y0) < 40 ? 1 : 0;  // no duplicate axis labels on flat curves
  for (let i = 0; i <= 3; i++) {
    const v = y0 + (y1 - y0) * i / 3, y = Y(v);
    g += `<line class="gridline" x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}"/>` +
         `<text x="${padL - 6}" y="${y + 3}" text-anchor="end">${fmt(v, yd)}</text>`;
  }
  [x0, (x0 + x1) / 2, x1].forEach(t => {
    g += `<text x="${X(t)}" y="${H - 6}" text-anchor="middle">${new Date(t * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}</text>`;
  });
  const d = curve.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join(" ");
  g += `<path class="eq-line" d="${d}"/>`;
  g += `<g id="hover" style="display:none"><line class="crosshair" y1="${padT}" y2="${H - padB}"/><circle class="hoverdot" r="4"/></g>`;
  svg.innerHTML = g;

  const hover = svg.querySelector("#hover"), tip = $("tooltip");
  svg.onmousemove = e => {
    const r = svg.getBoundingClientRect(), mx = e.clientX - r.left;
    let best = 0, bd = 1e18;
    curve.forEach((p, i) => { const dd = Math.abs(X(p[0]) - mx); if (dd < bd) { bd = dd; best = i; } });
    const p = curve[best], px = X(p[0]), py = Y(p[1]);
    hover.style.display = "";
    hover.querySelector("line").setAttribute("x1", px);
    hover.querySelector("line").setAttribute("x2", px);
    const c = hover.querySelector("circle"); c.setAttribute("cx", px); c.setAttribute("cy", py);
    tip.style.display = "block";
    tip.innerHTML = `${new Date(p[0] * 1000).toLocaleTimeString()} · $${fmt(p[1])}`;
    tip.style.left = Math.min(px + 10, r.width - tip.offsetWidth - 4) + "px";
    tip.style.top = Math.max(py - 34, 0) + "px";
  };
  svg.onmouseleave = () => { hover.style.display = "none"; tip.style.display = "none"; };
}

function render(s) {
  const sum = s.summary || {};
  const equity = s.bankroll_usd + (sum.realized_pnl || 0) + (sum.unrealized_pnl || 0);
  $("status").innerHTML =
    `cycle ${s.cycle} · ${s.tracked_pairs} pairs tracked · up ${ago(s.started_at)} · ` +
    (s.live_armed ? `<span class="badge live">LIVE</span>` : `<span class="badge">paper</span>`) +
    (s.halted ? ` <span class="badge live">HALTED</span>` : "");

  $("tiles").innerHTML =
    tile("Equity", "$" + fmt(equity), "bankroll $" + fmt(s.bankroll_usd, 0)) +
    tile("Realized PnL", `<span class="${pnlCls(sum.realized_pnl)}">$${fmt(sum.realized_pnl)}</span>`,
         (sum.trades || 0) + " trades · net of $" + fmt(sum.total_costs) + " costs") +
    tile("Unrealized PnL", `<span class="${pnlCls(sum.unrealized_pnl)}">$${fmt(sum.unrealized_pnl)}</span>`,
         (sum.open_positions || 0) + " open · $" + fmt(sum.exposure_usd, 0) + " exposure") +
    tile("Win rate", sum.win_rate == null ? "–" : (100 * sum.win_rate).toFixed(0) + "%",
         "of " + (sum.trades || 0) + " closed") +
    tile("Drawdown", pct(-(s.drawdown || 0)), "from equity peak");

  $("positions").innerHTML = table(
    ["Token", "Type", "Entry", "Now", "Size $", "PnL $", "Age"],
    (s.positions || []).map(p => [
      p.symbol, {v: p.signal_type || "", cls: "dim"}, price(p.entry_price), price(p.price),
      fmt(p.size_usd, 0), {v: `<span class="${pnlCls(p.pnl_usd)}">${fmt(p.pnl_usd)}</span>`},
      {v: ago(p.opened_at), cls: "dim"},
    ]), [2, 3, 4, 5]);

  $("signals").innerHTML = table(
    ["Age", "Token", "Type", "R:R", "Conf", "Why"],
    (s.signals || []).slice(0, 12).map(x => [
      {v: ago(x.ts), cls: "dim"}, x.symbol, {v: x.type, cls: "dim"},
      fmt(x.risk_reward, 1), fmt(x.confidence, 2),
      {v: `<span title="${x.reason}">${(x.reason || "").slice(0, 46)}…</span>`, cls: "dim"},
    ]), [3, 4]);

  $("movers").innerHTML = table(
    ["Token", "Price", "5m", "30m", "1h", "24h", "z"],
    (s.movers || []).slice(0, 12).map(m => [
      m.symbol, price(m.price_usd), pct(m.move_5m), pct(m.move_30m),
      pct(m.move_1h), pct(m.move_24h), fmt(m.zscore_5m, 1),
    ]), [1, 2, 3, 4, 5, 6]);

  $("closed").innerHTML = table(
    ["Token", "Type", "PnL $", "Exit", "When"],
    (s.closed_trades || []).slice(0, 12).map(t => [
      t.symbol, {v: t.signal_type || "", cls: "dim"},
      {v: `<span class="${pnlCls(t.pnl_usd)}">${fmt(t.pnl_usd)}</span>`},
      {v: t.exit_reason, cls: "dim"}, {v: ago(t.closed_at), cls: "dim"},
    ]), [2]);

  const et = s.edges && s.edges.by_signal_type || {};
  $("edges").innerHTML = table(
    ["Pattern", "Trades", "Win rate", "Profit factor", "Expectancy/$", "Total PnL $", "Sizing ×"],
    Object.entries(et).map(([k, v]) => [
      k, fmt(v.trades, 0), v.win_rate == null ? "–" : (100 * v.win_rate).toFixed(0) + "%",
      v.profit_factor == null ? "–" : fmt(v.profit_factor, 2),
      fmt(v.expectancy_per_dollar, 3),
      {v: `<span class="${pnlCls(v.total_pnl)}">${fmt(v.total_pnl)}</span>`},
      fmt((s.edges.multipliers || {})[k], 2),
    ]), [1, 2, 3, 4, 5, 6]);

  curve = s.equity_curve || [];
  drawChart();
}

async function poll() {
  try {
    const r = await fetch("/api/state");
    render(await r.json());
  } catch (e) {
    $("status").textContent = "disconnected — retrying…";
  }
}
poll();
setInterval(poll, 5000);
window.addEventListener("resize", drawChart);
</script>
</body>
</html>
"""
