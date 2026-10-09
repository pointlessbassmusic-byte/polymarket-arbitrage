"""The desk dashboard: one page for capital, allocation, the strategies'
paper and real books, execution quality, and the registry ("lab")."""

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Trading Desk</title>
<style>
:root{color-scheme:light;--bg:#fcfcfb;--card:#ffffff;--fg:#0b0b0b;--fg2:#52514e;--mut:#8a8984;--line:#e6e5e1;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#008300;--warn:#c98500;--bad:#c62828;--chip:#f1f0ec}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#111110;--card:#1a1a19;--fg:#fff;--fg2:#c3c2b7;--mut:#8f8e88;--line:#2b2b29;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#4cc26b;--warn:#e0a63a;--bad:#ff6b6b;--chip:#242423}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#111110;--card:#1a1a19;--fg:#fff;--fg2:#c3c2b7;--mut:#8f8e88;--line:#2b2b29;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#4cc26b;--warn:#e0a63a;--bad:#ff6b6b;--chip:#242423}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 2px}h2{font-size:15px;margin:0 0 10px;color:var(--fg2);font-weight:600}
.sub{color:var(--mut);margin:0 0 18px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;overflow-x:auto;min-width:0}
.card.strat{grid-column:span 2}@media (max-width:720px){.card.strat{grid-column:1/-1}}
.kpi{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.tile .l{color:var(--mut);font-size:12px}.tile .v{font-size:26px;font-weight:650;letter-spacing:-.01em;margin-top:2px}
.tile .d{font-size:12px;color:var(--fg2)}
.up{color:var(--good)}.dn{color:var(--bad)}.wn{color:var(--warn)}
.chip{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--chip);color:var(--fg2);font-size:12px;margin-right:6px}
.chip.good{color:var(--good)}.chip.bad{color:var(--bad)}.chip.warn{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:right;padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th:first-child,td:first-child{text-align:left}th{color:var(--mut);font-weight:500;font-size:12px}
td.l{text-align:left}
button{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid var(--line);background:var(--chip);color:var(--fg);cursor:pointer}
button.primary{background:var(--s1);border-color:var(--s1);color:#fff}button:disabled{opacity:.5;cursor:default}
input[type=number]{font:inherit;width:72px;padding:5px 6px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0}
.why{color:var(--fg2);font-size:12.5px;margin:4px 0 8px}
.muted{color:var(--mut);font-size:12px}
.legend{display:flex;gap:14px;font-size:12px;color:var(--fg2);margin:4px 0 6px}.legend i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
svg text{fill:var(--fg2);font-size:11px}.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12px;display:none}
pre{white-space:pre-wrap;font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--fg2);margin:0}
.alert{padding:8px 10px;border-radius:8px;background:var(--chip);margin:4px 0;font-size:13px}
details summary{cursor:pointer;color:var(--fg2)}
</style></head><body><div class="wrap">
<h1>Trading desk</h1><p class="sub" id="sub">loading…</p>
<div class="kpi" id="kpi"></div>
<div class="grid">
 <div class="card" style="grid-column:1/-1"><h2>Allocation</h2><div id="alloc"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Equity</h2><div id="legend" class="legend"></div><div style="position:relative"><svg id="chart" width="100%" height="220" viewBox="0 0 1000 220" preserveAspectRatio="none"></svg><div class="tip" id="tip"></div></div>
  <details><summary>table view</summary><div id="eqtable"></div></details></div>
 <div id="strats" style="display:contents"></div>
 <div class="card" style="grid-column:1/-1"><h2>Execution (real fills, last 30 days)</h2><pre id="exec">no real fills yet</pre></div>
 <div class="card" style="grid-column:1/-1"><h2>Lab: every idea tested, with its verdict</h2><div id="lab"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Desk events</h2><div id="alerts"></div></div>
</div></div>
<script>
const T=new URLSearchParams(location.search).get("t")||"";
const H={"x-dashboard-token":T,"content-type":"application/json"};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const usd=x=>"$"+Number(x||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=(x,d=1)=>(x>=0?"+":"")+(100*x).toFixed(d)+"%";
const cls=x=>x>0?"up":x<0?"dn":"";
const when=ts=>ts?new Date(1000*ts).toLocaleString():"–";
let S=null;
async function post(path,body){const r=await fetch(path,{method:"POST",headers:H,body:JSON.stringify(body)});const j=await r.json();if(!r.ok){alert(j.error||"failed")}await tick();return j}
function kpis(){
 const a=S.allocation,c=a.capital||{};const dep=Object.values(a.weights||{}).reduce((s,w)=>s+w,0);
 const names=Object.keys(S.strategies);
 const realEq=names.reduce((s,n)=>s+(S.strategies[n].real.equity||0),0), realStart=names.reduce((s,n)=>s+(S.strategies[n].real.starting_equity||0),0);
 const simEq=names.reduce((s,n)=>s+(S.strategies[n].sim.equity||0),0), simStart=names.reduce((s,n)=>s+(S.strategies[n].sim.starting_equity||0),0);
 const killed=Object.keys(a.killed||{}).length;
 const funded=names.some(n=>S.strategies[n].real_unlocked);
 const tiles=[
  funded?["Real capital",usd(c.total),`from ${esc(c.source||"config")} · ${Math.round(100*dep)}% deployed, ${Math.round(100*(a.cash||0))}% cash`]
        :["Real capital","unfunded",`config bankroll ${usd(c.total)}; arm a venue (preflight) to fund`],
  ["Real books",usd(realEq),`<span class="${cls(realEq-realStart)}">${pct(realStart?realEq/realStart-1:0,2)}</span> since start`],
  ["Paper books",usd(simEq),`<span class="${cls(simEq-simStart)}">${pct(simStart?simEq/simStart-1:0,2)}</span> since start`],
  ["Allocation mode",esc(a.mode),killed?`<span class="dn">${killed} strategy killed on drawdown</span>`:"no kills"],
 ];
 document.getElementById("kpi").innerHTML=tiles.map(([l,v,d])=>`<div class="tile"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");
 document.getElementById("sub").textContent=`updated ${when(S.ts)} · allocation decided ${when(a.ts)}`;
}
function alloc(){
 const a=S.allocation;let h=`<div class="row"><span class="chip ${a.mode==="auto"?"good":"warn"}">${esc(a.mode)}</span>`;
 h+=a.mode==="auto"?`<button onclick="post('api/allocation',{mode:'manual',weights:currentWeights()})">switch to manual (keep current weights)</button>`:`<button class="primary" onclick="post('api/allocation',{mode:'auto'})">back to auto</button>`;
 h+=`<span class="muted">auto = shrunk backtest evidence updated slowly by live trades, Kelly-sized, hard gates; manual = your weights. Weights are fractions of real capital; the rest stays cash.</span></div>`;
 h+=`<table><thead><tr><th>strategy</th><th>weight</th><th>capital</th><th>posterior / trade</th><th>f*</th><th>live trades</th><th class="l">why</th></tr></thead><tbody>`;
 for(const [n,st] of Object.entries(S.strategies)){const w=a.weights[n]||0,p=a.posterior[n]||{};const cap=(a.capital&&a.capital.total||0)*w;
  h+=`<tr><td class="l"><b>${esc(st.title)}</b><br><span class="muted">${esc(st.venue)} · ${esc(st.verdict)}</span></td>
  <td>${a.mode==="manual"?`<input type="number" min="0" max="100" step="5" id="w_${n}" value="${Math.round(100*w)}">%`:Math.round(100*w)+"%"}</td>
  <td>${st.real_unlocked?usd(cap):"–"}</td><td>${p.mean!=null?pct(p.mean,2):"–"}</td><td>${p.f_star!=null?p.f_star.toFixed(2):"–"}</td><td>${p.n_live??0}</td>
  <td class="l why">${esc(a.reasons[n]||"")}${a.killed[n]?` <button onclick="post('api/resume',{strategy:'${n}'})">resume</button>`:""}</td></tr>`}
 h+=`<tr><td class="l">cash</td><td>${Math.round(100*(a.cash||0))}%</td><td>${usd((a.capital&&a.capital.total||0)*(a.cash||0))}</td><td colspan="4"></td></tr></tbody></table>`;
 if(a.mode==="manual")h+=`<div class="row"><button class="primary" onclick="post('api/allocation',{mode:'manual',weights:readWeights()})">apply weights</button><span class="muted">must add up to 100% or less</span></div>`;
 if(a.history&&a.history.length)h+=`<details><summary>allocation history (${a.history.length})</summary><table><tbody>${a.history.slice().reverse().map(x=>`<tr><td class="l">${when(x.ts)}</td><td class="l">${esc(x.mode)}</td><td class="l">${esc(Object.entries(x.weights).map(([k,v])=>k+" "+Math.round(100*v)+"%").join(", ")||"nothing")}</td></tr>`).join("")}</tbody></table></details>`;
 document.getElementById("alloc").innerHTML=h;
}
function currentWeights(){const o={};for(const n of Object.keys(S.strategies))o[n]=S.allocation.weights[n]||0;return o}
function readWeights(){const o={};for(const n of Object.keys(S.strategies)){const e=document.getElementById("w_"+n);o[n]=e?Number(e.value)/100:0}return o}
function strategies(){
 let h="";for(const [n,st] of Object.entries(S.strategies)){
  const ev=st.evidence||{};const rc=st.reconcile;
  h+=`<div class="card strat"><h2>${esc(st.title)} <span class="chip">${esc(st.venue)}</span><span class="chip ${st.verdict==="killed"?"bad":st.verdict==="alive"?"good":"warn"}">${esc(st.verdict)}</span><span class="chip ${st.real_unlocked?"good":""}">${st.real_unlocked?"real "+esc(st.mode):"paper only"}</span></h2>`;
  h+=`<table><thead><tr><th></th><th>real</th><th>paper</th></tr></thead><tbody>
   <tr><td class="l">equity</td><td>${usd(st.real.equity)} <span class="${cls(st.real.return_pct)}">${pct(st.real.return_pct||0,2)}</span></td><td>${usd(st.sim.equity)} <span class="${cls(st.sim.return_pct)}">${pct(st.sim.return_pct||0,2)}</span></td></tr>
   <tr><td class="l">open / closed</td><td>${st.real.open} / ${st.real.trades}</td><td>${st.sim.open} / ${st.sim.trades}</td></tr>
   <tr><td class="l">drawdown</td><td class="${st.real.drawdown>0.1?"dn":""}">${pct(-(st.real.drawdown||0))}${st.real.halted?' <span class="chip bad">halted</span>':""}</td><td>${pct(-(st.sim.drawdown||0))}${st.sim.halted?' <span class="chip bad">halted</span>':""}</td></tr>
   <tr><td class="l">deployable capital</td><td>${st.capital!=null?usd(st.capital):"–"}</td><td></td></tr></tbody></table>`;
  h+=`<p class="why">evidence: backtest ${pct(ev.backtest_mean||0,2)}/trade, sd ${pct(ev.backtest_sd||0,1)}, confidence ${(ev.confidence??0).toFixed(2)} (${esc(st.registry_id)}). ${esc(st.track_record)}</p>`;
  if(rc)h+=`<p class="why ${rc.ok?"":"dn"}">${rc.ok?"venue positions match the book":"VENUE MISMATCH: venue-only ["+esc(rc.venue_only.join(","))+"] book-only ["+esc(rc.book_only.join(","))+"] size ["+esc(rc.qty_mismatch.join(","))+"]"}</p>`;
  if(!st.real_unlocked)h+=`<p class="muted">${esc(st.real_locked_reason)}</p>`;
  else h+=`<div class="row"><button ${st.mode==="real"?"disabled":""} onclick="post('api/strategy_mode',{strategy:'${n}',mode:'real'})">trade real</button><button ${st.mode==="sim"?"disabled":""} onclick="post('api/strategy_mode',{strategy:'${n}',mode:'sim'})">paper only</button></div>`;
  if(st.positions.length){h+=`<table><thead><tr><th>book</th><th>coin</th><th>size</th><th>entry</th><th>price</th><th>P&amp;L</th></tr></thead><tbody>`;
   for(const p of st.positions)h+=`<tr><td class="l">${esc(p.book)}</td><td>${esc(p.symbol)}</td><td>${usd(p.size_usd)}</td><td>${Number(p.entry_price).toPrecision(5)}</td><td>${Number(p.price).toPrecision(5)}</td><td class="${cls(p.pnl_usd)}">${usd(p.pnl_usd)}</td></tr>`;h+=`</tbody></table>`}
  if(st.decisions.length){h+=`<details><summary>recent decisions</summary><table><tbody>`;for(const d of st.decisions)h+=`<tr><td class="l muted">${when(d.ts)}</td><td class="l">${esc(d.book)} ${esc(d.action)} ${esc(d.symbol)}</td><td class="l muted">${esc(d.reason)}</td></tr>`;h+=`</tbody></table></details>`}
  h+=`</div>`}
 document.getElementById("strats").innerHTML=h;
}
function chart(){
 const names=Object.keys(S.equity).filter(n=>(S.equity[n]||[]).length>1);const svg=document.getElementById("chart");const colors=["var(--s1)","var(--s2)","var(--s3)"];
 const series=[];names.forEach((n,i)=>{const pts=S.equity[n];series.push({name:S.strategies[n].title+" real",pts:pts.map(p=>[p[0],p[2]]),color:colors[(2*i)%3]});series.push({name:S.strategies[n].title+" paper",pts:pts.map(p=>[p[0],p[1]]),color:colors[(2*i+1)%3]})});
 const show=series.slice(0,3);document.getElementById("legend").innerHTML=show.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("");
 if(!show.length){svg.innerHTML=`<text x="500" y="110" text-anchor="middle">equity points appear after the first hour of trading</text>`;return}
 const all=show.flatMap(s=>s.pts);const xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const L=56,R=16,Tp=12,B=28,W=1000,Hh=220;const X=t=>L+(x1>x0?(t-x0)/(x1-x0):0)*(W-L-R),Y=v=>Tp+(y1>y0?(y1-v)/(y1-y0):0.5)*(Hh-Tp-B);
 let g="";const ticks=4;for(let i=0;i<=ticks;i++){const v=y0+(y1-y0)*i/ticks,y=Y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="var(--line)" stroke-width="1"/><text x="${L-6}" y="${y+4}" text-anchor="end">${Math.round(v).toLocaleString()}</text>`}
 g+=`<text x="${L}" y="${Hh-8}">${new Date(1000*x0).toLocaleDateString()}</text><text x="${W-R}" y="${Hh-8}" text-anchor="end">${new Date(1000*x1).toLocaleDateString()}</text>`;
 for(const s of show){const d=s.pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ");g+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
  const last=s.pts[s.pts.length-1];g+=`<circle cx="${X(last[0])}" cy="${Y(last[1])}" r="4" fill="${s.color}" stroke="var(--card)" stroke-width="2"/><text x="${Math.min(X(last[0])+6,W-R-40)}" y="${Y(last[1])-6}">${esc(s.name.split(" ").pop())} ${Math.round(last[1]).toLocaleString()}</text>`}
 g+=`<line id="xh" x1="0" x2="0" y1="${Tp}" y2="${Hh-B}" stroke="var(--mut)" stroke-dasharray="3 3" style="display:none"/>`;
 svg.innerHTML=g;
 const tip=document.getElementById("tip");svg.onmousemove=e=>{const r=svg.getBoundingClientRect();const t=x0+(x1-x0)*Math.max(0,Math.min(1,((e.clientX-r.left)/r.width*W-L)/(W-L-R)));
  const xh=document.getElementById("xh");xh.style.display="";xh.setAttribute("x1",X(t));xh.setAttribute("x2",X(t));
  tip.style.display="block";tip.style.left=(e.clientX-r.left+12)+"px";tip.style.top=(e.clientY-r.top-10)+"px";
  tip.innerHTML=`<b>${new Date(1000*t).toLocaleString()}</b><br>`+show.map(s=>{let b=s.pts[0];for(const p of s.pts){if(p[0]<=t)b=p;else break}return `${esc(s.name)}: ${usd(b[1])}`}).join("<br>")};
 svg.onmouseleave=()=>{tip.style.display="none";document.getElementById("xh").style.display="none"};
 document.getElementById("eqtable").innerHTML=`<table><thead><tr><th>time</th>${show.map(s=>`<th>${esc(s.name)}</th>`).join("")}</tr></thead><tbody>${show[0].pts.slice(-12).map((p,i)=>`<tr><td class="l">${when(p[0])}</td>${show.map(s=>{const q=s.pts[s.pts.length-12+i]||s.pts[s.pts.length-1];return `<td>${usd(q[1])}</td>`}).join("")}</tr>`).join("")}</tbody></table>`;
}
function lab(){
 const order={alive:0,adopted:1,inconclusive:2,killed:3};const rows=(S.registry||[]).slice().sort((a,b)=>(order[a.verdict]??9)-(order[b.verdict]??9));
 document.getElementById("lab").innerHTML=`<table><thead><tr><th>id</th><th>verdict</th><th>trials</th><th>DSR / PSR</th><th class="l">result</th></tr></thead><tbody>`+
  rows.map(r=>`<tr><td class="l"><b>${esc(r.id)}</b><br><span class="muted">${esc(r.title)}</span></td><td><span class="chip ${r.verdict==="killed"?"bad":r.verdict==="alive"||r.verdict==="adopted"?"good":"warn"}">${esc(r.verdict)}</span></td><td>${r.trials_run??"–"}</td><td>${r.dsr!=null?Number(r.dsr).toFixed(2):r.psr!=null?Number(r.psr).toFixed(2):"–"}</td><td class="l muted">${esc(r.result)}</td></tr>`).join("")+`</tbody></table>`;
}
async function tick(){try{const r=await fetch("api/desk",{headers:H});if(!r.ok){document.getElementById("sub").textContent="token rejected; open the URL from the desk log";return}S=await r.json();
 kpis();alloc();strategies();chart();lab();const tune=Object.entries(S.tuning||{}).map(([n,t])=>`IOC limit ${n}: ${(100*t.limit).toFixed(2)}% — ${t.reason}`).join("\n");
 document.getElementById("exec").textContent=(S.execution_text||"no real fills yet")+(tune?"\n"+tune:"");
 document.getElementById("alerts").innerHTML=(S.alerts||[]).slice().reverse().map(a=>`<div class="alert"><span class="muted">${when(a.ts)}</span> ${esc(a.text)}</div>`).join("")||`<span class="muted">nothing yet</span>`;
}catch(e){document.getElementById("sub").textContent="desk unreachable: "+e}}
tick();setInterval(tick,30000);
</script></body></html>"""
