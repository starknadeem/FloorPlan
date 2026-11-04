"""
run_design.py — execute an AI-written design.py on top of cafe_kit, headless.

    blender --background --python run_design.py -- --scene scene.json --design design.py \
        --out DIR [--mode glb|stills|panos|both] [--samples 96] [--res 1600x900] \
        [--pano-res 2048x1024] [--textures DIR]

Prints STILL_TOTAL/STILL_DONE, PANO_TOTAL/PANO_DONE markers (progress) and RUN_OK on success.
"""
import json
import os
import sys

import bpy  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cafe_kit  # noqa: E402


def parse(argv):
    a = {"mode": "stills", "samples": 96, "res": (1600, 900), "pano_res": (2048, 1024),
         "textures": os.path.join(HERE, "..", "public", "textures")}
    i = 0
    while i < len(argv):
        k = argv[i]
        v = argv[i + 1] if i + 1 < len(argv) else None
        if k == "--scene": a["scene"] = v; i += 2
        elif k == "--design": a["design"] = v; i += 2
        elif k == "--out": a["out"] = v; i += 2
        elif k == "--mode": a["mode"] = v; i += 2
        elif k == "--samples": a["samples"] = int(v); i += 2
        elif k == "--textures": a["textures"] = v; i += 2
        elif k in ("--res", "--pano-res"):
            w, h = v.lower().split("x"); a["res" if k == "--res" else "pano_res"] = (int(w), int(h)); i += 2
        else:
            i += 1
    return a


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = parse(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with open(a["scene"]) as fh:
        scene = json.load(fh)
    with open(a["design"]) as fh:
        code = fh.read()
    ns = {"bpy": bpy, "SCENE": scene, "TEXTURES": os.path.abspath(a["textures"]), "Kit": cafe_kit.Kit, "cafe_kit": cafe_kit, "math": __import__("math")}
    exec(compile(code, a["design"], "exec"), ns)
    K = ns.get("K")
    if K is None:
        raise SystemExit("design.py must create the kit as `K`")
    out = a["out"]
    os.makedirs(out, exist_ok=True)
    result = {"stills": [], "panos": None, "glb": None}
    try:
        K.export_glb(os.path.join(out, "cafe.glb"))
        result["glb"] = "cafe.glb"
        print("GLB_OK", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] GLB export failed: {e}", flush=True)
    if a["mode"] in ("stills", "both"):
        result["stills"] = K.render_stills(out, samples=a["samples"], res=a["res"])
    if a["mode"] in ("panos", "both"):
        pts = K.stops or [(c.location.x, c.location.y, 0.0, lbl) for c, lbl in K.cameras]
        result["panos"] = K.render_panos(out, pts, res=a["pano_res"], samples=max(32, a["samples"] // 2))
    try:
        K.save(os.path.join(out, "cafe.blend"))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not save .blend: {e}")
    with open(os.path.join(out, "result.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    print("RUN_OK", flush=True)


if __name__ == "__main__":
    main()
