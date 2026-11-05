"""model_sheet.py — render a contact sheet of library GLBs (QA for new models).
   blender --background --python blender/model_sheet.py -- --out sheet.jpg --match equipment,kitchen [--cols 5] [--samples 48]"""
import json, math, os, sys
import bpy  # type: ignore
from mathutils import Vector  # type: ignore
HERE = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[sys.argv.index("--") + 1:]
out = a[a.index("--out") + 1]; match = a[a.index("--match") + 1].split(",")
cols = int(a[a.index("--cols") + 1]) if "--cols" in a else 5
samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
man = json.load(open(os.path.join(HERE, "assets", "manifest.json")))
items = [i for k, v in man.items() if isinstance(v, list) for i in v if any(m in i["file"] for m in match)]
cell = max(max(i["footprint"][0], i["footprint"][1], i["height"]) for i in items) * 1.25
rows = math.ceil(len(items) / cols)
for n, it in enumerate(items):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "assets", "models", it["file"]))
    for o in set(bpy.data.objects) - before:
        o.location.x += (n % cols) * cell
        o.location.y += (n // cols) * cell * 1.05
bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, 0))
fl = bpy.context.object; m = bpy.data.materials.new("fl"); m.use_nodes = True
next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (.55, .55, .53, 1); fl.data.materials.append(m)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
b = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); b.inputs["Color"].default_value = (.85, .88, .92, 1); b.inputs["Strength"].default_value = 0.9
s = bpy.data.lights.new("s", "SUN"); s.energy = 3.0; s.angle = math.radians(12); so = bpy.data.objects.new("s", s); so.rotation_euler = (math.radians(55), 0, math.radians(-35)); sc.collection.objects.link(so)
c = bpy.data.cameras.new("c"); c.type = "ORTHO"; W = cols * cell; H = rows * cell * 1.05
c.ortho_scale = max(W, H * 16 / 10) * 1.02; co = bpy.data.objects.new("c", c); sc.collection.objects.link(co); sc.camera = co
ctr = Vector(((cols - 1) * cell / 2, (rows - 1) * cell * 1.05 / 2, cell * 0.3)); d = Vector((-0.55, -1.0, 0.72)).normalized()
co.location = ctr + d * (W + H + 6); co.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
sc.render.engine = "CYCLES"; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1500, 940
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.image_settings.file_format = "JPEG"; sc.render.filepath = out
bpy.ops.render.render(write_still=True); print("SHEET_OK", [i["variant"] for i in items])
