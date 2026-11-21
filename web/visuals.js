/* Views of engine outputs only; this module does not calculate risk scores. */
(function(root){
  'use strict';
  const colors={Low:'#65d6ae',Guarded:'#73b5fa',Elevated:'#e6cf77',High:'#ff9b74',Severe:'#fb6f91'};
  const labels={transport:'Transport',health:'Health',energy_water_wastewater:'Energy / water',communications:'Communications',waste:'Waste',financial_services:'Financial services',security_and_safety:'Security / safety',food:'Food',government_facilities:'Government'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function summarize(rows){
    const bands=Object.fromEntries(Object.keys(colors).map(k=>[k,0])),sectors={},pillars={T:0,V:0,R:0,C:0};
    for(const f of rows){
      bands[f.result.band]++;
      const s=sectors[f.sector]||(sectors[f.sector]={key:f.sector,count:0,total:0});
      s.count++;s.total+=f.result.score_exact;
      for(const k of Object.keys(pillars))pillars[k]+=f.result.pillars[k];
    }
    for(const k of Object.keys(pillars))pillars[k]=rows.length?pillars[k]/rows.length:0;
    return {count:rows.length,bands,pillars,sectors:Object.values(sectors).map(s=>({...s,mean:s.total/s.count})).sort((a,b)=>b.mean-a.mean||a.key.localeCompare(b.key))};
  }
  function bandMarkup(summary){
    const circumference=2*Math.PI*61;let offset=0;
    const segments=Object.entries(summary.bands).map(([band,count])=>{
      if(!count)return '';
      const length=count/summary.count*circumference,start=offset;offset+=length;
      return `<circle cx="100" cy="100" r="61" fill="none" stroke="${colors[band]}" stroke-width="13" stroke-dasharray="${Math.max(0,length-3)} ${circumference}" stroke-dashoffset="${-start}" transform="rotate(-90 100 100)"><title>${band}: ${count} facilities</title></circle>`;
    }).join('');
    return `<div class="band-layout"><svg viewBox="0 0 200 200" role="img" aria-label="${esc(Object.entries(summary.bands).map(([k,v])=>k+': '+v).join(', '))}"><circle cx="100" cy="100" r="61" fill="none" stroke="#263449" stroke-width="13"/>${segments}<text x="100" y="104" text-anchor="middle" class="donut-number">${summary.count}</text><text x="100" y="126" text-anchor="middle" class="donut-label">FACILITIES</text></svg><div class="band-breakdown">${Object.entries(summary.bands).map(([band,count])=>`<div><span><i style="background:${colors[band]}"></i>${band}</span><strong>${count}</strong></div>`).join('')}</div></div><p class="chart-footnote">Risk bands include category overrides.</p>`;
  }
  function sectorMarkup(summary,active){
    return summary.sectors.length?`<div class="sector-bars">${summary.sectors.map(s=>`<button class="sector-row ${active===s.key?'active':''}" data-sector="${esc(s.key)}" aria-label="Filter ${esc(labels[s.key]||s.key)}: average risk ${s.mean.toFixed(1)}, ${s.count} facilities" aria-pressed="${active===s.key}"><span class="sector-name" title="${esc(s.key.replaceAll('_',' '))}">${esc(labels[s.key]||s.key)}<small>${s.count}</small></span><span class="sector-track"><i style="width:${s.mean}%;background:${s.mean>=80?colors.Severe:s.mean>=60?colors.High:s.mean>=40?colors.Elevated:s.mean>=20?colors.Guarded:colors.Low}"></i></span><strong>${s.mean.toFixed(1)}</strong></button>`).join('')}</div><p class="chart-footnote">Mean risk / 100 · click a sector to filter.</p>`:'<div class="empty">No facilities match the filters.</div>';
  }
  function radarMarkup(summary,selected){
    if(!selected)return '<div class="empty">Select a facility to compare pillars.</div>';
    const keys=['T','V','R','C'],names=['Threat','Vulnerability','Recovery gap','Consequence'],cx=150,cy=110,r=70;
    const point=(i,value)=>({x:cx+Math.sin(i*Math.PI/2)*r*value/10,y:cy-Math.cos(i*Math.PI/2)*r*value/10});
    const polygon=values=>keys.map((k,i)=>{const p=point(i,values[k]);return `${p.x},${p.y}`;}).join(' ');
    const grid=[2.5,5,7.5,10].map(n=>`<polygon points="${polygon({T:n,V:n,R:n,C:n})}" fill="none" stroke="#30415a" stroke-width="1"/>`).join('');
    return `<svg class="radar" viewBox="0 0 300 220" role="img" aria-label="${esc(selected.name_en)} pillar comparison: ${keys.map(k=>k+' '+selected.result.pillars[k].toFixed(2)).join(', ')}">${grid}${keys.map((k,i)=>{const p=point(i,10);return `<line x1="${cx}" y1="${cy}" x2="${p.x}" y2="${p.y}" stroke="#30415a"/>`;}).join('')}${summary.count?`<polygon points="${polygon(summary.pillars)}" fill="#949cff1c" stroke="#949cff" stroke-dasharray="4 4" stroke-width="1.4"/>`:''}<polygon points="${polygon(selected.result.pillars)}" fill="#67dccc33" stroke="#67dccc" stroke-width="2"/>${keys.map((k,i)=>{const p=point(i,selected.result.pillars[k]),label=point(i,12.3);return `<circle cx="${p.x}" cy="${p.y}" r="3" fill="#bff3db"/><text x="${label.x}" y="${label.y+4}" text-anchor="${i===1?'start':i===3?'end':'middle'}" class="radar-label">${k}</text>`;}).join('')}<text x="153" y="35" class="radar-scale">10</text><text x="153" y="77" class="radar-scale">5</text></svg><div class="radar-key"><span><i class="selected-line"></i>Selected asset</span><span><i class="mean-line"></i>Filtered mean</span></div><p class="radar-name">${esc(selected.name_en)}</p><details class="chart-values"><summary>View pillar values</summary><table><thead><tr><th>Pillar</th><th>Asset</th><th>Mean</th></tr></thead><tbody>${keys.map((k,i)=>`<tr><td>${names[i]}</td><td>${selected.result.pillars[k].toFixed(2)}</td><td>${summary.count?summary.pillars[k].toFixed(2):'—'}</td></tr>`).join('')}</tbody></table></details>`;
  }
  function render(rows,selected,{sector='',onSector=()=>{}}={}){
    const summary=summarize(rows);
    document.getElementById('band-chart').innerHTML=bandMarkup(summary);
    document.getElementById('sector-chart').innerHTML=sectorMarkup(summary,sector);
    document.getElementById('radar-chart').innerHTML=radarMarkup(summary,selected);
    document.querySelectorAll('.sector-row').forEach(b=>b.onclick=()=>onSector(b.dataset.sector));
  }
  const api={summarize,bandMarkup,sectorMarkup,radarMarkup,render};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DashboardVisuals=api;
})(typeof window!=='undefined'?window:globalThis);
