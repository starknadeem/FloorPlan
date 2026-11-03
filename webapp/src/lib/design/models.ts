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
   *  poke-through). "width" = scale uniformly so model width matches footprint width. */
  fit?: "width" | "contain";
}

const M = "/models/kenney";

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
};

/** Default model per category (first variant). Used when a fixture has no explicit modelKey. */
export const MODEL_REGISTRY: Partial<Record<FixtureCategory, ModelDef>> = {
  chair: MODEL_CATALOG.chair_cushion,
  stool: MODEL_CATALOG.stool_bar,
  sofa: MODEL_CATALOG.sofa,
  banquette: MODEL_CATALOG.bench_cushion,
  table: MODEL_CATALOG.table_round,
  fridge: MODEL_CATALOG.fridge,
  freezer: MODEL_CATALOG.fridge_large,
  ice_maker: MODEL_CATALOG.fridge_small,
  espresso_machine: MODEL_CATALOG.coffee_machine,
  grinder: MODEL_CATALOG.blender,
  blender: MODEL_CATALOG.blender,
  mixer: MODEL_CATALOG.blender,
  oven: MODEL_CATALOG.stove,
  sink: MODEL_CATALOG.kitchen_sink,
  dishwasher: MODEL_CATALOG.washer,
  shelving: MODEL_CATALOG.bookcase,
  plant: MODEL_CATALOG.plant_potted,
  monitor: MODEL_CATALOG.tv,
  toilet: MODEL_CATALOG.toilet,
  // Parametric fallbacks (kept on purpose): counter, cashier, display_case, cooling_case,
  // boiler, menu_board, signage, pendant_light, umbrella, generic.
};

/** Which catalog keys the AI layout pass may choose from, per category. */
export const VARIANTS_BY_CATEGORY: Partial<Record<FixtureCategory, string[]>> = {
  chair: ["chair_cushion", "chair_wood"],
  stool: ["stool_bar"],
  sofa: ["sofa", "sofa_long"],
  banquette: ["bench_cushion", "sofa_long"],
  table: ["table_round", "table_rect"],
  fridge: ["fridge", "fridge_large", "fridge_small"],
  freezer: ["fridge_large", "fridge"],
  ice_maker: ["fridge_small"],
  espresso_machine: ["coffee_machine"],
  grinder: ["blender"],
  blender: ["blender"],
  mixer: ["blender"],
  oven: ["stove"],
  sink: ["kitchen_sink", "bathroom_sink"],
  dishwasher: ["washer"],
  shelving: ["bookcase", "cabinet"],
  plant: ["plant_potted", "plant_small"],
  monitor: ["tv"],
  toilet: ["toilet"],
};

/** Resolve the model for a fixture: explicit modelKey wins, then the per-category default. */
export function resolveModel(category: FixtureCategory, modelKey?: string): ModelDef | undefined {
  if (modelKey && MODEL_CATALOG[modelKey]) return MODEL_CATALOG[modelKey];
  return MODEL_REGISTRY[category];
}
