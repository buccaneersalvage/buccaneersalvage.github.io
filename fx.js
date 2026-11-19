/* Shared decorative effects for the hub. Raw WebGL2 and CSS 3D, no library.
 * Opt in by attribute, so one file serves every page and cards rendered later:
 *   data-fx-tilt=".card-selector"  pointer tilt + gold sheen on matching cards (one delegated listener)
 *   data-fx-embers  /  data-fx-embers="dust"  slow ember sparks or gold dust behind a section
 *   data-fx-doubloon  a turning gold doubloon pinned to the host's corner
 *   data-fx-spill  coins and gems tumble out of the host's photo card and settle (one burst)
 * Decorative only: canvases are aria-hidden, sized by CSS, paused off-screen and in hidden tabs,
 * Canvases start on the first interaction after load. DPR capped at 1.5. Reduced motion = one still doubloon frame, no sparks, no tilt.
 * No WebGL = the page is unchanged. Touch devices get no tilt.
 * Remove: delete this file, its <script> tags, the data-fx-* attributes and the "fx" block in styles.css. */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var small = window.matchMedia("(max-width: 639px)").matches;
  var DPR = Math.min(window.devicePixelRatio || 1, 1.5);

  function idle(fn) {
    if ("requestIdleCallback" in window) window.requestIdleCallback(fn, { timeout: 1500 });
    else window.setTimeout(fn, 200);
  }

  function makeCanvas(host, cls) {
    var c = document.createElement("canvas");
    c.className = cls;
    c.setAttribute("aria-hidden", "true");
    host.appendChild(c);
    return c;
  }

  function compile(gl, vsSrc, fsSrc) {
    function sh(type, src) {
      var s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { gl.deleteShader(s); return null; }
      return s;
    }
    var v = sh(gl.VERTEX_SHADER, vsSrc), f = sh(gl.FRAGMENT_SHADER, fsSrc);
    if (!v || !f) return null;
    var p = gl.createProgram();
    gl.attachShader(p, v);
    gl.attachShader(p, f);
    gl.linkProgram(p);
    return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
  }

  /* Runs draw(t) on rAF while the canvas is on screen and the tab is visible. */
  function loop(canvas, draw, still) {
    var visible = false, raf = 0, t0 = performance.now(), dead = false;
    function frame(now) {
      raf = 0;
      if (dead || !visible || document.hidden) return;
      draw((now - t0) / 1000);
      if (!still) raf = window.requestAnimationFrame(frame);
    }
    function kick() { if (!raf && !dead) raf = window.requestAnimationFrame(frame); }
    new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting;
      if (visible) kick();
    }).observe(canvas);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) kick(); });
    canvas.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();
      dead = true;
      canvas.remove();
    });
    return kick;
  }

  function fit(canvas, gl) {
    var w = Math.max(1, Math.round(canvas.clientWidth * DPR));
    var h = Math.max(1, Math.round(canvas.clientHeight * DPR));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
  }

  /* ---------- Doubloon: analytic ray/cylinder coin with an embossed skull face ---------- */
  function faceTexture() {
    var S = 256, c = document.createElement("canvas");
    c.width = c.height = S;
    var g = c.getContext("2d");
    g.fillStyle = "#000";
    g.fillRect(0, 0, S, S);
    g.translate(S / 2, S / 2);
    g.fillStyle = "#fff";
    g.strokeStyle = "#fff";
    // raised rim and a ring of beads
    g.lineWidth = 14;
    g.beginPath(); g.arc(0, 0, 118, 0, Math.PI * 2); g.stroke();
    for (var i = 0; i < 36; i++) {
      var a = (i / 36) * Math.PI * 2;
      g.beginPath(); g.arc(Math.cos(a) * 98, Math.sin(a) * 98, 3.2, 0, Math.PI * 2); g.fill();
    }
    // crossbones
    g.lineCap = "round";
    g.lineWidth = 15;
    [[-1, 1], [1, 1]].forEach(function (d) {
      g.save();
      g.rotate(d[0] * Math.PI / 4);
      g.beginPath(); g.moveTo(-70, 0); g.lineTo(70, 0); g.stroke();
      [-74, 74].forEach(function (x) {
        g.beginPath(); g.arc(x, -7, 9, 0, Math.PI * 2); g.fill();
        g.beginPath(); g.arc(x, 7, 9, 0, Math.PI * 2); g.fill();
      });
      g.restore();
    });
    // skull: cranium + jaw, sockets and nose cut out
    g.beginPath(); g.ellipse(0, -14, 44, 42, 0, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.rect(-26, 12, 52, 30); g.fill();
    g.globalCompositeOperation = "destination-out";
    g.beginPath(); g.ellipse(-17, -10, 12, 13, 0.15, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.ellipse(17, -10, 12, 13, -0.15, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.moveTo(0, 4); g.lineTo(-6, 16); g.lineTo(6, 16); g.closePath(); g.fill();
    g.lineWidth = 3;
    for (var k = -2; k <= 2; k++) {
      g.beginPath(); g.moveTo(k * 9, 26); g.lineTo(k * 9, 42); g.stroke();
    }
    g.globalCompositeOperation = "source-over";
    // soften so the emboss reads as cast metal, not a cut-out
    var soft = document.createElement("canvas");
    soft.width = soft.height = S;
    var sg = soft.getContext("2d");
    sg.fillStyle = "#000";
    sg.fillRect(0, 0, S, S);
    sg.filter = "blur(3px)";
    sg.drawImage(c, 0, 0);
    return sg.filter === "blur(3px)" ? soft : c;
  }

  var COIN_VS = "#version 300 es\nin vec2 p;out vec2 v;void main(){v=p;gl_Position=vec4(p,0.,1.);}";
  var COIN_FS = [
    "#version 300 es",
    "precision highp float;",
    "in vec2 v;out vec4 o;",
    "uniform sampler2D face;uniform float ang;uniform vec2 tilt;",
    "const float H=0.085;",
    "mat3 ry(float a){float c=cos(a),s=sin(a);return mat3(c,0.,-s,0.,1.,0.,s,0.,c);}",
    "mat3 rx(float a){float c=cos(a),s=sin(a);return mat3(1.,0.,0.,0.,c,s,0.,-s,c);}",
    "float hgt(vec2 uv){return texture(face,uv).r;}",
    "vec3 env(vec3 r){",
    "  float up=r.y*.5+.5;",
    "  vec3 c=mix(vec3(.05,.035,.02),vec3(.55,.36,.14),smoothstep(.2,.95,up));",
    "  c+=vec3(1.,.82,.5)*pow(max(dot(r,normalize(vec3(-.5,.7,.6))),0.),24.)*1.6;",
    "  c+=vec3(.9,.35,.12)*pow(max(dot(r,normalize(vec3(.8,-.2,.4))),0.),6.)*.35;",
    "  return c;}",
    "void main(){",
    "  mat3 R=rx(tilt.y)*ry(ang+tilt.x);mat3 Ri=transpose(R);",
    "  vec3 ro=Ri*vec3(0.,0.,3.4);vec3 rd=Ri*normalize(vec3(v*.36,-1.));",
    "  float best=1e9;vec3 n=vec3(0.);bool face_hit=false;float side=1.;float hc=1.;",
    "  for(int i=0;i<2;i++){float zc=i==0?H:-H;float t=(zc-ro.z)/rd.z;",
    "    if(t>0.&&t<best){vec3 q=ro+rd*t;if(dot(q.xy,q.xy)<=1.){best=t;face_hit=true;side=sign(zc);}}}",
    "  float a=dot(rd.xy,rd.xy),b=dot(ro.xy,rd.xy),c=dot(ro.xy,ro.xy)-1.,d=b*b-a*c;",
    "  if(d>0.){float t=(-b-sqrt(d))/a;vec3 q=ro+rd*t;",
    "    if(t>0.&&t<best&&abs(q.z)<=H){best=t;face_hit=false;",
    "      float th=atan(q.y,q.x);n=normalize(vec3(q.xy,0.)+vec3(-sin(th),cos(th),0.)*sin(th*90.)*.18);}}",
    "  if(best>1e8){o=vec4(0.);return;}",
    "  vec3 q=ro+rd*best;",
    "  if(face_hit){vec2 uv=vec2(q.x*side,-q.y)*.5+.5;float e=1./256.;",
    "    float hx=hgt(uv+vec2(e,0.))-hgt(uv-vec2(e,0.));float hy=hgt(uv+vec2(0.,e))-hgt(uv-vec2(0.,e));",
    "    hc=hgt(uv);n=normalize(vec3(-hx*side*9.,hy*9.,side));}",
    "  vec3 wn=R*n;vec3 wd=normalize(R*rd);vec3 r=reflect(wd,wn);",
    "  vec3 gold=vec3(1.,.8,.44);",
    "  float fr=.65+.35*pow(1.-max(dot(-wd,wn),0.),5.);",
    "  vec3 col=env(r)*gold*fr*1.3+gold*.06;col*=mix(.6,1.1,hc);",
    "  col=col/(col+vec3(.7))*1.55;",
    "  float edge=smoothstep(1.,.985,length(q.xy))*1.+(face_hit?0.:1.);",
    "  o=vec4(col*min(edge,1.),min(edge,1.));}"
  ].join("\n");

  function doubloon(host) {
    var canvas = makeCanvas(host, "fx-doubloon");
    var gl = canvas.getContext("webgl2", { premultipliedAlpha: true, alpha: true, antialias: true, failIfMajorPerformanceCaveat: true });
    var prog = gl && compile(gl, COIN_VS, COIN_FS);
    if (!prog) { canvas.remove(); return; }
    gl.useProgram(prog);
    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, faceTexture());
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    var uAng = gl.getUniformLocation(prog, "ang"), uTilt = gl.getUniformLocation(prog, "tilt");
    gl.uniform1i(gl.getUniformLocation(prog, "face"), 0);
    var target = [0, 0], cur = [0, 0];
    if (finePointer && !reduce) {
      window.addEventListener("pointermove", function (e) {
        var r = canvas.getBoundingClientRect();
        var dx = (e.clientX - (r.left + r.width / 2)) / window.innerWidth;
        var dy = (e.clientY - (r.top + r.height / 2)) / window.innerHeight;
        target[0] = Math.max(-1, Math.min(1, dx)) * 0.45;
        target[1] = Math.max(-1, Math.min(1, dy)) * 0.35;
        kick();
      }, { passive: true });
    }
    var kick = loop(canvas, function (t) {
      fit(canvas, gl);
      cur[0] += (target[0] - cur[0]) * 0.06;
      cur[1] += (target[1] - cur[1]) * 0.06;
      // slow rocking turn so the face always reads; reduced motion holds a three-quarter view
      gl.uniform1f(uAng, reduce ? 0.55 : Math.sin(t * 0.5) * 0.95);
      gl.uniform2f(uTilt, cur[0], 0.18 + cur[1]);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }, reduce);
    canvas.classList.add("is-live");
  }

  /* ---------- Spill: coins and a few gems tumble out of the chest photo and settle ----------
   * Host = the hero panel; the photo card inside it is the chest. One burst on first view,
   * then the pile rests and the loop stops (no idle GPU work). Reduced motion draws only the
   * settled pile, once. Physics runs in card-width units so a resize keeps the pile in place. */
  var SPILL_VS = [
    "#version 300 es",
    "in vec2 q;in vec4 a;in vec2 b;uniform vec2 res;uniform float sh;out vec2 uv;out float fl;out float ty;",
    "void main(){float c=cos(a.w),s=sin(a.w);float z=a.z*(1.+sh*.15);vec2 p=q*z*.5;",
    "  if(sh<.5)p=vec2(c*p.x-s*p.y,s*p.x+c*p.y);else p.y*=.55;",
    "  vec2 px=(a.xy+p+sh*vec2(a.z*.08,a.z*.32))/res*2.-1.;gl_Position=vec4(px.x,-px.y,0.,1.);uv=q;fl=b.x;ty=sh>.5?-1.:b.y;}"
  ].join("\n");
  var SPILL_FS = [
    "#version 300 es",
    "precision mediump float;in vec2 uv;in float fl;in float ty;out vec4 o;",
    "void main(){",
    "  if(ty<-.5){float r=length(uv);float k=smoothstep(1.,.15,r)*.42;o=vec4(0.,0.,0.,k);return;}",
    "  if(ty<.5){",
    "    float f=max(abs(fl),.14);vec2 p=vec2(uv.x/f,uv.y);float r=length(p);",
    "    float m=smoothstep(1.,1.-fwidth(r)*1.5,r);if(m<=0.)discard;",
    "    vec3 g=vec3(.92,.69,.3);",
    "    float l=.5+.5*clamp(.55-.55*p.y-.3*p.x*sign(fl+1e-4),0.,1.);",
    "    vec3 col=g*l;",
    "    float ring=smoothstep(.68,.74,r)*(1.-smoothstep(.8,.86,r));",
    "    col=mix(col,g*1.2,ring*.55);",
    "    col*=1.-.16*smoothstep(.44,.4,r)*(.5+.5*p.y);",
    "    col*=mix(.42,1.,smoothstep(1.,.86,r));",
    "    col*=mix(.5,1.,f);",
    "    col+=vec3(1.,.92,.72)*pow(max(0.,1.-length(p-vec2(-.3,-.42))*1.7),6.)*.45*f;",
    "    o=vec4(col*m,m);",
    "  }else{",
    "    vec2 p=uv;float d=max(abs(p.x)*.866+abs(p.y)*.5,abs(p.y));",
    "    float m=smoothstep(.9,.9-fwidth(d)*1.5,d);if(m<=0.)discard;",
    "    vec3 base=ty<1.5?vec3(.62,.05,.1):ty<2.5?vec3(.04,.45,.24):vec3(.1,.24,.7);",
    "    float k=floor((atan(p.y,p.x)+3.1416)/1.0472);",
    "    float facet=.6+.4*cos(k*2.1+fl*3.);float table=smoothstep(.46,.42,d);",
    "    vec3 col=base*facet*(.8+.5*table)+base*.25*smoothstep(.7,.9,d);",
    "    col+=vec3(1.)*pow(max(0.,1.-length(p-vec2(-.22,-.3))*3.),4.)*.6;",
    "    o=vec4(col*m,m);",
    "  }}"
  ].join("\n");

  function spill(host) {
    var card = host.querySelector(".hero-panel-card, .hero-v3-art") || host;
    var canvas = makeCanvas(host, "fx-spill");
    var gl = canvas.getContext("webgl2", { premultipliedAlpha: true, alpha: true, antialias: true, failIfMajorPerformanceCaveat: true });
    var prog = gl && compile(gl, SPILL_VS, SPILL_FS);
    if (!prog) { canvas.remove(); return; }
    gl.useProgram(prog);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    var quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var lq = gl.getAttribLocation(prog, "q");
    gl.enableVertexAttribArray(lq);
    gl.vertexAttribPointer(lq, 2, gl.FLOAT, false, 0, 0);
    var N = small ? 24 : 40;
    var inst = new Float32Array(N * 6);
    var ib = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, ib);
    gl.bufferData(gl.ARRAY_BUFFER, inst.byteLength, gl.DYNAMIC_DRAW);
    var la = gl.getAttribLocation(prog, "a"), lb = gl.getAttribLocation(prog, "b");
    gl.enableVertexAttribArray(la);
    gl.vertexAttribPointer(la, 4, gl.FLOAT, false, 24, 0);
    gl.vertexAttribDivisor(la, 1);
    gl.enableVertexAttribArray(lb);
    gl.vertexAttribPointer(lb, 2, gl.FLOAT, false, 24, 16);
    gl.vertexAttribDivisor(lb, 1);
    var uRes = gl.getUniformLocation(prog, "res"), uSh = gl.getUniformLocation(prog, "sh");

    // Seeded random so every visit spills the same tidy pile.
    var seed = 7;
    function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
    var P = [], gems = 0;
    for (var i = 0; i < N; i++) {
      var gem = i % 6 === 4;
      P.push({
        x: 0.44 + rnd() * 0.28, y: 0.26 + rnd() * 0.05,
        vx: (rnd() - 0.5) * 0.38, vy: -(0.2 + rnd() * 0.3),
        r: gem ? 0.018 + rnd() * 0.004 : 0.021 + rnd() * 0.006,
        rf: 0.38 + rnd() * 0.5, fl: 1,
        rot: rnd() * 6.28, w: (rnd() - 0.5) * 8,
        ph: rnd() * 6.28, spin: 6 + rnd() * 8,
        type: gem ? 1 + (gems++ % 3) : 0,
        born: i * 0.05, live: false, rest: false
      });
    }
    var G = 2.2, aspect = 0.69, still = 0, simT = 0;
    function step(dt) {
      simT += dt;
      var floor = aspect, moving = 0;
      for (var i = 0; i < N; i++) {
        var p = P[i];
        if (!p.live) { if (simT >= p.born) p.live = true; else { moving++; continue; } }
        p.vy += G * dt;
        p.x += p.vx * dt; p.y += p.vy * dt;
        p.rot += p.w * dt;
        p.ph += p.spin * dt;
        if (p.y > floor - p.r) {
          p.y = floor - p.r;
          if (p.vy > 0) p.vy *= -0.32;
          p.vx *= 0.86; p.w *= 0.8; p.spin *= 0.82;
        }
        if (p.x < p.r) { p.x = p.r; p.vx = Math.abs(p.vx) * 0.4; }
        if (p.x > 1 - p.r) { p.x = 1 - p.r; p.vx = -Math.abs(p.vx) * 0.4; }
      }
      // light pile-up: push overlapping pieces apart, the upper one rides on the lower
      for (var a = 0; a < N; a++) {
        var A = P[a];
        if (!A.live) continue;
        for (var b = a + 1; b < N; b++) {
          var B = P[b];
          if (!B.live) continue;
          var dx = B.x - A.x, dy = B.y - A.y, d = Math.sqrt(dx * dx + dy * dy), m = (A.r + B.r) * 0.9;
          if (d > 0 && d < m) {
            var push = (m - d) / 2, nx = dx / d, ny = dy / d;
            A.x -= nx * push; A.y -= ny * push; B.x += nx * push; B.y += ny * push;
            var rv = (B.vx - A.vx) * nx + (B.vy - A.vy) * ny;
            if (rv < 0) { var j = rv * 0.6; A.vx += j * nx; A.vy += j * ny; B.vx -= j * nx; B.vy -= j * ny; }
          }
        }
      }
      for (var k = 0; k < N; k++) {
        var q = P[k];
        if (!q.live) continue;
        var sp = Math.abs(q.vx) + Math.abs(q.vy);
        if (sp < 0.02 && q.y > floor - q.r * 3.5) {
          // settle: ease the flip toward a readable face-on angle
          q.fl += (q.rf - q.fl) * 0.12; q.spin = 0; q.w *= 0.5;
          if (Math.abs(q.rf - q.fl) > 0.01) moving++;
        } else { q.fl = Math.cos(q.ph); moving++; }
      }
      still = moving === 0 ? still + 1 : 0;
    }
    function draw() {
      fit(canvas, gl);
      var cw = card.offsetWidth, ox = card.offsetLeft - canvas.offsetLeft, oy = card.offsetTop - canvas.offsetTop;
      aspect = card.offsetHeight / Math.max(1, cw);
      var s = DPR, n = 0;
      for (var i = 0; i < N; i++) {
        var p = P[i];
        if (!p.live) continue;
        inst[n * 6] = (ox + p.x * cw) * s;
        inst[n * 6 + 1] = (oy + p.y * cw) * s;
        inst[n * 6 + 2] = p.r * 2 * cw * s * 1.25;
        inst[n * 6 + 3] = p.rot;
        inst[n * 6 + 4] = p.fl;
        inst[n * 6 + 5] = p.type;
        n++;
      }
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bindBuffer(gl.ARRAY_BUFFER, ib);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, inst.subarray(0, n * 6));
      if (n) {
        gl.uniform1f(uSh, 1);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, n);
        gl.uniform1f(uSh, 0);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, n);
      }
    }
    aspect = card.offsetHeight / Math.max(1, card.offsetWidth);
    if (reduce) {
      // no motion: settle the pile off-screen and show the result once
      for (var t = 0; t < 1400 && still < 30; t++) step(1 / 120);
      P.forEach(function (p) { p.fl = p.rf; });
      draw();
      new ResizeObserver(draw).observe(card);
      canvas.classList.add("is-live");
      return;
    }
    var last = 0, raf = 0, visible = false, done = false;
    function frame(now) {
      raf = 0;
      if (!visible || document.hidden) { last = 0; return; }
      var dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
      last = now;
      for (var acc = dt; acc > 0; acc -= 1 / 120) step(Math.min(1 / 120, acc));
      draw();
      if (still > 30 || simT > 9) { done = true; return; }
      raf = window.requestAnimationFrame(frame);
    }
    function kick() { if (!raf && !done) raf = window.requestAnimationFrame(frame); }
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; if (visible) kick(); }).observe(canvas);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) kick(); });
    new ResizeObserver(function () { if (done) draw(); }).observe(card);
    canvas.addEventListener("webglcontextlost", function (e) { e.preventDefault(); done = true; canvas.remove(); });
    canvas.classList.add("is-live");
  }

  /* ---------- Embers: a few slow sparks behind the yard gallery ---------- */
  var EMBER_VS = [
    "#version 300 es",
    "in float id;uniform float t;uniform vec2 res;uniform float dust;out float a;out vec3 c;",
    "float h(float n){return fract(sin(n*127.1)*43758.5453);}",
    "void main(){",
    "  float s=h(id),s2=h(id+7.3),s3=h(id+19.1);",
    "  float sp=.018+.03*s2;float y=fract(s3+t*sp);",
    "  float x=s+.035*sin(t*(.25+.3*s2)+id);",
    "  gl_Position=vec4(x*2.-1.,y*2.-1.,0.,1.);",
    "  gl_PointSize=(1.5+3.*s2)*res.y;",
    "  a=smoothstep(0.,.15,y)*smoothstep(1.,.6,y)*(.55+.45*sin(t*.6+id*3.1));",
    "  c=dust>.5?mix(vec3(.95,.78,.38),vec3(1.,.92,.62),s3):mix(vec3(1.,.45,.12),vec3(1.,.8,.35),s3);}"
  ].join("\n");
  var EMBER_FS = "#version 300 es\nprecision mediump float;in float a;in vec3 c;out vec4 o;void main(){float d=length(gl_PointCoord-.5);float k=smoothstep(.5,0.,d);k*=k;o=vec4(c*k*a*.55,k*a*.55);}";

  function embers(host) {
    if (reduce) return;
    var dust = host.getAttribute("data-fx-embers") === "dust";
    var canvas = makeCanvas(host, "fx-embers");
    var gl = canvas.getContext("webgl2", { premultipliedAlpha: true, alpha: true, antialias: false, failIfMajorPerformanceCaveat: true });
    var prog = gl && compile(gl, EMBER_VS, EMBER_FS);
    if (!prog) { canvas.remove(); return; }
    var N = small ? 22 : 46;
    var ids = new Float32Array(N);
    for (var i = 0; i < N; i++) ids[i] = i;
    gl.useProgram(prog);
    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, ids, gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, "id");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 1, gl.FLOAT, false, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE);
    var uT = gl.getUniformLocation(prog, "t"), uRes = gl.getUniformLocation(prog, "res");
    gl.uniform1f(gl.getUniformLocation(prog, "dust"), dust ? 1 : 0);
    var last = -1;
    loop(canvas, function (t) {
      // ~30 fps is plenty for slow sparks and halves the GPU work
      if (t - last < 1 / 30) return;
      last = t;
      fit(canvas, gl);
      gl.uniform1f(uT, t);
      gl.uniform2f(uRes, 1, DPR);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.POINTS, 0, N);
    }, false);
  }

  /* ---------- Cards: pointer tilt + sheen, one delegated listener for every [data-fx-tilt] ---------- */
  function tilt() {
    if (reduce || !finePointer || !document.querySelector("[data-fx-tilt]")) return;
    var card = null, ev = null, raf = 0;
    function reset() {
      if (!card) return;
      card.classList.remove("fx-on");
      card.style.removeProperty("--fx-rx");
      card.style.removeProperty("--fx-ry");
      card = null;
    }
    function apply() {
      raf = 0;
      if (!card || !ev) return;
      var r = card.getBoundingClientRect();
      if (!r.width || !r.height) return;
      var x = (ev.clientX - r.left) / r.width, y = (ev.clientY - r.top) / r.height;
      card.style.setProperty("--fx-rx", ((0.5 - y) * 5).toFixed(2) + "deg");
      card.style.setProperty("--fx-ry", ((x - 0.5) * 6).toFixed(2) + "deg");
      card.style.setProperty("--fx-mx", (x * 100).toFixed(1) + "%");
      card.style.setProperty("--fx-my", (y * 100).toFixed(1) + "%");
    }
    document.addEventListener("pointermove", function (e) {
      if (e.pointerType !== "mouse") return;
      var host = e.target.closest ? e.target.closest("[data-fx-tilt]") : null;
      var next = host ? e.target.closest(host.getAttribute("data-fx-tilt")) : null;
      if (next && !host.contains(next)) next = null;
      if (next !== card) {
        reset();
        if (next) {
          card = next;
          if (!card.querySelector(":scope > .fx-sheen")) {
            var sheen = document.createElement("span");
            sheen.className = "fx-sheen";
            sheen.setAttribute("aria-hidden", "true");
            card.appendChild(sheen);
          }
          card.classList.add("fx-card", "fx-on");
        }
      }
      ev = e;
      if (card && !raf) raf = window.requestAnimationFrame(apply);
    }, { passive: true });
    document.documentElement.addEventListener("pointerleave", reset);
    window.addEventListener("blur", reset);
  }

  tilt();
  /* Build each canvas only once its host scrolls near view, after load and on idle.
   * failIfMajorPerformanceCaveat skips software-rendered WebGL (no GPU): no effect, no cost. */
  function whenNear(host, build) {
    var io = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting) return;
      io.disconnect();
      idle(function () { try { build(host); } catch (e) { /* decorative */ } });
    }, { rootMargin: "200px" });
    io.observe(host);
  }
  function start() {
    var d = document.querySelector("[data-fx-doubloon]");
    if (d) whenNear(d, doubloon);
    var sp = document.querySelector("[data-fx-spill]");
    if (sp) whenNear(sp, spill);
    document.querySelectorAll("[data-fx-embers]").forEach(function (h) { whenNear(h, embers); });
  }
  /* WebGL setup costs a shader compile, so it waits for the visitor's first interaction
   * (pointer, touch, wheel, key or scroll) after load: nothing competes with first paint. */
  var EV = ["pointermove", "pointerdown", "touchstart", "wheel", "keydown", "scroll"];
  function first() {
    EV.forEach(function (n) { window.removeEventListener(n, first, true); });
    start();
  }
  function arm() {
    EV.forEach(function (n) { window.addEventListener(n, first, { capture: true, passive: true }); });
  }
  if (document.readyState === "complete") arm();
  else window.addEventListener("load", arm, { once: true });
})();
