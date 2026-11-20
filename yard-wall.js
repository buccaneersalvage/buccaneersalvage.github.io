/* Yard wall: real photos (scrap.html) or videos (videos.html) hung as rusted steel plates
   on a curved rail. The plate in front sandblasts clean; a mouse or pen blasts any plate it
   crosses, and the rust creeps back a few seconds later. One tap on a plate opens it.
   three.js (vendored subset, MIT) loads only when the wall nears the viewport.
   Reduced motion, Save-Data, no WebGL2 or a lost GPU context leave the plain grid.
   Videos: every grid tile and plate plays in a youtube-nocookie player on this page. */

const THREE_URL = "./assets/vendor/three/three-lite-r186.1.js";

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const saveData = !!(navigator.connection && navigator.connection.saveData);
const wallOK = !reduceMotion && !saveData && "WebGL2RenderingContext" in window && "IntersectionObserver" in window;

function store(key, value) {
  try {
    if (value === undefined) return window.localStorage.getItem(key);
    window.localStorage.setItem(key, value);
  } catch (e) { /* private window or blocked storage: the default view still works */ }
  return null;
}

/* ---------------------------------------------------------------- shaders */

const VERT = `
uniform vec2 uSize;
uniform float uChain;
uniform float uOffset;
uniform float uR;
uniform float uSwing;
uniform float uY;
varying vec2 vLocal;
varying float vEdge;
void main() {
  float ly = -0.5 * uSize.y + (position.y + 0.5) * (uSize.y + uChain);
  vec2 local = vec2(position.x * uSize.x, ly);
  vLocal = local;
  vec2 pivot = vec2(0.0, 0.5 * uSize.y + uChain);
  vec2 d = local - pivot;
  float c = cos(uSwing);
  float s = sin(uSwing);
  vec2 p = pivot + vec2(c * d.x - s * d.y, s * d.x + c * d.y);
  float th = (p.x + uOffset) / uR;
  vEdge = cos(th);
  vec3 w = vec3(sin(th) * uR, p.y + uY, -cos(th) * uR);
  gl_Position = projectionMatrix * viewMatrix * vec4(w, 1.0);
}`;

const NOISE = `
float hh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hh(i), hh(i + vec2(1.0, 0.0)), f.x), mix(hh(i + vec2(0.0, 1.0)), hh(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) {
  float s = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * vn(p); p *= 2.03; a *= 0.5; }
  return s;
}
float fall(float e) { return mix(0.26, 1.0, smoothstep(0.55, 0.98, e)); }`;

const PLATE_FRAG = `
uniform sampler2D uMap;
uniform sampler2D uBlast;
uniform vec2 uSize;
uniform float uFocus;
uniform float uLoaded;
uniform float uSeed;
varying vec2 vLocal;
varying float vEdge;
${NOISE}
void main() {
  vec2 hs = 0.5 * uSize;
  vec2 hook = vec2(hs.x * 0.82, hs.y - 0.07 * uSize.y / 2.0);
  if (vLocal.y > hs.y) {
    float dx = min(abs(vLocal.x - hook.x), abs(vLocal.x + hook.x));
    float link = fract((vLocal.y - hs.y) * 15.0);
    float wdt = mix(0.010, 0.020, step(0.5, link)) * uSize.y;
    if (dx > wdt) discard;
    vec3 c = mix(vec3(0.16, 0.11, 0.07), vec3(0.64, 0.5, 0.2), 1.0 - dx / wdt) * (0.6 + 0.4 * link);
    gl_FragColor = vec4(c * fall(vEdge), 1.0);
    return;
  }
  vec2 uv = vLocal / uSize + 0.5;
  vec3 img = texture2D(uMap, uv).rgb;
  float lum = dot(img, vec3(0.299, 0.587, 0.114));
  vec2 q = uv * vec2(uSize.x / uSize.y, 1.0) * 5.0 + uSeed;
  float g = fbm(q);
  float pit = fbm(q * 3.1 + 7.0);
  vec3 dark = vec3(0.078, 0.055, 0.035);
  vec3 rust = vec3(0.50, 0.23, 0.07);
  vec3 r = mix(dark, rust, smoothstep(0.05, 0.85, lum * 0.85 + g * 0.3));
  r = mix(r, vec3(0.62, 0.5, 0.13), smoothstep(0.62, 0.82, lum) * 0.5);
  r *= 0.75 + 0.45 * g;
  r = mix(r, dark, smoothstep(0.62, 0.7, pit) * 0.7);
  r = mix(mix(dark, rust * 0.6, g), r, uLoaded);
  float m = max(texture2D(uBlast, uv).r, uFocus) * uLoaded;
  float front = m + (g - 0.5) * 0.55;
  float clean = smoothstep(0.42, 0.5, front);
  float rim = smoothstep(0.30, 0.42, front) * (1.0 - clean);
  vec3 col = mix(r, img, clean);
  col += vec3(1.0, 0.82, 0.42) * rim * (0.45 + 0.55 * hh(floor(uv * 240.0)));
  vec2 e = min(uv, 1.0 - uv) * uSize;
  col *= mix(0.4, 1.0, smoothstep(0.0, 0.035 * uSize.y, min(e.x, e.y)));
  float bd = min(length(vLocal - hook), length(vLocal - vec2(-hook.x, hook.y))) / uSize.y;
  col = mix(col, vec3(0.02), 1.0 - smoothstep(0.009, 0.012, bd));
  col = mix(col, vec3(0.78, 0.63, 0.16), (1.0 - smoothstep(0.012, 0.016, bd)) * smoothstep(0.009, 0.012, bd));
  gl_FragColor = vec4(col * fall(vEdge), 1.0);
}`;

const RAIL_FRAG = `
uniform vec2 uSize;
varying vec2 vLocal;
varying float vEdge;
${NOISE}
void main() {
  float t = vLocal.y / uSize.y;
  vec3 c = mix(vec3(0.05, 0.04, 0.03), vec3(0.3, 0.24, 0.12), 1.0 - abs(t * 2.0));
  c += vec3(0.94, 0.82, 0.47) * smoothstep(0.1, 0.0, abs(t - 0.18)) * 0.45;
  c *= 0.8 + 0.3 * fbm(vec2(vLocal.x * 6.0, t * 2.0));
  gl_FragColor = vec4(c * fall(vEdge), 1.0);
}`;

/* ---------------------------------------------------------------- the wall */

const BLAST = 64;
const R = 6;
const FOV = 34;

function createWall(T, root, opts) {
  const stage = root.querySelector(".wall-stage");
  const canvas = stage.querySelector("canvas");
  const caption = root.querySelector(".wall-caption");
  const ac = new AbortController();
  const on = (el, type, fn, o) => el.addEventListener(type, fn, Object.assign({ signal: ac.signal }, o || {}));

  let renderer;
  try {
    renderer = new T.WebGLRenderer({ canvas, antialias: true, powerPreference: "low-power" });
  } catch (e) {
    return null;
  }
  renderer.setClearColor(0x050403, 1);
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(FOV, 1, 0.1, 40);
  const loader = new T.TextureLoader();
  const blank = new T.DataTexture(new Uint8Array([20, 16, 12, 255]), 1, 1);
  blank.needsUpdate = true;
  const plateGeo = new T.PlaneGeometry(1, 1, 32, 1);
  const railGeo = new T.PlaneGeometry(1, 1, 96, 1);
  const maxAniso = Math.min(4, renderer.capabilities.getMaxAnisotropy());

  const rail = new T.Mesh(railGeo, new T.ShaderMaterial({
    vertexShader: VERT,
    fragmentShader: RAIL_FRAG,
    uniforms: {
      uSize: { value: new T.Vector2(1, 0.06) }, uChain: { value: 0 }, uOffset: { value: 0 },
      uR: { value: R }, uSwing: { value: 0 }, uY: { value: 0 }
    }
  }));
  rail.frustumCulled = false;
  scene.add(rail);

  let items = [];
  let plates = [];
  let H = 2;
  let visW = 4;
  let visH = 4;
  let unitPerPx = 0.01;
  let total = 1;
  let wrap = true;
  let pos = 0;
  let target = 0;
  let swing = 0;
  let swingV = 0;
  let current = -1;
  let raf = 0;
  let last = 0;
  let visible = false;
  let dead = false;
  let drag = null;
  let hoverPrev = null;
  let snapTimer = 0;
  let ro = null;
  let io = null;

  const wrapD = (d) => (wrap ? (((d + total / 2) % total) + total) % total - total / 2 : d);

  function disposePlates() {
    plates.forEach((p) => {
      scene.remove(p.mesh);
      p.mesh.material.dispose();
      if (p.tex) p.tex.dispose();
      p.blastTex.dispose();
    });
    plates = [];
  }

  function build() {
    disposePlates();
    plates = items.map((it, i) => {
      const blast = new Uint8Array(BLAST * BLAST);
      const blastTex = new T.DataTexture(blast, BLAST, BLAST, T.RedFormat);
      blastTex.magFilter = T.LinearFilter;
      blastTex.minFilter = T.LinearFilter;
      blastTex.needsUpdate = true;
      const mat = new T.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: PLATE_FRAG,
        uniforms: {
          uMap: { value: blank }, uBlast: { value: blastTex }, uSize: { value: new T.Vector2(1, 1) },
          uChain: { value: 0.5 }, uOffset: { value: 0 }, uR: { value: R }, uSwing: { value: 0 },
          uY: { value: 0 }, uFocus: { value: 0 }, uLoaded: { value: 0 }, uSeed: { value: i * 3.7 }
        }
      });
      const mesh = new T.Mesh(plateGeo, mat);
      mesh.frustumCulled = false;
      scene.add(mesh);
      return {
        it, mesh, u: mat.uniforms, blast, blastTex, heat: new Float32Array(BLAST * BLAST),
        hot: false, lastPaint: 0, focus: 0, tex: null, loading: false, offset: 0, w: 1
      };
    });
    current = -1;
    layout();
  }

  function layout() {
    const w = stage.clientWidth || 1;
    const h = stage.clientHeight || 1;
    const dpr = Math.min(window.devicePixelRatio || 1, w < 700 ? 1.5 : 1.75);
    renderer.setPixelRatio(dpr);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    const tanV = Math.tan((FOV * Math.PI) / 360);
    visH = 2 * R * tanV;
    visW = visH * camera.aspect;
    unitPerPx = (2 * R * Math.atan(tanV * camera.aspect)) / w;
    const maxAspect = items.reduce((m, it) => Math.max(m, it.w / it.h), 1);
    H = Math.min(0.58 * visH, (0.8 * visW) / maxAspect);
    const gap = 0.24 * H;
    const uY = -0.06 * visH;
    const railY = 0.4 * visH;
    const chain = Math.max(0.05, railY - (uY + H / 2));
    let x = 0;
    plates.forEach((p, i) => {
      p.w = (H * p.it.w) / p.it.h;
      if (i) x += p.w / 2;
      p.offset = x;
      x += p.w / 2 + gap;
      p.u.uSize.value.set(p.w, H);
      p.u.uChain.value = chain;
      p.u.uY.value = uY;
    });
    /* plate 0 is centred on 0, so its left half closes the loop at the wrap seam */
    total = Math.max(x + (plates[0] ? plates[0].w / 2 : 0), 0.001);
    wrap = total > visW * 2.2;
    rail.material.uniforms.uSize.value.set(R * Math.PI * 1.3, 0.05 * visH);
    rail.material.uniforms.uY.value = railY;
    const idx = Math.max(0, current);
    if (plates[idx]) pos = target = plates[idx].offset;
    current = -1;
    kick();
  }

  function nearest() {
    let best = 0;
    let bd = Infinity;
    plates.forEach((p, i) => {
      const d = Math.abs(wrapD(p.offset - pos));
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }

  function goTo(i) {
    if (!plates.length) return;
    const n = plates.length;
    i = wrap ? ((i % n) + n) % n : Math.max(0, Math.min(n - 1, i));
    target = pos + wrapD(plates[i].offset - pos);
    kick();
  }

  function snap() {
    if (!wrap && plates.length) {
      target = Math.max(plates[0].offset, Math.min(plates[plates.length - 1].offset, target));
    }
    let best = 0;
    let bd = Infinity;
    plates.forEach((p, i) => {
      const d = Math.abs(wrapD(p.offset - target));
      if (d < bd) { bd = d; best = i; }
    });
    if (plates[best]) target += wrapD(plates[best].offset - target);
  }

  function loadNear(idx) {
    const n = plates.length;
    const big = stage.clientHeight * renderer.getPixelRatio() * 0.58 > 520;
    plates.forEach((p, i) => {
      const d = wrap ? Math.min((i - idx + n) % n, (idx - i + n) % n) : Math.abs(i - idx);
      if (d > 5 || p.loading) return;
      p.loading = true;
      loader.load(big && p.it.big ? p.it.big : p.it.src, (tex) => {
        if (dead || !plates.includes(p)) { tex.dispose(); return; }
        tex.anisotropy = maxAniso;
        p.tex = tex;
        p.u.uMap.value = tex;
        p.u.uLoaded.value = 1;
        kick();
      }, undefined, () => { p.loading = false; });
    });
  }

  function setCurrent(i) {
    if (i === current) return;
    current = i;
    const p = plates[i];
    if (caption && p) caption.textContent = opts.label + " " + (i + 1) + " of " + plates.length + ": " + p.it.title;
    loadNear(i);
  }

  /* Analytic hit test: the camera sits on the cylinder axis, so a screen ray at horizontal
     angle th meets the rail at arc position th * R. No CPU mesh needed. */
  function hit(clientX, clientY) {
    const r = stage.getBoundingClientRect();
    const nx = ((clientX - r.left) / r.width) * 2 - 1;
    const ny = -(((clientY - r.top) / r.height) * 2 - 1);
    const tanV = Math.tan((FOV * Math.PI) / 360);
    const dx = nx * tanV * camera.aspect;
    const t = R / Math.sqrt(dx * dx + 1);
    const hy = ny * tanV * t;
    const sx = Math.atan(dx) * R;
    for (let i = 0; i < plates.length; i++) {
      const p = plates[i];
      const lx = sx - wrapD(p.offset - pos);
      const ly = hy - p.u.uY.value;
      if (Math.abs(lx) <= p.w / 2 && Math.abs(ly) <= H / 2) {
        return { i, u: lx / p.w + 0.5, v: ly / H + 0.5 };
      }
    }
    return null;
  }

  function paint(p, u, v, now) {
    const rw = 0.17 * H;
    const x0 = Math.max(0, Math.floor((u - rw / p.w) * BLAST));
    const x1 = Math.min(BLAST - 1, Math.ceil((u + rw / p.w) * BLAST));
    const y0 = Math.max(0, Math.floor((v - rw / H) * BLAST));
    const y1 = Math.min(BLAST - 1, Math.ceil((v + rw / H) * BLAST));
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const d = Math.hypot(((x + 0.5) / BLAST - u) * p.w, ((y + 0.5) / BLAST - v) * H);
        if (d >= rw) continue;
        const k = y * BLAST + x;
        const a = 1 - d / rw;
        p.heat[k] = Math.min(1, p.heat[k] + a * a * 0.55);
      }
    }
    p.hot = true;
    p.lastPaint = now;
  }

  function blastAt(clientX, clientY) {
    const now = performance.now();
    const steps = hoverPrev ? Math.min(8, Math.ceil(Math.hypot(clientX - hoverPrev[0], clientY - hoverPrev[1]) / 10)) : 1;
    for (let s = 1; s <= steps; s++) {
      const f = s / steps;
      const cx = hoverPrev ? hoverPrev[0] + (clientX - hoverPrev[0]) * f : clientX;
      const cy = hoverPrev ? hoverPrev[1] + (clientY - hoverPrev[1]) * f : clientY;
      const h = hit(cx, cy);
      if (h && plates[h.i].u.uLoaded.value > 0) paint(plates[h.i], h.u, h.v, now);
    }
    hoverPrev = [clientX, clientY];
    kick();
  }

  function frame(now) {
    raf = 0;
    if (dead || !visible || document.hidden) return;
    const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016);
    last = now;
    const prev = pos;
    if (!drag) pos += (target - pos) * (1 - Math.exp(-dt * 9));
    const vel = (pos - prev) / Math.max(dt, 0.001);
    const drive = Math.max(-0.22, Math.min(0.22, vel * 0.03));
    swingV += ((drive - swing) * 70 - swingV * 9) * dt;
    swing += swingV * dt;
    const idx = nearest();
    setCurrent(idx);
    const settled = !drag && Math.abs(target - pos) < 0.02 * H;
    let busy = !settled || Math.abs(swing) > 0.0005 || Math.abs(swingV) > 0.0005;
        plates.forEach((p, i) => {
      const off = wrapD(p.offset - pos);
      p.u.uOffset.value = off;
      /* only the front half of the cylinder is ever in view; a long rail would
         otherwise come round a second time and hang on top of the front plates */
      p.mesh.visible = Math.abs(off) - p.w / 2 < R * 1.45;
      p.u.uSwing.value = swing;
      const want = settled && i === idx && p.u.uLoaded.value > 0 ? 1 : 0;
      const next = want ? Math.min(1, p.focus + dt * 1.4) : Math.max(0, p.focus - dt * 2.2);
      if (next !== p.focus) busy = true;
      p.focus = next;
      p.u.uFocus.value = p.focus;
      if (p.hot) {
        busy = true;
        if (now - p.lastPaint > 2500) {
          let any = false;
          for (let k = 0; k < p.heat.length; k++) {
            if (p.heat[k] > 0) { p.heat[k] = Math.max(0, p.heat[k] - dt * 0.18); any = true; }
          }
          p.hot = any;
        }
        for (let k = 0; k < p.heat.length; k++) p.blast[k] = p.heat[k] * 255;
        p.blastTex.needsUpdate = true;
      }
    });
    renderer.render(scene, camera);
    if (busy || drag) raf = requestAnimationFrame(frame);
    else last = 0;
  }

  function kick() {
    if (!raf && visible && !dead && !document.hidden) raf = requestAnimationFrame(frame);
  }

  /* ---- input ---- */
  on(canvas, "pointerdown", (e) => {
    if (e.button !== 0) return;
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t: performance.now(), v: 0, lt: performance.now() };
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add("is-dragging");
    kick();
  });
  on(canvas, "pointermove", (e) => {
    if (drag && e.pointerId === drag.id) {
      const now = performance.now();
      const dx = e.clientX - drag.x;
      pos -= dx * unitPerPx;
      target = pos;
      drag.v = (-dx * unitPerPx) / Math.max(1, now - drag.lt);
      drag.x = e.clientX;
      drag.lt = now;
      kick();
      return;
    }
    if (e.pointerType !== "touch") blastAt(e.clientX, e.clientY);
  });
  const endDrag = (e, cancelled) => {
    if (!drag || e.pointerId !== drag.id) return;
    const d = drag;
    drag = null;
    canvas.classList.remove("is-dragging");
    const moved = Math.hypot(e.clientX - d.x0, e.clientY - d.y0);
    if (!cancelled && moved < 8 && performance.now() - d.t < 600) {
      const h = hit(e.clientX, e.clientY);
      if (h) {
        goTo(h.i);
        opts.open(plates[h.i].it, h.i);
      }
      return;
    }
    target = pos + d.v * 320;
    snap();
    kick();
  };
  on(canvas, "pointerup", (e) => endDrag(e, false));
  on(canvas, "pointercancel", (e) => endDrag(e, true));
  on(canvas, "pointerleave", () => { hoverPrev = null; });
  on(canvas, "wheel", (e) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) && !e.shiftKey) return; /* vertical wheel scrolls the page */
    e.preventDefault();
    const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    target += d * unitPerPx;
    clearTimeout(snapTimer);
    snapTimer = setTimeout(() => { snap(); kick(); }, 140);
    kick();
  }, { passive: false });
  on(stage, "keydown", (e) => {
    const k = e.key;
    if (k === "ArrowLeft" || k === "ArrowRight") {
      e.preventDefault();
      goTo(nearestTarget() + (k === "ArrowRight" ? 1 : -1));
    } else if (k === "Home" || k === "End") {
      e.preventDefault();
      goTo(k === "Home" ? 0 : plates.length - 1);
    } else if (k === "Enter" || k === " ") {
      e.preventDefault();
      const i = nearestTarget();
      if (plates[i]) opts.open(plates[i].it, i);
    }
  });
  function nearestTarget() {
    let best = 0;
    let bd = Infinity;
    plates.forEach((p, i) => {
      const d = Math.abs(wrapD(p.offset - target));
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }
  root.querySelectorAll("[data-step]").forEach((b) => {
    on(b, "click", () => goTo(nearestTarget() + Number(b.dataset.step)));
  });
  const openBtn = root.querySelector(".wall-open");
  if (openBtn) on(openBtn, "click", () => { const i = nearestTarget(); if (plates[i]) opts.open(plates[i].it, i); });
  on(document, "visibilitychange", kick);
  on(canvas, "webglcontextlost", (e) => { e.preventDefault(); api.destroy(); if (opts.onFail) opts.onFail(); });

  ro = new ResizeObserver(() => { if (!dead) layout(); });
  ro.observe(stage);
  io = new IntersectionObserver((en) => {
    visible = !!(en[0] && en[0].isIntersecting);
    if (visible) kick();
  }, { threshold: 0 });
  io.observe(stage);

  const api = {
    setItems(list) { items = list.slice(); build(); },
    goTo,
    current: () => nearestTarget(),
    destroy() {
      if (dead) return;
      dead = true;
      if (raf) cancelAnimationFrame(raf);
      ac.abort();
      if (ro) ro.disconnect();
      if (io) io.disconnect();
      disposePlates();
      rail.material.dispose();
      plateGeo.dispose();
      railGeo.dispose();
      blank.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
    }
  };
  return api;
}

/* Load three.js once the wall is about to be seen, then build. */
function whenNear(el, cb) {
  const io = new IntersectionObserver((en) => {
    if (en.some((x) => x.isIntersecting)) { io.disconnect(); cb(); }
  }, { rootMargin: "300px 0px" });
  io.observe(el);
}

/* items may be a list or a function that reads the grid when the wall is built. */
function mountWall(root, items, opts) {
  return new Promise((resolve) => {
    whenNear(root, () => {
      import(THREE_URL).then((T) => {
        const wall = createWall(T, root, opts);
        if (!wall) { resolve(null); return; }
        wall.setItems(typeof items === "function" ? items() : items);
        root.classList.add("is-live");
        window.addEventListener("pagehide", (e) => { if (!e.persisted) wall.destroy(); }, { once: true });
        resolve(wall);
      }).catch(() => resolve(null));
    });
  });
}

/* Grid tiles (.yard-open) become wall plates. A tile can name its own plate image, size and
   title with data-wall-src, data-w, data-h and data-title; otherwise the grid image is used. */
function tileItems(tiles) {
  return tiles.map((t, i) => {
    const img = t.querySelector("img");
    const src = t.querySelector("source");
    const small = t.dataset.wallSrc || (src && src.srcset ? src.srcset.split(",")[0].trim().split(" ")[0] : img.src);
    const fc = t.closest("figure") && t.closest("figure").querySelector("figcaption");
    return {
      i,
      id: t.dataset.video || "",
      src: small,
      big: t.dataset.full || small,
      w: Number(t.dataset.w) || Number(img.getAttribute("width")) || 4,
      h: Number(t.dataset.h) || Number(img.getAttribute("height")) || 3,
      title: (t.dataset.title || (fc ? fc.textContent : img.alt)).trim()
    };
  });
}

/* One gallery, two views: the wall (default where it can run) and the plain grid.
   The visitor's choice is remembered per page. Without the wall, the grid simply stays.
   o: { section, root, view, toggle, key, wallText, label, tiles(), open(item) } */
function wallOrGrid(o) {
  const stage = o.root.querySelector(".wall-stage");
  let wall = null;
  let mounting = null;
  let stale = false;
  const isWall = () => o.section.classList.contains("is-wall");
  function fail() {
    wall = null;
    o.section.classList.remove("is-wall");
    o.root.hidden = true;
    o.view.hidden = true;
  }
  function setMode(mode) {
    const on = mode === "wall";
    o.section.classList.toggle("is-wall", on);
    o.root.hidden = !on;
    o.toggle.textContent = on ? "Show as grid" : o.wallText;
    if (on && !mounting) {
      mounting = mountWall(o.root, () => tileItems(o.tiles()), { label: o.label, open: o.open, onFail: fail })
        .then((w) => { if (!w) { fail(); return; } wall = w; stale = false; });
    } else if (on && wall && stale) {
      stale = false;
      wall.setItems(tileItems(o.tiles()));
    }
  }
  o.toggle.addEventListener("click", () => {
    const next = isWall() ? "grid" : "wall";
    store(o.key, next);
    setMode(next);
    if (next === "wall") stage.focus({ preventScroll: true });
  });
  o.view.hidden = false;
  setMode(store(o.key) === "grid" ? "grid" : "wall");
  return {
    stage,
    /* The grid changed (another fleet): rebuild the plates now, or when the wall is next shown. */
    refresh() {
      if (wall && isWall()) wall.setItems(tileItems(o.tiles()));
      else stale = true;
    }
  };
}

/* ---------------------------------------------------------------- scrap.html */

(function yard() {
  const root = document.getElementById("yardWall");
  const section = document.getElementById("yard");
  const grid = document.getElementById("yardGrid");
  const dlg = document.getElementById("yardViewer");
  if (!section || !grid) return;
  const tiles = Array.from(grid.querySelectorAll(".yard-open"));

  /* Swipe left/right inside the enlarged photo viewer (buttons and arrow keys still work). */
  const vstage = dlg && dlg.querySelector(".yard-viewer-stage");
  if (vstage) {
    let sx = 0;
    let sy = 0;
    let sid = null;
    vstage.addEventListener("pointerdown", (e) => { sid = e.pointerId; sx = e.clientX; sy = e.clientY; });
    vstage.addEventListener("pointerup", (e) => {
      if (e.pointerId !== sid) return;
      sid = null;
      const dx = e.clientX - sx;
      if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(e.clientY - sy) * 1.5) return;
      const b = dlg.querySelector(dx < 0 ? ".yard-viewer-next" : ".yard-viewer-prev");
      if (b) b.click();
    });
  }

  if (!root || !tiles.length || !wallOK) return;
  let fromWall = false;
  const g = wallOrGrid({
    section,
    root,
    view: document.getElementById("yardView"),
    toggle: document.getElementById("yardViewToggle"),
    key: "bucYardView",
    wallText: "Show as yard wall",
    label: "Photo",
    tiles: () => tiles,
    open: (it) => {
      fromWall = true;
      tiles[it.i].click();
    }
  });
  if (dlg) {
    dlg.addEventListener("close", () => {
      if (!fromWall) return;
      fromWall = false;
      g.stage.focus({ preventScroll: true });
    });
  }
})();

/* ---------------------------------------------------------------- videos.html */

(function fleet() {
  const dlg = document.getElementById("fleetPlayer");
  const dataEl = document.getElementById("videos-data");
  if (!dlg || !dataEl || typeof dlg.showModal !== "function") return;
  const frameBox = document.getElementById("fleetPlayerFrame");
  const titleEl = document.getElementById("fleetPlayerTitle");
  const ytLink = dlg.querySelector(".fleet-player-yt");
  const closeBtn = dlg.querySelector(".fleet-player-close");
  let opener = null;
  let catalog = [];
  try { catalog = JSON.parse(dataEl.textContent || "[]"); } catch (e) { catalog = []; }
  if (!Array.isArray(catalog)) catalog = [];
  /* The owner turned embedding off on some videos: those stay plain links to YouTube. */
  const noEmbed = new Set(catalog.filter((v) => v && v.embed === false).map((v) => v.id));
  const watchUrl = (id) => "https://www.youtube.com/watch?v=" + encodeURIComponent(id);

  function play(id, title, from) {
    if (!/^[\w-]{6,}$/.test(id) || noEmbed.has(id)) return false;
    opener = from || document.activeElement;
    const f = document.createElement("iframe");
    f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(id) + "?autoplay=1&rel=0&playsinline=1";
    f.title = "Video player: " + title;
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.referrerPolicy = "strict-origin-when-cross-origin";
    f.width = 1280;
    f.height = 720;
    /* The autoplay embed grabs focus after it loads, which would swallow Escape.
       Pull focus back to Close unless the visitor has reached into the player. */
    let touched = false;
    frameBox.addEventListener("pointerdown", () => { touched = true; }, { once: true });
    f.addEventListener("load", () => {
      [250, 900, 2000].forEach((ms) => setTimeout(() => {
        if (!touched && dlg.open && document.activeElement === f) closeBtn.focus({ preventScroll: true });
      }, ms));
    }, { once: true });
    frameBox.replaceChildren(f);
    titleEl.textContent = title;
    ytLink.href = watchUrl(id);
    dlg.showModal();
    document.body.classList.add("fleet-player-open");
    closeBtn.focus();
    return true;
  }
  closeBtn.addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener("close", () => {
    frameBox.replaceChildren(); /* stops playback */
    document.body.classList.remove("fleet-player-open");
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    opener = null;
  });

  /* Grid tiles are facades: a plain click plays here; modified clicks still open YouTube. */
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest(".gallery-panel a.yard-open[data-video]");
    if (!a) return;
    if (play(a.dataset.video, a.dataset.title || "YouTube video", a)) e.preventDefault();
  });

  /* The rail shows the grid of whichever fleet is picked (videos.js builds both grids). */
  const section = document.getElementById("fleetGallery");
  const root = document.getElementById("fleetWall");
  const sw = document.getElementById("fleet-switch");
  if (!section || !root || !sw || !wallOK) return;
  const tiles = () => {
    const panel = document.getElementById(sw.dataset.active === "comedy" ? "gallery-comedy" : "gallery-music");
    return panel ? Array.from(panel.querySelectorAll(".yard-open")) : [];
  };
  if (!tiles().length) return;
  let stage = null;
  const g = wallOrGrid({
    section,
    root,
    view: document.getElementById("fleetView"),
    toggle: document.getElementById("fleetViewToggle"),
    key: "bucFleetView",
    wallText: "Show on the rail",
    label: "Video",
    tiles,
    open: (it) => {
      if (!play(it.id, it.title, stage)) window.open(watchUrl(it.id), "_blank", "noopener,noreferrer");
    }
  });
  stage = g.stage;
  let kind = sw.dataset.active;
  new MutationObserver(() => {
    if (sw.dataset.active === kind) return;
    kind = sw.dataset.active;
    g.refresh();
  }).observe(sw, { attributes: true, attributeFilter: ["data-active"] });
})();
