# Blender Cycles render pipeline

Offline **photoreal** render path for System 3. It reconstructs a `CafeScene` in Blender and
path-traces it with **Cycles** — true global illumination, soft shadows, real glass, physical
sky — instead of the real-time WebGL (three.js) view. Same geometry, same Kenney GLB assets,
same palette; just a much better renderer.

Think of it as the "beauty shot" button: three.js stays the live, walkable editor; Blender
produces the publishable still.

## Requirements

- **Blender 3.6+** on your `PATH` (`blender --version` must work), or set `BLENDER_BIN` in
  `webapp/.env.local` to the full path of the binary.
- No HDRI or extra downloads: lighting uses Blender's built-in **Nishita** physical sky + a sun,
  plus the scene's own pendant/point lights.
- Reuses `webapp/public/models/kenney/*.glb` and `webapp/public/textures/*` already in the repo.

## Use it from the app

Click **🎬 Blender Render** in the 3D viewer. It POSTs the current scene + camera pose to
`/api/render/blender`, which spawns Blender headless and returns the PNG into an overlay you can
download. If Blender isn't installed you get a clear 501 message (the live view still works).

## Use it from the command line

```bash
# dump the sample scene to JSON (type-only import strips cleanly, no bundler needed)
node --experimental-strip-types -e '
  import("./src/data/coffeeBerry.ts").then(m =>
    require("fs").writeFileSync("/tmp/scene.json", JSON.stringify(m.coffeeBerryScene)))'

# render it
blender --background --python blender/render_cafe.py -- \
  --scene /tmp/scene.json --out /tmp/cafe.png \
  --no-ceiling --samples 128 --res 1600x900
```

### Flags (after the `--`)

| flag | meaning |
|------|---------|
| `--scene FILE` | CafeScene JSON (required) |
| `--out FILE` | output PNG (required) |
| `--no-ceiling` | drop room ceilings → open "dollhouse" view of the interior |
| `--samples N` | Cycles samples (default 128; 32–64 for quick previews) |
| `--res WxH` | resolution, e.g. `1920x1080` |
| `--cam px,py,pz,tx,ty,tz` | camera pose in **three.js world** coords (pos xyz, target xyz); omit to auto-frame |
| `--models-dir DIR` / `--textures-dir DIR` | override asset locations (default: `../public/...`) |
| `--style KEY` | override palette (`industrial-chic` \| `scandinavian` \| `cozy-warm`) |

## Walkable photoreal 360° tour (the main product)

Uploading a floor plan now auto-builds a **walkable, photoreal 360° tour**: Blender renders an
**equirectangular panorama** at a standing point in each room, and the browser (`TourViewer.tsx`)
drops you *inside* those panoramas — drag to look around, scroll to zoom, pick a room to teleport.
This is how you get "walk through a photoreal space in a browser": Blender does the photoreal
lighting, the browser does the look-around.

Flow: **upload → parse → design (places furniture) → `POST /api/tour` → Blender renders panos into
`public/tours/<id>/` → `TourViewer` shows the walkable tour.** It also runs on demand via the
**🎬 Photoreal Tour** button.

```bash
# render a tour (equirectangular panos + manifest.json) straight from the CLI
blender --background --python blender/render_cafe.py -- \
  --scene /tmp/scene.json --pano-out /tmp/tour --pano-res 4096x2048 --samples 96
# -> /tmp/tour/pano_00.jpg ... + /tmp/tour/manifest.json
```

Pano flags: `--pano-out DIR` (switches to tour mode), `--pano-res WxH` (2:1, e.g. `4096x2048`),
`--eye 1.55` (camera eye height, m). Standing points are auto-chosen from room polygons
(`standing_points`), one per room, two for long rooms. Ceilings are forced ON in pano mode so each
room feels enclosed.

Current nav is a room strip (teleport by name). Spatial floor-arrow hotspots are a natural next
step — they need a one-time heading calibration against a rendered pano (noted in `TourViewer.tsx`).

## How it maps to the TypeScript engine

`render_cafe.py` mirrors the real-time engine so the two stay visually consistent:

| three.js / TS | Blender script |
|---------------|----------------|
| `geometry.ts` `buildWallBoxes` | `build_wall_boxes` (solid/header/sill splits + glass panes) |
| `geometry.ts` `roomShape` | `polygon_mesh` (ngon floor/ceiling with planar UVs) |
| `geometry.ts` `fixtureHeight` / `DEFAULT_HEIGHTS` / `CATEGORY_COLORS` | same tables, for fallback boxes |
| `models.ts` `MODEL_CATALOG` / `MODEL_REGISTRY` / `resolveModel` | embedded Python copies; same GLBs |
| `ModelFixture.tsx` fit/scale/placement | `build_fixtures` matrix (contain/width fit, center + sit on floor) |
| `palette.ts` `STYLE_PRESETS` | `STYLE_PRESETS` (colours + light temperature) |

**Coordinate mapping** (matches `geometry.ts §1.2`): three.js world `(x, height, -planY)` is Y-up;
Blender is Z-up, so `Blender(x,y,z) = (planX, planY, height)` — a det-+1 basis change, so rotations
about three's +Y map 1:1 to rotations about Blender's +Z.

## Known gaps / next steps

- **Parametric-only fixtures** (counter, display cases, menu board, umbrella, cashier) still render
  as simple boxes — they have no GLB in the app either. Tables are the exception: `build_table`
  draws a round bistro table (marble top + dark pedestal). Add more `build_*` helpers as needed.
- **Furniture facing**: `KENNEY_FRONT_DEG` (180°) is applied like the app. If a whole category faces
  the wrong way after an asset change, flip that constant.
- **Light power** (`build_lights`) uses a heuristic Watt mapping from the schema's `intensity`;
  tune to taste.
- Constants here are **copied** from the TS, not imported. If `models.ts` / `geometry.ts` /
  `palette.ts` change, update the mirrors at the top of `render_cafe.py`.
