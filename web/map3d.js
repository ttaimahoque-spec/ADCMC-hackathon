/* Offline 3D risk atlas. Orthographic 3D projection rendered with Canvas 2D.
   Coordinates come from the adapter; Z is a score encoding, never real elevation.
   No network, map tiles, external packages or fabricated facility locations. */
(function(root) {
  'use strict';
  const PALETTE = {Low:'#65d6ae',Guarded:'#73b5fa',Elevated:'#e6cf77',High:'#ff9b74',Severe:'#fb6f91'};
  const DEG = Math.PI/180;
  const clamp = (n,lo,hi) => Math.min(hi,Math.max(lo,n));
  function bounds(rows) {
    const valid=rows.filter(f=>Number.isFinite(f.location?.x_km)&&Number.isFinite(f.location?.y_km));
    if(!valid.length) return {minX:0,maxX:40,minY:0,maxY:35,cx:20,cy:17.5,span:40};
    const x=valid.map(f=>f.location.x_km),y=valid.map(f=>f.location.y_km);
    const minX=Math.floor(Math.min(...x)/5)*5-2,maxX=Math.ceil(Math.max(...x)/5)*5+2;
    const minY=Math.floor(Math.min(...y)/5)*5-2,maxY=Math.ceil(Math.max(...y)/5)*5+2;
    return {minX,maxX,minY,maxY,cx:(minX+maxX)/2,cy:(minY+maxY)/2,span:Math.max(maxX-minX,maxY-minY,10)};
  }
  function project(point,camera,box,width,height) {
    const x=point[0]-box.cx,y=point[1]-box.cy,z=point[2]||0;
    const u=x*Math.cos(camera.yaw)-y*Math.sin(camera.yaw);
    const v=x*Math.sin(camera.yaw)+y*Math.cos(camera.yaw);
    const scale=Math.min(width/(box.span*1.55),height/(box.span*1.05))*camera.zoom;
    return {x:width/2+u*scale,y:height*.57+(v*Math.sin(camera.pitch)-z*Math.cos(camera.pitch))*scale,
      depth:v*Math.cos(camera.pitch)+z*Math.sin(camera.pitch),scale};
  }
  function heightFor(facility,box) {return clamp(facility.result.score,0,100)/100*box.span*.19;}
  function inside(point,polygon) {
    let yes=false;
    for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
      const a=polygon[i],b=polygon[j];
      if((a.y>point.y)!==(b.y>point.y)&&point.x<(b.x-a.x)*(point.y-a.y)/(b.y-a.y)+a.x)yes=!yes;
    } return yes;
  }
  function connections(all,visible,selected) {
    const shown=new Set(visible.map(f=>f.asset_id)),known=new Set(all.map(f=>f.asset_id)),edges=[];
    for(const f of all)for(const d of f.dependencies||[]){
      if((f.asset_id===selected||d.upstream_asset_id===selected)&&shown.has(f.asset_id)&&shown.has(d.upstream_asset_id)&&known.has(d.upstream_asset_id))
        edges.push({from:d.upstream_asset_id,to:f.asset_id,kind:d.kind});
    } return edges;
  }
  function shade(hex,factor){return '#'+hex.slice(1).match(/../g).map(v=>Math.round(clamp(parseInt(v,16)*factor,0,255)).toString(16).padStart(2,'0')).join('');}

  class RiskAtlas {
    constructor(canvas,{onSelect=()=>{},onHover=()=>{},onCamera=()=>{}}={}) {
      this.canvas=canvas;this.ctx=canvas.getContext('2d');
      if(!this.ctx)throw new Error('This browser cannot render the map. Use the facility priority table.');
      this.onSelect=onSelect;this.onHover=onHover;this.onCamera=onCamera;
      this.camera={yaw:-28*DEG,pitch:37*DEG,zoom:1};this.all=[];this.rows=[];
      this.selected=null;this.hovered=null;this.showLinks=true;this.showLabels=true;
      this.box=bounds([]);this.width=800;this.height=480;this.hitFaces=[];this.points=[];this.links=[];
      this.bind();
      if(typeof ResizeObserver!=='undefined'){this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(canvas);}
      this.resize();
    }
    bind(){
      const c=this.canvas;
      c.addEventListener('pointerdown',e=>{
        if(e.button!==0||e.isPrimary===false)return;
        c.focus({preventScroll:true});c.setPointerCapture?.(e.pointerId);
        this.drag={id:e.pointerId,x:e.clientX,y:e.clientY,yaw:this.camera.yaw,pitch:this.camera.pitch,moved:false};
      });
      c.addEventListener('pointermove',e=>{
        if(this.drag&&e.pointerId===this.drag.id){
          const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;
          if(Math.hypot(dx,dy)>5)this.drag.moved=true;
          if(this.drag.moved){this.camera.yaw=this.drag.yaw+dx*.008;this.camera.pitch=clamp(this.drag.pitch+dy*.006,20*DEG,90*DEG);this.hovered=null;this.onHover(null);this.changed();}
        }else{
          const p=this.local(e),hit=this.hit(p.x,p.y);this.hovered=hit?.asset_id||null;
          c.style.cursor=hit?'pointer':'grab';this.onHover(hit,p);this.draw();
        }
      });
      const end=e=>{
        if(!this.drag||e.pointerId!==this.drag.id)return;
        const dragged=this.drag.moved;this.drag=null;
        if(c.hasPointerCapture?.(e.pointerId))c.releasePointerCapture(e.pointerId);
        if(!dragged&&e.type==='pointerup'){const p=this.local(e),hit=this.hit(p.x,p.y);if(hit)this.onSelect(hit.asset_id);}
      };
      c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);
      c.addEventListener('lostpointercapture',()=>{this.drag=null;});
      c.addEventListener('pointerleave',()=>{if(!this.drag){this.hovered=null;this.onHover(null);this.draw();}});
      c.addEventListener('keydown',e=>{
        const key=e.key;let used=true;
        if(key==='ArrowLeft')this.camera.yaw-=.12;
        else if(key==='ArrowRight')this.camera.yaw+=.12;
        else if(key==='ArrowUp')this.camera.pitch=clamp(this.camera.pitch+.08,20*DEG,90*DEG);
        else if(key==='ArrowDown')this.camera.pitch=clamp(this.camera.pitch-.08,20*DEG,90*DEG);
        else if(key==='+'||key==='=')this.camera.zoom=clamp(this.camera.zoom*1.13,.65,2.5);
        else if(key==='-')this.camera.zoom=clamp(this.camera.zoom/1.13,.65,2.5);
        else if(key==='Home')this.camera={yaw:-28*DEG,pitch:37*DEG,zoom:1};
        else used=false;
        if(used){e.preventDefault();this.changed();}
      });
    }
    local(e){const r=this.canvas.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};}
    update(all,visible,selected){
      this.all=all;this.rows=visible;this.selected=selected;this.box=bounds(all);
      this.links=connections(all,visible,selected);this.hovered=null;this.onHover(null);this.resize();
    }
    resize(){
      const r=this.canvas.getBoundingClientRect();if(r.width<1||r.height<1)return;
      this.width=r.width;this.height=r.height;
      const dpr=Math.min(root.devicePixelRatio||1,2);
      this.canvas.width=Math.round(r.width*dpr);this.canvas.height=Math.round(r.height*dpr);
      this.ctx.setTransform(dpr,0,0,dpr,0,0);this.draw();
    }
    changed(){this.draw();this.onCamera({...this.camera});}
    reset(){this.camera={yaw:-28*DEG,pitch:37*DEG,zoom:1};this.changed();}
    zoom(factor){this.camera.zoom=clamp(this.camera.zoom*factor,.65,2.5);this.changed();}
    top(){this.camera.pitch=90*DEG;this.camera.yaw=0;this.changed();}
    orbit(degrees){this.camera.yaw=degrees*DEG;this.changed();}
    tilt(degrees){this.camera.pitch=clamp(degrees,20,90)*DEG;this.changed();}
    p(x,y,z=0){return project([x,y,z],this.camera,this.box,this.width,this.height);}
    path(points){const c=this.ctx;c.beginPath();points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.closePath();}
    polygon(points,fill,stroke,line=1){const c=this.ctx;this.path(points);if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.lineWidth=line;c.stroke();}}
    line(points,color,width=1,dash=[]){const c=this.ctx;c.beginPath();points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.stroke();c.setLineDash([]);}
    ground(){
      const c=this.ctx,b=this.box;
      const corners=[[b.minX,b.minY],[b.maxX,b.minY],[b.maxX,b.maxY],[b.minX,b.maxY]];
      const floor=corners.map(([x,y])=>this.p(x,y));
      const sides=corners.map((xy,i)=>{
        const next=corners[(i+1)%4];const pts=[this.p(...xy),this.p(...next),this.p(...next,-.6),this.p(...xy,-.6)];
        return {pts,depth:pts.reduce((s,p)=>s+p.depth,0)/4};
      }).sort((a,b)=>a.depth-b.depth);
      for(const s of sides)this.polygon(s.pts,'#0c182b','#20344b');
      this.polygon(floor,'#14243a','#345069',1.3);
      c.save();this.path(floor);c.clip();
      const step=b.span>100?Math.ceil(b.span/50):1;
      for(let x=Math.ceil(b.minX/step)*step;x<=b.maxX;x+=step)this.line([this.p(x,b.minY),this.p(x,b.maxY)],x%(step*5)===0?'#2b4259':'#1c3149',.7);
      for(let y=Math.ceil(b.minY/step)*step;y<=b.maxY;y+=step)this.line([this.p(b.minX,y),this.p(b.maxX,y)],y%(step*5)===0?'#2b4259':'#1c3149',.7);
      c.restore();
      c.font='10px ui-monospace, monospace';c.textAlign='center';c.fillStyle='#7595ad';
      const tick=Math.max(5,Math.ceil(b.span/40)*5);
      for(let x=Math.ceil(b.minX/tick)*tick;x<=b.maxX;x+=tick){const p=this.p(x,b.maxY+1.3);c.fillText(String(x),p.x,p.y);}
      for(let y=Math.ceil(b.minY/tick)*tick;y<=b.maxY;y+=tick){const p=this.p(b.minX-1.3,y);c.fillText(String(y),p.x,p.y);}
      const xp=this.p(b.maxX+1,b.maxY+2),yp=this.p(b.minX-2,b.minY-1);
      c.fillStyle='#a4c0d3';c.fillText('X / km',xp.x,xp.y+12);c.fillText('Y / km',yp.x,yp.y-5);
    }
    drawLinks(){
      if(!this.showLinks)return;
      const byId=new Map(this.all.map(f=>[f.asset_id,f]));
      for(const edge of this.links){
        const a=byId.get(edge.from),b=byId.get(edge.to),path=[];
        for(let i=0;i<=30;i++){
          const t=i/30,x=a.location.x_km+(b.location.x_km-a.location.x_km)*t,y=a.location.y_km+(b.location.y_km-a.location.y_km)*t;
          path.push(this.p(x,y,.2+Math.sin(Math.PI*t)*this.box.span*.025));
        }
        const color=edge.to===this.selected?'#78c6fa':'#baeba2';this.line(path,color,1.6,[4,4]);
        const end=path[23],prev=path[21],angle=Math.atan2(end.y-prev.y,end.x-prev.x);
        this.polygon([end,{x:end.x-7*Math.cos(angle-.5),y:end.y-7*Math.sin(angle-.5)},{x:end.x-7*Math.cos(angle+.5),y:end.y-7*Math.sin(angle+.5)}],color);
      }
    }
    draw(){
      const c=this.ctx,w=this.width,h=this.height;
      c.clearRect(0,0,w,h);
      const bg=c.createRadialGradient(w*.5,h*.45,20,w*.5,h*.5,w*.72);
      bg.addColorStop(0,'#14243a');bg.addColorStop(1,'#0b1424');c.fillStyle=bg;c.fillRect(0,0,w,h);
      this.ground();this.drawLinks();this.hitFaces=[];this.points=[];
      const faces=[],b=this.box,half=b.span*.0105;
      for(const f of this.rows){
        const {x_km:x,y_km:y}=f.location,z=heightFor(f,b),color=PALETTE[f.result.band]||'#73b5fa';
        const selected=f.asset_id===this.selected,hovered=f.asset_id===this.hovered;
        const floor=this.p(x,y),top=this.p(x,y,z);
        this.points.push({asset_id:f.asset_id,x:top.x,y:top.y,baseX:floor.x,baseY:floor.y,depth:top.depth});
        if(selected){
          const circle=Array.from({length:49},(_,i)=>this.p(x+half*2.6*Math.cos(i/48*Math.PI*2),y+half*2.6*Math.sin(i/48*Math.PI*2),.02));
          this.line(circle,'#e0ffb4',2);this.line([floor,top],'#d6f7a5',1,[3,4]);
        }
        const coords=[[x-half,y-half,0],[x+half,y-half,0],[x+half,y+half,0],[x-half,y+half,0],
          [x-half,y-half,z],[x+half,y-half,z],[x+half,y+half,z],[x-half,y+half,z]];
        const p=coords.map(q=>this.p(...q));
        const definitions=[[[0,1,5,4],.59],[[1,2,6,5],.78],[[2,3,7,6],.69],[[3,0,4,7],.48],[[4,5,6,7],1]];
        for(const [indices,factor]of definitions){
          const poly=indices.map(i=>p[i]);faces.push({f,poly,fill:shade(color,factor),stroke:selected?'#e7ffc4':hovered?'#e5f2ff':shade(color,.85),
            line:selected||hovered?1.35:.5,depth:poly.reduce((s,p)=>s+p.depth,0)/4});
        }
      }
      faces.sort((a,b)=>a.depth-b.depth);
      for(const face of faces){this.polygon(face.poly,face.fill,face.stroke,face.line);this.hitFaces.push(face);}
      if(this.showLabels){
        const important=new Set([...this.rows].sort((a,b)=>b.result.score-a.result.score).slice(0,2).map(f=>f.asset_id));
        important.add(this.selected);if(this.hovered)important.add(this.hovered);
        const labels=[];
        for(const f of [...this.rows].sort((a,b)=>Number(a.asset_id===this.selected)-Number(b.asset_id===this.selected))){
          if(!important.has(f.asset_id))continue;
          const p=this.p(f.location.x_km,f.location.y_km,heightFor(f,b));
          const text=f.asset_id===this.selected?f.name_en:f.asset_id;
          c.font='11px system-ui, sans-serif';const width=Math.min(240,c.measureText(text).width+40);
          let x=clamp(p.x-width/2,12,w-width-12),y=p.y-35;
          for(const used of labels)if(x<used.x+used.w&&x+width>used.x&&Math.abs(y-used.y)<28)y=used.y-30;
          if(y<12)y=12;labels.push({x,y,w:width});
          this.line([{x:p.x,y:p.y-2},{x:x+width/2,y:y+23}],'#7793a9',.8);
          c.fillStyle=f.asset_id===this.selected?'#d3f3a1':'#14263b';c.fillRect(x,y,width,23);
          c.strokeStyle=f.asset_id===this.selected?'#d3f3a1':'#45637a';c.strokeRect(x,y,width,23);
          c.fillStyle=f.asset_id===this.selected?'#183428':'#e0ecf6';c.textAlign='left';
          let label=text;while(label.length>3&&c.measureText(label).width>width-37)label=label.slice(0,-2)+'…';
          c.fillText(label,x+8,y+15);c.textAlign='right';c.font='bold 11px ui-monospace, monospace';c.fillText(String(f.result.score),x+width-7,y+15);
        }
      }
      if(!this.rows.length){c.fillStyle='#dce9f5';c.font='15px system-ui, sans-serif';c.textAlign='center';c.fillText('No facilities match these filters',w/2,h/2);}
      this.canvas.dataset.pointCount=String(this.rows.length);
      this.canvas.dataset.visibleLinks=String(this.showLinks?this.links.length:0);
    }
    hit(x,y){
      for(let i=this.hitFaces.length-1;i>=0;i--)if(inside({x,y},this.hitFaces[i].poly))return this.hitFaces[i].f;
      // Small flat markers remain selectable by touch at the top-down view.
      const p=this.points.filter(p=>Math.hypot(p.x-x,p.y-y)<9).sort((a,b)=>Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y))[0];
      return p?this.rows.find(f=>f.asset_id===p.asset_id):null;
    }
    destroy(){this.observer?.disconnect();}
  }
  const exports={RiskAtlas,bounds,project,heightFor,inside,connections,PALETTE};
  if(typeof module!=='undefined'&&module.exports)module.exports=exports;
  else root.SahilAtlas=exports;
})(typeof window!=='undefined'?window:globalThis);
