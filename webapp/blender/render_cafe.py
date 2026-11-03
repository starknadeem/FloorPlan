#!/usr/bin/env python3
"""
render_cafe.py — reconstruct a CafeScene JSON in Blender and render it photoreal with Cycles.

This is System 3's offline / beauty-render path. It mirrors the real-time three.js engine:
  - geometry.ts   -> buildWallBoxes / roomShape / fixtureHeight / frameScene
  - models.ts     -> MODEL_CATALOG / MODEL_REGISTRY (same Kenney GLBs, same fit rules)
  - palette.ts    -> STYLE_PRESETS colours + lights
...but renders with a path tracer (true GI, soft shadows, real glass) instead of WebGL.

Coordinate mapping (single source of truth, matches geometry.ts 1.2):
    three.js world:  worldX = planX,  worldY = height,  worldZ = -planY   (Y-up)
    Blender (Z-up):  bx = planX,      by = planY,        bz = height
    => Blender(x,y,z) = (planX, planY, height). A rotation about three's +Y by a
       maps to a rotation about Blender's +Z by a (det +1 basis change, handedness kept).

Usage:
    blender --background --python render_cafe.py -- \
        --scene scene.json --out out.png \
        [--models-dir DIR] [--textures-dir DIR] \
        [--cam px,py,pz,tx,ty,tz]   (three.js WORLD coords: pos xyz, target xyz) \
        [--samples 128] [--res 1600x900] [--no-ceiling] [--sun-only]

Exit code 0 on success; prints "RENDER_OK <path>" on the last line.
"""

import sys
import os
import json
import math

import bpy  # type: ignore
import bmesh  # type: ignore
import mathutils  # type: ignore


# --------------------------------------------------------------------------------------
# constants mirrored from the TypeScript (keep in sync with geometry.ts / models.ts)
# --------------------------------------------------------------------------------------

KENNEY_FRONT_DEG = 180  # models.ts: Kenney pieces authored facing +Z; front -> local -Z
F = KENNEY_FRONT_DEG

# models.ts MODEL_CATALOG -> (glb filename, baseRotationDeg, fit)
MODEL_CATALOG = {
    "chair_cushion": ("chairCushion.glb", F, "contain"),
    "chair_wood": ("chair.glb", F, "contain"),
    "stool_bar": ("stoolBar.glb", F, "contain"),
    "sofa": ("loungeSofa.glb", F, "contain"),
    "sofa_long": ("loungeSofaLong.glb", F, "contain"),
    "bench_cushion": ("benchCushion.glb", F, "contain"),
    "table_round": ("tableRound.glb", 0, "contain"),
    "table_rect": ("table.glb", 0, "contain"),
    "fridge": ("kitchenFridge.glb", F, "contain"),
    "fridge_large": ("kitchenFridgeLarge.glb", F, "contain"),
    "fridge_small": ("kitchenFridgeSmall.glb", F, "contain"),
    "coffee_machine": ("kitchenCoffeeMachine.glb", F, "contain"),
    "blender": ("kitchenBlender.glb", F, "contain"),
    "stove": ("kitchenStove.glb", F, "contain"),
    "kitchen_sink": ("kitchenSink.glb", F, "contain"),
    "washer": ("washer.glb", F, "contain"),
    "cabinet": ("kitchenCabinet.glb", F, "contain"),
    "bookcase": ("bookcaseOpen.glb", F, "contain"),
    "plant_potted": ("pottedPlant.glb", 0, "contain"),
    "plant_small": ("plantSmall1.glb", 0, "contain"),
    "tv": ("televisionModern.glb", F, "contain"),
    "toilet": ("toilet.glb", F, "contain"),
    "bathroom_sink": ("bathroomSink.glb", F, "contain"),
    "mirror": ("bathroomMirror.glb", F, "contain"),
    "hood": ("hoodModern.glb", F, "contain"),
    "microwave": ("kitchenMicrowave.glb", F, "contain"),
    "toaster": ("toaster.glb", F, "contain"),
    "computer": ("computerScreen.glb", F, "contain"),
    "laptop": ("laptop.glb", F, "contain"),
    "crockery_cabinet": ("bookcaseClosedDoors.glb", F, "contain"),
    "wall_cabinet": ("kitchenCabinetUpper.glb", F, "contain"),
    "wall_cabinet_double": ("kitchenCabinetUpperDouble.glb", F, "contain"),
    "coat_rack": ("coatRackStanding.glb", 0, "contain"),
    "trashcan": ("trashcan.glb", 0, "contain"),
    "wall_lamp": ("lampWall.glb", F, "contain"),
    "box": ("cardboardBoxClosed.glb", 0, "contain"),
    "books": ("books.glb", 0, "contain"),
    "desk": ("desk.glb", F, "contain"),
    "desk_chair": ("chairDesk.glb", F, "contain"),
    "console": ("cabinetTelevision.glb", F, "contain"),
}

# models.ts MODEL_REGISTRY — default catalog key per fixture category
MODEL_REGISTRY = {
    "chair": "chair_cushion",
    "stool": "stool_bar",
    "sofa": "sofa",
    "banquette": "bench_cushion",
    "fridge": "fridge",
    "freezer": "fridge_large",
    "ice_maker": "fridge_small",
    "espresso_machine": "coffee_machine",
    "grinder": "blender",
    "blender": "blender",
    "mixer": "blender",
    "oven": "stove",
    "sink": "kitchen_sink",
    "dishwasher": "washer",
    "shelving": "bookcase",
    "plant": "plant_potted",
    "monitor": "tv",
    "toilet": "toilet",
}

# geometry.ts DEFAULT_HEIGHTS
DEFAULT_HEIGHTS = {
    "counter": 1.05, "espresso_machine": 0.55, "grinder": 0.5, "display_case": 0.6,
    "cooling_case": 1.2, "fridge": 1.9, "freezer": 0.9, "ice_maker": 0.8, "sink": 0.9,
    "dishwasher": 0.85, "oven": 0.9, "boiler": 0.5, "blender": 0.45, "mixer": 0.5,
    "monitor": 0.6, "table": 0.74, "chair": 0.9, "stool": 0.75, "sofa": 0.8,
    "banquette": 0.95, "shelving": 1.8, "menu_board": 0.9, "signage": 0.5, "plant": 1.1,
    "pendant_light": 0.3, "umbrella": 2.4, "cashier": 1.1, "toilet": 0.75, "generic": 0.8,
}

# geometry.ts CATEGORY_COLORS (sRGB hex) — used for parametric fallback boxes
CATEGORY_COLORS = {
    "counter": "#b07c46", "espresso_machine": "#8d9094", "grinder": "#6f7276",
    "display_case": "#c9d3d6", "cooling_case": "#c4ced1", "fridge": "#aeb4b8",
    "freezer": "#aeb4b8", "ice_maker": "#9aa0a4", "sink": "#b9bec1", "dishwasher": "#a7adb1",
    "oven": "#6a6d71", "boiler": "#7c7f83", "blender": "#7c7f83", "mixer": "#7c7f83",
    "monitor": "#2a2d30", "table": "#9a6b3c", "chair": "#3f4347", "stool": "#4a4e52",
    "sofa": "#6b5744", "banquette": "#6b5744", "shelving": "#8a6a44", "menu_board": "#cbb893",
    "signage": "#2f3335", "plant": "#4e7a46", "pendant_light": "#2d2f31", "umbrella": "#7d7a72",
    "cashier": "#8a6a44", "toilet": "#e8eaec", "generic": "#999999",
}

# palette.ts STYLE_PRESETS — only the fields the renderer needs
STYLE_PRESETS = {
    "industrial-chic": {
        "floor": "#c3ae90", "floorOutdoor": "#9a9690", "wall": "#cac4b8", "ceiling": "#b4b0a7",
        "glass": "#bcd4dd", "counterTop": "#d9d4cc", "wood": "#c0894c",
        "pendant": "#ffd49a", "colorTempK": 3000, "bg": "#e7e3da",
    },
    "scandinavian": {
        "floor": "#d9c4a0", "floorOutdoor": "#b8b2a6", "wall": "#eeece6", "ceiling": "#f3f1ec",
        "glass": "#cfe3ea", "counterTop": "#efede8", "wood": "#d7b88a",
        "pendant": "#ffe6c0", "colorTempK": 3600, "bg": "#eef0f0",
    },
    "cozy-warm": {
        "floor": "#b5885a", "floorOutdoor": "#9c8f7d", "wall": "#cab79d", "ceiling": "#c8bca4",
        "glass": "#cdd9d2", "counterTop": "#7a5236", "wood": "#8a5a34",
        "pendant": "#ffce8f", "colorTempK": 2700, "bg": "#efe6da",
    },
}
DEFAULT_STYLE = "industrial-chic"

# which categories should NOT be a fallback box (handled or intentionally invisible)
SKIP_FALLBACK = {"pendant_light"}  # lights are emitted separately


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------

def hex_to_linear(hex_str, alpha=1.0):
    """sRGB hex -> linear RGBA tuple for Blender node inputs."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def to_lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (to_lin(srgb[0]), to_lin(srgb[1]), to_lin(srgb[2]), alpha)


def kelvin_to_rgb(k):
    """Approximate black-body colour (linear-ish) for a light tint."""
    k = max(1000.0, min(12000.0, k)) / 100.0
    if k <= 66:
        r = 255.0
        g = 99.47 * math.log(k) - 161.12
    else:
        r = 329.7 * ((k - 60) ** -0.1332)
        g = 288.12 * ((k - 60) ** -0.0755)
    if k >= 66:
        b = 255.0
    elif k <= 19:
        b = 0.0
    else:
        b = 138.52 * math.log(k - 10) - 305.04
    clamp = lambda v: max(0.0, min(255.0, v)) / 255.0
    return (clamp(r), clamp(g), clamp(b))


def parse_args(argv):
    args = {
        "scene": None, "out": None, "models_dir": None, "textures_dir": None,
        "cam": None, "samples": 128, "res": (1600, 900),
        "ceiling": True, "sun_only": False, "style": None,
        "pano_out": None, "eye": 1.55, "pano_res": (2048, 1024), "max_stops": 10,
    }
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--scene": args["scene"] = argv[i + 1]; i += 2
        elif a == "--out": args["out"] = argv[i + 1]; i += 2
        elif a == "--models-dir": args["models_dir"] = argv[i + 1]; i += 2
        elif a == "--textures-dir": args["textures_dir"] = argv[i + 1]; i += 2
        elif a == "--cam": args["cam"] = [float(x) for x in argv[i + 1].split(",")]; i += 2
        elif a == "--samples": args["samples"] = int(argv[i + 1]); i += 2
        elif a == "--res":
            w, h = argv[i + 1].lower().split("x"); args["res"] = (int(w), int(h)); i += 2
        elif a == "--style": args["style"] = argv[i + 1]; i += 2
        elif a == "--no-ceiling": args["ceiling"] = False; i += 1
        elif a == "--sun-only": args["sun_only"] = True; i += 1
        elif a == "--pano-out": args["pano_out"] = argv[i + 1]; i += 2
        elif a == "--eye": args["eye"] = float(argv[i + 1]); i += 2
        elif a == "--pano-res":
            w, h = argv[i + 1].lower().split("x"); args["pano_res"] = (int(w), int(h)); i += 2
        elif a == "--max-stops": args["max_stops"] = int(argv[i + 1]); i += 2
        else: i += 1
    return args


# --------------------------------------------------------------------------------------
# scene bootstrap
# --------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    # prefer GPU if available, else CPU
    prefs = bpy.context.preferences.addons.get("cycles")
    try:
        cprefs = prefs.preferences
        for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                cprefs.compute_device_type = backend
                cprefs.get_devices()
                if any(d.type == backend for d in cprefs.devices):
                    sc.cycles.device = "GPU"
                    for d in cprefs.devices:
                        d.use = True
                    break
            except Exception:
                continue
    except Exception:
        pass
    return sc


# --------------------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------------------

_tex_cache = {}

def _img(path):
    if not path or not os.path.isfile(path):
        return None
    if path in _tex_cache:
        return _tex_cache[path]
    try:
        img = bpy.data.images.load(path, check_existing=True)
        _tex_cache[path] = img
        return img
    except Exception:
        return None


def mat_principled(name, color_hex, roughness=0.9, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(color_hex)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return m


def mat_glass(name, color_hex):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(color_hex)
    bsdf.inputs["Roughness"].default_value = 0.03
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 1.0
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.45
    return m


def mat_pbr(name, tex_dir, subfolder, color_hex, repeat):
    """PBR material from /textures/<subfolder>/{color,normal,rough}.jpg, tinted + tiled."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    base = os.path.join(tex_dir, subfolder) if tex_dir else None
    col = _img(os.path.join(base, "color.jpg")) if base else None
    if not col:
        bsdf.inputs["Base Color"].default_value = hex_to_linear(color_hex)
        bsdf.inputs["Roughness"].default_value = 0.95
        return m
    texco = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (repeat, repeat, repeat)
    nt.links.new(texco.outputs["UV"], mapping.inputs["Vector"])

    cnode = nt.nodes.new("ShaderNodeTexImage")
    cnode.image = col
    nt.links.new(mapping.outputs["Vector"], cnode.inputs["Vector"])
    nt.links.new(cnode.outputs["Color"], bsdf.inputs["Base Color"])

    rough = _img(os.path.join(base, "rough.jpg"))
    if rough:
        rough.colorspace_settings.name = "Non-Color"
        rnode = nt.nodes.new("ShaderNodeTexImage")
        rnode.image = rough
        nt.links.new(mapping.outputs["Vector"], rnode.inputs["Vector"])
        nt.links.new(rnode.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.9

    nrm = _img(os.path.join(base, "normal.jpg"))
    if nrm:
        nrm.colorspace_settings.name = "Non-Color"
        nnode = nt.nodes.new("ShaderNodeTexImage")
        nnode.image = nrm
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(mapping.outputs["Vector"], nnode.inputs["Vector"])
        nt.links.new(nnode.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# --------------------------------------------------------------------------------------
# geometry builders
# --------------------------------------------------------------------------------------

def add_box(name, size, location, rot_z=0.0, material=None, collection=None):
    """Axis-box of (sx,sy,sz) centred at location, rotated rot_z (radians) about Z."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.scale = (size[0], size[1], size[2])
    obj.rotation_euler = (0.0, 0.0, rot_z)
    obj.location = location
    if material:
        obj.data.materials.append(material)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def add_cylinder(name, radius, height, location, material=None, collection=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=radius, radius2=radius, depth=height)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    if material:
        obj.data.materials.append(material)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def build_table(f, mats, coll):
    """Parametric café table: round marble-ish top on a dark pedestal + base disk.
    Replaces the plain box the app renders parametrically (FurnitureModels.tsx)."""
    pos = f["position"]
    base = f.get("baseHeight", 0.0) or 0.0
    fp = f["footprint"]
    h = fixture_height(f)
    r = max(min(fp[0], fp[1]) / 2.0, 0.2)
    top_t = 0.04
    top = mats.get("table_top") or mat_principled("table_top", "#d9d4cc", 0.25)
    mats["table_top"] = top
    leg = mats.get("table_leg") or mat_principled("table_leg", "#3c3f42", 0.4, 0.6)
    mats["table_leg"] = leg
    add_cylinder(f"tbl_top_{f['id']}", r, top_t, (pos[0], pos[1], base + h - top_t / 2), top, coll)
    add_cylinder(f"tbl_col_{f['id']}", 0.05, h - top_t, (pos[0], pos[1], base + (h - top_t) / 2), leg, coll)
    add_cylinder(f"tbl_base_{f['id']}", r * 0.45, 0.03, (pos[0], pos[1], base + 0.015), leg, coll)


def build_wall_boxes(wall, openings):
    """Port of geometry.ts buildWallBoxes -> list of (u, yCenter, length, height, kind)
    plus glass panes (u, yCenter, width, height)."""
    ax, ay = wall["a"]
    bx, by = wall["b"]
    L = math.hypot(bx - ax, by - ay)
    H = wall["height"]
    boxes = []
    glass = []
    ops = sorted([o for o in openings if o["wallId"] == wall["id"]], key=lambda o: o["offset"])
    cursor = 0.0
    for op in ops:
        start = max(0.0, op["offset"])
        end = min(L, op["offset"] + op["width"])
        w = max(0.0, end - start)
        if w <= 0:
            continue
        if start > cursor + 1e-4:
            seg = start - cursor
            boxes.append((cursor + seg / 2, H / 2, seg, H, "solid"))
        sill = (op.get("sillHeight", 0.9) if op["type"] == "window" else 0.0)
        open_top = sill + op["height"]
        if sill > 1e-4:
            boxes.append((start + w / 2, sill / 2, w, sill, "sill"))
        if H - open_top > 1e-4:
            boxes.append((start + w / 2, open_top + (H - open_top) / 2, w, H - open_top, "header"))
        if op["type"] == "window":
            glass.append((start + w / 2, sill + op["height"] / 2, w, op["height"]))
        cursor = max(cursor, end)
    if cursor < L - 1e-4:
        seg = L - cursor
        boxes.append((cursor + seg / 2, H / 2, seg, H, "solid"))
    return boxes, glass


def build_walls(scene, mats, coll):
    openings = scene.get("openings", [])
    for wall in scene["walls"]:
        ax, ay = wall["a"]
        bx, by = wall["b"]
        angle = math.atan2(by - ay, bx - ax)
        base = wall.get("baseHeight", 0.0) or 0.0
        thick = wall["thickness"]
        dirx, diry = math.cos(angle), math.sin(angle)
        boxes, glass = build_wall_boxes(wall, openings)
        wall_mat = mats["wall_ext"] if wall.get("exterior") else mats["wall_int"]
        for (u, yc, length, height, kind) in boxes:
            cx = ax + dirx * u
            cy = ay + diry * u
            add_box(f"wall_{wall['id']}_{kind}", (length, thick, height),
                    (cx, cy, base + yc), angle, wall_mat, coll)
            if kind == "solid":
                # skirting / baseboard along the foot
                add_box(f"skirt_{wall['id']}", (length, thick + 0.02, 0.12),
                        (cx, cy, base + 0.06), angle, mats["skirt"], coll)
        for (u, yc, width, height) in glass:
            cx = ax + dirx * u
            cy = ay + diry * u
            add_box(f"glass_{wall['id']}", (width, 0.03, height),
                    (cx, cy, base + yc), angle, mats["glass"], coll)


def polygon_mesh(name, polygon, z, material, coll, uv_repeat=None):
    """Build a flat ngon face from a plan polygon at height z."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], z)) for p in polygon]
    try:
        face = bm.faces.new(verts)
    except ValueError:
        bm.free()
        return None
    bm.normal_update()
    if face.normal.z < 0:
        face.normal_flip()
    uv_layer = bm.loops.layers.uv.new()
    for loop in face.loops:
        co = loop.vert.co
        r = uv_repeat or 1.0
        loop[uv_layer].uv = (co.x * r, co.y * r)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    if material:
        obj.data.materials.append(material)
    coll.objects.link(obj)
    return obj


def build_rooms(scene, mats, tex_dir, want_ceiling, coll):
    for room in scene["rooms"]:
        outdoor = room.get("category") == "seating_outdoor"
        repeat = 0.5 if outdoor else 0.4
        floor_mat = mats["floor_outdoor"] if outdoor else mats["floor_indoor"]
        polygon_mesh(f"floor_{room['id']}", room["polygon"], 0.01, floor_mat, coll, repeat)
        ch = room.get("ceilingHeight", 0.0)
        if want_ceiling and ch and ch > 0:
            polygon_mesh(f"ceil_{room['id']}", room["polygon"], ch, mats["ceiling"], coll)


# --------------------------------------------------------------------------------------
# furniture (GLB import with per-url template caching + linked duplicates)
# --------------------------------------------------------------------------------------

_glb_templates = {}   # url -> (entries, size, mn, center) | None
# entries: list of (mesh_datablock, world_matrix) captured at import, then unlinked from the scene.


def _import_glb_template(path):
    """Import a GLB once, capture each mesh's data + baked world matrix, measure the combined
    bbox, then unlink the originals so they don't render. Instances share the mesh data."""
    if path in _glb_templates:
        return _glb_templates[path]
    if not os.path.isfile(path):
        _glb_templates[path] = None
        return None
    before = set(bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as e:
        print(f"  ! gltf import failed {path}: {e}")
        _glb_templates[path] = None
        return None
    imported = [o for o in bpy.data.objects if o not in before]
    mn = mathutils.Vector((1e9, 1e9, 1e9))
    mx = mathutils.Vector((-1e9, -1e9, -1e9))
    entries = []
    for o in imported:
        if o.type != "MESH":
            continue
        mw = o.matrix_world.copy()
        entries.append((o.data, mw))
        for corner in o.bound_box:
            wc = mw @ mathutils.Vector(corner)
            mn = mathutils.Vector((min(mn.x, wc.x), min(mn.y, wc.y), min(mn.z, wc.z)))
            mx = mathutils.Vector((max(mx.x, wc.x), max(mx.y, wc.y), max(mx.z, wc.z)))
    size = mx - mn
    center = (mn + mx) * 0.5
    # unlink originals from every collection (data survives via `entries`), so they never render
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
    rec = (entries, size, mn, center) if entries else None
    _glb_templates[path] = rec
    return rec


def resolve_model(category, model_key):
    if model_key and model_key in MODEL_CATALOG:
        return MODEL_CATALOG[model_key]
    key = MODEL_REGISTRY.get(category)
    return MODEL_CATALOG.get(key) if key else None


def fixture_height(f):
    h = f.get("height")
    if h and h > 0.01:
        return h
    return DEFAULT_HEIGHTS.get(f["category"], 0.8)


def build_fixtures(scene, models_dir, mats, coll):
    main = coll
    placed = 0
    fallbacks = 0
    for f in scene["fixtures"]:
        cat = f["category"]
        pos = f["position"]
        base = f.get("baseHeight", 0.0) or 0.0
        fp = f["footprint"]
        rot = math.radians(f.get("rotation", 0.0))
        model = resolve_model(cat, f.get("modelKey"))

        if model:
            fname, base_rot_deg, fit = model
            rec = _import_glb_template(os.path.join(models_dir, fname))
            if rec:
                entries, size, mn, center = rec
                # scale to footprint (ModelFixture.tsx): contain = min(sW,sD); width = sW
                tw = max(fp[0], 0.1)
                td = max(fp[1], 0.1)
                sW = tw / size.x if size.x > 1e-3 else 1.0
                sD = td / size.y if size.y > 1e-3 else 1.0  # plan depth -> Blender Y
                scale = min(sW, sD) if fit == "contain" else sW
                # M = T(pos) · Rz(rot+base) · S(scale) · T(center on x/y, min.z -> 0)
                T_pos = mathutils.Matrix.Translation((pos[0], pos[1], base))
                Rz = mathutils.Matrix.Rotation(rot + math.radians(base_rot_deg), 4, "Z")
                S = mathutils.Matrix.Diagonal((scale, scale, scale, 1.0))
                T_off = mathutils.Matrix.Translation((-center.x, -center.y, -mn.z))
                M = T_pos @ Rz @ S @ T_off
                for (mesh_data, mw) in entries:
                    o = bpy.data.objects.new(f"fx_{f['id']}", mesh_data)  # shares data = instanced
                    o.matrix_world = M @ mw
                    main.objects.link(o)
                placed += 1
                continue

        if cat in SKIP_FALLBACK:
            continue
        if cat == "table":
            build_table(f, mats, main)
            fallbacks += 1
            continue
        # parametric fallback box
        h = fixture_height(f)
        color = CATEGORY_COLORS.get(cat, "#999999")
        mat = mats.get(f"fb_{cat}")
        if not mat:
            mat = mat_principled(f"fb_{cat}", color, roughness=0.85)
            mats[f"fb_{cat}"] = mat
        add_box(f"fx_{f['id']}", (max(fp[0], 0.1), max(fp[1], 0.1), max(h, 0.1)),
                (pos[0], pos[1], base + h / 2), rot, mat, main)
        fallbacks += 1
    print(f"  fixtures: {placed} glb, {fallbacks} fallback boxes")


# --------------------------------------------------------------------------------------
# lighting + world
# --------------------------------------------------------------------------------------

def build_world(scene, style):
    world = bpy.data.worlds.new("CafeWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    # Nishita physical sky — realistic daylight through the windows, no HDRI file needed
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "NISHITA"
        sky.sun_elevation = math.radians(28)
        sky.sun_rotation = math.radians(50)
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.6
    except Exception:
        bg.inputs["Color"].default_value = hex_to_linear(style["bg"])
        bg.inputs["Strength"].default_value = 1.0


def build_lights(scene, style, coll):
    # Sun — crisp directional daylight. three.js directional was at world (14,18,10).
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 2.6
    sun_data.angle = math.radians(1.5)  # soft shadow edge
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(135))
    coll.objects.link(sun)

    # pendant / point lights from scene.lights
    tint = kelvin_to_rgb(style.get("colorTempK", 3000))
    lit_points = []
    for l in scene.get("lights", []):
        if l.get("type") not in ("pendant", "point", "spot"):
            continue
        p = l.get("position") or [0, 0]
        mh = l.get("mountHeight", 2.2)
        data = bpy.data.lights.new(f"pt_{l['id']}", "POINT")
        data.energy = 60.0 * float(l.get("intensity", 7)) / 7.0  # heuristic W, tuned to taste
        data.color = tint
        data.shadow_soft_size = 0.12
        o = bpy.data.objects.new(f"pt_{l['id']}", data)
        o.location = (p[0], p[1], mh)
        coll.objects.link(o)
        lit_points.append(p)

    # Guarantee every enclosed room has light. Cycles is physical: a windowless WC or back room
    # with no lamp renders pitch black (the furniture is there but invisible). Add a soft ceiling
    # fill to any ceilinged room that has no pendant/point light inside it.
    for room in scene.get("rooms", []):
        ch = room.get("ceilingHeight", 0) or 0
        if ch <= 0:
            continue  # outdoor / open to sky
        poly = room["polygon"]
        if any(_point_in_poly(poly, p[0], p[1]) for p in lit_points):
            continue  # already has a lamp
        cx, cy = _centroid(poly)
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        w = max(xs) - min(xs); d = max(ys) - min(ys)
        area = max(w * d, 1.0)
        data = bpy.data.lights.new(f"fill_{room['id']}", "AREA")
        data.shape = "RECTANGLE"
        data.size = min(max(w * 0.5, 0.4), 2.2)
        data.size_y = min(max(d * 0.5, 0.4), 2.2)
        data.energy = min(max(area * 18.0, 45.0), 280.0)
        data.color = tint
        o = bpy.data.objects.new(f"fill_{room['id']}", data)
        o.location = (cx, cy, ch - 0.08)  # just under the ceiling, facing down (area light -Z)
        coll.objects.link(o)


# --------------------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------------------

def bbox_plan(scene):
    xs, ys = [], []
    for w in scene["walls"]:
        xs += [w["a"][0], w["b"][0]]; ys += [w["a"][1], w["b"][1]]
    for r in scene["rooms"]:
        for p in r["polygon"]:
            xs.append(p[0]); ys.append(p[1])
    if not xs:
        return 0.0, 0.0, 10.0
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    span = max(max(xs) - min(xs), max(ys) - min(ys), 4.0)
    return cx, cy, span


def setup_camera(scene, cam_arg, res, coll):
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 24  # ~ three.js fov 52 on 16:9
    cam = bpy.data.objects.new("Camera", cam_data)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam

    if cam_arg and len(cam_arg) == 6:
        # three.js WORLD coords -> Blender (x,y,z) = (wx, -wz, wy)
        px, py, pz, tx, ty, tz = cam_arg
        loc = mathutils.Vector((px, -pz, py))
        tgt = mathutils.Vector((tx, -tz, ty))
    else:
        cx, cy, span = bbox_plan(scene)
        d = span * 1.05
        loc = mathutils.Vector((cx + d * 0.75, cy - d * 0.95, span * 0.7 + 3))
        tgt = mathutils.Vector((cx, cy, 1.1))

    cam.location = loc
    direction = (tgt - loc).normalized()
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# --------------------------------------------------------------------------------------
# 360 panorama tour
# --------------------------------------------------------------------------------------

def _centroid(poly):
    x = sum(p[0] for p in poly) / len(poly)
    y = sum(p[1] for p in poly) / len(poly)
    return x, y


def _point_in_poly(poly, x, y):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        denom = (yj - yi) or 1e-9
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / denom + xi:
            inside = not inside
        j = i
    return inside


def _nearest_inside(poly, x, y):
    """If (x,y) is outside the polygon, nudge toward the centroid until inside."""
    if _point_in_poly(poly, x, y):
        return x, y
    cx, cy = _centroid(poly)
    for t in (0.2, 0.4, 0.6, 0.8):
        nx, ny = x + (cx - x) * t, y + (cy - y) * t
        if _point_in_poly(poly, nx, ny):
            return nx, ny
    return cx, cy


def standing_points(scene, max_stops=10):
    """Eye-level viewpoints for the tour. One primary stop per room (always kept); a second
    stop for long rooms is an 'extra', added only while under the max_stops budget. This keeps
    every room represented while capping total render time."""
    primaries = []
    extras = []
    for room in scene["rooms"]:
        poly = room["polygon"]
        cx, cy = _centroid(poly)
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        w = max(xs) - min(xs); d = max(ys) - min(ys)
        label = room.get("name") or room.get("category") or room["id"]

        def mk(sx, sy, k, lab):
            sx, sy = _nearest_inside(poly, sx, sy)
            return {
                "id": f"{room['id']}_{k}",
                "name": lab,
                "category": room.get("category", "other"),
                "position": [round(sx, 3), round(sy, 3)],
                # yaw so the pano's centre faces the room centroid (nicer default heading)
                "yawDeg": round(math.degrees(math.atan2(cy - sy, cx - sx)), 1),
            }

        if max(w, d) > 6:
            if w >= d:
                a, b = (min(xs) + w * 0.3, cy), (min(xs) + w * 0.7, cy)
            else:
                a, b = (cx, min(ys) + d * 0.3), (cx, min(ys) + d * 0.7)
            primaries.append(mk(a[0], a[1], 0, f"{label} (1)"))
            extras.append(mk(b[0], b[1], 1, f"{label} (2)"))
        else:
            primaries.append(mk(cx, cy, 0, label))

    # always keep one per room; fill remaining budget with the long-room extras
    budget = max(len(primaries), max_stops)
    return (primaries + extras)[:budget]


def render_panos(scene, out_dir, eye, res, samples, max_stops=10):
    """Render an equirectangular 360 pano at each standing point; write a manifest.json.
    Prints PANO_TOTAL / PANO_DONE markers (flushed) so the caller can report live progress."""
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene

    cam_data = bpy.data.cameras.new("PanoCam")
    cam_data.type = "PANO"
    # Cycles equirectangular (property moved out of .cycles in Blender 4+)
    for target in (cam_data, getattr(cam_data, "cycles", None)):
        if target is not None and hasattr(target, "panorama_type"):
            try:
                target.panorama_type = "EQUIRECTANGULAR"
            except Exception:
                pass
    cam = bpy.data.objects.new("PanoCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = samples

    points = standing_points(scene, max_stops)
    print(f"PANO_TOTAL {len(points)}", flush=True)
    manifest = {"stops": []}
    for idx, pt in enumerate(points):
        x, y = pt["position"]
        cam.location = (x, y, eye)
        # upright pano: look at the horizon (+X local after this), yaw set per stop
        cam.rotation_euler = (math.radians(90), 0.0, math.radians(pt["yawDeg"]))
        fname = f"pano_{idx:02d}.jpg"
        sc.render.image_settings.file_format = "JPEG"
        sc.render.image_settings.quality = 90
        sc.render.filepath = os.path.join(out_dir, fname)
        print(f"[pano] {idx} {pt['name']} @ ({x:.2f},{y:.2f})", flush=True)
        bpy.ops.render.render(write_still=True)
        print(f"PANO_DONE {idx + 1} {pt['name']}", flush=True)
        manifest["stops"].append({
            "id": pt["id"], "name": pt["name"], "category": pt["category"],
            "position": pt["position"], "yawDeg": pt["yawDeg"], "image": fname,
        })

    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"PANO_OK {len(manifest['stops'])} {os.path.join(out_dir, 'manifest.json')}")


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def main():
    args = parse_args(sys.argv)
    if not args["scene"] or (not args["out"] and not args["pano_out"]):
        print("ERROR: --scene and (--out or --pano-out) are required")
        sys.exit(2)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    public = os.path.normpath(os.path.join(script_dir, "..", "public"))
    models_dir = args["models_dir"] or os.path.join(public, "models", "kenney")
    tex_dir = args["textures_dir"] or os.path.join(public, "textures")

    with open(args["scene"], "r") as fh:
        scene = json.load(fh)

    style_key = args["style"] or (scene.get("design") or {}).get("style") or DEFAULT_STYLE
    style = STYLE_PRESETS.get(style_key, STYLE_PRESETS[DEFAULT_STYLE])

    sc = reset_scene()
    sc.cycles.samples = args["samples"]
    sc.cycles.use_denoising = True
    # Keep the scene/BVH across renders — critical for the tour, where we render many panos of
    # the SAME scene: the geometry is acceleration-built once, not rebuilt per panorama.
    sc.render.use_persistent_data = True
    # Speed: cap light bounces. Interiors converge far faster with few bounces, and the
    # denoiser cleans the rest — the quality cost is small, the time saving is large.
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 8  # keep enough for window glass
    sc.cycles.volume_bounces = 0
    for attr, val in (("use_fast_gi", True), ("blur_glossy", 1.0)):
        try:
            setattr(sc.cycles, attr, val)
        except Exception:
            pass
    sc.render.resolution_x, sc.render.resolution_y = args["res"]
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "AgX"
    except Exception:
        pass

    coll = sc.collection

    print(f"[render_cafe] style={style_key} walls={len(scene['walls'])} "
          f"rooms={len(scene['rooms'])} fixtures={len(scene['fixtures'])}")

    mats = {
        "wall_int": mat_principled("wall_int", style["wall"], 0.92),
        "wall_ext": mat_principled("wall_ext", style["wall"], 0.95),
        "skirt": mat_principled("skirt", style["wall"], 0.6),
        "ceiling": mat_principled("ceiling", style["ceiling"], 0.95),
        "glass": mat_glass("glass", style["glass"]),
        "floor_indoor": mat_pbr("floor_indoor", tex_dir, "concrete", style["floor"], 0.4),
        "floor_outdoor": mat_pbr("floor_outdoor", tex_dir, "terrazzo", style["floorOutdoor"], 0.5),
    }
    # darken skirting
    mats["skirt"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = \
        tuple(c * 0.55 for c in hex_to_linear(style["wall"])[:3]) + (1.0,)

    pano = bool(args["pano_out"])
    build_world(scene, style)
    if not args["sun_only"]:
        build_lights(scene, style, coll)
    else:
        build_lights({"lights": []}, style, coll)
    # panos are shot from inside, so keep ceilings for enclosure; single shot can open the roof
    build_rooms(scene, mats, tex_dir, True if pano else args["ceiling"], coll)
    build_walls(scene, mats, coll)
    build_fixtures(scene, models_dir, mats, coll)

    if pano:
        render_panos(scene, args["pano_out"], args["eye"], args["pano_res"],
                     args["samples"], args["max_stops"])
        return

    setup_camera(scene, args["cam"], args["res"], coll)
    sc.render.filepath = os.path.abspath(args["out"])
    print("[render_cafe] rendering...")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OK {sc.render.filepath}")


if __name__ == "__main__":
    main()
