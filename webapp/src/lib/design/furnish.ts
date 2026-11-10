// Room-aware auto-furnishing: reads each room's category and fills in the equipment that belongs
// there (kitchen → stove/fridge/hood…, WC → toilet/basin/mirror, seating → chairs around every
// table, service counter → espresso machine/grinder/POS on the counter, etc.).
//
// Hybrid design: templates below decide WHAT goes in a room; the geometry here decides WHERE —
// wall-lining with clearance + facing, seating clusters, counter-top placement, corner props —
// while avoiding overlaps with fixtures the parser already placed. All math is 2D in PLAN space.

import type { CafeScene, Fixture, FixtureCategory, Room, Vec2 } from "@/types/cafescene";
import { facingDeg, polyCentroid } from "./layout";

// ---- vec helpers ----
const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]];
const add = (a: Vec2, b: Vec2): Vec2 => [a[0] + b[0], a[1] + b[1]];
const mul = (a: Vec2, s: number): Vec2 => [a[0] * s, a[1] * s];
const len = (v: Vec2) => Math.hypot(v[0], v[1]);
const norm = (v: Vec2): Vec2 => { const l = len(v) || 1; return [v[0] / l, v[1] / l]; };
const dot = (a: Vec2, b: Vec2) => a[0] * b[0] + a[1] * b[1];

function pointInPoly(poly: Vec2[], x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside;
  }
  return inside;
}

// ---- occupancy (circle approximation, rotation-agnostic) ----
interface Disc { x: number; y: number; r: number }
const discOf = (pos: Vec2, w: number, d: number): Disc => ({ x: pos[0], y: pos[1], r: 0.5 * Math.max(w, d) });
function hits(c: Disc, occ: Disc[], k = 0.8): boolean {
  for (const o of occ) if (Math.hypot(c.x - o.x, c.y - o.y) < (c.r + o.r) * k) return true;
  return false;
}

interface Edge { a: Vec2; b: Vec2; dir: Vec2; n: Vec2; len: number }
function roomEdges(room: Room): Edge[] {
  const c = polyCentroid(room.polygon);
  const out: Edge[] = [];
  for (let i = 0; i < room.polygon.length; i++) {
    const a = room.polygon[i], b = room.polygon[(i + 1) % room.polygon.length];
    const dir = norm(sub(b, a));
    let n: Vec2 = [-dir[1], dir[0]];
    const mid: Vec2 = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if (dot(n, sub(c, mid)) < 0) n = [-n[0], -n[1]];
    out.push({ a, b, dir, n, len: len(sub(b, a)) });
  }
  return out.sort((x, y) => y.len - x.len);
}

function roomFixtures(scene: CafeScene, room: Room): Fixture[] {
  return scene.fixtures.filter(
    (f) => f.roomId === room.id || pointInPoly(room.polygon, f.position[0], f.position[1]),
  );
}

// ---- item spec + fixture factory ----
interface Item {
  key: string;        // MODEL_CATALOG key
  cat: FixtureCategory; // for material enhancement / height defaults
  w: number; d: number; h: number;
  base?: number;      // baseHeight (wall-mounted / on-counter)
  gap?: number;       // extra spacing after this item along a wall
  name: string;
}
let _seq = 0;
function mkProp(it: Item, roomId: string, pos: Vec2, rot: number, base = it.base ?? 0): Fixture {
  return {
    id: `fx_furn_${roomId}_${it.key}_${_seq++}`,
    name: it.name,
    category: it.cat,
    roomId,
    position: [round2(pos[0]), round2(pos[1])],
    rotation: Math.round(rot),
    footprint: [it.w, it.d],
    height: it.h,
    baseHeight: base,
    modelKey: it.key || undefined,
    placedBy: "design",
    confidence: 0.6,
    source: { system: 2, method: "design" },
  };
}
const round2 = (n: number) => Math.round(n * 100) / 100;

/** Keep only items whose category the room doesn't already have (generic props always pass). */
const onlyMissing = (its: Item[], have: Set<FixtureCategory>) =>
  its.filter((it) => it.cat === "generic" || !have.has(it.cat));

// ---- placement primitives ----
function lineAlongWalls(room: Room, items: Item[], occ: Disc[], out: Fixture[]) {
  const edges = roomEdges(room);
  const cursor = edges.map(() => 0.3); // start inset from the corner
  for (const it of items) {
    // choose the edge with the most remaining room
    let bi = -1, bestRem = it.w;
    edges.forEach((e, i) => {
      const rem = e.len - 0.3 - cursor[i];
      if (rem >= it.w && rem > bestRem) { bestRem = rem; bi = i; }
    });
    if (bi < 0) continue;
    const e = edges[bi];
    let tries = 0;
    while (cursor[bi] + it.w <= e.len - 0.3 && tries < 40) {
      const t = cursor[bi] + it.w / 2;
      const inset = it.d / 2 + 0.04;
      const pos = add(add(e.a, mul(e.dir, t)), mul(e.n, inset));
      const disc = discOf(pos, it.w, it.d);
      if (pointInPoly(room.polygon, pos[0], pos[1]) && !hits(disc, occ)) {
        out.push(mkProp(it, room.id, pos, facingDeg(e.n)));
        occ.push(disc);
        cursor[bi] = t + it.w / 2 + (it.gap ?? 0.18);
        break;
      }
      cursor[bi] += 0.22; tries++;
    }
  }
}

// ---- clean per-table seating ----
/** Candidate seat positions + facings around one table, evenly spaced and tucked in. */
function tableSeats(t: Fixture): { pos: Vec2; rot: number }[] {
  const [w, d] = t.footprint;
  const cx = t.position[0], cy = t.position[1];
  const big = Math.max(w, d), small = Math.min(w, d);
  const seatGap = 0.3; // chair seat pulled this far off the table edge
  const out: { pos: Vec2; rot: number }[] = [];
  const rectangular = big - small > 0.35;

  if (!rectangular) {
    // round / square: evenly spaced around the perimeter, facing the centre
    const n = big <= 0.85 ? 2 : big <= 1.2 ? 4 : big <= 1.7 ? 6 : 8;
    const r = big / 2 + seatGap;
    for (let i = 0; i < n; i++) {
      const a = Math.PI / 2 + (2 * Math.PI * i) / n; // start at the far side
      const pos: Vec2 = [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
      out.push({ pos, rot: facingDeg([cx - pos[0], cy - pos[1]]) });
    }
    return out;
  }

  // rectangular: chairs along both long sides, spaced ~0.62 m; ends if long enough
  const alongX = w >= d;
  const L = alongX ? w : d, offLong = (alongX ? d : w) / 2 + seatGap;
  const per = Math.max(1, Math.round((L - 0.1) / 0.62));
  for (let s = -1; s <= 1; s += 2) {
    for (let i = 0; i < per; i++) {
      const f = per === 1 ? 0 : i / (per - 1) - 0.5;
      const along = f * (L - 0.35);
      const pos: Vec2 = alongX ? [cx + along, cy + s * offLong] : [cx + s * offLong, cy + along];
      out.push({ pos, rot: facingDeg(alongX ? [0, -s] : [-s, 0]) });
    }
  }
  if (L > 1.5) {
    const offEnd = (alongX ? w : d) / 2 + seatGap;
    for (let e = -1; e <= 1; e += 2) {
      const pos: Vec2 = alongX ? [cx + e * offEnd, cy] : [cx, cy + e * offEnd];
      out.push({ pos, rot: facingDeg(alongX ? [-e, 0] : [0, -e]) });
    }
  }
  return out;
}

/**
 * Drop all parsed chairs (they arrive scattered/overlapping) and regenerate one tidy, tucked-in
 * cluster per table. Bar stools and everything else are kept as-is. Returns a new scene.
 */
export function rearrangeSeating(scene: CafeScene): CafeScene {
  // The plan's own chairs are the client's layout: keep them (dropping only exact duplicates and chairs that sit
  // inside a table). Chairs are generated ONLY for tables the parser drew no seats for. (This used to drop every
  // parsed chair and regenerate them, which halved the indoor seating and scrambled the terrace.)
  const tablesAll = scene.fixtures.filter((f) => f.category === "table");
  const insideTable = (p: [number, number]) => tablesAll.some((t) => {
    const [w, d] = t.footprint;
    const r = ((t.rotation ?? 0) * Math.PI) / 180;
    const dx = p[0] - t.position[0], dy = p[1] - t.position[1];
    const lx = dx * Math.cos(r) + dy * Math.sin(r), ly = -dx * Math.sin(r) + dy * Math.cos(r);
    return Math.abs(lx) < w / 2 - 0.05 && Math.abs(ly) < d / 2 - 0.05;
  });
  const planChairs: Fixture[] = [];
  for (const c of scene.fixtures) {
    if (c.category !== "chair") continue;
    if (insideTable(c.position)) continue;
    if (planChairs.some((k) => Math.hypot(k.position[0] - c.position[0], k.position[1] - c.position[1]) < 0.3)) continue;
    planChairs.push(c);
  }
  // The parser's chair rotations are unreliable (it reads position well, direction badly): turn every plan chair and
  // stool to face the closest point of its nearest table, and give terrace chairs and stools the client's outdoor
  // models (Balfour chair / bar stool) instead of the indoor Pasadena ones.
  const nearestTable = (p: Vec2): Fixture | undefined => {
    let best: Fixture | undefined, bd = 1.4;
    for (const t of tablesAll) {
      const [w, d] = t.footprint;
      const dd = Math.hypot(Math.max(Math.abs(p[0] - t.position[0]) - w / 2, 0), Math.max(Math.abs(p[1] - t.position[1]) - d / 2, 0));
      if (dd < bd) { best = t; bd = dd; }
    }
    return best;
  };
  const isOutdoorAt = (f: Fixture) => {
    const room = scene.rooms.find((r) => r.id === f.roomId) ??
      scene.rooms.find((r) => r.polygon.length >= 3 && pointInPoly(r.polygon, f.position[0], f.position[1]));
    return room?.category === "seating_outdoor";
  };
  const aimed = (c: Fixture): Fixture => {
    const t = nearestTable(c.position);
    const next: Fixture = { ...c };
    if (t) {
      const [w, d] = t.footprint;
      let px = Math.min(Math.max(c.position[0], t.position[0] - w / 2), t.position[0] + w / 2);
      let py = Math.min(Math.max(c.position[1], t.position[1] - d / 2), t.position[1] + d / 2);
      if (Math.hypot(px - c.position[0], py - c.position[1]) < 1e-3) [px, py] = t.position;
      next.rotation = facingDeg([px - c.position[0], py - c.position[1]]);
    }
    if (isOutdoorAt(c)) next.modelKey = c.category === "chair" ? "cafe_chair_outdoor" : "cafe_stool_outdoor";
    return next;
  };
  const keep = [
    ...scene.fixtures.filter((f) => f.category !== "chair").map((f) => (f.category === "stool" ? aimed(f) : f)),
    ...planChairs.map(aimed),
  ];
  const occ: Disc[] = keep.map((f) => discOf(f.position, f.footprint[0], f.footprint[1]));
  const seats: Fixture[] = [];
  let i = 0;
  const seatedByPlan = (t: Fixture) => {
    const reach = Math.max(t.footprint[0], t.footprint[1]) / 2 + 0.75;
    return keep.some((c) => (c.category === "chair" || c.category === "stool") &&
      Math.hypot(c.position[0] - t.position[0], c.position[1] - t.position[1]) < reach);
  };
  const roomOfTable = (t: Fixture): Room | undefined =>
    scene.rooms.find((r) => r.id === t.roomId) ??
    scene.rooms.find((r) => r.polygon.length >= 3 && pointInPoly(r.polygon, t.position[0], t.position[1]));

  for (const t of scene.fixtures) {
    if (t.category !== "table" || seatedByPlan(t)) continue;
    const room = roomOfTable(t);
    for (const s of tableSeats(t)) {
      if (room && room.polygon.length >= 3 && !pointInPoly(room.polygon, s.pos[0], s.pos[1])) continue;
      const disc = discOf(s.pos, 0.5, 0.5);
      if (hits(disc, occ, 0.7)) continue;
      seats.push({
        id: `fx_seat_${i++}`,
        name: "Chair",
        category: "chair",
        roomId: room?.id ?? t.roomId,
        position: [round2(s.pos[0]), round2(s.pos[1])],
        rotation: Math.round(s.rot),
        footprint: [0.5, 0.5],
        height: 0.9,
        baseHeight: 0,
        modelKey: room?.category === "seating_outdoor" ? "cafe_chair_outdoor" : "cafe_chair",
        placedBy: "design",
        confidence: 0.6,
        source: { system: 2, method: "design" },
      });
      occ.push(disc);
    }
  }
  return { ...scene, fixtures: [...keep, ...seats] };
}

/** Place small machines on top of existing counters in a room (espresso machine, grinder, POS…). */
function placeOnCounters(scene: CafeScene, room: Room, items: Item[], occ: Disc[], out: Fixture[]) {
  const counters = roomFixtures(scene, room).filter((f) => f.category === "counter" || f.category === "cashier");
  if (!counters.length || !items.length) return;
  const counter = counters.sort((a, b) => b.footprint[0] - a.footprint[0])[0];
  const r = (counter.rotation * Math.PI) / 180;
  const ax: Vec2 = [Math.cos(r), Math.sin(r)]; // counter long axis in plan
  const topBase = counter.height ?? 1.05;
  const span = counter.footprint[0] - 0.3;
  items.forEach((it, i) => {
    const frac = items.length === 1 ? 0 : (i / (items.length - 1) - 0.5);
    const pos: Vec2 = [counter.position[0] + ax[0] * frac * span, counter.position[1] + ax[1] * frac * span];
    const disc = discOf(pos, it.w, it.d);
    out.push(mkProp(it, room.id, pos, counter.rotation, topBase));
    occ.push(disc);
  });
}

function cornerProps(room: Room, items: Item[], occ: Disc[], out: Fixture[]) {
  const c = polyCentroid(room.polygon);
  const verts = room.polygon;
  let vi = 0;
  for (const it of items) {
    // walk corners, pull slightly toward centre
    for (let k = 0; k < verts.length && vi < verts.length; k++, vi++) {
      const v = verts[vi % verts.length];
      const pos: Vec2 = add(v, mul(norm(sub(c, v)), 0.5 + it.w));
      const disc = discOf(pos, it.w, it.d);
      if (pointInPoly(room.polygon, pos[0], pos[1]) && !hits(disc, occ)) {
        out.push(mkProp(it, room.id, pos, facingDeg(sub(c, pos))));
        occ.push(disc);
        vi++;
        break;
      }
    }
  }
}

// ---- item presets ----
const I = {
  stove: { key: "stove", cat: "oven", w: 0.9, d: 0.7, h: 0.9, name: "Oven" } as Item,
  fridge: { key: "cafe_fridge", cat: "fridge", w: 0.7, d: 0.72, h: 1.9, name: "Fridge" } as Item,
  freezer: { key: "cafe_freezer", cat: "freezer", w: 0.7, d: 0.7, h: 1.1, name: "Freezer" } as Item,
  sink: { key: "cafe_sink", cat: "sink", w: 0.6, d: 0.6, h: 0.9, name: "Sink" } as Item,
  dishwasher: { key: "cafe_dishwasher", cat: "dishwasher", w: 0.6, d: 0.6, h: 0.85, name: "Dishwasher" } as Item,
  prepCab: { key: "cafe_counter", cat: "counter", w: 1.0, d: 0.6, h: 0.9, name: "Prep counter" } as Item,
  crockery: { key: "cafe_shelving", cat: "shelving", w: 1.0, d: 0.4, h: 1.8, name: "Crockery shelving" } as Item,
  shelving: { key: "cafe_shelving", cat: "shelving", w: 1.0, d: 0.4, h: 1.8, name: "Shelving" } as Item,
  trashcan: { key: "cafe_waste_bin", cat: "generic", w: 0.5, d: 0.5, h: 0.7, name: "Waste bin" } as Item,
  hood: { key: "hood", cat: "generic", w: 0.9, d: 0.45, h: 0.45, base: 1.5, name: "Extractor hood" } as Item,
  box: { key: "box", cat: "generic", w: 0.45, d: 0.45, h: 0.6, name: "Storage box" } as Item,
  plant: { key: "plant_potted", cat: "plant", w: 0.45, d: 0.45, h: 1.1, name: "Plant" } as Item,
  toilet: { key: "toilet", cat: "toilet", w: 0.65, d: 0.72, h: 0.75, name: "Toilet" } as Item,
  basin: { key: "cafe_handwash_sink", cat: "sink", w: 0.4, d: 0.35, h: 0.85, name: "Hand-wash basin" } as Item,
  mirror: { key: "mirror", cat: "generic", w: 0.5, d: 0.12, h: 0.6, base: 1.2, name: "Mirror" } as Item,
  coatRack: { key: "coat_rack", cat: "generic", w: 0.4, d: 0.4, h: 1.7, name: "Coat rack" } as Item,
  // counter-top machines (our custom café models)
  espresso: { key: "cafe_espresso", cat: "espresso_machine", w: 0.72, d: 0.5, h: 0.45, name: "Espresso machine" } as Item,
  grinder: { key: "cafe_grinder", cat: "grinder", w: 0.2, d: 0.24, h: 0.55, name: "Coffee grinder" } as Item,
  blender: { key: "cafe_blender", cat: "blender", w: 0.2, d: 0.2, h: 0.65, name: "Blender" } as Item,
  pos: { key: "cafe_pos", cat: "cashier", w: 0.26, d: 0.2, h: 0.32, name: "POS terminal" } as Item,
  microwave: { key: "cafe_microwave", cat: "generic", w: 0.52, d: 0.38, h: 0.3, name: "Microwave" } as Item,
  toaster: { key: "toaster", cat: "generic", w: 0.3, d: 0.2, h: 0.22, name: "Toaster" } as Item,
  displayCase: { key: "cafe_display_case", cat: "display_case", w: 1.0, d: 0.6, h: 1.4, name: "Display case" } as Item,
  // facility / safety
  fireExt: { key: "cafe_fire_extinguisher", cat: "generic", w: 0.16, d: 0.16, h: 0.5, name: "Fire extinguisher" } as Item,
  panel: { key: "cafe_electrical_panel", cat: "generic", w: 0.36, d: 0.12, h: 0.5, base: 1.0, name: "Electrical panel" } as Item,
  // wall decor + lighting (parametric unless a key is given)
  pendant: { key: "", cat: "pendant_light", w: 0.32, d: 0.32, h: 0.45, name: "Pendant light" } as Item,
  wallArt: { key: "", cat: "menu_board", w: 0.6, d: 0.05, h: 0.55, base: 1.45, name: "Framed art" } as Item,
  menuBoard: { key: "", cat: "menu_board", w: 1.3, d: 0.05, h: 0.6, base: 1.75, name: "Menu board" } as Item,
  sconce: { key: "wall_lamp", cat: "generic", w: 0.18, d: 0.12, h: 0.28, base: 1.95, name: "Wall lamp" } as Item,
  sign: { key: "cafe_signage", cat: "signage", w: 0.9, d: 0.06, h: 0.3, base: 2.0, name: "Café sign" } as Item,
  wallShelf: { key: "cafe_shelving", cat: "shelving", w: 0.9, d: 0.28, h: 0.7, base: 1.1, name: "Wall shelf" } as Item,
};

// ---- wall decor + lighting (fills bare walls, lights the tables) ----
const roomOfPos = (scene: CafeScene, p: Vec2): Room | undefined =>
  scene.rooms.find((r) => r.polygon.length >= 3 && pointInPoly(r.polygon, p[0], p[1]));

function pendantsOverTables(scene: CafeScene, out: Fixture[]) {
  for (const t of scene.fixtures) {
    if (t.category !== "table") continue;
    const room = scene.rooms.find((r) => r.id === t.roomId) ?? roomOfPos(scene, t.position);
    if (!room || room.category === "seating_outdoor") continue; // outdoors uses umbrellas
    const ch = room.ceilingHeight > 0 ? room.ceilingHeight : 3.0;
    out.push(mkProp(I.pendant, room.id, t.position, 0, ch - 0.55));
  }
}

function menuOverCounters(scene: CafeScene, out: Fixture[]) {
  for (const room of scene.rooms) {
    if (room.category !== "service_counter") continue;
    const counters = scene.fixtures.filter(
      (f) => f.category === "counter" && (f.roomId === room.id || pointInPoly(room.polygon, f.position[0], f.position[1])),
    );
    if (!counters.length) continue;
    const c = counters.sort((a, b) => b.footprint[0] - a.footprint[0])[0];
    out.push(mkProp(I.menuBoard, room.id, c.position, c.rotation, I.menuBoard.base ?? 1.75));
  }
}

/** Spread framed art + wall sconces along the longest walls of a guest room. */
function decorateWalls(room: Room, out: Fixture[]) {
  const edges = roomEdges(room).slice(0, 2); // the two longest walls only
  for (const e of edges) {
    if (e.len < 1.8) continue;
    for (let s = 1.4; s <= e.len - 1.2; s += 3.0) {
      const pos = add(add(e.a, mul(e.dir, s)), mul(e.n, 0.07));
      if (pointInPoly(room.polygon, pos[0], pos[1])) out.push(mkProp(I.wallArt, room.id, pos, facingDeg(e.n), I.wallArt.base ?? 1.45));
    }
    for (let s = 2.9; s <= e.len - 1.2; s += 4.2) {
      const pos = add(add(e.a, mul(e.dir, s)), mul(e.n, 0.05));
      if (pointInPoly(room.polygon, pos[0], pos[1])) out.push(mkProp(I.sconce, room.id, pos, facingDeg(e.n), I.sconce.base ?? 1.95));
    }
  }
}

function featureSign(scene: CafeScene, out: Fixture[]) {
  const room = scene.rooms.find((r) => r.category === "seating_indoor") ?? scene.rooms.find((r) => r.category === "service_counter");
  if (!room) return;
  const e = roomEdges(room)[0];
  if (!e || e.len < 1.2) return;
  const pos = add(add(e.a, mul(e.dir, e.len / 2)), mul(e.n, 0.08));
  if (pointInPoly(room.polygon, pos[0], pos[1])) out.push(mkProp(I.sign, room.id, pos, facingDeg(e.n), I.sign.base ?? 2.0));
}

/**
 * Counter-top appliances: max footprint (so the model doesn't scale up huge) + the fact that they
 * belong ON a counter. Floor-standing units (fridge, oven, display case…) are deliberately excluded.
 */
const COUNTERTOP = new Map<FixtureCategory, [number, number]>([
  ["espresso_machine", [0.78, 0.56]],
  ["grinder", [0.24, 0.26]],
  ["blender", [0.22, 0.22]],
  ["mixer", [0.3, 0.3]],
  ["boiler", [0.42, 0.36]],
  ["cashier", [0.34, 0.3]],
]);

const MIN_TABLE = 0.65; // a 2-top is ~0.7 m; parsed symbols often come in at 0.4-0.5 and render tiny

/** Point → segment: distance, normalised parameter t, and the closest point. */
function segProj(p: Vec2, a: Vec2, b: Vec2): { d: number; t: number; pt: Vec2 } {
  const abx = b[0] - a[0], aby = b[1] - a[1];
  const l2 = abx * abx + aby * aby || 1e-9;
  let t = ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / l2;
  t = Math.max(0, Math.min(1, t));
  const pt: Vec2 = [a[0] + abx * t, a[1] + aby * t];
  return { d: Math.hypot(p[0] - pt[0], p[1] - pt[1]), t, pt };
}

interface CounterSeg { h: number; a: Vec2; b: Vec2 }
/** A counter as a line segment along its length (footprint[0] runs along its rotation axis). */
function counterSeg(c: Fixture): CounterSeg {
  const r = ((c.rotation ?? 0) * Math.PI) / 180;
  const ax: Vec2 = [Math.cos(r), Math.sin(r)];
  const half = c.footprint[0] / 2;
  return {
    h: c.height ?? 0.9,
    a: [c.position[0] - ax[0] * half, c.position[1] - ax[1] * half],
    b: [c.position[0] + ax[0] * half, c.position[1] + ax[1] * half],
  };
}

/**
 * Normalise counter-top equipment and tables:
 *  1. clamp oversized appliance footprints (the model scales to the footprint → "giant grinder");
 *  2. where wall-lined equipment has NO counter beneath it, synthesise a back-counter run along that
 *     wall spanning the items (the L-shaped worktop the drawing implies but the parser missed);
 *  3. snap every counter-top item ONTO its counter (project onto the counter's centre line) and lift
 *     it to the worktop height — and never lift an item that has nothing underneath it (no floating);
 *  4. enforce a minimum table size.
 */
export function elevateCounterTopItems(scene: CafeScene): CafeScene {
  let fixtures: Fixture[] = scene.fixtures.map((f) => {
    const cap = COUNTERTOP.get(f.category);
    if (cap) return { ...f, footprint: [Math.min(f.footprint[0], cap[0]), Math.min(f.footprint[1], cap[1])] as Vec2 };
    if (f.category === "table") {
      return { ...f, footprint: [Math.max(f.footprint[0], MIN_TABLE), Math.max(f.footprint[1], MIN_TABLE)] as Vec2 };
    }
    return f;
  });

  const nearestCounter = (p: Vec2, segs: CounterSeg[], within: number) => {
    let best: ({ s: CounterSeg } & ReturnType<typeof segProj>) | null = null;
    for (const s of segs) {
      const r = segProj(p, s.a, s.b);
      if (r.d < within && (!best || r.d < best.d)) best = { ...r, s };
    }
    return best;
  };

  // --- 2) synthesise back-counter runs for wall-lined appliances with nothing beneath ---------
  let segs = fixtures.filter((f) => f.category === "counter").map(counterSeg);
  const orphans = fixtures.filter((f) => COUNTERTOP.has(f.category) && !nearestCounter(f.position, segs, 0.5));
  const byWall = new Map<number, { f: Fixture; t: number; n: Vec2 }[]>();
  for (const f of orphans) {
    let best: ({ i: number } & ReturnType<typeof segProj>) | null = null;
    for (let i = 0; i < scene.walls.length; i++) {
      const r = segProj(f.position, scene.walls[i].a, scene.walls[i].b);
      if (r.d < 0.9 && (best === null || r.d < best.d)) best = { ...r, i };
    }
    if (best === null) continue;
    const n = norm(sub(f.position, best.pt)); // inward: from the wall toward the item
    if (!byWall.has(best.i)) byWall.set(best.i, []);
    byWall.get(best.i)!.push({ f, t: best.t, n });
  }
  const synth: Fixture[] = [];
  let k = 0;
  for (const [wi, items] of byWall) {
    const w = scene.walls[wi];
    const L = len(sub(w.b, w.a));
    const dir = norm(sub(w.b, w.a));
    items.sort((x, y) => x.t - y.t);
    let run: typeof items = [];
    const flush = () => {
      if (!run.length) return;
      const t0 = Math.max(0, run[0].t * L - 0.35);
      const t1 = Math.min(L, run[run.length - 1].t * L + 0.35);
      const span = Math.max(1.0, t1 - t0);
      const n = run[0].n;
      const depth = 0.6;
      const mid = add(w.a, mul(dir, (t0 + t1) / 2));
      const center = add(mid, mul(n, (w.thickness ?? 0.15) / 2 + depth / 2));
      const axis: Vec2 = [n[1], -n[0]]; // long axis whose left-perpendicular is the inward normal
      synth.push({
        id: `fx_backcounter_${k++}`,
        name: "Back counter (auto)",
        category: "counter",
        roomId: run[0].f.roomId,
        position: [round2(center[0]), round2(center[1])],
        rotation: Math.round((Math.atan2(axis[1], axis[0]) * 180) / Math.PI),
        footprint: [round2(span), depth],
        height: 0.9,
        baseHeight: 0,
        modelKey: "cafe_counter",
        placedBy: "design",
        confidence: 0.5,
        source: { system: 2, method: "design" },
      });
      run = [];
    };
    for (const it of items) {
      if (run.length && (it.t - run[run.length - 1].t) * L > 1.5) flush();
      run.push(it);
    }
    flush();
  }
  fixtures = [...fixtures, ...synth];

  // --- 3) snap + lift onto a counter that is actually underneath; otherwise stay on the floor ---
  segs = fixtures.filter((f) => f.category === "counter").map(counterSeg);
  fixtures = fixtures.map((f) => {
    if (!COUNTERTOP.has(f.category)) return f;
    const hit = nearestCounter(f.position, segs, 0.75);
    if (!hit) return { ...f, baseHeight: 0 };
    return { ...f, position: [round2(hit.pt[0]), round2(hit.pt[1])] as Vec2, baseHeight: hit.s.h };
  });
  return { ...scene, fixtures };
}

/** Only add a "singleton" appliance if the room doesn't already have one. */
const SINGLETON = new Set<FixtureCategory>(["fridge", "freezer", "oven", "sink", "dishwasher", "toilet", "espresso_machine"]);

export function furnishScene(scene: CafeScene): Fixture[] {
  _seq = 0;
  const out: Fixture[] = [];
  const occ: Disc[] = scene.fixtures.map((f) => discOf(f.position, f.footprint[0], f.footprint[1]));
  // scene-wide categories already present (so we never duplicate parsed counter machines that sit
  // on a room boundary and get missed by the per-room check)
  const sceneHas = new Set<FixtureCategory>(scene.fixtures.map((f) => f.category));

  // per-room equipment (seating is handled separately by rearrangeSeating, before this runs)
  for (const room of scene.rooms) {
    if (room.polygon.length < 3) continue;
    const have = new Set(roomFixtures(scene, room).map((f) => f.category));
    const keep = (its: Item[]) => its.filter((it) => !(SINGLETON.has(it.cat) && have.has(it.cat)));

    switch (room.category) {
      case "kitchen": {
        lineAlongWalls(room, keep([I.stove, I.fridge, I.freezer, I.sink, I.dishwasher, I.prepCab, I.crockery]), occ, out);
        lineAlongWalls(room, [I.hood], occ, out); // wall-mounted high
        cornerProps(room, [I.trashcan, I.box, I.fireExt], occ, out);
        break;
      }
      case "preparation": {
        lineAlongWalls(room, keep([I.prepCab, I.sink, I.dishwasher, I.shelving, I.crockery]), occ, out);
        placeOnCounters(scene, room, onlyMissing([I.grinder, I.blender, I.toaster, I.microwave], sceneHas), occ, out);
        cornerProps(room, [I.trashcan, I.fireExt, I.panel], occ, out);
        break;
      }
      case "service_counter": {
        placeOnCounters(scene, room, onlyMissing([I.espresso, I.grinder, I.pos], sceneHas), occ, out);
        lineAlongWalls(room, onlyMissing([I.displayCase], sceneHas).concat([I.crockery]), occ, out);
        cornerProps(room, [I.fireExt], occ, out);
        break;
      }
      case "wc":
      case "wc_disabled": {
        lineAlongWalls(room, keep([I.toilet, I.basin]), occ, out);
        lineAlongWalls(room, [I.mirror], occ, out);
        cornerProps(room, [I.trashcan], occ, out);
        break;
      }
      case "storage": {
        lineAlongWalls(room, [I.shelving, I.shelving, I.crockery], occ, out);
        cornerProps(room, [I.box, I.box], occ, out);
        break;
      }
      case "seating_indoor": {
        cornerProps(room, [I.plant, I.plant], occ, out);
        break;
      }
      case "seating_outdoor": {
        cornerProps(room, [I.plant], occ, out);
        break;
      }
      case "entrance": {
        cornerProps(room, [I.plant, I.coatRack], occ, out);
        break;
      }
      default:
        break;
    }
  }

  // decor + lighting so walls/ceiling don't read empty
  pendantsOverTables(scene, out);
  menuOverCounters(scene, out);
  for (const room of scene.rooms) {
    // guest-facing rooms only; service-counter walls are already lined with equipment.
    if (room.category === "seating_indoor" || room.category === "entrance") {
      decorateWalls(room, out);
    }
  }
  featureSign(scene, out);
  return out;
}
