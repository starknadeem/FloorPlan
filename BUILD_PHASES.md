# Build Phases — Implementation Tracker

Build one phase completely, test it, then start the next. This file is the source of truth for
build status. See `ARCHITECTURE.md` (design) and `CAFESCENE_SCHEMA.md` (data contract).

Legend: ⬜ not started · 🟨 in progress · ✅ done · 🧪 ready to test

---

## Phase 1 — 3D Rendering Engine (walkable viewer)  ✅ 🧪 (built + self-tested; awaiting user test)
**Goal:** a runnable web app that renders a complete `CaféScene` as a good-looking, walkable 3D
coffee shop. Proves the visual bar and validates the schema. **No AI / no API key used.**

Why first: System 3 can be built against a hand-authored scene before the parser exists, and it
gives us a way to SEE the output of every later phase.

- [x] Scaffold Next.js + TypeScript app (`webapp/`) — Next 16.4.4, React 19.3
- [x] Install three.js (0.187) + @react-three/fiber (9.8) + @react-three/drei (10.7)
- [x] Implement `CaféScene` TypeScript types (`src/types/cafescene.ts`)
- [x] Hand-author a representative Coffee Berry `CaféScene` (`src/data/coffeeBerry.ts`)
- [x] Renderer: wall extrusion from centerlines + thickness + height (`Building.tsx`)
- [x] Renderer: door/window openings via wall-segment splitting (no CSG dep) + glass panes
- [x] Renderer: floors + ceilings from room polygons at real heights
- [x] Materials: colored PBR materials per surface role + per fixture category
- [x] Furniture/equipment: placeholder meshes sized to footprint, clickable
- [x] Lighting: ambient + hemisphere + daylight + warm pendant point lights, PCF soft shadows, ACES tone mapping
- [x] Controls: orbit + first-person walk (PointerLock + WASD), zoom, click-to-inspect
- [x] UI shell: title/stats card, orbit/walk toggle, inspector panel
- [x] `npm run build` passes (TypeScript + lint clean)
- [x] Self-test: headless WebGL render, 0 runtime errors, canvas mounts, scene renders
- [ ] **TEST** with the user (open in a real browser) before Phase 2

**Deliverable:** `cd webapp && npm run dev` → open `http://localhost:3000` → orbit/walk the café.
**Files:** `src/types/cafescene.ts`, `src/lib/geometry.ts`, `src/data/coffeeBerry.ts`,
`src/components/Viewer.tsx`, `src/components/scene/{CafeCanvas,Building,Fixtures,Lights,Controls}.tsx`.

---

## Phase 2 — Architectural Intelligence (parser)  ✅ 🧪 (built + self-tested on real A01; awaiting user test)
**Goal:** upload a floor plan → produce a correct `CaféScene` that loads in the Phase-1 viewer.
**Uses the Anthropic API key** (Claude vision).

Scope decision: Phase 2 v1 is the **Claude-vision semantic parser** — the core "AI understands the
plan" bet. Classical CV (OpenCV lines/OCR) + the dimension-graph constraint solver are an
**accuracy enhancement deferred to Phase 2.1**; the model currently reads printed dimensions and
emits metric coordinates directly (good, not yet survey-exact).

- [x] Parser runs as a **Next.js route** (`/api/parse`) using `@anthropic-ai/sdk` (TS) — keeps it
      to one `npm run dev`; a Python/CV service can be added for 2.1 behind the same contract.
- [x] Ingest/normalize: upload → sharp resize to 1568px → base64
- [x] Semantic parser: Claude `claude-opus-5-5` vision, streaming, medium effort, JSON output
      (`src/lib/parser/{types,prompt,anthropic,normalize}.ts`)
- [x] Prompt encodes coordinate conventions + the "use printed dimensions" accuracy rule, multilingual
- [x] Scale: model reads printed dimensions / scale text (chain + graph solve = 2.1)
- [x] Heights from sections; equipment identity from the legend (legendNo → fixture)
- [x] Confidence per element + `Issue`s (model + validator), shown in the viewer
- [x] `CaféScene` validator (`src/lib/validate.ts`) + normalizer (ids, provenance, enum coercion)
- [x] Frontend: upload button, busy overlay, scene switch (sample ↔ parsed), issues panel, cost/meta
- [x] Dynamic camera framing (`frameScene`) so arbitrary plans are centered
- [x] `npm run build` passes
- [x] Self-test on **real A01**: HTTP 200, valid `CaféScene` — 5 rooms (correct heights 3.35/3.0/2.4),
      29-item legend, 9 walls, 7 openings, 56 fixtures, scale "1:50"; renders in viewer, 0 runtime errors (~$0.24/parse)
- [ ] **TEST** with the user (upload a plan in the browser) before Phase 3

**Deferred to Phase 2.1:** OpenCV geometric parser, dimension-graph constraint solver, graphic
scale-bar detection, multi-sheet (PDF set) ingest + sheet classification (sections/legend linking).

### Decisions log (Phase 2)
- **2026-11-03:** Parser implemented in the Next app (route handler + TS SDK) rather than a separate
  Python/FastAPI service, to keep the demo to one process. The three-system boundary is preserved
  (it still only emits a `CaféScene`); a Python/CV service can replace/augment it later behind the
  same contract. CV + dimension-graph solver deferred to 2.1.
- **2026-11-03:** Model `claude-opus-5-5`, streaming, effort `medium`, `max_tokens` 40000 (16000 truncated
  the JSON). All overridable via env (`ANTHROPIC_MODEL`/`ANTHROPIC_EFFORT`/`ANTHROPIC_MAX_TOKENS`).

---

## Phase 2.1 — Geometry regularization (dimension-graph lite)  ✅ 🧪
Deterministic cleanup of parsed geometry (no OpenCV/Python). `src/lib/regularize.ts`:
- [x] `regularizeScene`: cluster near-equal X/Y wall coords → snap to shared values (aligns collinear
      walls, welds corners, squares right angles on axis-aligned plans)
- [x] `scaleScene`: uniform horizontal rescale (used by the editor's scale tool)
- [x] Auto-applied in the parse pipeline (`normalize.ts`) + a "Regularize" button in the editor
- [x] Build passes; exercised at runtime via the editor (0 errors)
**Deferred (full version):** OpenCV line/corner extraction, dimension-string OCR with positions,
scale-bar detection, and a least-squares constraint solve against printed dimensions (needs a Python
service). The current pass is the robust, dependency-free first increment.

## Phase 3 — Verify / correction editor  ✅ 🧪 (built + self-tested; awaiting user test)
2D top-down plan editor to confirm/fix the parsed geometry. `src/components/PlanEditor.tsx`:
- [x] SVG plan render: walls, rooms (labelled), openings, fixtures, grid; fit-to-view + zoom
- [x] Confidence coloring (green/amber/red) so low-confidence items stand out
- [x] Select any element; drag wall endpoints and drag fixtures to reposition
- [x] Property panels: wall thickness/height; fixture name/category/size/height/rotation;
      room name/category/ceiling; opening type/offset/width/height
- [x] "Rescale whole plan from a known wall length" tool; Regularize button; Delete; Apply→3D / Cancel
- [x] Wired into the viewer ("Verify & edit"); Apply commits + re-renders the 3D, Cancel discards
- [x] Self-test (headless): open editor on parsed A01 (9 walls, rooms, fixtures), select wall, regularize,
      Apply → 3D re-renders; 0 runtime errors
- [ ] **TEST** with the user in a browser
**Not yet editable (minor, future):** reshaping room polygon vertices; dragging openings along a wall
(panel-only for now).

## Phase 4 — Interior Design Intelligence  ✅ 🧪 (built + self-tested; awaiting user test)
System 2 (design decisions) + the System 3 renderer upgrade so it reads as a furnished café.

- [x] Style presets (`src/lib/design/palette.ts`): Industrial Chic, Scandinavian, Cozy Warm — each a
      full palette (floor/wall/ceiling/wood/metal/stainless/fabric/glass/accent) + lighting mood
- [x] `applyStyle(scene, key)`: writes the DesignSpec AND (when the scene has no pendant lighting)
      the design step adds pendant lamps + point lights over indoor rooms (idempotent on re-apply)
- [x] `resolvePalette(scene)` consumed by the renderer
- [x] **Parametric furniture models** (`src/components/scene/FurnitureModels.tsx`) — tables w/ legs,
      chairs, stools, counters w/ worktop, espresso machines w/ group heads, grinders, fridges/freezers,
      ovens, display/cooling cases w/ glass, sinks, shelving, sofas/banquettes, plants, pendant lamps,
      umbrellas, monitors/menu boards… (primitives, no asset files)
- [x] Renderer upgraded: walls/floors/ceilings + furniture use the palette; lighting from the mood;
      palette-driven background; fixtures clickable with hit-box + selection highlight
- [x] **AI design** (`/api/design` + `src/lib/design/anthropic.ts`): Claude picks the best style for the
      space (cheap text call); UI has a Style dropdown + "✨ AI design" button, applied to sample & parsed
- [x] `npm run build` passes
- [x] Self-test (headless): furnished sample renders (tables/chairs/plants), style switch recolors
      (industrial↔scandinavian), parsed scene furnished + design lighting (56→75 fixtures), 0 runtime
      errors; `/api/design` returns a valid style (~2s, ~$0.01)
- [ ] **TEST** with the user in a browser

**Deferred (polish / Phase 4.1):** real glTF asset library for hero equipment, PBR textures (wood grain,
concrete, stone) + HDRI environment, smarter furniture auto-layout (clearances/aisles).

## Phase 4.1 — Textures + IBL polish  ✅ 🧪
- [x] Procedural PBR textures, no asset files (`src/lib/design/textures.ts`): flagstone floor + wood
      grain, cached by (type,color)
- [x] Applied: stone on indoor/outdoor floors; wood on tables/counter/shelving/stool
- [x] Image-based lighting via drei `<Environment>` + `<Lightformer>` (offline, no network HDRI) for
      soft reflections; exposure bumped
- [x] Build passes; verified in render (flagstone terrace, wood tables, nicer shading), 0 errors
**Deferred:** normal maps, true HDRI.

## Phase 4.2 — Seating layout + data fixes + real glTF models  ✅ 🧪
- [x] **Chair auto-layout** (`src/lib/design/palette.ts` → `generateSeating`): places chairs around every
      table, inside the room, avoiding counters/walls; skips tables that already have chairs; idempotent
      (`fxd_chair_*`). Verified: parsed demo 73 → 87 fixtures, tables now seated.
- [x] **Data fixes:** `fixtureHeight` treats 0/missing height as "use category default" (fixes the
      flat/invisible 0-height "Construction table" counter); `pointInPolygon` helper added.
- [x] **Real glTF models** (drop-in): `src/lib/design/models.ts` registry + `ModelFixture.tsx` loader
      (useGLTF → scale to footprint → sit on floor → base rotation), with a `<Suspense>` fallback to the
      primitive while loading / when no model is registered. Bounding box cached per model.
- [x] Downloaded CC-licensed samples to `webapp/public/models/`: `SheenChair.glb` (chair),
      `GlamVelvetSofa.glb` (sofa). Registered: chair → SheenChair, sofa → GlamVelvetSofa.
- [x] Verified: real chair models render around tables; build passes.
**To add your own models:** drop a `.glb` in `webapp/public/models/` and add one line to the registry
(`MODEL_REGISTRY[category] = { url, baseRotationDeg }`). **Note:** the free Khronos chair is high-poly;
for many repeated items prefer **low-poly** models for best performance. Still needed: `table`,
`outdoor_chair` models (you're providing these).

## Phase 5 — Generative render layer  ✅ 🧪 (what's possible without an image model)
> Reality: Anthropic/Claude cannot generate images. Reference-A photorealism needs a separate
> image-generation key; the pipeline is built and gated, ready to switch on.
- [x] `preserveDrawingBuffer` + a capture controller (`CaptureApi`) inside the canvas
- [x] **Isometric "dollhouse" view** (Reference B) — repositions to a high 3/4 ortho-ish vantage
- [x] **Download PNG** — exports the current view (eye-level or dollhouse) from the real engine
- [x] **AI Photoreal** button → `/api/render` → `src/lib/render/photoreal.ts` (gated): returns a clear
      501 "add an image-model key (FAL_KEY/REPLICATE_API_TOKEN/STABILITY_API_KEY) and wire the provider"
      when none is configured; single integration point ready for the provider call
- [x] Render panel in the viewer (Dollhouse · Download PNG · AI Photoreal)
- [x] Build passes; verified: dollhouse view + capture work, AI-photoreal shows the honest 501 message
- [ ] **TEST** with the user
**To enable true photoreal (Ref A):** add an image-gen key + wire the one function in `photoreal.ts`
(send the captured snapshot + a scene depth/edge map to FLUX/ControlNet/Stability, return the image).

## Phase 6 — Upload flow + demo hardening  ✅ 🧪 (built + self-tested; awaiting user test)
- [x] Polished **Welcome screen** (`src/components/Welcome.tsx`): hero, explainer, drag-and-drop upload
      zone, two ready examples, Skip
- [x] **Pre-baked real parsed plan** (`src/data/sampleParsed*.{json,ts}`) — one click loads a real
      AI-parsed Coffee Berry **instantly** (no API call) so a live demo never fails or costs anything
- [x] App-wide **drag-and-drop** upload with a drop overlay
- [x] **Error hardening**: client-side type/size validation, friendly PDF message, and a "couldn't
      detect a floor plan" guard when the parse returns too few walls
- [x] `npm run build` passes; verified: welcome → one-click parsed demo renders (open terrace +
      umbrellas), 0 runtime errors
- [ ] **TEST** with the user in a browser
**Deferred:** PDF upload (needs client-side rasterization; export to PNG works today), multi-sheet sets.

---
### Demo tip
For the investor demo, run the **production** build to hide the Next.js dev indicator and run faster:
`cd webapp && npm run build && npm start` → http://localhost:3000

---

## Decisions log
- **2026-11-03:** Frontend = Next.js (App Router) + TypeScript + React-Three-Fiber. R3F canvas is
  a client component, dynamically imported with `ssr:false` to avoid SSR issues with three.js.
- **2026-11-03:** Phase 1 uses hand-authored scene data; no API calls. API key stored only in
  `webapp/.env.local` (gitignored) for Phase 2+. **Key must be rotated by the user (shared in chat).**
- **2026-11-03:** Repo layout: `webapp/` (frontend), `backend/` (Phase 2 parser), docs at root.
