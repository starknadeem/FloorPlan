// Phase 4.2 — real glTF models per fixture category + a variant catalog for the AI layout pass.
//
// Models: Kenney "Furniture Kit" (https://kenney.nl/assets/furniture-kit), licensed CC0
// (public domain, no attribution required). A cohesive, game-ready set so every fixture
// matches as one visual family. Files live in webapp/public/models/kenney/.
//
// Anything NOT covered here falls back to the built-in parametric model (FurnitureModels.tsx).
// We intentionally keep the parametric version for long/stretchy or special pieces
// (counter, cashier, glass display cases, menu boards, pendant lights, umbrellas) where a
// fixed-proportion mesh would distort or can't emit light.

import type { FixtureCategory } from "@/types/cafescene";

export interface ModelDef {
  url: string;
  /** degrees to rotate the model about Y so its "front" ends up facing local -Z,
   *  which — given the plan→world mapping (plan +Y → world -Z) — means the fixture's
   *  front faces plan +Y at rotation 0, per CAFESCENE_SCHEMA §1.1. */
  baseRotationDeg?: number;
  /** "contain" = scale uniformly to fit inside the footprint (no distortion, no wall
   *  poke-through). "width" = scale uniformly so model width matches footprint width.
   *  "stretch" = non-uniform: width AND depth match the footprint exactly (for boxy, long
   *  pieces like counters, where a 5 m bar must really be 5 m long). */
  fit?: "width" | "contain" | "stretch";
}

const M = "/models/kenney";
// Custom café fixture library — built in Blender (procedural + Poly Haven PBR), exported
// 1K/WebP GLB. Realistic, café-specific. Files in webapp/public/models/custom/.
const C = "/models/custom";

/**
 * Kenney Furniture Kit pieces are authored facing +Z. We need the "front" to face local
 * -Z, so directional pieces get a 180° base rotation. Flip this ONE constant to 0 if the
 * whole set turns out to face the wrong way in the rendered scene.
 */
export const KENNEY_FRONT_DEG = 180;
const F = KENNEY_FRONT_DEG;

/**
 * Every individual model, keyed by a friendly, stable name. The AI layout pass picks a
 * `modelKey` from VARIANTS_BY_CATEGORY; the renderer resolves it through this catalog.
 */
export const MODEL_CATALOG: Record<string, ModelDef> = {
  // seating
  chair_cushion: { url: `${M}/chairCushion.glb`, baseRotationDeg: F, fit: "contain" },
  chair_wood: { url: `${M}/chair.glb`, baseRotationDeg: F, fit: "contain" },
  stool_bar: { url: `${M}/stoolBar.glb`, baseRotationDeg: F, fit: "contain" },
  sofa: { url: `${M}/loungeSofa.glb`, baseRotationDeg: F, fit: "contain" },
  sofa_long: { url: `${M}/loungeSofaLong.glb`, baseRotationDeg: F, fit: "contain" },
  bench_cushion: { url: `${M}/benchCushion.glb`, baseRotationDeg: F, fit: "contain" },
  // tables
  table_round: { url: `${M}/tableRound.glb`, baseRotationDeg: 0, fit: "contain" },
  table_rect: { url: `${M}/table.glb`, baseRotationDeg: 0, fit: "contain" },
  // cold storage
  fridge: { url: `${M}/kitchenFridge.glb`, baseRotationDeg: F, fit: "contain" },
  fridge_large: { url: `${M}/kitchenFridgeLarge.glb`, baseRotationDeg: F, fit: "contain" },
  fridge_small: { url: `${M}/kitchenFridgeSmall.glb`, baseRotationDeg: F, fit: "contain" },
  // coffee / prep machines
  coffee_machine: { url: `${M}/kitchenCoffeeMachine.glb`, baseRotationDeg: F, fit: "contain" },
  blender: { url: `${M}/kitchenBlender.glb`, baseRotationDeg: F, fit: "contain" },
  // appliances
  stove: { url: `${M}/kitchenStove.glb`, baseRotationDeg: F, fit: "contain" },
  kitchen_sink: { url: `${M}/kitchenSink.glb`, baseRotationDeg: F, fit: "contain" },
  washer: { url: `${M}/washer.glb`, baseRotationDeg: F, fit: "contain" },
  cabinet: { url: `${M}/kitchenCabinet.glb`, baseRotationDeg: F, fit: "contain" },
  // fixtures / decor
  bookcase: { url: `${M}/bookcaseOpen.glb`, baseRotationDeg: F, fit: "contain" },
  plant_potted: { url: `${M}/pottedPlant.glb`, baseRotationDeg: 0, fit: "contain" },
  plant_small: { url: `${M}/plantSmall1.glb`, baseRotationDeg: 0, fit: "contain" },
  tv: { url: `${M}/televisionModern.glb`, baseRotationDeg: F, fit: "contain" },
  // washroom
  toilet: { url: `${M}/toilet.glb`, baseRotationDeg: F, fit: "contain" },
  bathroom_sink: { url: `${M}/bathroomSink.glb`, baseRotationDeg: F, fit: "contain" },
  mirror: { url: `${M}/bathroomMirror.glb`, baseRotationDeg: F, fit: "contain" },

  // extra props placed by the room-furnishing pass (referenced by modelKey)
  hood: { url: `${M}/hoodModern.glb`, baseRotationDeg: F, fit: "contain" },
  microwave: { url: `${M}/kitchenMicrowave.glb`, baseRotationDeg: F, fit: "contain" },
  toaster: { url: `${M}/toaster.glb`, baseRotationDeg: F, fit: "contain" },
  computer: { url: `${M}/computerScreen.glb`, baseRotationDeg: F, fit: "contain" },
  laptop: { url: `${M}/laptop.glb`, baseRotationDeg: F, fit: "contain" },
  crockery_cabinet: { url: `${M}/bookcaseClosedDoors.glb`, baseRotationDeg: F, fit: "contain" },
  wall_cabinet: { url: `${M}/kitchenCabinetUpper.glb`, baseRotationDeg: F, fit: "contain" },
  wall_cabinet_double: { url: `${M}/kitchenCabinetUpperDouble.glb`, baseRotationDeg: F, fit: "contain" },
  coat_rack: { url: `${M}/coatRackStanding.glb`, baseRotationDeg: 0, fit: "contain" },
  trashcan: { url: `${M}/trashcan.glb`, baseRotationDeg: 0, fit: "contain" },
  wall_lamp: { url: `${M}/lampWall.glb`, baseRotationDeg: F, fit: "contain" },
  box: { url: `${M}/cardboardBoxClosed.glb`, baseRotationDeg: 0, fit: "contain" },
  books: { url: `${M}/books.glb`, baseRotationDeg: 0, fit: "contain" },
  desk: { url: `${M}/desk.glb`, baseRotationDeg: F, fit: "contain" },
  desk_chair: { url: `${M}/chairDesk.glb`, baseRotationDeg: F, fit: "contain" },
  console: { url: `${M}/cabinetTelevision.glb`, baseRotationDeg: F, fit: "contain" },

  // ── Custom café library (webapp/public/models/custom/) ───────────────────────────
  // Directional pieces face +Z after glTF export → use F (180°); radially-symmetric → 0.
  cafe_chair: { url: `${C}/chair.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_table: { url: `${C}/table.glb`, baseRotationDeg: 0, fit: "contain" }, // client: Omicron pedestal, 60x60 top
  // Coffee Berry (client) standard furniture — webapp/blender/client_models.py builds these from 3DModels/
  cafe_stool: { url: `${C}/stool.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_chair_outdoor: { url: `${C}/chairOutdoor.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_table_round: { url: `${C}/tableRound.glb`, baseRotationDeg: 0, fit: "contain" },
  cafe_table_stand: { url: `${C}/tableStand.glb`, baseRotationDeg: 0, fit: "stretch" },
  cafe_counter: { url: `${C}/counter.glb`, baseRotationDeg: F, fit: "stretch" },
  cafe_cart: { url: `${C}/coffeeCart.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_sink: { url: `${C}/sink.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_handwash_sink: { url: `${C}/handWashSink.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_shelving: { url: `${C}/shelving.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_waste_bin: { url: `${C}/wasteBin.glb`, baseRotationDeg: 0, fit: "contain" },
  cafe_fridge: { url: `${C}/fridge.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_freezer: { url: `${C}/freezer.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_dishwasher: { url: `${C}/dishwasher.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_microwave: { url: `${C}/microwave.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_espresso: { url: `${C}/espressoMachine.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_grinder: { url: `${C}/coffeeGrinder.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_blender: { url: `${C}/blenderMachine.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_pos: { url: `${C}/posTerminal.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_display_case: { url: `${C}/displayCase.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_panini: { url: `${C}/paniniPress.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_water_filter: { url: `${C}/waterFilter.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_grease_trap: { url: `${C}/greaseTrap.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_electrical_panel: { url: `${C}/electricalPanel.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_fire_extinguisher: { url: `${C}/fireExtinguisher.glb`, baseRotationDeg: 0, fit: "contain" },
  cafe_hvac: { url: `${C}/hvacUnit.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_spotlights: { url: `${C}/spotlights.glb`, baseRotationDeg: 0, fit: "contain" },
  cafe_speaker: { url: `${C}/speaker.glb`, baseRotationDeg: F, fit: "contain" },
  cafe_signage: { url: `${C}/signage.glb`, baseRotationDeg: F, fit: "contain" },
};

/** Default model per category (first variant). Used when a fixture has no explicit modelKey. */
export const MODEL_REGISTRY: Partial<Record<FixtureCategory, ModelDef>> = {
  // Café-specific custom models now lead; Kenney kept as fallback/variants.
  chair: MODEL_CATALOG.cafe_chair,
  stool: MODEL_CATALOG.cafe_stool,
  sofa: MODEL_CATALOG.sofa,
  banquette: MODEL_CATALOG.bench_cushion,
  table: MODEL_CATALOG.cafe_table, // round bistro (real oak); revert to parametric by removing this line
  counter: MODEL_CATALOG.cafe_counter,
  cashier: MODEL_CATALOG.cafe_pos,
  fridge: MODEL_CATALOG.cafe_fridge,
  freezer: MODEL_CATALOG.cafe_freezer,
  ice_maker: MODEL_CATALOG.fridge_small,
  espresso_machine: MODEL_CATALOG.cafe_espresso,
  grinder: MODEL_CATALOG.cafe_grinder,
  blender: MODEL_CATALOG.cafe_blender,
  mixer: MODEL_CATALOG.cafe_blender,
  oven: MODEL_CATALOG.stove,
  sink: MODEL_CATALOG.cafe_sink,
  dishwasher: MODEL_CATALOG.cafe_dishwasher,
  display_case: MODEL_CATALOG.cafe_display_case,
  cooling_case: MODEL_CATALOG.cafe_display_case,
  shelving: MODEL_CATALOG.cafe_shelving,
  signage: MODEL_CATALOG.cafe_signage,
  plant: MODEL_CATALOG.plant_potted,
  monitor: MODEL_CATALOG.tv,
  toilet: MODEL_CATALOG.toilet,
  // Still parametric/fallback: boiler, menu_board, pendant_light, umbrella, generic.
  // Extra custom models reachable by modelKey (no 1:1 category): cafe_microwave,
  // cafe_panini, cafe_water_filter, cafe_grease_trap, cafe_electrical_panel,
  // cafe_fire_extinguisher, cafe_hvac, cafe_spotlights, cafe_speaker, cafe_cart,
  // cafe_handwash_sink, cafe_waste_bin.
};

/** Which catalog keys the AI layout pass may choose from, per category. */
export const VARIANTS_BY_CATEGORY: Partial<Record<FixtureCategory, string[]>> = {
  chair: ["cafe_chair", "cafe_chair_outdoor"],
  stool: ["cafe_stool", "stool_bar"],
  sofa: ["sofa", "sofa_long"],
  banquette: ["bench_cushion", "sofa_long"],
  table: ["cafe_table", "cafe_table_round", "cafe_table_stand"],
  counter: ["cafe_counter"],
  cashier: ["cafe_pos"],
  fridge: ["cafe_fridge", "fridge", "fridge_large"],
  freezer: ["cafe_freezer", "fridge_large"],
  ice_maker: ["fridge_small"],
  espresso_machine: ["cafe_espresso", "coffee_machine"],
  grinder: ["cafe_grinder"],
  blender: ["cafe_blender"],
  mixer: ["cafe_blender"],
  oven: ["cafe_microwave", "stove"],
  sink: ["cafe_sink", "cafe_handwash_sink", "kitchen_sink"],
  dishwasher: ["cafe_dishwasher", "washer"],
  display_case: ["cafe_display_case"],
  cooling_case: ["cafe_display_case"],
  shelving: ["cafe_shelving", "bookcase", "cabinet"],
  signage: ["cafe_signage"],
  plant: ["plant_potted", "plant_small"],
  monitor: ["tv"],
  toilet: ["toilet"],
};

/** Resolve the model for a fixture: explicit modelKey wins, then the per-category default. */
export function resolveModel(category: FixtureCategory, modelKey?: string): ModelDef | undefined {
  if (modelKey && MODEL_CATALOG[modelKey]) return MODEL_CATALOG[modelKey];
  return MODEL_REGISTRY[category];
}
