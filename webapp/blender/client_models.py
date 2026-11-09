"""client_models.py — turn the client's own (Coffee Berry) AI-generated GLBs into library assets.

The client's raw models (3DModels/*.glb) are ~500k tris with a 4K texture each and are normalised to a
~1 m bounding box, NOT real size. This script, per model:
  * scales it to its real-world size (uniform, or per-axis for tables that the kit stretches anyway),
  * makes it face -Y (cafe_kit rot=0 convention), centres XY, base at z=0,
  * decimates a render-weight and a web-weight copy, gives each fresh UVs and BAKES the original's colour onto it
    (decimating the AI meshes directly tears their texture seams), exports WebP GLBs to
      assets/models/client/<name>.glb      (Cycles stills)
      assets/models_web/client/<name>.glb  (walkable web GLB twin)
  * merges a manifest entry with "brand": "coffeeberry" — Kit.pick_asset() always prefers brand assets,
    because the client re-uses the same furniture/equipment in every shop.

    blender --background --python blender/client_models.py -- [--src ../3DModels] [--only name1,name2]
"""
import bpy, os, sys, json, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = a[a.index("--src") + 1] if "--src" in a else os.path.join(ROOT, "3DModels")
ONLY = set(a[a.index("--only") + 1].split(",")) if "--only" in a else None
WEB_ONLY = "--web-only" in a   # rebuild only assets/models_web twins, keep render models + manifest

# file (after renaming) -> spec.  size = target (w, d, h) metres; None axis = keep proportion with h.
# cat = manifest category used by cafe_kit; tris = (render, web); tex = (render, web) px.
SPECS = {
    # --- furniture (Coffee Berry standard set, see clientsDocs/7. Photo references/TABLES CHAIRS)
    "cb_chair_pasadena":      dict(cat="chair",        size=(None, None, 0.80), tris=(30000, 3000), tex=(2048, 1024), fit="real"),
    "cb_semistool_pasadena":  dict(cat="stool",        size=(None, None, 0.95), tris=(30000, 3000), tex=(2048, 1024), fit="real"),
    "cb_chair_balfour":       dict(cat="chair_outdoor", size=(None, None, 0.78), tris=(30000, 3000), tex=(2048, 1024), fit="real"),
    "cb_table_round":         dict(cat="table_round",  size=(0.80, 0.80, 0.75), tris=(10000, 2000), tex=(2048, 1024), fit="stretch"),
    "cb_table_semistand":     dict(cat="table_square", size=(0.60, 0.60, 0.92), tris=(10000, 2000), tex=(2048, 1024), fit="stretch"),
    "cb_table_stand":         dict(cat="table_high",   size=(1.60, 0.60, 1.05), tris=(10000, 2000), tex=(2048, 1024), fit="stretch"),
    # --- equipment
    "cb_espresso_lacimbali_3g": dict(cat="espresso",   size=(1.03, None, None), tris=(60000, 10000), tex=(2048, 1024), fit="real"),
    "cb_grinder_fiorenzato":    dict(cat="grinder",    size=(None, None, 0.62), tris=(30000, 5000), tex=(2048, 1024), fit="real"),
    # --- cups & merchandise (retail shelves / counter styling)
    "cb_cup_paper":           dict(cat="cup",          size=(None, None, 0.12), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_tumbler_black":       dict(cat="merch",        size=(None, None, 0.13), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_travel_mug_white":    dict(cat="merch",        size=(None, None, 0.18), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_box_pearl_capsules":  dict(cat="merch",        size=(None, None, 0.14), tris=(3000, 800), tex=(1024, 512), fit="real"),
    "cb_box_no10":            dict(cat="merch",        size=(None, None, 0.17), tris=(3000, 800), tex=(1024, 512), fit="real"),
    "cb_tin_aaamosa":         dict(cat="merch",        size=(0.17, None, None), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_bag_premium":         dict(cat="merch",        size=(None, None, 0.30), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_tin_round":           dict(cat="merch",        size=(None, None, 0.12), tris=(5000, 1500), tex=(1024, 512), fit="real"),
    "cb_syrup_peach":         dict(cat="syrup",        size=(None, None, 0.32), tris=(5000, 1500), tex=(1024, 512), fit="real"),
}


def bbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    ms = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    # unparent (glTF imports can sit under empties) and bake transforms
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def normalise(o, size):
    mn, mx = bbox(o)
    d = mx - mn
    tw, td, th = size
    # uniform factor from the first given axis, then per-axis overrides
    ref = next((t / cur for t, cur in ((th, d.z), (tw, d.x), (td, d.y)) if t), 1.0)
    sx = tw / d.x if tw else ref
    sy = td / d.y if td else ref
    sz = th / d.z if th else ref
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mn, mx = bbox(o)
    o.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)


def decimate(o, target):
    # AI-generated GLBs arrive with every triangle's vertices split apart; collapse-decimating loose triangles shatters
    # the mesh into shards. Weld first (UVs live on loops, so texture seams survive the weld).
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data)
    size = max(bbox(o)[1] - bbox(o)[0])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=size * 1e-5)
    bm.to_mesh(o.data); bm.free()
    n = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if n > target:
        m = o.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = target / n
        m.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="dec")
    bpy.ops.object.shade_smooth()
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def opaque(o):
    """AI-generated textures often carry a stray alpha channel: products would render see-through."""
    for mat in o.data.materials:
        if mat and mat.use_nodes:
            p = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if p:
                for l in list(p.inputs["Alpha"].links):
                    mat.node_tree.links.remove(l)
                p.inputs["Alpha"].default_value = 1.0


def shrink_textures(o, px):
    for mat in o.data.materials:
        if mat and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image and max(n.image.size) > px:
                    w, h = n.image.size
                    s = px / max(w, h)
                    n.image.scale(int(w * s), int(h * s))


def bake_low(high, target, px, name):
    """Decimated copy of `high` with FRESH UVs and the high model's colour baked onto it. Collapse-decimating the AI
    meshes directly tears their texture seams (white shards on tins, tumblers, table tops); baking does not."""
    sc = bpy.context.scene
    src_mat = high.data.materials[0] if high.data.materials else None
    sp = next((n for n in src_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if src_mat and src_mat.use_nodes else None
    rough = sp.inputs["Roughness"].default_value if sp else 0.5
    metal = sp.inputs["Metallic"].default_value if sp else 0.0
    low = high.copy(); low.data = high.data.copy(); low.name = name
    sc.collection.objects.link(low)
    bpy.ops.object.select_all(action="DESELECT")
    low.select_set(True); bpy.context.view_layer.objects.active = low
    tris = decimate(low, target)
    # fresh, non-overlapping UVs
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{name}_col", px, px)
    m = bpy.data.materials.new(f"{name}_mat"); m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Roughness"].default_value = rough; p.inputs["Metallic"].default_value = metal
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img
    nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    for n in nt.nodes:
        n.select = False
    t.select = True; nt.nodes.active = t
    low.data.materials.clear(); low.data.materials.append(m)
    try:
        sc.render.engine = "CYCLES"
    except TypeError:
        pass
    sc.cycles.samples = 1; sc.cycles.device = "CPU"
    size = max(bbox(high)[1] - bbox(high)[0])
    bk = sc.render.bake
    bk.use_selected_to_active = True; bk.cage_extrusion = size * 0.01; bk.max_ray_distance = size * 0.04; bk.margin = 6
    bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
    bpy.ops.object.select_all(action="DESELECT")
    high.select_set(True); low.select_set(True); bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True,
                        cage_extrusion=size * 0.01, max_ray_distance=size * 0.04, margin=6)
    img.pack()
    return low, tris


def export(o, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_image_format="WEBP", export_image_quality=82)


def main():
    man_path = os.path.join(HERE, "assets", "manifest.json")
    man = json.load(open(man_path))
    for name, sp in SPECS.items():
        if ONLY and name not in ONLY:
            continue
        src = os.path.join(SRC, name + ".glb")
        if not os.path.isfile(src):
            print(f"MISSING {src}", flush=True)
            continue
        entry = None
        high = load(src)
        normalise(high, sp["size"])
        opaque(high)
        for tier, out_root in (((1, "models_web"),) if WEB_ONLY else ((0, "models"), (1, "models_web"))):
            o, tris = bake_low(high, sp["tris"][tier], sp["tex"][tier], f"{name}_t{tier}")
            rel = f"client/{name}.glb"
            export(o, os.path.join(HERE, "assets", out_root, rel))
            if tier == 0:
                mn, mx = bbox(o)
                s = mx - mn
                entry = {"variant": name, "file": rel, "footprint": [round(s.x, 3), round(s.y, 3)],
                         "height": round(s.z, 3), "forward_deg": 0, "fit": sp["fit"], "brand": "coffeeberry",
                         "style_tags": ["any"], "tris": tris, "source": "client:3DModels/" + name + ".glb",
                         "license": "client-owned",
                         "_kb": round(os.path.getsize(os.path.join(HERE, "assets", out_root, rel)) / 1024)}
            print(f"OK {name} tier{tier} tris={tris}", flush=True)
        if WEB_ONLY:
            continue
        lst = man.setdefault(sp["cat"], [])
        lst[:] = [e for e in lst if e.get("variant") != name]
        lst.insert(0, entry)
    json.dump(man, open(man_path, "w"), indent=1)
    print("CLIENT_MODELS_DONE", flush=True)


main()
