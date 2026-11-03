# `CaféScene` — The Shared Data Contract (v1.0)

**Status: proposed lock · 2026-11-03**

`CaféScene` is the single data structure that the three subsystems exchange (see
`ARCHITECTURE.md` §1b). It is the *only* interface between them:

```
System 1 (Architectural Intelligence)  →  writes geometry      →  CaféScene
System 2 (Interior Design Intelligence) →  reads geometry, adds design → CaféScene
System 3 (3D Rendering Engine)          →  reads complete scene →  renders (never writes geometry)
```

**Rules of the contract**
- Every field below is either required or explicitly optional. Optional means "may be absent",
  never "may be null" — omit, don't null.
- Systems only *add* to or *refine* the object; they never silently drop another system's fields.
- A `CaféScene` is valid and renderable at every stage. After System 1 it has geometry and can be
  rendered as grey massing. After System 2 it is fully furnished and styled.
- The canonical definition is the **TypeScript** below. The backend mirrors it (pydantic). If the
  two ever disagree, the TypeScript wins and the Python is regenerated.

---

## 1. Conventions (read before the types)

### 1.1 Units
- **Length:** meters (m), floating point. Never pixels, never cm, in the contract.
- **Angles:** degrees, counter-clockwise positive, `0°` points toward **+Y** in plan space.
- **Color temperature:** Kelvin (K). **Light intensity:** relative 0..~10 (renderer-normalized).
- **Color:** sRGB hex string `"#rrggbb"`. Optional named/spec origin kept alongside.

### 1.2 Coordinate systems (the #1 source of bugs — defined once, here)
- **Plan space (2D)** — used by Systems 1 & 2 **exclusively**. `Vec2 = [x, y]` in meters.
  X increases to the right, Y increases "up the page" (toward plan-north). The origin `(0,0)` is
  the project **datum** (a declared point; see `project.datum`). All walls/rooms/fixtures are in
  plan space.
- **World space (3D)** — used by System 3 **exclusively**, right-handed, **Y-up** (three.js).
  System 3 converts plan→world with this fixed mapping and nothing else does:
  ```
  worldX = planX
  worldY = height above floor      // the up axis
  worldZ = -planY                  // plan "up the page" → world -Z
  ```
  Systems 1 & 2 must never emit world-space coordinates. System 3 must never emit plan-space edits.
- **Heights:** `height` = extent upward from the floor. Objects not sitting on the floor carry
  `baseHeight` (default `0`); windows carry `sillHeight`.

### 1.3 Identifiers
- All ids are stable, unique strings with a type prefix:
  `w_` wall · `op_` opening · `rm_` room · `fx_` fixture · `lg_` legend item · `lt_` light ·
  `mat_` material · `cam_` camera · `rnd_` render · `pg_` page.
- Ids are assigned by the system that creates the element and never reused after deletion.

### 1.4 Confidence & provenance (on every extracted element)
- `confidence: number` in `[0,1]`. Elements from a human edit are `1`.
- `source: Provenance` records which system/method/page produced or last changed the element.
  This powers the verify editor (surface low-confidence items) and debugging.

### 1.5 Enumerations
Closed string enums (extend only by editing this spec and bumping the version):

```ts
type OpeningType = "door" | "window" | "opening";           // "opening" = doorway with no door
type DoorSwing   = "none" | "left_in" | "left_out" | "right_in" | "right_out"
                 | "double" | "sliding";
type RoomCategory =
  | "seating_indoor" | "seating_outdoor" | "service_counter" | "preparation"
  | "kitchen" | "storage" | "wc" | "wc_disabled" | "corridor" | "entrance" | "other";
type FixtureCategory =
  | "counter" | "espresso_machine" | "grinder" | "display_case" | "cooling_case"
  | "fridge" | "freezer" | "ice_maker" | "sink" | "dishwasher" | "oven" | "boiler"
  | "blender" | "mixer" | "monitor" | "table" | "chair" | "stool" | "sofa" | "banquette"
  | "shelving" | "menu_board" | "signage" | "plant" | "pendant_light" | "umbrella"
  | "cashier" | "generic";
type SurfaceRole = "floor" | "wall" | "ceiling" | "counter_front" | "counter_top" | "trim";
type LightType   = "ambient" | "point" | "spot" | "area" | "pendant" | "daylight";
type RenderType  = "walkable_snapshot" | "photoreal" | "isometric";
type SystemId    = 1 | 2 | 3;
```

---

## 2. Canonical type definitions (TypeScript)

```ts
// ---------- shared ----------
type Vec2 = [number, number];           // meters, plan space
type Vec3 = [number, number, number];   // meters, world space (System 3 only)
type Hex  = string;                      // "#rrggbb"

interface Provenance {
  system: SystemId;
  method: "vision" | "cv" | "reconstruction" | "design" | "manual_edit" | "default";
  pageId?: string;                       // which source sheet, if applicable
  note?: string;
}

// ---------- top level ----------
interface CaféScene {
  schemaVersion: "1.0";
  project: Project;
  pages: Page[];                         // source sheets (System 1)
  legend: LegendItem[];                  // equipment legend, if the drawing had one
  walls: Wall[];
  openings: Opening[];
  rooms: Room[];
  fixtures: Fixture[];                   // System 1 anchors them; System 2 finalizes/adds
  design?: DesignSpec;                   // added by System 2
  lights?: LightSource[];                // added by System 2 (seed from ceiling plan if present)
  materials?: MaterialDef[];             // material library actually referenced by this scene
  assets?: SceneAssets;                  // added by System 3 (glb + renders)
  issues?: Issue[];                      // anything a system wants to flag to the user/editor
}

interface Project {
  id: string;
  name: string;
  units: "m";                            // fixed; present for self-description
  datum: { description: string; planOrigin: Vec2 }; // what (0,0) means; usually [0,0]
  drawnScale?: string;                   // e.g. "1:50" if read from the sheet
  confidenceOverall: number;             // [0,1], System 1's self-assessment
  createdAt: string;                     // ISO 8601
  schemaVersion: "1.0";
}

interface Page {
  id: string;                            // pg_*
  role: "floor_plan" | "section" | "elevation" | "ceiling_plan" | "legend" | "detail" | "other";
  sourceFile: string;                    // original filename / object-store key
  language?: string;                     // detected, e.g. "el", "en"
}

interface LegendItem {
  id: string;                            // lg_*
  no: string;                            // "9", "11a" — as printed (string, not int)
  name: string;                          // normalized English, e.g. "Professional coffee machine La Cimbali M100"
  category: FixtureCategory;
  source: Provenance;
}

// ---------- geometry (System 1) ----------
interface Wall {
  id: string;                            // w_*
  a: Vec2;                               // centerline start (plan)
  b: Vec2;                               // centerline end (plan)
  thickness: number;                     // m
  height: number;                        // m (floor to top of wall)
  baseHeight?: number;                   // m, default 0 (e.g. parapet starting above floor)
  exterior?: boolean;                    // true if a building-envelope wall
  materialRole?: SurfaceRole;            // usually "wall"; override allowed
  confidence: number;
  source: Provenance;
}

interface Opening {
  id: string;                            // op_*
  type: OpeningType;
  wallId: string;                        // the wall it is cut into
  offset: number;                        // m from wall.a to the opening's near edge, along centerline
  width: number;                         // m
  height: number;                        // m
  sillHeight?: number;                   // m, windows only (0 for doors/openings)
  swing?: DoorSwing;                     // doors only
  confidence: number;
  source: Provenance;
}

interface Room {
  id: string;                            // rm_*
  name: string;                          // normalized English ("Preparation Room", "Storage")
  category: RoomCategory;
  polygon: Vec2[];                       // ordered CCW, closed implicitly (first != last)
  ceilingHeight: number;                 // m (from section/ceiling plan, or default)
  floorMaterialId?: string;              // mat_*, set by System 2 (or from the drawing)
  confidence: number;
  source: Provenance;
}

// ---------- fixtures (System 1 anchors, System 2 finalizes) ----------
interface Fixture {
  id: string;                            // fx_*
  legendNo?: string;                     // links to LegendItem.no when the drawing numbered it
  name: string;                          // normalized English
  category: FixtureCategory;
  roomId?: string;                       // containing room, if known
  position: Vec2;                        // plan, the fixture's footprint center
  rotation: number;                      // degrees, see 1.1 (0° = local +Y faces plan +Y)
  footprint: Vec2;                       // [width(x), depth(y)] at 0°, meters
  height?: number;                       // m; may be inferred by System 2
  baseHeight?: number;                   // m off floor (wall shelf etc.), default 0
  assetId?: string;                      // chosen by System 2 (see DesignSpec.assets)
  placedBy: "parse" | "design";          // parse = came from the drawing; design = added by System 2
  confidence: number;
  source: Provenance;
}

// ---------- design (System 2) ----------
interface DesignSpec {
  style: string;                         // "industrial-chic", "scandinavian-cozy", ...
  palette: { name: string; hex: Hex }[];
  surfaceMaterials: Partial<Record<SurfaceRole, string>>; // role -> mat_* defaults
  mood: { colorTempK: number; brightness: number; notes?: string };
  decorNotes?: string;
  assets: AssetChoice[];                 // which catalog assets are used + how to fetch them
  source: Provenance;
}

interface AssetChoice {
  assetId: string;                       // referenced by Fixture.assetId
  catalogKey: string;                    // key into the glTF café library
  category: FixtureCategory;
  url: string;                           // resolved glb url (object store / CDN)
  defaultDims?: Vec2;                    // asset's native footprint (for scaling to fit)
}

interface MaterialDef {
  id: string;                            // mat_*
  role?: SurfaceRole;
  preset?: string;                       // library preset key, e.g. "wood_fluted_oak"
  baseColor?: Hex;
  roughness?: number;                    // 0..1
  metalness?: number;                    // 0..1
  textureUrl?: string;
  specOrigin?: string;                   // provenance from the drawing, e.g. "RAL 7021", "Vivechrome 30YY 58/082"
}

interface LightSource {
  id: string;                            // lt_*
  type: LightType;
  position?: Vec2;                       // plan (ambient/daylight may omit)
  mountHeight?: number;                  // m off floor
  intensity: number;                     // renderer-normalized
  colorTempK: number;
  source: Provenance;
}

// ---------- render outputs (System 3) ----------
interface SceneAssets {
  glbUrl?: string;                       // assembled walkable scene
  renders: RenderOutput[];
}

interface RenderOutput {
  id: string;                            // rnd_*
  type: RenderType;
  imageUrl: string;
  camera: CameraPose;                    // the pose it was rendered from (world space)
  conditionedOn?: ("depth" | "normal" | "edge" | "segmentation")[]; // for generative renders
  createdAt: string;
}

interface CameraPose {
  id?: string;                           // cam_*
  position: Vec3;                        // world space
  lookAt: Vec3;                          // world space
  fovDeg?: number;
}

// ---------- diagnostics ----------
interface Issue {
  id: string;
  severity: "info" | "warning" | "error";
  message: string;
  elementId?: string;                    // the offending wall/opening/etc.
  raisedBy: SystemId;
}
```

---

## 3. Validation invariants (must hold for a valid scene)

1. All `id`s are unique across the whole document.
2. Every `Opening.wallId` resolves to an existing `Wall`; `0 ≤ offset` and `offset + width ≤
   length(wall)`.
3. Every `Room.polygon` has ≥ 3 points, is non-self-intersecting, and is wound CCW.
4. Every `Fixture.roomId` (if present) resolves; `Fixture.position` lies inside that room's polygon
   (tolerance for counters against walls).
5. Every `Fixture.legendNo` (if present) matches some `LegendItem.no`.
6. Every `*.assetId` / `floorMaterialId` / `surfaceMaterials[*]` resolves to a declared
   `AssetChoice` / `MaterialDef`.
7. After System 1: `walls`, `rooms` non-empty; `project.datum` set. After System 2: every
   `Fixture` has an `assetId`; `design` present. After System 3: `assets.glbUrl` or ≥1 render.
8. All lengths ≥ 0; all angles in `[0,360)`; all confidences in `[0,1]`.
9. No plan-space array is ever a `Vec3`, and no world-space field is ever a `Vec2`.

A shared validator (TS + Python) enforces these; a scene failing validation is never passed
downstream — it goes to the verify editor with the failing `Issue`s attached.

---

## 4. Worked example (abridged) — Coffee Berry, from the real plan

Illustrative values drawn from sheets A01/A02/A04/A09 (dimensions in meters as printed on the
drawing; coordinates are representative, not surveyed). Shows the shape end-to-end.

```jsonc
{
  "schemaVersion": "1.0",
  "project": {
    "id": "proj_coffeeberry_leo",
    "name": "Coffee Berry — Leo-Center Leonberg",
    "units": "m",
    "datum": { "description": "SW corner of main seating hall, floor level +0.00", "planOrigin": [0, 0] },
    "drawnScale": "1:50",
    "confidenceOverall": 0.88,
    "createdAt": "2026-11-03T00:00:00Z",
    "schemaVersion": "1.0"
  },
  "pages": [
    { "id": "pg_a01", "role": "floor_plan",  "sourceFile": "CB_Leocenter-A01-rev02.jpg", "language": "el" },
    { "id": "pg_a02", "role": "section",     "sourceFile": "CB_Leocenter-A02-rev02.jpg" },
    { "id": "pg_a04", "role": "ceiling_plan","sourceFile": "CB_Leocenter-A04-rev02.jpg" },
    { "id": "pg_a09", "role": "detail",      "sourceFile": "CB_Leocenter-A09-rev02.jpg" }
  ],
  "legend": [
    { "id": "lg_9",  "no": "9",  "name": "Professional coffee machine La Cimbali M100 HD DT/3", "category": "espresso_machine", "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } },
    { "id": "lg_24", "no": "24", "name": "Freezer 1 door DEV 070F 620lt", "category": "freezer", "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } },
    { "id": "lg_25", "no": "25", "name": "Oven H90 267DW", "category": "oven", "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } }
  ],
  "walls": [
    { "id": "w_main_s", "a": [0, 0],      "b": [10.93, 0],    "thickness": 0.20, "height": 3.35, "exterior": true,  "confidence": 0.95, "source": { "system": 1, "method": "reconstruction", "pageId": "pg_a01" } },
    { "id": "w_main_w", "a": [0, 0],      "b": [0, 9.90],     "thickness": 0.20, "height": 3.35, "exterior": true,  "confidence": 0.95, "source": { "system": 1, "method": "reconstruction", "pageId": "pg_a01" } },
    { "id": "w_entry_angled", "a": [0, 9.90], "b": [2.05, 11.0], "thickness": 0.20, "height": 3.00, "exterior": true, "confidence": 0.78, "source": { "system": 1, "method": "cv", "pageId": "pg_a01" } }
  ],
  "openings": [
    { "id": "op_entrance", "type": "door", "wallId": "w_main_s", "offset": 7.60, "width": 1.30, "height": 2.10, "swing": "right_in", "confidence": 0.9, "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } }
  ],
  "rooms": [
    { "id": "rm_hall", "name": "Main seating hall", "category": "seating_indoor", "polygon": [[0,0],[10.93,0],[10.93,6.62],[0,6.62]], "ceilingHeight": 3.35, "floorMaterialId": "mat_floor_stone", "confidence": 0.9, "source": { "system": 1, "method": "reconstruction", "pageId": "pg_a01" } },
    { "id": "rm_prep", "name": "Preparation Room", "category": "preparation", "polygon": [[6.1,6.62],[10.0,6.62],[10.0,9.0],[6.1,9.0]], "ceilingHeight": 3.00, "confidence": 0.85, "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } },
    { "id": "rm_wc", "name": "WC (disabled)", "category": "wc_disabled", "polygon": [[10.0,6.62],[11.0,6.62],[11.0,9.0],[10.0,9.0]], "ceilingHeight": 2.40, "confidence": 0.8, "source": { "system": 1, "method": "vision", "pageId": "pg_a01" } }
  ],
  "fixtures": [
    { "id": "fx_counter_l", "name": "Service counter (L-shaped)", "category": "counter", "roomId": "rm_hall", "position": [2.2, 4.0], "rotation": 0, "footprint": [0.86, 7.40], "height": 1.10, "assetId": "as_counter_fluted", "placedBy": "parse", "confidence": 0.82, "source": { "system": 1, "method": "vision", "pageId": "pg_a09" } },
    { "id": "fx_cimbali", "legendNo": "9", "name": "La Cimbali M100 espresso machine", "category": "espresso_machine", "roomId": "rm_hall", "position": [2.4, 3.2], "rotation": 0, "footprint": [0.80, 0.58], "height": 0.55, "baseHeight": 1.10, "assetId": "as_espresso_cimbali", "placedBy": "parse", "confidence": 0.8, "source": { "system": 1, "method": "vision", "pageId": "pg_a09" } },
    { "id": "fx_table_1", "name": "Café table (4-top)", "category": "table", "roomId": "rm_hall", "position": [6.0, 2.0], "rotation": 0, "footprint": [0.70, 0.70], "height": 0.74, "assetId": "as_table_bistro", "placedBy": "design", "confidence": 1, "source": { "system": 2, "method": "design" } }
  ],
  "design": {
    "style": "industrial-chic",
    "palette": [ { "name": "warm oak", "hex": "#c89b63" }, { "name": "raw concrete", "hex": "#b8b4ad" }, { "name": "dark frame grey", "hex": "#3b3f42" } ],
    "surfaceMaterials": { "floor": "mat_floor_stone", "wall": "mat_wall_concrete", "ceiling": "mat_ceiling_exposed", "counter_front": "mat_counter_fluted" },
    "mood": { "colorTempK": 3000, "brightness": 0.7, "notes": "warm, exposed-ceiling café per A03 spec" },
    "assets": [
      { "assetId": "as_counter_fluted",   "catalogKey": "counter.fluted_wood", "category": "counter", "url": "cdn://assets/counter_fluted.glb", "defaultDims": [1.0, 0.6] },
      { "assetId": "as_espresso_cimbali", "catalogKey": "espresso.la_cimbali_m100", "category": "espresso_machine", "url": "cdn://assets/cimbali_m100.glb", "defaultDims": [0.8, 0.58] },
      { "assetId": "as_table_bistro",     "catalogKey": "table.bistro_round", "category": "table", "url": "cdn://assets/table_bistro.glb", "defaultDims": [0.7, 0.7] }
    ],
    "source": { "system": 2, "method": "design" }
  },
  "materials": [
    { "id": "mat_floor_stone", "role": "floor", "preset": "flagstone_beige", "baseColor": "#c7b299", "roughness": 0.9 },
    { "id": "mat_wall_concrete", "role": "wall", "preset": "concrete_raw", "baseColor": "#b8b4ad", "roughness": 0.85, "specOrigin": "Vivechrome 30YY 58/082" },
    { "id": "mat_counter_fluted", "role": "counter_front", "preset": "wood_fluted_oak", "baseColor": "#c89b63", "roughness": 0.6 }
  ],
  "lights": [
    { "id": "lt_pendant_1", "type": "pendant", "position": [2.2, 4.0], "mountHeight": 2.2, "intensity": 2.0, "colorTempK": 3000, "source": { "system": 2, "method": "design", "pageId": "pg_a04" } },
    { "id": "lt_daylight", "type": "daylight", "intensity": 1.0, "colorTempK": 5600, "source": { "system": 2, "method": "default" } }
  ],
  "assets": {
    "glbUrl": "cdn://scenes/proj_coffeeberry_leo.glb",
    "renders": [
      { "id": "rnd_hero", "type": "photoreal", "imageUrl": "cdn://renders/hero1.jpg", "camera": { "position": [5.0, 1.6, -1.0], "lookAt": [2.2, 1.4, -4.0], "fovDeg": 60 }, "conditionedOn": ["depth","edge","segmentation"], "createdAt": "2026-11-03T00:10:00Z" },
      { "id": "rnd_iso", "type": "isometric", "imageUrl": "cdn://renders/iso1.jpg", "camera": { "position": [20, 20, 20], "lookAt": [5, 0, -5] }, "conditionedOn": ["depth","segmentation"], "createdAt": "2026-11-03T00:11:00Z" }
    ]
  },
  "issues": [
    { "id": "iss_1", "severity": "warning", "message": "Angled entrance wall geometry below confidence threshold — verify.", "elementId": "w_entry_angled", "raisedBy": 1 }
  ]
}
```

---

## 5. Versioning
- `schemaVersion` is `"1.0"`. Any change to field names, enums, or coordinate conventions bumps
  the version and is recorded in this file's changelog.
- Additive optional fields → minor bump (`1.1`). Breaking changes → major (`2.0`) with a migration
  note.

### Changelog
- **1.0 (2026-11-03):** Initial locked contract.
