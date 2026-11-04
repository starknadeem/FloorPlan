// Walkable-tour model derived from a CafeScene.
//
// Everything here is pure data + math (no three.js, no React) so it can be unit-tested and reused
// by the Blender tour route later. All coordinates are WORLD xz (worldX = planX, worldZ = -planY),
// the same frame the three.js scene renders in, so the walk controller never converts.

import type { CafeScene, Fixture, FixtureCategory, Room, RoomCategory, Vec2 } from "@/types/cafescene";
import { fixtureHeight, pointInPolygon, polygonCentroid } from "@/lib/geometry";

export const PLAYER_RADIUS = 0.18;
export const EYE_HEIGHT = 1.6;
const CELL = 0.15; // nav-grid resolution in metres (fine enough to see 0.4 m gaps between fixtures)
const ZONE_MARGIN = 0.35; // how far outside a room polygon still counts as "inside" (door gaps)

export type XZ = [number, number];

export interface TourStop {
  id: string;
  roomId: string;
  /** short chip label */
  name: string;
  /** story card heading */
  title: string;
  /** story card body */
  text: string;
  pos: XZ;
  /** world point the camera settles on when it arrives */
  look: [number, number, number];
  /** false when no walkable route connects this room to the rest (the tour jumps there instead) */
  reachable: boolean;
}

export interface TourHotspot {
  id: string;
  pos: [number, number, number];
  title: string;
  text: string;
}

export interface MapRoom {
  id: string;
  category: RoomCategory;
  pts: XZ[];
}
export interface MapRect {
  x: number;
  z: number;
  w: number;
  d: number;
  /** radians, world Y rotation */
  rot: number;
}
export interface MapWall {
  a: XZ;
  b: XZ;
  t: number;
}

export interface Bounds {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

export interface TourModel {
  nav: Nav;
  stops: TourStop[];
  hotspots: TourHotspot[];
  bounds: Bounds;
  map: { rooms: MapRoom[]; rects: MapRect[]; walls: MapWall[] };
}

/* ------------------------------------------------------------------ */
/* collision + navigation                                               */
/* ------------------------------------------------------------------ */

interface WallSeg {
  id: string;
  ax: number;
  az: number;
  ux: number;
  uz: number;
  len: number;
  t: number;
  /** passable intervals (metres from a) — doors / open arches */
  open: [number, number][];
}

interface DoorMat {
  x: number;
  z: number;
  ux: number;
  uz: number;
  half: number;
}

interface Block {
  id: string;
  x: number;
  z: number;
  hw: number;
  hd: number;
  c: number;
  s: number;
  /** extra clearance around the piece (0 for chairs: you brush past them) */
  pad: number;
}

/** Fixtures that never block walking (ceiling / wall mounted or decorative). */
const NON_BLOCKING = new Set<FixtureCategory>(["pendant_light", "menu_board", "signage", "monitor"]);

function planToWorldPt(p: Vec2): XZ {
  return [p[0], -p[1]];
}

class MinHeap {
  private a: { k: number; v: number }[] = [];
  get size() {
    return this.a.length;
  }
  push(k: number, v: number) {
    const a = this.a;
    a.push({ k, v });
    let i = a.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (a[p].k <= a[i].k) break;
      [a[p], a[i]] = [a[i], a[p]];
      i = p;
    }
  }
  pop(): number {
    const a = this.a;
    const top = a[0].v;
    const last = a.pop()!;
    if (a.length) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        const r = l + 1;
        let m = i;
        if (l < a.length && a[l].k < a[m].k) m = l;
        if (r < a.length && a[r].k < a[m].k) m = r;
        if (m === i) break;
        [a[m], a[i]] = [a[i], a[m]];
        i = m;
      }
    }
    return top;
  }
}

export class Nav {
  readonly rooms: { room: Room; pts: XZ[] }[];
  private walls: WallSeg[] = [];
  private blocks: Block[] = [];
  private doorMats: DoorMat[] = [];
  readonly bounds: Bounds;
  private nx: number;
  private nz: number;
  private grid: Uint8Array; // 1 = free
  private comp: Int32Array; // connected-component label per cell (-1 = blocked)
  private mainComp = -1; // the largest walkable component

  constructor(scene: CafeScene) {
    this.rooms = scene.rooms
      .filter((r) => r.polygon.length >= 3)
      .map((r) => ({ room: r, pts: r.polygon.map(planToWorldPt) }));

    // walls with their passable intervals
    for (const w of scene.walls) {
      if ((w.baseHeight ?? 0) > 1.0) continue; // headers / bulkheads don't block
      const a = planToWorldPt(w.a);
      const b = planToWorldPt(w.b);
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (len < 1e-4) continue;
      const open: [number, number][] = scene.openings
        .filter((o) => o.wallId === w.id && (o.type === "door" || o.type === "opening"))
        .map((o) => [o.offset, o.offset + o.width]);
      const ux = (b[0] - a[0]) / len, uz = (b[1] - a[1]) / len;
      this.walls.push({ id: w.id, ax: a[0], az: a[1], ux, uz, len, t: Math.max(0.05, w.thickness), open });
      for (const [o0, o1] of open) {
        const mid = (o0 + o1) / 2;
        this.doorMats.push({ x: a[0] + ux * mid, z: a[1] + uz * mid, ux, uz, half: (o1 - o0) / 2 });
      }
    }

    for (const f of scene.fixtures) {
      if (NON_BLOCKING.has(f.category)) continue;
      if ((f.baseHeight ?? 0) >= 1.2) continue; // shelves / signs above head height
      let [w, d] = f.footprint;
      let pad = PLAYER_RADIUS;
      if (f.category === "umbrella") {
        w = 0.14;
        d = 0.14; // only the pole blocks
      } else if (f.category === "chair" || f.category === "stool") {
        // Rows of chairs must not fuse into a wall: block just the seat, no clearance.
        w *= 0.6;
        d *= 0.6;
        pad = 0;
      }
      const r = (f.rotation * Math.PI) / 180;
      this.blocks.push({ id: f.id, x: f.position[0], z: -f.position[1], hw: Math.max(0.05, w / 2), hd: Math.max(0.05, d / 2), c: Math.cos(r), s: Math.sin(r), pad });
    }

    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (const r of this.rooms)
      for (const p of r.pts) {
        if (p[0] < minX) minX = p[0];
        if (p[0] > maxX) maxX = p[0];
        if (p[1] < minZ) minZ = p[1];
        if (p[1] > maxZ) maxZ = p[1];
      }
    if (!isFinite(minX)) {
      minX = -5; maxX = 5; minZ = -5; maxZ = 5;
    }
    const m = 1.6;
    this.bounds = { minX: minX - m, maxX: maxX + m, minZ: minZ - m, maxZ: maxZ + m };
    this.nx = Math.max(1, Math.ceil((this.bounds.maxX - this.bounds.minX) / CELL));
    this.nz = Math.max(1, Math.ceil((this.bounds.maxZ - this.bounds.minZ) / CELL));
    this.grid = new Uint8Array(this.nx * this.nz);
    for (let j = 0; j < this.nz; j++)
      for (let i = 0; i < this.nx; i++) {
        const [x, z] = this.cellCenter(i, j);
        this.grid[j * this.nx + i] = this.free(x, z) ? 1 : 0;
      }
    // label connected components so stops can be placed where you can actually walk to
    this.comp = new Int32Array(this.nx * this.nz).fill(-1);
    let label = 0, bestN = 0;
    const stack: number[] = [];
    for (let c0 = 0; c0 < this.grid.length; c0++) {
      if (this.grid[c0] !== 1 || this.comp[c0] !== -1) continue;
      let n = 0;
      stack.push(c0);
      this.comp[c0] = label;
      while (stack.length) {
        const c = stack.pop()!;
        n++;
        const i = c % this.nx, j = (c / this.nx) | 0;
        for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
          const ni = i + di, nj = j + dj;
          if (!this.isFreeCell(ni, nj)) continue;
          const k = nj * this.nx + ni;
          if (this.comp[k] !== -1) continue;
          this.comp[k] = label;
          stack.push(k);
        }
      }
      if (n > bestN) { bestN = n; this.mainComp = label; }
      label++;
    }
  }

  /** Is this spot on the main walkable network (reachable from the biggest open area)? */
  inMain(x: number, z: number): boolean {
    const [i, j] = this.cellOf(x, z);
    return this.isFreeCell(i, j) && this.comp[j * this.nx + i] === this.mainComp;
  }

  /** Which room contains the point (strictly inside the polygon). */
  roomAt(x: number, z: number): Room | null {
    const py = -z;
    for (const r of this.rooms) if (pointInPolygon(r.room.polygon, x, py)) return r.room;
    return null;
  }

  private inZone(x: number, z: number): boolean {
    // The whole site is walkable (rooms plus the pavement / forecourt between them); walls do the
    // separating. ZONE_MARGIN keeps a thin band just outside the bounds so door thresholds work.
    const b = this.bounds;
    return x > b.minX + ZONE_MARGIN && x < b.maxX - ZONE_MARGIN && z > b.minZ + ZONE_MARGIN && z < b.maxZ - ZONE_MARGIN;
  }

  /** Door "mats": fixtures never block the metre either side of a door, so a badly placed piece can't trap you. */
  private inDoorMat(x: number, z: number): boolean {
    for (const m of this.doorMats) {
      const dx = x - m.x, dz = z - m.z;
      const u = dx * m.ux + dz * m.uz; // along the wall
      const v = -dx * m.uz + dz * m.ux; // across the wall
      if (Math.abs(u) <= m.half && Math.abs(v) <= 1.0) return true;
    }
    return false;
  }

  /** Why can't I stand here? (debug / tests) */
  explain(x: number, z: number): string {
    if (!this.inZone(x, z)) return "outside site";
    const R = PLAYER_RADIUS;
    for (const b of this.blocks) {
      const dx = x - b.x, dz = z - b.z;
      const u = dx * b.c + dz * b.s, v = -dx * b.s + dz * b.c;
      if (Math.abs(u) < b.hw + b.pad && Math.abs(v) < b.hd + b.pad && !this.inDoorMat(x, z)) return `fixture ${b.id} at (${b.x.toFixed(2)},${b.z.toFixed(2)}) ${(b.hw * 2).toFixed(2)}x${(b.hd * 2).toFixed(2)}`;
    }
    for (const w of this.walls) {
      const dx = x - w.ax, dz = z - w.az;
      const u = dx * w.ux + dz * w.uz;
      const uc = Math.max(0, Math.min(w.len, u));
      if (Math.hypot(x - (w.ax + w.ux * uc), z - (w.az + w.uz * uc)) < w.t / 2 + R && !w.open.some(([a, b]) => u >= a && u <= b)) return `wall ${w.id} (u=${u.toFixed(2)})`;
    }
    return "free";
  }

  /** Can a person stand at this world xz? */
  free(x: number, z: number): boolean {
    if (!this.inZone(x, z)) return false;
    const R = PLAYER_RADIUS;
    for (const b of this.blocks) {
      // Fixtures.tsx renders each fixture with rotation.y = -rotation, so undo that: local = R_y(+r) · (world delta)
      const dx = x - b.x;
      const dz = z - b.z;
      const u = dx * b.c + dz * b.s;
      const v = -dx * b.s + dz * b.c;
      if (Math.abs(u) < b.hw + b.pad && Math.abs(v) < b.hd + b.pad && !this.inDoorMat(x, z)) return false;
    }
    for (const w of this.walls) {
      const dx = x - w.ax;
      const dz = z - w.az;
      const u = dx * w.ux + dz * w.uz;
      const uc = Math.max(0, Math.min(w.len, u));
      const px = w.ax + w.ux * uc;
      const pz = w.az + w.uz * uc;
      if (Math.hypot(x - px, z - pz) < w.t / 2 + R) {
        let through = false;
        for (const [o0, o1] of w.open) if (u >= o0 && u <= o1) { through = true; break; }
        if (!through) return false;
      }
    }
    return true;
  }

  /** Straight-line walkability between two points. */
  lineOfSight(a: XZ, b: XZ): boolean {
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const n = Math.max(1, Math.ceil(d / 0.1));
    for (let k = 0; k <= n; k++) {
      const t = k / n;
      if (!this.free(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)) return false;
    }
    return true;
  }

  private cellCenter(i: number, j: number): XZ {
    return [this.bounds.minX + (i + 0.5) * CELL, this.bounds.minZ + (j + 0.5) * CELL];
  }
  private cellOf(x: number, z: number): [number, number] {
    return [
      Math.max(0, Math.min(this.nx - 1, Math.floor((x - this.bounds.minX) / CELL))),
      Math.max(0, Math.min(this.nz - 1, Math.floor((z - this.bounds.minZ) / CELL))),
    ];
  }
  private isFreeCell(i: number, j: number): boolean {
    return i >= 0 && j >= 0 && i < this.nx && j < this.nz && this.grid[j * this.nx + i] === 1;
  }

  /** Nearest free standing spot to (x,z), optionally restricted by a predicate (e.g. "in this room"). */
  nearestFree(x: number, z: number, accept?: (x: number, z: number) => boolean, maxRadiusCells = 40): XZ | null {
    if (this.free(x, z) && (!accept || accept(x, z))) return [x, z];
    const [ci, cj] = this.cellOf(x, z);
    for (let r = 0; r <= maxRadiusCells; r++) {
      let best: XZ | null = null;
      let bestD = Infinity;
      for (let dj = -r; dj <= r; dj++)
        for (let di = -r; di <= r; di++) {
          if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
          const i = ci + di, j = cj + dj;
          if (!this.isFreeCell(i, j)) continue;
          const c = this.cellCenter(i, j);
          if (accept && !accept(c[0], c[1])) continue;
          const d = Math.hypot(c[0] - x, c[1] - z);
          if (d < bestD) { bestD = d; best = c; }
        }
      if (best) return best;
    }
    return null;
  }

  /** A* over the nav grid + string-pulling. Returns null when unreachable. */
  path(from: XZ, to: XZ): XZ[] | null {
    if (this.lineOfSight(from, to)) return [from, to];
    const s = this.nearestFree(from[0], from[1], undefined, 6);
    const t = this.nearestFree(to[0], to[1], undefined, 6);
    if (!s || !t) return null;
    const [si, sj] = this.cellOf(s[0], s[1]);
    const [ti, tj] = this.cellOf(t[0], t[1]);
    const idx = (i: number, j: number) => j * this.nx + i;
    const N = this.nx * this.nz;
    const g = new Float32Array(N).fill(Infinity);
    const came = new Int32Array(N).fill(-1);
    const closed = new Uint8Array(N);
    const h = (i: number, j: number) => {
      const dx = Math.abs(i - ti), dz = Math.abs(j - tj);
      return Math.max(dx, dz) + (Math.SQRT2 - 1) * Math.min(dx, dz);
    };
    const open = new MinHeap();
    g[idx(si, sj)] = 0;
    open.push(h(si, sj), idx(si, sj));
    const goal = idx(ti, tj);
    let found = false;
    while (open.size) {
      const cur = open.pop();
      if (cur === goal) { found = true; break; }
      if (closed[cur]) continue;
      closed[cur] = 1;
      const ci = cur % this.nx, cj = (cur / this.nx) | 0;
      for (let dj = -1; dj <= 1; dj++)
        for (let di = -1; di <= 1; di++) {
          if (!di && !dj) continue;
          const ni = ci + di, nj = cj + dj;
          if (!this.isFreeCell(ni, nj)) continue;
          // no corner cutting
          if (di && dj && (!this.isFreeCell(ci + di, cj) || !this.isFreeCell(ci, cj + dj))) continue;
          const n = idx(ni, nj);
          if (closed[n]) continue;
          const ng = g[cur] + (di && dj ? Math.SQRT2 : 1);
          if (ng < g[n]) {
            g[n] = ng;
            came[n] = cur;
            open.push(ng + h(ni, nj), n);
          }
        }
    }
    if (!found) return null;
    const cells: XZ[] = [];
    for (let c = goal; c !== -1; c = came[c]) cells.push(this.cellCenter(c % this.nx, (c / this.nx) | 0));
    cells.reverse();
    const raw: XZ[] = [from, ...cells, to];
    // string pulling: skip ahead as far as line-of-sight allows
    const out: XZ[] = [raw[0]];
    let i = 0;
    while (i < raw.length - 1) {
      let j = raw.length - 1;
      while (j > i + 1 && !this.lineOfSight(raw[i], raw[j])) j--;
      out.push(raw[j]);
      i = j;
    }
    return out;
  }
}

/* ------------------------------------------------------------------ */
/* stops, narration, hotspots                                           */
/* ------------------------------------------------------------------ */

const ROOM_ORDER: Record<RoomCategory, number> = {
  entrance: 0,
  seating_outdoor: 1,
  seating_indoor: 2,
  service_counter: 3,
  corridor: 4,
  preparation: 5,
  kitchen: 6,
  storage: 7,
  wc: 8,
  wc_disabled: 9,
  other: 10,
};

const LOOK_WEIGHT: Partial<Record<FixtureCategory, number>> = {
  espresso_machine: 4,
  counter: 3,
  display_case: 3,
  cooling_case: 2.5,
  cashier: 2,
  banquette: 2,
  table: 1,
  shelving: 1,
  oven: 1,
  fridge: 0.6,
  umbrella: 0.8,
  sofa: 1.5,
};

const HOT: FixtureCategory[] = [
  "espresso_machine", "grinder", "display_case", "cooling_case", "cashier", "counter", "banquette", "shelving",
  "signage", "menu_board", "oven", "ice_maker", "dishwasher", "fridge", "umbrella",
];

const CAT_LABEL: Record<FixtureCategory, string> = {
  counter: "counter", espresso_machine: "espresso machine", grinder: "grinder", display_case: "display case",
  cooling_case: "cooling display", fridge: "fridge", freezer: "freezer", ice_maker: "ice maker", sink: "sink",
  dishwasher: "dishwasher", oven: "oven", boiler: "water boiler", blender: "blender", mixer: "mixer", monitor: "menu screen",
  table: "table", chair: "chair", stool: "stool", sofa: "sofa", banquette: "banquette", shelving: "shelving",
  menu_board: "menu board", signage: "signage", plant: "plant", pendant_light: "pendant light", umbrella: "umbrella",
  cashier: "till", toilet: "toilet", generic: "fixture",
};

const ROOM_LEAD: Record<RoomCategory, string> = {
  seating_indoor: "The dining room",
  seating_outdoor: "The terrace",
  service_counter: "The bar and order counter",
  preparation: "Back of house: the prep room",
  kitchen: "The kitchen",
  storage: "Storage",
  wc: "The washroom",
  wc_disabled: "The accessible washroom",
  corridor: "The corridor",
  entrance: "The entrance",
  other: "This room",
};

function polyArea(p: Vec2[]): number {
  let a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) a += (p[j][0] + p[i][0]) * (p[j][1] - p[i][1]);
  return Math.abs(a / 2);
}

function shortName(room: Room): string {
  const first = room.name.split(/[/(–—-]/)[0].trim();
  if (first.length > 0 && first.length <= 22) return first;
  const lbl = room.category.replace(/_/g, " ");
  return lbl.charAt(0).toUpperCase() + lbl.slice(1);
}

function plural(n: number, one: string, many = one + "s"): string {
  return `${n} ${n === 1 ? one : many}`;
}

function cleanName(f: Fixture): string {
  // "Professional coffee machine La Cimbali M100 HD DT/3" → keep it, but strip trailing dimensions like "130x83"
  return f.name.replace(/\s+\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*(?:cm|mm)?\s*$/i, "").trim();
}

function describeRoom(room: Room, inRoom: Fixture[]): string {
  const count = (c: FixtureCategory) => inRoom.filter((f) => f.category === c).length;
  const bits: string[] = [];
  const tables = count("table");
  const chairs = count("chair") + count("stool");
  if (tables) bits.push(`${plural(tables, "table")}${chairs ? ` with ${plural(chairs, "seat")}` : ""}`);
  else if (chairs) bits.push(plural(chairs, "seat"));
  if (count("banquette")) bits.push("a banquette along the wall");
  if (count("sofa")) bits.push("lounge seating");
  if (count("umbrella")) bits.push(plural(count("umbrella"), "umbrella"));

  const equipment = inRoom.filter(
    (f) => !["table", "chair", "stool", "banquette", "sofa", "umbrella", "pendant_light", "plant", "generic", "menu_board", "signage"].includes(f.category),
  );
  // unique, most interesting first (legend items first, then by category weight)
  const seen = new Set<string>();
  const names: string[] = [];
  for (const f of [...equipment].sort((a, b) => (LOOK_WEIGHT[b.category] ?? 0) - (LOOK_WEIGHT[a.category] ?? 0))) {
    const n = cleanName(f) || CAT_LABEL[f.category];
    const key = n.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    names.push(n.length > 40 ? CAT_LABEL[f.category] : n);
    if (names.length >= 5) break;
  }
  if (names.length) {
    const more = equipment.length - names.length;
    bits.push(`${names.join(", ")}${more > 0 ? ` and ${more} more` : ""}`);
  }
  if (count("pendant_light")) bits.push("pendant lights overhead");
  if (count("plant")) bits.push("greenery");

  const lead = ROOM_LEAD[room.category] ?? "This room";
  const size = `${polyArea(room.polygon).toFixed(0)} m²`;
  if (!bits.length) return `${lead}, about ${size}. Walk around with W A S D or click the floor.`;
  const body = bits.map((b, i) => (i === 0 ? b.charAt(0).toUpperCase() + b.slice(1) : b)).join(". ");
  return `${lead}, about ${size}. ${body}.`;
}

function fixturesInRoom(scene: CafeScene, room: Room): Fixture[] {
  return scene.fixtures.filter((f) => (f.roomId ? f.roomId === room.id : pointInPolygon(room.polygon, f.position[0], f.position[1])));
}

export function buildTourModel(scene: CafeScene): TourModel {
  const nav = new Nav(scene);

  const rooms = [...scene.rooms]
    .filter((r) => r.polygon.length >= 3)
    .sort((a, b) => (ROOM_ORDER[a.category] ?? 10) - (ROOM_ORDER[b.category] ?? 10) || polyArea(b.polygon) - polyArea(a.polygon));

  const stops: TourStop[] = [];
  for (const room of rooms) {
    const c = polygonCentroid(room.polygon);
    const cw: XZ = [c[0], -c[1]];
    const inThisRoom = (x: number, z: number) => nav.roomAt(x, z)?.id === room.id;
    const walkable = (x: number, z: number) => inThisRoom(x, z) && nav.inMain(x, z);
    let reachable = true;
    let pos = nav.nearestFree(cw[0], cw[1], walkable);
    if (!pos) {
      // room is cut off (no door, or furniture seals it): still show it, the tour will jump there
      reachable = false;
      pos = nav.nearestFree(cw[0], cw[1], inThisRoom);
    }
    if (!pos) continue;
    const inRoom = fixturesInRoom(scene, room);

    // look at the weighted centre of interest in the room, else across the room's long side
    let lx = 0, lz = 0, lw = 0;
    for (const f of inRoom) {
      const w = LOOK_WEIGHT[f.category] ?? 0;
      if (!w) continue;
      lx += f.position[0] * w;
      lz += -f.position[1] * w;
      lw += w;
    }
    let look: [number, number, number];
    if (lw > 0) look = [lx / lw, 1.15, lz / lw];
    else {
      let far: XZ = cw, fd = -1;
      for (const p of room.polygon) {
        const wp: XZ = [p[0], -p[1]];
        const d = Math.hypot(wp[0] - pos[0], wp[1] - pos[1]);
        if (d > fd) { fd = d; far = wp; }
      }
      look = [far[0], 1.3, far[1]];
    }
    // Frame the view: if the point of interest is right in front of us, step back from it (staying
    // in the room and on the walkable network) so the camera sees the whole counter / table group.
    let dist = Math.hypot(look[0] - pos[0], look[2] - pos[1]);
    if (dist < 2.4 && dist > 0.05) {
      const ux = (pos[0] - look[0]) / dist, uz = (pos[1] - look[2]) / dist;
      for (const back of [2.6, 2.0, 1.5]) {
        const cand: XZ = [look[0] + ux * back, look[2] + uz * back];
        const p2 = nav.nearestFree(cand[0], cand[1], reachable ? walkable : inThisRoom, 6);
        if (p2 && Math.hypot(p2[0] - look[0], p2[1] - look[2]) > dist + 0.3) {
          pos = p2;
          dist = Math.hypot(look[0] - pos[0], look[2] - pos[1]);
          break;
        }
      }
    }
    if (dist < 1.0) {
      const ang = Math.atan2(look[2] - pos[1], look[0] - pos[0]);
      look = [pos[0] + Math.cos(ang) * 2.5, look[1], pos[1] + Math.sin(ang) * 2.5];
    }

    stops.push({
      id: room.id,
      roomId: room.id,
      name: shortName(room),
      title: room.name,
      text: describeRoom(room, inRoom),
      pos,
      look,
      reachable,
    });
  }

  // hotspots: one marker per distinct named piece of key equipment
  const hotspots: TourHotspot[] = [];
  const seen = new Set<string>();
  const roomName = (f: Fixture) => scene.rooms.find((r) => r.id === f.roomId)?.name ?? nav.roomAt(f.position[0], -f.position[1])?.name;
  for (const cat of HOT) {
    for (const f of scene.fixtures.filter((x) => x.category === cat)) {
      const n = cleanName(f) || CAT_LABEL[cat];
      const key = `${cat}|${n.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const h = fixtureHeight(f);
      const base = f.baseHeight ?? 0;
      const top = cat === "umbrella" ? base + 1.9 : base + h;
      const dims = `${f.footprint[0].toFixed(2)} × ${f.footprint[1].toFixed(2)} m, ${h.toFixed(2)} m high`;
      const where = roomName(f);
      const legend = f.legendNo ? `Legend item ${f.legendNo}. ` : "";
      hotspots.push({
        id: f.id,
        pos: [f.position[0], Math.min(top + 0.12, 2.6), -f.position[1]],
        title: n,
        text: `${legend}${CAT_LABEL[cat].charAt(0).toUpperCase() + CAT_LABEL[cat].slice(1)}${where ? ` in the ${where}` : ""}. ${dims}.${f.placedBy === "design" ? " Added by the design pass." : ""}`,
      });
      if (hotspots.length >= 16) break;
    }
    if (hotspots.length >= 16) break;
  }

  // minimap data
  const mapRooms: MapRoom[] = nav.rooms.map((r) => ({ id: r.room.id, category: r.room.category, pts: r.pts }));
  const rects: MapRect[] = scene.fixtures
    .filter((f) => !NON_BLOCKING.has(f.category) && f.category !== "chair" && f.category !== "stool" && f.category !== "plant")
    .map((f) => ({
      x: f.position[0],
      z: -f.position[1],
      w: f.category === "umbrella" ? 0.3 : f.footprint[0],
      d: f.category === "umbrella" ? 0.3 : f.footprint[1],
      rot: (f.rotation * Math.PI) / 180, // canvas y = world z, and rotation.y = -r maps local +x to (cos r, sin r)
    }));
  const walls: MapWall[] = scene.walls.map((w) => ({ a: planToWorldPt(w.a), b: planToWorldPt(w.b), t: w.thickness }));

  return { nav, stops, hotspots, bounds: nav.bounds, map: { rooms: mapRooms, rects, walls } };
}

/** Human line for the ident card. */
export function whereLabel(nav: Nav, x: number, z: number): { prefix: string; name: string } {
  const r = nav.roomAt(x, z);
  if (!r) return { prefix: "You’re", name: "outside" };
  const outdoor = r.category === "seating_outdoor";
  return { prefix: outdoor ? "You’re on the" : "You’re in the", name: r.name };
}
