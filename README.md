# CaféVision — AI 2D Floor Plan → Realistic 3D Café

Upload a 2D coffee-shop floor plan and get an **interactive, furnished 3D café** you can walk
through — the AI reads the walls, rooms, doors and equipment, reconstructs the space, designs the
interior, and renders it in the browser.

> Upload a 2D plan → AI understands it → structured 3D scene → AI interior design → explore in 3D.

## The three independent systems

1. **Architectural Intelligence** — understands the plan and produces accurate geometry.
2. **Interior Design Intelligence** — decides style, materials, furniture and lighting.
3. **3D Rendering Engine** — turns the structured scene into an interactive 3D environment.

They communicate only through one data contract, [`CaféScene`](./CAFESCENE_SCHEMA.md).

## Features

- **AI parsing** of a floor-plan image into structured geometry (Claude vision) — walls, rooms,
  openings, equipment (from the legend), heights, with per-element confidence.
- **Geometry regularization** — snaps near-axis walls and aligns shared coordinates.
- **Verify & correct editor** — fix walls/scale/fixtures in a 2D plan view before rendering.
- **Interior design** — style presets + AI style selection; auto materials, furniture and lighting.
- **Walkable 3D** — orbit + first-person walk, click to inspect fixtures.
- **Render/export** — isometric "dollhouse" view, PNG export, and a gated hook for AI-photoreal
  rendering (needs an image-generation key — Claude does not generate images).

## Tech stack

- **Frontend / app:** Next.js 16 (App Router) + React 19 + TypeScript
- **3D:** three.js + React-Three-Fiber + drei
- **AI:** Anthropic Claude (vision) via `@anthropic-ai/sdk`
- **Image handling:** sharp

## Getting started

```bash
cd webapp
npm install
# create webapp/.env.local with your key:
#   ANTHROPIC_API_KEY=sk-ant-...
npm run dev        # http://localhost:3000
```

For a demo build: `npm run build && npm start`.

### Environment variables (`webapp/.env.local`)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for parsing (`/api/parse`) and AI design (`/api/design`) |
| `ANTHROPIC_MODEL` | Optional, defaults to `claude-opus-5-5` |
| `ANTHROPIC_EFFORT` | Optional parsing effort (`low`/`medium`/`high`), default `medium` |
| `ANTHROPIC_MAX_TOKENS` | Optional, default `40000` |
| `FAL_KEY` / `REPLICATE_API_TOKEN` / `STABILITY_API_KEY` | Optional — enables AI-photoreal rendering (see `src/lib/render/photoreal.ts`) |

## Documentation

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system design, pipeline, decisions.
- [`CAFESCENE_SCHEMA.md`](./CAFESCENE_SCHEMA.md) — the shared data contract (v1.0).
- [`BUILD_PHASES.md`](./BUILD_PHASES.md) — build phases and status.

## Notes

- `clientsDocs/`, `FloorPlans/` and reference images are intentionally **not** committed (client
  material / large assets). The app ships a pre-parsed sample scene for demos.
