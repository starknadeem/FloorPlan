"""
hardsurface.py — small modelling toolkit for detailed, real-looking props (no operators, runs headless).

All parts of a model accumulate in ONE bmesh with per-face material indices, so a model exports as a
single light object. Edges sharper than ~32° stay crisp; everything else shades smooth, so bevelled
boxes catch a real edge highlight and lathed/swept parts read round.

    b = Model("fridge")
    b.box((0.6, 0.6, 1.9), (0, 0, 0.95), "steel", bevel=0.006)
    b.lathe([(0, 0), (0.03, 0), (0.03, 0.2), (0, 0.2)], (0, 0, 1.9), "glass")
    b.tube([(0, 0, 0), (0, -0.1, 0.1)], 0.01, "chrome")
    obj = b.build()
"""
import math
import os

import bpy  # type: ignore
import bmesh  # type: ignore
from mathutils import Euler, Matrix, Vector  # type: ignore

TEX = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "textures"))
_MATS = {}


def _srgb(h):
    h = h.lstrip("#")
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(int(h[0:2], 16)), lin(int(h[2:4], 16)), lin(int(h[4:6], 16)), 1.0)


def plain(name, color="#ffffff", rough=0.5, metal=0.0, coat=0.0, emit=None, emit_power=0.0, glass=False, alpha=1.0):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = _srgb(color)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.08
    if emit:
        p.inputs["Emission Color"].default_value = _srgb(emit)
        p.inputs["Emission Strength"].default_value = emit_power
    if glass:
        p.inputs["Transmission Weight"].default_value = 1.0
        p.inputs["IOR"].default_value = 1.45
    if alpha < 1.0:
        p.inputs["Alpha"].default_value = alpha
    _MATS[name] = m
    return m


def pbr(name, folder, tint=None, metal=0.0, tiles_per_m=None, normal=0.6, rough_only=False, sheen=0.0):
    """Image-based material; UVs are in metres, so tiles_per_m defaults to the texture's real size."""
    if name in _MATS:
        return _MATS[name]
    import json
    base = os.path.join(TEX, folder)
    if tiles_per_m is None:
        try:
            tiles_per_m = 1.0 / json.load(open(os.path.join(base, "meta.json")))["size_m"][0]
        except Exception:
            tiles_per_m = 1.0
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Metallic"].default_value = metal
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
    uv = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (tiles_per_m, tiles_per_m, 1.0)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])

    def img(fn, noncolor=True):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(base, fn), check_existing=True)
        if noncolor:
            t.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t
    if rough_only:
        p.inputs["Base Color"].default_value = _srgb(tint or "#c6c8cb")
    else:
        c = img("color.jpg", False)
        if tint:
            c.image = _tinted(c.image, tint)
        nt.links.new(c.outputs["Color"], p.inputs["Base Color"])
    r = img("rough.jpg")
    s = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(r.outputs["Color"], s.inputs["Color"])
    nt.links.new(s.outputs["Green"], p.inputs["Roughness"])
    n = img("normal.jpg")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    _MATS[name] = m
    return m


def _tinted(img, tint):
    """Recolour keeping variation: mean of the image maps exactly onto `tint` (works on dark or light sources)."""
    import numpy as np
    t = img.copy()
    t.name = f"{img.name}_{tint.strip('#')}"
    px = np.empty(len(t.pixels), dtype=np.float32)
    t.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    h = tint.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)
    lum = px[:, :3].mean(axis=1, keepdims=True)
    px[:, :3] = np.clip(c * (lum / max(float(lum.mean()), 1e-3)), 0.0, 1.0)
    t.pixels.foreach_set(px.ravel())
    t.update()
    t.pack()
    return t


class Model:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        # bmesh operators (bevel!) clobber the TAG flag, so "already committed" lives in layers
        self._vdone = self.bm.verts.layers.int.new("done")
        self._fdone = self.bm.faces.layers.int.new("done")

    # ---- internals ----
    def _mi(self, mat):
        m = _MATS[mat] if isinstance(mat, str) else mat
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _commit(self, mat, M=None):
        """Everything not yet tagged belongs to the primitive just created."""
        i = self._mi(mat)
        vs = [v for v in self.bm.verts if not v[self._vdone]]
        if M is not None:
            bmesh.ops.transform(self.bm, matrix=M, verts=vs)
        for f in self.bm.faces:
            if not f[self._fdone]:
                f.material_index = i
                f[self._fdone] = 1
        for v in vs:
            v[self._vdone] = 1

    @staticmethod
    def _rot(rot):
        return Euler(tuple(math.radians(a) for a in rot)).to_matrix().to_4x4()

    # ---- primitives ----
    def box(self, size, at, mat, bevel=0.003, seg=2, rot=(0, 0, 0)):
        """Rounded box of size (x, y, z) centred at `at`."""
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        bmesh.ops.scale(self.bm, vec=size, verts=res["verts"])
        if bevel > 0 and min(size) > bevel * 2.2:
            edges = list({e for v in res["verts"] for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
        self._commit(mat, Matrix.Translation(at) @ self._rot(rot))

    def cyl(self, r, h, at, mat, rot=(0, 0, 0), seg=32, r2=None, bevel=0.0):
        """Cylinder/cone; `at` is the centre of the base before rotation (axis +Z)."""
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
        bmesh.ops.translate(self.bm, vec=(0, 0, h / 2), verts=res["verts"])
        if bevel > 0:
            caps = [e for e in {e for v in res["verts"] for e in v.link_edges} if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6]
            bmesh.ops.bevel(self.bm, geom=caps, offset=bevel, offset_type="OFFSET", segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
        self._commit(mat, Matrix.Translation(at) @ self._rot(rot))

    def lathe(self, profile, at, mat, seg=32, rot=(0, 0, 0)):
        """Revolve a (radius, z) profile about +Z. Radius 0 points close the ends."""
        rings = []
        for (r, z) in profile:
            if r <= 1e-6:
                rings.append([self.bm.verts.new((0, 0, z))])
            else:
                rings.append([self.bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z)) for k in range(seg)])
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for k in range(seg):
                if len(a) == 1:
                    self.bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
                elif len(b) == 1:
                    self.bm.faces.new((a[k], b[0], a[(k + 1) % seg]))
                else:
                    self.bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
        self._commit(mat, Matrix.Translation(at) @ self._rot(rot))

    def tube(self, pts, r, mat, seg=10, samples=8, closed=False, caps=True):
        """Round tube swept through points with Catmull-Rom smoothing (bent steel, faucets, frames)."""
        P = [Vector(p) for p in pts]
        path = []
        n = len(P)
        if n == 2 or samples <= 1:
            path = P
        else:
            rng = range(n) if closed else range(n - 1)
            for i in rng:
                p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
                p1, p2 = P[i], P[(i + 1) % n]
                p3 = P[(i + 2) % n] if (closed or i + 2 < n) else p2
                for s in range(samples):
                    t = s / samples
                    path.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
            if not closed:
                path.append(P[-1])
        rings = []
        up = Vector((0.13, 0.27, 0.95)).normalized()
        L = len(path)
        for i, c in enumerate(path):
            if closed:
                d = (path[(i + 1) % L] - path[(i - 1) % L]).normalized()
            else:
                d = (path[min(i + 1, L - 1)] - path[max(i - 1, 0)]).normalized()
            x = up.cross(d)
            if x.length < 1e-4:
                x = Vector((1, 0, 0)).cross(d)
            x.normalize()
            y = d.cross(x).normalized()
            up = y
            rings.append([self.bm.verts.new(c + (x * math.cos(2 * math.pi * k / seg) + y * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)])
        last = L if closed else L - 1
        for i in range(last):
            a, b = rings[i], rings[(i + 1) % L]
            for k in range(seg):
                self.bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
        if caps and not closed:
            self.bm.faces.new(list(reversed(rings[0])))
            self.bm.faces.new(rings[-1])
        self._commit(mat)

    def surface(self, fn, nu, nv, mat, thick=0.0, wrap_u=False):
        """Parametric surface fn(u, v) -> (x, y, z) for u, v in 0..1; optional thickness (shells, cushions, drapes)."""
        grid = [[self.bm.verts.new(fn(i / (nu if wrap_u else nu - 1), j / (nv - 1))) for j in range(nv)] for i in range(nu)]
        rows = nu if wrap_u else nu - 1
        for i in range(rows):
            a, b = grid[i], grid[(i + 1) % nu]
            for j in range(nv - 1):
                self.bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
        if thick:
            self.bm.normal_update()
            faces = [f for f in self.bm.faces if not f[self._fdone]]
            r = bmesh.ops.extrude_face_region(self.bm, geom=faces)
            nv_ = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
            for v in nv_:
                v.co -= v.normal * thick if v.normal.length > 0.5 else Vector((0, 0, thick))
            bmesh.ops.recalc_face_normals(self.bm, faces=[f for f in self.bm.faces if not f[self._fdone]])
        self._commit(mat)

    def slats(self, n, size, start, step, mat, bevel=0.0):
        """n identical boxes in a row: vents, grilles, flutes."""
        for i in range(n):
            self.box(size, (start[0] + step[0] * i, start[1] + step[1] * i, start[2] + step[2] * i), mat, bevel=bevel)

    # ---- output ----
    def build(self, smooth_angle=32.0, collection=None, uv_scale=1.0):
        bm = self.bm
        bm.normal_update()
        for f in bm.faces:
            f.smooth = True
        lim = math.radians(smooth_angle)
        for e in bm.edges:
            if len(e.link_faces) == 2:
                e.smooth = e.calc_face_angle(0.0) < lim
            else:
                e.smooth = False
        uv = bm.loops.layers.uv.verify()
        for f in bm.faces:
            n = f.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            for l in f.loops:
                c = l.vert.co
                if az >= ax and az >= ay:
                    l[uv].uv = (c.x * uv_scale, c.y * uv_scale)
                elif ax >= ay:
                    l[uv].uv = (c.y * uv_scale, c.z * uv_scale)
                else:
                    l[uv].uv = (c.x * uv_scale, c.z * uv_scale)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        o = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(o)
        return o
