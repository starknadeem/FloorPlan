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
    modelKey: it.key,
    placedBy: "design",
    confidence: 0.6,
    source: { system: 2, method: "design" },
  };
}
const round2 = (n: number) => Math.round(n * 100) / 100;

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

const CHAIR: Item = { key: "chair_cushion", cat: "chair", w: 0.5, d: 0.5, h: 0.9, name: "Chair" };
function seatTables(scene: CafeScene, occ: Disc[], out: Fixture[]) {
  const roomsByTable = (f: Fixture) => scene.rooms.find((r) => pointInPoly(r.polygon, f.position[0], f.position[1]));
  for (const t of scene.fixtures) {
    if (t.category !== "table") continue;
    const room = scene.rooms.find((r) => r.id === t.roomId) ?? roomsByTable(t);
    // already has chairs nearby? skip
    const tr = 0.5 * Math.max(t.footprint[0], t.footprint[1]);
    const near = scene.fixtures.some(
      (c) => (c.category === "chair" || c.category === "stool") && len(sub(c.position, t.position)) < tr + 0.7,
    );
    if (near) continue;
    const off = tr + 0.34;
    const dirs: Vec2[] = [[0, 1], [0, -1], [1, 0], [-1, 0]];
    for (const dv of dirs) {
      const pos: Vec2 = [t.position[0] + dv[0] * off, t.position[1] + dv[1] * off];
      if (room && !pointInPoly(room.polygon, pos[0], pos[1])) continue;
      const disc = discOf(pos, CHAIR.w, CHAIR.d);
      if (hits(disc, occ)) continue;
      out.push(mkProp(CHAIR, room?.id ?? t.roomId ?? "rm", pos, facingDeg([-dv[0], -dv[1]])));
      occ.push(disc);
    }
  }
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
  stove: { key: "stove", cat: "oven", w: 0.9, d: 0.7, h: 0.9, name: "Stove" } as Item,
  fridge: { key: "fridge", cat: "fridge", w: 0.7, d: 0.7, h: 1.9, name: "Fridge" } as Item,
  freezer: { key: "fridge_large", cat: "freezer", w: 0.9, d: 0.72, h: 1.45, name: "Freezer" } as Item,
  sink: { key: "kitchen_sink", cat: "sink", w: 0.6, d: 0.6, h: 0.9, name: "Sink" } as Item,
  dishwasher: { key: "washer", cat: "dishwasher", w: 0.6, d: 0.62, h: 0.85, name: "Dishwasher" } as Item,
  prepCab: { key: "cabinet", cat: "counter", w: 1.0, d: 0.6, h: 0.9, name: "Prep counter" } as Item,
  crockery: { key: "crockery_cabinet", cat: "shelving", w: 0.7, d: 0.32, h: 1.9, name: "Crockery cabinet" } as Item,
  shelving: { key: "bookcase", cat: "shelving", w: 0.8, d: 0.3, h: 1.8, name: "Shelving" } as Item,
  trashcan: { key: "trashcan", cat: "generic", w: 0.45, d: 0.45, h: 0.9, name: "Bin" } as Item,
  hood: { key: "hood", cat: "generic", w: 0.9, d: 0.45, h: 0.45, base: 1.5, name: "Extractor hood" } as Item,
  box: { key: "box", cat: "generic", w: 0.45, d: 0.45, h: 0.6, name: "Storage box" } as Item,
  plant: { key: "plant_potted", cat: "plant", w: 0.45, d: 0.45, h: 1.1, name: "Plant" } as Item,
  toilet: { key: "toilet", cat: "toilet", w: 0.65, d: 0.72, h: 0.75, name: "Toilet" } as Item,
  basin: { key: "bathroom_sink", cat: "sink", w: 0.5, d: 0.42, h: 0.85, name: "Basin" } as Item,
  mirror: { key: "mirror", cat: "generic", w: 0.5, d: 0.12, h: 0.6, base: 1.2, name: "Mirror" } as Item,
  coatRack: { key: "coat_rack", cat: "generic", w: 0.4, d: 0.4, h: 1.7, name: "Coat rack" } as Item,
  // counter-top machines
  espresso: { key: "coffee_machine", cat: "espresso_machine", w: 0.55, d: 0.5, h: 0.5, name: "Espresso machine" } as Item,
  grinder: { key: "blender", cat: "grinder", w: 0.25, d: 0.25, h: 0.4, name: "Grinder" } as Item,
  pos: { key: "computer", cat: "monitor", w: 0.4, d: 0.2, h: 0.35, name: "POS terminal" } as Item,
  microwave: { key: "microwave", cat: "generic", w: 0.45, d: 0.35, h: 0.28, name: "Microwave" } as Item,
  toaster: { key: "toaster", cat: "generic", w: 0.3, d: 0.2, h: 0.22, name: "Toaster" } as Item,
};

/** Only add a "singleton" appliance if the room doesn't already have one. */
const SINGLETON = new Set<FixtureCategory>(["fridge", "freezer", "oven", "sink", "dishwasher", "toilet", "espresso_machine"]);

export function furnishScene(scene: CafeScene): Fixture[] {
  _seq = 0;
  const out: Fixture[] = [];
  const occ: Disc[] = scene.fixtures.map((f) => discOf(f.position, f.footprint[0], f.footprint[1]));

  // 1) seat every table (chairs are almost never in the parse)
  seatTables(scene, occ, out);

  // 2) per-room equipment
  for (const room of scene.rooms) {
    if (room.polygon.length < 3) continue;
    const have = new Set(roomFixtures(scene, room).map((f) => f.category));
    const keep = (its: Item[]) => its.filter((it) => !(SINGLETON.has(it.cat) && have.has(it.cat)));

    switch (room.category) {
      case "kitchen": {
        lineAlongWalls(room, keep([I.stove, I.fridge, I.freezer, I.sink, I.dishwasher, I.prepCab, I.crockery]), occ, out);
        lineAlongWalls(room, [I.hood], occ, out); // wall-mounted high
        cornerProps(room, [I.trashcan, I.box], occ, out);
        break;
      }
      case "preparation": {
        lineAlongWalls(room, keep([I.prepCab, I.sink, I.shelving, I.crockery]), occ, out);
        placeOnCounters(scene, room, [I.grinder, I.toaster, I.microwave], occ, out);
        cornerProps(room, [I.trashcan], occ, out);
        break;
      }
      case "service_counter": {
        placeOnCounters(scene, room, [I.espresso, I.grinder, I.pos], occ, out);
        lineAlongWalls(room, [I.crockery], occ, out);
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
  return out;
}
