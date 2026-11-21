/* Depth-buffered mesh renderer: native WebGL, with an offline software fallback. */
(function(root){
  'use strict';
  function triangleList(model,project,color,view){
    const triangles=[];
    for(const face of model.faces){
      if(face.normal.reduce((s,v,i)=>s+v*view[i],0)<=.015)continue;
      const points=face.vertices.map(project),rgb=color(face);
      for(let i=1;i<points.length-1;i++)triangles.push({points:[points[0],points[i],points[i+1]],color:rgb});
    }
    return triangles;
  }
  function shadowGeometry(width,height,center,zoom){
    const radius=Math.min(width*.36,height*.44)*zoom;
    return {x:center.x+8,y:center.y+9,rx:radius,ry:radius*.32};
  }
  class SoftwareRenderer {
    constructor(canvas){this.canvas=canvas;this.ctx=canvas.getContext('2d');this.kind='software';if(!this.ctx)throw new Error('No graphics context is available.');}
    draw(triangles,width,height,shadow){
      const c=this.ctx,W=this.canvas.width,H=this.canvas.height,sx=W/width,sy=H/height;
      c.setTransform(1,0,0,1,0,0);c.fillStyle='#e9eff0';c.fillRect(0,0,W,H);
      c.save();c.translate(shadow.x*sx,shadow.y*sy);c.scale(shadow.rx*sx,shadow.ry*sy);
      const gradient=c.createRadialGradient(0,0,0,0,0,1);gradient.addColorStop(0,'#243f4b44');gradient.addColorStop(1,'#243f4b00');c.fillStyle=gradient;c.fillRect(-1,-1,2,2);c.restore();
      const image=c.getImageData(0,0,W,H),pixels=image.data,depth=new Float32Array(W*H);
      const edge=(a,b,x,y)=>(x-a.x)*(b.y-a.y)-(y-a.y)*(b.x-a.x);
      for(const triangle of triangles){
        const [a,b,d]=triangle.points.map(p=>({x:p.x*sx,y:p.y*sy,q:1/(24-p.depth)}));
        const area=edge(a,b,d.x,d.y);if(Math.abs(area)<.00001)continue;
        const minX=Math.max(0,Math.floor(Math.min(a.x,b.x,d.x))),maxX=Math.min(W-1,Math.ceil(Math.max(a.x,b.x,d.x)));
        const minY=Math.max(0,Math.floor(Math.min(a.y,b.y,d.y))),maxY=Math.min(H-1,Math.ceil(Math.max(a.y,b.y,d.y)));
        for(let y=minY;y<=maxY;y++)for(let x=minX;x<=maxX;x++){
          const u=edge(b,d,x+.5,y+.5)/area,v=edge(d,a,x+.5,y+.5)/area,w=1-u-v;
          if(u<-.00001||v<-.00001||w<-.00001)continue;
          const q=u*a.q+v*b.q+w*d.q,index=y*W+x;if(q+1e-8<depth[index])continue;
          depth[index]=q;const offset=index*4;
          pixels[offset]=triangle.color[0];pixels[offset+1]=triangle.color[1];pixels[offset+2]=triangle.color[2];pixels[offset+3]=255;
        }
      }
      c.putImageData(image,0,0);
    }
    destroy(){}
  }
  class WebGLRenderer {
    constructor(canvas,gl){this.canvas=canvas;this.gl=gl;this.kind='webgl';this.init();}
    init(){
      const gl=this.gl;
      const compile=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const error=gl.getShaderInfoLog(s);gl.deleteShader(s);throw new Error(error);}return s;};
      const vs=compile(gl.VERTEX_SHADER,'attribute vec4 position; attribute vec4 color; varying lowp vec4 shade; void main(){gl_Position=position;shade=color;}');
      const fs=compile(gl.FRAGMENT_SHADER,'precision mediump float; varying lowp vec4 shade; void main(){gl_FragColor=shade;}');
      this.program=gl.createProgram();gl.attachShader(this.program,vs);gl.attachShader(this.program,fs);gl.linkProgram(this.program);
      gl.deleteShader(vs);gl.deleteShader(fs);
      if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(this.program));
      this.buffer=gl.createBuffer();this.position=gl.getAttribLocation(this.program,'position');this.color=gl.getAttribLocation(this.program,'color');
    }
    upload(values){
      const gl=this.gl;gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(this.position);gl.vertexAttribPointer(this.position,4,gl.FLOAT,false,32,0);
      gl.enableVertexAttribArray(this.color);gl.vertexAttribPointer(this.color,4,gl.FLOAT,false,32,16);
      gl.drawArrays(gl.TRIANGLES,0,values.length/8);
    }
    draw(triangles,width,height,shadow){
      const gl=this.gl;if(gl.isContextLost())return;
      gl.viewport(0,0,this.canvas.width,this.canvas.height);gl.clearColor(233/255,239/255,240/255,1);gl.clearDepth(1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.useProgram(this.program);gl.disable(gl.CULL_FACE);gl.disable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      const haze=[],vertex=(x,y,alpha)=>[x/width*2-1,1-y/height*2,0,1,.14,.25,.29,alpha];
      for(let i=0;i<64;i++)haze.push(...vertex(shadow.x,shadow.y,.22),...vertex(shadow.x+Math.cos(i/64*Math.PI*2)*shadow.rx,shadow.y+Math.sin(i/64*Math.PI*2)*shadow.ry,0),...vertex(shadow.x+Math.cos((i+1)/64*Math.PI*2)*shadow.rx,shadow.y+Math.sin((i+1)/64*Math.PI*2)*shadow.ry,0));
      this.upload(haze);gl.disable(gl.BLEND);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
      const values=[];
      for(const t of triangles)for(const p of t.points){
        const distance=24-p.depth;
        values.push((p.x/width*2-1)*distance,(1-p.y/height*2)*distance,(61/59)*distance-120/59,distance,t.color[0]/255,t.color[1]/255,t.color[2]/255,1);
      }
      this.upload(values);
    }
    destroy(){this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);}
  }
  function createRenderer(canvas,{software=false}={}){
    let gl;
    if(!software)try{gl=canvas.getContext('webgl',{alpha:false,antialias:true,depth:true,powerPreference:'low-power'});}catch{/* Software Canvas implementations may throw for WebGL. */}
    return gl?new WebGLRenderer(canvas,gl):new SoftwareRenderer(canvas);
  }
  const api={createRenderer,triangleList,shadowGeometry,SoftwareRenderer,WebGLRenderer};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SahilRenderer=api;
})(typeof window!=='undefined'?window:globalThis);
