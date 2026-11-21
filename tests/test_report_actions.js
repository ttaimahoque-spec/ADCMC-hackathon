'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync(require('node:path').join(__dirname,'../web/report.js'),'utf8');
function setup(protocol='http:'){
  const data={dashboard:{at:'2026-08-27T06:40:00+04:00'},scope:'portfolio',selected_asset:'AST-0001',selected_measure_ids:['M-SPARES'],scenario:{score_after:66.2}};
  const events={},downloads=[],blobs=[],details=[{open:false},{open:true}],online={hidden:false},status={textContent:''};
  const nodes=Object.fromEntries(['report-data','download-report','download-evidence','print-report','scope-link'].map(id=>[id,{}]));
  nodes['report-data'].textContent=JSON.stringify(data);
  const document={getElementById:id=>nodes[id],querySelectorAll:()=>details,querySelector:s=>s==='.online-actions'?online:status,documentElement:{outerHTML:'<html><svg>Frozen graph</svg></html>'},body:{appendChild(){}},createElement:()=>({click(){downloads.push({href:this.href,name:this.download});},remove(){}})};
  const window={addEventListener:(name,fn)=>events[name]=fn,print(){events.beforeprint();}};
  vm.runInNewContext(script,{document,window,location:{protocol},URLSearchParams,Blob,URL:{createObjectURL:b=>{blobs.push(b);return 'blob:test';},revokeObjectURL(){}},setTimeout:()=>{}});
  return {nodes,data,events,downloads,blobs,details,online,status};
}
test('report download freezes the rendered charts and keeps evidence JSON separate',async()=>{
  const app=setup();app.nodes['download-report'].onclick();
  assert.equal(app.downloads[0].name,'Sahil_Atlas_portfolio_2026-08-27.html');
  assert.match(await app.blobs[0].text(),/<!doctype html>[\s\S]*Frozen graph/);
  app.nodes['download-evidence'].onclick();
  assert.deepEqual(JSON.parse(await app.blobs[1].text()),app.data);
});
test('printing expands all history tables, then restores reader state',()=>{
  const app=setup();app.nodes['print-report'].onclick();
  assert.deepEqual(app.details.map(d=>d.open),[true,true]);
  app.events.afterprint();assert.deepEqual(app.details.map(d=>d.open),[false,true]);
  app.events.beforeprint();app.events.afterprint();assert.deepEqual(app.details.map(d=>d.open),[false,true]);
});
test('saved report works without app navigation and scope switching preserves the scenario',()=>{
  const app=setup('file:');assert.equal(app.online.hidden,true);assert.equal(app.status.textContent,'Saved offline snapshot');
  const query=new URLSearchParams(app.nodes['scope-link'].href.split('?')[1]);
  assert.equal(query.get('scope'),'selected');assert.equal(query.get('asset'),'AST-0001');assert.deepEqual(query.getAll('measure'),['M-SPARES']);
});
