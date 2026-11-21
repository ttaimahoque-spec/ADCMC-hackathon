'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {AssetViewer,buildModel,archetype,project}=require('../web/asset3d.js');
const {SoftwareRenderer}=require('../web/asset-renderer.js');
const facilities=require('../data/facilities.json');
const scores=new Map(require('../examples/scores_after.json').map(r=>[r.asset_id,r]));
const rows=facilities.map(f=>({...f,result:scores.get(f.asset_id)}));
function canvas(width=160,height=110){
  const handlers={},gradient={addColorStop:()=>{}};
  const c={width,height,style:{},dataset:{},handlers,focus:()=>{},matches:()=>true,setAttribute:()=>{},
    getBoundingClientRect:()=>({width,height}),addEventListener:(name,fn)=>handlers[name]=fn,
    removeEventListener:name=>delete handlers[name],setPointerCapture:()=>{},hasPointerCapture:()=>false};
  const context=new Proxy({createRadialGradient:()=>gradient,
    getImageData:()=>({data:new Uint8ClampedArray(c.width*c.height*4)}),putImageData:image=>c.pixels=image.data},
    {get:(obj,key)=>key in obj?obj[key]:()=>{}});
  c.getContext=type=>type==='2d'?context:null;return c;
}

test('all 60 assets get deterministic, finite illustrative geometry without changing source data',()=>{
  const snapshot=JSON.stringify(rows),types=new Set();
  for(const f of rows){
    const model=buildModel(f);types.add(model.type);assert.ok(model.faces.length>100);
    for(const face of model.faces){
      assert.ok(face.vertices.length>=3);
      assert.ok(face.vertices.flat().every(Number.isFinite));
      assert.ok(Math.abs(Math.hypot(...face.normal)-1)<1e-8);
    }
    assert.ok(model.parts.every(part=>model.faces.some(face=>face.group===part.id)));
    assert.deepEqual(buildModel({...f,result:{...f.result,score:0,band:'Low'}}),model,'risk must not invent building dimensions');
  }
  assert.equal(types.size,10);assert.equal(JSON.stringify(rows),snapshot);
});

test('building types follow facility metadata and fall back for unknown facilities',()=>{
  for(const [id,type]of [['AST-0001','plant'],['AST-0002','substation'],['AST-0006','hospital'],['AST-0036','tower'],['AST-0020','communications'],['AST-0059','solar']])assert.equal(archetype(rows.find(f=>f.asset_id===id)),type);
  assert.equal(archetype({asset_id:'UNSEEN',name_en:'New Facility',sector:'new'}),'commercial');
});

test('a full rotation keeps the initial model inside desktop and mobile stage bounds',()=>{
  const models=[...new Map(rows.map(f=>[archetype(f),buildModel(f)])).values()];
  for(const [w,h] of [[850,540],[350,390]])for(const model of models)for(let degrees=0;degrees<360;degrees+=30){
    const cam={yaw:degrees*Math.PI/180,pitch:26*Math.PI/180,zoom:1};
    for(const face of model.faces)for(const v of face.vertices){
      const p=project(v,cam,w,h,model.target);
      assert.ok(p.x>4&&p.x<w-4&&p.y>30&&p.y<h-20,`${model.type}, ${w}px, ${degrees}°: ${JSON.stringify(p)}`);
    }
  }
});

test('depth buffer shows near geometry regardless of submission order',()=>{
  const c=canvas(80,80),renderer=new SoftwareRenderer(c),shape=depth=>[{x:10,y:10,depth},{x:70,y:10,depth},{x:40,y:70,depth}];
  const far={points:shape(0),color:[0,0,255]},near={points:shape(8),color:[255,0,0]};
  for(const triangles of [[far,near],[near,far]]){
    renderer.draw(triangles,80,80,{x:40,y:40,rx:30,ry:10});
    assert.deepEqual([...c.pixels.slice((30*80+40)*4,(30*80+40)*4+4)],[255,0,0,255]);
  }
});

test('facility selection swaps models and risk tint does not change geometry',()=>{
  const c=canvas(),v=new AssetViewer(c,{reducedMotion:true});v.setFacility(rows[0]);
  assert.equal(c.dataset.modelType,'plant');const model=v.model;
  v.setMode('risk');assert.equal(c.dataset.viewMode,'risk');assert.equal(v.model,model);
  v.setFacility(rows[1]);assert.equal(c.dataset.assetId,'AST-0002');assert.equal(c.dataset.modelType,'substation');
  v.setPart('equipment');assert.equal(v.part,'equipment');v.setPart('equipment');assert.equal(v.part,'');v.destroy();
});

test('drag, keyboard and zoom controls pause motion and stay bounded',()=>{
  const c=canvas(),v=new AssetViewer(c);v.setFacility(rows[0]);
  const yaw=v.camera.yaw;let prevented=0;
  c.handlers.pointerdown({button:0,pointerId:1,clientX:40,clientY:40});
  c.handlers.pointermove({pointerId:1,clientX:80,clientY:400});
  c.handlers.pointerup({pointerId:1});
  assert.ok(v.camera.yaw>yaw);assert.ok(v.camera.pitch<=75*Math.PI/180);assert.equal(v.rotating,false);
  c.handlers.keydown({key:'Home',preventDefault:()=>prevented++});assert.equal(v.camera.zoom,1);assert.equal(prevented,1);
  c.handlers.keydown({key:' ',preventDefault:()=>{}});assert.equal(v.rotating,true);
  v.zoom(100);assert.equal(v.camera.zoom,1.65);v.zoom(.0001);assert.equal(v.camera.zoom,.65);v.destroy();
});

test('animation pauses when hidden, honors reduced motion and releases callbacks',()=>{
  const oldRaf=global.requestAnimationFrame,oldCancel=global.cancelAnimationFrame;
  let next=0;const callbacks=new Map();
  global.requestAnimationFrame=fn=>{const id=++next;callbacks.set(id,fn);return id;};global.cancelAnimationFrame=id=>callbacks.delete(id);
  try{
    const c=canvas(),v=new AssetViewer(c,{reducedMotion:true});v.setFacility(rows[0]);
    assert.equal(v.rotating,false);assert.equal(callbacks.size,0);
    v.setRotation(true);assert.equal(callbacks.size,1);
    const advance=time=>{const [id,fn]=callbacks.entries().next().value;callbacks.delete(id);fn(time);};
    const yaw=v.camera.yaw;advance(0);advance(50);assert.ok(v.camera.yaw>yaw);
    v.setVisible(false);assert.equal(callbacks.size,0);v.setVisible(true);assert.equal(callbacks.size,1);
    v.setRotation(false);assert.equal(c.dataset.rotating,'false');assert.equal(callbacks.size,0);
    v.destroy();assert.equal(Object.keys(c.handlers).length,0);
  }finally{global.requestAnimationFrame=oldRaf;global.cancelAnimationFrame=oldCancel;}
});
