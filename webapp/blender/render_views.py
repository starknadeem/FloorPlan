"""
render_views.py — photograph every area of a finished design from several angles.

    blender --background cafe.blend --python render_views.py -- \
        --scene scene.json --out images/ [--samples 32] [--res 1536x1024] [--plan-only] [--limit N]

Runs on the saved cafe.blend, never a rebuild, so every view shows exactly the model the walkthrough
was exported from. These renders are the source of truth for the AI images.

Cameras are planned by ray casting: inside each room, candidate standing points and directions are scored
on how much of the room they see that earlier views did not, and rejected when something blocks the lens.
Prints PLAN_OK, then VIEW_DONE <id> per image (also for images that already exist, so a job can resume).
"""
import json
import math
import os
import sys

import bpy  # type: ignore
from mathutils import Vector  # type: ignore

EYE = 1.4
PITCH_DEG = -3.0                 # nearly level, so verticals stay straight as in architectural photography
AZ_STEP = 10                     # degrees between candidate ray columns
ELEVATIONS = (-30, -16, -4, 10)  # ray rows through the frame
NON_FURNITURE = ("floor_", "ceiling_", "wall_", "glass_", "frame_", "mullion_", "skirt_", "ground", "roof", "neighbour", "bulkhead")


def parse(argv):
    a = {"samples": 32, "res": (1536, 1024), "plan_only": False, "limit": 0}
    i = 0
    while i < len(argv):
        k = argv[i]
        v = argv[i + 1] if i + 1 < len(argv) else None
        if k == "--scene": a["scene"] = v; i += 2
        elif k == "--out": a["out"] = v; i += 2
        elif k == "--samples": a["samples"] = int(v); i += 2
        elif k == "--limit": a["limit"] = int(v); i += 2
        elif k == "--res":
            w, h = v.lower().split("x"); a["res"] = (int(w), int(h)); i += 2
        elif k == "--plan-only": a["plan_only"] = True; i += 1
        else: i += 1
    return a


def in_poly(poly, x, y):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def edge_dist(poly, x, y):
    best = 1e9
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / max(1e-9, dx * dx + dy * dy)))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def area_of(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) / 2


def diag_of(xs, ys):
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def is_outdoor(room):
    return not (room.get("ceilingHeight") or 0) > 0 or "outdoor" in (room.get("category") or "")


class Planner:
    def __init__(self, sc):
        self.sc = sc
        self.dg = bpy.context.evaluated_depsgraph_get()

    def cast(self, origin, d, far=40.0):
        hit, loc, _n, _i, obj, _m = self.sc.ray_cast(self.dg, Vector(origin), Vector(d), distance=far)
        if not hit:
            return far, None, None
        return (loc - Vector(origin)).length, loc, obj.name if obj else ""

    def can_stand(self, x, y, clear):
        """Floor below, nothing right at the lens: not on a table, in a chair or inside a plant."""
        d, _, _ = self.cast((x, y, EYE), (0, 0, -1), 3.0)
        if d < EYE - 0.2:
            return False
        for z in (EYE, 0.9, 0.5):
            for k in range(8):
                a = k * math.pi / 4
                if self.cast((x, y, z), (math.cos(a), math.sin(a), 0), clear)[1] is not None:
                    return False
        return True

    def columns(self, x, y, poly):
        """One sample per azimuth column: distance, in-room floor cells seen, furniture seen."""
        out = {}
        for az in range(0, 360, AZ_STEP):
            a = math.radians(az)
            for el in ELEVATIONS:
                e = math.radians(el)
                d, loc, name = self.cast((x, y, EYE), (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
                cell = None
                if loc is not None and in_poly(poly, loc.x, loc.y):
                    cell = (round(loc.x / 0.5), round(loc.y / 0.5))
                furn = name if name and not name.lower().startswith(NON_FURNITURE) else None
                out.setdefault(az, []).append((d, cell, furn))
        return out


def plan_room(pl, room, wanted):
    poly = [tuple(p) for p in room["polygon"]]
    area = area_of(poly)
    small = area < 10
    fov = 84 if small else (72 if is_outdoor(room) else 70)
    near, max_block, clear = (0.5, 0.45, 0.25) if small else (0.9, 0.3, 0.4)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    step = max(0.35, math.sqrt(area) / 10)
    candidates = []
    margin = 0.3 if small else 0.45
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            if in_poly(poly, x, y) and edge_dist(poly, x, y) >= margin and pl.can_stand(x, y, clear):
                candidates.append((x, y, pl.columns(x, y, poly)))
            y += step
        x += step
    half = int(fov / 2 / AZ_STEP)
    views = []
    for x, y, cols in candidates:
        for az in range(0, 360, 30):
            rays = [r for off in range(-half, half + 1) for r in cols[(az + off * AZ_STEP) % 360]]
            dists = sorted(r[0] for r in rays)
            centre = [r[0] for off in (-1, 0, 1) for r in cols[(az + off * AZ_STEP) % 360]]
            views.append({
                "x": x, "y": y, "az": az,
                "block": sum(1 for d in dists if d < near) / len(dists),
                # a pole or chair back down the middle of the frame ruins a shot even when the rest is open
                "centre": sum(1 for d in centre if d < near * 1.6) / len(centre),
                # rays that see neither this area nor anything in it: the shot is aimed out of the area, at sky or neighbours
                "away": sum(1 for r in rays if r[1] is None and r[2] is None and r[0] > diag_of(xs, ys) * 0.6) / len(rays),
                "median": dists[len(dists) // 2],
                "cells": {r[1] for r in rays if r[1]},
                "furn": {r[2] for r in rays if r[2]},
            })
    if not views:
        return [], fov
    all_cells = set().union(*(v["cells"] for v in views)) or {0}
    all_furn = set().union(*(v["furn"] for v in views)) or {""}
    diag = diag_of(xs, ys)
    chosen, seen_cells, seen_furn = [], set(), set()
    for limit in (max_block, max_block + 0.25):  # a packed room may need a looser limit: still photograph it
        while len(chosen) < wanted:
            best, best_s = None, -1e9
            for v in views:
                if v["block"] > limit:
                    continue
                if any(abs((v["az"] - c["az"] + 180) % 360 - 180) < 50 and math.hypot(v["x"] - c["x"], v["y"] - c["y"]) < diag * 0.45 for c in chosen):
                    continue  # a genuinely different angle, not a nudge of the last one
                s = (len(v["cells"] - seen_cells) / len(all_cells)
                     + 0.5 * len(v["furn"] - seen_furn) / len(all_furn)
                     + 0.2 * min(1.0, v["median"] / max(1e-3, diag * 0.5))
                     - 1.0 * v["block"] - 0.6 * v["centre"] - 0.9 * v["away"])
                if s > best_s:
                    best, best_s = v, s
            if best is None:
                break
            chosen.append(best)
            seen_cells |= best["cells"]
            seen_furn |= best["furn"]
    return chosen, fov


def make_plan(sc, scene):
    pl = Planner(sc)
    plan = []
    for room in scene["rooms"]:
        poly = room.get("polygon") or []
        if len(poly) < 3:
            continue
        area = area_of(poly)
        wanted = 2 if area < 10 else (3 if area < 45 else 4)
        views, fov = plan_room(pl, room, wanted)
        if not views:
            print(f"VIEW_SKIP {room.get('name')}: nowhere clear to stand", flush=True)
        for n, v in enumerate(views):
            vid = f"view_{len(plan):02d}"
            plan.append({
                "id": vid, "image": f"{vid}.jpg", "area": room.get("name") or room.get("id"), "roomId": room.get("id"),
                "label": f"{room.get('name') or room.get('id')} · View {n + 1}",
                "x": round(v["x"], 3), "y": round(v["y"], 3), "az": v["az"], "fov": fov, "outdoor": is_outdoor(room),
            })
    return plan


def base_exposure(saved):
    """The .blend stores the last exposure used; a stills run may have ended on a darker exterior one."""
    if saved < 0.5:
        return 0.85
    return 1.05 if abs(saved - 0.75) < 0.02 else saved


def setup(sc, samples, res):
    sc.render.engine = "CYCLES"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 92
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
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = parse(argv)
    with open(a["scene"]) as fh:
        scene = json.load(fh)
    out = a["out"]
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    plan_file = os.path.join(out, "plan.json")
    if os.path.isfile(plan_file):
        with open(plan_file) as fh:
            plan = json.load(fh)
    else:
        plan = make_plan(sc, scene)
        tmp = plan_file + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(plan, fh, indent=2)
        os.replace(tmp, plan_file)
    print(f"PLAN_OK {len(plan)}", flush=True)
    if a["plan_only"]:
        return

    setup(sc, a["samples"], a["res"])
    base = base_exposure(sc.view_settings.exposure)
    data = bpy.data.cameras.new("ViewCam")
    data.lens_unit = "FOV"
    data.clip_start = 0.15
    cam = bpy.data.objects.new("ViewCam", data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    todo = plan[: a["limit"]] if a["limit"] else plan
    for v in todo:
        dest = os.path.join(out, v["image"])
        if not os.path.isfile(dest):
            data.angle = math.radians(v["fov"])
            cam.location = (v["x"], v["y"], EYE)
            cam.rotation_euler = (math.radians(90 + PITCH_DEG), 0.0, math.radians(v["az"] - 90))
            sc.view_settings.exposure = base - 1.5 if v["outdoor"] and base < 1.0 else base
            tmp = os.path.join(out, f".tmp_{v['image']}")   # a killed render never leaves a half image behind
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            os.replace(tmp, dest)
        print(f"VIEW_DONE {v['id']}", flush=True)
    print("VIEWS_OK", flush=True)


if __name__ == "__main__":
    main()
