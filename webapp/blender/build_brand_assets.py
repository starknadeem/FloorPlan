"""build_brand_assets.py — Coffee Berry assets the client did not supply as models, built from what they did supply.

    blender -b --python blender/build_brand_assets.py

1. cb_stool_balfour: the outdoor Balfour bar stool (furniture schedule: 17 on the terrace). The client sent the Balfour
   CHAIR model and a photo of the stool (clientsDocs/7. Photo references/TABLES CHAIRS/WEB-COMPRESSED_BALFOUR-STOOL.png):
   same slatted terracotta shell, raised to bar height on four splayed tube legs with a square footrest. We cut the
   shell off the chair model and rebuild the base to the photo.
2. cb_logo + cb_logo_halo: the real Coffee Berry logo (tree over the wordmark, webapp/public/brand/coffee-berry-logo.png)
   as solid 12 mm built-up lettering, plus a flat warm emissive copy for the back-lit halo the shops' signs have.
   Built from the PNG's alpha at ~1.5 mm per pixel for a 1 m wide sign: no alpha cut-outs, so no Cycles transparency
   artefacts. Model frame: 1 m wide along +X, front faces -Y, back on y=0 (the wall).

Writes render + web twins into assets/models/client and assets/models_web/client, copies the web twins to
public/models/custom, and upserts the manifest entries ("stool_outdoor", "logo", "logo_halo").
"""
import bpy, bmesh, json, math, os, shutil
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
PUBLIC = os.path.join(HERE, "..", "public")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export(path, objs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True)


def plain(name, rgb, rough=0.55, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*rgb, 1.0)
    p.inputs["Roughness"].default_value = rough
    if emit:
        p.inputs["Emission Color"].default_value = (*rgb, 1.0)
        p.inputs["Emission Strength"].default_value = emit
    return m


def tube(bm, a, b, r, seg=12):
    """Closed cylinder between points a and b into bm."""
    from mathutils import Vector, Matrix
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = d.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    M = Matrix.Translation((a + b) / 2) @ rot
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length, matrix=M)


def stats(objs):
    vs = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    mn = [min(v[i] for v in vs) for i in range(3)]
    mx = [max(v[i] for v in vs) for i in range(3)]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    return mn, mx, tris


# ---------------------------------------------------------------- Balfour stool
def build_stool():
    reset()
    bpy.ops.import_scene.gltf(filepath=os.path.join(ASSETS, "models", "client", "cb_chair_balfour.glb"))
    chair = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    bpy.context.view_layer.objects.active = chair
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # leg colour: the frame's terracotta sampled from the client's stool photo (median sRGB 139,68,18 → linear).
    # (The baked texture can't be averaged: its unused UV padding is black.)
    col = (0.258, 0.058, 0.006)
    # keep the shell (everything above the leg tops), lift it to bar height
    CUT, LIFT = 0.40, 0.33
    bm = bmesh.new()
    bm.from_mesh(chair.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < CUT], context="VERTS")
    for v in bm.verts:
        v.co.z += LIFT
    bm.to_mesh(chair.data)
    bm.free()
    chair.name = "cb_stool_balfour_shell"
    # base to the photo: 4 splayed Ø22 tube legs, square footrest ring at 0.30 m
    bm = bmesh.new()
    top_z, R = CUT + LIFT + 0.03, 0.011
    tops = [(-0.20, -0.20), (0.20, -0.20), (0.20, 0.13), (-0.20, 0.13)]
    feet = [(-0.25, -0.28), (0.25, -0.28), (0.25, 0.21), (-0.25, 0.21)]
    for (tx, ty), (fx, fy) in zip(tops, feet):
        tube(bm, (fx, fy, 0.0), (tx, ty, top_z), R)
    fr = 0.30 / top_z
    ring = [(f[0] + (t[0] - f[0]) * fr, f[1] + (t[1] - f[1]) * fr, 0.30) for t, f in zip(tops, feet)]
    for i in range(4):
        tube(bm, ring[i], ring[(i + 1) % 4], 0.009)
    # seat-support frame under the shell
    for i in range(4):
        a, b = tops[i], tops[(i + 1) % 4]
        tube(bm, (a[0], a[1], top_z), (b[0], b[1], top_z), 0.009)
    me = bpy.data.meshes.new("cb_stool_balfour_base")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    base = bpy.data.objects.new("cb_stool_balfour_base", me)
    base.data.materials.append(plain("cb_stool_balfour_frame", col, 0.5))
    bpy.context.scene.collection.objects.link(base)
    objs = [chair, base]
    export(os.path.join(ASSETS, "models", "client", "cb_stool_balfour.glb"), objs)
    mn, mx, tris = stats(objs)
    # web twin: decimate the shell
    dec = chair.modifiers.new("dec", "DECIMATE")
    dec.ratio = 0.25
    bpy.context.view_layer.objects.active = chair
    bpy.ops.object.modifier_apply(modifier="dec")
    export(os.path.join(ASSETS, "models_web", "client", "cb_stool_balfour.glb"), objs)
    shutil.copy(os.path.join(ASSETS, "models_web", "client", "cb_stool_balfour.glb"), os.path.join(PUBLIC, "models", "custom", "stoolOutdoor.glb"))
    print("STOOL", [round(x, 3) for x in mn], [round(x, 3) for x in mx], tris, "leg colour", [round(c, 3) for c in col])
    return dict(variant="cb_stool_balfour", file="client/cb_stool_balfour.glb", footprint=[round(mx[0] - mn[0], 3), round(mx[1] - mn[1], 3)],
                height=round(mx[2] - mn[2], 3), forward_deg=0, fit="real", brand="coffeeberry", style_tags=["any"], tris=tris,
                source="derived: client cb_chair_balfour shell + base rebuilt to WEB-COMPRESSED_BALFOUR-STOOL.png",
                license="client-owned")


# ---------------------------------------------------------------- logo
def logo_mesh(alpha, step, width, name):
    """Filled pixels of the alpha mask → one flat mesh in the XZ plane (1 m wide along +X, reading left→right from -Y)."""
    a = alpha[::step, ::step] > 0.5
    H, W = a.shape
    s = width / W
    bm = bmesh.new()
    vid = {}
    def V(i, j):   # grid corner (row i from top, col j)
        k = (i, j)
        if k not in vid:
            vid[k] = bm.verts.new(((j - W / 2) * s, 0.0, (H - i) * s))
        return vid[k]
    for i in range(H):
        row = a[i]
        for j in np.nonzero(row)[0]:
            # front faces -Y: counter-clockwise seen from -Y
            bm.faces.new((V(i + 1, j), V(i + 1, j + 1), V(i, j + 1), V(i, j)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=s * 0.01)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=bm.verts, edges=bm.edges)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def build_logo():
    reset()
    img = bpy.data.images.load(os.path.join(PUBLIC, "brand", "coffee-berry-logo.png"))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    alpha = px.reshape(h, w, 4)[::-1, :, 3]   # Blender rows are bottom-up → top-down
    out = {}
    for tier, step in (("models", 3), ("models_web", 6)):
        reset()
        # letters: 12 mm deep, standing 15 mm off the wall (back at y=-0.015, front at y=-0.027)
        let = logo_mesh(alpha, step, 1.0, "cb_logo")
        let.location.y = -0.015
        so = let.modifiers.new("solid", "SOLIDIFY")
        so.thickness = 0.012
        so.offset = -1.0          # grow towards -Y (front)
        so.use_even_offset = True
        let.data.materials.append(plain("cb_logo_black", (0.012, 0.010, 0.009), 0.4))
        export(os.path.join(ASSETS, tier, "client", "cb_logo.glb"), [let])
        mn, mx, tris = stats([let])
        out["logo"] = dict(variant="cb_logo", file="client/cb_logo.glb", footprint=[round(mx[0] - mn[0], 3), round(mx[1] - mn[1], 3)],
                           height=round(mx[2] - mn[2], 3), forward_deg=0, fit="width", brand="coffeeberry", style_tags=["any"], tris=tris,
                           source="webapp/public/brand/coffee-berry-logo.png (traced)", license="client-owned")
        print("LOGO", tier, tris, [round(x, 3) for x in mn], [round(x, 3) for x in mx])
        # halo: the same artwork 6 % larger, flat on the wall, warm 3000 K glow (back-lit letter effect)
        reset()
        halo = logo_mesh(alpha, step * 2, 1.06, "cb_logo_halo")
        halo.location = (0.0, -0.002, -0.06 * (h / w) / 2)
        halo.data.materials.append(plain("cb_logo_glow", (1.0, 0.55, 0.22), 0.8, emit=8.0))
        export(os.path.join(ASSETS, tier, "client", "cb_logo_halo.glb"), [halo])
        mn, mx, tris = stats([halo])
        out["logo_halo"] = dict(variant="cb_logo_halo", file="client/cb_logo_halo.glb", footprint=[round(mx[0] - mn[0], 3), 0.002],
                                height=round(mx[2] - mn[2], 3), forward_deg=0, fit="width", brand="coffeeberry", style_tags=["any"],
                                tris=tris, source="webapp/public/brand/coffee-berry-logo.png (traced)", license="client-owned")
    return out


def main():
    entries = {"stool_outdoor": build_stool()}
    for cat, e in build_logo().items():
        entries[cat] = e
    mpath = os.path.join(ASSETS, "manifest.json")
    m = json.load(open(mpath))
    for cat, e in entries.items():
        e["_kb"] = os.path.getsize(os.path.join(ASSETS, "models", e["file"])) // 1024
        m[cat] = [e]
    with open(mpath, "w") as f:
        json.dump(m, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("BRAND_ASSETS_OK", sorted(entries))


main()
