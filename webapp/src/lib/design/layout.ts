// AI-assisted layout pass: decides which model each fixture uses and which way it faces,
// and drops toilets/sinks into WC rooms. The deterministic layer here always runs (no API
// key needed); the AI step in anthropic.ts refines model choice + facing on top of it.
//
// All math is 2D in PLAN space (x right, y up-the-page). Facing follows CAFESCENE_SCHEMA
// §1.1: rotation 0 => the fixture's front faces plan +Y, CCW positive.

import type { CafeScene, Fixture, FixtureCategory, Room, Vec2 } from "@/types/cafescene";
import { VARIANTS_BY_CATEGORY } from "./models";

// ---------- small 2D helpers ----------
const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]];
const len = (v: Vec2) => Math.hypot(v[0], v[1]);
const norm = (v: Vec2): Vec2 => {
  const l = len(v) || 1;
  return [v[0] / l, v[1] / l];
};
const dot = (a: Vec2, b: Vec2) => a[0] * b[0] + a[1] * b[1];

/** Degrees so the fixture's front faces `dir` (front is +Y at rotation 0, CCW positive). */
export function facingDeg(dir: Vec2): number {
  const d = norm(dir);
  let deg = (Math.atan2(-d[0], d[1]) * 180) / Math.PI;
  deg = Math.round(deg);
  if (deg <= -180) deg += 360;
  if (deg > 180) deg -= 360;
  return deg;
}

function closestPointOnSeg(p: Vec2, a: Vec2, b: Vec2): { pt: Vec2; d: number; t: number } {
  const ab = sub(b, a);
  const l2 = ab[0] * ab[0] + ab[1] * ab[1] || 1e-9;
  let t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / l2;
  t = Math.max(0, Math.min(1, t));
  const pt: Vec2 = [a[0] + ab[0] * t, a[1] + ab[1] * t];
  return { pt, d: len(sub(p, pt)), t };
}

export function polyCentroid(poly: Vec2[]): Vec2 {
  let x = 0, y = 0, a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x0, y0] = poly[i];
    const [x1, y1] = poly[(i + 1) % poly.length];
    const cr = x0 * y1 - x1 * y0;
    a += cr;
    x += (x0 + x1) * cr;
    y += (y0 + y1) * cr;
  }
  if (Math.abs(a) < 1e-9) {
    // degenerate: average of vertices
    const n = poly.length || 1;
    return [poly.reduce((s, p) => s + p[0], 0) / n, poly.reduce((s, p) => s + p[1], 0) / n];
  }
  a *= 0.5;
  return [x / (6 * a), y / (6 * a)];
}

function pointInPoly(poly: Vec2[], x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    const hit = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi;
    if (hit) inside = !inside;
  }
  return inside;
}

function roomOf(scene: CafeScene, f: Fixture): Room | undefined {
  if (f.roomId) {
    const r = scene.rooms.find((r) => r.id === f.roomId);
    if (r) return r;
  }
  return scene.rooms.find((r) => r.polygon.length >= 3 && pointInPoly(r.polygon, f.position[0], f.position[1]));
}

/** Inward normal of the wall nearest to `p`, pointing toward `toward` (room centroid). */
function nearestWallInwardNormal(
  scene: CafeScene,
  p: Vec2,
  toward?: Vec2,
): { normal: Vec2; dist: number } | null {
  let best: { a: Vec2; b: Vec2; d: number; pt: Vec2 } | null = null;
  for (const w of scene.walls) {
    const c = closestPointOnSeg(p, w.a, w.b);
    if (!best || c.d < best.d) best = { a: w.a, b: w.b, d: c.d, pt: c.pt };
  }
  if (!best) return null;
  const dir = norm(sub(best.b, best.a));
  let n: Vec2 = [-dir[1], dir[0]];
  const ref = toward ?? p;
  if (dot(n, sub(ref, best.pt)) < 0) n = [-n[0], -n[1]];
  return { normal: n, dist: best.d };
}

function nearestTable(scene: CafeScene, f: Fixture, maxDist: number): Fixture | null {
  let best: { fx: Fixture; d: number } | null = null;
  for (const o of scene.fixtures) {
    if (o.category !== "table" || o.id === f.id) continue;
    const d = len(sub(o.position, f.position));
    if (d <= maxDist && (!best || d < best.d)) best = { fx: o, d };
  }
  return best?.fx ?? null;
}

// categories that back onto a wall and face into the room
const WALL_BACKED = new Set<FixtureCategory>([
  "counter", "cashier", "fridge", "freezer", "ice_maker", "espresso_machine", "grinder",
  "oven", "sink", "dishwasher", "boiler", "blender", "mixer", "shelving", "display_case",
  "cooling_case", "menu_board", "signage", "monitor", "toilet", "sofa", "banquette",
]);
const SEATING = new Set<FixtureCategory>(["chair", "stool"]);
// leave these as parsed (orientation is visually irrelevant)
const FREEFORM = new Set<FixtureCategory>(["table", "plant", "umbrella", "pendant_light", "generic"]);

/** Deterministic facing per fixture. Returns { fixtureId: rotationDeg }. */
export function suggestFacing(scene: CafeScene): Record<string, number> {
  const out: Record<string, number> = {};
  for (const f of scene.fixtures) {
    if (FREEFORM.has(f.category)) continue;
    const room = roomOf(scene, f);
    const centroid = room ? polyCentroid(room.polygon) : undefined;

    if (SEATING.has(f.category)) {
      const t = nearestTable(scene, f, 2.4);
      if (t) {
        out[f.id] = facingDeg(sub(t.position, f.position));
        continue;
      }
      const wall = nearestWallInwardNormal(scene, f.position, centroid);
      if (wall && wall.dist < 0.9) out[f.id] = facingDeg(wall.normal);
      else if (centroid) out[f.id] = facingDeg(sub(centroid, f.position));
      continue;
    }

    if (WALL_BACKED.has(f.category)) {
      const wall = nearestWallInwardNormal(scene, f.position, centroid);
      if (wall) out[f.id] = facingDeg(wall.normal);
      else if (centroid) out[f.id] = facingDeg(sub(centroid, f.position));
    }
  }
  return out;
}

const WC_CATS = new Set(["wc", "wc_disabled"]);

/** Add a toilet (+ basin) to any WC room that doesn't already have one. */
export function insertWcFixtures(scene: CafeScene): Fixture[] {
  const added: Fixture[] = [];
  for (const room of scene.rooms) {
    if (!WC_CATS.has(room.category) || room.polygon.length < 3) continue;
    const already = scene.fixtures.some(
      (f) => f.category === "toilet" && (f.roomId === room.id || pointInPoly(room.polygon, f.position[0], f.position[1])),
    );
    if (already) continue;

    const c = polyCentroid(room.polygon);
    // edges, longest first
    const edges = room.polygon.map((a, i) => {
      const b = room.polygon[(i + 1) % room.polygon.length];
      return { a, b, mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] as Vec2, L: len(sub(b, a)) };
    }).sort((x, y) => y.L - x.L);
    if (!edges.length || edges[0].L < 0.9) continue;

    const place = (edge: typeof edges[number], off: number): { pos: Vec2; rot: number } => {
      const dir = norm(sub(edge.b, edge.a));
      let n: Vec2 = [-dir[1], dir[0]];
      if (dot(n, sub(c, edge.mid)) < 0) n = [-n[0], -n[1]];
      return { pos: [edge.mid[0] + n[0] * off, edge.mid[1] + n[1] * off], rot: facingDeg(n) };
    };

    const t = place(edges[0], 0.45);
    added.push(mkFixture(`fx_wc_toilet_${room.id}`, "WC toilet", "toilet", room.id, t.pos, t.rot, [0.6, 0.7], 0.7));
    // basin on a different wall if the room has one long enough
    const sinkEdge = edges.find((e) => e !== edges[0] && e.L >= 0.7) ?? null;
    if (sinkEdge) {
      const s = place(sinkEdge, 0.3);
      added.push(mkFixture(`fx_wc_sink_${room.id}`, "WC basin", "sink", room.id, s.pos, s.rot, [0.5, 0.4], 0.85, "bathroom_sink"));
    }
  }
  return added;
}

function mkFixture(
  id: string, name: string, category: FixtureCategory, roomId: string,
  position: Vec2, rotation: number, footprint: Vec2, height: number, modelKey?: string,
): Fixture {
  return {
    id, name, category, roomId, position, rotation, footprint, height, modelKey,
    placedBy: "design", confidence: 0.6, source: { system: 2, method: "design" },
  };
}

// ---------- AI context + apply ----------
export interface LayoutItemCtx {
  id: string;
  name: string;
  category: FixtureCategory;
  room: string; // room category
  pos: [number, number];
  footprint: [number, number];
  suggestedRotation: number; // deterministic facing, degrees
  variants: string[]; // allowed modelKeys (empty = no choice)
}

/** Compact per-fixture context for the AI prompt. Includes the deterministic rotation hint. */
export function buildLayoutContext(scene: CafeScene): LayoutItemCtx[] {
  const facing = suggestFacing(scene);
  return scene.fixtures.map((f) => {
    const room = roomOf(scene, f);
    return {
      id: f.id,
      name: f.name,
      category: f.category,
      room: room?.category ?? "other",
      pos: [round2(f.position[0]), round2(f.position[1])],
      footprint: [round2(f.footprint[0]), round2(f.footprint[1])],
      suggestedRotation: facing[f.id] ?? f.rotation,
      variants: VARIANTS_BY_CATEGORY[f.category] ?? [],
    };
  });
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export interface LayoutResult {
  rotations: Record<string, number>;
  models: Record<string, string>;
}

/** Apply a layout result + deterministic WC additions to produce a new scene. */
export function applyLayout(scene: CafeScene, result: LayoutResult): CafeScene {
  const fixtures = scene.fixtures.map((f) => {
    const next = { ...f };
    if (result.rotations[f.id] != null && Number.isFinite(result.rotations[f.id])) {
      next.rotation = result.rotations[f.id];
    }
    const mk = result.models[f.id];
    if (mk && (VARIANTS_BY_CATEGORY[f.category] ?? []).includes(mk)) next.modelKey = mk;
    return next;
  });
  const added = insertWcFixtures(scene);
  return { ...scene, fixtures: [...fixtures, ...added] };
}

/** The deterministic-only result (used as a fallback when the AI call is unavailable). */
export function deterministicResult(scene: CafeScene): LayoutResult {
  return { rotations: suggestFacing(scene), models: {} };
}
