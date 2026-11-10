// Hand-authored Coffee Berry CaféScene for Phase 1 (the 3D Rendering Engine).
//
// IMPORTANT: this is a clean, REPRESENTATIVE reconstruction based on the real drawing set
// (sheets A01/A02/A04/A09) — headline dimensions and the real equipment legend are used, but
// exact wall coordinates are approximated by hand. Phase 2's parser will produce the true,
// surveyed geometry into this same CafeScene shape. The renderer does not care which produced it.

import type {
  CafeScene,
  Fixture,
  FixtureCategory,
  LightSource,
  Provenance,
  Vec2,
} from "@/types/cafescene";

const SRC: Provenance = { system: 1, method: "manual_edit", note: "hand-authored Phase 1 scene" };

let seq = 0;
const fid = (p: string) => `${p}_${++seq}`;

// ---- fixture builder helpers --------------------------------------------------

function fx(
  category: FixtureCategory,
  name: string,
  position: Vec2,
  footprint: Vec2,
  opts: Partial<Fixture> = {},
): Fixture {
  return {
    id: fid("fx"),
    name,
    category,
    position,
    rotation: opts.rotation ?? 0,
    footprint,
    height: opts.height,
    baseHeight: opts.baseHeight,
    roomId: opts.roomId,
    legendNo: opts.legendNo,
    assetId: opts.assetId,
    placedBy: opts.placedBy ?? "design",
    confidence: opts.confidence ?? 1,
    source: SRC,
  };
}

/** A café table with chairs around it. */
function seating(cx: number, cy: number, roomId: string, chairs = 4): Fixture[] {
  const out: Fixture[] = [fx("table", "Café table", [cx, cy], [0.7, 0.7], { roomId, height: 0.74 })];
  const offs: Vec2[] = [
    [0, -0.58],
    [0, 0.58],
    [-0.58, 0],
    [0.58, 0],
  ];
  for (let i = 0; i < chairs; i++) {
    const [ox, oy] = offs[i];
    out.push(fx("chair", "Chair", [cx + ox, cy + oy], [0.45, 0.45], { roomId, height: 0.9 }));
  }
  return out;
}

// ---- fixtures -----------------------------------------------------------------

const fixtures: Fixture[] = [];

// L-shaped service counter (two runs meeting at the top-left corner of the hall)
fixtures.push(
  fx("counter", "Service counter (back run)", [3.5, 5.9], [6.4, 0.8], {
    roomId: "rm_hall",
    height: 1.05,
    placedBy: "parse",
    confidence: 0.85,
  }),
);
fixtures.push(
  fx("counter", "Service counter (side run)", [0.7, 3.2], [0.8, 4.8], {
    roomId: "rm_hall",
    height: 1.05,
    placedBy: "parse",
    confidence: 0.85,
  }),
);

// Equipment on / near the counter — linked to the real legend numbers (A01/A09)
const onCounter = { roomId: "rm_hall", baseHeight: 1.05, placedBy: "parse" as const };
fixtures.push(
  fx("espresso_machine", "La Cimbali M100 espresso machine", [2.2, 5.9], [0.8, 0.58], {
    ...onCounter,
    legendNo: "9",
    height: 0.55,
    confidence: 0.8,
  }),
  fx("grinder", "Coffee grinder F83", [3.0, 5.95], [0.3, 0.45], { ...onCounter, legendNo: "10", height: 0.5 }),
  fx("grinder", "Coffee grinder F4 Eco", [3.4, 5.95], [0.3, 0.45], { ...onCounter, legendNo: "11", height: 0.5 }),
  fx("cooling_case", "Cooling display case 108x58", [5.2, 5.9], [1.1, 0.58], { ...onCounter, legendNo: "3", height: 0.6 }),
  fx("cashier", "Cashier", [6.2, 5.9], [0.5, 0.5], { ...onCounter, legendNo: "2", height: 0.3 }),
  fx("sink", "Sink 24x33.5", [0.7, 2.0], [0.5, 0.4], { ...onCounter, legendNo: "6", height: 0.25 }),
  fx("ice_maker", "Ice maker Scotsman", [0.7, 4.2], [0.5, 0.55], { ...onCounter, legendNo: "23", height: 0.5 }),
);

// Grab'n'go cooling case (floor standing) near entrance
fixtures.push(
  fx("cooling_case", "Grab'n'Go cooling display 130x83", [8.6, 5.9], [1.3, 0.83], {
    roomId: "rm_hall",
    legendNo: "1",
    height: 1.5,
    placedBy: "parse",
  }),
);

// 65" monitor on the wall behind the counter
fixtures.push(
  fx("monitor", 'Monitor 65"', [4.0, 6.45], [1.4, 0.08], {
    roomId: "rm_hall",
    legendNo: "22",
    baseHeight: 1.7,
    height: 0.8,
    placedBy: "parse",
  }),
);

// Menu board + shelving on the back wall
fixtures.push(
  fx("menu_board", "Menu board", [2.0, 6.45], [2.2, 0.06], { roomId: "rm_hall", baseHeight: 1.6, height: 1.0 }),
  fx("shelving", "Back-bar shelving", [0.2, 4.0], [0.3, 2.4], { roomId: "rm_hall", height: 1.8 }),
);

// Preparation room equipment (floor standing) — A01 legend
fixtures.push(
  fx("oven", "Oven H90 267DW", [7.2, 8.6], [0.9, 0.8], { roomId: "rm_prep", legendNo: "25", height: 0.9, placedBy: "parse" }),
  fx("freezer", "Freezer 1 door 620lt", [7.2, 7.1], [0.8, 0.8], { roomId: "rm_prep", legendNo: "24", height: 1.8, placedBy: "parse" }),
  fx("freezer", "Freezer 300lt", [8.1, 7.1], [0.7, 0.8], { roomId: "rm_prep", legendNo: "27", height: 1.5, placedBy: "parse" }),
  fx("dishwasher", "Dishwasher", [9.3, 8.6], [0.6, 0.6], { roomId: "rm_prep", legendNo: "26", height: 0.85, placedBy: "parse" }),
  fx("generic", "Construction table", [8.5, 7.9], [1.6, 0.7], { roomId: "rm_prep", height: 0.9 }),
);

// WC (disabled) fixtures
fixtures.push(
  fx("generic", "WC", [10.4, 8.7], [0.45, 0.65], { roomId: "rm_wc", height: 0.42 }),
  fx("sink", "WC sink", [10.4, 7.0], [0.45, 0.35], { roomId: "rm_wc", height: 0.85 }),
);

// Indoor seating grid in the hall
const hallTables: Vec2[] = [
  [2.5, 1.3],
  [4.3, 1.3],
  [6.1, 1.3],
  [7.9, 1.3],
  [9.6, 1.3],
  [2.5, 3.3],
  [4.3, 3.3],
  [6.1, 3.3],
  [7.9, 3.3],
];
for (const [x, y] of hallTables) fixtures.push(...seating(x, y, "rm_hall", 4));

// Banquette along the east wall
fixtures.push(
  fx("banquette", "Banquette seating", [10.6, 3.2], [0.45, 4.2], { roomId: "rm_hall", height: 0.95 }),
);

// Planters in the hall
fixtures.push(
  fx("plant", "Floor plant", [0.4, 0.5], [0.5, 0.5], { roomId: "rm_hall", height: 1.3 }),
  fx("plant", "Floor plant", [10.5, 0.5], [0.5, 0.5], { roomId: "rm_hall", height: 1.3 }),
);

// Pendant light fixtures (visual) over the counter and tables
const pendantSpots: Vec2[] = [
  [2.2, 5.9],
  [4.5, 5.9],
  [3.4, 3.3],
  [7.0, 3.3],
  [5.0, 1.3],
  [8.5, 1.3],
];
for (const [x, y] of pendantSpots)
  fixtures.push(fx("pendant_light", "Pendant lamp", [x, y], [0.3, 0.3], { roomId: "rm_hall", baseHeight: 2.2, height: 0.35 }));

// Outdoor seating + planters
const outdoorTables: Vec2[] = [
  [2.0, -1.8],
  [5.0, -1.8],
  [8.0, -1.8],
  [2.0, -4.0],
  [5.0, -4.0],
  [8.0, -4.0],
];
for (const [x, y] of outdoorTables) fixtures.push(...seating(x, y, "rm_outdoor", 2));
for (const x of [1, 3, 5, 7, 9])
  fixtures.push(fx("plant", "Planter", [x, -5.7], [0.5, 0.5], { roomId: "rm_outdoor", height: 0.9 }));

// ---- lights -------------------------------------------------------------------

const lights: LightSource[] = pendantSpots.map((p, i) => ({
  id: `lt_pendant_${i + 1}`,
  type: "pendant",
  position: p,
  mountHeight: 2.2,
  intensity: 6,
  colorTempK: 3000,
  source: SRC,
}));
lights.push({ id: "lt_daylight", type: "daylight", intensity: 1.1, colorTempK: 5600, source: SRC });

// ---- scene --------------------------------------------------------------------

export const coffeeBerryScene: CafeScene = {
  schemaVersion: "1.0",
  project: {
    id: "proj_coffeeberry_leo",
    name: "Coffee Berry — Leo-Center Leonberg",
    units: "m",
    datum: { description: "SW corner of the main seating hall, floor level +0.00", planOrigin: [0, 0] },
    drawnScale: "1:50",
    confidenceOverall: 0.85,
    createdAt: "2026-11-03T00:00:00Z",
    schemaVersion: "1.0",
  },
  pages: [
    { id: "pg_a01", role: "floor_plan", sourceFile: "CB_Leocenter-A01-rev02.jpg", language: "el" },
    { id: "pg_a02", role: "section", sourceFile: "CB_Leocenter-A02-rev02.jpg" },
    { id: "pg_a04", role: "ceiling_plan", sourceFile: "CB_Leocenter-A04-rev02.jpg" },
    { id: "pg_a09", role: "detail", sourceFile: "CB_Leocenter-A09-rev02.jpg" },
  ],
  legend: [
    { id: "lg_1", no: "1", name: "Grab'n'Go cooling display case 130x83", category: "cooling_case", source: SRC },
    { id: "lg_2", no: "2", name: "Cashier", category: "cashier", source: SRC },
    { id: "lg_3", no: "3", name: "Cooling display case 108x58", category: "cooling_case", source: SRC },
    { id: "lg_6", no: "6", name: "Sink 24x33.5", category: "sink", source: SRC },
    { id: "lg_9", no: "9", name: "Professional coffee machine La Cimbali M100 HD DT/3", category: "espresso_machine", source: SRC },
    { id: "lg_10", no: "10", name: "Coffee grinder F83", category: "grinder", source: SRC },
    { id: "lg_11", no: "11", name: "Coffee grinder F4 Eco", category: "grinder", source: SRC },
    { id: "lg_22", no: "22", name: 'Monitor 65"', category: "monitor", source: SRC },
    { id: "lg_23", no: "23", name: "Ice maker Scotsman", category: "ice_maker", source: SRC },
    { id: "lg_24", no: "24", name: "Freezer 1 door 620lt", category: "freezer", source: SRC },
    { id: "lg_25", no: "25", name: "Oven H90 267DW", category: "oven", source: SRC },
    { id: "lg_26", no: "26", name: "Dishwasher", category: "dishwasher", source: SRC },
    { id: "lg_27", no: "27", name: "Freezer 300lt", category: "freezer", source: SRC },
  ],
  walls: [
    // exterior envelope (L-shape)
    { id: "w_s", a: [0, 0], b: [11, 0], thickness: 0.2, height: 3.35, exterior: true, confidence: 0.95, source: SRC },
    { id: "w_e", a: [11, 0], b: [11, 9.2], thickness: 0.2, height: 3.35, exterior: true, confidence: 0.95, source: SRC },
    { id: "w_n_boh", a: [11, 9.2], b: [6.5, 9.2], thickness: 0.2, height: 3.0, exterior: true, confidence: 0.9, source: SRC },
    { id: "w_step", a: [6.5, 9.2], b: [6.5, 6.6], thickness: 0.2, height: 3.0, exterior: true, confidence: 0.9, source: SRC },
    { id: "w_n_hall", a: [6.5, 6.6], b: [0, 6.6], thickness: 0.2, height: 3.35, exterior: true, confidence: 0.9, source: SRC },
    { id: "w_w", a: [0, 6.6], b: [0, 0], thickness: 0.2, height: 3.35, exterior: true, confidence: 0.95, source: SRC },
    // interior partitions
    { id: "w_part", a: [6.5, 6.6], b: [11, 6.6], thickness: 0.15, height: 3.0, confidence: 0.85, source: SRC },
    { id: "w_wc", a: [9.8, 6.6], b: [9.8, 9.2], thickness: 0.12, height: 2.6, confidence: 0.85, source: SRC },
  ],
  openings: [
    // storefront (south wall) — windows + entrance
    { id: "op_w1", type: "window", wallId: "w_s", offset: 0.8, width: 2.0, height: 2.2, sillHeight: 0.4, confidence: 0.9, source: SRC },
    { id: "op_w2", type: "window", wallId: "w_s", offset: 3.2, width: 2.0, height: 2.2, sillHeight: 0.4, confidence: 0.9, source: SRC },
    { id: "op_w3", type: "window", wallId: "w_s", offset: 5.4, width: 1.5, height: 2.2, sillHeight: 0.4, confidence: 0.85, source: SRC },
    { id: "op_entrance", type: "door", wallId: "w_s", offset: 7.3, width: 1.4, height: 2.3, swing: "right_in", confidence: 0.9, source: SRC },
    { id: "op_w4", type: "window", wallId: "w_s", offset: 9.0, width: 1.5, height: 2.2, sillHeight: 0.4, confidence: 0.85, source: SRC },
    // west wall window
    { id: "op_w5", type: "window", wallId: "w_w", offset: 2.0, width: 2.0, height: 2.2, sillHeight: 0.4, confidence: 0.85, source: SRC },
    // interior doors
    { id: "op_prep", type: "door", wallId: "w_part", offset: 0.5, width: 1.0, height: 2.1, swing: "left_in", confidence: 0.85, source: SRC },
    { id: "op_wc", type: "door", wallId: "w_wc", offset: 1.3, width: 0.9, height: 2.1, swing: "left_in", confidence: 0.8, source: SRC },
  ],
  rooms: [
    { id: "rm_hall", name: "Main seating hall", category: "seating_indoor", polygon: [[0, 0], [11, 0], [11, 6.6], [0, 6.6]], ceilingHeight: 3.35, floorMaterialId: "mat_floor_stone", confidence: 0.9, source: SRC },
    { id: "rm_prep", name: "Preparation Room", category: "preparation", polygon: [[6.5, 6.6], [9.8, 6.6], [9.8, 9.2], [6.5, 9.2]], ceilingHeight: 3.0, confidence: 0.85, source: SRC },
    { id: "rm_wc", name: "WC (disabled)", category: "wc_disabled", polygon: [[9.8, 6.6], [11, 6.6], [11, 9.2], [9.8, 9.2]], ceilingHeight: 2.6, confidence: 0.8, source: SRC },
    { id: "rm_outdoor", name: "Outdoor seating", category: "seating_outdoor", polygon: [[0, -6], [11, -6], [11, 0], [0, 0]], ceilingHeight: 0, floorMaterialId: "mat_paving", confidence: 0.8, source: SRC },
  ],
  fixtures,
  lights,
  materials: [
    { id: "mat_floor_stone", role: "floor", preset: "flagstone_beige", baseColor: "#c7b299", roughness: 0.9 },
    { id: "mat_paving", role: "floor", preset: "paving_grey", baseColor: "#9a9690", roughness: 0.95 },
  ],
  design: {
    style: "coffee-berry",
    palette: [
      { name: "warm oak", hex: "#c89b63" },
      { name: "raw concrete", hex: "#cfcabf" },
      { name: "dark frame grey", hex: "#3b3f42" },
    ],
    surfaceMaterials: { floor: "mat_floor_stone" },
    mood: { colorTempK: 3000, brightness: 0.75, notes: "warm, exposed-ceiling café per A03" },
    assets: [],
    source: SRC,
  },
  issues: [
    { id: "iss_1", severity: "info", message: "Phase 1 hand-authored scene — geometry is representative, not surveyed.", raisedBy: 3 },
  ],
};
