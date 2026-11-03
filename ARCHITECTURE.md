# CaféVision — AI 2D Floor Plan → Realistic 3D Coffee Shop

**Architecture & Roadmap**
Version 0.1 · 2026-11-03 · Author: project team (ali@automizerai.com) + Claude

---

## 1. Vision (one paragraph)

A web app where a user uploads a 2D floor-plan image (or a multi-sheet PDF set) of a
**coffee shop**, and the system uses AI to understand it, reconstruct it as an accurate,
**explorable 3D space**, design a finished-looking interior, and optionally produce
**photorealistic renders** of any viewpoint. The target user is someone who wants to *see*
their future café before building it. The core bet is that **an investor can upload their own
plan live** and get a convincing result — so the AI parsing is the product, not a gimmick.

**Flow:** Upload → AI understands the plan → extracts structured data → reconstructs 3D →
AI designs the interior → user explores (walkable 3D + photoreal stills).

---

## 1a. Core principle: structured understanding, NOT image-to-3D

This is the defining decision of the project. It is **not** an image-to-3D generator.

| | Naïve image-to-3D (what we are NOT building) | Structured understanding (what we ARE building) |
|---|---|---|
| Approach | One model: image → mesh (depth/point-cloud or generative 3D) | Interpret → structured geometry → assemble scene → design |
| Output | An unstructured mesh "blob" | Semantic model: walls, openings, rooms, fixtures |
| Scale | Guessed / wrong | Exact, from the drawing's printed dimensions |
| Walls/rooms | Not real entities | First-class, metric, closed rooms |
| Objects | Fused into the mesh, not separable | Individually placed, identified, swappable assets |
| Editable | No | Yes — every element is data in `CaféScene` (§7) |
| Design decisions | Impossible (nothing to reason about) | Explicit AI choices over a model it understands |

The system has three distinct competencies, kept separate on purpose:

1. **Understands architectural geometry** — walls, dimensions, openings, rooms, heights,
   as real metric entities (§5.3–5.4), not pixels or a mesh.
2. **Generates structured 3D scenes** — a clean scene graph of parametric walls + placed,
   identified assets exported as glTF (§5.6), driven by the `CaféScene` data model (§7).
3. **Makes intelligent interior-design decisions** — the design AI reasons *about that
   structured model* (style, palette, materials, furniture selection, lighting) and emits a
   `designSpec` applied deterministically (§6.3).

Everything downstream is a transformation of a structured, inspectable data object — never an
opaque pixel-to-mesh step. The photoreal render (§5.7) sits on top as a *presentation* layer
and is the only place generative imagery is used; it never replaces the structured model.

---

## 1b. The three independent subsystems (hard boundaries)

The product is **three decoupled systems**, each with one responsibility, communicating
**only** through the structured `CaféScene` data contract (§7). None of them calls into another
directly; each reads a well-defined input and writes a well-defined output. This makes them
independently buildable, testable, replaceable, and even runnable as separate services.

```
  raw upload                 geometry only                complete scene
 (images / PDF)            (no design choices)          (no pixels, no CV)
      │                          │                             │
      ▼                          ▼                             ▼
┌───────────────┐  CaféScene  ┌───────────────┐  CaféScene  ┌────────────────┐
│ 1. ARCHITECT. │  (geometry) │ 2. INTERIOR   │  (+design)  │ 3. 3D RENDERING│
│ INTELLIGENCE  │ ──────────► │ DESIGN INTEL. │ ──────────► │ ENGINE         │
│               │             │               │             │                │
│ image → walls │             │ geometry →    │             │ scene → pixels │
│ dims, rooms,  │             │ style, layout,│             │ walkable 3D +  │
│ openings      │             │ materials,    │             │ photoreal      │
│               │             │ lighting      │             │ renders        │
└───────────────┘             └───────────────┘             └────────────────┘
```

### System 1 — Architectural Intelligence
- **Responsibility:** understand the floor plan; produce accurate measurements and geometry.
- **Input:** raw upload (images / PDF).
- **Output:** the *geometric* part of `CaféScene` — walls, openings, rooms, heights, fixture
  anchors (where equipment is, by legend number), scale, and per-element confidence.
- **Owns:** ingest, sheet classification, vision+CV parsing, scale calibration, dimension-graph
  reconstruction, the verify/correction editor (§5.1–5.4, §3).
- **Must NOT:** choose styles, pick furniture models, or decide materials/lighting. It reports
  what the drawing *says*, nothing more. It knows nothing about rendering.

### System 2 — Interior Design Intelligence
- **Responsibility:** decide how the space should look and where furniture, equipment, and
  decorations go.
- **Input:** `CaféScene` geometry from System 1 (structured data only — **never the image**).
- **Output:** an enriched `CaféScene` — a `designSpec` (style, palette, materials, lighting) +
  concrete fixture/furniture placements with chosen `assetId`s and transforms.
- **Owns:** style selection, furniture/equipment layout reasoning, material & color assignment
  (honoring any specs the drawing carried, e.g. RAL/3000K), lighting design, decoration (§6.3).
- **Must NOT:** do any computer vision or geometry extraction, and must not render. It reasons
  purely about the structured model it is handed.

### System 3 — 3D Rendering Engine
- **Responsibility:** convert structured scene data into a realistic, interactive 3D environment
  (and photoreal stills).
- **Input:** a complete `CaféScene` (geometry + design) — **no pixels, no floor plan, no CV.**
- **Output:** an optimized glTF/GLB scene + the interactive walkable/orbit viewer, plus
  on-demand photoreal renders of any camera pose.
- **Owns:** wall extrusion/opening cuts, asset instantiation, PBR materials, real-time lighting
  & post-processing, the browser viewer, the structure-preserving render layer (§5.6–5.7, §6.1).
- **Must NOT:** know or care how the scene was produced. Hand it any valid `CaféScene` — from
  the parser, the editor, or a hand-authored test file — and it renders identically.

**Why this matters in practice:**
- Each system has its own repo/package, test suite, and mock `CaféScene` fixtures, so teams work
  in parallel without blocking each other.
- The rendering engine can be developed against a hand-authored scene **before parsing exists**.
- The design intelligence can be improved (better layouts, new styles) without touching parsing
  or rendering.
- Any stage can be swapped (e.g. a different vision model, a different render path) as long as it
  honors the `CaféScene` contract.

---

## 1c. Target output fidelity & the real-time-vs-photoreal reconciliation

Two reference images define the quality bar (`image.jpeg`, `image2.jpeg`):
- **Reference A — eye-level photorealistic interior** (industrial-chic café, exposed-duct
  ceiling, fluted-wood counter, flagstone floor, daylight). Archviz/ray-traced-or-AI quality.
- **Reference B — isometric "dollhouse" cutaway** of the whole furnished café. Polished,
  AI-isometric look.

**Critical constraint (must be understood by everyone, including stakeholders):**
These are **not** outputs of a real-time browser 3D engine. Reference-A photorealism comes from
offline ray-tracing (minutes/frame, non-interactive) or AI image generation — **not** WebGL. You
cannot have a single viewport that is simultaneously *free-roam walkable* and *this photoreal*.
The product reconciles this with a **hybrid**: the structured scene (Systems 1+2) drives three
distinct presentation modes.

| Output mode | Target look | Tech | Interactive |
|---|---|---|---|
| Walkable 3D | Clean, stylized-realistic (NOT Ref-A photoreal) | Real-time three.js/R3F from `CaféScene` | Free roam, zoom, inspect |
| Photoreal still (Ref A) | Archviz photoreal | AI image model **conditioned on the 3D scene** (depth/edge/segmentation ControlNet) | No — hero shot of a chosen camera pose |
| Isometric overview (Ref B) | Polished dollhouse | AI isometric **or** ortho 3D render of the scene | Regenerate per layout |

**Faithfulness is enforced by conditioning.** Photoreal/isometric images are generated from the
**actual structured scene** (rendered depth, normals, edges, segmentation as control inputs), so
the beautiful image matches *this* floor plan — same walls, counter, window, equipment positions
— rather than a generic café. This is only possible because Systems 1+2 produce a real model
first; it is the strongest justification for the structured (non image-to-3D) approach.

**The fidelity ↔ faithfulness dial (set expectations honestly):**
- Structured real-time 3D = perfectly faithful to the plan, less glossy.
- AI render = glossy (Ref-A), approximately faithful; may beautify or reinterpret small details.
- Conditioning narrows the gap but never closes it to zero.

**Owned by System 3** (§5.6–5.7): the walkable path is the real-time renderer; the photoreal and
isometric paths are the structure-preserving generative render layer. All three consume the same
`CaféScene` — no mode ever sees the original floor-plan image.

**DECISION (2026-11-03):** Both modes are **first-class and equal** — invest fully in the
real-time walkable engine **and** the generative photoreal/isometric layer, shown side by side.
Expectation accepted: the live walkable view is clean/stylized-realistic, and Reference-A
photorealism is delivered through the AI still + isometric renders, not the free-roam view.

---

## 2. What the real inputs taught us

The `/FloorPlans` example set ("Coffee Berry, Leo-Center Leonberg", sheets A01–A21, scale
1:50/1:25, 2026) is a professional CAD-exported drawing set. Key findings that shaped this
architecture:

| Sheet | Content | Why it matters |
|-------|---------|----------------|
| A01 | Ground-floor plan + 28-item equipment legend | Primary geometry + object identity |
| A02 | Sections C–C / D–D | **Real Z heights** (3.00 / 3.35 / 2.40 / 4.48 m) |
| A03 | Exterior elevations + signage | **Material & color specs** (RAL 7021, Vivechrome, 3000K) |
| A04 | Reflected ceiling plan | Per-zone ceiling heights, **light positions**, umbrellas |
| A05 | Storage / lockers plan | Back-of-house rooms (separate plan) |
| A09 | Counter/bar detail 1:25 + **graphic scale bar** | Precise equipment placement; a built-in ruler |

**Design implications (these are the important takeaways):**

1. **Dimensions are printed on the drawing.** We do **not** need to measure pixels to get
   real-world sizes — we read the architect's own numbers (`2.05`, `6.80`, `10.93` m) and
   reconstruct geometry from them. This is the single most important fact: it turns an
   unreliable CV problem into a mostly text-reading + constraint-solving problem.
2. **A legend maps numbers → named equipment.** "#9 = La Cimbali M100 coffee machine" means
   object placement is identity-based, not guesswork.
3. **Heights, lighting, and materials already exist** in the section/elevation/ceiling sheets.
   When present, we use them; when absent, the design-AI infers them.
4. **Inputs vary enormously.** A real upload may be a single phone photo of one plan, a clean
   single CAD plan, or a full multi-sheet PDF. The pipeline must **degrade gracefully**.
5. **Multilingual.** Labels mix Greek + English. The vision model must handle arbitrary
   languages and we normalize to a canonical English schema.

---

## 3. The honest truth about "100% accurate parsing"

This is the project's central risk, so it gets its own section.

**No AI will *guarantee* 100% on an arbitrary floor plan.** Vision models (Claude, GPT-4V,
Gemini) are excellent at *reading and interpreting* drawings but are **not pixel-precise**;
they will occasionally misread a corner or a small dimension. Pure computer-vision pipelines
(line detection, vectorization) are precise on clean CAD but brittle on photos, hand drawings,
and unusual styles. Promising unconditional 100% would be dishonest.

**What we *can* credibly deliver, and how:**

- **Exact where the drawing states a number.** Because dimensions are printed, geometry is
  reconstructed from those numbers, not from pixels → wall lengths are the architect's exact
  figures.
- **Two parsers, cross-checked.** Run (a) a vision LLM for semantic understanding (what is a
  wall, door, counter, which equipment) and (b) a classical CV pass for precise line/scale
  geometry. Reconcile them; disagreement flags low confidence.
- **Scale calibration with fallbacks:** printed scale ("1:50 @ A2") → a dimension string of
  known length → the graphic scale bar (seen on A09) → ask the user for one known measurement.
- **Confidence scoring + human-verify step.** Every extracted element carries a confidence.
  A lightweight correction editor lets the user (or us, for a demo) fix the few uncertain
  items in seconds. For a **live investor upload**, this is what prevents an on-stage failure:
  the AI does ~95%, the 10-second verify closes the gap.

> **Recommended framing for investors:** "The AI reconstructs your plan automatically and shows
> you a quick confirmation step for anything it's unsure about" — honest, and still feels
> magical. We should **not** market "100% automatic, zero input."

---

## 4. System architecture (high level)

```
┌─────────────┐   upload    ┌──────────────────────────────────────────┐
│  Browser    │ ──────────► │  API (FastAPI)                            │
│  (Next.js)  │             │                                            │
│             │             │  1. Ingest  (PDF/img → normalized pages)  │
│  - uploader │             │  2. Classify sheets (plan/section/legend) │
│  - 3D view  │ ◄─────────  │  3. Parse  (Vision LLM + CV)  ──► JSON    │
│  - editor   │  scene.json │  4. Reconstruct geometry (dimension graph)│
│  - renders  │             │  5. Design AI (materials/furniture/light) │
└─────────────┘             │  6. Scene assembly (glTF + placements)    │
       ▲                    │  7. Photoreal render (image model)        │
       │  glTF + renders    └──────────────────────────────────────────┘
       └──────────────────────────────┘
                          storage: Postgres (projects) + object store (files/assets)
```

**The backbone is a single canonical data structure** (`CaféScene`, §7) that every stage reads
and writes. Everything is just transformations of that object. This keeps stages swappable and
testable.

---

## 5. Pipeline, stage by stage

### 5.1 Ingest & normalize
- Accept: JPG/PNG, single or multiple; PDF (rasterize each page at ~200 DPI).
- De-skew, enhance contrast, detect page orientation.
- Output: a list of normalized page images + any embedded PDF vector text (huge accuracy win
  when the PDF is vector, not scanned — we can read dimension strings directly).

### 5.2 Sheet classification
- A quick vision-model pass labels each page: `floor_plan`, `section/elevation`,
  `ceiling_plan`, `legend`, `detail`, `other`.
- Picks the primary floor plan; links sections/legend/ceiling as supporting data.
- Handles the single-image case trivially (one page = the plan).

### 5.3 Parsing (the hard part)
Two cooperating parsers:

**(A) Semantic parser — Vision LLM (Claude).** Structured-output prompt returns:
walls (as polylines with any adjacent dimension text), openings (doors/windows + swing),
rooms (name + area label), fixtures/equipment (legend number, name, approx position/footprint),
annotations (heights, materials, colors), and the drawing's scale text.

**(B) Geometric parser — classical CV.** Line segment detection, wall vectorization,
corner snapping, graphic-scale-bar detection, OCR of dimension strings with positions.
Gives pixel-precise geometry + a reliable px→meter scale.

**Reconciliation:** align the two; where the semantic model says "wall here" and CV found a
line, snap to CV geometry; attach the LLM's semantics (this line is the entrance wall, that
box is equipment #9). Produce per-element confidence.

### 5.4 Geometry reconstruction (dimension graph)
- Build a graph of points/edges constrained by the **printed dimensions**.
- Solve for metric coordinates so wall lengths match the stated numbers (least-squares /
  constraint solve). Printed numbers win over pixel estimates.
- Close loops into rooms; derive wall thickness from double-line spacing.
- Apply Z: wall/ceiling heights from sections & ceiling plan (per zone); defaults when absent.
- Output: a clean, metric 2.5D model (floor polygons, wall solids, openings, fixture anchors).

### 5.5 Interior design AI (§6)

### 5.6 3D scene assembly
- Extrude walls, cut door/window openings, add floors/ceilings.
- Place furniture & equipment from a **curated glTF asset library** (§6.2), matched by the
  legend names ("La Cimbali M100" → espresso-machine model) with sensible fallbacks.
- Bake/choose materials and lighting from the design step.
- Export a single optimized **glTF/GLB** scene + a `scene.json` describing placements.

### 5.7 Photoreal render layer
- From any camera pose in the 3D viewer, generate a photorealistic still:
  render the 3D view to a depth/normal/segmentation buffer and feed an image model
  (img2img / ControlNet-style, structure-preserving) so the photoreal image **matches the
  actual geometry** rather than hallucinating a different room.
- This is the investor "wow" shot; it's an enhancement layer, not the source of truth.

---

## 6. Making it look like a finished café (not white boxes)

This is an explicit requirement ("I don't want only a white simple building"). Three levers:

### 6.1 Real-time materials & lighting (the walkable layer)
- PBR materials: wood counters, concrete/tile floors, brick/plaster walls, glass storefront.
- Warm café lighting: 3000K (as specified on A03), soft shadows, baked ambient occlusion,
  image-based lighting, light fixtures placed from the ceiling plan.
- Post-processing: bloom, tone mapping, subtle depth of field.

### 6.2 Curated coffee-shop asset library
Because the domain is **only coffee shops**, we can pre-build/curate a focused glTF library:
counters & bars, espresso machines, grinders, display/cooling cases, fridges/freezers, ovens,
sinks, café tables & chairs, stools, sofas/banquettes, shelving, menu boards, signage, plants,
pendant lights, outdoor tables + umbrellas. Each tagged so the legend matcher can pick one.
Finite, high-quality, reusable — this is what separates "real product" from "grey blocks".

### 6.3 Design AI
- Picks a cohesive style (modern/industrial/cozy/Scandinavian), palette, materials, and décor.
- Honors specs found in the drawings (RAL/Vivechrome colors, 3000K) when present.
- Produces a `designSpec` the scene assembler applies deterministically.

---

## 7. Canonical data model (`CaféScene`) — the backbone

> **The full, locked contract lives in [`CAFESCENE_SCHEMA.md`](./CAFESCENE_SCHEMA.md) (v1.0).**
> That file is authoritative: canonical TypeScript types, unit/coordinate conventions, validation
> invariants, and a worked Coffee Berry example. The sketch below is just orientation.

Single source of truth passed between stages (abbreviated — see the schema file for the real thing):

```jsonc
{
  "project": { "id", "name", "units": "m", "scale": "1:50", "confidenceOverall": 0.0-1.0 },
  "pages":   [ { "id", "role": "floor_plan|section|legend|ceiling|detail" } ],
  "walls":   [ { "id", "a":[x,y], "b":[x,y], "thickness", "height", "confidence" } ],
  "openings":[ { "id", "type":"door|window", "wallId", "offset", "width", "height", "swing" } ],
  "rooms":   [ { "id", "name", "polygon":[[x,y]...], "ceilingHeight", "floorMaterial" } ],
  "fixtures":[ { "id", "legendNo", "name", "category", "position":[x,y], "rotation",
                 "footprint":[w,d], "assetId", "confidence" } ],
  "legend":  [ { "no", "name", "category" } ],
  "designSpec": { "style", "palette":[...], "materials":{...}, "lighting":{...} },
  "assets":  { "glbUrl", "renders":[ {"cameraPose", "imageUrl"} ] }
}
```

Everything downstream (3D, editor, renders) is a pure function of this object. It is also what
the human-verify editor reads and writes.

---

## 8. Tech stack (concrete recommendation)

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | **Next.js + React + TypeScript** | SSR, routing, familiar, fast to demo |
| 3D viewer | **React-Three-Fiber + three.js + drei** | Best-in-class browser 3D, walkable + orbit |
| Backend | **Python + FastAPI** | Best ecosystem for CV/ML; clean API |
| Vision parsing | **Claude (vision)** structured output | Strong plan interpretation, multilingual |
| Classical CV | **OpenCV** + a line/vectorization step; OCR via a doc model | Pixel-precise geometry + dimension OCR |
| Geometry solve | NumPy/SciPy least-squares constraint solve | Dimension-graph reconstruction |
| Photoreal render | Structure-preserving image model (img2img/ControlNet-style) | Matches geometry, not hallucinated |
| 3D assets | Curated **glTF/GLB** café library | Realistic, reusable, domain-focused |
| Storage | Postgres (metadata) + S3-compatible object store (files/assets) | Standard |
| Auth/accounts | Deferred to production phase | Not needed for demo |

Rationale for split frontend (JS) / backend (Python): the hard parsing work lives where the CV
and ML libraries are strongest; the viewer lives where browser 3D is strongest.

---

## 9. Handling arbitrary uploads (graceful degradation)

| Input quality | Behavior |
|---------------|----------|
| Full CAD set (like Coffee Berry) | Best result: exact geometry, real heights, real materials, equipment from legend |
| Single clean plan, dimensioned | Exact XY from dimensions; heights/materials inferred by design AI |
| Single plan, no dimensions | Ask user for ONE known length (or detect a scale bar); geometry scaled from that |
| Photo / hand-drawn / messy | Best-effort; confidence low; verify-editor does more of the work; set expectations in UI |
| Non-coffee-shop or non-plan | Detect and politely reject / warn (domain is coffee shops) |

The **verify/correction editor** is the universal safety net: it guarantees a good final result
regardless of input quality, which is exactly what makes a *live* investor upload safe.

---

## 10. Risks & mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Parsing wrong on unfamiliar plan (live demo) | High | Dual parser + confidence + quick verify editor; prepared fallback samples |
| Scale/units misread | High | Multiple calibration sources + one-tap user confirmation |
| Non-orthogonal / curved walls (A01 has an angled entrance) | Medium | Polyline walls (not just rectangles) from the start |
| Equipment model missing from library | Medium | Category fallback (generic espresso machine) + "generic box" last resort |
| Photoreal render drifts from geometry | Medium | Structure-preserving conditioning (depth/edges), not free generation |
| Performance of big scenes in browser | Medium | glTF optimization, instancing, draco compression, LODs |
| Cost per upload (vision + render calls) | Low/Med | Cache per project; renders on-demand only |

---

## 11. Roadmap (demo-first, then product)

### Phase 0 — Foundations (scaffolding)
- Repo setup (Next.js app + FastAPI service), the `CaféScene` schema, storage, upload endpoint.
- A hand-authored `scene.json` for the Coffee Berry plan to unblock 3D work in parallel.

### Phase 1 — The "wow" 3D viewer (de-risks the visual promise)
- R3F walkable + orbit viewer that renders a `CaféScene` with real materials & warm lighting.
- Load the hand-authored Coffee Berry scene; make it look like a finished café.
- **Milestone:** a beautiful, explorable Coffee Berry that proves the look.

### Phase 2 — Parsing pipeline (de-risks the core bet)
- Ingest + sheet classification + dual parser + dimension-graph reconstruction.
- Target the Coffee Berry set end-to-end; measure accuracy vs. the hand-authored ground truth.
- **Milestone:** upload the real A01 (+supporting sheets) → correct `CaféScene` automatically.

### Phase 3 — Verify/correction editor
- 2D overlay editor: confirm/fix walls, openings, scale, equipment placement; confidence badges.
- **Milestone:** any imperfect parse is fixable in under a minute.

### Phase 4 — Design AI + asset library + 3D assembly
- Curated glTF library; legend→asset matcher; design-spec generation; automated scene assembly.
- **Milestone:** parse → auto-furnished, styled, walkable 3D with no manual modeling.

### Phase 5 — Generative render layer (first-class, per the §1c decision)
Equal priority to the walkable viewer, not an afterthought. Two outputs:
- **Photoreal eye-level still (Reference A):** camera-pose → render scene's depth/normals/edges/
  segmentation → structure-preserving image model → archviz-quality still faithful to the scene.
- **Isometric dollhouse (Reference B):** ortho/isometric camera over the scene → same conditioning
  → polished top-down cutaway of the whole furnished café.
- Caching per project; renders regenerate when the layout or style changes.
- **Milestone:** one-click photoreal shot of any view **and** a one-click dollhouse overview,
  both visibly matching the uploaded plan.

> Because both modes are first-class, Phase 1 (walkable engine) and Phase 5 (generative layer)
> are **parallel tracks** over the same `CaféScene`; the generative track can start as soon as a
> hand-authored scene exists, alongside the viewer.

### Phase 6 — Demo hardening
- Prepared sample plans, graceful errors, polish, loading states, the live-upload path.
- **Milestone:** investor-ready demo that survives a live arbitrary upload.

### (Later) Production
- Accounts, billing, scaling, broader input robustness, export (share links, video flythrough).

**Suggested build order to de-risk fastest:** Phase 1 (prove the look) and Phase 2 (prove the
parse) can proceed in parallel against the same `CaféScene` contract — the hand-authored scene
lets the viewer team start before parsing is done.

---

## 12. What the investor demo will show

1. Upload the Coffee Berry plan (or the investor's own).
2. Watch the AI extract walls, rooms, doors, equipment — with a quick confirmation step.
3. A furnished, styled, **walkable** 3D café appears; investor moves through it (proves it's
   real and faithful to *their* plan).
4. **Side by side:** one click → a **photorealistic** still (Reference A) of the current view,
   and one click → an **isometric dollhouse** overview (Reference B) of the whole café.
5. Message: "From a flat drawing to a space you can walk through — and a photoreal preview of how
   it will really look — before you build it."

---

## 13. Open questions to settle before Phase 2

- Preferred default interior styles to support first (modern / industrial / cozy / Scandinavian)?
- Any existing 3D asset packs/licenses available, or do we source/commission the café library?
- Budget tolerance per upload for AI calls (affects how aggressively we cache / batch)?
- Hosting target (Vercel for frontend + a Python host for the API; or a single cloud)?
- Does the investor upload tend to be a single image or a full PDF set? (Affects phase priority.)

---

*This document is the build guide. It will evolve as phases complete.*
