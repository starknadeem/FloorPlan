"""
curate_asset.py — normalize a freshly-imported model into a mid-poly, web-weight library GLB.

Run inside LIVE Blender (via the MCP addon). Workflow per asset:

    exec(open("/.../webapp/blender/curate_asset.py").read())   # load helpers once
    clean_workspace()                                           # empty the scene
    # ...MCP import_asset(source=polyhaven, id=..., target_size=...)...
    print(curate("chair/dining_leather.glb", "chair", "polyhaven:dining_chair_02",
                 forward_deg=0, target_tris=6500, style_tags=["modern"]))

`curate` joins the imported meshes, applies transforms, centres them in XY, drops the base to z=0,
optionally rotates so the piece faces -Y (cafe_kit's rot=0 convention), decimates to ~target_tris,
resizes textures to <=tex_size, and exports a WebP-compressed GLB into assets/models/<out_rel>.
It prints a manifest-ready JSON entry (paste into assets/manifest.json). The whole-café render
imports these GLBs headlessly via Kit.place(); no MCP is needed at render time.
"""
import bpy, bmesh, os, json, math
from mathutils import Vector, Matrix

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:   # exec'd over the MCP socket, no __file__
    _HERE = "/home/nadeem-israr/Desktop/plan/webapp/blender"
MODELS_DIR = os.path.join(_HERE, "assets", "models")
_KEEP = {"Light", "Camera"}


def clean_workspace():
    """Remove every mesh/curve/empty object (keep Light + Camera) so the next import starts clean."""
    for o in list(bpy.data.objects):
        if o.name not in _KEEP and o.type != "CAMERA" and o.type != "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(blk):
            if d.users == 0:
                blk.remove(d)
    return "clean"


def _simplify_base_color(obj):
    """glTF exports only image textures, not procedural node graphs. Some Poly Haven models feed the
    Principled Base Color through MIX/mask nodes (e.g. cakes) — that base colour then exports as None
    and the mesh renders magenta. Rewire Base Color straight to the diffuse/albedo image."""
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        bc = bsdf.inputs["Base Color"]
        if bc.links and bc.links[0].from_node.type == "TEX_IMAGE" and bc.links[0].from_node.image:
            continue  # already a direct image
        cand = None
        for n in nt.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                nm = n.image.name.lower()
                if any(k in nm for k in ("diff", "albedo", "basecolor", "base_color", "_col", "color")):
                    cand = n
                    break
        if cand is None:  # else any colour-space (not Non-Color) image
            for n in nt.nodes:
                if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name != "Non-Color":
                    cand = n
                    break
        if cand:
            for l in list(bc.links):
                nt.links.remove(l)
            nt.links.new(cand.outputs["Color"], bc)


def _world_bbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return mn, mx


def curate(out_rel, category, source_id, forward_deg=0, target_tris=6500,
           tex_size=1024, style_tags=None, fit="real", license="CC0"):
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name not in _KEEP]
    if not meshes:
        return "ERROR: no imported mesh objects in the scene"

    # join into one object
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = os.path.splitext(os.path.basename(out_rel))[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # face -Y: rotate the mesh by forward_deg about Z, then re-apply
    if forward_deg:
        obj.rotation_euler = (0, 0, math.radians(forward_deg))
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # centre XY on origin, drop base to z=0
    mn, mx = _world_bbox(obj)
    obj.location.x -= (mn.x + mx.x) / 2
    obj.location.y -= (mn.y + mx.y) / 2
    obj.location.z -= mn.z
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    tris_before = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris_before > target_tris:
        m = obj.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = target_tris / float(tris_before)
        bpy.ops.object.modifier_apply(modifier="dec")
    tris_after = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    bpy.ops.object.shade_smooth()

    # make Base Color a direct image so it survives glTF export (no procedural MIX/mask graphs)
    _simplify_base_color(obj)

    # shrink textures
    imgs = set()
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    imgs.add(n.image)
    for img in imgs:
        w, h = img.size
        if max(w, h) > tex_size:
            s = tex_size / max(w, h)
            img.scale(int(w * s), int(h * s))

    out_path = os.path.join(MODELS_DIR, out_rel)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True,
                              export_image_format="WEBP", export_image_quality=80)

    mn, mx = _world_bbox(obj)
    s = mx - mn
    entry = {
        "variant": obj.name, "file": out_rel,
        "footprint": [round(s.x, 3), round(s.y, 3)], "height": round(s.z, 3),
        "forward_deg": 0, "fit": fit,
        "style_tags": style_tags or ["modern"],
        "tris": tris_after, "source": source_id, "license": license,
        "_kb": round(os.path.getsize(out_path) / 1024),
    }
    return json.dumps(entry, indent=2)
