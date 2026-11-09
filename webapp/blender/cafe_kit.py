"""
cafe_kit.py — designer kit for building a café in Blender from a parsed CafeScene.

The AI design step writes a short `design.py` that composes these builders; the same script runs
in the user's live Blender (through the MCP addon socket) or headless (`blender --background`)
for stills and 360° panoramas.

Coordinates: Blender (x, y, z) = (planX, planY, height in metres). Rotations are degrees, CCW in
plan, about +Z. All builders return the object(s) they create and put them in a named collection.

WALL FACES: SCENE walls are centrelines with a thickness. Every builder that sits on or against a
wall (back_bar, shelving_wall, banquette, wall_panel, accent_wall, slat_screen, quote_wall, kiosk,
menu_screen, sign, art, mirror, wall_shelf, wall_sconce, neon_sign, letter_board) takes points on
the wall FACE inside the room: face = centreline ± thickness/2 (e.g. a west wall at x=0 with
thickness 0.25 has its room-side face at x=0.125).

Typical design.py:

    from cafe_kit import Kit
    K = Kit(SCENE, textures_dir=TEXTURES)      # SCENE / TEXTURES are injected by the runner
    K.architecture(wall="plaster", floors={"seating_indoor": "oak", "service_counter": "stone"})
    K.counter_run((0.7, 14.0), (0.7, 21.5), depth=0.7, top="terrazzo", front="walnut_slat")
    K.back_bar((0.0, 14.2), (0.0, 21.2), depth=0.55, shelves=3, cups=True)
    K.espresso_station((1.0, 17.0), rot=90)
    ...
    K.plan_equipment()                         # every fridge, oven, sink... from the plan, as detailed models
    K.lights(mood="day")                       # sky, sun through the glazing, fills
    K.camera((5.0, 12.0), look_at=(3.0, 18.0)) # eye-level camera for the hero still
    K.finish()                                 # EEVEE preview settings, selection cleanup
"""

import hashlib
import json
import math
import os
import random
import sys

import bpy  # type: ignore
import bmesh  # type: ignore
from mathutils import Vector  # type: ignore

# ----------------------------------------------------------------------------------------------
# material catalogue. K.M(name) builds on demand. Besides these names, ANY colour works:
#   "#c9a58b"            limewash/painted plaster in that colour
#   "plaster:#hex" "zellige:#hex" "subway:#hex" "hex_tile:#hex" "square_tile:#hex" "terracotta:#hex"
#   "veneer:#hex" "planks:#hex" "brick_paint:#hex" "concrete:#hex" "velvet:#hex" "boucle:#hex"
#   "linen:#hex" "leather:#hex" "felt:#hex"
# Textures tile at their true real-world size (from each folder's meta.json).
# ----------------------------------------------------------------------------------------------
FAMILIES = {"plaster": "plaster", "limewash": "beige_plaster", "zellige": "zellige", "subway": "subway", "hex_tile": "hex_tile", "square_tile": "square_tile",
            "terracotta": "terracotta_tile", "veneer": "veneer_b", "planks": "hinoki", "brick_paint": "brick_dark", "concrete": "concrete_brushed",
            "velvet": "velvet", "boucle": "boucle_teddy", "linen": "linen", "leather": "leather_white", "felt": "fabric", "marble": "marble_carrara"}
CATALOG = {
    # timber
    "oak": ("oak", "#c79f6e", 0.75), "oak_pale": ("oak_light", "#d9bf97", 0.8), "oak_smoked": ("oak_light", "#6a4b34", 0.7), "ash": ("ash", "#dcccb0", 0.8),
    "walnut": ("veneer_a", "#5e3d29", 0.65), "walnut_slat": ("veneer_a", "#54351f", 0.65), "mahogany": ("veneer_b", "#4f2319", 0.5), "ebony": ("veneer_c", "#221e1b", 0.5),
    "hinoki": ("hinoki", None, 0.85), "cedar": ("cedar", "#a8703f", 0.8), "old_boards": ("old_boards", None, 0.85), "parquet": ("parquet_herringbone", None, 0.6),
    "parquet_dark": ("parquet_herringbone", "#59402b", 0.55), "parquet_pale": ("parquet_herringbone", "#c9ae85", 0.65), "tatami": ("tatami", None, 1.0),
    # plaster, concrete, masonry
    "plaster": ("plaster", "#ece3d3", 1.0), "plaster_white": ("plaster", "#f2eee6", 1.0), "plaster_warm": ("plaster", "#dccdb5", 1.0), "lime_plaster": ("beige_plaster", "#d9ccb4", 1.0),
    "clay_plaster": ("clay_plaster", "#b78d68", 1.0), "concrete": ("concrete", "#a9a59d", 0.8), "concrete_dark": ("concrete_brushed", "#5b5956", 0.75), "concrete_ribbed": ("concrete_ribbed", "#9a968e", 0.9),
    "brick_red": ("brick_red", None, 1.0), "brick_white": ("brick_dark", "#e8e3d8", 1.0), "brick_black": ("brick_dark", "#39363a", 0.9), "brick_stone": ("brick_white", None, 1.0), "brick_herringbone": ("brick_herringbone", None, 0.9),
    # stone + tile
    "terrazzo": ("terrazzo", None, 0.45), "marble": ("marble_carrara", None, 1.0), "marble_white": ("marble_carrara", None, 1.0), "marble_nero": ("marble", None, 0.35), "marble_verde": ("marble", "#27473a", 0.35),
    "marble_rosso": ("marble", "#5c2a26", 0.35), "limestone": ("limestone_tile", None, 0.8), "stone": ("limestone_tile", "#b9b4ab", 0.8), "slate": ("slate", "#4a4644", 0.7), "granite": ("granite_tile", None, 0.6),
    "tile_check": ("checker", None, 0.45), "tile_white": ("subway", "#f2efe7", 1.0), "tile_stone_check": ("tile_patterned", None, 0.55), "tile_diamond": ("tile_interior", None, 0.55), "marble_mosaic": ("marble_mosaic", None, 0.5), "marble_tile": ("marble_tile", None, 0.5),
    # outdoors
    "paving": ("paving", "#9b968c", 1.0), "paving_herringbone": ("paving_herringbone", "#8f8678", 1.0), "cobble": ("cobble", None, 1.0),
    # textiles
    "rattan": ("hessian", "#c8a978", 1.0), "hessian": ("hessian", None, 1.0), "corduroy": ("corduroy", "#8a6a4a", 1.0), "rug": ("hessian", "#8d6e55", 1.0),
    "boucle": ("boucle_teddy", "#e6dfd0", 1.0), "boucle_sage": ("boucle_teddy", "#9fae95", 1.0), "leather": ("leather_brown", "#6b4a35", 0.7), "felt": ("fabric", "#2a2620", 1.0),
    "brushed_steel": ("brushed_steel", "#c9cbce", 1.0),
    # Coffee Berry brand finishes (client schedule "CB Leo ΥΛΙΚΑ" + 7. Photo references), see gen_client_textures.py
    "cb_floor": ("cb_soulant", None, 0.8),            # Soulant gris mat 60x120: shop floor + WC floor/walls
    "cb_prep_floor": ("cb_ariman", None, 0.9),        # Ariman grey mat R10 30x60: preparation room
    "cb_bar_tile": ("cb_sassiepietre", None, 0.75),   # COEM Sassiepietre Grigio 90.6: bar
    "cb_milazza": ("cb_milazza", None, 0.6),          # HPL Millaza matt (outdoor table tops, stand tops)
    "cb_oak": ("oak_light", "#cfae84", 0.65),         # light sonoma-oak melamine: worktops, cabinets, bean-dispenser panel
    "cb_marble_black": ("marble", "#26292b", 0.3),    # Nero Marquina-look counter fronts + splashbacks
    "rockfon": ("plaster", "#f5f4f0", 1.0),           # Rockfon Mono Acoustic seamless white ceiling
}
METAL_PBR = {"brushed_steel"}

# ----------------------------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------------------------

def hex_to_linear(h, alpha=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), alpha)


def kelvin_to_rgb(k):
    t = k / 100.0
    r = 255 if t <= 66 else max(0, min(255, 329.698727446 * ((t - 60) ** -0.1332047592)))
    g = max(0, min(255, 99.4708025861 * math.log(t) - 161.1195681661)) if t <= 66 else max(0, min(255, 288.1221695283 * ((t - 60) ** -0.0755148492)))
    b = 255 if t >= 66 else (0 if t <= 19 else max(0, min(255, 138.5177312231 * math.log(t - 10) - 305.0447927307)))
    return (r / 255.0, g / 255.0, b / 255.0)


def _principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _centroid(poly):
    x = sum(p[0] for p in poly) / len(poly)
    y = sum(p[1] for p in poly) / len(poly)
    return x, y


def point_in_poly(poly, x, y):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def project_uvs(bm, scale=1.0):
    """Per-face planar UVs in metres (dominant-axis projection), so tiled textures read at life size
    and survive glTF export (which needs real UV coordinates)."""
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            c = loop.vert.co
            if az >= ax and az >= ay:
                u, v = c.x, c.y
            elif ax >= ay:
                u, v = c.y, c.z
            else:
                u, v = c.x, c.z
            loop[uv].uv = (u * scale, v * scale)
    return bm


def crisp_smooth(bm, angle=32.0):
    """Shade smooth but keep edges sharper than `angle` crisp, so bevels catch a real highlight."""
    bm.normal_update()
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0.0) < lim


def lathe_into(bm, profile, center, seg=14):
    """Revolve a (radius, z) profile about +Z into an existing bmesh (fast, for repeated props)."""
    cx, cy, cz = center
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((cx, cy, cz + z))])
        else:
            rings.append([bm.verts.new((cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg), cz + z)) for k in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
            elif len(b) == 1:
                bm.faces.new((a[k], b[0], a[(k + 1) % seg]))
            else:
                bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))


# ----------------------------------------------------------------------------------------------
# the kit
# ----------------------------------------------------------------------------------------------

class Kit:
    def __init__(self, scene, textures_dir=None, seed=None, style=None, collection="Cafe", clear=True, brand="coffeeberry"):
        """seed: the runner passes a fresh SEED per design, so every run differs even on the same plan
        (without one, the plan geometry is hashed, which repeats). style: design language, selects which
        library variants may appear (industrial, scandinavian, japandi, bistro, mediterranean, deco,
        midcentury, biophilic, brutalist, retro, modern, cozy)."""
        self.scene = scene
        self.tex = textures_dir
        if seed is None:
            seed = self._seed_from_scene(scene)
        self.seed = seed
        self.rng = random.Random(seed)
        self._mood = "day"
        self._runs = []       # counters/back bars, so equipment can sit on them
        self._occupied = []   # (x, y, radius) of placed equipment
        self._canopies = []   # (x, y, radius) of trees
        self._faces_cache = {}
        self._face_used = {}
        self._finished = set()     # rooms a design already finished by hand
        self._plan_done = False
        self.sc = bpy.context.scene
        if clear:
            self.clear_scene()
        self.coll = self._collection(collection)
        self.mats = {}
        self._img_cache = {}
        self._build_materials()
        self.stops = []   # suggested camera standing points (x, y, yaw_deg, label)
        self.cameras = []
        # ---- real-asset library (curated GLBs) ----
        self.style = style
        self.brand = brand   # the client's own models (manifest "brand") always win over generic library variants
        self._here = os.path.dirname(os.path.abspath(__file__))
        self.assets_root = os.path.join(self._here, "assets")
        self.models_dir = os.path.join(self.assets_root, "models")
        self.manifest = self._load_manifest()
        self._asset_templates = {}        # file -> (entries, size, mn, center) | None
        self._chosen = {}                 # category -> locked variant entry (one model per café, coherent)
        self._placed = []                 # (object, library file, part index), so the web export can swap in low-detail models

    # ---------------- scene plumbing ----------------
    def clear_scene(self):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(bpy.data.collections):
            bpy.data.collections.remove(c)
        for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves):
            for d in list(blk):
                if d.users == 0:
                    blk.remove(d)

    def _collection(self, name):
        c = bpy.data.collections.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
            self.sc.collection.children.link(c)
        return c

    # ---------------- materials ----------------
    def _img(self, path):
        if not path or not os.path.isfile(path):
            return None
        if path in self._img_cache:
            return self._img_cache[path]
        try:
            img = bpy.data.images.load(path, check_existing=True)
        except Exception:
            return None
        self._img_cache[path] = img
        return img

    def mat_plain(self, name, color, roughness=0.6, metallic=0.0, coat=0.0, emission=None, strength=0.0, alpha=1.0):
        if name in self.mats:
            return self.mats[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = _principled(m)
        p.inputs["Base Color"].default_value = hex_to_linear(color)
        p.inputs["Roughness"].default_value = roughness
        p.inputs["Metallic"].default_value = metallic
        if coat and "Coat Weight" in p.inputs:
            p.inputs["Coat Weight"].default_value = coat
        if emission:
            p.inputs["Emission Color"].default_value = hex_to_linear(emission)
            p.inputs["Emission Strength"].default_value = strength
        if alpha < 1.0:
            p.inputs["Alpha"].default_value = alpha
            m.blend_method = "BLEND" if hasattr(m, "blend_method") else m.blend_method
        self.mats[name] = m
        return m

    def mat_glass(self, name="glass", color="#dfeeee"):
        if name in self.mats:
            return self.mats[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = _principled(m)
        p.inputs["Base Color"].default_value = hex_to_linear(color)
        p.inputs["Roughness"].default_value = 0.03
        if "Transmission Weight" in p.inputs:
            p.inputs["Transmission Weight"].default_value = 1.0
        p.inputs["IOR"].default_value = 1.45
        self.mats[name] = m
        return m

    def _tinted(self, img, tint, roughness_mul=None):
        """Packed copy of `img` recoloured so its MEAN lands exactly on `tint` (variation kept, works on dark or
        light sources), or a roughness map scaled by roughness_mul. Baked so colour survives glTF export."""
        key = (img.name, tint, roughness_mul)
        if key in self._img_cache:
            return self._img_cache[key]
        if (tint in (None, "#ffffff") and not roughness_mul) or (roughness_mul == 1.0):
            self._img_cache[key] = img
            return img
        import numpy as np
        t = img.copy()
        t.name = f"{img.name}_{(tint or 'r').strip('#')}{'' if roughness_mul is None else f'_r{roughness_mul}'}"
        px = np.empty(len(t.pixels), dtype=np.float32)
        t.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        if roughness_mul is not None:
            px[:, :3] = np.clip(px[:, :3] * roughness_mul, 0.0, 1.0)
        else:
            h = tint.lstrip("#")
            c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)
            lum = px[:, :3].mean(axis=1, keepdims=True)
            px[:, :3] = np.clip(c * (lum / max(float(lum.mean()), 1e-3)), 0.0, 1.0)
        t.pixels.foreach_set(px.ravel())
        t.update()
        try:
            t.pack()
        except Exception:
            pass
        self._img_cache[key] = t
        return t

    def mat_pbr(self, name, folder, tint="#ffffff", scale=None, roughness_mul=1.0, metallic=0.0):
        """PBR from textures/<folder>/{color,normal,rough}.jpg, tinted and tiled (scale = tiles/m, default: the
        texture's true real-world size). Built the way the glTF exporter understands: UV → Mapping → Image → Principled."""
        if name in self.mats:
            return self.mats[name]
        if scale is None:
            try:
                scale = 1.0 / json.load(open(os.path.join(self.tex, folder, "meta.json")))["size_m"][0]
            except Exception:
                scale = 1.0
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = _principled(m)
        p.inputs["Metallic"].default_value = metallic
        base = os.path.join(self.tex, folder) if self.tex else None
        col = self._img(os.path.join(base, "color.jpg")) if base else None
        if not col:
            p.inputs["Base Color"].default_value = hex_to_linear(tint)
            p.inputs["Roughness"].default_value = 0.8
            self.mats[name] = m
            return m
        texco = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (scale, scale, 1.0)
        nt.links.new(texco.outputs["UV"], mapping.inputs["Vector"])
        cnode = nt.nodes.new("ShaderNodeTexImage")
        cnode.image = self._tinted(col, tint)
        nt.links.new(mapping.outputs["Vector"], cnode.inputs["Vector"])
        nt.links.new(cnode.outputs["Color"], p.inputs["Base Color"])
        rough = self._img(os.path.join(base, "rough.jpg"))
        if rough:
            rimg = self._tinted(rough, None, roughness_mul)
            rimg.colorspace_settings.name = "Non-Color"
            rnode = nt.nodes.new("ShaderNodeTexImage")
            rnode.image = rimg
            nt.links.new(mapping.outputs["Vector"], rnode.inputs["Vector"])
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(rnode.outputs["Color"], sep.inputs["Color"])
            nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
        else:
            p.inputs["Roughness"].default_value = 0.8 * roughness_mul
        nrm = self._img(os.path.join(base, "normal.jpg"))
        if nrm:
            nrm.colorspace_settings.name = "Non-Color"
            nnode = nt.nodes.new("ShaderNodeTexImage")
            nnode.image = nrm
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.inputs["Strength"].default_value = 0.6
            nt.links.new(mapping.outputs["Vector"], nnode.inputs["Vector"])
            nt.links.new(nnode.outputs["Color"], nmap.inputs["Color"])
            nt.links.new(nmap.outputs["Normal"], p.inputs["Normal"])
        self.mats[name] = m
        return m

    def mat_checker(self, name, c1="#e9e2d6", c2="#3a3632", scale=0.3):
        """Two-tone checker tile floor from textures/checker (a real image, so it exports to glTF).
        One image = 2×2 tiles of `scale` metres; c1/c2 are kept for API compatibility."""
        return self.mat_pbr(name, "checker", "#ffffff", scale=1.0 / (2 * scale), roughness_mul=0.5)

    def _build_materials(self):
        """Plain (non-image) finishes. Image-based ones build on demand in M()."""
        self.mat_plain("ceiling", "#2d2b29", roughness=0.95)
        self.mat_plain("ceiling_light", "#ece7dd", roughness=0.9)
        self.mat_plain("sage", "#9aa88f", roughness=0.9)
        self.mat_plain("terracotta_paint", "#b9704f", roughness=0.9)
        self.mat_plain("ink", "#20262a", roughness=0.9)
        self.mat_plain("ochre", "#c9a15a", roughness=0.9)
        self.mat_plain("mirror", "#e8e8e8", roughness=0.02, metallic=1.0)
        self.mat_plain("neon", "#000000", emission="#ff9a6a", strength=14.0)
        self.mat_plain("bulb", "#000000", emission="#ffd9a0", strength=14.0)
        self.mat_plain("paper", "#efe6d4", roughness=0.9)
        self.mat_plain("black", "#161616", roughness=0.5)
        self.mat_plain("black_steel", "#1d1d1e", roughness=0.42, metallic=0.75)
        self.mat_plain("charcoal", "#3b3a39", roughness=0.8)
        self.mat_plain("steel", "#b9bcbf", roughness=0.28, metallic=1.0)
        self.mat_plain("chrome", "#e6e7e9", roughness=0.07, metallic=1.0)
        self.mat_plain("brass", "#c49a56", roughness=0.27, metallic=1.0)
        self.mat_plain("bronze", "#8a6a48", roughness=0.4, metallic=0.95)
        self.mat_plain("copper", "#b76e45", roughness=0.28, metallic=1.0)
        self.mat_plain("cream", "#eae2d3", roughness=0.8)
        self.mat_plain("white", "#f4f1ea", roughness=0.5)
        self.mat_plain("cup", "#f4f1ea", roughness=0.25, coat=0.5)
        self.mat_plain("kraft", "#b48a5a", roughness=0.8)
        self.mat_plain("pastry", "#c98d4d", roughness=0.7)
        self.mat_plain("pastry_dark", "#8a5a30", roughness=0.7)
        self.mat_plain("leaf_a", "#3f5f2e", roughness=0.42)
        self.mat_plain("leaf_b", "#58783c", roughness=0.45)
        self.mat_plain("leaf_c", "#2f4d27", roughness=0.4)
        self.mat_plain("leaf_stem", "#5a5a30", roughness=0.7)
        self.mat_plain("leaf_dark", "#141f10", roughness=0.95)
        self.mat_plain("box_light", "#4f7a34", roughness=0.42)
        self.mat_plain("box_mid", "#35592a", roughness=0.45)
        self.mat_plain("box_deep", "#1f3a1c", roughness=0.6)
        self.mat_plain("leaf_olive", "#5e6e48", roughness=0.5)
        self.mat_plain("leaf_olive2", "#77875d", roughness=0.5)
        self.mat_plain("leaf_olive3", "#a1ab8c", roughness=0.62)
        self.mat_plain("greens", "#5f7f46", roughness=0.8)
        self.mat_plain("olive_green", "#7d8a66", roughness=0.9)
        self.mat_plain("bark", "#4d4238", roughness=0.95)
        self.mat_plain("pot", "#a69f95", roughness=0.85)
        self.mat_plain("soil", "#2c2219", roughness=1.0)
        self.mat_plain("canvas", "#eee8da", roughness=0.95)
        self.mat_plain("enamel_sage", "#9fae95", roughness=0.25, coat=0.6)
        self.mat_plain("matte_black", "#1a1a1a", roughness=0.6)
        self.mat_plain("screen", "#0d0f12", roughness=0.15, emission="#3a5468", strength=1.2)
        self.mat_plain("led", "#000000", emission="#ffc78a", strength=5.0)
        self.mat_plain("led_cool", "#000000", emission="#fff0d6", strength=6.0)
        self.mat_plain("opal", "#f3ece0", roughness=0.4, emission="#ffd29a", strength=3.5)
        self.mat_plain("lens", "#000000", emission="#fff0d6", strength=9.0)
        self.mat_plain("red", "#9b2d20", roughness=0.5)
        self.mat_plain("beans", "#4a2a16", roughness=0.7)
        self.mat_plain("roof", "#3a3a3c", roughness=0.9)
        self.mat_plain("rubber", "#111111", roughness=0.9)
        self.mat_glass("glass")
        self.mat_glass("display_glass", "#eef7f5")
        self.mat_plain("dark_glass", "#1b2326", roughness=0.12, metallic=0.3)

    def mat_image(self, name, path, roughness=0.5, emit=0.0):
        """Material from one image file (art prints, menu boards). emit>0 makes it glow (screens)."""
        if name in self.mats:
            return self.mats[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = _principled(m)
        p.inputs["Roughness"].default_value = roughness
        img = self._img(path)
        if img:
            uv = nt.nodes.new("ShaderNodeTexCoord")
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img
            t.extension = "CLIP"
            nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
            nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
            if emit:
                nt.links.new(t.outputs["Color"], p.inputs["Emission Color"])
                p.inputs["Emission Strength"].default_value = emit
        self.mats[name] = m
        return m

    def M(self, name):
        """Material by name: a catalogue entry, a plain finish, "#hex" (painted plaster) or "family:#hex"."""
        if name in self.mats:
            return self.mats[name]
        if name.startswith("#"):
            return self.mat_pbr(name, "plaster", name, roughness_mul=1.0)
        if ":" in name:
            fam, col = name.split(":", 1)
            folder = FAMILIES.get(fam)
            if folder:
                rough = {"zellige": 1.0, "subway": 1.0, "hex_tile": 1.0, "square_tile": 1.0, "veneer": 0.65, "planks": 0.8, "leather": 0.7}.get(fam, 1.0)
                return self.mat_pbr(name, folder, col, roughness_mul=rough)
        spec = CATALOG.get(name)
        if spec:
            folder, tint, rough = spec
            return self.mat_pbr(name, folder, tint or "#ffffff", roughness_mul=rough, metallic=1.0 if name in METAL_PBR else 0.0)
        print(f"[cafe_kit] unknown material {name!r}, using plaster", flush=True)
        return self.M("plaster")

    # ---------------- real-asset library (curated GLBs) ----------------
    def _seed_from_scene(self, scene):
        """Stable hash of the plan geometry: same plan → same seed, different plan → different seed."""
        try:
            key = json.dumps([[w.get("a"), w.get("b")] for w in scene.get("walls", [])],
                             sort_keys=True) + str(len(scene.get("rooms", [])))
        except Exception:
            key = str(len(scene.get("walls", [])))
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def _load_manifest(self):
        path = os.path.join(self.assets_root, "manifest.json")
        if not os.path.isfile(path):
            return {}
        try:
            data = json.load(open(path))
            return {k: v for k, v in data.items() if isinstance(v, list)}
        except Exception as e:  # noqa: BLE001
            print(f"[cafe_kit] manifest load failed: {e}")
            return {}

    def _asset_template(self, file):
        """Import a curated GLB once, capture each mesh's data + baked world matrix and the combined
        bbox, then unlink the originals. Instances share the mesh data (cheap for many chairs)."""
        import mathutils
        if file in self._asset_templates:
            return self._asset_templates[file]
        path = os.path.join(self.models_dir, file)
        if not os.path.isfile(path):
            print(f"[cafe_kit] asset missing: {path}")
            self._asset_templates[file] = None
            return None
        before = set(bpy.data.objects)
        try:
            bpy.ops.import_scene.gltf(filepath=path)
        except Exception as e:  # noqa: BLE001
            print(f"[cafe_kit] gltf import failed {file}: {e}")
            self._asset_templates[file] = None
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
            for c in o.bound_box:
                wc = mw @ mathutils.Vector(c)
                mn = mathutils.Vector((min(mn.x, wc.x), min(mn.y, wc.y), min(mn.z, wc.z)))
                mx = mathutils.Vector((max(mx.x, wc.x), max(mx.y, wc.y), max(mx.z, wc.z)))
        for o in imported:
            for c in list(o.users_collection):
                c.objects.unlink(o)
        rec = (entries, mx - mn, mn, (mn + mx) * 0.5) if entries else None
        self._asset_templates[file] = rec
        return rec

    def pick_asset(self, category, style=None, variant=None):
        """One model per category per café (coherent inside a building), chosen with the run's seed from the
        variants tagged for the design style, so different runs get different furniture."""
        items = self.manifest.get(category)
        if not items:
            return None
        if variant:
            for it in items:
                if it.get("variant") == variant:
                    return it
        key = (category, style or self.style)
        if key in self._chosen:
            return self._chosen[key]
        if self.brand:
            # the client re-uses the same furniture and equipment in every shop: their models are not optional
            own = [it for it in items if it.get("brand") == self.brand]
            if own:
                self._chosen[key] = own[0]
                return own[0]
        st = style or self.style
        pool = [it for it in items if st in it.get("style_tags", [])] if st else items
        chosen = self.rng.choice(pool or items)
        self._chosen[key] = chosen
        return chosen

    def place(self, category, at, rot=0.0, style=None, variant=None, fit=None,
              footprint=None, z=0.0, coll=None, name=None, height=None):
        """Place a curated GLB from the library. Returns the created objects, or None if no asset is
        available for `category` (callers then fall back to their parametric build). fit 'real' keeps
        the model's true size; 'contain'/'width' scale it to `footprint` (plan w,d); 'stretch' scales x/y to
        `footprint` exactly and z to `height` (tables: the plan's top size, the brand's model)."""
        import mathutils
        it = self.pick_asset(category, style, variant)
        if not it:
            return None
        rec = self._asset_template(it["file"])
        if not rec:
            return None
        entries, size, mn, center = rec
        fit = fit or it.get("fit", "real")
        sx = sy = sz = 1.0
        if fit in ("contain", "width") and footprint:
            sW = footprint[0] / size.x if size.x > 1e-3 else 1.0
            sD = footprint[1] / size.y if size.y > 1e-3 else 1.0
            sx = sy = sz = min(sW, sD) if fit == "contain" else sW
        elif fit == "stretch":
            if footprint:
                sx = footprint[0] / size.x if size.x > 1e-3 else 1.0
                sy = footprint[1] / size.y if size.y > 1e-3 else 1.0
            sz = (height / size.z) if (height and size.z > 1e-3) else 1.0
        rotz = math.radians(rot + it.get("forward_deg", 0))
        M = (mathutils.Matrix.Translation((at[0], at[1], z))
             @ mathutils.Matrix.Rotation(rotz, 4, "Z")
             @ mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
             @ mathutils.Matrix.Translation((-center.x, -center.y, -mn.z)))
        g = coll or self.coll
        objs = []
        for idx, (data, mw) in enumerate(entries):
            o = bpy.data.objects.new(name or f"{category}_{it['variant']}", data)
            o.matrix_world = M @ mw
            g.objects.link(o)
            objs.append(o)
            self._placed.append((o, it["file"], idx))
        return objs

    # ---------------- geometry primitives ----------------
    def box(self, name, size, loc, rot=0.0, mat=None, coll=None, bevel=None):
        """Box: size (w along x, d along y, h), loc = centre (x, y, z), rot degrees about Z. Edges get a small
        real bevel so they catch light like joinery (bevel=0 for flush architecture)."""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        res = bmesh.ops.create_cube(bm, size=1.0)
        sz = (max(size[0], 1e-4), max(size[1], 1e-4), max(size[2], 1e-4))
        bmesh.ops.scale(bm, vec=sz, verts=res["verts"])
        if bevel is None:
            bevel = 0.0035 if min(sz) > 0.012 else 0.0
        if bevel > 0 and min(sz) > bevel * 2.2:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type="OFFSET", segments=2 if bevel > 0.01 else 1, profile=0.5, affect="EDGES", clamp_overlap=True)
        crisp_smooth(bm)
        project_uvs(bm)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.location = loc
        o.rotation_euler = (0, 0, math.radians(rot))
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def cyl(self, name, r, h, loc, mat=None, segments=24, r_top=None, rot=(0, 0, 0), coll=None):
        """Cylinder (or cone when r_top given); loc = centre of the base."""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r if r_top is None else r_top, depth=h)
        bm.normal_update()
        project_uvs(bm)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = segments >= 12 and len(poly.vertices) == 4
        o = bpy.data.objects.new(name, mesh)
        o.location = (loc[0], loc[1], loc[2] + h / 2)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def rod(self, name, p0, p1, r, mat=None, segments=12, coll=None):
        """Round bar between two 3D points (rails, spouts, branches, ribs, rods at any angle)."""
        a, b = Vector(p0), Vector(p1)
        d = b - a
        L = d.length or 1e-4
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r, depth=L)
        crisp_smooth(bm, 50.0)
        project_uvs(bm)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = d.to_track_quat("Z", "Y")
        o.location = (a + b) * 0.5
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def sphere(self, name, r, loc, mat=None, scale=(1, 1, 1), coll=None):
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
        bm.normal_update()
        project_uvs(bm)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.location = loc
        o.scale = scale
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        for poly in mesh.polygons:
            poly.use_smooth = True
        return o

    def slab(self, name, polygon, z, mat, thickness=0.0, coll=None):
        """Flat ngon (or extruded slab) from a plan polygon at height z."""
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
        if thickness:
            r = bmesh.ops.extrude_face_region(bm, geom=[face])
            vs = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, verts=vs, vec=(0, 0, -thickness))
        bm.normal_update()
        project_uvs(bm)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def text(self, name, body, loc, rot=0.0, size=0.3, mat=None, extrude=0.01, align="CENTER", upright=True, coll=None):
        """3D text (brand wordmark, menu headings). upright=True stands it on a wall: `rot` is the wall
        direction and the text FACES THE LEFT of that direction (the room side, like every run), so it
        reads correctly from the room. A fascia read from the street uses the direction with the street
        on its left."""
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = size
        cu.extrude = extrude
        cu.align_x = align
        o = bpy.data.objects.new(name, cu)
        o.location = loc
        o.rotation_euler = (math.radians(90) if upright else 0, 0, math.radians(rot + 180 if upright else rot))
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def _along(self, a, b, depth_side=1):
        """Direction helpers for a run from a to b: unit along, unit normal (left of travel), length, angle deg."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-9
        ux, uy = dx / L, dy / L
        nx, ny = -uy * depth_side, ux * depth_side
        return (ux, uy), (nx, ny), L, math.degrees(math.atan2(dy, dx))

    # ---------------- architecture from the plan ----------------
    def architecture(self, wall="plaster", floors=None, ceiling="plaster_white", skirting=True, downlights=True, glazing=True,
                     ground="paving", skirt_mat="charcoal", frame_mat="black_steel", door_mat="oak_smoked", context=True):
        """The building shell from the plan: walls, glazed windows with frames, real doors (frames, thresholds, leaves),
        floors per room category, ceilings, roof, site ground and neighbours. floors: {category: material}."""
        S = self.scene
        floors = floors or {}
        wm = self.M(wall)
        fr = self.M(frame_mat)
        openings = S.get("openings", [])
        arch = self._collection("Architecture")
        for w in S["walls"]:
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-4:
                continue
            ang = math.degrees(math.atan2(by - ay, bx - ax))
            ux, uy = (bx - ax) / L, (by - ay) / L
            H = max(w["height"], self._adjacent_ceiling(w)); t = w["thickness"]; base = w.get("baseHeight") or 0.0
            ops = sorted([o for o in openings if o["wallId"] == w["id"]], key=lambda o: o["offset"])
            segs = []
            cursor = 0.0
            for op in ops:
                s0 = max(0.0, op["offset"]); s1 = min(L, op["offset"] + op["width"])
                if s1 - s0 <= 0:
                    continue
                if s0 > cursor + 1e-4:
                    segs.append((cursor, s0, 0.0, H, "solid"))
                sill = (op.get("sillHeight") or 0.9) if op["type"] == "window" else 0.0
                top = sill + op["height"]
                if sill > 1e-4:
                    segs.append((s0, s1, 0.0, sill, "sill"))
                if H - top > 1e-4:
                    segs.append((s0, s1, top, H, "header"))
                if op["type"] == "window" and glazing:
                    segs.append((s0, s1, sill, top, "glass"))
                elif op["type"] != "window":
                    segs.append((s0, s1, 0.0, top, "door"))
                cursor = max(cursor, s1)
            if cursor < L - 1e-4:
                segs.append((cursor, L, 0.0, H, "solid"))
            for (s0, s1, z0, z1, kind) in segs:
                u = (s0 + s1) / 2
                cx, cy = ax + ux * u, ay + uy * u
                if kind == "glass":
                    self._window(w, cx, cy, ang, s0, s1, z0 + base, z1 + base, t, fr, arch)
                elif kind == "door":
                    self._door(w, cx, cy, ang, s1 - s0, z1, t, fr, self.M(door_mat), arch)
                else:
                    self.box(f"wall_{w['id']}_{kind}", (s1 - s0, t, z1 - z0), (cx, cy, base + (z0 + z1) / 2), ang, wm, arch, bevel=0)
                    if kind == "solid" and skirting:
                        self.box(f"skirt_{w['id']}", (s1 - s0, t + 0.024, 0.11), (cx, cy, base + 0.055), ang, self.M(skirt_mat), arch)
        top = max((w["height"] for w in S["walls"]), default=3.0)
        for room in S["rooms"]:
            cat = room.get("category", "other")
            fm = floors.get(cat) or floors.get(room["id"]) or ("paving" if cat == "seating_outdoor" else "oak" if cat in ("seating_indoor", "entrance", "corridor") else "stone" if cat == "service_counter" else "concrete")
            self.slab(f"floor_{room['id']}", room["polygon"], 0.0, self.M(fm), coll=arch)
            ch = room.get("ceilingHeight") or 0
            if ch > 0:
                self.slab(f"ceiling_{room['id']}", room["polygon"], ch, self.M(ceiling), coll=arch)
                self.slab(f"ceiling_roof_{room['id']}", room["polygon"], max(top, ch + 0.2), self.M("roof"), coll=arch)
                if downlights:
                    work = cat in ("preparation", "kitchen", "storage") or str(cat).startswith("wc")
                    area = self._room_area(room)
                    self.downlights(room["polygon"], ch, coll=arch, power=(min(55.0, area * 3.2) if work else min(28.0, 6.0 + area * 2.5)), kelvin=4000 if work else 3000)
        self._site(ground, context, arch)
        return arch

    def _adjacent_ceiling(self, w):
        """Highest ceiling of a room touching this wall, so a low partition is carried up as a bulkhead (no sky gap)."""
        ax, ay = w["a"]; bx, by = w["b"]
        L = math.hypot(bx - ax, by - ay) or 1.0
        nx, ny = -(by - ay) / L, (bx - ax) / L
        off = w["thickness"] / 2 + 0.08
        best = 0.0
        for t in (0.1, 0.3, 0.5, 0.7, 0.9):
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            for sd in (1, -1):
                r = self._room_at(x + nx * off * sd, y + ny * off * sd)
                if r:
                    best = max(best, r.get("ceilingHeight") or 0.0)
        return best

    def _room_at(self, x, y):
        for r in self.scene["rooms"]:
            if point_in_poly(r["polygon"], x, y):
                return r
        return None

    def _window(self, w, cx, cy, ang, s0, s1, z0, z1, t, fr, arch):
        width = s1 - s0
        r = math.radians(ang)
        ux, uy = math.cos(r), math.sin(r)
        self.box(f"glass_{w['id']}", (width, 0.016, z1 - z0), (cx, cy, (z0 + z1) / 2), ang, self.M("glass"), arch, bevel=0)
        for zz, tk in ((z0 + 0.03, 0.06), (z1 - 0.03, 0.06)):
            self.box(f"frame_{w['id']}", (width, t + 0.024, tk), (cx, cy, zz), ang, fr, arch)
        n = max(1, int(width / 1.15))
        for k in range(n + 1):
            d = -width / 2 + width * k / n
            self.box(f"mullion_{w['id']}", (0.055, t * 0.7, z1 - z0), (cx + ux * d, cy + uy * d, (z0 + z1) / 2), ang, fr, arch)
        if z1 - z0 > 2.0:   # storefront transom
            self.box(f"mullion_{w['id']}_tr", (width, t * 0.7, 0.045), (cx, cy, z1 - 0.55), ang, fr, arch)

    def _door(self, w, cx, cy, ang, width, height, t, fr, leaf, arch):
        """Frame, threshold and a door leaf. Glazed entrance leaves on the envelope; timber leaf standing open inside."""
        r = math.radians(ang)
        ux, uy = math.cos(r), math.sin(r)
        nx, ny = -uy, ux
        for sd in (-1, 1):
            self.box(f"frame_jamb_{w['id']}", (0.06, t + 0.03, height), (cx + ux * sd * (width / 2 - 0.03), cy + uy * sd * (width / 2 - 0.03), height / 2), ang, fr, arch)
        self.box(f"frame_head_{w['id']}", (width, t + 0.03, 0.07), (cx, cy, height - 0.035), ang, fr, arch)
        self.box(f"floor_threshold_{w['id']}", (width, t + 0.06, 0.012), (cx, cy, 0.006), ang, self.M("brass" if w.get("exterior") else "charcoal"), arch)
        inner_w = width - 0.12
        if w.get("exterior"):
            # aluminium-framed glass leaf with a long pull handle (glass_/frame_ names stay walkable on the web)
            n = 2 if width > 1.25 else 1
            lw = inner_w / n
            for i in range(n):
                d = -inner_w / 2 + lw * (i + 0.5)
                lx, ly = cx + ux * d, cy + uy * d
                self.box(f"glass_door_{w['id']}", (lw - 0.02, 0.012, height - 0.1), (lx, ly, (height - 0.07) / 2), ang, self.M("glass"), arch, bevel=0)
                for sd in (-1, 1):
                    self.box(f"frame_leaf_{w['id']}", (0.05, 0.04, height - 0.1), (lx + ux * sd * (lw / 2 - 0.035), ly + uy * sd * (lw / 2 - 0.035), (height - 0.07) / 2), ang, fr, arch)
                for zz in (0.1, height - 0.13):
                    self.box(f"frame_rail_{w['id']}", (lw - 0.04, 0.04, 0.12 if zz < 1 else 0.05), (lx, ly, zz), ang, fr, arch)
                hx = lx + ux * (lw / 2 - 0.1) * (1 if i == 0 and n == 2 else -1)
                for sd in (-1, 1):
                    self.cyl(f"frame_pull_{w['id']}", 0.012, 1.0, (hx + nx * sd * 0.055, (ly + uy * (lw / 2 - 0.1) * (1 if i == 0 and n == 2 else -1)) + ny * sd * 0.055, 0.6), self.M("brass"), 12, coll=arch)
        else:
            # timber leaf open at 95 degrees into the room, hinged on one jamb
            hx, hy = cx - ux * inner_w / 2, cy - uy * inner_w / 2
            sd = 1 if self._room_at(cx + nx * (t / 2 + 0.2), cy + ny * (t / 2 + 0.2)) else -1
            a = math.radians(ang + 95 * sd)
            lx, ly = hx + math.cos(a) * inner_w / 2, hy + math.sin(a) * inner_w / 2
            self.box(f"frame_doorleaf_{w['id']}", (inner_w, 0.04, height - 0.08), (lx, ly, (height - 0.08) / 2), math.degrees(a), leaf, arch)
            kx, ky = hx + math.cos(a) * (inner_w - 0.07), hy + math.sin(a) * (inner_w - 0.07)
            self.rod(f"frame_knob_{w['id']}", (kx - math.sin(a) * 0.07, ky + math.cos(a) * 0.07, 1.03), (kx + math.sin(a) * 0.07, ky - math.cos(a) * 0.07, 1.03), 0.013, self.M("brass"), 12, arch)

    def _site(self, ground, context, arch):
        """Ground around the building (no void at door thresholds) and quiet neighbours on the horizon."""
        xs, ys = [], []
        for w in self.scene["walls"]:
            xs += [w["a"][0], w["b"][0]]; ys += [w["a"][1], w["b"][1]]
        for r in self.scene["rooms"]:
            xs += [p[0] for p in r["polygon"]]; ys += [p[1] for p in r["polygon"]]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        M = 90.0
        self.slab("floor_site", [(x0 - M, y0 - M), (x1 + M, y0 - M), (x1 + M, y1 + M), (x0 - M, y1 + M)], -0.012, self.M(ground), coll=arch)
        if not context:
            return
        tones = ["#bdb4a6", "#a79c8e", "#cabfb0", "#9d9a94"]
        win = self.M("dark_glass")
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for i, (dx, dy, w_, d_, h_) in enumerate(((0, -66, 70, 12, 9), (-68, -6, 12, 70, 9), (68, -8, 12, 70, 10), (0, 68, 80, 12, 9))):
            m = self.mat_plain(f"ctx{i}", tones[i % 4], roughness=0.95)
            self.box(f"wall_ctx_{i}", (w_, d_, h_), (cx + dx, cy + dy, h_ / 2), 0, m, arch, bevel=0)
            alongx = w_ > d_
            face = (dy < 0 and alongx) or (dx < 0 and not alongx)
            n = int((w_ if alongx else d_) / 3.4)
            for lv in range(int(h_ / 3.4)):
                for k in range(n):
                    off = -(n - 1) * 1.7 + k * 3.4
                    z = 2.0 + lv * 3.4
                    if alongx:
                        y = cy + dy + (d_ / 2 + 0.03) * (1 if dy < 0 else -1)
                        self.box(f"wall_ctxw_{i}", (1.5, 0.05, 1.9), (cx + dx + off, y, z), 0, win, arch, bevel=0)
                    else:
                        x = cx + dx + (w_ / 2 + 0.03) * (1 if dx < 0 else -1)
                        self.box(f"wall_ctxw_{i}", (0.05, 1.5, 1.9), (x, cy + dy + off, z), 0, win, arch, bevel=0)

    # ---------------- wall faces: lets a design finish every wall of a room without hand coordinates ----------------
    def faces(self, target="all"):
        """Interior wall faces, each {a, b, len, room, category, wall, ceil, openings:[(s0, s1, z0, z1)]}, with the room on the
        LEFT of a→b so they plug straight into wall_panel / shelving_wall / banquette etc. target: "all", a room id or a room category."""
        out = []
        ops = self.scene.get("openings", [])
        for w in self.scene["walls"]:
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay)
            if L < 0.2:
                continue
            ux, uy = (bx - ax) / L, (by - ay) / L
            t = w["thickness"]
            for sd in (1, -1):
                nx, ny = -uy * sd, ux * sd
                steps = max(2, int(L / 0.1))
                cur = None
                runs = []
                for i in range(steps):
                    u = (i + 0.5) * L / steps
                    r = self._room_at(ax + ux * u + nx * (t / 2 + 0.08), ay + uy * u + ny * (t / 2 + 0.08))
                    rid = r["id"] if r and (r.get("ceilingHeight") or 0) > 0 else None
                    if rid != cur:
                        if cur is not None:
                            runs[-1][2] = (i) * L / steps
                        if rid is not None:
                            runs.append([rid, i * L / steps, L])
                        cur = rid
                for rid, s0, s1 in runs:
                    if s1 - s0 < 0.25:
                        continue
                    room = next(r for r in self.scene["rooms"] if r["id"] == rid)
                    if target not in ("all", rid, room.get("category")):
                        continue
                    pa = (ax + ux * s0 + nx * t / 2, ay + uy * s0 + ny * t / 2)
                    pb = (ax + ux * s1 + nx * t / 2, ay + uy * s1 + ny * t / 2)
                    gaps = []
                    for o in ops:
                        if o["wallId"] != w["id"]:
                            continue
                        o0, o1 = max(s0, o["offset"]), min(s1, o["offset"] + o["width"])
                        if o1 - o0 < 0.05:
                            continue
                        sill = (o.get("sillHeight") or 0.9) if o["type"] == "window" else 0.0
                        gaps.append((o0 - s0, o1 - s0, sill, sill + o["height"]))
                    # travel so the room is on the left
                    if sd == 1:
                        a_, b_, g_ = pa, pb, sorted(gaps)
                    else:
                        ln = s1 - s0
                        a_, b_, g_ = pb, pa, sorted((ln - g[1], ln - g[0], g[2], g[3]) for g in gaps)
                    out.append({"a": a_, "b": b_, "len": s1 - s0, "room": rid, "category": room.get("category"), "wall": w["id"], "ceil": room.get("ceilingHeight") or 3.0, "openings": g_})
        return out

    def _skin(self, f, s0, s1, z0, z1, mat, thick=0.012, name="wall_finish", bevel=0):
        if s1 - s0 < 0.01 or z1 - z0 < 0.005:
            return
        ax, ay = f["a"]; bx, by = f["b"]
        L = f["len"]
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        u = (s0 + s1) / 2
        self.box(name, (s1 - s0, thick, z1 - z0), (ax + ux * u + nx * thick / 2, ay + uy * u + ny * thick / 2, (z0 + z1) / 2), math.degrees(math.atan2(uy, ux)), mat, self._collection("Design"), bevel=bevel)

    def _face_rects(self, f, z0, z1):
        """Solid (s0, s1, z0, z1) rectangles of a face between heights, cut around doors and windows."""
        rects = []
        cur = 0.0
        for (g0, g1, gz0, gz1) in f["openings"]:
            if g0 > cur:
                rects.append((cur, g0, z0, z1))
            if gz0 > z0:
                rects.append((g0, g1, z0, min(gz0, z1)))
            if gz1 < z1:
                rects.append((g0, g1, max(gz1, z0), z1))
            cur = max(cur, g1)
        if cur < f["len"]:
            rects.append((cur, f["len"], z0, z1))
        return rects

    def finish_walls(self, target="all", finish=None, dado=None, dado_h=1.1, dado_style="plain", rail=None, crown=None, skirting=None, skirting_h=0.14, only_longest=False):
        """Dress every wall of a room in one call. target: "all", a room id or a category. finish: wall material or "#hex".
        dado: lower-wall material (zellige, subway, paint or timber) up to dado_h; dado_style "plain" | "panel" (raised panel moulding)
        | "beadboard". rail: chair-rail material. crown: cornice material. skirting: tall skirting material."""
        self._finished.add(target)
        fs = self.faces(target)
        if only_longest and fs:
            fs = [max(fs, key=lambda f: f["len"])]
        for f in fs:
            ch = f["ceil"]
            d = dado_h if dado else 0.0
            if finish:
                for (s0, s1, z0, z1) in self._face_rects(f, d, ch):
                    self._skin(f, s0, s1, z0, z1, self.M(finish))
            if dado:
                dm = self.M(dado)
                for (s0, s1, z0, z1) in self._face_rects(f, 0.0, d):
                    self._skin(f, s0, s1, z0, z1, dm, thick=0.016)
                    w_ = s1 - s0
                    if dado_style == "panel" and z1 - z0 > 0.5:
                        n = max(1, int(w_ / 0.75))
                        pw = w_ / n
                        for k in range(n):
                            c = s0 + pw * (k + 0.5)
                            ph, pz0, pz1 = pw - 0.12, z0 + 0.2, z1 - 0.1
                            for (ss0, ss1, zz0, zz1) in ((c - ph / 2, c + ph / 2, pz1 - 0.025, pz1), (c - ph / 2, c + ph / 2, pz0, pz0 + 0.025), (c - ph / 2, c - ph / 2 + 0.025, pz0, pz1), (c + ph / 2 - 0.025, c + ph / 2, pz0, pz1)):
                                self._skin(f, ss0, ss1, zz0, zz1, dm, thick=0.03, bevel=0.004)
                    elif dado_style == "beadboard":
                        for k in range(int(w_ / 0.09)):
                            self._skin(f, s0 + k * 0.09, s0 + k * 0.09 + 0.012, z0, z1, dm, thick=0.022, bevel=0)
                if rail is None:
                    rail = dado if dado_style != "plain" else None
            if rail and d:
                for (s0, s1, z0, z1) in self._face_rects(f, d - 0.02, d + 0.03):
                    self._skin(f, s0, s1, z0, z1, self.M(rail), thick=0.035, bevel=0.006)
            if crown:
                cm = self.M(crown)
                for (s0, s1, z0, z1) in self._face_rects(f, ch - 0.14, ch):
                    self._skin(f, s0, s1, max(z0, ch - 0.14), z1, cm, thick=0.03, bevel=0.005)
                    self._skin(f, s0, s1, max(z0, ch - 0.07), z1, cm, thick=0.06, bevel=0.006)
            if skirting:
                sm = self.M(skirting)
                for (s0, s1, z0, z1) in self._face_rects(f, 0.0, skirting_h):
                    if z1 > 0 and z0 < 0.01:
                        self._skin(f, s0, s1, z0, z1, sm, thick=0.03, bevel=0.004)
        return len(fs)

    def facade(self, material="brick_red", plinth="stone", plinth_h=0.45, cornice="plaster_white", pilasters=None, awning=None, band=None, band_z=None):
        """Dress the street-facing envelope: cladding, plinth, cornice, optional pilasters, sign band and awnings over glazing."""
        g = self._collection("Facade")
        top = max((w["height"] for w in self.scene["walls"]), default=4.0)
        ops = self.scene.get("openings", [])
        n_faces = 0
        for w in self.scene["walls"]:
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay)
            if L < 0.3:
                continue
            ux, uy = (bx - ax) / L, (by - ay) / L
            t = w["thickness"]
            mid = (ax + bx) / 2, (ay + by) / 2
            for sd in (1, -1):
                nx, ny = -uy * sd, ux * sd
                here = self._room_at(mid[0] + nx * (t / 2 + 0.1), mid[1] + ny * (t / 2 + 0.1))
                back = self._room_at(mid[0] - nx * (t / 2 + 0.1), mid[1] - ny * (t / 2 + 0.1))
                if (here and (here.get("ceilingHeight") or 0) > 0) or not (back and (back.get("ceilingHeight") or 0) > 0):
                    continue
                n_faces += 1
                # outer face travelling with the outside on the left
                pa = (ax + nx * t / 2, ay + ny * t / 2); pb = (bx + nx * t / 2, by + ny * t / 2)
                gaps = []
                for o in ops:
                    if o["wallId"] == w["id"]:
                        sill = (o.get("sillHeight") or 0.9) if o["type"] == "window" else 0.0
                        g0, g1 = o["offset"], o["offset"] + o["width"]
                        gaps.append((g0, g1, sill, sill + o["height"]) if sd == 1 else (L - g1, L - g0, sill, sill + o["height"]))
                f = {"a": pa if sd == 1 else pb, "b": pb if sd == 1 else pa, "len": L, "openings": sorted(gaps), "ceil": top}
                for (s0, s1, z0, z1) in self._face_rects(f, plinth_h if plinth else 0.0, top):
                    self._skin(f, s0, s1, z0, z1, self.M(material), thick=0.03, name="wall_clad")
                if plinth:
                    for (s0, s1, z0, z1) in self._face_rects(f, 0.0, plinth_h):
                        self._skin(f, s0, s1, z0, z1, self.M(plinth), thick=0.05, name="wall_plinth", bevel=0.006)
                if cornice:
                    self._skin(f, -0.1, L + 0.1, top - 0.22, top, self.M(cornice), thick=0.09, name="wall_cornice", bevel=0.012)
                    self._skin(f, -0.05, L + 0.05, top - 0.34, top - 0.22, self.M(cornice), thick=0.055, name="wall_cornice", bevel=0.008)
                if band:
                    bz = band_z or (max((g[3] for g in gaps), default=2.8) + 0.06)
                    self._skin(f, 0.0, L, bz, bz + 0.62, self.M(band), thick=0.07, name="wall_band", bevel=0.01)
                if pilasters and gaps:
                    for s_ in {round(g[0] - 0.13, 3) for g in gaps} | {round(gaps[-1][1] + 0.13, 3)}:
                        if 0.05 < s_ < L - 0.05:
                            self._skin(f, s_ - 0.11, s_ + 0.11, 0, top - 0.34, self.M(pilasters), thick=0.08, name="wall_pilaster", bevel=0.01)
                if awning:
                    self._awning(f, gaps, awning, g)
        return n_faces

    def _awning(self, f, gaps, colour, g):
        ax, ay = f["a"]; bx, by = f["b"]
        L = f["len"]
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        ang = math.degrees(math.atan2(uy, ux))
        col = self.mat_plain(f"awning_{colour}", colour, roughness=0.9)
        for (g0, g1, gz0, gz1) in gaps:
            w_ = g1 - g0 + 0.2
            c = (g0 + g1) / 2
            z = gz1 + 0.3
            bm = bmesh.new()
            n = 2
            vs = []
            for i in range(n):
                t = i / (n - 1)
                d = 0.03 + 0.85 * t
                zz = z - 0.42 * t
                vs.append((bm.verts.new((-w_ / 2, d, zz)), bm.verts.new((w_ / 2, d, zz))))
            bm.faces.new((vs[0][1], vs[0][0], vs[1][0], vs[1][1]))
            stripes = max(3, int(w_ / 0.32))
            for k in range(stripes):
                x0 = -w_ / 2 + w_ * k / stripes; x1 = x0 + w_ / stripes
                a_, b_ = bm.verts.new((x0, 0.88, z - 0.42)), bm.verts.new((x1, 0.88, z - 0.42))
                c_, d_ = bm.verts.new((x1 - 0.0, 0.885, z - 0.56)), bm.verts.new((x0 + 0.0, 0.885, z - 0.56))
                bm.faces.new((a_, b_, c_, d_))
            bm.normal_update(); project_uvs(bm)
            me = bpy.data.meshes.new("awning")
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new("wall_awning", me)
            o.data.materials.append(col)
            o.location = (ax + ux * c, ay + uy * c, 0)
            o.rotation_euler = (0, 0, math.radians(ang))
            g.objects.link(o)

    def downlights(self, polygon, z, step=2.0, margin=0.75, power=28.0, coll=None, kelvin=3000):
        xs = [p[0] for p in polygon]; ys = [p[1] for p in polygon]
        n = 0
        x = min(xs) + margin
        while x <= max(xs) - margin:
            y = min(ys) + margin
            while y <= max(ys) - margin:
                if point_in_poly(polygon, x, y):
                    self.cyl(f"downlight", 0.055, 0.02, (x, y, z - 0.02), self.M("lens"), 16, coll=coll)
                    d = bpy.data.lights.new("downlight", "SPOT")
                    d.energy = power; d.spot_size = math.radians(88); d.spot_blend = 0.8
                    d.color = kelvin_to_rgb(kelvin); d.shadow_soft_size = 0.06
                    o = bpy.data.objects.new("downlight", d)
                    o.location = (x, y, z - 0.03)
                    o.rotation_euler = (0, 0, 0)  # spot points -Z
                    (coll or self.coll).objects.link(o)
                    n += 1
                y += step
            x += step
        return n

    # ---------------- joinery & equipment ----------------
    def _front(self, name, a, b, n, depth_off, z0, z1, front, g):
        """Counter/case fronts. `front`: material, or "fluted:<mat>" (reeded), "slat:<mat>", "panel:<mat>", "tile:<mat>"."""
        (ax, ay), (bx, by) = a, b
        L = math.hypot(bx - ax, by - ay) or 1e-6
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = n
        ang = math.degrees(math.atan2(uy, ux))
        style, mat = (front.split(":", 1) + [None])[:2] if front.split(":", 1)[0] in ("fluted", "slat", "panel", "tile") else ("flat", front)
        if style == "flat" or style == "tile":
            return self.box(f"{name}_front", (L, 0.015, z1 - z0), ((ax + bx) / 2 + nx * depth_off, (ay + by) / 2 + ny * depth_off, (z0 + z1) / 2), ang, self.M(mat), g, bevel=0.002)
        if style == "panel":
            self.box(f"{name}_front", (L, 0.012, z1 - z0), ((ax + bx) / 2 + nx * depth_off, (ay + by) / 2 + ny * depth_off, (z0 + z1) / 2), ang, self.M(mat), g, bevel=0)
            n_ = max(1, int(L / 0.6))
            for i in range(n_):
                c = L * (i + 0.5) / n_
                pw = L / n_ - 0.09
                cx, cy = ax + ux * c + nx * (depth_off + 0.012), ay + uy * c + ny * (depth_off + 0.012)
                self.box(f"{name}_pn", (pw, 0.018, z1 - z0 - 0.12), (cx, cy, (z0 + z1) / 2), ang, self.M(mat), g, bevel=0.007)
            return None
        # reeds (half-round, one mesh) or square slats
        pitch = 0.034 if style == "fluted" else 0.055
        r = pitch * 0.5
        bm = bmesh.new()
        ct = int(L / pitch)
        for i in range(ct):
            c = (i + 0.5) * L / ct
            px, py = ax + ux * c + nx * depth_off, ay + uy * c + ny * depth_off
            if style == "fluted":
                segs = 7
                bot, top = [], []
                for k in range(segs):
                    t = math.pi * k / (segs - 1)
                    ox = math.cos(t) * r * 0.98
                    oy = math.sin(t) * r * 0.9
                    x, y = px + ux * ox + nx * oy, py + uy * ox + ny * oy
                    bot.append(bm.verts.new((x, y, z0))); top.append(bm.verts.new((x, y, z1)))
                for k in range(segs - 1):
                    bm.faces.new((bot[k], bot[k + 1], top[k + 1], top[k]))
            else:
                w_ = pitch * 0.55
                dd = 0.022
                pts = [(-w_ / 2, 0), (w_ / 2, 0), (w_ / 2, dd), (-w_ / 2, dd)]
                vs_b = [bm.verts.new((px + ux * o + nx * e, py + uy * o + ny * e, z0)) for o, e in pts]
                vs_t = [bm.verts.new((px + ux * o + nx * e, py + uy * o + ny * e, z1)) for o, e in pts]
                for k in range(4):
                    bm.faces.new((vs_b[k], vs_b[(k + 1) % 4], vs_t[(k + 1) % 4], vs_t[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        crisp_smooth(bm, 70.0 if style == "fluted" else 32.0)
        project_uvs(bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(f"{name}_reeds", me)
        o.data.materials.append(self.M(mat))
        g.objects.link(o)
        self.box(f"{name}_front", (L, 0.012, z1 - z0), ((ax + bx) / 2 + nx * (depth_off - 0.004), (ay + by) / 2 + ny * (depth_off - 0.004), (z0 + z1) / 2), ang, self.M("black" if style == "slat" else mat), g, bevel=0)
        return o

    def counter_run(self, a, b, depth=0.7, h=0.95, top="terrazzo", front="fluted:walnut", led_kick=True, top_thick=0.04, side=1, rail=None, name="counter"):
        """Service counter from a to b. Body extends `depth` to the LEFT of a→b (side=1) or right (side=-1): the BARISTA works on
        that side; customers stand on the a→b line side. front: material or "fluted:<mat>", "slat:<mat>", "panel:<mat>".
        rail: foot-rail metal ("brass", "chrome", "black_steel") along the customer face."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        g = self._collection("Joinery")
        self._runs.append({"a": a, "b": b, "n": (nx, ny), "u": (ux, uy), "L": L, "depth": depth, "h": h, "front": (-nx, -ny), "line": a, "name": name, "ang": ang, "items": []})
        self.box(f"{name}_plinth", (L, depth - 0.1, 0.1), (cx, cy, 0.05), ang, self.M("black"), g)
        self.box(f"{name}_body", (L, depth - 0.02, h - 0.1 - top_thick), (cx, cy, 0.1 + (h - 0.1 - top_thick) / 2), ang, self.M("charcoal"), g, bevel=0)
        # customer face at a→b line, sits just proud of the body
        self._front(name, a, b, (-nx, -ny), -0.012 * 0 + 0.002, 0.1, h - top_thick, front, g)
        self.box(f"{name}_top", (L + 0.04, depth + 0.08, top_thick), (cx - nx * 0.03, cy - ny * 0.03, h - top_thick / 2), ang, self.M(top), g, bevel=0.006)
        if rail:
            ox, oy = -nx * 0.09, -ny * 0.09
            p0 = (a[0] + ox, a[1] + oy); p1 = (b[0] + ox, b[1] + oy)
            self.rod(f"{name}_rail", (p0[0], p0[1], 0.2), (p1[0], p1[1], 0.2), 0.019, self.M(rail), 14, g)
            for i in range(max(2, int(L / 1.1) + 1)):
                t_ = i / max(1, max(2, int(L / 1.1) + 1) - 1)
                x_, y_ = p0[0] + (p1[0] - p0[0]) * t_, p0[1] + (p1[1] - p0[1]) * t_
                self.cyl(f"{name}_railpost", 0.012, 0.2, (x_, y_, 0.0), self.M(rail), 10, coll=g)
        if led_kick:
            fx, fy = cx - nx * (depth / 2 - 0.05), cy - ny * (depth / 2 - 0.05)
            self.box(f"{name}_led", (L - 0.1, 0.012, 0.01), (fx, fy, 0.09), ang, self.M("led"), g, bevel=0)
            ax_, ay_ = a[0] + nx * 0.06, a[1] + ny * 0.06
            self.strip_light((ax_, ay_), (ax_ + (b[0] - a[0]), ay_ + (b[1] - a[1])), 0.085, (-nx * 0.9, -ny * 0.9, -0.5), 7.0, name=f"{name}_kick")
        return (cx, cy, h, ang)

    def back_bar(self, a, b, depth=0.6, h=0.92, shelves=3, shelf_z=(1.55, 1.95, 2.35), cups=True, led=True, splash="terrazzo", body="walnut", top="terrazzo", side=1, name="backbar"):
        """Back counter against a wall from a to b with floating shelves above, rows of cups and LED
        strips under each shelf. The body extends `depth` to the left of a→b (side=1)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Joinery")
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        self._runs.append({"a": a, "b": b, "n": (nx, ny), "u": (ux, uy), "L": L, "depth": depth, "h": h, "front": (nx, ny), "line": a, "name": name, "ang": ang, "items": []})
        self.box(f"{name}_body", (L, depth, h - 0.04), (cx, cy, (h - 0.04) / 2), ang, self.M(body), g)
        self.box(f"{name}_top", (L, depth + 0.02, 0.04), (cx, cy, h - 0.02), ang, self.M(top), g)
        # splashback up to the first shelf, flush with the wall face (at a→b line)
        wx, wy = (a[0] + b[0]) / 2 + nx * 0.015, (a[1] + b[1]) / 2 + ny * 0.015
        self.box(f"{name}_splash", (L, 0.03, shelf_z[0] - h), (wx, wy, h + (shelf_z[0] - h) / 2), ang, self.M(splash), g)
        for i in range(min(shelves, len(shelf_z))):
            z = shelf_z[i]
            sd = 0.3
            sx, sy = (a[0] + b[0]) / 2 + nx * sd / 2, (a[1] + b[1]) / 2 + ny * sd / 2
            self.box(f"{name}_shelf{i}", (L, sd, 0.035), (sx, sy, z), ang, self.M(body), g)
            self.box(f"{name}_shelf{i}_edge", (L, 0.015, 0.035), (sx + nx * sd / 2, sy + ny * sd / 2, z), ang, self.M("black_steel"), g)
            if led:
                self.box(f"{name}_shelf{i}_led", (L - 0.08, 0.02, 0.008), (sx + nx * (sd / 2 - 0.03), sy + ny * (sd / 2 - 0.03), z - 0.022), ang, self.M("led"), g)
                ox, oy = nx * (sd - 0.04), ny * (sd - 0.04)
                self.strip_light((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy), z - 0.028, (nx * 0.35, ny * 0.35, -1), 3.0, name=f"{name}_shelf{i}")
            if cups:
                self.cup_row(a, b, z + 0.0175, offset=sd / 2, side=side, name=f"{name}_cups{i}")
        return (cx, cy, h, ang)

    def cup_row(self, a, b, z, offset=0.15, spacing=0.125, side=1, name="cups", margin=0.1, rows=1, row_gap=0.1, kind="mug"):
        """Rows of real hollow cups along a→b at height z (one mesh). kind: "mug" (with handle) | "tumbler" | "takeaway"."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        bm = bmesh.new()
        n = int((L - 2 * margin) / spacing)
        prof = {"mug": [(0, 0), (0.03, 0), (0.038, 0.006), (0.042, 0.04), (0.043, 0.085), (0.04, 0.085), (0.038, 0.012), (0, 0.01)],
                "tumbler": [(0, 0), (0.033, 0), (0.038, 0.1), (0.035, 0.1), (0.031, 0.006), (0, 0.004)],
                "takeaway": [(0, 0), (0.03, 0), (0.042, 0.11), (0.0455, 0.112), (0.0455, 0.122), (0.039, 0.128), (0.012, 0.13), (0, 0.13)]}[kind]
        for r in range(rows):
            off = offset + r * row_gap
            for i in range(n + 1):
                u = margin + i * spacing
                x, y = a[0] + ux * u + nx * off, a[1] + uy * u + ny * off
                lathe_into(bm, prof, (x, y, z), seg=14)
                if kind == "mug":
                    # handle as a short arc of a small swept loop pointing into the room with slight variety
                    ha = math.atan2(ny, nx) + self.rng.uniform(-0.5, 0.5)
                    hx, hy = math.cos(ha), math.sin(ha)
                    px, py = -hy, hx
                    ring = []
                    for t in range(6):
                        th = math.pi * t / 5 - math.pi / 2
                        cx_ = 0.043 + math.cos(th) * 0.018
                        cz = 0.045 + math.sin(th) * 0.024
                        loop = []
                        for k in range(5):
                            a5 = 2 * math.pi * k / 5
                            rr = cx_ + math.cos(a5) * math.cos(th) * 0.0045
                            zz = cz + math.cos(a5) * math.sin(th) * 0.0045
                            ss = math.sin(a5) * 0.0045
                            loop.append(bm.verts.new((x + hx * rr + px * ss, y + hy * rr + py * ss, z + zz)))
                        ring.append(loop)
                    for t in range(5):
                        for k in range(5):
                            bm.faces.new((ring[t][k], ring[t][(k + 1) % 5], ring[t + 1][(k + 1) % 5], ring[t + 1][k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        crisp_smooth(bm, 55.0)
        project_uvs(bm)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.data.materials.append(self.M("cup"))
        self._collection("Props").objects.link(o)
        return o

    def espresso_station(self, at, rot=0.0, on=0.95, machine_w=1.0, grinders=2, variant=None, name="espresso"):
        """Espresso machine + grinders on a counter top at `at` (plan point, centre of the machine),
        facing `rot` (degrees; the barista side is behind)."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), on + dz)
        self._occupied.append((at[0], at[1], 0.6))
        if self.place("espresso", at, rot=rot, z=on, coll=g, name=f"{name}_machine", variant=variant) is not None:
            it = self.pick_asset("espresso", variant=variant)
            half_w = it["footprint"][0] / 2
            ca = P(-half_w + 0.1, 0.1, 0.0); cb = P(half_w - 0.1, 0.1, 0.0)
            self.cup_row((ca[0], ca[1]), (cb[0], cb[1]), on + it["height"] - 0.012, offset=0.0, spacing=0.095, margin=0.0, name=f"{name}_cups")
        else:
            half_w = machine_w / 2
            self.box(f"{name}_body", (machine_w, 0.56, 0.42), P(0, 0, 0.21), rot, self.M("matte_black"), g)
        for k in range(grinders):
            gx = half_w + 0.17 + k * 0.27
            gp = P(gx, 0.03, 0.0)
            self._occupied.append((gp[0], gp[1], 0.16))
            if self.place("grinder", (gp[0], gp[1]), rot=rot, z=on, coll=g, name=f"{name}_grinder{k}") is None:
                self.box(f"{name}_grinder{k}", (0.22, 0.3, 0.3), P(gx, -0.05, 0.15), rot, self.M("matte_black"), g)
        self._has_grinders = True
        return g

    def display_case(self, at, rot=0.0, w=1.3, d=0.75, on=0.0, h_base=0.9, glass_h=0.55, pastries=True, body="walnut_slat", top="terrazzo", name="display"):
        """Pastry / grab-and-go display: cabinet base + glass top with lit shelves and food inside."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), on + dz)
        self.box(f"{name}_base", (w, d, h_base - 0.04), P(0, 0, (h_base - 0.04) / 2), rot, self.M(body), g)
        self.box(f"{name}_top", (w + 0.04, d + 0.04, 0.04), P(0, 0, h_base - 0.02), rot, self.M(top), g, bevel=0.006)
        for sx in (-1, 1):   # slim steel uprights + pass-through rails
            for sy in (-1, 1):
                self.box(f"{name}_post", (0.016, 0.016, glass_h), P(sx * (w / 2 - 0.006), sy * (d / 2 - 0.006), h_base + glass_h / 2), rot, self.M("black_steel"), g, bevel=0)
        self.box(f"{name}_glass", (w, d, glass_h), P(0, 0, h_base + glass_h / 2), rot, self.M("display_glass"), g)
        self.box(f"{name}_lid", (w + 0.02, d + 0.02, 0.03), P(0, 0, h_base + glass_h + 0.015), rot, self.M("black_steel"), g)
        self.box(f"{name}_led", (w - 0.1, 0.02, 0.01), P(0, d / 2 - 0.04, h_base + glass_h - 0.03), rot, self.M("led_cool"), g)
        for lz in (glass_h - 0.035, 0.235):
            la, lb = P(-w / 2 + 0.06, 0.0, h_base + lz), P(w / 2 - 0.06, 0.0, h_base + lz)
            self.strip_light(la[:2], lb[:2], la[2], (0, 0, -1), 5.0, kelvin=3400, width=0.08, name=f"{name}_case")
        self.box(f"{name}_shelf", (w - 0.08, d - 0.12, 0.02), P(0, 0, h_base + 0.26), rot, self.M("steel"), g)
        if pastries:
            foods = self.manifest.get("pastry")
            if foods:
                # real food models scattered on the shelves (variety WITHIN the case, not the per-café
                # lock), spaced so the larger cakes/croissants don't overlap
                nx_ = max(1, int(w / 0.3)); ny_ = max(1, int(d / 0.34))
                for z in (h_base + 0.02, h_base + 0.28):
                    for i in range(nx_):
                        for j in range(ny_):
                            px = -w / 2 + 0.2 + i * (w - 0.4) / max(1, nx_ - 1)
                            py = -d / 2 + 0.2 + j * (d - 0.4) / max(1, ny_ - 1)
                            wp = P(px, py, z)
                            it = self.rng.choice(foods)
                            self.place("pastry", (wp[0], wp[1]), rot=self.rng.uniform(0, 360),
                                       variant=it["variant"], z=wp[2], coll=g, name=f"{name}_food")
            else:
                for z in (h_base + 0.02, h_base + 0.28):
                    nx_ = max(2, int(w / 0.16)); ny_ = max(1, int(d / 0.26))
                    for i in range(nx_):
                        for j in range(ny_):
                            px = -w / 2 + 0.12 + i * (w - 0.24) / max(1, nx_ - 1)
                            py = -d / 2 + 0.16 + j * (d - 0.32) / max(1, ny_ - 1)
                            kind = (i + j) % 3
                            if kind == 0:
                                self.sphere(f"{name}_bun", 0.045, P(px, py, z + 0.03), self.M("pastry"), (1, 1, 0.7), coll=g)
                            elif kind == 1:
                                self.box(f"{name}_slice", (0.09, 0.06, 0.05), P(px, py, z + 0.025), rot + 20, self.M("pastry_dark"), g)
                            else:
                                self.cyl(f"{name}_tart", 0.04, 0.03, P(px, py, z), self.M("pastry"), 14, coll=g)
        return g

    def till(self, at, rot=0.0, on=0.95, name="till"):
        """Point-of-sale terminal on a counter. The screen faces (sin rot, -cos rot), so aim rot at the barista."""
        g = self._collection("Equipment")
        self._occupied.append((at[0], at[1], 0.25))
        if self.place("pos", at, rot=rot, z=on, coll=g, name=name) is None:
            self.box(f"{name}_screen", (0.32, 0.02, 0.22), (at[0], at[1], on + 0.3), rot, self.M("screen"), g)
        return g

    def menu_screen(self, at, rot=0.0, w=1.45, h=0.82, z=2.1, name="menu", board=None):
        """Wall-mounted lit menu board with real typeset content; `at` on the wall face, `rot` = wall direction, faces left of it."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        board = self.rng.randrange(3) if board is None else board
        self.box(f"{name}_frame", (w + 0.04, 0.05, h + 0.04), (at[0] - math.sin(r) * 0.025, at[1] + math.cos(r) * 0.025, z), rot, self.M("black"), g)
        m = self.mat_image(f"menu_{board}", os.path.join(self.tex or "", "menu", f"menu_{board}.jpg"), roughness=0.25, emit=0.35)
        self._picture(f"{name}_panel", (at[0] - math.sin(r) * 0.052, at[1] + math.cos(r) * 0.052), rot, z, w, h, m, g)
        return g

    def _picture(self, name, at, rot, z, w, h, mat, g):
        """A rectangle with 0..1 UVs, facing the left of `rot` (images read correctly from the room)."""
        r = math.radians(rot)
        ux, uy = math.cos(r), math.sin(r)
        bm = bmesh.new()
        # reading left→right from the room means travelling against `rot`
        p = [(ux * w / 2, uy * w / 2, -h / 2), (-ux * w / 2, -uy * w / 2, -h / 2), (-ux * w / 2, -uy * w / 2, h / 2), (ux * w / 2, uy * w / 2, h / 2)]
        vs = [bm.verts.new(v) for v in p]
        f = bm.faces.new(vs)
        uv = bm.loops.layers.uv.verify()
        for l, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            l[uv].uv = c
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        o.data.materials.append(mat)
        o.location = (at[0], at[1], z)
        g.objects.link(o)
        return o

    def kiosk(self, at, rot=0.0, name="kiosk"):
        """Self-order kiosk: walnut panel with a flush screen (at = point on the wall face)."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        self.box(f"{name}_panel", (0.7, 0.06, 2.4), (at[0] + nx * 0.03, at[1] + ny * 0.03, 1.2), rot, self.M("walnut"), g)
        self.box(f"{name}_reveal", (0.74, 0.07, 0.02), (at[0] + nx * 0.03, at[1] + ny * 0.03, 2.41), rot, self.M("bronze"), g)
        self.box(f"{name}_screen", (0.46, 0.02, 0.9), (at[0] + nx * 0.07, at[1] + ny * 0.07, 1.5), rot, self.M("screen"), g)
        self.box(f"{name}_tray", (0.32, 0.12, 0.08), (at[0] + nx * 0.1, at[1] + ny * 0.1, 0.9), rot, self.M("black"), g)
        return g

    def shelving_wall(self, a, b, depth=0.35, h=2.4, levels=5, products=True, side=1, name="retail"):
        """Retail / display wall from a to b: walnut carcass, black steel shelves, LED edge, products."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Joinery")
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        self.box(f"{name}_back", (L, 0.03, h), ((a[0] + b[0]) / 2 + nx * 0.015, (a[1] + b[1]) / 2 + ny * 0.015, h / 2), ang, self.M("walnut"), g)
        for end in (a, b):
            self.box(f"{name}_side", (0.03, depth, h), (end[0] + nx * depth / 2, end[1] + ny * depth / 2, h / 2), ang, self.M("walnut"), g)
        self.box(f"{name}_topcap", (L, depth, 0.04), (cx, cy, h - 0.02), ang, self.M("walnut"), g)
        self.box(f"{name}_led", (L - 0.06, 0.02, 0.01), (cx + nx * (depth / 2 - 0.03), cy + ny * (depth / 2 - 0.03), h - 0.05), ang, self.M("led"), g)
        self.strip_light((a[0] + nx * (depth - 0.05), a[1] + ny * (depth - 0.05)), (b[0] + nx * (depth - 0.05), b[1] + ny * (depth - 0.05)), h - 0.055, (-nx * 0.5, -ny * 0.5, -1), 9.0, name=f"{name}_top")
        pal = ["#b48a5a", "#2a2420", "#3e5c44", "#efe8dc", "#7a4a2c", "#c9b089", "#9b2d20"]
        for i in range(levels):
            z = 0.12 + i * (h - 0.4) / max(1, levels - 1)
            self.box(f"{name}_shelf{i}", (L - 0.06, depth - 0.04, 0.025), (cx, cy, z), ang, self.M("black_steel"), g)
            if products:
                self.products_on_shelf(a, b, z + 0.0125, depth, side=side, name=f"{name}_lv{i}")
        return g

    def products_on_shelf(self, a, b, z, depth=0.35, side=1, name="products"):
        """Styled merchandise along a shelf: coffee bags with labels, glass jars of beans, tins, book stacks."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Props")
        merch = [it for it in self.manifest.get("merch", []) if it.get("brand") == self.brand] if self.brand else []
        if merch:
            # the client's real retail range (Coffee Berry bags, tins, capsule boxes, tumblers), facing the room
            face_rot = math.degrees(math.atan2(nx, -ny))
            u, k = 0.1, 0
            while True:
                it = merch[k % len(merch)]
                wid = it["footprint"][0]
                if u + wid > L - 0.08:
                    break
                n_ = 2 if wid < 0.12 else 1      # small packs stand in pairs
                for j in range(n_):
                    x = a[0] + ux * (u + wid / 2) + nx * (depth * (0.35 + 0.3 * j))
                    y = a[1] + uy * (u + wid / 2) + ny * (depth * (0.35 + 0.3 * j))
                    if it["height"] < 0.4:
                        self.place("merch", (x, y), rot=face_rot + self.rng.uniform(-6, 6), z=z, coll=g, name=f"{name}_{it['variant']}", variant=it["variant"])
                u += wid + 0.05
                k += 1
            return g
        pal = ["#b48a5a", "#2a2420", "#3e5c44", "#efe8dc", "#7a4a2c", "#9b2d20"]
        u = 0.12
        k = 0
        while u < L - 0.14:
            x, y = a[0] + ux * u + nx * (depth * 0.5), a[1] + uy * u + ny * (depth * 0.5)
            kind = k % 5
            if kind in (0, 3):      # coffee bag with a label band
                col = pal[self.rng.randrange(len(pal))]
                self.box(f"{name}_bag", (0.11, 0.07, 0.2), (x + ux * 0.055, y + uy * 0.055, z + 0.1), ang + self.rng.uniform(-6, 6), self.mat_plain(f"bag_{col}", col, 0.75), g)
                self.box(f"{name}_label", (0.08, 0.072, 0.06), (x + ux * 0.055, y + uy * 0.055, z + 0.09), ang, self.M("paper"), g)
                u += 0.17
            elif kind == 1:         # glass jar of beans with a wooden lid
                self.cyl(f"{name}_jar", 0.045, 0.17, (x + ux * 0.05, y + uy * 0.05, z), self.M("display_glass"), 16, coll=g)
                self.cyl(f"{name}_beans", 0.04, 0.13, (x + ux * 0.05, y + uy * 0.05, z + 0.005), self.M("beans"), 12, coll=g)
                self.cyl(f"{name}_lid", 0.047, 0.025, (x + ux * 0.05, y + uy * 0.05, z + 0.17), self.M("oak"), 16, coll=g)
                u += 0.14
            elif kind == 2:         # tin
                col = pal[self.rng.randrange(len(pal))]
                self.cyl(f"{name}_tin", 0.04, 0.14, (x + ux * 0.045, y + uy * 0.045, z), self.mat_plain(f"tin_{col}", col, 0.35, 0.6), 16, coll=g)
                self.cyl(f"{name}_tinlid", 0.041, 0.01, (x + ux * 0.045, y + uy * 0.045, z + 0.14), self.M("steel"), 16, coll=g)
                u += 0.13
            else:                   # small stack of books
                for j in range(3):
                    self.box(f"{name}_book", (0.16, 0.12, 0.025), (x + ux * 0.08, y + uy * 0.08, z + 0.0125 + j * 0.027), ang + self.rng.uniform(-10, 10), self.mat_plain(f"book{j}", ("#3e5c44", "#9b2d20", "#2a2420")[j], 0.8), g)
                u += 0.24
            k += 1
        return g

    # ---------------- seating ----------------
    def _outdoor_chair(self):
        """Weatherproof pick for terrace seating (never upholstered), one model per café."""
        if not hasattr(self, "_outdoor_variant"):
            names = ["metal_black", "metal_olive", "metal_mustard", "bentwood_black"]
            items = [i for i in self.manifest.get("chair", []) if i["variant"] in names]
            tagged = [i for i in items if self.style in i.get("style_tags", [])]
            pool = tagged or items
            self._outdoor_variant = self.rng.choice(pool)["variant"] if pool else None
        return self._outdoor_variant

    def chair(self, at, rot=0.0, seat_mat="boucle", frame="oak", name="chair", variant=None):
        """Café chair at `at`. It faces the direction (sin rot, -cos rot): rot=0 faces south (-y),
        90 faces east (+x), 180 faces north (+y), -90 faces west (-x). Uses a curated real model from
        the asset library when one exists for category 'chair'; otherwise builds the parametric chair."""
        g = self._collection("Seating")
        outdoor = self._is_outdoor(at)
        if variant is None and outdoor and self.manifest.get("chair_outdoor"):
            # the brand's terrace chair (Balfour, terracotta)
            if self.place("chair_outdoor", at, rot=rot, coll=g, name=name) is not None:
                return g
        if variant is None and outdoor:
            variant = self._outdoor_chair()
        if self.place("chair", at, rot=rot, coll=g, name=name, variant=variant) is not None:
            return g
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), dz)
        fm = self.M(frame)
        self.cyl(f"{name}_seat", 0.21, 0.035, P(0, 0, 0.425), fm, 20, coll=g)
        self.cyl(f"{name}_cushion", 0.19, 0.03, P(0, 0, 0.46), self.M(seat_mat), 20, coll=g)
        for sx, sy in ((-0.16, -0.16), (0.16, -0.16), (-0.16, 0.16), (0.16, 0.16)):
            self.cyl(f"{name}_leg", 0.016, 0.425, P(sx, sy, 0), fm, 10, r_top=0.013, coll=g)
        for sx in (-0.17, 0.17):
            self.cyl(f"{name}_post", 0.014, 0.45, P(sx, 0.18, 0.46), fm, 10, coll=g)
        self.box(f"{name}_backrest", (0.38, 0.03, 0.12), P(0, 0.18, 0.84), rot, fm, g)
        self.box(f"{name}_slat", (0.34, 0.025, 0.05), P(0, 0.18, 0.66), rot, fm, g)
        return g

    def table(self, at, shape="round", size=0.8, h=0.74, top="walnut", chairs=2, chair_r=None, name="table", seat_mat="boucle", base="auto", edge=None, variant=None):
        """Table with chairs. shape "round" (size = diameter) or "rect" (size=(w, d)). top: any material (marble, terrazzo, walnut, "marble_verde"...).
        base: "pedestal" | "tulip" | "trestle" | "hairpin" | "auto". edge: metal edge band or None. variant: force a chair model."""
        g = self._collection("Seating")
        if self._brand_table(at, shape, size, h, name):
            # client's own table model; chairs still go round it exactly as the parametric table seats them
            base = "__brand__"
        bm_ = self.M("black_steel")
        if base == "__brand__":
            pass
        elif base == "auto":
            base = "tulip" if shape == "round" and self.style in ("midcentury", "modern", "scandinavian", "deco") else "pedestal" if shape == "round" else "hairpin" if self.style in ("industrial", "midcentury", "brutalist", "retro") else "trestle"
        if shape == "round":
            r = size / 2
            if base == "__brand__":
                pass
            else:
              self.lathe(f"{name}_top", [(0, h - 0.028), (r - 0.012, h - 0.028), (r, h - 0.018), (r, h - 0.006), (r - 0.006, h), (0, h)], (at[0], at[1], 0), self.M(top), 56, g)
              if edge:
                  self.cyl(f"{name}_edge", r + 0.002, 0.012, (at[0], at[1], h - 0.022), self.M(edge), 56, coll=g)
              if base == "tulip":
                  self.lathe(f"{name}_base", [(0, 0), (0.24, 0), (0.25, 0.006), (0.2, 0.02), (0.06, 0.06), (0.034, 0.2), (0.034, h - 0.16), (0.075, h - 0.03), (0, h - 0.03)], (at[0], at[1], 0), self.M(self.style_base()), 48, g)
              else:
                  self.lathe(f"{name}_base", [(0, 0), (0.25, 0), (0.25, 0.012), (0.16, 0.022), (0.035, 0.05), (0.03, 0.2), (0.03, h - 0.1), (0.05, h - 0.06), (0.1, h - 0.04), (0.1, h - 0.03), (0, h - 0.03)], (at[0], at[1], 0), bm_, 40, g)
            cr = chair_r or (r + 0.3)
            for i in range(chairs):
                a = 2 * math.pi * i / chairs + math.pi / 2
                cx, cy = at[0] + math.cos(a) * cr, at[1] + math.sin(a) * cr
                self.chair((cx, cy), math.degrees(a) - 90, seat_mat=seat_mat, name=f"{name}_chair{i}", variant=variant)
        else:
            w, d = size if isinstance(size, (tuple, list)) else (size, size * 0.6)
            if base != "__brand__":
              self.box(f"{name}_top", (w, d, 0.03), (at[0], at[1], h - 0.015), 0, self.M(top), g, bevel=0.006)
              if edge:
                  self.box(f"{name}_edge", (w + 0.006, d + 0.006, 0.012), (at[0], at[1], h - 0.022), 0, self.M(edge), g, bevel=0)
              if base == "trestle":
                  for sx in (-1, 1):
                      x = at[0] + sx * (w / 2 - 0.14)
                      self.box(f"{name}_upright", (0.05, 0.05, h - 0.06), (x, at[1], (h - 0.06) / 2 + 0.03), 0, bm_, g)
                      self.box(f"{name}_foot", (0.05, d - 0.1, 0.03), (x, at[1], 0.015), 0, bm_, g)
                      self.box(f"{name}_cap", (0.05, d - 0.16, 0.03), (x, at[1], h - 0.045), 0, bm_, g)
                  self.box(f"{name}_rail", (w - 0.32, 0.03, 0.05), (at[0], at[1], h - 0.06), 0, bm_, g)
              else:
                  for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                      x, y = at[0] + sx * (w / 2 - 0.07), at[1] + sy * (d / 2 - 0.07)
                      self.cyl(f"{name}_leg", 0.008, h - 0.03, (x, y, 0), bm_, 10, coll=g)
                      self.cyl(f"{name}_leg", 0.008, h - 0.03, (x, y - sy * 0.05, 0), bm_, 10, coll=g)
            per_side = max(1, chairs // 2) if chairs else 0
            for i in range(per_side):
                x = at[0] - w / 2 + w * (i + 0.5) / per_side
                self.chair((x, at[1] - d / 2 - 0.26), 180, seat_mat=seat_mat, name=f"{name}_chair_s{i}", variant=variant)
                self.chair((x, at[1] + d / 2 + 0.26), 0, seat_mat=seat_mat, name=f"{name}_chair_n{i}", variant=variant)
        return g

    def _is_outdoor(self, at):
        room = self._room_at(at[0], at[1]) or {}
        return str(room.get("category", "")).endswith("outdoor") or not (room.get("ceilingHeight") or 0) > 0 and bool(room)

    def _brand_table(self, at, shape, size, h, name, rot=0.0):
        """Client table model stretched to the plan's top size and height. Round → table_round; tall (h ≥ 0.9) or long
        (≥ 1.3 m) → table_high (Ferro stand / Daylight frame); small square → table_square (Omicron pedestal, 60×60 top)."""
        if not self.brand:
            return False
        if shape == "round":
            cat, fp = "table_round", (size, size)
        else:
            w, d = size if isinstance(size, (tuple, list)) else (size, size * 0.6)
            cat = "table_high" if (h >= 0.9 or max(w, d) >= 1.3) else "table_square"
            fp = (w, d)
        if not any(it.get("brand") == self.brand for it in self.manifest.get(cat, [])):
            return False
        return self.place(cat, at, rot=rot, fit="stretch", footprint=fp, height=h, coll=self._collection("Seating"), name=f"{name}_top") is not None

    def plan_furniture(self, seat_mat="linen:#d8cbb4", bench_mat=None, auto_chairs=True, umbrella_colour="#efe4cf"):
        """Build ALL loose seating exactly where the floor plan draws it, with the client's own furniture models:
        every table (size + position from the plan), every chair turned to face its table, every stool, every banquette
        (backed onto its wall) and terrace stand counters. Nothing is invented or moved. Tables in work rooms are skipped
        (prep tables are worktops, plan_equipment dresses them). Call after the counters exist and before décor."""
        fx = self.scene.get("fixtures", [])
        g = self._collection("Seating")
        def room_ok(x, y):
            rc = str((self._room_at(x, y) or {}).get("category", ""))
            return not any(k in rc for k in ("prep", "kitchen", "storage", "wc", "staff"))
        def dims(f):
            w, d = (f.get("footprint") or [0.6, 0.6])[:2]
            if abs(round((f.get("rotation") or 0) / 90)) % 2 == 1:
                w, d = d, w
            return w, d
        tables, made = [], {"table": 0, "chair": 0, "stool": 0, "banquette": 0, "stand": 0}
        for f in fx:
            cat, nm = f.get("category"), (f.get("name") or "").lower()
            x, y = f["position"][:2]
            is_stand = cat == "counter" and self._is_outdoor((x, y)) and any(k in nm for k in ("stand", "πάγκος", "bar table"))
            if not (cat == "table" or is_stand) or not room_ok(x, y):
                continue
            w, d = dims(f)
            tall = is_stand or any(k in nm for k in ("stand", "bar table", "high", "poseur")) or (f.get("height") or 0) >= 0.9
            h = 1.05 if tall else 0.75
            name = f"plan_{f.get('id', len(tables))}"
            if "round" in nm or f.get("shape") == "round":
                self.table((x, y), shape="round", size=max(w, d), h=h, chairs=0, name=name)
            else:
                self.table((x, y), shape="rect", size=(w, d), h=h, chairs=0, name=name)
            tables.append((x, y, w, d, h))
            made["stand" if is_stand else "table"] += 1
            self._occupied.append((x, y, max(w, d) / 2))
        def nearest_table(x, y, reach=1.4):
            best, bd = None, reach
            for t in tables:
                # distance to the table's rectangle, not its centre (long tables)
                dx = max(abs(x - t[0]) - t[2] / 2, 0); dy = max(abs(y - t[1]) - t[3] / 2, 0)
                dd = math.hypot(dx, dy)
                if dd < bd:
                    best, bd = t, dd
            return best
        def face(x, y, t):
            # aim at the closest point of the table's top, so chairs along a long table face it squarely
            px = min(max(x, t[0] - t[2] / 2), t[0] + t[2] / 2); py = min(max(y, t[1] - t[3] / 2), t[1] + t[3] / 2)
            if abs(px - x) < 1e-3 and abs(py - y) < 1e-3:
                px, py = t[0], t[1]
            return math.degrees(math.atan2(px - x, -(py - y)))
        seats = [f for f in fx if f.get("category") in ("chair", "stool")]
        for f in seats:
            x, y = f["position"][:2]
            if not room_ok(x, y):
                continue
            t = nearest_table(x, y)
            rot = face(x, y, t) if t else (f.get("rotation") or 0)
            if f["category"] == "stool" or (t and t[4] >= 0.9):
                self.stool((x, y), name=f"plan_{f.get('id')}", rot=rot)
                made["stool"] += 1
            else:
                self.chair((x, y), rot=rot, seat_mat=seat_mat, name=f"plan_{f.get('id')}")
                made["chair"] += 1
        if auto_chairs and not seats:
            for (x, y, w, d, h) in tables:   # plan without drawn chairs: seat each side that is ≥ 0.55 m
                for (sx, sy, L) in ((0, -1, w), (0, 1, w), (-1, 0, d), (1, 0, d)):
                    n = int(L / 0.55)
                    for i in range(n):
                        off = -L / 2 + L * (i + 0.5) / n
                        cx = x + (sx * (w / 2 + 0.3) if sx else off)
                        cy = y + (sy * (d / 2 + 0.3) if sy else off)
                        if room_ok(cx, cy) and (sx == 0 or w < 1.0):
                            rot = math.degrees(math.atan2(x - cx, -(y - cy)))
                            (self.stool((cx, cy), rot=rot) if h >= 0.9 else self.chair((cx, cy), rot=rot, seat_mat=seat_mat))
                            made["stool" if h >= 0.9 else "chair"] += 1
        for f in fx:
            if f.get("category") not in ("banquette", "bench", "sofa"):
                continue
            x, y = f["position"][:2]
            w, d = dims(f)
            along_x = w >= d
            L, D = (w, d) if along_x else (d, w)
            D = max(0.5, min(D, 0.7))
            # the wall is on the side whose probe point leaves the room (or is nearest a wall)
            best = None
            for s in (1, -1):
                nx_, ny_ = (0, s) if along_x else (s, 0)
                inside = self._room_at(x + nx_ * 1.0, y + ny_ * 1.0) is not None
                behind = self._room_at(x - nx_ * (D / 2 + 0.35), y - ny_ * (D / 2 + 0.35)) is not None
                score = (inside and not behind, inside)
                if best is None or score > best[0]:
                    best = (score, nx_, ny_)
            _, nx_, ny_ = best
            bx, by = x - nx_ * D / 2, y - ny_ * D / 2
            ux, uy = (1, 0) if along_x else (0, 1)
            # order a→b so the room (n) lies LEFT of travel
            if (-uy * 1, ux * 1) != (nx_, ny_):
                ux, uy = -ux, -uy
            a = (bx - ux * L / 2, by - uy * L / 2); b = (bx + ux * L / 2, by + uy * L / 2)
            outdoor = self._is_outdoor((x, y))
            self.banquette(a, b, depth=D, seat_mat=(bench_mat or "cb_oak") if outdoor else seat_mat, panel=None,
                           back_h=0.45 if outdoor else 1.05, cushions="roll" if outdoor else "channel", name=f"plan_{f.get('id')}")
            made["banquette"] += 1
        # terrace umbrellas and edge planters drawn on the plan
        made["umbrella"] = made["planter"] = 0
        for f in fx:
            nm = (f.get("name") or "").lower()
            x, y = f["position"][:2]
            w, d = dims(f)
            if "umbrella" in nm or "ομπρέλ" in nm:
                self.umbrella((x, y), size=max(2.5, min(4.0, max(w, d))) if max(w, d) > 1.0 else 3.2, h=2.55, colour=umbrella_colour, name=f"plan_{f.get('id')}")
                made["umbrella"] += 1
            elif f.get("category") == "plant" and ("planter" in nm or "ζαρντιν" in nm):
                along_x = w >= d
                L = max(w, d)
                a = (x - L / 2, y) if along_x else (x, y - L / 2)
                b = (x + L / 2, y) if along_x else (x, y + L / 2)
                self.planter_hedge(a, b, w=max(0.3, min(w, d)), h=0.5, hedge_h=0.35, planter="concrete", name=f"plan_{f.get('id')}")
                made["planter"] += 1
        print(f"PLAN_FURNITURE {made}", flush=True)
        self._furniture_done = True
        return made

    def style_base(self):
        return {"deco": "brass", "midcentury": "white", "modern": "white", "scandinavian": "white"}.get(self.style, "black_steel")

    def lathe(self, name, profile, loc, mat, segments=32, coll=None):
        """Lathed (revolved) solid from a (radius, z) profile, smooth shaded. Use for vases, tabletops, bases, bottles."""
        bm = bmesh.new()
        lathe_into(bm, profile, (0, 0, 0), seg=segments)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        crisp_smooth(bm, 40.0)
        project_uvs(bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        o.location = loc
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def lounge_group(self, at, rot=0.0, chairs=2, table_top="marble", variant=None, rug=None, name="lounge"):
        """Conversation group: upholstered tub chairs around a low table, on an optional rug colour."""
        g = self._collection("Seating")
        if rug:
            self.rug(at, w=2.4, d=2.0, mat=rug, name=f"{name}_rug")
        h = 0.42
        self.lathe(f"{name}_table", [(0, 0), (0.2, 0), (0.2, 0.01), (0.03, 0.04), (0.03, h - 0.04), (0.3, h - 0.03), (0.32, h - 0.018), (0.32, h - 0.006), (0.31, h), (0, h)], (at[0], at[1], 0), self.M(table_top), 48, g)
        for i in range(chairs):
            a = math.radians(rot) + 2 * math.pi * i / chairs + math.pi / 2
            cx, cy = at[0] + math.cos(a) * 0.72, at[1] + math.sin(a) * 0.72
            self.place("lounge", (cx, cy), rot=math.degrees(a) - 90, coll=g, name=f"{name}_chair{i}", variant=variant)
        return g

    def stool(self, at, h=0.75, name="stool", variant=None, rot=None):
        g = self._collection("Seating")
        rot = self.rng.uniform(-8, 8) if rot is None else rot
        if self.place("stool", at, rot=rot, coll=g, name=name, variant=variant) is not None:
            return g
        self.cyl(f"{name}_seat", 0.17, 0.05, (at[0], at[1], h - 0.05), self.M("leather"), 20, coll=g)
        self.cyl(f"{name}_stem", 0.025, h - 0.07, (at[0], at[1], 0.02), self.M("black"), 12, coll=g)
        self.cyl(f"{name}_base", 0.2, 0.02, (at[0], at[1], 0), self.M("black"), 24, coll=g)
        return g

    def banquette(self, a, b, depth=0.6, seat_h=0.46, back_h=1.05, panel_h=2.2, side=1, seat_mat="boucle", panel="walnut_slat", cushions="channel", name="banquette"):
        """Fixed upholstered bench along a wall a→b: plinth, plump seat, tufted back cushions, panel above (panel=None to show the wall).
        cushions: "channel" (vertical channels) | "tufted" (square tufts) | "roll" (one long bolster). seat_mat: any fabric, e.g. "velvet:#46624f"."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Seating")
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        fab = self.M(seat_mat)
        self.box(f"{name}_plinth", (L, depth - 0.08, 0.12), (cx - nx * 0.03, cy - ny * 0.03, 0.06), ang, self.M("black"), g)
        self.box(f"{name}_base", (L, depth, 0.12), (cx, cy, 0.18), ang, fab, g, bevel=0.012)
        seats = max(1, int(L / 1.1))
        for i in range(seats):
            u = L * (i + 0.5) / seats
            self.box(f"{name}_seat", (L / seats - 0.012, depth - 0.02, seat_h - 0.24), (a[0] + ux * u + nx * depth / 2, a[1] + uy * u + ny * depth / 2, 0.24 + (seat_h - 0.24) / 2), ang, fab, g, bevel=0.04)
        bh = back_h - seat_h
        if cushions == "roll":
            self.rod(f"{name}_bolster", (a[0] + ux * 0.02 + nx * 0.2, a[1] + uy * 0.02 + ny * 0.2, seat_h + 0.11), (b[0] - ux * 0.02 + nx * 0.2, b[1] - uy * 0.02 + ny * 0.2, seat_h + 0.11), 0.09, fab, 24, g)
            self.box(f"{name}_back", (L, 0.1, bh), (a[0] * 0.5 + b[0] * 0.5 + nx * 0.05, a[1] * 0.5 + b[1] * 0.5 + ny * 0.05, seat_h + bh / 2), ang, fab, g, bevel=0.03)
        else:
            pitch = 0.2 if cushions == "channel" else 0.4
            n = max(1, int(L / pitch))
            for i in range(n):
                u = L * (i + 0.5) / n
                rows = 1 if cushions == "channel" else 2
                for j in range(rows):
                    hh = bh / rows
                    self.box(f"{name}_tuft", (L / n - 0.008, 0.13, hh - 0.008), (a[0] + ux * u + nx * 0.075, a[1] + uy * u + ny * 0.075, seat_h + hh * (j + 0.5)), ang, fab, g, bevel=min(0.045, (L / n) * 0.3))
        px, py = (a[0] + b[0]) / 2 + nx * 0.025, (a[1] + b[1]) / 2 + ny * 0.025
        if panel:
            self.box(f"{name}_panel", (L, 0.04, panel_h - back_h), (px, py, back_h + (panel_h - back_h) / 2), ang, self.M(panel), g)
            self.box(f"{name}_cove", (L - 0.1, 0.012, 0.008), (px + nx * 0.03, py + ny * 0.03, panel_h - 0.02), ang, self.M("led"), g, bevel=0)
            self.strip_light((a[0] + nx * 0.07, a[1] + ny * 0.07), (b[0] + nx * 0.07, b[1] + ny * 0.07), panel_h - 0.03, (-nx * 0.8, -ny * 0.8, -0.3), 12.0, name=f"{name}_cove")
        return g

    # ---------------- interior design layer: walls, ceilings, styling ----------------
    def wall_panel(self, a, b, z0=0.0, z1=2.4, mat="walnut", thick=0.03, side=1, name="panel"):
        """Cladding on a wall face from a to b (panel grows to the left of travel), e.g. walnut behind
        the banquette, a sage paint block, lime plaster, or a mirror."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        return self.box(name, (L, thick, z1 - z0), ((a[0] + b[0]) / 2 + nx * thick / 2, (a[1] + b[1]) / 2 + ny * thick / 2, (z0 + z1) / 2), ang, self.M(mat), self._collection("Design"))

    def accent_wall(self, a, b, color="sage", z0=0.0, z1=None, side=1, name="accent"):
        """Painted colour block on a wall (full height unless z1 given)."""
        z1 = z1 or (max((r.get("ceilingHeight") or 0) for r in self.scene["rooms"]) or 3.0)
        return self.wall_panel(a, b, z0, z1, color, 0.012, side, name)

    def slat_screen(self, a, b, h=2.4, z0=0.0, slat=0.04, gap=0.04, depth=0.04, mat="walnut", backing=None, side=1, name="slats"):
        """Vertical timber slats from a to b (feature wall or room divider), one mesh. backing="felt" adds a
        dark acoustic panel behind the slats."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Design")
        if backing:
            self.box(f"{name}_backing", (L, 0.02, h), ((a[0] + b[0]) / 2 + nx * 0.01, (a[1] + b[1]) / 2 + ny * 0.01, z0 + h / 2), ang, self.M(backing), g)
        bm = bmesh.new()
        n = max(1, int(L / (slat + gap)))
        for i in range(n):
            u = gap / 2 + i * (slat + gap) + slat / 2
            res = bmesh.ops.create_cube(bm, size=1.0)
            vs = res["verts"]
            bmesh.ops.scale(bm, vec=(slat, depth, h), verts=vs)
            bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.radians(ang), 3, "Z"), verts=vs)
            bmesh.ops.translate(bm, verts=vs, vec=(a[0] + ux * u + nx * (depth / 2 + (0.02 if backing else 0)), a[1] + uy * u + ny * (depth / 2 + (0.02 if backing else 0)), z0 + h / 2))
        bm.normal_update()
        project_uvs(bm)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.data.materials.append(self.M(mat))
        g.objects.link(o)
        return o

    def quote_wall(self, a, b, lines, z_top=2.3, size=0.22, mat="bronze", wall_mat="lime_plaster", side=1, name="quote"):
        """Feature wall: lime plaster panel with raised script-style lines of text (list of strings)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        self.wall_panel(a, b, 0.0, z_top + 0.6, wall_mat, 0.02, side, f"{name}_panel")
        for i, line in enumerate(lines):
            z = z_top - i * size * 1.6
            self.text(f"{name}_line{i}", line, ((a[0] + b[0]) / 2 + nx * 0.035, (a[1] + b[1]) / 2 + ny * 0.035, z), ang, size, self.M(mat), extrude=0.012)
        self.led_strip((a[0] + nx * 0.25, a[1] + ny * 0.25), (b[0] + nx * 0.25, b[1] + ny * 0.25), z_top + 0.55, name=f"{name}_graze")
        return name

    def ceiling_raft(self, x0, y0, x1, y1, z, style="slats", drop=0.35, led=True, name="raft"):
        """Dropped ceiling feature over a zone: timber slat raft or dark panel with an LED cove."""
        g = self._collection("Design")
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, d = abs(x1 - x0), abs(y1 - y0)
        if style == "slats":
            bm = bmesh.new()
            n = max(2, int(w / 0.12))
            for i in range(n):
                x = x0 + 0.06 + i * (w - 0.12) / max(1, n - 1)
                res = bmesh.ops.create_cube(bm, size=1.0)
                bmesh.ops.scale(bm, vec=(0.04, d, 0.12), verts=res["verts"])
                bmesh.ops.translate(bm, verts=res["verts"], vec=(x, cy, z - drop / 2))
            bm.normal_update()
            project_uvs(bm)
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            bm.free()
            o = bpy.data.objects.new(name, mesh)
            o.data.materials.append(self.M("walnut"))
            g.objects.link(o)
        else:
            self.box(f"{name}_panel", (w, d, 0.06), (cx, cy, z - drop), 0, self.M("ink"), g)
        for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            self.box(f"{name}_edge", (math.hypot(bx - ax, by - ay), 0.04, drop), ((ax + bx) / 2, (ay + by) / 2, z - drop / 2), math.degrees(math.atan2(by - ay, bx - ax)), self.M("ink" if style != "slats" else "walnut"), g)
        if led:
            for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y1, x0, y1)):
                self.led_strip((ax, ay), (bx, by), z - drop + 0.02, name=f"{name}_cove")
                self.strip_light((ax, ay), (bx, by), z - drop + 0.03, (0, 0, 1), 22.0, name=f"{name}_cove")
        return g

    def track_light(self, a, b, z, heads=4, power=70.0, aim=None, name="track"):
        """Black lighting track with spot heads; aim = plan point the heads point at (default: straight down)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        g = self._collection("Lighting")
        self.box(f"{name}_rail", (L, 0.035, 0.035), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), ang, self.M("black"), g)
        for i in range(heads):
            u = L * (i + 0.5) / heads
            x, y = a[0] + ux * u, a[1] + uy * u
            self.cyl(f"{name}_head", 0.035, 0.1, (x, y, z - 0.12), self.M("black"), 14, coll=g)
            d = bpy.data.lights.new(f"{name}_spot", "SPOT")
            d.energy = power; d.spot_size = math.radians(45); d.spot_blend = 0.5; d.color = kelvin_to_rgb(3000); d.shadow_soft_size = 0.05
            o = bpy.data.objects.new(f"{name}_spot", d)
            o.location = (x, y, z - 0.14)
            if aim:
                direction = Vector((aim[0], aim[1], 1.0)) - o.location
                o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            g.objects.link(o)
        return g

    def wall_sconce(self, at, rot=0.0, z=1.7, power=12.0, name="sconce"):
        """Brass arm with an opal globe on a wall face (rot = wall direction)."""
        g = self._collection("Lighting")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        self.cyl(f"{name}_plate", 0.05, 0.015, (at[0] + nx * 0.008, at[1] + ny * 0.008, z), self.M("brass"), 16, rot=(90, 0, rot), coll=g)
        self.box(f"{name}_arm", (0.02, 0.18, 0.02), (at[0] + nx * 0.1, at[1] + ny * 0.1, z), rot, self.M("brass"), g)
        self.sphere(f"{name}_globe", 0.08, (at[0] + nx * 0.2, at[1] + ny * 0.2, z), self.M("opal"), coll=g)
        d = bpy.data.lights.new(name, "POINT")
        d.energy = power; d.color = kelvin_to_rgb(2700); d.shadow_soft_size = 0.08
        o = bpy.data.objects.new(name, d)
        o.location = (at[0] + nx * 0.22, at[1] + ny * 0.22, z)
        g.objects.link(o)
        return g

    def neon_sign(self, body, at, rot=0.0, z=2.2, size=0.3, name="neon"):
        """Glowing script-style sign on a wall face."""
        r = math.radians(rot)
        o = self.text(name, body, (at[0] - math.sin(r) * 0.03, at[1] + math.cos(r) * 0.03, z), rot, size, self.M("neon"), extrude=0.01)
        d = bpy.data.lights.new(f"{name}_glow", "AREA")
        d.energy = 25.0; d.color = (1.0, 0.55, 0.35); d.size = size * 4
        lo = bpy.data.objects.new(f"{name}_glow", d)
        lo.location = (at[0] - math.sin(r) * 0.2, at[1] + math.cos(r) * 0.2, z + size * 0.3)
        lo.rotation_euler = (math.radians(90), 0, math.radians(rot))
        self._collection("Lighting").objects.link(lo)
        return o

    def letter_board(self, at, rot=0.0, z=1.9, w=0.9, h=0.6, lines=("ESPRESSO  2.6", "FLAT WHITE  4.2", "FILTER  3.4", "COLD BREW  4.5"), name="board"):
        """Felt letter board with white lettering on a wall face."""
        g = self._collection("Design")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        self.box(f"{name}_frame", (w + 0.05, 0.03, h + 0.05), (at[0] + nx * 0.015, at[1] + ny * 0.015, z), rot, self.M("oak"), g)
        self.box(f"{name}_felt", (w, 0.012, h), (at[0] + nx * 0.035, at[1] + ny * 0.035, z), rot, self.M("felt"), g)
        for i, line in enumerate(lines):
            zz = z + h / 2 - 0.1 - i * (h - 0.16) / max(1, len(lines) - 1)
            self.text(f"{name}_l{i}", line, (at[0] + nx * 0.045, at[1] + ny * 0.045, zz), rot, 0.055, self.M("white"), extrude=0.003)
        return g

    def wall_shelf(self, at, rot=0.0, z=1.5, w=1.0, props="mixed", name="wshelf"):
        """Floating walnut shelf on a wall face styled with coffee bags, books and a plant."""
        g = self._collection("Props")
        r = math.radians(rot)
        ux, uy = math.cos(r), math.sin(r)
        nx, ny = -math.sin(r), math.cos(r)
        self.box(f"{name}_board", (w, 0.22, 0.03), (at[0] + nx * 0.11, at[1] + ny * 0.11, z), rot, self.M("walnut"), g)
        self.box(f"{name}_led", (w - 0.06, 0.01, 0.008), (at[0] + nx * 0.2, at[1] + ny * 0.2, z - 0.02), rot, self.M("led"), g)
        self.strip_light((at[0] - ux * w / 2 + nx * 0.19, at[1] - uy * w / 2 + ny * 0.19), (at[0] + ux * w / 2 + nx * 0.19, at[1] + uy * w / 2 + ny * 0.19), z - 0.026, (-nx * 0.5, -ny * 0.5, -1), 6.0, name=f"{name}_under")
        u = -w / 2 + 0.08
        k = 0
        while u < w / 2 - 0.08:
            x, y = at[0] + ux * u + nx * 0.11, at[1] + uy * u + ny * 0.11
            kind = k % 3
            if kind == 0:
                self.box(f"{name}_bag", (0.11, 0.07, 0.19), (x, y, z + 0.11), rot + self.rng.uniform(-8, 8), self.M("kraft"), g)
                self.box(f"{name}_label", (0.07, 0.072, 0.05), (x, y, z + 0.1), rot, self.M("paper"), g)
                u += 0.17
            elif kind == 1:
                for j in range(3):
                    self.box(f"{name}_book", (0.03, 0.16, 0.2 + j * 0.02), (x + ux * j * 0.035, y + uy * j * 0.035, z + 0.115), rot, self.mat_plain(f"book{j}", ("#3e5c44", "#9b2d20", "#2a2420")[j], 0.8), g)
                u += 0.19
            else:
                self.cyl(f"{name}_pot", 0.05, 0.08, (x, y, z + 0.015), self.M("pot"), 14, coll=g)
                self._leaf_cloud(f"{name}_leaf", (x, y, z + 0.17), (0.09, 0.08, 0.09), 90, 0.05, coll=g)
                u += 0.18
            k += 1
        return g

    def hanging_plants(self, a, b, z, n=3, name="hang"):
        """Trailing plants in hung pots along a→b; z = ceiling height underside. Real vines with leaves along them."""
        g = self._collection("Props")
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        rng = self.rng
        for i in range(n):
            u = L * (i + 0.5) / n
            x, y = a[0] + ux * u, a[1] + uy * u
            self.cyl(f"{name}_cord", 0.002, 0.6, (x, y, z - 0.6), self.M("black"), 6, coll=g)
            self.lathe(f"{name}_pot", [(0, 0), (0.07, 0), (0.115, 0.13), (0.125, 0.14), (0.118, 0.14), (0, 0.11)], (x, y, z - 0.75), self.M("pot"), 24, g)
            vines = bmesh.new()
            bms = [bmesh.new() for _ in range(3)]
            for k in range(11):
                a_ = 6.283 * k / 11 + rng.uniform(-0.2, 0.2)
                out = rng.uniform(0.08, 0.13)
                length = rng.uniform(0.3, 0.95)
                pts = [Vector((x + math.cos(a_) * out, y + math.sin(a_) * out, z - 0.62))]
                dirx, diry = math.cos(a_), math.sin(a_)
                segs = max(4, int(length / 0.05))
                for t in range(segs):
                    f = 1 - t / segs
                    pts.append(pts[-1] + Vector((dirx * 0.04 * f + rng.uniform(-0.012, 0.012), diry * 0.04 * f + rng.uniform(-0.012, 0.012), -length / segs)))
                self._tube_into(vines, pts, 0.0028, 0.0016, seg=4)
                for pi, p_ in enumerate(pts[:-1]):
                    for side in (-1, 1):
                        ld = Vector((dirx * side * 0.7 + rng.uniform(-0.5, 0.5), diry * side * 0.7 + rng.uniform(-0.5, 0.5), rng.uniform(-0.7, -0.05))).normalized()
                        ll = rng.uniform(0.06, 0.095) * (1 - 0.35 * pi / len(pts))
                        self._leaf_into(bms[rng.randrange(3)], p_ + Vector((rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), 0)), ld, Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 1)), ll, ll * 0.62)
            self._commit_bm(vines, f"{name}_twig", "leaf_stem", g, smooth=60.0)
            for j, (bm, mt) in enumerate(zip(bms, ("leaf_a", "leaf_b", "leaf_c"))):
                self._commit_bm(bm, f"{name}{i}_leaf{j}", mt, g)
            self._leaf_cloud(f"{name}{i}_crown", (x, y, z - 0.6), (0.17, 0.17, 0.07), 90, 0.07, coll=g)
        return g

    def mirror(self, at, rot=0.0, z=1.5, w=1.2, h=1.6, name="mirror"):
        g = self._collection("Design")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        self.box(f"{name}_frame", (w + 0.06, 0.03, h + 0.06), (at[0] + nx * 0.015, at[1] + ny * 0.015, z), rot, self.M("brass"), g)
        self.box(f"{name}_glass", (w, 0.01, h), (at[0] + nx * 0.035, at[1] + ny * 0.035, z), rot, self.M("mirror"), g)
        return g

    def rug(self, at, w=2.4, d=1.6, mat="rug", name="rug"):
        return self.box(name, (w, d, 0.012), (at[0], at[1], 0.006), 0, self.M(mat), self._collection("Design"))

    def floor_zone(self, polygon, mat="tile_check", name="floor_zone"):
        """A different floor finish inside a zone (plan polygon), e.g. checker tile at the bar."""
        return self.slab(name, polygon, 0.006, self.M(mat), coll=self._collection("Design"))

    def condiment_station(self, at, rot=0.0, name="condiments"):
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), dz)
        self.box(f"{name}_body", (0.9, 0.45, 0.9), P(0, 0, 0.45), rot, self.M("walnut"), g)
        self.box(f"{name}_top", (0.94, 0.49, 0.03), P(0, 0, 0.915), rot, self.M("terrazzo"), g)
        self.box(f"{name}_bin", (0.3, 0.3, 0.2), P(-0.25, 0, 0.93), rot, self.M("black"), g)
        for i in range(3):
            self.cyl(f"{name}_jar", 0.04, 0.12, P(0.05 + i * 0.12, 0.08, 0.93), self.M("display_glass"), 12, coll=g)
        self.cup_row(P(-0.1, -0.12), P(0.4, -0.12), 0.93, offset=0.0, spacing=0.1, margin=0.0, name=f"{name}_cups")
        return g

    def waste_station(self, at, rot=0.0, name="waste"):
        g = self._collection("Equipment")
        self.box(f"{name}_body", (0.9, 0.45, 1.0), (at[0], at[1], 0.5), rot, self.M("walnut_slat"), g)
        self.box(f"{name}_top", (0.92, 0.47, 0.03), (at[0], at[1], 1.015), rot, self.M("black_steel"), g)
        return g

    def planter_hedge(self, a, b, w=0.4, h=0.45, hedge_h=0.5, name="hedge", planter="pot"):
        """Planter trough with a formally clipped boxwood hedge: a crisp rounded block of dense tiny leaves over dark interior foliage."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        g = self._collection("Props")
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        self.box(f"{name}_planter", (L, w, h), (mx, my, h / 2), ang, self.M(planter), g, bevel=0.012)
        self.box(f"{name}_rim", (L + 0.03, w + 0.03, 0.03), (mx, my, h - 0.012), ang, self.M(planter), g, bevel=0.008)
        hx, hy, hz = L / 2 - 0.015, w / 2 + 0.03, hedge_h / 2
        cz = h + hz - 0.02
        self.box(f"{name}_core", (2 * hx - 0.11, 2 * hy - 0.11, 2 * hz - 0.11), (mx, my, cz), ang, self.M("leaf_dark"), g, bevel=0.04)
        faces_ = [("x", 3 * 2 * hy * 2 * hz), ("y", 2 * hx * 2 * hz), ("z", 2 * hx * 2 * hy)]
        total_a = 2 * sum(f[1] for f in faces_) - 2 * faces_[2][1] * 0.5     # the underside is barely seen
        n = int(total_a * 4800)
        rng = self.rng
        bms = [bmesh.new() for _ in range(3)]
        fq = rng.uniform(5, 8)
        names = [f[0] for f in faces_]
        weights = [f[1] for f in faces_]
        for i in range(n):
            ax_ = rng.choices(names, weights)[0]
            sg = rng.choice((-1, 1)) if ax_ != "z" else (1 if rng.random() < 0.9 else -1)
            dx = (sg * hx) if ax_ == "x" else rng.uniform(-hx, hx)
            dy = (sg * hy) if ax_ == "y" else rng.uniform(-hy, hy)
            dz = (sg * hz) if ax_ == "z" else rng.uniform(-hz, hz)
            # round the block (superellipsoid, exponent 6): clipped faces with softly rounded edges
            q = (abs(dx / hx) ** 6 + abs(dy / hy) ** 6 + abs(dz / hz) ** 6) ** (1 / 6)
            lx, ly, lz = dx / q, dy / q, dz / q
            gx, gy, gz = (lx / hx) ** 3 * abs(lx / hx), (ly / hy) ** 3 * abs(ly / hy), (lz / hz) ** 3 * abs(lz / hz)
            N = Vector((gx / hx, gy / hy, gz / hz)).normalized()
            bump = 0.012 * (math.sin(lx * fq + 1.3) + math.sin(ly * fq * 1.7) + math.sin(lz * fq * 1.3 + lx * 3))
            depth = rng.uniform(-0.035, 0.016) + bump
            pl = Vector((lx, ly, lz)) + N * depth
            wx = mx + ux * pl.x + nx * pl.y
            wy = my + uy * pl.x + ny * pl.y
            N_w = Vector((ux * N.x + nx * N.y, uy * N.x + ny * N.y, N.z))
            rd = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            d = (N_w * 0.65 + rd.normalized() * 0.8).normalized()
            kind = 0 if depth > 0.0 else (1 if depth > -0.02 else 2)
            self._leaf_into(bms[kind], Vector((wx, wy, cz + pl.z)), d, N_w, rng.uniform(0.028, 0.042), rng.uniform(0.015, 0.022))
        for i, (bm, mt) in enumerate(zip(bms, ("box_light", "box_mid", "box_deep"))):
            self._commit_bm(bm, f"{name}_leaf{i}", mt, g)
        return g

    def string_lights(self, a, b, z, n=12, sag=0.25, name="festoon"):
        """Festoon bulbs between two points (a catenary of warm bulbs), one mesh + a few lights."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        g = self._collection("Lighting")
        bm = bmesh.new()
        for i in range(n):
            t = (i + 0.5) / n
            zz = z - sag * math.sin(math.pi * t)
            res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.035)
            bmesh.ops.translate(bm, verts=res["verts"], vec=(a[0] + ux * L * t, a[1] + uy * L * t, zz))
        bm.normal_update()
        project_uvs(bm)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.data.materials.append(self.M("bulb"))
        g.objects.link(o)
        self.box(f"{name}_cable", (L, 0.01, 0.01), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z - sag * 0.6), ang, self.M("black"), g)
        for i in range(3):
            t = (i + 0.5) / 3
            d = bpy.data.lights.new(f"{name}_l", "POINT")
            d.energy = 10.0; d.color = kelvin_to_rgb(2500)
            lo = bpy.data.objects.new(f"{name}_l", d)
            lo.location = (a[0] + ux * L * t, a[1] + uy * L * t, z - sag * 0.8)
            g.objects.link(lo)
        return g

    def high_table(self, at, rot=0.0, w=1.6, d=0.6, h=1.05, stools=3, name="hightable"):
        """Standing-height shared table with stools along one side."""
        g = self._collection("Seating")
        self.box(f"{name}_top", (w, d, 0.04), (at[0], at[1], h - 0.02), rot, self.M("walnut"), g)
        r = math.radians(rot)
        for sx in (-w / 2 + 0.1, w / 2 - 0.1):
            self.box(f"{name}_leg", (0.05, d - 0.1, h - 0.04), (at[0] + sx * math.cos(r), at[1] + sx * math.sin(r), (h - 0.04) / 2), rot, self.M("black"), g)
        for i in range(stools):
            u = -w / 2 + w * (i + 0.5) / stools
            self.stool((at[0] + u * math.cos(r) + math.sin(r) * (d / 2 + 0.3), at[1] + u * math.sin(r) - math.cos(r) * (d / 2 + 0.3)), h=0.75, name=f"{name}_stool{i}")
        return g

    # ---------------- lighting & décor ----------------
    def pendant(self, at, z_ceiling, drop=0.9, r=0.16, style="auto", power=55.0, name="pendant", variant=None):
        """Pendant lamp hung from the ceiling at `at`, shade bottom at z_ceiling - drop. Real library fixtures: variant "dome_black",
        "dome_brass", "dome_sage", "globe_brass", "globe_black", "rattan", "fluted", or auto from the design style."""
        g = self._collection("Lighting")
        legacy = {"opal": "globe_brass", "brass": "dome_brass"}
        variant = variant or legacy.get(style)
        z = z_ceiling - drop
        it = self.pick_asset("pendant", variant=variant)
        if it:
            self.place("pendant", at, rot=0, z=z, coll=g, name=name, variant=it["variant"])
            top = z + it["height"]
            lz = z + it["height"] * 0.35
        else:
            self.sphere(f"{name}_dome", r, (at[0], at[1], z), self.M("opal"), (1, 1, 0.75), coll=g)
            top = z + r
            lz = z
        self.cyl(f"{name}_rose", 0.05, 0.018, (at[0], at[1], z_ceiling - 0.018), self.M("brass"), 24, coll=g)
        self.cyl(f"{name}_cord", 0.0035, max(0.02, z_ceiling - top), (at[0], at[1], top), self.M("black"), 8, coll=g)
        d = bpy.data.lights.new(name, "POINT")
        d.energy = power; d.color = kelvin_to_rgb(2700); d.shadow_soft_size = 0.1
        o = bpy.data.objects.new(name, d)
        o.location = (at[0], at[1], lz)
        g.objects.link(o)
        return g

    def pendant_cluster(self, at, z_ceiling, n=5, spread=0.5, name="cluster", variant=None, power=22.0):
        """Staggered group of pendants at different drops: a feature over a table, stair or the bar end."""
        for i in range(n):
            a = 2.399 * i
            rr = spread * math.sqrt((i + 0.4) / n)
            self.pendant((at[0] + math.cos(a) * rr, at[1] + math.sin(a) * rr), z_ceiling, drop=0.7 + 0.55 * ((i * 0.618) % 1.0), name=f"{name}{i}", variant=variant, power=power)

    def pendant_linear(self, at, z_ceiling, rot=0.0, drop=1.0, power=60.0, name="linear", variant=None):
        """Long bar pendant over a counter or communal table; rot = direction of the bar."""
        g = self._collection("Lighting")
        z = z_ceiling - drop
        self.place("pendant_linear", at, rot=rot, z=z, coll=g, name=name, variant=variant)
        r = math.radians(rot)
        for sd in (-0.5, 0.5):
            x, y = at[0] + math.cos(r) * sd, at[1] + math.sin(r) * sd
            self.cyl(f"{name}_cable", 0.002, drop - 0.05, (x, y, z + 0.05), self.M("black"), 6, coll=g)
        d = bpy.data.lights.new(name, "AREA")
        d.shape = "RECTANGLE"; d.size = 1.3; d.size_y = 0.06; d.energy = power; d.color = kelvin_to_rgb(3000)
        o = bpy.data.objects.new(name, d)
        o.location = (at[0], at[1], z - 0.005)
        o.rotation_euler = (0, 0, r)
        g.objects.link(o)
        return g

    def led_strip(self, a, b, z, mat="led", name="led"):
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        return self.box(name, (L, 0.02, 0.01), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), ang, self.M(mat), self._collection("Lighting"))

    def _leaf_into(self, bm, p, d, up, L, W):
        """One folded leaf (2 triangles meeting along the midrib): reads as a real blade, not a flat card."""
        s_ = d.cross(up)
        if s_.length < 1e-4:
            s_ = d.cross(Vector((1, 0, 0)))
        s_.normalize()
        n_ = s_.cross(d).normalized()
        base, tip = p, p + d * L
        mid = p + d * (L * 0.5) - n_ * (W * 0.16)
        a_, b_ = bm.verts.new(mid + s_ * W * 0.5), bm.verts.new(mid - s_ * W * 0.5)
        v0, v1 = bm.verts.new(base), bm.verts.new(tip)
        bm.faces.new((v0, a_, v1))
        bm.faces.new((v0, v1, b_))

    def _tube_into(self, bm, pts, r0, r1, seg=6, caps=False):
        """Tapered round tube through points (branches, vines)."""
        P = [Vector(p) for p in pts]
        n = len(P)
        up = Vector((0.13, 0.27, 0.95)).normalized()
        rings = []
        for i, c in enumerate(P):
            d = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
            x = up.cross(d)
            if x.length < 1e-4:
                x = Vector((1, 0, 0)).cross(d)
            x.normalize()
            y = d.cross(x).normalized()
            up = y
            r = r0 + (r1 - r0) * (i / max(1, n - 1))
            rings.append([bm.verts.new(c + (x * math.cos(2 * math.pi * k / seg) + y * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)])
        for a, b in zip(rings, rings[1:]):
            for k in range(seg):
                bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
        if caps:
            bm.faces.new(rings[-1])

    def _commit_bm(self, bm, name, mat, g, smooth=None):
        if smooth is not None:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            crisp_smooth(bm, smooth)
        else:
            bm.normal_update()
        project_uvs(bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        o.data.materials.append(self.M(mat))
        g.objects.link(o)
        return o

    def _leaf_cloud(self, name, center, radii, n, leaf=0.06, mats=("leaf_a", "leaf_b", "leaf_c"), coll=None, droop=0.0, core=None, core_k=0.78):
        """Loose foliage volume made of folded leaves."""
        g = coll or self._collection("Props")
        bms = [bmesh.new() for _ in mats]
        rng = self.rng
        for i in range(n):
            while True:
                x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
                if x * x + y * y + z * z <= 1:
                    break
            k = rng.uniform(0.55, 1.0)
            p = Vector((center[0] + x * radii[0] * k, center[1] + y * radii[1] * k, center[2] + z * radii[2] * k))
            d = Vector((x + rng.uniform(-0.6, 0.6), y + rng.uniform(-0.6, 0.6), z * 0.5 + rng.uniform(-0.5, 0.3) - droop)).normalized()
            self._leaf_into(bms[i % len(mats)], p, d, Vector((0, 0, 1)), leaf * rng.uniform(0.75, 1.25), leaf * rng.uniform(0.3, 0.42))
        for mi, bm in enumerate(bms):
            self._commit_bm(bm, f"{name}_leaf{mi}", mats[mi], g)

    def plant(self, at, h=1.1, pot_r=0.22, name="plant", variant=None):
        """Real potted plant from the library; picks the model closest to height h."""
        g = self._collection("Props")
        z = at[2] if len(at) > 2 else 0.0
        items = self.manifest.get("plant") or []
        if items and not variant:
            variant = min(items, key=lambda i: abs(i["height"] - h))["variant"]
        if self.place("plant", (at[0], at[1]), rot=self.rng.uniform(0, 360), z=z, coll=g, name=name, variant=variant) is not None:
            return g
        self.lathe(f"{name}_pot", [(0, 0), (pot_r * 0.8, 0), (pot_r, h * 0.3), (pot_r * 0.92, h * 0.3), (0, h * 0.27)], (at[0], at[1], z), self.M("pot"), 28, g)
        self._leaf_cloud(f"{name}_leaf", (at[0], at[1], z + h * 0.65), (pot_r * 1.6, pot_r * 1.6, h * 0.35), 500, 0.09, coll=g)
        return g

    def _grow(self, bark, twigs, leaf_bms, start, d, length, r, level, max_level, leaf_len):
        """Recursive branching: each limb wanders, tapers and splits; the finest twigs carry the leaves."""
        rng = self.rng
        steps = 5 if level < 2 else 3
        pts = [Vector(start)]
        cur = Vector(d).normalized()
        for i in range(steps):
            cur = (cur + Vector((rng.uniform(-0.28, 0.28), rng.uniform(-0.28, 0.28), rng.uniform(-0.1, 0.22)))).normalized()
            pts.append(pts[-1] + cur * (length / steps))
        target = twigs if level == max_level else bark
        self._tube_into(target, pts, r, r * 0.6, seg={0: 12, 1: 8, 2: 6, 3: 4}.get(level, 3))
        if level == max_level:
            n = len(pts)
            for i in range(120):
                t = rng.uniform(0.0, 1.0) * (n - 1)
                a, b = pts[int(t)], pts[min(int(t) + 1, n - 1)]
                p = a + (b - a) * (t - int(t))
                side = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.25, 0.75))).normalized()
                ld = (cur * 0.55 + side).normalized()
                self._leaf_into(leaf_bms[rng.randrange(len(leaf_bms))], p, ld, Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 1)), leaf_len * rng.uniform(0.75, 1.2), leaf_len * rng.uniform(0.2, 0.28))
            return
        kids = {0: 4, 1: 4, 2: 4, 3: 3}.get(level, 3)
        for k in range(kids):
            ti = rng.randint(len(pts) // 2, len(pts) - 1)
            # limbs fan evenly round the trunk so the crown fills out; finer wood droops slightly like olive
            a = 6.283 * k / kids + rng.uniform(-0.5, 0.5) + level * 1.1
            spread = rng.uniform(0.9, 1.35) if level == 0 else rng.uniform(0.6, 1.05)
            nd = (cur * (1.0 if level == 0 else 0.7) + Vector((math.cos(a) * spread, math.sin(a) * spread, rng.uniform(-0.12, 0.22) - 0.06 * level))).normalized()
            self._grow(bark, twigs, leaf_bms, pts[ti], nd, length * rng.uniform(0.72, 0.88), r * 0.62, level + 1, max_level, leaf_len)

    def olive_tree(self, at, h=2.6, name="olive", pot="pot"):
        """Olive tree in a big planter: gnarled trunk splitting into limbs and twigs, thousands of narrow silver-green leaves."""
        g = self._collection("Props")
        self.lathe(f"{name}_pot", [(0, 0), (0.27, 0), (0.36, 0.5), (0.385, 0.53), (0.385, 0.56), (0.335, 0.56), (0.32, 0.5), (0, 0.5)], (at[0], at[1], 0), self.M(pot), 36, g)
        self.cyl(f"{name}_soil", 0.33, 0.012, (at[0], at[1], 0.5), self.M("soil"), 28, coll=g)
        bark, twigs = bmesh.new(), bmesh.new()
        leaves = [bmesh.new() for _ in range(3)]
        crown = max(1.2, h - 0.5)
        self._canopies.append((at[0], at[1], crown * 1.0))
        self._grow(bark, twigs, leaves, (at[0], at[1], 0.49), (0.05, 0.03, 1.0), crown * 0.36, 0.058, 0, 4, 0.058)
        self._commit_bm(bark, f"{name}_bark", "bark", g, smooth=60.0)
        self._commit_bm(twigs, f"{name}_twig", "bark", g, smooth=60.0)
        for i, (bm, mt) in enumerate(zip(leaves, ("leaf_olive", "leaf_olive2", "leaf_olive3"))):
            self._commit_bm(bm, f"{name}_leaf{i}", mt, g)
        return g

    def umbrella(self, at, size=3.2, h=2.5, name="umbrella", colour="#eee8da"):
        """Market umbrella: weighted base, timber pole, 8 ribs, fabric canopy with scalloped valance and finial."""
        g = self._collection("Props")
        m = self.mat_plain(f"canvas_{colour}", colour, roughness=0.95)
        self.lathe(f"{name}_base", [(0, 0), (0.28, 0), (0.28, 0.05), (0.06, 0.09), (0.035, 0.14), (0, 0.14)], (at[0], at[1], 0), self.M("charcoal"), 32, g)
        self.cyl(f"{name}_pole", 0.02, h + 0.1, (at[0], at[1], 0.05), self.M("oak_smoked"), 14, coll=g)
        R = size / 2
        rise = 0.42
        z0 = h - 0.26
        bm = bmesh.new()
        n = 8
        rings = [(0.03, z0 + rise), (R * 0.35, z0 + rise * 0.74), (R * 0.72, z0 + rise * 0.34), (R, z0)]
        vs = [[bm.verts.new((at[0] + r * math.cos(2 * math.pi * k / n + 0.39), at[1] + r * math.sin(2 * math.pi * k / n + 0.39), z)) for k in range(n)] for r, z in rings]
        for a, b in zip(vs, vs[1:]):
            for k in range(n):
                bm.faces.new((a[k], b[k], b[(k + 1) % n], a[(k + 1) % n]))
        for k in range(n):   # scalloped valance
            p0, p1 = vs[-1][k], vs[-1][(k + 1) % n]
            bm.faces.new((p0, bm.verts.new(p0.co + Vector((0, 0, -0.14))), bm.verts.new(p1.co + Vector((0, 0, -0.14))), p1))
        bm.normal_update(); project_uvs(bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(f"{name}_canopy", me)
        o.data.materials.append(m)
        g.objects.link(o)
        self.lathe(f"{name}_finial", [(0.03, 0), (0.035, 0.02), (0.02, 0.05), (0.012, 0.09), (0, 0.11)], (at[0], at[1], z0 + rise), self.M("brass"), 16, g)
        for k in range(n):
            a = 2 * math.pi * k / n + 0.39
            self.rod(f"{name}_rib", (at[0], at[1], z0 + rise - 0.04), (at[0] + math.cos(a) * R * 0.97, at[1] + math.sin(a) * R * 0.97, z0 - 0.015), 0.007, self.M("oak_smoked"), 6, g)
        return g

    def sign(self, body, at, rot=0.0, z=2.9, size=0.32, mat="walnut", name="sign"):
        """Wordmark on a wall: `at` on the wall face, `rot` = wall direction (text reads left→right along it)."""
        r = math.radians(rot)
        return self.text(name, body, (at[0] - math.sin(r) * 0.02, at[1] + math.cos(r) * 0.02, z), rot, size, self.M(mat), extrude=0.015)

    def art(self, at, rot=0.0, z=1.6, w=0.7, h=0.95, frame="black", name="art", print_id=None):
        """Framed print with a real image and mount; `at` on the wall face, rot = wall direction. frame: any material."""
        g = self._collection("Props")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        pid = self.rng.randrange(12) if print_id is None else print_id
        self.box(f"{name}_frame", (w, 0.03, h), (at[0] + nx * 0.015, at[1] + ny * 0.015, z), rot, self.M(frame), g)
        self.box(f"{name}_mount", (w - 0.05, 0.008, h - 0.05), (at[0] + nx * 0.03, at[1] + ny * 0.03, z), rot, self.M("white"), g, bevel=0)
        m = self.mat_image(f"art_{pid}", os.path.join(self.tex or "", "art", f"art_{pid:02d}.jpg"), roughness=0.55)
        self._picture(f"{name}_print", (at[0] + nx * 0.036, at[1] + ny * 0.036), rot, z, w - 0.17, h - 0.17, m, g)
        return g

    def gallery_wall(self, a, b, z=1.65, n=None, frame="black", side=1, name="gallery"):
        """A hung salon of mixed-size framed prints between two points on a wall face."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        n = n or max(2, int(L / 0.72))
        for i in range(n):
            u = L * (i + 0.5) / n
            w_, h_ = self.rng.choice(((0.5, 0.7), (0.62, 0.84), (0.42, 0.56), (0.5, 0.5)))
            self.art((a[0] + ux * u, a[1] + uy * u), ang, z + self.rng.uniform(-0.12, 0.12), w_, h_, frame, f"{name}{i}")

    def _glazing_outward(self):
        """Outward plan normal of the wall with the most glazing: the side daylight should come from."""
        best, bestw = (0.0, -1.0), 0.0
        for w in self.scene["walls"]:
            gl = sum(o["width"] for o in self.scene.get("openings", []) if o["wallId"] == w["id"] and o["type"] == "window")
            if gl <= bestw:
                continue
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay) or 1.0
            nx, ny = -(by - ay) / L, (bx - ax) / L
            mx, my = (ax + bx) / 2, (ay + by) / 2
            off = w["thickness"] / 2 + 0.1
            r = self._room_at(mx + nx * off, my + ny * off)
            if r and (r.get("ceilingHeight") or 0) > 0:
                nx, ny = -nx, -ny
            best, bestw = (nx, ny), gl
        return best

    def lights(self, mood="day", sun=True, sun_elev=None, sun_az=None, sun_power=None, fills=True, sky=True):
        """World + sun + a soft fill in lampless rooms. mood: "day" (bright, sun through the glazing) | "golden" (low warm sun) |
        "evening" (dusk sky, interior lamps carry the room). By default the sun is aimed through the main glazing.
        sun_az (optional) = plan angle of the direction TOWARD the sun, degrees CCW from +x (east); sun_elev = degrees above horizon."""
        S = self.scene
        self._mood = mood
        presets = {"day": (32.0, 7.0, (1.0, 0.94, 0.86), 0.42), "golden": (15.0, 8.0, (1.0, 0.72, 0.48), 0.8), "evening": (-1.0, 0.0, (1.0, 0.6, 0.4), 0.9)}
        elev, power, col, sky_strength = presets.get(mood, presets["day"])
        elev = elev if sun_elev is None else sun_elev
        power = power if sun_power is None else sun_power
        ox, oy = self._glazing_outward()
        base = math.atan2(oy, ox)
        az = base + math.radians(32) if sun_az is None else math.radians(sun_az)
        ce, se = math.cos(math.radians(elev)), math.sin(math.radians(elev))
        toward = Vector((math.cos(az) * ce, math.sin(az) * ce, se))
        world = bpy.data.worlds.get("CafeWorld") or bpy.data.worlds.new("CafeWorld")
        self.sc.world = world
        world.use_nodes = True
        nt = world.node_tree
        bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
        if sky:
            skyn = nt.nodes.new("ShaderNodeTexSky")
            types = [i.identifier for i in skyn.bl_rna.properties["sky_type"].enum_items]
            skyn.sky_type = next((t for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE") if t in types), types[0])
            if hasattr(skyn, "sun_disc"):
                skyn.sun_disc = False   # the SUN lamp below is the shadow-casting key
            if hasattr(skyn, "sun_elevation"):
                skyn.sun_elevation = math.radians(elev)
                skyn.sun_rotation = math.atan2(toward.x, toward.y)
            nt.links.new(skyn.outputs["Color"], bg.inputs["Color"])
            bg.inputs["Strength"].default_value = sky_strength
        else:
            bg.inputs["Color"].default_value = hex_to_linear("#cfdbe6")
        g = self._collection("Lighting")
        self._window_portals()
        if sun and power > 0 and elev > 0:
            d = bpy.data.lights.new("Sun", "SUN")
            d.energy = power; d.angle = math.radians(1.2); d.color = col
            o = bpy.data.objects.new("Sun", d)
            o.rotation_euler = toward.to_track_quat("Z", "Y").to_euler()
            g.objects.link(o)
        if fills:
            lamp_pts = [tuple(o.location[:2]) for c in bpy.data.collections for o in c.objects if o.type == "LIGHT" and o.data.type in ("POINT", "SPOT", "AREA")]
            for room in S["rooms"]:
                ch = room.get("ceilingHeight") or 0
                if ch <= 0:
                    continue
                poly = room["polygon"]
                if any(point_in_poly(poly, x, y) for x, y in lamp_pts) and mood != "evening":
                    continue
                cx, cy = _centroid(poly)
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                w, dd = max(xs) - min(xs), max(ys) - min(ys)
                d = bpy.data.lights.new(f"fill_{room['id']}", "AREA")
                d.shape = "RECTANGLE"; d.size = min(max(w * 0.5, 0.4), 2.2); d.size_y = min(max(dd * 0.5, 0.4), 2.2)
                d.energy = min(max(w * dd * 5.0, 20.0), 110.0); d.color = kelvin_to_rgb(3800)
                o = bpy.data.objects.new(f"fill_{room['id']}", d)
                o.location = (cx, cy, ch - 0.08)
                g.objects.link(o)
        return g

    def strip_light(self, a, b, z, direction=(0, 0, -1), watts_per_m=26.0, kelvin=2900, width=0.05, name="strip"):
        """A real linear light: an LED strip that actually lights what is around it (shelves, coves, kicks, display cases).
        direction: where it shines, e.g. (0, 0, -1) down, (0, 0, 1) up into a cove, or toward a wall."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.05:
            return None
        d = bpy.data.lights.new(name, "AREA")
        d.shape = "RECTANGLE"; d.size = L; d.size_y = width
        d.energy = watts_per_m * L; d.color = kelvin_to_rgb(kelvin)
        d.spread = math.radians(150)
        o = bpy.data.objects.new(f"fill_{name}", d)
        o.location = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z)
        ax = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized()
        zv = (-Vector(direction)).normalized()          # area lights emit along local -Z
        yv = zv.cross(ax)
        if yv.length < 1e-3:
            ax = Vector((0, 1, 0)).cross(zv).normalized()
            yv = zv.cross(ax)
        yv.normalize()
        ax2 = yv.cross(zv).normalized()
        from mathutils import Matrix
        o.rotation_euler = Matrix((ax2, yv, zv)).transposed().to_euler()
        self._collection("Lighting").objects.link(o)
        return o

    def wall_wash(self, a, b, z=None, n=None, power=38.0, kelvin=3000, side=1, name="wash"):
        """Row of recessed wall-washers grazing a feature wall from the ceiling (a→b on the wall face, room on the left). Makes brick, panels and art glow."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        z = z or max((r.get("ceilingHeight") or 0) for r in self.scene["rooms"]) - 0.03
        n = n or max(1, int(L / 0.9))
        g = self._collection("Lighting")
        for i in range(n):
            u = L * (i + 0.5) / n
            x, y = a[0] + ux * u + nx * 0.32, a[1] + uy * u + ny * 0.32
            self.cyl(f"downlight_{name}", 0.05, 0.015, (x, y, z - 0.012), self.M("lens"), 18, coll=g)
            d = bpy.data.lights.new(name, "SPOT")
            d.energy = power; d.spot_size = math.radians(95); d.spot_blend = 0.75; d.color = kelvin_to_rgb(kelvin); d.shadow_soft_size = 0.04
            o = bpy.data.objects.new(f"fill_{name}", d)
            o.location = (x, y, z - 0.03)
            aim = Vector((a[0] + ux * u, a[1] + uy * u, z - 1.3)) - o.location
            o.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
            g.objects.link(o)
        return g

    def _window_portals(self):
        """Cycles light portals in every window: daylight floods in cleanly with a natural falloff across the room."""
        g = self._collection("Lighting")
        for w in self.scene["walls"]:
            ops = [o for o in self.scene.get("openings", []) if o["wallId"] == w["id"] and o["type"] == "window"]
            if not ops:
                continue
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay) or 1.0
            ux, uy = (bx - ax) / L, (by - ay) / L
            nx, ny = -uy, ux
            t = w["thickness"]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            r_ = self._room_at(mx + nx * (t / 2 + 0.1), my + ny * (t / 2 + 0.1))
            if not (r_ and (r_.get("ceilingHeight") or 0) > 0):
                nx, ny = -nx, -ny
            for op in ops:
                sill = op.get("sillHeight") or 0.9
                c = op["offset"] + op["width"] / 2
                d = bpy.data.lights.new("portal", "AREA")
                d.shape = "RECTANGLE"; d.size = op["width"]; d.size_y = op["height"]
                try:
                    d.cycles.is_portal = True
                except Exception:
                    bpy.data.lights.remove(d)
                    continue
                o = bpy.data.objects.new("fill_portal", d)
                o.location = (ax + ux * c + nx * (t / 2 + 0.02), ay + uy * c + ny * (t / 2 + 0.02), sill + op["height"] / 2)
                zv = Vector((-nx, -ny, 0))        # local -Z points into the room
                from mathutils import Matrix
                xv = Vector((0, 0, 1)).cross(zv).normalized()
                yv = zv.cross(xv).normalized()
                o.rotation_euler = Matrix((xv, yv, zv)).transposed().to_euler()
                g.objects.link(o)

    # ---------------- decorative architecture ----------------
    def fluted_panel(self, a, b, z0=0.0, z1=2.4, mat="walnut", style="fluted", side=1, name="fluted"):
        """Reeded / slatted cladding on a wall face from a to b; style "fluted" | "slat"."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Design")
        return self._front(name, a, b, (nx, ny), 0.01, z0, z1, f"{style}:{mat}", g)

    def curtain(self, a, b, z0=0.05, z1=3.1, colour="linen:#e6dccb", rail="brass", side=1, offset=0.1, open_frac=0.0, name="curtain"):
        """Floor-to-ceiling wave drapes with a rail, along a wall face (use to frame glazing or soften a wall). open_frac 0..0.9 parts them to both sides."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Design")
        self.rod(f"{name}_rail", (a[0] + nx * offset, a[1] + ny * offset, z1), (b[0] + nx * offset, b[1] + ny * offset, z1), 0.011, self.M(rail), 12, g)
        parts = ((0.0, L),) if open_frac <= 0 else ((0.0, L * (1 - open_frac) / 2), (L - L * (1 - open_frac) / 2, L))
        for s0, s1 in parts:
            w_ = s1 - s0
            folds = max(3, int(w_ / 0.15))
            nu = folds * 6
            nv = 8
            bm = bmesh.new()
            grid = []
            for i in range(nu + 1):
                t = i / nu
                col = []
                for j in range(nv):
                    v = j / (nv - 1)
                    amp = 0.045 + 0.018 * (1 - v)
                    o = offset + amp * math.sin(t * folds * 2 * math.pi) + 0.006 * math.sin(v * 7 + t * 40)
                    u = s0 + t * w_
                    col.append(bm.verts.new((a[0] + ux * u + nx * o, a[1] + uy * u + ny * o, z0 + (z1 - z0) * v)))
                grid.append(col)
            for i in range(nu):
                for j in range(nv - 1):
                    bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            bm.normal_update()
            for f in bm.faces:
                f.smooth = True
            project_uvs(bm)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new(name, me)
            o.data.materials.append(self.M(colour))
            g.objects.link(o)
        return g

    def _arch_points(self, w, h, n=20):
        """Arch outline in (u, z), from bottom-left, over the semicircle, to bottom-right."""
        r = w / 2
        pts = [(-r, 0.0)]
        for i in range(n + 1):
            t = math.pi - math.pi * i / n
            pts.append((r * math.cos(t), h - r + r * math.sin(t)))
        pts.append((r, 0.0))
        return pts

    def _arch_mesh(self, name, at, rot, z, w, h, mat, off, depth=0.0, ring=0.0, g=None):
        """Filled arch plane (ring=0) or a raised arch frame `ring` wide, on a wall face."""
        r_ = math.radians(rot)
        ux, uy = math.cos(r_), math.sin(r_)
        nx, ny = -uy, ux
        bm = bmesh.new()
        def V(u, zz, d):
            return bm.verts.new((at[0] + ux * u + nx * (off + d), at[1] + uy * u + ny * (off + d), z + zz))
        outer = self._arch_points(w + 2 * ring, h + ring)
        if ring <= 0:
            f = bm.faces.new([V(u, zz, 0.0) for u, zz in reversed(outer)] if False else [V(u, zz, 0.0) for u, zz in outer][::-1])
        else:
            inner = self._arch_points(w, h)
            of = [V(u, zz, depth) for u, zz in outer]
            inf = [V(u, zz, depth) for u, zz in inner]
            ob = [V(u, zz, 0.0) for u, zz in outer]
            ib = [V(u, zz, 0.0) for u, zz in inner]
            for i in range(len(outer) - 1):
                bm.faces.new((of[i], of[i + 1], inf[i + 1], inf[i]))
                bm.faces.new((ob[i], ob[i + 1], of[i + 1], of[i]))
                bm.faces.new((inf[i], inf[i + 1], ib[i + 1], ib[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        crisp_smooth(bm, 40.0)
        project_uvs(bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        o.data.materials.append(mat)
        (g or self._collection("Design")).objects.link(o)
        return o

    def arch_mirror(self, at, rot=0.0, z=0.5, w=1.0, h=2.1, frame="brass", name="archmirror"):
        """Tall arched mirror on a wall face (at = bottom centre on the face, rot = wall direction)."""
        self._arch_mesh(f"{name}_glass", at, rot, z, w, h, self.M("mirror"), 0.01)
        self._arch_mesh(f"{name}_frame", at, rot, z, w, h, self.M(frame), 0.0, depth=0.03, ring=0.03)

    def arch_niche(self, at, rot=0.0, z=0.95, w=0.9, h=1.7, back="#1f3a35", frame="plaster_white", shelves=2, led=True, name="niche"):
        """Arched display niche: coloured back, raised surround, lit shelves with bottles and jars. at = bottom centre on the wall face."""
        g = self._collection("Design")
        r = math.radians(rot)
        ux, uy, nx, ny = math.cos(r), math.sin(r), -math.sin(r), math.cos(r)
        self._arch_mesh(f"{name}_back", at, rot, z, w, h, self.M(back), 0.008, g=g)
        self._arch_mesh(f"{name}_frame", at, rot, z, w, h, self.M(frame), 0.0, depth=0.14, ring=0.07, g=g)
        for i in range(shelves):
            sz = z + (h - w / 2) * (i + 0.6) / shelves
            self.box(f"{name}_shelf", (w, 0.14, 0.025), (at[0] + nx * 0.075, at[1] + ny * 0.075, sz), rot, self.M(frame), g)
            if led:
                self.box(f"{name}_led", (w - 0.06, 0.008, 0.006), (at[0] + nx * 0.12, at[1] + ny * 0.12, sz - 0.018), rot, self.M("led"), g, bevel=0)
                self.strip_light((at[0] - ux * w / 2 + nx * 0.1, at[1] - uy * w / 2 + ny * 0.1), (at[0] + ux * w / 2 + nx * 0.1, at[1] + uy * w / 2 + ny * 0.1), sz - 0.022, (-nx * 0.4, -ny * 0.4, -1), 8.0, name=f"{name}_shelf")
            n = max(2, int(w / 0.16))
            bm = bmesh.new()
            for k in range(n):
                u = -w / 2 + 0.08 + k * (w - 0.16) / max(1, n - 1)
                x, y = at[0] + ux * u + nx * 0.08, at[1] + uy * u + ny * 0.08
                hh = self.rng.uniform(0.2, 0.32)
                lathe_into(bm, [(0, 0), (0.035, 0), (0.038, 0.01), (0.038, hh * 0.65), (0.016, hh * 0.82), (0.015, hh), (0, hh)], (x, y, sz + 0.0125), seg=12)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            crisp_smooth(bm, 50.0)
            project_uvs(bm)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new(f"{name}_bottles", me)
            o.data.materials.append(self.M("dark_glass"))
            g.objects.link(o)

    def ceiling_beams(self, x0, y0, x1, y1, z, spacing=1.0, size=(0.12, 0.2), mat="oak_smoked", axis="y", name="beam"):
        """Exposed beams under a ceiling at height z over a plan rectangle; axis = direction they run."""
        g = self._collection("Design")
        w, d = abs(x1 - x0), abs(y1 - y0)
        ct = max(2, int((w if axis == "y" else d) / spacing))
        for i in range(ct + 1):
            if axis == "y":
                self.box(f"{name}", (size[0], d, size[1]), (min(x0, x1) + w * i / ct, (y0 + y1) / 2, z - size[1] / 2), 0, self.M(mat), g, bevel=0.008)
            else:
                self.box(f"{name}", (w, size[0], size[1]), ((x0 + x1) / 2, min(y0, y1) + d * i / ct, z - size[1] / 2), 0, self.M(mat), g, bevel=0.008)

    def ceiling_coffers(self, x0, y0, x1, y1, z, cell=1.2, mat="plaster_white", drop=0.14, led=False, name="coffer"):
        """Coffered ceiling grid under height z."""
        g = self._collection("Design")
        w, d = abs(x1 - x0), abs(y1 - y0)
        nx_, ny_ = max(1, int(w / cell)), max(1, int(d / cell))
        for i in range(nx_ + 1):
            self.box(name, (0.1, d, drop), (min(x0, x1) + w * i / nx_, (y0 + y1) / 2, z - drop / 2), 0, self.M(mat), g, bevel=0.008)
        for j in range(ny_ + 1):
            self.box(name, (w, 0.1, drop), ((x0 + x1) / 2, min(y0, y1) + d * j / ny_, z - drop / 2), 0, self.M(mat), g, bevel=0.008)

    def exposed_duct(self, a, b, z, r=0.17, mat="steel", name="duct"):
        """Round spiral duct with hangers and joint bands, industrial ceilings."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        g = self._collection("Design")
        self.rod(f"{name}_body", (a[0], a[1], z), (b[0], b[1], z), r, self.M(mat), 28, g)
        for i in range(int(L / 1.4) + 1):
            u = i * 1.4
            x, y = a[0] + ux * u, a[1] + uy * u
            self.rod(f"{name}_band", (x - ux * 0.025, y - uy * 0.025, z), (x + ux * 0.025, y + uy * 0.025, z), r + 0.008, self.M("steel"), 28, g)
            self.cyl(f"{name}_hanger", 0.005, 0.6, (x, y, z + r), self.M("black_steel"), 6, coll=g)

    def column(self, at, h=3.3, r=0.2, shape="round", mat="plaster_white", name="column"):
        """Free-standing column; shape "round" or "square"."""
        g = self._collection("Design")
        if shape == "round":
            self.lathe(name, [(0, 0), (r * 1.25, 0), (r * 1.25, 0.1), (r, 0.16), (r, h - 0.16), (r * 1.25, h - 0.1), (r * 1.25, h), (0, h)], (at[0], at[1], 0), self.M(mat), 36, g)
        else:
            self.box(name, (2 * r, 2 * r, h), (at[0], at[1], h / 2), 0, self.M(mat), g, bevel=0.008)

    # ---------------- equipment ----------------
    def equip(self, category, at, rot=0.0, z=0.0, variant=None, name=None):
        """Place one detailed library model. Categories: fridge (glass door), fridge_tall, undercounter, freezer, stove, oven (combi),
        oven_counter, microwave, toaster, dishwasher, sink, basin, toilet, ice_maker, hood, waste, extinguisher, grinder, blender, boiler.
        rot uses the chair rule: the front faces (sin rot, -cos rot)."""
        g = self._collection("Equipment")
        it = self.pick_asset(category, variant=variant)
        if it:
            self._occupied.append((at[0], at[1], max(it["footprint"]) * 0.5))
        return self.place(category, at, rot=rot, z=z, coll=g, name=name or f"{category}_{it['variant'] if it else 'x'}", variant=variant)

    def _run_at(self, x, y, margin=0.08):
        for R in self._runs:
            dx, dy = x - R["a"][0], y - R["a"][1]
            t = dx * R["u"][0] + dy * R["u"][1]
            dn = dx * R["n"][0] + dy * R["n"][1]
            if -margin <= t <= R["L"] + margin and -margin <= dn <= R["depth"] + margin:
                return R, t
        return None, 0.0

    def _free_on_run(self, R, t, half):
        """Slide along the run until nothing already sits there; None if the run is full."""
        for shift in (0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.45, -0.45, 0.6, -0.6, 0.8, -0.8):
            tt = t + shift
            if tt - half < 0.02 or tt + half > R["L"] - 0.02:
                continue
            x = R["a"][0] + R["u"][0] * tt + R["n"][0] * R["depth"] / 2
            y = R["a"][1] + R["u"][1] * tt + R["n"][1] * R["depth"] / 2
            if all(math.hypot(x - ox, y - oy) > half + orad - 0.03 for ox, oy, orad in self._occupied):
                return tt, x, y
        return None

    # ---- wall-aware placement: plan rotations are unreliable (the same toilet parses as 0, 90 or 180), walls are not ----
    def _room_faces(self, rid):
        if rid not in self._faces_cache:
            self._faces_cache[rid] = self.faces(rid)
        return self._faces_cache[rid]

    def _F(self, f, s, off=0.0, z=0.0):
        """World point on a face: s metres along it, off metres into the room, height z."""
        ux, uy = (f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]
        return (f["a"][0] + ux * s - uy * off, f["a"][1] + uy * s + ux * off, z)

    def _face_rot(self, f):
        """Rotation that makes a -Y-fronted model face into the room (its back to this wall)."""
        ux, uy = (f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]
        nx, ny = -uy, ux
        return math.degrees(math.atan2(nx, -ny))

    def _face_blocked(self, f, height, depth=0.7):
        """Intervals of a face that cannot take furniture: doors (with swing room), windows lower than the item, counters, placed items."""
        out = []
        for (g0, g1, gz0, gz1) in f["openings"]:
            if gz0 < 0.05:
                out.append((g0 - 0.18, g1 + 0.18))
            elif gz0 < height:
                out.append((g0, g1))
        key = (f["wall"], f["room"], round(f["a"][0], 2), round(f["a"][1], 2))
        out += self._face_used.get(key, [])
        ux, uy = (f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]
        for R in self._runs:
            pts = [R["a"], R["b"], (R["a"][0] + R["n"][0] * R["depth"], R["a"][1] + R["n"][1] * R["depth"]), (R["b"][0] + R["n"][0] * R["depth"], R["b"][1] + R["n"][1] * R["depth"])]
            ss, nn = [], []
            for p_ in pts:
                dx, dy = p_[0] - f["a"][0], p_[1] - f["a"][1]
                ss.append(dx * ux + dy * uy)
                nn.append(-dx * uy + dy * ux)
            if min(nn) < depth and max(nn) > -0.05 and max(ss) > 0 and min(ss) < f["len"]:
                out.append((min(ss), max(ss)))
        return sorted(out)

    def _mark_face(self, f, s0, s1):
        key = (f["wall"], f["room"], round(f["a"][0], 2), round(f["a"][1], 2))
        self._face_used.setdefault(key, []).append((s0, s1))

    def _free_spot(self, f, want, width, height):
        """Nearest position to `want` along a face where `width` fits; None if the wall is full."""
        half = width / 2
        lo, hi = half + 0.02, f["len"] - half - 0.02
        if hi < lo:
            return None
        blocked = self._face_blocked(f, height)
        cands = [min(max(want, lo), hi)]
        for (b0, b1) in blocked:
            cands += [b0 - half - 0.01, b1 + half + 0.01]
        best = None
        for c in cands:
            if c < lo or c > hi or any(c + half > b0 and c - half < b1 for b0, b1 in blocked):
                continue
            if best is None or abs(c - want) < abs(best - want):
                best = c
        return best

    def _against_wall(self, x, y, width, depth, height, reach=1.6, clear=0.6):
        """Choose the nearest free wall for an item at plan point (x, y) that leaves `clear` metres of usable floor in front
        (a toilet in a 1 m wide WC goes on the end wall, facing down the room): returns (face, s), or None."""
        room = self._room_at(x, y)
        if not room or not (room.get("ceilingHeight") or 0) > 0:
            return None
        ranked = []
        for f in self._room_faces(room["id"]):
            ux, uy = (f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]
            dx, dy = x - f["a"][0], y - f["a"][1]
            s_ = max(0.0, min(f["len"], dx * ux + dy * uy))
            ranked.append((math.hypot(x - (f["a"][0] + ux * s_), y - (f["a"][1] + uy * s_)), s_, f))
        for lim in (reach, 99.0):        # nearest suitable wall first, then any wall in the room
            for dist, s_, f in sorted(ranked, key=lambda r: r[0]):
                if dist > lim:
                    break
                spot = self._free_spot(f, s_, width, height)
                if spot is None:
                    continue
                fx, fy, _ = self._F(f, spot, depth + clear)
                inside = self._room_at(fx, fy)
                if inside and inside["id"] == room["id"]:
                    return f, spot
        return None

    def _place_on_wall(self, lib, x, y, name, variant=None):
        it = self.pick_asset(lib, variant=variant)
        hit = self._against_wall(x, y, it["footprint"][0] + 0.03, it["footprint"][1], it["height"])
        if not hit:
            return None
        f, s_ = hit
        px, py, _ = self._F(f, s_, it["footprint"][1] / 2 + 0.015)
        self._mark_face(f, s_ - it["footprint"][0] / 2 - 0.015, s_ + it["footprint"][0] / 2 + 0.015)
        self._occupied.append((px, py, max(it["footprint"]) * 0.5))
        self.place(lib, (px, py), rot=self._face_rot(f), coll=self._collection("Equipment"), name=name, variant=variant)
        return f, s_, it

    def _nearest_run(self, x, y, room_id, reach=2.5):
        """Worktop in the same room closest to a plan point."""
        best, bt, bd = None, 0.0, reach
        for R in self._runs:
            mx, my = R["a"][0] + R["u"][0] * R["L"] / 2 + R["n"][0] * R["depth"] / 2, R["a"][1] + R["u"][1] * R["L"] / 2 + R["n"][1] * R["depth"] / 2
            rr = self._room_at(mx, my)
            if not rr or rr["id"] != room_id:
                continue
            t = max(0.0, min(R["L"], (x - R["a"][0]) * R["u"][0] + (y - R["a"][1]) * R["u"][1]))
            d = math.hypot(x - (R["a"][0] + R["u"][0] * t), y - (R["a"][1] + R["u"][1] * t))
            if d < bd:
                best, bt, bd = R, t, d
        return best, bt

    def plan_equipment(self, skip=(), dress=True, wc_finish=None, wc_dado=None, vanity="auto", kitchen_finish=None):
        """Put every appliance from the plan's legend into the building with detailed models, then dress the washrooms and kitchens
        (vanity, backlit mirror, grab rails, accessories; steel worktops, shelves, hood, task light, cookware). Items that stand on the floor
        go back-to-wall facing the room, wherever the plan put them. Items inside a counter sit on it or become under-counter units. Never
        floats anything. Call AFTER counter_run/back_bar/espresso_station. Optional style: wc_finish, wc_dado, vanity, kitchen_finish (materials)."""
        self._plan_done = True
        placed, skipped = [], []
        toilets, basins, stoves = {}, {}, []
        jobs = []
        for f in self.scene.get("fixtures", []):
            cat = f.get("category")
            nm = (f.get("name") or f.get("label") or "").lower()
            if cat in skip or any(k in nm for k in skip):
                continue
            x, y = f["position"][:2]
            fw, fd = (f.get("footprint") or [0.5, 0.5])[:2]
            room = self._room_at(x, y) or {}
            rcat = str(room.get("category", ""))
            lib, mode = None, "floor"
            if "toilet" in nm or cat == "toilet":
                lib = "toilet"
            elif cat == "sink" and ("basin" in nm or "hand wash" in nm or rcat.startswith("wc")):
                lib = "basin"
            elif cat == "sink":
                lib, mode = "sink", "bench"
            elif cat == "fridge":
                lib, mode = ("undercounter", "under") if fw > 1.0 or self._run_at(x, y)[0] else ("fridge", "floor")
            elif cat == "freezer":
                lib = "freezer" if ("300" in nm or fw >= fd + 0.05) else "fridge_tall"
            elif cat == "dishwasher":
                lib, mode = "dishwasher", "under"
            elif cat == "ice_maker" and "storage" not in nm:
                lib = "ice_maker"
            elif cat == "oven":
                if "merry" in nm or "speed" in nm or self._run_at(x, y)[0]:
                    lib, mode = "oven_counter", "top"
                elif any(k in nm for k in ("stove", "range", "hob", "cook")):
                    lib = "stove"
                else:
                    lib = "stove" if not stoves else "oven"
                    stoves.append(1)
            elif "microwave" in nm:
                lib, mode = "microwave", "top"
            elif "toaster" in nm:
                lib, mode = "toaster", "top"
            elif "waste" in nm or "bin" in nm.split():
                lib = "waste"
            elif "extinguisher" in nm:
                lib = "extinguisher"
            elif cat in ("blender", "mixer"):
                lib, mode = "blender", "top"
            elif cat == "boiler":
                lib, mode = "boiler", "top"
            elif cat == "grinder" and not getattr(self, "_has_grinders", False):
                lib, mode = "grinder", "top"
            if lib and lib not in skip and self.pick_asset(lib):
                jobs.append((lib, mode, x, y, room, rcat))
        # 1. floor-standing items take their wall spots first
        hoods = []
        for lib, mode, x, y, room, rcat in jobs:
            if mode == "top":
                continue
            rid = room.get("id")
            if lib == "toilet":
                area = self._room_area(room)
                if toilets.get(rid, 0) >= max(1, int(area / 3.5)):   # parsed plans list the same toilet twice
                    continue
                toilets[rid] = toilets.get(rid, 0) + 1
            if lib == "basin":
                basins.setdefault(rid, []).append((x, y))
                continue
            R, t = self._run_at(x, y)
            if R and mode in ("under", "bench"):
                it = self.pick_asset(lib)
                if lib == "sink":
                    free = self._free_on_run(R, t, 0.22)
                    if free:
                        self._inset_sink(R, free[0], f"sink_{len(placed)}")
                        placed.append("sink_inset")
                    continue
                free = self._free_on_run(R, t, it["footprint"][0] / 2)
                if not free:
                    skipped.append(f"{lib}:run-full")
                    continue
                tt, px, py = free
                fx, fy = R["front"]
                self._occupied.append((px, py, it["footprint"][0] / 2))
                sd = -1 if R["front"] == R["n"] else 1
                edge = R["depth"] if sd == -1 else 0.0
                D = it["footprint"][1]
                self.place(lib, (R["a"][0] + R["u"][0] * tt + R["n"][0] * (edge + sd * (D / 2 - 0.012)), R["a"][1] + R["u"][1] * tt + R["n"][1] * (edge + sd * (D / 2 - 0.012))), rot=math.degrees(math.atan2(fx, -fy)), coll=self._collection("Equipment"), name=f"{lib}_{len(placed)}")
                placed.append(lib)
                continue
            hit = self._place_on_wall(lib, x, y, f"{lib}_{len(placed)}")
            if hit:
                placed.append(lib)
                if lib in ("stove", "oven"):
                    hoods.append(hit)
            else:
                skipped.append(f"{lib}@({x:.1f},{y:.1f}):no-wall")
        # 2. dress the rooms: worktops give counter-top items somewhere real to sit
        if dress:
            for room in self.scene.get("rooms", []):
                cat = str(room.get("category", ""))
                if not (room.get("ceilingHeight") or 0) > 0:
                    continue
                if cat in ("preparation", "kitchen"):
                    self.dress_kitchen(room, finish=kitchen_finish, hoods=[h for h in hoods if h[0]["room"] == room["id"]])
                elif cat == "storage":
                    self.dress_storage(room)
        # 3. things that sit on counters
        for lib, mode, x, y, room, rcat in jobs:
            if mode != "top":
                continue
            it = self.pick_asset(lib)
            half = it["footprint"][0] / 2
            R, t = self._run_at(x, y)
            if not R and room.get("id"):
                R, t = self._nearest_run(x, y, room["id"])
            if not R:
                skipped.append(f"{lib}@({x:.1f},{y:.1f}):no-counter")
                continue
            free = self._free_on_run(R, t, half)
            if not free:
                skipped.append(f"{lib}:run-full")
                continue
            tt, px, py = free
            fx, fy = R["front"]
            self._occupied.append((px, py, half))
            self.place(lib, (px, py), rot=math.degrees(math.atan2(fx, -fy)), z=R["h"], coll=self._collection("Equipment"), name=f"{lib}_{len(placed)}")
            placed.append(lib)
        # 4. washrooms last: they fit round whatever the plan fixed
        if dress:
            for room in self.scene.get("rooms", []):
                if str(room.get("category", "")).startswith("wc") and (room.get("ceilingHeight") or 0) > 0:
                    self.dress_washroom(room, basins.get(room["id"], []), has_toilet=toilets.get(room["id"], 0) > 0, finish=wc_finish, dado=wc_dado, vanity=vanity)
        report = {"placed": placed, "skipped": skipped}
        print(f"PLAN_EQUIPMENT placed={len(placed)} {sorted(set(placed))} skipped={skipped}", flush=True)
        return report

    def _room_area(self, room):
        p_ = room["polygon"]
        return abs(sum(p_[i][0] * p_[(i + 1) % len(p_)][1] - p_[(i + 1) % len(p_)][0] * p_[i][1] for i in range(len(p_)))) / 2

    # ---------------- washroom ----------------
    def _style_pick(self, table, default):
        return table.get(self.style, default)

    def dress_washroom(self, room, basin_points=(), has_toilet=True, finish=None, dado=None, vanity="auto"):
        """A finished washroom: tiled walls, vanity with vessel basin and wall tap, backlit mirror, towel and paper, soap, plant, and grab rails in accessible rooms."""
        rid = room["id"]
        ch = room.get("ceilingHeight") or 2.5
        g = self._collection("Washroom")
        tile = {"japandi": "subway:#e6e0d3", "scandinavian": "subway:#f0ede6", "industrial": "subway:#2b2b2d", "brutalist": "concrete", "bistro": "hex_tile:#ece6d8", "deco": "zellige:#1f4a40",
                "midcentury": "zellige:#2f6668", "retro": "zellige:#b0562f", "mediterranean": "zellige:#2e6f73", "biophilic": "zellige:#3f6b52", "modern": "marble_white", "cozy": "zellige:#6d5a4a"}
        top_mat = {"japandi": "limestone", "scandinavian": "marble_white", "industrial": "concrete_dark", "brutalist": "concrete_dark", "bistro": "marble_white", "deco": "marble_nero",
                   "midcentury": "terrazzo", "retro": "terrazzo", "mediterranean": "limestone", "biophilic": "marble_white", "modern": "marble_nero", "cozy": "limestone"}
        body_mat = {"japandi": "oak_pale", "scandinavian": "oak_pale", "industrial": "black_steel", "brutalist": "ebony", "bistro": "mahogany", "deco": "mahogany", "midcentury": "walnut",
                    "retro": "walnut", "mediterranean": "oak", "biophilic": "ash", "modern": "ebony", "cozy": "oak"}
        metal = {"deco": "brass", "bistro": "brass", "midcentury": "brass", "cozy": "brass", "retro": "brass", "mediterranean": "brass", "industrial": "black_steel", "brutalist": "black_steel", "modern": "chrome"}.get(self.style, "chrome")
        if rid not in self._finished and (room.get("category") not in self._finished):
            self.finish_walls(rid, finish=finish or "#e9e4d9", dado=dado or tile.get(self.style, "subway:#f0ede6"), dado_h=1.45, rail=metal if metal != "chrome" else None, crown=None, skirting=None)
        fs = sorted(self._room_faces(rid), key=lambda f: -f["len"])
        if not fs:
            return
        if not has_toilet:
            cx, cy = _centroid(room["polygon"])
            self._place_on_wall("toilet", cx, cy, f"toilet_{rid}")
        # vanity: wall nearest the plan's basin, else the longest free wall
        bx, by = (basin_points[0] if basin_points else _centroid(room["polygon"]))
        W = min(1.1, max(0.6, min(max(p[0] for p in room["polygon"]) - min(p[0] for p in room["polygon"]), max(p[1] for p in room["polygon"]) - min(p[1] for p in room["polygon"])) * 0.5))
        hit = self._against_wall(bx, by, W, 0.5, 0.9, reach=9.0)
        D_ = 0.48
        if not hit:     # narrow room: a compact hand basin in the wall's free stretch
            W, D_ = 0.5, 0.26
            hit = self._against_wall(bx, by, W, D_, 0.9, reach=9.0, clear=0.4)
        if hit:
            f, s_ = hit
            self._mark_face(f, s_ - W / 2, s_ + W / 2)
            self._vanity(f, s_, W, top_mat.get(self.style, "marble_white"), body_mat.get(self.style, "oak") if vanity == "auto" else vanity, metal, g, rid, D=D_)
        # accessories on the wall beside the toilet, grab rails where the room is accessible
        ts = [o for (o, file, i) in self._placed if file.startswith("wc/toilet") and (self._room_at(o.matrix_world.translation.x, o.matrix_world.translation.y) or {}).get("id") == rid]
        disabled = "disabled" in str(room.get("category")) or "accessible" in str(room.get("name", "")).lower()
        for t_ in ts:
            tx, ty = t_.matrix_world.translation.x, t_.matrix_world.translation.y
            near = sorted(fs, key=lambda f: self._dist_face(f, tx, ty))
            back = near[0]
            sidef = next((f for f in near[1:] if abs(self._face_dot(f, back)) < 0.3 and self._dist_face(f, tx, ty) < 1.6), None)
            if sidef:
                ss = self._proj(sidef, tx, ty)
                ss = min(max(ss, 0.2), sidef["len"] - 0.2)
                px, py, _ = self._F(sidef, ss, 0.05, 0.72)
                self.rod(f"{rid}_rollarm", self._F(sidef, ss, 0.0, 0.72), self._F(sidef, ss, 0.1, 0.72), 0.006, self.M(metal), 8, g)
                self.rod(f"{rid}_roll", self._F(sidef, ss - 0.055, 0.075, 0.72), self._F(sidef, ss + 0.055, 0.075, 0.72), 0.05, self.M("white"), 20, g)
                if disabled:
                    a_, b_ = self._F(sidef, ss - 0.35, 0.05, 0.82), self._F(sidef, ss + 0.4, 0.05, 0.82)
                    self.rod(f"{rid}_grab", a_, b_, 0.016, self.M(metal), 12, g)
                    for e_ in (ss - 0.35, ss + 0.4):
                        self.rod(f"{rid}_grab_post", self._F(sidef, e_, 0.0, 0.82), self._F(sidef, e_, 0.05, 0.82), 0.012, self.M(metal), 8, g)
            bs = self._proj(back, tx, ty)
            if disabled:
                for sg in (-0.33, 0.33):   # fold-down rails either side of the seat
                    b0, b1 = self._F(back, bs + sg, 0.03, 0.78), self._F(back, bs + sg, 0.72, 0.78)
                    self.rod(f"{rid}_fold", b0, b1, 0.016, self.M(metal), 12, g)
            # brush holder
            self.lathe(f"{rid}_brush", [(0, 0), (0.05, 0), (0.05, 0.14), (0.042, 0.14), (0.012, 0.16), (0.008, 0.42), (0, 0.42)], self._F(back, bs + 0.42 if bs + 0.42 < back["len"] - 0.1 else bs - 0.42, 0.1, 0.0), self.M(metal), 16, g)
        # warm soft ceiling panel so the room is flattering, not flat
        cx, cy = _centroid(room["polygon"])
        d = bpy.data.lights.new(f"fill_{rid}_panel", "AREA")
        d.shape = "RECTANGLE"; d.size = 0.9; d.size_y = 0.9; d.energy = min(26.0, self._room_area(room) * 1.6); d.color = kelvin_to_rgb(3300)
        o = bpy.data.objects.new(f"fill_{rid}_panel", d)
        o.location = (cx, cy, ch - 0.03)
        self._collection("Lighting").objects.link(o)
        return g

    def _dist_face(self, f, x, y):
        s_ = self._proj(f, x, y)
        px, py, _ = self._F(f, s_)
        return math.hypot(x - px, y - py)

    def _proj(self, f, x, y):
        ux, uy = (f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]
        return max(0.0, min(f["len"], (x - f["a"][0]) * ux + (y - f["a"][1]) * uy))

    def _face_dot(self, f, h):
        return ((f["b"][0] - f["a"][0]) * (h["b"][0] - h["a"][0]) + (f["b"][1] - f["a"][1]) * (h["b"][1] - h["a"][1])) / (f["len"] * h["len"])

    def _vanity(self, f, s_, W, top, body, metal, g, rid, D=0.48):
        ang = math.degrees(math.atan2(f["b"][1] - f["a"][1], f["b"][0] - f["a"][0]))
        vs_ = 0.62 if D < 0.4 else 1.0   # compact basin scale
        Pc = self._F(f, s_, D / 2)
        self.box(f"{rid}_vanity", (W, D, 0.34), (Pc[0], Pc[1], 0.66), ang, self.M(body), g, bevel=0.006)
        for sg in (-W / 4, W / 4):
            pf = self._F(f, s_ + sg, D + 0.002)
            self.box(f"{rid}_drawer", (W / 2 - 0.012, 0.008, 0.3), (pf[0], pf[1], 0.66), ang, self.M(body), g, bevel=0.003)
            ph = self._F(f, s_ + sg, D + 0.02)
            ph0, ph1 = self._F(f, s_ + sg - 0.09, D + 0.02, 0.76), self._F(f, s_ + sg + 0.09, D + 0.02, 0.76)
            self.rod(f"{rid}_pull", ph0, ph1, 0.006, self.M(metal), 8, g)
        self.box(f"{rid}_top", (W + 0.03, D + 0.02, 0.035), (Pc[0], Pc[1], 0.848), ang, self.M(top), g, bevel=0.005)
        self.box(f"{rid}_splash", (W + 0.03, 0.015, 0.1), self._F(f, s_, 0.008, 0.915), ang, self.M(top), g, bevel=0.003)
        # vessel basin, wall spout + lever
        vx = self._F(f, s_, D * 0.52)
        self.lathe(f"{rid}_vessel", [(0, 0), (0.09 * vs_, 0), (0.17 * vs_, 0.08), (0.185 * vs_, 0.13), (0.178 * vs_, 0.13), (0.16 * vs_, 0.085), (0.08 * vs_, 0.018), (0, 0.012)], (vx[0], vx[1], 0.866), self.M("cup"), 40, g)
        self.rod(f"{rid}_spout", self._F(f, s_, 0.0, 1.1), self._F(f, s_, D * 0.4, 1.08), 0.009, self.M(metal), 10, g)
        self.rod(f"{rid}_lever", self._F(f, s_ + 0.12, 0.0, 1.1), self._F(f, s_ + 0.12, 0.08, 1.1), 0.007, self.M(metal), 8, g)
        # backlit mirror with real light
        r_ = min(0.38, W * 0.42)
        mz = 1.52
        self.rod(f"{rid}_halo", self._F(f, s_, 0.004, mz), self._F(f, s_, 0.012, mz), r_ + 0.012, self.M("led"), 48, g)
        self.rod(f"{rid}_mirror", self._F(f, s_, 0.012, mz), self._F(f, s_, 0.026, mz), r_, self.M("mirror"), 48, g)
        lp = self._F(f, s_, 0.13, mz + r_ + 0.12)
        d = bpy.data.lights.new(f"fill_{rid}_mirror", "POINT")
        d.energy = 18.0 if D > 0.4 else 7.0; d.color = kelvin_to_rgb(3200); d.shadow_soft_size = 0.2
        o = bpy.data.objects.new(f"fill_{rid}_mirror", d)
        o.location = lp
        self._collection("Lighting").objects.link(o)
        if D < 0.4:     # no room for styling on a compact basin, keep it clean
            return
        # towels, soap, a small plant
        soap = self._F(f, s_ + W / 2 - 0.11, 0.12)
        self.lathe(f"{rid}_soap", [(0, 0), (0.032, 0), (0.034, 0.01), (0.034, 0.13), (0.012, 0.15), (0.009, 0.19), (0.03, 0.2), (0.03, 0.208), (0, 0.208)], (soap[0], soap[1], 0.866), self.M("dark_glass"), 14, g)
        tw = self._F(f, s_ - W / 2 + 0.13, 0.15)
        for k in range(3):
            self.box(f"{rid}_towel", (0.17, 0.13, 0.024), (tw[0], tw[1], 0.879 + k * 0.026), ang + k * 2, self.M("linen:#e8e1d2"), g, bevel=0.01)
        side = s_ + W / 2 + 0.34 if s_ + W / 2 + 0.5 < f["len"] else s_ - W / 2 - 0.34
        if 0.15 < side < f["len"] - 0.15 and not any(side > b0 and side < b1 for b0, b1 in self._face_blocked(f, 1.2)):
            a_, b_ = self._F(f, side - 0.2, 0.06, 1.15), self._F(f, side + 0.2, 0.06, 1.15)
            self.rod(f"{rid}_rail", a_, b_, 0.009, self.M(metal), 10, g)
            for e_ in (side - 0.2, side + 0.2):
                self.rod(f"{rid}_railpost", self._F(f, e_, 0.0, 1.15), self._F(f, e_, 0.06, 1.15), 0.008, self.M(metal), 8, g)
            p0, p1 = self._F(f, side, 0.066, 0.92), 0
            self.box(f"{rid}_handtowel", (0.26, 0.016, 0.46), (p0[0], p0[1], 0.93), ang, self.M("linen:#d7cdb8"), g, bevel=0.005)
        pv = self._F(f, s_ + W / 2 - 0.2, 0.22)
        self.lathe(f"{rid}_vase", [(0, 0), (0.035, 0), (0.05, 0.05), (0.04, 0.11), (0.024, 0.13), (0.028, 0.15), (0.02, 0.15), (0, 0.1)], (pv[0], pv[1], 0.866), self.M("pot"), 18, g)
        self._leaf_cloud(f"{rid}_sprig", (pv[0], pv[1], 1.1), (0.09, 0.09, 0.11), 70, 0.05, coll=g)

    # ---------------- kitchen ----------------
    def dress_kitchen(self, room, finish=None, hoods=()):
        """A working kitchen: washable walls, stainless worktops along every free wall, shelving with cookware and task light, hood over the stove, utensil rail, battens."""
        rid = room["id"]
        ch = room.get("ceilingHeight") or 2.8
        g = self._collection("Kitchen")
        if rid not in self._finished and room.get("category") not in self._finished:
            self.finish_walls(rid, finish=finish or "subway:#ece9e2", skirting="charcoal", skirting_h=0.1)
        # hoods first: they own the wall above the stove
        for f, s_, it in hoods:
            hit_z = min(1.95, ch - 0.68)
            hp = self._F(f, s_, 0.44)
            self.place("hood", (hp[0], hp[1]), rot=self._face_rot(f), z=hit_z, coll=g, name=f"{rid}_hood")
            lc = self._F(f, s_, 0.44, hit_z - 0.02)
            self.strip_light(self._F(f, s_ - 0.4, 0.44)[:2], self._F(f, s_ + 0.4, 0.44)[:2], hit_z - 0.02, (0, 0, -1), 22.0, kelvin=3800, width=0.1, name=f"{rid}_hood")
        tops = []
        for f in sorted(self._room_faces(rid), key=lambda x: -x["len"]):
            blocked = sorted(self._face_blocked(f, 0.92, depth=0.66))
            cur = 0.03
            spans = []
            for (b0, b1) in blocked + [(f["len"] - 0.03, f["len"] + 1)]:
                if b0 - cur >= 0.6:
                    spans.append((cur, b0))
                cur = max(cur, b1)
            for (s0, s1) in spans:
                self._worktop(f, s0, s1, g, rid, len(tops))
                tops.append((f, s0, s1))
        # utensil rail above the longest worktop
        if tops:
            f, s0, s1 = max(tops, key=lambda t: t[2] - t[1])
            self._utensils(f, s0, s1, g, rid)
        self._batten(room, g, 75.0)
        # floor drain
        cx, cy = _centroid(room["polygon"])
        self.box(f"{rid}_drain", (0.2, 0.2, 0.004), (cx, cy, 0.003), 0, self.M("brushed_steel"), g, bevel=0)
        return g

    def _batten(self, room, g, watts):
        """Bright clean linear ceiling light along the length of a working room."""
        rid, ch = room["id"], room.get("ceilingHeight") or 2.8
        cx, cy = _centroid(room["polygon"])
        xs = [p[0] for p in room["polygon"]]; ys = [p[1] for p in room["polygon"]]
        alongx = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        L = min(2.4, (max(xs) - min(xs) if alongx else max(ys) - min(ys)) * 0.6)
        ang = 0 if alongx else 90
        self.box(f"{rid}_batten", (L, 0.09, 0.05), (cx, cy, ch - 0.03), ang, self.M("white"), g)
        self.box(f"{rid}_batten_led", (L - 0.04, 0.07, 0.006), (cx, cy, ch - 0.057), ang, self.M("led_cool"), g, bevel=0)
        d = bpy.data.lights.new(f"fill_{rid}_batten", "AREA")
        d.shape = "RECTANGLE"; d.size = L; d.size_y = 0.12; d.energy = watts; d.color = kelvin_to_rgb(4000)
        o = bpy.data.objects.new(f"fill_{rid}_batten", d)
        o.location = (cx, cy, ch - 0.065); o.rotation_euler = (0, 0, math.radians(ang))
        self._collection("Lighting").objects.link(o)

    def _worktop(self, f, s0, s1, g, rid, idx):
        """Stainless bench on a wall face: upstand, legs, undershelf with stock, wall shelf with cookware and task light; registered as a real counter."""
        name = f"{rid}_top{idx}"
        L, D, H = s1 - s0, 0.62, 0.9
        c = (s0 + s1) / 2
        ang = math.degrees(math.atan2(f["b"][1] - f["a"][1], f["b"][0] - f["a"][0]))
        steel = self.M("brushed_steel")
        Pc = self._F(f, c, D / 2)
        self.box(f"{name}_top", (L, D, 0.04), (Pc[0], Pc[1], H - 0.02), ang, steel, g, bevel=0.003)
        up = self._F(f, c, 0.012)
        self.box(f"{name}_upstand", (L, 0.024, 0.12), (up[0], up[1], H + 0.06), ang, steel, g, bevel=0.002)
        fr = self._F(f, c, D - 0.012)
        self.box(f"{name}_apron", (L, 0.02, 0.09), (fr[0], fr[1], H - 0.085), ang, steel, g, bevel=0.002)
        legs = max(2, int(L / 1.2) + 1)
        for i in range(legs):
            s_ = s0 + 0.05 + (L - 0.1) * i / (legs - 1)
            for off in (0.06, D - 0.06):
                p_ = self._F(f, s_, off)
                self.box(f"{name}_leg", (0.04, 0.04, H - 0.05), (p_[0], p_[1], (H - 0.05) / 2), ang, steel, g, bevel=0.003)
        sh = self._F(f, c, D / 2)
        self.box(f"{name}_under", (L - 0.04, D - 0.1, 0.02), (sh[0], sh[1], 0.25), ang, steel, g, bevel=0.002)
        # stock under the bench: lidded containers, crates, sacks
        u = s0 + 0.2
        k = 0
        while u < s1 - 0.2:
            p_ = self._F(f, u, D / 2)
            if k % 3 == 0:
                self.box(f"{name}_tub", (0.3, 0.4, 0.2), (p_[0], p_[1], 0.36), ang, self.M("white"), g, bevel=0.012)
                self.box(f"{name}_lid", (0.31, 0.41, 0.02), (p_[0], p_[1], 0.47), ang, self.M("charcoal"), g, bevel=0.005)
            elif k % 3 == 1:
                self.lathe(f"{name}_potstock", [(0, 0), (0.15, 0), (0.15, 0.2), (0.142, 0.2), (0.142, 0.01), (0, 0.01)], (p_[0], p_[1], 0.26), self.M("steel"), 24, g)
            else:
                self.box(f"{name}_sack", (0.28, 0.38, 0.18), (p_[0], p_[1], 0.35), ang + 4, self.M("hessian"), g, bevel=0.05)
            u += 0.42
            k += 1
        self._runs.append({"a": self._F(f, s0)[:2], "b": self._F(f, s1)[:2], "n": ((-(f["b"][1] - f["a"][1])) / f["len"], (f["b"][0] - f["a"][0]) / f["len"]), "u": ((f["b"][0] - f["a"][0]) / f["len"], (f["b"][1] - f["a"][1]) / f["len"]), "L": L, "depth": D, "h": H,
                           "front": ((-(f["b"][1] - f["a"][1])) / f["len"], (f["b"][0] - f["a"][0]) / f["len"]), "line": self._F(f, s0)[:2], "name": name, "ang": ang, "items": []})
        self._mark_face(f, s0, s1)
        # bench styling
        items = ["board", "pot", "jars", "knives", "bowls", "scale", "oil"]
        u = s0 + 0.2
        i = int(self.rng.random() * 7)
        while u < s1 - 0.18:
            self._bench_prop(items[i % len(items)], f, u, g, name, H)
            i += 1
            u += self.rng.uniform(0.55, 0.85)
        # wall shelf + cookware + task light
        Sz = 1.62
        sp = self._F(f, c, 0.15)
        self.box(f"{name}_shelf", (L, 0.3, 0.025), (sp[0], sp[1], Sz), ang, steel, g, bevel=0.002)
        for i in range(max(2, int(L / 0.9) + 1)):
            s_ = s0 + 0.06 + (L - 0.12) * i / max(1, max(2, int(L / 0.9) + 1) - 1)
            bp = self._F(f, s_, 0.13)
            self.box(f"{name}_bracket", (0.012, 0.26, 0.05), (bp[0], bp[1], Sz - 0.035), ang, self.M("black_steel"), g, bevel=0)
        a_, b_ = self._F(f, s0 + 0.05, 0.24), self._F(f, s1 - 0.05, 0.24)
        self.strip_light(a_[:2], b_[:2], Sz - 0.03, (0, 0, -1), 13.0, kelvin=3900, width=0.03, name=f"{name}_task")
        self.box(f"{name}_taskled", (L - 0.1, 0.02, 0.008), (sp[0] + (a_[0] - self._F(f, s0 + 0.05, 0.15)[0]), sp[1] + (a_[1] - self._F(f, s0 + 0.05, 0.15)[1]), Sz - 0.018), ang, self.M("led_cool"), g, bevel=0)
        u = s0 + 0.14
        k = int(self.rng.random() * 5)
        while u < s1 - 0.1:
            p_ = self._F(f, u, 0.15)
            z = Sz + 0.0125
            kind = k % 5
            if kind == 0:     # stacked plates
                self.lathe(f"{name}_plates", [(0, 0), (0.09, 0), (0.125, 0.012), (0.125, 0.09), (0, 0.09)], (p_[0], p_[1], z), self.M("cup"), 28, g)
                u += 0.3
            elif kind == 1:   # lidded canisters
                for t_ in range(2):
                    q = self._F(f, u + t_ * 0.13, 0.15)
                    self.lathe(f"{name}_can", [(0, 0), (0.055, 0), (0.055, 0.19), (0.058, 0.19), (0.058, 0.215), (0.012, 0.22), (0.012, 0.235), (0, 0.235)], (q[0], q[1], z), self.M("steel"), 20, g)
                u += 0.34
            elif kind == 2:   # glass jars of dry goods
                for t_ in range(3):
                    q = self._F(f, u + t_ * 0.105, 0.15)
                    self.lathe(f"{name}_jar", [(0, 0), (0.044, 0), (0.046, 0.01), (0.046, 0.15), (0.03, 0.17), (0.03, 0.185), (0, 0.185)], (q[0], q[1], z), self.M("display_glass"), 16, g)
                    self.lathe(f"{name}_grain", [(0, 0.004), (0.04, 0.004), (0.04, 0.1 + 0.03 * t_), (0, 0.1 + 0.03 * t_)], (q[0], q[1], z), self.M(("beans", "kraft", "pastry")[t_ % 3]), 12, g)
                u += 0.4
            elif kind == 3:   # stock pot with lid
                self.lathe(f"{name}_pot", [(0, 0), (0.11, 0), (0.115, 0.01), (0.115, 0.17), (0.12, 0.175), (0.12, 0.185), (0.04, 0.2), (0.014, 0.2), (0.016, 0.225), (0, 0.228)], (p_[0], p_[1], z), self.M("steel"), 28, g)
                u += 0.32
            else:             # mixing bowls
                self.lathe(f"{name}_bowl", [(0, 0), (0.05, 0), (0.13, 0.075), (0.135, 0.085), (0.128, 0.085), (0.05, 0.012), (0, 0.01)], (p_[0], p_[1], z), self.M("steel"), 28, g)
                u += 0.32
            k += 1

    def _bench_prop(self, kind, f, u, g, name, H):
        ang = math.degrees(math.atan2(f["b"][1] - f["a"][1], f["b"][0] - f["a"][0]))
        p_ = self._F(f, u, 0.3)
        if kind == "board":
            self.box(f"{name}_board", (0.42, 0.28, 0.022), (p_[0], p_[1], H + 0.011), ang + self.rng.uniform(-6, 6), self.M("oak"), g, bevel=0.005)
        elif kind == "pot":
            self.lathe(f"{name}_saucepan", [(0, 0), (0.1, 0), (0.1, 0.12), (0.094, 0.12), (0.094, 0.006), (0, 0.006)], (p_[0], p_[1], H), self.M("steel"), 24, g)
            a_ = self._F(f, u + 0.1, 0.3, H + 0.1); b_ = self._F(f, u + 0.3, 0.4, H + 0.11)
            self.rod(f"{name}_handle", a_, b_, 0.009, self.M("black_steel"), 8, g)
        elif kind == "jars":
            for t_ in range(3):
                q = self._F(f, u - 0.1 + t_ * 0.1, 0.12)
                self.lathe(f"{name}_tin", [(0, 0), (0.04, 0), (0.04, 0.14), (0.042, 0.14), (0.042, 0.16), (0, 0.16)], (q[0], q[1], H), self.M(("oak", "steel", "white")[t_]), 14, g)
        elif kind == "knives":
            q = self._F(f, u, 0.1)
            self.box(f"{name}_knifeblock", (0.1, 0.17, 0.2), (q[0], q[1], H + 0.1), ang, self.M("walnut"), g, bevel=0.005)
            for t_ in range(4):
                h_ = self._F(f, u - 0.03 + t_ * 0.02, 0.13, H + 0.2)
                self.rod(f"{name}_knifehandle", h_, (h_[0], h_[1], H + 0.3), 0.008, self.M("black"), 8, g)
        elif kind == "bowls":
            self.lathe(f"{name}_mix", [(0, 0), (0.05, 0), (0.15, 0.09), (0.155, 0.1), (0.146, 0.1), (0.05, 0.012), (0, 0.01)], (p_[0], p_[1], H), self.M("steel"), 28, g)
        elif kind == "scale":
            self.box(f"{name}_scale", (0.2, 0.22, 0.04), (p_[0], p_[1], H + 0.02), ang, self.M("charcoal"), g, bevel=0.008)
            self.box(f"{name}_pan", (0.17, 0.17, 0.006), (p_[0], p_[1], H + 0.044), ang, self.M("brushed_steel"), g, bevel=0)
        else:
            for t_ in range(2):
                q = self._F(f, u + t_ * 0.09, 0.12)
                self.lathe(f"{name}_oil", [(0, 0), (0.032, 0), (0.033, 0.16), (0.012, 0.21), (0.012, 0.26), (0, 0.26)], (q[0], q[1], H), self.M("dark_glass"), 12, g)

    def _utensils(self, f, s0, s1, g, rid):
        """Hanging rail with ladles, whisks and pans."""
        z = 1.34
        L = min(s1 - s0 - 0.2, 1.5)
        c = (s0 + s1) / 2
        self.rod(f"{rid}_utensilrail", self._F(f, c - L / 2, 0.03, z), self._F(f, c + L / 2, 0.03, z), 0.006, self.M("steel"), 8, g)
        u = c - L / 2 + 0.08
        k = 0
        while u < c + L / 2 - 0.06:
            top = self._F(f, u, 0.04, z)
            kind = k % 4
            if kind in (0, 2):   # ladle / spatula
                lw = 0.26
                self.rod(f"{rid}_ladle", top, (top[0], top[1], z - lw), 0.004, self.M("steel"), 6, g)
                self.lathe(f"{rid}_ladlehead", [(0, 0), (0.03, 0.008), (0.04, 0.03), (0, 0.03)], (top[0], top[1], z - lw - 0.03), self.M("steel"), 12, g)
                u += 0.12
            elif kind == 1:      # small pan hung flat to the wall
                cp = self._F(f, u + 0.09, 0.03, z - 0.3)
                self.rod(f"{rid}_pan", self._F(f, u + 0.09, 0.012, z - 0.3), self._F(f, u + 0.09, 0.05, z - 0.3), 0.1, self.M("charcoal"), 26, g)
                self.rod(f"{rid}_panhandle", (cp[0], cp[1], z - 0.2), top, 0.006, self.M("steel"), 6, g)
                u += 0.26
            else:                # whisk
                self.rod(f"{rid}_whisk", top, (top[0], top[1], z - 0.16), 0.005, self.M("steel"), 6, g)
                self.lathe(f"{rid}_whiskhead", [(0.004, 0), (0.028, 0.05), (0.022, 0.1), (0.005, 0.12)], (top[0], top[1], z - 0.28), self.M("steel"), 8, g)
                u += 0.12
            k += 1

    def dress_storage(self, room):
        """Dry store: steel racking with boxes and sacks along the free walls."""
        rid = room["id"]
        g = self._collection("Kitchen")
        if rid not in self._finished and room.get("category") not in self._finished:
            self.finish_walls(rid, finish="#d9d6cd", skirting="charcoal", skirting_h=0.1)
        for f in self._room_faces(rid):
            blocked = self._face_blocked(f, 1.9, depth=0.5)
            cur, spans = 0.03, []
            for (b0, b1) in sorted(blocked) + [(f["len"] - 0.03, f["len"] + 1)]:
                if b0 - cur >= 0.7:
                    spans.append((cur, b0))
                cur = max(cur, b1)
            for (s0, s1) in spans:
                ang = math.degrees(math.atan2(f["b"][1] - f["a"][1], f["b"][0] - f["a"][0]))
                c, L = (s0 + s1) / 2, s1 - s0
                for lv, z in enumerate((0.2, 0.75, 1.3, 1.85)):
                    p_ = self._F(f, c, 0.25)
                    self.box(f"{rid}_rack", (L, 0.48, 0.022), (p_[0], p_[1], z), ang, self.M("brushed_steel"), g, bevel=0.002)
                    u = s0 + 0.22
                    while u < s1 - 0.2 and lv < 3:
                        q = self._F(f, u, 0.25)
                        if self.rng.random() < 0.82:
                            self.box(f"{rid}_box", (0.3, 0.34, self.rng.uniform(0.2, 0.36)), (q[0], q[1], z + 0.14), ang + self.rng.uniform(-3, 3), self.M(self.rng.choice(("kraft", "white", "hessian"))), g, bevel=0.01)
                        u += 0.38
                for s_ in (s0 + 0.03, s1 - 0.03):
                    for off in (0.04, 0.46):
                        q = self._F(f, s_, off)
                        self.box(f"{rid}_post", (0.026, 0.026, 1.95), (q[0], q[1], 0.975), ang, self.M("steel"), g, bevel=0.002)
                self._mark_face(f, s0, s1)
        self._batten(room, g, 34.0 + self._room_area(room) * 3.0)

    def _inset_sink(self, R, t, name):
        g = self._collection("Equipment")
        cx = R["a"][0] + R["u"][0] * t + R["n"][0] * R["depth"] / 2
        cy = R["a"][1] + R["u"][1] * t + R["n"][1] * R["depth"] / 2
        h = R["h"]
        ang = R["ang"]
        self._occupied.append((cx, cy, 0.25))
        self.box(f"{name}_rim", (0.42, 0.38, 0.006), (cx, cy, h + 0.002), ang, self.M("brushed_steel"), g, bevel=0)
        self.box(f"{name}_bowl", (0.36, 0.32, 0.002), (cx, cy, h + 0.0055), ang, self.M("steel_dark") if "steel_dark" in self.mats else self.M("charcoal"), g, bevel=0)
        back = 1 if R["front"] != R["n"] else -1
        tx, ty = cx + R["n"][0] * back * 0.22, cy + R["n"][1] * back * 0.22
        self.lathe(f"{name}_tap", [(0.024, 0), (0.02, 0.012), (0.012, 0.02), (0.012, 0.2), (0.008, 0.21), (0.008, 0.28), (0, 0.285)], (tx, ty, h), self.M("chrome"), 16, g)
        self.rod(f"{name}_spout", (tx, ty, h + 0.27), (tx - R["n"][0] * back * 0.17, ty - R["n"][1] * back * 0.17, h + 0.25), 0.008, self.M("chrome"), 10, g)

    # ---------------- cameras & render ----------------
    def camera(self, at, look_at, eye=1.55, fov=68, name="Camera", label=None, look_z=1.3):
        """Eye-level camera at plan point `at` looking at plan point `look_at` at height look_z."""
        cam = bpy.data.cameras.new(name)
        cam.lens_unit = "FOV"
        cam.clip_start = 0.3    # stray leaves right at the lens never fill the frame
        cam.angle = math.radians(fov)
        o = bpy.data.objects.new(name, cam)
        o.location = (at[0], at[1], eye)
        direction = Vector((look_at[0], look_at[1], look_z)) - o.location
        o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        self._collection("Cameras").objects.link(o)
        if self.sc.camera is None:
            self.sc.camera = o
        self.cameras.append((o, label or name))
        return o

    def _exposure(self):
        return {"day": 0.85, "golden": 0.8, "evening": 1.05}.get(self._mood, 0.85)

    def finish(self, engine="CYCLES", samples=96, res=(1600, 900)):
        """Render settings. Live Blender keeps EEVEE for interaction; headless renders use Cycles."""
        sc = self.sc
        if not self._plan_done:      # safety net: a design that forgot the legend still gets equipped washrooms and kitchens
            self.plan_equipment()
        try:
            sc.render.engine = engine
        except TypeError:
            pass
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        if engine == "CYCLES":
            sc.cycles.samples = samples
            sc.cycles.max_bounces = 14
            sc.cycles.diffuse_bounces = 8        # interiors live on bounced light
            sc.cycles.glossy_bounces = 6
            sc.cycles.transmission_bounces = 12
            sc.cycles.sample_clamp_indirect = 8.0  # no fireflies from small hot sources
            sc.cycles.caustics_reflective = False
            sc.cycles.caustics_refractive = False
            sc.cycles.blur_glossy = 1.0
            try:
                sc.cycles.use_denoising = True
            except Exception:
                pass
            try:
                prefs = bpy.context.preferences.addons["cycles"].preferences
                for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
                    try:
                        prefs.compute_device_type = backend
                        prefs.get_devices()
                        if any(d.type == backend for d in prefs.devices):
                            sc.cycles.device = "GPU"
                            for d in prefs.devices:
                                d.use = True
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        try:
            sc.view_settings.view_transform = "AgX"
        except TypeError:
            pass
        # A bare AgX transform desaturates and flattens; a contrast look + a touch of exposure
        # restores the punch a reference interior shot has. Look names vary by Blender version,
        # so try the richer ones first and fall back.
        for _look in ("AgX - Medium High Contrast", "AgX - Base Contrast", "None"):
            try:
                sc.view_settings.look = _look
                break
            except TypeError:
                continue
        sc.view_settings.exposure = self._exposure()
        for o in sc.objects:      # Cycles shadow rays stop at glass: without this no sun or sky ever reaches a room directly
            if o.type == "MESH" and o.data.materials and all(m and m.use_nodes and _principled(m).inputs["Transmission Weight"].default_value > 0.5 for m in o.data.materials):
                o.visible_shadow = False
        for o in bpy.context.selected_objects:
            o.select_set(False)
        return sc

    def _clear_of_canopies(self, cam):
        """A photographer never shoots from inside a tree: step the camera out along its own axis until the leaves are behind it."""
        fw = (cam.rotation_euler.to_matrix() @ Vector((0, 0, -1)))
        fw = Vector((fw.x, fw.y, 0)).normalized()
        for _ in range(30):
            p = cam.location
            near = [(x, y, r) for x, y, r in self._canopies if math.hypot(p.x - x, p.y - y) < r and (Vector((x - p.x, y - p.y, 0))).dot(fw) > -0.2]
            if not near:
                return
            cam.location = p + fw * 0.15

    def render_stills(self, out_dir, samples=96, res=(1600, 900)):
        """Render every camera created with camera() to out_dir; prints STILL_TOTAL/STILL_DONE markers."""
        os.makedirs(out_dir, exist_ok=True)
        self.finish("CYCLES", samples, res)
        sc = self.sc
        print(f"STILL_TOTAL {len(self.cameras)}", flush=True)
        out = []
        for i, (cam, label) in enumerate(self.cameras):
            sc.camera = cam
            self._clear_of_canopies(cam)
            room = self._room_at(cam.location.x, cam.location.y)
            indoors = bool(room and (room.get("ceilingHeight") or 0) > 0)
            sc.view_settings.exposure = self._exposure() if indoors else self._exposure() - {"day": 1.55, "golden": 1.45, "evening": 0.3}.get(self._mood, 1.5)
            fn = f"still_{i:02d}.jpg"
            sc.render.image_settings.file_format = "JPEG"
            sc.render.image_settings.quality = 92
            sc.render.filepath = os.path.join(out_dir, fn)
            bpy.ops.render.render(write_still=True)
            print(f"STILL_DONE {i + 1} {label}", flush=True)
            out.append({"label": label, "image": fn})
        return out

    def render_panos(self, out_dir, points, eye=1.55, res=(2048, 1024), samples=64):
        """360° equirectangular at each (x, y, yaw_deg, label); writes manifest.json for TourViewer."""
        import json
        os.makedirs(out_dir, exist_ok=True)
        self.finish("CYCLES", samples, res)
        sc = self.sc
        cam_data = bpy.data.cameras.new("PanoCam")
        cam_data.type = "PANO"
        for target in (cam_data, getattr(cam_data, "cycles", None)):
            if target is not None and hasattr(target, "panorama_type"):
                try:
                    target.panorama_type = "EQUIRECTANGULAR"
                except Exception:
                    pass
        cam = bpy.data.objects.new("PanoCam", cam_data)
        self._collection("Cameras").objects.link(cam)
        sc.camera = cam
        print(f"PANO_TOTAL {len(points)}", flush=True)
        manifest = {"stops": []}
        for i, (x, y, yaw, label) in enumerate(points):
            cam.location = (x, y, eye)
            cam.rotation_euler = (math.radians(90), 0.0, math.radians(yaw))
            fn = f"pano_{i:02d}.jpg"
            sc.render.image_settings.file_format = "JPEG"
            sc.render.image_settings.quality = 90
            sc.render.filepath = os.path.join(out_dir, fn)
            bpy.ops.render.render(write_still=True)
            print(f"PANO_DONE {i + 1} {label}", flush=True)
            manifest["stops"].append({"id": f"s{i}", "name": label, "category": "room", "position": [round(x, 3), round(y, 3)], "yawDeg": yaw, "image": fn})
        with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
        return manifest

    def save(self, path):
        bpy.ops.wm.save_as_mainfile(filepath=path)
        return path

    def _web_lod(self, target=230000):
        """Lighten the walkable model only (the export runs after renders). Library models swap to their authored low-detail
        versions (assets/models_web: clean round tubes, never crushed); foliage thins with larger leaves; fine twigs drop out.
        Only what remains over budget (props like cup rows, scanned plants) is decimated."""
        web_dir = os.path.join(self.assets_root, "models_web")
        cache = {}
        for (o, file, idx) in self._placed:
            path = os.path.join(web_dir, file)
            if file not in cache:
                cache[file] = None
                if os.path.isfile(path):
                    before = set(bpy.data.objects)
                    bpy.ops.import_scene.gltf(filepath=path)
                    new = [x for x in bpy.data.objects if x not in before]
                    cache[file] = [x.data for x in new if x.type == "MESH"]
                    for x in new:
                        for c in list(x.users_collection):
                            c.objects.unlink(x)
            if cache[file] and idx < len(cache[file]):
                o.data = cache[file][idx]
        import random as _r
        rnd = _r.Random(5)
        def tris(ob):
            return sum(len(p.vertices) - 2 for p in ob.data.polygons)
        for o in list(self.sc.objects):
            if o.type != "MESH":
                continue
            if "_twig" in o.name:
                bpy.data.objects.remove(o, do_unlink=True)
                continue
            if "_leaf" in o.name or "_crown" in o.name:
                keep = 0.07 if ("hedge" in o.name or "box" in o.data.materials[0].name) else 0.2
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.faces.ensure_lookup_table()
                faces = list(bm.faces)
                kill = []
                k = min(2.4, (1.0 / keep) ** 0.5)
                for i in range(0, len(faces) - 1, 2):      # a leaf is two faces
                    pair = faces[i:i + 2]
                    if rnd.random() > keep:
                        kill += pair
                    else:
                        vs = {v for f in pair for v in f.verts}
                        c = sum((v.co for v in vs), Vector((0, 0, 0))) / len(vs)
                        for v in vs:
                            v.co = c + (v.co - c) * k
                bmesh.ops.delete(bm, geom=kill, context="FACES")
                bm.to_mesh(o.data)
                bm.free()
        total = sum(tris(o) for o in self.sc.objects if o.type == "MESH")
        swapped = {o.name for (o, f, i) in self._placed if cache.get(f)}
        by = {}
        file_of = {o.name: f for (o, f, i) in self._placed}
        for o in self.sc.objects:
            if o.type != "MESH":
                continue
            f = file_of.get(o.name, "")
            ratio = 0.2 if f.startswith("plant/") else 0.13 if f.startswith("pastry/") else 0.3 if "cups" in o.name else 0.45 if (f and o.name not in swapped) else None
            if ratio and tris(o) > 300:
                m = o.modifiers.new("web", "DECIMATE")
                m.decimate_type = "COLLAPSE"
                m.ratio = ratio
                by[o.name.split("_")[0]] = by.get(o.name.split("_")[0], 0) + 1
        dg = bpy.context.evaluated_depsgraph_get()
        after = sum(len(o.evaluated_get(dg).to_mesh().polygons) * 1 for o in self.sc.objects if o.type == "MESH")
        print(f"WEB_LOD before={total} faces_after={after}", flush=True)

    def export_glb(self, path, lights=True, web_tex=512):
        """Web-weight GLB of the whole café (WebP textures, lights included). Blender (x, y, z) exports
        to glTF (x, z, -y), which is exactly the web viewer's frame (worldX = planX, worldZ = -planY)."""
        for o in bpy.data.objects:
            o.select_set(False)
        for img in bpy.data.images:      # web weight; call this LAST, renders keep full-size textures
            w_, h_ = img.size
            if max(w_, h_) > web_tex and img.has_data:
                k = web_tex / max(w_, h_)
                img.scale(max(1, int(w_ * k)), max(1, int(h_ * k)))
        self._web_lod()
        kwargs = dict(filepath=path, export_format="GLB", export_apply=True, export_lights=lights, export_cameras=False, export_yup=True)
        for extra in ({"export_image_format": "WEBP", "export_image_quality": 80}, {"export_image_format": "JPEG", "export_image_quality": 80}, {}):
            try:
                bpy.ops.export_scene.gltf(**kwargs, **extra)
                break
            except TypeError:
                continue
        return path
