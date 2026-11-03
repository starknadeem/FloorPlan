// Convert a ParsedPlan (vision model output) into a valid CafeScene (schema v1.0).
// Assigns ids + provenance, coerces enum values, maps opening wallIndex -> wallId,
// and attaches validation issues. The result is always renderable.

import type {
  CafeScene,
  Fixture,
  FixtureCategory,
  LegendItem,
  Opening,
  OpeningType,
  Provenance,
  Room,
  RoomCategory,
  Vec2,
  Wall,
} from "@/types/cafescene";
import { validateScene } from "@/lib/validate";
import { regularizeScene } from "@/lib/regularize";
import {
  FIXTURE_CATEGORIES,
  OPENING_TYPES,
  ROOM_CATEGORIES,
  type ParsedPlan,
  type PPoint,
} from "./types";

const SRC: Provenance = { system: 1, method: "vision" };

const pt = (p: PPoint): Vec2 => [num(p?.x), num(p?.y)];
const num = (v: unknown, d = 0): number => (typeof v === "number" && isFinite(v) ? v : d);
const clamp01 = (v: unknown): number => Math.max(0, Math.min(1, num(v, 0.5)));

function coerceFixtureCat(c: string): FixtureCategory {
  return (FIXTURE_CATEGORIES as readonly string[]).includes(c) ? (c as FixtureCategory) : "generic";
}
function coerceRoomCat(c: string): RoomCategory {
  return (ROOM_CATEGORIES as readonly string[]).includes(c) ? (c as RoomCategory) : "other";
}
function coerceOpeningType(t: string): OpeningType {
  return (OPENING_TYPES as readonly string[]).includes(t) ? (t as OpeningType) : "opening";
}

export function parsedPlanToScene(plan: ParsedPlan, sourceFile: string): CafeScene {
  const walls: Wall[] = (plan.walls ?? []).map((w, i) => ({
    id: `w_${i}`,
    a: pt(w.a),
    b: pt(w.b),
    thickness: num(w.thickness, 0.2),
    height: num(w.height, 3.0),
    exterior: !!w.exterior,
    confidence: clamp01(w.confidence),
    source: SRC,
  }));

  const openings: Opening[] = (plan.openings ?? [])
    .map((o, i): Opening | null => {
      const w = walls[o.wallIndex];
      if (!w) return null; // dropped; validator will note missing wall separately
      return {
        id: `op_${i}`,
        type: coerceOpeningType(o.type),
        wallId: w.id,
        offset: num(o.offset, 0),
        width: num(o.width, 0.9),
        height: num(o.height, 2.1),
        sillHeight: o.sillHeight != null ? num(o.sillHeight) : undefined,
        confidence: clamp01(o.confidence),
        source: SRC,
      };
    })
    .filter((o): o is Opening => o !== null);

  const rooms: Room[] = (plan.rooms ?? []).map((r, i) => {
    const category = coerceRoomCat(r.category);
    // Outdoor areas have no ceiling, regardless of what the model reported.
    const ceilingHeight = category === "seating_outdoor" ? 0 : num(r.ceilingHeight, 3.0);
    return {
      id: `rm_${i}`,
      name: r.name || `Room ${i + 1}`,
      category,
      polygon: (r.polygon ?? []).map(pt),
      ceilingHeight,
      confidence: clamp01(r.confidence),
      source: SRC,
    };
  });

  const fixtures: Fixture[] = (plan.fixtures ?? []).map((f, i) => ({
    id: `fx_${i}`,
    legendNo: f.legendNo || undefined,
    name: f.name || "Fixture",
    category: coerceFixtureCat(f.category),
    position: pt(f.position),
    rotation: num(f.rotation, 0),
    footprint: [num(f.footprint?.w, 0.5), num(f.footprint?.d, 0.5)],
    height: f.height != null ? num(f.height) : undefined,
    baseHeight: f.baseHeight != null ? num(f.baseHeight) : undefined,
    placedBy: "parse",
    confidence: clamp01(f.confidence),
    source: SRC,
  }));

  const legend: LegendItem[] = (plan.legend ?? []).map((l, i) => ({
    id: `lg_${l.no ?? i}`,
    no: String(l.no ?? i),
    name: l.name || `Item ${i + 1}`,
    category: coerceFixtureCat(l.category),
    source: SRC,
  }));

  const rawScene: CafeScene = {
    schemaVersion: "1.0",
    project: {
      id: `proj_${Date.now()}`,
      name: plan.project?.name || "Uploaded floor plan",
      units: "m",
      datum: {
        description: plan.project?.datumDescription || "bottom-left interior corner",
        planOrigin: [0, 0],
      },
      drawnScale: plan.project?.drawnScale,
      confidenceOverall: clamp01(plan.project?.confidenceOverall),
      createdAt: new Date().toISOString(),
      schemaVersion: "1.0",
    },
    pages: [{ id: "pg_1", role: "floor_plan", sourceFile }],
    legend,
    walls,
    openings,
    rooms,
    fixtures,
    issues: [],
  };

  // Phase 2.1: regularize geometry (snap near-axis walls, weld corners, align shared coordinates)
  const scene = regularizeScene(rawScene);

  // model-reported issues + a regularization note + validator issues
  const modelIssues = (plan.issues ?? []).map((iss, i) => ({
    id: `mi_${i}`,
    severity: iss.severity ?? "info",
    message: iss.message ?? "",
    raisedBy: 1 as const,
  }));
  scene.issues = [
    ...modelIssues,
    {
      id: "reg_1",
      severity: "info" as const,
      message: "Geometry regularized: near-axis walls snapped and shared coordinates aligned (Phase 2.1).",
      raisedBy: 1 as const,
    },
    ...validateScene(scene),
  ];

  return scene;
}
