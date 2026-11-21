/* Offline, rotatable architectural models. Geometry is illustrative, not surveyed.
   True XYZ meshes are perspective-projected, lit and depth-buffered locally.
   No network services, textures, external models, or alternate risk calculations. */
(function(root) {
  'use strict';
  const Renderer=root.SahilRenderer||(typeof require==='function'?require('./asset-renderer.js'):null);
  const TAU=Math.PI*2, DEG=Math.PI/180;
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const sub=(a,b)=>a.map((v,i)=>v-b[i]);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
  const unit=v=>{const n=Math.hypot(...v)||1;return v.map(x=>x/n);};
  const COLORS={wall:'#d3d9d6',brick:'#b96d50',trim:'#edf0e9',roof:'#586371',steel:'#81949e',
    dark:'#283e4b',glass:'#41758a',glassLight:'#7ea8b3',glassDark:'#305765',pipe:'#3b939b',
    tank:'#c7d5d0',concrete:'#9ea9aa',site:'#d4dcd9',asphalt:'#647077',line:'#e4e9dc',
    leaf:'#698c71',water:'#5b9eae',solar:'#234f6f',accent:'#b86d50'};
  const BANDS={Low:'#65d6ae',Guarded:'#73b5fa',Elevated:'#e6cf77',High:'#ff9b74',Severe:'#fb6f91'};

  class Mesh {
    constructor(){this.faces=[];this.group='envelope';}
    face(vertices,material='wall',group=this.group){
      const normal=unit(cross(sub(vertices[1],vertices[0]),sub(vertices[2],vertices[0])));
      this.faces.push({vertices,normal,material,group,center:vertices[0].map((_,i)=>vertices.reduce((s,v)=>s+v[i],0)/vertices.length)});
    }
    box(x,y,z,w,d,h,material='wall',group=this.group){
      const v=[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]
        .map(p=>[x+p[0]*w/2,y+p[1]*d/2,z+p[2]*h]);
      for(const f of [[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7],[3,2,1,0]])this.face(f.map(i=>v[i]),material,group);
    }
    tube(a,b,r,material='steel',segments=14,group=this.group){
      const axis=unit(sub(b,a)),u=unit(cross(axis,Math.abs(axis[2])>.9?[0,1,0]:[0,0,1])),v=cross(axis,u);
      const ring=c=>Array.from({length:segments},(_,i)=>c.map((p,j)=>p+r*(Math.cos(TAU*i/segments)*u[j]+Math.sin(TAU*i/segments)*v[j])));
      const aa=ring(a),bb=ring(b);
      for(let i=0;i<segments;i++){const j=(i+1)%segments;this.face([aa[i],aa[j],bb[j],bb[i]],material,group);}
      this.face(aa.slice().reverse(),material,group);this.face(bb,material,group);
    }
    cylinder(x,y,z,r,h,material='tank',segments=24,group=this.group){this.tube([x,y,z],[x,y,z+h],r,material,segments,group);}
  }
  function windowFace(m,x,y,z,w,h,side,material){
    let p;
    if(side==='front'||side==='back'){
      p=[[x+w/2,y,z],[x-w/2,y,z],[x-w/2,y,z+h],[x+w/2,y,z+h]];
      if(side==='back')p.reverse();
    }else{
      p=[[x,y-w/2,z],[x,y+w/2,z],[x,y+w/2,z+h],[x,y-w/2,z+h]];
      if(side==='left')p.reverse();
    }
    m.face(p,material,'envelope');
    // A narrow pale reflection is a separate plane on every pane.
    const q=p.map((v,i)=>i<2?v:v.map((n,j)=>n+(p[(i+2)%4][j]-n)*.86));
    const outward=side==='front'?[0,.002,0]:side==='back'?[0,-.002,0]:side==='left'?[-.002,0,0]:[.002,0,0];
    m.face(q.map(p=>p.map((v,i)=>v+outward[i])),'glassLight','envelope');
  }
  function building(m,x,y,w,d,h,{z=.2,levels=2,columns=4,wall='wall',windows=true}={}){
    m.box(x,y,z,w,d,h,wall,'envelope');
    m.box(x,y,z+h,w+.14,d+.14,.13,'roof','roof');
    for(const yy of [-1,1])m.box(x,y+yy*d/2,z+h+.13,w+.15,.09,.17,'trim','roof');
    for(const xx of [-1,1])m.box(x+xx*w/2,y,z+h+.13,.09,d+.15,.17,'trim','roof');
    if(windows){
      for(let floor=0;floor<levels;floor++){
        const zz=z+.2+(h-.25)*floor/levels,hh=(h-.25)/levels*.62;
        for(const side of ['front','back'])for(let j=0;j<columns;j++){
          const xx=x-w/2+(j+.5)*w/columns,yy=y+(side==='front'?1:-1)*(d/2+.009);
          windowFace(m,xx,yy,zz,w/columns*.67,hh,side,(j+floor)%3===0?'glassLight':(j+floor)%3===1?'glass':'glassDark');
        }
        const n=Math.max(2,Math.round(columns*d/w));
        for(const side of ['left','right'])for(let j=0;j<n;j++){
          const yy=y-d/2+(j+.5)*d/n,xx=x+(side==='right'?1:-1)*(w/2+.009);
          windowFace(m,xx,yy,zz,d/n*.65,hh,side,(j+floor)%2?'glass':'glassDark');
        }
        if(floor)m.box(x,y,z+(h-.25)*floor/levels,w+.035,d+.035,.055,'trim','envelope');
      }
    }
  }
  function door(m,x,y,z=.2,w=.6,h=1){
    m.box(x,y,z,w+.1,.1,h+.07,'dark','envelope');
    m.box(x,y+.06,z+.03,w,.025,h,'glass','envelope');
    m.box(x,y+.08,z,.035,.03,h,'trim','envelope');
    m.box(x,y+.09,z+h*.5,w*.8,.03,.025,'steel','envelope');
  }
  function hvac(m,x,y,z,w=.72,d=.55){
    m.box(x,y,z,w,d,.32,'steel','roof');
    m.box(x,y,z+.32,w+.04,d+.04,.035,'trim','roof');
    for(let i=0;i<5;i++)m.box(x-w*.38+i*w*.19,y+d/2+.005,z+.06,.025,.015,.21,'dark','roof');
    m.cylinder(x,y,z+.36,Math.min(w,d)*.33,.016,'dark',18,'roof');
    m.cylinder(x,y,z+.38,.04,.02,'steel',10,'roof');
    for(let i=0;i<4;i++){
      const a=i*TAU/4,rr=Math.min(w,d)*.26;
      const spin=(u,v)=>[x+u*Math.cos(a)-v*Math.sin(a),y+u*Math.sin(a)+v*Math.cos(a),z+.39];
      m.face([spin(.025,-.025),spin(rr,-.06),spin(rr,.04),spin(.025,.035)],'steel','roof');
    }
  }
  function tank(m,x,y,z=.2,r=.65,h=1.7){
    m.cylinder(x,y,z,r,h,'tank',28,'equipment');
    for(const zz of [z+.06,z+h*.5,z+h-.06])m.cylinder(x,y,zz,r+.018,.045,'steel',28,'equipment');
    m.cylinder(x,y,z+h,r*.92,.09,'trim',28,'equipment');
    m.cylinder(x,y,z+h+.09,.12,.12,'steel',14,'equipment');
    for(let i=0;i<7;i++)m.box(x,y+r+.025,z+.16+i*h/8,.22,.045,.028,'dark','equipment');
  }
  function site(m){
    m.box(0,0,-.12,7.8,5.8,.3,'site','site');
    m.box(0,2.24,.185,7.5,.85,.015,'asphalt','site');
    for(let i=-3;i<=3;i++)m.box(i,2.23,.207,.38,.025,.01,'line','site');
    for(const x of [-3.5,3.5]){
      m.box(x,-2.3,.19,.48,.58,.2,'trim','site');
      m.box(x,-2.3,.39,.4,.5,.18,'leaf','site');
    }
  }
  function archetype(f){
    const name=(f?.name_en||'').toLowerCase(),sector=f?.sector||'';
    if(/substation/.test(name))return 'substation';
    if(/water tower|reservoir|fuel|silos|gas receiving/.test(name))return 'storage';
    if(/mast|telecom|communications hub/.test(name))return 'communications';
    if(/bridge|interchange/.test(name))return 'bridge';
    if(/solar/.test(name))return 'solar';
    if(/desalin|wastewater|power station|incinerator|pump station/.test(name))return 'plant';
    if(sector==='health'&&/hospital|health centre/.test(name))return 'hospital';
    if(sector==='financial_services'||/city hall|courts|headquarters|operations centre/.test(name))return 'tower';
    if(sector==='food'||sector==='transport'||sector==='waste'||/depot|store|storage|sports|school|data centre/.test(name))return 'warehouse';
    return 'commercial';
  }
  const TYPE_NAMES={plant:'Treatment & utility plant',substation:'Electrical substation',storage:'Storage & water infrastructure',
    communications:'Communications facility',bridge:'Bridge & transport structure',solar:'Solar energy facility',
    hospital:'Healthcare building',tower:'Civic & office building',warehouse:'Logistics & service building',commercial:'Commercial building'};
  function buildModel(f){
    const m=new Mesh(),type=archetype(f);site(m);
    if(type==='plant'){
      building(m,-.85,-.1,3.5,2.8,2.35,{levels:2,columns:5,wall:'brick'});
      building(m,-2.3,-1.25,1.2,1.1,1.35,{levels:1,columns:2});
      door(m,-.85,1.32);m.box(-.85,1.52,1.38,1.3,.7,.1,'trim','envelope');
      hvac(m,-1.65,-.55,2.68);hvac(m,-.25,-.55,2.68);
      tank(m,2.1,-1.13,.2,.66,1.85);tank(m,2.1,.5,.2,.66,1.85);
      for(const y of [-1.13,.5]){
        m.tube([1,y,.72],[1.3,y,.72],.09,'pipe',12,'equipment');
        m.tube([1.3,y,.72],[1.3,y,1.3],.09,'pipe',12,'equipment');
        m.tube([1.3,y,1.3],[2.1,y,1.3],.09,'pipe',12,'equipment');
      }
    }else if(type==='substation'){
      building(m,0,-1.25,4.2,1.2,1.25,{levels:1,columns:5});hvac(m,1,-1.2,1.58);
      for(const x of [-2.2,0,2.2]){
        m.box(x,.65,.2,1.3,1.3,.14,'concrete','equipment');
        m.box(x,.65,.34,.9,1.05,.85,'steel','equipment');
        for(let i=0;i<7;i++)m.box(x-.45+i*.15,.65,.4,.035,1.17,.7,'dark','equipment');
        for(const y of [.3,1]){
          m.cylinder(x,y,1.2,.08,.58,'dark',10,'equipment');
          for(let z=1.3;z<1.8;z+=.1)m.cylinder(x,y,z,.14,.035,'trim',12,'equipment');
        }
      }
      for(const x of [-3.1,3.1])m.box(x,.6,.2,.14,.14,2.5,'steel','equipment');
      m.box(0,.6,2.65,6.4,.16,.16,'steel','equipment');
      m.tube([-3.1,.6,2.5],[3.1,.6,2.5],.025,'dark',8,'equipment');
    }else if(type==='storage'){
      tank(m,-1.9,-.5,.2,1.15,2.9);tank(m,.65,-.6,.2,1.15,2.9);
      building(m,2.75,.9,1.3,1.6,1.1,{levels:1,columns:2,wall:'brick'});hvac(m,2.75,.8,1.43,.45,.45);
      m.tube([-2,1,.55],[2.5,1,.55],.13,'pipe',14,'equipment');
      for(const x of [-1.9,.65])m.tube([x,-.1,.55],[x,1,.55],.12,'pipe',14,'equipment');
    }else if(type==='communications'){
      building(m,-.9,0,3.1,2.4,1.5,{levels:1,columns:4});hvac(m,-1.6,0,1.83);
      const x=1.8,y=-.6;
      for(const dx of [-.55,.55])for(const dy of [-.55,.55])m.tube([x+dx,y+dy,.2],[x+dx*.2,y+dy*.2,5.3],.045,'steel',8,'equipment');
      for(let z=.6;z<5;z+=.8){
        const a=.57*(1-z/6),b=.57*(1-(z+.8)/6);
        for(const s of [-1,1]){
          m.tube([x-a,y+s*a,z],[x+b,y+s*b,z+.8],.025,'steel',8,'equipment');
          m.tube([x+s*a,y-a,z],[x+s*b,y+b,z+.8],.025,'steel',8,'equipment');
        }
      }
      for(const s of [-1,1])m.box(x+s*.25,y,4.4,.12,.3,.9,'trim','equipment');
      m.tube([x,y,5],[x,y,5.9],.035,'dark',10,'equipment');
    }else if(type==='bridge'){
      m.box(0,0,.19,7.4,3.7,.02,'water','site');
      m.box(0,0,1.3,7.2,1.7,.25,'concrete','envelope');
      m.box(0,0,1.56,7.2,1.5,.025,'asphalt','envelope');
      for(let x=-3;x<=3;x+=.65)m.box(x,0,1.59,.3,.04,.01,'line','envelope');
      for(const x of [-2.3,2.3])for(const y of [-.95,.95]){
        m.box(x,y,.22,.22,.22,3.5,'trim','equipment');
        for(const offset of [-1.1,-.6,.6,1.1])m.tube([x,y,3.55],[x+offset,y,1.55],.018,'steel',6,'equipment');
      }
      for(const x of [-2.3,2.3])m.box(x,0,3.6,.25,2.15,.17,'trim','equipment');
      for(const y of [-.79,.79])m.box(0,y,1.6,7.2,.06,.23,'trim','envelope');
    }else if(type==='solar'){
      for(let y=-1.5;y<=1.4;y+=1.15)for(let x=-2.65;x<3;x+=1.7){
        m.box(x,y,.2,.08,.7,.65,'steel','equipment');
        const p=[[x-.7,y-.42,.6],[x+.7,y-.42,.6],[x+.7,y+.42,1.12],[x-.7,y+.42,1.12]];
        m.face(p,'solar','equipment');
        for(let i=0;i<4;i++)m.tube([x-.7+i*.47,y-.42,.61],[x-.7+i*.47,y+.42,1.13],.012,'steel',6,'equipment');
        m.tube([x-.7,y,.87],[x+.7,y,.87],.012,'steel',6,'equipment');
      }
    }else if(type==='hospital'){
      building(m,0,-.2,2.45,2.8,4.45,{levels:5,columns:4});
      building(m,-2,-.15,1.5,2.6,2.35,{levels:2,columns:2});
      building(m,2,-.15,1.5,2.6,2.35,{levels:2,columns:2});
      m.box(0,1.24,3.62,.72,.045,.65,'pipe','envelope');
      m.box(0,1.27,3.73,.14,.025,.43,'trim','envelope');m.box(0,1.28,3.88,.44,.025,.14,'trim','envelope');
      door(m,0,1.23,.2,.85,1);m.box(0,1.58,1.32,1.65,.9,.1,'trim','envelope');
      hvac(m,-.5,-.4,4.78);hvac(m,.5,-.4,4.78);hvac(m,2,0,2.68);
    }else if(type==='tower'){
      building(m,0,0,3.35,2.65,6.25,{levels:9,columns:5,wall:'brick'});
      building(m,0,0,4.8,3.6,.75,{levels:1,columns:8});
      m.box(0,0,6.58,2.2,1.65,.5,'wall','roof');hvac(m,-.5,0,7.08,.55,.5);hvac(m,.5,0,7.08,.55,.5);
      door(m,0,1.83,.2,.8,.65);m.box(0,2.08,.95,1.7,.7,.1,'trim','envelope');
    }else if(type==='warehouse'){
      building(m,0,-.1,5.4,3,2,{levels:1,columns:8,wall:'brick'});
      for(const x of [-1.8,0,1.8]){
        m.box(x,1.44,.2,1.25,.1,1.42,'dark','envelope');
        m.box(x,1.51,.25,1.1,.025,1.29,'steel','envelope');
        for(let z=.38;z<1.5;z+=.2)m.box(x,1.53,z,1.1,.018,.022,'dark','envelope');
      }
      for(const x of [-1.6,0,1.6])hvac(m,x,-.6,2.33,.85,.65);
      m.box(0,1.73,1.83,5.9,.85,.09,'roof','envelope');
    }else{
      building(m,0,0,3.7,3,2.1,{levels:1,columns:4,wall:'brick'});
      m.box(0,1.52,.2,3.7,.1,1.65,'trim','envelope');
      for(const x of [-1.15,1.15]){m.box(x,1.59,.55,1.05,.04,1,'dark','envelope');m.box(x,1.62,.6,.9,.02,.88,'glass','envelope');}
      door(m,0,1.59,.2,.63,1.45);hvac(m,-.65,-.35,2.43,.95,.8);hvac(m,.8,.4,2.43,.65,.65);
      m.box(0,1.75,1.91,4,.7,.12,'roof','envelope');
    }
    const maxZ=Math.max(...m.faces.flatMap(f=>f.vertices.map(v=>v[2])));
    return {type,label:TYPE_NAMES[type],faces:m.faces,maxZ,target:Math.max(.7,maxZ*.4),
      parts:[{id:'envelope',label:type==='bridge'?'Deck & structure':'Building envelope'},
        {id:type==='solar'||type==='substation'||type==='storage'||type==='communications'||type==='bridge'?'equipment':'roof',label:type==='solar'?'Panels & supports':type==='substation'?'Transformers & gantry':type==='storage'?'Tanks & pipes':type==='communications'?'Mast & antennas':type==='bridge'?'Towers & cables':'Roof & equipment'},
        {id:'site',label:'Site & access'}].filter(p=>m.faces.some(f=>f.group===p.id))};
  }
  function project(point,camera,width,height,target=.9){
    const [x,y,z]=point,u=x*Math.cos(camera.yaw)-y*Math.sin(camera.yaw),v=x*Math.sin(camera.yaw)+y*Math.cos(camera.yaw);
    const depth=v*Math.cos(camera.pitch)+(z-target)*Math.sin(camera.pitch),perspective=24/(24-depth);
    const scale=Math.min(width/12.8,height/Math.max(10.2,target*3.4+3.6))*camera.zoom;
    return {x:width/2+u*scale*perspective,y:height*.46+(v*Math.sin(camera.pitch)-(z-target)*Math.cos(camera.pitch))*scale*perspective,depth};
  }
  const rgb=hex=>hex.slice(1).match(/../g).map(v=>parseInt(v,16));
  function faceColor(face,camera,risk,mode,part){
    let color=rgb(COLORS[face.material]||COLORS.wall);
    if(mode==='risk'&&face.group!=='site'&&!['glass','glassLight','glassDark','dark'].includes(face.material)){
      const tint=rgb(risk);color=color.map((v,i)=>v*.25+tint[i]*.75);
    }
    const n=face.normal,nx=n[0]*Math.cos(camera.yaw)-n[1]*Math.sin(camera.yaw),ny=n[0]*Math.sin(camera.yaw)+n[1]*Math.cos(camera.yaw);
    const light=clamp(.76+(-nx*.25+ny*.3+n[2]*.4),.45,1.12);
    if(part&&face.group!==part)color=color.map(v=>v*.3+205*.7);
    return color.map(v=>Math.round(clamp(v*light,0,255)));
  }
  class AssetViewer {
    constructor(canvas,{onChange=()=>{},reducedMotion}={}){
      this.canvas=canvas;this.renderer=Renderer.createRenderer(canvas);this.contextLost=false;
      this.onChange=onChange;this.camera={yaw:-28*DEG,pitch:26*DEG,zoom:1};
      this.width=700;this.height=490;this.mode='materials';this.part='';this.model=null;this.facility=null;
      this.visible=true;this.inView=true;this.drag=null;this.frame=null;this.lastTime=null;this.destroyed=false;this.handlers=[];
      this.motionQuery=root.matchMedia?.('(prefers-reduced-motion: reduce)');
      this.reducedMotion=reducedMotion??this.motionQuery?.matches??false;this.rotating=!this.reducedMotion;
      this.motionChange=e=>{this.reducedMotion=e.matches;if(e.matches)this.setRotation(false);};
      this.motionQuery?.addEventListener?.('change',this.motionChange);
      this.listen(root.document,'visibilitychange',()=>this.schedule());
      this.bind();
      this.listen(canvas,'webglcontextlost',e=>{e.preventDefault();this.contextLost=true;this.schedule();});
      this.listen(canvas,'webglcontextrestored',()=>{this.renderer.init();this.contextLost=false;this.draw();this.schedule();});
      if(root.ResizeObserver){this.resizeObserver=new root.ResizeObserver(()=>this.resize());this.resizeObserver.observe(canvas);}
      if(root.IntersectionObserver){this.intersectionObserver=new root.IntersectionObserver(entries=>{this.inView=entries[0].isIntersecting;this.schedule();},{threshold:0});this.intersectionObserver.observe(canvas);}
      this.resize();
    }
    listen(target,event,fn,options){target?.addEventListener?.(event,fn,options);this.handlers.push([target,event,fn,options]);}
    bind(){
      const c=this.canvas;
      this.listen(c,'pointerdown',e=>{
        if(e.button!==0||e.isPrimary===false)return;
        c.focus({preventScroll:true});c.setPointerCapture?.(e.pointerId);this.setRotation(false);
        this.drag={id:e.pointerId,x:e.clientX,y:e.clientY,yaw:this.camera.yaw,pitch:this.camera.pitch};c.style.cursor='grabbing';
      });
      this.listen(c,'pointermove',e=>{
        if(!this.drag||e.pointerId!==this.drag.id)return;
        this.camera.yaw=this.drag.yaw+(e.clientX-this.drag.x)*.009;
        this.camera.pitch=clamp(this.drag.pitch+(e.clientY-this.drag.y)*.007,10*DEG,75*DEG);this.draw();
      });
      const finish=e=>{if(!this.drag||e.pointerId!==this.drag.id)return;this.drag=null;c.style.cursor='grab';if(c.hasPointerCapture?.(e.pointerId))c.releasePointerCapture(e.pointerId);};
      this.listen(c,'pointerup',finish);this.listen(c,'pointercancel',finish);this.listen(c,'lostpointercapture',()=>{this.drag=null;c.style.cursor='grab';});
      this.listen(c,'wheel',e=>{if(!c.matches?.(':focus'))return;e.preventDefault();this.zoom(Math.exp(-e.deltaY*.001));},{passive:false});
      this.listen(c,'keydown',e=>{
        if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','Home',' '].includes(e.key))return;
        e.preventDefault();
        if(e.key===' '){this.setRotation(!this.rotating);return;}
        this.setRotation(false);
        if(e.key==='ArrowLeft')this.camera.yaw-=.12;
        if(e.key==='ArrowRight')this.camera.yaw+=.12;
        if(e.key==='ArrowUp')this.camera.pitch=clamp(this.camera.pitch+.08,10*DEG,75*DEG);
        if(e.key==='ArrowDown')this.camera.pitch=clamp(this.camera.pitch-.08,10*DEG,75*DEG);
        if(e.key==='+'||e.key==='=')this.zoom(1.12);
        if(e.key==='-')this.zoom(1/1.12);
        if(e.key==='Home')this.reset();
        this.draw();
      });
    }
    setFacility(f){
      if(!f){this.facility=null;this.model=null;this.draw();this.schedule();return;}
      const changed=this.facility?.asset_id!==f.asset_id||this.model?.type!==archetype(f);
      this.facility=f;
      if(changed){this.model=buildModel(f);this.part='';this.reset();}
      this.canvas.setAttribute?.('aria-label',`Rotating 3D illustration of ${f.name_en}. ${this.model.label}. Drag to orbit. Arrow keys rotate, plus and minus zoom, Space toggles rotation. Illustrative geometry, not an actual surveyed building.`);
      this.draw();this.schedule();
    }
    setMode(mode){if(!['materials','risk'].includes(mode))return;this.mode=mode;this.draw();this.notify();}
    setPart(part){this.part=this.part===part?'':part;this.draw();this.notify();}
    setRotation(value){this.rotating=Boolean(value);this.draw();this.schedule();this.notify();}
    setVisible(value){this.visible=Boolean(value);this.resize();this.schedule();}
    zoom(factor){this.camera.zoom=clamp(this.camera.zoom*factor,.65,1.65);this.draw();}
    reset(){this.camera={yaw:-28*DEG,pitch:26*DEG,zoom:1};this.draw();this.notify();}
    notify(){this.onChange({rotating:this.rotating,mode:this.mode,part:this.part});}
    canAnimate(){return !this.destroyed&&!this.contextLost&&this.rotating&&this.visible&&this.inView&&!!this.model&&!root.document?.hidden&&!this.drag;}
    schedule(){
      if(this.frame!==null){root.cancelAnimationFrame?.(this.frame);this.frame=null;}this.lastTime=null;
      if(this.canAnimate()&&root.requestAnimationFrame)this.frame=root.requestAnimationFrame(t=>this.tick(t));
    }
    tick(time){
      this.frame=null;if(!this.canAnimate())return;
      if(this.lastTime===null)this.lastTime=time;
      const elapsed=time-this.lastTime;
      if(elapsed>=1000/30){this.camera.yaw=(this.camera.yaw+Math.min(elapsed,100)*.00019)%TAU;this.lastTime=time;this.draw();}
      this.frame=root.requestAnimationFrame?.(t=>this.tick(t))??null;
    }
    resize(){
      const r=this.canvas.getBoundingClientRect();if(r.width<1||r.height<1)return;
      this.width=r.width;this.height=r.height;const dpr=this.renderer.kind==='webgl'?Math.min(root.devicePixelRatio||1,2):1;
      this.canvas.width=Math.round(r.width*dpr);this.canvas.height=Math.round(r.height*dpr);this.draw();
    }
    draw(){
      if(this.contextLost||!this.model)return;
      const model=this.model,cam=this.camera,w=this.width,h=this.height;
      const p=v=>project(v,cam,w,h,model.target),risk=BANDS[this.facility?.result?.band]||BANDS.Guarded;
      const view=[Math.sin(cam.yaw)*Math.cos(cam.pitch),Math.cos(cam.yaw)*Math.cos(cam.pitch),Math.sin(cam.pitch)];
      const triangles=Renderer.triangleList(model,p,f=>faceColor(f,cam,risk,this.mode,this.part),view);
      this.renderer.draw(triangles,w,h,Renderer.shadowGeometry(w,h,p([.4,.4,-.14]),cam.zoom));
      this.canvas.dataset.assetId=this.facility.asset_id;this.canvas.dataset.modelType=model.type;
      this.canvas.dataset.rotating=String(this.rotating);this.canvas.dataset.faceCount=String(model.faces.length);
      this.canvas.dataset.viewMode=this.mode;this.canvas.dataset.renderer=this.renderer.kind;
    }
    destroy(){
      this.destroyed=true;if(this.frame!==null)root.cancelAnimationFrame?.(this.frame);this.frame=null;
      this.renderer.destroy();this.resizeObserver?.disconnect();this.intersectionObserver?.disconnect();
      this.motionQuery?.removeEventListener?.('change',this.motionChange);
      for(const [target,event,fn,options]of this.handlers)target?.removeEventListener?.(event,fn,options);
    }
  }
  const exports={AssetViewer,Mesh,archetype,buildModel,project,faceColor,TYPE_NAMES};
  if(typeof module!=='undefined'&&module.exports)module.exports=exports;else root.SahilAsset3D=exports;
})(typeof window!=='undefined'?window:globalThis);
