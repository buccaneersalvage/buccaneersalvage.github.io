"""BuccaneerSalvage OG card god-mode renderer.

One headless Blender 4.0.2 process renders all page cards: crest emblem backdrop,
gold extruded brand title (Pirata One) + per-page subtitle (Cinzel Decorative),
procedural pirate props standing on a dark studio floor with real contact
shadows, Poly Haven HDRI lighting (reflections only, never camera-visible),
and a compositor pass: bloom, color balance, vignette.

Usage: blender --background --python og_render.py -- <page>   (single card, optional)
Output: assets/og/og-<page>.jpg  (1200x630 JPEG q92)
"""
import bpy, bmesh, math, os, sys

REPO = "/home/jollyroge1480/sites/buccaneersalvage-hub"
CREST = f"{REPO}/assets/crest-rustjack-web.jpg"
HDRI = "/tmp/studio_hdr.hdr"
PIRATA = "/home/jollyroge1480/.local/share/fonts/PirataOne.ttf"
CINZEL = "/home/jollyroge1480/.local/share/fonts/CinzelDecorative.ttf"
OUTDIR = f"{REPO}/assets/og"

CARDS = {
    "index":         ("Parts, Service & Salvage",      [("chest", -4.4, 1.1), ("barrel", 4.5, 1.15)]),
    "store":         ("Store Catalog",                 [("chest", -4.4, 1.15), ("coins", 4.4, 1.0)]),
    "services":      ("eBay Listing Services",         [("spyglass", -4.4, 1.2), ("crate", 4.4, 1.1)]),
    "concierge":     ("AI Concierge for Shop Owners",  [("spyglass", -4.4, 1.2), ("envelope", 4.4, 1.1)]),
    "scrap":         ("Free Scrap & E-Waste Pickup",   [("barrel", -4.4, 1.2), ("crate", 4.5, 1.15)]),
    "videos":        ("YouTube Video Gallery",            [("cannon", -4.2, 1.0), ("barrel", 4.6, 1.1)]),
    "contact":       ("Contact the Yard",              [("envelope", -4.4, 1.2), ("barrel", 4.5, 1.15)]),
    "map":           ("Directions to the Yard",        [("spyglass", -4.4, 1.15), ("flag", 4.4, 1.1)]),
    "terms":         ("Terms & Returns",               [("crate", -4.4, 1.15), ("coins", 4.4, 1.0)]),
    "terms-service": ("eBay Service Terms",            [("spyglass", -4.4, 1.2), ("coins", 4.4, 1.05)]),
    "privacy":       ("Privacy Policy",                [("lock", -4.4, 1.2), ("crate", 4.5, 1.1)]),
    "thanks":        ("Message Sent — Fair Winds",     [("flag", -4.3, 1.15), ("chest", 4.5, 1.1)]),
    "404":           ("Lost at Sea",                   [("barrel", -4.4, 1.15), ("crate", 4.5, 1.1)]),
    "templates":     ("Web & eBay Listing Templates",           [("envelope", -4.4, 1.2), ("coins", 4.4, 1.0)]),
}

FLOOR_Z = -3.1
TILT = math.radians(3.0)

# ---------------------------------------------------------------- scene reset
scene = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

scene.render.engine = 'CYCLES'
scene.render.resolution_x = 1200
scene.render.resolution_y = 630
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 92
scene.cycles.samples = 256
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 6
try:
    scene.view_settings.look = 'AgX - Punchy'
except Exception as e:
    print("view settings fallback:", e)

# GPU if available, else CPU
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'
    prefs.get_devices()
    gpus = [d for d in prefs.devices if d.type == 'CUDA']
    if gpus:
        for d in prefs.devices:
            d.use = (d.type == 'CUDA')
        scene.cycles.device = 'GPU'
        print("GPU: CUDA", [d.name for d in gpus])
except Exception as e:
    print("cpu render:", e)

# ---------------------------------------------------------------- world (HDRI lights + reflects; backdrop hides it from camera)
world = bpy.data.worlds.new("ogworld")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
bg = wnt.nodes["Background"]
try:
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    hdr = bpy.data.images.load(HDRI)
    env.image = hdr
    wnt.links.new(env.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.006  # studio HDRIs are huge in linear units; whisper-level
    print("HDRI world OK")
except Exception as e:
    bg.inputs[0].default_value = (0.0113, 0.0113, 0.0113, 1.0)
    print("HDRI failed, flat world:", e)

# ---------------------------------------------------------------- materials
def noise_rough(nt, lo, hi, scale=14.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = lo
    mr.inputs["To Max"].default_value = hi
    nt.links.new(n.outputs["Fac"], mr.inputs[0])
    nt.links.new(mr.outputs[0], nt.nodes["Principled BSDF"].inputs["Roughness"])

def mat_gold():
    m = bpy.data.materials.new("gold"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.795, 0.585, 0.180, 1.0)
    p.inputs["Metallic"].default_value = 1.0
    try:
        p.inputs["Coat Weight"].default_value = 0.25
    except KeyError:
        pass
    noise_rough(m.node_tree, 0.12, 0.42)
    return m

def mat_iron():
    m = bpy.data.materials.new("iron"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.025, 0.022, 0.020, 1.0)
    p.inputs["Metallic"].default_value = 0.85
    noise_rough(m.node_tree, 0.35, 0.7)
    return m

def mat_brass():
    m = bpy.data.materials.new("brass"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.62, 0.46, 0.20, 1.0)
    p.inputs["Metallic"].default_value = 1.0
    noise_rough(m.node_tree, 0.2, 0.5)
    return m

def mat_wood():
    m = bpy.data.materials.new("wood"); m.use_nodes = True
    nt = m.node_tree; p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.105, 0.062, 0.032, 1.0)
    p.inputs["Roughness"].default_value = 0.75
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 30.0
    b = nt.nodes.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.12
    nt.links.new(n.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m

def mat_sail():
    m = bpy.data.materials.new("sail"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.22, 0.045, 0.035, 1.0)
    p.inputs["Roughness"].default_value = 0.85
    return m

def mat_parch():
    m = bpy.data.materials.new("parchment"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.85, 0.77, 0.58, 1.0)
    p.inputs["Roughness"].default_value = 0.7
    return m

GOLD, IRON, BRASS, WOOD, SAIL, PARCH = mat_gold(), mat_iron(), mat_brass(), mat_wood(), mat_sail(), mat_parch()

def box(name, size, loc, rot=(0, 0, 0), mat=WOOD, bevel=0.02):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me); bm.free()
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    ob.location = loc; ob.rotation_euler = rot
    md = ob.modifiers.new("bev", 'BEVEL'); md.width = bevel; md.segments = 3
    me.materials.append(mat)
    return ob

def cyl(name, r, depth, loc, rot=(0, 0, 0), mat=WOOD, verts=32):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    bm.to_mesh(me); bm.free()
    ob.location = loc; ob.rotation_euler = rot
    me.materials.append(mat)
    return ob

def torus(name, R, r, loc, rot=(0, 0, 0), mat=IRON):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot)
    tob = bpy.context.active_object
    tob.name = name
    tob.data.materials.append(mat)
    return tob

# ---------------------------------------------------------------- props (base sits on z=0)
def prop_chest():
    parts = []
    parts.append(box("chest-base", (1.15, 0.62, 0.5), (0, 0, 0.25), mat=WOOD, bevel=0.025))
    parts.append(cyl("chest-lid", 0.31, 1.15, (0, 0, 0.5), rot=(0, math.radians(90), 0), mat=WOOD))
    for x in (-0.38, 0.38):
        parts.append(box(f"band{x}", (0.09, 0.66, 0.52), (x, 0, 0.25), mat=GOLD, bevel=0.01))
    parts.append(box("lidband-l", (0.09, 0.66, 0.09), (-0.38, 0, 0.72), mat=GOLD, bevel=0.01))
    parts.append(box("lidband-r", (0.09, 0.66, 0.09), (0.38, 0, 0.72), mat=GOLD, bevel=0.01))
    parts.append(box("lock", (0.14, 0.08, 0.18), (0, 0.3, 0.42), mat=GOLD, bevel=0.02))
    return parts

def prop_barrel():
    parts = []
    prof = [(0.26, 0.0), (0.33, 0.18), (0.36, 0.45), (0.36, 0.75), (0.33, 1.02), (0.26, 1.2)]
    me = bpy.data.meshes.new("barrel-body")
    ob = bpy.data.objects.new("barrel-body", me)
    scene.collection.objects.link(ob)
    bm = bmesh.new()
    segs = 24
    rings = []
    for (r, z) in prof:
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for li in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((rings[li][i], rings[li][j], rings[li + 1][j], rings[li + 1][i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(WOOD)
    parts.append(ob)
    for z in (0.28, 0.92):
        parts.append(torus(f"bband{z}", 0.365, 0.028, (0, 0, z), rot=(math.radians(90), 0, 0), mat=IRON))
    return parts

def prop_crate():
    parts = []
    parts.append(box("crate-body", (0.95, 0.95, 0.8), (0, 0, 0.4), mat=WOOD, bevel=0.02))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box("post", (0.09, 0.09, 0.84), (sx * 0.44, sy * 0.44, 0.4), mat=WOOD, bevel=0.01))
    for zz in (0.06, 0.74):
        parts.append(box("railx", (1.0, 0.07, 0.07), (0, 0.46, zz), mat=WOOD, bevel=0.01))
        parts.append(box("railx2", (1.0, 0.07, 0.07), (0, -0.46, zz), mat=WOOD, bevel=0.01))
    parts.append(box("raily", (0.07, 1.0, 0.07), (0.46, 0, 0.74), mat=WOOD, bevel=0.01))
    parts.append(box("raily2", (0.07, 1.0, 0.07), (-0.46, 0, 0.74), mat=WOOD, bevel=0.01))
    return parts

def prop_coins():
    import random
    random.seed(7)
    parts = []
    for i in range(7):
        x = random.uniform(-0.12, 0.12); y = random.uniform(-0.1, 0.1)
        parts.append(cyl("coin", 0.17, 0.05, (x, y, 0.025 + i * 0.048), rot=(0, 0, random.uniform(0, 3.1)), mat=GOLD, verts=24))
    return parts

def prop_spyglass():
    parts = []
    lens = [(0.30, 0.17), (0.30, 0.135), (0.30, 0.105)]
    xoff = 0.0
    for i, (ln, r) in enumerate(lens):
        parts.append(cyl(f"scope{i}", r, ln, (xoff, 0, 0.17), rot=(0, math.radians(90), 0), mat=BRASS))
        xoff += ln * 0.85
    parts.append(torus("eyepiece", 0.11, 0.025, (xoff - 0.22, 0, 0.17), rot=(0, math.radians(90), 0), mat=GOLD))
    return parts

def prop_cannon():
    parts = []
    parts.append(box("carriage", (0.8, 0.5, 0.3), (0, 0, 0.32), mat=WOOD, bevel=0.02))
    barrel = cyl("cannon-barrel", 0.17, 1.15, (0.25, 0, 0.62), rot=(0, math.radians(90), 0), mat=IRON)
    barrel.scale = (1.0, 1.0, 0.85)
    parts.append(barrel)
    parts.append(torus("muzzle", 0.175, 0.03, (0.83, 0, 0.62), rot=(0, math.radians(90), 0), mat=GOLD))
    for sx in (-0.3, 0.3):
        parts.append(cyl(f"wheel{sx}", 0.26, 0.08, (sx, 0.3, 0.26), rot=(math.radians(90), 0, 0), mat=WOOD, verts=24))
        parts.append(cyl(f"hub{sx}", 0.06, 0.1, (sx, 0.3, 0.26), rot=(math.radians(90), 0, 0), mat=IRON, verts=12))
    return parts

def prop_lock():
    parts = []
    parts.append(box("lock-body", (0.5, 0.18, 0.55), (0, 0, 0.28), mat=BRASS, bevel=0.06))
    parts.append(torus("shackle", 0.16, 0.035, (0, 0, 0.58), mat=GOLD))
    parts.append(box("keyhole", (0.06, 0.02, 0.12), (0, 0.095, 0.3), mat=IRON, bevel=0.005))
    return parts

def prop_flag():
    parts = []
    parts.append(cyl("pole", 0.035, 1.9, (0, 0, 0.95), mat=WOOD, verts=16))
    parts.append(torus("finial", 0.05, 0.02, (0, 0, 1.95), mat=GOLD))
    parts.append(box("sail", (0.06, 0.95, 0.6), (0.51, 0, 1.55), mat=SAIL, bevel=0.01))
    return parts

def prop_envelope():
    parts = []
    parts.append(box("env-body", (0.95, 0.62, 0.06), (0, 0, 0.05), mat=PARCH, bevel=0.008))
    parts.append(box("env-flap", (0.95, 0.34, 0.03), (0, -0.1, 0.16), rot=(math.radians(-60), 0, 0), mat=PARCH, bevel=0.006))
    parts.append(box("wax", (0.12, 0.12, 0.02), (0, 0.02, 0.09), mat=GOLD, bevel=0.008))
    return parts

PROP_BUILDERS = {"chest": prop_chest, "barrel": prop_barrel, "crate": prop_crate, "coins": prop_coins,
                 "spyglass": prop_spyglass, "cannon": prop_cannon, "lock": prop_lock, "flag": prop_flag,
                 "envelope": prop_envelope}

# ---------------------------------------------------------------- static scene
STAGE = bpy.data.materials.new("stage"); STAGE.use_nodes = True
sp = STAGE.node_tree.nodes["Principled BSDF"]
sp.inputs["Base Color"].default_value = (0.0113, 0.0113, 0.0113, 1.0)
sp.inputs["Roughness"].default_value = 1.0

def build_static():
    # big self-dark emissive backdrop (hides HDRI from camera, never washes out)
    big = box("backdrop-big", (30.0, 0.1, 16.0), (0, 4.5, 1.5))
    bm2 = bpy.data.materials.new("stage-em"); bm2.use_nodes = True
    bnt = bm2.node_tree; bnt.nodes.clear()
    bem = bnt.nodes.new("ShaderNodeEmission"); bem.inputs[0].default_value = (0.0113, 0.0113, 0.0113, 1.0)
    bout = bnt.nodes.new("ShaderNodeOutputMaterial")
    bnt.links.new(bem.outputs[0], bout.inputs[0])
    big.data.materials[0] = bm2

    img = bpy.data.images.load(CREST)
    m = bpy.data.materials.new("emblem"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    me = bpy.data.meshes.new("emblem-plane")
    ob = bpy.data.objects.new("emblem", me)
    scene.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    bm.to_mesh(me); bm.free()
    uvl = me.uv_layers.new(name="uv")
    for i in range(4):
        uvl.data[i].uv = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))[i]
    ob.scale = (3.1, 3.1, 1.0)  # 6.2 x 6.2 world
    ob.rotation_euler = (math.radians(90), 0, 0)
    ob.location = (0, 3.0, 0.4)
    me.materials.append(m)

    fm = bpy.data.materials.new("floor"); fm.use_nodes = True
    fp = fm.node_tree.nodes["Principled BSDF"]
    fp.inputs["Base Color"].default_value = (0.0022, 0.0022, 0.0022, 1.0)
    fp.inputs["Roughness"].default_value = 0.55
    fp.inputs["Metallic"].default_value = 0.2
    fme = bpy.data.meshes.new("floor-mesh")
    fob = bpy.data.objects.new("floor", fme)
    scene.collection.objects.link(fob)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    bm.to_mesh(fme); bm.free()
    fob.scale = (14.0, 9.0, 1.0)
    fob.location = (0, -1.5, FLOOR_Z)
    fme.materials.append(fm)

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (0, -9.5, 0.5)
    cam.rotation_euler = (math.radians(90) - TILT, 0, 0)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 13.6

    def area(name, loc, rot, size, energy, color):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.size = size; ld.energy = energy; ld.color = color
        ob = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(ob)
        ob.location = loc; ob.rotation_euler = rot
        ob.visible_camera = False
        return ob

    area("key",  (-4.5, -6.0, 5.0), (math.radians(48), 0, math.radians(-32)), 5.0, 1200, (1.0, 0.82, 0.60))
    area("rim",  ( 5.5,  0.5, 3.5), (math.radians(68), 0, math.radians(112)), 3.0, 900, (0.55, 0.65, 0.95))
    area("fill", ( 0.5, -7.0, 0.5), (math.radians(86), 0, 0), 7.0, 180, (1.0, 0.9, 0.8))
    area("soft", ( 0.0, -2.5, 7.5), (math.radians(18), 0, 0), 9.0, 250, (1.0, 0.95, 0.88))
    area("props", ( 0.0, -4.0, 1.2), (math.radians(78), 0, 0), 10.0, 550, (1.0, 0.88, 0.72))

build_static()

# ---------------------------------------------------------------- compositor
import os as _os
if _os.environ.get('OG_NOCOMP'):
    print("COMPOSITOR DISABLED FOR BISECT")
    scene.use_nodes = False
else:
    scene.use_nodes = True
tree = scene.node_tree
if tree is None:
    print("compositor fully off (bisect)")
else:
    tree.nodes.clear()
    rl = tree.nodes.new('CompositorNodeRLayers')
    comp = tree.nodes.new('CompositorNodeComposite')
    cur = rl
    _want = _os.environ.get('OG_COMP', 'all')
    _os.environ.setdefault('OG_COMP', 'all')
    if _want in ('all', 'glare'):
      try:
        g = tree.nodes.new('CompositorNodeGlare')
        g.glare_type = 'FOG_GLOW'; g.threshold = 1.0; g.size = 8; g.mix = -0.25
        tree.links.new(cur.outputs[0], g.inputs[0]); cur = g
        print("compositor: glare ok")
      except Exception as e:
        print("compositor: glare skipped", e)
    # ColorBalance node dropped: floods the frame in Blender 4.0.2 (AgX Punchy grades instead)
    if _want in ('all', 'vignette'):
      try:
        el = tree.nodes.new('CompositorNodeEllipseMask')
        el.width = 0.95; el.height = 0.9
        bl = tree.nodes.new('CompositorNodeBlur')
        bl.size_x = 300; bl.size_y = 300; bl.use_relative = True
        bl.factor = 0.5
        mx = tree.nodes.new('CompositorNodeMixRGB')
        mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 0.32
        tree.links.new(cur.outputs[0], mx.inputs[1])
        tree.links.new(el.outputs[0], bl.inputs[0])
        tree.links.new(bl.outputs[0], mx.inputs[2])
        cur = mx
        print("compositor: vignette ok")
      except Exception as e:
        print("compositor: vignette skipped", e)
    tree.links.new(cur.outputs[0], comp.inputs[0])

# ---------------------------------------------------------------- per-card build & render
def add_text(body, font_path, size, loc, extrude=0.055, mat=None):
    cu = bpy.data.curves.new(type='FONT', name=body)
    cu.body = body
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.extrude = extrude
    cu.bevel_depth = 0.014; cu.bevel_resolution = 2
    try:
        cu.font = bpy.data.fonts.load(font_path)
    except Exception:
        pass
    ob = bpy.data.objects.new(body, cu)
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (math.radians(90) - TILT, 0, 0)
    cu.size = size
    if mat:
        ob.data.materials.append(mat)
    return ob

KEEP = {"backdrop-big", "emblem", "floor", "cam", "key", "rim", "fill", "soft"}

def clear_card():
    for ob in list(scene.objects):
        if ob.name not in KEEP:
            bpy.data.objects.remove(ob, do_unlink=True)

def render_card(key):
    sub, props = CARDS[key]
    clear_card()
    for kind, x, s in props:
        parts = PROP_BUILDERS[kind]()
        root = bpy.data.objects.new(f"root-{kind}", None)
        scene.collection.objects.link(root)
        for p in parts:
            p.parent = root
        root.scale = (s * 1.2, s * 1.2, s * 1.2)
        root.location = (x, 0.6, FLOOR_Z + 0.02)
        if key == "404" and kind == "barrel":
            root.rotation_euler = (0, math.radians(90), 0)
            root.location = (x, 0.6, FLOOR_Z + 0.48)
    title = add_text("Buccaneer Salvage", PIRATA, 1.18, (0, 0, -1.35), mat=GOLD)
    sub_t = add_text(sub, CINZEL, 0.46, (0, 0, -2.25), extrude=0.02)
    sub_t.data.materials.append(PARCH)
    scene.render.filepath = f"{OUTDIR}/og-{key}"
    bpy.ops.render.render(write_still=True)
    print("WROTE", f"{OUTDIR}/og-{key}.jpg")

only = None
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    if args:
        only = args[0]

keys = [only] if only else list(CARDS.keys())
for k in keys:
    render_card(k)
print("ALL DONE", keys)
