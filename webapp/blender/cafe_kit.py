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
    K.lights()                                 # sun + interior lamps + fills
    K.camera((5.0, 12.0), look_at=(3.0, 18.0)) # eye-level camera for the hero still
    K.finish()                                 # EEVEE preview settings, selection cleanup
"""

import math
import os
import random

import bpy  # type: ignore
import bmesh  # type: ignore
from mathutils import Vector  # type: ignore

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


# ----------------------------------------------------------------------------------------------
# the kit
# ----------------------------------------------------------------------------------------------

class Kit:
    def __init__(self, scene, textures_dir=None, seed=7, collection="Cafe", clear=True):
        self.scene = scene
        self.tex = textures_dir
        self.rng = random.Random(seed)
        self.sc = bpy.context.scene
        if clear:
            self.clear_scene()
        self.coll = self._collection(collection)
        self.mats = {}
        self._img_cache = {}
        self._build_materials()
        self.stops = []   # suggested camera standing points (x, y, yaw_deg, label)
        self.cameras = []

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

    def mat_pbr(self, name, folder, tint="#ffffff", scale=1.0, roughness_mul=1.0, metallic=0.0):
        """PBR from textures/<folder>/{color,normal,rough}.jpg, tinted and tiled (scale = tiles/m)."""
        if name in self.mats:
            return self.mats[name]
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
        mapping.inputs["Scale"].default_value = (scale, scale, scale)
        # object-space mapping: no UVs needed on boxes, texture stays life-sized
        nt.links.new(texco.outputs["Object"], mapping.inputs["Vector"])
        cnode = nt.nodes.new("ShaderNodeTexImage")
        cnode.image = col
        cnode.projection = "BOX"
        cnode.projection_blend = 0.2
        nt.links.new(mapping.outputs["Vector"], cnode.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(cnode.outputs["Color"], mix.inputs[6])
        mix.inputs[7].default_value = hex_to_linear(tint)
        nt.links.new(mix.outputs[2], p.inputs["Base Color"])
        rough = self._img(os.path.join(base, "rough.jpg"))
        if rough:
            rough.colorspace_settings.name = "Non-Color"
            rnode = nt.nodes.new("ShaderNodeTexImage")
            rnode.image = rough
            rnode.projection = "BOX"
            nt.links.new(mapping.outputs["Vector"], rnode.inputs["Vector"])
            if roughness_mul != 1.0:
                mm = nt.nodes.new("ShaderNodeMath")
                mm.operation = "MULTIPLY"
                mm.inputs[1].default_value = roughness_mul
                nt.links.new(rnode.outputs["Color"], mm.inputs[0])
                nt.links.new(mm.outputs[0], p.inputs["Roughness"])
            else:
                nt.links.new(rnode.outputs["Color"], p.inputs["Roughness"])
        else:
            p.inputs["Roughness"].default_value = 0.8 * roughness_mul
        nrm = self._img(os.path.join(base, "normal.jpg"))
        if nrm:
            nrm.colorspace_settings.name = "Non-Color"
            nnode = nt.nodes.new("ShaderNodeTexImage")
            nnode.image = nrm
            nnode.projection = "BOX"
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.inputs["Strength"].default_value = 0.6
            nt.links.new(mapping.outputs["Vector"], nnode.inputs["Vector"])
            nt.links.new(nnode.outputs["Color"], nmap.inputs["Color"])
            nt.links.new(nmap.outputs["Normal"], p.inputs["Normal"])
        self.mats[name] = m
        return m

    def mat_checker(self, name, c1, c2, scale=0.3):
        """Two-tone checker floor (object-space, scale = tile size in m)."""
        if name in self.mats:
            return self.mats[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = _principled(m)
        texco = nt.nodes.new("ShaderNodeTexCoord")
        ck = nt.nodes.new("ShaderNodeTexChecker")
        ck.inputs["Scale"].default_value = 1.0 / scale
        ck.inputs["Color1"].default_value = hex_to_linear(c1)
        ck.inputs["Color2"].default_value = hex_to_linear(c2)
        nt.links.new(texco.outputs["Object"], ck.inputs["Vector"])
        nt.links.new(ck.outputs["Color"], p.inputs["Base Color"])
        p.inputs["Roughness"].default_value = 0.35
        self.mats[name] = m
        return m

    def _build_materials(self):
        M = self.mats
        self.mat_pbr("plaster", "plaster", "#ece3d3", scale=0.5)
        self.mat_pbr("plaster_warm", "plaster", "#d9c9b0", scale=0.5)
        self.mat_pbr("oak", "oak", "#d8b98c", scale=0.7)
        self.mat_pbr("walnut", "wood", "#8a5a3c", scale=0.9, roughness_mul=0.7)
        self.mat_pbr("walnut_slat", "wood", "#7a4a30", scale=1.8, roughness_mul=0.7)
        self.mat_pbr("lime_plaster", "plaster", "#cdbfa6", scale=0.5)
        self.mat_pbr("tile_white", "marble", "#f4f1ea", scale=0.9, roughness_mul=0.5)
        self.mat_pbr("rattan", "fabric", "#c8a978", scale=4.0)
        self.mat_pbr("terrazzo", "terrazzo", "#ffffff", scale=0.8, roughness_mul=0.5)
        self.mat_pbr("stone", "concrete", "#b9b4ab", scale=0.25, roughness_mul=0.8)
        self.mat_pbr("concrete", "concrete", "#a8a39a", scale=0.5)
        self.mat_pbr("marble", "marble", "#f2eee6", scale=0.6, roughness_mul=0.4)
        self.mat_plain("boucle", "#d8ccb8", roughness=1.0)
        self.mat_plain("boucle_sage", "#9fae95", roughness=1.0)
        self.mat_plain("leather", "#6b4a35", roughness=0.55, coat=0.2)
        self.mat_plain("ceiling", "#2d2b29", roughness=0.95)
        self.mat_plain("sage", "#9aa88f", roughness=0.9)
        self.mat_plain("terracotta", "#b9704f", roughness=0.9)
        self.mat_plain("ink", "#20262a", roughness=0.9)
        self.mat_plain("ochre", "#c9a15a", roughness=0.9)
        self.mat_plain("felt", "#2a2620", roughness=1.0)
        self.mat_plain("rug", "#8d6e55", roughness=1.0)
        self.mat_plain("mirror", "#e8e8e8", roughness=0.02, metallic=1.0)
        self.mat_plain("neon", "#000000", emission="#ff9a6a", strength=30.0)
        self.mat_plain("bulb", "#000000", emission="#ffd9a0", strength=20.0)
        self.mat_plain("paper", "#efe6d4", roughness=0.9)
        self.mat_checker("tile_check", "#e9e2d6", "#3a3632", scale=0.3)
        self.mat_plain("ceiling_light", "#e9e3d8", roughness=0.9)
        self.mat_plain("black", "#161616", roughness=0.5)
        self.mat_plain("black_steel", "#1d1d1e", roughness=0.45, metallic=0.6)
        self.mat_plain("charcoal", "#3b3a39", roughness=0.8)
        self.mat_plain("steel", "#b9bcbf", roughness=0.28, metallic=1.0)
        self.mat_plain("brass", "#bf9659", roughness=0.3, metallic=1.0)
        self.mat_plain("bronze", "#8a6a48", roughness=0.42, metallic=0.9)
        self.mat_plain("copper", "#b0623b", roughness=0.3, metallic=1.0)
        self.mat_plain("cream", "#eae2d3", roughness=0.8)
        self.mat_plain("white", "#f4f1ea", roughness=0.5)
        self.mat_plain("cup", "#f4f1ea", roughness=0.45, coat=0.3)
        self.mat_plain("kraft", "#b48a5a", roughness=0.8)
        self.mat_plain("pastry", "#c98d4d", roughness=0.7)
        self.mat_plain("pastry_dark", "#8a5a30", roughness=0.7)
        self.mat_plain("greens", "#5f7f46", roughness=0.9)
        self.mat_plain("olive_green", "#7d8a66", roughness=1.0)
        self.mat_plain("bark", "#5e5145", roughness=1.0)
        self.mat_plain("pot", "#a69f95", roughness=0.9)
        self.mat_plain("canvas", "#eee8da", roughness=0.95)
        self.mat_plain("enamel_sage", "#9fae95", roughness=0.25, coat=0.6)
        self.mat_plain("matte_black", "#1a1a1a", roughness=0.6)
        self.mat_plain("screen", "#0d0f12", roughness=0.15, emission="#1b2430", strength=1.6)
        self.mat_plain("menu_glow", "#17110d", roughness=0.3, emission="#2a211a", strength=2.5)
        self.mat_plain("led", "#000000", emission="#ffc78a", strength=18.0)
        self.mat_plain("led_cool", "#000000", emission="#fff0d6", strength=12.0)
        self.mat_plain("opal", "#f3ece0", roughness=0.4, emission="#ffd29a", strength=6.0)
        self.mat_plain("lens", "#000000", emission="#fff0d6", strength=25.0)
        self.mat_plain("red", "#9b2d20", roughness=0.5)
        self.mat_plain("beans", "#4a2a16", roughness=0.7)
        self.mat_glass("glass")
        self.mat_glass("display_glass", "#eef7f5")
        self.mat_plain("dark_glass", "#1b2326", roughness=0.12, metallic=0.3)

    def M(self, name):
        return self.mats[name]

    # ---------------- geometry primitives ----------------
    def box(self, name, size, loc, rot=0.0, mat=None, coll=None):
        """Axis box: size (w along x, d along y, h), loc = centre (x, y, z), rot degrees about Z."""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.scale = (size[0], size[1], size[2])
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
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.location = (loc[0], loc[1], loc[2] + h / 2)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def sphere(self, name, r, loc, mat=None, scale=(1, 1, 1), coll=None):
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
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
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        if mat:
            o.data.materials.append(mat)
        (coll or self.coll).objects.link(o)
        return o

    def text(self, name, body, loc, rot=0.0, size=0.3, mat=None, extrude=0.01, align="CENTER", upright=True, coll=None):
        """3D text (brand wordmark, menu headings). upright=True stands it on a wall (rot = wall direction)."""
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = size
        cu.extrude = extrude
        cu.align_x = align
        o = bpy.data.objects.new(name, cu)
        o.location = loc
        o.rotation_euler = (math.radians(90) if upright else 0, 0, math.radians(rot))
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
    def architecture(self, wall="plaster", floors=None, ceiling="ceiling", skirting=True, downlights=True, glazing=True):
        """Walls with doors/windows, floors per room category, ceilings with a downlight grid.
        floors: {category: material name}, e.g. {"seating_indoor": "oak", "service_counter": "stone",
        "seating_outdoor": "stone", "wc": "concrete"}."""
        S = self.scene
        floors = floors or {}
        wm = self.M(wall)
        openings = S.get("openings", [])
        arch = self._collection("Architecture")
        for w in S["walls"]:
            ax, ay = w["a"]; bx, by = w["b"]
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-4:
                continue
            ang = math.degrees(math.atan2(by - ay, bx - ax))
            ux, uy = (bx - ax) / L, (by - ay) / L
            H = w["height"]; t = w["thickness"]; base = w.get("baseHeight") or 0.0
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
                cursor = max(cursor, s1)
            if cursor < L - 1e-4:
                segs.append((cursor, L, 0.0, H, "solid"))
            for (s0, s1, z0, z1, kind) in segs:
                u = (s0 + s1) / 2
                cx, cy = ax + ux * u, ay + uy * u
                if kind == "glass":
                    self.box(f"glass_{w['id']}", (s1 - s0, 0.02, z1 - z0), (cx, cy, base + (z0 + z1) / 2), ang, self.M("glass"), arch)
                    # frame + mullions
                    fr = self.M("black")
                    for zz in (z0 + 0.03, z1 - 0.03):
                        self.box(f"frame_{w['id']}", (s1 - s0, t + 0.02, 0.06), (cx, cy, base + zz), ang, fr, arch)
                    n = max(1, int((s1 - s0) / 1.2))
                    for k in range(n + 1):
                        uu = s0 + (s1 - s0) * k / n
                        self.box(f"mullion_{w['id']}", (0.05, t + 0.02, z1 - z0), (ax + ux * uu, ay + uy * uu, base + (z0 + z1) / 2), ang, fr, arch)
                else:
                    self.box(f"wall_{w['id']}_{kind}", (s1 - s0, t, z1 - z0), (cx, cy, base + (z0 + z1) / 2), ang, wm, arch)
                    if kind == "solid" and skirting:
                        self.box(f"skirt_{w['id']}", (s1 - s0, t + 0.02, 0.1), (cx, cy, base + 0.05), ang, self.M("charcoal"), arch)
        for room in S["rooms"]:
            cat = room.get("category", "other")
            fm = floors.get(cat) or ("stone" if cat in ("seating_outdoor",) else "oak" if cat in ("seating_indoor", "entrance", "corridor") else "stone" if cat == "service_counter" else "concrete")
            self.slab(f"floor_{room['id']}", room["polygon"], 0.0, self.M(fm), coll=arch)
            ch = room.get("ceilingHeight") or 0
            if ch > 0:
                self.slab(f"ceiling_{room['id']}", room["polygon"], ch, self.M(ceiling), coll=arch)
                if downlights:
                    self.downlights(room["polygon"], ch, coll=arch)
        return arch

    def downlights(self, polygon, z, step=2.2, margin=0.7, power=90.0, coll=None):
        xs = [p[0] for p in polygon]; ys = [p[1] for p in polygon]
        n = 0
        x = min(xs) + margin
        while x <= max(xs) - margin:
            y = min(ys) + margin
            while y <= max(ys) - margin:
                if point_in_poly(polygon, x, y):
                    self.cyl(f"downlight", 0.055, 0.02, (x, y, z - 0.02), self.M("lens"), 16, coll=coll)
                    d = bpy.data.lights.new("downlight", "SPOT")
                    d.energy = power; d.spot_size = math.radians(70); d.spot_blend = 0.6
                    d.color = kelvin_to_rgb(3000); d.shadow_soft_size = 0.08
                    o = bpy.data.objects.new("downlight", d)
                    o.location = (x, y, z - 0.03)
                    o.rotation_euler = (0, 0, 0)  # spot points -Z
                    (coll or self.coll).objects.link(o)
                    n += 1
                y += step
            x += step
        return n

    # ---------------- joinery & equipment ----------------
    def counter_run(self, a, b, depth=0.7, h=0.95, top="terrazzo", front="walnut_slat", led_kick=True, top_thick=0.04, side=1, name="counter"):
        """Service counter from a to b (plan points). The counter body extends `depth` to the LEFT of
        the a→b direction (side=1) or right (side=-1): the customer stands on the other side."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        g = self._collection("Joinery")
        # plinth (recessed) + body + top with overhang on the customer side
        self.box(f"{name}_plinth", (L, depth - 0.1, 0.1), (cx, cy, 0.05), ang, self.M("black"), g)
        self.box(f"{name}_body", (L, depth, h - 0.1 - top_thick), (cx, cy, 0.1 + (h - 0.1 - top_thick) / 2), ang, self.M(front), g)
        self.box(f"{name}_top", (L + 0.04, depth + 0.08, top_thick), (cx - nx * 0.03, cy - ny * 0.03, h - top_thick / 2), ang, self.M(top), g)
        if led_kick:
            # warm LED in the plinth recess, washing the floor along the customer face
            fx, fy = cx - nx * (depth / 2 - 0.025), cy - ny * (depth / 2 - 0.025)
            self.box(f"{name}_led", (L - 0.1, 0.015, 0.012), (fx, fy, 0.085), ang, self.M("led"), g)
        return (cx, cy, h, ang)

    def back_bar(self, a, b, depth=0.6, h=0.92, shelves=3, shelf_z=(1.55, 1.95, 2.35), cups=True, led=True, splash="terrazzo", body="walnut", top="terrazzo", side=1, name="backbar"):
        """Back counter against a wall from a to b with floating shelves above, rows of cups and LED
        strips under each shelf. The body extends `depth` to the left of a→b (side=1)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Joinery")
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
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
            if cups:
                self.cup_row(a, b, z + 0.0175, offset=sd / 2, side=side, name=f"{name}_cups{i}")
        return (cx, cy, h, ang)

    def cup_row(self, a, b, z, offset=0.15, spacing=0.125, side=1, name="cups", margin=0.1, rows=1, row_gap=0.1):
        """Rows of takeaway cups along a→b at height z (one mesh for speed)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        bm = bmesh.new()
        n = int((L - 2 * margin) / spacing)
        for r in range(rows):
            off = offset + r * row_gap
            for i in range(n + 1):
                u = margin + i * spacing
                x, y = a[0] + ux * u + nx * off, a[1] + uy * u + ny * off
                res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.034, radius2=0.045, depth=0.13)
                bmesh.ops.translate(bm, verts=res["verts"], vec=(x, y, z + 0.065))
                res2 = bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=0.041, radius2=0.0465, depth=0.05)
                bmesh.ops.translate(bm, verts=res2["verts"], vec=(x, y, z + 0.065))
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.data.materials.append(self.M("cup"))
        self._collection("Props").objects.link(o)
        return o

    def espresso_station(self, at, rot=0.0, on=0.95, machine_w=1.0, grinders=2, name="espresso"):
        """Espresso machine + grinders on a counter top at `at` (plan point, centre of the machine),
        facing `rot` (degrees; the barista side is behind)."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), on + dz)
        # machine: matte black body, chrome top rail, brass badge, group heads, cup warmer tray
        self.box(f"{name}_body", (machine_w, 0.56, 0.42), P(0, 0, 0.21), rot, self.M("matte_black"), g)
        self.box(f"{name}_top", (machine_w, 0.56, 0.03), P(0, 0, 0.435), rot, self.M("steel"), g)
        self.box(f"{name}_rail", (machine_w, 0.02, 0.05), P(0, 0.27, 0.47), rot, self.M("steel"), g)
        for k in range(3):
            dx = -machine_w / 2 + machine_w * (k + 1) / 4
            self.cyl(f"{name}_group", 0.045, 0.1, P(dx, -0.2, 0.17), self.M("steel"), 16, coll=g)
            self.box(f"{name}_handle", (0.02, 0.16, 0.02), P(dx, -0.3, 0.16), rot, self.M("walnut"), g)
        self.cyl(f"{name}_wand", 0.008, 0.3, P(machine_w / 2 + 0.03, -0.1, 0.1), self.M("steel"), 10, rot=(0, 25, 0), coll=g)
        self.box(f"{name}_badge", (0.14, 0.01, 0.06), P(0, -0.285, 0.3), rot, self.M("brass"), g)
        # cups on the warmer
        a = P(-machine_w / 2 + 0.08, 0.1, 0.45); b = P(machine_w / 2 - 0.08, 0.1, 0.45)
        self.cup_row((a[0], a[1]), (b[0], b[1]), on + 0.45, offset=0.0, spacing=0.095, margin=0.0, name=f"{name}_cups")
        for k in range(grinders):
            gx = machine_w / 2 + 0.22 + k * 0.3
            self.box(f"{name}_grinder{k}", (0.22, 0.3, 0.3), P(gx, -0.05, 0.15), rot, self.M("matte_black"), g)
            self.cyl(f"{name}_hopper{k}", 0.08, 0.2, P(gx, -0.02, 0.3), self.M("dark_glass"), 18, coll=g)
            self.cyl(f"{name}_ring{k}", 0.085, 0.015, P(gx, -0.02, 0.295), self.M("copper"), 18, coll=g)
            self.sphere(f"{name}_beans{k}", 0.06, P(gx, -0.02, 0.42), self.M("beans"), (1, 1, 0.5), coll=g)
        return g

    def display_case(self, at, rot=0.0, w=1.3, d=0.75, on=0.0, h_base=0.9, glass_h=0.55, pastries=True, name="display"):
        """Pastry / grab-and-go display: cabinet base + glass top with lit shelves and food inside."""
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), on + dz)
        self.box(f"{name}_base", (w, d, h_base - 0.04), P(0, 0, (h_base - 0.04) / 2), rot, self.M("walnut_slat"), g)
        self.box(f"{name}_top", (w + 0.04, d + 0.04, 0.04), P(0, 0, h_base - 0.02), rot, self.M("terrazzo"), g)
        self.box(f"{name}_glass", (w, d, glass_h), P(0, 0, h_base + glass_h / 2), rot, self.M("display_glass"), g)
        self.box(f"{name}_lid", (w + 0.02, d + 0.02, 0.03), P(0, 0, h_base + glass_h + 0.015), rot, self.M("black_steel"), g)
        self.box(f"{name}_led", (w - 0.1, 0.02, 0.01), P(0, d / 2 - 0.04, h_base + glass_h - 0.03), rot, self.M("led_cool"), g)
        self.box(f"{name}_shelf", (w - 0.08, d - 0.12, 0.02), P(0, 0, h_base + 0.26), rot, self.M("steel"), g)
        if pastries:
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
        g = self._collection("Equipment")
        r = math.radians(rot)
        def P(dx, dy, dz=0.0):
            return (at[0] + dx * math.cos(r) - dy * math.sin(r), at[1] + dx * math.sin(r) + dy * math.cos(r), on + dz)
        self.box(f"{name}_base", (0.22, 0.18, 0.03), P(0, 0, 0.015), rot, self.M("oak"), g)
        self.box(f"{name}_arm", (0.04, 0.04, 0.2), P(0, 0.04, 0.12), rot, self.M("steel"), g)
        self.box(f"{name}_screen", (0.32, 0.02, 0.22), P(0, 0.0, 0.3), rot + 180, self.M("screen"), g)
        self.box(f"{name}_reader", (0.09, 0.09, 0.05), P(0.2, -0.05, 0.025), rot, self.M("enamel_sage"), g)
        return g

    def menu_screen(self, at, rot=0.0, w=1.45, h=0.82, z=2.1, name="menu"):
        """Wall-mounted menu screen; `at` on the wall face, `rot` = wall direction, screen faces left of it."""
        g = self._collection("Equipment")
        self.box(f"{name}_frame", (w + 0.04, 0.05, h + 0.04), (at[0], at[1], z), rot, self.M("black"), g)
        r = math.radians(rot)
        self.box(f"{name}_panel", (w, 0.02, h), (at[0] - math.sin(r) * 0.03, at[1] + math.cos(r) * 0.03, z), rot, self.M("menu_glow"), g)
        return g

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
        pal = ["#b48a5a", "#2a2420", "#3e5c44", "#efe8dc", "#7a4a2c", "#c9b089", "#9b2d20"]
        for i in range(levels):
            z = 0.12 + i * (h - 0.4) / max(1, levels - 1)
            self.box(f"{name}_shelf{i}", (L - 0.06, depth - 0.04, 0.025), (cx, cy, z), ang, self.M("black_steel"), g)
            if products:
                u = 0.12
                while u < L - 0.12:
                    w_ = 0.07 + self.rng.random() * 0.06; hh = 0.12 + self.rng.random() * 0.14
                    col = pal[self.rng.randrange(len(pal))]
                    m = self.mat_plain(f"product_{col}", col, roughness=0.7)
                    x, y = a[0] + ux * (u + w_ / 2) + nx * (depth * 0.5), a[1] + uy * (u + w_ / 2) + ny * (depth * 0.5)
                    self.box(f"{name}_product", (w_, 0.07 + self.rng.random() * 0.05, hh), (x, y, z + 0.0125 + hh / 2), ang, m, self._collection("Props"))
                    u += w_ + 0.035 + self.rng.random() * 0.05
        return g

    # ---------------- seating ----------------
    def chair(self, at, rot=0.0, seat_mat="boucle", frame="oak", name="chair"):
        """Bentwood-style café chair at `at`, facing `rot` (the back is behind)."""
        g = self._collection("Seating")
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

    def table(self, at, shape="round", size=0.8, h=0.74, top="walnut", chairs=2, chair_r=None, name="table", seat_mat="boucle"):
        """Table with evenly spaced chairs around it (round) or on the long sides (rect: size=(w,d))."""
        g = self._collection("Seating")
        if shape == "round":
            r = size / 2
            self.cyl(f"{name}_top", r, 0.03, (at[0], at[1], h - 0.03), self.M(top), 40, coll=g)
            self.cyl(f"{name}_edge", r + 0.004, 0.012, (at[0], at[1], h - 0.03), self.M("brass"), 40, coll=g)
            self.cyl(f"{name}_stem", 0.04, h - 0.05, (at[0], at[1], 0.02), self.M("black"), 16, coll=g)
            self.cyl(f"{name}_base", 0.26, 0.02, (at[0], at[1], 0), self.M("black"), 32, coll=g)
            cr = chair_r or (r + 0.33)
            for i in range(chairs):
                a = 2 * math.pi * i / chairs + math.pi / 2
                cx, cy = at[0] + math.cos(a) * cr, at[1] + math.sin(a) * cr
                self.chair((cx, cy), math.degrees(a) + 90, seat_mat=seat_mat, name=f"{name}_chair{i}")
        else:
            w, d = size if isinstance(size, (tuple, list)) else (size, size * 0.6)
            self.box(f"{name}_top", (w, d, 0.03), (at[0], at[1], h - 0.015), 0, self.M(top), g)
            self.box(f"{name}_edge", (w + 0.008, d + 0.008, 0.012), (at[0], at[1], h - 0.03), 0, self.M("brass"), g)
            for sx, sy in ((-w / 2 + 0.06, -d / 2 + 0.06), (w / 2 - 0.06, -d / 2 + 0.06), (-w / 2 + 0.06, d / 2 - 0.06), (w / 2 - 0.06, d / 2 - 0.06)):
                self.box(f"{name}_leg", (0.04, 0.04, h - 0.03), (at[0] + sx, at[1] + sy, (h - 0.03) / 2), 0, self.M("black"), g)
            per_side = max(1, chairs // 2)
            for i in range(per_side):
                x = at[0] - w / 2 + w * (i + 0.5) / per_side
                self.chair((x, at[1] - d / 2 - 0.3), 0, seat_mat=seat_mat, name=f"{name}_chair_s{i}")
                self.chair((x, at[1] + d / 2 + 0.3), 180, seat_mat=seat_mat, name=f"{name}_chair_n{i}")
        return g

    def stool(self, at, h=0.75, name="stool"):
        g = self._collection("Seating")
        self.cyl(f"{name}_seat", 0.17, 0.05, (at[0], at[1], h - 0.05), self.M("leather"), 20, coll=g)
        self.cyl(f"{name}_stem", 0.025, h - 0.07, (at[0], at[1], 0.02), self.M("black"), 12, coll=g)
        self.cyl(f"{name}_base", 0.2, 0.02, (at[0], at[1], 0), self.M("black"), 24, coll=g)
        self.cyl(f"{name}_ring", 0.17, 0.015, (at[0], at[1], 0.25), self.M("brass"), 24, coll=g)
        return g

    def banquette(self, a, b, depth=0.6, seat_h=0.46, back_h=1.05, panel_h=2.2, side=1, seat_mat="boucle", name="banquette"):
        """Fixed bench along a wall from a to b: plinth, seat, channel-tufted back, slatted wall panel above."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, side)
        g = self._collection("Seating")
        cx, cy = (a[0] + b[0]) / 2 + nx * depth / 2, (a[1] + b[1]) / 2 + ny * depth / 2
        self.box(f"{name}_plinth", (L, depth - 0.1, 0.12), (cx, cy, 0.06), ang, self.M("black"), g)
        self.box(f"{name}_seat", (L, depth, seat_h - 0.12), (cx, cy, 0.12 + (seat_h - 0.12) / 2), ang, self.M(seat_mat), g)
        bx, by = (a[0] + b[0]) / 2 + nx * 0.09, (a[1] + b[1]) / 2 + ny * 0.09
        n = max(1, int(L / 0.45))
        for i in range(n):
            u = L * (i + 0.5) / n
            self.box(f"{name}_tuft", (L / n - 0.03, 0.16, back_h - seat_h), (a[0] + ux * u + nx * 0.09, a[1] + uy * u + ny * 0.09, seat_h + (back_h - seat_h) / 2), ang, self.M(seat_mat), g)
        px, py = (a[0] + b[0]) / 2 + nx * 0.025, (a[1] + b[1]) / 2 + ny * 0.025
        self.box(f"{name}_panel", (L, 0.04, panel_h - back_h), (px, py, back_h + (panel_h - back_h) / 2), ang, self.M("walnut_slat"), g)
        self.box(f"{name}_cove", (L - 0.1, 0.02, 0.01), (px + nx * 0.03, py + ny * 0.03, panel_h - 0.02), ang, self.M("led"), g)
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
                for j in range(4):
                    self.sphere(f"{name}_leaf", 0.045, (x + self.rng.uniform(-0.04, 0.04), y + self.rng.uniform(-0.04, 0.04), z + 0.13 + self.rng.uniform(0, 0.05)), self.M("greens"), (1.3, 1.0, 0.7), coll=g)
                u += 0.18
            k += 1
        return g

    def hanging_plants(self, a, b, z, n=3, name="hang"):
        """Trailing plants hung from the ceiling along a→b."""
        g = self._collection("Props")
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        for i in range(n):
            u = L * (i + 0.5) / n
            x, y = a[0] + ux * u, a[1] + uy * u
            self.cyl(f"{name}_cord", 0.003, 0.6, (x, y, z - 0.6), self.M("black"), 6, coll=g)
            self.cyl(f"{name}_pot", 0.1, 0.12, (x, y, z - 0.72), self.M("pot"), 16, r_top=0.12, coll=g)
            for j in range(5):
                self.sphere(f"{name}_leaf", 0.07, (x + self.rng.uniform(-0.1, 0.1), y + self.rng.uniform(-0.1, 0.1), z - 0.62 - self.rng.uniform(0, 0.25)), self.M("greens"), (1.2, 1.0, 0.6), coll=g)
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

    def planter_hedge(self, a, b, w=0.4, h=0.45, hedge_h=0.5, name="hedge"):
        """Street-edge planter run with a clipped hedge (one mesh for the hedge)."""
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        g = self._collection("Props")
        self.box(f"{name}_planter", (L, w, h), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, h / 2), ang, self.M("pot"), g)
        bm = bmesh.new()
        n = max(2, int(L / 0.35))
        for i in range(n):
            u = L * (i + 0.5) / n
            res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            bmesh.ops.scale(bm, vec=(0.24, w * 0.45, hedge_h * 0.5), verts=res["verts"])
            bmesh.ops.translate(bm, verts=res["verts"], vec=(a[0] + ux * u, a[1] + uy * u, h + hedge_h * 0.35))
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        o = bpy.data.objects.new(name, mesh)
        o.data.materials.append(self.M("greens"))
        g.objects.link(o)
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
    def pendant(self, at, z_ceiling, drop=0.9, r=0.16, style="opal", power=45.0, name="pendant"):
        """Pendant lamp hung from the ceiling at `at`; style opal (glowing dome) or brass (metal shade)."""
        g = self._collection("Lighting")
        z = z_ceiling - drop
        self.cyl(f"{name}_rose", 0.05, 0.02, (at[0], at[1], z_ceiling - 0.02), self.M("brass"), 16, coll=g)
        self.cyl(f"{name}_cord", 0.004, drop - 0.1, (at[0], at[1], z + 0.08), self.M("black"), 6, coll=g)
        if style == "opal":
            self.sphere(f"{name}_dome", r, (at[0], at[1], z), self.M("opal"), (1, 1, 0.75), coll=g)
        else:
            self.cyl(f"{name}_shade", r * 0.5, 0.22, (at[0], at[1], z - 0.1), self.M("brass"), 24, r_top=r, coll=g)
            self.cyl(f"{name}_bulb", 0.03, 0.05, (at[0], at[1], z - 0.12), self.M("opal"), 12, coll=g)
        d = bpy.data.lights.new(name, "POINT")
        d.energy = power; d.color = kelvin_to_rgb(2700); d.shadow_soft_size = 0.12
        o = bpy.data.objects.new(name, d)
        o.location = (at[0], at[1], z - 0.05)
        g.objects.link(o)
        return g

    def led_strip(self, a, b, z, mat="led", name="led"):
        (ux, uy), (nx, ny), L, ang = self._along(a, b, 1)
        return self.box(name, (L, 0.02, 0.01), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), ang, self.M(mat), self._collection("Lighting"))

    def plant(self, at, h=1.1, pot_r=0.22, name="plant"):
        g = self._collection("Props")
        self.cyl(f"{name}_pot", pot_r * 0.85, h * 0.32, at + (0,) if len(at) == 2 else at, self.M("pot"), 20, r_top=pot_r, coll=g)
        z0 = (at[2] if len(at) > 2 else 0) + h * 0.32
        for k in range(12):
            a = self.rng.random() * 6.28; d = self.rng.random() * pot_r * 0.9
            self.sphere(f"{name}_leaf", h * 0.09 + self.rng.random() * h * 0.07, (at[0] + math.cos(a) * d, at[1] + math.sin(a) * d, z0 + h * 0.25 + self.rng.random() * h * 0.4), self.M("greens"), (1.3, 1.0, 0.6), coll=g)
        return g

    def olive_tree(self, at, h=2.6, name="olive"):
        g = self._collection("Props")
        self.cyl(f"{name}_pot", 0.32, 0.5, (at[0], at[1], 0), self.M("pot"), 24, r_top=0.36, coll=g)
        self.cyl(f"{name}_trunk", 0.06, h * 0.45, (at[0], at[1], 0.5), self.M("bark"), 10, r_top=0.04, coll=g)
        for k in range(8):
            a = self.rng.random() * 6.28; d = self.rng.random() * h * 0.22
            self.sphere(f"{name}_canopy", h * 0.14 + self.rng.random() * h * 0.08, (at[0] + math.cos(a) * d, at[1] + math.sin(a) * d, 0.5 + h * 0.55 + self.rng.random() * h * 0.25), self.M("olive_green"), coll=g)
        return g

    def umbrella(self, at, size=3.2, h=2.5, name="umbrella"):
        g = self._collection("Props")
        self.cyl(f"{name}_base", 0.3, 0.06, (at[0], at[1], 0), self.M("charcoal"), 20, coll=g)
        self.cyl(f"{name}_pole", 0.03, h - 0.2, (at[0], at[1], 0.06), self.M("black"), 12, coll=g)
        self.cyl(f"{name}_canopy", size / 2, 0.35, (at[0], at[1], h - 0.2), self.M("canvas"), 8, r_top=0.03, coll=g)
        self.box(f"{name}_valance", (size * 0.92, size * 0.92, 0.12), (at[0], at[1], h - 0.24), 22.5, self.M("canvas"), g)
        return g

    def sign(self, body, at, rot=0.0, z=2.9, size=0.32, mat="walnut", name="sign"):
        """Wordmark on a wall: `at` on the wall face, `rot` = wall direction (text reads left→right along it)."""
        r = math.radians(rot)
        return self.text(name, body, (at[0] - math.sin(r) * 0.02, at[1] + math.cos(r) * 0.02, z), rot, size, self.M(mat), extrude=0.015)

    def art(self, at, rot=0.0, z=1.6, w=0.7, h=0.5, name="art"):
        g = self._collection("Props")
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        self.box(f"{name}_frame", (w, 0.03, h), (at[0] + nx * 0.015, at[1] + ny * 0.015, z), rot, self.M("black"), g)
        self.box(f"{name}_print", (w - 0.08, 0.01, h - 0.08), (at[0] + nx * 0.035, at[1] + ny * 0.035, z), rot, self.M("cream"), g)
        return g

    def lights(self, sun=True, sun_elev=38, sun_az=140, sun_power=3.0, fills=True, sky=True):
        """World (Nishita sky) + sun + a soft ceiling fill in every enclosed room with no lamp."""
        S = self.scene
        world = bpy.data.worlds.get("CafeWorld") or bpy.data.worlds.new("CafeWorld")
        self.sc.world = world
        world.use_nodes = True
        nt = world.node_tree
        bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
        if sky:
            try:
                skyn = nt.nodes.new("ShaderNodeTexSky")
                skyn.sky_type = "NISHITA"
                skyn.sun_elevation = math.radians(sun_elev)
                skyn.sun_rotation = math.radians(sun_az)
                nt.links.new(skyn.outputs["Color"], bg.inputs["Color"])
                bg.inputs["Strength"].default_value = 1.0
            except Exception:
                bg.inputs["Color"].default_value = hex_to_linear("#cfdbe6")
        g = self._collection("Lighting")
        if sun:
            d = bpy.data.lights.new("Sun", "SUN")
            d.energy = sun_power; d.angle = math.radians(1.5)
            o = bpy.data.objects.new("Sun", d)
            o.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az))
            g.objects.link(o)
        if fills:
            lamp_pts = [tuple(o.location[:2]) for o in g.objects if o.type == "LIGHT" and o.data.type in ("POINT", "SPOT")]
            for room in S["rooms"]:
                ch = room.get("ceilingHeight") or 0
                if ch <= 0:
                    continue
                poly = room["polygon"]
                has_lamp = any(point_in_poly(poly, x, y) for x, y in lamp_pts)
                cx, cy = _centroid(poly)
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                w = max(xs) - min(xs); dd = max(ys) - min(ys)
                d = bpy.data.lights.new(f"fill_{room['id']}", "AREA")
                d.shape = "RECTANGLE"; d.size = min(max(w * 0.5, 0.4), 2.2); d.size_y = min(max(dd * 0.5, 0.4), 2.2)
                d.energy = min(max(w * dd * (8.0 if has_lamp else 18.0), 45.0), 280.0); d.color = kelvin_to_rgb(3000)
                o = bpy.data.objects.new(f"fill_{room['id']}", d)
                o.location = (cx, cy, ch - 0.08)
                g.objects.link(o)
        return g

    # ---------------- cameras & render ----------------
    def camera(self, at, look_at, eye=1.55, fov=68, name="Camera", label=None, look_z=1.3):
        """Eye-level camera at plan point `at` looking at plan point `look_at` at height look_z."""
        cam = bpy.data.cameras.new(name)
        cam.lens_unit = "FOV"
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

    def finish(self, engine="CYCLES", samples=96, res=(1600, 900)):
        """Render settings. Live Blender keeps EEVEE for interaction; headless renders use Cycles."""
        sc = self.sc
        try:
            sc.render.engine = engine
        except TypeError:
            pass
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        if engine == "CYCLES":
            sc.cycles.samples = samples
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
        except Exception:
            pass
        for o in bpy.context.selected_objects:
            o.select_set(False)
        return sc

    def render_stills(self, out_dir, samples=96, res=(1600, 900)):
        """Render every camera created with camera() to out_dir; prints STILL_TOTAL/STILL_DONE markers."""
        os.makedirs(out_dir, exist_ok=True)
        self.finish("CYCLES", samples, res)
        sc = self.sc
        print(f"STILL_TOTAL {len(self.cameras)}", flush=True)
        out = []
        for i, (cam, label) in enumerate(self.cameras):
            sc.camera = cam
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

    def export_glb(self, path, lights=True):
        """Web-weight GLB of the whole café (WebP textures, lights included). Blender (x, y, z) exports
        to glTF (x, z, -y), which is exactly the web viewer's frame (worldX = planX, worldZ = -planY)."""
        for o in bpy.data.objects:
            o.select_set(False)
        kwargs = dict(filepath=path, export_format="GLB", export_apply=True, export_lights=lights, export_cameras=False, export_yup=True)
        for extra in ({"export_image_format": "WEBP", "export_image_quality": 80}, {"export_image_format": "JPEG", "export_image_quality": 80}, {}):
            try:
                bpy.ops.export_scene.gltf(**kwargs, **extra)
                break
            except TypeError:
                continue
        return path
