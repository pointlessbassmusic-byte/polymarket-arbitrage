"""Live web dashboard for the crypto volatility bot.

FastAPI app that reads the running Scanner's state: equity curve, open
positions, recent signals, wildest movers, closed trades, and the learned
edge report. Single embedded page, polls /api/state every 5 seconds.

Shows both books side by side (simulated and real), the live decision
journal — including every signal the bot declined and which gate stopped
it — and the learned per-pattern edge.

Run with:  python run_cryptobot.py --dashboard [--port 8081]
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ModeRequest(BaseModel):
    """Body of POST /api/mode. Defined at module scope because FastAPI
    resolves endpoint annotations against module globals."""
    mode: str


def create_app(scanner) -> FastAPI:
    app = FastAPI(title="Crypto Volatility Bot", docs_url=None, redoc_url=None)

    @app.get("/api/state")
    async def state() -> dict:
        return scanner.state()

    @app.post("/api/mode")
    async def set_mode(req: ModeRequest) -> dict:
        """Switch the active book. Real mode is refused unless the executor
        is genuinely armed — this endpoint cannot arm anything itself."""
        ok, why = scanner.set_mode(req.mode)
        return {"ok": ok, "mode": scanner.mode, "error": why}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return PAGE

    return app


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Swing Bot</title>
<style>
:root{
  color-scheme: light;
  --surface-0:#fcfcfb; --surface-1:#f2f1ee; --surface-2:#e9e8e4;
  --border:#e0dfda; --border-strong:#c9c8c2;
  --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#8a8983;
  --sim:#2a78d6; --real:#eb6834;
  --good:#0ca30c; --warn:#fab219; --bad:#d03b3b;
}
@media (prefers-color-scheme: dark){:root:where(:not([data-theme="light"])){
  color-scheme: dark;
  --surface-0:#1a1a19; --surface-1:#232322; --surface-2:#2c2c2a;
  --border:#3a3a38; --border-strong:#4a4a47;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8983;
  --sim:#3987e5; --real:#d95926;
}}
:root[data-theme="dark"]{
  color-scheme: dark;
  --surface-0:#1a1a19; --surface-1:#232322; --surface-2:#2c2c2a;
  --border:#3a3a38; --border-strong:#4a4a47;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8983;
  --sim:#3987e5; --real:#d95926;
}
*{box-sizing:border-box}
body{margin:0;padding:20px 16px 40px;background:var(--surface-0);color:var(--ink);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
  max-width:1400px;margin-inline:auto}
header{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;
  justify-content:space-between;margin-bottom:20px}
h1{font-size:19px;margin:0 0 3px;letter-spacing:-.01em}
.meta{color:var(--ink-2);font-size:12.5px}
h2{font-size:12px;margin:0 0 12px;color:var(--ink-2);text-transform:uppercase;
  letter-spacing:.06em;font-weight:600}

/* mode toggle */
.toggle{display:flex;background:var(--surface-2);border:1px solid var(--border);
  border-radius:9px;padding:3px;gap:3px}
.toggle button{appearance:none;border:0;background:none;color:var(--ink-2);
  font:inherit;font-weight:600;font-size:13px;padding:7px 18px;border-radius:6px;
  cursor:pointer;display:flex;align-items:center;gap:6px}
.toggle button[aria-pressed="true"]{background:var(--surface-0);color:var(--ink);
  box-shadow:0 1px 3px rgba(0,0,0,.14)}
.toggle button[disabled]{cursor:not-allowed;opacity:.55}
.dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
.toggle button[aria-pressed="true"] .dot.sim{background:var(--sim)}
.toggle button[aria-pressed="true"] .dot.real{background:var(--real)}
.lockmsg{font-size:11.5px;color:var(--ink-3);margin-top:6px;max-width:330px;
  text-align:right;line-height:1.4}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  gap:12px;margin-bottom:18px}
.card{background:var(--surface-1);border:1px solid var(--border);
  border-radius:10px;padding:13px 15px}
.card .lab{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--ink-3);font-weight:600}
.card .val{font-size:23px;font-weight:650;margin-top:3px;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.card .sub{font-size:11.5px;color:var(--ink-2);margin-top:2px}
.card.hero{background:var(--surface-2);border-color:var(--border-strong)}
.card.hero .val{font-size:30px}

.grid{display:grid;grid-template-columns:1fr;gap:16px}
@media(min-width:1040px){.grid{grid-template-columns:1fr 1fr}.span2{grid-column:1/-1}}
.panel{background:var(--surface-1);border:1px solid var(--border);
  border-radius:10px;padding:15px}

table{width:100%;border-collapse:collapse;font-size:13px;
  font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--ink-3);font-weight:600;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.05em;padding:0 8px 7px 0;
  border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:6px 8px 6px 0;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:0}
.num{text-align:right}
.dim{color:var(--ink-2)}
.empty{color:var(--ink-3);font-size:13px;padding:10px 0}
.pos{color:var(--good);font-weight:600}
.neg{color:var(--bad);font-weight:600}
.sym{font-weight:600}

/* decision feed */
.feed{max-height:430px;overflow-y:auto;margin:-4px -4px 0;padding:4px}
.dec{display:grid;grid-template-columns:44px 1fr auto;gap:10px;padding:8px 6px;
  border-bottom:1px solid var(--border);align-items:baseline}
.dec:last-child{border-bottom:0}
.dec .age{color:var(--ink-3);font-size:11.5px;font-variant-numeric:tabular-nums}
.dec .body{min-width:0}
.dec .head{display:flex;gap:7px;align-items:baseline;flex-wrap:wrap}
.dec .why{color:var(--ink-2);font-size:12px;margin-top:2px;
  overflow-wrap:anywhere}
.dec .amt{font-variant-numeric:tabular-nums;font-size:12.5px;white-space:nowrap}
.tag{font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  padding:2px 7px;border-radius:5px;border:1px solid var(--border-strong);
  color:var(--ink-2);white-space:nowrap}
.tag.opened{background:color-mix(in srgb,var(--good) 16%,transparent);
  border-color:var(--good);color:var(--good)}
.tag.closed{background:color-mix(in srgb,var(--sim) 14%,transparent);
  border-color:var(--sim);color:var(--sim)}
.tag.skipped{background:transparent}
.tag.book-real{border-color:var(--real);color:var(--real)}

/* funnel */
.funnel{display:flex;flex-direction:column;gap:7px}
.frow{display:grid;grid-template-columns:96px 1fr 44px;gap:10px;align-items:center;
  font-size:12.5px}
.bar{height:9px;border-radius:5px;background:var(--surface-2);overflow:hidden}
.bar span{display:block;height:100%;border-radius:5px;background:var(--ink-3)}
.bar span.opened{background:var(--good)}
.frow .n{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-2)}

/* chart */
#wrap{position:relative}
#tip{position:absolute;pointer-events:none;display:none;background:var(--surface-0);
  border:1px solid var(--border-strong);border-radius:7px;padding:7px 10px;
  font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;
  box-shadow:0 2px 10px rgba(0,0,0,.14);z-index:5;line-height:1.5}
.legend{display:flex;gap:16px;font-size:12px;color:var(--ink-2);margin-bottom:8px}
.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;
  margin-right:6px;vertical-align:middle}
svg text{fill:var(--ink-3);font-size:10px;font-family:inherit}
svg .grid{stroke:var(--border)}
svg .base{stroke:var(--border-strong);stroke-dasharray:4 4}
svg .xh{stroke:var(--ink-3);stroke-dasharray:3 3}
</style>
</head>
<body>
<header>
  <div>
    <h1>Crypto Swing Bot</h1>
    <div class="meta" id="meta">connecting…</div>
  </div>
  <div>
    <div class="toggle" role="group" aria-label="Trading mode">
      <button id="bSim" aria-pressed="true" onclick="setMode('sim')">
        <span class="dot sim"></span>Simulated</button>
      <button id="bReal" aria-pressed="false" onclick="setMode('real')">
        <span class="dot real"></span>Real money</button>
    </div>
    <div class="lockmsg" id="lock"></div>
  </div>
</header>

<div class="cards" id="cards"></div>

<div class="grid">
  <div class="panel span2">
    <h2>Equity</h2>
    <div class="legend" id="legend"></div>
    <div id="wrap"><svg id="chart" width="100%" height="190" role="img"
      aria-label="Equity over time"></svg><div id="tip"></div></div>
  </div>

  <div class="panel">
    <h2>Live decisions — what it did, and why</h2>
    <div class="feed" id="feed"></div>
  </div>

  <div class="panel">
    <h2>Open positions</h2><div id="positions"></div>
    <h2 style="margin-top:18px">Where signals get filtered</h2>
    <div class="funnel" id="funnel"></div>
  </div>

  <div class="panel">
    <h2>Closed trades</h2><div id="closed"></div>
  </div>

  <div class="panel">
    <h2>Wildest movers right now</h2><div id="movers"></div>
  </div>

  <div class="panel span2">
    <h2>Learned edge by pattern</h2><div id="edges"></div>
  </div>
</div>

<script>
"use strict";
const $=id=>document.getElementById(id);
const n=(v,d=2)=>v==null?"–":Number(v).toLocaleString("en-US",
  {minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(v,d=1)=>v==null?"–":(v>=0?"+":"")+(100*v).toFixed(d)+"%";
const px=v=>v==null?"–":(v>=1?n(v,4):Number(v).toPrecision(4));
const cls=v=>v>0?"pos":v<0?"neg":"";
// Signed money: a loss must carry its minus sign, not rely on colour
// alone (colour is not available to every reader, and red "$1.88" reads
// as a gain).
const money=(v,d=2)=>(v<0?"\u2212":"+")+"$"+n(Math.abs(v),d);
const ago=t=>{const s=Date.now()/1000-t;
  if(s<60)return Math.max(0,Math.round(s))+"s";
  if(s<5400)return Math.round(s/60)+"m";
  if(s<172800)return (s/3600).toFixed(1)+"h";return Math.round(s/86400)+"d";};

let S=null, curve=[], view="sim";

function table(cols,rows,nums=[]){
  if(!rows.length)return '<div class="empty">nothing yet</div>';
  const th=cols.map((c,i)=>`<th class="${nums.includes(i)?'num':''}">${c}</th>`).join("");
  const tb=rows.map(r=>"<tr>"+r.map((c,i)=>{
    const o=(c&&typeof c==="object")?c:{v:c};
    return `<td class="${nums.includes(i)?'num ':''}${o.c||''}">${o.v}</td>`;
  }).join("")+"</tr>").join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table>`;
}

async function setMode(m){
  if(m===view&&S&&S.mode===m)return;
  if(m==="real"&&S&&!S.real_unlocked){view="sim";render();return;}
  try{
    const r=await fetch("/api/mode",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:m})});
    const j=await r.json();
    if(j.ok){view=m;}
  }catch(e){}
  poll();
}

function renderCards(b){
  const s=b.summary||{}, ret=b.return_pct||0;
  const isReal=view==="real";
  $("cards").innerHTML=
    `<div class="card hero"><div class="lab">${isReal?"Real":"Simulated"} equity</div>
      <div class="val">$${n(b.equity)}</div>
      <div class="sub"><span class="${cls(ret)}">${pct(ret,2)}</span>
        from $${n(b.starting_equity,0)}</div></div>`+
    `<div class="card"><div class="lab">Realized</div>
      <div class="val ${cls(s.realized_pnl)}">${money(s.realized_pnl)}</div>
      <div class="sub">${s.trades||0} trades · $${n(s.total_costs)} costs paid</div></div>`+
    `<div class="card"><div class="lab">Open</div>
      <div class="val ${cls(s.unrealized_pnl)}">${money(s.unrealized_pnl)}</div>
      <div class="sub">${s.open_positions||0} positions · $${n(s.exposure_usd,0)} at risk</div></div>`+
    `<div class="card"><div class="lab">Win rate</div>
      <div class="val">${s.win_rate==null?"–":(100*s.win_rate).toFixed(0)+"%"}</div>
      <div class="sub">of ${s.trades||0} closed</div></div>`+
    `<div class="card"><div class="lab">Drawdown</div>
      <div class="val">${pct(-(b.drawdown||0))}</div>
      <div class="sub">${b.halted?"⚠ entries halted":"from peak"}</div></div>`;
}

function renderFeed(decs){
  if(!decs.length){$("feed").innerHTML='<div class="empty">no decisions yet — '+
    'the bot logs every signal it evaluates here, taken or not</div>';return;}
  $("feed").innerHTML=decs.map(d=>{
    const amt=d.action==="closed"
      ? `<span class="${cls(d.pnl_usd)}">${money(d.pnl_usd)}</span>`
      : (d.size_usd?`<span class="dim">$${n(d.size_usd,0)}</span>`:"");
    const bookTag=d.book==="real"?'<span class="tag book-real">real</span>':"";
    return `<div class="dec"><div class="age">${ago(d.ts)}</div><div class="body">
      <div class="head"><span class="tag ${d.action}">${d.action}</span>
        <span class="sym">${d.symbol}</span>
        <span class="dim" style="font-size:12px">${d.chain} · ${d.signal_type||d.stage}</span>
        ${bookTag}</div>
      <div class="why">${d.reason||""}</div></div>
      <div class="amt">${amt}</div></div>`;
  }).join("");
}

function renderFunnel(counts){
  const order=["entry","protections","sizing","costs","security","exit"];
  const label={entry:"Entered",protections:"Cooldown/guard",sizing:"Too small",
    costs:"Costs too high",security:"Failed rug scan",exit:"Exited"};
  const rows=order.filter(k=>counts[k]);
  if(!rows.length){$("funnel").innerHTML='<div class="empty">no signals evaluated yet</div>';return;}
  const max=Math.max(...rows.map(k=>counts[k]));
  $("funnel").innerHTML=rows.map(k=>
    `<div class="frow"><span class="dim">${label[k]||k}</span>
     <span class="bar"><span class="${k==='entry'?'opened':''}"
       style="width:${(100*counts[k]/max).toFixed(1)}%"></span></span>
     <span class="n">${counts[k]}</span></div>`).join("");
}

function drawChart(){
  const svg=$("chart"),W=svg.clientWidth||900,H=190,L=58,R=14,T=10,B=24;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const showReal=S&&S.real_unlocked;
  $("legend").innerHTML=`<span><i style="background:var(--sim)"></i>Simulated</span>`+
    (showReal?`<span><i style="background:var(--real)"></i>Real</span>`:"");
  if(curve.length<2){
    svg.innerHTML=`<text x="${W/2}" y="${H/2}" text-anchor="middle">collecting data…</text>`;
    return;}
  const xs=curve.map(p=>p[0]);
  const series=showReal?[1,2]:[1];
  let vals=[];series.forEach(i=>curve.forEach(p=>vals.push(p[i])));
  const base=S.books.sim.starting_equity;vals.push(base);
  let y0=Math.min(...vals),y1=Math.max(...vals);
  if(y1-y0<0.02*base){y0=base*0.99;y1=base*1.01;}
  const pad=(y1-y0)*0.12;y0-=pad;y1+=pad;
  const x0=Math.min(...xs),x1=Math.max(...xs);
  const X=t=>L+(x1===x0?0.5:(t-x0)/(x1-x0))*(W-L-R);
  const Y=v=>T+(1-(v-y0)/(y1-y0))*(H-T-B);
  const dg=(y1-y0)<4?2:(y1-y0)<40?1:0;
  let g="";
  for(let i=0;i<=3;i++){const v=y0+(y1-y0)*i/3,y=Y(v);
    g+=`<line class="grid" x1="${L}" y1="${y}" x2="${W-R}" y2="${y}"/>
        <text x="${L-7}" y="${y+3}" text-anchor="end">${n(v,dg)}</text>`;}
  g+=`<line class="base" x1="${L}" y1="${Y(base)}" x2="${W-R}" y2="${Y(base)}"/>`;
  [x0,(x0+x1)/2,x1].forEach(t=>{g+=`<text x="${X(t)}" y="${H-7}" text-anchor="middle">`+
    new Date(t*1000).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})+`</text>`;});
  const colors={1:"var(--sim)",2:"var(--real)"};
  series.forEach(i=>{
    const d=curve.map((p,k)=>(k?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[i]).toFixed(1)).join(" ");
    g+=`<path d="${d}" fill="none" stroke="${colors[i]}" stroke-width="2"
         stroke-linejoin="round"/>`;});
  g+=`<g id="hv" style="display:none"><line class="xh" y1="${T}" y2="${H-B}"/>`+
     series.map(i=>`<circle r="4" fill="${colors[i]}" stroke="var(--surface-1)"
       stroke-width="2" data-s="${i}"/>`).join("")+`</g>`;
  svg.innerHTML=g;
  const hv=svg.querySelector("#hv"),tip=$("tip");
  svg.onmousemove=e=>{
    const r=svg.getBoundingClientRect(),mx=(e.clientX-r.left)*(W/r.width);
    let bi=0,bd=1e18;
    curve.forEach((p,i)=>{const d=Math.abs(X(p[0])-mx);if(d<bd){bd=d;bi=i;}});
    const p=curve[bi],cx=X(p[0]);
    hv.style.display="";
    hv.querySelector("line").setAttribute("x1",cx);
    hv.querySelector("line").setAttribute("x2",cx);
    hv.querySelectorAll("circle").forEach(c=>{
      c.setAttribute("cx",cx);c.setAttribute("cy",Y(p[+c.dataset.s]));});
    tip.style.display="block";
    tip.innerHTML=new Date(p[0]*1000).toLocaleTimeString()+
      `<br>Sim $${n(p[1])}`+(showReal?`<br>Real $${n(p[2])}`:"");
    const left=cx/(W/r.width);
    tip.style.left=Math.min(left+12,r.width-tip.offsetWidth-6)+"px";
    tip.style.top="6px";
  };
  svg.onmouseleave=()=>{hv.style.display="none";tip.style.display="none";};
}

function render(){
  if(!S)return;
  if(view==="real"&&!S.real_unlocked)view="sim";
  const b=S.books[view];
  $("bSim").setAttribute("aria-pressed",String(view==="sim"));
  $("bReal").setAttribute("aria-pressed",String(view==="real"));
  $("bReal").disabled=!S.real_unlocked;
  $("lock").textContent=S.real_unlocked
    ? (S.mode==="real"?"Real money is ARMED and trading.":"Unlocked — switch when ready.")
    : "🔒 "+S.real_locked_reason;
  $("meta").innerHTML=`cycle ${S.cycle} · ${S.tracked_pairs} pairs tracked · `+
    `${(S.chains||[]).join(", ")} · up ${ago(S.started_at)}`;

  renderCards(b);
  renderFeed((S.decisions||[]).filter(d=>d.book===view));
  renderFunnel(S.journal_counts||S.gate_counts||{});

  $("positions").innerHTML=table(
    ["Token","Pattern","Entry","Now","Size","P&L","Age"],
    (b.positions||[]).map(p=>[{v:p.symbol,c:"sym"},{v:p.signal_type||"",c:"dim"},
      px(p.entry_price),px(p.price),"$"+n(p.size_usd,0),
      {v:money(p.pnl_usd),c:cls(p.pnl_usd)},
      {v:ago(p.opened_at),c:"dim"}]),[2,3,4,5,6]);

  $("closed").innerHTML=table(
    ["Token","Pattern","P&L","Costs","Exit","Held","When"],
    (b.closed_trades||[]).slice(0,14).map(t=>[{v:t.symbol,c:"sym"},
      {v:t.signal_type||"",c:"dim"},
      {v:money(t.pnl_usd),c:cls(t.pnl_usd)},
      {v:"$"+n(t.costs_usd),c:"dim"},{v:t.exit_reason,c:"dim"},
      {v:ago(Date.now()/1000-t.held_s),c:"dim"},{v:ago(t.closed_at),c:"dim"}]),
    [2,3,5,6]);

  $("movers").innerHTML=table(
    ["Token","Price","5m","30m","1h","24h"],
    (S.movers||[]).slice(0,12).map(m=>[{v:m.symbol,c:"sym"},px(m.price_usd),
      {v:pct(m.move_5m),c:cls(m.move_5m)},{v:pct(m.move_30m),c:cls(m.move_30m)},
      {v:pct(m.move_1h),c:cls(m.move_1h)},{v:pct(m.move_24h),c:cls(m.move_24h)}]),
    [1,2,3,4,5]);

  const et=(S.edges&&S.edges.by_signal_type)||{};
  $("edges").innerHTML=table(
    ["Pattern","Trades","Win rate","Profit factor","Expectancy/$","Net P&L","Sizing ×"],
    Object.entries(et).map(([k,v])=>[k,n(v.trades,0),
      v.win_rate==null?"–":(100*v.win_rate).toFixed(0)+"%",
      v.profit_factor==null?"–":n(v.profit_factor),
      n(v.expectancy_per_dollar,3),
      {v:money(v.total_pnl),c:cls(v.total_pnl)},
      n((S.edges.multipliers||{})[k])]),[1,2,3,4,5,6]);

  curve=S.equity_curve||[];
  drawChart();
}

async function poll(){
  try{
    const r=await fetch("/api/state");
    S=await r.json();
    if(view==="sim"&&S.mode==="real")view="real";
    render();
  }catch(e){$("meta").textContent="disconnected — retrying…";}
}
poll();setInterval(poll,4000);
addEventListener("resize",drawChart);
</script>
</body>
</html>
"""
