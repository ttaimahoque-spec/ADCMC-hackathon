/* Optional Node.js checks. No packages required; the app itself needs no Node.js. */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {RiskAtlas,bounds,project,heightFor,connections} = require('../web/map3d.js');
const {summarize,bandMarkup,sectorMarkup,radarMarkup} = require('../web/visuals.js');
const facilities = require('../data/facilities.json');
const scores = require('../examples/scores_after.json');
const scoreById = new Map(scores.map(s=>[s.asset_id,s]));
const rows = facilities.map(f=>({...f,result:scoreById.get(f.asset_id)}));

function canvas(width=1050,height=500) {
  const handlers={};
  const context = new Proxy({
    measureText:s=>({width:s.length*6}),
    createRadialGradient:()=>({addColorStop:()=>{}})
  }, {get:(obj,key)=>key in obj?obj[key]:()=>{}});
  return {width,height,style:{},dataset:{},handlers,
    getContext:()=>context, getBoundingClientRect:()=>({width,height,left:0,top:0}),
    addEventListener:(name,fn)=>handlers[name]=fn,focus:()=>{},
    setPointerCapture:()=>{},hasPointerCapture:()=>false};
}

test('atlas keeps every supplied facility inside the initial desktop and mobile viewport',()=>{
  for(const [w,h] of [[1050,500],[360,370]]) {
    const c=canvas(w,h),atlas=new RiskAtlas(c);
    atlas.update(rows,rows,'AST-0001');
    assert.equal(c.dataset.pointCount,'60');
    assert.equal(new Set(atlas.points.map(p=>p.asset_id)).size,60);
    for(const p of atlas.points) {
      assert.ok(p.x>0&&p.x<w&&p.y>0&&p.y<h,`${w}px: ${p.asset_id}`);
      assert.ok(Number.isFinite(p.depth));
    }
  }
});

test('top view preserves local coordinate directions; score controls vertical extrusion',()=>{
  const b=bounds(rows),camera={yaw:0,pitch:Math.PI/2,zoom:1};
  const p=project([10,10,0],camera,b,800,500);
  const east=project([15,10,0],camera,b,800,500);
  const south=project([10,15,0],camera,b,800,500);
  assert.ok(east.x>p.x);assert.equal(east.y,p.y);
  assert.ok(south.y>p.y);assert.equal(south.x,p.x);
  assert.ok(heightFor(rows[0],b)>heightFor({...rows[0],result:{score:20}},b));
  const perspective={...camera,pitch:Math.PI/4};
  assert.ok(project([10,10,8],perspective,b,800,500).y<project([10,10,0],perspective,b,800,500).y);
});

test('selected links are actual upstream relationships and never point to filtered-out assets',()=>{
  const edges=connections(rows,rows,'AST-0001');
  assert.equal(edges.filter(e=>e.to==='AST-0001').length,3);
  assert.equal(edges.filter(e=>e.from==='AST-0001').length,2);
  for(const e of edges)assert.ok(rows.find(f=>f.asset_id===e.to).dependencies.some(d=>d.upstream_asset_id===e.from));
  assert.deepEqual(connections(rows,[rows[0]],'AST-0001'),[]);
  assert.deepEqual(connections(rows,[],null),[]);
});

test('click selects a facility, while dragging or cancellation does not select',()=>{
  const selected=[],c=canvas(),atlas=new RiskAtlas(c,{onSelect:id=>selected.push(id)});
  atlas.update(rows,[rows[0]],rows[0].asset_id);
  const p=atlas.points[0];
  const event={button:0,pointerId:1,clientX:p.x,clientY:p.y,type:'pointerup'};
  c.handlers.pointerdown(event);c.handlers.pointerup(event);
  assert.deepEqual(selected,[rows[0].asset_id]);
  c.handlers.pointerdown(event);c.handlers.pointermove({...event,clientX:p.x+40});c.handlers.pointerup(event);
  assert.equal(selected.length,1);
  c.handlers.pointerdown(event);c.handlers.pointercancel({...event,type:'pointercancel'});
  assert.equal(selected.length,1);
});

test('keyboard camera controls, zoom bounds and empty filters remain usable',()=>{
  const c=canvas(),atlas=new RiskAtlas(c);let prevented=0;
  atlas.update(rows,rows,'AST-0001');
  const yaw=atlas.camera.yaw;
  c.handlers.keydown({key:'ArrowRight',preventDefault:()=>prevented++});
  assert.ok(atlas.camera.yaw>yaw);assert.equal(prevented,1);
  atlas.zoom(100);assert.ok(atlas.camera.zoom<=2.5);
  atlas.zoom(.0001);assert.ok(atlas.camera.zoom>=.65);
  atlas.tilt(-100);assert.ok(atlas.camera.pitch>0);
  atlas.top();assert.equal(atlas.camera.pitch,Math.PI/2);
  c.handlers.keydown({key:'Home',preventDefault:()=>{}});
  assert.equal(atlas.camera.zoom,1);assert.ok(atlas.camera.pitch<Math.PI/2);
  atlas.update(rows,[],'AST-0001');
  assert.equal(c.dataset.pointCount,'0');assert.equal(c.dataset.visibleLinks,'0');
  assert.equal(atlas.hit(400,250),null);
});

test('band and sector summaries account for all filtered engine outputs without mutation',()=>{
  const original=JSON.stringify(rows),summary=summarize(rows);
  assert.equal(summary.count,60);
  assert.equal(Object.values(summary.bands).reduce((a,b)=>a+b,0),60);
  assert.equal(summary.sectors.reduce((n,s)=>n+s.count,0),60);
  assert.equal(summary.sectors.length,9);
  const single=summarize([rows[0]]);
  assert.equal(single.bands.High,1);
  assert.equal(single.sectors[0].mean,70.9);
  assert.deepEqual(single.pillars,rows[0].result.pillars);
  assert.equal(JSON.stringify(rows),original);
});

test('visuals handle empty filters and category overrides without inventing means',()=>{
  const empty=summarize([]);
  for(const markup of [bandMarkup(empty),sectorMarkup(empty,''),radarMarkup(empty,rows[0])]) {
    assert.ok(!markup.includes('NaN'));assert.ok(!markup.includes('Infinity'));
  }
  assert.match(sectorMarkup(empty,''),/No facilities/);
  const override={...rows[0],result:{...rows[0].result,score:0,score_exact:0,band:'High'}};
  assert.equal(summarize([override]).bands.High,1);
});

test('facility labels in generated charts are escaped',()=>{
  const hostile={...rows[0],name_en:'<img src=x onerror="alert(1)">',sector:'<script>'};
  const summary=summarize([hostile]);
  assert.ok(!radarMarkup(summary,hostile).includes('<img'));
  assert.ok(radarMarkup(summary,hostile).includes('&lt;img'));
  assert.ok(!sectorMarkup(summary,'').includes('<script>'));
  assert.ok(sectorMarkup(summary,'').includes('&lt;script&gt;'));
});
