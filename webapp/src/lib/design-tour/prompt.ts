// Prompt for the AI design-tour generator: Claude writes a complete, self-contained walkable
// three.js tour of the café from the floor plan (+ parsed plan data + interior references), the
// same way the reference tour was produced on claude.ai. The exemplar HTML is appended to the
// system prompt so the model matches its architecture, polish and depth.

import { readFile } from "node:fs/promises";
import path from "node:path";
import type { CafeScene } from "@/types/cafescene";

export const DESIGN_TOUR_SYSTEM = `You are CaféVision's lead interior designer and three.js engineer. A client uploads a café floor plan (and optionally interior reference images and a brief). You design the café and deliver a WALKABLE VIRTUAL TOUR of it as one self-contained HTML file.

THE DELIVERABLE
- Exactly one complete HTML document. Start with <!DOCTYPE html> and end with </html>. No markdown fences, no commentary before or after, no placeholders or TODOs.
- Only external dependencies: three.js r128 from https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js and Google Fonts. Everything else inline. All textures, logos, menus and signage are drawn procedurally on canvas (no image files).
- Size: roughly 60–110 KB of code. Write real, runnable code: every variable defined before use, balanced braces, no syntax errors. Re-read your code mentally for undefined identifiers before finishing.

THE CAFÉ (model the client's plan, not a generic shop)
- Coordinates in metres taken from the plan. Use the parsed plan data when given (plan x → world x, plan y → world −z, y up): the room outline, every wall with its openings, and the legend equipment list. Where the drawing and the parsed data disagree, trust the drawing.
- Build the architecture: floor slab per room with the right material, ceiling with recessed downlights, walls with doors and glazing (storefront glass with dark frames and mullions), the outside context the plan implies (pavement/street, terrace with balustrade and planters and branded umbrellas, or a mall concourse with its fascia and shutter line).
- Design bespoke built-ins instead of placing generic furniture: the service counter run (stone/terrazzo tops, timber or slatted fronts, LED kick), back bar with shelving full of cups and bottles under LED strips, espresso station with the specified machine and grinders, pastry and grab-and-go displays with food inside, self-order kiosks, retail wall with products, menu screens, banquettes, tables and chairs sized and arranged for the room, plants, pendants, wall art or a quote wall, the café's wordmark drawn as a canvas texture on fascia, umbrellas and signage.
- Place every legend item (each numbered piece of equipment) where the plan puts it.
- Materials with real detail: procedural terrazzo, wood grain, plaster, fabric, metal (MeshStandardMaterial with roughness/metalness, envMapIntensity, a PMREM environment), emissive LED strips and lamp opals. Lighting: directional sun with shadows, hemisphere, warm interior point lights, ACES tone mapping. Follow the client's references and brief for palette and mood; otherwise choose a coherent designer palette.

THE TOUR (match the reference implementation feature-for-feature)
- First-person camera at 1.6 m: drag to look, W A S D / arrows (Shift = faster), click the floor to walk there, wheel = zoom, touch joystick on coarse pointers, gentle head-bob with prefers-reduced-motion respected.
- Collision: walkable zones + blocking boxes so the visitor cannot pass through walls, counters or furniture, and walks through doors.
- 6–10 numbered stops in a sensible route (arrival outside → entrance → each zone → back of house where relevant), each with a short title and 1–2 sentence story card in the voice of a designer presenting the concept. "Play tour" flies along the route through the doors, pausing at each stop; any user input pauses it.
- Mini-map (canvas) with the plan outline, furniture, numbered stops, the visitor's position and view cone; click the map to walk there. Hide/show map.
- Day / Evening toggle that changes sky, sun, interior lights, LED and sign emissives and exposure.
- Bronze "+" hotspot markers on key design details that open a detail card (title + one or two sentences of design specification).
- Ident card (café name, site/concept line, "You're in the …" updated by zone), controls help sheet shown on load with "Explore freely" / "Play tour", toasts for blocked clicks, loading screen while textures build.
- Light/dark colour scheme via CSS variables and prefers-color-scheme; mobile-safe layout.

QUALITY BAR: the result must look like a designer's presentation model — considered proportions, consistent materials, generous detail (cups on shelves, products on retail, pastries in displays, umbrella graphics, menu text), nothing floating or intersecting, nothing left as a plain grey box.`;

/** Appended after the system text: the reference implementation to match (a different café). */
export async function loadExemplar(): Promise<string> {
  const p = path.join(process.cwd(), "prompts", "tour-exemplar.html");
  return readFile(p, "utf8");
}

/** Compact, prompt-friendly view of the parsed plan (drops provenance/confidence/ids). */
export function compactScene(scene: CafeScene): string {
  const r2 = (n: number) => Math.round(n * 100) / 100;
  const v = (p: [number, number]) => [r2(p[0]), r2(p[1])];
  const out = {
    project: { name: scene.project.name, units: scene.project.units },
    legend: scene.legend.map((l) => ({ no: l.no, name: l.name, category: l.category })),
    rooms: scene.rooms.map((r) => ({ id: r.id, name: r.name, category: r.category, ceilingHeight: r.ceilingHeight, polygon: r.polygon.map(v) })),
    walls: scene.walls.map((w) => ({ id: w.id, a: v(w.a), b: v(w.b), thickness: r2(w.thickness), height: r2(w.height), exterior: !!w.exterior })),
    openings: scene.openings.map((o) => ({ type: o.type, wallId: o.wallId, offset: r2(o.offset), width: r2(o.width), height: r2(o.height), sillHeight: o.sillHeight })),
    fixtures: scene.fixtures.slice(0, 140).map((f) => ({
      name: f.name,
      category: f.category,
      legendNo: f.legendNo,
      position: v(f.position),
      rotation: Math.round(f.rotation),
      footprint: v(f.footprint),
      height: f.height ? r2(f.height) : undefined,
      baseHeight: f.baseHeight ? r2(f.baseHeight) : undefined,
      placedBy: f.placedBy,
    })),
  };
  return JSON.stringify(out);
}

export function buildUserText(opts: { projectName: string; brief?: string; sceneJson?: string; hasPlanImages: boolean; refCount: number }): string {
  const parts: string[] = [];
  parts.push(`CLIENT: ${opts.projectName}.`);
  if (opts.brief?.trim()) parts.push(`BRIEF FROM THE CLIENT:\n${opts.brief.trim()}`);
  if (opts.hasPlanImages) parts.push(`The floor plan page(s) are attached above. Read the dimensions, room labels, legend and numbered equipment positions from them.`);
  if (opts.refCount) parts.push(`${opts.refCount} interior reference image(s) are attached above: match their material palette, furniture language and mood.`);
  if (opts.sceneJson) parts.push(`PARSED PLAN DATA (metres; plan x right, plan y up the page; world z = −y). Fixtures marked placedBy "design" were auto-furnished and may be moved or replaced, "parse" items come from the drawing:\n${opts.sceneJson}`);
  parts.push(`Now design this café and write the complete walkable tour HTML. Output only the HTML document.`);
  return parts.join("\n\n");
}
