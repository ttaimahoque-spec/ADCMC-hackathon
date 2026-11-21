/* All scores and scenarios are computed by the local Python engine. */
'use strict';
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sectorNames = {transport:'Transport',health:'Health',energy_water_wastewater:'Energy, water & wastewater',communications:'Communications',waste:'Waste',financial_services:'Financial services',security_and_safety:'Security & safety',food:'Food',government_facilities:'Government facilities'};
const colors = SahilAtlas.PALETTE;
let atlas, assetViewer;
const state = {data:null, selected:'AST-0001', filter:'all', tab:'overview', view:'overview', detail:null, measures:new Set(), detailRequest:0, scenarioRequest:0};
const number = value => new Intl.NumberFormat('en').format(value);
const money = value => 'AED ' + new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(value);
const date = value => new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Dubai',hour12:false}).format(new Date(value));
const badge = band => `<span class="badge ${band.toLowerCase()}">${escapeHTML(band)}</span>`;
const delta = value => value == null ? '<span class="delta">—</span>' : `<span class="delta ${value > 0 ? 'up' : value < 0 ? 'down' : ''}">${value > 0 ? '↑ +' : value < 0 ? '↓ ' : ''}${value}</span>`;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function showError(error) { $('#error').textContent = error.message || String(error); $('#error').hidden = false; }
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').hidden = true, 5000); }
async function guarded(action) {
  $('#error').hidden = true;
  try { await action(); } catch(error) { showError(error); }
}
function facility() { return state.data.facilities.find(f => f.asset_id === state.selected); }

async function refresh() {
  state.data = await api('/api/state');
  if (!state.data.facilities.some(f => f.asset_id === state.selected)) state.selected = state.data.facilities[0]?.asset_id;
  $('#city-name').textContent = state.data.city.city_en;
  $('#asof').textContent = date(state.data.at) + ' GST';
  $('#nav-warning-count').textContent = state.data.warnings.length;
  const selectedSector = $('#sector').value;
  $('#sector').innerHTML = '<option value="">All sectors</option>' + [...new Set(state.data.facilities.map(f => f.sector))].sort().map(s => `<option value="${escapeHTML(s)}">${escapeHTML(sectorNames[s] || s)}</option>`).join('');
  $('#sector').value = selectedSector;
  const isAfter = new Date(state.data.at) >= new Date('2026-08-27T06:30:00+04:00');
  $('#before').classList.toggle('selected', !isAfter); $('#after').classList.toggle('selected', isAfter);
  const bloom = state.data.warnings.find(w => w.risk_id === 'RSK-BLOOM-001');
  $('#banner-title').textContent = bloom ? (isAfter ? 'Coastal warning escalated · Red alert' : 'Before the warning · Baseline snapshot') : 'Day 87 · Demonstration snapshots';
  $('#banner-description').textContent = bloom ? (isAfter ? 'Algal bloom approaching the intake. Inspect the plant’s score and recovery options.' : 'The coastal warning is green. Replay the escalation to compare facility scores.') : 'Use the supplied scenario dates to compare portfolio snapshots.';
  renderMetrics(); renderTable(); renderScatter(); renderWarnings();
  if (state.view === 'methodology') await renderMethodology();
  await loadDetail();
}

function renderMetrics() {
  const rows = state.data.facilities.map(f => f.result);
  const high = rows.filter(r => ['High','Severe'].includes(r.band)).length;
  const review = rows.filter(r => r.review.proposed_checkup).length;
  const trusted = rows.filter(r => ['A','B'].includes(r.confidence)).length;
  const avg = rows.length ? rows.reduce((sum,r) => sum+r.score, 0)/rows.length : 0;
  const bands = Object.keys(colors).map(b => `<i style="flex:${rows.filter(r => r.band === b).length};background:${colors[b]}"></i>`).join('');
  const totalInputs = rows.reduce((sum,r) => sum + r.confidence_inputs.required,0);
  const currentInputs = rows.reduce((sum,r) => sum + r.confidence_inputs.current,0);
  $('#metrics').innerHTML = `
    <div class="metric"><span class="metric-symbol">▦</span><div class="metric-label">Facilities monitored</div><div class="metric-number">${rows.length}</div><div class="metric-foot">Across ${new Set(state.data.facilities.map(f => f.sector)).size} critical sectors</div></div>
    <div class="metric attention"><span class="metric-symbol">↗</span><div class="metric-label">High & severe risk</div><div class="metric-number">${high} <em>/ ${rows.length}</em></div><div class="metric-foot">${review} with a check-up proposed</div></div>
    <div class="metric"><span class="metric-symbol">◷</span><div class="metric-label">Average risk score</div><div class="metric-number">${avg.toFixed(1)} <em>/ 100</em></div><div class="mini-segments" aria-label="Risk-band distribution">${bands}</div></div>
    <div class="metric"><span class="metric-symbol">✓</span><div class="metric-label">Current evidence</div><div class="metric-number">${totalInputs ? Math.round(currentInputs/totalInputs*100) : 0}<em>%</em></div><div class="metric-foot">${trusted} facilities at confidence A or B</div></div>`;
  $('#review-count').textContent = review;
}

function filteredFacilities() {
  const query = $('#search').value.toLowerCase().trim();
  return [...state.data.facilities].sort((a,b) => b.result.score_exact - a.result.score_exact || a.asset_id.localeCompare(b.asset_id)).filter(f =>
    (!query || `${f.name_en} ${f.name_ar} ${f.asset_id}`.toLowerCase().includes(query)) &&
    (!$('#sector').value || f.sector === $('#sector').value) &&
    (!$('#category').value || f.category === Number($('#category').value)) &&
    (state.filter !== 'review' || f.result.review.proposed_checkup) &&
    (state.filter !== 'high' || ['High','Severe'].includes(f.result.band)));
}
function renderTable() {
  const rows = filteredFacilities();
  const fullRanks = new Map([...state.data.facilities].sort((a,b) => b.result.score_exact-a.result.score_exact || a.asset_id.localeCompare(b.asset_id)).map((f,i) => [f.asset_id,i+1]));
  $('#facility-count').textContent = state.data.facilities.length + ' facilities';
  $('#facility-rows').innerHTML = rows.map(f => `<tr class="${state.selected === f.asset_id ? 'selected' : ''}"><td class="rank">${String(fullRanks.get(f.asset_id)).padStart(2,'0')}</td><td><button class="asset-button" data-asset="${escapeHTML(f.asset_id)}" aria-pressed="${state.selected === f.asset_id}">${escapeHTML(f.name_en)}<span class="asset-meta">${escapeHTML(f.asset_id)} <span aria-hidden="true">·</span> Category ${f.category}</span></button></td><td><div class="score-cell"><strong>${f.result.score}</strong><span class="score-bar"><i style="width:${f.result.score}%;background:${colors[f.result.band]}"></i></span></div></td><td>${badge(f.result.band)}${f.result.override_applied ? '<span title="Category override applied"> *</span>' : ''}</td><td><span class="grade" title="${f.result.confidence_inputs.current} of ${f.result.confidence_inputs.required} inputs current">${f.result.confidence}</span></td><td>${delta(f.result.trend.d30)}</td></tr>`).join('');
  $('#no-results').hidden = rows.length > 0;
  $('#shown-count').textContent = `Showing ${rows.length} of ${state.data.facilities.length} facilities`;
  $$('.asset-button').forEach(button => button.onclick = () => guarded(async () => {
    state.selected = button.dataset.asset; state.measures.clear(); state.tab = 'overview'; renderTable(); renderScatter(); await loadDetail();
    if (innerWidth < 800) $('.model-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }));
}

async function loadDetail() {
  if (!state.selected) { $('#detail').innerHTML = '<div class="empty">No facilities in this dataset.</div>'; return; }
  const request = ++state.detailRequest;
  const detail = await api('/api/detail?asset=' + encodeURIComponent(state.selected));
  if (request !== state.detailRequest) return;
  state.detail = detail;
  renderDetail();
}
function renderDetail() {
  const f = facility(), r = f.result;
  const conf = r.confidence_inputs;
  const offset = 283 * (1-r.score/100);
  const trendText = r.trend.d7 == null ? 'No 7-day comparison available' : `${r.trend.d7 >= 0 ? '+' : ''}${r.trend.d7} points over 7 days`;
  $('#detail').innerHTML = `<div class="detail-top"><div class="detail-topline"><span>FACILITY PROFILE</span><span>${escapeHTML(f.asset_id)}</span></div><h2>${escapeHTML(f.name_en)}</h2><p class="detail-sub">${escapeHTML(sectorNames[f.sector])} <span aria-hidden="true">·</span> Category ${f.category}</p><div class="score-overview"><div class="score-ring"><svg viewBox="0 0 106 106" aria-hidden="true"><circle cx="53" cy="53" r="45" fill="none" stroke="#34465c" stroke-width="6"/><circle cx="53" cy="53" r="45" fill="none" stroke="${colors[r.band]}" stroke-width="6" stroke-dasharray="283" stroke-dashoffset="${offset}" stroke-linecap="round"/></svg><div class="ring-num">${r.score}<small>RISK SCORE / 100</small></div></div><div class="score-summary">${badge(r.band)}<p><strong>${escapeHTML(trendText)}</strong></p><p>${r.override_applied ? 'Category override applied' : 'Calculated from four pillars'}</p></div></div><div class="confidence-row"><span>Evidence confidence</span><strong>Grade ${r.confidence} <span aria-hidden="true">·</span> ${conf.current}/${conf.required} current</strong></div></div><div class="detail-tabs" role="tablist" aria-label="Facility detail"><button role="tab" data-tab="overview">Overview</button><button role="tab" data-tab="measures">Measures</button><button role="tab" data-tab="plans">Plans <small>${r.dependent_plans.length}</small></button><button role="tab" data-tab="history">History</button></div><div class="detail-content" role="tabpanel" id="detail-content"></div>`;
  $$('.detail-tabs button').forEach(b => { b.onclick = () => {state.tab=b.dataset.tab; renderDetailContent();}; });
  renderDetailContent();
}
function renderDetailContent() {
  $$('.detail-tabs button').forEach(b => {b.classList.toggle('active',b.dataset.tab===state.tab); b.setAttribute('aria-selected',String(b.dataset.tab===state.tab));});
  const f = facility(), r = f.result;
  const target = $('#detail-content');
  if (state.tab === 'overview') {
    target.innerHTML = `<div class="section-label"><h3>Four pillars of risk</h3><span>Scale 0–10</span></div>${[['T','Threat & exposure'],['V','Vulnerability'],['R','Recovery gap'],['C','Consequence']].map(([key,label]) => `<div class="pillar-row"><span class="pillar-label"><b>${key}</b>${label}</span><div class="pillar-track"><div class="pillar-fill" style="width:${r.pillars[key]*10}%;background:${key==='C'?'#949cff':key==='R'?'#e6cf77':'#69d6c4'}"></div></div><strong>${r.pillars[key].toFixed(2)}</strong></div>`).join('')}<div class="drivers"><div class="section-label"><h3>What is driving the score?</h3><span>Effect in points</span></div>${r.drivers.map((d,i) => `<div class="driver"><span class="driver-n">${i+1}</span><div class="driver-copy">${escapeHTML(d.factor)}<small>${d.kind === 'change' ? 'Input change' : 'Structural weakness'}</small></div><span class="driver-effect">${d.effect >= 0 ? '+' : ''}${d.effect.toFixed(1)}</span></div>`).join('') || '<p class="detail-note">No material drivers at this snapshot.</p>'}</div>${r.review.proposed_checkup ? '<div class="review-callout"><span>⚑</span><div><strong>Full check-up proposed</strong><p>Risk-band entry or a rise of 15+ points in 30 days.<br>Awaiting a named analyst’s decision.</p></div></div>' : ''}<button class="detail-action" id="explore-measures">Explore measures <span aria-hidden="true">↗</span></button><p class="detail-note">Driver effects are separate counterfactuals and should not be added together.</p>`;
    $('#explore-measures').onclick = () => {state.tab='measures';renderDetailContent();};
  } else if (state.tab === 'measures') {
    target.innerHTML = `<div class="section-label"><h3>Test an improvement scenario</h3><span>Current ${r.score_exact.toFixed(1)}</span></div><p class="detail-note">Select measures to recompute their combined effect. Base records stay unchanged.</p>${r.levers.map(l => `<label class="measure"><input type="checkbox" value="${escapeHTML(l.measure_id)}" ${state.measures.has(l.measure_id)?'checked':''} ${l.modeled?'':'disabled'}><span class="measure-info"><strong>${escapeHTML(l.measure)}</strong><small>${money(l.capex_aed)} capex · ${money(l.opex_aed_per_year)}/yr</small>${l.modeled?'':'<small>No input changes supplied; benefit not modeled.</small>'}</span><span class="measure-score">${l.score_after.toFixed(1)}<small>score after</small></span></label>`).join('') || '<div class="empty">No costed measures supplied for this facility.</div>'}<div id="scenario-result" class="scenario-result" aria-live="polite"></div><p class="detail-note">Planning estimates from the synthetic dataset. Measures are evaluated, never implemented automatically.</p>`;
    $$('.measure input').forEach(input => input.onchange = () => guarded(async () => {input.checked ? state.measures.add(input.value) : state.measures.delete(input.value); await updateScenario();}));
    guarded(updateScenario);
  } else if (state.tab === 'plans') {
    target.innerHTML = `<div class="section-label"><h3>Plans that rely on this facility</h3></div>${state.detail.plans.map(p => `<div class="plan"><strong>${escapeHTML(p.plan_id)} · § ${escapeHTML(p.section_ref)}</strong><p>${escapeHTML(p.assumption)}</p><small>Version ${escapeHTML(p.plan_version)} · ${escapeHTML(p.reliance)} reliance</small></div>`).join('') || '<div class="empty">No dependent plans in the supplied dataset.</div>'}<p class="detail-note">These are plan assumptions, not verified statements about current capability.</p>`;
  } else {
    const points = state.detail.history;
    target.innerHTML = `<div class="section-label"><h3>Score history</h3><span>${points.length} snapshots</span></div><div class="trend-stats">${[7,30,90].map(d => `<div>${d} days<strong>${r.trend['d'+d] == null ? '—' : (r.trend['d'+d] >= 0 ? '+' : '')+r.trend['d'+d]}</strong></div>`).join('')}</div>${lineChart(points)}<p class="detail-note">Warnings replayed against the supplied facility snapshot. Pilot records supply the early baseline.</p><details class="detail-note"><summary>Changes to source inputs (${(r.input_changes||[]).length})</summary><p>Compared with ${escapeHTML(r.change_comparison?.as_of || 'the previous day')}. Zero-point changes affect evidence or metadata only.</p>${(r.input_changes||[]).map(c=>`<div class="event"><strong>${escapeHTML(c.factor)}</strong><br>${escapeHTML(JSON.stringify(c.previous))} → ${escapeHTML(JSON.stringify(c.current))}<br>Effect ${c.effect >= 0 ? '+' : ''}${c.effect.toFixed(1)} points</div>`).join('') || '<p>No recorded facility or exposure changes for this comparison.</p>'}</details><div class="evidence-list"><h3>Evidence freshness</h3>${r.confidence_inputs.evidence.map(e => `<div class="evidence-line"><span>${escapeHTML(e.input)}</span><small title="${escapeHTML(e.reason)}">${e.current?'Current':'Needs review'}</small></div>`).join('')}</div><p class="detail-note">Computed ${escapeHTML(date(r.computed_at))} GST<br>Model ${escapeHTML(r.model_version)}</p><code class="hash">${escapeHTML(r.inputs_hash)}</code>`;
  }
}
async function updateScenario() {
  const request = ++state.scenarioRequest, asset = state.selected;
  const result = await api('/api/scenario',{asset_id:asset,measure_ids:[...state.measures]});
  if (request !== state.scenarioRequest || state.tab !== 'measures' || state.selected !== asset) return;
  const change = facility().result.score_exact - result.score_after;
  $('#scenario-result').innerHTML = `<div class="section-label"><h3>${state.measures.size ? 'Combined scenario' : 'Select measures above'}</h3>${badge(result.band)}</div><span class="big">${result.score_after.toFixed(1)}</span> <span class="detail-note">/ 100</span><p>${change.toFixed(1)} points lower · ${state.measures.size} selected measure${state.measures.size===1?'':'s'}</p><div class="measure-comparison"><div class="comparison-row"><span>Current</span><i><b style="width:${facility().result.score_exact}%"></b></i><strong>${facility().result.score_exact.toFixed(1)}</strong></div><div class="comparison-row"><span>Scenario</span><i><b style="width:${result.score_after}%"></b></i><strong>${result.score_after.toFixed(1)}</strong></div></div><div class="costs">${money(result.capex_aed)} capex · ${money(result.opex_aed_per_year)}/year opex</div>`;
}
function lineChart(points) {
  if (!points.length) return '<div class="empty">No score history available.</div>';
  const times = points.map(p => new Date(p.at).getTime());
  const low = Math.min(...times), range = Math.max(1,Math.max(...times)-low);
  const coords = points.map((p,i) => `${28+(times[i]-low)/range*270},${128-p.score*1.1}`).join(' ');
  return `<svg class="history-chart" viewBox="0 0 320 160" role="img" aria-label="Historical risk scores from ${points[0].score} to ${points.at(-1).score}">${[0,50,100].map(s => `<line x1="28" x2="302" y1="${128-s*1.1}" y2="${128-s*1.1}" stroke="#304259"/><text x="0" y="${131-s*1.1}" class="plot-label">${s}</text>`).join('')}<polyline fill="none" stroke="#77d8c5" stroke-width="2.5" points="${coords}"/><text x="28" y="153" class="plot-label">${escapeHTML(date(points[0].at).slice(0,6))}</text><text x="265" y="153" class="plot-label">${escapeHTML(date(points.at(-1).at).slice(0,6))}</text></svg>`;
}

function renderScatter() {
  const rows = filteredFacilities();
  const x=n=>48+n*4.82,y=n=>330-(n-2)*35;
  $('#scatter').innerHTML = `<svg viewBox="0 0 570 395" role="group" aria-label="Facility risk score versus consequence"><rect x="${x(60)}" y="42" width="${x(100)-x(60)}" height="288" fill="#362c2e"/>${[0,20,40,60,80,100].map(n => `<line x1="${x(n)}" x2="${x(n)}" y1="42" y2="330" stroke="#2a3c52"/><text x="${x(n)}" y="352" text-anchor="middle" class="plot-label">${n}</text>`).join('')}${[2,4,6,8,10].map(n => `<line x1="48" x2="530" y1="${y(n)}" y2="${y(n)}" stroke="#2b3f55"/><text x="32" y="${y(n)+4}" text-anchor="end" class="plot-label">${n}</text>`).join('')}<text x="290" y="382" text-anchor="middle" class="plot-label">RISK SCORE →</text><text x="48" y="20" class="plot-label">CONSEQUENCE</text><text x="518" y="30" text-anchor="end" class="plot-label">REVIEW ZONE ≥ 60</text>${rows.map(f => `<circle class="plot-point" data-asset="${escapeHTML(f.asset_id)}" tabindex="0" role="button" aria-label="${escapeHTML(f.name_en)}: score ${f.result.score}, consequence ${f.result.pillars.C}" cx="${x(f.result.score_exact)}" cy="${y(f.result.pillars.C)}" r="${f.asset_id===state.selected?7:4.5}" fill="${colors[f.result.band]}" fill-opacity=".9" stroke="${f.asset_id===state.selected?'#e5ffc1':'#16283b'}" stroke-width="${f.asset_id===state.selected?2:1}"><title>${escapeHTML(f.name_en)} · ${f.result.score} / consequence ${f.result.pillars.C}</title></circle>`).join('')}</svg><p class="chart-footnote">Points use exact scores; bands use published scores and overrides.</p>`;
  $$('.plot-point').forEach(p => {
    const select = () => guarded(async () => {await selectAsset(p.dataset.asset);$('.model-panel').scrollIntoView({behavior:'smooth',block:'start'});});
    p.onclick=select; p.onkeydown=e => {if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}};
  });
  renderVisuals(rows);
}

async function selectAsset(asset) {
  if (!state.data.facilities.some(f=>f.asset_id===asset)) return;
  state.selected=asset;state.tab='overview';state.measures.clear();
  renderTable();renderScatter();await loadDetail();
}
function renderVisuals(rows) {
  const selected=facility();
  DashboardVisuals.render(rows,selected,{sector:$('#sector').value,onSector:key=>{
    $('#sector').value=$('#sector').value===key?'':key;renderTable();renderScatter();
  }});
  atlas?.update(state.data.facilities,rows,state.selected);
  renderAssetModel(selected);
  $('#map-asset-count').textContent=`${rows.length} / ${state.data.facilities.length} ASSETS IN VIEW`;
  $('#map-focus').innerHTML='<option value="">Choose a facility</option>'+[...rows].sort((a,b)=>a.name_en.localeCompare(b.name_en)).map(f=>`<option value="${escapeHTML(f.asset_id)}">${escapeHTML(f.name_en)} · ${f.result.score}</option>`).join('');
  $('#map-focus').value=rows.some(f=>f.asset_id===state.selected)?state.selected:'';
  if(!selected){$('#map-selection').textContent='No facility selected.';return;}
  const visible=rows.some(f=>f.asset_id===selected.asset_id);
  const links=atlas?.links||[],upstream=links.filter(e=>e.to===selected.asset_id).length,downstream=links.filter(e=>e.from===selected.asset_id).length;
  $('#map-selection').innerHTML=`<span class="map-selected-icon">◈</span><div class="selection-brief"><strong>${escapeHTML(selected.name_en)}</strong><small>${escapeHTML(selected.asset_id)} · X ${selected.location.x_km} / Y ${selected.location.y_km} km · ${visible?`${upstream} upstream / ${downstream} downstream links in view`:'Outside current filters'}</small></div>${badge(selected.result.band)}`;
}
function syncModelControls({rotating,mode,part}) {
  $('#model-rotate').innerHTML=rotating?'Ⅱ <span>Pause rotation</span>':'▶ <span>Rotate model</span>';
  $('#model-rotate').setAttribute('aria-label',rotating?'Pause automatic model rotation':'Start automatic model rotation');
  $('#model-rotate').setAttribute('aria-pressed',String(rotating));
  $$('[data-model-mode]').forEach(b=>{b.classList.toggle('active',b.dataset.modelMode===mode);b.setAttribute('aria-pressed',String(b.dataset.modelMode===mode));});
  $$('[data-model-part]').forEach(b=>{b.classList.toggle('active',b.dataset.modelPart===part);b.setAttribute('aria-pressed',String(b.dataset.modelPart===part));});
}
function renderAssetModel(selected) {
  $('#model-focus').innerHTML=state.data.facilities.map(f=>`<option value="${escapeHTML(f.asset_id)}">${escapeHTML(f.name_en)}</option>`).join('');
  $('#model-focus').value=selected?.asset_id||'';
  if(!selected)return;
  assetViewer?.setFacility(selected);
  $('#model-name').textContent=selected.name_en;
  $('#model-type').textContent=assetViewer?.model.label||'Asset model';
  $('#model-live-score').innerHTML=`<i style="background:${colors[selected.result.band]}"></i>${selected.result.score} / 100 · ${escapeHTML(selected.result.band)} risk`;
  $('#model-parts').innerHTML=(assetViewer?.model.parts||[]).map(p=>`<button data-model-part="${p.id}" aria-pressed="false">◈ ${escapeHTML(p.label)}</button>`).join('');
  $$('[data-model-part]').forEach(b=>b.onclick=()=>assetViewer?.setPart(b.dataset.modelPart));
  if(assetViewer)syncModelControls(assetViewer);
}
function mapHover(f,p) {
  const tooltip=$('#map-tooltip');
  if(!f){tooltip.hidden=true;return;}
  tooltip.innerHTML=`<strong>${escapeHTML(f.name_en)}</strong><small>${escapeHTML(f.asset_id)} · ${escapeHTML(sectorNames[f.sector])}</small><span class="tooltip-score" style="color:${colors[f.result.band]}">${f.result.score} <small style="display:inline">${escapeHTML(f.result.band)} · Confidence ${f.result.confidence}</small></span><small>X ${f.location.x_km} / Y ${f.location.y_km} km</small>`;
  tooltip.hidden=false;
  const box=$('#map-stage').getBoundingClientRect();
  tooltip.style.left=Math.max(8,Math.min(p.x+15,box.width-tooltip.offsetWidth-8))+'px';
  tooltip.style.top=Math.max(8,Math.min(p.y+10,box.height-tooltip.offsetHeight-8))+'px';
}

function renderWarnings() {
  const channels = Object.fromEntries(state.data.channels.map(c => [c.channel_id,c.name_en]));
  const warnings = [...state.data.warnings].sort((a,b) => new Date(b.updated_at)-new Date(a.updated_at));
  $('#warnings-view').innerHTML = `<div class="page-heading"><div><div class="eyebrow">EARLY WARNING & CHANGE LOG</div><h1>Warning feed</h1><p>Latest open version of each risk at the selected snapshot.</p></div><div class="heading-actions"><button class="button" id="inputs-template">↓ Asset inputs</button><button class="button" id="inputs-upload">＋ Load asset inputs</button><button class="button primary" id="feed-upload">＋ Load warning</button></div></div><p class="detail-note">Asset inputs accept dated facility, exposure or city-population updates. Download the selected facility’s inputs, edit its source values and effective_at timestamp, then load the JSON. Base files remain unchanged; updates are recorded in history.</p><div class="warning-list">${warnings.map(w => `<article class="warning-card warning-${w.warning_level}"><span class="badge ${w.warning_level==='red'?'high':w.warning_level==='amber'?'elevated':'low'}">${escapeHTML(w.warning_level)} · ${escapeHTML(w.coverage)} coverage</span><h2>${escapeHTML(w.title)}</h2><p>${w.channels.map(c => escapeHTML(channels[c])).join(' · ')}</p><div class="warning-meta"><span>Likelihood ${Math.round(w.likelihood*100)}% · ${escapeHTML(w.horizon)} · ${escapeHTML(w.velocity)}</span><span>${escapeHTML(date(w.updated_at))}</span></div></article>`).join('') || '<p class="empty">No open warnings at this time.</p>'}</div><div class="panel event-log"><h2>Recent events</h2>${state.data.events.slice().reverse().map(e => `<div class="event"><strong>${e.versions} ${e.kind==='input_import'?'input update':'warning version'}${e.versions===1?'':'s'} loaded</strong> · ${e.affected.length} facilities rescored in ${e.elapsed_ms} ms<br>${escapeHTML(date(e.at))} GST</div>`).join('') || '<p class="detail-note">No files imported yet. Load a warning or dated asset inputs to record an update.</p>'}<details class="detail-note"><summary>Supplied warning version log (${state.data.warning_log.length} records)</summary>${state.data.warning_log.slice().sort((a,b)=>new Date(b.updated_at)-new Date(a.updated_at)).map(w=>`<div class="event">${escapeHTML(date(w.updated_at))} · ${escapeHTML(w.risk_id)} · ${escapeHTML(w.warning_level)} · ${escapeHTML(w.status || 'open')}</div>`).join('')}</details></div>`;
  $('#feed-upload').onclick = () => $('#warning-file').click();
  $('#inputs-upload').onclick = () => $('#inputs-file').click();
  $('#inputs-template').onclick = () => guarded(async () => {
    if (!state.selected) throw new Error('Select a facility first.');
    download(await api('/api/input-template?asset=' + encodeURIComponent(state.selected)), 'asset-input-update.json');
    toast('Edit the source values and effective_at timestamp, then load the JSON.');
  });
}

async function renderMethodology() {
  $('#methodology-view').innerHTML = `<div class="page-heading"><div><div class="eyebrow">TRANSPARENT BY DESIGN</div><h1>How the score works</h1><p>Four pillars. One reproducible score. Every assumption visible.</p></div></div><p class="page-copy">The resilience-risk score ranges from 0 to 100. Higher values mean higher risk. It is a prioritization measure, not a probability of failure. Input freshness is reported separately as confidence.</p><div class="formula">Score = 100 × (T × V × R × C / 10⁴)<sup>¼</sup></div><div class="method-grid"><article class="method-card"><h2>T · Threat & exposure</h2><p>For each exposed channel, select the strongest open risk. Combine as <code>10 × (1 − ∏(1 − p̂))</code>, where <code>p̂ = min(1, L × h × w × (0.85 + 0.30v))</code>. Warning versions are selected at or before the snapshot time.</p></article><article class="method-card"><h2>V · Vulnerability</h2><p><code>0.4 × audit mean + 0.3 × control gap + 0.3 × irreplaceability</code>. Unknown audit or control values score 10. A single point of failure scores 10; full redundancy scores 3.5.</p></article><article class="method-card"><h2>R · Recovery gap</h2><p>Ten times one minus the mean of six recovery facts: N−1 redundancy, buffer, recovery time, spares, protection plan and exercise. Unknown facts earn no recoverability credit.</p></article><article class="method-card"><h2>C · Consequence</h2><p>The maximum of the category score and ten times the larger supply or population share. Categories 1–5 score 10, 8, 6, 4 and 2. Population is read from the city adapter.</p></article><article class="method-card"><h2>Risk bands & overrides</h2><p>Low 0–19; Guarded 20–39; Elevated 40–59; High 60–79; Severe 80–100. A Category 1–2 facility with T, V or R ≥ 9 is at least High. Scores use full precision before rounding to whole points.</p></article><article class="method-card"><h2>Confidence & evidence</h2><p>A ≥90%; B ≥75%; C ≥50%; D below 50% of required inputs current. Mute or blind channel coverage reduces confidence. No-open-risk channels and verified continuity blocks follow the starter pack’s reference convention.</p></article></div><section class="panel sensitivity"><h2>Ranking sensitivity</h2><p class="detail-note">Each vulnerability weight is moved ±20%, with all three weights then normalized to sum to one. Loading results…</p><div id="sensitivity-results"></div></section><section class="method-card" style="margin-top:20px"><h2>Assumptions & limits</h2><p>The city and every facility are fictional. History starts from the supplied static baseline. Imported, dated input updates preserve later facility and exposure versions for replay. “Full exercise” is treated as current because the input format has no exercise date. Change drivers compare warnings, facility inputs, exposures and city population with the previous day. Unrecorded changes cannot be reconstructed. Some reference pillar display values vary by 0.01 due to rounding; the published scores, bands and confidence grades match. A zero pillar makes the geometric score zero, subject to the category override. A human analyst decides what happens next.</p></section>`;
  const values = await api('/api/sensitivity');
  const result = $('#sensitivity-results');
  if (!result) return;
  result.previousElementSibling.textContent = 'Each vulnerability weight is moved ±20%, then all three weights are normalized. Rankings use unrounded scores.';
  result.innerHTML = `<div class="table-wrap" style="margin-top:15px;max-height:none"><table><thead><tr><th>Weight change</th><th>Normalized weights (A / C / I)</th><th>Facilities moved</th><th>Largest rank change</th></tr></thead><tbody>${values.map(v => `<tr><td>${escapeHTML(v.label)}</td><td>${v.weights.map(w=>(w*100).toFixed(1)+'%').join(' / ')}</td><td>${v.moved}</td><td>${v.max_movement} places</td></tr>`).join('')}</tbody></table></div><details class="detail-note"><summary>Inspect individual rank movements</summary>${values.map(v => `<p style="margin-top:10px"><strong>${escapeHTML(v.label)}</strong><br>${v.changes.filter(c=>c.movement).map(c=>`${escapeHTML(c.asset_id)}: ${c.baseline} → ${c.rank}`).join(' · ') || 'No rank changes'}</p>`).join('')}</details>`;
}

function download(value, name) {
  const blob = new Blob([JSON.stringify(value,null,2)],{type:'application/json'});
  const url = URL.createObjectURL(blob), link=document.createElement('a');
  link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('#report').onclick = event => {
  if (!state.data) { event.preventDefault(); toast('Wait for the snapshot to load.'); return; }
  const query = new URLSearchParams({asset:state.selected || '',scope:'portfolio'});
  for (const id of state.measures) query.append('measure',id);
  $('#report').href = '/report?' + query.toString();
};
$('#export').onclick = () => guarded(async () => {download(await api('/api/export'),'asset-resilience-scores.json');toast('Score records exported with pillars, explanations and audit hashes.');});
$('#upload').onclick = () => $('#warning-file').click();
$('#warning-file').onchange = event => guarded(async () => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 2_000_000) throw new Error('Warning file must be smaller than 2 MB.');
    const records = JSON.parse(await file.text());
    const result = await api('/api/warnings',records);
    state.measures.clear(); await refresh();
    toast(`${result.affected.length} facilities rescored in ${result.elapsed_ms} ms. ${result.versions} new warning versions loaded.`);
  } finally { event.target.value=''; }
});
$('#inputs-file').onchange = event => guarded(async () => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 2_000_000) throw new Error('Input file must be smaller than 2 MB.');
    const result = await api('/api/inputs', JSON.parse(await file.text()));
    state.measures.clear(); await refresh();
    toast(`${result.versions} input update recorded; ${result.affected.length} facilities rescored.`);
  } finally { event.target.value=''; }
});
$$('[data-phase]').forEach(button => button.onclick = () => guarded(async () => {
  $$('[data-phase]').forEach(b=>b.disabled=true);
  try { await api('/api/replay',{phase:button.dataset.phase});state.measures.clear();await refresh();toast(button.dataset.phase==='before'?'Baseline snapshot loaded.':'Warning scenario loaded.'); }
  finally { $$('[data-phase]').forEach(b=>b.disabled=false); }
}));
$('#search').oninput = () => {renderTable();renderScatter();};
['#sector','#category'].forEach(s => $(s).onchange = () => {renderTable();renderScatter();});
$$('[data-filter]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;$$('[data-filter]').forEach(c=>c.classList.toggle('active',c===b));renderTable();renderScatter();});
$('#reset-filters').onclick=()=>{$('#search').value='';$('#sector').value='';$('#category').value='';state.filter='all';$$('[data-filter]').forEach(b=>b.classList.toggle('active',b.dataset.filter==='all'));renderTable();renderScatter();};
$$('[data-view]').forEach(button=>button.onclick=()=>guarded(async()=>{
  state.view=button.dataset.view;
  $$('[data-view]').forEach(b=>b.classList.toggle('active',b===button));
  ['overview','warnings','methodology'].forEach(v=>$('#'+v+'-view').hidden=v!==state.view);
  $('#view-title').textContent={overview:'Resilience atlas',warnings:'Warning feed',methodology:'Scoring methodology'}[state.view];
  if(state.view==='methodology')await renderMethodology();
  assetViewer?.setVisible(state.view==='overview');
  if(state.view==='overview')requestAnimationFrame(()=>{atlas?.resize();assetViewer?.resize();});
}));
try {
  atlas=new SahilAtlas.RiskAtlas($('#city-map'),{onSelect:asset=>guarded(async()=>{
    await selectAsset(asset);if(innerWidth<830)$('.model-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }),onHover:mapHover,onCamera:camera=>{
    $('#map-orbit').value=((camera.yaw*180/Math.PI+180)%360+360)%360-180;
    $('#map-tilt').value=camera.pitch*180/Math.PI;
    $('#map-top').textContent=camera.pitch>1.56?'3D':'2D';
    $('#map-top').setAttribute('aria-label',camera.pitch>1.56?'Return to 3D perspective':'View map from above');
  }});
} catch(error) {showError(error);}
$('#map-legend').innerHTML=Object.entries(colors).map(([band,color])=>`<span><i style="background:${color}"></i>${band}</span>`).join('');
$('#map-focus').onchange=e=>guarded(()=>selectAsset(e.target.value));
$('#map-links').onchange=e=>{if(atlas){atlas.showLinks=e.target.checked;atlas.draw();}};
$('#map-labels').onchange=e=>{if(atlas){atlas.showLabels=e.target.checked;atlas.draw();}};
$('#map-zoom-in').onclick=()=>atlas?.zoom(1.15);
$('#map-zoom-out').onclick=()=>atlas?.zoom(1/1.15);
$('#map-reset').onclick=()=>atlas?.reset();
$('#map-top').onclick=()=>{if(atlas?.camera.pitch>1.56)atlas.reset();else atlas?.top();};
$('#map-orbit').oninput=e=>atlas?.orbit(Number(e.target.value));
$('#map-tilt').oninput=e=>atlas?.tilt(Number(e.target.value));
try {
  assetViewer=new SahilAsset3D.AssetViewer($('#asset-model'),{onChange:syncModelControls});
} catch(error) {
  $('#model-note').textContent='The 3D viewer could not initialize in this browser. All facility data and scoring controls remain available.';
  $('#model-rotate').disabled=true;
}
$('#model-focus').onchange=e=>guarded(()=>selectAsset(e.target.value));
$('#model-rotate').onclick=()=>assetViewer?.setRotation(!assetViewer.rotating);
$('#model-zoom-in').onclick=()=>assetViewer?.zoom(1.12);
$('#model-zoom-out').onclick=()=>assetViewer?.zoom(1/1.12);
$('#model-reset').onclick=()=>assetViewer?.reset();
$$('[data-model-mode]').forEach(b=>b.onclick=()=>assetViewer?.setMode(b.dataset.modelMode));
$('#model-expand').hidden=!document.fullscreenEnabled;
$('#model-expand').onclick=()=>guarded(async()=>{
  if(document.fullscreenElement)await document.exitFullscreen();else await $('#model-stage').requestFullscreen();
});
document.addEventListener('fullscreenchange',()=>{
  const expanded=document.fullscreenElement===$('#model-stage');
  $('#model-expand').setAttribute('aria-pressed',String(expanded));
  $('#model-expand').setAttribute('aria-label',expanded?'Exit expanded 3D view':'Expand 3D viewer');
  requestAnimationFrame(()=>assetViewer?.resize());
});
guarded(refresh);
// Pick up the daily server run in live mode without disrupting active controls.
setInterval(()=>guarded(async()=>{const data=await api('/api/state');if(data.at!==state.data?.at)await refresh();}),30000);
