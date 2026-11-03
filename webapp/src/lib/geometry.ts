// Geometry helpers for the 3D Rendering Engine (System 3).
// All plan->world conversion lives here and NOWHERE else (see CAFESCENE_SCHEMA.md 1.2).
//
//   worldX = planX
//   worldY = height above floor
//   worldZ = -planY

import * as THREE from "three";
import type { Fixture, FixtureCategory, Opening, Vec2, Wall } from "@/types/cafescene";

/** Convert a plan point + height to a world-space Vector3. */
export function planToWorld(x: number, y: number, h = 0): THREE.Vector3 {
  return new THREE.Vector3(x, h, -y);
}

/** Rotation about world Y so a group's local +X points along a plan direction a->b. */
export function wallAngleY(a: Vec2, b: Vec2): number {
  return Math.atan2(b[1] - a[1], b[0] - a[0]);
}

export function wallLength(a: Vec2, b: Vec2): number {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

/** A single box of wall, expressed in wall-local coords (x along wall, y up, z = thickness). */
export interface WallBox {
  /** center position along the wall (local x), meters from wall.a */
  u: number;
  /** center height (local y), meters */
  yCenter: number;
  /** length along the wall */
  length: number;
  /** vertical extent */
  height: number;
  kind: "solid" | "header" | "sill";
}

/** Glass pane spec (for windows), wall-local. */
export interface GlassPane {
  u: number;
  yCenter: number;
  width: number;
  height: number;
}

/**
 * Split a wall into solid boxes around its openings. Doors/openings leave a gap
 * (with a header above); windows add a sill below and a header above + a glass pane.
 */
export function buildWallBoxes(
  wall: Wall,
  openings: Opening[],
): { boxes: WallBox[]; glass: GlassPane[] } {
  const L = wallLength(wall.a, wall.b);
  const H = wall.height;
  const boxes: WallBox[] = [];
  const glass: GlassPane[] = [];

  const sorted = [...openings]
    .filter((o) => o.wallId === wall.id)
    .sort((a, b) => a.offset - b.offset);

  let cursor = 0;
  for (const op of sorted) {
    const start = Math.max(0, op.offset);
    const end = Math.min(L, op.offset + op.width);
    const w = Math.max(0, end - start);
    if (w <= 0) continue;

    // solid segment before this opening
    if (start > cursor + 1e-4) {
      const segLen = start - cursor;
      boxes.push({
        u: cursor + segLen / 2,
        yCenter: H / 2,
        length: segLen,
        height: H,
        kind: "solid",
      });
    }

    const sill = op.type === "window" ? op.sillHeight ?? 0.9 : 0;
    const openTop = sill + op.height;

    // sill (below window)
    if (sill > 1e-4) {
      boxes.push({
        u: start + w / 2,
        yCenter: sill / 2,
        length: w,
        height: sill,
        kind: "sill",
      });
    }
    // header (above opening)
    if (H - openTop > 1e-4) {
      boxes.push({
        u: start + w / 2,
        yCenter: openTop + (H - openTop) / 2,
        length: w,
        height: H - openTop,
        kind: "header",
      });
    }
    // glass for windows
    if (op.type === "window") {
      glass.push({ u: start + w / 2, yCenter: sill + op.height / 2, width: w, height: op.height });
    }

    cursor = Math.max(cursor, end);
  }

  // trailing solid segment
  if (cursor < L - 1e-4) {
    const segLen = L - cursor;
    boxes.push({
      u: cursor + segLen / 2,
      yCenter: H / 2,
      length: segLen,
      height: H,
      kind: "solid",
    });
  }

  return { boxes, glass };
}

/** Build a flat THREE.Shape from a plan polygon (used for floors/ceilings). */
export function roomShape(polygon: Vec2[]): THREE.Shape {
  const shape = new THREE.Shape();
  polygon.forEach((p, i) => {
    if (i === 0) shape.moveTo(p[0], p[1]);
    else shape.lineTo(p[0], p[1]);
  });
  shape.closePath();
  return shape;
}

/** Centroid of a plan polygon (for labels / camera targeting). */
export function polygonCentroid(polygon: Vec2[]): Vec2 {
  let x = 0;
  let y = 0;
  for (const p of polygon) {
    x += p[0];
    y += p[1];
  }
  return [x / polygon.length, y / polygon.length];
}

/** Default vertical extent (m) per fixture category when height is unspecified. */
export const DEFAULT_HEIGHTS: Record<FixtureCategory, number> = {
  counter: 1.05,
  espresso_machine: 0.55,
  grinder: 0.5,
  display_case: 0.6,
  cooling_case: 1.2,
  fridge: 1.9,
  freezer: 0.9,
  ice_maker: 0.8,
  sink: 0.9,
  dishwasher: 0.85,
  oven: 0.9,
  boiler: 0.5,
  blender: 0.45,
  mixer: 0.5,
  monitor: 0.6,
  table: 0.74,
  chair: 0.9,
  stool: 0.75,
  sofa: 0.8,
  banquette: 0.95,
  shelving: 1.8,
  menu_board: 0.9,
  signage: 0.5,
  plant: 1.1,
  pendant_light: 0.3,
  umbrella: 2.4,
  cashier: 1.1,
  toilet: 0.75,
  generic: 0.8,
};

/** Placeholder color per fixture category (Phase 1; real glTF assets come in Phase 4). */
export const CATEGORY_COLORS: Record<FixtureCategory, string> = {
  counter: "#b07c46",
  espresso_machine: "#8d9094",
  grinder: "#6f7276",
  display_case: "#c9d3d6",
  cooling_case: "#c4ced1",
  fridge: "#aeb4b8",
  freezer: "#aeb4b8",
  ice_maker: "#9aa0a4",
  sink: "#b9bec1",
  dishwasher: "#a7adb1",
  oven: "#6a6d71",
  boiler: "#7c7f83",
  blender: "#7c7f83",
  mixer: "#7c7f83",
  monitor: "#2a2d30",
  table: "#9a6b3c",
  chair: "#3f4347",
  stool: "#4a4e52",
  sofa: "#6b5744",
  banquette: "#6b5744",
  shelving: "#8a6a44",
  menu_board: "#cbb893",
  signage: "#2f3335",
  plant: "#4e7a46",
  pendant_light: "#2d2f31",
  umbrella: "#7d7a72",
  cashier: "#8a6a44",
  toilet: "#e8eaec",
  generic: "#999999",
};

export function fixtureHeight(f: Fixture): number {
  // treat 0 / missing / negative as "unspecified" and fall back to a category default
  if (f.height && f.height > 0.01) return f.height;
  return DEFAULT_HEIGHTS[f.category] ?? 0.8;
}

/** Ray-cast point-in-polygon test (plan space). */
export function pointInPolygon(poly: Vec2[], x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0];
    const yi = poly[i][1];
    const xj = poly[j][0];
    const yj = poly[j][1];
    const denom = yj - yi || 1e-9;
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / denom + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export interface SceneFraming {
  /** orbit target in world space */
  target: [number, number, number];
  /** a good initial camera position in world space */
  camera: [number, number, number];
  /** world-space center at floor level */
  center: [number, number, number];
  /** largest plan extent (meters) */
  span: number;
}

/** Compute a camera + target that frames the whole scene, from walls and room polygons. */
export function frameScene(opts: {
  walls: { a: Vec2; b: Vec2 }[];
  rooms: { polygon: Vec2[] }[];
}): SceneFraming {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const consider = (x: number, y: number) => {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  };
  for (const w of opts.walls) {
    consider(w.a[0], w.a[1]);
    consider(w.b[0], w.b[1]);
  }
  for (const r of opts.rooms) for (const p of r.polygon) consider(p[0], p[1]);

  if (!isFinite(minX)) {
    // empty scene fallback
    return { target: [0, 1, 0], camera: [10, 8, 12], center: [0, 0, 0], span: 10 };
  }

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const span = Math.max(maxX - minX, maxY - minY, 4);

  // world: worldX = x, worldZ = -y
  const target: [number, number, number] = [cx, 1.1, -cy];
  const d = span * 1.05;
  const camera: [number, number, number] = [cx + d * 0.75, span * 0.7 + 3, -cy + d * 0.95];
  return { target, camera, center: [cx, 0, -cy], span };
}
