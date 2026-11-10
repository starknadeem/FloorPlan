// Phase 4 — Interior Design Intelligence (System 2).
// Style presets (palette + materials + lighting mood) and the logic that writes a DesignSpec into
// a CafeScene and lets the design step add pendant lighting over indoor rooms.

import type { CafeScene, Fixture, LightSource, Provenance, Room, Vec2 } from "@/types/cafescene";
import { polygonCentroid, pointInPolygon } from "@/lib/geometry";

export interface StylePalette {
  key: string;
  name: string;
  floor: string;
  floorOutdoor: string;
  wall: string;
  ceiling: string;
  wood: string;
  woodDark: string;
  counterTop: string;
  metal: string; // dark metal (legs, frames)
  stainless: string; // equipment
  fabric: string; // upholstery
  plantPot: string;
  foliage: string;
  glass: string;
  accent: string;
  light: {
    colorTempK: number;
    ambient: number;
    hemiSky: string;
    hemiGround: string;
    hemi: number;
    dir: number;
    dirColor: string;
    pendant: string;
    pendantI: number;
    bg: string;
  };
}

export const STYLE_PRESETS: Record<string, StylePalette> = {
  // The client's brand standard, from their documents (CB Leo technical description + materials schedule):
  // Soulant grey floor, Vivechrome 30YY 58/082 walls, 96YR 09/033 dark ceiling, Brown Warmia Walnut joinery,
  // Sassiepietre Grigio stone bar, RAL 7021 frames. Lighting: ceiling spots + only 3 pendants, over the bench.
  "coffee-berry": {
    key: "coffee-berry",
    name: "Coffee Berry Standard",
    floor: "#9d9b96",
    floorOutdoor: "#9a9690",
    wall: "#d7c6ae",
    ceiling: "#5d534d",
    wood: "#6c5448",
    woodDark: "#4e3b30",
    counterTop: "#b1a9a0",
    metal: "#2e3234",
    stainless: "#a7acb0",
    fabric: "#d8cbb4",
    plantPot: "#a8a39a",
    foliage: "#4e7a46",
    glass: "#bcd4dd",
    accent: "#1b1b1b",
    light: {
      colorTempK: 3000,
      ambient: 0.34,
      hemiSky: "#fff3e0",
      hemiGround: "#b3a488",
      hemi: 0.62,
      dir: 1.2,
      dirColor: "#fff1dc",
      pendant: "#ffd49a",
      pendantI: 6,
      bg: "#e7e3da",
    },
  },
  "industrial-chic": {
    key: "industrial-chic",
    name: "Industrial Chic",
    floor: "#c3ae90",
    floorOutdoor: "#9a9690",
    wall: "#cac4b8",
    ceiling: "#b4b0a7",
    wood: "#c0894c",
    woodDark: "#7c5230",
    counterTop: "#d9d4cc",
    metal: "#3c3f42",
    stainless: "#a7acb0",
    fabric: "#6d5d47",
    plantPot: "#8a6a4a",
    foliage: "#4e7a46",
    glass: "#bcd4dd",
    accent: "#9a6b2f",
    light: {
      colorTempK: 3000,
      ambient: 0.32,
      hemiSky: "#fff3e0",
      hemiGround: "#b3a488",
      hemi: 0.62,
      dir: 1.25,
      dirColor: "#fff1dc",
      pendant: "#ffd49a",
      pendantI: 7,
      bg: "#e7e3da",
    },
  },
  scandinavian: {
    key: "scandinavian",
    name: "Scandinavian",
    floor: "#d9c4a0",
    floorOutdoor: "#b8b2a6",
    wall: "#eeece6",
    ceiling: "#f3f1ec",
    wood: "#d7b88a",
    woodDark: "#b89a6a",
    counterTop: "#efede8",
    metal: "#2f3133",
    stainless: "#b7bcc0",
    fabric: "#bcb6ac",
    plantPot: "#cfc7ba",
    foliage: "#6f9068",
    glass: "#cfe3ea",
    accent: "#8a9a7b",
    light: {
      colorTempK: 3600,
      ambient: 0.42,
      hemiSky: "#ffffff",
      hemiGround: "#cfc7b6",
      hemi: 0.8,
      dir: 1.2,
      dirColor: "#fbfaf6",
      pendant: "#ffe6c0",
      pendantI: 5.5,
      bg: "#eef0f0",
    },
  },
  "cozy-warm": {
    key: "cozy-warm",
    name: "Cozy Warm",
    floor: "#b5885a",
    floorOutdoor: "#9c8f7d",
    wall: "#cab79d",
    ceiling: "#c8bca4",
    wood: "#8a5a34",
    woodDark: "#5f3d22",
    counterTop: "#7a5236",
    metal: "#9a7b3f",
    stainless: "#aeaba2",
    fabric: "#9c5f44",
    plantPot: "#8a5a3a",
    foliage: "#5c7a4a",
    glass: "#cdd9d2",
    accent: "#b5542f",
    light: {
      colorTempK: 2700,
      ambient: 0.3,
      hemiSky: "#ffeccb",
      hemiGround: "#8f765a",
      hemi: 0.6,
      dir: 1.1,
      dirColor: "#ffe3bd",
      pendant: "#ffce8f",
      pendantI: 8,
      bg: "#efe6da",
    },
  },
};

export const DEFAULT_STYLE = "coffee-berry";

/** Brand rule (lighting drawing HM01): pendants hang only over the seating bench — three in a line, ~1 m apart. */
function benchPendantSpots(fixtures: Fixture[]): { pos: Vec2; roomId?: string }[] {
  const out: { pos: Vec2; roomId?: string }[] = [];
  for (const f of fixtures) {
    if (f.category !== "banquette") continue;
    const r = ((f.rotation ?? 0) * Math.PI) / 180;
    const along = f.footprint[0] >= f.footprint[1];
    const L = Math.max(f.footprint[0], f.footprint[1]);
    const ux = along ? Math.cos(r) : -Math.sin(r), uy = along ? Math.sin(r) : Math.cos(r);
    const n = 3, gap = Math.min(1.06, (L - 0.4) / (n - 1));
    for (let i = 0; i < n; i++) {
      const u = (i - (n - 1) / 2) * gap;
      out.push({ pos: [f.position[0] + ux * u, f.position[1] + uy * u], roomId: f.roomId });
    }
  }
  return out.slice(0, 3);
}

/** Resolve the active palette for a scene (from its design.style), with safe fallback. */
export function resolvePalette(scene: CafeScene): StylePalette {
  const key = scene.design?.style ?? DEFAULT_STYLE;
  return STYLE_PRESETS[key] ?? STYLE_PRESETS[DEFAULT_STYLE];
}

const DESIGN_SRC: Provenance = { system: 2, method: "design" };

/**
 * Apply a style to a scene: writes the DesignSpec, and (when the scene has no pendant lighting yet)
 * lets the design step add pendant lamps + point lights over the indoor rooms. Idempotent: re-applying
 * removes previously design-added pendants first.
 */
export function applyStyle(scene: CafeScene, key: string): CafeScene {
  const pal = STYLE_PRESETS[key] ?? STYLE_PRESETS[DEFAULT_STYLE];

  // strip previously design-added pendants / lights so re-applying is clean
  const baseFixtures = scene.fixtures.filter((f) => !f.id.startsWith("fxd_"));
  const baseLights = (scene.lights ?? []).filter((l) => !l.id.startsWith("ltd_"));

  const hasPendants = baseLights.some((l) => l.type === "pendant" || l.type === "point");
  const added: Fixture[] = [];
  const addedLights: LightSource[] = [];

  if (!hasPendants && pal.key === "coffee-berry") {
    let i = 0;
    // ceiling spots (light only, the fixture is flush) on a ~2 m grid in every lit room…
    for (const room of scene.rooms) {
      if (room.ceilingHeight <= 0) continue;
      for (const [x, y] of pendantSpotsForRoom(room.polygon)) {
        i++;
        addedLights.push({ id: `ltd_${i}`, type: "point", position: [x, y], mountHeight: room.ceilingHeight - 0.15,
          intensity: pal.light.pendantI * 0.8, colorTempK: pal.light.colorTempK, source: DESIGN_SRC });
      }
    }
    // …and exactly three pendants, over the bench
    for (const { pos, roomId } of benchPendantSpots(baseFixtures)) {
      i++;
      const room = scene.rooms.find((r) => r.id === roomId) ?? scene.rooms.find((r) => r.polygon.length >= 3 && pointInPolygon(r.polygon, pos[0], pos[1]));
      const mount = Math.max(1.8, (room?.ceilingHeight ?? 3.35) - 1.3);
      added.push({ id: `fxd_pend_${i}`, name: "Pendant lamp", category: "pendant_light", roomId: room?.id ?? roomId ?? "",
        position: pos, rotation: 0, footprint: [0.28, 0.28], height: 0.3, baseHeight: mount, placedBy: "design", confidence: 1, source: DESIGN_SRC });
      addedLights.push({ id: `ltd_${i}`, type: "pendant", position: pos, mountHeight: mount, intensity: pal.light.pendantI,
        colorTempK: pal.light.colorTempK, source: DESIGN_SRC });
    }
  } else if (!hasPendants) {
    let i = 0;
    for (const room of scene.rooms) {
      if (room.ceilingHeight <= 0) continue; // outdoor / no ceiling
      if (room.category === "wc" || room.category === "wc_disabled") continue;
      const spots = pendantSpotsForRoom(room.polygon);
      const mount = Math.max(1.8, room.ceilingHeight - 0.5);
      for (const [x, y] of spots) {
        i++;
        added.push({
          id: `fxd_pend_${i}`,
          name: "Pendant lamp",
          category: "pendant_light",
          roomId: room.id,
          position: [x, y],
          rotation: 0,
          footprint: [0.28, 0.28],
          height: 0.3,
          baseHeight: mount,
          placedBy: "design",
          confidence: 1,
          source: DESIGN_SRC,
        });
        addedLights.push({
          id: `ltd_${i}`,
          type: "pendant",
          position: [x, y],
          mountHeight: mount,
          intensity: pal.light.pendantI,
          colorTempK: pal.light.colorTempK,
          source: DESIGN_SRC,
        });
      }
    }
  }

  // design step also arranges chairs around tables
  const chairs = generateSeating(scene.rooms, baseFixtures);

  return {
    ...scene,
    fixtures: [...baseFixtures, ...added, ...chairs],
    lights: [...baseLights, ...addedLights],
    design: {
      style: pal.key,
      palette: [
        { name: "floor", hex: pal.floor },
        { name: "wall", hex: pal.wall },
        { name: "wood", hex: pal.wood },
        { name: "accent", hex: pal.accent },
        { name: "fabric", hex: pal.fabric },
      ],
      surfaceMaterials: {},
      mood: { colorTempK: pal.light.colorTempK, brightness: pal.light.dir, notes: pal.name },
      assets: [],
      source: DESIGN_SRC,
    },
  };
}

const dist2 = (a: Vec2, b: Vec2) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;

// furniture a chair must not overlap
const BLOCKER_CATS = new Set([
  "counter", "banquette", "sofa", "cooling_case", "display_case", "fridge", "freezer",
  "shelving", "sink", "oven", "dishwasher", "cashier", "ice_maker",
]);

/**
 * Design-time seating: place chairs around each table (inside the room, avoiding counters/walls).
 * Idempotent via the `fxd_` id prefix (stripped on re-apply). Skips tables that already have chairs.
 */
function generateSeating(rooms: Room[], fixtures: Fixture[]): Fixture[] {
  const tables = fixtures.filter((f) => f.category === "table");
  const existingChairs = fixtures.filter((f) => f.category === "chair" || f.category === "stool");
  const blockers = fixtures.filter((f) => BLOCKER_CATS.has(f.category));
  const out: Fixture[] = [];
  const CW = 0.46;
  const GAP = 0.3;
  let n = 0;

  for (const t of tables) {
    const room =
      rooms.find((r) => r.id === t.roomId) ??
      rooms.find((r) => pointInPolygon(r.polygon, t.position[0], t.position[1]));

    // already seated? (parsed chairs nearby)
    const near = existingChairs.filter((c) => dist2(c.position, t.position) < 1.3 * 1.3).length;
    if (near >= 2) continue;

    const [w, d] = t.footprint;
    const seats = Math.max(w, d) >= 1.1 ? 4 : 2;
    const ox = w / 2 + GAP + CW / 2;
    const oy = d / 2 + GAP + CW / 2;
    const offsets: Vec2[] =
      seats === 4
        ? [[0, oy], [0, -oy], [-ox, 0], [ox, 0]]
        : [[0, oy], [0, -oy]];

    for (const off of offsets) {
      const pos: Vec2 = [t.position[0] + off[0], t.position[1] + off[1]];
      if (room && !pointInPolygon(room.polygon, pos[0], pos[1])) continue; // outside room / into wall
      const blocked = blockers.some(
        (b) =>
          Math.abs(pos[0] - b.position[0]) < b.footprint[0] / 2 + CW / 2 &&
          Math.abs(pos[1] - b.position[1]) < b.footprint[1] / 2 + CW / 2,
      );
      if (blocked) continue;
      const dx = t.position[0] - pos[0];
      const dy = t.position[1] - pos[1];
      const rotation = (Math.atan2(-dx, dy) * 180) / Math.PI; // face the table
      n++;
      out.push({
        id: `fxd_chair_${n}`,
        name: "Chair",
        category: "chair",
        roomId: room?.id,
        position: pos,
        rotation,
        footprint: [CW, CW],
        height: 0.9,
        placedBy: "design",
        confidence: 1,
        source: DESIGN_SRC,
      });
    }
  }
  return out;
}

/** 1–4 evenly spread ceiling-light spots for a room polygon, based on its area/extent. */
function pendantSpotsForRoom(polygon: Vec2[]): Vec2[] {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of polygon) {
    minX = Math.min(minX, x); minY = Math.min(minY, y);
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  }
  const w = maxX - minX;
  const d = maxY - minY;
  const [cx, cy] = polygonCentroid(polygon);
  if (w < 3 && d < 3) return [[cx, cy]];
  const nx = Math.min(3, Math.max(1, Math.round(w / 3)));
  const ny = Math.min(3, Math.max(1, Math.round(d / 3)));
  const spots: Vec2[] = [];
  for (let ix = 0; ix < nx; ix++)
    for (let iy = 0; iy < ny; iy++) {
      spots.push([minX + (w * (ix + 1)) / (nx + 1), minY + (d * (iy + 1)) / (ny + 1)]);
    }
  return spots;
}
